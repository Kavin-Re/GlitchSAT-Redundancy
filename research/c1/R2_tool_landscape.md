# R2: Fault-injection / fault-resistance verification tool landscape (as of 2026-11-19)

Evidence labels: OPENED = I fetched the primary page this run (fetch tool returns a model-summarised view, not raw text). SEARCH-ONLY = seen only in search snippets (treat as UNVERIFIED in detail). Anything not listed was not checked. No tool was installed or run.

## 1. Open-source tools

### SYNFI (lowRISC) - OPENED https://github.com/lowRISC/synfi ; paper arXiv 2205.04775 (SEARCH-ONLY for paper details)
- Fault model: user JSON fault spec (`examples/fault_model.json`); README does not describe fault types. Paper (snippet only): differential/miter style, SAT-based.
- Inputs: Yosys-synthesized netlist as JSON, fault spec, cell library converted from a .lib (NANGATE45 example).
- Search vs check: README does not say; flow is parse -> inject -> evaluate whether countermeasures detect faults (a check of a given countermeasure).
- Scalability: not stated; applied to OpenTitan blocks per the paper (UNVERIFIED here).
- License Apache-2.0. Run: pip install, cell_lib_generator.py, parse.py, fi_injector.py (4 commands).
- Cannot: README states no limitations; needs a per-library cell-model conversion step; no explanation layer or UI evident.

### FIVER (RUB / Richter-Brockmann, Sasdrich, Moradi; TCHES 2021) - OPENED artifact readme https://artifacts.iacr.org/tches/2021/a16/readme.html
- Fault model: bit-flip mapping file, N faults, injection at combinational and/or sequential locations, blacklist; correction or detection countermeasures.
- Inputs: gate-level Verilog with clock/control annotations, or instruction list (.nl); cell library file.
- Method: ROBDD-based symbolic fault injection; a check (enumerates effective/ineffective/detected faults), reports fault rate.
- Scalability: paper claim (search snippet): ~90M injections on 1-round CRAFT in <50 min.
- Open: C++ source with a LICENSE file; terms not read. Run: build Boost + CUDD 3.0.0, `make release`, `bin/release/verify -c config/verify`.
- Cannot: aimed at cryptographic ciphers (redundancy/detection), not control-flow bypass; heavy C++/CUDD build; no search for minimal attack sets.

### FIRMER (Chinese research group; TCHES 2024) and CLEAVE - OPENED https://github.com/S3L-official/CLEAVE ; abstract https://arxiv.org/abs/2307.00561
- Fault model: bit-flip, set-reset, or all; max/min fault count per cycle over chosen clock cycles; correction or detection.
- Inputs: gate-level netlist converted to .nl via included parser; blacklist; NANG45 library; Design Compiler implied for synthesis.
- Method: encode to SAT/SMT (Z3, Bitwuzla, Glucose); a check/verification. Claims (abstract): 46/48 benchmarks in ~3 min; verification problem NP-complete (arXiv) / coNP-complete (journal, search snippet).
- Open: repo shows no license (README states none). CLEAVE is the compositional extension; the repo is the CLEAVE repo, not clearly a standalone FIRMER repo.
- Cannot: depends on commercial synthesis in its documented flow; Yosys flow not documented; no license.

### VerFI (Arribas, Wegener, Moradi, Nikova; HOST 2020) - OPENED https://github.com/emsec/verfi (v2 beta, BSD-3-Clause)
- Gate-level fault simulator, adversary configurable, reports detected / ineffective / non-detected. Detection heuristic is "output all zeros" (README). Run instructions and inputs not in README. Simulation (random/chosen stimuli), not exhaustive. Beta; v2 drops some v1 features.

### uArchiFI (CEA-LIST) - OPENED https://github.com/CEA-LIST/uArchiFI (LGPL-2.1)
- Closest in spirit to this project. Fault model: transient, timed window, set/reset/flip/xor/fixed, `-cnt` max simultaneous faults, selectable targets. Inputs: RTL + software binary + attacker model. Yosys builds SMT2/BTOR2 with saboteurs; BMC via yosys-smtbmc (yices) or Pono; iterator loop adds constraints per counterexample. Proves robustness up to the BMC depth, or returns counterexample VCD.
- Run: Docker/Podman/Apptainer; needs Yosys 0.61; three examples (robust software, robust hardware, crypto software). Tests need specific Yosys variant.
- Cannot (README implied): bounded only; RTL-level, not post-synthesis netlist verdicts per se (so synthesis-dependence is not its topic); design-dependent setup; no plain-language explanation or dashboard mentioned. CEA page (SEARCH-ONLY) reports an OpenTitan root-of-trust finding.
- NOTE: this overlaps the project strongly (Yosys + SMT + BMC + counterexample). It is the main prior-art risk for any novelty claim.

### SHADOWFI (Guerrero-Balaguera et al., IEEE Access Dec 2025) - OPENED https://divadnauj-gb.github.io/shadowfi
- Netlist/HDL saboteur insertion, simulation on HPC or FPGA emulation, outcomes Masked/SDC. Reliability (soft-error) focus, no security/attack modelling on the page. License not stated on page. Not a verification tool (sampling campaigns).

### FIESTA (Uhle, Mueller, Moradi; TCHES 2025) - OPENED abstract https://eprint.iacr.org/2025/1287
- Non-exhaustive, scalable evaluation under the "general random fault model" incl. multi-gate / whole-state faults; precise-adversary procedure; AES cores. Code availability not stated on the page (an IACR artifact page for 2025/a44 appeared in search; not opened). Statistical, not proof.

### Others, SEARCH-ONLY (UNVERIFIED details)
- NAIL (arXiv 2508.06344, Luebeck): Chisel RTL FI framework with state-based faults; repo gitlab.iti.uni-luebeck.de/pubs/nail (not opened; PDF unreadable via fetch).
- vRTLmod (TUM): LLVM tool adding FI to Verilator models. FISSA (2024): TCL-driven FI around an HDL simulator. Icarus-based batch/concurrent RTL fault simulation (2025). InjectV (arXiv 2606.12011, RISC-V simulation FI attack model). HDFIT NetlistFaultInjector (IntelLabs), NetFi3 (LCSR-lab). A 2024 SoK of automated FI simulators: eprint 2024/1944 (fetch returned 403; not read).
- FIES and FIMA: I found no tool by these names; FIES may be a misreading of FIESTA. UNVERIFIED / not found.
- Cascade (ETH, USENIX Sec 2024): OPENED only via search: a CPU bug fuzzer, NOT a fault-injection tool; irrelevant here.

## 2. Commercial
(SEARCH-ONLY; vendor pages not opened.)
- Riscure/Keysight Inspector FI + VC Glitcher: physical voltage/clock/EM/laser glitching of real devices (Keysight product DS2101A listed). Needs hardware; out of scope for software-only. Price figures only from a third-party blog, UNVERIFIED.
- Synopsys VC Z01X (+ VC Formal FuSa fault pruning): functional-safety fault simulation (stuck-at, bridge, transition, soft errors), ISO 26262/IEC 61508. No security-attack use found in results.
- Cadence Xcelium Safety / Jasper FSV / Midas / Verisium Manager Safety: same safety flow (formal pruning then fault simulation).
- Siemens Austemper (SafetyScope, fault simulation): safety, closed loop.
- Optima Fault Injection Engine (DVCon slides, SEARCH-ONLY): safety and security FI on chip designs.
Pattern: commercial EDA targets safety coverage (random faults vs diagnostic coverage), not "does the attacker bypass this check with k glitches"; physical vendors target real silicon.

## 3. Comparison table (open tools)
| Tool | Level | Method | Fault count | Finds attack / proves | Setup | Explains |
|---|---|---|---|---|---|---|
| SYNFI | Yosys netlist | SAT-ish check | spec-driven | check of countermeasures | pip + lib conversion | no |
| FIVER | netlist | BDD symbolic | n per level | enumerates effective faults | Boost+CUDD C++ | no |
| FIRMER/CLEAVE | netlist (.nl) | SAT/SMT | max/min per cycle | verifies resistance | CMake+Z3+DC | no |
| VerFI | netlist | simulation | configurable | statistical | unclear | no |
| uArchiFI | RTL+binary | Yosys+BMC | -cnt | counterexample or bounded proof | container, Yosys 0.61 | VCD only |
| SHADOWFI | netlist | saboteur sim | sampling | none | container/FPGA | reliability only |
| FIESTA | netlist | statistical | whole-state | none (non-exhaustive) | code unknown | no |

## 4. Gap map (what an open, easy, explainable tool could occupy)
Evidence for each: from the README gaps above; absence claims are limited to what I searched (a handful of queries, not a systematic review).
1. Minimal attack search on a Yosys netlist: most open tools check a countermeasure or simulate; only uArchiFI iterates counterexamples, at RTL. A netlist-level "smallest flip set" with replay is not shown by the tools I opened.
2. Synthesis sensitivity: none of the opened READMEs address that a different Yosys version/flow changes the verdict. This project measured exactly this (0.33 vs 0.38). Candidate differentiator, but UNVERIFIED that no paper addresses it.
3. Plain-language explanation and visualization of why a fault works: not found in any opened README (uArchiFI gives VCD, others tables).
4. Ease of setup: FIVER/CLEAVE require C++ builds, commercial synthesis or NANG45 conversion; uArchiFI requires containers pinned to Yosys 0.61. A pip + apt Yosys flow with CI-checkable expected verdicts is a small but real usability gap.
5. Fault models matter: this project covers single-cycle flips on gate outputs/flops. Set/reset/stuck, multi-cycle, and clock/voltage-derived effects are modelled by FIRMER/uArchiFI; adopting those would reduce a stated weakness.
6. Not served by any open tool seen: analog/electrical grounding (glitch voltage -> which gates actually flip; timing-violation faults with SDF or SPICE). Papers/tools found are all logical-level. This is the electronics-depth gap; a software-only attempt would be ngspice characterization of a few cells and STA slack-driven fault plausibility, labelled SIMULATED.
7. Unbounded proof for control-bypass properties: uArchiFI is bounded; this project has one k-induction proof. Not a gap with a tool answer, rather an honest limitation.

## 5. Positioning implications
- Do not claim novelty over uArchiFI, SYNFI, FIRMER. Position as an easy, explainable, netlist-level complement, with synthesis-sensitivity evidence.
- Cheap adoption wins: import SYNFI-style cell libs / JSON netlists, support set/reset faults and multi-cycle, emit uArchiFI-comparable result on a shared design (cross-tool agreement is a strong credibility item; SYNFI agreement already done).
- Worth checking next (UNOPENED): FIESTA artifact page https://artifacts.iacr.org/tches/2025/a44/ ; SoK eprint 2024/1944 via another route; uArchiFI examples for runnable designs to cross-check; lowRISC SYNFI paper for fault model definition.
