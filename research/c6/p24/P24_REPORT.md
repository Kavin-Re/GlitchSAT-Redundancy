# P24 report: "Same blueprint, many builders" reveal wall

License: UNDECIDED. Working title TBD.
Work done in a copy (`/tmp/work_p24`), then only the files listed below were copied into the tree. No existing file was edited.

## Files written
| file | what |
|---|---|
| `scripts/export_e2_wall.py` | reads `research/c2/e2_variance/raw/matrix.csv` (288 V2 rows) and `research/c6/p01/sweep_rows.csv`; writes `docs/explainers/e2_wall.json` and the copy embedded in `wall.html`. Deterministic, no timestamp. |
| `docs/explainers/e2_wall.json` | 288 tiles (264 solved + 24 without verdict), 152 netlists, cause table, V2/V2e block. Option fields, gates, flops, min flips, canonical sha (16 hex), csv line. |
| `docs/explainers/wall.html` | the standalone page (about 161 kB with data; no network, no libraries). |
| `docs/explainers/dev/check_wall.py` | 42 checks: recount from the source with its own code, JSON against source row by row, page against JSON, wording and caveats. |
| `docs/explainers/dev/WALL_NOTES.md` | 90-second presenter script. |
| `research/c6/p24/shoot.py`, `shots/` | headless-Chrome test and 28 screenshots; `shots/shoot_log.txt` is its output. |

## Numbers (MEASURED: row counts of the source files; recomputed here, not copied)
Command: `python3 scripts/export_e2_wall.py && python3 docs/explainers/dev/check_wall.py` (ALL PASS, 0 failed).
- 288 V2 rows, 264 SOLVED, 24 ENGINE_UNSUPPORTED (no verdict).
- Per setting, min flips 1 / 2 / 3 = 180 / 60 / 24. Matches E2_REPORT section 3 and NUMBERS `E2.v2.min`.
- 152 distinct `sha256_canon`; no netlist has two verdicts; per netlist 94 / 38 / 20. Matches DA3 A2 and NUMBERS `DA3.E2.distinct`.
- `opt_merge` on: 120 / 12 / 0 (so 120 of the 180 one-flip settings). Flatten before ABC, no merge: 48 / 12 / 6. Neither: 12 / 36 / 18, and all 12 one-flip settings there use `abc -dff`.
- Per netlist the cause table is 69 / 10 / 0, 17 / 8 / 6, 8 / 20 / 14, where a netlist counts as "`opt_merge` on" if any setting that builds it has it on (6 netlists are built both with and without it). DA3 quotes 65 / 8 for opt_merge netlists using a different (first-row) attribution; the two are not in conflict, but they are different counts.
- Second wall (P01 `sweep_rows.csv`, 8 project flows x 2 Yosys versions): V2 2 1 1 2 2 2 2 2 and 3 1 1 2 3 2 3 2; V2e 3 1 1 3 3 3 3 3 on both. 9 constants in the file.
All verdicts are bounded: goal `boot_word == 0x96`, 6 cycles, at most 3 modelled single-cycle flips, one toy design. I ran no solver; I only counted rows.

## What the page does
- One tile per result, in two boxes (`opt_merge` off / on), each with four blocks (flow x order). Tile = minimum flips, coded three ways: colour, shape (square 3, cut corner 2, circle 1) and the digit.
- Toggle "distinct netlists (152)" (default) / "every setting (264)". The 264 view is a 6 x 6 grid per block (ABC script x build and keep) and shows the 24 no-verdict settings as dashed tiles.
- Headline as briefed, with computed counts in the line under it. Every number in the text is a `data-n` span that the checker compares with the data, so the static text is right even without JavaScript.
- Tooltip on hover, focus or tap: option combination, gates and flops, netlist sha (16 hex), min flips, source file and line. In the 152 view it lists every setting that built the netlist.
- Stage reveal, four steps on the Space key (also PageDown/PageUp, step buttons, Esc to leave): the blueprint, the builders, the verdicts, the cause. The cause step outlines the `opt_merge` settings (solid) and flatten-first settings (dashed), dims the rest, shows the measured table and the caption "Previously shown by SYNFI".
- Four caveats in a strip that no step hides. `?stage=1`, `?view=264`, `?kiosk=1`, `?theme=dark`.
- Second wall: V2 against V2e on the 8 project flows only, captioned as a different experiment.

## Tests (headless Chrome via `research/c6/p24/shoot.py`, log in `shots/shoot_log.txt`)
- 1366 x 768 and 390 x 844, light and dark: 0 console errors, warnings, page errors or failed requests.
- No horizontal scroll at either width (scrollWidth = clientWidth).
- No text under 12 px (smallest is the tile digit at 12.03 px on 1366 x 768). No control button under 44 x 44 px.
- At 1366 x 768 the headline, wall, caption and all four caveats fit in one screen in every step (caveat strip bottom at 754 to 759 px).
- Space key steps 1 to 4 and Esc verified by script; keyboard tooltip (arrows + Enter) and tap tooltip verified.
- Reduced motion: 60 ms after a step change the last tile is already in its final state (transition 0 s).

## Not done, and limits
- Wall tiles are 27 px at 1366 x 768 so that the whole wall fits one screen; that is under 44 px. They are reachable by keyboard and are 57 px on a 390 px phone. Control buttons are all at least 44 px.
- Colour-blind safety rests on shape and digit; I did not run a colour-vision simulator. The amber tile has low contrast against the light background (its dark digit does not).
- Not tested: Firefox, Safari, a real phone, a real projector, a screen reader. Only headless Chrome.
- `check_wall.py` is not wired into `make test` or `scripts/check_numbers.py`, and the page is not linked from any other page: those files are outside my scope (integration step).
- The page was not embedded in `explainer.html`.
- "The cause" is an association between options and verdicts in this grid plus E2's structural note; it is not a per-netlist causal analysis. The 12 `abc -dff` one-flip settings stay unexplained, and 6 flatten-first settings still need 3.
- Observation for the integration step: `WHY_TWO_FLIPS.md` lists plain-flow hashes `214a2987 / 152aad31` for V2, while `sweep_rows.csv` has `f3fe9621 / 32b82842` for the same rows. The min-flip rows agree. I used the csv and did not investigate the hash difference.
- Nothing established as new. No hardware claim.
