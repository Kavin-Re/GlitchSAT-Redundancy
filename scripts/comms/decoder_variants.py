#!/usr/bin/env python3
"""decoder_variants.py - License: UNDECIDED.

Communication-engineering experiment: give rtl/v2.v a real error-control decoder and measure what it does to the minimum
number of MODELLED single-cycle bit flips that reach the accept goal with a wrong key.
  v2         rtl/v2.v          reference
  v2e        rtl/v2e.v         reference (re-encoded pre-boot word)
  v2_secded  rtl/v2_secded.v   SECDED decoder (corrects 1, detects 2) between the state flops and every user
  v2c        rtl/v2c.v         detection-only consumer: boot_ok = (syndrome == 0) AND (st == 0x96)
Pre-registration (written before any solver run): research/c6/comms/P18_PREREG.md.

Steps per design: iverilog functional check (tb/tb_<design>.v for the two new designs: all 256 keys and every single
state-flop flip; the P11 256-key bench for v2/v2e) -> product CLI `faultbound-wt analyze --synth-sweep` (stem rule,
known init, inputs not sites, T cycles, k_max flips) for goal boot_word == 0x96 and goal boot_ok == 1, flops only and
all nets. A design that fails the functional check gets no solver run. A timeout is written 'unknown', a bounded
UNSAT '>k'. Neither means safe. Flow 'plain' = the project flow of scripts/synth.sh; hashes are those of the sweep
(source read as design.v) and are comparable only within this tool and Yosys version.

usage: decoder_variants.py --out results/comms/decoder_variants.csv [--log FILE] [--cli faultbound-wt] [--work DIR]
Toy designs, modelled faults, bounded (T, k_max). No physical claim; nothing established as new; no general claim about ECC.
"""
import argparse, csv, json, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import distance_sweep as ds   # read-only reuse: 256-key bench for the reference designs, yosys_version

KEY, W = 0xC3, 0x96
DESIGNS = ["v2", "v2e", "v2_secded", "v2c"]
GOALS = {"boot_word==0x96": ("boot_word", W), "boot_ok==1": ("boot_ok", 1)}
SITES = {"flops": '["flop"]', "all": '["gate", "flop"]'}
# Pre-registered predictions (research/c6/comms/P18_PREREG.md), plain flow only. v2/v2e are references, not predicted.
PREDICTED = {
    ("v2_secded", "boot_word==0x96", "flops"): "3", ("v2_secded", "boot_word==0x96", "all"): "2",
    ("v2c", "boot_word==0x96", "flops"): "4", ("v2c", "boot_word==0x96", "all"): "2",
    ("v2_secded", "boot_ok==1", "flops"): "3", ("v2c", "boot_ok==1", "flops"): "4",
    ("v2", "boot_ok==1", "all"): "1", ("v2e", "boot_ok==1", "all"): "1",
    ("v2_secded", "boot_ok==1", "all"): "1", ("v2c", "boot_ok==1", "all"): "1",
}
COLUMNS = ["design", "goal", "sites", "min_flips", "k_max", "T", "yosys", "flow", "netlist_sha256", "gates", "flops", "predicted"]
EXTRA_VARIANT = '[[variant]]\nname = "struct_no_abc"\ndescription = "no ABC: proc; techmap; flatten (RTL structure kept)"\nextends = "plain"\nabc = ""\n'


def functional_check(design, work):
    """Returns (ok, text). New designs: their own bench with single-flip injection. References: P11's 256-key bench."""
    v = os.path.join(ROOT, "rtl", design + ".v")
    tb = os.path.join(ROOT, "tb", f"tb_{design}.v")
    if not os.path.exists(tb):
        return ds.functional_check(v, W, top=design, workdir=work)
    out = os.path.join(work, f"tb_{design}.out")
    r = subprocess.run(["iverilog", "-g2005", "-o", out, tb, v], capture_output=True, text=True, timeout=120)
    if r.returncode:
        return False, "iverilog error: " + (r.stderr or r.stdout)[:400]
    r = subprocess.run(["vvp", "-n", out], capture_output=True, text=True, timeout=300)
    lines = [l for l in r.stdout.splitlines() if l.startswith(("FAIL", "FUNC_", "INFO"))]
    ok = r.returncode == 0 and "FUNC_PASS" in lines and not any(l.startswith("FAIL") for l in lines)
    return ok, "; ".join(lines[:3] + lines[-1:])[:400]


def sweep(cli, design, goal, sites, k, T, timeout_s, work):
    """One `analyze --synth-sweep` call. Returns list of (flow, cell, sha, gates, flops, witness)."""
    port, val = GOALS[goal]
    tag = f"{design}_{port}_{sites}"
    toml, var, rep = (os.path.join(work, tag + e) for e in (".toml", "_variants.toml", ".json"))
    with open(toml, "w") as f:
        f.write(f'[faults]\nmax_flips = {k}\ncycles = {T}\nkinds = {SITES[sites]}\ninput_sites = "none"\ninit = "known"\n'
                f'count_rule = "stem"\n[attacker]\ninput = "sig"\nmodel = "constant"\nlegitimate_value = 0x{KEY:02X}\n'
                f'[property]\noutput = "{port}"\nbad_value = 0x{val:02X}\n')
    with open(var, "w") as f:
        f.write(EXTRA_VARIANT)
    if os.path.exists(rep):
        os.remove(rep)
    cmd = cli + ["analyze", os.path.join(ROOT, "rtl", design + ".v"), "--top", design, "--config", toml, "--synth-sweep",
                 "--synth-variants", var, "--sweep-out", rep, "--timeout-s", str(timeout_s)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s * 12 + 60)
    except subprocess.TimeoutExpired:
        return [("plain", "unknown", "", "", "", "outer timeout")]
    if r.returncode not in (0, 1, 2) or not os.path.exists(rep):
        return [("plain", "unknown", "", "", "", f"cli exit {r.returncode}: {(r.stderr or r.stdout)[-200:]}")]
    rows = []
    for v in json.load(open(rep))["variants"]:
        verdict, cost = v.get("verdict"), str(v.get("cost", ""))
        if verdict == "ATTACK_FOUND" and re.fullmatch(r"\d+", cost):
            cell = cost
        elif verdict == "NO_ATTACK_UP_TO_BOUND":
            cell = f">{k}"
        else:   # timeout, unsupported, synth-failed, inexact: never a number, never 'no attack'
            cell = "unknown"
        rows.append((v["name"], cell, v.get("netlist_sha256", ""), v.get("gates", ""), v.get("flops", ""),
                     ",".join(v.get("faults") or []) or f"{v.get('status')}/{verdict}"))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--log", default=None, help="text log with functional-check output and witnesses")
    ap.add_argument("--work", default=None)
    ap.add_argument("--cli", default="faultbound-wt")
    ap.add_argument("--T", type=int, default=6)
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--timeout-s", type=int, default=300)
    ap.add_argument("--only", nargs="*", help="design names")
    a = ap.parse_args()
    work = a.work or tempfile.mkdtemp(prefix="p18_")
    os.makedirs(work, exist_ok=True)
    yv, cli, out_rows, log = ds.yosys_version(), a.cli.split(), [], []
    for d in [x for x in DESIGNS if not a.only or x in a.only]:
        ok, msg = functional_check(d, work)
        log.append(f"FUNC {d}: {'PASS' if ok else 'FAIL'} | {msg}")
        print(log[-1])
        if not ok:   # no solver run on a design that fails its functional check
            continue
        for goal in GOALS:
            for sites in SITES:
                for flow, cell, sha, gates, flops, wit in sweep(cli, d, goal, sites, a.k, a.T, a.timeout_s, work):
                    pred = PREDICTED.get((d, goal, sites), "") if flow == "plain" else ""
                    out_rows.append(dict(design=d, goal=goal, sites=sites, min_flips=cell, k_max=a.k, T=a.T, yosys=yv, flow=flow,
                                         netlist_sha256=sha, gates=gates, flops=flops, predicted=pred))
                    log.append(f"{d:10s} {goal:16s} {sites:5s} {flow:20s} min={cell:8s} pred={pred or '-':2s} witness: {wit}")
                    if flow == "plain":
                        print(log[-1])
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(out_rows)
    if a.log:
        with open(a.log, "w") as f:
            f.write("\n".join(log) + "\n")
    print(f"wrote {a.out} ({len(out_rows)} rows)")


if __name__ == "__main__":
    main()
