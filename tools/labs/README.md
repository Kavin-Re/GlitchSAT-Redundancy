# GlitchSAT Labs (experimental)

**Experiments in progress: try them, don't rely on them.**

Labs is the clearly marked experimental area of GlitchSAT. A Labs module asks a real question and can answer it
on at least one small example, but it is not finished, not reviewed like the main tools, and its results must
not be used to decide whether a product is safe. Nothing in Labs is part of the default learner path in the
Studio: the Labs tab sits in the "More" menu.

## The Labs bar (what every EXPERIMENTAL module must have)

1. It runs end to end on at least one small, meaningful example without crashing.
2. A `README.md` that says plainly WHAT WORKS, WHAT DOESN'T, and HOW FAR TO TRUST RESULTS, with every result
   labelled (see below).
3. A smoke test (pytest) that runs the example.
4. A result file in the common format `labs-result/1` (below).

## Labels

Every finding is EXPERIMENTAL and carries one of:

| label | meaning |
|---|---|
| MEASURED | counted or computed by running real tools (Yosys, clang, the checker) on real inputs in this module |
| SIMULATED | the outcome of a model (fault simulator, probing model); a model, not silicon |
| UNTESTED | stated or expected, but not checked by any run in this module yet |

## Modules

| module | status | what it tries to answer | README | run |
|---|---|---|---|---|
| `masking` | EXPERIMENTAL | Does a masked circuit still hide its secret from someone who measures one wire, with and without glitches, and after synthesis? | [`tools/masking/README.md`](../masking/README.md) | `labs.py run masking` |
| `bootloader` | EXPERIMENTAL | Experimental analysis of a real bootloader's fault hardening; details withheld pending responsible disclosure. | [`tools/bootloader/README.md`](../bootloader/README.md) | `labs.py run bootloader` |
| `opentitan_prims` | EXPERIMENTAL | Do OpenTitan's built-in fault countermeasures still need several bit flips to break after open-source synthesis? | [`tools/real/opentitan_prims/README.md`](../../real/opentitan_prims/README.md) | `labs.py run opentitan_prims` |
| `consttime` | PLANNED | Does the time a firmware routine takes, or the memory it touches, depend on a secret after the compiler has optimised it? | this page | - |
| `secretflow` | PLANNED | Can a secret reach an output the attacker can see? | this page | - |

### Planned: constant-time firmware checks (`consttime`, no code yet)

- Question: does a firmware routine (for example a MAC compare in the boot ROMs of `tools/firmware`) run for the same
  number of cycles and touch the same addresses whatever the secret is, at every `-O` level?
- Intended approach: run the RV32 simulator of `tools/firmware` with two secret values that differ, record the
  instruction trace and memory addresses, and report the first difference (a trace-difference check), then a
  symbolic version.
- Rule format: the project file already has the pieces: `inputs.secret` and `assets.secrets` name what is secret
  (`tools/byod/docs/SCHEMA.md`). No `consttime` check kind exists yet.
- Status: UNTESTED. Nothing is claimed.

### Planned: secret-flow checks (`secretflow`, no code yet)

- Question: can a key register, or anything computed from it, reach an output the attacker can see (a debug port,
  a status register), possibly only while some condition holds?
- Rule format (exists, "format only"): in `glitchsat.yaml`, a check with `kind: secret_flow` and
  `rule: "src =/=> dst when cond unless cond"`, plus `observe` (outputs the attacker can see) and
  `assets.secrets` (schema: `tools/byod/schema/glitchsat.schema.json`). `glitchsat check` lists such checks as NOT RUN.
- Intended approach: information-flow tracking on the synthesised netlist (taint through gates and flip-flops),
  then a solver query "can dst differ when only src differs?" for an exact answer.
- Status: UNTESTED. Nothing is claimed.

## Result format `labs-result/1`

Each module writes one JSON file (`results/labs_result.json`; for `opentitan_prims`, `labs/results/labs_result.json`).
`tools/labs/labs_result.py` builds and validates it.

| key | content |
|---|---|
| `schema` | `"labs-result/1"` |
| `module`, `title` | module id and plain name |
| `status` | `EXPERIMENTAL` or `PLANNED` |
| `question` | what it tries to answer, in plain words |
| `example` | `{name, description, command}` of the example that was run |
| `findings` | list of `{id, text, label, experimental: true, evidence}`; `label` is MEASURED, SIMULATED or UNTESTED |
| `labels` | the legend above (same in every file) |
| `caveats` | plain-language limits of the module |
| `run` | `{started, seconds, ok, errors, tools, rows}`; `rows` holds the raw numbers |
| `readme` | README path, relative to the module folder |

## Command line

Implemented as a small script:

```
python3 tools/labs/labs.py list              # every module: status, last run, findings per label
python3 tools/labs/labs.py run masking       # run the example, write the result file, print the findings
python3 tools/labs/labs.py show bootloader     # print the last result without running
```

Design for the main command (not wired yet): the `glitchsat` launcher gets a sub-command `labs` that calls
`labs.main()`, so the same commands read `glitchsat labs list`, `glitchsat labs run <module>`,
`glitchsat labs show <module>`. Every output line starts with the EXPERIMENTAL marker and its label; `run` exits
0 when the example ran without errors (whatever it found), 2 for a planned module, 3 when it hit the 570 s limit.
Labs commands never appear in `glitchsat --help` of the default commands; they are listed under "Labs (experimental)".

## Studio

The Studio shows Labs in its own tab (`studio/labs_view.py`), reached from the "More" menu, not from the learner
path. One card per module with its status badge, its question in plain words, its findings with labels and a
link to its README. It reads the same result files; it never runs a module itself.

## Tests

`python3 -m pytest -q tools/labs/tests tools/masking/tests tools/bootloader/tests tools/real/opentitan_prims/tests`
