# Real-design attempt: report

Saved by the lead session from the real-design hunter's hand-back (the agent could not write this file itself). Numbers are as reported by that agent and stored in `fsm_results.json` in this folder. Status of the underlying files: present on disk (fsm.v, wrapper.v, glitchsat_adapted.py, fsm5.json, fsm_results.json); untrusted downloads are under `work/`.

## Design used
- Tiny Hardware Authentication Engine (one-time-password unlock FSM), https://github.com/raghul-g1322/tiny_hardware_authentication_tto (a Tiny Tapeout-style hobby design, not a widely deployed one).
- Licence: Apache-2.0 (LICENSE file confirmed by the agent). Plain Verilog.
- Fetched from `main` via raw.githubusercontent.com on 2026-11-19. **No commit hash was pinned** (UNVERIFIED which revision).
- FSM: IDLE -> GENERATE_OTP -> ENTER_OTP -> UNLOCK; `unlock <= 1` only when `otp == user_otp`.
- Other candidates seen but not pursued: hi5253/4-Bit-High-Security-Password-System; a "Verilog Keypad Password Lock" (canonical URL not confirmed). OpenTitan and OpenCores JTAG are SystemVerilog or large; no usable sv2v / yosys-slang wheel on PyPI (only pyslang, a parser).

## Adapter and commands
```
yosys -p "read_verilog fsm.v wrapper.v; hierarchy -top wrapper; flatten; proc; opt -full; memory; opt -full; techmap; opt -full; abc -g AND,OR,XOR,MUX; dffunmap; opt_clean; write_json fsm5.json"
```
- Resulting cells: {$_AND_, $_DFF_P_, $_MUX_, $_NOT_, $_OR_, $_XOR_}.
- `dffunmap` must run after abc, otherwise abc re-introduces $_DFFE_PP_.
- The design's async active-low reset gave an unsupported $_DFF_PN0_ cell; a one-line `wrapper.v` ties reset inactive so `opt -full` removes it.
- The flow was first checked against the toy design's own v0.v (reproduced its known k=0 UNSAT, k=1 SAT).
- **Modelling assumption, not a measurement:** with the reset tied away there is no init attribute, so the adapted solver assumes all flip-flops start at 0 (the design's own reset value).

## Security goal and threat model (as modelled)
- Goal: `unlock == 1` while `user_otp_out != otp` in the same cycle.
- `lfsr_digit` = secret (one free Boolean per bit, constant across the trace); `lfsr_latch`, `user_digit`, `user_latch` = attacker inputs (free per bit per cycle). This is stronger than a real board, where reset and buttons are not fully free.

## Results (MEASURED, z3, single core; limits: T and k tested only as below)
| k | T | verdict | runtime | minimal fault |
|---|---|---|---|---|
| 0 | 4, 6 | UNSAT | 0.02 s | none (model self-consistent) |
| 1 | 4 | SAT | 0.33 s | flip of the `unlock` register bit itself |
| 1 | 6 | SAT | 0.56 s | same |
| 2 | 4, 6 | SAT | ~0.35 s | minimises back to the same single fault |

## Interpretation
The "attack" found is a flip of the decision flip-flop itself. That is a generic single-event-upset on any 1-bit security-decision register. It is not evidence of a design-specific weakness in the comparator, and no fault flipping only the compare tree was found within the tested bounds. **This is not a finding to publish or disclose as a vulnerability.** Any claim about this or any real design would first need a prior-art check and responsible disclosure to the authors.

## Not done
Larger T (8 to 16) or k >= 3; a second or third real design; a SystemVerilog frontend; pinning a commit.
