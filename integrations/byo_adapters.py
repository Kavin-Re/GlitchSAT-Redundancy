"""'Bring your own install' adapters for tools we are NOT allowed to run here.

STATUS: UNTESTED AGAINST THE REAL TOOLS. FIRMER, FIVER, uArchiFI and k-FRP were not run by this project (owner has
authorised running SYNFI only). Nothing here contains or copies their code or text. What is implemented:
  * `run_external()`: a thin, tool-agnostic wrapper that runs a command the USER supplies (their own install),
    with a timeout, and records provenance (command, exit code, stdout/stderr hashes, wall time, working-dir
    listing before/after). It refuses to run without the explicit acknowledgement flag. Tested here only with a
    harmless stand-in command (`python -c ...`), which tests the wrapper, NOT any third-party tool.
  * `to_uarchifi_script()`: renders a Yosys-script FRAGMENT using the option names given in uArchiFI's public README
    (`fault_rtlil -cnt N -timing a:b -effect X`, signals chosen by a Yosys `select` expression). Option names were
    READ, not executed; the user must check them against their installed version.
  * `to_fiver_config()`: renders a FIVER-style configuration file using the key names listed in the comments of the
    public sample config (general/library/circuit/fault sections). READ, not executed; the mapping file and library
    file are the user's own.
  * `from_attack_list()`: importer for a plain CSV/JSON list "signal,cycle[,effect]" so a user can paste the faults
    another tool reported (e.g. read off a counterexample) into our format. No tool-native parser is claimed.
FIRMER: no native format is read by this project at all (the public repo is not licensed for reuse and was only
read for the plan); use `from_attack_list()` and the generic exporter in campaign.py.
"""
import csv
import hashlib
import io
import json
import os
import subprocess
import time

EFFECT_FOR_TYPE = {"bit_flip": "flip", "set": "set", "reset": "reset", "stuck_at_0": "reset", "stuck_at_1": "set"}


def to_uarchifi_script(campaign, set_id=None, select_expr=None):
    """Yosys script fragment (text). UNTESTED. With set_id the select expression lists that set's signals."""
    tm = campaign.get("threat_model", {})
    sets = [s for s in campaign["fault_sets"] if set_id in (None, s["id"])]
    faults = [f for s in sets for f in s["faults"]]
    effects = {EFFECT_FOR_TYPE.get(f["type"]) for f in faults} - {None}
    cycles = [f["cycle"] for f in faults]
    cnt = tm.get("max_faults") or max((len(s["faults"]) for s in sets), default=1)
    lines = ["# UNTESTED (uArchiFI not run by this project). Check option names against your install.",
             "# select the signals the attacker may fault"]
    if select_expr is None:
        names = sorted({f["target"]["name"] for f in faults})
        select_expr = " ".join(f"w:{n}" for n in names) or "w:*"
    lines += [f"select {select_expr}", "setattr -set fault_signals 1", "select -clear",
              "# fault injection: counter, time window, effect"]
    if len(effects) > 1:
        lines.append(f"# NOTE: mixed effects {sorted(effects)} need one fault_rtlil call per effect; first one emitted")
    eff = sorted(effects)[0] if effects else "flip"
    win = f" -timing {min(cycles)}:{max(cycles)}" if cycles else ""
    lines.append(f"fault_rtlil -cnt {cnt}{win} -effect {eff}")
    return "\n".join(lines) + "\n"


def to_fiver_config(circuit_file, module, mapping_file, library_file, library_name, fault_number=1, variate=1,
                    location="cs", blacklist=None, interrupt=True):
    """FIVER-style config text with the section/key names of the public sample. UNTESTED; paths are the user's."""
    cfg = ["# UNTESTED (FIVER not run by this project).", "[general]", "cores = 4", "memory = 4", "verbose = 0",
           "[library]", f"file = {library_file}", f"name = {library_name}",
           "[circuit]", f"dut = {circuit_file}", f"module = {module}", "correction_based = false",
           "[fault]", f"number = {fault_number}", f"variate = {variate}", f"mapping = {mapping_file}", f"location = {location}"]
    if blacklist:
        cfg.append(f"blacklist = {blacklist}")
    cfg.append(f"interrupt = {'true' if interrupt else 'false'}")
    return "\n".join(cfg) + "\n"


def from_attack_list(text, design_name, label="UNVERIFIED", tool="external", fmt="csv"):
    """Parse 'signal,cycle[,effect]' lines (csv) or a JSON list of {signal,cycle,effect} into a fault-campaign doc
    with ONE fault set. effect in {flip,set,reset,stuck0,stuck1}; default flip."""
    emap = {"flip": "bit_flip", "bit_flip": "bit_flip", "set": "set", "reset": "reset", "stuck0": "stuck_at_0", "stuck1": "stuck_at_1"}
    rows = json.loads(text) if fmt == "json" else [
        dict(zip(("signal", "cycle", "effect"), r)) for r in csv.reader(io.StringIO(text)) if r and not r[0].startswith("#")]
    faults = []
    for r in rows:
        eff = (r.get("effect") or "flip").strip()
        if eff not in emap:
            raise ValueError(f"unknown effect {eff!r}")
        faults.append({"target": {"kind": "net", "name": str(r["signal"]).strip()}, "cycle": int(r["cycle"]),
                       "type": emap[eff], "duration": 1})
    return {"schema": "fault-campaign/0.1", "label": label, "generator": {"tool": tool}, "design": {"name": design_name},
            "verdict": "UNKNOWN", "fault_sets": [{"id": "imported", "faults": faults, "effective": None,
                                                   "source": "user-supplied attack list"}]}


def _listing(d):
    out = {}
    for root, _, files in os.walk(d):
        for f in files:
            p = os.path.join(root, f)
            out[os.path.relpath(p, d)] = os.path.getsize(p)
    return out


def run_external(argv, workdir, i_have_the_licence_and_install, timeout_s=600, env_extra=None):
    """Run the user's own install of a third-party tool. `argv` is a list (no shell). Returns a provenance record.
    Raises unless the caller passes True: the person running this takes responsibility for the tool's licence."""
    if i_have_the_licence_and_install is not True:
        raise PermissionError("refusing to run a third-party tool without i_have_the_licence_and_install=True")
    before = _listing(workdir)
    env = dict(os.environ); env.update(env_extra or {})
    t0 = time.time()
    try:
        r = subprocess.run(argv, cwd=workdir, capture_output=True, text=True, timeout=timeout_s, env=env)
        rc, out, err, timed_out = r.returncode, r.stdout, r.stderr, False
    except subprocess.TimeoutExpired as e:
        so = e.stdout
        rc, out, err, timed_out = None, (so.decode(errors="replace") if isinstance(so, bytes) else (so or "")), "", True
    after = _listing(workdir)
    return {"argv": argv, "workdir": workdir, "exit_code": rc, "timed_out": timed_out, "wall_s": round(time.time() - t0, 3),
            "stdout_sha256": hashlib.sha256(out.encode()).hexdigest(), "stderr_sha256": hashlib.sha256(err.encode()).hexdigest(),
            "stdout": out, "stderr": err,
            "files_new_or_changed": sorted(k for k, v in after.items() if before.get(k) != v),
            "label": "MEASURED wrapper record; says nothing about the tool's correctness"}
