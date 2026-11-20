# IN_REPORT: integration with existing fault-injection tools

License: UNDECIDED. Project title: working title TBD. Agent IN, 2026-11-19. Deliverables: `integrations/INTEGRATION_PLAN.md`, `integrations/*.py`, `integrations/tests/`, `integrations/examples/`, `integrations/data/`. Labels: MEASURED = run in this session; READ = read only; DESIGNED / UNTESTED = written or specified, never exercised against the real third-party tool.

## 1. What "integration" means here (honest statement)
Integration means: our data can be converted to, and compared with, another tool's inputs and outputs, and we record where each result came from. It does NOT mean we validated the other tools, nor that they validated ours. Where SYNFI agrees with our solver this is agreement on three toy designs under a stated model, produced with hand-built SYNFI inputs; it is not independent proof of either tool. FIRMER, FIVER, uArchiFI and k-FRP were not run; the adapters for them are UNTESTED code that no one has tried against those tools. No third-party code or text was copied or vendored. Nothing was pushed or sent anywhere.

## 2. What was integrated (code + tests; 29 pytest tests pass, `cd integrations && python3 -m pytest tests -q`, 1.3 s, MEASURED)
- **Fault-campaign JSON** (`campaign.py`, `schema/fault_campaign.schema.json`, 4 examples). Our own interchange format; hand-written validator; fault types bit_flip/set/reset/stuck_at_0/1/gate_replace. Examples ex1 (V1 min set), ex2 (V2 min-3 set), ex4 (V2 no attack at k=1) come from `scripts/glitchsat.py` run this session on `reference/spike_netlists/v{1,2}.json` (N=6 cycles; MEASURED); ex3 is ILLUSTRATIVE invented data for mixed types.
- **SYNFI adapter** (`synfi_adapter.py`): (a) exports a fault set as a SYNFI fimodel with explicit `fault_locations` (net id -> driving cell -> stage), keeping the user's start state; flop-Q flips and non-flip types are listed in `skipped`, never dropped silently; (b) reads the RESULT/EFFECTIVE lines of `synfi_report.py` logs and stock summary lines; (c) compares minimum fault count and, when SYNFI lists sets, whether our set is among them (18-char cell-name tail match, flagged weak when tails repeat); (d) imports a SYNFI spec's explicit locations as a campaign. Tested on the recorded V0/V1/V2 logs from `compare/synfi_run/out/`: V1 min 1 (the `ok` gate) both; V0 min 1 both (set-level check skipped, our witness is a flop-Q flip); V2 no effective set at k=1, 2 (61 sets; 1830 pairs) and min 3 both; k=3 full run 182 effective of 35,990 (60 listed). All MEASURED in the earlier SYNFI session; this session re-parses those logs.
- **SYNFI re-run succeeded within the time box** (constraint (a)): Python 3.13 venv in `/tmp/work_in`, unpinned PyPI packages plus `setuptools<81` (needed for `pkg_resources`); about 5 min of setup. MEASURED: V1 k=1 gives 53 sets / 1 effective, equal to the earlier run. MEASURED: SYNFI replayed the specs our exporter wrote from the solver's sets (V1: the `ok` gate; V2: a three-gate OR-type triple, one in each of the copies c0, c1, c2): both reported effective. This is the first end-to-end check that the exporter output is accepted by SYNFI. Logs: `integrations/data/replay_v{1,2}.log`, `rerun_v1_k1.log`, versions in `synfi_rerun_pip_freeze.txt`. Not repeated: k=3 full enumeration (11 min), V2 k=2.
- **Yosys provenance reader** (`yosys_provenance.py`): parses `creator` fields, log banners, optional `yosys -V`; records netlist sha256 and cell histograms; `diff()` flags different builds. Test reads the real 0.33 netlist (`reference/spike_netlists/v2.json`, 76 cells incl. flops) and the 0.38+92 netlist (`formal/gen/v2.json`, 91 cells incl. flops, conda-style build) and flags them as different builds. The ex1/ex2 examples carry this block.
- **SARIF 2.1.0 and JUnit exporters** (`ci_formats.py`): structure checked in tests; not uploaded or consumed by GitHub/any CI (UNTESTED as a consumer).
- **Bring-your-own wrapper** (`byo_adapters.py: run_external`): refuses to run without an explicit acknowledgement flag, uses a timeout and no shell, records provenance. Tested only with a stand-in Python command, which tests the wrapper, not any tool.

## 3. What was only designed (UNTESTED / not done)
- `to_uarchifi_script()` (Yosys script fragment from option names in uArchiFI's README) and `to_fiver_config()` (config from the key names in FIVER's public sample): written from READ documentation only; the real tools never ran, so key names, semantics and units may be wrong.
- `from_attack_list()`: plain CSV/JSON importer so a user can paste faults reported by FIRMER/FIVER/uArchiFI; no tool-native output parser exists.
- OpenSTA/OpenROAD slack import, ngspice/sky130 cross-check, SymbiYosys counterexample -> fault-set importer: plan rows only. `research/c2/el1_spice` is empty here.
- Multi-cycle (multi-stage) SYNFI export: emitted with a warning; our earlier two-stage SYNFI run crashed (`KeyError: 'sig'`), so this path is untested.
- Not done: GitHub code-scanning upload (outward action, forbidden), any JSON-Schema-library validation of the schema file.

## 4. OPEN questions that need the owner's explicit OK before anything is run
| # | Tool | Licence as found | What would be run | Why it matters |
|---|---|---|---|---|
| 1 | FIRMER (Tan et al., TCHES 2024; only reachable copy is inside CLEAVE) | No LICENSE file (R10 REPO); standalone repo licence UNVERIFIED | their build and a netlist converter, on our V1/V2 netlists | would give an independent multi-cycle SAT cross-check; without a licence, "run privately, do not redistribute" is the only safe stance and the owner should decide |
| 2 | uArchiFI (CEA-LIST) v0.2 | LGPL-2.1 | Docker image + `fault_rtlil` on our RTL (needs Yosys 0.61, their Docker) | closest tool in spirit; run as a separate program only |
| 3 | k-FRP (Couroussé/Jan et al., eprint 2024/247) | UNKNOWN (paper not read; eprint returned 403 earlier) | nothing yet: first need the owner's OK to read a copy the owner supplies | highest-risk overlap for any "unbounded proof" wording |
| 4 | FIVER (Richter-Brockmann et al., TCHES 2021) | UNVERIFIED (standalone repo has a LICENSE per R2, contents unread; CLEAVE's copy none) | Boost + CUDD build, `bin/release/verify` | BDD-based exhaustive cross-check; heavy build |

## 5. Surprises and caveats
- The solver's V2 minimum-3 set differs from run to run and from the one used in the earlier SYNFI explicit spec (OR-type vs NAND-type gates); both are effective in SYNFI. Many equivalent minimal sets exist (SYNFI counted 182 effective triples), so set-level comparison is weak; the minimum count is the robust comparison.
- SYNFI's stock summary line double-counts (`Injecting 3660 faults` for 1830 pairs); the reader does not use it as a set total.
- SYNFI effective-set labels are truncated to 18 characters of the cell name; matching by tail can be ambiguous (flagged).
- SYNFI's `pkg_resources` import fails on current setuptools; pin `setuptools<81`.
- Number labels: all counts above are MEASURED by the commands/logs named; effort estimates in the plan are ESTIMATED.
