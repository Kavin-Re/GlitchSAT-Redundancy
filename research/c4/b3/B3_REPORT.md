# B3 report: rail-dip and wrong-time-capture fault models, minimum event cost

Everything is a MODELLED single-cycle event on a Yosys gate netlist, solved with z3 (bounded). The SPICE basis (`research/c2/el1_spice`) is SIMULATED circuit-level (ngspice), not silicon. No physical or hardware claim. Verdicts are bounded: T = 6 cycles, at most 3 events, free constant `sig` != 0xC3, known init state, goal observed at any cycle. `>3` = UNSAT for every cost <= 3 (not "secure"). `unknown` = solver timeout; there were 0 unknowns in this matrix (z3 timeout 90 s per call).

## Model semantics (b3pack.py; one event = cost 1)
- RAIL-DIP (EL1: rail-correlated, 1 to 0 only, flop Q not flipped by a dip alone). One event in cycle t forces to 0 every gate output in a chosen set G (gates already at 0 stay 0; no gate is ever driven 0 to 1 by the dip itself; a downstream inverter can turn a dipped 0 into a 1, which is logic). Output-port bits that are gate outputs are dipped too. Flop Q is untouched. Flop D-capture: for flops in the chosen domain the captured value is D AND 0, i.e. the dip makes a flop capture 0 where it should have captured 1. This only differs from the gate dip when D is a flop Q, a constant, or an input (D from a gate is already 0).
- Domain families (netlist-derived, NOT layout): `rail_all` (G = whole design + all flop D pins); `rail_unions` (any union of hierarchy units: c0/c1/c2 compare copies, voters, top logic, from `$flatten\<unit>.` cell names); `rail_half` (unions with <= 50 % of the gates, the "half-design by hierarchy" proxy); `rail_cone` (G = gates in the combinational fanout cone of one net, the "fanout-cone half" proxy); `rail_any` = union of all three. Bounds and controls: `reset_one` (a single gate forced to 0; analogue of B1 `reset_only`, not a rail); `dip_subset` (ONE event may force ANY subset of gates and flop D pins to 0: the worst-case upper bound on a 1-to-0 event, physically unsupported because EL1 saw all high gates on the rail droop together).
- WRONG-TIME CAPTURE, EARLY (EL1 exp B, runt clock pulse: Q takes D). Two-pass cycle: pass 1 computes the D each chosen flop would capture; in this cycle those flops show Q := that D (skip ahead one cycle); pass 2 re-evaluates the cycle and the normal edge captures. Models `early_one` (one flop), `early_all` (all flops together, a global runt), `early_subset` (any subset of flops, one event).
- WRONG-TIME CAPTURE, LATE (EL1 exp C, setup violation, old value kept) = hold: the chosen flops keep Q across one edge. This is equivalent to B1 `flop_hold` / `clock_skip_all` (late capture is observable only as a hold because the next edge captures fresh D). Reused as `hold_one`, `hold_subset`; results agree with B1 (`>3`).
- `stem_flip` re-implemented as events = control: reproduces B1 numbers (V2 spike 3, V2 apt 2, boot_ok 1 everywhere).

## Validation (MEASURED)
- Independent checker `bf_b3.py`: B1's `modelsim.Sim` reader, own `run2()` (adds rail-dip, early capture), own re-derivation of domain groups, exhaustive enumeration of all event sets of cost <= k, 256 `sig` lanes, no z3. Logs `val.log`, `val_a.json` (V0, T=4, k<=2, 9 models), `val_b.json` (V1, T=3, k<=2, 9 models), `val.log` also holds early/hold_subset on V0 and V1 and dip_subset on V0 (T=4, k=1; 1,048,579 sets tried, z3 1 = brute 1). Result: every completed row agrees; 0 disagreements. Positives that were cross-checked: V0 rail_cone 1, V0 dip_subset 1, V0/V1 reset_one 1/2, stem_flip. Most rail/early/hold rows are agreed negatives, so the check mainly tests "no spurious attack"; replay of z3 witnesses in the brute-force simulator was NOT done.
- NOT validated by brute force: all V2, V5 and apt-synthesised rows, V1 dip_subset, anything at T=6 (enumeration too large in Python). V2 relies on the z3 engine, which passed on V0/V1 and the control.
- pytest `test_b3.py`: 16 passed (`cd /tmp/work_b3; python3 -m pytest -q test_b3.py`, 0.6 s): hand-made toy netlists for early = skip-ahead, hold = delay, D-capture dip forces 0 only, no direct 0-to-1 on a flop, inverter turns a dip into a 1; z3 vs brute force on V0 spike for 10 models; stem_flip control vs B1 on V1.

## Matrix (MEASURED; `python3 run_cells.py matrix_T6.jsonl <designs> <models> word,ok` with T=6 CAP=3 TMO=90000; raw rows `matrix_T6.jsonl`)
Netlists: spike = `reference/spike_netlists/v{0,1,2}.json`; apt033 = apt Yosys 0.33 plain flow of `rtl/v*.v` (B1 `synth_variants.sh` flow); V5 = `research/c3/v456/rtl/v5.v` same flow (217 cells). No spike netlist for V5 exists. Cell = minimum events. `word` = boot_word == 0x96; `ok` = boot_ok == 1.

| model | goal | V0 spike | V1 spike | V2 spike | V0 apt | V1 apt | V2 apt | V5 apt |
|---|---|---|---|---|---|---|---|---|
| stem_flip (baseline) | word | 1 | 1 | 3 | 1 | 1 | 2 | 3 |
| stem_flip (baseline) | ok | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| reset_one (1 gate to 0, not a rail) | word | 1 | 2 | 3 | 1 | 2 | 3 | 3 |
| reset_one | ok | 1 | 2 | 3 | 1 | 2 | 3 | 3 |
| rail_all (whole design) | word / ok | >3 | >3 | >3 | >3 | >3 | >3 | >3 |
| rail_half (hierarchy, <= half) | word / ok | >3 | >3 | >3 | >3 | >3 | >3 | >3 |
| rail_unions (any union of hier. units) | word / ok | >3 | >3 | >3 | >3 | >3 | >3 | >3 |
| rail_cone (fanout cone of one net) | word / ok | 1 | >3 | >3 | 1 | >3 | >3 | >3 |
| rail_any (all rail families) | word / ok | 1 | >3 | >3 | 1 | >3 | >3 | >3 |
| dip_subset (any subset, ONE event; bound) | word / ok | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| early_one / early_all / early_subset | word / ok | >3 | >3 | >3 | >3 | >3 | >3 | >3 |
| hold_one / hold_subset (= B1 hold, clock_skip) | word / ok | >3 | >3 | >3 | >3 | >3 | >3 | >3 |
(V0 is the single-compare toy: one dip of a fanout cone in the compare logic gives the word. Witnesses with cycle and sig are in the `events` and `sig` fields of `matrix_T6.jsonl`.)

Smallest dip domain for the dip_subset attack (`python3 minsubset.py v2,v2_apt033,v5_apt033,v1`, MEASURED, one event, T=6): V2 spike 3 gates (word and ok), V2 apt 3, V5 apt 3, V1 spike 2 (out of 396-1302 candidate sites). The 3 sites are the same as the `reset_one` 3-attack: one compare net in each of the three compare copies, all in cycle 1 (witness in `matrix_T6.jsonl`).

## Plain answers
- Does V2 survive a physically grounded 1-to-0 rail event with the word goal? Per cell: whole-rail dip (rail_all): NO attack found up to 3 events (V2 spike, V2 apt, V5 apt), i.e. survives within the bound. Half-design by hierarchy (rail_half, rail_unions): no attack up to 3, survives. Fanout-cone domains (rail_cone): no attack up to 3, survives (V0 does not: 1 event). boot_ok goal: same, no rail attack up to 3 on V2 and V5, even though stem_flip needs only 1 flip. Wrong-time capture (early, hold, any subset): no attack up to 3 on every design. All of this is bounded by T = 6 and 3 events.
- Where it breaks: the verdict depends entirely on selectivity. If one 1-to-0 event may pick WHICH gates fall (dip_subset), V2 and V5 fall to 1 event; the smallest such domain is 3 gates (2 for V1), for V2 and V5 one in each compare copy. EL1 shows all high gates on the dipping rail drooping together, so this selective event is NOT what the SPICE basis supports; but EL1 simulated one tiny rail with a handful of gates, so it also cannot show that a real dip cannot be selective (not established either way).
- Cheapest attack under the rail model (rail_all / half / unions / cone): V0 1 event (cone domain), V1 none (rail models only), V2 none, V5 none. Cheapest under the stem-flip baseline: V2 3 (spike) / 2 (apt), V5 3 (word), 1 (boot_ok). So under the rail models the word goal is harder than under stem flips; the 1-event boot_ok attack (flip the `boot_ok` net, a 0-to-1 flip) is not reachable by a 1-to-0 dip.
- boot_ok caveat: stem_flip finds boot_ok in 1 flip on every design including V5; the dip cannot, because it has no 0-to-1 effect on an output gate and the accept needs boot_ok = 1 from a state that is not accepting. This is a consequence of directionality, not of any extra protection in V2/V5.
- V5 vs V2: identical in this matrix except stem baseline V5 word 3 (apt) vs V2 word 2 (apt); rail rows identical (`>3`).

## Not done / limits
- No unknowns, but caps are 3 events and T=6; `>3` is not a proof beyond that. Domains are netlist-derived (hierarchy units, cones), not from layout or a power grid; "half-design" is a proxy. Set of events is mine; EL1 gives windows only qualitatively.
- Rail models treat the dip as exactly all-or-nothing within a domain; partial dips (some gates cross the threshold, others not) are only bracketed by the dip_subset bound.
- Early capture is a cycle-level abstraction of a runt pulse; sub-cycle effects, metastability and setup/hold windows are not modelled; Q-flip from a dip alone is excluded because EL1 did not see it (so absence of that site is an input assumption).
- Brute-force validation is small (V0, V1 at T <= 4, k <= 2; no V2/V5, no witness replay). Scripts `cmp_b3.py`, `run_cells.py`, `minsubset.py` use the work dir `/tmp/work_b3` (netlists in `nl/`; V5 and V2-apt netlists copied here; V0/V1 apt from `research/c2/b1_faultmodels/netlists`, spike from `reference/spike_netlists`).
- `b3pack.py` is a new z3 unrolling (imports `Netlist` from the unchanged B1 `faultpack.py` copy); B1's tree files were not touched.
- Nothing established as new.
