# Formal cross-check with SymbiYosys (formal/)

Label: MEASURED. All verdicts are for the stated fault model (modelled single-cycle bit flips on gate outputs and flop Q nets, `sig` free but constant and != 0xC3, goal `boot_word == 0x96` observed at some cycle). Toy designs. Not physical.

## 1. Install (what worked, what did not)
| route | result |
|---|---|
| conda `micromamba create -n formal -c litex-hub -c conda-forge symbiyosys yosys` (MAMBA_ROOT_PREFIX=/tmp/mm_root) | **worked**, 2m45s, env 264 MB. Gives sby (litex-hub `symbiyosys 0.0.0_0074_g091222b`), Yosys 0.38+92, yosys-smtbmc, yosys-abc, boolector, btormc, z3 binary (3.2.1 boolector reported by `boolector --version`) |
| conda specs `boolector`, `yices`, `z3` as separate packages | solver said "does not exist" in litex-hub/conda-forge (first attempt, `logs/conda_create1.log`); boolector and z3 binaries still arrive as dependencies of symbiyosys |
| `yices-smt2` | **not available** (not installed by any route tried). Consequence: sby cannot rebuild counterexample traces for `abc pdr` FAIL results (it tries yices); the engine verdict FAIL is still in the logfile. |
| pip | z3-solver 5.4.1, pyboolector, `yices` (1.1.6, a different, old package) are listable; not needed. sby is not on PyPI. |
| apt | yosys 0.33 and boolector 1.5 present (pre-installed), sby/yices2 not available |
Use: `export PATH=/tmp/mm_root/envs/formal/bin:$PATH` (note this env's `python3` has no z3 module; run `scripts/glitchsat.py` with `/usr/bin/python3`). The `eda` env and /tmp/mm_root2 were not touched. Versions: `logs/versions.log`.

## 2. Formulation (`src/gen_wrapper.py`)
Input: a flattened Yosys JSON gate netlist (the same format glitchsat reads). Output `gen/fi_*.sv`: the netlist re-expressed as continuous assigns where every gate-output net and every flop Q net is XORed with a free 1-bit input `flip[i]` for that cycle only (Q flip does not change stored state, same as glitchsat). A 16-bit running counter `used` accumulates popcount(flip); `assume(used + this <= K)` gives at most K flips over the whole run. `assume(sig != 8'hC3)` every cycle, `assume(sig == previous sig)`. `assert(boot_word != 8'h96)` on the (possibly faulted) observed nets. Flop initial values are taken from the netlist. `src/matrix.py`, `matrix2.py`, `prove.py` drive sby (`mode bmc`, `depth 6`, engine `smtbmc boolector`; depth 6 = cycles 0..5 = glitchsat N=6).
Sanity (non-vacuity): with `assume(sig == 8'hC3)` and k=0 the assert FAILS for V0, V1, V2 (honest key boots; in `runs/bmc_matrix.json`, honest=true) and for the pdr runs on s2 and w2. k=0 with attacker input PASSES everywhere.

Netlists compared (all different synthesis results of the same RTL; the verdict depends on it):
- `v*`: `scripts/synth.sh rtl/vN.v plain` re-run in the conda `formal` environment (Yosys 0.38+92): v2 has 37 AND, 25 OR, 20 NOT, 1 MUX, 8 DFF (83 gates). CORRECTION (2026-11-19, later check): an earlier version of this file said Yosys 0.33 gives the identical netlist. That is wrong. With apt Yosys 0.33 the same script gives 40 AND, 25 OR, 20 NOT, 8 DFF (85 gates) and a 2-fault attack; see section 3.
- `s*`: `reference/spike_netlists/v{0,1,2}.json` (the spike's).
- `w*`: copies of `results/work/v{0,1,2}.json` and `v2_opt.json` as found on disk (the netlists behind results/reproduce_summary.json; v2 has 40 AND, no MUX). `results/work/` is a shared, overwritten scratch dir, so these copies are the stable reference.

## 3. Bounded results: sby BMC depth 6 vs glitchsat (z3), same netlist files
Each pair = sby `smtbmc boolector` verdict and `glitchsat.py check --cycles 6` on the identical JSON. **40 netlist/k pairs, 0 disagreements** (full table with runtimes: `runs/bmc_matrix*.json`, `runs/glitchsat_crosscheck.json`; sby wall time 0.16-1.7 s each, all runs).

| design / netlist | k=0 | k=1 | k=2 | k=3 |
|---|---|---|---|---|
| V0 (v, s, w) | no CEX | CEX | CEX | CEX |
| V1 (v, s, w) | no CEX | CEX | CEX | CEX |
| V2 spike netlist (s2) | no CEX | no CEX | no CEX | CEX (glitchsat min 3) |
| V2 re-synthesized here (v2, conda Yosys 0.38+92; apt Yosys 0.33 gives the 85-gate netlist instead, like w2) | no CEX | no CEX | **no CEX** | CEX (min 3) |
| V2 repo's results/work netlist (w2) and opt flow (w2o) | no CEX | no CEX | **CEX** (min 2) | CEX |

"no CEX" = sby PASS, i.e. no attack with <= k flips within 6 cycles (bounded). Comparison with `results/reproduce_summary.json`: V0, V1 (all k), V2 spike (k<=2 none, k=3 attack) and V2 w-netlist (k=2 attack, min 2) all reproduce under sby. One discrepancy to flag against the headline in ENGINE_STATUS.md: re-running `synth.sh` on `rtl/v2.v` in the `formal` environment (conda Yosys 0.38+92) did not give the 40-AND netlist that the stored `results/work/v2.json` has, and on that netlist **both z3 and sby find no 2-fault attack**. Cause now found (later check, MEASURED): the Yosys build. The same `scripts/synth.sh` gives 85 gates (40 AND, 25 OR, 20 NOT, 8 DFF) and a 2-fault attack with apt Yosys 0.33 (the build behind the stored netlist), and 83 gates (37 AND, 25 OR, 20 NOT, 1 MUX, 8 DFF) and no 2-fault attack with conda Yosys 0.38+92; k=3 breaks it with min 3. Why ABC differs between the two builds was not analysed. So "re-synthesized V2 has a 2-fault attack" holds for Yosys 0.33, not for 0.38+92. This confirms that the claim is netlist (and tool build) dependent.

## 4. Unbounded attempts (sby `mode prove`)
| netlist | k | engine | result | time |
|---|---|---|---|---|
| s2 (V2 spike) | 0 | abc pdr | PASS: "Property proved" | 0.32 s engine |
| s2 | 1 | abc pdr | **PASS: property proved (unbounded in time)** | 0.56 s |
| s2 | 2 | abc pdr | **PASS: property proved (unbounded in time)**, invariant of 10 clauses on 10 of 35 flops, verified by ABC | 0.78 s |
| s2 | 3 | abc pdr | FAIL (counterexample exists; trace not rebuilt, yices missing) | |
| w2 | 1 | abc pdr | PASS: proved | 0.76 s |
| w2 | 2 | abc pdr | FAIL (counterexample) | |
| s1 (V1), s0 (V0) | 1 | abc pdr | FAIL (counterexample) | |
| s2 | 1, 2 | smtbmc boolector k-induction, depth 20 | **inconclusive**: base case holds, inductive step fails (step counterexample, from a state not shown reachable); sby status UNKNOWN, 16-21 s | |
| w2 | 1 | k-induction depth 20 | inconclusive (UNKNOWN), 31 s | |
Non-vacuity of the pdr proofs: same wrapper with `sig == 0xC3`, k=0 gives FAIL under pdr on s2 and w2, so the assert is reachable and the constraints are not contradictory.

### What is proven, exactly
- Proven by ABC PDR (sby reports PASS, "Property proved") on `reference/spike_netlists/v2.json` and k = 1 or 2: for **any number of cycles**, with `sig` constant and != 0xC3, no set of at most k single-cycle flips on any gate-output or flop-Q net (any cycles, total over the whole run) makes `boot_word` equal 0x96. Also k=1 on the stored `results/work/v2.json`.
- Not proven: any statement beyond this fault model (stuck-at, multi-bit/spatial, clock/voltage, non-constant `sig`, or faults on the wrapper's own counter, which is not a fault site); other synthesis results of V2; V2 with k>=3 (a counterexample exists on the spike netlist); V0 and V1 (counterexamples at k=1). The model and wrapper are mine and share semantics with glitchsat; an error in that shared reading of the netlist (my generator is independent code, but written to the same stated model) would not be caught. The wrapper models netlists, not RTL, and not Yosys-vs-RTL equivalence.
- The k-induction engine could not prove anything without strengthening; PDR did the unbounded work. PDR is trusted as ABC's checked-invariant result (it prints that it verified the invariant); no independent proof certificate was exported.

## 5. Reproduce
```
export PATH=/tmp/mm_root/envs/formal/bin:$PATH
cd formal
python3 src/matrix.py runs/bmc_matrix.json     # v*, s* netlists, k=0..3 plus honest sanity
python3 src/matrix2.py                          # w* netlists
/usr/bin/python3 src/gs_crosscheck.py           # glitchsat on the same files
TMO=300 python3 src/prove.py                    # abc pdr and k-induction
```
Logs in `logs/`, sby work directories in `runs/` (each has `logfile.txt`; counterexample VCDs for smtbmc FAILs).


> Tool-build labels: apt Yosys is 0.33. The conda package is `yosys-0.38_93_g84116c9a3` (litex-hub, 2024-02-23); its binary banner prints 'Yosys 0.38+92 (git sha1 84116c9a3)': same source. Where this repo writes 'conda 0.38+92' it means that package. Always record the Yosys build and the netlist gate count next to any V2 verdict.
