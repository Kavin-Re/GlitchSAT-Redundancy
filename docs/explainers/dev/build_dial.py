#!/usr/bin/env python3
"""Builds docs/explainers/dial.json for the Verdict Dial and inlines it into dial.html.

Read-only on the sources:
  research/c2/b2_scope/matrix.jsonl      360-cell scope matrix (B2)      -> word / accept-flag readers, stored + plain builds
  research/c2/b2_scope/run_matrix.py     for the search limit KMAX        -> bound string
  research/c3/m1/m1_all_masks.csv        255 consumer masks (M1)          -> "only 4 lights" readers
  research/c6/p01/sweep_rows.csv         8-flow synthesis sweep (P01)     -> merging build, V2e build
  reference/spike_netlists/v{0,1,2}.json stored netlists                  -> sha256 only
Writes: docs/explainers/dial.json, and replaces the <script id="dial-data"> block of docs/explainers/dial.html (if present).
Every digit is copied from one source row. A combination with no source row is written as status "not_measured"
with value null. Nothing is interpolated, extrapolated or inferred.
Usage: python3 docs/explainers/dev/build_dial.py            (run from anywhere; paths are relative to the project root)
"""
import csv, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the pages folder docs/explainers (this script is in its dev/ subfolder)
ROOT = os.path.dirname(os.path.dirname(HERE))
F_MATRIX = "research/c2/b2_scope/matrix.jsonl"
F_RUNMAT = "research/c2/b2_scope/run_matrix.py"
F_MASKS = "research/c3/m1/m1_all_masks.csv"
F_P01 = "research/c6/p01/sweep_rows.csv"
F_STORED = "reference/spike_netlists/%s.json"
P01_YOSYS = "Yosys 0.33"          # the dial shows the Yosys 0.33 rows only (same version as the B2 'apt033' rows)


def p(rel):
    return os.path.join(ROOT, rel)


def sha256(rel):
    return hashlib.sha256(open(p(rel), "rb").read()).hexdigest()


# ---------------------------------------------------------------- controls (order = order on screen)
DESIGNS = [
    {"id": "v2", "label": "V2", "sub": "three copies of the check"},
    {"id": "v1", "label": "V1", "sub": "two copies, one shared wire"},
    {"id": "v0", "label": "V0", "sub": "one check"},
]
MASKS = ["0x4E", "0x0F", "0x1B", "0x99"]     # four 4-bit masks picked to show 3, 2, 1 and 0 on the stored V2 netlist
READERS = [{"id": "word", "label": "Whole word", "sub": "all 8 lights"}] + \
          [{"id": "m" + m, "label": m, "sub": "4 of the 8 lights", "mask": m} for m in MASKS] + \
          [{"id": "flag", "label": "Accept flag", "sub": "one wire, boot_ok"}]
BUILDS = [
    {"id": "stored", "label": "Stored", "sub": "the netlist file in the repo"},
    {"id": "plain", "label": "Re-built", "sub": "plain recipe"},
    {"id": "merge", "label": "Merging", "sub": "re-built, opt_merge recipe"},
    {"id": "v2e", "label": "V2e", "sub": "re-encoded: one constant changed"},
]
INPUTS = [{"id": "no", "label": "No", "sub": "pins are out of reach"},
          {"id": "yes", "label": "Yes", "sub": "pins can be flipped too"}]
POWERS = [{"id": "known", "label": "Known", "sub": "starts in its idle state"},
          {"id": "nonopen", "label": "Any, not open", "sub": "any state that would not open by itself"},
          {"id": "any", "label": "Any", "sub": "any state at all"}]

# ---------------------------------------------------------------- reasons (the lookup table shown under the digit)
REASONS = {
    "any_power": "If the lock may wake up in any state, it can wake up already open. No flip needed.",
    "nonopen_power": "It may wake up one flip away from the open code. One flip finishes the job.",
    "flag": "The accept flag is one wire: one flip.",
    "inputs": "Every copy of the check reads the same input pins. With the pins in play, one flip was enough.",
    "v0_word": "One check, one decision: one flip.",
    "v1_word": "Two copies of the check, but both answers meet on one wire: one flip.",
    "v2_stored_word": "Here the three copies stay separate. It took three flips.",
    "v2_plain_word": "Same design, re-built. Two shared wires now move the four bits that matter: two flips.",
    "v2_merge_word": "This recipe merged the three copies into one check: one flip.",
    "v2e_word": "One constant changed, so the idle code now differs from the open code on all three copies. "
                "Back to three in this recipe.",
    "mask_collide": "These four lights already match the open code while the lock is still idle. No flip needed.",
    "mask_1": "A reader that checks only these four lights: one flip was enough.",
    "mask_2": "A reader that checks only these four lights: two flips were enough.",
    "mask_3": "These four lights depend on all three copies. It took three flips.",
    "nm_mask_scope": "Not measured. The four-light readers were only run with input pins out of reach and a known power-up.",
    "nm_mask_build": "Not measured. The four-light readers were not run on this build.",
    "nm_build_scope": "Not measured. This build was only run for the whole word, pins out of reach, known power-up.",
    "nm_build_design": "Not measured. This build exists only for the three-copy design (V2).",
    "nm_other": "Not measured. Nobody ran this combination.",
}

# ---------------------------------------------------------------- load sources
def load_matrix():
    rows = {}
    with open(p(F_MATRIX), encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            r["_line"] = n
            rows[(r["design"], r["netlist"], r["goal"], r["input_sites"], r["init"], r["free_input"])] = r
    return rows


def load_masks():
    rows = {}
    with open(p(F_MASKS), encoding="utf-8", newline="") as f:
        for n, r in enumerate(csv.DictReader(f), 2):      # line 1 is the header
            r["_line"] = n
            rows[r["mask_hex"]] = r
    return rows


def load_p01():
    rows = {}
    with open(p(F_P01), encoding="utf-8", newline="") as f:
        for n, r in enumerate(csv.DictReader(f), 2):
            r["_line"] = n
            if r["yosys"].startswith(P01_YOSYS):
                rows[(r["design"], r["variant"])] = r
    return rows


def kmax_from_run_matrix():
    m = re.search(r"^N\s*=\s*(\d+)\s*;\s*KMAX\s*=\s*(\d+)", open(p(F_RUNMAT), encoding="utf-8").read(), re.M)
    if not m:
        sys.exit("build_dial: cannot find 'N = ..; KMAX = ..' in " + F_RUNMAT)
    return int(m.group(1)), int(m.group(2))


MATRIX_NETLIST = {"stored": "spike", "plain": "apt033_plain"}
MATRIX_GOAL = {"word": "boot_word", "flag": "boot_ok"}
MATRIX_INIT = {"known": "known", "nonopen": "free_nongoal", "any": "free"}
MASK_COL = {("v0", "stored"): "v0_spike_min_flips", ("v1", "stored"): "v1_spike_min_flips",
            ("v1", "plain"): "v1_apt033_min_flips", ("v2", "stored"): "v2_spike_min_flips",
            ("v2", "plain"): "v2_apt033_min_flips"}
P01_ROW = {"merge": ("v2", "plain_opt_merge"), "v2e": ("v2e", "plain")}


def main():
    matrix, masks, p01 = load_matrix(), load_masks(), load_p01()
    mat_ticks, mat_kmax = kmax_from_run_matrix()
    stored_sha = {d: sha256(F_STORED % d) for d in ("v0", "v1", "v2")}

    # "N of M recipes" line for V2e, counted from the P01 rows (Yosys 0.33)
    v2e_rows = [r for (d, _), r in p01.items() if d == "v2e"]
    v2e_three = sum(1 for r in v2e_rows if r["min_flips"] == "3")
    v2e_one = sum(1 for r in v2e_rows if r["min_flips"] == "1")
    v2e_note = "Measured 3 in %d of %d recipes on Yosys 0.33; %d merging recipes stay at 1." % (
        v2e_three, len(v2e_rows), v2e_one)

    cells = {}
    for D in DESIGNS:
        for R in READERS:
            for B in BUILDS:
                for I in INPUTS:
                    for P in POWERS:
                        d, rd, b, i, pw = D["id"], R["id"], B["id"], I["id"], P["id"]
                        key = "|".join((d, rd, b, i, pw))
                        cell = None
                        if b in MATRIX_NETLIST and rd in MATRIX_GOAL:
                            r = matrix.get((d, MATRIX_NETLIST[b], MATRIX_GOAL[rd], i == "yes", MATRIX_INIT[pw], False))
                            if r is not None and r["verdict"] == "ATTACK_FOUND" and r["min_cost"] is not None:
                                v = int(r["min_cost"])
                                if pw == "any" and v == 0: reason = "any_power"
                                elif rd == "flag": reason = "flag"
                                elif pw == "nonopen": reason = "nonopen_power"
                                elif i == "yes": reason = "inputs"
                                elif d == "v2": reason = "v2_%s_word" % b
                                else: reason = d + "_word"
                                cell = {"status": "measured", "value": v, "reason": reason, "label": r["label"],
                                        "source": {"file": F_MATRIX, "row": "line %d" % r["_line"],
                                                   "key": "design=%s netlist=%s goal=%s input_sites=%s init=%s free_input=false" % (
                                                       r["design"], r["netlist"], r["goal"], str(r["input_sites"]).lower(), r["init"])},
                                        "netlist_sha256": stored_sha[d] if b == "stored" else None,
                                        "netlist_sha_note": ("sha256 of " + F_STORED % d + ", computed by build_dial.py") if b == "stored"
                                                            else "not recorded in the source row",
                                        "yosys": None if b == "stored" else "apt Yosys 0.33, scripts/synth.sh plain",
                                        "bound": {"ticks": int(r["N"]), "kmax": mat_kmax, "from": F_RUNMAT},
                                        "witness": ["%s @ tick %d" % (n, t) for n, t in r["faults"]]}
                        elif "mask" in R and (d, b) in MASK_COL and i == "no" and pw == "known":
                            r = masks.get(R["mask"])
                            col = MASK_COL[(d, b)]
                            if r is not None and r.get(col, "") != "":
                                v = int(r[col])
                                reason = "mask_collide" if (v == 0 and r["collides_with_legit_state"] == "1") else "mask_%d" % v
                                cell = {"status": "measured", "value": v, "reason": reason, "label": "MEASURED",
                                        "source": {"file": F_MASKS, "row": "line %d" % r["_line"],
                                                   "key": "mask_hex=%s column=%s" % (r["mask_hex"], col)},
                                        "netlist_sha256": stored_sha[d] if b == "stored" else None,
                                        "netlist_sha_note": ("sha256 of " + F_STORED % d + ", computed by build_dial.py") if b == "stored"
                                                            else "not recorded in the source row",
                                        "yosys": None if b == "stored" else "apt Yosys 0.33, scripts/synth.sh plain",
                                        "bound": {"ticks": 6, "kmax": 3, "from": "research/c3/m1/M1_REPORT.md (T=6, k<=3)"},
                                        "witness": []}
                        elif b in P01_ROW and d == "v2" and rd == "word" and i == "no" and pw == "known":
                            r = p01.get(P01_ROW[b])
                            if r is not None and r["min_flips"].isdigit():
                                v = int(r["min_flips"])
                                cell = {"status": "measured", "value": v, "reason": "v2_merge_word" if b == "merge" else "v2e_word",
                                        "label": "MEASURED",
                                        "source": {"file": F_P01, "row": "line %d" % r["_line"],
                                                   "key": "yosys=%s design=%s variant=%s" % (P01_YOSYS, r["design"], r["variant"])},
                                        "netlist_sha256": r["netlist_sha256"], "netlist_sha_note": "from the source row",
                                        "yosys": P01_YOSYS + ", faultbound-wt --synth-sweep flow '%s'" % r["variant"],
                                        "bound": {"ticks": 6, "kmax": 3, "from": "docs/report/WHY_TWO_FLIPS.md (T=6, k<=3)"},
                                        "witness": [w.replace("@", " @ tick ") for w in r["witness"].split(";") if w]}
                                if b == "v2e":
                                    cell["note"] = v2e_note
                        if cell is None:
                            if "mask" in R and (i != "no" or pw != "known") and (d, b) in MASK_COL: reason = "nm_mask_scope"
                            elif "mask" in R: reason = "nm_mask_build" if not (b in P01_ROW and d != "v2") else "nm_build_design"
                            elif b in P01_ROW and d != "v2": reason = "nm_build_design"
                            elif b in P01_ROW: reason = "nm_build_scope"
                            else: reason = "nm_other"
                            cell = {"status": "not_measured", "value": None, "reason": reason}
                        cells[key] = cell

    data = {
        "meta": {
            "what": "Verdict Dial data. Every value is copied from one MEASURED source row; "
                    "faults are modelled single-tick bit flips on toy designs; nothing physical. License: UNDECIDED.",
            "generated_by": "docs/explainers/dev/build_dial.py",
            "key_order": ["design", "reader", "build", "inputs", "power"],
            "sources": [{"file": f, "sha256": sha256(f)} for f in (F_MATRIX, F_MASKS, F_P01, F_RUNMAT)],
            "cells_total": len(cells),
            "cells_measured": sum(1 for c in cells.values() if c["status"] == "measured"),
        },
        "controls": {"design": DESIGNS, "reader": READERS, "build": BUILDS, "inputs": INPUTS, "power": POWERS},
        "reasons": REASONS,
        "cells": cells,
    }
    out = json.dumps(data, indent=1, sort_keys=True) + "\n"
    with open(os.path.join(HERE, "dial.json"), "w", encoding="utf-8") as f:
        f.write(out)
    msg = "dial.json: %d cells, %d measured, %d not measured" % (
        len(cells), data["meta"]["cells_measured"], len(cells) - data["meta"]["cells_measured"])

    html_path = os.path.join(HERE, "dial.html")
    if os.path.exists(html_path):
        html = open(html_path, encoding="utf-8").read()
        inline = json.dumps(data, separators=(",", ":"), sort_keys=True).replace("</", "<\\/")
        pat = re.compile(r'(<script type="application/json" id="dial-data">)(.*?)(</script>)', re.S)
        if not pat.search(html):
            sys.exit("build_dial: dial.html has no <script type=\"application/json\" id=\"dial-data\"> block")
        html = pat.sub(lambda m: m.group(1) + "\n" + inline + "\n" + m.group(3), html, count=1)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        msg += "; inlined into dial.html"
    print(msg)


if __name__ == "__main__":
    main()
