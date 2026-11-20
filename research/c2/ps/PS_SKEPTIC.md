# PS_SKEPTIC: would a hardware-security engineer adopt this?

Role: skeptical hardware-security engineer. Sources read: README.md, scripts/glitchsat.py, scripts/synth.sh, research/c1/R1_users_needs.md (head), research/c1/R2_tool_landscape.md, ci/README.md. No new measurements in this phase. Labels: [READ] = from the files above; [INFERENCE] = my reasoning, not evidence.

## 1. Would anyone adopt the current thing?

Honest answer: not as it stands, probably, and the reasons are about fit, not about the solver.

1. Hard-wired to one toy property. [READ] glitchsat.py defaults to `boot_word == 0x96`, attacker input `sig`, key `0xC3`. Anyone with a different design must know the flags exist and which ports mean what. There is no config file, so a result is not reviewable or re-runnable from a committed artifact.
2. No way to say which nets the attacker can reach. [READ] Fault sites are every gate output and every flop Q in the cone. Real threat models are narrower ("flops only", "not the alarm path", "only this module") and a verdict under an unrealistic model is noise. A reviewer will ask for this first.
3. Output is a bespoke JSON plus console text. [READ] Nothing a CI system or code-scanning UI ingests (SARIF, JUnit). Exit codes: 0 for both verdicts, 2 for timeout, so "attack found" does not fail a pipeline. [INFERENCE] That makes it a report generator, not a gate.
4. Provenance is thin. [READ] The JSON has a 16-hex-char netlist hash and a netlist path, but no Yosys version, no z3 version, no command line, no gate count in a form tied to the hash. [READ] The project's own headline finding is that the verdict depends on the exact synthesized netlist (Yosys 0.33 vs 0.38), so a result without the Yosys build is close to uninterpretable. This is the single most important gap to close.
5. Soundness limits the user must see. [READ] Bounded in k and cycles; single-cycle bit flips only; attacker input constant over time; flops initialised to 0/`init`; supports only AND/OR/XOR/NOT/MUX and `$_DFF_P_` (raises on anything else). A real netlist with a standard-cell library, reset flops or latches will just crash. [INFERENCE] Most real adopters hit the cell-type wall in the first five minutes.
6. Competition. [READ, R2] SYNFI (Apache-2.0, Yosys JSON in), uArchiFI (Yosys+BMC, counterexample), FIRMER/CLEAVE, FIVER exist. Nothing here is established as new. The credible niche is: pip + apt-Yosys install, minimal-attack search with an explanation, CI-friendly outputs, and an explicit synthesis-sensitivity record. [INFERENCE] If the install is not one command and the first run not under a minute, the niche is gone.
7. Trust. [INFERENCE] A security tool that says "NO_ATTACK_UP_TO_BOUND" will be misread as "secure". The wording must keep the bound in every output format, including SARIF/JUnit.

## 2. What the CLI must have to be worth trying

Inputs
- Yosys JSON netlist (primary, because it is what the engine consumes and what makes the synthesized-netlist caveat explicit) and Verilog (convenience, runs Yosys; record its version).
- Threat-model config in TOML, committed next to the design: attacker-reachable nets (include/exclude globs, kinds gate/flop), max flips, cycles, attacker input and legitimate value, target property (output == value). Time-varying attacker input only if the engine supports it (it does not yet; see E1 TODO in the build report).
- CLI flags override config; every effective value echoed into the report.

Outputs
- JSON (full detail; the source of truth), SARIF 2.1.0 (code-scanning UIs), JUnit XML (generic CI). Chosen by extension of `--report`, repeatable.
- Every format states: bound (k, cycles), fault model, that it is bounded, not a proof of security.
- A provenance block: tool version, command line, Yosys version/build (if Verilog was synthesized, and as parsed from the JSON `creator` string otherwise), netlist SHA-256 and gate/flop counts, z3 version, Python version, UTC time.

CI behaviour
- Exit codes distinct and documented: 0 no attack up to bound; 1 attack found; 2 unknown/timeout; 3 usage or input error (including unsupported cells). `--exit-zero` for report-only runs.
- Deterministic report content apart from timestamps and runtimes (so golden tests are possible).

Docs honesty
- README quickstart that works verbatim; limits section; no license claim (owner decision pending); no "secure" wording.

## 3. What I would still not trust after Phase 2 (predictions, to be checked in the build report)
- Cell-library netlists (only the generic gate set is supported).
- Scale: [READ] the engine builds a full unrolled formula; no benchmark here beyond the toy designs.
- Property language: one equality on one output port; no "any of these alarm outputs stays low" style properties.
- Reset/init handling, multi-clock, latches.
- Whether config-restricted fault sites are sound relative to the unrestricted run (restricting sites only removes attacks; I will say so and test monotonicity).
