# Security notes for people running GlitchSAT

GlitchSAT is a learning and early-design-check tool for small designs. Please read this before you run it on files you did not write.

- **Yosys is not sandboxed.** When you give the tool a Verilog file (`.v`), it calls Yosys to build the gate-level netlist. Yosys runs with your user rights. Only analyse Verilog files you trust. Stored JSON netlists (`.json`) do not call Yosys.
- **A command-injection bug was found and fixed.** A red-team review found that a module name or Verilog path could be pasted into a Yosys command (high severity, measured: `research/c5/rt2/RT2_REPORT.md`). Names are now validated and written to a Yosys script file instead of a command line (`scripts/synth.sh`, `scripts/glitchsat.py check`, `product/`, `docs/edu/tools/synth_merge.sh`). The fix was re-tested with a harmless test name on 2026-11-19 (rejected with exit 3, no file written; `research/c5/h2/H2_REPORT.md`, `research/c5/h3/H3_REPORT.md`). No outside reviewer has checked the fix.
- **Not tested on GitHub.** The GitHub Action (`product/action/action.yml`) had only its two shell steps run locally, and the Dockerfile (`product/Dockerfile`) was built and run locally only. Do not run the Verilog path or the Action on untrusted input.
- **Limits of the cycle and flip budget.** The installable CLI caps `--cycles` at 200 and `--max-flips` at 64 so that a bad argument cannot exhaust memory.

Remaining findings and their history: `docs/dossier/CRITIQUE.md`, `research/c5/rt3/RT3_REPORT.md`.

To report a problem, open an issue on the repository.
