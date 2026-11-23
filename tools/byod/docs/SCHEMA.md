# glitchsat.yaml: the project file

One file describes one design and the question to ask about it. `glitchsat init` and the Studio wizard write it for
you; you can also write it by hand. It is checked against `schema/glitchsat.schema.json` (JSON Schema 2020-12), so an
editor with YAML schema support can complete keys. A misspelt key is an error (GS002) with a suggestion, never ignored.
Paths are relative to the folder of the file. Run `glitchsat check` to validate without analysing: it checks the
format and, when Yosys is installed, reads the design and checks every name (clock, reset, inputs, signals in
conditions); without Yosys it says that names were not checked.

A project file is data and can never run a program: names must be plain identifiers, values must not contain line
breaks, quotes or `;`, check ids and task names become folder names, `report.out` stays inside the project folder,
and importer placeholders (`TODO...`) are refused (all GS002).

The words follow SymbiYosys where the idea is the same (`depth`, `tasks`, a raw `yosys_script`), the fault model follows
FIRMER/SYNFI (number of faults, fault types, include/exclude site lists, alert signals).

## The smallest file

```yaml
glitchsat: 1
design: {sources: [rtl/lock.v]}          # top, clock and reset are found automatically (with evidence)
checks:
  - id: opens
    bad: "open_o"                          # a Verilog expression: true when the attack succeeded
```

Defaults then: every input except clock and reset is attacker-controlled (a new value every cycle), all outputs are
visible, 20 cycles after reset, up to 3 faults, single-cycle bit flips on every gate and flip-flop output, flow `plain`.

## Every key

| key | meaning | default |
|---|---|---|
| `glitchsat` | format version, always `1` | required |
| `name`, `description` | for reports | folder name |
| **design** | | |
| `design.sources` | Verilog / SystemVerilog files, a gate-level netlist, a Yosys JSON netlist, or `{filelist: files.f}` (`-f` style: paths, `+incdir+`, `+define+`) | required |
| `design.top` | top module | the one module nothing instantiates (GS010 lists candidates if several) |
| `design.frontend` | `auto`, `slang` (Yosys ≥ 0.67 `read_slang`), `verilog` (`read_verilog -sv`), `netlist` (gate-level Verilog + Liberty), `json` (Yosys JSON) | `auto`: `.sv` → slang if available, `.json` → json |
| `design.include_dirs`, `design.defines` | like `-I` and `-D` | none |
| `design.params` | parameter overrides of the top (like `-G`); values like `8'hC3` are fine | none |
| `design.liberty` | Liberty files of the cells (`.lib` or `.lib.gz`), read in place, never copied; `$GLITCHSAT_LIBS` is expanded | none |
| `design.blackboxes` | `[{module, stub}]`: modules without source (encrypted or missing IP). Their outputs become free inputs (any value, every cycle) and every report lists them as a coverage boundary | none |
| `design.yosys_script` | flow `custom`: your Yosys commands after reading. Only allow-listed synthesis commands (synth, proc, opt*, techmap, abc, fsm*, memory*, flatten, setattr, dfflibmap, read_* of files inside the project folder, ...); never `!`, shell, exec, script, tee, plugin, tcl, python, write_*, or options that write files or start programs (`-o`, `-write`, `-exe`, `-script`). `glitchsat check` and the Studio show the resolved commands | none |
| `design.physical_cells` | cell-type patterns of physical-only cells dropped before a netlist is read, and counted | `[*tap*, *fill*, *decap*, *diode*]` for `frontend: netlist` |
| **who controls what** | | |
| `clock` | `port`, `{port, edge}` or `none` (combinational); mixed clock edges in a netlist are refused (GS013) | auto: the input that clocks the most flip-flops |
| `reset` | `{port, active: low/high, cycles, glitch_during_reset}` or `none` | auto: the input that resets the most flip-flops; held 1 cycle; faults start after reset |
| `powerup` | flip-flop values at power-up: `any` (unknown; the search may pick), `zero`, `init` (from the design; error if missing) | `any` with a reset, otherwise `init` where given and 0 elsewhere |
| `inputs.attacker` | `all` or a list | every input that is not clock, reset, secret or fixed |
| `inputs.attacker_changes` | `every_cycle` or `once` | `every_cycle` |
| `inputs.secret` | inputs that carry a key: constant, any value (the result says which value an attack needs) | none |
| `inputs.fixed` | `{port: value}`, e.g. `scan_en: 0` | test/scan-mode inputs found by name are fixed to 0 with a warning |
| `observe` | outputs the attacker can see (used by secret-flow checks) | all outputs |
| `probes` | `{alias: u_inst.signal}`; dotted names in conditions become probes automatically; they are marked `keep` before synthesis and recorded in `glitchsat.lock` | none |
| `assets` | `secrets` (patterns or `@attribute`), `protected_states {fsm, states}`: recorded for reports and the paused secret-flow analysis; not used by the fault analysis in this release | none |
| **what must never happen** | | |
| `checks[].id` | name | required |
| `checks[].kind` | `fault`; `secret_flow` and `masking` are part of the format only (listed as NOT RUN) | `fault` |
| `checks[].template` + `params` | one of the six templates (`glitchsat templates`) | none |
| `checks[].goal` | what an attacker gets when the check fails: `boot_accept`, `key_leak`, `debug_unlock`, `lock_bypass`, `alarm_suppress`, `state_change`, `crash_only`. The plain-words findings take "what the attacker gets" (and any real-world comparison) only from this. Without it, the words of the check's id and condition are matched (whole words only) and the finding says "guessed from the signal name - please confirm"; with no match nothing is claimed | the template's goal (`secure_boot_wrong_key`: `boot_accept`, `debug_unlock_locked`: `debug_unlock`, `key_to_output`: `key_leak`, `alarm_suppressed`: `alarm_suppress`, `counter_skip` and `fsm_forbidden_state`: `state_change`; `custom`: none) |
| `checks[].bad` | Verilog expression over top-level ports and probes; `$past(x)`, `$past(x, n)`, `$initial` | from the template |
| `checks[].must_hold` | expressions that must be true in every cycle up to the success | none |
| `checks[].detected_by` | an alarm expression that must stay false (adds `!(...)` to must_hold) | none |
| `checks[].detect_latency` | cycles the alarm may take: the success must stay unreported that long | 0 |
| `checks[].assertions` | a checker module with SVA immediate `assert`/`assume` (read with `read_verilog -formal`); its port names are top-level signals; a failing assert is the success | none |
| `checks[].horizon`, `checks[].max_faults` | per-check override | from `faults` |
| `checks[].rule` (secret_flow) | `src =/=> dst when cond unless cond` | format only |
| `checks[].labels`, `order`, `leakage` (masking) | `secret N`, `static_random`, `volatile_random`, `unimportant`; `glitch`, `transition` | format only |
| **fault model** | | |
| `faults.types` | `flip` (`bitflip`), `set`, `reset`; `stuck_at_0/1` are accepted as one-cycle reset/set (warning) | `[flip]` |
| `faults.where` | `both`, `gates` (`combinational`), `flops` (`registers`) | `both` |
| `faults.include`, `faults.exclude` | site patterns: hierarchy globs (`u_core.*`), `re:REGEX`, `@attribute` or `@attribute=value` (Yosys attributes on cells). A pattern that matches nothing is an error (GS018) | all sites |
| `faults.max_faults` (`search_k_up_to`) | largest budget searched | 3 |
| `faults.horizon` (`depth`) | cycles after reset | 20 |
| `faults.per_cycle`, `faults.cycles` | not modelled in this release: must be omitted (GS008) | |
| **how** | | |
| `flows` | synthesis flows; the first is the main one, the others are compared (survival): `plain`, `synth`, `synth-nofsm`, `synth-keep`, `nangate45`, `sky130hd`, `ihp-sg13g2`, `gf180mcu`, `liberty`, `netlist`, `custom` | `[plain]` (`[netlist]` for netlists) |
| `analyses` | `validate`, `min_faults`, `attack_surface`, `merge_lint`, `survival`, `unbounded` | all |
| `solver` | `backend` (`auto` = CaDiCaL if installed, else the built-in solver; `py`, `cadical`, `kissat`, `dimacs:/path`), `time_s` (300), `workers` (1/2) | |
| `unbounded` | `max_state_bits` (400), `time_s` (60) | |
| `validation` | `runs` (256), `cycles`, `seed` | |
| `report` | `redact` (aliases instead of names), `out` (`.glitchsat/`) | |
| `tasks` | named variants; each value overrides keys of the file (`glitchsat run --task NAME`) | none |

## What the tool generates (no hand-written Verilog)

For every check, in `.glitchsat/<task>/check_<id>/`:

* `glitchsat_monitor.v`: computes `bad` and `ok` from the top-level signals (with the `$past` registers it needs);
* `glitchsat_wrap.v`: design + monitor + reset sequence + tied inputs, for reading and as the RTL reference.

The monitor is synthesised on its own and joined to the design netlist at the level of nets, so synthesis never
optimises the property together with the chip and no monitor gate is ever a fault site. Before any analysis, the
joined netlist is simulated next to `glitchsat_wrap.v` elaborated from your RTL (random inputs, three-valued, every
output plus `bad` and `ok` in every cycle). A difference stops the run (GS050).

`<project>.lock` next to the YAML (`glitchsat.lock` for `glitchsat.yaml`, `glitchsat_hardened.lock` for
`glitchsat_hardened.yaml`, `<stem>.<task>.lock` for a task) records what was resolved and what was asked: top, clock
and reset, the role of every input, probes and the module/wire they were found in, the resolved checks (`bad`,
`must_hold`, `detect_latency`, horizon, fault budget), the fault model (types, where, include/exclude, the
normalisation), flows and analyses, the GlitchSAT version, the Yosys version of every step, the sha256 of the project
file, of every source, of every `include file, black-box stub and assertion file, and of every Liberty file (keyed by
its path under `$GLITCHSAT_LIBS` or the project, so locks are portable), the number of fault sites per check and flow,
black boxes, validation and solver settings. A run reports which of these changed since the last run. Results go to
`.glitchsat/<task>/` for `glitchsat.yaml` and to `.glitchsat/<stem>/<task>/` for any other project file, so two
project files in one folder never share a lock or a result folder. The lock and `.glitchsat/` are not redacted.

Fault sites: one per combinational cell output pin and one per flip-flop, its stored value (a flip stays until the
flop loads a new value). Every flow ends with `dffunmap`, so enable and synchronous-reset flip-flops are plain D
flip-flops plus gates in every build, and builds are compared on the same fault model.

## Template parameters

| template | params | bad condition built |
|---|---|---|
| `secure_boot_wrong_key` | `accept`, `key_input`, `good_key`, `alarm`? | `(accept) && (key_input != good_key)` |
| `debug_unlock_locked` | `unlocked`, `locked`, `alarm`? | `(unlocked) && (locked)` |
| `fsm_forbidden_state` | `state`, `forbidden: [...]` or `allowed: [...]`, `when`?, `alarm`? | state equals a forbidden value / none of the allowed ones |
| `key_to_output` | `key`, `test_key`, `output`, `mask`?, `valid`? | key input fixed to `test_key`; `output == test_key` (masked) |
| `counter_skip` | `counter`, `step` (1), `must_step_when`?, `when`?, `alarm`?, `alarm_latency`? | the counter changes by anything other than `+step` (modulo its width); with `must_step_when`, also: that event happened and the counter did not move (a stuck retry counter). Without it a counter that does not change is not reported |
| `alarm_suppressed` | `trigger`, `alarm`, `latency` (1) | `$past(trigger, latency)` while `!(alarm)` held throughout |

Each template file in `templates/` is a ready snippet with a plain explanation (`glitchsat templates NAME`).

## Python

```python
from glitchsat_byod import Project
rep = Project('glitchsat.yaml', task=None).run()          # the same dict as .glitchsat/default/report.json
print(Project('glitchsat.yaml').explain(rep))
```
