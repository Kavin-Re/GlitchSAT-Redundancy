# W8 report: wow fix round 8
Edited only docs/explainers/explainer.html, game.html, poster.md, script_60s.md, this file; backups and shots in research/c5/w8/ (backup/, shots/, shoot.py). README.md untouched. No persona test run, no score claim. `python3 docs/explainers/dev/check_game_answers.py`: OVERALL PASS.

## Changes mapped to the WP7 complaints
| WP7 complaint | Change |
|---|---|
| Green MEASURED pill beside the toy hero (expert, #1) | Pill removed from the hero. The "Picture, not computed: a drawing, not a result" label sits directly above the hero drawing; banner now reads "In this picture (a drawing, not a result)". Hero note: "Nothing above is a measurement." Section 1 split into a dashed picture line and a separate green measured block. MEASURED pills now appear only on the table/number blocks. |
| Wiring A/B drawings look like results (#4) | Both picker buttons say "illustration of the structure, not a result"; the game stage carries the same label above the drawing. |
| "The twist" overstates one recipe family (#9) | Renamed "In the designs we tested (one recipe family)" in explainer, poster, 60 s script, game bullet. |
| Outsider cannot see why to care (rider P37 would-tell 5) | One-sentence "Why you might care" under the hero (also in poster and script). The supplier analogy is labelled "An analogy, not a result". |
| "flip" undefined, "par" jargon, game start | "flip" defined at first use (hero, game lead, word list): a glitch that turns one 0 into 1 or one 1 into 0 for one clock tick. "par" is now "best possible score". Game opens on "3 guards, own wires". |
| Accept-flag caveat repeated in every block | Said once, bold, in the green results box (explainer) and above the result cards (game); the repeats in rows, banners, toggles, cards and bullets were removed (evidence sections keep the sourced detail). |
| Paste unclear (P39) | "Tap copy, then paste into a message or email." |
| Polarity only deep in evidence (#1 expert, rail dips) | One plain sentence in both scope boxes, poster, script: a power dip makes outputs fall (1 to 0); a push the other way (0 to 1) breaks even the guarded designs in our model; which is realistic depends on the attack. |
| Kept | Scope box, supplier box with good/worrying answers, evidence sections, checker PASS. |

## Tests (playwright, /usr/bin/google-chrome; research/c5/w8/shoot.py, shots/)
390, 1366, 320, 640 px (stand-in for 200% zoom of 1280), both pages: no console errors, scrollWidth = clientWidth (no sideways scroll), no HTML text under 12 px (tags are 13 px), all buttons/links/summaries at least 44 px.

## Not done
Poster/script_60s wording changed but not re-timed; the 60 s script is now about 210 words (header says so, with a cut suggestion). script_90s.md still uses "twist" (outside the named files). SVG text sizes were not measured.
