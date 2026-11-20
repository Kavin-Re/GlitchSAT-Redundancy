# R10: Prior art, full-text pass

Date of work: 2026-11-19. Agent R10. License: UNDECIDED. Project title: working title TBD.
Scope: replace the abstract/README-only novelty basis in `docs/PRIOR_ART.md`, `compare/COMPARISON.md`, `research/c1/R2_tool_landscape.md` with full-text reading where reachable. Nothing was run; repos were cloned read-only into /tmp/work_r10/repos and PDFs read with pdftotext into /tmp/work_r10/p (outside the project).

Evidence labels used per cell: FULLTEXT (I read the paper/README text; page/section given) / REPO (read the repo files) / SNIPPET (search-result text only) / UNVERIFIED. Section numbers for FIRMER and uArchiFI are from the section headings visible in the text; page numbers for the arXiv/FMCAD layouts are approximate (FIRMER arXiv v1 pp.1-8 main text; uArchiFI FMCAD 2023 pp.101-109 as printed). SYNFI page numbers are the printed page numbers of arXiv v2.

## 0. Headline findings (things the earlier notes got wrong or missed)

1. SYNFI (FULLTEXT) already discusses synthesis dependence as a central motivation (Abstract; Sec. 1, p.2: "contemporary design automation tools tend to optimize inserted structures away") and measures it. Sec. 4.1.3, p.17-18: re-synthesising a sparsely encoded AES FSM with Yosys "using an aggressive optimization strategy" dropped the needed simultaneous faults from 3 to 2; `nofsm` prevents it. Sec. 4.2.3, p.21: synthesis merged duplicate registers of a 4-bit encoded flash-erase signal, cutting effective Hamming distance 4 to 2; fixed with `set_dont_touch`. So "synthesis changes the verdict" is NOT uncovered. Only a systematic quantification across many flows/versions (this project's Yosys 0.33 vs 0.38 comparison) could still be different; I did not find one, but nothing established as new.
2. SYNFI (FULLTEXT) does search over fault count in a user-driven loop: Sec. 4.2.2, p.21: "inject 1 to 7 simultaneous faults into the state register ... at least 7 simultaneous faults are required". It also exhaustively injects into all gates (Sec. 3.4). So a minimum fault count is obtainable by iterating the budget; it is not an automatic min-cardinality optimisation, but the distinction is thin.
3. FIRMER (FULLTEXT) is multi-cycle (unrolled k-cycle circuits), uses bit-flip/set/reset, per-cycle budget ne and cycle budget nc, and a universally quantified input SEQUENCE x1..xk. Its SAT query is "exists input sequence and fault vector within budget such that output differs without alarm" (Sec. III Def. 4-7; Sec. IV.C). That is per-cycle symbolic input plus fault search in one query. Minimum search is not performed (budget is a parameter) but is a trivial outer loop.
4. uArchiFI (FULLTEXT, FMCAD 2023) states unbounded techniques are "ill-suited" for fault injection (Sec. IV.A) and uses BMC only. Its Use Case I (VerifyPIN v7) is a PIN/authentication-bypass with single fault found as counterexample (Sec. VI.A): close to a "secure-boot compare" case study at RTL+software level.
5. NEW, not in earlier notes: k-Fault-Resistant Partitioning (k-FRP), Couroussé/Jan et al. (eprint 2024/247; TCHES version). I could NOT open the paper (eprint returned HTTP 403; not worked around). From search snippets and a CEA RISC-V Summit 2025 abstract that I did read (FULLTEXT of the abstract only): formally proves "at the gate level" after synthesis that redundancy countermeasures capture up to k faults, independent of program; snippet says inductive approach with unbounded guarantees; applied to the OpenTitan Ibex and "the first step of a secure boot process, a previously intractable verification". This overlaps three of the five project features (unbounded proof, netlist, secure boot). UNVERIFIED in detail; must be read before any claim.
6. CLEAVE's repo contains the full paper PDF (FM2024-full-version.pdf), which I read. It is round-based crypto only, compositional; not control FSMs.

## 1. Per-tool table

Columns: fault types / search vs enumeration / input model / level / synthesis discussion / multi-fault budget / solver / licence. Cites: section and page.

### SYNFI (Nasahl, Osorio, Vogel, Schaffner, Trippel, Rizzo, Mangard; arXiv 2205.04775v2; FULLTEXT)
| Item | Finding | Cite |
|---|---|---|
| Fault types | Faults are gate-function replacement via a mapping (e.g. NAND2 -> AND2 for transient inversion; set gate to 0/1 for stuck-at). Paper says "transient or permanent". No explicit "bit flip on a flop" type; flips are modelled by function replacement. No clock/voltage-glitch effect modelling; the paper says it models faults "at the logical and not at the electrical level" and cannot analyse intra-cycle transients or propagation delay | Sec. 1 p.3; Sec. 3.1 p.6; Sec. 3.7 p.11; Sec. 6 p.27 |
| Search vs enumeration | Enumerates fault locations x mappings, one SAT call each ("for each fault combination ... a new process"); user may give a location list or "exhaustive" all gates. Input values left undefined are chosen by the SAT solver. Minimum number is found by the user re-running with 1..N faults (OpenTitan lifecycle, 1 to 7) | Sec. 3.4 p.9; Sec. 4.2.2 p.21 |
| Input model | Per-experiment fixed input/expected-output state for chosen nodes (a "circuit state"); unspecified inputs are free (SAT-chosen) but shared by faulty and golden copy. Not a per-cycle symbolic sequence | Sec. 3.5 p.9-10; Sec. 3.7 p.12 |
| Level | Synthesized gate-level netlist (Yosys JSON in repo flow; paper uses Synopsys DC + proprietary lib and Yosys + Nangate45) | Sec. 1 p.2; Sec. 4 p.13; Sec. 4.3 p.23 |
| Time / multi-cycle | Time-independent model: pipeline registers replaced by pass-through, loops removed. Can model "a fault in multiple clock cycles" only by separate fault configs; each loop iteration analysed separately; automatic unrolling is listed as future work. The lifecycle "three faults in three cycles" attack is analysed as three separate single-fault experiments | Sec. 3.3.2 p.8; Sec. 6 p.27; Sec. 4.2.1 p.20 |
| Synthesis dependence | Yes, central (see headline 1). Verifies that synthesis did not remove redundancy; Yosys FSM recoding weakens sparse encoding (3 -> 2 faults); register merge halves Hamming distance | Abstract; Sec. 4.1.3 p.17-18; Sec. 4.2.3 p.21; Sec. 5 p.25 |
| Fault budget | "Simultaneous Faults" N in the spec file; all N-subsets of locations tried | Listing 1 p.5; Sec. 3.1 |
| Solver | Tseitin CNF, PySAT with MiniSat22 chosen after benchmarking | Sec. 3.6.1 p.11 |
| Guarantee | "No false negatives within the bounds of the fault specification"; false positives possible from unreachable start states | Sec. 3.7 p.12 |
| Licence | Apache-2.0 (REPO: /synfi/LICENSE) | repo |
| Case study | OpenTitan AES, lifecycle controller (production -> RMA state, token compare), Ibex lockstep. Lifecycle FSM/RMA transition is a security-state-entry analysis, similar in spirit to a boot-gating FSM | Sec. 4.2 p.19-22 |
| Own admitted limits | Needs manual state spec; one cycle of state; combinatorial explosion in fault combinations; no layout | Sec. 6 p.26-27 |

### FIRMER (Tan, Gao, Chen, Song, Wu; arXiv 2307.00561v1, TCHES 2024; FULLTEXT of arXiv v1)
| Item | Finding | Cite |
|---|---|---|
| Fault types | bit-flip (tau_bf), bit-set (tau_s), bit-reset (tau_r); transient, single gate output at one cycle. Clock glitch / underpowering / voltage glitch are cited as physical causes, with the three types said to capture them | Sec. II (fault types, Def. 3) |
| Search vs enumeration | Neither enumerates nor minimises explicitly: "conditionally-controlled faulty circuit" with a control input per gate; SAT finds a fault vector if one exists within budget; "avoids explicit enumeration of all possible fault test vectors". Budget fixed per query; no minimum-k optimisation reported | Sec. I Contributions; Sec. IV; Sec. VI |
| Input model | Universally quantified input SEQUENCE (x1..xk) over the unrolled k cycles, i.e. per-cycle symbolic input | Def. 5; Sec. IV.C |
| Level | Verilog gate-level netlists (benchmarks synthesised with Synopsys DC O-2018.06-SP2 and manually unrolled; round-based crypto, DAG per cycle) | Sec. V Benchmarks |
| Synthesis dependence | Motivation only ("flaws introduced by front-end tools (e.g., optimization passes)", Sec. I). No experiment varying synthesis | Sec. I |
| Multi-fault budget | Fault-resistance model zeta(ne, nc, T, l): ne faults per cycle, nc cycles with faults, fault type set, gate class (combinational c, registers r, both cr). Cardinality constraints via Z3 sorting networks | Def. 6; Sec. IV.C |
| Solver | Z3 bit-vector -> DIMACS -> Glucose 4.2.1 (parallel); bitwuzla SMT variant compared | Sec. V |
| Complexity | Verification problem NP-complete (arXiv v1); journal version snippet says coNP-complete (SNIPPET; I did not reconcile) | Abstract; Sec. III |
| Scale | 19 circuits (925-40,184 gates), 46/48 tasks under 3 min, FIVER fails 23 at 24 h | Abstract; Sec. V |
| Licence | Paper says open-source. The only repo I can reach (CLEAVE) has NO LICENSE file (REPO: top-level listing shows none; README has none). Standalone FIRMER repo: UNVERIFIED | repo |
| Own scope | Round-based crypto circuits that "can be unrolled" with bounded cycles; not control FSMs; no alarm-gated boot property | Sec. II.B |

### CLEAVE (Tan, Yang, Song, Chen, Wu; FM 2024; full-version PDF in repo; FULLTEXT)
| Item | Finding | Cite |
|---|---|---|
| Fault types / budget | Same three types and (ne, nc, T, l) model as FIRMER | Sec. 3 |
| Method | Decomposes round-based crypto circuits into single-round sub-circuits, verifies each by SAT/SMT (FIRMER-extend) or BDD (FIVER-extend); composition soundness claimed | Sec. 1, 4 |
| Level / synthesis | Verilog gate-level netlists, Synopsys DC; no synthesis-variance study | Sec. 5 Benchmarks |
| Solver | Z3 4.11.2, bitwuzla 0.1, glucose >= 4.0 (REPO README) | repo README |
| Licence | none in repo (REPO) | repo |
| Fit to project | Crypto rounds only; does not address FSM/boot control | Sec. 1 |

### FIVER (Richter-Brockmann, Sasdrich, Moradi; TCHES 2021, ePrint 2021/936)
Paper PDF NOT reachable: eprint PDF returned 403 and tches.iacr.org returned a bot-protection denial; not worked around. All cells below are UNVERIFIED for the paper itself; what I have is (a) the C++ repo copy inside CLEAVE (REPO: README and config), and (b) how SYNFI, FIRMER, uArchiFI describe it (FULLTEXT of those papers, i.e. second-hand), and (c) R2's reading of the IACR artifact readme.
| Item | Finding | Cite |
|---|---|---|
| Fault types | Mapping file; the shipped `model/mixed.txt` maps each gate type to set / reset / complementary function (e.g. and -> set, reset, nand; reg -> set, reset, not). So set, reset, bit-flip-like | REPO FIVER_extend/model/mixed.txt |
| Search vs enumeration | Enumerates fault locations/permutations per logic stage and builds a BDD per fault; "interrupt" option stops at first effective fault; reports effective/ineffective/detected. FIRMER Sec. VI describes it as exploring each fault vector. No minimum search | REPO config/verify; FIRMER Sec. VI (second-hand) |
| Input model | All inputs symbolic via BDD; netlist must be acyclic (SYNFI says user must unroll manually) | SYNFI Sec. 1 p.2 (second-hand); uArchiFI Sec. VII |
| Level | Gate-level netlist (.v or .nl); limited gate library (SYNFI p.2) | repo; second-hand |
| Budget | `fault.number` n per logic stage, `variate` (uni/bivariate), location c/s/cs | REPO config/verify |
| Solver | ROBDD (CUDD 3.0.0), no SAT | REPO README |
| Licence | Source has a LICENSE file in the original repo per R2; contents unread by me. The CLEAVE copy: unknown. UNVERIFIED |  |
| Scale | 90M+ faults < 50 min on 1-round CRAFT (SNIPPET/abstract, R2) |  |

### uArchiFI (Tollec, Asavoae, Couroussé, Heydemann, Jan; FMCAD 2023 pp.101-109; repo v0.2; FULLTEXT paper + REPO README)
| Item | Finding | Cite |
|---|---|---|
| Fault types | Effects set, reset, flips, fliplsb (paper); repo adds diff, xor, fixed value. Transient, timed window (`-timing a:b`). Location L = registers in paper; "implemented extension" to intermediate combinational functions; repo selects signals. No clock-glitch semantic (paper maps clock/voltage glitches to multiple set/reset) | Sec. III.B p.103; Sec. III.C; repo README |
| Search vs enumeration | Reachability: BMC solver finds a counterexample (fault location + timing) satisfying the attacker goal phi with cnt <= N. Repo `iterator` adds constraints from each CEX and re-runs to enumerate further faults. Max N is a parameter; no automatic minimum, but N=1,2.. loop is trivial | Sec. IV.A p.104; repo Iterator CLI |
| Input model | Inputs X are the fault-control inputs; PIN/data values symbolic (Use Case I: both PINs symbolic, assumed digit-wise different). Software fixed as binary in initial memory; external inputs largely not per-cycle data | Sec. III.A; Sec. VI.A |
| Level | RTL (Verilog/SystemVerilog) via Yosys to SMT-LIB2/BTOR2; "does not support advanced technological netlists" but a Yosys-simplified word-level netlist is used. It does say it keeps sequential logic rather than unrolling | Sec. VII p.108 |
| Synthesis dependence | Not discussed as a topic; states SYNFI does the netlist/synthesis check | Sec. VII |
| Budget | N total faults over the run (`cnt`); timing range T | Sec. III.B |
| Solver | BMC; yosys-smtbmc + yices, Pono, others (README default yices); paper compares three checkers | Sec. VI; README |
| Unbounded | Explicitly rejected: "unbounded verification ... ill-suited on the fault injection problem"; BMC bound set from software run length. k-completeness lost with PC sandboxing | Sec. IV.A-B p.104 |
| Case study | VerifyPIN v7 on CV32E40P: single fault bypasses authentication (counterexample); crypto software; "robust hardware" case | Sec. VI p.105-107 |
| Licence | LGPL-2.1 (REPO LICENSE.txt, README "Licensing"); paper CC BY 4.0; Yosys 0.61 pinned in Docker | repo |
| Extension | CEA RISC-V Summit 2025 abstract (read in full, 2 pages): k-FRP extension proves gate-level k-fault security independent of software; OpenTitan secure-boot first step; new single-fault vulnerability in Ibex register file | abstract pp.1-2 |

### Other directly relevant work (mostly UNVERIFIED)
| Work | What I got | Status |
|---|---|---|
| k-FRP "Fault-Resistant Partitioning of Secure CPUs for System Co-Verification" (eprint 2024/247; TCHES) | Search snippets: inductive unbounded verification of k-fault-resistant partitioning, RTL or netlist, Yosys flow, program-independent; plus CEA summit abstract (above) | Paper UNVERIFIED (eprint 403). Highest-risk overlap |
| SOLOMON (DATE 2020) | Abstract page read: formal methods map vulnerable cipher regions to hardware at RTL or gate level; AES/CLEFIA/Simon; method details not on page | UNVERIFIED (abstract only) |
| EXERT (UF; SAT+ATPG+FSM analysis, 25k-gate RISC-V) | Search snippet only | UNVERIFIED |
| eprint 2026/648 "Synthesis of RTL-based Characterization Programs for Fault Injection" (Alle Monne et al., HOST 2026) | Abstract read: BMC-based program synthesis, bit-flips on microarchitectural signals, RTL | abstract only; not about countermeasure verification |
| OneSpin Fault Injection App (commercial) | Product page title in search; formal safety-mechanism verification, RTL and netlist | SNIPPET only |
| SoK automated FI (eprint 2024/1944) | Surfaced in search; fetch 403 earlier (R2); not read | UNVERIFIED |
| VerFI, FIESTA, SHADOWFI, NAIL | per R2 only | not re-read |
| Synthesis removing redundancy (general EDA) | Standard redundancy-removal engines exist (arXiv 1503.06632 listed in search; not opened); SYNFI is the security-specific primary source | SNIPPET + SYNFI FULLTEXT |
| "ChipFI", "FormalFI" | No hits for these names | not found |
| IC3/PDR or k-induction on fault countermeasures | No tool named PDR found; k-FRP is described as inductive (SNIPPET) | UNVERIFIED |

## 2. Verdict per project feature

| Project feature | Verdict | Basis |
|---|---|---|
| (a) Min-fault search over unrolled cycles (smallest k such that boot breaks within T) | Partly covered; remaining difference is only that min-k is an automatic optimisation | FIRMER encodes a fault vector search with (ne, nc) over unrolled cycles (FULLTEXT); SYNFI reports a minimum by iterating N=1..7 (FULLTEXT p.21); uArchiFI iterates N and CEX (REPO). An outer loop over the budget is trivially applicable to all three. Treat as an incremental framing, not established as new |
| (b) Per-cycle symbolic input | Covered by FIRMER (input sequence x1..xk, Def. 5 / Sec. IV.C). SYNFI: not per-cycle (one fixed state, free unspecified inputs). uArchiFI: data symbolic, fault controls per cycle | FULLTEXT |
| (c) Unbounded PDR proof (netlist/FSM) | Appears uncovered by the tools whose full text I read (FIRMER, SYNFI, CLEAVE bounded; uArchiFI explicitly says unbounded is ill-suited). BUT k-FRP is described (SNIPPET only) as inductive/unbounded at gate level, so UNVERIFIED and a major risk. No tool named PDR/IC3 found. Do not claim uncovered until k-FRP is read | |
| (d) Netlist / synthesis-variance quantification | Qualitative effect covered by SYNFI (Yosys FSM recoding 3->2; register merge 4->2; Sec. 4.1.3, 4.2.3). Cross-version/cross-flow quantification (e.g. Yosys 0.33 vs 0.38): appears uncovered in what I read, UNVERIFIED for k-FRP, SoK 2024/1944 and non-open sources | |
| (e) Secure-boot case study | Not a distinct class: SYNFI lifecycle RMA entry (Sec. 4.2), uArchiFI VerifyPIN authentication bypass (Sec. VI.A), and k-FRP "first step of secure boot" on OpenTitan (SNIPPET + CEA abstract). A toy FSM boot-compare example appears uncovered as a published toy, but that is a weak statement | |
| (f) Open, pip+Yosys easy flow, plain-language explanation | Not assessed by me beyond R2 and READMEs; usability claims are not novelty claims | |
| (g) Fault types | Project: single-cycle bit flips. FIRMER, FIVER, uArchiFI, SYNFI all cover set/reset or stuck-at too; none models clock glitch at electrical level. Project is narrower | FULLTEXT |

## 3. Safe wording paragraph (for the owner to edit)

"This project reproduces, on a small secure-boot style FSM, ideas that are established in the literature: SAT/SMT fault analysis of Yosys gate-level netlists over unrolled cycles with a bounded number of simultaneous faults (SYNFI, FIRMER, CLEAVE), bounded model checking of fault effects with a fault-count budget (uArchiFI), and the observation that logic synthesis can weaken redundancy-based fault countermeasures (SYNFI). It adds a small, self-contained, reproducible implementation that searches for the smallest number of single-cycle bit flips that defeats a boot check, an attempt at an unbounded proof of a bound, and a comparison of results across two Yosys versions. I read the full texts of SYNFI, FIRMER, CLEAVE and uArchiFI, but could not read FIVER's paper or the k-fault-resistant-partitioning paper, which may be closer to parts of this work. Nothing is established as new, and results hold only for the stated fault model (modelled bit flips, not physical glitches), cycle bound and fault budget."
(Do not add 'first', 'novel', 'proves secure', or any statement about physical feasibility.)

## 4. Hard questions an examiner would ask on related work

1. SYNFI Sec. 4.1.3 already shows Yosys optimisation reducing the fault threshold from 3 to 2. What does your Yosys 0.33 vs 0.38 comparison add that is not that experiment? Is the difference a version effect or a flag effect (`nofsm`, `opt`, `abc`)?
2. FIRMER and CLEAVE already search fault vectors over multiple unrolled cycles with a symbolic input sequence. Where exactly does your search differ from running FIRMER with ne=1, nc=T and decreasing the budget?
3. SYNFI got "at least 7 faults" by iterating the budget. Is your "minimum" anything other than that loop in one script?
4. k-FRP claims unbounded, program-independent, gate-level k-fault proofs and an OpenTitan secure-boot step. Have you read it? What does your PDR result establish that theirs does not, on what property, and is your invariant over reachable states from reset only?
5. uArchiFI argues unbounded verification is ill-suited for fault injection. Your PDR proof: for what exact property, with what fault counter encoding, and does the proof depend on a bounded fault budget?
6. What is your threat model: faults only on gate outputs and flops, single cycle each? FIRMER/FIVER/uArchiFI/SYNFI also cover set/reset/stuck. Why is bit-flip sufficient, and what changes for stuck-at or multi-cycle-persistent faults?
7. Is your toy FSM representative? Did you check your counterexample on a design from the literature (e.g. SYNFI lifecycle controller or VerifyPIN) so that agreement with a published tool exists beyond your own netlist?
8. How do you know the netlist you analyse is the one after the synthesis a vendor would use (Design Compiler vs Yosys, technology mapping vs generic gates)? SYNFI and FIRMER use technology libraries (Nangate45); your gate-primitive cells may differ.
9. Does your fault model exclude faults on the alarm/compare logic (a blacklist in FIRMER/FIVER)? Which gates are protected and why?
10. Your result is a bound on T and k. How is T justified relative to the boot sequence length, and what happens beyond T?
11. SYNFI states no false negatives within spec but possible false positives from unreachable start states; how do you exclude unreachable states (start from reset, or invariants)?
12. Is the tool or code reuse licence-compatible with the tools you compared (Apache-2.0 SYNFI, LGPL-2.1 uArchiFI, FIRMER/CLEAVE with no licence in repo)? Did you copy any code or only ideas?

## 5. URLs opened and what was read

| URL | What I read |
|---|---|
| https://arxiv.org/pdf/2205.04775 (WebFetch returned binary; pdf saved locally and read with pdftotext) | SYNFI full paper v2, all sections |
| https://arxiv.org/pdf/2307.00561 (same method) | FIRMER full paper v1, Sec. I-VII, parts of appendix |
| https://github.com/CEA-LIST/uArchiFI (git clone, read-only) | README (all), file listing, LICENSE name; LGPL-2.1 from README |
| https://github.com/S3L-official/CLEAVE (git clone) | README, FIVER_extend README/config/model/mixed.txt, FM2024-full-version.pdf (CLEAVE full paper), file list (no LICENSE) |
| https://github.com/lowRISC/synfi (git clone, read-only) | file list, LICENSE head (Apache-2.0), README grep |
| https://repositum.tuwien.at/handle/20.500.12708/188805 and its bitstream PDF | uArchiFI FMCAD 2023 paper, Sec. I-VII |
| https://riscv-europe.org/summit/2025/media/proceedings/2025-05-14-RISC-V-Summit-Europe-P1.3.10-COUROUSS%C3%89-abstract.pdf | CEA 2-page abstract (uArchiFI, k-FRP, OpenTitan) |
| https://eprint.iacr.org/2026/648 | abstract only |
| https://past.date-conference.com/proceedings-archive/2020/html/0667.html | SOLOMON abstract only |
| https://eprint.iacr.org/2021/936.pdf | BLOCKED (HTTP 403); not worked around |
| https://eprint.iacr.org/2024/247.pdf | BLOCKED (HTTP 403); not worked around |
| https://tches.iacr.org/index.php/TCHES/article/download/9072/8659/6511 | BLOCKED (bot-protection denial); not worked around |
| WebSearch (4 queries: formal FI netlist SAT minimum faults; synthesis removes redundancy; ChipFI/FormalFI/PDR; k-induction/IC3 FI) | result titles/snippets only (SNIPPET label) |

## 6. Not done

- FIVER paper, k-FRP paper, SoK 2024/1944, SOLOMON, EXERT, VerFI/FIESTA full texts not read.
- No tool was executed. SYNFI exact table values beyond those quoted not re-extracted.
- No claim of absence is made: searches were four queries plus reading; "appears uncovered" means only "not found in what I read".
- Earlier notes said FIRMER/CLEAVE "depend on commercial synthesis in documented flow": confirmed for benchmarks (Design Compiler), but the tools themselves take any Verilog netlist via a parser (CLEAVE README), so not a hard dependency.
