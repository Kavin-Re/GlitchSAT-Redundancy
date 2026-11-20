"""SYNFI adapter.

SYNFI (lowRISC, Apache-2.0) is a third-party tool. This module does NOT contain SYNFI code. It
  (1) EXPORTS one of our fault sets (fault-campaign document, see campaign.py) as a SYNFI fault-model entry that
      replays exactly that set: explicit `fault_locations` + `simultaneous_faults` = set size,
  (2) READS SYNFI output (the per-model RESULT/EFFECTIVE lines written by compare/synfi_run/scripts/synfi_report.py,
      or SYNFI's own stock summary line) and
  (3) COMPARES SYNFI's counts and minimum fault count with our solver's.
Format facts used (all READ from compare/synfi_run/SYNFI_RESULT.md and the specs in compare/synfi_run/inputs/, and
confirmed by the tests): a spec is {"fimodels": {name: {simultaneous_faults, stages, node_fault_mapping,
fault_locations: {cell_name: [stage,...]}, output_values, input_values, output_fault_values, ...}}}.

Limits (stated, not hidden):
  - flop-Q faults cannot be replayed: the stock SYNFI cell library maps only `input_fault_q_o` (MEASURED failure,
    SYNFI_RESULT.md 3.5). They are reported in `skipped`, never silently dropped.
  - faults in more than one cycle need several SYNFI stages; our two-stage attempt crashed (MEASURED), so multi-cycle
    export is emitted with a warning and is UNTESTED against SYNFI.
  - the SYNFI start state / expected output words (`input_values`, `output_values`, `output_fault_values`) come from
    a BASE spec the user supplies; this module never invents them.
"""
import copy
import json
import re

# Output-inverted variants from the generic cell library used in compare/synfi_run (a bit flip of the gate output
# within one stage). Keys are SYNFI-side cell types; Yosys internal gate names are normalised first.
YOSYS_TO_SYNFI_TYPE = {"$_AND_": "AND2_X1", "$_OR_": "OR2_X1", "$_XOR_": "XOR2_X1", "$_NOT_": "INV_X1", "$_MUX_": "MUX2_X1"}
DEFAULT_FLIP_MAP = {"AND2_X1": ["NAND2_X1"], "OR2_X1": ["NOR2_X1"], "XOR2_X1": ["XNOR2_X1"],
                    "INV_X1": ["BUF_X1"], "MUX2_X1": ["MUXI2_X1"]}


class NetlistIndex:
    """Net id / net name -> driving cell, from a Yosys JSON netlist (either our original or the SYNFI-converted one)."""

    def __init__(self, path, top=None):
        doc = json.load(open(path))
        mods = doc["modules"]
        self.top = top or next(iter(mods))
        m = mods[self.top]
        self.cells = {cn: c["type"] for cn, c in m["cells"].items()}
        self.driver = {}   # net id -> (cell name, cell type, is_flop)
        for cn, c in m["cells"].items():
            outs = [p for p in ("Y", "Q", "ZN", "Z", "O") if p in c["connections"]]
            is_flop = "DFF" in c["type"] or "dff" in c["type"]
            for p in outs:
                for b in c["connections"][p]:
                    if isinstance(b, int):
                        self.driver[b] = (cn, c["type"], is_flop)
        self.name_bits = {}
        for n, x in m["netnames"].items():
            bits = x["bits"]
            for i, b in enumerate(bits):
                if isinstance(b, int):
                    self.name_bits[f"{n}[{i}]" if len(bits) > 1 else n] = b

    def resolve(self, target):
        """target = fault-campaign target dict. Returns (cell_name, cell_type, is_flop) or None."""
        bid = target.get("id")
        if bid is None:
            bid = self.name_bits.get(target["name"])
        if target["kind"] == "cell":
            t = self.cells.get(target["name"])
            return (target["name"], t, "DFF" in t or "dff" in t) if t else None
        return self.driver.get(bid)


def _synfi_type(t):
    return YOSYS_TO_SYNFI_TYPE.get(t, t)


def export_fimodel(campaign, set_id, netlist_path, base_fimodel, name=None, top=None, stage_of_cycle=None):
    """Return (fimodel_dict, report). `base_fimodel` is an existing SYNFI fimodel entry (stages, start state,
    expected values); only fault_locations / simultaneous_faults / node_fault_mapping are rewritten."""
    fs = next((s for s in campaign["fault_sets"] if s["id"] == set_id), None)
    if fs is None:
        raise KeyError(f"fault set {set_id!r} not in campaign")
    idx = NetlistIndex(netlist_path, top)
    report = {"set_id": set_id, "replayed": [], "skipped": [], "warnings": []}
    todo = []
    for f in fs["faults"]:
        if f["type"] != "bit_flip":
            report["skipped"].append({"fault": f, "reason": f"type {f['type']} has no output-inverted cell mapping in the generic library"})
            continue
        hit = idx.resolve(f["target"])
        if hit is None:
            report["skipped"].append({"fault": f, "reason": "target net has no driving cell in the netlist (input/constant?)"})
        elif hit[2]:
            report["skipped"].append({"fault": f, "reason": "flop Q flip: stock SYNFI cell library has only input_fault_q_o; not replayable (MEASURED failure earlier)"})
        else:
            todo.append((f, hit))
    cycles = sorted({f["cycle"] for f, _ in todo})
    stages = list(base_fimodel.get("stages", {}))
    if stage_of_cycle is None:
        if len(cycles) <= 1:
            stage_of_cycle = {c: (stages[0] if stages else "stage_1") for c in cycles}
        else:
            stage_of_cycle = {c: f"stage_{i + 1}" for i, c in enumerate(cycles)}
            report["warnings"].append("faults span several cycles: mapped to successive SYNFI stages; multi-stage replay "
                                      "is UNTESTED (our 2-stage attempt crashed, SYNFI_RESULT.md section 4)")
    locs, types = {}, set()
    for f, (cell, ctype, _) in todo:
        st = stage_of_cycle[f["cycle"]]
        locs.setdefault(cell, [])
        if st not in locs[cell]:
            locs[cell].append(st)
        types.add(_synfi_type(ctype))
        report["replayed"].append({"cell": cell, "cell_type": _synfi_type(ctype), "stage": st, "cycle": f["cycle"]})
    fm = copy.deepcopy(base_fimodel)
    fm["fault_locations"] = locs
    fm["simultaneous_faults"] = len(report["replayed"])
    nfm = dict(fm.get("node_fault_mapping", {}))
    for t in types:
        if t not in DEFAULT_FLIP_MAP:
            report["warnings"].append(f"cell type {t} has no default flip mapping; add it to node_fault_mapping")
        elif not nfm.get(t):
            nfm[t] = list(DEFAULT_FLIP_MAP[t])
    fm["node_fault_mapping"] = nfm
    if report["skipped"]:
        report["warnings"].append(f"{len(report['skipped'])} fault(s) not replayable: the SYNFI run covers a SUBSET of the set, "
                                  "so an 'ineffective' answer does not refute the attack")
    if not report["replayed"]:
        report["warnings"].append("nothing replayable: no SYNFI spec produced")
        return None, report
    return fm, report


def write_spec(fimodel, name, path):
    with open(path, "w") as fh:
        json.dump({"fimodels": {name: fimodel}}, fh, indent=1)
        fh.write("\n")


def campaign_from_synfi_spec(spec, fimodel_name, design_name, label="MEASURED"):
    """Import a SYNFI fault spec's explicit `fault_locations` as a fault-campaign (one set, cell targets, bit_flip
    when the mapping is an output-inverted variant). Cycle = index of the stage (stage_N -> N-1): SYNFI stages are
    relative to a hand-chosen start state, so this cycle is relative, not a reset-based cycle."""
    fm = spec["fimodels"][fimodel_name]
    faults = []
    for cell, stages in fm["fault_locations"].items():
        for st in stages:
            m = re.search(r"(\d+)$", st)
            faults.append({"target": {"kind": "cell", "name": cell}, "cycle": int(m.group(1)) - 1 if m else 0,
                           "type": "bit_flip", "duration": 1})
    return {"schema": "fault-campaign/0.1", "label": label, "generator": {"tool": "SYNFI fault spec (imported)"},
            "design": {"name": design_name}, "verdict": "UNKNOWN",
            "threat_model": {"max_faults": fm["simultaneous_faults"]},
            "fault_sets": [{"id": "synfi_spec", "faults": faults, "effective": None, "source": f"fimodel {fimodel_name}"}]}


# ------------------------------------------------------------------ reader
_RESULT = re.compile(r"RESULT model=(?P<model>\S+) k=(?P<k>\d+) total_fault_sets=(?P<tot>\d+) effective=(?P<eff>\d+) ineffective=(?P<ineff>\d+)")
_STOCK = re.compile(r"Found (?P<n>\d+) \((?P<pct>[\d.]+)%\) effective combinational faults, (?P<ns>\d+) \([\d.]+%\) effective sequential faults, and (?P<ni>\d+) ineffective faults")
_INJ = re.compile(r"Injecting (?P<n>\d+) faults")
_EFF = re.compile(r"^\s*EFFECTIVE:\s*(?P<body>.+)$")
_ITEM = re.compile(r"(?P<label>.*?)\[(?P<tail>[^\]]*)\]\s+stage=(?P<stage>\S+)\s+(?P<mapping>\S+)\s*$")
_MORE = re.compile(r"\.\.\. (\d+) more effective")
_RT = re.compile(r"RUNTIME_s\s+([\d.]+)")


def parse_synfi_log(text):
    """Parse a log from run_synfi.sh / synfi_report.py (preferred) or a stock SYNFI run (counts only).
    Effective-set labels are SYNFI's abbreviated 'netlabel[last 18 chars of the cell location]'."""
    out = {"model": None, "k": None, "total_fault_sets": None, "effective": None, "ineffective": None,
           "effective_sets": [], "unlisted_effective": 0, "runtime_s": None, "format": None}
    for line in text.splitlines():
        m = _RESULT.search(line)
        if m:
            out.update(model=m["model"], k=int(m["k"]), total_fault_sets=int(m["tot"]),
                       effective=int(m["eff"]), ineffective=int(m["ineff"]), format="synfi_report")
            continue
        m = _EFF.match(line)
        if m:
            items = []
            for part in m["body"].split(" + "):
                im = _ITEM.match(part.strip())
                items.append({"label": im["label"], "tail": im["tail"], "stage": im["stage"], "mapping": im["mapping"]} if im
                             else {"raw": part.strip()})
            out["effective_sets"].append(items)
            continue
        m = _MORE.search(line)
        if m:
            out["unlisted_effective"] = int(m.group(1)); continue
        m = _RT.search(line)
        if m:
            out["runtime_s"] = float(m.group(1)); continue
        m = _STOCK.search(line)
        if m:
            out["stock_effective_comb"] = int(m["n"]); out["stock_effective_seq"] = int(m["ns"]); out["stock_ineffective"] = int(m["ni"])
            continue
        m = _INJ.search(line)
        if m:
            out["stock_injecting"] = int(m["n"])
    if out["format"] is None and "stock_effective_comb" in out:
        # stock summary only: effective count is exact for the count line, total is NOT taken from 'Injecting N'
        # (for V2 k=2 it printed 3660 while 1830 pairs existed), so leave total unset.
        out.update(effective=out["stock_effective_comb"] + out["stock_effective_seq"], format="stock_summary")
    return out


def synfi_min_k(runs):
    """runs: {k: parsed log}. Smallest k with effective > 0 among the runs given, plus the largest k tried."""
    ks = sorted(runs)
    for k in ks:
        if (runs[k]["effective"] or 0) > 0:
            return k, ks[-1]
    return None, (ks[-1] if ks else None)


def compare(ours, synfi_runs, netlist_path=None, set_id="min_attack_set", top=None):
    """ours: fault-campaign document (verdict + fault_sets). synfi_runs: {k: parsed SYNFI log}.
    Verdict-level comparison on the common bound only; set-level check when the SYNFI log lists effective sets."""
    res = {"label": "MEASURED if both inputs are measured logs; this function only compares", "checks": [], "agree": None}
    ours_has = ours.get("verdict") == "ATTACK_FOUND" and bool(ours.get("fault_sets"))
    ours_min = min((len(s["faults"]) for s in ours["fault_sets"]), default=None) if ours_has else None
    smin, smax = synfi_min_k(synfi_runs)
    res.update(ours_min_faults=ours_min, ours_bound_k=ours.get("threat_model", {}).get("max_faults"),
               synfi_min_k=smin, synfi_max_k_tried=smax)
    if ours_min is not None:
        agree = (smin == ours_min)
        why = "same minimum" if agree else ("SYNFI found no effective set up to k=%s" % smax if smin is None else f"SYNFI minimum {smin} differs")
        if not agree and smin is not None and smin < ours_min:
            why += " (SYNFI's fault options are richer or its start state differs; investigate before trusting either)"
        res["agree"] = agree
        res["checks"].append({"check": "minimum fault count", "ours": ours_min, "synfi": smin, "ok": agree, "note": why})
    else:
        bound = res["ours_bound_k"]
        tried = [k for k in synfi_runs if bound is None or k <= bound]
        any_eff = [k for k in tried if (synfi_runs[k]["effective"] or 0) > 0]
        res["agree"] = not any_eff
        res["checks"].append({"check": "no attack within common bound", "ours_bound_k": bound, "synfi_k_tried": sorted(tried),
                              "synfi_effective_ks": any_eff, "ok": not any_eff,
                              "note": "both report none within their own bound" if not any_eff else "SYNFI found an effective set where ours found none"})
    # set-level
    if ours_has and netlist_path and ours["fault_sets"]:
        k = len(next(s for s in ours["fault_sets"] if s["id"] == set_id)["faults"])
        run = synfi_runs.get(k)
        if run and run["effective_sets"]:
            idx = NetlistIndex(netlist_path, top)
            fs = next(s for s in ours["fault_sets"] if s["id"] == set_id)
            tails, skipped = [], 0
            for f in fs["faults"]:
                hit = idx.resolve(f["target"])
                if hit is None or hit[2]:
                    skipped += 1
                else:
                    tails.append(hit[0][-18:])
            if skipped:
                res["checks"].append({"check": "our set listed by SYNFI", "ok": None,
                                      "note": f"{skipped} fault(s) are flop-Q or unresolved: not expressible in SYNFI, set-level check skipped"})
            else:
                found = any(sorted(it.get("tail") for it in s) == sorted(tails) for s in run["effective_sets"])
                dup = len(set(tails)) != len(tails)
                ok = True if found else (None if run["unlisted_effective"] else False)
                note = ("found by 18-char cell-name tail" if found else
                        ("not among the listed sets, but %d effective sets were not listed in the log" % run["unlisted_effective"]
                         if run["unlisted_effective"] else "not among SYNFI's effective sets"))
                if dup:
                    note += "; tails repeat (several cells share the same 18-char tail) so the match is weak"
                res["checks"].append({"check": "our set listed by SYNFI", "ok": ok, "note": note, "tails": tails})
    return res


def _cli():
    import argparse, sys
    from campaign import load
    ap = argparse.ArgumentParser(description="export a fault set as a SYNFI fimodel / compare SYNFI logs with ours")
    sp = ap.add_subparsers(dest="cmd", required=True)
    e = sp.add_parser("export")
    e.add_argument("campaign"); e.add_argument("--set", default="min_attack_set"); e.add_argument("--netlist", required=True)
    e.add_argument("--base-spec", required=True, help="existing SYNFI spec JSON; its first fimodel supplies stages/start state")
    e.add_argument("--name", required=True); e.add_argument("--out", required=True)
    c = sp.add_parser("compare")
    c.add_argument("campaign"); c.add_argument("--synfi-log", nargs="+", required=True); c.add_argument("--netlist")
    a = ap.parse_args()
    camp = load(a.campaign)
    if a.cmd == "export":
        base = next(iter(json.load(open(a.base_spec))["fimodels"].values()))
        fm, rep = export_fimodel(camp, a.set, a.netlist, base)
        print(json.dumps(rep, indent=1, default=str))
        if fm is None:
            sys.exit(2)
        write_spec(fm, a.name, a.out)
    else:
        runs = {}
        for p in a.synfi_log:
            r = parse_synfi_log(open(p).read()); runs[r["k"]] = r
        print(json.dumps(compare(camp, runs, a.netlist), indent=1))


if __name__ == "__main__":
    _cli()
