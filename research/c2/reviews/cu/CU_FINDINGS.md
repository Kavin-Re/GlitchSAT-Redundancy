# CU_FINDINGS: usability critique

Reviewer CU. Pages tested from a COPY in /tmp/work_cu/site (originals not edited): dashboard/index.html, docs/explainers/explainer.html, docs/explainers/game.html.
Tool: Playwright (node) + Chromium, file:// URLs, widths 360/390/768/1100, light and dark colour scheme, reducedMotion emulation, scripts /tmp/work_cu/{t,k,g,d}.js (copies of the measuring code are not kept in the project).
All numbers below are MEASURED in that Chromium unless marked otherwise. Screenshots are in this folder (`<page>_<scheme>_<width>.png`, full page).

## What passed (so nobody re-checks it)
- Console errors: 0 on explainer and game at every width; dashboard 1, see CU-9 (artifact of the copy).
- Horizontal page scroll: none on any page at any width (documentElement.scrollWidth == clientWidth). Overflow lives only inside local scroll boxes (CU-2, CU-3).
- Text size: explainer and game min 16 px; dashboard min 12.48 px (badges).
- HTML text contrast, 374 text elements on dashboard, 111 explainer, 94 game, light and dark: lowest ratio 5.38 (dashboard `p.sub`, light), 6.12 (dashboard `td.bad`, dark), 7.29 (explainer `p.kick`). All >= 4.5. SVG text 14/17 px, lowest 5.24 (dashboard "flipped here", light), 6.74 dark. No contrast defect found.
- Keyboard-only game: works (Enter/Space on a wire g[role=button] flipped "guard A", status line changed to "Flips so far: 1"); wires have aria-labels "guard A, currently says no. Press to flip." and a polite live status. Tab order is DOM order, no traps.
- prefers-reduced-motion: explainer has 3 rules and `document.getAnimations()` is empty under `reduce` (12+ animations without it); game has 1 rule; dashboard has no animations.
- lang="en", viewport meta, one h1 per page.

## Findings

### CU-1 (medium) Game: SVG labels overlap and clip the "guard A (flipped)" label, even at 1100 px
Evidence: `game_keyboard_3flips_1100.png` (design 5 or 3, after flipping guard A). "wrong code goes in" is drawn over the labels "guard A (flipped)" / "guard B", and "guard A (flipped)" is cut at the left edge ("uard A"). At 360 px, `docs_wow_game.html_light_360.png`: "wrong code goes in" and "the check" touch/overlap (design 1). Selector: the labels are `svg text` (font-size 17 px, fixed) inside the wire diagram.
Not checked: which exact designs trigger it at every width; the label that gets longer on flip is the trigger.
Fix: give the label row fixed spacing sized for the longest string ("guard A (flipped)"), or shorten to "A flipped", use `text-anchor:middle` with a wider viewBox, and move the "wrong code goes in" caption above the first label row.

### CU-2 (high on phones) Game: the results table, the main payoff, is cut off at 360/390 px
Evidence: `docs_wow_game.html_light_360.png` (3rd column of the contact view, and the full-page file). `div.tw` has scrollWidth 440 vs clientWidth 328 (360 px) and 358 (390 px). The "Real solver (MEASURED)" columns and their headings are cut at "Real solv..."; "attack found" is visible, the rest is not. No scroll hint, no shadow, and the box is not focusable (no tabindex, no role, no aria-label), so a keyboard user cannot scroll it in the browser tested (Tab order did not stop on it).
Fix: at <=480 px render the table as stacked cards (one per design, label/value pairs), or drop the Toy block into its own table; at minimum add `tabindex="0" role="region" aria-label="Results table"` and an edge fade plus "swipe sideways" hint.

### CU-3 (high on phones) Dashboard: schematics, chart and two data tables are clipped at 360/390 px
Evidence: `dashboard_index.html_light_360.png`. Scroll boxes: `div#schem` and `div#schem2` (sw 600 / cw 294), `div#chart` (sw 600 / cw 294), two `div.tw` (sw 413 and 376 / cw 294). Visible clipping: schematic nodes "AND chai..", "per-bit sel..", the runtime chart loses its right half (x-axis stops at "12 cy"), result cells show "attack, min 1 fault" cut to "attac / min 1 / fault", "293.5 s" wraps to "s" on a new line. None of the boxes has tabindex/role/aria-label.
Fix: let the SVGs scale (`width:100%;height:auto` with viewBox, min font via a larger viewBox font) instead of fixed 600 px; for tables use stacked rows below 520 px; if scroll boxes stay, make them `tabindex=0` with an accessible name and a visible scroll cue. Note: do not restyle the dashboard per project rules, so this is for the integration step to decide.

### CU-4 (medium) Dashboard: touch targets below 44 px
Measured (360 px; same at 390): `button#theme` 78x38, `button` "V0 naive FSM" 130x38, "V1 duplicated + sparse FSM" 237x38, "V2 triplicated + split word" 220x38, `button#boot` 180x38, `button.cy` "c6" 294x36 (c0 to c5 are 46x57, OK), `summary` "Words used on this page" 294x24. 7 of 13 interactive elements fail at 360/390, 6 of 13 at 768/1100 (theme, 3 variant buttons, boot, summary; c6 is 36 high at all widths too).
Fix: `min-height:44px` on buttons and summary (padding), and `min-width:44px`.

### CU-5 (low) Game: `<summary>` "Plain explanations and limits" is 32 px high at 768/1100
Selector `details > summary`, 728x32 at 1100 (54 px at 360 because the text wraps). Everything else in game.html is >= 48 px. Fix: `summary{min-height:44px;display:flex;align-items:center}`.

### CU-6 (low) Game: five design tabs are all separate tab stops, and wires come after them
Tab order (measured): 5 x `button.tab`, then the wire(s), "Put the wires back", "Show the cheapest break", summary. A keyboard player has to press Tab 6 times to reach the first wire, and again 5 times after every reset to the top. The tabs expose `aria-selected` but there is no arrow-key roving behaviour.
Fix: either treat them as a radio group (arrow keys, one tab stop) or add a "Skip to the wires" link; and move focus to the first wire (or announce in the status) after a design is chosen. Not verified with a screen reader.

### CU-7 (low) Inconsistent and thin focus indicators
Measured: dashboard buttons `outline: solid 3px #2456c9`; explainer and game buttons keep the UA default (`outline auto 1px`, rendered ~2 px dark ring); SVG wires (`.node`) have `outline:none` and rely on `.node:focus-visible circle.ring {stroke: blue; width 4}`; explainer wires `g` report `outline none 3px` and I did not verify a visible ring for them (explainer `g` wires focus: ring not confirmed by screenshot). In `game_keyboard_3flips_1100.png` the game ring is visible (blue on the red YES circle).
Fix: one `:focus-visible{outline:3px solid; outline-offset:2px}` rule for buttons, summary, a.go, and `.node`; check the explainer wires get the same ring (add a test).

### CU-8 (low) Explainer and game ignore dark mode; dashboard supports it
`grep prefers-color-scheme`: dashboard 2, explainer 0, game 0. The dark-scheme screenshots of explainer and game are identical to light (e.g. `docs_wow_game.html_dark_1100.png`). Someone arriving from the dark dashboard lands on a bright cream page; no toggle. Not a WCAG failure. Fix: add the token set for dark, or state it in docs. (Dark contrast of the dashboard itself passed, see above.)

### CU-9 (medium for deployment) Dashboard image uses a path outside its own folder
`dashboard/index.html` line with `src="../layout/v_designs/out_patched/v1_zoom_ok.png"`. In my copy (only the 3 pages) it fails: 1 console error `ERR_FILE_NOT_FOUND`, 1 failed request, and the user sees broken-image alt text ("Zoomed sky130 layout of V1 with the shared AND cell that drives net ok boxed in red") in `dashboard_index.html_light_360.png`. In the project tree the file exists (checked), so this only breaks if dashboard/ is published or shared without layout/. The alt text is good, but the evidence figure for "Act 4" would be missing.
Fix: copy/inline the PNG into dashboard/ (build.py), or add an `onerror` fallback note; add a check in the build that every `src` resolves inside dashboard/.

### CU-10 (low) Explainer: sections are invisible until scrolled into view
`.js section.pre{opacity:0;transform:translateY(24px)}`, revealed by IntersectionObserver. In full-page captures (`docs_wow_explainer.html_light_360.png`, all widths) everything below the first section is blank; print or "save as PDF" will very likely be blank too (print not tested), and a very fast jump (anchor, find-in-page) shows empty space for a moment. With reduced motion the content still starts hidden until intersected.
Fix: add `@media print{section.pre{opacity:1;transform:none}}` and reveal immediately when `reduce` is set; or only hide after the observer is confirmed running (already gated by `.js`, add a timeout fallback).

### CU-11 (low) Explainer: the "answer wire" caption sits on the dashed wire
`docs_wow_explainer.html_light_360.png`, first diagram: the dashed line passes through/under the text "answer wire" (visible tick between the "no" circle and caption). Readability is still OK. Fix: move the label beside the wire (x offset) or add a background-coloured rect behind the text.

### CU-12 (low) Missing landmarks on the two wow pages
`document.querySelector('main')`: dashboard true, explainer false, game false. No skip links anywhere (`a[href^="#"]` absent). With one h1 and short pages this is minor. Fix: wrap content in `<main>`.

### CU-13 (low) Dashboard: smallest text 12.48 px and long dense blocks on a phone
12.48 px for `span.badge` (MEASURED / ILLUSTRATIVE labels, which are the honesty labels). Page height 10317 px at 360 px, 5711 px at 1100 (`dashboard_index.html_light_360.png`). Not a failure, but the labels that matter most are the smallest text on the page; the "Words used" glossary is collapsed by default, which is good. Fix: 14 px badges.

## Not done / limits
- Only Chromium (headless, file://), no Safari/Firefox; Chromium of this build did not put scroll boxes in the Tab order, newer Chrome may (CU-2, CU-3 keyboard claim applies to the tested build).
- No screen reader run; ARIA statements come from attributes only.
- Contrast: HTML text computed from computed styles and ancestor backgrounds (gradients/images not handled); SVG text against page background or its rect fill where detectable (the white-on-green "LOCK SHUT"/"DOOR SHUT" labels were mis-detected by the script, visually they are white on dark green, clearly legible).
- Dark scheme for explainer/game has no separate styles, so the dark pass equals light.
- Not tested: zoom 200 percent, text-spacing overrides, forced-colours, real touch devices.
