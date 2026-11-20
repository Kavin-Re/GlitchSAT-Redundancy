# R20: benchmark designs, research and scoping

Date 2026-11-19. Labels: MEASURED = produced by a command I ran (logs and JSON in `out/`, wrappers in `designs/wrappers/`, copies under /tmp/work_r20/); SOURCED = from my own knowledge or a file header, not re-checked online; UNVERIFIED = not checked. All faults are modelled bit flips. All verdicts are bounded (k flips, T cycles). Nothing here is claimed as new.

## 1. Short answer
- Best new test of the solver: **DMR AES S-box with full output compare** (2040 gates, 32 flops). MEASURED: k=1 gives NO_ATTACK_UP_TO_BOUND (62 s), k=2 gives ATTACK_FOUND with minimum 2 flips (46 s). This is the first design here where the answer is not "1 flip".
- Every other synthesised design had a **1-flip attack** under my goal (CRC boot compare, CRC boot compare with TMR flag, UART spurious-transmit, S-box with parity check).
- The engine handled everything I fed it without errors. It was loud about unsupported cells in the one case I tried (async-reset flops are not supported by the adapter path; see 4).
- Scaling is set by gates x cycles x k in the z3 PbLe encoding, not by gate count alone (section 5).

## 2. Candidates (SOURCED unless marked)
Network used: only raw.githubusercontent.com GETs of public files (allowed). No git clone, no blocked hosts hit. Licences of the files I fetched are in `designs/*/SOURCE.txt`. None is pinned to a commit (raw `master`), so revision is UNVERIFIED.

| # | Design | Source / licence | Size after synth | Sequential? | Plausible goal | Flow fit / blockers |
|---|---|---|---|---|---|---|
| 1 | AES S-box lookup (secworks/aes `aes_sbox.v`) | raw github, BSD-2-Clause (LICENSE fetched) | MEASURED 1012 gates for one lookup (+16 flops in my wrapper), 2040 for two | combinational; I added registers | wrong S-box output released with the parity/compare alarm silent | Fits. Synthesised and run (section 3). |
| 2 | CRC-8 boot-image compare (alexforencich/verilog-lfsr `lfsr.v`, my wrapper) | raw github, MIT per file header (no LICENSE file fetched, UNVERIFIED) | MEASURED 40 gates, 9 flops (plain); 44 gates, 11 flops (TMR flag) | wrapper registers | image word accepted without matching the stored CRC/key | Fits. Parametric module with function-built mask tables: yosys prints "Replacing memory ... with list of registers" warnings but synthesises. Run. |
| 3 | UART transmitter (alexforencich/verilog-uart `uart_tx.v`) | raw github, MIT per header | MEASURED 368 gates, 34 flops | yes (real FSM, prescaler, bit counter) | transmit a frame with no valid request (start bit and busy) | Fits (sync reset, tied inactive). Security meaning is weak (no secret); good as a control-logic stress. Run. |
| 4 | AES key_mem control (secworks `aes_key_mem.v`) | BSD-2 | MEASURED 32 gates, 7 flops after constants are propagated | yes | `ready` raised with no `init` | Async-reset flops (`$_DFF_PN0_`) survive the project synth.sh flows; only my custom yosys line (`proc; flatten; opt -full; ...; dffunmap`) removes them when reset_n is tied 1. Result is a toy, because init=0 and a constant key make the datapath vanish. Run, not informative. |
| 5 | ISCAS'89 s27 / s298 / s344 / s382 | public benchmark; licence/distribution terms not checked (UNVERIFIED) | s27: about 10 gates, 3 flops (SOURCED, from memory); s298: about 119 gates, 14 flops; s344/s382 about 160/158 gates (SOURCED, approximate) | yes | no security goal; they have no countermeasure and no secret | **Not fetched or run**: I did not find a raw URL I could name with confidence and I did not guess repos. They are fit-compatible (BENCH to Verilog first) but a goal would be invented. |
| 6 | Tiny Tapeout designs with redundancy (TMR, lockstep) | not found | n/a | n/a | n/a | Could not identify one with a known URL; no search tool used. Open item. |
| 7 | OpenTitan `prim_*` (e.g. `prim_sparse_fsm_flop`, `prim_count`, `prim_double_lfsr`) | Apache-2.0, lowRISC | small | yes | built-in countermeasures: sparse FSM encoding, redundant counters | SystemVerilog with package dependencies; earlier report says no usable sv2v / yosys-slang here. **Blocker.** Highest-value target if a converter appears. |
| 8 | Earlier two designs (OTP FSM, 6-gate door lock) | see `real_designs/` | 6 gates, 0 flops for the lock | | | already done; not repeated |

## 3. Designs built and run (all MEASURED)
Setup: copy of `scripts/` in /tmp/work_r20/gs; synthesis through its own `synth.sh` plain flow (per-module map, then flatten, no opt_merge so duplicated copies stay separate) with the apt Yosys 0.33; solver `glitchsat.py check --reduce full`. Attacker input `sig` is constant over the run and must differ from the key. The tool only supports one goal output port and one attacker input, so each design needs a wrapper that tied the other inputs (wrapper sources in `designs/wrappers/`). `legit` = fault-free run with the key reaches the goal.

| Design (wrapper) | Gates / flops | Goal | k | T | Verdict | Min flips | Solve time (incl. minimise) | legit |
|---|---|---|---|---|---|---|---|---|
| sbox_unprot (1 lookup, no check) | 1012 / 16 | y == S(1)=0x7c, input != 1 | 1,2,3 | 4 | ATTACK_FOUND | 1 | 0.9-1.3 s | yes |
| sbox_par (parity of 2nd lookup, shared input reg) | 2040 / 17 | {no alarm, y}==0x17c | 1,2,3 | 4 | ATTACK_FOUND | 1 (flip on shared input flop `sboxw[0]`, cycle 0) | 1.8-2.5 s | yes |
| sbox_par2 (parity, separate input regs) | 2040 / 25 | same | 1,2,3 | 4 | ATTACK_FOUND | 1 | 1.7-2.8 s | yes |
| sbox_dmr (two lookups, 8-bit compare, separate input regs) | 2040 / 32 | same | 1 | 4 | **NO_ATTACK_UP_TO_BOUND** | - | 62 s | yes |
| | | | 2 | 4 | ATTACK_FOUND: flips at cycle 1 on `A.new_sboxw[5]` and a gate in copy B | 2 | 46 s | yes |
| | | | 3 | 4 | no result within the 250 s outer timeout (killed or still running when I wrote this; see section 5) | - | - | |
| crc_plain (CRC-8 compare to 0x81, key 0xA5) | 40 / 9 | ok==1, input != 0xA5 | 0 (par2 run) / 1,2 | 4 | ATTACK_FOUND | 1 | 0.06 s | yes |
| crc_tmr (TMR ok flag, majority vote) | 44 / 11 | same | 1,2 | 4 | ATTACK_FOUND | 1 (a gate in the shared compare, cycle 3) | 0.09-0.12 s; k=0: NO_ATTACK | yes |
| uart (tvalid tied 0, prescale 1) | 368 / 34 | busy==1 and txd==0 (3-bit port == 7) | 0 | 6 | NO_ATTACK_UP_TO_BOUND | - | 0.9 s | no (by construction, no legit frame exists) |
| | | | 1,2 | 6 | ATTACK_FOUND | 1 (control gate, load path) | 1.5 s | no |
| | | | 2 | 30 | ATTACK_FOUND | 1 | 31.8 s solve, 70 s wall | no |
| aes_key_mem control (custom synth) | 32 / 7 | ready==1 | 1,2 | 8 | ATTACK_FOUND | 1 (`key_mem_ctrl_new[0]`) | 0.4-0.5 s | no (init tied 0) |

Notes on what the results mean:
1. **Parity is a weak check on an S-box (MEASURED effect, my reading).** A 1-bit parity over 8 output bits is blind to any even-weight output error. An S-box maps a single wrong input to a many-bit output change, so the solver finds an input where the wrong output has the same parity as the right one. Min stays 1 for both parity variants. A full-width compare (dmr) raises it to 2.
2. **Shared input register defeats duplication in the sbox_par case** (single flip on `x` reaches both copies): MEASURED min 1 at a flop Q.
3. **TMR on the output flag does not help when the three copies share one compare gate** (crc_tmr): MEASURED min 1 in the shared compare logic. That is the same lesson as the earlier OTP FSM (the decision logic is the attack), not a bug in the engine.
4. First sbox attempt used goal S(0)=0x63 with key 0, and the solver reported 0 flips: pipeline registers power up at 0, so `y` legitimately equals S(0) at cycle 1 for any input. This is a wrapper/goal artefact (reset state), found because the tool reported min 0. I re-ran with key 1 / goal 0x7c.
5. Reduction `none` with k=3, T=8 on sbox_par2 still finished (ATTACK_FOUND, 6.8 s solve).

## 4. Flow fit and blockers (MEASURED where stated)
- The project flow cell set (AND, OR, XOR, NOT, MUX, `$_DFF_P_`) covered everything after `dffunmap`. Unsupported cells raise "unsupported cell" in `Netlist` or in `build` (code read, not triggered here except by the next point).
- Async-reset flops: in the project's `synth.sh` plain and opt flows, `aes_key_mem` kept `$_DFF_PN0_` / `$_DFF_PN1_` cells even with reset_n tied high (MEASURED cell counts). The Netlist constructor treats every non-`$_DFF_P_` cell as combinational and reads `con['Y']`; I did not run the solver on that netlist, so whether it errors or silently mis-models is UNVERIFIED. This is a fidelity risk worth a loud check in the engine (assert on any `$_DFF*` other than `$_DFF_P_`).
- The solver supports one attacker input and one goal output; multi-input designs need a wrapper that ties the rest. The attacker input is constant for the whole run, so protocols (UART with changing tvalid) cannot be attacked by input sequencing, only by faults.
- All flops start at 0 (no reset modelling). Designs whose reset value is 1 must be wrapped or have `initial` values (the UART's `txd_reg = 1` initial value was picked up by yosys; `legit=no` there is expected).
- Parametric/generate-heavy Verilog (lfsr) works with Yosys 0.33; SystemVerilog does not (OpenTitan).

## 5. Scaling (MEASURED, single machine, outer `timeout` 200-250 s, z3 timeout 120-200 s)
| Case | Gates | k | T | Result |
|---|---|---|---|---|
| sbox_par2 | 2040 | 0 | 4 | NO_ATTACK in 1.0 s |
| sbox_par2 | 2040 | 2 | 8 | ATTACK_FOUND in 5.1 s |
| sbox_par2 | 2040 | 2 | 16 | ATTACK_FOUND in 10.5 s |
| sbox_par2, `--reduce none` | 2040 | 3 | 8 | ATTACK_FOUND in 6.8 s |
| sbox_dmr | 2040 | 1 | 4 | **UNSAT in 62 s** |
| sbox_dmr | 2040 | 2 | 4 | SAT (min 2) in 46 s |
| sbox_dmr | 2040 | 3 | 4 | not finished inside the 250 s outer timeout |
| uart | 368 | 2 | 30 | SAT in 31.8 s (70 s wall incl. build) |
| uart | 368 | 3 | 60 | not finished inside the 200 s outer timeout |

Reading: finding a 1-flip attack is fast even at about 2000 gates; **proving absence (UNSAT) is the expensive direction**: 62 s for 2040 gates, 8+8 flops of redundancy, T=4, k=1. Cost rises quickly with k (k=3 on dmr did not finish) and with T (uart T=30 already 70 s wall). I did not test beyond that; the T=60/k=3 and dmr k=3 runs were cut by my outer timeouts, so these are "unknown", not verdicts. The earlier flip-everything `--reduce none` mode was not the bottleneck at k=3 here.

## 6. Recommendation (my opinion)
1. Use **sbox_dmr** (and a variant with 3 copies and majority vote, to push minimum to 3) as the scaling and countermeasure benchmark; it has a known-good answer pattern (min = number of copies that must be corrupted consistently), a gate count of about 2000, and runtimes in the tens of seconds.
2. Use **crc_plain vs crc_tmr** as a short, fast example that flag redundancy fails when the decision gate is shared; combine with the earlier OTP FSM.
3. If time allows: obtain a Verilog (not SystemVerilog) lockstep/TMR design, or get an sv2v path so OpenTitan `prim_sparse_fsm_flop` / `prim_count` can be used. Not done here.
4. Add an engine guard against non-`$_DFF_P_` flop cells before using any third-party design (see section 4).

## 7. What I did not do
- No ISCAS'89 file fetched, no Tiny Tapeout redundancy design found, no OpenTitan conversion.
- No Yosys-0.38 (conda) cross-check; all synthesis with apt 0.33. The earlier report found 0.33 and 0.38 can give different netlists (85 vs 83 gates for V2), so numbers here may shift.
- Licences for the two Forencich files are from file headers only.
- Wrapper designs are my own and are not third-party code; their goals are my choice, not a published threat model.

## Files
- `research/c3/r20/designs/*/SOURCE.txt`, third-party files and `wrappers/`
- `research/c3/r20/out/` solver JSON and logs (MEASURED)
