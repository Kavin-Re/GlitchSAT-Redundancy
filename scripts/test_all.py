#!/usr/bin/env python3
"""Run every test suite of the repository, each in its own pytest process, and print a pass/fail table.

usage: python3 scripts/test_all.py [--only NAME[,NAME..]] [--list] [-- extra pytest arguments]

Run it from anywhere; no environment variables are needed. Suites whose tools are missing do not fail: their tests
skip (z3, Yosys, Icarus Verilog, CaDiCaL, a Yosys with read_slang for the OpenTitan primitives).
Exit code 0 when no suite failed, 1 otherwise."""
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (name, test path relative to the repository root). One process per suite: several modules use the same
# top-level module names (model, engine, sat, ...), so they cannot share one interpreter.
SUITES = [
    ("engine", "tests"),
    ("package", "product/tests"),
    ("integrations", "integrations/tests"),
    ("studio", "tools/studio/tests"),
    ("findings", "tools/findings/tests"),
    ("byod", "tools/byod/tests"),
    ("soc", "tools/soc/tests"),
    ("labs", "tools/labs/tests"),
    ("masking", "tools/masking/tests"),
    ("bootloader", "tools/bootloader/tests"),
    ("real", "tools/real/tests"),
    ("ot_prims", "tools/real/opentitan_prims/tests"),
    ("surface", "tools/surface/tests"),
    ("unbounded", "tools/unbounded/tests"),
    ("vlab", "tools/vlab/tests"),
    ("shots", "tools/shots/tests"),
    ("harden", "tools/harden/tests"),
    ("fastsat", "tools/fastsat/tests"),
    ("scale", "tools/scale/tests"),
    ("checker", "tools/checker/tests"),
    ("firmware", "tools/firmware/tests"),
    ("secboot_hw", "tools/secboot_hw"),
]


def counts(text):
    out = {}
    tail = text.strip().splitlines()[-1] if text.strip() else ""
    for n, what in re.findall(r"(\d+) (passed|failed|skipped|errors?|xfailed|xpassed|deselected)", tail):
        out["error" if what.startswith("error") else what] = int(n)
    return out, tail


def main(argv):
    extra = []
    if "--" in argv:
        i = argv.index("--")
        argv, extra = argv[:i], argv[i + 1:]
    only = None
    if "--only" in argv:
        only = set(argv[argv.index("--only") + 1].split(","))
    if "--list" in argv:
        for n, p in SUITES:
            print(f"{n:14s} {p}")
        return 0
    rows, bad = [], 0
    for name, path in SUITES:
        if only and name not in only:
            continue
        full = os.path.join(ROOT, path)
        if not os.path.isdir(full):
            rows.append((name, "MISSING", 0, 0, 0, 0.0, path + " not found"))
            bad += 1
            continue
        t0 = time.time()
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", path] + extra,
                           cwd=ROOT, capture_output=True, text=True)
        dt = time.time() - t0
        c, tail = counts(r.stdout)
        ok = r.returncode in (0, 5) and not c.get("failed") and not c.get("error")   # 5 = nothing collected
        status = "PASS" if ok else "FAIL"
        if not ok:
            bad += 1
            sys.stdout.write(f"\n--- {name} ({path}) ---\n" + "\n".join(r.stdout.splitlines()[-30:]) + "\n" + r.stderr[-2000:] + "\n")
        rows.append((name, status, c.get("passed", 0), c.get("failed", 0) + c.get("error", 0), c.get("skipped", 0), dt,
                     "nothing collected" if r.returncode == 5 else ""))
    print(f"\n{'suite':14s} {'result':7s} {'passed':>7s} {'failed':>7s} {'skipped':>8s} {'time':>7s}")
    for name, status, p, f, s, dt, note in rows:
        print(f"{name:14s} {status:7s} {p:7d} {f:7d} {s:8d} {dt:6.0f}s  {note}")
    tot = [sum(r[i] for r in rows) for i in (2, 3, 4)]
    print(f"{'total':14s} {'PASS' if not bad else 'FAIL':7s} {tot[0]:7d} {tot[1]:7d} {tot[2]:8d}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
