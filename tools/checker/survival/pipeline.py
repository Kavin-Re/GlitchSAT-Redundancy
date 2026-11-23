"""Run the survival check described by a config: intent capture, then every stage in order."""
import hashlib
import os
import re
import subprocess
import tempfile

import yaml

from . import __version__, explain, gnet, intent_fw, intent_rtl, margin, paths
from . import stage_netlist as SN
from .model import Countermeasure, StageResult, SURVIVED, WEAKENED, REMOVED, UNTRACKED, NOT_CHECKED, ORDER, worst

SCHEMA = "glitchsat-survival/1"
HW_KINDS = ("redundant_copies", "complement_pair", "sparse_encoding", "redundant_register", "alarm", "mubi")
FW_KINDS = ("fw_repeated_check", "fw_flow_counter")
RTL_REFERENCE_FLOW = "proc; setattr -mod -unset keep_hierarchy *; flatten; techmap"       # as written: no optimisation pass that could merge anything


class ConfigError(Exception):
    pass


def load_config(path):
    with open(path) as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict) or not isinstance(cfg.get("stages"), list) or not cfg["stages"]:
        raise ConfigError(f"{path}: a config needs a `stages:` list (see README.md)")
    for i, s in enumerate(cfg["stages"]):
        if not isinstance(s, dict) or not s.get("name"):
            raise ConfigError(f"{path}: stage {i} needs a `name`")
        if not any(k in s for k in ("netlist", "elf", "verilog")):
            raise ConfigError(f"{path}: stage {s['name']} needs `netlist:`, `verilog:` (+ `flow:`/`script:`) or `elf:`")
    return cfg


def _sha(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def _abs(base, p):
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))


def _aslist(x):
    return [] if x is None else (list(x) if isinstance(x, (list, tuple)) else [x])


def yosys_version():
    y = paths.tool("yosys")
    if not y:
        return None
    try:
        return subprocess.run([y, "-V"], capture_output=True, text=True, timeout=30).stdout.strip() or None
    except Exception:
        return None


def run_yosys(verilog, top, flow, out_json, log=None):
    """read_verilog <files>; hierarchy -top <top>; <flow>; write_json <out>. Returns (ok, message)."""
    y = paths.tool("yosys")
    if not y:
        return False, "Yosys is not installed (looked on PATH and in the tools env file)"
    sv = any(str(v).endswith(".sv") for v in verilog)
    script = "".join(f"read_verilog {'-sv ' if sv else ''}{v}\n" for v in verilog)
    script += f"hierarchy -top {top}\n" if top else "hierarchy -auto-top\n"
    script += "\n".join(c.strip() for c in re.split(r"[;\n]", flow) if c.strip()) + f"\nwrite_json {out_json}\n"
    with tempfile.NamedTemporaryFile("w", suffix=".ys", delete=False) as f:
        f.write(script)
        ys = f.name
    try:
        r = subprocess.run([y, "-q", "-s", ys], capture_output=True, text=True, timeout=900)
    except Exception as e:
        return False, f"Yosys failed to run: {e}"
    finally:
        os.unlink(ys)
    if log:
        with open(log, "w") as f:
            f.write(script + "\n--- stdout ---\n" + r.stdout + "\n--- stderr ---\n" + r.stderr)
    if r.returncode != 0 or not os.path.isfile(out_json):
        return False, "Yosys error: " + (r.stderr.strip().splitlines() or r.stdout.strip().splitlines() or ["?"])[-1][:300]
    return True, script


def _declared(cfg, base):
    out = []
    for i, d in enumerate(_aslist((cfg.get("intent") or {}).get("countermeasures"))):
        d = dict(d)
        kind = d.pop("kind", None)
        if kind not in HW_KINDS + FW_KINDS:
            raise ConfigError(f"intent.countermeasures[{i}]: unknown kind {kind!r}")
        cid = str(d.pop("id", f"{kind}:{i}"))
        if kind == "sparse_encoding" and d.get("codes"):
            d["codes"] = sorted(int(c, 16) if isinstance(c, str) else int(c) for c in d["codes"])
            d.setdefault("min_distance", gnet.min_distance(d["codes"]))
            d.setdefault("aliases", [])
        out.append(Countermeasure(id=cid if ":" in cid else f"{kind}:{cid}", kind=kind, origin="yaml",
                                  where=d.pop("where", ""), intent=d))
    return out


def run(cfg, base=".", workdir=None, want_margin=True, bisect=False, log=print):
    """Returns the report dict (schema glitchsat-survival/1)."""
    paths.setup()
    intent = cfg.get("intent") or {}
    top = cfg.get("top")
    goal = cfg.get("goal")
    mcfg = cfg.get("margin") or {}
    policy = cfg.get("policy") or {}
    workdir = workdir or tempfile.mkdtemp(prefix="gs-survival-")
    os.makedirs(workdir, exist_ok=True)
    rtl_files = [_abs(base, p) for p in _aslist(intent.get("rtl"))]
    for p in rtl_files:
        if not os.path.isfile(p):
            raise ConfigError(f"intent.rtl: {p} not found")
    cms = intent_rtl.scan(rtl_files)
    if top:
        mods = {c.intent.get("module") for c in cms}
        if top in mods:                     # keep the top module's countermeasures (sub-modules are flattened into it)
            cms = [c for c in cms if c.intent.get("module") in (top, None)] or cms
    only = set(_aslist(intent.get("only"))) or None
    declared = _declared(cfg, base)
    ids = {c.id for c in declared}
    cms = declared + [c for c in cms if c.id not in ids]
    stages = [dict(s) for s in cfg["stages"]]
    # an "as written" reference netlist made from the RTL when Yosys is available and the config does not give one
    if rtl_files and intent.get("reference", "auto") == "auto" and not any(s.get("reference") for s in stages) \
            and all(str(p).endswith(".v") for p in rtl_files):
        out = os.path.join(workdir, "rtl_reference.json")
        ok, msg = run_yosys(rtl_files, top, RTL_REFERENCE_FLOW, out, log=out + ".log")
        if ok:
            stages.insert(0, dict(name="rtl", netlist=out, reference=True, flow=RTL_REFERENCE_FLOW, generated=True,
                                  note="made by the checker: read_verilog; " + RTL_REFERENCE_FLOW + " (no optimisation)"))
    report = dict(schema=SCHEMA, tool=dict(name="glitchsat check-survival", version=__version__, yosys=yosys_version()),
                  name=cfg.get("name") or top or "design", top=top, goal=goal, stages=[], countermeasures=[], notes=[])
    results = {}
    prev_net, first_net = None, True
    for st in stages:
        name = st["name"]
        info = dict(name=name, kind=None, files={}, status="ok", notes=[])
        report["stages"].append(info)
        if st.get("note"):
            info["notes"].append(st["note"])
        script_text = st.get("flow") or ""
        if st.get("script"):
            sp = _abs(base, st["script"])
            if os.path.isfile(sp):
                with open(sp) as f:
                    script_text = f.read()
                info["files"]["script"] = dict(path=st["script"], sha256=_sha(sp))
        st["script_text"] = script_text
        # ------------------------------------------------------------ firmware
        if st.get("elf"):
            info["kind"] = st["kind"] = "firmware"
            _firmware_stage(st, info, base, cms, results, only, want_margin, log)
            continue
        # ------------------------------------------------------------ netlist (made by Yosys here, or given)
        nl_path = _abs(base, st["netlist"]) if st.get("netlist") else os.path.join(workdir, f"{name}.json")
        if st.get("verilog") and (st.get("flow") or st.get("script")) and not (st.get("netlist") and os.path.isfile(nl_path) and not st.get("rebuild")):
            ok, msg = run_yosys([_abs(base, v) for v in _aslist(st["verilog"])], st.get("top", top), script_text, nl_path,
                                log=nl_path + ".log")
            if not ok:
                info.update(status="not_run", kind="netlist")
                info["notes"].append(msg)
                for cm in cms:
                    if cm.kind in HW_KINDS:
                        results.setdefault(cm.id, []).append(StageResult(cm.id, name, NOT_CHECKED, evidence=[msg], label="untested"))
                continue
            info["notes"].append("netlist made here with " + (report["tool"]["yosys"] or "Yosys"))
        if not os.path.isfile(nl_path):
            info.update(status="not_run", kind="netlist")
            info["notes"].append(f"netlist {st.get('netlist')} not found")
            for cm in cms:
                if cm.kind in HW_KINDS:
                    results.setdefault(cm.id, []).append(StageResult(cm.id, name, NOT_CHECKED, evidence=[info["notes"][-1]], label="untested"))
            continue
        info["kind"] = st["kind"] = "placement" if st.get("def") else "netlist"
        info["files"]["netlist"] = dict(path=st.get("netlist") or os.path.relpath(nl_path, base), sha256=_sha(nl_path))
        try:
            g = gnet.load(nl_path, st.get("top", top))
        except (gnet.NetlistError, ValueError, KeyError) as e:
            info.update(status="error")
            info["notes"].append(str(e))
            for cm in cms:
                if cm.kind in HW_KINDS:
                    results.setdefault(cm.id, []).append(StageResult(cm.id, name, UNTRACKED, evidence=[str(e)[:300]]))
            continue
        info["stats"] = g.stats()
        info["notes"] += g.notes
        if prev_net is not None and any(f.init is None for f in g.flops.values()):
            n = SN.copy_init(g, prev_net)
            if n:
                info["notes"].append(f"power-up values of {n} flops taken from the previous netlist stage (same flop names)")
        if first_net:
            info["reference"] = True
            det = intent.get("detect", "auto")
            if det is True or det == "always" or (det == "auto" and not any(c.kind in HW_KINDS for c in cms)):
                have = {c.kind for c in cms}
                added = 0
                for c in SN.detect(g):
                    if (det == "always" or c.kind not in have) and c.id not in {x.id for x in cms}:
                        cms.append(c)
                        added += 1
                info["notes"].append(f"{added} countermeasure(s) detected in this netlist itself; it is the reference for them")
        pl = None
        if st.get("def"):
            from . import stage_place as SP
            try:
                pl = SP.Placement(_abs(base, st["def"]), _abs(base, st["lef"]) if st.get("lef") else None)
                info["files"]["def"] = dict(path=st["def"], sha256=pl.sha256)
            except Exception as e:
                info["notes"].append(f"DEF not usable: {e}")
        radius = float(st.get("spot_radius_um", (cfg.get("placement") or {}).get("spot_radius_um", 0.5)))
        st["spot_radius_um"] = radius
        for cm in cms:
            if cm.kind not in HW_KINDS or (only and cm.id not in only):
                continue
            r = SN.check(cm, g, name, first_net)
            if r is None:
                continue
            st2 = dict(st, kind="netlist")
            explain.explain(cm, r, st2)
            if pl is not None and r.verdict in (SURVIVED, WEAKENED):
                rp = SP.check(cm, g, pl, name, radius)
                if rp is not None and rp.verdict != UNTRACKED:
                    explain.explain(cm, rp, dict(st, kind="placement"))
                    rp.measured = dict(netlist=r.measured, placement=rp.measured)
                    rp.evidence = r.evidence + rp.evidence
                    if ORDER[r.verdict] > ORDER[rp.verdict]:
                        rp.verdict, rp.cause, rp.fix = r.verdict, r.cause, r.fix
                    r = rp
            results.setdefault(cm.id, []).append(r)
        if goal and want_margin and st.get("margin", True) and nl_path.endswith(".json"):
            m = margin.measure(nl_path, st.get("top", top), goal, kmax=int(mcfg.get("k", 3)), cycles=int(mcfg.get("cycles", 6)),
                               engines=tuple(_aslist(mcfg.get("engines")) or ("auto", "z3")),
                               timeout_s=float(mcfg.get("timeout_s", 120)), unbounded=bool(mcfg.get("unbounded", False)),
                               backend=mcfg.get("backend", "auto"))
            for w in m.get("witness") or []:        # where each fault of the minimum attack lands
                hit = g.find("^" + re.escape(str(w.get("net", ""))) + "$")
                if hit:
                    sinks = g.sinks(next(iter(hit.values())))
                    w["reaches_state_bits"] = sum(1 for x in sinks if x.startswith("ff:"))
            info["margin"] = m
        if pl is not None and want_margin:
            from . import stage_place as SP
            rs = SP.recorded_shots(pl, radius)
            if rs:
                info["margin_shots"] = dict(rs, spot_radius_um=radius)
        if bisect and script_text and st.get("verilog") and prev_net is not None:
            from . import bisect as B
            info["bisect"] = B.bisect([_abs(base, v) for v in _aslist(st["verilog"])], st.get("top", top), script_text,
                                      [c for c in cms if c.kind in HW_KINDS], workdir, name)
            for cm in cms:
                hit = info["bisect"].get("first_break", {}).get(cm.id)
                rs_ = [r for r in results.get(cm.id, []) if r.stage == name]
                if hit and rs_:
                    rs_[0].cause = (f"MEASURED by re-running the script one command at a time: the verdict changes to "
                                    f"{hit['verdict']} right after command {hit['index'] + 1}, `{hit['command']}`. ") + rs_[0].cause
        prev_net, first_net = g, False
    # ---------------------------------------------------------------- assemble
    for cm in cms:
        rs = results.get(cm.id, [])
        if only and cm.id not in only:
            continue
        d = cm.to_json()
        d["stages"] = [r.to_json() for r in rs]
        d["verdict"] = worst([r.verdict for r in rs])
        d["broken_at"] = next((r.stage for r in rs if r.verdict in (WEAKENED, REMOVED)), None)
        report["countermeasures"].append(d)
    _summarise(report, mcfg, policy)
    return report


def _firmware_stage(st, info, base, cms, results, only, want_margin, log):
    from . import stage_fw as SF
    name = st["name"]
    elf = _abs(base, st["elf"])
    info["files"]["elf"] = dict(path=st["elf"], sha256=_sha(elf))
    srcs = [_abs(base, p) for p in _aslist(st.get("sources"))]
    funcs = set(_aslist(st.get("function"))) or None
    mine = []
    for c in intent_fw.scan([p for p in srcs if os.path.isfile(p)], funcs):
        c.id = f"{c.id}@{os.path.basename(c.intent['file'])}"
        ex = next((x for x in cms if x.id == c.id), None)
        if ex is None:
            cms.append(c)
            ex = c
        mine.append(ex)
    mine += [c for c in cms if c.kind in ("fw_repeated_check", "fw_flow_counter") and c.origin == "yaml" and c not in mine]
    if not os.path.isfile(elf):
        info.update(status="not_run")
        info["notes"].append(f"ELF {st['elf']} not found")
        for cm in mine:
            results.setdefault(cm.id, []).append(StageResult(cm.id, name, NOT_CHECKED, evidence=[info["notes"][-1]], label="untested"))
        return
    try:
        b = SF.Binary(elf)
    except Exception as e:
        info.update(status="error")
        info["notes"].append(f"ELF not readable: {e}")
        for cm in mine:
            results.setdefault(cm.id, []).append(StageResult(cm.id, name, UNTRACKED, evidence=[str(e)[:300]]))
        return
    info["notes"].append(f"line table: {b.lines_from or 'none'}")
    texts = {p: open(p, encoding="utf-8", errors="replace").read() for p in srcs if os.path.isfile(p)}
    for cm in mine:
        if only and cm.id not in only:
            continue
        r = SF.check(cm, b, name, texts.get(cm.intent.get("file")))
        if r is None:
            continue
        explain.explain(cm, r, dict(st, kind="firmware"))
        results.setdefault(cm.id, []).append(r)
    if want_margin:
        m = SF.recorded_margin(elf)
        if m:
            info["margin_faults"] = m


def _summarise(report, mcfg, policy):
    cms = report["countermeasures"]
    counts = {v: sum(1 for c in cms if c["verdict"] == v) for v in (SURVIVED, WEAKENED, REMOVED, UNTRACKED, NOT_CHECKED)}
    fail_on = str(policy.get("fail_on", "weakened")).lower()
    bad = counts[REMOVED] + (counts[WEAKENED] if fail_on == "weakened" else 0)
    if fail_on == "never":
        bad = 0
    margins, below = [], []
    target = mcfg.get("min")
    for s in report["stages"]:
        m = s.get("margin")
        if m and m.get("status") == "attack":
            margins.append((s["name"], m["min_faults"]))
            if target is not None and m["min_faults"] < int(target):
                below.append(dict(stage=s["name"], min_faults=m["min_faults"], target=int(target)))
    drop = None
    if len(margins) >= 2:
        ref = margins[0][1]
        low = min(margins[1:], key=lambda x: x[1])
        if low[1] < ref:
            drop = dict(reference_stage=margins[0][0], reference=ref, stage=low[0], min_faults=low[1])
    if drop:
        st = next(s for s in report["stages"] if s["name"] == drop["stage"])
        broken = [c["title"] for c in cms for r in c["stages"] if r["stage"] == drop["stage"] and r["verdict"] in (WEAKENED, REMOVED)]
        wit = (st.get("margin") or {}).get("witness") or []
        wtxt = ", ".join(f"{w.get('net')} (cycle {w.get('cycle')}" + (f", feeds {w['reaches_state_bits']} state flops" if w.get("reaches_state_bits") else "") + ")" for w in wit)
        drop["explained_by"] = broken
        drop["text"] = (f"explained by: {'; '.join(broken)}" if broken else
                        "no tracked countermeasure changed at this stage: the copies and the encoding are intact, and the "
                        "logic between them was mapped so that fewer flips are enough") + (f". Minimum attack found: {wtxt}" if wtxt else "")
    incomplete = counts[UNTRACKED] + sum(1 for s in report["stages"] if s["status"] != "ok")
    code = 1 if (bad or below or (drop and policy.get("fail_on_margin_drop", True))) else (2 if incomplete else 0)
    report["summary"] = dict(counts=counts, margin_below_target=below, margin_drop=drop, incomplete=incomplete,
                             verdict="FAIL" if code == 1 else ("INCOMPLETE" if code == 2 else "PASS"), exit_code=code)
    return report
