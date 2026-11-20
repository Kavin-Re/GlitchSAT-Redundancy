# Quickstart (about 10 minutes)

Working package name `faultbound-wt`; project title GlitchSAT; licence Apache-2.0.

You will check a small digital lock against **modelled** bit-flip faults. Nothing here is a physical glitch, and no hardware is involved.
A result is *bounded result under this model; not a proof of security*.

## What to install, in 5 lines
```
python3 -m venv .venv && . .venv/bin/activate     # Python 3.11+
pip install ./product                              # pulls z3-solver from PyPI; add [test] for pytest
sudo apt install yosys                             # only if you start from Verilog (or use the Dockerfile below)
faultbound-wt example-path                         # sanity check: prints the bundled examples folder
faultbound-wt analyze "$(faultbound-wt example-path)/v2.json" --config "$(faultbound-wt example-path)/threat.toml" --max-flips 2
```

## 0. What you need
- Python 3.11 or newer. Internet only to download the solver (`z3-solver`) from PyPI.
- Optional, only for step 4 (your own Verilog): `yosys` (for example `sudo apt install yosys`).

## 1. Install (2 minutes)
From the repository root (the folder that contains `product/`):
```
python3 -m venv .venv
. .venv/bin/activate
pip install ./product
```

## 2. Run the bundled example (1 minute)
```
EX="$(faultbound-wt example-path)"
faultbound-wt analyze "$EX/v2.json" --config "$EX/threat.toml" --max-flips 2
echo "exit code: $?"
```
Expected: `NO_ATTACK_UP_TO_BOUND`, exit code `0`. Now allow one more flip (takes several seconds):
```
faultbound-wt analyze "$EX/v2.json" --config "$EX/threat.toml" --max-flips 3
echo "exit code: $?"
```
Expected: `ATTACK_FOUND`, a list of 3 nets and cycles, exit code `1`.

Exit codes: `0` no attack up to the bound, `1` attack found, `2` solver gave up, `3` your input or config is wrong, `4` internal error.

## 3. Read the output
- `minimum attack:` the smallest set of `net@cycle` flips the solver found.
- The `scope:` lines say what the answer is about: the goal, how inputs are treated, the assumed start state, how a fault is counted,
  the bounds and the SHA-256 of the exact netlist. Always keep them next to the verdict.
- `scope` also appears in JSON, SARIF and JUnit reports (`--report out.json --report out.sarif --report out.junit.xml`).

## 4. Try your own Verilog (about 5 minutes)
A 4-bit PIN lock is in `product/examples/pin_lock/` (real PIN = 10, goal = `unlock` becomes 1 with any other PIN).
```
faultbound-wt analyze product/examples/pin_lock/pin.v --top pin --config product/examples/pin_lock/pin.toml
```
Expected: `ATTACK_FOUND` with 1 flip (exit 1): flipping one gate output for one cycle opens the lock. That is the finding.
Edit `pin.toml`: change `legitimate_value = 10` to `5`. The tool now stops with exit 3 and
`CONFIGURATION PROBLEM: the honest input does not reach the goal`: the honest PIN must open the lock in the fault-free design, otherwise
the result would be meaningless. Set it back to 10.

## 4b. Scope options and the scope sweep
The same netlist gives a different answer when the *scope* changes. These options make the scope explicit; each one is also a config key
(see `product/examples/scope_sweep/scope.toml`) and is printed as `scope: options:` and stored in `scope.options` of every report
(schema stays `faultbound-wt-report/1`, the keys are additions). Defaults are the old behaviour.

| option | meaning | default |
|---|---|---|
| `--goal-out PORT`, `--accept-value N` | which output the goal is judged on (`boot_word` result word or the 1-bit `boot_ok`) and its accept value | config / `boot_word`, `0x96` |
| `--consumer-bits MASK` | the consumer reads only these bits: goal holds when they equal the accept value on those bits. **Syntax (H2, unambiguous):** a MASK is `0xF0`, `0b1010` or a plain decimal number (`15` = bits 0..3, in the CLI and in TOML alike; TOML int `15` = same); a BIT LIST is `bits:3,5` or `bits:0-3,6` or `[3,5]` (TOML list `[3,5]` too; ranges need both ends). A bare number is never a bit index (`3` = mask 3 = bits 0 and 1; bit 3 alone is `bits:3` or `0x8`). The old bare list `0-3,6` is still read as a bit list. Bit indices above 4095 are refused at once; bits beyond the output width: exit 3 | all bits |
| `--input-sites {none,all}` | `all`: every primary-input bit is also a fault site (one flip of the input net, seen by all its fanout) | `none` |
| `--init {known,arbitrary,free_nongoal}` | `arbitrary`: flops may power up in any state (no reset); expect 0 flips for every design, the report says so. `free_nongoal` (PS5, B2 semantics): any power-up state from which the fault-free run with the same inputs never accepts, so at least 1 flip is needed | `known` |
| `--timeout-s SEC` | hard wall-clock limit for the whole run (PS5). The work runs in a worker process that is killed at the deadline, so a slow model build cannot overrun it. Exit 2, verdict `UNKNOWN_TIMEOUT`, `timed_out: true`, note says it is NOT 'no attack' | none |
| `--count-rule {stem,fanout,fanout_pins,fanout_gates,branch}` | PS6: how a flip is counted (see 4c). `fanout` = `fanout_pins`. `branch` is NOT IMPLEMENTED: exit 3 | `stem` |

Worked example on the bundled spike V2 (6 cycles; each line MEASURED in this session, see `research/c4/ps4/PS4_REPORT.md`):
```
EX="$(faultbound-wt example-path)"; A="analyze $EX/v2.json --config $EX/threat.toml"
faultbound-wt $A --max-flips 3                                    # full word: ATTACK_FOUND, 3 flips (2 flips: no attack)
faultbound-wt $A --max-flips 1 --goal-out boot_ok --accept-value 1   # boot_ok: 1 flip
faultbound-wt $A --max-flips 2 --input-sites all                  # 1 flip (an input net)
faultbound-wt $A --max-flips 2 --init arbitrary                   # 0 flips: no reset, not a fault result
faultbound-wt $A --max-flips 3 --consumer-bits 0x6A               # a 4-bit consumer: 3 flips
faultbound-wt $A --max-flips 3 --consumer-bits 0x8D               # another 4-bit consumer: 1 flip
```
**Scope sweep** runs the matrix goal x input-sites x init and prints one table (cost = minimum flips found; `>k` = none up to k;
`unknown` = the solver hit the per-cell timeout, which is NOT "no attack"):
```
faultbound-wt $A --max-flips 3 --scope-sweep --sweep-masks 0x0F,0x6A --cell-timeout-ms 120000 --sweep-out sweep.json   # or .csv
```
Rows are the configured goal, each `--sweep-masks` mask, and `boot_ok` if the design has it. Exit code: 1 if any cell found an attack, else 2 if any
cell is unknown, else 0; 3 if the honest input fails for some goal. The timeout is the solver's; building a very large model is not interrupted.
**Consumer width curve** (PS5): `--sweep-widths` (alone or with `--scope-sweep`) prints the minimum flips if the consumer reads only the lowest n bits of the goal output, n = 1..W, in the one scope given by `--input-sites`/`--init`:
```
faultbound-wt $A --max-flips 3 --sweep-widths --sweep-out widths.csv
```
On the spike V2 (6 cycles, k<=3) this gives n=1..8: 0,1,1,2,2,3,3,3 (equal to the M1 table for the masks 0x01..0xFF). Contiguous groups per comparator copy are not offered; use `--sweep-masks`. `--timeout-s` also bounds a sweep (no partial table is printed when it fires).
Warning text: values given by `--goal-out`/`--accept-value` are no longer listed as "NOT set"; the genuinely unset keys are named with the default in use.
A "0" under `--consumer-bits` can mean the idle state already looks like acceptance on those bits (M1 calls these collisions); the report says 0 flips needed.

## 4c. Counting rules and the synthesis-flow sweep (PS6)
Two of the axes a verdict depends on were research scripts only; they are now in the tool. All numbers below are MEASURED on this repository (commands in `research/c5/ps6/PS6_REPORT.md`); faults are modelled bit flips.

**Counting rule** (`--count-rule`, config key `faults.count_rule`). `stem` (default): flipping a net costs 1, however many gates read it. `fanout_pins` (alias `fanout`): a flip of a net costs the number of gate input pins, flop D pins and output-port bits it feeds (at least 1; a gate that reads the same net on two pins counts two), i.e. the same as flipping every branch separately. `fanout_gates`: the same without output-port bits. These are the two rules of `research/c3/rep` (`fanout_pins`, `fanout_gates`) and of `docs/edu/tools/edu_scope.py`. Under a fanout rule `--max-flips` is a **cost budget** (sum of the costs of the flipped nets); the scope block says so, `min_faults` stays the number of flipped nets, and the report adds `min_cost` and a per-fault `cost` (additions only; stem reports are unchanged). `branch` (partial-branch flips) is not implemented. Spike V2, boot_word, 6 cycles: stem 3, fanout_pins 3, fanout_gates 3; with `--input-sites all`: stem 1 but fanout_pins 3 (an input net feeds several pins).
```
faultbound-wt analyze product/src/faultbound_wt/examples/v2.json --top v2 --max-flips 3 --count-rule fanout
faultbound-wt analyze $A --scope-sweep --max-flips 3 --sweep-count-rules stem,fanout_pins,fanout_gates --sweep-out table.csv
```
`--sweep-count-rules` adds the counting rule as a third axis of `--scope-sweep` (columns `... rule=...`; JSON/CSV cells carry `count_rule`).

**Synthesis sweep** (`--synth-sweep`, Verilog `.v` plus `--top`, needs `yosys` on PATH, otherwise exit 3 with a message). The source is synthesized by a small documented set of Yosys flows and the minimum flips of each netlist are computed, because one design gives different netlists (and different minimum flips) under different synthesis choices (`research/c2/e2_variance`). Built-in variants: `plain` (the project flow of `scripts/synth.sh`), `plain_opt_merge` (opt_merge after flatten), `flatten_before_abc`, `abc_fast`, `abc_no_mux`, `opt_flow` (Yosys `synth` + dffunmap), `plain_keep_off` and `opt_flow_keep_off` (`(* keep *)` stripped, `keep_hierarchy` kept). Each script is generated from this template (one command per line, run as `yosys -q -s flow.ys` in a private directory that holds the source as `design.v`; it is stored in the JSON output):
```
read_verilog design.v
hierarchy -top TOP
<pre>      plain: proc; opt_clean; techmap; opt_clean   | opt: synth -top TOP; dffunmap | flatten-first: proc; setattr -mod -unset keep_hierarchy *; flatten; opt_clean; techmap; opt_clean
<abc>      abc -g AND,OR,XOR,MUX   (or -fast, or without MUX)
<post>     opt_clean; setattr -mod -unset keep_hierarchy *; flatten; opt_clean; techmap; opt_clean   (+ opt_merge for plain_opt_merge)
write_json netlist.json
```
```
cd product/examples/synth_sweep
faultbound-wt analyze v2.v --top v2 --max-flips 4 --synth-sweep --synth-variants variants.toml --sweep-out ss.json
```
It prints per variant the netlist SHA-256, gate and flop counts, the Yosys version and the minimum flips (`unknown` after the per-cell timeout, `unsupported` if the engine cannot read the netlist, `synth-failed` on a Yosys error), then `verdict changes across N variants: min flips ranged a..b`. `expected_output.txt` in the example folder is the output of the command above (Yosys 0.33: 1..2 flips over 10 variants; baseline 85 gates 2 flips, opt_merge 63 gates 1 flip). Notes: byte-identical netlists are analysed once (marked `*`); the hash depends on this flow (the source is read as `design.v`), so it differs from the hash of `analyze v2.v` and of other scripts: compare hashes only within one tool and Yosys version; single-file Verilog only (`include is not copied); `--synth-select a,b` runs a subset; `--sweep-out` takes `.json` or `.csv`; `--synth-sweep` cannot be combined with `--scope-sweep`. Exit codes follow the sweep: 1 if any variant has an attack within the bound, 2 for unknown/timeout, 0 otherwise, 3 for input errors.
**Custom flows** (`--synth-variants FILE`, `.toml` with `[[variant]]` tables or `.json` `{"variant": [...]}`): fields `name`, `description`, `extends` (a built-in, default `plain`), `pre`, `abc`, `post` (Yosys commands separated by `;`), `strip_keep`. **Allow-list (H2, replaces the PS6 deny-list):** a `pre`/`post` step may contain ONLY `proc`, `opt_clean [-purge]`, `clean [-purge]`, `opt [-fast|-full|-purge]`, `opt_merge [-share_all] [-nomux]`, `opt_expr [-mux_undef|-mux_bool|-fine|-full]`, `opt_muxtree`, `opt_reduce [-fine|-full]`, `opt_dff`, `flatten`, `techmap` (no `-map`), `dffunmap`, `synth [-flatten] [-noabc] [-top NAME|{top}]` and exactly `setattr -mod -unset keep_hierarchy *`; the `abc` step may contain ONLY `abc [-fast] [-g AND,OR,XOR,MUX,...]` (gate names from AND NAND OR NOR XOR XNOR ANDNOT ORNOT MUX NMUX AOI3 OAI3 AOI4 OAI4) or be empty. Any other command or option (`shell`, `exec`, `script`, `plugin`, `tee`, `read_*`, `write_*`, `abc -script/-exe/-liberty`, `techmap -map`, `!...`, quotes, `#`) is refused with exit 3 before Yosys starts. Custom variants files are still TRUSTED INPUT: they are written by whoever runs the tool, and the allow-list is a safety net against mistakes and hostile pull requests, not a security boundary for Yosys features that are on the list. Only pass variant files you trust. The sweep samples a few synthesis choices; it does not cover all of them, other Yosys versions, or place-and-route.

## 4d. Limits, reports of sweeps, timeouts, safe names (H2)
- **Maximum `--max-flips` is 64** (`faults.max_flips` too); more is exit 3 with a message. The at-most-k counter is built for min(k, number of fault items), so a k above the item count costs the same as "any number of flips"; before H2 `--max-flips 500` took 54 s on the spike V2 (MEASURED by RT2).
- **Maximum `--cycles` is 200** (`faults.cycles` too); more is exit 3 with a message (H4/F2: `--cycles 1000000000` used to run until the kernel OOM-killed it). A `--report`/`--badge` file in a directory that does not exist is exit 3 before the solve (H4/F5).
- **Verilog top names and file names** are validated before they reach Yosys: `top` must match `[A-Za-z_$][A-Za-z0-9_$]*` (escaped identifiers are refused); a Verilog path must not contain control characters, quotes, backtick, `;`, backslash or `#`, and must not start with `-` (exit 3). Spaces are allowed. Yosys runs from a fixed script file (`yosys -q -s flow.ys`), without a shell, with a minimal environment, in its own process group.
- **Sweeps and `--report`/`--badge`:** `--scope-sweep`, `--sweep-widths` and `--synth-sweep` write their table to every `--report FILE.json` / `FILE.csv` (same content as `--sweep-out`). `--badge`, `.sarif` and `.junit.xml` are NOT supported with a sweep (a table has no single verdict): exit 3, nothing written. CSV cells that start with `=`, `+`, `-`, `@`, tab or CR get a leading `'` (spreadsheet formula injection).
- **Atomic writes:** every report, badge and sweep file is written to a unique temp file in the same directory and moved into place with `os.replace`, so concurrent writers (or a crash) cannot leave half a JSON document; the last writer wins. A symlink at the target is replaced, not followed.
- **`--init free_nongoal`** on a design whose goal output is constant or always accepting: exit 3 "goal output is constant: nothing to attack" (before H2: a vacuous NO_ATTACK_UP_TO_BOUND, exit 0).
- **`--timeout-s`:** the worker runs in its own process group; at the deadline the whole group (worker, yosys, abc) is killed and the temporary directories are removed. If the CLI itself is killed with SIGTERM/SIGHUP its cleanup runs; if it is killed with SIGKILL the worker notices within about 0.5 s and kills its group. Verilog/config errors remove their `/tmp/fbwt_*` directory.
- **`ci/check_reproduce.py`:** a RERUN MISMATCH is a failed row (never counted in "N/36 rows match"), a crashing engine row is `RERUN ERROR` (exit 4), the output states what is and is not tamper-evident, and `--rerun` warns when `scripts/glitchsat.py` or `scripts/synth.sh` differ from the built-in SHA-256 manifest (`--strict-engine` makes that a failure). Coordinated edits of several files in the tree are only caught by comparing with an external copy.

## 5. What the tool cannot read
Only plain gates (AND, OR, XOR, NOT, MUX) and rising-edge flops without reset or enable pins after Yosys synthesis. Flops with
an **asynchronous** reset (`always @(posedge clk or posedge rst)`) are refused with exit 3 and an explanation: use a synchronous reset.
`faultbound-wt analyze product/examples/pin_lock/pin_async.v --top pina --config product/examples/pin_lock/pin.toml` shows the refusal (exit 3).

## 6. Use it in CI (example workflow)
`product/examples/github-actions-sarif.yml` is an example workflow that runs the tool and uploads the SARIF file. It has never been run;
copy it into `.github/workflows/` yourself if you want it.

## 7. Docker, pre-commit, pytest, badge
**One-command Verilog to netlist.** `product/scripts/yosys_flow.sh design.v TOP out.json` runs the documented Yosys recipe, prints the Yosys
version and the netlist SHA-256 (a verdict belongs to that one hash), and exits 3 with a clear message if `yosys` is missing. H2: `TOP` must be a plain identifier and the file names must not contain control characters, quotes, backtick, `;`, backslash or `#` or start with `-` (exit 3); they are written as quoted tokens into a Yosys script FILE (`yosys -q -s`), never pasted into a `-p` string or a shell line; names with spaces work.

**Docker (built and run locally only, 2026-11-20, with the sandbox proxy's CA added to a COPY of the Dockerfile; not built on a normal network).** `docker build -f product/Dockerfile -t faultbound-wt:dev .` then
`docker run --rm -v "$PWD":/work faultbound-wt:dev analyze /work/netlist.json --config /work/threat.toml`. Yosys version = whatever Debian ships; the report records it.

**pre-commit (local).** `product/.pre-commit-hooks.yaml` defines hook `faultbound-wt` (entry `faultbound-wt-hook`, installed with the package). Use it from your own repo with a local hook:
```
repos:
  - repo: local
    hooks:
      - id: faultbound-wt
        name: faultbound-wt bounded fault check
        entry: faultbound-wt-hook --config threat.toml --max-flips 2
        language: system
        files: '^build/.*\.json$'
        pass_filenames: true
```
It runs `analyze` once per committed netlist and returns the worst exit code (0/1/2/3/4). Only list netlists you want checked in `files`.

**pytest.**
```
from faultbound_wt.pytest_helper import assert_no_attack
def test_lock():
    assert_no_attack("build/pin.json", goal=("unlock", 1), k=1, cycles=4, attacker_input="code", legitimate_value=10)
```
On an attack the AssertionError lists the minimal fault set and the scope block; it also fails on solver-unknown and on a configuration problem.
Passing means only "no attack up to the bound under this model".

**Badge.** `faultbound-wt analyze ... --badge badge.json` writes a shields.io endpoint JSON, label `fault check`, message like
`no attack <=2 flips @ 6 cycles (scoped)`. The bound and the word "scoped" are always in the message; it never says "secure" or "safe".

**GitHub Action.** `product/action/action.yml` is a composite action (inputs netlist/config, output exit-code, SARIF upload). Its two shell steps were run locally in a clean venv (lead, 2026-11-20; a dependency-confusion bug in the default `package-path` was found and fixed); the `uses:` steps and the SARIF upload were not run: UNTESTED ON GITHUB. H2: every input reaches the shell only through `env:` variables (no `${{ }}` substitution inside `run:` scripts), as one argv element each in `--opt=value` form, with the netlist after `--`; `max-flips` and `cycles` must be digits.

## 8. Remember
- Faults are modelled single-cycle bit flips of gate outputs and flop outputs (and input nets only with `--input-sites all`). Inputs are constant over the run. Start state is known unless `--init arbitrary`.
- "No attack up to the bound" means nothing was found within `max_flips` and `cycles`, nothing more.
- Related open tools exist (SYNFI, uArchiFI, FIRMER/CLEAVE, FIVER). Nothing here is established as new.
- Yosys versions: the loader skips `$scopeinfo` hierarchy-metadata cells (emitted by Yosys >= 0.38 after flatten), so newer Yosys works; any other unsupported cell type is still rejected. Synthesised gate counts can differ between Yosys versions.
