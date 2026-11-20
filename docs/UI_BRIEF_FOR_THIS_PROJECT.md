# UI brief for this project's dashboard (from your ai_ui_pack, applied)

Status: a PROPOSAL. Nothing has been restyled yet; waiting for your yes. Date 2026-11-19.

## 1. What was read, and by whom (honest)
- **Read by me in full:** `README.md` of the updated pack (your quotes, rules, the preferred laptop design, the nine add-ons, the master prompt). Also `design/03` sections 0, 1 and 6 to 12, the original `design_tokens.css`, `wording_deck.md`, and three screenshots.
- **Read by five readers, digests written, and I read the sections I rely on below:** `design/01` (all 472 lines), `design/02` (all 407 lines), `design/03` sections 2 to 5, all 41 new screenshots plus the 7 first-pack images, `images/INDEX.md`, `captions.json`. Digests: `/home/user/uipack2/digests/D1..D5`. I read D2 sections 3 to 6 and D5 section 4 in full; I did not read the rest of the digests line by line.
- Pack problems found: image 16 missing, image 13 has no caption, several captions do not match the picture, and the pack's own files disagree in places (section 6 below).

## 2. Your preferences that apply here (SAID, dated, from the README)
- Plain words for non-experts; no jargon on the main screen (2026-11-15, 2026-11-18).
- "one category of settings in one way"; know what is where (2026-11-15).
- Confidence that is earned, not faked: no obvious mistakes, honest limits (2026-11-15).
- The UI must explain itself when you are not present (2026-11-15).
- Results shown as what changed, not a long log (2026-11-15).
- Engineer features should not be locked away from the real user, but sit behind an explanation (2026-11-15).
- Laptop: "i like nirmalyas laptop ui but i like the addons (ideas i made as well)", and "all nine add-ons are mine, keep them" (2026-11-19).
- Method: test as a user with screenshots, several independent reviewers, state my understanding before research, short chat answers with detail in files, verify claims, label SOURCED/MEASURED/ASSUMED/UNVERIFIED, list anything safety-related as "needs approval".

## 3. The look (tokens), with the fixes the pack itself says are needed
- Near-black cool grey, one teal accent for interaction and selection only, red = failure, amber = caution or demo data, green only sparingly, grey = neutral. 1 px hairlines, 2 px corners, no shadows or gradients, monospace tabular numerals for every number, hash, net name and cycle count.
- Three themes from one token file: charcoal (default), high-contrast daylight, red-monochrome night. Tokens are in `design_tokens.css`.
- **Contrast fixes needed (reader D3 recomputed them; they match the pack's own table):** the file's "4.5:1 in every theme" claim is false. Fix before reuse: daylight warn on surface-2 (4.24), daylight ok and ambient on surface-2 (about 4.1), night warn (4.34 to 4.46), night ok (3.2 to 3.4), night ambient (about 2.9), night strong-border (2.2), charcoal strong-border on surface-2 (2.66, mark threshold 3.0).
- Sizes: nothing under 12 px for text people must read (the pack's own flaw list: 10 to 13 px everywhere); 32 px controls for mouse, 48 px for touch; wrap fault text, never truncate; 200% zoom must work.
- Fonts: IBM Plex Sans and Mono (plus Barlow Condensed for the big word). The pack does NOT include the font files; this dashboard is a single offline file.

## 4. Mapping ADIS to this project (my inference from D2 section 5 and D5; the sources are ADIS-specific)
| Your ADIS element | This dashboard |
|---|---|
| 36 px top bar, text tabs, no icons | Same: tool name and version, tabs, run-state dot, Run/Stop, design selector, Simple/Expert toggle, Settings button |
| Operator view: polar radar left, sortable expandable track table right, selection synced | **Analysis:** real netlist graph left (faulted net red), results table right; click a row to light the net, click a node to select the row |
| Radar "can't see" hatching | Hatched "not checked beyond the bound" (cycles beyond T, faults beyond k) |
| Threat dot plus word | Verdict dot plus word, never colour alone |
| Expandable row with evidence for and against | Row expands to: why it breaks, fix pattern, replay waveform, layout zoom, assumptions |
| Engineer view | **Solver:** runtime against cycle bound, independent-check results, reduction benchmark, mutation results |
| System view (registry, latency, drivers, event log) | **System:** tool versions with hashes, stage timings, run log with Export CSV, "what was not verified" list |
| Radio drawer showing confirmed values | Settings drawer: solver parameters; readout shows the values the tool actually used |
| Field button and Survey tab (add-on 2) | **Summary** button: the simple, phone-style page with one big verdict word and one plain sentence |
| Hard confirms for risky changes | Confirm before overwriting results or starting a long run |
| Persistent simulation marking, fail loud | Persistent ILLUSTRATIVE banner for example data; per-panel error boxes; "no result yet: run it" empty states |
| ASSUMED / MEASURED labels | MEASURED / SIMULATED / ESTIMATED / ILLUSTRATIVE / UNVERIFIED badges (already in the dashboard) |

**Does not transfer:** everything RF, audio and Android, the guard user model, real-time streaming (this dashboard is run-based, so show "result from run X, tool version Y, at time T" instead of a live scan), and radar semantics (a netlist graph needs real graph layout, zoom and pan).
**Note:** reader D5 drew its example layout for a hardware glitch rig; ours is a solver, so I used reader D2's mapping and D5's header, status-bar and column rules.

## 5. Proposed 1366x768 layout (Analysis workspace)
```
+------------------------------------------------------------------------------------------+
| FAULT LAB v1  Summary | Analysis  Solver  System |  * Done   [Run][Design: V1 v] [Simple|Expert] [Settings] | 36 px
+------------------------------------------------------------------------------------------+
| 9 results - bound: 6 cycles - MEASURED        Primary: V2 re-synthesized BREAKS with 2 faults  [Details] | 29 px
+------------------------------------------+-----------------------------------------------+
| Netlist graph (real, from Yosys)         | Results (9)                      Filter: none |
|  faulted net in red, label "ok"          | Design     Netlist       k  Min  Fault   Verdict |
|  hatched = not checked beyond bound      | V1 dup.    spike         1  1    ok@1    * BREAKS |
|  legend: teal selection, red fault       |            (re-synth: plain)                    |
|                                          | V2 triple. spike         2  -    -       * NO BREAK FOUND (to 6) |
|                                          | V2 triple. RTL plain     2  2    n58@0..  * BREAKS |
| footer: model = single-cycle flips       | (7 columns, all fit at 1366; click row to expand) |
+------------------------------------------+-----------------------------------------------+
```
At 1920 a third column shows the selected result's detail (explanation, replay, layout zoom) instead of stretching two columns.

## 6. Contradictions in the pack and how I would resolve them
- Clear colour: README says green, the built screen uses grey. **Use grey for "no break found", green only for a confirmed pass condition, sparingly.**
- Corner radius: README says 2 px everywhere, many elements use 4 px. **Use 2 px.**
- "A quiet screen does not mean no drone" is in the README but only in Help on the built screen. **Here: always show next to "no break found": "not proof beyond 6 cycles and 3 faults".**
- Top bar: 36, 44 and 35.75 px are all quoted. **Use 36 px.**
- Three themes versus the original's one theme and different hex values: **use your current tokens (charcoal, daylight, night) with the contrast fixes**; if you want the original's exact palette, tell me.
- Add-on 8 (directional-by-default) leaves the simulation empty: not relevant here.
- Your preference for Nirmalya's design reaches two of the pack's files only second-hand; the README has the direct dated quote, which I used.

## 7. Wording (plain first, the pack's own lesson: never overclaim)
Verdict words: **BREAKS** (attack found), **NO BREAK FOUND (to 6 cycles, 3 faults)** (bounded; never "SECURE" or "SAFE"), **NOT PROVEN**, **SOLVER FAILED**. Fault words are red and underlined and outrank everything. Technical terms (SAT, UNSAT, k, cone of influence) move to a glossary where the on-screen word comes first. The wording deck's proposed words were never built in ADIS, so these are suggestions to test with a non-expert.

## 8. What I need from you (the pack says to ask)
1. Is the Summary-plus-three-workspaces layout right for this project?
2. Who reads it: evaluator, students, or you? (sets how plain the words must be)
3. Keep all three themes? (You said to keep the add-ons; themes are add-on 1.)
4. Fonts: use IBM Plex by embedding font files (I would need to fetch them; the pack has none) or a system fallback?
5. English only?

## 9. If you say yes (plan, small)
Restyle `dashboard/` with these tokens and layout; fix the contrast values; plain-word verdicts and glossary; test at 320, 360, 390, 412 and 1366x768 and 1920x1080, at 200% zoom, in all three themes; three small independent reviewers (usability, wording, accessibility) report findings including bad scores; one report file, short chat summary.
