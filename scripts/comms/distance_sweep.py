#!/usr/bin/env python3
"""distance_sweep.py - License: UNDECIDED.

Communication-engineering experiment: treat the boot state words of rtl/v2.v as a CODE and measure, per codebook,
the minimum number of MODELLED single-cycle bit flips that reach the accept word W
  (1) when only flops are fault sites ("flops only": product threat-model key  [faults] kinds = ["flop"]) and
  (2) when every gate output and flop Q is a site ("all nets", the product default).
Pre-registration: research/c6/p11/PREREG.md (written before the first run).

Steps per codebook: generate Verilog (rtl/v2.v structure, constants substituted) -> iverilog functional check
(honest key boots, wrong keys never boot, power-up not accepted) -> synthesis (scripts/synth.sh plain, plus a no-ABC
structural flow) -> product CLI `faultbound-wt analyze` (stem rule, goal boot_word == W, known init, T cycles).
A timeout is written as 'unknown', a bounded UNSAT as '>k'. Neither means safe.

usage: distance_sweep.py --out results/comms/distance_sweep.csv [--work DIR] [--cli faultbound-wt] [--jobs 4]
       distance_sweep.py --only F0_96 ...
Toy design, modelled faults, bounded (T, k_max). No physical claim; nothing established as new.
"""
import argparse, csv, hashlib, itertools, json, os, re, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
KEY = 0xC3
DEFAULT_GROUPING = "10210210"   # owner copy of bit7..bit0, as sel={m1,m0,m2,m1,m0,m2,m1,m0} in rtl/v2.v
T_DEFAULT = 6


def pop(x):
    return bin(x & 0xFF).count("1")


# ----------------------------------------------------------------------------- codebooks
def codebooks():
    """(name, idle I, step C or None, accept W, fail B, grouping, kind). Fixed in PREREG.md."""
    cb = [
        ("F0_96_stored", 0xF0, 0xCC, 0x96, 0x69, DEFAULT_GROUPING, "named"),
        ("CC_96", 0xCC, 0xF0, 0x96, 0x69, DEFAULT_GROUPING, "named"),
        ("69_96_complement", 0x69, None, 0x96, 0x69, DEFAULT_GROUPING, "named"),
        ("2B_95", 0x2B, 0x69, 0x95, 0x6A, DEFAULT_GROUPING, "named"),
        ("C3_3C_complement", 0xC3, None, 0x3C, 0xC3, DEFAULT_GROUPING, "named"),
        ("A5_5A_complement", 0xA5, None, 0x5A, 0xA5, DEFAULT_GROUPING, "named"),
        ("A5_96", 0xA5, 0x66, 0x96, 0x69, DEFAULT_GROUPING, "named"),
        ("A5_A6", 0xA5, 0x66, 0xA6, 0x59, DEFAULT_GROUPING, "named"),
        ("00_1F_F8_E7", 0x00, 0xF8, 0x1F, 0xE7, DEFAULT_GROUPING, "named"),
    ]
    for d in range(1, 8):   # distance family: I = W xor low d bits, C = W xor high d bits, B = ~W
        w = 0x96
        cb.append((f"fam_d{d}", w ^ ((1 << d) - 1), w ^ (((1 << d) - 1) << (8 - d)), w, 0x69, DEFAULT_GROUPING, "family"))
    cb += [
        ("Bvar_one_copy", 0x69, None, 0x96, 0x96 ^ 0x49, DEFAULT_GROUPING, "ceiling"),   # B xor W = bits 0,3,6 (copy m0 only)
        ("Bvar_two_copies", 0x69, None, 0x96, 0x96 ^ 0xDB, DEFAULT_GROUPING, "ceiling"),  # bits of m0 and m1 only
        ("ctrl_one_copy_grouping", 0xF0, 0xCC, 0x96, 0x69, "00000000", "control"),
        ("NEG_fail_equals_accept", 0xF0, 0xCC, 0x96, 0x96, DEFAULT_GROUPING, "negative"),  # wrong keys would boot
        ("NEG_idle_equals_accept", 0x96, 0xCC, 0x96, 0x69, DEFAULT_GROUPING, "negative"),  # power-up accepted
    ]
    return cb


# ----------------------------------------------------------------------------- model-side predictions
def owners(grouping):
    """bit index -> copy index. grouping string is written bit7..bit0."""
    if not re.fullmatch(r"[012]{8}", grouping):
        raise ValueError("grouping must be 8 characters from 0,1,2 (owner copy of bit7..bit0)")
    return {7 - i: int(c) for i, c in enumerate(grouping)}


def copies_touched(B, W, grouping):
    own = owners(grouping)
    return len({own[b] for b in range(8) if ((B ^ W) >> b) & 1})


def d_min(I, C, W, B):
    return min(pop(x ^ W) for x in (I, C, B) if x is not None)


def rule(I, C, W, B, grouping):
    """M1 rule for the full-word consumer: min(state route, min over copy subsets S of |S| + bits of B^W not owned by S)."""
    own = owners(grouping)
    need = [b for b in range(8) if ((B ^ W) >> b) & 1]
    best = d_min(I, C, W, B)
    for r in range(4):
        for S in itertools.combinations(range(3), r):
            best = min(best, len(S) + sum(1 for b in need if own[b] not in S))
    return best


# ----------------------------------------------------------------------------- generator
def gen_verilog(I, W, B, C=None, grouping=DEFAULT_GROUPING, top="v2"):
    """Verilog variant of rtl/v2.v. I = idle word (flop init), C = optional step word (second pre-boot state),
    W = accept word, B = fail word. Structure kept: three cmp8 copies, sel grouping, per-bit select of good/bad."""
    for n, v in (("I", I), ("W", W), ("B", B)) + ((("C", C),) if C is not None else ()):
        if not (isinstance(v, int) and 0 <= v <= 0xFF):
            raise ValueError(f"{n} must be an 8-bit value")
    if C is not None and C == I:
        raise ValueError("step word C must differ from idle word I")
    own = owners(grouping)
    sel = ",".join(f"m{own[b]}" for b in range(7, -1, -1))
    h = lambda v: f"8'h{v:02X}"
    if C is None:
        arms = f"    {h(I)}: st <= word;\n"
    else:
        arms = f"    {h(I)}: st <= {h(C)};\n    {h(C)}: st <= word;\n"
    return (
        f"// Generated (scripts/comms/distance_sweep.py). Variant of rtl/v2.v: idle {h(I)}, step {h(C) if C is not None else 'none'}, "
        f"accept {h(W)}, fail {h(B)}, grouping {grouping}. KEY = 8'hC3. Toy design.\n"
        "(* keep_hierarchy *) module cmp8(input [7:0] a, output m);\n"
        "  assign m = (a == 8'hC3);\n"
        "endmodule\n\n"
        f"module {top}(input clk, input [7:0] sig, output boot_ok, output [7:0] boot_word);\n"
        f"  (* keep *) reg [7:0] st; initial st = {h(I)};\n"
        "  wire m0, m1, m2; cmp8 c0(.a(sig), .m(m0)); cmp8 c1(.a(sig), .m(m1)); cmp8 c2(.a(sig), .m(m2));\n"
        f"  wire [7:0] good = {h(W)}, bad = {h(B)};\n"
        f"  (* keep *) wire [7:0] sel = {{{sel}}}; // per-bit match\n"
        "  (* keep *) wire [7:0] word = (sel & good) | (~sel & bad);\n"
        "  always @(posedge clk) case (st)\n"
        f"{arms}"
        "    default: st <= st;\n"
        "  endcase\n"
        "  assign boot_word = st;\n"
        f"  assign boot_ok = (st == {h(W)});\n"
        "endmodule\n")


TB = r"""
`timescale 1ns/1ps
module tb;
  reg clk = 0; integer t, i; integer bad = 0; integer honest_ok = 0;
  wire [255:0] ok; wire [8*256-1:0] w;
  genvar g;
  generate for (g = 0; g < 256; g = g + 1) begin : G
    wire [7:0] s = g;
    TOPNAME u(.clk(clk), .sig(s), .boot_ok(ok[g]), .boot_word(w[8*g +: 8]));
  end endgenerate
  initial begin
    #1;
    for (i = 0; i < 256; i = i + 1)
      if (ok[i] || w[8*i +: 8] == 8'hWW) begin bad = bad + 1; $display("FAIL power-up accepted sig=%0d", i); end
    for (t = 0; t < 10; t = t + 1) begin
      #5 clk = 1; #5 clk = 0; #1;
      for (i = 0; i < 256; i = i + 1)
        if (i != 8'hC3 && (ok[i] || w[8*i +: 8] == 8'hWW)) begin bad = bad + 1; $display("FAIL wrong key boots sig=%0d t=%0d", i, t); end
      if (t >= 3 && !(ok[8'hC3] && w[8*8'hC3 +: 8] == 8'hWW)) begin bad = bad + 1; $display("FAIL honest key not booted t=%0d", t); end
      if (ok[8'hC3] !== (w[8*8'hC3 +: 8] == 8'hWW)) begin bad = bad + 1; $display("FAIL boot_ok/boot_word disagree"); end
    end
    if (bad == 0) $display("FUNC_PASS"); else $display("FUNC_FAIL %0d", bad);
    $finish;
  end
endmodule
"""


def functional_check(vfile, W, top="v2", workdir=None):
    """iverilog: all 256 keys in parallel, 10 clock edges. Returns (ok, first lines of output)."""
    wd = workdir or tempfile.mkdtemp(prefix="p11_tb_")
    tb = os.path.join(wd, "tb_" + os.path.basename(vfile))
    with open(tb, "w") as f:
        f.write(TB.replace("TOPNAME", top).replace("WW", f"{W:02X}"))
    vvp = tb + ".out"
    r = subprocess.run(["iverilog", "-g2005", "-o", vvp, tb, vfile], capture_output=True, text=True, timeout=120)
    if r.returncode:
        return False, "iverilog error: " + (r.stderr or r.stdout)[:400]
    r = subprocess.run(["vvp", "-n", vvp], capture_output=True, text=True, timeout=120)
    try:
        os.remove(vvp)
    except OSError:
        pass
    out = [l for l in r.stdout.strip().splitlines() if l.startswith(("FAIL", "FUNC_"))]
    return (r.returncode == 0 and out == ["FUNC_PASS"]), "; ".join(out[:2] + out[-1:])[:200]


# ----------------------------------------------------------------------------- synthesis
def synth_plain(vfile, top, out):
    """Project flow: scripts/synth.sh <v> <top> <json> plain (system yosys = apt 0.33)."""
    # run inside the netlist's directory with relative names: yosys writes source paths into the JSON, so this keeps the hash path-independent
    subprocess.run(["sh", os.path.join(ROOT, "scripts", "synth.sh"), os.path.basename(vfile), top, os.path.basename(out), "plain"],
                   check=True, timeout=300, capture_output=True, cwd=os.path.dirname(os.path.abspath(out)))


def synth_struct(vfile, top, out):
    """No-ABC structural flow (stand-in for a netlist where the RTL copies stay unshared): proc; techmap; flatten."""
    scr = out + ".ys"
    with open(scr, "w") as f:
        f.write(f'read_verilog "{os.path.basename(vfile)}"\nhierarchy -top {top}\nproc\nopt_clean\ntechmap\nopt_clean\n'
                f'setattr -mod -unset keep_hierarchy *\nflatten\nopt_clean\nwrite_json "{os.path.basename(out)}"\n')
    subprocess.run(["yosys", "-q", "-s", os.path.basename(scr)], check=True, timeout=300, capture_output=True, cwd=os.path.dirname(os.path.abspath(out)))


def yosys_version():
    r = subprocess.run(["yosys", "-V"], capture_output=True, text=True, timeout=60)
    m = re.search(r"Yosys (\S+)", r.stdout)
    return m.group(1) if m else "unknown"


def sha256(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


# ----------------------------------------------------------------------------- measurement (product CLI)
def measure(cli, netlist, top, W, k, T, flops_only, timeout_s, workdir, tag):
    """Returns (cell, detail). cell: '<n>' minimum found | '>k' no attack with <= k flips in T cycles | 'unknown'."""
    toml = os.path.join(workdir, f"{tag}.toml")
    rep = os.path.join(workdir, f"{tag}.json")
    with open(toml, "w") as f:
        f.write(f'[faults]\nmax_flips = {k}\ncycles = {T}\nkinds = {"[\"flop\"]" if flops_only else "[\"gate\", \"flop\"]"}\n'
                f'input_sites = "none"\ninit = "known"\ncount_rule = "stem"\n'
                f'[attacker]\ninput = "sig"\nmodel = "constant"\nlegitimate_value = 0x{KEY:02X}\n'
                f'[property]\noutput = "boot_word"\nbad_value = 0x{W:02X}\n')
    if os.path.exists(rep):
        os.remove(rep)
    cmd = cli + ["analyze", netlist, "--top", top, "--config", toml, "--report", rep, "--timeout-s", str(timeout_s)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s + 60)
    except subprocess.TimeoutExpired:
        return "unknown", "outer timeout"
    if r.returncode not in (0, 1, 2) or not os.path.exists(rep):
        return "unknown", f"cli exit {r.returncode}: {(r.stderr or r.stdout)[-300:]}"
    j = json.load(open(rep))
    v = j.get("verdict")
    if v == "ATTACK_FOUND" and r.returncode == 1:
        wit = ",".join(f"{x['net']}@{x['cycle']}" for x in j.get("faults", []))
        return str(j["min_faults"]), wit
    if v == "NO_ATTACK_UP_TO_BOUND" and r.returncode == 0:
        return f">{k}", "no attack with <= k flips within T (bounded; not 'safe')"
    return "unknown", f"verdict {v} exit {r.returncode}"


def run_codebook(cb, args, cli, yv):
    name, I, C, W, B, grouping, kind = cb
    t0 = time.time()
    wd = os.path.join(args.work, name)
    os.makedirs(wd, exist_ok=True)
    d = pop(I ^ W)
    row = dict(codebook=name, idle=f"{I:02X}", accept=f"{W:02X}", d_to_accept=d,
               copies_touched_by_xor=copies_touched(B, W, grouping), min_flops="", min_all="", yosys=yv, T=args.T,
               k_max=min(d, 6), netlist_sha256="", step="" if C is None else f"{C:02X}", fail=f"{B:02X}", grouping=grouping,
               kind=kind, d_min=d_min(I, C, W, B), rule_pred=rule(I, C, W, B, grouping), min_flops_struct="", min_all_struct="",
               struct_sha256="", status="", witness_all="", wall_s="")
    vfile = os.path.join(wd, name + ".v")
    with open(vfile, "w") as f:
        f.write(gen_verilog(I, W, B, C, grouping))
    ok, msg = functional_check(vfile, W, workdir=wd)
    if not ok:   # no solver run on a design that fails the functional check
        row["status"] = "rejected_by_functional_check: " + msg
        row["k_max"] = ""
        row["wall_s"] = round(time.time() - t0, 1)
        return row
    k = max(1, min(d, 6))
    jp, js = os.path.join(wd, name + "_plain.json"), os.path.join(wd, name + "_struct.json")
    synth_plain(vfile, "v2", jp)
    synth_struct(vfile, "v2", js)
    row["netlist_sha256"], row["struct_sha256"] = sha256(jp), sha256(js)
    row["min_flops"], _ = measure(cli, jp, "v2", W, k, args.T, True, args.timeout_s, wd, "flops_plain")
    row["min_all"], row["witness_all"] = measure(cli, jp, "v2", W, k, args.T, False, args.timeout_s, wd, "all_plain")
    row["min_flops_struct"], _ = measure(cli, js, "v2", W, k, args.T, True, args.timeout_s, wd, "flops_struct")
    row["min_all_struct"], _ = measure(cli, js, "v2", W, k, args.T, False, args.timeout_s, wd, "all_struct")
    row["status"] = "measured" if "unknown" not in (row["min_flops"], row["min_all"], row["min_flops_struct"], row["min_all_struct"]) else "measured_with_unknown"
    row["wall_s"] = round(time.time() - t0, 1)
    return row


COLUMNS = ["codebook", "idle", "accept", "d_to_accept", "copies_touched_by_xor", "min_flops", "min_all", "yosys", "T", "k_max",
           "netlist_sha256", "step", "fail", "grouping", "kind", "d_min", "rule_pred", "min_flops_struct", "min_all_struct",
           "struct_sha256", "status", "witness_all", "wall_s"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--work", default=None, help="work directory for generated Verilog, netlists and reports")
    ap.add_argument("--cli", default="faultbound-wt", help="product CLI command (may contain spaces, e.g. 'python -m faultbound_wt.cli')")
    ap.add_argument("--T", type=int, default=T_DEFAULT)
    ap.add_argument("--timeout-s", type=int, default=300, help="wall-clock limit per solver run; a timeout is written 'unknown'")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--only", nargs="*", help="codebook names to run")
    args = ap.parse_args()
    args.work = args.work or tempfile.mkdtemp(prefix="p11_sweep_")
    os.makedirs(args.work, exist_ok=True)
    cbs = [c for c in codebooks() if not args.only or c[0] in args.only]
    yv = yosys_version()
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        rows = list(ex.map(lambda c: run_codebook(c, args, args.cli.split(), yv), cbs))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    for r in rows:
        print(f"{r['codebook']:26s} d={r['d_to_accept']} dmin={r['d_min']} rule={r['rule_pred']} flops={r['min_flops']} all={r['min_all']} "
              f"| struct flops={r['min_flops_struct']} all={r['min_all_struct']} | {r['status'][:60]}")
    print(f"total wall {time.time() - t0:.1f}s; wrote {args.out}")


if __name__ == "__main__":
    main()
