# GlitchSAT on real OpenTitan security IP (prepared, not yet run)

**Status (2026-11-20): nothing in this folder has been measured.** The scripts, wrappers and checklist are written and statically checked (see `CHECKLIST.md`, section A). Every number below is either a quoted published number (marked SYNFI) or a PREDICTION from reading the code. No result exists until the three commands in the runbook have been run on a cloud VM (Ubuntu 24.04, apt Yosys 0.33).

## In plain words

So far GlitchSAT has been tested on toy designs written for this project. OpenTitan is an open-source silicon root of trust (lowRISC, Apache-2.0). Its hardware uses standard "hardening" building blocks: sparse state encodings, multi-bit booleans, counters kept twice, duplicated random-number generators, multi-rail control FSMs. These blocks are meant to make a single fault useless.

This folder runs the same GlitchSAT question on those real blocks: **what is the smallest number of modelled single-cycle bit flips that makes the block produce a security-relevant wrong output without raising its own alarm?** Some of the same blocks were analysed by SYNFI (Nasahl et al.) with a different tool, a commercial synthesis flow and an older OpenTitan revision, so the answers can be set next to published ones. Same caveats as the rest of the project: a modelled bit flip is not a physical glitch, and every verdict holds only for the stated fault budget k, cycle bound T and netlist.

## Files

| File | Purpose |
|---|---|
| `fetch.sh` | pinned OpenTitan sources (sparse git clone, raw download as fallback) with sha256 checks; pinned sv2v binary with sha256 check |
| `build.sh` | per experiment: sv2v conversion, Yosys synthesis with the repository's plain flow plus three marked steps, netlist check |
| `run.sh` | per experiment: `scripts/glitchsat.py check` for k = 1, 2, 3 (stops at the first attack), optional second solver from `tools/fastsat`, summary, tarball to send |
| `experiments.tsv` | one line per experiment: wrapper, sources, goal value, key, T, predictions |
| `wrappers/*.sv` | one wrapper per experiment (own code): one attacker input `sig`, one goal port `gout`, reset generation |
| `shims/*.sv` | own stand-ins for OpenTitan's generated abstract primitives (`prim_flop`, `prim_buf`, `prim_xor2`, `prim_flop_2sync`) that select the generic implementations |
| `check_netlist.py` | refuses a netlist with cells the engine does not model, a second clock, or an unknown power-up state |
| `summarise.py` | table and CSV from one run |
| `SOURCES.sha256` | sha256 of every OpenTitan file used, at the pinned commit |
| `fetch_osscad.sh` | optional: OSS CAD Suite for the slang cross-check frontend |
| `CHECKLIST.md` | what was checked here, and every assumption with the output that confirms it |

Generated files go to `tools/opentitan/work/` (ignored by git).

## Targets (all OpenTitan, Apache-2.0, tag Earlgrey-PROD-M6, commit a78922f14a8cc20c7ee569f322a04626f2ac6127, 2024-10-17)

| Module (file) | What it protects | Used in | Analysed by SYNFI? |
|---|---|---|---|
| `prim_sparse_fsm_flop` (hw/ip/prim/rtl) | state register of sparse FSMs (macro `PRIM_FLOP_SPARSE_FSM`) | aes_ctr_fsm, aes_cipher_control_fsm | sparse AES FSM states, yes (older revision) |
| `aes_ctr_fsm`, `aes_ctr_fsm_p/_n`, `aes_ctr` (hw/ip/aes/rtl) | AES-CTR counter control: one rail, and the three-rail version with sp2v signals, input checks (`aes_sel_buf_chk`) and cross-rail compare | ctr_fsm_1rail, ctr_3rail | not this module (SYNFI analysed the cipher control FSM) |
| `aes_cipher_control` + `_fsm`, `_fsm_p/_n` | AES cipher control, three rails, sp2v handshakes | ciph_out_valid | yes: the out_valid handshake and the multi-rail FSM (older revision) |
| `prim_count` (+ `prim_count_pkg`) | cross counter: up and down counter, registered sum check `err_o` | count_req, count_regs | yes |
| `prim_double_lfsr`, `prim_lfsr` (+ `prim_cipher_pkg`) | two LFSR copies, combinational compare `err_o` | dlfsr_zero | yes |
| `prim_mubi4_sender`, `prim_mubi4_sync`, `prim_mubi4_dec` (+ `prim_mubi_pkg`) | 4-bit multi-bit boolean (True 4'h6, False 4'h9), synchroniser with stability check, strict decoder | mubi_word, mubi_flag | no (the paper does not mention mubi) |
| support: `prim_util_pkg`, `aes_reg_pkg`, `aes_pkg`, `prim_assert*.sv/.svh`, `prim_flop_macros.sv`, `prim_generic_flop`, `prim_generic_buf`, `prim_generic_xor2`, `prim_generic_flop_2sync`, `prim_sec_anchor_buf` | packages, assertion macros (dummy under `SYNTHESIS`), generic cells | all | |

Licence: every file carries `SPDX-License-Identifier: Apache-2.0`; the repository `LICENSE` is copied as `work/src/OPENTITAN_LICENSE`. The OpenTitan files are not committed here; `fetch.sh` downloads them. Wrappers, shims and scripts in this folder are this project's code (Apache-2.0).

## Experiments

Common rules: the solver's cycle 0 is the first cycle after reset (see "Reset model"). The attacker input `sig` is held constant and must differ from `--key`; where the question has no attacker input, `sig` is a dummy port (the engine needs one) and the experiment asks what faults alone can do. The goal port is compared bit by bit by the solver, outside the netlist, so the comparison itself is not a fault site. k = 1..3, stop at the first k with an attack (the engine minimises the count).

| id | Security question (goal) | Goal port = value | T | Why this T | PREDICTION (not a result) |
|---|---|---|---|---|---|
| mubi_flag | a strict mubi decoder reports True although the sender sends False | decoded flag = 1 | 6 | a value entering the sender needs 4 clock edges to reach the output (sender, 2 sync flops, third stage); T = 6 also lets a value be held 2 cycles, as the stability check requires | 1: the decoder ends in one gate |
| mubi_word | the receiver's 4-bit mubi value reads True (0x6) although the sender sends False (0x9) | `gout` (4 bits) = 0x6 | 6 | same | no attack up to k = 3: each output bit comes from its own gate after the stability mux, so 4 flips; a one-cycle wrong value upstream is caught by the stability check |
| count_req | the counter changes without a request and `err_o` stays low (request comes from a register that never asks) | `{err, cnt, cnt_prev}` = 9'h011 | 5 | flip at cycle c, both counters change at c+1, goal visible at c+2; T = 5 gives c = 0..2 | 1: the single request register feeds both counters (the effect SYNFI reports) |
| count_regs | same goal, all control inputs constant | same | 5 | same | 2: one bit in each counter, or one counter bit plus the error flop |
| dlfsr_zero | the double LFSR outputs the all-zero lock-up state and `err_o` stays low | `{err, state}` = 9'h000 | 4 | the goal can be met in the cycle of the faults; T = 4 gives four states of the sequence to choose from | 2: one bit in each copy (seed 0x01 is one bit from 0) |
| ctr_fsm_1rail | the single-rail CTR FSM writes a counter slice without a request and without alert | `{alert, we}` = 2'b01 | 4 | one state transition is enough (legitimately the goal is reached at cycle 1); T = 4 leaves 2 extra cycles | 1: single-rail request and write-enable decode |
| ctr_3rail | the three-rail CTR control writes the first slice (sp2v HIGH) without a request and without alert | `{alert, ctr_we_o[7]}` = 4'b0011 | 4 | same | 3 if no gate is shared (one write-enable decode per rail; the cross-rail compare does not compare write enables); otherwise unknown |
| ciph_out_valid | the idle AES cipher control signals valid output (sp2v HIGH) without alert | `{alert, out_valid}` = 4'b0011 | 4 | same; legitimately unreachable (cipher never starts) | 3 if no gate is shared (one out_valid decode per rail); otherwise unknown. Largest netlist; may time out |

Why the two-cycle goal in count_*: `err_o` of prim_count is registered, so it reports a cycle later. A goal "wrong value now, err low now" would be met by one flip in every design (the error simply has not arrived yet). Requiring the changed value on two consecutive cycles means the check of the first cycle is due when the goal is judged; a wrapper register alone cannot fake it more cheaply than the real attack (the current counter output is part of the goal).

## What SYNFI reported (SOURCED)

Source: P. Nasahl, M. Osorio, P. Vogel, M. Schaffner, T. Trippel, D. Rizzo, S. Mangard, "SYNFI: Pre-Silicon Fault Analysis of an Open-Source Secure Element", arXiv:2205.04775 v2 (2022-07-07), read on 2026-11-20 in the arXiv HTML rendering (two separate reads gave the same numbers). The arXiv page names no venue; notes elsewhere in this repository cite a TCHES 2022 page that was not re-read here. "Effective" = share of the enumerated fault combinations that reached the target; FD = output manipulated without the countermeasure raising its alert; FS = output driven to a specific state without triggering the countermeasures.

| Target (SYNFI) | Setting | Simultaneous faults | Effective | Total injected | Time | Circuit |
|---|---|---|---|---|---|---|
| prim_count (Table 8) | FD | 2 | 10.82 % | 1,552 | 37.46 s | 29.75 GE |
| prim_double_lfsr (Table 8) | FD | 2 | 0.05 % | 7,827 | 74.44 s | 116.75 GE |
| prim_double_lfsr (Table 8) | FD | 3 | 0.09 % | 340,692 | 2,114.69 s | 116.75 GE |
| unprotected AES handshake signal (Table 2) | FS | 1 | 83.83 % | 31 | 4.49 s | 32 GE |
| protected AES handshake signal (Table 2) | FS | 3 | 15.32 % | 8,436 | 270.68 s | 38 GE |
| AES multi-rail FSM, tight (Table 3) | | 1 / 2 / 3 | 0 % / 0 % / 0.02 % | 573 / 170,982 / 35,222,293 | 266.87 s / 1.01 h / 38.27 h | 355.75 GE |
| AES encoded FSM states (Table 4) | FS | 3 | 15 % | 29 | 16.09 s | 90.5 GE |

From the text: with one fault, SYNFI found two effective faults in prim_count, both on the counter increment or clear signal that both counter instances use (the paper notes this is documented behaviour). For prim_double_lfsr with two faults it reports 4 effective faults that either suppress the error signal or change the LFSR value in both copies. For the protected handshake it found no effective fault with one or two faults. Section 4.1.3: re-synthesising the sparse AES FSM with Yosys FSM optimisation meant "2 instead of 3 simultaneous faults" skip a state. Section 4.2.2: synthesis merged four duplicated registers of the flash erase signal into two (Hamming distance 4 to 2) until `set_dont_touch` kept all four. Setup: OpenTitan modules synthesised with Synopsys DC and a proprietary cell library (Ibex: Yosys with Nangate45); no OpenTitan commit is given; the LFSR and counter widths are not stated; Table 8 has no 1-fault row for prim_double_lfsr.

**How far the comparison goes.** GlitchSAT reports the smallest k (a search); SYNFI reports the share of enumerated fault sets that work at a given k. The comparable quantity is "the smallest k at which any effective fault exists": from SYNFI, 1 for prim_count, 3 for the protected handshake (none at 1 or 2), and at most 2 for prim_double_lfsr (no 1-fault row given). Differences that can change the answer: OpenTitan revision (2022 vs 2024 tag), synthesis (DC with a commercial library vs Yosys 0.33 with AND/OR/XOR/MUX/NOT), fault model (SYNFI replaces a gate's function, e.g. NAND to AND/OR; here an output bit flips for one cycle, gates and flop outputs, T cycles), parameters (unknown there, chosen here), and the cut-out (SYNFI used subcircuits around the target; here the whole module plus a small wrapper). A matching number would be agreement under different models, not a replication.

## Pipeline

```
fetch.sh   OpenTitan @ Earlgrey-PROD-M6 (sparse clone)  -> work/src/*.sv   (sha256 checked)
           sv2v v0.0.13 sv2v-Linux.zip                   -> work/tools/     (sha256 checked)
build.sh   per experiment:
           sv2v --define=SYNTHESIS --incdir=work/src --top=<wrapper> pkgs + modules + generic prims + shims + wrapper
           yosys: read_verilog; hierarchy -check; proc; memory(+); async2sync(+); techmap; abc -g AND,OR,XOR,MUX;
                  flatten; techmap; sim -clock clk -n 1 -w(+); write_json
           check_netlist.py (cell set, one clock, init values)
run.sh     python3 scripts/glitchsat.py check <netlist.json> --top <wrapper> --k k --cycles T
           --goal-out gout --goal-value V --attack-input sig --key KEY --reduce full
           [optional: the same arguments to tools/fastsat/fastsat.py]
```

**Converter choice.** sv2v (BSD-3-Clause) release v0.0.13 with the apt Yosys 0.33. Reasons: (1) OpenTitan's own Yosys flow converts with sv2v and `--define=SYNTHESIS` (`hw/ip/aes/pre_syn/syn_yosys.sh` at the pinned tag); (2) one static binary with a published asset (`sv2v-Linux.zip`, built on ubuntu-22.04 by the release workflow), no compiler needed; (3) it keeps the Yosys version of all earlier results in this repository (R20 noted that Yosys 0.33 and 0.38 can give different netlists). Not chosen as the main path: yosys-slang, now named sv-elab (ISC licence). Its README (read 2026-11-20) says it is part of Yosys from v0.67, that the plugin build supports Yosys 0.59 to 0.66, and that a prebuilt plugin ships with OSS CAD Suite. The apt Yosys 0.33 is too old for it. OSS CAD Suite is offered as an optional cross-check (`fetch_osscad.sh`, pinned `oss-cad-suite-linux-x64-20261119.tgz`, about 754 MB; then `OT_FRONTEND=slang bash build.sh`). It brings a different Yosys version, so its netlists are a second data point, not a replacement.

**Shims.** In an OpenTitan build, `prim_flop`, `prim_buf`, `prim_xor2` and `prim_flop_2sync` are generated by the primgen tool. The shims here select the generic implementations, as OpenTitan's AES Yosys flow does with `sed`.

**Reset model.** OpenTitan flops have asynchronous active-low resets, which the engine does not model (R20 section 4). Each wrapper drives `rst_ni` from a register `rst_q` that starts at 0 and becomes 1 after one clock. `async2sync` turns every async-reset flop into a plain flop with reset muxes. `sim -clock clk -n 1 -w` then simulates that one reset cycle and stores the resulting state as each flop's initial value, so the solver starts from the real post-reset state (e.g. CTR_IDLE = 01110, secondary counter 1111) and not from all zeros. A flip of `rst_q` re-applies reset, which only returns the design to that state. Fallback if `sim -w` fails: `OT_NO_SIM=1` (cycle 0 is then the reset cycle, run.sh adds one cycle, and a flip of `rst_q` in cycle 0 would expose the all-zero pre-reset state, which is an artefact).

**Model differences to keep in mind.** (1) Buffers (`prim_buf`, `prim_sec_anchor_buf`) become wires; real OpenTitan synthesis keeps them as cells. (2) The reset muxes from `async2sync` are extra fault sites with the same effect as existing ones (CHECKLIST B5). (3) Tied-off inputs are not constant-folded, so the module's logic stays as it would be when those inputs come from logic. (4) The repository's plain flow has no FSM re-encoding; SYNFI's 3-to-2 result came from Yosys FSM optimisation, which is not run here (a possible next step: the repository's `opt` flow).

## Expected runtime

Unknown until measured. The netlist sizes are not known yet (build.sh prints them). For orientation only, earlier measurements in this repository on other designs (R20): finding an attack took under 3 s on about 2,000 gates, while proving that no 1-flip attack exists took 62 s on 2,040 gates at T = 4, and k = 3 did not finish in 250 s. The small experiments here (mubi, count, dlfsr, ctr_fsm_1rail) are expected to be much smaller than that; ctr_3rail and ciph_out_valid may be larger. run.sh limits each solver run to 900 s (`OT_RUN_TIMEOUT_S`) and reports a timeout as UNKNOWN, never as "no attack". Worst case with every run hitting the limit: 8 experiments x 3 values of k x 15 min = 6 h.

## Runbook (Ubuntu 24.04 cloud VM)

One-time setup on a fresh Ubuntu 24.04 cloud VM (its apt Yosys is 0.33, the version of the earlier results), from the repository root:

```
sudo apt install -y git curl unzip yosys python3-venv
python3 -m venv .venv && . .venv/bin/activate && pip install -r ci/requirements-ci.txt
```

Then run these 3 commands and send the output (the terminal text, or the file named on the last line):

```
bash tools/opentitan/fetch.sh
bash tools/opentitan/build.sh
bash tools/opentitan/run.sh
```

`run.sh` ends with `Send this file: .../ext/opentitan/work/send_<date>.tar.gz`. It contains the logs, JSON results, summary and build logs. If build.sh reports an experiment as NOT BUILT, run.sh skips it and the others still run; send the output anyway, because the error text is what is needed. Single experiments: `bash tools/opentitan/run.sh count_req` (same for build.sh).

## Not prepared (yet)

- SYNFI's exact cut-outs: the AES round counter (Table 1), the life-cycle controller (RMA token checks, lock counter), Ibex PC and lockstep. The paper's netlists came from a commercial flow and are not published with it, so the cut-outs cannot be copied; they could be rebuilt from the RTL (e.g. `rnd_ctr` inside `aes_cipher_control_fsm`).
- A dual-rail decoder (`prim_diff_decode`): its natural goal (suppress an incoming alert) needs a time-dependent goal that the engine's "value at any cycle" goal does not express cleanly.
- The repository's `opt` flow (full `synth`, FSM re-encoding) as a sensitivity check against SYNFI's Section 4.1.3 finding.
