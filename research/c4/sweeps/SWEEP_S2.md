# SWEEP S2: research editor report

Labels: SOURCED = page or paper text read. SNIPPET = search snippet or partial read only. UNVERIFIED = inference, negative result, or not opened.
Nothing here is claimed as novel. Everything is "found in these searches", not "first".

## 1. What is new since earlier reports

- Extends S1 (SWEEP_S1.md) and R23 (FIRMER per-gate counting), R27 (Sinz sequential counter vs totalizer).
- FIRMER (extends R23): now SOURCED from arXiv 2307.00561v1 (first ~100k of 150k chars). Counting convention is upper bounds only, zeta(ne, nc, T, l). Fault types are set, reset, flip. Each gate faulted at most once per vector. Reported metrics are MaxEpC and #Clk.
- SYNFI (extends R23): paper text read via pdftotext. It reports synthesis lowering the fault count needed to defeat a countermeasure: AES FSM state skip 3 to 2 faults (Yosys FSM recoding), flash erase signal 4 to 2 faults (merged duplicate registers). set_dont_touch restored 4. This is the strongest sourced item this round for our synthesis-sensitivity concern.
- SCA plus fault verifier family (new to the file set): VerFI, VERICA, CocoAlma, PROLEAD and its RR d-probing refinement, FIVER lineage, and the SoK 2024/1944 survey. Only VerFI, VERICA, CocoAlma and 2024/1277 were read at abstract or README level.
- Synthesis and preserve attributes: OpenTitan commit cb56b46 read (KEEP replaced by DONT_TOUCH, with the stated reason). AMD DONT_TOUCH and Yosys keep semantics remain SNIPPET.
- rIC3 licence (extends R27 background): master README and LICENSE read, BSD-3-Clause, 2026. Older releases reportedly GPL-3.0 (SNIPPET).
- Incremental cardinality (extends R27): only the abstract of Martins et al. 1408.4628 was read. No BMC-specific comparison found.

## 2. Per-angle findings

### 2a. SCA and fault verifiers

| Claim | URL | Year | Label |
|---|---|---|---|
| VerFI is a bit-level netlist fault simulator. User sets adversary bounds and test vectors. Detected means all-zero output. Outcomes: detected, ineffective, non-detected. Diagnosis reports per fault kind, cycle and cell. BSD-3-Clause, beta. Fault model list, counting unit and synthesis handling not on the pages read. | https://eprint.iacr.org/2019/1312 ; https://github.com/emsec/verfi | 2019-2020 | SOURCED (thin) |
| VERICA checks Verilog netlists against SCA, fault and combined attacks. Fault bound is max simultaneous faults, set by `number`. Location class c, s or cs. Strategy: detection, correction, sifa, sfa. PIID annotation tags duplicated inputs. Transitions and couplings not supported. Example run 0.778 s on 16 cores. Licence text not read (copyright notice only). Synthesis not discussed. | https://artifacts.iacr.org/tches/2022/a15/readme.html | 2022 | SOURCED |
| CocoAlma: Apache-2.0 formal masking verifier. Yosys flow, stable or transient mode. README mentions no faults. | https://github.com/IAIK/coco-alma | 2022-2025 | SOURCED |
| PROLEAD: simulation-based leakage detection on netlists, statistical so not a proof. Licence not confirmed. | https://tches.iacr.org/index.php/TCHES/article/view/9822 | 2022 | SNIPPET |
| RR d-probing: models only glitches that manifest. Extends PROLEAD. Open-source release not confirmed. ePrint 2025/733 (flaw in masked AES S-box) is a snippet only. | https://eprint.iacr.org/2024/1277 | 2024-2025 | SOURCED (abstract), 2025/733 SNIPPET |
| FIVER: BDD symbolic fault injection. Predecessor of FIRMER. Artifact licence not read. | https://tches.iacr.org/index.php/TCHES/article/view/9072 | 2021 | SNIPPET |
| SoK on fault injection simulation: taxonomy by target and development stage. Abstract only. | https://eprint.iacr.org/2024/1944 | 2024 | SOURCED (abstract) |
| "Fides" and "COMETS": no matching tool found in four searches. SILVER, maskVerif, REBECCA only named in a snippet. | none | 2026 | UNVERIFIED |

### 2b. Synthesis and redundancy

| Claim | URL | Year | Label |
|---|---|---|---|
| SYNFI works on the synthesized netlist, builds faulty and non-faulty copies, SAT via PySAT/MiniSAT22. Fault model: count, location, gate-function replacement. A fault is effective if outputs differ and no alert was raised. Synthesis cut faults needed from 3 to 2 (FSM recoding, nofsm avoids it) and from 4 to 2 (merged duplicate registers; set_dont_touch fixed). Out of scope: safe-error and ineffective-fault attacks. SAT may report unreachable states. Authors used Synopsys DC with a proprietary library. | https://arxiv.org/pdf/2205.04775 | 2022 | SOURCED |
| OpenTitan commit: KEEP replaced by DONT_TOUCH in Xilinx primitives; DONT_TOUCH is forward-annotated to place and route. Diffs not seen. | https://opensecura.googlesource.com/3p/lowrisc/opentitan/+/cb56b467022a58683cdbf5589cc7a8a7c15944a6 | 2022 | SOURCED (commit page only) |
| AMD UG903/UG901: DONT_TOUCH stops optimization of replicated drivers. Documented use is fanout, not security. | https://docs.amd.com/r/en-US/ug903-vivado-using-constraints/DONT_TOUCH | 2025 | SNIPPET |
| Old Synopsys DC patent: dont_touch on a generic-netlist net is not guaranteed to survive compile. Current DC behaviour unknown. | https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/6263483 | old | SNIPPET |
| Yosys commits: opt_merge skips merges where both cells carry keep; opt_dff skips keep wires (stopgap comment). Not confirmed for $dff duplicates. | https://git.libre-chip.org/mirrors/yosys/commit/1d773b50a4bc44cd9b431387adf053d1998a4590 | n/d | SNIPPET |
| Redundancy-removal paper: commercial tools include redundancy removal, few guarantee redundancy-free output. | https://arxiv.org/pdf/1503.06632 | 2015 | SNIPPET |
| TCHES 9813 and 9481: reportedly say RTL-to-netlist mapping may harm redundancy countermeasures. Not opened. | https://tches.iacr.org/index.php/TCHES/article/view/9813 | 2022+ | UNVERIFIED |

### 2c. Formal fault-injection flows

| Claim | URL | Year | Label |
|---|---|---|---|
| FIRMER: SAT encoding, gate-level Verilog, Z3 to DIMACS, Glucose 4.2.1. Fault-resistant if every allowed vector is ineffective. Upper bounds ne and nc only. Encoding overhead at most 6|T| times gate count. Gate counts 925 to 40,184. Vulnerable-gate reduction averages more than 72%. Abstract says 46 of 48 benchmarks verify in 3 minutes, intro says other two take 31 and 35 minutes while abstract says 35 (inconsistent). FIVER baseline times out at 24 h on 23 of 48. Paper claims that deciding "not fault-resistant" is NP-complete (proof in appendix unread). UNSAT instances harder than SAT. Page marked "HPCA 2024 submission" which conflicts with TCHES 2024 listing. Tool called open-source, no repo or licence seen. | https://arxiv.org/html/2307.00561v1 | 2023/2024 | SOURCED (partial) |
| FIRMER scale snippets: "72 of 76 within 3 minutes" and a coNP-complete claim in one snippet. Conflicts with the paper's own 46/48 and NP-complete. | https://tches.iacr.org/index.php/TCHES/article/view/11782 | 2024 | SNIPPET |
| SYNFI README: preprocess, inject, evaluate phases; Yosys with NANGATE45; Apache-2.0 "unless otherwise noted". No fault model in README. | https://github.com/lowRISC/synfi | n/a | SOURCED |
| FIVER: BDD symbolic injection, over 90 million injections on single-round CRAFT in under 50 minutes. Fault model and licence not stated on the abstract. | https://eprint.iacr.org/2021/936 | 2021 | SOURCED (abstract) |
| ArchiFI/uArchiFI: Yosys-based formal microarchitectural fault injection. Model checker unknown. Repo returned 403. | https://repositum.tuwien.at/bitstream/20.500.12708/188805/1/Tollec-2023-ArchiFI%20Formal%20Modeling%20and%20Verification%20Strategies%20for%20Micro...-vor.pdf | 2023 | SNIPPET |
| OneSpin Fault Injection App: commercial, closed. | https://onespin.com/products/specialized-apps/fault-injection-app | n/a | SNIPPET |
| DVCon formal fault propagation analysis (OneSpin). PDF unread (binary). | https://dvcon-proceedings.org/wp-content/uploads/formal-fault-propagation-analysis-that-scales-to-modern-automotive-socs-paper.pdf | c.2020 | SNIPPET |
| No source gives "minimum faults to defeat" as a stated result. It is only the smallest (ne, nc) with a counterexample. | none | n/a | UNVERIFIED (inference) |

### 2d. Cardinality and BMC

| Claim | URL | Year | Label |
|---|---|---|---|
| rIC3 README: BSD-3-Clause, HWMCC 2024 and 2025 first place per README. | https://raw.githubusercontent.com/gipsyh/rIC3/master/README.md | 2026 | SOURCED |
| rIC3 master LICENSE: BSD 3-Clause, Copyright 2026 Yuheng Su. | https://raw.githubusercontent.com/gipsyh/rIC3/master/LICENSE | 2026 | SOURCED |
| Older rIC3 releases listed as GPL-3.0 with a commercial-use restriction. | https://lib.rs/crates/ric3 | 2024-2025 | SNIPPET |
| rIC3 paper (CAV 2025): bit-level IC3, usable as SymbiYosys backend. Abstract read. No cardinality or budget content. | https://arxiv.org/abs/2502.13605 | 2025 | SOURCED (abstract) |
| Martins et al.: incremental cardinality schemes for MaxSAT, claimed "significant performance boost". Abstract only. MaxSAT, not BMC. | https://arxiv.org/abs/1408.4628 | 2014 | SOURCED (abstract) |
| Totalizer needs only k+1 outputs, tightenable by unit clauses. | https://arxiv.org/pdf/1408.4628 | 2014 | SNIPPET |
| IC3-Evolve: peripheral. | https://arxiv.org/pdf/2604.03232 | 2026 | SNIPPET |
| FIRMER repo or paper by that name not found by search in the cardinality angle (although the FIRMER paper was read in the formal-FI angle). Licence unresolved. | none | 2026 | UNVERIFIED |
| No BMC-specific comparison of Sinz vs totalizer vs cardinality networks found. | none | 2026 | UNVERIFIED |

## 3. Implications for our project, in plain words

Weaken:
- Any wording that a bound or count is "the" fault count. FIRMER and VERICA both state bounds (upper limits per cycle, per gate class), and neither pages shows a stem/branch rule. Say our counting is one convention among several.
- Any claim that a result on RTL or on one synthesis run carries over to the netlist. SYNFI shows counts dropping (3 to 2, 4 to 2) after synthesis.
- Any claim that a speedup of Sinz over a totalizer is externally supported. Only our own measurement supports it. Say so.
- Any statement of the complexity class of the fault-resistance question until the FIRMER appendix is read. The paper's claim (NP-complete for "not fault-resistant") and one snippet (coNP-complete) disagree on wording only, and the two are consistent as complements, but we have read neither proof.

Strengthen:
- The case for reporting minimum faults on the post-synthesis netlist, with and without preserve attributes. SYNFI and the OpenTitan commit are sourced support.
- The case for stating evidence strength: bound proof (SAT/BDD) vs sampled simulation (VerFI, PROLEAD). The families differ and this is a fair contrast.
- The case that model choice changes the verdict (2024/1277 for SCA).

Build or cite:
- Cite SYNFI (2205.04775), FIRMER (2307.00561), VERICA (a15 readme), VerFI (2019/1312), FIVER (2021/936), SoK 2024/1944 (abstract level only).
- Build: a small test on local yosys 0.33 for opt_merge with and without keep/DONT_TOUCH on duplicated registers, reporting the minimum-fault count each time.
- Build: a counting-convention table in our docs: FIRMER (ne, nc, per gate once), VERICA (max simultaneous per class), SYNFI (simultaneous faults x locations x mappings), VerFI (per cell, per cycle), ours.
- Licence note: rIC3 master is BSD-3-Clause; pin the tag. The project's own LICENSE stays undecided (author's call).

## 4. Not verified or blocked

- VerFI CASA PDF 404; fault-model list and counting unit unread. ePrint 2019/1312 full text unread.
- uArchiFI repo 403 (not worked around).
- TCHES 9813: fetch failed with an API error citing a filter; looks spurious; not retried.
- Yosys opt_merge docs 404; keep semantics for $dff duplicates unconfirmed; local yosys 0.33 untested.
- ePrint 2024/1944 full PDF unread; 2024/1277 abstract only; repo link not confirmed.
- FIRMER: last ~50k chars unread (NP-complete proof, appendix); repo and licence unknown; HPCA vs TCHES venue conflict; 46/48 vs 72/76 numbers differ across sources.
- SYNFI licence is "Apache-2.0 unless otherwise noted" only per README; paper does not state it.
- DVCon PDF and 1503.06632 and 1408.4628 PDFs came back as binary and were not decoded (only 2205.04775 was).
- SILVER, maskVerif, PROLEAD repo and licence, VERICA licence text not read.
- k-FRP full text still behind Anubis wall.
- AMD DONT_TOUCH, Synopsys DC behaviour, OpenTitan commit diffs not opened.
- Fides, COMETS: not found.
- Certitude, JasperGold, Questa, SymbiYosys/EQY fault flows: nothing found.

## 5. Next-round searches from the reviewer

Modalities not tried: pdftotext on saved PDFs (1503.06632, 1408.4628, VerFI HOST 2020, 2019/1312); raw.githubusercontent.com READMEs for PROLEAD, FIRMER, VERICA; local yosys 0.33 experiment (needs a integration-run copy).

1. "Bailleux Boufkhad totalizer encoding" and "Sinz sequential counter at-most-k" (pdftotext route).
2. "PROLEAD fault injection probing-secure glitch" repo and licence.
3. "FIRMER fault-resistance verification github" and the TCHES 2024 FIRMER artifact.
4. "yosys opt_merge keep attribute duplicated registers fault countermeasure".
5. "SymbiYosys EQY equivalence check fault injection countermeasure netlist".

Also not searched: ABC/Genus/equivalence checking after synthesis; Certitude/JasperGold/Questa; further combined SCA-FI tools beyond VerFI and VERICA.
