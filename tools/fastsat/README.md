# fastsat: direct-CNF SAT backend for GlitchSAT

`tools/fastsat/scripts/glitchsat_sat.py` answers the same bounded question as `scripts/glitchsat.py check`
(smallest number of modelled single-cycle bit flips, at most `k`, within `N` cycles, that makes the goal port show
the goal value while the attacker input differs from the key), but solves it as plain CNF with a SAT solver
instead of z3 terms. `scripts/glitchsat.py` is not modified; its `Netlist` parser, `coi_and_dist`, `explain`, `NOTE`
and input checks are imported (z3 is not needed).

Labels used below: **MEASURED HERE** = produced by a command run in the build environment (2 vCPU Xeon 2.1 GHz,
Python 3.13, numpy 2.5, no z3, no PySAT, no SAT binary, no Yosys; the machine was shared with other jobs during some
runs, so timings are indicative only); **TO CONFIRM (cloud)** = written and exercised here only against stand-ins,
to be run for real by `cloud_bench.sh` on the cloud VM (Ubuntu 24.04, `pip install python-sat z3-solver`, apt
Yosys). All verdicts are bounded (k flips, N cycles), exactly as in the z3 engine.

## 1. Status in one table

| Item | Status |
|---|---|
| Encoder, cardinality, fault collapsing, witness replay | MEASURED HERE: correct on every check in section 6 (0 disagreements) |
| Minimum flips vs `results/reproduce` and docs/NUMBERS.md | MEASURED HERE: all equal (section 6, first table) |
| Cross-check against the `tools/surface` exhaustive enumerator | MEASURED HERE: 0 mismatches (section 6 (c)) |
| Bundled pure-Python CDCL (`minicdcl.py`) | MEASURED HERE (all results in this file were produced with it) |
| z3 agreement/timing table (`bench.py --z3`) | Table logic MEASURED HERE with stand-ins for the z3 engine (verdict parsing, crash, hang, disagreement fails the run). Real z3 numbers: TO CONFIRM (cloud) |
| PySAT backend (CaDiCaL/Glucose/...) | TO CONFIRM (cloud). The adapter was run only against a stand-in module (`tests/fake_pysat`) with the same method names |
| External DIMACS solver backend (`dimacs:kissat`, ...) | TO CONFIRM (cloud); here run against the bundled solver wrapped as a DIMACS binary |
| The R20 target (2,040-gate `sbox_dmr`, k=3) | TO CONFIRM (cloud). Its netlist is not stored in the repository and Yosys is not installed here. Only proxy netlists of similar size were run (section 7). The goal/key/horizon `bench.py` uses for R20 are tested against `research/c3/r20/out/*.json` |
| Any speed comparison with z3 | NOT MEASURED HERE (z3 is not installed). No speed-up is claimed; TO CONFIRM (cloud) |

## 2. Use

```
python3 tools/fastsat/scripts/glitchsat_sat.py check reference/spike_netlists/v2.json --top v2 --k 3 --cycles 6
python3 tools/fastsat/scripts/glitchsat_sat.py sweep reference/spike_netlists/v2.json --top v2 --k 3 --cycles 6
python3 tools/fastsat/scripts/glitchsat_sat.py cnf   reference/spike_netlists/v2.json --top v2 --k 3 --cycles 6
```

`check` takes every flag of `glitchsat.py check` (`--top --k --cycles --out --reduce --goal-out --goal-value
--attack-input --key --timeout-ms --flow`, and `--amk`, which is accepted and ignored) plus:

| Flag | Meaning |
|---|---|
| `--backend auto` | default: PySAT CaDiCaL when `python-sat` is importable, else the bundled Python solver |
| `--backend py` | bundled pure-Python CDCL (always available, slow) |
| `--backend pysat:<name>` or `<name>` | a PySAT solver: `cadical` (newest CaDiCaL that the installed PySAT lists), `cadical195`, `cadical153`, `glucose4`, `glucose42`, `minisat22`, ... The name is looked up in `pysat.solvers.SolverNames` at run time |
| `--backend dimacs:<binary>` | a solver binary on PATH that reads DIMACS and prints `s SATISFIABLE` / `v ...` (Kissat, CaDiCaL, CryptoMiniSat). One process per budget. Extra arguments: env `GLITCHSAT_DIMACS_ARGS` |
| `--card totalizer\|seqcounter` | at-most-k encoding (default totalizer) |
| `--no-collapse` | every time-relevant fault site keeps its own variable |
| `--fault-enc xor\|relax` | exact flip (default) or "selector frees the net" |
| `--dimacs-out FILE` | also write the CNF |

Result JSON: the same fields as `run_check` (`label, tool, design, design_sha256_16, top, synth_flow, verdict, bound,
note, netlist, honest_key_boots_fault_free, model, runtime_s, netlist_json`, and on an attack `min_faults, faults,
attacker_input, attacker_input_raw, explanation`) plus `"backend": "sat:<solver>"`. `model` keeps `sites_total`,
`sites_modelled`, `reduce`, `build_s`, `solve_s`, `minimize_s` with the engine's meaning and adds `fault_vars`,
`sites_collapsed`, `cnf` (vars, clauses, literals), `amk` (the cardinality encoding) and `minimum_proved`.
Exit codes: 0 verdict, 2 unknown/timeout, 3 input error or backend not installed, 4 internal error.

Differences a caller can see:
- `tool` is `glitchsat_sat.py`; the witness may be a different minimum-size fault set than z3 reports (the repository
  already records that z3 witnesses vary between runs: `T.repro.witness` in docs/NUMBERS.md).
- `--timeout-ms` limits the whole search (first solve plus minimisation), not each solver call.
- If the limit is hit during minimisation, the verdict is ATTACK_FOUND with the witness found so far and
  `model.minimum_proved = false`; the CLI prints "minimum NOT proved". (The z3 engine reports the same situation
  without a marker.)
- `sweep` is new: one CNF and one solver instance, budgets 0..k as assumptions in ascending order.

Python API: `glitchsat_sat.solve(nl, N, k, backend=..., **kw)` mirrors `glitchsat.solve`; also `run_check`, `sweep`,
`honest_boots`, `encode`.

## 3. Encoding

1. **Unrolling.** One CNF variable per free input bit (every input port except `clk`, constant over the run, as in
   `build()`). Flops start at their `init` value (constant). Cycle by cycle, gates are visited in topological order;
   the next state of a flop is the literal of its D net. Only nodes that can reach a goal bit before the horizon are
   built (`t + dist[b] <= N-1`, with `dist` from `Netlist.coi_and_dist`).
2. **Gates.** Tseitin clauses for AND, XOR and MUX (MUX with the two redundant clauses); OR is an AND by De Morgan
   and NOT is a negated literal, so they cost nothing. Constants are folded (variable 1 is the constant TRUE) and
   identical fault-free gates are shared (structural hashing).
3. **Fault selector.** A site with a fault variable `f` gets `out = gate(inputs) XOR f`. For AND and MUX the XOR is
   merged into the gate clauses (each gate clause once with `f`, once with the output negated and `-f`), so no
   extra variable is needed. A flop Q at cycle t is `state XOR f`.
4. **Goal.** `h_t -> (goal bit i == goal value bit i)` for every bit, plus the clause `h_0 v ... v h_{N-1}`.
   Attacker input: one clause "differs from the key in some bit".
5. **At most k.** A totalizer over the fault variables (leaves ordered by cycle, then topological position),
   truncated at k+1 outputs, clauses in the direction "inputs force outputs" only. "At most j" is the single
   assumption `-out[j+1]`, so one instance answers every budget j <= k and clauses learned at one budget stay
   valid at the next.
   Why a totalizer rather than the sequential counter: both have about n(k+1) auxiliary variables and both
   propagate "one more flip is impossible" by unit propagation; the totalizer has depth log2(n) instead of n,
   so implication chains between a fault variable and the budget literal are short. This is a design argument;
   on the one ablation run here (section 7.3) the two were within noise of each other. `--card seqcounter` builds
   the same counter as `glitchsat.seq_counter`.
6. **Search order.** `check` does what `glitchsat.solve` does: ask for <= k, then tighten to (found - 1) until
   UNSAT. `sweep` goes upward from 0.

## 4. Soundness argument

Claim: for every netlist, bound and goal, the CNF with assumption "at most j" is satisfiable if and only if the
model of `glitchsat.build()` has an attack with at most j flips. Steps:

- *Same semantics.* Inputs, init values, gate functions, flip semantics, goal and key constraint are transcribed
  from `build()`; Tseitin encoding, constant folding and structural hashing preserve equivalence. The goal uses
  implications only; `h_t` occurs only positively elsewhere, so this keeps satisfiability.
- *Nodes outside the time-relevant cone.* `dist[b]` is the minimum number of clock edges from `b` to a goal bit.
  If `b` is outside the cone or `t + dist[b] > N-1`, no value of `b` at cycle `t` reaches a goal bit at a cycle
  < N, so its logic and its fault can be dropped. Under `--reduce none/coi` the engine gives such sites a fault
  variable that occurs only in the at-most-k constraint; fixing it to 0 never loses a model. `sites_modelled`
  still reports the engine's count.
- *Fault collapsing.* Site (t, b) gets no variable when b is not a goal bit and exactly one time-relevant cell
  reads it: a gate h (dominator (t, h)) or a flop with output q (dominator (t+1, q)). The flip of b can affect
  the goal only through that reader, and its whole effect there is "reader output flipped" or "unchanged". Given
  an attack that uses (t, b): if the reader output is unchanged, remove the flip; if it is flipped and the
  dominator is not in the attack, replace (t, b) by the dominator; if the dominator is already in the attack, the
  two cancel and both are removed. The goal bits at every cycle are unchanged and the number of flips does not
  grow. The replacement moves strictly forward in (cycle, topological) order, so repeating it ends in an attack
  of the same or smaller size that uses only kept sites. Kept sites are a subset of the engine's sites, so the
  other direction is immediate. Hence verdict and minimum are unchanged; the reported flips sit on dominators.
- *`--fault-enc relax`.* With `f` true the gate output is unconstrained, so it may also keep its fault-free value.
  Every model of the exact encoding is a model of the relaxed one, and a relaxed model whose freed net is not
  actually flipped is an attack with one flip fewer. The witness is normalised to the nets that really differ.
- *Cardinality.* By induction over the totalizer tree, if j inputs of a node are true its outputs 1..min(j, k+1)
  are forced true; so `-out[j+1]` forbids j+1 flips, and with at most j flips all clauses can be satisfied by
  setting each output to its exact meaning.
- *No reliance on the argument alone.* Every SAT answer is replayed on a separate scalar simulator
  (`simulate()`); if the witness does not reach the goal with a non-key input the run aborts with exit 4.
  UNSAT answers have no such certificate; they rest on the argument above and on the tests in section 6.

No symmetry breaking is used.

## 5. Files

```
tools/fastsat/
  scripts/glitchsat_sat.py     encoder, backends, run_check, CLI (check / sweep / cnf)
  scripts/minicdcl.py          pure-Python CDCL (watched literals, 1-UIP, VMTF, restarts, assumptions); DIMACS CLI
  tests/                       pytest suite; bruteforce.py = exhaustive reference; netgen.py = random netlists;
                               fake_pysat/ = stand-in for PySAT (test double, clearly marked)
  bench/gen_sbox_proxy.py      S-box proxy netlists without Yosys
  bench/verify_all.py          recorded results + exhaustive cross-check over every repository netlist
  bench/verify_surface.py      cross-check against the separate numpy enumerator of tools/surface (attack_surface.py)
  bench/bench.py               CNF sizes, timings, optional comparison with the z3 engine
  bench/results/               MEASURED outputs of the runs quoted below
  cloud_bench.sh               native-solver + z3 benchmark, to be run on the cloud VM (Ubuntu 24.04)
```

Run the tests: `cd tools/fastsat && python3 -m pytest -q tests` (set `GLITCHSAT_ROOT` if the folder is not at
`<repo>/ext/fastsat`, and `GLITCHSAT_SURFACE` if `tools/surface` is not next to it).

## 6. Correctness checks (MEASURED HERE, bundled solver)

Minimum flips against the repository's recorded numbers (re-run for this README with `glitchsat_sat.py sweep --k 3`
and `check`; also asserted in `tests/test_reference_designs.py`):

| design (T=6) | recorded | source | SAT backend |
|---|---|---|---|
| V0 spike / V1 spike | 1 / 1 | `results/reproduce/v*_spike_given-netlist_k*.json`, NUMBERS.md `B2.v0v1` | 1 / 1 |
| V2 spike, goal `boot_word` | 3 (k<=2 none) | `results/reproduce/v2_spike_given-netlist_k*.json`, NUMBERS.md `B2.v2.spike.word` | 3 (k<=2 none) |
| V0 / V1 / V2 rtl plain (`results/deep/work/nl/v*_rtl.json`) | 1 / 1 / 2 | `results/reproduce/v*_rtl_plain_k*.json` | 1 / 1 / 2 |
| V2 spike, goal `boot_ok == 1` | 1 | NUMBERS.md `B2.v2.ok` | 1 (`boot_ok` at cycle 1) |

`rtl_opt` rows (V2 min 2) are not checked: no stored netlist for that flow.


Command: `python3 bench/verify_all.py --jobs 2` (about 10 minutes here); output in `bench/results/verify_all.{log,json}`.

**(a) Recorded results: 116 of 116 equal.**

| Source | Cells | Equal |
|---|---|---|
| `results/reproduce/*given-netlist*` (spike V0/V1/V2, k=0..3, T=6) | 12 | 12 |
| `results/reproduce/*rtl_plain*` on `results/deep/work/nl/v*_rtl.json` (matched by gate/flop count) | 12 | 12 |
| `validation/data/spike_v*_results.json` (k=1..5, sat/unsat) | 15 | 15 |
| `research/c4/ver/heldout.csv`, full-width goal, T=6, k<=3 (rc103, rc117 corrected by `rerun_x.json`) | 76 | 76 |
| docs/NUMBERS.md `B2.v2.ok` (V2, goal `boot_ok`) | 1 | 1 |

Skipped, 12: the `rtl_opt` rows (no stored netlist for the opt flow; needs Yosys). R20 rows cannot be checked (no netlists).

History of the 14 heldout netlists (`research/c4/ver/gen/{crc301,307,311,313,319,321,rc103,107,111,113,117,119,121,127}_opt.json`,
28 cells with T=3 and T=6): an earlier run skipped them because `Netlist` rejected their flops. The flops do have a known
init: the opt flow aliases one flop bit to several positions of a net (for example `o = [9,10,10,'0','0',10,'0',10]`, init
`xx0xxxx0`), and the bit is `x` at some positions and 0/1 at another. The parser treated the `x` as an error without looking
at the other positions. `scripts/glitchsat.py` now merges the init per bit (an `x` yields to a known value; only a flop that
is `x` everywhere is rejected), and the two exhaustive simulators (`tests/bruteforce.py` here, `tools/surface`) use the same rule.
All 14 netlists are now in the table above. The `solver` column of `heldout.csv` for rc103 (mask 0x18) and rc117 (mask 0xf)
predates `research/c4/ver/rerun_x.json`; the checks use the corrected values from that file (0 and 2).

**(b) Exhaustive simulator: 240 cells, 0 mismatches.** For each of the 120 distinct repository netlists with
`sig`/`boot_word` ports (all accepted by the parser), at T=6 and T=3, k<=3: the SAT minimum from five encoder
configurations (default; no collapse; seqcounter + reduce none; relax; relax + no collapse + reduce coi) must be
equal, every witness must replay on `tests/bruteforce.py`, and the minimum is compared with exhaustive enumeration
of all fault sets on all sites and cycles (2.7 million fault sets in total, each over all input values).
- 226 cells: exact minimum confirmed (exhaustive minimum equal, or exhaustive "none with <= m-1" plus a replayed
  witness of size m, or exhaustive "none <= 3").
- 14 cells: only a lower bound could be enumerated within the budget of 160,000 sets per size (V5-class netlists
  and a few V2 variants: exhaustive to 1 flip, SAT says 3; three `rand` netlists: exhaustive to 2, SAT says none
  <= 3). They are consistent, not confirmed.
- Not covered: `real_designs/fsm5.json` and `real_designs/second/door5.json` (no `sig`/`boot_word` ports; their
  recorded results come from adapted solvers with per-cycle inputs, a different model).

**(c) `tools/surface` exhaustive enumerator** (`bench/verify_surface.py`; a numpy bit-parallel simulator written
separately from this backend and from `tests/bruteforce.py`). Output in `bench/results/verify_surface.{log,json}`.
- The 8 minimums recorded in `tools/surface/results/surface_*.json` (V0, V1, V2 at T=4/6 incl. k=2, V2 apt 0.33,
  V2 flow B, V2 with input buffers): 8 of 8 equal, and each of the 7 SAT witnesses is one of the recorded complete
  lists of minimum attacks (in the test-suite).
- Six small designs (V0, V1, V2 at T=4, V2 flow B, V2 input buffers, V2 apt 0.33): oracle run in the test-suite,
  minimum equal and the SAT witness inside the complete oracle attack set.
- Every repository netlist with `sig`/`boot_word` ports at T=6 and T=3, k<=3, 30 s oracle limit per cell:
  240 cells (120 netlists x 2 horizons), **0 mismatches**: 224 ok (minimum equal; in 208 of them the SAT witness is
  inside the complete oracle attack set), 14 consistent (oracle stopped early with no attack below its last size, SAT
  minimum not lower), 2 skipped because the oracle process died (V5-class netlists at T=6; the machine has 8 GB and was
  shared). Command: `python3 bench/verify_surface.py --timeout-s 30 --batch 10000 --jobs 2` (about 7 minutes here).

**V0/V1/V2 against `validation/netsim.py`** (in the test-suite): k=0 and all 456 single faults x 255 inputs
agree with min 1/1/3; V2 at T=4, all 46,056 fault pairs find nothing and SAT says the same; the 3-flip witness
replays on netsim.

**Fuzz** (test-suite): 750 random netlists (up to 14 gates, 4 flops, 2 input ports, constants, init values) x 6
encoder configurations against the exhaustive minimum, plus `sweep`; a direct single-fault test of the collapsing
lemma. Earlier ad-hoc runs: 6,400 more random cases, 0 disagreements.

**Solver**: 3,600 random CNF queries with assumptions against truth tables; pigeonhole; limits return "unknown".

Test-suite total: see the last line of section 7.4.

## 7. Measurements here (MEASURED HERE, bundled Python solver, single runs, 2 vCPU)

These are timings of an interpreted solver on this machine. They are not predictions for CaDiCaL and they are
not comparable with the z3 timings in R20_REPORT.md (other machine, other solver, and for the S-box other netlists).

### 7.1 CNF size and solve time, default settings (`bench/results/bench_here_py.md`)

"k<=j s" = one instance, ascending budgets; "(implied)" = not solved again after the minimum was found.

| design | gates/flops | T | sites modelled | fault vars | CNF vars | CNF clauses | min | k<=0 s | k<=1 s | k<=2 s | k<=3 s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| v0 spike | 18/2 | 6 | 106 | 34 | 211 | 553 | 1 | 0.001 | 0.0 | (implied) | (implied) |
| v1 spike | 58/8 | 6 | 313 | 78 | 505 | 1349 | 1 | 0.001 | 0.007 | (implied) | (implied) |
| v2 spike | 68/8 | 6 | 353 | 83 | 535 | 1419 | 3 | 0.001 | 0.009 | 0.062 | 0.24 |
| v2 rtl plain | 85/8 | 6 | 408 | 133 | 771 | 1935 | 2 | 0.001 | 0.009 | 0.022 | (implied) |
| v5 (apt 0.33) | 208/9 | 6 | 1028 | 193 | 1354 | 3639 | 3 | 0.003 | 0.05 | 0.294 | 1.577 |
| v2 spike T=12 | 68/8 | 12 | 767 | 173 | 1124 | 3034 | 3 | 0.004 | 0.03 | 0.548 | 0.631 |
| v2 spike T=20 | 68/8 | 20 | 1319 | 293 | 1908 | 5186 | 3 | 0.003 | 0.097 | 4.002 | 79.7 |
| otp fsm5 (engine semantics, see note) | 515/102 | 6 | 2190 | 657 | 4510 | 12547 | 1 | 0.058 | 0.032 | (implied) | (implied) |
| dmr (proxy, trees) | 1790/32 | 4 | 5498 | 90 | 2899 | 14749 | 2 | 0.656 | 1.918 | 0.02 | (implied) |
| tmr2 (proxy, trees) | 2693/48 | 4 | 8279 | 121 | 4298 | 22047 | 3 | 1.078 | 2.789 | 11.76 | 0.07 |
| dmrs (proxy, shared) | 834/32 | 4 | 2630 | 534 | 4705 | 20149 | 2 | 0.386 | 2.855 | 0.091 | (implied) |
| tmr2s (proxy, shared) | 1259/48 | 4 | 3977 | 787 | 7006 | 30146 | 3 | 0.504 | 2.225 | 27.87 | 0.064 |

The full table (22 designs, plus the time of a fresh `check` per budget) is in the file named above. All 106
repository netlists that parsed at the time of that run (14 more parse after the init fix; not re-benchmarked) at T=6: `bench/results/bench_here_repo_py.md` (largest CNF 1,514 variables /
3,797 clauses; all sweeps k=0..3 together 6.9 s). Note on fsm5: goal `unlock == 1`, attacker port `user_digit`
!= 0, other inputs free constants. This is the engine's model on that netlist, not the threat model of
`real_designs/REPORT.md`.

### 7.2 Without fault collapsing (`bench/results/bench_here_py_nocollapse.md`, 120 s limit per budget)

| design | fault vars | CNF vars | CNF clauses | min | k<=1 s | k<=2 s | k<=3 s |
|---|---|---|---|---|---|---|---|
| v5 | 1028 | 5152 | 13169 | 3 | 0.357 | 3.051 | 7.647 |
| v2 spike T=20 | 1319 | 6612 | 17400 | 3 | 1.626 | 16.86 | 116.5 |
| dmr (proxy, trees) | 5498 | 27499 | 88339 | 2 | 21.79 | 0.592 | (implied) |
| tmr2 (proxy, trees) | 8279 | 41420 | 132944 | unknown | 15.46 | timeout | - |
| dmrs (proxy, shared) | 2630 | 13159 | 46723 | 2 | 22.02 | 4.234 | (implied) |
| tmr2s (proxy, shared) | 3977 | 19911 | 70521 | 3 | 17.59 | 55.74 | 0.475 |

Same minimum wherever both runs finished. One cell hit the limit (tmr2 trees, k<=2) and is "unknown" there.

### 7.3 Ablation on the shared-mux proxies (`bench/results/ablation_*.md`)

tmr2s, "no attack with <= 2 flips": totalizer+xor 27.9 s, seqcounter+xor 27.4 s, totalizer+relax 17.8 s. dmrs,
"no attack with <= 1 flip": 2.9 s, 3.0 s, 3.2 s. One run each; differences of this size are within what a
single run can show. Nothing is concluded about which option is faster with a native solver.

### 7.4 What the proxies are and are not

`bench/gen_sbox_proxy.py` builds the R20 wrapper structures (`sbox_unprot/par/par2/dmr`, plus two three-copy
variants) around an AES S-box written as one multiplexer tree per output bit ("trees", fan-out 1 inside the
S-box) or with identical multiplexers shared ("shared", fan-out > 1). They are **not** the R20 netlists: R20's
come from Yosys + ABC on secworks `aes_sbox.v` (2,040 gates for `sbox_dmr`). In the tree proxies collapsing
removes about 98% of the fault variables, which a real ABC netlist with shared logic will not allow; the
shared proxies and the no-collapse runs are the more cautious reference. Minimums found: unprot/par/par2 = 1,
dmr = 2 (no 1-flip attack), tmr (one shared alarm bit) = 2, tmr2 (two alarm bits) = 3. The dmr result has the
same pattern R20 measured on the real netlist (k=1 none, minimum 2); that is an agreement of pattern on a
different netlist, not a reproduction.

On R20's open cell: R20 measured "k=1 no attack" and "k=2 minimum 2" on `sbox_dmr`. The answer at k=3 follows
from those two (ATTACK_FOUND, minimum 2); what did not finish was z3's search at that budget.

Test-suite: 51 tests, 51 passed here with `tools/surface` present (`python3 -m pytest -q tests`, about 105 s on this machine
while it was shared with other jobs); without `tools/surface` (set `GLITCHSAT_SURFACE`) 44 pass and 7 are skipped. Of these, 12 are in `tests/test_bench_and_oracle.py`: the z3 agreement/timing table (with stand-ins for
the z3 engine: agreement, disagreement exits 1, timeout on either side is "not comparable", result-file parsing,
engine crash and hang), the R20 parameters against `research/c3/r20/out`, and the `tools/surface` cross-checks.

## 8. To confirm on the cloud VM (all TO CONFIRM (cloud))

Target: the cloud VM (Ubuntu 24.04, setup commands in the header of `cloud_bench.sh`: venv, `pip install
python-sat z3-solver pytest numpy`, `apt-get install yosys`). `sh tools/fastsat/cloud_bench.sh` does this in one run and writes `bench/results/native_<time>.{txt,json}`:

1. `pip install python-sat` installs on that Python, and the adapter's calls exist there:
   `pysat.solvers.Solver(name=..., bootstrap_with=...)`, `.solve(assumptions=...)`, `.get_model()`, `.delete()`,
   `pysat.solvers.SolverNames`. Which solver names that PySAT version offers (CaDiCaL 1.9.5 as `cadical195` is
   assumed; Kissat is not assumed to be in PySAT and is reached through `--backend dimacs:kissat` if the binary
   is installed).
2. The script re-runs the test-suite and `verify_all.py --quick --backend <native>` so the native solver itself is
   checked against the exhaustive simulator.
3. With Yosys on PATH it synthesises the R20 wrappers through `scripts/synth.sh` and prints gate/flop counts to
   compare with R20 (2040/32 for `sbox_dmr` with Yosys 0.33; other versions may differ).
4. It runs every design at k = 1, 2, 3 with the native backend, runs `scripts/glitchsat.py check` with z3 under
   `Z3_TIMEOUT`, and prints timings and an agreement column (equal / different / not comparable when one side
   has no verdict). Exit status of `bench.py` is 1 on any disagreement.
5. Whether `sbox_dmr` k=3 finishes, and in what time, is the open question this work was built for. It is not
   answered here.

Known limits: time limits for PySAT are enforced by running the search in a forked child process (Linux/macOS);
the fork path was exercised only with the stand-in. The bundled solver is single-threaded interpreted Python.
The backend is not wired into `scripts/glitchsat.py` or the product CLI; it is a separate entry point.
