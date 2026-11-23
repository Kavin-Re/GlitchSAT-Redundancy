# Error codes

Every problem has a code. `glitchsat explain GSxxx` prints the same text. Messages follow one pattern:

```
error[GS023]: module `secret_ip` is used by instance `u_ip` in `top` but is not defined in the sources
  = help: add the file that defines `secret_ip` to `design.sources`, or declare it as a black box: ...
  (more: glitchsat explain GS023)
```

Silent weakening is always an error, never a quiet change of the question: an unmapped cell (GS039), a module without source (GS023), a fault-site pattern that matches nothing (GS018), assertions that disappear (GS024), an x on a pin (GS035), a netlist that differs from the RTL in simulation (GS050), a net nothing drives (GS044). A value in a project file that could reach a Yosys script unsafely is refused too (GS002).

Warnings (the run continues) have codes GS070 and up.

## GS001: The project file could not be read.

glitchsat.yaml must be valid YAML. The message gives the line. Common causes: a tab character used for indentation (use spaces), a missing space after a colon, or an unquoted Verilog expression that starts with a character YAML treats specially (`!`, `&`, `*`, `{`, `[`, `|`, `>`, `%`, `@`). Put such expressions in double quotes: bad: "!unlocked && debug_en".

## GS002: A key in the project file is not known, or has the wrong type.

The project file is checked against schema/glitchsat.schema.json. The message names the key and what was expected. Misspelt keys are an error on purpose: a misspelt `exclude` would otherwise silently fault the whole design. GS002 is also given for values that cannot be used safely: a project file is data and can never run a program. Names (top, ports, probes, defines, parameters) must be plain identifiers, values must not contain line breaks, quotes or `;`, check ids and task names become folder names, `report.out` must stay inside the project folder, and `design.yosys_script` may only use allow-listed Yosys synthesis commands (never `!`, shell, exec, script, tee, plugin, tcl, python or write_*), reading files from inside the project folder only. A placeholder left by an importer (`TODO...`) is refused too.

## GS003: A file named in the project does not exist.

Paths are relative to the folder that contains glitchsat.yaml.

## GS004: The project names no design sources.

Add `design: {sources: [rtl/my_top.v]}` (or a netlist with `frontend: netlist`).

## GS005: The project has no check.

Add at least one entry under `checks:`, for example from a template (`glitchsat templates`).

## GS006: The schema version is not supported.

Set `glitchsat: 1` at the top of the file.

## GS007: A check of a kind that this version does not run.

Kinds `secret_flow` and `masking` are part of the file format so projects can be written now, but their analyses are not part of this release. They are listed as NOT RUN in the report; nothing is claimed.

## GS008: A setting of the fault model that is not modelled.

This release models: at most k faults in total, any cycle of the horizon, any number per cycle, types flip/set/reset. `per_cycle` and `cycles` windows are refused instead of being ignored.

## GS009: A filelist could not be read.

Filelists (`-f`) may contain file paths, +incdir+DIR, +define+N=V and -y/-v are not supported.

## GS010: The top module could not be found or is ambiguous.

With several modules that are never instantiated, the tool cannot guess which one is the chip. Set `design.top`. The message lists the candidates.

## GS011: A port named in the project is not a port of the top module.

Clock, reset, attacker, secret and fixed inputs must be input ports of the top module; signals in the `bad`/`must_hold` expressions must be ports of the top module or `probes`. The message lists the ports.

## GS012: No clock was found.

The design has flip-flops but no input drives their clock pins. Set `clock: {port: <name>}`. For a purely combinational design set `clock: none`.

## GS013: More than one clock, or a gated or generated clock.

The model has one clock: every flip-flop must be clocked by the same input port (through buffers or inverters only), on the same edge. Gated clocks (clock AND enable) and clock dividers are not modelled; replace the gate by a clock enable for the analysis.

## GS014: Reset settings are inconsistent.

reset.active is `low` or `high`; reset.cycles >= 1. (The warning that a reset was auto-detected is GS070.)

## GS015: A port is listed in two roles.

Each input is exactly one of: clock, reset, attacker-controlled, secret, fixed. Remove it from all but one list. (Warnings about tied test inputs and unlisted inputs are GS071 and GS072.)

## GS016: A fixed value does not fit the port.

The value is wider than the port.

## GS017: A probe could not be found in the netlist.

Probes name internal signals (hierarchical, with dots). The tool marks them `keep` before synthesis; if a probe is still missing, the signal does not exist under that name after elaboration (check the spelling and the instance names) or it is constant.

## GS018: A selector matched nothing.

A fault-site include/exclude pattern that matches no cell is an error: it usually means a typo, and a typo in an exclude list would silently widen the analysis. The message lists similar scopes.

## GS019: An expression could not be compiled.

The `bad`/`must_hold` expressions are Verilog expressions over top-level ports and probes, plus `$past(x)`, `$past(x, n)` and `$initial` (true in cycle 0 only). Yosys reports the problem; the message shows the generated monitor line.

## GS020: The secret, attacker or fixed list names a signal of the wrong direction.

Only inputs can be attacker-controlled, secret or fixed.

## GS021: Yosys, or one of the GlitchSAT engines, is not installed or could not be found.

Every input path needs Yosys: Verilog, SystemVerilog, a gate-level netlist (`frontend: netlist`) and a Yosys JSON netlist (`frontend: json`) are all read by Yosys, so none of them works without it. Install Yosys 0.33 or newer (Debian/Ubuntu: `sudo apt-get install -y yosys`; or the OSS CAD Suite), or set GLITCHSAT_YOSYS=/path/to/yosys. SystemVerilog sources need Yosys 0.67 or newer, which includes read_slang (GLITCHSAT_YOSYS_SLANG). The same code is used when an engine of the repository (scale, fastsat, unbounded, checker) or the repository itself is not found: the message lists the folders looked in. `glitchsat doctor` prints the whole set-up. The Studio still shows the saved results of the gallery examples without Yosys.

## GS022: Synthesis failed.

Yosys stopped with an error. The last lines of its log are shown; the full log is in .glitchsat/<flow>/yosys.log.

## GS023: A module is missing (implicit black box).

A module is instantiated but not defined in the sources. It is not silently treated as empty: add its source, or declare it under `design.blackboxes` with a stub (ports only). Black-box outputs become free inputs of the analysis (any value, every cycle) and the report lists them as a coverage boundary.

## GS024: Assertions were dropped.

The assertion file or the design contains `assert`/`assume` statements but no assertion survived elaboration (for example a converter removed them). The check would be empty, so it is refused.

## GS025: Unknown synthesis flow.

Use one of the flows listed by `glitchsat flows`.

## GS026: A flow needs a Liberty file.

Flows that map to standard cells need `design.liberty` or the library named by the flow (see `glitchsat flows`). Liberty files are read in place and never copied.

## GS028: `powerup: init` but some flip-flops have no initial value.

Use `powerup: any` (unknown values, the safest choice) or `powerup: zero`, or give every register an initial value in the design.

## GS031: Inout port.

Bidirectional ports are not modelled.

## GS032: A cell drives a constant.

The netlist is malformed.

## GS033: Two drivers on one net.

The netlist is malformed or an input port is also driven inside.

## GS034: A multi-bit cell pin.

Only 1-bit cell pins are modelled (flatten and techmap first).

## GS035: A pin is connected to x/z.

An undefined value is refused instead of being treated as 0.

## GS036: A latch, memory or asynchronous-load flip-flop.

Only edge-triggered flip-flops and gates are modelled.

## GS037: A black box without port directions.

Give a stub module so the tool knows which pins are outputs.

## GS038: A coarse Yosys cell in a netlist.

The netlist is not mapped to gates yet.

## GS039: Unknown cell type (unmapped cell).

The cell is in no Liberty file given and is not a declared black box. Nothing is skipped silently.

## GS040: A standard cell that cannot be modelled.

Latches, clock-gating cells (statetable), tri-state outputs, multibit flip-flops and master-slave descriptions are refused when a netlist uses them. Gated clocks are not modelled: synthesise without clock gating (no ICG cells) for the analysis. Physical-only cells (fillers, taps, decaps, antenna diodes; `design.physical_cells`) are dropped before reading and counted in the report.

## GS041: An unconnected cell input.

Tie it to 0 or 1.

## GS042: A Liberty cell failed its truth-table check.

The gate network built from the Liberty function disagrees with the function itself. This is an internal error of the importer; please report the cell name and library.

## GS043: The Liberty file could not be parsed.

The message gives the line.

## GS044: A net is used but never driven.

Some gate or flip-flop reads a net that nothing drives, usually an output of a submodule that was left unconnected or never assigned. Its value would be undefined, so the analysis is refused. Assign the signal in the module the message names, or tie it to 0/1.

## GS045: Physical-only cells were dropped.

Instances whose cell type matches `design.physical_cells` (default for netlists: *tap*, *fill*, *decap*, *diode*) have no logic function. They are removed before the netlist is read, and the report counts them.

## GS046: This Yosys reads a Liberty clear/preset rule wrongly.

For flip-flops with both an asynchronous clear and preset, the Liberty attributes clear_preset_var1/2 say what Q is when both are active. Yosys 0.33 `read_liberty` ignores them (it gives clear priority), so the reference used to validate a gate-level netlist is wrong for such a cell, while GlitchSAT follows the Liberty file. Yosys 0.71 agrees with the Liberty file. Install a newer Yosys (or point GLITCHSAT_YOSYS / GLITCHSAT_YOSYS_SLANG at one): GlitchSAT then picks the newest Yosys it finds for gate-level netlists.

## GS050: The generated wrapper does not match the design in simulation.

The netlist that is analysed (synthesised design + generated monitor) was simulated next to the RTL as written (wrapper included) with random inputs, and some output or the `bad` signal differed. The analysis is refused. Typical causes: an FSM re-encoded by synthesis while a probe reads its state (use a flow that keeps encodings, or probe an output instead), x-propagation in the RTL (uninitialised registers without reset), a custom flow that changes the logic, or a synthesis bug. For a gate-level netlist the reference is Yosys's own reading of the cells, see GS046. The two netlists compared are in .glitchsat/<task>/flow_<flow>/netlist.json and check_<id>/reference/netlist.json. This check runs without faults, so logic that only acts after a fault (alarms, redundant copies) is not covered by it.

## GS051: The fault-free design already reaches the bad condition.

With zero faults, some input sequence makes `bad` true. Either the design has a functional bug, or the bad condition is too wide (for example it does not exclude the legitimate case). The report shows the input sequence. The fault analysis is skipped because "0 faults needed" is the answer.

## GS052: The must-hold assumptions can never be met.

No fault-free run satisfies every `must_hold` expression in cycle 0, so every result would be vacuous.

## GS053: The solver hit its time limit.

The result is an interval or a lower bound; raise `solver.time_s`.

## GS054: The unbounded proof was skipped.

Too many state bits for the methods within the time limit, or per-cycle attacker inputs together with a large state.

## GS060: Network access attempted.

GlitchSAT makes no network connections; a test enforces this.

## GS070: Reset auto-detected (warning).

The reset port and its polarity were found from the structure. Confirm them by writing `reset: {port: ..., active: low|high}` in glitchsat.yaml.

## GS071: Test-mode input tied to 0 (warning).

An input named like a scan or test-mode enable was tied to 0 (functional mode). List it under `inputs.attacker` if the attacker can drive it.

## GS072: Inputs treated as attacker-controlled (warning).

Inputs not listed under attacker, secret or fixed are given to the attacker (the safe choice). List them under `inputs.fixed` or `inputs.secret` if that is wrong.

## GS073: Scan enable driven by the attacker (warning).

A scan flip-flop's scan-enable pin is driven by an attacker input, so the attacker can switch the flop to its scan input. That is usually a test-mode pin: tie it with `inputs.fixed` unless the attacker really controls it.
