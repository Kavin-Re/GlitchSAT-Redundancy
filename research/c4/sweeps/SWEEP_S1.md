# SWEEP S1: periodic research sweep

from search snippets and a few deep reads. Nothing here is claimed as novel. Absence of hits is not evidence of absence. Labels: SOURCED (page or PDF read), SNIPPET (search summary only), UNVERIFIED (not confirmed).

## 1. What is new since earlier reports

| Item | Extends | Status |
|---|---|---|
| ePrint 2026/648 (Monne et al., HOST 2026): model-checking synthesis of RTL fault-characterization programs on CV32E40P and Ibex | R23 (prior art) | SOURCED, abstract page only. Characterization, not countermeasure verification. |
| TCHES article 11782 is the FIRMER journal version ("SAT-based Formal Verification of Fault Injection Countermeasures for Cryptographic Circuits") | R23, which listed 11782 as unidentified | SNIPPET. Resolves an open entry. |
| SCFI (arXiv 2208.01356) and TRANSPOSE (arXiv 2411.02798): FSM hardening and encoding papers | R23 (not previously listed) | SNIPPET only. |
| SYNFI deep read: count is per gate, or per state-register bit for FSM experiments; Yosys FSM optimization cut the faults needed from 3 to 2 | R23 and R10 (consistent, now SOURCED) | SOURCED. |
| rIC3 (arXiv 2502.13605), GipSAT (arXiv 2501.18612), HWMCC'25 corpus (Zenodo, CC BY 4.0), A-IC3 and IC3-Evolve | Methods angle. R20 was only partly read, and R27_REPORT.md does not exist, so the extension is incomplete. | rIC3, GipSAT and Zenodo SOURCED; A-IC3 and IC3-Evolve SNIPPET. |
| Moro et al. EM deep read (Table I and III numbers); EMMap (arXiv 2512.09049, Dec 2025) | R22 (EM multiplicity) | SOURCED. EMMap is new relative to R22. |
| Tiny Tapeout tile 046 gate-level CI flow; UNSW COMP6420 syllabus (Lab 3 Fault Injection Attack, CC BY-SA 4.0) | R24 (adoption) | SOURCED. Tile 046 supports R24 change #8. |
| Correction: the UNSW Yosys/icestorm tooling claim is not on the syllabus page | R24 and earlier S1 snippet | Downgraded to SNIPPET/UNVERIFIED. |

## 2. Per-angle findings

### Prior art

| Claim | URL | Year | Label |
|---|---|---|---|
| ePrint 2026/648: BMC-style synthesis of test programs exposing microarchitectural bit-flips; about 70% of signals exposed in 2 days on 10 cores. CC BY-NC-SA 4.0, no code mentioned. | https://eprint.iacr.org/2026/648 | 2026 | SOURCED |
| k-FRP: inductive k-fault-resistant partitioning, OpenTitan lockstep, single bit-flips, Ibex register-file weakness. Full text unread. | https://tches.iacr.org/index.php/TCHES/article/view/11788 | 2024 | SNIPPET |
| FIRMER (TCHES): SAT-based gate-level verification, coNP-complete, 72/76 benchmarks in 3 min (snippet). | https://tches.iacr.org/index.php/TCHES/article/view/11782 | 2024 | SNIPPET |
| SYNFI: user sets simultaneous fault count, location, effect (gate replacement or stuck-at). AES control FSM: 1-2 flips raise the alert, 3 redirect control flow; after Yosys FSM optimization, 2 suffice. Open source; licence not extracted. | https://arxiv.org/pdf/2205.04775 | 2022 | SOURCED |
| SCFI: FSM control-flow hardening in Yosys, diffusion layer instead of duplicated next-state logic. | https://arxiv.org/pdf/2208.01356 | 2022 | SNIPPET |
| TRANSPOSE and related LFI-resilient FSM encoding; synthesis may insert don't-care states. | https://arxiv.org/html/2411.02798v1 | 2024 | SNIPPET |
| FIVER (BDD) and CLEAVE (compositional, sequential): no new 2025-2026 formal netlist FI tool surfaced. | https://link.springer.com/chapter/10.1007/978-3-031-71177-0_13 | 2024 | SNIPPET |
| Counting conventions (stem/branch/per-gate/collapsing) and their effect on a security verdict: no source found. | https://en.wikipedia.org/wiki/Fault_model | n/a | UNVERIFIED |

### Physics

| Claim | URL | Year | Label |
|---|---|---|---|
| Post-layout SPICE Monte Carlo: one transient can flip several flip-flops; P(multiple flips given at least one) up to 0.31. Particle-strike transients, not attacks. | https://arxiv.org/pdf/1401.1003 | 2014 | SOURCED (first pages only) |
| Moro et al., Cortex-M3 EMFI: timing faults with metastability. 10000 runs: no fault 60.1%, FFF45679 27.4%, FFFC5679 12.3%. About 9-10 bits changed per event, set-to-1; voltage sweep reaches FFFFFFFF at 186-190 V; Flash loads only, SRAM unaffected. One device, no per-bit rates. | https://arxiv.org/pdf/1402.6421.pdf | 2013 | SOURCED |
| EMMap: fault type depends on probe position, voltage, pulse width, polarity, height. Classes: control-flow, data corruption, system. Self-described pilot, no numeric multiplicity, peer review unknown, CC BY 4.0. | https://arxiv.org/pdf/2512.09049v1 | 2025 | SOURCED |
| LFI at 28 nm: contrast of data-independent bit-flip with data-dependent set/reset; separate master/slave latch sensitive regions. Quantitative multiplicity not obtained. | https://hal-emse.ccsd.cnrs.fr/emse-01856008/document | 2018 | SNIPPET |
| EM "curse of flip-flops": set/reset sampling faults on D flip-flops. | https://hal-lirmm.ccsd.cnrs.fr/lirmm-01430913 | 2017 | SNIPPET |
| Power/clock glitch talk: more than 90% single-bit per slides, relayed by a search summary. Not opened. | https://hal-emse.ccsd.cnrs.fr/emse-01110353v1/file/C_2013_2_talk_cosade2013_power_glitch.pdf | 2013 | SNIPPET |
| Voltage glitching modelled as setup-time violation; no turnkey SPICE supply-dip flow for standard-cell flops found. | https://re.public.polimi.it/retrieve/e0c31c0e-09fa-4599-e053-1705fe0aef77/A%20Combined%20Design%20Time-Test%20Time%20Study_11311-1003711_Barenghi.pdf | 2016-2020 | SNIPPET |
| mu-Glitch: up to four coordinated voltage faults from one trigger; cost is parameter search, not multiplicity. | https://www.usenix.org/conference/usenixsecurity23/presentation/sass | 2023 | SNIPPET |
| Laser on 0.35 um MCU: multiple-byte faults, yet single-bit DFA possible. Year inferred. | https://bvbvf1.bib-bvb.de/vufind/PrimoRecord/cdi_ieee_primary_5655079 | 2010 | SNIPPET |

### Adoption

| Claim | URL | Year | Label |
|---|---|---|---|
| Tiny Tapeout tile 046: CI via Makefile and .github/workflows. `make test-gatelevel-smoke` is quick; `make test-gatelevel` is deep and slow. Netlist is sky130A cell-mapped. No fault injection mentioned; licence not stated. | https://tinytapeout.com/chips/ttsky26a/046 | 2026 | SOURCED |
| tt06 template: gl_test step uses a sky130-mapped netlist. A 2026 template was not checked. | https://uithub.com/TinyTapeout/tt06-verilog-template | 2024 | SNIPPET |
| UNSW COMP6420: Lab 3 "Fault Injection Attack" (10% of grade, weeks 5-7), virtual or real hardware allowed, CC BY-SA 4.0. Page does not mention Yosys. | https://cgi.cse.unsw.edu.au/~cs6420/syllabus/ | 2026 | SOURCED |
| SYNFI applied to OpenTitan netlists; no evidence of it running in OpenTitan CI (absence not proven). | https://tches.iacr.org/index.php/TCHES/article/view/9813 | 2022 | SNIPPET |
| TU Delft thesis on Yosys netlist-level FI simulation. | https://repository.tudelft.nl/record/uuid:734f8266-621f-484b-a181-1f64a5dc034a | 2021 | SNIPPET |
| OER listing of simulated FI labs; content not opened. | https://oersi.tesshub.hzdr.de/materials/hardware-security-simulated-labs-side-channel-analysis-and-fault-injection | unknown | SNIPPET |
| SARIF limits: 10 MB upload cap, 1,000 locations per result (Enterprise Server docs, not github.com). | https://docs.github.com/en/enterprise-server@3.16/code-security/reference/code-scanning/sarif-files/troubleshoot-sarif-uploads/file-too-large | 2026 | SNIPPET |
| Third-party claim that the code_scanning_upload rate-limit field was removed May 19, 2026. | https://dev.to/flarecanary/githubs-codescanningupload-rate-limit-field-goes-away-may-19-your-sarif-pre-flight-check-is-40d1 | 2026 | UNVERIFIED |
| Current OpenTitan CI use of SARIF or a netlist FI gate: no source found. | https://arxiv.org/pdf/2205.04775 | 2026 | UNVERIFIED |

### Methods

| Claim | URL | Year | Label |
|---|---|---|---|
| rIC3: bit-level IC3, top in HWMCC'25 bit-level and word-level tracks, can back SymbiYosys. Licence not stated. | https://arxiv.org/abs/2502.13605 | 2025 | SOURCED (abstract) |
| GipSAT: IC3-tuned CDCL restricted to the cone of influence; 3.61x geomean speedup over MiniSat-based rIC3; 392 vs 369 of 635 cases. No licence stated. | https://arxiv.org/html/2501.18612v3 | 2025 | SOURCED |
| HWMCC'25 benchmarks and results, CC BY 4.0, 843.3 MB. General hardware verification, not security-specific; formats inferred. | https://zenodo.org/records/17428464 | 2025 | SOURCED |
| FIRMER arXiv: novel SAT encoding, NP-complete (TCHES says coNP-complete); 46 of 48 benchmarks in about 3 min, the other 2 in about 35 min; prior approach fails on 23 tasks at 24 h. Fault model and cardinality encoding unread; PDF came back as binary. | https://arxiv.org/abs/2307.00561 | 2023 | SOURCED (abstract only) |
| FIRMER TCHES figures (72/76, hardest about 4 h, prior approach fails on 31) differ from the arXiv figures. | https://tches.iacr.org/index.php/TCHES/article/view/11782 | 2024 | SNIPPET |
| A-IC3 (learning-guided generalization) and IC3-Evolve (IJCAI 2026). | https://arxiv.org/pdf/2604.21688 | 2026 | SNIPPET |
| Functional reduction for BMC; Dureja et al. sequential redundancy removal. | https://arxiv.org/pdf/2512.06643 | 2025 | SNIPPET |
| LABS (NUS) and FIVER artifacts; licences not confirmed. | https://nus-labs.github.io | 2020 | SNIPPET |
| IC3/PDR with an at-most-k budget counter, and open sequential fault-security benchmarks: no source found. | (none) | 2026 | UNVERIFIED |

## 3. Implications for our project

Plain words. Nothing here shows our work is novel; treat each item as a comparison or citation target.

- **Weaken any claim that implies no prior min-fault verification exists.** FIRMER (SAT, gate level, per-cycle and cycle-count caps) and SYNFI (formal, per gate) both do bounded minimum-fault verification. k-FRP may cover unbounded proof for single flips. We have read only the FIRMER abstract and the k-FRP abstract, so we cannot say where we differ.
- **Strengthen the claim that synthesis changes the verdict.** SYNFI's own numbers (3 faults before Yosys FSM optimization, 2 after) are SOURCED and show the verdict holds only for the exact post-synthesis netlist. Cite it directly. TRANSPOSE (don't-care states) is a SNIPPET-level supporting hint.
- **Fault counting convention.** SYNFI counts per gate, or per register bit in FSM experiments. We found no source on how conventions change a security verdict. Keep that as an open question, state our convention explicitly, and do not claim it is new.
- **Fault model for what-if runs.** Moro and EMMap suggest sampling from a distribution over bit-sets, not a fixed single-bit XOR. Offer a set-to-1 mode and a group-flip mode with position dependence. Moro gives about 9-10 bits per event on one device; EMMap gives no numbers. The SPICE paper (up to 0.31 multi-flop probability) is radiation-origin and only supports the group-flip row by analogy. The more-than-90% single-bit clock-glitch figure is unverified and must not be cited.
- **Build or cite.** (a) Cite FIRMER and SYNFI as nearest work and cross-check on a shared benchmark if artifacts are public. (b) Consider encoding the fault budget as a saturating counter so an IC3 engine such as rIC3 can attempt unbounded queries; this is an untested design suggestion. (c) Use the COI-restricted decision idea from GipSAT in our own SAT encoding. (d) HWMCC'25 (CC BY 4.0) can serve as a solver-scaling set only, not as a security benchmark.
- **Adoption.** A netlist fault job fits beside gl_test in Tiny Tapeout CI, in the slow tier. Inputs are sky130-mapped, so a plain-gate tool needs re-synthesis from RTL (supports R24 change #8). UNSW Lab 3 offers a "virtual hardware" slot, but its fault model is unknown, so do not claim compatibility. Keep the SARIF output small; the 10 MB limit is unlikely to bind. Position the tool as complementary to SYNFI for the OpenTitan audience.
- **Licences.** The UNSW teaching material is CC BY-SA 4.0 (share-alike), ePrint 2026/648 is CC BY-NC-SA 4.0, EMMap and HWMCC'25 are CC BY 4.0. SYNFI, FIRMER, rIC3, GipSAT, LABS and FIVER licences are not confirmed; do not reuse code or benchmarks until checked.

## 4. Not verified or blocked

- Anubis blocks, not worked around: k-FRP 11788 (full text), FIRMER 11782 PDF and page, the HAL-EMSE and HAL-LIRMM PDFs and slides.
- Binary or unreadable fetches: arXiv 2604.21688 (A-IC3) and the FIRMER arXiv PDF.
- Missing inputs: R27_REPORT.md does not exist (the r27 directory is empty); R20 was read only in its first ~3.5 KB.
- Unread beyond snippets: SCFI, TRANSPOSE, CLEAVE, FIVER, LABS, A-IC3, IC3-Evolve, functional reduction paper, Dutertre 28 nm results, Ordas et al., Zussa slides, mu-Glitch details.
- The SPICE multiplicity paper was read only through related work and the start of methodology; results tables were not read.
- FIRMER fault model, cardinality encoding and the arXiv versus TCHES benchmark discrepancy are unresolved.
- No measured nets-per-event for voltage or clock glitches at gate level; no turnkey SPICE supply-dip flow.
- OpenTitan current CI not reachable (github.com direct reads are 403 per project rules, not worked around).
- GitHub docs seen were Enterprise Server pages, not github.com. The rate-limit blog is unverified.
- Licences for SYNFI, FIRMER and rIC3 were not extracted.
- The UNSW tooling claim (Yosys, icestorm) is not on the syllabus page.
- Tile 046's repo workflow files, licence and lab content were not opened.

## 5. Next-round searches from the reviewer

Competing work not yet searched: VerFI, Fides, COMETS, the Coco/Silver/PROLEAD family, Yosys/SymbiYosys/EQY fault-aware flows, ABC and yosys opt-merge redundancy studies, ATPG-based fault analysis tools, and Cadence/Synopsys formal-security apps (comparison points only). Modalities not tried: arXiv HTML or ar5iv, DBLP/OpenAlex/Semantic Scholar listings, raw.githubusercontent.com READMEs, conference slides and videos, SPICE-based studies.

1. arXiv HTML or ar5iv text of FIRMER 2307.00561, for the fault model and cardinality encoding.
2. Open-access PDFs of SCFI, TRANSPOSE and k-FRP via author sites or ePrint mirrors (not Anubis hosts).
3. "gate-level fault injection netlist open source Yosys" plus "redundancy removal countermeasure synthesis" (2024-2026).
4. "multi-bit fault multiplicity laser clock glitch measured flip-flops" via non-HAL sources.
5. "OpenTitan fault injection CI sec_cm" via the docs site, not github.com.
6. From methods: "incremental totalizer" and cardinality encodings in BMC; also check the licence on the rIC3 and FIRMER repositories.
