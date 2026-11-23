# tools/checker: did the fault countermeasures survive the build?

## The problem, in plain words

A chip that checks something important (a boot signature, a debug lock) can be attacked by disturbing it for an
instant: a voltage dip, a clock glitch, a laser or EM pulse. Designers defend against this by writing the check more
than once: two or three copies of the comparison, state values that differ in several bits, a second counter that
must agree with the first, an alarm when the copies disagree. In firmware, the same check is written twice.

The tools that build the chip do not know these repeats are deliberate. A synthesis tool sees three identical
comparisons and keeps one. A placer puts the three copies next to each other, where one laser spot covers all of
them. A C compiler sees the same `if` twice and removes the second. Nothing warns you: the design still works, and
the protection is gone.

This tool checks, for every countermeasure it finds in your source, whether it is still there after each build
step, and how many faults an attacker now needs:

- **SURVIVED**: still there, as written.
- **WEAKENED**: partly lost (two of three copies share a gate, copies sit within one fault spot, ...).
- **REMOVED**: gone (one copy left, the state encoding replaced, the repeated check compiled once).

For anything not SURVIVED it names the evidence (which cells were merged, which source lines have no code), the
tool step that did it, and the smallest change that keeps it.

It reads what you already have: Verilog, Yosys JSON netlists, a DEF from place and route, C source and the ELF.
You do not have to describe your countermeasures; it finds the common ones by itself.

What it is not: faults are modelled (single-cycle bit flips in a netlist, spots on a layout, skipped instructions on
a simulator). Nothing here was measured on a chip. A SURVIVED verdict means the structure is intact, not that the
design is secure.

## Quickstart

```
export GLITCHSAT_ROOT=/path/to/glitchsat                      # the repository (engines are reused from it)
tools/checker/glitchsat check-survival --rtl rtl/v2.v --top v2 --netlist build/v2.json --goal boot_word,0x96,sig,0xC3
echo $?        # 0 all survived, 1 something weakened/removed or margin dropped, 2 incomplete, 3 bad input
```

Needs Python 3.11+, numpy, PyYAML. Optional: Yosys (the checker then elaborates the RTL itself as the "as written"
reference, runs your flow, and can name the breaking command), z3 / PySAT / CaDiCaL / Kissat (faster fault search).

## Example output

`glitchsat check-survival examples/v2_synth.yaml --brief` (MEASURED here; full file: `results/example_v2_synth.txt`):

```
GlitchSAT countermeasure survival: v2    FAIL (exit 1)

  3 copies of cmp8(sig)   [redundant_copies; rtl-scan; rtl/v2.v:9]
    synth-plain  SURVIVED  3 independent copies of 3 intended, no shared cell
    synth-flat   REMOVED   1 independent copy left of 3 intended: 2 net(s) still compute the function but share 4 cell(s)
        why:  The copies were optimised together and now share gates. The script runs `abc -g AND,OR,XOR,MUX` on the
              flattened design, so ABC sees all copies at once and shares their common sub-expressions.
        fix:  RTL: put `(* keep_hierarchy *)` on module `cmp8` and map before flattening ...
              Constraint: mark each copy's cells `keep` / `dont_touch` ... (`setattr -set keep 1 c0/* c1/* c2/*`)
              tools/harden: `glitchsat harden design <design> --goal N --out fixes/` writes a Yosys script with this guard
    placed       WEAKENED  3 independent copies of 3 intended, no shared cell
                   - closest cells of two different copies: c1/_3_ and c2/_3_, centres 1.84 um apart: a spot of radius 0.92 um reaches both
                   - one spot of radius 1.665 um at (20.24, 8.004) reaches a cell of every copy: c0/_2_, c1/_4_, c2/_4_
        fix:  Placement constraint: one region per copy, at least 2.00 um apart edge to edge ...

  register st with 4 codes, distance 4   [sparse_encoding; rtl-scan; rtl/v2.v:8]
    synth-plain  SURVIVED  st: fault-free reachable codes 0x69, 0x96, 0xcc, 0xf0; minimum Hamming distance 4 (intended 4)
    synth-flat   SURVIVED  ...
    placed       SURVIVED  ...

  Security margin per stage (goal: boot_word == 0x96 with a wrong sig):
    synth-plain  3 fault(s) (within 6 cycles, exhaustive (<= 2 flips) + fastsat)
    synth-flat   1 fault(s) (within 6 cycles, exhaustive)
    placed       2 shot(s) of radius 1.0 um (SIMULATED (recorded by tools/shots))
    -> margin dropped from 3 (synth-plain) to 1 (synth-flat); explained by: 3 copies of cmp8(sig).
```

Firmware (`examples/firmware_triple.yaml`, the triple-check ROM of `tools/firmware` at -O2, ordinary C):

```
  check `LAUNDER(r1) != 0` written 3 times in rom_main   [fw_repeated_check; c-scan; rom_triple.c:27]
    firmware     REMOVED   1 of 3 independent checks left in the binary (1 guard line(s) with a branch): the repetition is gone
                   - rom_triple.c:30 `if (LAUNDER(r2) != 0)` -> rom_alarm(): no instruction of the binary belongs to this line
                   - rom_triple.c:33 `if (LAUNDER(r3) != 0)` -> rom_alarm(): no instruction of the binary belongs to this line
        why:  The compiler proved the repeated checks equivalent ... and kept one
        fix:  Compiler barrier: pass each checked value through an empty inline-asm barrier (`LAUNDER(x)`), once per check.
```

With Yosys and `--bisect` (`examples/v2_rtl_to_synth.yaml`) the cause is measured, not inferred:
`why: MEASURED by re-running the script one command at a time: the verdict changes to REMOVED right after command 12, `opt_merge`.`

## What it finds without being told

| countermeasure | found in | how |
|---|---|---|
| duplicated / triplicated logic | Verilog | two or more instances of one module with the same inputs and different outputs |
| | netlist (no RTL needed) | nets that compute the same Boolean function through cell-disjoint cones and feed a flop or output |
| complemented copy | netlist | as above, with one net the inverse of the other |
| sparse state encoding | Verilog / SystemVerilog | a register or `enum` whose code constants are pairwise at Hamming distance >= 2 |
| | netlist | a register whose fault-free reachable values are at distance >= 2 |
| multi-bit boolean | SystemVerilog | `mubi4_t` ... `mubi16_t` signals |
| redundant register / counter | Verilog | register pairs `x` / `x_n`, `x_dup`, `x_shadow`, `x_chk` ... of equal width |
| alarm path | Verilog | output ports named alarm / alert / fault / tamper / err |
| repeated firmware check | C | the same `if (condition)` twice or more in one function, after removing barrier macros and replacing a local by its initialiser |
| firmware flow counter | C | a variable (or update macro) stepped at several places and compared in an `if` |

`glitchsat scan rtl/*.v fw/*.c build/v2.json` lists what is found, with file and line.

When the scan misses something, say it in one line. In Verilog (attributes survive into the Yosys JSON):

```verilog
(* cm_copies = "sigcheck" *) wire ok_a;   (* cm_copies = "sigcheck" *) wire ok_b;   // also valid on instances
(* cm_sparse = "f0,cc,96,69" *) reg [7:0] st;       (* cm_mubi = "6" *) wire [3:0] en;
(* cm_dup = "round" *) reg [3:0] rnd;   (* cm_dup = "round" *) reg [3:0] rnd_copy;   (* cm_alarm *) wire mismatch;
```

or in the YAML (`intent.countermeasures`), or in C with a comment on the `if` line: `/* cm: repeat NAME */`,
`/* cm: ignore */`.

## How a countermeasure is followed from stage to stage

| stage | input | check | margin attached |
|---|---|---|---|
| RTL as written | Verilog (Yosys: `proc; flatten; techmap`, nothing optimised) or the first netlist given | fixes what is tracked: the function the copies compute, the decision flops they feed, the register's codes | bounded fault search |
| synthesis | any Yosys JSON gate netlist (`$_*_` gates, flops with enable / sync reset, Nangate45 cells) | copies: how many nets still compute the function, how many of them share no cell; encoding: codes re-derived by fault-free reachability (exact for small designs, random-simulation sample otherwise) and their distance; registers: both still separate flops; alarm: not constant | minimum flips: exhaustive (`tools/surface`) up to 2, `tools/fastsat` (bundled solver, PySAT, CaDiCaL, Kissat) or z3 beyond; `tools/unbounded` on request |
| placement | DEF + LEF sizes + post-route Verilog (sky130) | smallest spot radius reaching two copies / every copy (including the cells only that copy drives); smallest spot covering the flops in which two codes differ | shots at that radius recorded by `tools/shots`, when it covers the layout |
| firmware | RV32 ELF + line table, C source | per source guard: does a conditional branch or handler call of the binary belong to its lines; how many times the compared function is still evaluated | instruction faults recorded by `tools/firmware`, when it covers the build |

Copies are followed by the function they compute (a simulation signature; the exact truth table when the design has
at most 12 input bits), not by name, so they are found after renaming, re-mapping and flattening. Hierarchy names
are used as extra evidence when they exist ("the outputs of copies c0, c1, c2 are one and the same net").

Verdict for N intended copies: SURVIVED when N cell-disjoint copies remain, WEAKENED when at least two do, REMOVED
when at most one does (including "three nets that all read through one shared cell"). Placement: REMOVED when one
spot of the configured radius reaches every copy, WEAKENED when it reaches two. Encoding: SURVIVED when the
distance is at least the RTL's, REMOVED when it is 1.

Explanations come from the evidence and from the script text when the config gives it (`flow:` or `script:`); with
Yosys installed, `--bisect` re-runs the script one command at a time and reports the first command after which the
verdict changes. Fixes point at `tools/harden` (copy-separation Yosys script, "remove single points" on a netlist,
encoding search), at the pinned layouts of `research/c4/l2_inputs`, and at the barrier / volatile styles of
`tools/firmware`.

## Config

```yaml
name: v2
top: v2
intent:
  rtl: [rtl/v2.v]                 # scanned for intent; with Yosys also elaborated as the reference stage
  # reference: none               # do not make that reference
  # detect: always                # also detect countermeasures in the first netlist
  # countermeasures:              # state what the scan cannot see
  #   - {kind: redundant_copies, id: sigcheck, copies: 2, nets: [ok_a, ok_b]}
  #   - {kind: sparse_encoding, register: st, width: 8, codes: [0xF0, 0xCC, 0x96, 0x69]}
goal: {output: boot_word, value: 0x96, input: sig, key: 0xC3}    # optional: enables the fault search per stage
margin: {k: 3, cycles: 6, min: 3}          # min: fail below this; unbounded: true; backend: dimacs:cadical
policy: {fail_on: weakened}                # weakened (default) | removed | never
stages:                                    # in build order
  - {name: synth, netlist: build/v2.json, script: flow/synth.ys}          # a netlist you built
  - {name: synth2, verilog: [rtl/v2.v], flow: "synth -top v2; flatten; abc -g AND,OR,XOR,MUX"}   # or let Yosys run here
  - {name: placed, netlist: pnr/v2_pnr.v, def: pnr/v2.def, lef: pdk/cells.lef, spot_radius_um: 0.5}
  - {name: firmware, elf: fw/rom.elf, sources: [fw/rom.c], function: rom_main}
```

## In CI

```
glitchsat check-survival survival.yaml --sarif survival.sarif --json survival.json     # exit code gates the job
glitchsat check-survival survival.yaml --baseline main.json      # diff: this build vs a stored report of main
glitchsat check-survival survival.yaml --against origin/main     # diff: baseline computed from that git revision
```

Exit codes: `0` every countermeasure survived and margins meet the target; `1` something WEAKENED / REMOVED, a
margin below `margin.min` or lower than at the reference stage, or (diff mode) a regression; `2` incomplete (a
countermeasure could not be tracked or a stage could not run) with nothing found broken; `3` bad input.

Diff mode reports a regression when a verdict got worse, the number of independent copies fell, a countermeasure
is no longer found, or a margin dropped; `--diff-only` fails for regressions only. `--against` checks the other
revision out in a temporary git worktree and runs the same config there.

SARIF 2.1.0 follows the conventions of `tools/product` (schema URI, fingerprints, result locations at the RTL line
that declares the countermeasure) and is checked with its validator (schema subset and GitHub upload rules). Rules:
`GSS001` removed, `GSS002` weakened, `GSS003` margin below target or dropped, `GSS004` untracked, `GSS005`
regression against the baseline. `examples/ci_github.yml` is a ready job (upload-sarif v4; untested on GitHub).

## Results (details and every count: `results/RESULTS.md`)

"Flagged" = structural verdict WEAKENED or REMOVED. The margin comparison is never counted as a detection, because
the minimum number of faults is the ground truth.

| data set | cases | ground truth | flagged | precision | recall |
|---|---|---|---|---|---|
| V2, 96-flow synthesis grid re-synthesised with Yosys 0.33 | 88 with a fault search | minimum flips = 1 (MEASURED here; equals the RECORDED value in 88 of 88) | 68 | 0.88 (60/68) | 1.00 (60/60) |
| same | 88 | minimum flips below the as-written 3 | 68 | 1.00 (68/68) | 0.81 (68/84) |
| stored V2-family netlists | 22 | minimum flips below the as-written minimum (MEASURED by `tools/surface`) | 2 | 1.00 (2/2) | 0.22 (2/9) |
| placed V2 layouts x spot radii | 331 | fewer shots than at radius 0 (SIMULATED by `tools/shots`) | 301 | 0.95 (286/301) | 1.00 (286/286) |
| firmware repeated checks, 108 builds | 60 | fewer repeats executed than written (MEASURED by `tools/firmware`, simulator) | 1 | 1.00 (1/1) | 1.00 (1/1) |
| OpenTitan AES FSM netlists (lowRISC/synfi) | 2 | no broken case available | 0 | n/a | n/a |

Read them honestly:

- **Merges are caught; every flagged V2 netlist really is below the as-written minimum.** In the grid, all 56
  netlists with REMOVED copies and a fault search need 1 flip, and all 8 with WEAKENED copies need 2. The four 1-flip netlists whose
  copies are intact (`abc -dff`) are caught by the encoding check: a state flop was removed and the code distance
  fell from 4 to 2.
- **Not every loss of margin is a broken countermeasure.** 16 grid netlists and 7 stored ones need fewer flips than
  the RTL as written although every copy is separate and the encoding intact: the next-state logic was mapped so
  that a cheaper attack exists. The structural check does not see these (recall 0.81 and 0.22). The same run still
  fails on them, as "margin dropped ... no tracked countermeasure changed", with the minimum attack it found, but it
  cannot name a fix.
- **The "264 configurations" are only partly reproduced.** The study's netlists are not stored. This run rebuilt the
  96 flows with a Yosys 0.33 built here (gate counts and minima equal the recorded apt-0.33 rows in 88 of 88). The
  two Yosys 0.38 builds (176 of the 264 solved V2 rows) were not available: **untested**.
- **Placement is geometry.** It says one spot reaches the copies, not that the shot succeeds; 15 of 301 flags are
  radii where the shot search of `tools/shots` still needs all its shots. V1 is flagged at most radii although
  placement cannot make it worse (it needs one shot anyway).
- **Firmware has one positive case** (the -O2 merge of the triple check), and the rule counting inlined copies was
  adjusted on these same builds. Treat 1/1 as a fit. Flow-counter verdicts have no ground truth: **untested**.
- **Real netlists:** on SYNFI's two AES control netlists the encoding is found intact (6 state flops per rail; every
  code seen in simulation is an RTL code; distance 3), which agrees with the recorded SAT result for faults on the
  state flops (3 flips). The cheaper attacks recorded there (1 flip single rail, 2 flips three rails) go through
  combinational cells and are a margin result; the checker does **not** flag a 3-to-2 weakening on these netlists
  by structure. No real netlist with a broken encoding was available, so REMOVED is untested on real designs.

MEASURED here as well: `--bisect` with real Yosys names `opt_merge` (V2 copies) and `synth` (FSM re-encoding of a
small test FSM; `synth -nofsm` keeps it); CaDiCaL and Kissat, through `tools/fastsat`'s DIMACS back end, give the
same minimum (3) as the bundled solver on the reference V2 netlist. z3 and PySAT were not installed: untested here.

## Limits

- Text scans of Verilog and C: no parameter evaluation, generate blocks, macros beyond the listed barrier names,
  or cross-module tracing. What they cannot read they do not report; annotate or use the YAML.
- A netlist must be flat and gate-level (run `techmap`/`synth` and `flatten`). Supported libraries: Yosys gates,
  Nangate45 (through `glitchsat_real.nangate`), sky130 placed Verilog (through `tools/shots`). Other libraries need
  their cell functions added.
- Function tracking is exact for designs with at most 12 input bits and functions of inputs only; otherwise it is
  a random-simulation signature (8192 patterns), which can in principle confuse two functions that differ rarely.
  Functions of flop outputs are matched across stages only while the flop names are stable.
- If the only netlist you give is already merged and has no names, and Yosys is not available to elaborate the RTL,
  the copies are UNTRACKED (exit 2), not REMOVED.
- Encoding codes of large designs come from a random simulation sample; rarely reached states may be missing.
  Flops with asynchronous set/reset are not simulated (the verdict then rests on flop count only and says so).
- "Copy computed once, tested N times" in firmware is not detected. The firmware stage reads RV32 ELFs only.
- Margins are those of the reused engines: bounded (k flips, T cycles) unless the unbounded proof is requested,
  one fault model, toy-sized goal (`output == value` with a wrong input). For other designs give no `goal`; the
  structural verdicts still work.
- The placement radius rule (cell centre inside the spot) and the default 0.5 um radius are ASSUMED, as in `tools/shots`.

## Files

| path | what |
|---|---|
| `glitchsat` | launcher: `check-survival`, `scan` |
| `survival/intent_rtl.py`, `intent_fw.py` | intent from Verilog/SystemVerilog and from C; annotations |
| `survival/gnet.py` | one gate-level view for all netlist formats; signatures, function classes, reachability |
| `survival/stage_netlist.py`, `stage_place.py`, `stage_fw.py` | the three kinds of stage; netlist-only detection |
| `survival/margin.py` | calls `tools/surface`, `tools/fastsat`, `scripts/glitchsat.py` (z3), `tools/unbounded` |
| `survival/explain.py`, `bisect.py` | cause and fix; per-command Yosys bisection |
| `survival/pipeline.py`, `report.py`, `cli.py` | config, run, text / Markdown / JSON / SARIF, diff, exit codes |
| `examples/` | configs for V2 (stored netlists; Yosys flow), firmware, OpenTitan AES FSM; CI job |
| `validation/` | the scripts behind every number above; `sh validation/run_all.sh` regenerates `results/` |
| `tests/` | `python3 -m pytest -q tools/checker/tests`: 49 tests (2 need Yosys and are skipped without it), about 40 s |

Reused, not copied: `scripts/glitchsat.py` (netlist reader, z3 engine), `tools/surface` (exhaustive search),
`tools/fastsat`, `tools/unbounded`, `tools/shots` (DEF/LEF/placed-netlist readers, sky130 cell functions, shot results),
`tools/firmware` (RV32 decoder, ELF loader, fault results), `tools/harden` (the fixes), `tools/product` (SARIF
conventions and validator), `glitchsat_real` (Nangate45 adapter). Set `GLITCHSAT_ROOT`, and `GLITCHSAT_EXT` /
`GLITCHSAT_REAL` when those folders are not next to this one.

Landing in the repository: this folder as `tools/checker/` (or `tools/checker/`); the packaged `glitchsat` command
gets the subcommand by forwarding `check-survival` and `scan` to `survival.cli.main`. That forwarding is not done
here (the repository was read-only for this work).
