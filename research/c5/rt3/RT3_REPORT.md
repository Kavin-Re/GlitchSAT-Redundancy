# RT3 final-gates red team report

Scope: replay of RT2 reproducers against the CURRENT tree after H2/H3, new bypass attempts, re-verification of H2 fixes, fresh gate run, bundle check. Everything ran on a copy under `/tmp/work_rt3/` (`p` = tar-pipe copy; `venv` = `pip install ./product[test]`; after that `product/build` and `product/src/*.egg-info` were deleted in the copy). No `make`. Nothing in the tree changed except this folder. Labels: MEASURED = I ran it and saw the output. Faults are modelled bit flips; nothing here is a hardware statement. Scripts used are in this folder (`inj.sh`, `inj2.sh`, `inj3.sh`, `conc.py`; they assume the `/tmp/work_rt3/t` layout and `pin.v`/`pin.toml` from `product/examples/pin_lock`).

## Headline
- Canary files created by the product CLI, `scripts/synth.sh`, `glitchsat.py check`, `product/scripts/yosys_flow.sh`, the GitHub Action steps (shell-simulated): **0** across about 300 payload runs. The RT2 N1 class is closed on every path RT2 listed.
- **One NEW hole of the same class, still open: `docs/edu/tools/synth_merge.sh`** (shipped in the bundle; HIGH by class, see F1).
- Gates on the copy: check_reproduce 36/36 (default and `--rerun`, no manifest warning), `pytest tests` 133 passed, `pytest product/tests` 308 passed + 2 skipped (310 only with pyyaml installed), check_numbers 0 STALE, dashboard build leaves `index.html` identical, bundle dry-run clean, `verify_bundle.sh` 0 fails.

## Findings (rated, minimal reproducers)
| # | Sev | Finding | Label |
|---|---|---|---|
| F1 | HIGH (class N1; exposure smaller: a manual classroom script, not CI) | `docs/edu/tools/synth_merge.sh` still pastes `$V`, `$TOP`, `$OUT` into `yosys -q -p "read_verilog $V; hierarchy -top $TOP; ...; write_json $OUT"`. Command execution via Yosys `exec`. | MEASURED |
| F2 | MED | `--cycles` has no cap (H2 capped only `--max-flips` at 64). V2 `--max-flips 1`: `--cycles 100000` no result in 34 s (`timeout` killed); `--cycles 1000000000` runs until the kernel OOM-kills it (exit 137, 50 s). `--timeout-s 5` does stop `--cycles 20000` in 5 s (exit 2), so only an unguarded run is exposed. Same DoS class as RT2 N8. | MEASURED |
| F3 | LOW-MED | The documented install `pip install ./product[test]` does not install pyyaml, so 2 YAML tests skip: **308 passed, 2 skipped**, while README l.68, START l.19 and FINAL_STATUS l.35 say "310 passed after `pip install ./product[test]`". 310 appears only when pyyaml is also installed (verify_bundle.sh installs it). Honesty/consistency issue, not a code bug. | MEASURED |
| F4 | LOW | `ci/check_reproduce.py --rerun` with an edited engine file prints `WARNING: ENGINE FILE DIFFERS FROM MANIFEST ...`, but still prints `36/36 rows match (engine re-run); 0 row(s) FAILED; 0 problem(s) in total` and exits 0 unless `--strict-engine` is passed (then exit 1). A CI that greps the summary line stays green. Tamper-evidence limits are stated in the output itself. | MEASURED (appended one comment line to `scripts/synth.sh` in a second copy) |
| F5 | LOW | `--report /nonexistentdir/x.json`: the full analysis runs, then `internal error (FileNotFoundError ... .x.json.<rand>.tmp); no verdict was produced`, exit 4. Should be an exit-3 check before the solve; the computed verdict is thrown away. | MEASURED |
| F6 | LOW | SIGKILL of the parent still leaves `/tmp/fbwt_w_*` (H2 documents this). The worker and yosys are gone within 3 s. 34 old `fbwt_*` dirs from earlier agents were in `/tmp` before my runs; none of my runs added any other than the one `fbwt_w_*` from the SIGKILL case. | MEASURED |
| F7 | LOW | Inconsistent path rules between scripts: `synth.sh` / `glitchsat check` accept non-ASCII file names (`pіn.v` with a Cyrillic i), `yosys_flow.sh` refuses them (exit 3). No execution either way. | MEASURED |
| F8 | LOW (cosmetic) | `--consumer-bits bits:4095` on an 8-bit output prints a roughly 1000-character hex mask in the error. | MEASURED |
| F9 | LOW (semantics trap, documented) | Bare strings that look like a list are still bit lists (`"0-3"` = bits 0..3, `"0-3,6"`), while a bare number is a mask (`3` = bits 0,1; `255` = all). `--consumer-bits 3` now means mask 3, a behaviour change from the pre-H2 string form (documented by H2). | MEASURED |
| F10 | INFO | Yosys itself is unsandboxed: a hostile `.v` with `` `include `` still reads other files (H2 lists this). Not re-tested. The action's `sarif-file` input accepts an absolute path and writes there (`canary_sarif.sarif` was created at the path I gave; that is caller authority, not injection). | MEASURED (sarif path) / INFERRED (include) |

### F1 reproducer (MEASURED)
```
sh docs/edu/tools/synth_merge.sh pin.v "pin; exec -- touch /tmp/work_rt3/canary_edu1; hierarchy -top pin" o.json   # canary created
sh docs/edu/tools/synth_merge.sh pin.v pin "o.json; exec -- touch /tmp/work_rt3/canary_edu2"                       # canary created
```
Fix (not applied): same validation and script-file template as `scripts/synth.sh` (H3), or delete the script and describe `opt_merge` as a `--synth-variants` variant (`post = "...; flatten; opt_merge; ..."` is already on the allow-list). Also check other copies of the old pattern: `validation/synth.sh` uses fixed names (not exploitable); `handoff/evidence/F1_ff.py` and `gasp_spike_F1/ff.py` build `-p` strings from fixed text (history, not exploitable).

## 1. RT2 replay and new bypass attempts (MEASURED, no canary anywhere)
Payload canary pattern: `touch /tmp/work_rt3/canary_*` (or relative `canary_*` in cwd). After every run the harness counts canaries.

| surface | cases | result |
|---|---|---|
| `--top` CLI, TOML `[netlist] top` (`inj.sh`, 20 payloads each) | `;`+`exec`, newline, CR, `$(...)`, backticks, `;touch`, trailing/leading space, NBSP, Cyrillic p, NUL (bash drops it, so it became plain `pin` and ran normally), `\pin ` escaped identifier, `\pin; exec ...`, `-top` (argparse -> exit 3), `#`, `%s`, 5000-char name, `${HOME}`, `;`, quote break-out | all exit 3 `not a plain module identifier` except the NUL case (valid `pin`, exit 1 = attack found, correct). 0 canaries |
| Verilog file names via product CLI (`inj2.sh`, 24 names) | `;exec`, newline, `$(..)`, backtick, `'`, `"`, Cyrillic, trailing space, 300-char, `${HOME}` literal, backslash, `#`, space, CR, TAB, `%s`, `$HOME`, `,`, `!`, RLO U+202E, glob chars, `{a}` | refused with exit 3 or analysed normally (space, `$`, `,`, `!`, glob chars, unicode); 0 canaries. Symlink whose name carries a payload: no canary. Symlink to a valid file: analysed (exit 1) |
| `--synth-variants` (`pre`/`abc`/`post`, 18 payloads x 3 fields, plus variant name, `extends`, `--synth-select`, JSON variants file, description with newline) | `exec`, newline, CR, `$()`, `#`, `techmap -map`, `synth -run`, `abc -script`, `abc -exe`, `flatten -wb`, `opt -fast` | all refused (exit 3) except allow-listed commands (`opt -fast`, `synth -top {top} -noabc -flatten`, `dffunmap -ce-only` accepted in `post`, as designed). 0 canaries |
| `scripts/synth.sh` args (24 file names, 9 output names, 18 tops) | same payload families | hostile top/path: exit 3, no canary. Payload-looking but harmless names (`$(touch ..)`, `%s`, spaces, Cyrillic, glob chars) run as literal file names, exit 0, no canary |
| `glitchsat.py check` (`inj3.sh`: 11 tops, 8 file names, 6 `--out` names) with the right goal flags (`--goal-out unlock --goal-value 1 --attack-input code --key 10`) | | hostile top/path: exit 3; `--out` accepts any name and writes there (caller authority); 0 canaries. Note argparse errors in `glitchsat.py` exit 2 (= its "solver unknown" code); the product CLI remaps usage errors to 3 |
| `product/scripts/yosys_flow.sh` (24 names x 9 outputs x 18 tops) | | exit 3 for hostile input; 0 canaries |
| GitHub Action `action.yml`, steps extracted with a YAML parser and run under bash with env vars set as the runner would (not run on GitHub) | 19 analyze-step cases, 5 install-step cases | top / max-flips / cycles payloads: exit 3, 0 canaries. `netlist` or `config` beginning with `--`: taken as a file name after `--` / `--config=` form, exit 3 (`no such file`). A `netlist` value with a newline or extra words stays ONE argv element (exit 3 no such file). `max-flips` Arabic-Indic digit, `-1`, `1 2`, newline: exit 3. `package-path`: empty or leading `-` exit 3; `product; touch ...` and `$(touch ...)` are echoed as one literal argument (`pip install -- "<value>"`), 0 canaries. Remaining by design: `sarif-file` can name any path; a `sarif-file` with a space and `--report=` text produced `internal error` exit 4 (FileNotFoundError), not a command. The `upload-sarif` step was only read, not simulated |
| environment variable | `FAULTBOUND_AMK='legacy; touch ...'` | rejected (`amk must be counter or legacy`), no canary |

## 2. H2 fixes re-verified, 15 adversarial cases (MEASURED)
1. Atomic report writes, 20 concurrent `faultbound-wt` writers x 6 rounds to one `--report` path (json) plus `.sarif` and `--badge`, while a reader thread parsed continuously (`conc.py`): 70195 reads, **0 invalid**, all exit codes 0/1, no temp file left, final json/sarif/badge parse. PASS.
2. `--timeout-s 1` on a 32-bit cube design (`big.v`): returned in 1.13 s wall, exit 2 `UNKNOWN_TIMEOUT`, no new `fbwt_*` dir, no live `yosys`/`abc` (only two `<defunct>` entries reparented to pid 1, a container without a reaper; not running processes). PASS.
3. SIGTERM to the parent mid-run: exit 143, no worker, no yosys, no new dir. PASS.
4. SIGINT to the parent: no process left, no new dir. PASS.
5. SIGKILL to the parent: worker and yosys gone within 3 s; one `fbwt_w_*` dir left (F6, documented). PARTIAL.
6. Four error paths after Verilog synthesis (`--goal-out nonexist`, `--accept-value 99999`, `--consumer-bits bits:99`, `--max-flips 65`) leak no `fbwt_*` dir. PASS.
7. `--consumer-bits` matrix, 31 forms on V2 (`/tmp/work_rt3/t`, one command each, all under 0.4 s): exit 3 with a clear message for `0`, `0x0`, `-1`, `1-`, `bits:1-`, `bits:0-100000000`, `bits:4096`, `0x1FF`, `1_0`, `3,`, `bits:`, empty string, `0o7`, Arabic digit, `0x`, `7-0`, `+3`, `3.0`, `True`, `1e3`. Accepted: `3` = mask 0x3 (ATTACK, 1 flip), `255` and `0xFF` = all bits, `bits:3` = bit 3, `bits:0-3,6`, `[3,5]`, `0-3`, `0b101`, ` 0x0F `, `00012`, `bits:00`, `bits:0-3,2` (duplicate bit ignored). `bits:0-100000000` (RT2 N7, 59 s CPU before) now exits 3 immediately. PASS (F8, F9 cosmetic/semantic).
8. `--max-flips`: 1, 64 work (64 on V2 took 1.5 s); 65 and 99999999999999999999 exit 3; `-1` exit 3; `1.5`, `1e1`, `abc`, `0x10` exit 3 (argparse usage); `0` runs (NO_ATTACK at 0 flips); `"3 "` accepted. TOML: `true`, `64.0`, `'3'` rejected, `65` rejected, `0` runs. PASS.
9. Counter vs cap: 64 on V2 returns ATTACK with 1.5 s. PASS.
10. Sweep CSV formula guard, `--scope-sweep --report x.csv` with an output port named `=cmd|"calc"!A0`, `+SUM(1)`, `-2+3`, `@SUM(1)`, TAB+`=1`, CR+`=1`: every such cell has a leading `'`; a leading space and a fullwidth `＝` pass through unguarded (not formula starters in Excel; treated as acceptable). PASS.
11. `--sweep-widths --report w.csv` with port `=cmd|x`: guarded. PASS. `--synth-sweep --report s.csv`: 10 columns, no net text. PASS.
12. `--scope-sweep --report x.json --badge b.json` combined options: sweep table written, badge refused (exit 3), per H2. PASS (read from H2; JSON path exercised in step 10/11 with CSV only).
13. Report path that is a symlink to a not-yet-existing target: replaced by a regular file, target not created. PASS.
14. `--report x.txt` unknown extension: exit 3. `--report /nonexistentdir/x.json`: exit 4 internal error after the solve (F5). PARTIAL.
15. `--cycles 0` exit 3, `-1` exit 3, `1` exit 3 with CONFIGURATION PROBLEM; very large `--cycles` not capped (F2). FAIL (new finding).

## 3. Fresh-eyes gates on the copy (MEASURED)
| gate | result |
|---|---|
| `python3 ci/check_reproduce.py` | `36/36 rows match (summary + per-run files + input hashes; engine NOT re-run); 0 row(s) FAILED; 0 problem(s)`; 0.04 s |
| `python3 ci/check_reproduce.py --rerun` | `36/36 rows match (engine re-run); 0 row(s) FAILED; 0 problem(s)`, exit 0, 9.1 s; `WARNING` count in output: 0. `--print-engine-manifest` equals `sha256sum scripts/glitchsat.py scripts/synth.sh` (0747950d..., 99686d4e...) |
| `pytest tests` | 133 passed, 17.9 s |
| `pytest product/tests` (venv from `pip install ./product[test]`) | **308 passed, 2 skipped** (pyyaml missing; F3). With the bundle verifier's extra `pip install pyyaml`: 310 passed, 81.7 s |
| `python3 scripts/check_numbers.py` | `52 files scanned, 0 STALE, 15 HISTORICAL (rules: 36)`, exit 0 |
| `python3 dashboard/build.py` | `wrote index.html; live = True`; md5 6992e082951c2e386e6493b3edfae3e6 before and after: identical |
| safety notice | no "H2 in progress" / "until the fix lands" text left in README, START, FINAL_STATUS, dashboard (grep, 0 hits) |

## 4. Bundle (MEASURED, copy tree: NOT the real tree, which also has `third_party_derived` and handoff zips that the allow-list excludes anyway)
- `BUNDLE_ROOT=/tmp/work_rt3/p scripts/make_bundle.sh --out /tmp/work_rt3/bundle_dry`: dry run exit 0. Bundle B: 1872 files, 82.8 MB uncompressed, 178 .md; PII/SECRET scan clean (1872 text files). Exclusions hit: `formal/runs` (1020 files), `backup/` dirs, `shots/`, `__pycache__`, `.pytest_cache`, one png over 3 MB.
- `--build --out /tmp/work_rt3/bundle_out`: review kit 1,100,137 bytes, full tree 56,021,015 bytes, SHA256SUMS written.
- `verify_bundle.sh` run from a sed-copy with all `/tmp/bundle_*` paths redirected to `/tmp/work_rt3/bv*` (the original hard-codes `/tmp/bundle_verify`, shared with other agents): **fails: 0**; PASS for pip installs, check_reproduce, `--rerun`, pytest tests (133), product tests (310), check_numbers, the 3 START.md commands, dashboard_build, `dashboard_index_unchanged`, `no_forbidden_paths_in_zip`. 599 text files in the zip mention `/tmp/` or `<home>` (8 in run-path directories: `ci/clean_install_log.txt`, `formal/src/gs_crosscheck.py`, two product tests, `scripts/make_bundle.sh`, `scripts/setup_layout_tools.sh`, `scripts/verify_bundle.sh`, `validation/boolector.log`); informational.
- The bundle includes the vulnerable `docs/edu/tools/synth_merge.sh` (F1; confirmed in the zip listing).
- Not verified: the zips built from the real tree (third_party_derived etc. absent from my copy); zip determinism.

## 5. What a reviewer could still break in 5 minutes
```
# 1. command execution in a shipped script (F1)
sh docs/edu/tools/synth_merge.sh pin.v "pin; exec -- touch /tmp/PWN; hierarchy -top pin" o.json && ls /tmp/PWN
# 2. unbounded cycles (F2): hangs or is OOM-killed
faultbound-wt analyze reference/spike_netlists/v2.json --config product/src/faultbound_wt/examples/threat.toml --max-flips 1 --cycles 1000000000
# 3. the "310 passed" claim after the documented install (F3)
python3 -m venv v && v/bin/pip install './product[test]' && v/bin/pytest -q product/tests    # 308 passed, 2 skipped
# 4. editing the engine and reading only the summary line (F4)
echo '# x' >> scripts/synth.sh && python3 ci/check_reproduce.py --rerun | head -3; echo $?     # WARNING, but 36/36 and exit 0
# 5. lost verdict (F5)
faultbound-wt analyze product/examples/pin_lock/pin.v --top pin --config product/examples/pin_lock/pin.toml --report /nope/x.json   # exit 4
# 6. pip install ./product inside the tree leaves product/build and product/src/*.egg-info (the tree is clean of them now)
# 7. coordinated edit of results + per-run files + hashes passes the default check (documented limit, RT2 T2)
# 8. different Yosys: apt 0.33 vs conda 0.38 give different V2 netlists (README says so); --rerun on another Yosys can mismatch
# 9. hostile .v with `include of another file (Yosys unsandboxed, F10, INFERRED)
```

## Not done
- GitHub Action not run on GitHub (shell simulation only; `upload-sarif` step not simulated). No fuzz of the Verilog frontend. No check of `integrations/byo_adapters.py` (subprocess uses an argv list, read only). Real-tree bundle not built. The `make` targets were not run by design. Timings are single runs on a shared machine.
