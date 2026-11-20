# PS3 report: product adoption items, Face B
Scope: product/ (new files + 4 edited), research/c3/ps3/. Built on a copy in /tmp/work_ps3/product, applied after tests passed. Backups of the 4 edited files: research/c3/ps3/backup/. No make, no push, nothing published or enabled. Exit codes (0/1/2/3/4) and scope schema faultbound-wt-report/1 unchanged.

## Built
1. product/scripts/yosys_flow.sh `design.v TOP out.json`: same recipe as YOSYS_PLAIN in runner.py; prints Yosys version + netlist SHA-256; exit 3 with clear message if yosys missing / bad file / unsafe names (spaces, quotes, ';', odd TOP).
2. product/Dockerfile (python:3.12-slim + apt yosys + pip install of the package, non-root, ENTRYPOINT faultbound-wt). NOT BUILT, linted by reading only (docker exists on PATH but I was told not to rely on it and did not run it).
3. product/.pre-commit-hooks.yaml + new module faultbound_wt/precommit.py (script `faultbound-wt-hook`): runs `analyze` per file, returns the worst exit code. Note: pre-commit wants the file at a hook repo root; QUICKSTART gives a `repo: local` config. Never run through the pre-commit program itself (not installed).
4. faultbound_wt/pytest_helper.py: `assert_no_attack(netlist, goal, k, cycles, attacker_input=, legitimate_value=, top=, config_file=, include=, exclude=, timeout_ms=)` and `check(...)`. goal = ("out", value) or "out==value". AssertionError lists verdict, minimal fault set, attacker input, full scope block (net names escaped).
5. product/action/action.yml composite action (inputs netlist/config/top/max-flips/cycles/..., output exit-code, SARIF upload via codeql upload-sarif). Parsed with PyYAML only; UNTESTED ON GITHUB.
6. `analyze --badge FILE`: shields endpoint JSON, label "fault check", e.g. "no attack <=2 flips @ 6 cycles (scoped)"; all four verdict messages contain "scoped", none contain "secure"/"safe" (tested).
7. QUICKSTART.md: "What to install, in 5 lines" + section 7 (yosys flow, Docker, pre-commit, pytest, badge, Action).
8. Acceptance + cleanup (below).

## MEASURED results (clean venv /tmp/work_ps3/venv2, Python 3.13, `pip install ./product[test]` from the tree, PyPI only)
- `python -m pytest tests` in product/: 38 passed in 28.7 s (27 old + 11 new in tests/test_ps3.py; 11 run incl. yosys 0.33 flow tests).
- analyze v2 --max-flips 2: exit 0, badge "no attack <=2 flips @ 6 cycles (scoped)". --max-flips 3: exit 1, badge "attack found: 3 flips @ 6 cycles (scoped)". --cycles 0: exit 3. missing file: exit 3. pin_lock/pin.v: exit 1. faultbound-wt-hook on v2 k=2: exit 0.
- yosys_flow.sh on pin.v: prints "Yosys 0.33 (git sha1 2584903a060)" and a SHA-256 that equals scope.netlist_sha256 of the check run on that file (tested). Missing-yosys case (PATH emptied): exit 3 with message.
- After tests: egg-info, build, __pycache__, .pytest_cache removed from product/ (find shows 0).

## Not tested / limits
- Docker image never built. GitHub Action and the example workflow never run on GitHub; SARIF upload unexercised. pre-commit program never run (only the hook's entry function tested).
- Hook passes the same options to every file; `--report` would be overwritten per file.
- Badge is a file only; nothing hosts it. A badge is a bound-carrying label, not an assurance.
- Yosys version differences (R24: 0.33 vs 0.38 gave different verdicts) are recorded, not controlled; Dockerfile does not pin a Yosys version.
- Pytest helper's `defaulted` handling touches scope.defaulted_config_values only as implemented; the helper does not support time-varying inputs (unsupported in the product).
