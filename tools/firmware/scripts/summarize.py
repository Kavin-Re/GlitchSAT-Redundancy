#!/usr/bin/env python3
"""Collect results/raw/*.json into the summary files.

  results/summary.json          every job (one row each) + the headline table
  results/studio_firmware.json  the same numbers shaped for the Studio "Firmware" view
  results/compare_hw.json       firmware variants next to the hardware V0/V1/V2 figures

Every number here is MEASURED on the rv32sim instruction-set simulator (an
instruction-level model of an in-order RV32IMC core), not on silicon.
The hardware figures are quoted from GlitchSAT docs/NUMBERS.md (row ids given);
they were not re-run here.

  python3 scripts/summarize.py
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "results", "raw")
ELF_DIR = os.environ.get("FW_ELF_DIR", os.path.join(ROOT, "elf"))
sys.path.insert(0, ROOT)
from faultsim.static import count_calls, count_op  # noqa: E402
from rv32sim import isa, load_elf  # noqa: E402
OUT = os.path.join(ROOT, "results")

VARIANTS = ["rom_naive", "rom_double", "rom_triple", "rom_compl", "rom_ctres",
            "rom_cfi", "rom_delay", "rom_infective", "rom_hardened"]
DESCR = {
    "rom_naive": "one compare, one branch per check",
    "rom_double": "rollback test and MAC compare each done twice; second disagreeing raises the alarm",
    "rom_triple": "three rollback tests and three MAC compares (software counterpart of hardware V2)",
    "rom_compl": "decision kept as a multi-bit boolean and its complement; OTP version read with its complement copy",
    "rom_ctres": "constant-time MAC compare plus an independent count of equal words",
    "rom_cfi": "flow-integrity counter checked before the jump",
    "rom_delay": "random (TRNG-driven) delays before the rollback test and the MAC compare",
    "rom_infective": "MAC difference mixed into the jump address",
    "rom_hardened": "combined: double OTP read + complement, constant-time compare, multi-bit boolean, "
                    "flow counter, assembly checks that trap, infective jump address",
}
OPTS = ["O0", "O1", "O2", "Os"]
MODES = ["plain", "vol", "barrier"]
MODELS = ["skip", "brinv", "rdflip", "pcoff", "iwflip"]
MODEL_TEXT = {"skip": "instruction skip", "brinv": "branch inversion", "rdflip": "register bit flip",
              "pcoff": "small PC corruption (+-2..16 bytes)", "iwflip": "fetched instruction-word bit flip"}

# Hardware results, quoted from GlitchSAT docs/NUMBERS.md (status there: MEASURED; not re-run here)
HW = [
    {"design": "V0", "what": "one check", "min_flips": "1", "numbers_ids": ["B2.v0v1"],
     "firmware_counterpart": "rom_naive"},
    {"design": "V1", "what": "two checks joined by one AND gate", "min_flips": "1", "numbers_ids": ["B2.v0v1"],
     "firmware_counterpart": "rom_double"},
    {"design": "V2", "what": "three checks with separate output bits",
     "min_flips": "3 (stored netlist, full 8-bit word goal); 2 after re-synthesis with apt Yosys 0.33; "
                  "1 if only the boot_ok flag must be forced",
     "numbers_ids": ["B2.v2.spike.word", "B2.v2.apt", "B2.v2.conda", "B2.v2.ok"],
     "firmware_counterpart": "rom_triple"},
]
HW_NOTE = ("Hardware: single-cycle bit flips on nets of a gate-level netlist (8-bit toy designs, 6 cycles, at most "
           "3 flips). Firmware: instruction-level faults on a simulated RV32IMC core. The units differ (one net flip "
           "vs one instruction fault); compare the pattern, not the absolute numbers.")


def parse_stem(stem):
    v, o, md, h = stem.split("-")
    return v, o, md, h


def load_rows():
    rows = []
    for f in sorted(glob.glob(os.path.join(RAW, "*.json"))):
        r = json.load(open(f))
        v, o, md, h = parse_stem(r["build"])
        rows.append({
            "job": os.path.basename(f)[:-5], "build": r["build"], "variant": v, "opt": o, "mode": md, "mac": h,
            "scenario": r["scenario"], "model": r["model"], "kmax": r["kmax"], "exec_lock": r["exec_lock"],
            "status": r["status"], "min_faults": r["min_faults"], "completed_k": r["completed_k"],
            "k1_count": r["k1_count"], "k1_sites": r.get("k1_sites", []), "witness": r["witness"],
            "witness_replay": r.get("witness_replay"), "golden_outcome": r["golden_outcome"],
            "golden_steps": r["golden_steps"], "sites_in_window": r["sites_in_window"],
            "seconds": r.get("seconds"), "budget_s": r["budget_s"], "date": r["date"],
        })
    return rows


def cell(r):
    """Text and numbers for one job: exact minimum, or a lower bound."""
    if r is None:
        return {"text": "not run", "exact": None, "lower_bound": None}
    if r["min_faults"] is not None:
        return {"text": str(r["min_faults"]), "exact": r["min_faults"], "lower_bound": r["min_faults"]}
    lb = r["completed_k"] + 1
    if r["status"] == "budget_exhausted":
        return {"text": ">=%d (k=%d not completed)" % (lb, lb), "exact": None, "lower_bound": lb}
    return {"text": ">%d" % r["completed_k"], "exact": None, "lower_bound": lb}


def combine(cells):
    """Minimum over fault models (each search uses one model at a time).
    Exact if some model found m and every other model ruled out every k < m."""
    found = [c["exact"] for c in cells if c["exact"] is not None]
    if found:
        m = min(found)
        exact = all(c["exact"] is not None or c["lower_bound"] >= m for c in cells)
        return {"text": str(m) if exact else "<=%d" % m, "exact": m if exact else None,
                "upper_bound": m, "lower_bound": m if exact else min(c["lower_bound"] for c in cells)}
    if not cells:
        return {"text": "not run", "exact": None, "upper_bound": None, "lower_bound": None}
    lb = min(c["lower_bound"] for c in cells)
    done = all(not c["text"].startswith(">=") for c in cells)
    return {"text": (">%d" % (lb - 1)) if done else ">=%d (not completed)" % lb, "exact": None,
            "upper_bound": None, "lower_bound": lb}


def main():
    rows = load_rows()
    idx = {(r["build"], r["scenario"], r["model"], r["exec_lock"]): r for r in rows}
    bad = [r["job"] for r in rows if r["min_faults"] and r["witness_replay"] != "image_runs"]
    if bad:
        sys.exit("witness does not replay: %s" % bad)

    table = []   # main matrix: hw MAC engine, flash execute-locked
    for v in VARIANTS:
        for o in OPTS:
            for md in MODES:
                b = "%s-%s-%s-hw" % (v, o, md)
                ent = {"variant": v, "opt": o, "mode": md, "build": b}
                for scen, models in (("tampered_payload", MODELS), ("rollback_signed_old", ["skip", "brinv"])):
                    per = {m: cell(idx.get((b, scen, m, True))) for m in models}
                    ent[scen] = {"per_model": per,
                                 "any_model": combine([c for c in per.values() if c["lower_bound"] is not None]),
                                 "four_models": combine([per[m] for m in models if m != "iwflip"
                                                         and per[m]["lower_bound"] is not None])}
                table.append(ent)

    headline = {}   # variant -> opt -> text (plain C, tampered payload, min over skip/brinv/rdflip/pcoff)
    for e in table:
        if e["mode"] == "plain":
            headline.setdefault(e["variant"], {})[e["opt"]] = e["tampered_payload"]["four_models"]["text"]

    xip = []
    for r in rows:
        if not r["exec_lock"]:
            xip.append({"build": r["build"], "model": r["model"], "min_faults": r["min_faults"],
                        "status": r["status"], "witness": r["witness"]})
    def other(r, suffix):
        return cell(idx.get((r["build"].rsplit("-", 1)[0] + "-hw", r["scenario"], r["model"], True)))["text"]
    sw = [{"build": r["build"], "model": r["model"], "kmax": r["kmax"], "result": cell(r)["text"],
           "hw_engine_result": other(r, "hw")} for r in rows if r["mac"] == "sw"]
    sha3 = []
    for r in rows:
        if r["mac"] != "sha3":
            continue
        a = cell(r)
        h = idx.get((r["build"].rsplit("-", 1)[0] + "-hw", r["scenario"], r["model"], True))
        b = cell(h)
        K = r["kmax"]
        if a["lower_bound"] is None or b["lower_bound"] is None or a["text"].startswith(">=") \
                or b["text"].startswith(">="):
            agree = None                                    # one side incomplete or not run
        elif a["exact"] is not None:
            agree = b["exact"] == a["exact"]
        else:                                               # sha3: none up to K
            agree = b["lower_bound"] > K
        sha3.append({"build": r["build"], "model": r["model"], "kmax": K, "result": a["text"],
                     "hmac_engine_result": b["text"], "agree_within_k": agree})
    dpath = os.path.join(OUT, "extra_delay.json")
    delay = json.load(open(dpath)) if os.path.exists(dpath) else None

    red = json.load(open(os.path.join(OUT, "extra_redundancy.json")))["rows"]
    redundancy = []
    for x in red:
        y = {k: x[k] for k in ("build", "variant", "opt", "mode", "mac_compares_executed",
                               "otp_min_version_reads", "good_run_steps")}
        prog = load_elf(os.path.join(ELF_DIR, x["build"] + ".elf"))
        y["alarm_call_sites"] = count_calls(prog, "rom_alarm")
        y["fail_call_sites"] = count_calls(prog, "rom_fail")
        y["infective_mul"] = count_op(prog, isa.MUL)
        redundancy.append(y)

    meta = {
        "label": "MEASURED",
        "platform": "rv32sim: pure-Python RV32IMC instruction-set simulator, one instruction per step. "
                    "A model, not silicon: no pipeline, caches, interrupts or analogue effects.",
        "toolchain": json.load(open(manifest_path())).get("clang"),
        "fault_window": "faults land on every executed ROM instruction outside the MAC unit "
                        "(hmac_hw.c / hmac_sw.c): start-up, header checks, rollback test, compare, jump",
        "fault_models": MODEL_TEXT,
        "goal": "the core fetches its first instruction from flash (the image runs) although the image is "
                "tampered (tampered_payload) or older than OTP MIN_VERSION (rollback_signed_old)",
        "search": "exhaustive for k=1 (all single faults); depth-first with state de-duplication for k>=2, "
                  "one fault model per search; a budget-stopped level is reported as not completed",
        "kmax": {"skip": 3, "brinv": 3, "rdflip": 2, "pcoff": 2, "iwflip": 1},
        "jobs": len(rows),
        "dates": sorted({r["date"] for r in rows}),
    }
    summary = {"meta": meta, "headline_plain_tampered_four_models": headline, "table": table,
               "flash_executable_from_reset": xip, "software_hmac_builds": sw, "sha3_engine_builds": sha3,
               "random_delay_fixed_time_attacker": delay,
               "redundancy_survival": redundancy, "jobs": rows}
    json.dump(summary, open(os.path.join(OUT, "summary.json"), "w"), indent=1)

    # Studio view: compact, self-describing
    studio = {
        "view": "Firmware", "schema": 1, "label": "MEASURED", "source": "firmware/results/summary.json",
        "platform": "simulator (rv32sim), not silicon",
        "caption": "Minimum number of instruction-level faults (skip, branch inversion, register bit flip, "
                   "small PC offset; one model per search) that make the boot ROM run a tampered image",
        "variants": [{"id": v, "description": DESCR[v]} for v in VARIANTS],
        "opts": OPTS, "modes": MODES, "models": MODELS, "model_text": MODEL_TEXT,
        "cells": [{"variant": e["variant"], "opt": e["opt"], "mode": e["mode"],
                   "tampered": e["tampered_payload"]["four_models"]["text"],
                   "tampered_iwflip_k1": e["tampered_payload"]["per_model"]["iwflip"]["text"],
                   "tampered_per_model": {m: e["tampered_payload"]["per_model"][m]["text"] for m in MODELS},
                   "rollback": e["rollback_signed_old"]["any_model"]["text"],
                   "witness": first_witness(idx, e["build"])} for e in table],
        "redundancy": [{"variant": x["variant"], "opt": x["opt"], "mode": x["mode"],
                        "mac_compares": x["mac_compares_executed"], "otp_reads": x["otp_min_version_reads"],
                        "alarm_call_sites": x["alarm_call_sites"], "infective_mul": x["infective_mul"]}
                       for x in redundancy],
        "hardware_compare": {"rows": HW, "note": HW_NOTE},
        "sha3_engine": {"note": "builds with the secboot_hw SHA3-256 engine driver (the SoC interface); "
                                "subset k<=2 skip/brinv, k=1 rdflip/pcoff",
                        "rows": [{k: x[k] for k in ("build", "model", "kmax", "result", "hmac_engine_result",
                                                    "agree_within_k")} for x in sha3]},
        "random_delay": delay,
        "notes": ["'>k' = no attack with k or fewer faults of any model searched (inside the model).",
                  "'>=k (not completed)' = the search stopped at its time budget; no conclusion at k.",
                  "Fault models are searched one at a time; mixed-model attacks are not searched."],
    }
    json.dump(studio, open(os.path.join(OUT, "studio_firmware.json"), "w"), indent=1)

    cmp_rows = []
    for h in HW:
        v = h["firmware_counterpart"]
        cmp_rows.append({"hardware": h, "firmware_variant": v,
                         "firmware_plain_tampered": headline.get(v, {}),
                         "firmware_barrier_tampered": {e["opt"]: e["tampered_payload"]["four_models"]["text"]
                                                                 for e in table
                                                                 if e["variant"] == v and e["mode"] == "barrier"},
                         "firmware_plain_skip_only": {e["opt"]: e["tampered_payload"]["per_model"]["skip"]["text"]
                                                      for e in table if e["variant"] == v and e["mode"] == "plain"},
                         "firmware_barrier_skip_only": {e["opt"]: e["tampered_payload"]["per_model"]["skip"]["text"]
                                                        for e in table
                                                        if e["variant"] == v and e["mode"] == "barrier"}})
    json.dump({"label": "firmware MEASURED (simulator); hardware quoted from docs/NUMBERS.md", "note": HW_NOTE,
               "rows": cmp_rows}, open(os.path.join(OUT, "compare_hw.json"), "w"), indent=1)

    write_tables(summary, cmp_rows)
    print("jobs", len(rows))
    print("%-14s %s" % ("variant", "  ".join("%-6s" % o for o in OPTS)))
    for v in VARIANTS:
        print("%-14s %s" % (v, "  ".join("%-6s" % headline.get(v, {}).get(o, "-") for o in OPTS)))


def write_tables(s, cmp_rows):
    """results/TABLES.md: every table of the README and more, generated from summary.json."""
    L = ["# Fault-analysis tables (generated by scripts/summarize.py; do not edit)", "",
         "Label: **MEASURED** on the rv32sim instruction-set simulator, not on silicon. "
         "Dates of the runs: %s. Jobs: %d." % (", ".join(s["meta"]["dates"]), s["meta"]["jobs"]), "",
         "Cell = smallest number of faults that makes the ROM run a tampered image. "
         "`>k`: none with k or fewer (search completed). `>=k (k=.. not completed)`: the time budget "
         "stopped the search; no conclusion at k. `<=k`: an attack with k faults exists but a smaller "
         "count was not ruled out for every model. Fault models are searched one at a time.", ""]

    def grid(title, scen, key, mode, model=None):
        L.append("## %s" % title)
        L.append("")
        L.append("| variant | " + " | ".join("-" + o for o in OPTS) + " |")
        L.append("|---|" + "---|" * len(OPTS))
        for v in VARIANTS:
            cells = []
            for o in OPTS:
                e = [x for x in s["table"] if x["variant"] == v and x["opt"] == o and x["mode"] == mode][0]
                cells.append(e[scen][key][model]["text"] if model else e[scen][key]["text"])
            L.append("| %s | %s |" % (v, " | ".join(cells)))
        L.append("")

    for md, what in (("plain", "ordinary C"), ("vol", "volatile header reads and results"),
                     ("barrier", "asm value barrier (launder)")):
        grid("Tampered payload, minimum over skip / branch inversion / register flip / PC offset, %s (%s)"
             % (md, what), "tampered_payload", "four_models", md)
    for m in MODELS:
        for md in MODES:
            grid("Tampered payload, %s only (k <= %d), %s" % (MODEL_TEXT[m], {"skip": 3, "brinv": 3, "rdflip": 2,
                 "pcoff": 2, "iwflip": 1}[m], md), "tampered_payload", "per_model", md, m)
    for md in MODES:
        grid("Rolled-back image (validly signed, version below OTP minimum), skip or branch inversion, %s" % md,
             "rollback_signed_old", "any_model", md)

    L.append("## Tampered payload, per fault model (all modes)")
    L.append("")
    L.append("| build | " + " | ".join(MODELS) + " | a minimal attack (skip/brinv/rdflip/pcoff) |")
    L.append("|---|" + "---|" * (len(MODELS) + 1))
    for e in s["table"]:
        pm = e["tampered_payload"]["per_model"]
        w = None
        for j in s["jobs"]:
            if j["build"] == e["build"] and j["scenario"] == "tampered_payload" and j["exec_lock"] \
                    and j["model"] != "iwflip" and j["min_faults"] and (w is None or j["min_faults"] < len(w)):
                w = j["witness"]
        wt = "; ".join("%s at %s:%d `%s`" % (x["model"], x["file"], x["line"], x["asm"].replace("\t", " "))
                       for x in w) if w else ""
        L.append("| %s | %s | %s |" % (e["build"], " | ".join(pm[m]["text"] for m in MODELS), wt))
    L.append("")

    L.append("## How much written redundancy survives compilation (good image, no faults)")
    L.append("")
    L.append("MAC compares = passes over the 8 header MAC words actually executed; OTP reads = reads of "
             "MIN_VERSION / MIN_VERSION_INV; alarm call sites = call instructions to rom_alarm left in rom_main; mul = multiply instructions in "
             "rom_main (the infective address mixing; only rom_infective and rom_hardened have one in C).")
    L.append("")
    L.append("| build | MAC compares | OTP reads | alarm call sites | mul | steps |")
    L.append("|---|---|---|---|---|---|")
    for x in s["redundancy_survival"]:
        L.append("| %s | %g | %d | %d | %d | %d |" % (x["build"], x["mac_compares_executed"],
                                                    x["otp_min_version_reads"], x["alarm_call_sites"],
                                                    x["infective_mul"], x["good_run_steps"]))
    L.append("")

    if s["flash_executable_from_reset"]:
        L.append("## Flash executable from reset (no EXEC_EN lock), -O2, k = 1")
        L.append("")
        L.append("| build | model | result |")
        L.append("|---|---|---|")
        for x in sorted(s["flash_executable_from_reset"], key=lambda x: (x["build"], x["model"])):
            L.append("| %s | %s | %s |" % (x["build"], x["model"], x["min_faults"] if x["min_faults"] else
                                          (">1" if x["status"] == "no_attack_up_to_kmax" else x["status"])))
        L.append("")
    if s["sha3_engine_builds"]:
        L.append("## SHA3-256 engine builds (the secboot_hw interface) vs HMAC-engine builds (same decision code)")
        L.append("")
        L.append("Subset: plain and barrier styles, tampered payload; skip and branch inversion up to k = 2, "
                 "register flip and PC offset k = 1. The HMAC-engine column is the main-matrix result (larger k).")
        L.append("")
        ag = [x["agree_within_k"] for x in s["sha3_engine_builds"]]
        L.append("Agreement within the smaller bound: %d agree, %d differ, %d not comparable (one side not "
                 "completed or not run). Differences come from the linked code: the driver changes addresses, "
                 "the stack frame and the register values left for the decision code." %
                 (ag.count(True), ag.count(False), ag.count(None)))
        L.append("")
        L.append("| build | model | k searched | SHA3 engine | HMAC engine (main matrix) | same within k |")
        L.append("|---|---|---|---|---|---|")
        for x in sorted(s["sha3_engine_builds"], key=lambda x: (x["build"], MODELS.index(x["model"]))):
            L.append("| %s | %s | %d | %s | %s | %s |" % (x["build"], x["model"], x["kmax"], x["result"],
                                                         x["hmac_engine_result"],
                                                         {True: "yes", False: "**no**", None: "-"}[x["agree_within_k"]]))
        L.append("")
    if s["random_delay_fixed_time_attacker"]:
        d = s["random_delay_fixed_time_attacker"]
        L.append("## Random delays against an attacker who fixes the fault time in advance (one skip, %d TRNG seeds)"
                 % d["seeds"])
        L.append("")
        L.append("| build | seeds with any single-skip attack | best fixed step works for | run length (steps) |")
        L.append("|---|---|---|---|")
        for r in d["rows"]:
            L.append("| %s | %d of %d | %d of %d seeds | %d..%d |" % (
                r["build"], r["seeds_with_any_single_skip"], d["seeds"], r["seeds_where_best_step_works"],
                d["seeds"], r["run_length_min"], r["run_length_max"]))
        L.append("")
    if s["software_hmac_builds"]:
        L.append("## Software HMAC builds vs hardware-engine builds (same decision code)")
        L.append("")
        L.append("| build | model | software HMAC | hardware engine |")
        L.append("|---|---|---|---|")
        for x in s["software_hmac_builds"]:
            L.append("| %s | %s | %s | %s |" % (x["build"], x["model"], x["result"], x["hw_engine_result"]))
        L.append("")

    L.append("## Firmware next to the hardware V0/V1/V2 (hardware quoted from GlitchSAT docs/NUMBERS.md)")
    L.append("")
    L.append(HW_NOTE)
    L.append("")
    L.append("Firmware cells: -O0 / -O1 / -O2 / -Os. 'four models' = minimum over skip, branch inversion, "
             "register flip, PC offset; 'skip' = instruction skip only (k <= 3).")
    L.append("")
    L.append("| hardware | min flips (NUMBERS.md ids) | firmware | plain, four models | barrier, four models "
             "| plain, skip | barrier, skip |")
    L.append("|---|---|---|---|---|---|---|")
    for c in cmp_rows:
        h = c["hardware"]
        L.append("| %s, %s | %s (%s) | %s | %s | %s | %s | %s |" % (
            h["design"], h["what"], h["min_flips"], ", ".join(h["numbers_ids"]), c["firmware_variant"],
            *[" / ".join(c[k].get(o, "-") for o in OPTS) for k in (
                "firmware_plain_tampered", "firmware_barrier_tampered", "firmware_plain_skip_only",
                "firmware_barrier_skip_only")]))
    L.append("")
    open(os.path.join(OUT, "TABLES.md"), "w").write("\n".join(L))


def first_witness(idx, build):
    best = None
    for m in MODELS[:4]:
        r = idx.get((build, "tampered_payload", m, True))
        if r and r["min_faults"] and (best is None or r["min_faults"] < len(best)):
            best = r["witness"]
    return [{k: w[k] for k in ("model", "pc", "file", "line", "asm", "effect")} for w in best] if best else None


def manifest_path():
    return os.path.join(ELF_DIR, "manifest.json")


if __name__ == "__main__":
    main()
