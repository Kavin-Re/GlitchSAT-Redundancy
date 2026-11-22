# W7 report: wow fix round 7
Edited only docs/explainers/explainer.html, game.html, this file, and research/c5/w7/ (backup/ of the two originals, shoot.py, inter.py, shots/). No persona test run; no score claim. Not touched: README.md.

## Changes
1. game.html: once the lock is open, further taps are ignored and the status shows neutral "Round finished: press Reset to play again." (no green "lock still holds"); the open message also ends with that line. The page order is now title, short goal, tabs, score, status, drawing; the glossary moved below the game. Fixed a pre-existing CSS order bug that kept the 2-column desktop layout from applying. check_game_answers.py: OVERALL PASS.
2. explainer.html first screen: hero button AND drawing both visible at 390x844 (drawing 373-622 px, button 637-681 px, measured by script). Tag clutter around the hero result cut to one compact line (toy tag + measured tag). Quote, model-only line, word glossary and skip link moved below the hero. Scope box ("What we did, and where it holds") kept unchanged.
3. New "Tell a friend" box (before the Play link): 10-word version "Copies that meet at one point may count as one." and 25-word version "In a computer model, how many glitches fool a lock depends on where its backup copies meet and how you count; nothing physical was tested." (word counts checked: 10 and 25). Copy buttons use plain JS (clipboard API, execCommand fallback), no network; clipboard contents verified.
4. Supplier box: added line "Show your supplier this page."
5. New "What this project is" block directly under the title: Built / Found / Not done, in the three-line wording requested.

## Checks (research/c5/w7/shoot.py, inter.py; Chrome headless)
Both pages at 390x844, 1366x768, 320x640, 640x400 (200% zoom): no console errors, no sideways scroll, no HTML text under 12 px, no visible button or link under 44 px. Game drawing at 390x844 spans 394-731 px, fully above the fold; at 1366x768 it starts at 283 px beside the status panel. Game flow clicked: win then extra tap shows "Round finished", Reset returns to 0. Screenshots in research/c5/w7/shots/.

## Limits
The explainer title stays "Picture: how one shared wire can beat three guards". The Tell a friend sentences are a draft for the author to edit. At 1366x768 the explainer drawing's bottom edge is about 6 px past the first screen (button is visible). Not re-read by a real person.
