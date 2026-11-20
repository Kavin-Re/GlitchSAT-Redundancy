# H3 hardening report (wave 2b). agent H3

Scope: close the N1 residue H2 listed as "not fixed": `scripts/synth.sh` built `yosys -q -p "read_verilog $1; hierarchy -top $2; ..."` from user text and `glitchsat.py check <v> --top TOP` called it. Work on the copy `/tmp/work_h3`, applied to the tree after it passed. Backups of the pre-change files: `research/c5/h3/backup/` (+ `tests/test_h3.py.new`, a copy of the new test). Labels: MEASURED = I ran it.

## Changes
- `scripts/synth.sh`: TOP must match `[A-Za-z_$][A-Za-z0-9_$]*` (<=255); verilog and output paths refused if empty, starting with `-`, or containing control chars (incl. newline), `"` `'` backtick `;` `\` `#` (same rules as H2 `runner.check_top/check_path`, copied, no product import); verilog must be a regular file. Failure: message on stderr, exit 3. Commands are written one per line with quoted paths into a `mktemp` script file (removed by trap) and run as `yosys -q -s FILE`: no shell interpolation, no `-p`. Same yosys commands in the same order.
- `scripts/glitchsat.py`: `synth()` (used by `check`) validates top/verilog/out with a copied regex pair before calling `synth.sh` (NetlistError, exit 3); `import re` added. The solver code is untouched.
- `product/examples/synth_sweep/variants.toml`: only the stale "Not allowed: ..." comment replaced by the H2 allow-list wording.
- `tests/test_h3.py` (34 cases).

## Measured
| check | result |
|---|---|
| sha256 of netlist, old vs new synth.sh, Yosys 0.33, rtl/v0,v1,v2.v x flow plain,opt (relative path `rtl/vN.v`, because the JSON embeds `src` paths) | **6/6 identical** (v0 plain 018b3d96..., v0 opt 0bbd470a..., v1 plain 1973089c..., v1 opt 34027b09..., v2 plain f954078f..., v2 opt 79d6236f...) |
| canary on OLD synth.sh (`--top 'v0; exec -- touch CANARY'`) | CANARY created (reproduced) |
| canary on NEW synth.sh / `glitchsat.py check`, bad top (9 payloads) and bad file/out names (6 payloads, both args) | all exit non-zero, no CANARY |
| `pytest -q tests` on the copy | **133 passed** (99 + 34 new) |
| `python3 ci/check_reproduce.py --rerun` on the copy | **36/36 rows match (engine re-run); 0 row(s) FAILED**, exit 0 |
| in the tree after applying | `check_reproduce.py` (no rerun) and `pytest tests/test_h3.py` re-run, see final line of the lead message |

## Needs the lead / not done
- `ci/check_reproduce.py` holds `ENGINE_MANIFEST` hashes of `scripts/glitchsat.py` and `scripts/synth.sh` (outside my scope). `--rerun` now prints `WARNING: ENGINE FILE DIFFERS FROM MANIFEST` for both files (by design; exit still 0, 36/36). Run `python3 ci/check_reproduce.py --print-engine-manifest` after reviewing, and update the manifest (and any `--strict-engine` CI step).
- Behaviour change: a Verilog path containing `;`, quotes, backslash or `#` now fails (was passed through). Paths with spaces and `$` work (tested).
- Yosys itself is not sandboxed: a hostile .v file's contents (e.g. `include`) are still read by Yosys. `--flow` is argparse-restricted; `synth.sh` itself treats any non-`opt` flow as plain, as before.
- Single runs on one machine; Yosys 0.33 only.
