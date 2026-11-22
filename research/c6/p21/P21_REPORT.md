# P21 report: Solver Replay Theatre

License: UNDECIDED. Working title TBD. Nothing established as new.

## Files written
- `scripts/export_witness.py`: runs the solver, replays the witnesses, parses VCD, writes the data, inlines it into the page.
- `docs/explainers/witness.json`: the data (7 frames, about 39 kB). Re-running the export gave a byte-identical file (checked once, same machine).
- `docs/explainers/theatre.html`: the page (one file, offline, no external resources). `?kiosk=1` loops.
- `docs/explainers/dev/check_theatre.py`: the checker. `python3 docs/explainers/dev/check_theatre.py --browser` -> 149 passed, 0 failed (work copy, 2026-11-20).
- `docs/explainers/dev/THEATRE_NOTES.md`: 3-minute stage script.
- `research/c6/p21/shots/step{1..5}_{390,1366}.png`: screenshots written by the checker (`--shots`).

## What was replayed (all on the STORED netlists, 6 ticks, key 0xC3)
| frame | solver command (prefix `python3 scripts/glitchsat.py check`) | solver verdict (MEASURED) | replay in gate-level simulation (SIMULATED) |
|---|---|---|---|
| v1_faultfree | `reference/spike_netlists/v1.json --top v1 --k 0 --cycles 6` | NO_ATTACK_UP_TO_BOUND | key 0xC3: opens at tick 2; wrong key 0xC7: not opened in 6 ticks |
| v1_k1 | `... v1.json --top v1 --k 1 --cycles 6` | ATTACK_FOUND, 1 flip: `ok` at tick 1, input 0xC7 | faulted: boot word 0x96 at tick 2; fault-free: not opened |
| v2_faultfree | `... v2.json --top v2 --k 0 --cycles 6` | NO_ATTACK_UP_TO_BOUND | key 0xC3: opens at tick 2; wrong key 0xD3: not opened |
| v2_k1, v2_k2 | `... v2.json --top v2 --k 1` / `--k 2` | NO_ATTACK_UP_TO_BOUND; 456 sites total, 353 modelled (solver output fields) | none (nothing to replay) |
| v2_k3 | `... v2.json --top v2 --k 3 --cycles 6` | ATTACK_FOUND, 3 flips: `c2.m`, `word[0]`, `c1.m`, all tick 1, input 0xD3 | faulted: boot word 0x96 at tick 2; fault-free: not opened |
| v2_flag_k1 | `... v2.json --top v2 --k 1 --cycles 6 --goal-out boot_ok --goal-value 1` | ATTACK_FOUND, 1 flip: `boot_ok` at tick 3, input 0x43 | faulted: boot_ok = 1 at tick 3 only, boot word stays 0x69; fault-free: flag stays 0 |

Netlist sha256: v1 `84730fa7b5e3dbefd41ae57efd8d6bc18ca2bf02b03c231a90615c827ec7b5cc`, v2 `289355dc483b9e6a74fea40b2d33a782350a2fd626468e97dd1c10b1cfe781ec`.
Tools: z3 5.4.1, Icarus Verilog 12.0; netlists were made by Yosys 0.33 (creator field in the JSON).

Replay recipe: the project's own `scripts/replay.py` (the code behind `make replay`), imported and called by the export
script with a temporary output directory. It re-emits the netlist as Verilog with an XOR on each witness net at its
tick, and runs iverilog/vvp with faults on and off. Nothing under `results/` or `tb/` is written.

## Measured versus hand-drawn
- MEASURED (solver output): verdicts, minimum flip counts, net names, ticks, attacker input, site counts 456 / 353.
- SIMULATED (gate-level replay, parsed VCD): every waveform strip (clk, sig, the flipped nets, boot_ok, boot_word), the
  "opens at tick N" lines, the tick chips. The red "flip" block is computed in the page from two VCD signals: the net as
  its gate drives it (`r<id>`) and the net after the flip (`n<id>`).
- Read from the netlist structure (not simulated): which boot-word bits each witness net can reach; used only to choose
  which wire of the diagram to colour.
- HAND-DRAWN: the two small schematics. They are labelled "simplified diagram" on the page. Their layout, the box
  names ("check 0", "both?") and the bit groups (from `rtl/v2.v` line 10) are not derived from the netlist.
- Arithmetic in the page: "456 single places and 103,740 pairs" = n and n(n-1)/2 from the solver's site count
  (the same pair count appears in `validation/VALIDATION.md`; that enumeration was not re-run here).
- Built by the export script, not by the solver: the honest-key stimulus (sig = 0xC3, no faults). `replay.py` only
  accepts ATTACK_FOUND-shaped files, so the stimulus file carries that field; it is marked as a stimulus in the file.

## What the checker establishes
A: provenance on every frame; agreement with `results/reproduce_summary.json` (verdict and minimum faults for v1 k=0,1
and v2 k=0..3, stored-netlist rows; V1 net and tick identical); agreement with a fresh solver run; each replay repeated
from witness.json in two ways (iverilog VCD compared change by change, and a pure-Python netlist simulator written in
the checker): faulted runs reach the goal, fault-free runs do not, honest key opens; inlined data equals witness.json;
no external resources; required and banned wording. B (headless Chrome, 390 and 1366 px): no console errors, no
horizontal scroll, text >= 12 px, controls >= 44 px, keyboard operation, reduced motion, kiosk loop, on-screen digits.

## Limits and things that differ from the plan
- The V2 3-flip witness differs from the one stored in `results/reproduce_summary.json` (that row lists
  `$flatten\c0...new_n16_`, `c1...new_n15_`, `c2...new_n15_`; today's run returns `c2.m`, `word[0]`, `c1.m`). Same
  count (3), same tick (1), one net per copy in both. The checker compares verdict and count, not net names, for V2.
- The accept-flag result has no row in `reproduce_summary.json`; it is checked against the fresh solver run and
  against `research/c2/b2_scope/matrix.jsonl` (row v2, spike, boot_ok: 1).
- The enhancement plan also lists v0 and the apt-built V2 netlist; the work plan asked for V1 and V2 stored netlists
  only, so those are not in the theatre. The 2-flip fresh-build result is quoted in the caveat panel, not replayed.
- The accept flag of V1 was not run separately; the page says "not measured here".
- The product CLI (`faultbound-wt`) was not used; no venv was created.
- Not done: adding the checker to `make test` (Makefile is the integration step's file). Suggested line:
  `$(PY) docs/explainers/dev/check_theatre.py` (about 10 s; `--browser` adds about 25 s and needs playwright + Chrome).
- Not done: a link from `explainer.html` or the dashboard (not my files).
- No human has watched the page; the 3-minute script is untimed.
- Bounded results only: at most 3 flips, 6 ticks, one stored netlist per design, modelled single-tick flips. No hardware.
