# GlitchSAT CLI (package directory `product/`)

Licence: Apache-2.0 (see the LICENSE file at the repository root).

The installable command-line tool of GlitchSAT. It installs the command `glitchsat`; the older name `faultbound-wt` is kept as an alias, and the Python module is still called `faultbound_wt`. The baseline reproduce table (`make reproduce`) comes from the reference engine `scripts/glitchsat.py`; this CLI wraps a copy of that engine and adds scope options, reports and sweeps.

Bounded search for **modelled** bit-flip attacks on a Yosys gate-level netlist, using z3. A fault is a single-cycle flip of a gate output or flop Q. Nothing here is a physical glitch model and nothing was run on hardware. Verdicts are bounded in flips and cycles and are not a proof of security. Nothing here is established as new; related open tools (SYNFI, uArchiFI, FIRMER/CLEAVE, FIVER) exist.

## Quickstart (Python >= 3.11; z3-solver is installed by pip; yosys is needed only for Verilog input)
Run from the repository root (the directory that contains `product/`):
```
python3 -m venv .venv && . .venv/bin/activate
pip install ./product
EX="$(glitchsat example-path)"
glitchsat analyze "$EX/v2.json" --config "$EX/threat.toml" --max-flips 2 --report out.json
echo "exit code: $?"
glitchsat analyze "$EX/v2.json" --config "$EX/threat.toml" --max-flips 3 --report out.json --report out.sarif --report out.junit.xml
echo "exit code: $?"
```
First command: `NO_ATTACK_UP_TO_BOUND`, exit 0. Second: `ATTACK_FOUND` (3 flips), exit 1. Both about 1 to 10 s on the bundled toy netlists (MEASURED on one machine, see research/c2/ps/PS_BUILD_REPORT.md).

## Command
```
glitchsat analyze NETLIST[.json|.v] [--config threat.toml] [--max-flips K] [--cycles T] [--top MODULE]
                  [--report FILE ...] [--exit-zero] [--no-honest-check]
```
- `--report` format comes from the extension: `.json`, `.sarif` (SARIF 2.1.0), `.junit.xml`. Repeatable.
- Exit codes: `0` no attack up to the bound; `1` attack found; `2` solver unknown/timeout; `3` usage, input, netlist or configuration error (including 'the honest input does not reach the goal in the fault-free design'); `4` internal error. `--exit-zero` forces 0 except for errors. (The reference engine `scripts/glitchsat.py` differs: it exits 0 for both verdicts and leaves the verdict in the text.) `--no-honest-check` turns the configuration error into a warning.
- Verilog input (`.v`) runs the repository's "plain" Yosys flow (same script as `scripts/synth.sh`) and needs `yosys` on PATH and `--top`. `--top` must be a plain identifier and the path free of quotes, `;`, backslash, `#`, control characters (exit 3); `--max-flips` is capped at 64; `--consumer-bits` syntax is documented in QUICKSTART 4b/4d.
- Flags override the config.

## Threat-model config (TOML)
See `faultbound_wt/examples/threat.toml` (printed path: `glitchsat example-path`).
| key | meaning |
|---|---|
| `[faults] max_flips`, `cycles` | attacker budget and analysis horizon |
| `[faults] kinds` | `gate` and/or `flop`: which net kinds may be flipped |
| `[faults] include`, `exclude` | glob patterns on net names (any alias of the net matches); empty include = all |
| `[attacker] input`, `legitimate_value` | free input port and the value that does not count as an attack |
| `[attacker] model` | only `"constant"` (held constant over the run). Per-cycle input is a TODO (see Limits) |
| `[property] output`, `bad_value` | attack goal: output equals `bad_value` at some cycle |
| `[netlist] top`, `[solver] timeout_ms` | optional |

Restricting fault sites can only remove attacks (tested), so a restricted "no attack" says less than an unrestricted one.

## Scope block (every report)
JSON `scope`, SARIF `runs[0].properties.scope`, JUnit properties `scope_*` and the `scope:` lines of the text output state: goal definition, input treatment (all non-clock inputs free and constant), initial-state assumption, fault model and counting rule, bounds, netlist SHA-256, tool version, and "bounded result under this model; not a proof of security". Config values that were not set (built-in defaults in use) are listed and warned about on stderr. The scope options (`--consumer-bits`, `--goal-out`/`--accept-value`, `--input-sites`, `--init` including `free_nongoal`, `--count-rule` (`stem`, `fanout`/`fanout_pins`, `fanout_gates`; `branch` exits 3), `--scope-sweep`, `--sweep-widths`, `--timeout-s`) appear as `scope.options` and the `scope: options:` line. Further options: `--sweep-count-rules` (a counting-rule axis of the scope sweep) and `--synth-sweep` / `--synth-variants` / `--synth-select` (the same Verilog through a documented set of Yosys flows, minimum flips per netlist hash; needs yosys). See QUICKSTART sections 4b and 4c.

## Provenance (in every JSON report; summarised in SARIF properties and JUnit properties)
Tool version, full command line, netlist SHA-256, gate and flop counts, z3 version, Python version, UTC time, the Yosys `creator` string stored in the netlist JSON, and (Verilog input) the Yosys version used to synthesize plus the source hash. The verdict depends on the exact synthesized netlist, so keep the netlist hash with the result.

## Engine choice
The solver is a copy of the engine part of `scripts/glitchsat.py` (see header of `src/faultbound_wt/_engine.py`: origin, and three small marked changes: site filter, net aliases, unsupported-cell check). `scripts/` is untouched. The copy is a snapshot and drifts unless re-synced by hand. No third-party code is vendored.

## Limits
- Supported cells: AND, OR, XOR, NOT, MUX and `$_DFF_P_` only (Yosys `abc -g AND,OR,XOR,MUX` flow). Others give exit 3; flops with asynchronous reset/set get a message that says so (not modelled; use a synchronous reset).
- Explanation text is derived from the fault set and cone structure; the fix patterns are generic and labelled so.
- Single-cycle bit flips only; no stuck-at, multi-bit or timing/voltage effects.
- Attacker input constant over the run. Time-varying input: not implemented (an unfinished SymbiYosys-based experiment is in `research/c2/e1_timevarying/`; not copied).
- Property is one equality on one output port.
- Scale untested beyond toy netlists (18 to 68 gates, MEASURED from netlist stats).

## Tests
```
pip install "./product[test]" && python -m pytest product/tests
```
`product/examples/github-actions-sarif.yml` (SARIF upload) and `product/ci/github-actions-example.yml` are examples only and have never been run. See `product/QUICKSTART.md`.
