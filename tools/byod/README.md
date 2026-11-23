# Use GlitchSAT on your own chip in 5 minutes

## In plain words

A chip that checks something important (a password, the signature of a program, a debug lock) can be attacked by
disturbing it for an instant: a short dip in the supply voltage, a too-early clock edge, a laser flash. Each such
**glitch** flips one wire for one clock tick. GlitchSAT answers one question about a chip design:

> **How many glitches does an attacker need to make the chip do something it must never do?**

Until now GlitchSAT answered it for its own built-in example designs. This folder lets you ask it about **any** design:
your Verilog or SystemVerilog, a design from a class project, an OpenTitan block, or a netlist of real standard cells from a
chip factory's library. You say, in a few lines, which inputs the attacker controls and what must never happen.
GlitchSAT writes all the extra Verilog it needs itself, checks by simulation that it understood your design
correctly, and then tells you:

* the smallest number of glitches that is enough, and exactly where and when they must hit;
* every cheapest attack, so you see the weak spots;
* whether the protection survived the build (synthesis tools sometimes merge copies of a check);
* whether "no attack" holds however long the chip runs (a proof), when that can be computed.

Everything runs on your computer. GlitchSAT makes no network connections, your files are never uploaded, and a
`--redact` switch replaces every design name, file name, path, secret value and constant in the reports by an alias.
A project file is data: it can never run a program (see "Privacy and safety").

What it is not: a glitch here is a model (one wire inverted, or forced to 0 or 1, for one clock cycle). Nothing is
measured on a chip, and "no attack" is bounded by the number of glitches and cycles you chose, unless a proof is shown.

## The 5-minute path

```
cd tools/byod                                      # this folder, inside the GlitchSAT repository
export PATH=$PWD:$PATH                             # so that `glitchsat` works from any folder
export GLITCHSAT_ROOT=/path/to/the/repository     # only when this folder is NOT at tools/byod inside the repository
glitchsat doctor                                   # setup check: Yosys, engines, solvers ("Ready.")
glitchsat examples copy hello_lock ~/my_lock       # a tiny lock: opens on the code A5
cd ~/my_lock
glitchsat run                                      # the weak version: "1 fault is enough", and where
glitchsat run glitchsat_hardened.yaml              # three separate checks: 3 faults in the plain build, 1 after `synth`
glitchsat explain                                  # the last result again, in plain language
```

In the Studio (`python3 studio.py`, or `python3 tools/studio/studio_byod.py`), tab **Open my design**: pick an
example, or point it at your own folder and answer five questions (your design, clock and reset, who can do what,
what must never happen and what a legitimate user may do, how hard to search). The wizard writes the same
`glitchsat.yaml` as `glitchsat init`. Without Yosys the tab still shows the saved results of every gallery example,
labelled RECORDED. The tab needs the Python package PyYAML (`python3 -m pip install pyyaml`); it says so when it is
missing. An example that needs more than a plain Yosys (OpenTitan: Yosys 0.67+ with `read_slang`; sky130: the cell
library from `scripts/fetch_libs.sh`) says what it needs and shows its saved result instead. The folder picker opens
folders in your home folder; to allow another one, start the Studio with `--allow-root /path` (or set
`GLITCHSAT_ALLOW_ROOTS=/path1:/path2`).

`glitchsat init --yes` accepts every suggestion and therefore writes no must-hold condition (what a legitimate user
may do). It says so, leaves a commented line to fill in, and the first run then names the missing condition and the
line to add when it finds the "attack" without any fault.

For your own design: `glitchsat init` in its folder (five questions, with what was detected shown as evidence, e.g.
"`clk` drives the clock of 412/412 flip-flops"), then `glitchsat check` (format and every name: clock, reset, inputs,
signals in conditions) and `glitchsat run`.

Requirements: Python 3.10+, PyYAML, Yosys 0.33+ for every input path (SystemVerilog: Yosys 0.67+ with `read_slang`;
gate-level netlists with clear+preset flip-flops: Yosys 0.71 recommended, see GS046), and four GlitchSAT engines that
land next to this folder (table "Landing" below). CaDiCaL is used when installed; otherwise a built-in solver.

## What you write

```yaml
glitchsat: 1
design:
  sources: [rtl/hello_lock.v]
clock: clk
reset: {port: rst_n, active: low}
inputs:
  attacker: [code_i, try_i]                 # what the attacker can drive (a new value every cycle)
checks:
  - id: open_without_code
    bad: "open_o"                           # what must never happen (a Verilog expression)
    must_hold: ["!(try_i && code_i == 8'hA5)"]   # ... while the attacker never types the right code
faults: {max_faults: 2, horizon: 6}
```

Or use a template for the common questions (`glitchsat templates`):

| template | the question in plain words |
|---|---|
| `secure_boot_wrong_key` | the boot check accepts a program whose key or signature is wrong |
| `debug_unlock_locked` | the debug port (JTAG) opens while the life cycle says "locked" |
| `fsm_forbidden_state` | a state machine reaches a forbidden state, or an illegal code |
| `key_to_output` | bits of a secret key appear on an output |
| `counter_skip` | a counter jumps over a value, or does not count what it must (`must_step_when`: the classic retry-counter attack) |
| `alarm_suppressed` | something that must raise the alarm happens, and the alarm stays silent |

The full format: [docs/SCHEMA.md](docs/SCHEMA.md) (JSON Schema: `schema/glitchsat.schema.json`). Errors and how to fix
them: [docs/ERRORS.md](docs/ERRORS.md) (`glitchsat explain GSxxx`).

## The gallery (each with a weak and a protected version; MEASURED by `scripts/run_examples.py`)

| example | what it teaches | weak | protected |
|---|---|---|---|
| `hello_lock` | one check falls to one glitch; three separate checks need three, until an optimising build merges them | 1 fault | 3 faults (plain and `synth-keep` builds); "no attack with 2" proved for any number of cycles; `synth` build: 1 |
| `secure_boot` | our boot-check hardware (a copy of its four RTL files is in `examples/secure_boot/rtl/`), used as is with parameters; no hand-written wrapper | 1 fault | 3 faults (three compares + alarm) |
| `opentitan_count` | OpenTitan `prim_count` (tag Earlgrey-PROD-M6) against a plain counter | plain counter: 1 | prim_count: 2; "no attack with 1 fault" proved for any number of cycles |
| `sky130_lock` | the hello lock as SkyWater sky130 cells: no RTL, only the cell netlist and the Liberty file | 1 fault | no attack with ≤ 2; proved |

Each example folder has a `README.md` (what it is, why the protection matters, what it teaches) and
`expected_results.json`, and `saved/` holds the full report of every run (shown by the Studio when Yosys is
missing). `python3 scripts/run_examples.py` re-runs all of them (about 2.5 minutes with CaDiCaL) and rewrites those
files; `--check` compares instead and exits 1 on any difference, error or missing run; `--readme` rewrites the
example READMEs from the stored results.

Independent check of the secure-boot numbers (`results/secboot_handwrapper_crosscheck.json`, MEASURED): the original
engine (`scripts/glitchsat.py`, z3) on the hand-written wrappers `rtl/tops/top_d_single.v` and `top_d_trip_alarm.v`
gives 1 and 3 faults as well, although that setup differs (no reset, power-up values, the original solver).

## How it works

1. **Read and resolve.** Yosys elaborates the design. Top, clock and reset are detected from the structure (which
   input drives the flip-flops' clock and reset pins) and confirmed in the file; secrets and test-mode inputs are
   suggested by name. The resolution and the question (checks, fault model, flows, tool versions) are written to
   `<project>.lock` (`glitchsat.lock` for `glitchsat.yaml`) with the sha256 of every file read, `include files,
   stubs and assertion files included; the next run lists what changed.
2. **Build.** Each flow in `flows:` synthesises the design alone. Internal signals named in conditions are marked
   `keep` first. Every flow ends with the same normalisation, `dffunmap`: enable and synchronous-reset flip-flops
   become plain D flip-flops plus explicit gates, exactly what the `plain` flow writes anyway.
3. **Import.** The netlist becomes AND/OR/XOR/NOT/MUX gates and D flip-flops. Standard cells are read from Liberty
   files (`function`; `ff` with `next_state`, `clocked_on`, `clear`, `preset`, `clear_preset_var1/2`). Every cell a
   netlist uses is checked by exhaustive truth table against its Liberty function before it is used. **Fault sites**
   (the same in every flow and library): one per combinational cell output pin (the primitives inside a cell are
   never sites), and one per flip-flop: its **stored value**. The flop's output pins and its own hold path (an
   enable flop such as sky130 `edfxtp`) read that value, so a flipped bit stays until the flop loads a new value,
   whether the netlist uses an enable flop or a D flop with a hold multiplexer. So the same RTL gives the same
   minimum in every build when the logic is equivalent (`tests/test_review_fixes.py`, design `en_reg`), and a build
   can no longer look stronger only because it used enable cells. Unmapped cells, latches, clock gates,
   tri-states, gated clocks, x values, undriven nets and missing modules are refused with an error that names them.
4. **Generate the question.** A monitor module computes `bad` and `ok` from your expressions; it is synthesised on
   its own and joined to the design at net level (synthesis never mixes it with the chip, and it is never a fault
   site). Reset, tied inputs and power-up are added the same way.
5. **Validate.** The joined netlist is simulated next to the generated wrapper elaborated from your RTL (256 random
   runs, three-valued, every output and `bad`/`ok` in every cycle). Any difference stops the analysis (GS050). This
   is fault-free operation: logic that only acts after a fault (alarms, redundant copies) is not covered by it. For a
   gate-level netlist the reference is Yosys's own reading of the same cells, so the check covers the wrapper and
   monitor wiring, not the design.
6. **Analyse.** The scale engine finds the minimum number of faults (every attack is replayed on a separate
   gate-level simulator; the attack shown is the earliest one with that many faults), lists every cheapest attack,
   repeats this for every flow, runs the checker engine for the merge lint, and adapts the unbounded engine
   (k-induction and IC3 with a re-checked invariant) for the proof.
7. **Report.** Answer, the weakest build when builds differ, the attack step by step (with the RTL line where
   synthesis kept it), the coverage boundary of black boxes, risks (a scan enable driven by the attacker), and
   **What to do**: the named remedy for what was found (keep the copies apart with `(* keep_hierarchy *)` /
   `(* keep *)` or the per-module flow, dont_touch in commercial flows; keep FSM encodings; a sparse encoding;
   no single shared decision signal; a placement constraint that spreads the copies; a compiler barrier for
   firmware checks).

## Formats

| input | path | status |
|---|---|---|
| Verilog-2005 | `read_verilog -sv` (Yosys 0.33+) | stable, tested |
| SystemVerilog | `read_slang` (Yosys ≥ 0.67; tested with 0.71) first; `frontend: verilog` for simple SV; sv2v by hand. Without `read_slang`, `.sv` files fall back to `read_verilog -sv`, and a parse error then says so | stable, tested (OpenTitan prim_count) |
| Gate-level netlist + Liberty (ASIC, LibreLane/OpenLane `nl.v`, DC/Genus output) | `frontend: netlist`; Yosys parses the Verilog (the newest Yosys found is used), GlitchSAT maps the cells from the Liberty file; physical-only cells (`design.physical_cells`, default `*tap*`, `*fill*`, `*decap*`, `*diode*`) are dropped first and counted | stable, tested with sky130, Nangate45 (SYNFI netlist), IHP SG13G2, GF180MCU cells; LibreLane run folders not tested |
| Yosys JSON netlist | `frontend: json` (read by Yosys too) | stable, tested |
| Tiny Tapeout project | `glitchsat init --from-tinytapeout DIR` (reads `info.yaml`: `top_module`, `source_files`) | stable, tested on a small project |
| SymbiYosys `.sby`, SYNFI `fault_model.json` | `glitchsat import-sby`, `import-synfi` (`fimodels.<name>`: one check per model; output and alert values, fault locations, fault count; unused keys listed): a starting `glitchsat.yaml`. Placeholders (`TODO...`) are refused by `glitchsat check` until filled in | experimental |
| SVA immediate `assert`/`assume` in a checker file | `checks[].assertions` (`read_verilog -formal`) | experimental (tested on one design; no wrapper validation for this path) |
| Chisel / FIRRTL | generate Verilog with `firtool --lowering-options=disallowLocalVariables,disallowPackedArrays`, then as SystemVerilog | experimental, not tested |
| VHDL | not built in: convert first (`ghdl --synth --out=verilog`, or the ghdl-yosys-plugin, GPL) | experimental, not tested |
| FPGA netlists (Vivado `write_verilog -mode funcsim`) | needs the vendor cell models as Verilog; LUT INIT mapping is not built in | experimental, not tested |
| Encrypted IP (IEEE 1735) | never decrypted: declare it under `design.blackboxes` with a port stub; its outputs become free inputs, its inputs are reported, and the report lists the coverage boundary | stable (black-box path tested) |

Scan flip-flops are modelled with their scan multiplexer; tie the scan enable (`inputs.fixed`, suggested automatically
for inputs named like `scan_en`/`test_mode`). Scan, clock-gating, retention and multibit cells are detected and reported
as risks; the ones that cannot be modelled stop the import. A scan enable driven by an attacker input is reported in
the text report (warning GS073).

## Standard-cell libraries (MEASURED; `results/liberty_crosscheck.json`)

`sh scripts/fetch_libs.sh` fetches open Liberty files with git at pinned commits (sha256 checked) into
`$GLITCHSAT_LIBS`: Nangate45 (the library the SYNFI repository uses, via OpenROAD-flow-scripts), SkyWater
sky130_fd_sc_hd (Apache-2.0), IHP SG13G2 (Apache-2.0), GF180MCU 7-track (Apache-2.0). Nothing from them is copied into
this folder or into reports. `python3 scripts/crosscheck_liberty.py` checks every cell four ways:

| library | cells | A: truth table vs Liberty | B: same as Yosys `read_liberty` | C / D |
|---|---|---|---|---|
| Nangate45 | 135 (108 modelled) | 108 pass, 0 fail | 104 of 108 | D: 92/92 functions equal to SYNFI's cell library |
| sky130_fd_sc_hd | 428 (379 modelled) | 379 pass, 0 fail | 373 of 379 | C: 379/379 equal to the Liberty-JSON of google/skywater-pdk-libs-sky130_fd_sc_hd @ ac7fb61 |
| IHP SG13G2 | 84 (63 modelled) | 63 pass, 0 fail | 62 of 63 | |
| GF180MCU 7t | 229 (181 modelled) | 181 pass, 0 fail | 181 of 181 | |

The 11 differences in B are all flip-flops with both asynchronous clear and preset, in the rows where both are active:
the Liberty files say `clear_preset_var1/2` (e.g. sky130 `dfbbp`: Q = 1), Yosys 0.33 `read_liberty` gives reset
priority (Q = 0). GlitchSAT follows the Liberty file, and Yosys 0.71 agrees with the Liberty file (and GlitchSAT).
Because Yosys's reading is the validation reference for `frontend: netlist`, GlitchSAT uses the newest Yosys it finds
for netlists, and with an older one a mismatch on such a cell is reported as GS046 (install Yosys 0.71) instead of a
generic GS050. Not modelled (refused if a netlist uses them): latches,
clock-gating cells (statetable; the message says "gated clocks are not modelled: synthesise without clock gating"),
tri-state buffers, the IHP sighold cell (inout). Fillers, taps, decaps and diodes are dropped before reading and
counted, even when the Liberty file does not list them (post-placement netlists). Note: Yosys 0.33 `dfflibmap` skips sky130 scan and enable flip-flops ("unsupported
expression"); GlitchSAT's reader handles them (16 combinations checked for `sdfxtp_1`).

The importer was also run on a third-party netlist: lowRISC SYNFI's Nangate45 AES control FSM gives the same outputs as
Yosys's own reading of the same cells, cycle by cycle (`tests/test_cli_privacy.py`).

## Privacy and safety

* No network: no module imports a network client (test), and the full pipeline runs with every socket connection
  refused (test). Liberty files are referenced, never copied.
* A project file is data and can never run a program. Every value that reaches a Yosys script is checked against a
  strict pattern (names are plain identifiers; defines and parameters plain values; no line breaks, quotes or `;`),
  check ids and task names become folder names and are checked as such, `report.out` stays inside the project
  folder, and every script line is checked again before Yosys starts (no `!`, which Yosys would run in a shell).
  `design.yosys_script` (flow `custom`) accepts only allow-listed synthesis commands, reads files from inside the
  project folder only, and never allows `!`, `shell`, `exec`, `script`, `tee`, `plugin`, `tcl`, `python`, any
  `write_*`, or options that write files or start programs. `glitchsat check` prints those commands. Tests run
  malicious project files (a newline in a define, `!cmd`, path traversal) and check that nothing is executed.
* `--redact` (or `report.redact: true`) works on the structure of the report: design names, check ids, file names and
  paths become aliases (the same name always gets the same alias), secret input values become `<secret>`, tied values
  `<value>`, constants in conditions `<const>`, Yosys command lists a count and a sha256; Liberty files keep their
  public base name and sha256. The lock file and the `.glitchsat/` folder are NOT redacted (they stay next to the
  design), and neither are the progress lines printed while a run works; the run prints a note saying so. Share the
  report files only, never a zip of the project folder.
* Design sources must lie inside the project folder (a project file cannot make the tool read files elsewhere);
  `--allow-outside` (or `GLITCHSAT_ALLOW_OUTSIDE=1`) lifts this for a project file you trust.
* Names that GlitchSAT generates (monitor, wrapper, instances) all start with `gsat__`, so a design whose ports are
  called `ok`, `bad`, `clk` or `dut` is analysed like any other.
* Studio: `tools/studio/byod_view.py` adds the "Open my design" tab through the Studio's extension points
  (`Studio.registerView`, page install). `studio.py` loads it by itself when it finds `tools/studio/studio_byod.py`;
  `python3 tools/studio/studio_byod.py` starts the Studio with it as well (see `tools/studio/INSTALL.md`). The server
  stays on 127.0.0.1 with the Studio's Host/Origin checks; this module's requests also need a per-session token, every
  page gets a Content-Security-Policy, there is no CDN, and the folder picker only shows folders inside your home
  folder. A project that is not a gallery example is never run on one click: "Open and run" shows the Yosys commands
  of every build first and runs only after you confirm, and the confirmation is bound to the file content. Gallery
  examples run on a copy in a scratch folder, so the install folder stays clean.

## Limits (read before trusting a result)

* Modelled faults only: one-cycle flip/set/reset of a gate output or of a flip-flop's stored value. Not modelled:
  a glitch on one output pin of a flip-flop only (Q but not QN), faults lasting several
  cycles, timing or clock effects, faults on wires between two gates, multi-bit spatial effects, anything physical.
  `faults.per_cycle` and `faults.cycles` windows are refused rather than ignored.
* Bounded unless proved: "no attack" holds for the chosen number of faults and cycles. The unbounded proof is given
  only when k-induction and IC3 agree (or IC3's invariant passes its independent re-check); it often times out on
  bigger designs (secure boot, hardened: not decided in 60 s).
* One clock, one edge. Gated or generated clocks, latches and memories without `memory_map` are refused.
* Attacker inputs are free (the search picks the worst values); secret inputs are existential (the result shows the
  key value the attack needs). The "every key" (non-interference) question is not asked.
* The merge lint and its countermeasure detection come from the checker engine and inherit its limits (text scan of
  the RTL; untracked copies are reported as UNTRACKED, not as removed; sparse-encoding hits on a type name or a
  top-level port are dropped).
* Validation is random fault-free simulation (256 runs), not an equivalence proof: logic that only acts after a fault
  (alarms, redundant copies) is not covered; values that are unknown on either side (power-up X) are not compared,
  and the share compared is reported.
* Gate names: cells that `abc` creates carry no RTL line (Yosys drops the `src` attribute there), so some fault sites
  are named `AND gate #212`; flip-flops and cells kept by `proc`/`techmap` show their RTL line.
* `secret_flow` and `masking` checks are part of the file format only; they are reported as NOT RUN.
* Tested with: Python 3.13, Yosys 0.33 and 0.71, CaDiCaL, z3 (unbounded backend). Not tested: Windows, macOS,
  LibreLane run folders, VHDL, FPGA netlists.

## Files

| path | what |
|---|---|
| `glitchsat` | launcher (`./glitchsat run`, no install needed); lands as the `glitchsat` command's subcommands |
| `glitchsat_byod/project.py`, `schema.py`, `schema/` | the project file, its schema and validator, and the checks of every value (GS002) |
| `glitchsat_byod/flows.py`, `detect.py` | Yosys runs (elaboration, flows, normalisation, monitor, reference, the command allow-list); auto-detection with evidence |
| `glitchsat_byod/liberty.py`, `netlist.py` | Liberty reader and cell verification; netlist import to primitives (fault sites) |
| `glitchsat_byod/monitor.py`, `compose.py`, `validate.py` | generated monitor and wrapper; composition; simulation check |
| `glitchsat_byod/analyses.py`, `unbounded.py`, `lint.py` | minimum faults, attack surface, survival; proof adapter; checker adapter |
| `glitchsat_byod/cli.py`, `init.py`, `importers.py`, `report.py`, `errors.py`, `engine.py` | commands, wizard logic, importers, reports, remedies and redaction, error codes, where the engines are |
| `templates/` | the six property templates (plus `custom`) |
| `examples/` | the gallery with lessons, expected results and saved reports |
| `tools/studio/` | the Studio module, its launcher and install note |
| `scripts/` | `fetch_libs.sh`, `crosscheck_liberty.py`, `run_examples.py` |
| `tests/` | `python3 -m pytest -q tests`: 92 tests, about 45 s with everything installed. Tests that need something missing skip themselves; settings: `GLITCHSAT_ROOT` (repository, only when this folder is not inside it), `GLITCHSAT_YOSYS_SLANG` (Yosys with read_slang), `GLITCHSAT_LIBS`, `GLITCHSAT_STUDIO` (studio.py), `GLITCHSAT_SYNFI_NETLIST`, `SYNFI_CELL_LIB` |
| `docs/` | `SCHEMA.md`, `ERRORS.md`, `shots/` (Studio screenshots) |
| `results/` | `liberty_crosscheck.json`, `secboot_handwrapper_crosscheck.json` |

## Landing

This folder lands as `tools/byod/` in the GlitchSAT repository, together with the engines it uses. They are found
relative to the repository root (the first parent folder with `scripts/glitchsat.py`), then under `$GLITCHSAT_ROOT`;
an environment variable per engine overrides both. `glitchsat doctor` shows what was found where; a missing piece is
error GS021 with the folders that were looked in (never a traceback).

| what | lands at | used for | override |
|---|---|---|---|
| this folder | `tools/byod/` | the `glitchsat` subcommands (`init`, `run`, `check`, `explain`, `doctor`, `templates`, `examples`, `flows`, `liberty`, `import-sby`, `import-synfi`) | |
| the scale engine | `tools/scale/` | minimum faults, attack lists, replay (`scripts/gscale`) | `GLITCHSAT_SCALE` |
| the SAT engine | `tools/fastsat/` | the built-in SAT encoding (`scripts/glitchsat_sat.py`) | `GLITCHSAT_FASTSAT_DIR` |
| the unbounded engine | `tools/unbounded/` | the proof for any number of cycles (`src/ic3.py`) | `GLITCHSAT_UNBOUNDED` |
| the checker engine | `tools/checker/` | the merge lint (`survival/`) | `GLITCHSAT_CHECKER` |
| the Studio files | `tools/studio/byod_view.py`, `tools/studio/studio_byod.py` | the "Open my design" tab | `GLITCHSAT_STUDIO` |
| the repository | (root) | `scripts/glitchsat.py`, the netlist reader the engines share | `GLITCHSAT_ROOT` |

The secure-boot example carries its own copy of the four secure-boot RTL files (`examples/secure_boot/rtl/`,
sha256 in `rtl/SOURCES.sha256`), so no other folder is needed for it, and `glitchsat examples copy` rewrites any
relative path that would leave a copied example. The `glitchsat` command of the repository forwards the subcommands
above to `glitchsat_byod.cli.main`. Licence: Apache-2.0, like the repository.
