# SWEEP S3

Round S3 research editor note. Nothing here is claimed as novel. Labels: SOURCED (page or paper text read), SNIPPET (search summary or listing only), UNVERIFIED (not read, or inferred).

## 1. What is new since earlier reports

Extends SWEEP_S1.md and SWEEP_S2.md (not re-read this round) and COUNTING_CONVENTIONS.md.

- FIRMER (arXiv 2307.00561): the counting convention is now read. It counts per gate, with a split budget zeta(ne, nc, T, l). This extends the counting comparison in COUNTING_CONVENTIONS.md (the ne/nc split should be added).
- SYNFI (arXiv 2205.04775): re-read against SWEEP_S2.md and COUNTING_CONVENTIONS.md. No discrepancy found. Cycle model is time-independent, not unrolled.
- uArchiFI: fault model (L, T, E) with a single total budget N over a bounded window, read from the paper and README. Closest to our budget style.
- k-FRP: now identified as Tollec et al., TCHES 2024(4), ePrint 2024/247. Identification is SNIPPET only. The paper was not read.
- FIVER: abstract page only. The counting unit is still UNVERIFIED.
- Polarity: one new SOURCED data point (Moro et al., FDTC 2013, Cortex-M3 flash bus, looks like set-to-1). Other polarity items remain SNIPPET.
- Licences: uArchiFI LGPL-2.1, SYNFI Apache-2.0, PROLEAD BSD-3-Clause and rIC3 BSD-3-Clause (current master) read from raw LICENSE files. FIRMER/CLEAVE and VerFI licences are not established.
- Safety standards: new angle this round. Vocabulary only, from secondary sources.

## 2. Per-angle findings

### 2.1 Primary papers

| Claim | URL | Year | Label |
|---|---|---|---|
| FIRMER faults target gates (logic and memory gates), not nets. A fault event is (cycle, gate not in blacklist, type: bit-set, bit-reset or bit-flip). Each gate is faulted at most once per vector. Permanent faults are modelled as repeated transient faults. | https://arxiv.org/html/2307.00561v1 | 2023 | SOURCED |
| FIRMER budget zeta(ne, nc, T, l): max events per cycle, max cycles containing faults, allowed types, gate class (c, r, cr). Bounds are upper bounds. Differs from our single total budget k<=3 over T=6. | https://arxiv.org/html/2307.00561v1 | 2023 | SOURCED |
| FIRMER results: 46 of 48 benchmarks in about 3 min, the other two about 35 min (abstract). The intro reportedly says 31 and 35 min, so the sources disagree. FIVER timed out on 23 of 48 at 24 h. Vulnerable gate reduction averages over 72%. CHES 2024 issue 4 version exists; PDF not readable here. | https://arxiv.org/abs/2307.00561 | 2023 | SOURCED |
| SYNFI: the user gives number of simultaneous faults, a gate location, and an effect that replaces the gate's boolean function. Transient and stuck-at supported. | https://arxiv.org/pdf/2205.04775 | 2022 | SOURCED |
| SYNFI has no sequential unrolling. Pipeline registers become pass-through and loops are broken. FSM experiments use 1 to 7 simultaneous state-register faults. Not comparable with a T=6 unrolling without a caveat. | https://arxiv.org/pdf/2205.04775 | 2022 | SOURCED |
| SYNFI results: AES FSM skip needs 3 faults, or 2 after Yosys FSM recoding. Flash erase signal 4 faults, down to 2 after register merging. LC controller needs at least 7 faults, matching Hamming distance 7. Consistent with SWEEP_S2.md. | https://arxiv.org/pdf/2205.04775 | 2022 | SOURCED |
| FIVER: netlist-level BDD verification with symbolic fault injection. More than 90 million injections on single-round CRAFT in under 50 min. Counting unit and cycle model are not stated on the abstract page. A gate-based unit is an inference from SYNFI text. | https://eprint.iacr.org/2021/936 | 2021 | SOURCED (abstract only); counting unit UNVERIFIED |
| k-FRP is Tollec et al., "Fault-Resistant Partitioning of Secure CPUs for System Co-Verification against Faults", TCHES 2024(4), ePrint 2024/247. Described as an inductive invariant that proves at gate level that up to k faults are caught, independent of the program. Fault unit, counting rule for k, cycle model and licence not read. | https://eprint.iacr.org/2024/247.pdf ; https://tches.iacr.org/index.php/TCHES/article/view/11788 ; https://artifacts.iacr.org/tches/2024/a27/ | 2024 | SNIPPET |
| CEA-List describes the k-FRP use on OpenTitan as the first such analysis. This is a claim to attribute, not to repeat. | https://list.cea.fr/en/page/%C2%B5archifi-2/ | 2024-2025 | SNIPPET |
| uArchiFI fault model (L, T, E): registers, a cycle range, and effects (set, reset, flip). A counter bounds total faulty transitions by N over the run. Bounded model checking. Unit is a register or signal, not a gate. | https://repositum.tuwien.at/bitstream/20.500.12708/188805/1/Tollec-2023-ArchiFI%20Formal%20Modeling%20and%20Verification%20Strategies%20for%20Micro...-vor.pdf | 2023 | SOURCED |
| uArchiFI README: transient faults, -cnt N caps simultaneous faults, targets chosen by Yosys select, BMC with yosys-smtbmc or Pono, UNSAT at a bound means robust up to that step. The README does not say whether a multi-fanout signal counts once. | https://github.com/CEA-LIST/uArchiFI | 2025 | SOURCED |

### 2.2 Polarity evidence

| Claim | URL | Year | Label |
|---|---|---|---|
| Moro et al. EMFI on a Cortex-M3 at 56 MHz: a voltage sweep on an LDR from flash turns 0x12345678 into progressively higher-Hamming-weight values, ending at FFFFFFFF. The authors read it as set-to-1 on the flash data path. Graded effect, one device and one bus path, no 0-to-1 versus 1-to-0 rate table. | https://fdtc.deib.polimi.it/FDTC13/shared/FDTC-2013-session-3-1.pdf | 2013 | SOURCED |
| Ordas et al.: EMFI on an FPGA and a microcontroller produces bit-set and bit-reset faults, not timing faults. | https://hal-lirmm.ccsd.cnrs.fr/lirmm-01430913 | 2017 | SNIPPET |
| KU Leuven, ATmega328p: EM pulses set some read bits to 1, while an earlier laser study on the same device found set-to-0. Polarity depends on the injection method. | https://lirias.kuleuven.be/retrieve/615572 | unknown | SNIPPET |
| Laser faults in SRAM behave as bit-set and bit-reset, not flip. Zones for set and reset do not overlap. | https://hal-emse.ccsd.cnrs.fr/emse-01109133 | 2013-2015 | SNIPPET |
| COSADE 2014 talk: on a 90 nm standard-cell flip-flop, the fault model depends on gate implementation. Both single bit-set and single bit-reset must be considered. No rate table. | https://cosade.telecom-paristech.fr/cosade14/presentations/session9_b.pdf | 2014 | SNIPPET |
| EMMap: skipped loop iterations, localized SRAM bit flips and ESP32 halts. No polarity or multiplicity data. The coil-polarity claim is second-hand from earlier work. | https://arxiv.org/html/2512.09049v1 | 2025 | SOURCED |
| Voltage glitching on STM8 and 78K0 is instruction-level. A search found no measured set, reset and flip rates for supply glitching. | https://arxiv.org/html/2509.18341v1 | 2025 | SNIPPET |
| Khuat et al.: EM pulse width gives replay or skip, so the fault model changes with parameters. | https://researchportal.ip-paris.fr/en/publications/multiple-and-reproducible-fault-models-on-micro-controller-using-/ | 2021 | SNIPPET |

### 2.3 Licences

| Claim | URL | Year | Label |
|---|---|---|---|
| uArchiFI LICENSE.txt is GNU LGPL v2.1. The local fault_rtlil.cc carries a CEA header, LGPL-2.1 and a change note (two Yosys API substitutions for Yosys 0.38). Whether a runtime-loaded Yosys plugin counts as linking was not resolved. | https://raw.githubusercontent.com/CEA-LIST/uArchiFI/main/LICENSE.txt | 2026 | SOURCED; linking question UNVERIFIED |
| SYNFI LICENSE is Apache-2.0; per-file headers should be checked. | https://raw.githubusercontent.com/lowRISC/synfi/master/LICENSE | 2022-2023 | SOURCED |
| PROLEAD LICENSE is BSD 3-Clause. No PROLEAD code is in the local project. | https://raw.githubusercontent.com/ChairImpSec/PROLEAD/master/LICENSE | 2022 | SOURCED |
| rIC3 master LICENSE is BSD 3-Clause, with no non-commercial clause in that text. Older listings and snippets say GPL-3.0 with a possible non-commercial notice. Licence differs by version, so pin the commit. | https://raw.githubusercontent.com/gipsyh/rIC3/master/LICENSE | 2026 | SOURCED (master); older claims SNIPPET |
| Local HEADER_TEXT.txt in third_party_derived/firmer_cleave/ records no licence file found in S3L-official/CLEAVE (commit 0b9f052). A raw LICENSE fetch returned 404, which is consistent with that but does not prove it. FIRMER licence is not established. | https://raw.githubusercontent.com/S3L-official/CLEAVE/main/LICENSE | 2026 | SOURCED (local header); upstream state UNVERIFIED |
| VerFI (emsec/verfi): LICENSE returned 404 and a search found nothing. | https://raw.githubusercontent.com/emsec/verfi/main/LICENSE | n/d | UNVERIFIED |
| k-FRP and FIVER: no repository or licence found. Do not assume they inherit uArchiFI terms. | n/a | n/d | UNVERIFIED |
| The uArchiFI licence conflict is resolved for the LICENSE file (LGPL-2.1). The Apache-2.0 claim came from a search summary. | https://github.com/CEA-LIST/uArchiFI | 2025-2026 | SOURCED for LGPL-2.1; Apache claim SNIPPET |

### 2.4 Safety standards

| Claim | URL | Year | Label |
|---|---|---|---|
| ISO 26262 vocabulary, as quoted by exida from the 2011 definitions (not 2018; an earlier note said 2018). Dependent failure is either a common cause failure (single root cause hits several elements) or a cascading failure (one element's failure causes another's). Independence is the absence of dependent failures that violate a safety goal. FFI covers cascading failures only, not CCFs. DFA is in Part 9 clause 7. | https://www.exida.com/Blog/iso-26262-independence-and-related-terms | 2011 text | SOURCED |
| DFA method: top-down and bottom-up analysis, eight steps, dependent failure initiators, coupling factors (power and clock networks, shared resources), causal chains, mitigations. A report lists DFI, coupling factors, CCF and CF summaries and residual risk. No numbers, and no mention of SPFM, LFM or beta. | https://semiengineering.com/dependent-failure-analysis-for-safety-critical-ip-and-socs | n/d | SOURCED |
| Single-point, residual and dual-point fault definitions, with dual-point classes detected, perceived and latent (Part 10). | https://www.einfochips.com/blog/automotive-functional-safety-iso26262-faults-and-failures/ ; https://webstore.ansi.org/preview-pages/ISO/preview_ISO+26262-10-2018.pdf | 2018 | SNIPPET |
| SPFM, LFM and PMHF meaning. Quoted target percentages disagree between sources. | https://semiengineering.com/technologies/iso-26262/ | n/d | SNIPPET |
| IEC 61508-6 Annex D beta-factor method, with a 37-question checklist, CCF rate = lambda_DU*beta + lambda_DD*beta_D, and multiplication factors for configurations above 1oo2. Checklist and Table D.5 values not seen. | https://webstore.iec.ch/publication/5520 | 2010 | SNIPPET |
| Route 1H uses SFF with hardware fault tolerance tables. A shared element that all channels depend on is a single point for that subsystem. Table values not checked. | https://www.exida.com/Blog/back-to-the-basics-18-route-1h | n/d | SNIPPET |
| SAE 2009-01-0739 separates independence from non-interference. | https://saemobilus.sae.org/papers/independence-non-interference-two-cardinal-concepts-develop-ee-architectures-hosting-safety-critical-systems-2009-01-0739 | 2009 | SNIPPET |

## 3. Implications for our project in plain words

Weaken:
- Any wording that our flip-a-net rule matches other tools. FIRMER counts per gate with a split per-cycle and per-cycle-count budget. SYNFI replaces a gate's function and has no unrolled cycles. uArchiFI counts registers or signals under one total budget. The units differ, and the "same direction" remark in the FIRMER finding holds only if a net has several driving gates.
- Any suggestion that a 1-to-0-only or symmetric flip model represents real faults. The only SOURCED measurement (one Cortex-M3 flash bus) looks like set-to-1. The other polarity items are SNIPPET. They point both ways depending on method, so nothing here supports a single polarity.
- Any statement about the rail or supply-glitch model. No measured polarity study was found, so the evidence neither supports nor refutes it. Mark it UNVERIFIED.
- Any statement that FIVER or k-FRP use a given unit or cycle model.
- Any repetition of CEA-List's "first analysis" claim. Attribute it if used.

Strengthen:
- The reading "UNSAT at a bound is robust only up to that bound". uArchiFI's README says the same thing, and SYNFI, FIRMER and uArchiFI all state bounds explicitly.
- The statement that SAT/BMC-style bound proofs on gate-level netlists are an established approach (FIRMER, uArchiFI). This is context, not novelty.
- The SYNFI synthesis-sensitivity point (3 faults to 2 after recoding), now confirmed against the paper.

Build or cite:
- Add the ne/nc split and the gate-class restriction as columns in COUNTING_CONVENTIONS.md. Add SYNFI's "no unrolling" caveat.
- Report any bound we state with its unit (stem versus gate), total versus per-cycle budget, and polarity set. Where useful, run a set and reset variant alongside the flip variant.
- Use ISO 26262 terms in any safety write-up: a shared decision net or rail event is a dependent failure initiator or common cause failure with a coupling factor, and redundancy gives no dual-point credit for it. Define how a safety goal violation is detected in our toolkit. A what-if fault run on a shared element maps onto the DFA verification step.
- Cite papers and link repos. Reimplement from the published method. Keep the uArchiFI-derived file separable under LGPL-2.1 with its header. Keep the firmer_cleave folder private or remove it before publication (owner decision). Pin the rIC3 commit used.

## 4. Not verified or blocked

- k-FRP: fault unit, counting rule for k, cycle model, licence and limits are all unread. The identification is SNIPPET.
- FIVER: counting unit and cycle model. Only the abstract was read.
- FIRMER: the last 50k of 150k characters of the arXiv HTML were not read. The abstract says the two slow benchmarks take about 35 min, while the intro reportedly says 31 and 35 min; this is unresolved. The CHES PDF was not text-extractable.
- uArchiFI: whether a runtime-loaded Yosys plugin counts as linking (legal, owner's call). The README does not state whether a multi-fanout signal counts once.
- rIC3: GPL-3.0 and non-commercial claims are SNIPPET. Only master was read.
- CLEAVE and VerFI licences: raw LICENSE returned 404. Branch and filename guesses may be wrong. FIRMER, k-FRP and FIVER repositories were not found.
- Polarity: Ordas 2017 and the laser SRAM items are SNIPPET because the HAL pages returned Anubis access-denied pages (not worked around). KU Leuven returned HTTP 504 once. COSADE 2014, FDTC-derived slides beyond the Moro deck and the TCHES voltage-glitch paper were not read. No multiplicity data and no supply or clock glitch polarity data.
- research/c5/ledger/LEDGER_REPORT.md was not read, so the effect on the ledger's V2/V5 items was not judged here.
- Standards: all SPFM, LFM, beta and HFT numbers are unverified. ISO 26262-5, -9, -10 and IEC 61508-2, -6 are paywalled. Annex D questions and Table D.5 not seen. The SINTEF beta report returned 403. No source found on a shared voter or shared supply in a 1oo2 setting.
- eprint 2024/247 PDF returned 403, not worked around. Whether the TCHES article page may be fetched needs a check against the project rules first.

## 5. Next-round searches from the critic

1. "TCHES 2024 fault-resistant partitioning k-FRP fault model gate-level counting" (and the artifact page a27).
2. "voltage glitch fault polarity measured microcontroller 0-to-1 1-to-0 bit-set bit-reset".
3. "formal fault injection BMC bounded bit-flip budget gate-level netlist verification 2023 2024".
4. "common cause failure shared voter power supply 1oo2 beta factor IEC 61508-6 Annex D".
5. "uArchiFI Yosys fault injection pass licence README" and "rIC3 licence history".

Modalities not tried: reading source code or READMEs for SYNFI, FIRMER, PROLEAD and VerFI; conference talks and artifact pages; quantitative tables (rates, multiplicity, counting rules). Competing work not searched: other fault-injection and verification tools (FaultFinder-style, ScVerif, REFINE-like, gate-level SAT/BMC flows), OpenTitan's own FI verification, and safety-side DFA tooling.
