# Plain-words findings

One explainer for every GlitchSAT result path: the Studio (path steps, "Explore a real chip", the boot program page,
the example gallery, "Open my design"), the own-design tool's text report, `report.json` (`plain_findings`) and SARIF
(`glitchsat run --sarif FILE`), and the whole-chip `results/RESULTS.md`.

Each finding gives, learner first: a severity (Critical, High, Medium, Low, Info: a word and an icon, never colour
alone) with its reasons, what it means in real life, a real-world comparison from the lesson where one honestly fits,
how urgent the fix is; then one plain sentence, why it happened (patterns (a) to (d) below), where (file:line, signal or
instruction, clock step, with the source line marked when the file is there), how sure we are, what to do and how to
check the fix; and "How we found it" (six steps, a before/after trace when the run stored one, try it yourself, spot it
next time). Nothing is invented: when a piece is not in the run data, the finding says so.

Patterns: (a) the build tool or compiler removed a protection; (b) one skipped instruction made two values the same;
(c) a random delay did not stop a precisely timed glitch; (d) one wire or branch decides the outcome. A pattern that
cannot be told from the data is reported as "cannot tell from this data", not guessed.

Severity rules: `SEVERITY.md` (written from `SEVERITY_RULES` in `plain_findings.py`: `python3 plain_findings.py doc`).
Severity is an estimate for a modelled fault, not a measured attack on hardware; no CVSS score is given.

Tests: `python3 -m pytest -q tests`. Standard library only. In the repository this folder lands as `tools/findings/`.
