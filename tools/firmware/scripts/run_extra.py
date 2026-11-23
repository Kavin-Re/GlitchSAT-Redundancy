#!/usr/bin/env python3
"""Extra experiments (results in results/extra_*.json):

  delay    Random delays against an attacker who must pick the fault time in
           advance. For seeds 1..S of the modelled TRNG, find every step t at
           which ONE instruction skip boots the tampered image; report, per t,
           the share of seeds for which t works, and the best t. Compared with
           the same routine without delays (rom_naive, same build settings).
  inhash   One instruction skip at EVERY executed step of a software-HMAC
           build, including the SHA-256 code the main matrix leaves out.
  redund   How much of the written redundancy survives compilation: number of
           MAC-word loads from the image header and OTP MIN_VERSION reads in a
           good-image run, per variant, optimisation level and mode.

  python3 scripts/run_extra.py delay|inhash|redund
"""
import json
import os
import sys
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from faultsim import image  # noqa: E402
from faultsim.search import Searcher, describe  # noqa: E402
from rv32sim import load_elf  # noqa: E402
from rv32sim.cpu import F_SKIP, IMAGE, RUNNING, Machine  # noqa: E402

RES = os.path.join(ROOT, "results")


def single_skip_times(prog, flash, otp, seed):
    """Set of absolute steps t where one skip boots the image (exhaustive, k=1)."""
    s = Searcher(prog, flash, otp, "skip", trng_seed=seed, budget_s=3600)
    hits = s.k1_all()
    return sorted({h[0][0] for h in hits}), s.golden.steps


def delay(seeds=32):
    sc = image.scenarios()
    flash, otp = sc["tampered_payload"][0], image.otp()
    out = {"seeds": seeds, "scenario": "tampered_payload", "rows": []}
    for opt in ("O0", "O1", "O2", "Os"):
        for var in ("rom_naive", "rom_delay"):
            stem = "%s-%s-plain-hw" % (var, opt)
            p = load_elf(os.path.join(ROOT, "elf", stem + ".elf"))
            per_t = Counter()
            lens = []
            any_seed = 0
            for sd in range(1, seeds + 1):
                ts, n = single_skip_times(p, flash, otp, sd)
                lens.append(n)
                per_t.update(ts)
                any_seed += bool(ts)
            best_t, best_n = (per_t.most_common(1)[0] if per_t else (None, 0))
            row = {"build": stem, "seeds_with_any_single_skip": any_seed,
                   "best_fixed_step": best_t, "seeds_where_best_step_works": best_n,
                   "best_fixed_step_success_rate": round(best_n / seeds, 4),
                   "run_length_min": min(lens), "run_length_max": max(lens)}
            out["rows"].append(row)
            print(row, flush=True)
    json.dump(out, open(os.path.join(RES, "extra_delay.json"), "w"), indent=1)


def inhash(stem="rom_naive-O2-plain-sw"):
    sc = image.scenarios()
    flash, otp = sc["tampered_payload"][0], image.otp()
    p = load_elf(os.path.join(ROOT, "elf", stem + ".elf"))
    t0 = time.time()
    s = Searcher(p, flash, otp, "skip", budget_s=36000, sites="all", memo=False)
    hits = s.k1_all()
    in_hash = [h for h in hits if p.lines.get(h[0][1], ("?", 0))[0] in ("hmac_sw.c",)]
    out = {"build": stem, "scenario": "tampered_payload", "model": "skip", "k": 1,
           "steps_tried": s.golden.steps, "hits_total": len(hits), "hits_inside_hmac_sw": len(in_hash),
           "hits": [describe(p, h[0]) for h in hits], "seconds": round(time.time() - t0, 1)}
    json.dump(out, open(os.path.join(RES, "extra_inhash_%s.json" % stem), "w"), indent=1)
    print({k: v for k, v in out.items() if k != "hits"})


class CountingMachine(Machine):
    __slots__ = ("mac_loads", "otp_minv_loads")

    def load(self, addr, n, signed):
        if 0x20000010 <= addr < 0x20000030:
            self.mac_loads += 1
        if addr in (0x40000020, 0x40000024):
            self.otp_minv_loads += 1
        return Machine.load(self, addr, n, signed)


def redund():
    good = image.scenarios()["good"][0]
    otp = image.otp()
    rows = []
    for var in ("rom_naive", "rom_double", "rom_triple", "rom_compl", "rom_ctres", "rom_cfi",
                "rom_delay", "rom_infective", "rom_hardened"):
        for opt in ("O0", "O1", "O2", "Os"):
            for md in ("plain", "vol", "barrier"):
                stem = "%s-%s-%s-hw" % (var, opt, md)
                p = load_elf(os.path.join(ROOT, "elf", stem + ".elf"))
                m = CountingMachine(p, good, otp)
                m.mac_loads = 0
                m.otp_minv_loads = 0
                m.run(10 ** 6)
                assert m.outcome == IMAGE
                rows.append({"build": stem, "variant": var, "opt": opt, "mode": md,
                             "mac_word_loads": m.mac_loads, "mac_compares_executed": m.mac_loads / 8,
                             "otp_min_version_reads": m.otp_minv_loads, "good_run_steps": m.steps})
    json.dump({"rows": rows, "image": "good"}, open(os.path.join(RES, "extra_redundancy.json"), "w"), indent=1)
    for r in rows:
        print(r["build"], r["mac_compares_executed"], r["otp_min_version_reads"])


if __name__ == "__main__":
    {"delay": delay, "inhash": inhash, "redund": redund}[sys.argv[1]](*sys.argv[2:])
