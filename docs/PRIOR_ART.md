# Prior art and positioning

Updated about 2026-11-19 19:30 UTC.

Status: first pass 2026-11-19 by opening abstract/README pages only (the table and sections below keep that wording). A later agent read the FULL texts of SYNFI, FIRMER, CLEAVE and uArchiFI (`research/c2/r10_prior_art/R10_PRIOR_ART_FULL.md`); its findings are in the section "Update from the full-text read (R10)" below and override the older cells where they differ. NOT read: the k-FRP paper (k-fault-resistant partitioning, eprint 2024/247; eprint returned HTTP 403) and the FIVER paper (UNREAD). No 2025-2026 paper was found in two searches (not proof of absence).

## Tools

| Tool | What it does (as opened) | Open source | Not covered / unknown |
|---|---|---|---|
| SYNFI (lowRISC, venue UNVERIFIED (older notes said CHES 2022; the arXiv page gives none), arXiv 2205.04775; github.com/lowRISC/synfi) | Formal pre-silicon fault analysis of synthesized netlists (Yosys flow). Parse netlist to graph, inject faults from a JSON fault spec into an extracted subcircuit, check whether faults are effective and whether countermeasures detect them. Found weaknesses in OpenTitan AES, contributed fixes. | Yes, Apache-2.0. Python, `parse.py` then `fi_injector.py`. | Pages did not state transient vs permanent, fault count, multi-cycle. Resolved by a run: it enumerates user-specified fault sets and does not search for a minimum (see `compare/synfi_run/SYNFI_RESULT.md`; that run was a one-cycle transition from a hand-chosen start state). |
| FIVER (TCHES 2021, ePrint 2021/936) | Netlist-level, BDD-based symbolic fault injection; CRAFT, LED-64, AES; 90M+ faults in under 50 min. | Code link not on page; artifacts.iacr.org/tches/2021/a16 exists (UNVERIFIED contents). | Fault model detail unverified; BDD blow-up reported by others. |
| FIRMER (TCHES 2024 issue 4, arXiv 2307.00561) | SAT-encoded fault-resistance verification of crypto circuits on Verilog gate-level netlists; 46/48 benchmarks about 3 min. Closest method match to this project. | Paper says open-source tool; repo link UNVERIFIED. | Multi-cycle FSM, minimal fault set: not stated on abstract. |
| CLEAVE (Springer LNCS 2024, 10.1007/978-3-031-71177-0_13) | Compositional SAT/SMT+BDD verification of sequential crypto circuits against faults; Verilog netlists. | Said to be open source (UNVERIFIED, paywalled). | Not opened. |
| SCFI (Graz, DATE 2023; abstract via search only) | FSM hardening: next-state function absorbs history; automatic synthesis tool, claimed open. This is a countermeasure, not a verifier. | Claimed. UNVERIFIED. | Note arXiv 2303.03711 is SCRAMBLE-CFI, a different (CPU CFI) paper. |
| FIES / FIDELITY / OpenTitan lifecycle-controller hardening | Not opened. UNVERIFIED. |  |  |

## Update from the full-text read (R10; labels as in the R10 file)
- SYNFI (FULLTEXT) already studies synthesis dependence: it motivates the tool by tools optimising inserted structures away (Sec. 1), re-synthesising a sparsely encoded AES FSM with Yosys and aggressive optimisation dropped the needed simultaneous faults from 3 to 2 (Sec. 4.1.3), and synthesis merged duplicate registers of a flash-erase signal, cutting effective Hamming distance 4 to 2 (Sec. 4.2.3). So "synthesis changes the verdict" is NOT uncovered; a systematic cross-flow quantification (this project's Yosys 0.33 versus 0.38, and the 32-netlist matrix) was not found in what was read, but nothing is established as new.
- SYNFI (FULLTEXT) obtains a minimum by iterating the fault budget ("1 to 7 simultaneous faults ... at least 7 required", Sec. 4.2.2), so a min-fault count is an outer loop that these tools already allow.
- FIRMER (FULLTEXT) is multi-cycle (unrolled circuits), has per-cycle and per-run fault budgets, and quantifies over an input SEQUENCE; its SAT query is "exists input sequence and fault vector within budget". Multi-cycle analysis with a per-cycle input is therefore covered.
- k-FRP (Couroussé/Jan et al., eprint 2024/247; TCHES): paper UNREAD; search snippets and a two-page CEA abstract say it proves gate-level k-fault resistance with unbounded, inductive guarantees and applies it to the OpenTitan Ibex and the first step of a secure boot. It may cover unbounded proofs, the netlist level and the secure-boot theme. UNVERIFIED in detail: must be read before any claim about the PDR result.
- Not claimable as new: any of (a) min-fault search, (b) per-cycle input, (c) the unbounded PDR result, (d) the synthesis-variance observation, (e) the secure-boot case study.

**Safe wording paragraph (for the owner to edit; from R10):** "This project reproduces, on a small secure-boot style FSM, ideas that are established in the literature: SAT/SMT fault analysis of Yosys gate-level netlists over unrolled cycles with a bounded number of simultaneous faults (SYNFI, FIRMER, CLEAVE), bounded model checking of fault effects with a fault-count budget (uArchiFI), and the observation that logic synthesis can weaken redundancy-based fault countermeasures (SYNFI). It adds a small, self-contained, reproducible implementation that searches for the smallest number of single-cycle bit flips that defeats a boot check, an attempt at an unbounded proof of a bound, and a comparison of results across two Yosys versions. I read the full texts of SYNFI, FIRMER, CLEAVE and uArchiFI, but could not read FIVER's paper or the k-fault-resistant-partitioning paper, which may be closer to parts of this work. Nothing is established as new, and results hold only for the stated fault model (modelled bit flips, not physical glitches), cycle bound and fault budget."

## (1) What is new, strictly (first-pass text; superseded by the R10 update above: nothing established as new)
- Probably NOT new: SAT/SMT fault verification on Yosys netlists (SYNFI, FIRMER, CLEAVE); the idea that countermeasures can be defeated.
- Possibly new, UNVERIFIED against full papers: (a) framing as a minimum-cardinality fault search (smallest k such that a wrong-key boot occurs) over T unrolled cycles; (b) a worked secure-boot/password FSM case with a single-fault break through a shared AND net in a duplicated-compare plus sparse-FSM design; (c) a k<=2 bounded result for a triplicated split-word design. Shared-net common-mode weakness is a known class (SYNFI and fault-redundancy literature), so (b) is a clean teaching example, not a new class.
- Honest default: "nothing established as new" until the SYNFI and FIRMER papers are read in full.

## (2) Compare / merge
Done in a narrow form: `compare/synfi_run/SYNFI_RESULT.md` (SYNFI enumerates and does not search; two-cycle chain crashed; re-synthesized V2 not run). The plan below is the original one.
Run SYNFI (Apache-2.0) on the same netlist: write a fault spec targeting the shared AND net and the compare cone, and check it reports the single-fault break found by z3. Then check whether SYNFI or FIRMER finds a minimum set or only confirms given sets. One day is realistic for the single-fault reproduction; FIRMER only if its repo is public.

## (3) Wording
Use: "reproduces SYNFI/FIRMER-style SAT/SMT netlist fault analysis on a small secure-boot FSM, and teaches why duplication with a shared net fails; adds a minimum-fault-count search over multi-cycle unrolling (to be confirmed against prior tools)."
Avoid: "first", "novel verifier", "proves secure" (only up to the stated k and T bound), "breaks OpenTitan" unless it does, any claim about physical feasibility of single-net faults.

## (4) Disclosure
Applies if a real open design (for example OpenTitan) is shown vulnerable. OpenTitan policy (github.com/lowRISC/opentitan/security/policy): report privately via GitHub Security Advisories, notify security@opentitan.org without details, PGP keys listed; full CVD policy at opentitan.org/cvd-policy (not opened; opentitan.org/security returned 404). Scope for pre-silicon RTL issues UNVERIFIED. For the student's own toy FSM, no disclosure is needed; if the netlist derives from a real design, report first and wait before publishing.
