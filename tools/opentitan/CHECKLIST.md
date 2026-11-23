# tools/opentitan: assumptions and how the cloud VM run confirms each one

Status on 2026-11-20: **nothing here has been run end to end.** The machine these files were written on has no Yosys, no z3 and was not allowed to execute the downloaded sv2v binary. What was checked there is listed in section A. Everything in section B is an assumption until the cloud VM run (Ubuntu 24.04, apt Yosys 0.33) confirms it. Each item says what output to look at.

## A. Checked while writing (static only)

| # | Check | How | Result |
|---|---|---|---|
| A1 | Shell syntax of fetch.sh, build.sh, run.sh, fetch_osscad.sh | `bash -n` | no errors |
| A2 | Python syntax of check_netlist.py, summarise.py | `python3 -m py_compile` | no errors |
| A3 | build.sh and run.sh control flow (TSV parsing, per-experiment directories, Yosys script text, failure handling, skip of failed builds, summary, tarball) | ran them with stub `sv2v`, stub `yosys` and a stub engine that write fixed files | worked as intended after one fix (run.sh now skips experiments whose netlist check failed) |
| A4 | check_netlist.py rejects an async-reset flop cell, a missing init, a wrong `rst_q` init | hand-written netlists | each rejected with exit 3 |
| A5 | Wrapper port names equal the target module port names | script comparing `.port(` names in each wrapper with the `input`/`output` names of aes_cipher_control, aes_ctr, aes_ctr_fsm, prim_count, prim_double_lfsr at the pinned commit; mubi modules compared by reading | identical |
| A6 | Pinned tag and commit | `git ls-remote` and a sparse clone: tag Earlgrey-PROD-M6 is an annotated tag pointing at commit a78922f14a8cc20c7ee569f322a04626f2ac6127 (commit date 2024-10-17) | as pinned in fetch.sh |
| A7 | sha256 of the 34 OpenTitan files | computed from that checkout | in SOURCES.sha256 |
| A8 | sv2v release asset | release workflow at tag v0.0.13 zips `sv2v-Linux/` (built on ubuntu-22.04); the zip was downloaded and listed (contains `sv2v-Linux/sv2v`, dated 2025-03-20) and its sha256 recorded. **The binary was not executed.** | in fetch.sh |
| A9 | OSS CAD Suite asset name | 1-byte range request: `oss-cad-suite-linux-x64-20261119.tgz` under tag 2026-11-19 exists, 754,243,903 bytes. Not downloaded. | in fetch_osscad.sh |
| A10 | Wrapper Verilog | read line by line; not parsed by any tool | see B3 |

## B. Assumptions the cloud VM run must confirm

| # | Assumption | Why it matters | Where the run shows it |
|---|---|---|---|
| B1 | The sv2v v0.0.13 Linux binary (built on Ubuntu 22.04) runs on Ubuntu 24.04. | No converter, no netlists. | fetch.sh prints `sv2v: v0.0.13`. If it fails: build from source or use `OT_FRONTEND=slang`. |
| B2 | sv2v converts every source set with `--define=SYNTHESIS` (packages, `prim_sparse_fsm_flop` type parameter, enum casts, `ASSERT_STATIC_*` macros). OpenTitan's own AES Yosys flow does this, but per file and with `sed` fixes; here it is one call per experiment. | Conversion errors stop that experiment. | build.sh prints `[id] sv2v failed` with the log tail, or a `netlist OK` line. |
| B3 | The wrappers are valid SystemVerilog (package-qualified enum constants, packed enum arrays `sp2v_e [7:0]`, `mubi4_t [0:0]`). | Same. | sv2v log; then Yosys `hierarchy -check`. |
| B4 | Yosys 0.33 reads the sv2v output and runs `async2sync` and `sim -clock clk -n 1 -w` as used. | `async2sync` removes async-reset flops (R20 section 4: they survive the plain flow); `sim -w` writes the post-reset state as init values. | `netlist OK ... reset_mode=sim`; check_netlist fails loudly if any `$_DFF_PN*` cell survives, any flop has no 0/1 init, or `rst_q` does not start at 1. Fallback: `OT_NO_SIM=1` (run.sh then adds one cycle so cycle 0 is the reset cycle). |
| B5 | After `async2sync`, each async-reset flop becomes a plain flop plus a mux on D and a mux on Q (reset value when `rst_ni` is low). The two muxes are extra fault sites that a real reset flop does not have; flipping the Q-side mux has the same effect as flipping the flop output, and the D-side mux the same as flipping the gate that drives D. | A wrong mapping would change attack costs. | Compare `flops` with the expected register count (stat.txt per experiment); read the fault list of any attack: a fault on a mux whose select is `rst_q` should appear only where a flop-output fault would do the same. If not, report it. |
| B6 | The simulated reset gives the documented reset values (e.g. aes_ctr_fsm state CTR_IDLE = 01110; prim_count secondary counter = 1111; LFSR copies = 0x01; mubi flops = 1001). | Wrong start state = wrong experiment. | `legit_reaches_goal` = True for ctr_fsm_1rail and ctr_3rail (the legitimate request reaches the goal without faults; impossible if the FSM started in a wrong state). For the others, `flops starting at 1` in the `netlist OK` line (each count includes `rst_q`): count_req and count_regs 5 (secondary counter 1111 + rst_q); dlfsr_zero 3 (bit 0 of each copy + rst_q); mubi_word and mubi_flag 9 (four 4-bit stages at 1001 + rst_q). A different count needs a look before trusting that experiment. |
| B7 | Per-module `abc` before flatten keeps the copies independent (two LFSRs, two counters, three FSM rails). Copies of one module are mapped once and instantiated twice; nothing merges them after flatten (no `opt_merge`). | This is the repository's plain-flow rule (scripts/synth.sh header). | gate counts: the dlfsr and count netlists should contain two copies of the per-copy logic. |
| B8 | `prim_buf` / `prim_sec_anchor_buf` become plain wires (abc removes the double inverter inside prim_generic_buf). | Buffers are no fault sites here; in real OpenTitan synthesis they are kept as cells. | no `$_NOT_` pairs from buffers in the netlist; stated as a model difference in the README. |
| B9 | Constant tie-offs in the wrappers stay constants (no folding after flatten), so the target module's logic is kept as in a context where those inputs come from logic. | Folding would remove gates and fault sites. | build flow has no `opt_expr` after flatten; netlist sizes are reported. |
| B10 | The goal values and keys in experiments.tsv match the wrapper ports. | A wrong value would answer a different question. | engine refuses values that do not fit the port; `legit_reaches_goal` True for the two ctr experiments. The other experiments have no legitimate way to reach the goal by design, so False is expected there (as for the UART in R20). |
| B11 | T values (experiments.tsv) are long enough for the reasoning in the README. | Too short = an attack is missed. | optional: rerun one experiment with a longer T, e.g. edit the TSV cycles column for count_regs to 8 and run `bash tools/opentitan/run.sh count_regs`. |
| B12 | z3 finishes within 900 s per run for these netlist sizes. | Timeouts are reported as UNKNOWN, not as results. | per-run seconds in run.log; increase `OT_RUN_TIMEOUT_S` if needed. |
| B13 | The optional fast solver (tools/fastsat) takes the same arguments as `scripts/glitchsat.py check`. | Otherwise it is skipped. | run.sh prints `fastsat: ... skipped` or its verdict per run; summarise.py marks `DISAGREES`. |
| B14 | The slang frontend (OSS CAD Suite) loads with `plugin -i slang` and accepts `read_slang -D SYNTHESIS -I dir --top TOP files...`. | Only needed for the optional cross-check. | fetch_osscad.sh prints whether the plugin loads; build.sh prints the Yosys error otherwise. |
