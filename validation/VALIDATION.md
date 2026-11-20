# Independent validation of the z3 fault-injection claims

Method independent of the z3 encoding: `netsim.py` is a plain gate-level simulator over the Yosys JSON
netlist (AND/OR/XOR/NOT/MUX/DFF_P), bit-parallel over all 256 `sig` values (big-int lanes). It flips any
gate output or flop Q for one cycle. Goal (same as solver): `boot_word == 0x96` observed at some cycle
t<T while `sig != 0xC3`. Faults hit the observed net as well (same as solver). No z3 anywhere in the sim;
`smt.py` writes SMT-LIB2 (QF_BV, bit-vector popcount for the fault budget) for boolector 3.x.
Netlists: (A) the spike's `work/v{0,1,2}.json` (what the solver used; keep_hierarchy compares);
(B) `nl/*.json`, my own yosys 0.33 flow (`synth.sh`: keep_hierarchy stripped, `synth -flatten`, `dffunmap`, `abc -g AND,OR,XOR,MUX`).

## Results (T=6 unless stated; sig space always exhaustive: all 255 sig != C3; k=0 gives 0 attacks and honest C3 boots, all designs)

| design / netlist | k | coverage | sim result | solver claim | agree |
|---|---|---|---|---|---|
| V0 (A) | 1 | exhaustive, 120 (site,cycle) | 19 successful single faults (flop Q st[1]@0, st[0]@2..5, c.m, mux gates, compare internals) | SAT | yes |
| V1 (A) | 1 | exhaustive, 396 | exactly 1: net `ok` @ cycle 1, all 255 sigs | SAT via `ok` | yes |
| V2 (A) | 1 | exhaustive, 456 | 0 | UNSAT | yes |
| V2 (A) | 2 | exhaustive T=4 (46,056 sets) and T=6 (103,740 sets) | 0 | UNSAT | yes |
| V2 (A) | 3 | exhaustive T=3 (1,949,476 sets): 182 attacks; exhaustive for the slice "all 3 faults in cycle 1" at T=6 (70,300 sets): 182 attacks (e.g. word[0] + c1/c2 compare nets @1, sig 3 etc.) | SAT | yes |
| V2 (A) | 3 | NOT exhaustive over all cycle combinations at T=6 (C(456,3)=15.7M not run) | | | |
| V0/V1/V2 (A) | - | replay of all 13 SAT witnesses in `work/*_results.json` | 13/13 CONFIRMED (`replay.log`) | | yes |
| boolector (A, my smt.py encoding) | | V2 T=4 k<=2 / V2 T=6 k<=2: **unsat**; V2 T=6 k<=3: sat; V1 T=6 k<=1: sat; V0 T=6 k<=1: sat (`boolector.log`, 0-2 s) | | | yes (second solver, re-encoding) |

Counts: 13 witnesses replayed, 5 boolector queries, ~2.1M simulated fault sets x 255 inputs, 0 disagreements with the solver on netlist (A).

## Finding that matters beyond the z3 encoding: netlist-dependence
On netlist (B) (hierarchy not kept), yosys/abc merge the three identical compare copies: V1 and V2 synthesize to the
same cell counts (V2: 4 of 378 single-fault pairs succeed at T=6; at k=2, 1,266 of 71,253 sets succeed). The
V2 "no attack at k<=2" claim therefore holds only for the netlist with keep_hierarchy compares (A) and is destroyed
by ordinary flat optimisation (the redundancy is removed). V1 (B) also: 4 single faults succeed (not only `ok`; `ok` itself is merged away).
Any report should state the synthesis flow (keep_hierarchy / no merging) as part of the claim.

## Commands (all run from validation/; runtimes on this box)
- `sh synth.sh` (regenerate nl/*.json, ~2 s)
- `python3 k1.py <netlist.json> <top> 6` (k=1 exhaustive; <1 s each) -> `k1_*_spike.log`, `k1_v1_flat.log`
- `python3 k2.py <netlist.json> v2 6 2` (exhaustive pairs; 17 s), `... v2 3 3` (1.9M triples, 163 s) -> `k2_v2.log`, `k3_v2_T3.log`, `k2_v2_flat.log`
- `python3 k3c1.py` (triples at cycle 1, 70,300 sets, ~20 s) -> `k3c1.log`
- `python3 replay.py` -> `replay.log`
- `python3 smt.py <netlist> <top> T k > q.smt2; boolector q.smt2` -> `boolector.log`

## Honest limits
- Same fault model as the solver (single-cycle flips on gate outputs/flop Q, sig held constant, goal = word 0x96 observed in a cycle); this validates the encoding, not the fault model. Fault-set minimality (sat for k<=3 claims) not independently checked beyond: k<=2 exhaustive none exist for V2 (A) T<=6.
- k=3 on V2 at T=6 was not exhaustive; T>6 and k>=4 not simulated. UNSAT at k=2 is shown exhaustively only for T<=6.
- boolector was run on the spike netlist (A) only, by an encoding of my own that shares the netlist reading code (`netsim.Net`) with the simulator; a netlist-parsing bug in that reader would affect both (mitigated: simulator agreed with the solver's independent parsing on all 13 witnesses).
- Synthesis flow (B) differs from the spike's, which is the point of the finding above.
