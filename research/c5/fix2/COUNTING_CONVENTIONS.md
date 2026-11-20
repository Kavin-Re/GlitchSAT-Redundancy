# Counting conventions of related fault-verification tools

Uses only what `research/c4/sweeps/SWEEP_S1.md`, `SWEEP_S2.md` and `research/c3/r23/R23_REPORT.md` SOURCED rows say; everything else is UNVERIFIED. Nothing here is a claim of novelty.

| Tool | Evidence style (sampled vs bound) | Counting unit (per gate vs per stem) | Label |
|---|---|---|---|
| VerFI (2019/2020) | Simulation: user sets adversary bounds and test vectors, so sampled over the vectors given | Not stated on pages read; per fault kind, cycle and cell in the report | SOURCED (thin); unit UNVERIFIED |
| VERICA (TCHES 2022) | Verification of a Verilog netlist against a bound on simultaneous faults (`number`); exhaustiveness not checked here | Bound is max simultaneous faults by location class; stem or branch rule not shown | SOURCED; stem vs gate UNVERIFIED |
| FIRMER (arXiv 2307.00561) | Bound: SAT encoding, upper bounds `ne`, `nc` per vector; fault-resistant if every allowed vector is ineffective | Per gate: each gate faulted at most once per vector (R23) | SOURCED (partial) |
| SYNFI (arXiv 2205.04775) | Enumerates fault sets on the synthesized netlist with SAT (does not search a minimum); user sets count, location, effect | Per gate, or per state-register bit for FSM experiments | SOURCED |
| FIVER (ePrint 2021/936) | Symbolic (BDD) injection, exhaustive within its model | Not stated on the abstract | SOURCED (abstract); unit UNVERIFIED |
| This project | Bound: z3 UNSAT within T cycles and at most k flips (headline T=6, k<=3); `>3` means no attack found up to 3, not secure | Headline: one flipped net (stem) = 1 fault, however many gates read it; fanout counting (net = f faults) is a stress test; neither rule shown physical | MEASURED |

Why this matters: the same design gives 2 flips under stem counting on 26 of 32 rebuilt netlists and 3 on all 32 under fanout counting (`research/c3/rep/REP_REPORT.md`), so a "minimum faults" figure is only comparable between tools when the counting unit matches.

Synthesis dependence was previously shown by SYNFI: faults needed dropped 3->2 after Yosys FSM recoding and 4->2 after register merging; `set_dont_touch` restored 4. Our E2 replicates the effect on a toy design across 864 synthesis configurations and a keep-attribute axis.
