# R1: Who would use a netlist fault-injection (FI) analysis tool, and what would make them adopt it

Date: 2026-11-19. Labels: [OPENED] = I fetched and read the page; [SNIPPET] = search-result snippet only (treat as UNVERIFIED); [INFERENCE] = my reasoning, not evidence.
Caveat up front: I found NO forum/Reddit/StackExchange threads of practitioners complaining; searches for them returned vendor blogs, papers and patents. Evidence of pain below comes from tool authors, vendors and course pages, i.e. people with an interest. Do not present it as user-survey data.

## 1. Evidence by persona

### Hardware security engineers on open silicon (OpenTitan / lowRISC style)
- [OPENED] https://lowrisc.org/news/opentitans-pre-silicon-security-simulation-and-verification/ : OpenTitan says "We do not conduct fault injection evaluation on pre-silicon FPGAs"; they use SYNFI (formal, gate-level), Fault-Resistant Partitioning for Ibex lockstep (formal then Verilator), a custom FI-extended Verilator, and commercial Synopsys VC Z01X. Stated pains of the empirical route: mapping FPGA fault behaviour to the ASIC "is not straightforward"; evaluations "highly time-consuming"; results "not always 100% reproducible"; root-causing "exceedingly difficult". The page gives no run times or coverage numbers, links no open FI flow, and says the FI tooling is "only available for OpenTitan Silver members and above" (so an accessible open flow is a gap).
- [OPENED] SYNFI paper intro (via https://github.com/lowRISC/synfi and https://arxiv.org/pdf/2205.04775 [SNIPPET for the arXiv text]): synthesis can optimize away redundancy countermeasures, so analysis must be on the synthesized netlist; functional tests do not cover faults; hardware FI needs specialist equipment; post-silicon fixes need another tape-out. This is exactly the project's "depends on the exact netlist" finding, so the motivation is established in the literature.
- [OPENED] SYNFI README: install is `pip install -r requirements.txt`, then manually mkdir output, run parse.py then fi_injector.py; inputs are Yosys JSON netlist + JSON fault spec + a Liberty-derived cell library converted by a script; README does not document the file schemas or limitations. [INFERENCE] Setup friction is documentation, not install.

### Secure-boot / firmware teams
- [OPENED] NCC Group, MediaTek BootROM glitch: https://www.nccgroup.com/research/there-s-a-hole-in-your-soc-glitching-the-mediatek-bootrom/ . Signature check bypassed with ~USD 390 hardware, "several days worth of bruteforce", 15-20% success; flaw is in mask ROM so unpatchable; authors say in-silicon brown-out detection is the best mitigation and that fault resistance must be designed in before tape-out. Software counters (redundant checks, random delays, CFI) only raise cost. Relevance: the bypass-the-check scenario is real, and the "redundant check" mitigation is exactly what the project tests.
- [OPENED] eShard MCUboot series pt1: https://www.eshard.com/blog/mcuboot-under-good-pressure-part-1 . Pains: hardware campaigns slow, samples can be destroyed, needs deep expertise; root cause hard to understand for countermeasure design; emulation "depends on the fault model, and so may, or may not, be realistic". This is firmware-level; it does not address RTL/netlist.
- [SNIPPET] Patents on randomized execution / redundant checks in secure boot (USPTO) show redundancy is the standard industrial countermeasure; UNVERIFIED details.

### EDA / verification tool developers and academic tool authors
- [OPENED] Kudelski Verilaptor: https://kudelskisecurity.com/research/verilaptor-software-fault-simultation-in-hardware-designs . Wanted pure-software FI on Verilog before manufacture; pains: slow full-SoC sim, Verilator hides signals unless marked public (edit design), faults hardcoded; says VerFI needs a synthesized netlist which they wanted to avoid; names Glitchoz0r, FiSim (Riscure), VerFI.
- [OPENED via search description, partly] VerFI/VerMFi https://github.com/vmarribas/VerMFi : gate-level fault simulator with random test vectors and user-defined adversary bounds, reports coverage; optional Yosys front end; default expects Synopsys DC netlist. [SNIPPET] FIVER (BDD-based, TCHES): needs acyclic netlist, manual unrolling.
- [OPENED] Intel HDFIT NetlistFaultInjector: README fetch returned 404; known only from search snippet: sv2v + Yosys, inject into netlist, simulate with Verilator. UNVERIFIED.
- [SNIPPET] ARMORY (https://arxiv.org/pdf/2105.13769) says Riscure FiSim is closed-source, first-order only, Unicorn-based. UNVERIFIED.
- [SNIPPET] DVCon Europe 2025 paper 163 (Siemens): says HW-implemented FI needs silicon and FI creates a verification-workflow gap. The PDF was unreadable (compressed), so only the search summary exists. UNVERIFIED.
- [SNIPPET] Academic claims "no automated framework for comprehensive FI assessment; existing EDA tools not equipped" (UF/Tehranipoor group papers such as SOFI, ISQED25) and CRAFT (https://arxiv.org/abs/2503.03877): 9248 scenarios pre-silicon, 97.31% search-space reduction for post-silicon. [OPENED abstract] for CRAFT numbers; the "no framework" claim is UNVERIFIED and is a motivating claim by authors.
- Commercial: Secure-IC Virtualyzr (pre-silicon FI/SCA evaluation, mentions CC/SESIP/FIPS; [SNIPPET], UNVERIFIED), Synopsys Z01X (named by lowRISC [OPENED]), Cadence security flow ([SNIPPET]). These exist and are paid; open tools are thin.

### Students and instructors
- [OPENED] UNSW CS6420 Lab 3 https://cgi.cse.unsw.edu.au/~cs6420/labs/lab03fault/ : FI is taught as differential fault analysis on AES with FPGA bitstreams, phoenixAES, Makefile targets, Python venv; 10% of course. Lab 4 (snippet) uses Yosys JSON netlists for logic-locking SAT attacks, so Yosys JSON netlists are already used in teaching.
- [SNIPPET] TU Delft DFA lab (MATLAB), sroman0 "hardware security labs" GitHub repo (secure boot, FI, Verilog/C), The Hardware Hacking Handbook ch.6 FI lab (O'Reilly). UNVERIFIED contents.
- [SNIPPET] Hack@DAC (student/industry contest on buggy SoC RTL; 54 teams in 2018; organizers say students lack venues to learn design security review); benchmark designs reused widely in research; no FI-specific content found. https://semiengineering.com/hacking-soc-ip-under-pressure . A newer arXiv survey of competitions (listed as 2608.22202) is [SNIPPET] only; UNVERIFIED.
- [INFERENCE] Gap in teaching: existing labs use FPGA/hardware or DFA on crypto; I found no course lab where students bypass a boot-style check on a gate netlist and reason about redundancy. This is an absence-of-evidence finding from limited searches, not proof.

### Certification labs
- [SNIPPET] Secure-IC claims support for CC/SESIP evaluations. No primary evidence on how evaluation labs actually work with open tools; I did not open Common Criteria/JIL attack-potential documents. Treat certification-lab adoption as UNVERIFIED and low-probability for a student tool. [INFERENCE] Labs rely on silicon benches (Riscure, NewAE) and accredited tools.

## 2. What people do instead today
1. Physical benches (ChipWhisperer, ChipShouter, Riscure Spider): slow, specialist, can destroy samples, post-silicon only. [OPENED NCC, eShard]
2. Firmware-level instruction-skip/bit-flip emulation (esReverse, FiSim, ARMORY, SimpliFI): does not see gate-level synthesis effects. [OPENED eShard; others SNIPPET]
3. FPGA fault tests: poor ASIC mapping, not reproducible. [OPENED lowRISC]
4. Custom Verilator/RTL injection scripts (Verilaptor, OpenTitan's own): ad hoc, hardcoded faults. [OPENED]
5. Netlist formal/simulation tools (SYNFI, VerFI, FIVER, HDFIT): academic, thin docs, tied to specific flows (Python+Liberty conversion, Design Compiler, acyclic-only).
6. Commercial (Z01X, Secure-IC): paid, gated.

## 3. What would make adoption happen in an afternoon (derived from the pains above; [INFERENCE] unless cited)
- Input is a plain Yosys netlist/JSON or Verilog that the user already has; one command; no Liberty conversion step. (SYNFI friction is documented above.)
- A worked "secure-boot style check" example that runs in minutes and prints a plain-language story: which wires, which flip, why redundancy shared a wire. Directly answers eShard's "difficult to understand its origin".
- Explicit, versioned netlist provenance and a warning that verdicts depend on the synthesis tool version (lowRISC/SYNFI motivation; the project's own 0.33 vs 0.38 result is strong demo material).
- Honest fault-model statement (eShard: results depend on the fault model). Cross-check by independent simulator/second solver is a differentiator vs one-tool outputs.
- Export of attacks as a testbench/replay (Verilator/iverilog) so engineers can reproduce, addressing "not 100% reproducible".
- Open licence and pip/apt-only install; CI that is actually green (project's CI was never run: fix before pitching).
- Teaching pack: a lab handout, grading-friendly deterministic outputs, a few designs of rising difficulty. UNSW-style labs show 10%-of-course FI labs are normal, so a 2-week lab is a realistic unit.

## 4. Implications for the project direction
- Strongest real niche: educational and small-team pre-silicon check of redundancy countermeasures on synthesized netlists, with a visual/plain-language explanation. Weakest: certification labs and industrial sign-off (no evidence, Z01X incumbency).
- Evidence for demand is indirect (authors/vendors, not users). A cheap test of real demand: ask in OpenTitan/lowRISC, Yosys, and a university hardware-security course contact to try it (do not publish externally without owner consent).
- Gaps to research next: how SYNFI actually performs on the project's designs (already run per status), VERICA/FIVER availability, Z01X/Secure-IC pricing (UNVERIFIED), electronics/analog relevance (voltage-glitch to bit-flip model link) for the owner's "electronics" weakness.
- Unfilled: no practitioner forum evidence found; Common Criteria docs not opened; HDFIT README, DVCon 2025 PDF, TU Delft thesis not read.
