# Start here (10 minutes)

**GlitchSAT** counts how many well-timed glitches an attacker needs to break a chip's protection, on a computer
model of the circuit, and explains the answer in plain words. Author: Kavin.K.K. Licence: Apache-2.0.

## Minutes 0 to 2: install (Linux Mint or Ubuntu)

```bash
git clone https://github.com/Kavin-Re/GlitchSAT-Redundancy.git
cd GlitchSAT-Redundancy
python3 -m venv .venv && . .venv/bin/activate
pip install z3-solver
pip install .
```

Optional: `sudo apt-get install -y yosys` (needed only to rebuild designs from Verilog source).

## Minutes 2 to 6: open the app

```bash
glitchsat-studio
```

Your browser opens GlitchSAT Studio (it runs on your computer only). Then:

1. **Welcome story.** Read it or press "Skip". It says why the tool exists, how a glitch attack works, what was
   found and what the limits are.
2. **Why protect chips?** A short lesson with true stories.
3. **Guided path.** Three tiny locks: one check, two copies, three copies. Guess first, then watch the attack
   replay one clock step at a time. Expected: 1, 1 and 3 glitches.
4. **A finding card.** Open one: severity, what an attacker would get, why it happened, and "How we found it".

## Minutes 6 to 8: real designs and your own

- **Explore a real chip**: a whole open-source chip design, PicoSoC with a three-copy boot check, needs 3, 2 or 1
  glitches depending on how it was built (a model result within 8 clock cycles). The drop to 2 comes from a weak
  stored code; the drop to 1 is the build tool merging the three copies.
- **Open my design**: the example gallery (each example has a weak and a protected version) and a wizard for your
  own Verilog file. Or on the command line:

  ```bash
  glitchsat examples copy hello_lock && cd hello_lock && glitchsat run    # needs Yosys
  ```

## Minutes 8 to 10: know what the numbers mean

- Every number is a **model result inside stated limits** (glitch count, clock cycles, one gate list). Nothing was
  measured on a real chip.
- Labels: MEASURED (a command here produced it), BOUNDED (exact within the stated clock cycles), recorded (stored,
  not computed now), SIMULATED, PROVED (only where a proof for any number of cycles says so).
- The build tools can change the answer. That is one of the main findings, not a bug.

| Question | File |
|---|---|
| Everything in one page | [`README.md`](README.md) |
| How severity is decided | [`tools/findings/SEVERITY.md`](tools/findings/SEVERITY.md) |
| Your own design in 5 minutes | [`tools/byod/README.md`](tools/byod/README.md) |
| Whole chips | [`tools/soc/README.md`](tools/soc/README.md) |
| Real OpenTitan netlists (SYNFI) | [`tools/real/README.md`](tools/real/README.md) |
| The written report | [`docs/report/PROJECT_REPORT.md`](docs/report/PROJECT_REPORT.md) |
| Every number and its source | [`docs/NUMBERS.md`](docs/NUMBERS.md) |
| Related work | [`docs/PRIOR_ART.md`](docs/PRIOR_ART.md) |
| Known weaknesses | [`docs/dossier/CRITIQUE.md`](docs/dossier/CRITIQUE.md) |
| Short names used in reports | [`docs/GLOSSARY.md`](docs/GLOSSARY.md) |

## Without installing anything

Open [`docs/explainers/index.html`](docs/explainers/index.html) in a browser: picture stories and replayed attacks,
no install needed.

## For the full reproduction

`sudo apt-get install -y yosys iverilog`, `pip install -r ci/requirements-ci.txt`, then
`make test && make reproduce && make check-reproduce` (36 of 36 rows with apt Yosys 0.33). See README, "The
research behind it".
