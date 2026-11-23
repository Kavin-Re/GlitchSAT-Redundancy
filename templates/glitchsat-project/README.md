# Project template: fault-margin checks with GlitchSAT

Copy this folder as the start of a hardware repository (or copy its files into one).

| file | what it is |
|---|---|
| `rtl/boot_check.v` | example design: a triplicated compare (replace with your own) |
| `threat.toml` | threat model: attacker input, goal output and value, fault kinds |
| `glitchsat.toml` | targets: which netlists to analyse and the margin each must keep |
| `.github/workflows/glitchsat.yml` | GitHub Actions: runs the check, uploads SARIF to code scanning, fails below target |
| `.pre-commit-config.yaml` | the same check before each commit |

Local run (Python 3.10+, Yosys on PATH for Verilog input):
```
pip install glitchsat            # or: pip install ./product from a GlitchSAT clone
glitchsat check --targets glitchsat.toml
```
Results go to `glitchsat-evidence/` (an HTML and Markdown evidence report per target) and `glitchsat.sarif`.
Exit 0 = every target meets its margin, 1 = below target, 2 = no verdict, 3 = input error.

All results are bounded and about modelled bit flips; the attack-potential figure in the report is an estimate that supports,
and never replaces, lab evaluation.
