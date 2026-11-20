# RT2 red-team report, wave 2

Scope: the NEW code: T3 sequential-counter at-most-k, PS4/PS5 scope options, report writers, `ci/check_reproduce.py`, config/Verilog injection.
All runs on copies under `/tmp/work_rt2/` (`p` = tar-pipe copy, `venv` = `pip install ./product`, `fz`/`t` = scratch). Nothing was run in the tree; no `make`; the tree has no `product/build` or egg-info (checked). Modelled bit flips only; nothing here is a hardware statement.
Labels: MEASURED = I ran it and saw the output. INFERRED = read from code, not run.
Files here: `fuzz_amk.py` (differential fuzz + oracle + witness replay), `mk_netlists.py` (the degenerate/hostile netlists used).

## Wave-1 findings (RT_REPORT.md): status now (all MEASURED on the current code)
| RT finding | status |
|---|---|
| A1/A2 multi-driver, A3 `x` init, A6 crash exit 1, A7 recursion, A8 KeyError, C1 JUnit control chars, D1 duplicate rows | fixed by H1 (clean `error:` exit 3 / 4; JUnit parses with U+0001; check_reproduce rejects duplicate rows and cross-checks hashes). Spot-checked: hostile JUnit parses, `$_BUF_` and latches give exit 3. |
| A4/A5 (glitchsat.py width / bounds) | fixed in H1 (not re-tested here beyond the CLI). |
| A9 (all non-clk inputs free) | still a documented semantics decision. |
| D1 (not tamper-evident) | partly improved, see section 4: still NOT tamper-evident against anyone who can edit the tree. |

## Summary table of NEW findings
| # | Finding | Sev | Label |
|---|---|---|---|
| N1 | `[netlist] top` / `--top` / Verilog file name are pasted into the Yosys `-p` script: Yosys `exec` runs an arbitrary command | HIGH | MEASURED |
| N2 | `check_reproduce.py` (default and `--rerun`) is fooled by a coordinated edit or a tampered engine; the summary line says "36/36 match" even with a RERUN MISMATCH | MED | MEASURED |
| N3 | `--scope-sweep` / `--sweep-widths` silently ignore `--report` and `--badge` (no file written, no warning) | MED | MEASURED |
| N4 | `--init free_nongoal` can be vacuous: empty allowed set gives NO_ATTACK_UP_TO_BOUND with no warning | MED | MEASURED |
| N5 | Concurrent writers to the same `--report` path produce corrupt JSON (non-atomic write) | MED | MEASURED (1 of 40 pairs) |
| N6 | `--consumer-bits` string form is a BIT LIST, TOML int is a MASK: `"3"` = bit 3, `3` = bits 0,1; `"0"` = bit 0 but int `0` is an error | LOW-MED | MEASURED |
| N7 | `--consumer-bits "0-100000000"` burns CPU for minutes (unbounded range loop, big-int mask) | LOW-MED (DoS) | MEASURED |
| N8 | Counter encoding sized by `k`, not by number of fault sites: `--max-flips 500` takes 54 s, 3000 times out; no cap | LOW-MED (perf DoS) | MEASURED |
| N9 | `--timeout-s`: killed worker leaves its grandchild `yosys` running (ppid 1, uncapped) and a `/tmp/fbwt_*` dir; parent SIGKILL/SIGTERM orphans the worker and leaks `/tmp/fbwt_w_*` | LOW-MED | MEASURED |
| N10 | Verilog input + any later error (bad port, config error) leaks `/tmp/fbwt_*` (tmp dir not removed on exceptions) | LOW | MEASURED (8 left-overs from earlier agents + 1 mine) |
| N11 | Sweep CSV: net/port names starting with `=` are not neutralised (formula injection) | LOW | MEASURED |
| N12 | Verilog path with a space fails (`Can't open input file 'v/my'`) | LOW (functional) | MEASURED |
| N13 | `--rerun` on a mismatched top crashes with a traceback and exit 1 (= EXIT_MISMATCH) | LOW | MEASURED |
| N14 | `"1-"` accepted as bit 1 (`hi = int(hi or lo)`) | LOW | MEASURED |
| none | T3 counter vs legacy vs brute force: 0 disagreements, 0 bad witnesses | OK | MEASURED |
| none | report writers with hostile names: JSON/SARIF/JUnit parse, badge carries no netlist text | OK | MEASURED |

## 1. T3 sequential counter: differential fuzz (MEASURED)
`fuzz_amk.py SEED COUNT` (venv python): random netlists with 1-3 sig bits (+ optional second free input `aux`), 0-3 flops (random init attr), 2-8 gates (AND/OR/XOR/NOT/MUX, constants, outputs wired to inputs/Q/constants), 1-4 output bits, N in 1..5, k in {0,1,2,3,3}, random key/goal, consumer mask (1/3 of cases), `input_sites` (35%), init mode known/arbitrary/free_nongoal.
Per netlist: product `_engine.solve` AND `scripts/glitchsat.py solve` (plain features only) x `amk` counter/legacy x reduce none/coi/full.
Checks: (a) counter vs legacy verdict AND min-fault count equal; (b) vs a brute-force oracle with its own simulator (enumerates all fault sets <= k over gate outputs, flop Q, optionally input nets, every input != key, every init state; free_nongoal drops pairs whose fault-free run accepts) when tractable; (c) every returned witness replayed with the independent simulator: <= k distinct flips, `sig != key`, goal reached (masked), init state from `init_ones`, free_nongoal fault-free run does not accept.
Seeds 1-4 (80 each) and 11-14 (200 each): **1120 netlists, 8406 solver runs, oracle on 1076 netlists, 0 verdict/min-fault disagreements, 0 crashes, 0 bad witnesses.** Outcomes: about 76% attack, 24% no-attack. Limits: tiny netlists (<= ~14 sites), the oracle shares my reading of the fault model (flip applies to that cycle's read; flop-Q flip does not change stored state), no multi-gigabyte cases, k=3 only on small site counts. This validates the encoding, not the model.
Related: a k larger than the site count is fine in the fuzz (k=3 with 2-3 sites). But see N8 for large k.

## 2. PS4/PS5 options (MEASURED unless noted)
Setup: bundled `examples/v2.json` + `threat.toml`, plus tiny netlists in `mk_netlists.py` (pass-through, constant output, gates without flops, `$_BUF_` cells, flop with/without `init`).
- `--consumer-bits`: `0x0` exit 3; `-1`, `-0x1`, `7-0`, `0,,1`, `0x`, `abc`, `""`, `1e3`, `0b101`, `1_0` exit 3 with a clear message; `0x1FF`, `0xFFFF...` exit 3 ("beyond the 8-bit output"); `0-7`, `0xFF` = no mask; `" 0x0F "`, `0X0f` accepted. TOML: `[]`, `0`, `[-1]`, `[true]`, `1.5`, `[1.0]` exit 3.
  - **N6 (LOW-MED)**: CLI/TOML-string `"0"` means bit 0 (ATTACK, 0 flips on v2), TOML int `0` is an error; `"255"` means bit 255 (error text prints a 2^255 mask); TOML int `255` means mask 0xFF = all bits; `"3"` = bit 3 only, TOML `3` = bits 0-1. A reviewer who types a decimal mask gets a different, silent, narrower scope (the scope block prints the effective mask, so it is visible, but only if read). Repro: `faultbound-wt analyze examples/v2.json --config threat.toml --max-flips 1 --consumer-bits 0` -> ATTACK_FOUND "NONE NEEDED". Fix: reject bare decimal strings (require `0x` or a `bits:` prefix / list), or document and make int and string agree.
  - **N14**: `--consumer-bits "1-"` = bit 1 silently. Fix: require both ends of a range.
  - **N7 (LOW-MED)**: `--consumer-bits "0-100000000"` and `"0-99999999999999"`: no result after 60 s, 59 s CPU (killed by `timeout`). Repro: `timeout 60 faultbound-wt analyze examples/v2.json --config threat.toml --consumer-bits 0-100000000`. Fix: check `hi` against a sane max (e.g. 4096) before the range loop, or cap against the port width after knowing it.
- `--input-sites all`: pass-through netlist: 1 flip of input net (`3@2`), exit 1; netlists with only gates/flops fine; `$_BUF_` is a clean exit 3 (unsupported cell), also with `--input-sites all`. No crash on constant/pass-through outputs.
- `--init arbitrary`: constant-output and flop designs give 0 flips with the "no reset" text, as documented. `--init free_nongoal` with and without `init` attributes: gates-only design 1 flip, flop designs 1 flip (`q@1` / `q@0`).
  - **N4 (MED)**: constant-output design (`b_const.json`, output 0b10 = accept value 2): known init gives ATTACK 0 flips; `--init free_nongoal` gives `NO_ATTACK_UP_TO_BOUND`, exit 0. The allowed power-up set is empty (every run accepts), so the verdict is vacuously "no attack" and a CI would go green. Repro: `faultbound-wt analyze b_const.json --config t.toml --init free_nongoal` (files in `mk_netlists.py`, config `legitimate_value=2 bad_value=2 top=t`). Fix: when free_nongoal is used, first check satisfiability of the init/inputs constraint with zero faults (`Not(Or(unroll(False)))` alone); if unsat, report CONFIGURATION_PROBLEM / a distinct "no admissible power-up state" verdict.
- `--count-rule branch`: exit 3 "NOT IMPLEMENTED" (also TOML). OK.
- `--scope-sweep`, `--sweep-widths` on pass-through / constant / gates-only / flop-only netlists: tables produced, no crash; sweep exit 1 if any cell has an attack. Exit 3 for mask beyond width.
  - **N3 (MED)**: `faultbound-wt analyze c_gates.json --config t.toml --scope-sweep --report sw.json --badge sw.badge.json` -> neither file exists (the sweep branch returns before the report/badge code), no warning. A CI step that uploads `sw.json` finds nothing, or uploads a stale file from a previous run. Fix: error out (exit 3) when `--report/--badge` are combined with sweep modes, or write a sweep report.
  - **N11 (LOW)**: a port named `=cmd|"calc"!A0é` gives a CSV cell `"=cmd|'calc'!A0é==0x2"` (quotes replaced, `=` kept). Fix: prefix `'` to cells starting with `= + - @ \t \r`.
- `--timeout-s` (worker kill), run with `FAULTBOUND_AMK=legacy` so the 3-flip V2 case is slow enough (about 5 s): `--timeout-s 1` returned in 1.14 s wall, exit 2, UNKNOWN_TIMEOUT, `timed_out: true`, reports and badge written ("unknown <=3 flips"), scope block carries `wall_clock_timeout_s`. No zombie (`ps` shows no leftover worker). Good.
  - **N9 (LOW-MED)**: with a Verilog input (a 32-bit multiplier, yosys about 4 s) `--timeout-s 1`: the parent kills only the worker; `ps` right after shows `yosys -q -p read_verilog ...` with ppid 1 still running (it finishes on its own, but its 600 s `subprocess.run` timeout died with the worker), and a `/tmp/fbwt_*` dir is left. Killing the PARENT with SIGKILL (or `timeout`'s SIGTERM, INFERRED for SIGTERM) leaves the worker running with ppid 1 and `/tmp/fbwt_w_*` behind. Repro: `faultbound-wt analyze v/big.v --top big --config big.toml --timeout-s 1 ...; ps -eo pid,ppid,cmd | grep yosys`. Fix: `Popen(..., start_new_session=True)`, `os.killpg` on timeout, same for the yosys `subprocess.run` (own process group), `try/finally` and a SIGTERM handler for tmp cleanup; Linux `prctl(PR_SET_PDEATHSIG)` in the worker.
  - **N10 (LOW)**: `analyze v/m.v --top m --goal-out nonexist` -> clean `error:` exit 3 but `/tmp/fbwt_*` count rose 8 -> 9 (and again 11 -> 12 on a bad `bad_value`). `analyze()` only removes `tmp` on the normal and honest-fail paths. Fix: wrap in `try/finally`.
- **N5 (MED)**: two concurrent runs with `--report race.json` (one hostile-name run, one short run): 1 of 40 pairs left invalid JSON. The mechanism is deterministic (`open(path,'w')` in each, short write lands over a longer one without truncation: `{"s":1}\n"xxxx..."`, MEASURED in `mech.json`). Fix: write to `path.tmp.<pid>` and `os.replace`.
- **N8 (LOW-MED)**: `solve()` builds the counter for `kcap = k`, `O(sites x k)` clauses regardless of the number of sites: V2 `--max-flips 50` 3.0 s, `--max-flips 500` 54 s, `--max-flips 3000` no result in 60 s (4 GB ulimit not hit). Legacy PbLe at 3000 also did not return within 120 s (stopped). Fix: `kcap = min(k, len(allf))` (a bound above the site count is vacuous) and validate `max_flips` against a sane maximum in `validate()`.
- **N13 (LOW)**: `check_reproduce.py --rerun` with a netlist whose module name differs -> uncaught `NetlistError` traceback; Python exit 1 equals EXIT_MISMATCH. Fix: wrap the rerun loop; report ERROR rows and exit 3/4.

## 3. Report writers with hostile names (MEASURED)
Net name (g_hostile.json) = `n</script><img src=x onerror=alert(1)>"'&amp;]]>--` + U+0001 + U+001F + U+202E + U+2028 + `${jndi:x}%s` + newline + `../../etc/passwd`, attack on that net, `--report h.json --report h.sarif --report h.junit.xml --badge h.badge.json`:
- JSON and SARIF load with `json.load` (control chars escaped). JUnit parses with `xml.etree`; no raw `<script` or `]]>`; control chars replaced by U+FFFD. Badge JSON parses and contains only numbers, the fixed label and `(scoped)`, no netlist text. Terminal output escapes control/bidi (`\x01`, `‮`).
- New scope block: carries port names, option values and the free-input list from the netlist (`input_treatment`), all JSON-escaped / XML-escaped; the JUnit `scope_*` properties go through `quoteattr` plus `_xml_clean`. No injection found.
- Remaining (unchanged from wave 1, INFERRED): SARIF/JSON keep raw names, so a consumer that renders them as HTML/Markdown is the risk; SARIF `informationUri` is `about:working-title-tbd`; the dashboard path was not re-tested. New: N3 (sweep writes nothing) and N11 (CSV formula).

## 4. Forged inputs vs `ci/check_reproduce.py` (MEASURED on `/tmp/work_rt2/p`)
Baseline: default mode `36/36 rows match ... 0 problem(s)`.
| attack | default mode | `--rerun` |
|---|---|---|
| T1: replace `reference/spike_netlists/v2.json` by v0.json | DETECTED (4 problems: input hash != hash recorded in run file) | not run |
| T2: T1 plus rewrite `design_sha256_16` in the 4 v2 per-run files to the new hash | **PASSES, 0 problems** | rerun then crashes (top `v2` missing, N13); a verdict-preserving replacement netlist would pass (INFERRED, not built) |
| T4: `scripts/glitchsat.py` `run_check` replaced by a lookup of `ci/expected_reproduce.json` | n/a | **PASSES, `36/36 rows match (engine re-run); 0 problem(s)`** |
| T5: flip `v2 spike k3` to NO_ATTACK in `expected_reproduce.json`, summary and per-run file | **PASSES, 0 problems** | DETECTED: `RERUN MISMATCH v2|spike/given-netlist|k3`, exit 1 |
What is tamper-evident now: accidental or one-sided edits (summary vs per-run file vs input hash vs expected file; duplicate/missing/extra rows), and, only with `--rerun`, edits to results/expected that the real engine disagrees with.
What is NOT: anything where the attacker can edit several files in the same tree (T2), the engine file itself (T4; `-v` prints its SHA-256 but nothing compares it to anything unless you pass a manifest that was produced from the same tree), the RTL/netlist as long as the verdicts still match, and the 16-hex-char (64-bit) hash prefix. `--rerun` shows "this engine on this tree reproduces the table", nothing more (the script's own docstring says so; that statement is correct).
- **N2 (MED)**: also the final line counts `RERUN MISMATCH` rows as matching: `36/36 rows match (engine re-run); 1 problem(s)` for T5. Only the `MISMATCH`/`MISSING ROW` tags are subtracted. Fix: count all problem tags that name a row.
- Proposed fix: publish the SHA-256 of `expected_reproduce.json`, `glitchsat.py` and the inputs out of band (signed tag / release notes) and have the script take it as an argument (`--expect-manifest-sha256 HASH`); run `--rerun` in CI from a fresh checkout of a pinned commit, not from a workspace the job can modify; compare full 64-hex hashes.

## 5. Injection through config and file names (MEASURED)
- **N1 (HIGH)**: `runner.synthesize` does `subprocess.run(["yosys","-q","-p", YOSYS_PLAIN.format(v=verilog, top=top, out=out)])`; Yosys splits `-p` on `;`, and its `exec` command runs a program. Reproducers (canary files, work copy):
  1. TOML: `[netlist]\ntop = "m; exec -- touch /tmp/work_rt2/pwned3; hierarchy -top m"` then `faultbound-wt analyze m.v --config inj.toml` -> `/tmp/work_rt2/pwned3` created (then `error: top ... not in netlist modules` exit 3; the command had already run).
  2. CLI: `--top 'm; exec -- touch /tmp/work_rt2/pwned1; hierarchy -top m'` -> `pwned1` created.
  3. File name: `cp m.v 'm.v; exec -- touch pwned_fn; .v'`; `faultbound-wt analyze 'm.v; exec -- touch pwned_fn; .v' --top m` -> `pwned_fn` created in the cwd (error `No such command: .v` afterwards).
  Impact: whoever controls `threat.toml` or a Verilog file name in a PR gets command execution in the CI job that runs `faultbound-wt` (the shipped GitHub Action passes `config` and `top` through unchanged). The shell `!` form is rejected by this Yosys (0.33), but `exec` works. `scripts/synth.sh` / `glitchsat.py check x.v --top ...` has the same pattern (`yosys -q -p "read_verilog $1; hierarchy -top $2; ..."`, INFERRED from the source, the product path measured). Fix: validate `top` against `^[A-Za-z_\\$][A-Za-z0-9_\\$.]*$` and reject any Verilog path containing `;`, newline, space, quote or backslash; better: write a Yosys script file with the path passed via `read_verilog -- <path>` after the path is checked, or copy the source to a temp file with a fixed safe name (`src.v`) and pass only that; run Yosys with a cleaned environment and no network.
- **N12 (LOW)**: `analyze "v/my file.v"` -> `yosys synthesis failed: Can't open input file 'v/my'`. Same root cause; names with `'` or `"` worked.
- Other TOML fields: `include/exclude` go only to `fnmatchcase`; `output`/`input`/`kinds` are checked against ports/enum; `solver.timeout_ms` is checked non-negative int; unknown keys rejected. No path fields exist except `top`. `--report`/`--badge`/`--sweep-out` write wherever the caller says (and follow symlinks); that is the caller's authority, not an injection.

## Not done
- No Verilator/other-tool differential; no fuzz of the Verilog path itself; no netlist with more than ~14 fault sites in the oracle (large cases compared only through counter vs legacy in the earlier T3/R27 runs, not by me).
- `check_reproduce.py` with a verdict-preserving but different netlist was not constructed (INFERRED pass). `--manifest` mode not attacked.
- Dashboard XSS (C2 of wave 1) not re-run; GitHub Action not run; SIGTERM-to-parent behaviour of `--timeout-s` inferred from the SIGKILL result.
- The fuzz covers counter/legacy equivalence on tiny designs; the timing claims (N8) are single runs on a shared 4-core machine.
