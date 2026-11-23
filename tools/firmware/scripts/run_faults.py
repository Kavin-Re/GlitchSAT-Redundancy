#!/usr/bin/env python3
"""Run the fault-search matrix and store one JSON per job in results/raw/.

A job = (build stem, attack scenario, fault model, kmax, flash execute-lock).
Jobs already present in results/raw/ are not re-run (delete the file to redo).

  python3 scripts/run_faults.py --set main      # hw-engine builds, full matrix
  python3 scripts/run_faults.py --set sw        # software-HMAC builds, subset
  python3 scripts/run_faults.py --set xip       # flash executable from reset
  python3 scripts/run_faults.py --set sha3      # SHA3-256 engine builds (secboot_hw interface), subset
  python3 scripts/run_faults.py --set all -j 2
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from faultsim import image  # noqa: E402
from faultsim.search import Searcher, describe, replay  # noqa: E402
from rv32sim import load_elf  # noqa: E402
from rv32sim.cpu import IMAGE, OUTCOME_NAMES  # noqa: E402

RAW = os.path.join(ROOT, "results", "raw")
VARIANTS = ["rom_naive", "rom_double", "rom_triple", "rom_compl", "rom_ctres",
            "rom_cfi", "rom_delay", "rom_infective", "rom_hardened"]
OPTS = ["O0", "O1", "O2", "Os"]
MODES = ["plain", "vol", "barrier"]
KMAX = {"skip": 3, "brinv": 3, "rdflip": 2, "pcoff": 2, "iwflip": 1}


def jobs_for(which):
    J = []
    if which in ("main", "all"):
        for v in VARIANTS:
            for o in OPTS:
                for md in MODES:
                    stem = "%s-%s-%s-hw" % (v, o, md)
                    for model, k in KMAX.items():
                        J.append((stem, "tampered_payload", model, k, True, 150))
                    for model in ("skip", "brinv"):
                        J.append((stem, "rollback_signed_old", model, 3, True, 150))
    if which in ("sw", "all"):
        for v in VARIANTS:
            for o in ("O2", "Os"):
                for md in ("plain", "barrier"):
                    stem = "%s-%s-%s-sw" % (v, o, md)
                    for model, k in (("skip", 2), ("brinv", 3), ("rdflip", 1), ("pcoff", 1), ("iwflip", 1)):
                        J.append((stem, "tampered_payload", model, k, True, 300))
    if which in ("sha3", "all"):
        # secboot_hw SHA3-256 engine driver: same decision code, the hardware-matching MAC path
        for v in VARIANTS:
            for o in OPTS:
                for md in ("plain", "barrier"):
                    stem = "%s-%s-%s-sha3" % (v, o, md)
                    for model, k in (("skip", 2), ("brinv", 2), ("pcoff", 1), ("rdflip", 1)):
                        J.append((stem, "tampered_payload", model, k, True, 150))
    if which in ("xip", "all"):
        for v in VARIANTS:
            for md in ("plain", "barrier"):
                stem = "%s-O2-%s-hw" % (v, md)
                for model in ("rdflip", "pcoff", "iwflip"):
                    J.append((stem, "tampered_payload", model, 1, False, 150))
    return J


def job_name(j):
    stem, scen, model, k, lock, _b = j
    return "%s__%s__%s__k%d__%s" % (stem, scen, model, k, "lock" if lock else "xip")


def run_job(j):
    stem, scen, model, k, lock, budget = j
    out_path = os.path.join(RAW, job_name(j) + ".json")
    if os.path.exists(out_path):
        return out_path, "cached"
    p = load_elf(os.path.join(ROOT, "elf", stem + ".elf"))
    flash = image.scenarios(image.mac_kind(p))[scen][0]
    otp = image.otp()
    s = Searcher(p, flash, otp, model, budget_s=budget, exec_lock=lock)
    r = s.minimum(k)
    if r["witness"]:
        m = replay(p, flash, otp, r["witness"], exec_lock=lock)
        r["witness_replay"] = OUTCOME_NAMES[m.outcome]
        assert m.outcome == IMAGE, (job_name(j), "witness does not replay")
    r["witness"] = [describe(p, f) for f in r["witness"]] if r["witness"] else r["witness"]
    hits = r.pop("k1_hits")
    r["k1_sites"] = sorted({(d["file"], d["line"], d["pc"], d["asm"]) for h in hits for d in (describe(p, h[0]),)})
    r["k1_hits"] = [describe(p, h[0]) for h in hits[:200]]
    r.update(build=stem, scenario=scen, exec_lock=lock, budget_s=budget,
             date=time.strftime("%Y-%m-%d"), sites_in_window=len(s.sites))
    tmp = out_path + ".tmp"
    json.dump(r, open(tmp, "w"), indent=1)
    os.replace(tmp, out_path)
    return out_path, "%s min=%s %s %.1fs" % (r["status"], r["min_faults"], r["completed_k"], r.get("seconds", 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="main")
    ap.add_argument("-j", type=int, default=2)
    ap.add_argument("--filter", default="")
    ap.add_argument("--budget", type=float, default=None, help="override the per-job time budget (s)")
    a = ap.parse_args()
    os.makedirs(RAW, exist_ok=True)
    J = [j for j in jobs_for(a.set) if a.filter in job_name(j)]
    if a.budget:
        J = [j[:5] + (a.budget,) for j in J]
    # cheap jobs first so partial runs are useful
    order = {"brinv": 0, "iwflip": 1, "skip": 2, "rdflip": 3, "pcoff": 4}
    J.sort(key=lambda j: (order[j[2]], j[0]))
    print(len(J), "jobs", flush=True)
    with mp.Pool(a.j) as pool:
        for i, (path, msg) in enumerate(pool.imap_unordered(run_job, J)):
            print(i + 1, os.path.basename(path), msg, flush=True)


if __name__ == "__main__":
    main()
