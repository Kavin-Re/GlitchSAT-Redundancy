# GlitchSAT

Licence: Apache-2.0 (see the LICENSE file at the repository root).

## What it does, in plain words

Chips that check something important (a boot signature, a password, a debug lock) can be attacked by disturbing
them at the right moment: a short dip in the supply voltage, a clock pulse that comes too early, an electromagnetic
pulse or a laser spot. The disturbance flips a few internal signals and the check says "yes" when it should say "no".
Designers protect such checks by doing them more than once, in separate logic, so that one disturbed signal is not
enough.

GlitchSAT takes the gate-level netlist of a design (the list of gates and flip-flops that synthesis produces) and
asks a solver: **what is the smallest number of flipped signals that makes this design accept a wrong input?** If the
answer is 1, the protection does not work. If it is 3, an attacker must hit three signals in the right clock cycles.

It then helps you use that answer:

- a **margin estimate** that translates the number into the attack-potential points used by PSA Certified and by
  Common Criteria smartcard evaluations (the JIL document), with every assumption written out and changeable;
- a **fault-resilience evidence report** (one HTML file that works offline, and the same content as Markdown) that
  records what was analysed, with which tool versions and file hashes, what was found, and what it does not show;
- **SARIF** output, so findings appear in GitHub code scanning, a **GitHub Action** and a **pre-commit hook** that
  fail when the margin drops below a target you set.

What it is not: GlitchSAT models faults as single-cycle bit flips in a netlist. It never touched a chip. Every result
holds only within stated bounds (number of flips, number of clock cycles, this exact netlist). The attack-potential
figure is an estimate that **supports, and never replaces, evaluation by an accredited lab**.

## Install

```
pip install "glitchsat[solver]"            # once a release is on PyPI (the release workflow exists but has not been run yet)
pip install "./product[solver]"            # from a clone of this repository, today
pip install -r ci/requirements-ci.txt      # optional: the exact z3 version of the recorded results (reproduction)
```

Python 3.10 or newer (on 3.10 pip also installs `tomli`). The z3 solver is the optional `solver` extra (`z3-solver>=5.4.1,<6`): `glitchsat analyze`
needs it, the evidence commands do not, so `pip install glitchsat` alone is enough for reports, SARIF and `check` on
recorded results. The exact solver version used for the recorded results (`z3-solver==5.4.1.0`) is pinned only in
the reproducibility lock file `ci/requirements-ci.txt`. Yosys is needed only for Verilog input (Ubuntu:
`sudo apt-get install yosys`, or the OSS CAD Suite). The commands you get:

| command | what it does |
|---|---|
| `glitchsat analyze` | search a netlist for the smallest bit-flip attack (needs z3) |
| `glitchsat margin` | attack-potential margin estimate from result files (no z3) |
| `glitchsat evidence` | evidence report, HTML and/or Markdown (no z3) |
| `glitchsat sarif` | SARIF 2.1.0 for code scanning (no z3) |
| `glitchsat check` | CI check over a targets file: runs or reads results, writes reports and SARIF, exit 1 below target |
| `glitchsat validate-sarif` | check a SARIF file against the schema subset and GitHub's upload rules |
| `glitchsat evidence-example DIR` | write the example V0/V1/V2 outputs from the recorded results bundled with the package |
| `glitchsat-studio` | start GlitchSAT Studio, the local desktop app (see below) |
| `glitchsat-hook`, `glitchsat-evidence-hook` | pre-commit entry points |

The older names `faultbound-wt` and `faultbound-wt-hook` still work; the Python module is still called `faultbound_wt`.

## Try it in one minute

```
python3 -m venv .venv && . .venv/bin/activate
pip install ./product
glitchsat evidence-example /tmp/gs-example        # no solver needed
xdg-open /tmp/gs-example/v2_evidence.html          # or open it in any browser; it loads nothing from the network
```

The same files are in `product/examples/evidence/`: `v0_*`, `v1_*`, `v2_*` (evidence report as HTML and Markdown,
and the margin estimate as JSON) and `glitchsat.sarif` (all three designs). They are generated from results recorded
on 2026-11-19 and 2026-11-20 and kept up to date by a test.

What the examples say, in short (all modelled, all bounded):

| design | smallest attack (stored netlist, 6 cycles) | unbounded check (any number of cycles) | margin estimate, default assumptions |
|---|---|---|---|
| V0 (no redundancy) | 1 flip | no proof beyond 0 flips; attack with 1 flip | PSA 20, JIL 16 |
| V1 (duplicated check) | 1 flip | no proof beyond 0 flips; attack with 1 flip | PSA 20, JIL 16 |
| V2 (triplicated check) | 3 flips | proved: no attack with up to 2 flips at any cycle | PSA 20 with one glitch for all flips; PSA 21 if each flip needs its own laser shot |

Read the last column with care: under the default assumption one voltage, clock or EM glitch can flip any number of
signals in one clock cycle, so 1 flip and 3 flips both count as one glitch and score the same. Whether the redundancy
of V2 raises the attack potential depends on whether one physical disturbance can produce all three flips. The
report shows both readings side by side.

## Run it on your design

```
EX="$(glitchsat example-path)"
glitchsat analyze "$EX/v2.json" --config "$EX/threat.toml" --max-flips 3 --report v2.result.json
glitchsat margin   --result v2.result.json
glitchsat evidence --result v2.result.json --netlist "$EX/v2.json" --html v2.html --md v2.md
glitchsat sarif    --result v2.result.json --netlist "$EX/v2.json" --target-min-faults 2 --out v2.sarif
```

More inputs the report and margin commands accept (all optional, matched to a result by the netlist hash):

- `--surface FILE`: attack-surface listing (every minimum attack, which nets and cycles they use), from the
  attack-surface tool;
- `--lint FILE`: structural redundancy lint (did synthesis merge the redundant copies?);
- `--unbounded FILE` (one per flip budget): unbounded-in-time results, which prove "no attack with k flips at any
  cycle" or find an attack that needs more cycles than the bounded run looked at;
- `--netlist FILE`: the netlist itself, so its hash is recomputed and compared with the one recorded in the result.

## The margin estimate

`glitchsat margin` turns "minimum m flips" into attack-potential points in four explicit steps:

1. **Flips to injection events.** `flips_per_event` (default `any` for voltage, clock, EM and light; `1` for laser)
   decides how many physical injections the m flips need. `events_from_cycles=true` counts one event per distinct
   clock cycle of the minimum attacks (needs a complete attack-surface listing). `events=N` sets it directly.
2. **Events to exploitation time.** One event: "<= one day", two events: "<= one week", taken from the two PSA worked
   examples for glitching secure boot (JSADEN004 v1.3, section 5.1.3). Three or more: no published example, so the
   tool keeps "<= one week" and says so. `success_rare=true` applies the PSA note that a very low success probability
   pushes exploitation beyond one month.
3. **Other factors.** Identification and exploitation levels default to the PSA glitch examples (expert,
   specialized equipment, public knowledge, fewer than 10 samples). For JIL the equipment class follows JIL Table 10
   for the fault type (electrical glitch: standard; EMFI and high-end laser: specialized).
4. **Score.** PSA Table 1 and Table 2 (level ceilings 15, 20, 24); JIL Table 13 and Table 14 (bands Basic to High).

Every factor shown in the report carries its table or section number. The number of distinct minimum attacks and the
timing precision (in how many separate cycles the flips must land) are reported but not scored, because no cited
factor gives points for them. The tool also reports where a printed example and the point table disagree (the PSA
two-glitch example prints 23; Table 1 gives 21).

Change any assumption with `--assume key=value` (repeatable), or in a targets file under `[defaults.assume]` /
`[target.assume]`. Keys: `fault_type` (voltage, clock, em, laser, light), `flips_per_event`, `events`,
`events_from_cycles`, `success_rare`, `id_elapsed`, `id_expertise`, `id_knowledge`, `id_access`, `id_equipment`,
`exploit_elapsed`, `exploit_expertise`, `exploit_knowledge`, `exploit_access`, `exploit_equipment`,
`jil_equipment`, `jil_open_samples`, `target_psa_level`. A changed value is marked "set by the user" in the report.

Sources: PSA Certified Attack Methods, JSADEN004 v1.3 (issue 01/02/2024); Joint Interpretation Library,
Application of Attack Potential to Smartcards and Similar Devices v3.2.1 (Feb 2024). Links are in every report.

## The evidence report

Sections: summary in plain words; scope and bounds; netlist provenance (hashes as recorded and as recomputed, Yosys
and solver versions, hash of every input file); results per assumption (one row per solver run and netlist variant);
unbounded proof status; minimal attacks; attack surface; redundancy lint; margin estimate with every assumption;
limits; sources. The HTML file has no scripts and no external resources, and prints cleanly.

## In CI and before each commit

- **Targets file** (`glitchsat.toml`): which netlists to check and the margin each must keep (`target_min_faults`,
  optionally `target_psa_level`). A target can point at a recorded `result` instead of running the solver.
  `glitchsat check` exits 0 when every target meets its margin, 1 below target, 2 no verdict, 3 input error.
- **GitHub Action** (`product/action/action.yml`, composite): installs Python, Yosys (apt, ubuntu-24.04) and this
  package with its `solver` extra, runs `glitchsat check`, uploads SARIF to code scanning (codeql-action v4) and the
  reports as an artifact (name: input `artifact-name`, default `glitchsat-evidence-<job>`), and fails the job below
  target. Needs `permissions: security-events: write`. Third-party actions are pinned by commit SHA.
- **pre-commit**: hook ids `glitchsat-margin` (runs `glitchsat check` when RTL, netlists or targets change) and
  `glitchsat` (per-netlist analysis), defined in `.pre-commit-hooks.yaml` at the repository root.
- **Project template**: `templates/glitchsat-project/` has a targets file, a threat model, an example design, the
  workflow and the pre-commit configuration ready to copy.

Status: the action, the release workflow and the template workflow are written and checked locally (YAML parsed,
shell steps run with the same variables); they have not run on GitHub-hosted runners.

## GlitchSAT Studio

`glitchsat-studio` starts the Studio desktop app. Studio is installed with the package as package data
(`faultbound_wt/tools/studio/studio.py`). The command looks for it in this order: `$GLITCHSAT_STUDIO` (path to a
`studio.py`), the installed copy, then `$GLITCHSAT_ROOT/tools/studio/studio.py` and `tools/studio/studio.py` in the
current directory and each parent (a clone of the repository). Studio's project root is `$GLITCHSAT_ROOT`; if that
is not set, the command uses the clone above the current directory (the directory with `scripts/glitchsat.py`), and
without one Studio shows recorded results only. It runs Studio with the same Python and passes all arguments
through. If no copy is found it says where it looked and how to point at one, and exits 3.

## Tool bundles

Notes for getting GlitchSAT into the OSS CAD Suite and the IIC-OSIC-TOOLS image (how each is built, what GlitchSAT
needs from it, draft rule, open points such as the z3 pin): `product/packaging/BUNDLES.md`.

## Command reference: `glitchsat analyze`

```
glitchsat analyze NETLIST[.json|.v] [--config threat.toml] [--max-flips K] [--cycles T] [--top MODULE]
                  [--report FILE ...] [--exit-zero] [--no-honest-check]
```
- `--report` format comes from the extension: `.json`, `.sarif` (SARIF 2.1.0), `.junit.xml`. Repeatable.
- Exit codes: `0` no attack up to the bound; `1` attack found; `2` solver unknown/timeout; `3` usage, input, netlist
  or configuration error (including 'the honest input does not reach the goal in the fault-free design'); `4`
  internal error. `--exit-zero` forces 0 except for errors. (The reference engine `scripts/glitchsat.py` differs: it
  exits 0 for both verdicts and leaves the verdict in the text.) `--no-honest-check` turns the configuration error
  into a warning.
- Verilog input (`.v`) runs the repository's "plain" Yosys flow (same script as `scripts/synth.sh`) and needs
  `yosys` on PATH and `--top`. `--top` must be a plain identifier and the path free of quotes, `;`, backslash, `#`,
  control characters (exit 3); `--max-flips` is capped at 64; `--consumer-bits` syntax is documented in QUICKSTART
  4b/4d.
- Scope options (`--consumer-bits`, `--goal-out`/`--accept-value`, `--input-sites`, `--init`, `--count-rule`,
  `--scope-sweep`, `--sweep-widths`, `--sweep-count-rules`, `--synth-sweep`, `--timeout-s`) are described in
  `glitchsat analyze --help` and QUICKSTART sections 4b and 4c. Every report states its scope.
- Flags override the config.

### Threat-model config (TOML)
See `faultbound_wt/examples/threat.toml` (printed path: `glitchsat example-path`).

| key | meaning |
|---|---|
| `[faults] max_flips`, `cycles` | attacker budget and analysis horizon |
| `[faults] kinds` | `gate` and/or `flop`: which net kinds may be flipped |
| `[faults] include`, `exclude` | glob patterns on net names (any alias of the net matches); empty include = all |
| `[attacker] input`, `legitimate_value` | free input port and the value that does not count as an attack |
| `[attacker] model` | only `"constant"` (held constant over the run) |
| `[property] output`, `bad_value` | attack goal: output equals `bad_value` at some cycle |
| `[netlist] top`, `[solver] timeout_ms` | optional |

Restricting fault sites can only remove attacks (tested), so a restricted "no attack" says less than an unrestricted
one.

### Provenance
Every JSON report records the tool version, full command line, netlist SHA-256, gate and flop counts, z3 version,
Python version, UTC time, the Yosys `creator` string stored in the netlist JSON, and (Verilog input) the Yosys
version used to synthesize plus the source hash. The verdict depends on the exact synthesized netlist, so keep the
netlist hash with the result.

### Engine
The solver is a copy of the engine part of `scripts/glitchsat.py` (see the header of `src/faultbound_wt/_engine.py`
for origin and the three small marked changes). The copy is a snapshot and drifts unless re-synced by hand. No
third-party code is vendored.

## Limits

- Faults are modelled single-cycle bit flips of gate outputs and flop Q nets. No stuck-at, multi-cycle, timing or
  voltage effects; nothing was measured on hardware.
- Results are bounded: number of flips, number of cycles (the unbounded check removes only the cycle bound), this
  netlist. Another synthesis flow can change the minimum; the examples show this (V2: 2 flips after the RTL flows,
  3 on the stored netlist).
- The number of flips is not the number of physical glitches; the margin estimate shows both extreme readings.
- Supported cells: AND, OR, XOR, NOT, MUX and `$_DFF_P_` (Yosys `abc -g AND,OR,XOR,MUX` flow). Others give exit 3.
- Attacker input constant over the run; the goal is one equality on one output port.
- Scale untested beyond toy netlists (18 to 68 gates).
- No source was found in which an evaluation lab states that it accepts formal pre-silicon fault results as
  evaluation evidence. The report is design evidence for your own vulnerability analysis and for choosing what a lab
  should test first.

## Tests

```
pip install "./product[test]" && python -m pytest product/tests
```

`product/tests/test_evidence_*.py` cover the margin estimate (including every cited worked example), the loaders,
the reports, SARIF (schema subset and GitHub rules), `glitchsat check` exit codes, the pre-commit hook, packaging,
the action's shell steps and the Studio launcher. They run on the recorded results and need neither z3 nor Yosys.
