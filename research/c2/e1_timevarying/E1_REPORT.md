# E1 report: time-varying attacker input

All numbers MEASURED unless stated; faults are modelled single-cycle bit flips, not physical glitches; toy 8-bit designs; netlists = `reference/spike_netlists/v{0,1,2}.json`. Original project files were not edited. Work copy: /tmp/work_e1/.

## 1. How the engine encodes the input
`scripts/glitchsat.py` `build()` creates ONE z3 bit-vector `in_sig` and uses it in every cycle (`inbit`), plus `sig != key` (0xC3). So `sig` is constant by construction. The SymbiYosys wrapper (`formal/src/gen_wrapper.py`) does the same with `assume(sig == sig_q)` and `assume(sig != 8'hC3)` each cycle. The goal is `boot_word == 0x96` observed at some cycle.
Design behaviour that matters: `st` goes F0 -> CC -> (word computed from `sig` at cycle 1) -> holds forever. So fault-free, `sig` is sampled exactly once, at cycle 1. A flip of `st` can re-enter CC and force another sampling, which is the only way later-cycle input values could help an attacker.

## 2. What I added (files in this folder)
- `glitchsat_tv.py`: copy of glitchsat with `inmode` in {`const` (original), `free_never` (fresh input every cycle, != 0xC3 at EVERY cycle), `free_hit` (fresh input every cycle; a goal hit at cycle t counts if input at t != 0xC3)}. `run_matrix.py` drives it. Output: `matrix_bmc_z3.json/.log`.
- `gen_wrapper_free.py` + `run_sby_free.py`: SymbiYosys wrapper with the constancy assume removed under `-DFREEIN`; PDR and BMC runs. Output: `sby_free_results.json`.
- `explicit_state_free.py` (independent check, no z3/sby): exact reachability of (flop state, flips used) with the input chosen freely per cycle. Output: `explicit_state_results.jsonl`.

## 3. Spec: is "wrong key accepted" still defined?
Only partly. With a constant input, "input != key" is unambiguous. With a per-cycle input there is no single "the key" value, so the port-level spec needs a choice, and the choice decides the answer:
- `free_never` (attacker never presents 0xC3 on any cycle): well-defined and the fair strengthening; used for the headline question.
- `free_hit` (accept at t counts if input at t != key): trivially violated by EVERY design at k=0 (present 0xC3 at cycle 1, then anything; the accepted state latches). So this spec is not a usable security property; accepting is bound to the cycle where the key was sampled, which is an internal notion (`st==CC`) and not visible at the port.
- A faithful spec would be "accept only if the value at the sampling cycle was the key" and must name that cycle (or the design needs a sampled/registered key). I did not model it separately beyond `free_never` (which is stricter for the attacker: he may not show the key at the sampling cycle, nor any other).
So the secure-boot spec is well-defined only after adding a sampling-time definition; under `free_never` it is well-defined and I used that.

## 4. Results, bounded z3 (T = 4, 6, 8; k searched 0,1,2,3 until the first attack; runtime = cumulative over the k tried)
V2 rows: k=0,1,2 were NO_ATTACK_UP_TO_BOUND in both const and free_never for T=4,6,8 (e.g. T=8: 0.09 s, 0.5 s, 6.3 s free_never; 0.08, 0.5, 6.7 s const); the table shows the final k=3 attack. V0/V1: attack at k=1, none at k=0, same in both models. `free_hit` rows show the trivial k=0 break.

| design | T | input model | k tried | result | min-k | runtime s (last k) | fault set / attack input trace | label |
|---|---|---|---|---|---|---|---|---|
| V0 | 4 | const | 0..1 | ATTACK_FOUND | 1 | 0.04 | flips c3:st[0] | sig {'sig': '0x28'} | MEASURED |
| V0 | 4 | free_never | 0..1 | ATTACK_FOUND | 1 | 0.04 | flips c3:st[0] | sig ['0x4', '0x0', '0x0', '0x3c'] | MEASURED |
| V0 | 4 | free_hit | 0..0 | ATTACK_FOUND | 0 | 0.01 | no flips | sig ['0x0', '0xc3', '0x3c', '0x3c'] | MEASURED |
| V0 | 6 | const | 0..1 | ATTACK_FOUND | 1 | 0.1 | flips c5:st[0] | sig {'sig': '0x4'} | MEASURED |
| V0 | 6 | free_never | 0..1 | ATTACK_FOUND | 1 | 0.12 | flips c5:st[0] | sig ['0xc0', '0x0', '0x0', '0x0', '0x0', '0x3c'] | MEASURED |
| V0 | 6 | free_hit | 0..0 | ATTACK_FOUND | 0 | 0.02 | no flips | sig ['0x0', '0xc3', '0x3c', '0x3c', '0x3c', '0x3c'] | MEASURED |
| V0 | 8 | const | 0..1 | ATTACK_FOUND | 1 | 0.27 | flips c0:st[1] | sig {'sig': '0xe3'} | MEASURED |
| V0 | 8 | free_never | 0..1 | ATTACK_FOUND | 1 | 0.23 | flips c0:st[1] | sig ['0x0', '0x0', '0xe3', '0x0', '0x8', '0x0', '0x0', '0x3c'] | MEASURED |
| V0 | 8 | free_hit | 0..0 | ATTACK_FOUND | 0 | 0.02 | no flips | sig ['0x0', '0xc3', '0x3c', '0x3c', '0x3c', '0x3c', '0x3c', '0x3c'] | MEASURED |
| V1 | 4 | const | 0..1 | ATTACK_FOUND | 1 | 0.3 | flips c1:ok | sig {'sig': '0xc7'} | MEASURED |
| V1 | 4 | free_never | 0..1 | ATTACK_FOUND | 1 | 0.36 | flips c1:ok | sig ['0xe7', '0x20', '0xc1', '0x3c'] | MEASURED |
| V1 | 4 | free_hit | 0..0 | ATTACK_FOUND | 0 | 0.03 | no flips | sig ['0x0', '0xc3', '0x3c', '0x3c'] | MEASURED |
| V1 | 6 | const | 0..1 | ATTACK_FOUND | 1 | 0.41 | flips c1:ok | sig {'sig': '0xc0'} | MEASURED |
| V1 | 6 | free_never | 0..1 | ATTACK_FOUND | 1 | 0.43 | flips c1:ok | sig ['0xd7', '0x43', '0xe2', '0xd0', '0x3', '0x3c'] | MEASURED |
| V1 | 6 | free_hit | 0..0 | ATTACK_FOUND | 0 | 0.06 | no flips | sig ['0x0', '0xc3', '0x3c', '0x3c', '0x3c', '0x3c'] | MEASURED |
| V1 | 8 | const | 0..1 | ATTACK_FOUND | 1 | 0.65 | flips c1:ok | sig {'sig': '0x3'} | MEASURED |
| V1 | 8 | free_never | 0..1 | ATTACK_FOUND | 1 | 0.45 | flips c1:ok | sig ['0x0', '0xc0', '0x0', '0xc0', '0x24', '0xe3', '0xc2', '0x3c'] | MEASURED |
| V1 | 8 | free_hit | 0..0 | ATTACK_FOUND | 0 | 0.08 | no flips | sig ['0x0', '0xc3', '0x3c', '0x3c', '0x3c', '0x3c', '0x3c', '0x3c'] | MEASURED |
| V2 | 4 | const | 0..3 | ATTACK_FOUND | 3 | 2.74 | flips c1:c2.m; c1:c1.m; c1:$flatten\c0.$abc$251$n | sig {'sig': '0xdb'} | MEASURED |
| V2 | 4 | free_never | 0..3 | ATTACK_FOUND | 3 | 1.51 | flips c1:$flatten\c0.$abc$251$n; c1:$flatten\c1.$abc$251$n; c1:$flatten\c2.$abc$251$n | sig ['0x3', '0xc0', '0x3', '0x3c'] | MEASURED |
| V2 | 4 | free_hit | 0..0 | ATTACK_FOUND | 0 | 0.03 | no flips | sig ['0x0', '0xc3', '0x3c', '0x3c'] | MEASURED |
| V2 | 6 | const | 0..3 | ATTACK_FOUND | 3 | 6.32 | flips c1:c1.m; c1:$flatten\c0.$abc$251$n; c1:$flatten\c2.$abc$251$n | sig {'sig': '0x3'} | MEASURED |
| V2 | 6 | free_never | 0..3 | ATTACK_FOUND | 3 | 4.27 | flips c1:c0.m; c1:$flatten\c1.$abc$251$n; c1:$flatten\c2.$abc$251$n | sig ['0xe3', '0xc0', '0xd3', '0xe4', '0xc0', '0x3c'] | MEASURED |
| V2 | 6 | free_hit | 0..0 | ATTACK_FOUND | 0 | 0.06 | no flips | sig ['0x0', '0xc3', '0x3c', '0x3c', '0x3c', '0x3c'] | MEASURED |
| V2 | 8 | const | 0..3 | ATTACK_FOUND | 3 | 20.88 | flips c1:c1.m; c1:$flatten\c0.$abc$251$n; c1:$flatten\c2.$abc$251$n | sig {'sig': '0x3'} | MEASURED |
| V2 | 8 | free_never | 0..3 | ATTACK_FOUND | 3 | 21.01 | flips c1:$flatten\c0.$abc$251$n; c1:$flatten\c1.$abc$251$n; c1:$flatten\c2.$abc$251$n | sig ['0xe3', '0xd3', '0xe3', '0xeb', '0xd7', '0x0', '0x3', '0x3c'] | MEASURED |
| V2 | 8 | free_hit | 0..0 | ATTACK_FOUND | 0 | 0.09 | no flips | sig ['0x0', '0xc3', '0x3c', '0x3c', '0x3c', '0x3c', '0x3c', '0x3c'] | MEASURED |

Observation: min-k is identical with constant and free per-cycle input for V0 (1), V1 (1) and V2 (3) at T=4,6,8. Runtime is similar (free input adds 5 x 8-bit variables but the sampled cycle is what matters). The attack traces under free input only constrain `sig` at cycle 1 (e.g. V2 T=4: sig = 0xC0 at cycle 1; the other cycles are don't-care values the solver filled in). The 0x3c at the last cycle seen in the traces is a solver filler, not a requirement.

## 5. V2 "no attack with <= 2 flips", free input
- Bounded (z3), T=4,6,8, k<=2, free_never: NO_ATTACK_UP_TO_BOUND (table note above). Survives.
- Bounded (sby smtbmc boolector, free input, `sby_free_results.json`): k=1 and k=2 PASS at depth 12 and 16 (k=2 depth 16 in 6.9 s).
- Unbounded (step 4, ABC PDR through sby, env `formal`, yosys 0.38+92): see section 6.
- Independent explicit-state fixpoint (section 7).
- k=3: attack exists with free input too (min 3, three compare-internal nets at cycle 1), same as constant input.

## 6. Unbounded PDR with free per-cycle input (DONE; env 'formal' existed)
Command: `export PATH=/tmp/mm_root/envs/formal/bin:$PATH; python3 run_sby_free.py /tmp/work_e1/sby` (sby `mode prove`, engine `abc pdr`, wrapper with `-DFREEIN`: `sig != 8'hC3` assumed every cycle, no constancy assume; fault budget counter as in formal/FORMAL.md).
| netlist | k | input | sby result | note |
|---|---|---|---|---|
| spike V2 | 0 | const (control) | PASS "Property proved" | reproduces formal/FORMAL.md |
| spike V2 | 1 | const (control) | PASS proved | |
| spike V2 | 2 | const (control) | PASS proved, invariant 10 clauses / 10 of 35 flops | reproduces |
| spike V2 | 0 | free | PASS proved | |
| spike V2 | 1 | free | PASS proved | |
| spike V2 | 2 | free | **PASS "Property proved", invariant 9 clauses / 8 of 25 flops, verified by ABC (0.5 s engine)** | wall ~2 s |
| spike V2 | 3 | free | engine FAIL (counterexample exists; sby prints no DONE line because yices-smt2 is missing, as already in FORMAL.md) | |
| spike V0, V1 | 1,2,3 | const and free | engine FAIL (same missing-DONE behaviour) | attacks exist |
Non-vacuity: V2 k=0 with `sig == 0xC3` ("honest") gives engine FAIL under free input too (the assertion is reachable). I checked that "NOSTATUS" in my JSON means engine FAIL, from the logfiles (`Status returned by engine: FAIL`).
So: for the V2 spike netlist and k<=2, with the attacker input free every cycle and never equal to 0xC3, ABC PDR reports an unbounded proof. Same limits as the original claim: this netlist only, this fault model only, trust in ABC's checked invariant (no exported certificate), and the wrapper shares its model with glitchsat (same author lineage).

## 7. Independent cross-check (exhaustive, no solver)
`explicit_state_free.py`: enumerates every flop state reachable with 255 input values per cycle (bit-parallel) and every flip subset of size <= K at every cycle, tracking flips used, to a fixpoint. Results (`explicit_state_results.jsonl`, MEASURED, same free_never model):
- V2 k=1: goal unreachable, fixpoint reached (33 state/used pairs, 0.1 s).
- V2 k=2: goal unreachable, fixpoint reached (141 pairs, 3 s). Covers ALL cycle counts, so it agrees with PDR by a different method.
- V2 k=3: goal reachable at cycle 2 (observed), 109 s.
- V1 k=1: goal reachable at cycle 2.
Agreement: all four verdicts match z3 and sby. Caveat: it parses the same Yosys JSON with the same flip semantics (Q flip does not alter stored state), so a shared misreading of the netlist would not be caught; iverilog replay of the free-input attack was not done.

## 8. What this changes about the headline claim
Plainly: nothing breaks. For the spike V2 netlist, letting the attacker change the input on every cycle (never presenting 0xC3) does not lower the minimum number of flips: still 3, and "no attack with <= 2 flips" holds in bounded z3 (T up to 8), in sby BMC (depth 16), in an unbounded ABC PDR run and in an exhaustive explicit-state fixpoint. V0 and V1 stay at 1. So the earlier statement "for any number of cycles" can now also be stated for free per-cycle input under the `free_never` spec, for this netlist and this fault model. The reason is structural: after state CC the design samples `sig` once and then latches, so the extra input freedom has no extra effect; I would not expect this to carry over to designs that keep re-sampling the input, and nothing here tests such designs.
What does change: the claim must state its spec. Under the weaker "accept observed while the current input != key" spec every design (V0, V1, V2) is broken with ZERO flips by an attacker who presents the key once and then changes the input, because the accepted state latches; the project's "wrong key accepted" has to be tied to the sampled value to mean anything for non-constant input. Also unchanged limits: single netlist, other synthesis results of V2 (apt Yosys 0.33, 2-flip attack) remain separate and weaker, no multi-bit or non-flip faults, toy design.

## 9. Not done
No iverilog replay of a free-input attack; no free-input run on the re-synthesized V2 netlists (v2 conda/apt) or on the stored `results/work` netlists; no timing-dependent input (sig is bit-level free, not constrained by protocol or by a real interface); no certificate export from PDR.
