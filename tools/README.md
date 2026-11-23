# tools/: the parts of GlitchSAT

Each folder is one part with its own README, tests and stored results. Run one part's tests from the repository
root with `python3 -m pytest -q tools/<name>/tests` (`tools/secboot_hw` for that one), or every suite with
`python3 scripts/test_all.py`. No environment variables are needed; tests that need z3, Yosys, a SAT solver binary
or a Yosys with `read_slang` skip without them.

## The app and the everyday tools

| Folder | What it does, in plain words |
|---|---|
| [`studio/`](studio/README.md) | GlitchSAT Studio, the local app: welcome story, lesson, guided path, findings, real chips, Labs (`glitchsat-studio`) |
| [`byod/`](byod/README.md) | Use GlitchSAT on your own design: project file `glitchsat.yaml`, templates, example gallery, the "Open my design" view (`glitchsat init`, `glitchsat run`) |
| [`findings/`](findings/README.md) | Turns every result into a plain-words finding with a severity, a cause and "how we found it" ([severity rules](findings/SEVERITY.md)) |
| [`soc/`](soc/README.md) | Whole open-source chips (PicoSoC, Ibex demo system): one security decision at a time, replayed on the whole chip |
| [`real/`](real/README.md) | Real OpenTitan netlists published with SYNFI, and the OpenTitan hardening primitives study |
| [`checker/`](checker/README.md) | Did the protections (repeated checks, sparse state codes) survive synthesis, placement and compilation? |

## Engines and analyses

| Folder | What it does |
|---|---|
| [`scale/`](scale/README.md) | The GlitchSAT question on designs of thousands of gates |
| [`fastsat/`](fastsat/README.md) | Direct SAT encoding; runs a bundled pure-Python solver, CaDiCaL or Kissat |
| [`unbounded/`](unbounded/README.md) | Results for any number of clock cycles, not only a fixed window |
| [`surface/`](surface/README.md) | Attack surface, and a lint that finds redundant copies merged by synthesis |
| [`harden/`](harden/README.md) | Suggests and checks fixes for merged redundancy |
| [`shots/`](shots/README.md) | Layout-aware fault model: one laser or EM spot hits every cell within a radius |
| [`vlab/`](vlab/README.md) | Virtual clock-glitch lab: a timing-based fault model on a simulated circuit (no proof claim) |
| [`firmware/`](firmware/README.md) | Secure-boot ROM firmware on a RISC-V simulator under instruction-level faults |
| [`secboot_hw/`](secboot_hw/README.md) | A small secure-boot hardware block (SHA3-256) with its model, RTL and tests |

## Labs (experimental: try them, don't rely on them)

| Folder | What it does |
|---|---|
| [`labs/`](labs/README.md) | The Labs runner, the common result format and the labels MEASURED / SIMULATED / UNTESTED |
| [`masking/`](masking/README.md) | Does a masked circuit still hide its secret after glitches and after synthesis? |
| [`bootloader/`](bootloader/README.md) | Fault hardening of a real bootloader; details withheld pending responsible disclosure |

## Data and preparation

| Folder | What it does |
|---|---|
| [`datasets/`](datasets/DATASETS.md) | Published results of related work, transcribed, and a fetch script for public datasets |
| [`opentitan/`](opentitan/README.md) | Prepared pipeline for more OpenTitan security IP (not yet run) |
| `check_wording.py` | The shared wording and path check used by the test suites |

Third-party sources inside these folders (SYNFI, OpenTitan, PicoSoC wrappers) keep their own licences; see
[`../THIRD_PARTY.md`](../THIRD_PARTY.md).
