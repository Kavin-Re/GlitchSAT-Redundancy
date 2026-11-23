"""GlitchSAT evidence tools: attack-potential margin estimate, evidence report (HTML/Markdown), SARIF 2.1.0 and CI check.
Pure Python standard library; reads result files and never needs z3 (except `check` on targets without a recorded result).
The recorded V0/V1/V2 results in data/recorded/ are copies of results/reproduce/*.json (MEASURED, 2026-11-19) and of
attack-surface / merge-lint runs on reference/spike_netlists (MEASURED, 2026-11-20, exhaustive method, numpy, no z3)."""
