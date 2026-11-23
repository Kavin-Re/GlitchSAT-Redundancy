# Labs: OpenTitan hardening primitives

> The build folders `work/` and `labs/work/` (netlists, logs and per-run records, about 28 MB) are not part of the repository: they hold machine-specific paths. `scripts/build.py` and `scripts/run.py` rebuild them; the summaries in `results/` are kept.

**Status: EXPERIMENTAL (GlitchSAT Labs).** Experiments in progress: try them, don't rely on them.
Every result below is labelled MEASURED, SIMULATED or UNTESTED (meaning in `tools/labs/README.md`).

## What it tries to answer

OpenTitan is an open-source security chip. Its designers built small "hardening primitives" that make
fault attacks (flipping bits with a glitch or a laser) harder: a *multi-bit boolean* uses 4 wires for one yes/no
value, a *redundant counter* keeps an up-counting and a down-counting copy that must agree. This module asks:
**after an open-source synthesis tool has turned the real OpenTitan source code into gates, how many bit flips
does it take to break each primitive, and are the redundant parts still there?**

## Run it

```
. ./env.sh        # your own tool setup: puts Yosys, CaDiCaL and Kissat on PATH
python3 tools/real/opentitan_prims/labs/run_labs.py              # under 10 s; writes labs/results/labs_result.json
python3 -m pytest -q tools/real/opentitan_prims/tests            # smoke test
```

The Labs example builds into `labs/work/` (environment variable `OT_WORK`), never over the recorded runs in `work/`.

## WHAT WORKS

- `scripts/build.py`: elaborates the pinned OpenTitan sources (`src/`, tag Earlgrey-PROD-M6, commit a78922f,
  hashes in `SOURCES.sha256`) with **Yosys 0.71 `read_slang`**, maps them to generic gates with Yosys 0.33 (the
  version of the earlier GlitchSAT results), and builds a cross-check netlist with Yosys 0.71 alone. `check_netlist.py`
  checks every netlist before analysis. Wrappers in `wrappers/`, primgen stand-ins in `shims/`.
- `scripts/run.py --only scale,legit`: the smallest number of bit flips that reaches the attack goal (CaDiCaL),
  plus a sanity run with 0 flips.
- `scripts/name_flops.py` + `tools/checker` (`glitchsat check-survival`): structural check that the redundant copies
  are still separate registers or nets after synthesis.
- `labs/run_labs.py`: the Labs example on 3 primitives, comparing every answer with the prediction written before
  the first run (`experiments.tsv`) and with the recorded run in `work/`.
- Fixed while preparing Labs: `build.py` required an instance `u_dut` even for the plain flow, so the two
  multi-bit-boolean experiments could no longer be built; it is now required only by the flows that use it.

## Results of the example (all EXPERIMENTAL)

| primitive | gates / flip-flops (MEASURED) | smallest attack (SIMULATED) | prediction | countermeasure survived synthesis (MEASURED) |
|---|---|---|---|---|
| `mubi_flag`: prim_mubi4 sender, sync, decoder | 65 / 17 | **1 bit flip** (the decoder ends in one gate) | 1 | - |
| `mubi_word`: prim_mubi4 sender, sync | 60 / 17 | 4 bit flips | none up to 3 | yes, all 4 bits keep their own driver; 1 RTL item could not be tracked (UNTESTED) |
| `count_regs`: prim_count up and down copies | 269 / 14 | 2 bit flips | 2 | yes, both counter registers and the error alarm |

- SIMULATED: the 4-bit multi-bit boolean itself needs 4 flips, but once it is decoded to one flag, one flip
  after the decoder is enough. The protection is only as strong as the place where it is turned back into one wire.
- All three answers equal the recorded runs in `work/` (reproduced).
- Yosys 0.71 alone gives similar sizes (MEASURED: 64 vs 65 and 60 vs 60 gates for the multi-bit booleans, 285 vs 269 for prim_count).

## WHAT DOESN'T (yet)

- UNTESTED in Labs: the other 16 experiments of `experiments.tsv` (double LFSR, AES counter and cipher FSMs with
  and without FSM optimisation). They have recorded runs in `work/` and `survival/`, but they are not re-run or
  reviewed for Labs.
- UNTESTED: equivalence of the netlists with the RTL. `results/equivalence.json` is a recorded earlier run; in it,
  several negative controls (a deliberately broken netlist) were also reported "proved", so that check is not yet
  able to tell a broken netlist apart and must not be relied on.
- UNTESTED: OpenTitan's own synthesis flow, real standard-cell libraries, placement.
- Each primitive is analysed alone, inside a small wrapper.

## HOW FAR TO TRUST RESULTS

- Gate and flip-flop counts and survival verdicts come from running real tools on the real sources (MEASURED).
- "Smallest attack" is exact for the model (single-cycle bit flips on gate and flip-flop outputs, at most `kmax`
  flips within `cycles` clock cycles, see `experiments.tsv`), and says nothing outside those bounds (SIMULATED).
- Generic gates from Yosys are not the cells of a real chip; a real flow can merge or split logic differently.

## Files

`src/` pinned OpenTitan files (Apache-2.0) · `wrappers/` `shims/` own SystemVerilog · `scripts/` build, run, checks ·
`experiments.tsv` all experiments with predictions · `survival/` checker configs and recorded results ·
`work/` recorded runs · `labs/` Labs runner, results (`labs-result/1`) and builds · `tests/test_labs_smoke.py`.
