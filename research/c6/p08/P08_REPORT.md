# P08 report
Changes: scripts/glitchsat.py only (backup: research/c6/p08/backup/scripts/glitchsat.py), new tests/test_p08.py.
- P08a: `subprocess.run([synth.sh,...])` -> `['sh', synth.sh, ...]` (synth.sh shebang is `#!/bin/sh`, POSIX case/[ ] only). Only direct exec site in glitchsat.py; product/src has its own inline Yosys script (no synth.sh exec), validation/synth.sh is run as `sh synth.sh`, Makefile/ci/tests have no direct exec (tests/test_h3.py already uses `sh`). Nothing else to change.
- P08b: multi-fault summary now says faults at N distinct nets (names listed), "this output does not classify whether they sit on independent copies or on a shared decision path; see the consumer-bits and ledger docs"; "add another independent copy" advice removed from fix_pattern (now: inspect the listed nets, re-run at k). Dict keys, verdicts, exit codes unchanged. product/ has no such text (grep), untouched.
## Measured (on /tmp/work_p08 copy, all scripts chmod -x, venv /tmp/p08venv)
- BEFORE (original, synth.sh mode 644): `python3 scripts/glitchsat.py check rtl/v0.v --top v0 --k 1 --cycles 6` -> PermissionError [Errno 13] (MEASURED).
- `python3 ci/check_reproduce.py --rerun`: 36/36 rows match, 0 failed (MEASURED); expected WARNING engine sha differs from manifest.
- `pytest -q tests`: 138 passed (incl. 2 new). `pytest -q product/tests` (pip install ./product[test]): 324 passed, 1 skipped (xcheck: `python3 research/c3/rt/xcheck.py 1 20`: 20 netlists, 0 disagreements).
- apt 0.33 V2 `check rtl/v2.v --top v2 --k 2 --cycles 6`: MIN 2, new text has no 'independent redundant' / 'add another' (tested).
## sha256 scripts/glitchsat.py
old 78ecea0813051f2a6e962cf6c42983afd34754245b99651f026bef6df45cfe40
new 1ad037ef07e23c2aabcea75b87a99616591957bd61ed8e0b80abae6b737a9f3c
Lead: update ENGINE_MANIFEST in ci/check_reproduce.py (not edited here).
