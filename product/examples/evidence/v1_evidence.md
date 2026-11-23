# Fault-resilience evidence report: V1

Design evidence - not a certification or lab result. Generated (example: regenerate to stamp the time).

## 1. Summary in plain words

This report collects what GlitchSAT measured about how many modelled bit flips it takes to make the design accept a wrong input, and what that could mean in the attack-potential language of PSA Certified and Common Criteria (JIL). Plain reading first; details and every assumption follow.

- v1 / rtl/v1.v (opt): the smallest attack found needs 1 modelled flip(s) (no attack with fewer, checked up to 3 flips in 6 cycles). Margin estimate: minimum 1 modelled flip(s) -> 1 injection event(s) assumed -> PSA rating 20 (<= L3 ceiling 20, in scope at L3: the device must resist it); JIL re-scored 16 ('Basic').
- v1 / rtl/v1.v (plain): the smallest attack found needs 1 modelled flip(s) (no attack with fewer, checked up to 3 flips in 6 cycles). Margin estimate: minimum 1 modelled flip(s) -> 1 injection event(s) assumed -> PSA rating 20 (<= L3 ceiling 20, in scope at L3: the device must resist it); JIL re-scored 16 ('Basic').
- v1 / reference/spike_netlists/v1.json (given-netlist): the smallest attack found needs 1 modelled flip(s) (no attack with fewer, checked up to 3 flips in 6 cycles). Unbounded check (known power-up state): proved: no attack with 0 flip(s) at any cycle; smallest attack at any cycle: 1 flip(s). Margin estimate: minimum 1 modelled flip(s) -> 1 injection event(s) assumed -> PSA rating 20 (<= L3 ceiling 20, in scope at L3: the device must resist it); JIL re-scored 16 ('Basic').

> Estimate only. It supports, and never replaces, evaluation by an accredited lab: the scores use the schemes' point tables, but the factor levels are assumptions about a modelled result, not a lab rating of a demonstrated attack.

## 2. Scope and bounds

Each result holds only inside these bounds. A 'minimum' is the smallest attack within them.

| netlist variant | fault model | attack goal | attacker input | bound | initial state |
|---|---|---|---|---|---|
| v1 / rtl/v1.v (opt) | single-cycle bit flip of any gate output or flop Q | boot_word == 0x96 at some cycle < 6 | `sig` free, held constant, != key 0xC3 | <= 3 flips, 6 cycles | known power-up state from the netlist (engine default) |
| v1 / rtl/v1.v (plain) | single-cycle bit flip of any gate output or flop Q | boot_word == 0x96 at some cycle < 6 | `sig` free, held constant, != key 0xC3 | <= 3 flips, 6 cycles | known power-up state from the netlist (engine default) |
| v1 / reference/spike_netlists/v1.json (given-netlist) | single-cycle bit flip of any gate output or flop Q | boot_word == 0x96 at some cycle < 6 | `sig` free, held constant, != key 0xC3 | <= 3 flips, 6 cycles | known power-up state from the netlist (engine default) |

Note recorded with the results: BOUNDED, NOT UNBOUNDED: verdict holds only for <= 3 single-cycle bit-flip faults (gate outputs and flop Q) within 6 cycles on this synthesized netlist. It says nothing about more faults, longer runs, other fault types (stuck-at, multi-bit/spatial, clock/voltage effects), or physical feasibility. Toy design; modelled faults.

## 3. Netlist provenance

The verdict depends on the exact synthesized netlist. Keep the hash with the result.

| variant | netlist | SHA-256 (as recorded) | hash check | surface / lint netlist | size | Yosys | solver |
|---|---|---|---|---|---|---|---|
| v1 / rtl/v1.v (opt) | results/work/v1_opt.json | c19dd22839d6aa70 (RTL source rtl/v1.v, first 16 hex digits of SHA-256 (the synthesized netlist is not stored with this result)) | file not given or hash refers to the RTL source | - / - | 61 gates, 8 flops | not recorded | glitchsat.py ; z3 not recorded |
| v1 / rtl/v1.v (plain) | results/work/v1.json | c19dd22839d6aa70 (RTL source rtl/v1.v, first 16 hex digits of SHA-256 (the synthesized netlist is not stored with this result)) | file not given or hash refers to the RTL source | - / - | 72 gates, 8 flops | not recorded | glitchsat.py ; z3 not recorded |
| v1 / reference/spike_netlists/v1.json (given-netlist) | reference/spike_netlists/v1.json | 84730fa7b5e3dbef (netlist file, first 16 hex digits of SHA-256) | matches the file given | same netlist / same netlist | 58 gates, 8 flops | Yosys 0.33 (git sha1 2584903a060) | glitchsat.py ; z3 not recorded |

Report generated (example: regenerate to stamp the time) by GlitchSAT evidence 0.9.0 on Python 3.13.18.

| input file | SHA-256 (first 16) |
|---|---|
| evidence/data/recorded/reproduce/v1_rtl_opt_k0.json | f8cabc52d02014db |
| evidence/data/recorded/reproduce/v1_rtl_opt_k1.json | f06ef0f04d2612c2 |
| evidence/data/recorded/reproduce/v1_rtl_opt_k2.json | fa21fee9aef27900 |
| evidence/data/recorded/reproduce/v1_rtl_opt_k3.json | 4d4f84c16272a2a6 |
| evidence/data/recorded/reproduce/v1_rtl_plain_k0.json | 3f6c0e0ec03196e9 |
| evidence/data/recorded/reproduce/v1_rtl_plain_k1.json | 970fcc861cd77d62 |
| evidence/data/recorded/reproduce/v1_rtl_plain_k2.json | d2c695754ff06e58 |
| evidence/data/recorded/reproduce/v1_rtl_plain_k3.json | 3ec63c7b918a915b |
| evidence/data/recorded/reproduce/v1_spike_given-netlist_k0.json | 19796c82c072de90 |
| evidence/data/recorded/reproduce/v1_spike_given-netlist_k1.json | e84cc4964a1afe93 |
| evidence/data/recorded/reproduce/v1_spike_given-netlist_k2.json | aa5d3e9163df09bb |
| evidence/data/recorded/reproduce/v1_spike_given-netlist_k3.json | 238b3affc4f8f154 |
| evidence/data/recorded/surface/v1_spike_surface.json | c77a12a0eeeb5943 |
| evidence/data/recorded/lint/v1_spike_lint.json | b01773bdf6111f01 |
| examples/v1.json | 84730fa7b5e3dbef |
| evidence/data/recorded/unbounded/v1_stored_k0.json | 6c49d7071fb5c9e5 |
| evidence/data/recorded/unbounded/v1_stored_k1.json | e4b3e770b593c3c0 |
| evidence/data/recorded/unbounded/v1_stored_k2.json | 0277134cd42b574e |
| evidence/data/recorded/unbounded/v1_stored_k3.json | 761dc39d0b1334bf |

## 4. Results per assumption

One row per solver run. Different netlist variants of the same RTL (stored netlist, Yosys flows) are different assumptions about what gets fabricated; they are listed separately because synthesis can change the minimum.

| variant | max flips k | cycles | verdict | min flips | witness (net @ cycle) | runtime s | label |
|---|---|---|---|---|---|---|---|
| v1 / rtl/v1.v (opt) | 0 | 6 | NO_ATTACK_UP_TO_BOUND | - | - | 0.058 | MEASURED |
| v1 / rtl/v1.v (opt) | 1 | 6 | ATTACK_FOUND | 1 | ok @ cycle 1 | 0.31 | MEASURED |
| v1 / rtl/v1.v (opt) | 2 | 6 | ATTACK_FOUND | 1 | ok @ cycle 1 | 0.258 | MEASURED |
| v1 / rtl/v1.v (opt) | 3 | 6 | ATTACK_FOUND | 1 | ok @ cycle 1 | 0.258 | MEASURED |
| v1 / rtl/v1.v (plain) | 0 | 6 | NO_ATTACK_UP_TO_BOUND | - | - | 0.064 | MEASURED |
| v1 / rtl/v1.v (plain) | 1 | 6 | ATTACK_FOUND | 1 | ok @ cycle 1 | 0.378 | MEASURED |
| v1 / rtl/v1.v (plain) | 2 | 6 | ATTACK_FOUND | 1 | ok @ cycle 1 | 0.428 | MEASURED |
| v1 / rtl/v1.v (plain) | 3 | 6 | ATTACK_FOUND | 1 | ok @ cycle 1 | 0.414 | MEASURED |
| v1 / reference/spike_netlists/v1.json (given-netlist) | 0 | 6 | NO_ATTACK_UP_TO_BOUND | - | - | 0.051 | MEASURED |
| v1 / reference/spike_netlists/v1.json (given-netlist) | 1 | 6 | ATTACK_FOUND | 1 | ok @ cycle 1 | 0.339 | MEASURED |
| v1 / reference/spike_netlists/v1.json (given-netlist) | 2 | 6 | ATTACK_FOUND | 1 | ok @ cycle 1 | 0.281 | MEASURED |
| v1 / reference/spike_netlists/v1.json (given-netlist) | 3 | 6 | ATTACK_FOUND | 1 | ok @ cycle 1 | 0.34 | MEASURED |

## 5. Unbounded proof status

The bounded runs above look at a fixed number of clock cycles. The unbounded check asks the same question for any number of cycles: 'PROVED_UNBOUNDED' for k flips means no attack with k flips exists at any time, under the same fault model, on the same netlist (matched by its hash) and for the same goal. It is a proof about the model, not about a chip.

| variant | status (known power-up state) | verdict per flip budget | other power-up assumptions | method agreement | tool and netlist |
|---|---|---|---|---|---|
| v1 / rtl/v1.v (opt) | not run for this netlist (no unbounded result with this netlist hash and goal) | - | - | - | - |
| v1 / rtl/v1.v (plain) | not run for this netlist (no unbounded result with this netlist hash and goal) | - | - | - | - |
| v1 / reference/spike_netlists/v1.json (given-netlist) | Unbounded check (known power-up state): proved: no attack with 0 flip(s) at any cycle; smallest attack at any cycle: 1 flip(s). | k=0: PROVED_UNBOUNDED, k=1: ATTACK_FOUND, k=2: ATTACK_FOUND, k=3: ATTACK_FOUND | arbitrary: k=0 ATTACK_FOUND, k=1 ATTACK_FOUND, k=2 ATTACK_FOUND, k=3 ATTACK_FOUND; free_nongoal: k=0 PROVED_UNBOUNDED, k=1 ATTACK_FOUND, k=2 ATTACK_FOUND, k=3 ATTACK_FOUND | all methods agree | ext/unbounded/src/unbounded.py 0.1.0 (minicdcl, Python 3.13.18); netlist reference/spike_netlists/v1.json 84730fa7b5e3dbef |

> Recorded with the unbounded result: UNBOUNDED IN TIME, BOUNDED IN EVERYTHING ELSE: the verdict covers any number of clock cycles, for at most 0 modelled single-cycle bit flips (gate outputs and flop Q nets) in total, on this one netlist, with the attacker input held constant and not equal to the key. It says nothing about more flips, other fault types (stuck-at, multi-cycle, clock or voltage effects), other netlists of the same RTL, or physical feasibility. Toy design; modelled faults.

## 6. Minimal attacks

### v1 / rtl/v1.v (opt)

- witness 1: ok @ cycle 1

Attacker input used by the witness: {"sig": "0xE3"}.

Engine explanation: SINGLE POINT OF FAILURE: one AND gate output, net `ok`, combines 8 input bits of `sig` (the redundant checks converge here) and alone drives 8 of 8 bits of `boot_word`. Flipping it for ONE cycle (cycle 1) makes a wrong `sig` look valid, even though the checks upstream are duplicated.

Generic fix pattern (not derived from this netlist): Do not let any one net decide. Split the decision across independent bits: give each redundant check its own disjoint group of result-word bits (no shared AND/OR of the checks), use a sparse result encoding with Hamming distance > fault budget, and make the final accept require all groups to agree bit-by-bit.

### v1 / rtl/v1.v (plain)

- witness 1: ok @ cycle 1

Attacker input used by the witness: {"sig": "0xD3"}.

Engine explanation: SINGLE POINT OF FAILURE: one AND gate output, net `ok`, combines 8 input bits of `sig` (the redundant checks converge here) and alone drives 8 of 8 bits of `boot_word`. Flipping it for ONE cycle (cycle 1) makes a wrong `sig` look valid, even though the checks upstream are duplicated.

Generic fix pattern (not derived from this netlist): Do not let any one net decide. Split the decision across independent bits: give each redundant check its own disjoint group of result-word bits (no shared AND/OR of the checks), use a sparse result encoding with Hamming distance > fault budget, and make the final accept require all groups to agree bit-by-bit.

### v1 / reference/spike_netlists/v1.json (given-netlist)

- witness 1: ok @ cycle 1

Attacker input used by the witness: {"sig": "0x03"}.

Engine explanation: SINGLE POINT OF FAILURE: one AND gate output, net `ok`, combines 8 input bits of `sig` (the redundant checks converge here) and alone drives 8 of 8 bits of `boot_word`. Flipping it for ONE cycle (cycle 1) makes a wrong `sig` look valid, even though the checks upstream are duplicated.

Generic fix pattern (not derived from this netlist): Do not let any one net decide. Split the decision across independent bits: give each redundant check its own disjoint group of result-word bits (no shared AND/OR of the checks), use a sparse result encoding with Hamming distance > fault budget, and make the final accept require all groups to agree bit-by-bit.

Attack surface listing: 1 distinct minimum attack(s) of 1 flip(s); complete = True (stop reason: exhausted; method: exhaustive). Distinct cycles per attack: 1 to 1; 1 attack(s) fit in one cycle.

| # | flips (net @ cycle) | attacker inputs that work |
|---|---|---|
| 1 | ok @ 1 | 255 |

## 7. Attack surface

### v1 / reference/spike_netlists/v1.json (given-netlist)

| net | kind | copy | used by attacks | share | cycles |
|---|---|---|---|---|---|
| ok | gate_output | merge | 1 | 100.0% | 1:1 |

Flips per copy: merge 100.0% (copies identified from names). Attacks by number of copies touched: 0: 1.

> BOUNDED and MODELLED: all attacks of the minimum size m with single-cycle bit flips of gate outputs and flop Q within 6 cycles on this netlist. Nothing is said about more cycles, other fault types, or physical feasibility.

## 8. Redundancy lint (structural, no solver)

### v1 / reference/spike_netlists/v1.json (given-netlist)

Redundancy lint verdict: merged (mode: names); copies: c1, c2; single points: 18.

- copy groups from hierarchy names: c1 (8 input-dependent nets), c2 (8 input-dependent nets)
- 1 first merge point(s) combine copies before the decision bits: `ok` (c1+c2) (18 merge nets in total)
- copies c1, c2 are structurally identical (same canonical hash): a structural-hashing pass (e.g. opt_merge) can fold them unless the flow keeps them apart
- 8 decision bit(s) depend on more than one copy: bits [0, 1, 2, 3, 4, 5, 6, 7]

## 9. Margin estimate (attack potential)

> Estimate only. It supports, and never replaces, evaluation by an accredited lab: the scores use the schemes' point tables, but the factor levels are assumptions about a modelled result, not a lab rating of a demonstrated attack.

### v1 / rtl/v1.v (opt)

Result: minimum 1 modelled flip(s) -> 1 injection event(s) assumed -> PSA rating 20 (<= L3 ceiling 20, in scope at L3: the device must resist it); JIL re-scored 16 ('Basic').

| assumption (override with --assume key=value) | value |
|---|---|
| fault_type | voltage |
| flips_per_event | any |
| events | None |
| events_from_cycles | False |
| success_rare | False |
| id_elapsed | month |
| id_expertise | expert |
| id_knowledge | public |
| id_access | lt10 |
| id_equipment | specialized |
| exploit_elapsed | None |
| exploit_expertise | proficient |
| exploit_knowledge | public |
| exploit_access | lt10 |
| exploit_equipment | specialized |
| jil_equipment | None |
| jil_open_samples | public |
| target_psa_level | 3 |

- flips_per_event = any (default for fault_type=voltage): one injection event is assumed able to cause every flip of the attack in its clock cycle, so 1 flip(s) count as 1 event

| PSA factor | identification | pts | exploitation | pts | basis |
|---|---|---|---|---|---|
| Elapsed time | <= one month | 3 | <= one day | 3 | identification: PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20); exploitation: PSA JSADEN004 v1.3, section 5.1.3, 'glitch required on each target device': exploitation <= one day |
| Expertise | Expert | 5 | Proficient | 2 | PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20) |
| Knowledge of the TOE | Public | 0 | Public | 0 | PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20) |
| Access to TOE (samples) | < 10 samples | 0 | < 10 samples | 0 | PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20) |
| Equipment | Specialized | 3 | Specialized | 4 | PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20) |
| total |  | 11 |  | 9 | = 20 (PSA JSADEN004 v1.3, section 4.2, Table 1 (page 19)) |

| PSA level | ceiling | this estimate | reading |
|---|---|---|---|
| L2 | 15 | 20 | above ceiling by 5: out of scope |
| L3 | 20 | 20 | within ceiling: in scope, must be resisted |
| L4 | 24 | 20 | within ceiling: in scope, must be resisted |

| JIL factor | identification | pts | exploitation | pts | basis |
|---|---|---|---|---|---|
| Elapsed time | < one month | 3 | < one day | 3 | identification: PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20); exploitation: PSA JSADEN004 v1.3, section 5.1.3, 'glitch required on each target device': exploitation <= one day; JIL bands are '< one day' / '< one week' where PSA writes '<='; the factor levels are the PSA example's choices re-scored on JIL Table 13, not a JIL worked example |
| Expertise | Expert | 5 | Proficient | 2 | PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20) |
| Knowledge of the TOE | Public | 0 | Public | 0 | PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20) |
| Access to TOE (samples) | < 10 samples | 0 | < 10 samples | 0 | PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20) |
| Equipment | Standard | 1 | Standard | 2 | JIL v3.2.1, Table 10 'Categorisation of Tools' (para. 67): 'Electrical glitches workstation' is standard |
| Open samples | Public / not required | 0 | NA | NA | JIL v3.2.1, Table 12 (para. 98): open samples not required = 0 |
| total |  | 9 |  | 7 | = 16: 'Basic' (JIL v3.2.1, Table 14 'Rating of vulnerabilities and TOE resistance' (para. 121)) |

Timing precision (reported, not scored): every listed minimum attack puts all its flips in ONE clock cycle (source: 1 witness(es) of the bounded runs, not a complete listing): a single, well-timed injection event could in principle cause it, if one event can flip all of those nets.

| if ... | events | PSA | JIL | JIL band |
|---|---|---|---|---|
| one glitch can cause every flip of a cycle (flips_per_event=any) | 1 | 20 | 16 | Basic |
| every flip needs its own injection (flips_per_event=1) | 1 | 20 | 16 | Basic |

### v1 / rtl/v1.v (plain)

Result: minimum 1 modelled flip(s) -> 1 injection event(s) assumed -> PSA rating 20 (<= L3 ceiling 20, in scope at L3: the device must resist it); JIL re-scored 16 ('Basic').

| assumption (override with --assume key=value) | value |
|---|---|
| fault_type | voltage |
| flips_per_event | any |
| events | None |
| events_from_cycles | False |
| success_rare | False |
| id_elapsed | month |
| id_expertise | expert |
| id_knowledge | public |
| id_access | lt10 |
| id_equipment | specialized |
| exploit_elapsed | None |
| exploit_expertise | proficient |
| exploit_knowledge | public |
| exploit_access | lt10 |
| exploit_equipment | specialized |
| jil_equipment | None |
| jil_open_samples | public |
| target_psa_level | 3 |

- flips_per_event = any (default for fault_type=voltage): one injection event is assumed able to cause every flip of the attack in its clock cycle, so 1 flip(s) count as 1 event

| PSA factor | identification | pts | exploitation | pts | basis |
|---|---|---|---|---|---|
| Elapsed time | <= one month | 3 | <= one day | 3 | identification: PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20); exploitation: PSA JSADEN004 v1.3, section 5.1.3, 'glitch required on each target device': exploitation <= one day |
| Expertise | Expert | 5 | Proficient | 2 | PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20) |
| Knowledge of the TOE | Public | 0 | Public | 0 | PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20) |
| Access to TOE (samples) | < 10 samples | 0 | < 10 samples | 0 | PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20) |
| Equipment | Specialized | 3 | Specialized | 4 | PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20) |
| total |  | 11 |  | 9 | = 20 (PSA JSADEN004 v1.3, section 4.2, Table 1 (page 19)) |

| PSA level | ceiling | this estimate | reading |
|---|---|---|---|
| L2 | 15 | 20 | above ceiling by 5: out of scope |
| L3 | 20 | 20 | within ceiling: in scope, must be resisted |
| L4 | 24 | 20 | within ceiling: in scope, must be resisted |

| JIL factor | identification | pts | exploitation | pts | basis |
|---|---|---|---|---|---|
| Elapsed time | < one month | 3 | < one day | 3 | identification: PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20); exploitation: PSA JSADEN004 v1.3, section 5.1.3, 'glitch required on each target device': exploitation <= one day; JIL bands are '< one day' / '< one week' where PSA writes '<='; the factor levels are the PSA example's choices re-scored on JIL Table 13, not a JIL worked example |
| Expertise | Expert | 5 | Proficient | 2 | PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20) |
| Knowledge of the TOE | Public | 0 | Public | 0 | PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20) |
| Access to TOE (samples) | < 10 samples | 0 | < 10 samples | 0 | PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20) |
| Equipment | Standard | 1 | Standard | 2 | JIL v3.2.1, Table 10 'Categorisation of Tools' (para. 67): 'Electrical glitches workstation' is standard |
| Open samples | Public / not required | 0 | NA | NA | JIL v3.2.1, Table 12 (para. 98): open samples not required = 0 |
| total |  | 9 |  | 7 | = 16: 'Basic' (JIL v3.2.1, Table 14 'Rating of vulnerabilities and TOE resistance' (para. 121)) |

Timing precision (reported, not scored): every listed minimum attack puts all its flips in ONE clock cycle (source: 1 witness(es) of the bounded runs, not a complete listing): a single, well-timed injection event could in principle cause it, if one event can flip all of those nets.

| if ... | events | PSA | JIL | JIL band |
|---|---|---|---|---|
| one glitch can cause every flip of a cycle (flips_per_event=any) | 1 | 20 | 16 | Basic |
| every flip needs its own injection (flips_per_event=1) | 1 | 20 | 16 | Basic |

### v1 / reference/spike_netlists/v1.json (given-netlist)

Result: minimum 1 modelled flip(s) -> 1 injection event(s) assumed -> PSA rating 20 (<= L3 ceiling 20, in scope at L3: the device must resist it); JIL re-scored 16 ('Basic').

| assumption (override with --assume key=value) | value |
|---|---|
| fault_type | voltage |
| flips_per_event | any |
| events | None |
| events_from_cycles | False |
| success_rare | False |
| id_elapsed | month |
| id_expertise | expert |
| id_knowledge | public |
| id_access | lt10 |
| id_equipment | specialized |
| exploit_elapsed | None |
| exploit_expertise | proficient |
| exploit_knowledge | public |
| exploit_access | lt10 |
| exploit_equipment | specialized |
| jil_equipment | None |
| jil_open_samples | public |
| target_psa_level | 3 |

- flips_per_event = any (default for fault_type=voltage): one injection event is assumed able to cause every flip of the attack in its clock cycle, so 1 flip(s) count as 1 event

| PSA factor | identification | pts | exploitation | pts | basis |
|---|---|---|---|---|---|
| Elapsed time | <= one month | 3 | <= one day | 3 | identification: PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20); exploitation: PSA JSADEN004 v1.3, section 5.1.3, 'glitch required on each target device': exploitation <= one day |
| Expertise | Expert | 5 | Proficient | 2 | PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20) |
| Knowledge of the TOE | Public | 0 | Public | 0 | PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20) |
| Access to TOE (samples) | < 10 samples | 0 | < 10 samples | 0 | PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20) |
| Equipment | Specialized | 3 | Specialized | 4 | PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20) |
| total |  | 11 |  | 9 | = 20 (PSA JSADEN004 v1.3, section 4.2, Table 1 (page 19)) |

| PSA level | ceiling | this estimate | reading |
|---|---|---|---|
| L2 | 15 | 20 | above ceiling by 5: out of scope |
| L3 | 20 | 20 | within ceiling: in scope, must be resisted |
| L4 | 24 | 20 | within ceiling: in scope, must be resisted |

| JIL factor | identification | pts | exploitation | pts | basis |
|---|---|---|---|---|---|
| Elapsed time | < one month | 3 | < one day | 3 | identification: PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20); exploitation: PSA JSADEN004 v1.3, section 5.1.3, 'glitch required on each target device': exploitation <= one day; JIL bands are '< one day' / '< one week' where PSA writes '<='; the factor levels are the PSA example's choices re-scored on JIL Table 13, not a JIL worked example |
| Expertise | Expert | 5 | Proficient | 2 | PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20) |
| Knowledge of the TOE | Public | 0 | Public | 0 | PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20) |
| Access to TOE (samples) | < 10 samples | 0 | < 10 samples | 0 | PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20) |
| Equipment | Standard | 1 | Standard | 2 | JIL v3.2.1, Table 10 'Categorisation of Tools' (para. 67): 'Electrical glitches workstation' is standard |
| Open samples | Public / not required | 0 | NA | NA | JIL v3.2.1, Table 12 (para. 98): open samples not required = 0 |
| total |  | 9 |  | 7 | = 16: 'Basic' (JIL v3.2.1, Table 14 'Rating of vulnerabilities and TOE resistance' (para. 121)) |

Timing precision (reported, not scored): every listed minimum attack puts all its flips in ONE clock cycle (source: attack-surface listing of 1 minimum attack(s), complete = True): a single, well-timed injection event could in principle cause it, if one event can flip all of those nets.

| if ... | events | PSA | JIL | JIL band |
|---|---|---|---|---|
| one glitch can cause every flip of a cycle (flips_per_event=any) | 1 | 20 | 16 | Basic |
| every flip needs its own injection (flips_per_event=1) | 1 | 20 | 16 | Basic |

Scheme rules that bear on the reading:

- At PSA Level 2 physical attacks on the TOE are out of scope during the exploitation phase. (PSA JSADEN004 v1.3, section 5.1.3 (page 24))
- At PSA Level 3 and Level 4, physical attacks on the device are permitted in the exploitation phase. (PSA JSADEN004 v1.3, section 5.1.3 (page 24))
- For Level 4, laser fault injection needs to be considered as an attack method. (PSA JSADEN004 v1.3, section 5.1.3 (page 27))
- Elapsed time assumes the attacker works eight hours a day or runs scripts twenty-four hours a day; for probabilistic attacks take the time for a 50/50 chance. (PSA JSADEN004 v1.3, section 4.1.1 (pages 16-17))
- Combined attacks are rated factor by factor for the combination, not by adding the totals of the parts. (PSA JSADEN004 v1.3, section 4.3 (page 20))
- Under defence in depth 'a successful exploit may take multiple glitches at separate times to carry out'. (PSA JSADEN004 v1.3, section 5.1.3 (page 25))
- If the probability of successful glitches is very low, exploitation takes more than one month and the two-glitch total rises to 25 (above the Level 4 ceiling of 24). (PSA JSADEN004 v1.3, section 5.1.3 (two-glitch example, page 27))
- For voltage-glitch bypass of firmware rollback protection (total 21), the document notes that with countermeasures two glitches might still fall in scope for Level 4. (PSA JSADEN004 v1.3, section 5.4.3 (pages 38-39))
- Several perturbations may be required (one per firewall check); performing them is 'difficult, however still feasible' because the check can be found by synchronisation. No point value is given for this. (JIL v3.2.1, section 5.9.10, paras. 273-274)
- For fault analysis, a lack of accuracy in the synchronisation requirements 'can render the analysis to recover the key much more complex'; no point value is attached to timing precision. (JIL v3.2.1, section 5.4, para. 148)
- Perturbation attacks: an effect that occurs only in one of 10 or 100 attempts may still be usable, depending on the application context. (JIL v3.2.1, section 5.3, para. 145)
- Table 13 adds one point when several similar specialized tools are needed; this tool never adds it on its own (set jil_equipment or rate by hand). (JIL v3.2.1, Table 13 footnote (para. 120) and section 4.4 (para. 59))
- The '> four months' level (Table 1a) 'only applies as a reasonable exception' and must be justified with analysis or measurement results; it is used only when set explicitly. (JIL v3.2.1, section 2, paras. 14-15)

Not scored, because no cited factor covers them: the number of distinct minimum attacks (more alternatives plausibly make identification easier) and the timing precision between flips in different cycles. Both are reported above for the evaluator to weigh.

## 10. Limits

- Faults are MODELLED single-cycle bit flips of gate outputs and flop Q nets. Stuck-at, multi-bit spatial, timing and voltage effects are not modelled, and nothing here was measured on hardware.
- Every verdict is bounded: at most the stated number of flips within the stated number of cycles, on this exact synthesized netlist. Another synthesis run, flow or tool version can change the minimum (the netlist hash identifies what was analysed).
- 'No attack up to k' is not a proof of security; it says nothing about more flips, longer runs or other fault types.
- The number of flips is not the number of physical glitches. One supply, clock or EM glitch can flip several nets in one cycle; the margin estimate states which assumption it uses and shows the result under both extremes.
- The attack-potential figures use the PSA Certified and JIL point tables, but the factor levels are assumptions about a modelled result. Only an evaluation lab rates a real attack path; this report is design evidence that supports, and never replaces, that evaluation.
- An unbounded proof removes the cycle bound only. It keeps every other bound: this netlist, this fault model and count rule, this attacker input, this goal, this power-up assumption and the flip budgets that were checked.
- No source was found in which an evaluation lab states that it accepts formal pre-silicon fault results as evaluation evidence.

## 11. Sources

- PSA Certified Attack Methods, JSADEN004 v1.3 (issue 01/02/2024): https://www.psacertified.org/app/uploads/2024/04/JSADEN004-PSA_Certified_Attack_Methods-V1.3.pdf
- JIL Application of Attack Potential to Smartcards and Similar Devices v3.2.1 (Feb 2024): https://www.commoncriteriaportal.org/files/ccfiles/JIL-Application-of-Attack-Potential-to-Smartcards-v3.2.1.pdf
- Section, table and paragraph numbers are given next to every factor above.
