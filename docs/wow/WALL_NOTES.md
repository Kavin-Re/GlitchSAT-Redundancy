# Reveal wall: how to present it in 90 seconds

License: Apache-2.0. GlitchSAT.
Page: `docs/wow/wall.html` (standalone, works from `file://`, no network). Data: `docs/wow/e2_wall.json`.
Every number below is MEASURED: a count of rows in `research/c2/e2_variance/raw/matrix.csv` (wall) or
`research/c6/p01/sweep_rows.csv` (second wall); re-derive with `python3 docs/wow/check_wall.py`.
Bound of every verdict: one toy design (`rtl/v2.v`), modelled bit flips, 6 cycles, at most 3 flips.

## Set-up (before you speak)
- Open `docs/wow/wall.html?stage=1` full screen (F11). It opens on step 1, "the blueprint".
- Keys: **Space** = next step (PageDown/PageUp also work, for a clicker), **Esc** = show everything.
- The default count is the 152 distinct netlists. Leave it there. Use "every setting (264)" only if asked.
- Booth loop: `wall.html?kiosk=1` (steps change every 7 s). Dark room: add `&theme=dark`.
- If the audience asks for no animation, the page already obeys the system "reduce motion" setting.

## The 90 seconds
| time | key | on screen | say |
|---|---|---|---|
| 0:00 | (page open) | Step 1, the blueprint: one file, three checks | "One blueprint. The key check is written three times, so on paper a fault must beat all three: three flips." |
| 0:15 | Space | Step 2, the builders: 152 grey tiles appear, block by block | "I gave the same file to 264 synthesis settings: three Yosys builds, 96 option combinations each. They built 152 different netlists. How many still need three flips? Guess." |
| 0:35 | Space | Step 3, the verdicts: tiles turn into 3 / 2 / 1 | "20 of 152 keep three. 38 drop to two. 94 open with a single modelled flip. Same blueprint, different builders." |
| 0:55 | Space | Step 4, the cause: merge settings outlined, the rest dimmed | "Outlined are the settings that let the tool see the three identical checks together: `opt_merge`, or flattening before ABC. Identical logic gets merged into one copy. That is ordinary optimisation, and SYNFI showed this effect before us." |
| 1:15 | (point at the yellow strip) | The four caveats | "Four limits: one toy design; the settings are not independent; one option, `opt_merge`, gives 120 of the 180 one-flip settings; and the effect is not new." |
| 1:25 | (optional: scroll) | Second wall, V2 against V2e | "Changing one constant brings six of eight project flows to three flips. It does not help the two flows that merge the checks." |

## Numbers you may be asked for (all MEASURED, bounded as above)
- Per distinct netlist (default): 152 netlists, min flips 1 / 2 / 3 = 94 / 38 / 20 (13% at 3).
- Per setting: 264 solved settings, 180 / 60 / 24 (9% at 3). 24 more settings gave a netlist the engine cannot read: no verdict, not "safe".
- `opt_merge` on: 132 settings, 120 at 1 flip, 12 at 2, none at 3. Flatten before ABC without merge: 48 / 12 / 6. Neither: 12 / 36 / 18; those 12 one-flip settings all use `abc -dff` and were not analysed.
- Second wall (8 project flows, not the 264): V2 row on Yosys 0.33 is 2 1 1 2 2 2 2 2, V2e is 3 1 1 3 3 3 3 3; on 0.38+92 V2 is 3 1 1 2 3 2 3 2, V2e the same as on 0.33. 9 of 253 possible constants tried.

## Do not say
- "Safe", "secure", "proved", "new", "first". A "3" means no attack was found with 2 or fewer flips within 6 cycles.
- "264 independent experiments". It is one full grid on one design; 264 settings give 152 netlists, and two of the three builds share a git sha.
- "Glitch" for what was measured. These are modelled bit flips in a netlist; nothing was measured on a chip.
- "The fix" for V2e. It is one re-encoding that held on 6 of 8 flows; the merging flows still fall to 1.

## If something goes wrong
- Tiles do not appear: JavaScript is off. The headline, counts and caveats in the text are static and still correct.
- Pressed Space and nothing moved: a control button has focus; click the page background or press the "Next" button.
