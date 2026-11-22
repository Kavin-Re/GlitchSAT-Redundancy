# RUN2 report: uArchiFI, k-FRP, FIVER on our toy designs

Authorised by the author's live instruction "run the third party tools" for these three tools only. Everything marked MEASURED was run in this run (commands below); nothing was pushed or published; nothing was written outside `research/c5/run2/` and `third_party_derived/uarchifi_kfrp_fiver/`. Work area: `/tmp/work_run2/` (clones, build, runs). Faults are modelled single-cycle flips on toy netlists; nothing physical.

## 0. Headline
- uArchiFI: built (against Yosys 0.38, not its target 0.61), ran on our designs, and reproduced our minimums on the stored netlists and the apt re-synthesis: V0 1, V1 1, V2 3 (stored) / 2 (apt 0.33), boot_ok 1. Bundled example: model generation MEASURED; its BMC did not finish (see 2.1).
- k-FRP: built and ran its bundled example (Skinny64 red3, k=2). It runs on our netlists but answers a different question (any output corruption without an alert), so it cannot give our goal-specific minimum. It reports "exploitable" single faults on V0, V1 and V2 alike.
- FIVER: cloned and read only. NOT built, NOT run: its CUDD dependency is not on PyPI or the conda channels we may use (details 2.3). Stopped there.
- Agreement of uArchiFI with our engine on three toy designs (same netlists, same goal, same counting) validates neither tool. Both are small, share our own netlists, and the one result that is not 1 (V2) is the same cell family that our own B2/M1 work already explored. It is a consistency check of an adapter plus our engine, not a validation.

## 1. Origins and licences (MEASURED: `git rev-parse HEAD`, LICENSE files read)
| Tool | Origin URL | Commit (date) | Licence |
|---|---|---|---|
| uArchiFI | https://github.com/CEA-LIST/uArchiFI | 8a2d792fbd40da0af7518a27f26873b752a3c854 (2026-07-21) | `LICENSE.txt` = LGPL-2.1 (matches S3) |
| k-FRP (Tollec et al., TCHES 2024(4), ePrint 2024/247; artifact page https://artifacts.iacr.org/tches/2024/a27/) | https://github.com/CEA-LIST/Fault-Resistant-Partitioning | 75929f6019be0dd8802be3533c184ba29d9c94c4 (2024-08-23) | `LICENSE` = Apache-2.0 (README: "Apache License, Version 2.0" unless noted). Submodules: cxxsat 032652bb66c9b572f36cebf38b3c6fa5cf4af3f9 (MIT), cadical 84b44398e6346f387182a4ab0fe23ddffd7c8570, nlohmann/json 960b763ecd144f156d05ec61f577b04107290137 (licences of the last two not read here) |
| FIVER (Richter-Brockmann et al., TCHES 2021(4), ePrint 2021/936) | https://github.com/Chair-for-Security-Engineering/FIVER | 176a1db7f80764543324db5378b6f82d4adebcbe (2021-08-20) | `LICENSE` = custom licence, non-commercial use only, derived works must carry the same licence, credit required. Not an OSI licence. |

The artifact repo for k-FRP was found by public search; the submodules were fetched by `git submodule update` from the URLs in the tool's own `.gitmodules` (github.com), which I treated as part of "cloning their public repositories". Say so if that was not intended.

Derived or adapted code is in `third_party_derived/uarchifi_kfrp_fiver/`: `uarchifi_plugin/fault_rtlil.cc` (already there from an earlier pass; byte-identical to the file I built; header states origin, commit, LGPL-2.1, the two API edits), `uarchifi_run_u.sh` (header with origin, commit, licence), `kfrp_config_run2.json` plus `ORIGIN_kfrp_config.txt`, `ORIGIN_fiver.txt`. Our own adapters `j2v.py` and `addalert.py` are in `research/c5/run2/` (own code, not derived). No file renamed. Nothing is in any bundle.

## 2. Build and bundled example
### 2.1 uArchiFI
- Build: `README` wants Yosys 0.61 (Docker). I did not use Docker. I compiled `src/passes/fault/fault_rtlil.cc` as a plugin against the existing conda Yosys 0.38+92 with `g++` (yosys-config's compiler is missing; flags from `yosys-config --cxxflags`), with two API substitutions (`all_selected_modules` to `selected_modules`, `selected_members` count). The existing conda env was not modified. This is a deviation from the supported version; behaviour on 0.38 is therefore not guaranteed to equal 0.61 behaviour. Output: `/tmp/work_run2/up_build/fault_rtlil.so` (not copied into the tree).
- Bundled example `examples/1.robust_software` (cv32e40p + VerifyPIN v7), `make prep_baseline`: MEASURED, finished in 5.4 s, produced .il, .btor2 and .smt2 (log: `raw/uarchifi_example1_prep.log`). Then `yosys-smtbmc -s z3 -t 75`: the README's solvers (yices, Pono, btormc) are not installed, I used z3. It reached step 7 in 34 s and then made no further progress until my 600 s cap killed it. So the example's verification result is NOT obtained (not run to completion). Model generation = MEASURED; verdict = not run.
- The pass test-suite (`tests/passes`) was not run (it needs `--yosys-variant`, 0.61 is the listed target).

### 2.2 k-FRP
- Build: `cmake src -Bbuild && cmake --build build` (31 s). MEASURED.
- Bundled example `./build/k-partitions skinny_red3` (Skinny64 with 3x redundancy, k=2): MEASURED, 13.5 s wall. Procedure 1 built partitionings (7 partition files), Procedure 2 enumerated exploitable faults at every step with "UNSAT", ending with "Procedure 2 verification time: 0.70 s" and no exploitable fault listed in the final iterations (log: `raw/kfrp_skinny_red3_log.txt`). I did not compare with the paper's table. The second README example (Ibex regfile k1, 1.5 min) was not run.

### 2.3 FIVER (stopped)
- `README` build needs Boost program_options (present in an existing conda env, not used) and the CUDD 3.0.0 library from `davidkebo.com` (tarball). `conda search` (conda-forge, litex-hub) and `pip download cudd` find no CUDD package. The only source named is a host outside the PyPI/conda scope I was authorised for, so I did not fetch it, and I did not look for another source (that would be working around the limit). FIVER is therefore NOT built, NOT run, and the bundled `test/craft-1round` example is NOT run. The repo's `inc/cudd` holds only headers.
- What I can state about FIVER is from reading its README, `model/*.txt` and `src/passes/analysis/fault.cpp` headings (SOURCED from the repo, not run): netlist as Verilog or `.nl` instruction list, ROBDDs via CUDD, faults applied per gate with `fault.number` per logic stage and `fault.variate` = number of logic stages faulted together, fault models in `model/` (bitflip, set-reset, em, laser), location `c`/`s`/`cs`, outputs compared with the fault-free circuit (effective/ineffective/detected), designs must be acyclic with annotated clock and control inputs (SYNFI's note, see SWEEP_S3). I did not read the C++ passes in full.

## 3. Our designs (MEASURED unless marked)
Adapter chain for uArchiFI: `reference/spike_netlists/vN.json` (or an apt-0.33 re-synthesis made with `scripts/synth.sh rtl/vN.v vN out.json plain` into /tmp) -> `j2v.py` (flat Verilog, one 1-bit wire per net, input nets named so they are not fault sites, flop init copied) -> wrapper with `(* anyconst *)` 8-bit `sig`, `assume(sig != 0xC3)`, `assert(boot_word != 0x96)` (or `boot_ok != 1`) -> `select` of all `n*` wires -> `fault_rtlil -effect flip -timing 0:5 -cnt K` -> `write_smt2` -> `yosys-smtbmc -s z3 -t 6`. T=6 cycles, K flips total, same horizon and goal as `glitchsat`. Sanity: with `sig == 0xC3` and K=0 the assertion fails (honest boot reaches 0x96) on all three designs, and with `sig != 0xC3`, K=0 it holds.

Minimum K found (first K where the BMC returns FAILED; K-1 returned PASSED unless noted):
| Design / netlist | goal | uArchiFI min flips | Ours (NUMBERS.md) | Match |
|---|---|---|---|---|
| V0 stored | boot_word | 1 | 1 | yes |
| V1 stored | boot_word | 1 | 1 | yes |
| V2 stored | boot_word | 3 (K=1 PASSED 66 s, K=2 PASSED 144 s, K=3 FAILED 18 s) | 3 | yes |
| V0, V1, V2 stored | boot_ok | 1, 1, 1 | 1 | yes |
| V0 apt 0.33 | boot_word | 1 | 1 | yes |
| V1 apt 0.33 | boot_word | 1 | 1 | yes |
| V2 apt 0.33 | boot_word | 2 (K=1 PASSED 113 s, K=2 FAILED 17 s) | 2 | yes |
| V0, V1, V2 RTL (rtl/vN.v, per RTL wire, `keep_hierarchy` removed) | boot_word | 1, 1, 1 (K=1 FAILED on all) | not comparable | counting unit differs, see 4 |
| k-FRP V0, V1, V2 stored (alert tied to constant 1) | output corruption with no alert | exploitable single faults exist at k=1: union of listed gate IDs 4 (V0), 11 (V1), 11 (V2) | not comparable | different question, see 4 |
| FIVER | any | NOT RUN | | |

boot_ok on apt netlists, uArchiFI on conda 0.38 re-synthesis, and k-FRP on apt netlists: not run. The V2 witness at K=3 was dumped as VCD (`raw/net_v2_word_k3/cex.vcd`); I did not decode which three nets, so I do not claim it equals M1's witness.

## 4. What each tool can and cannot express (SOURCED = read in README/source; MEASURED = seen in a run)
| Question | uArchiFI | k-FRP | FIVER |
|---|---|---|---|
| Flop-Q flips | Yes (MEASURED: flop Q nets in the site list; the flip appears on the net after the flop for one cycle, stored state not changed, same as our model) | Yes, via partitions of registers (faulty partitions) at the initial state and the next cycle (SOURCED from `k-partitions.cpp` and README) | Reg faults through the `s` location and `reg` entries in the model files (SOURCED, not run) |
| Multi-cycle | Yes: BMC to depth N; `-timing a:b` window (MEASURED 0:5) | No unrolling over a program run: golden and faulty traces for max(1, delay)+1 cycles from an unconstrained start; the multi-cycle claim comes from the inductive invariant (SOURCED) | Only unrolled feed-forward stages; designs must be acyclic (SOURCED, via SYNFI note) |
| Symbolic input | Yes (MEASURED: `anyconst` input; free per-cycle input also possible) | Inputs free, same in golden and faulty copy; no `!= key` constraint available except via `invariant_list` on the golden initial state (SOURCED) | Yes, BDD over all inputs (SOURCED) |
| Set / reset | Yes: `-effect set / reset / flip / diff / xor / fixed` (README, source; only flip MEASURED) | Active code is bit-flip only; the 3-effect (none/flip/reset/set) variant sits under `#if false` in `utils.h` (SOURCED) | `model/set-reset.txt` provided (SOURCED, not run) |
| Specific goal value (boot_word == 0x96) | Yes, as an assert in a wrapper (MEASURED) | No. Question is "can the primary outputs differ from golden with no alert", not a chosen value; needs an alert port (I tied one to constant 1, a stand-in that the tool treats as an alert that never fires) | Output vs fault-free comparison, no goal value (SOURCED) |
| Minimum fault count | Not directly: you pick K and ask SAT/UNSAT; I looped K=1,2,3 | Not directly: you pick k; `increasing_k` option exists | Not directly: you pick `fault.number` |
| Counting unit | One Yosys wire per cycle = 1 fault, whatever its width or fanout. On our flat 1-bit netlists that is per net (stem): a fanout-3 net costs 1 (MEASURED: results equal our stem counting). On RTL a multi-bit wire flipped as a whole costs 1 (MEASURED: V2 RTL gives 1, not 3) | One gate (one cell output signal) per fault in the combinational part, one register partition per fault (SOURCED); stem-like; no fanout split seen | Per gate, `number` per logic stage and `variate` stages (SOURCED README; paper not read) |
| Exhaustive or sampled | Bounded model checking: UNSAT at depth = no attack within T and K, not a proof beyond | Inductive invariant, program independent (SOURCED claim, paper not read) | BDD-exhaustive within its model (SOURCED claim) |

Deviations that limit what the uArchiFI numbers mean: Yosys 0.38 instead of 0.61; z3 instead of yices; `keep_hierarchy` removed for the RTL runs; the `n*` selection excludes input nets by construction (as our engine does); the design is flattened and re-emitted by my `j2v.py`, so the tool saw our netlist through my adapter, not the original JSON.

## 5. Statement on agreement
uArchiFI matches our minimums on 9 of 9 cells it was asked (stored boot_word x3, stored boot_ok x3, apt boot_word x3) (V0 1, V1 1, V2 3 and 2, boot_ok 1). Three designs of 8-bit toy size, fed through my adapter and measuring the same bounded flip model, cannot validate either tool, nor our engine; they show only that two independent implementations of "k flips of nets within T cycles" agree on these cells. The two checks that carry information are: V2 stored 3 versus apt 2 reproduced (synthesis dependence), and the RTL-wire count giving 1 (the counting unit changes the headline). k-FRP and FIVER give no comparison for the minimum-fault number at all (k-FRP asks a different question; FIVER not run).

## 6. Status table
| Item | Status |
|---|---|
| Origin, commit, licence of the 3 tools | MEASURED |
| uArchiFI plugin build (Yosys 0.38) | MEASURED |
| uArchiFI example 1 model generation | MEASURED |
| uArchiFI example 1 BMC verdict | not run (killed at 600 s, depth 7) |
| uArchiFI on V0/V1/V2 stored, boot_word and boot_ok, T=6, K up to 3 | MEASURED |
| uArchiFI on apt V0/V1/V2, boot_word | MEASURED |
| uArchiFI on RTL (per-wire count) | MEASURED (V0 3 wires, V1 5, V2 9 fault wires; K=1 attack found on all) |
| uArchiFI set/reset effects | not run |
| k-FRP build | MEASURED |
| k-FRP bundled example skinny_red3 | MEASURED |
| k-FRP Ibex example | not run |
| k-FRP on our V0/V1/V2 stored (k=1,2,3) | MEASURED (exploitable faults listed; goal-specific minimum not expressible) |
| FIVER build, bundled example, our designs | not run (CUDD not available from allowed channels) |
| FIVER capability statements | SOURCED from repo files, not run |

Reproduce: `/tmp/work_run2/u/run_u.sh`, `matrix.sh`, `matrix_apt.sh`, `matrix_rtl.sh` (copies of the driver are in `third_party_derived/uarchifi_kfrp_fiver/uarchifi_run_u.sh`); raw outputs in `research/c5/run2/raw/`. The k-FRP config used is `raw/config_run2.json` (copy placed as `config/config_file.json` in a scratch directory, because the tool reads that fixed path).
