"""glitchsat check-survival: did the fault countermeasures survive synthesis, placement and compilation?

  glitchsat check-survival survival.yaml                      # run every stage of the config
  glitchsat check-survival survival.yaml --sarif out.sarif    # + SARIF for code scanning
  glitchsat check-survival survival.yaml --baseline main.json # diff mode: fail if anything weakened vs the baseline
  glitchsat check-survival survival.yaml --against origin/main  # same, baseline computed from that git revision
  glitchsat check-survival --rtl rtl/v2.v --top v2 --netlist build/v2.json   # no config file
  glitchsat scan rtl/*.v fw/*.c build/v2.json                 # only list the countermeasures that are found

Exit codes: 0 every countermeasure survived (and margins meet the target); 1 something was weakened or removed, a
margin is below target / dropped, or (diff mode) a regression; 2 incomplete (a countermeasure could not be tracked or
a stage could not run), nothing found broken; 3 bad input.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

from . import gnet, intent_fw, intent_rtl, pipeline, report
from . import stage_netlist as SN


def _implicit_config(a):
    stages = []
    for i, n in enumerate(a.netlist or []):
        stages.append(dict(name=os.path.splitext(os.path.basename(n))[0] if len(a.netlist) > 1 else "netlist", netlist=n))
    if a.placed:
        if not a.def_:
            raise pipeline.ConfigError("--placed needs --def")
        stages.append(dict(name="placed", netlist=a.placed, **{"def": a.def_}, **({"lef": a.lef} if a.lef else {}),
                           spot_radius_um=a.spot_radius))
    if a.elf:
        stages.append(dict(name="firmware", elf=a.elf, sources=a.src or []))
    if not stages:
        raise pipeline.ConfigError("give a config file, or at least one of --netlist / --placed / --elf")
    cfg = dict(name=a.top or "design", top=a.top, intent=dict(rtl=a.rtl or []), stages=stages)
    if a.goal:
        o, v, i, k = (a.goal.split(",") + [None] * 4)[:4]
        cfg["goal"] = dict(output=o, value=int(v, 0), input=i, key=int(k, 0))
    return cfg


def cmd_check(a):
    try:
        if a.config:
            cfg = pipeline.load_config(a.config)
            base = os.path.dirname(os.path.abspath(a.config))
        else:
            cfg, base = _implicit_config(a), os.getcwd()
        if a.fail_on:
            cfg.setdefault("policy", {})["fail_on"] = a.fail_on
        rep = pipeline.run(cfg, base, workdir=a.workdir, want_margin=not a.no_margin, bisect=a.bisect)
    except (pipeline.ConfigError, FileNotFoundError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 3
    baseline = None
    if a.baseline:
        try:
            with open(a.baseline) as f:
                baseline = json.load(f)
            bname = a.baseline
        except (OSError, ValueError) as e:
            print(f"error: baseline {a.baseline}: {e}", file=sys.stderr)
            return 3
    elif a.against:
        try:
            baseline = _run_at_revision(a, a.against)
            bname = a.against
        except Exception as e:
            print(f"error: cannot compute the baseline at {a.against}: {e}", file=sys.stderr)
            return 3
    if baseline is not None:
        rep["diff"] = report.diff(baseline, rep, bname)
        if rep["diff"]["regressions"]:
            rep["summary"]["exit_code"] = 1
            rep["summary"]["verdict"] = "FAIL"
        elif a.diff_only and rep["summary"]["exit_code"] == 1:
            # diff-only: pre-existing findings do not fail the build, only regressions do
            rep["summary"]["exit_code"] = 0
            rep["summary"]["verdict"] = "PASS (no regression; existing findings remain)"
    root = a.repo_root or os.getcwd()
    report.write(rep, a.json, a.md, a.sarif, root, a.config or "survival.yaml", " ".join(["glitchsat"] + sys.argv[1:]))
    if a.sarif:
        with open(a.sarif) as f:
            errs = report.validate_sarif(json.load(f))
        if errs:
            print("warning: SARIF check (ext/product) reports: " + "; ".join(map(str, errs[:5])), file=sys.stderr)
    if not a.quiet:
        print(report.text(rep, verbose=not a.brief))
    return rep["summary"]["exit_code"]


def _run_at_revision(a, rev):
    """Check out `rev` in a temporary git worktree and run the same config there."""
    if not a.config:
        raise RuntimeError("--against needs a config file that exists in both revisions")
    cfg_abs = os.path.abspath(a.config)
    top = subprocess.run(["git", "-C", os.path.dirname(cfg_abs), "rev-parse", "--show-toplevel"], capture_output=True,
                         text=True, check=True).stdout.strip()
    rel = os.path.relpath(cfg_abs, top)
    tmp = tempfile.mkdtemp(prefix="gs-base-")
    wt = os.path.join(tmp, "wt")
    subprocess.run(["git", "-C", top, "worktree", "add", "--detach", wt, rev], capture_output=True, text=True, check=True)
    try:
        cfg = pipeline.load_config(os.path.join(wt, rel))
        return pipeline.run(cfg, os.path.dirname(os.path.join(wt, rel)), want_margin=not a.no_margin)
    finally:
        subprocess.run(["git", "-C", top, "worktree", "remove", "--force", wt], capture_output=True, text=True)
        shutil.rmtree(tmp, ignore_errors=True)


def cmd_scan(a):
    n = 0
    for p in a.files:
        try:
            if p.endswith((".c", ".h")):
                found = intent_fw.scan([p])
            elif p.endswith(".json") or (p.endswith(".v") and "sky130_fd_sc" in open(p, errors="replace").read(20000)):
                found = SN.detect(gnet.load(p, a.top))
            else:
                found = intent_rtl.scan([p])
        except (OSError, gnet.NetlistError) as e:
            print(f"{p}: error: {e}", file=sys.stderr)
            return 3
        for c in found:
            n += 1
            print(f"{c.where or p}: {c.kind}: {c.title()}  [{c.origin}; id {c.id}]")
    print(f"{n} countermeasure(s) found")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="glitchsat", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check-survival", help="check that countermeasures survive every build stage")
    c.add_argument("config", nargs="?", help="YAML config (see README.md); optional when --netlist/--placed/--elf are given")
    c.add_argument("--rtl", action="append", help="Verilog source scanned for countermeasure intent (repeatable)")
    c.add_argument("--top")
    c.add_argument("--netlist", action="append", help="Yosys JSON netlist stage, in build order (repeatable)")
    c.add_argument("--placed", help="post-route structural Verilog")
    c.add_argument("--def", dest="def_", help="DEF of the placed design")
    c.add_argument("--lef", help="LEF with cell sizes")
    c.add_argument("--spot-radius", type=float, default=0.5, help="fault spot radius in um for the placement stage (default 0.5)")
    c.add_argument("--elf", help="firmware binary (RV32, with line table)")
    c.add_argument("--src", action="append", help="C source of the firmware (repeatable)")
    c.add_argument("--goal", help="output,value,input,key for the margin search, e.g. boot_word,0x96,sig,0xC3")
    c.add_argument("--json", help="write the full report as JSON (also the baseline format of the diff mode)")
    c.add_argument("--md", help="write a Markdown summary")
    c.add_argument("--sarif", help="write SARIF 2.1.0")
    c.add_argument("--baseline", help="report JSON of an earlier run: fail when anything is weaker than there")
    c.add_argument("--against", metavar="GIT_REV", help="compute the baseline from this git revision (same config path)")
    c.add_argument("--diff-only", action="store_true", help="with a baseline: exit 1 only for regressions")
    c.add_argument("--fail-on", choices=["weakened", "removed", "never"], help="override policy.fail_on")
    c.add_argument("--no-margin", action="store_true", help="skip the fault searches (structural check only, instant)")
    c.add_argument("--bisect", action="store_true", help="with Yosys: find the script command that breaks a countermeasure")
    c.add_argument("--workdir", help="where generated netlists go (default: a temp folder)")
    c.add_argument("--repo-root", help="root for SARIF file paths (default: current folder)")
    c.add_argument("--brief", action="store_true")
    c.add_argument("--quiet", action="store_true")
    c.set_defaults(fn=cmd_check)
    s = sub.add_parser("scan", help="list the countermeasures found in RTL, C or netlist files")
    s.add_argument("files", nargs="+")
    s.add_argument("--top")
    s.set_defaults(fn=cmd_scan)
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 3
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
