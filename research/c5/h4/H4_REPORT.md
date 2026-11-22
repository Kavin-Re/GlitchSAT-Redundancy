# H4 report: gate-found fixes
All numbers MEASURED on the copy /tmp/work_h4 (venv /tmp/h4venv, `pip install ./product[test]`), then the same files applied to the tree.

Changed files (originals in research/c5/h4/backup/): product/src/faultbound_wt/config.py (MAX_CYCLES = 200, check in validate), product/src/faultbound_wt/cli.py (--help text; output-directory check before the solve for --report/--badge/--sweep-out), product/pyproject.toml ([test] = pytest>=8, pyyaml), product/QUICKSTART.md (one bullet in 4d), new product/tests/test_h4.py (11 tests; backup copy in backup/product/tests/).

- F2: `--cycles` or TOML `cycles` > 200 is exit 3 `cycles N is above the supported maximum of 200`. RT3 reproducer (`--max-flips 1 --cycles 1000000000`): exit 3 immediately. All 36 reproduce rows use cycles = 6 (ci/expected_reproduce.json), so no verdict is affected; the product engine path is unchanged except the validate check.
- F3: `pip install ./product[test]` now installs pyyaml: 0 skipped.
- F5: `--report /nope/x.json`: exit 3 `output file ... directory '/nope' does not exist (checked before the analysis ...)`, no solve (test monkeypatches runner.analyze to fail if reached).

## Exact counts (docs can be updated)
| Check | Result |
|---|---|
| product tests (`pytest product/tests`) | **321 passed, 0 skipped** (310 + 11 new) |
| root tests (`pytest tests`) | **133 passed** (unchanged) |
| `python3 ci/check_reproduce.py --rerun` | 36/36 rows match, 0 FAILED (exit 0) |
| `python3 scripts/check_numbers.py` | 52 files scanned, 0 STALE, 15 HISTORICAL (exit 0; run on the copy, before docs say 321, so the 310 figure was not flagged by rule) |

Exit codes 0-4 and report schema keys unchanged. Not done: README/START/FINAL_STATUS still say 310 (docs are the integration step's). Tree has no product/build or egg-info (egg-info exists only in the /tmp copy). check_numbers must be re-run after docs change to 321.
