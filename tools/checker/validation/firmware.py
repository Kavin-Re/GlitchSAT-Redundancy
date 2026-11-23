#!/usr/bin/env python3
"""Firmware builds: repeated checks found in the C source vs what the compiled ELF still has, on the 108 builds of
ext/firmware (9 ROM variants x -O0/-O1/-O2/-Os x plain/volatile/barrier, hardware-MAC interface).

Ground truth (MEASURED by ext/firmware on its simulator, results/summary.json `redundancy_survival`): the number of
MAC compares executed in a good boot and the number of OTP minimum-version reads. A repeated check written N times is
"merged" in truth when fewer than N-0.5 of them are executed.
"""
import glob
import json
import os
import sys

from common import RESULTS, prf, prf_text
from survival import intent_fw, paths
from survival import stage_fw as SF


def main():
    fw = os.path.join(paths.ext_root(), "firmware")
    with open(os.path.join(fw, "results", "summary.json")) as f:
        s = json.load(f)
    gt = {r["build"]: r for r in s["redundancy_survival"]}
    faults = {r["build"]: r["tampered_payload"]["four_models"]["text"] for r in s["table"]}
    rows = []
    for elf in sorted(glob.glob(os.path.join(fw, "elf", "*-hw.elf"))):
        build = os.path.splitext(os.path.basename(elf))[0]
        variant = build.split("-")[0]
        src = os.path.join(fw, "src", variant + ".c")
        cms = intent_fw.scan([src], {"rom_main"})
        b = SF.Binary(elf)
        text = open(src).read()
        row = dict(build=build, variant=variant, opt=build.split("-")[1], mode=build.split("-")[2], checks=[],
                   min_faults=faults.get(build))
        for cm in cms:
            r = SF.check(cm, b, "firmware", text)
            d = dict(id=cm.id, kind=cm.kind, verdict=r.verdict, intended=cm.intent.get("copies"),
                     guards_present=r.measured.get("guards_present"), evaluations=r.measured.get("evaluations"))
            if cm.kind == "fw_repeated_check":
                is_mac = any("mac" in c for c in cm.intent.get("callees", []))
                executed = gt[build]["mac_compares_executed"] if is_mac else gt[build]["otp_min_version_reads"]
                d.update(truth_executed=executed, truth_merged=executed < cm.intent["copies"] - 0.5, what="MAC compare" if is_mac else "rollback check")
            row["checks"].append(d)
        rows.append(row)
    checks = [(r, c) for r in rows for c in r["checks"] if c["kind"] == "fw_repeated_check"]
    tp = sum(1 for r, c in checks if c["verdict"] != "SURVIVED" and c["truth_merged"])
    fp = sum(1 for r, c in checks if c["verdict"] != "SURVIVED" and not c["truth_merged"])
    fn = sum(1 for r, c in checks if c["verdict"] == "SURVIVED" and c["truth_merged"])
    summary = dict(builds=len(rows), builds_with_repeated_checks=sum(1 for r in rows if any(c["kind"] == "fw_repeated_check" for c in r["checks"])),
                   repeated_checks=len(checks), **prf(tp, fp, fn), text=prf_text(prf(tp, fp, fn)),
                   flagged=[dict(build=r["build"], check=c["what"], verdict=c["verdict"], intended=c["intended"],
                                 executed_in_truth=c["truth_executed"], min_faults=r["min_faults"]) for r, c in checks if c["verdict"] != "SURVIVED"],
                   truth_merged=[r["build"] + " / " + c["what"] for r, c in checks if c["truth_merged"]],
                   flow_counters=dict(found=sum(1 for r in rows for c in r["checks"] if c["kind"] == "fw_flow_counter"),
                                      verdicts={v: sum(1 for r in rows for c in r["checks"] if c["kind"] == "fw_flow_counter" and c["verdict"] == v)
                                                for v in ("SURVIVED", "WEAKENED", "REMOVED")},
                                      note="no ground truth recorded for flow counters: untested against truth"))
    with open(os.path.join(RESULTS, "firmware.json"), "w") as f:
        json.dump(dict(schema="glitchsat-survival-validation/firmware/1", rows=rows, summary=summary,
                       label="verdicts MEASURED here (static, ELF + line table); truth MEASURED by ext/firmware on its simulator"), f, indent=1)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
