# Integration plan: interoperate with existing fault-injection tools

License: Apache-2.0. Project title: GlitchSAT: How Many Glitches Does Redundancy Stop? Date 2026-11-19. Agent IN.
Owner direction (chat, quoted): "even if something exists we integrate it". Reading of that direction: the project should interoperate with and build on existing tools, not compete with them. The project's own contribution is then limited to the pieces listed in section 1; nothing here is established as new.

Labels: MEASURED = command run in this session (logs in `integrations/data/`, tests in `integrations/tests/`); READ = from reading documents/repos, nothing run; DESIGNED = specified or code written but not exercised against the real tool; UNTESTED = code exists, third-party tool never run; ESTIMATED = my guess. Effort is ESTIMATED person-hours. Faults are modelled bit flips, not physical glitches.

## 1. What is ours and stays ours (the reason to exist once the tools are integrated)
min-flip search (solver chooses the smallest set of single-cycle flips over N reset-started cycles with the attacker input held constant), per-run provenance (design hash, Yosys build, bound, label), threat-model configuration, plain-language reports and fix patterns, teaching material, and the electronics bridge (circuit-level simulation, not silicon). Everything else below is "use or exchange with the existing tool".

## 2. Fault-injection tools

| Tool | What it gives that we lack | What we give that it lacks | Mode | Licence constraint | Effort (ESTIMATED) | Status |
|---|---|---|---|---|---|---|
| SYNFI (lowRISC) | Independent SAT check of a fault set on a netlist; user cell libraries (Liberty); gate-replacement faults (stuck-like mappings); applied by its authors to OpenTitan blocks (READ, `R10` section 1) | Solver picks the faults (min search), multi-cycle unrolling from reset with constant attacker input, flop-Q flips, provenance, report | **cross-check + export/import + wrapper** | Apache-2.0 (`compare/synfi_run/src/LICENSE`). Owner authorised running it. Keep notice if the clone is published | 6 h done; 4 h more for multi-stage | **DONE, MEASURED**: exporter, log reader, comparator (`synfi_adapter.py`); SYNFI re-run in `/tmp/work_in` worked (section 4); SYNFI replayed our exported V1 and V2 sets as effective |
| FIRMER (Tan et al., TCHES 2024) | Multi-cycle SAT with per-cycle symbolic input sequence, per-cycle/per-cycle-count budgets, bit-flip/set/reset types, benchmarks up to ~40k gates (READ, R10) | Control-FSM property (boot gate), Yosys flow, min search, provenance | **interchange only**: our JSON <-> a plain attack list; wrapper for the user's own install | No LICENSE file seen in the only repo reachable (CLEAVE) (R10 REPO). Treat as all rights reserved: read only, no code or text copied, never vendored | 3 h | **DESIGNED**; generic importer `from_attack_list()` UNTESTED against real output; no FIRMER format is parsed |
| CLEAVE (FM 2024) | Compositional verification of round-based crypto | Control FSMs | **cite-only** (+ same plain-list importer) | No LICENSE file (R10 REPO). No code or text copied | 0 | cite-only |
| FIVER (Richter-Brockmann et al., TCHES 2021) | BDD-based exhaustive injection with effective/ineffective/detected reports, mapping files (set/reset/flip), blacklist, large fault counts (claim: 90M+ faults, not verified here) | Search, multi-cycle FSM view, provenance | **export (config file) + wrapper** | Licence of the standalone repo UNVERIFIED (R10); CLEAVE's copy has none. Not run, not vendored | 3 h | **UNTESTED**: `to_fiver_config()` renders a config using the key names in the public sample (READ); mapping and library files left to the user |
| uArchiFI (CEA-LIST, FMCAD 2023, v0.2) | RTL + software binary threat models; saboteur insertion in Yosys (`fault_rtlil`); BMC counterexamples with fault timing (READ) | Post-synthesis netlist verdicts, min search, provenance | **export (Yosys script fragment) + wrapper** | LGPL-2.1 (R10 REPO). Not run; no code copied. If ever linked/vendored the LGPL terms apply: keep it a separate user-installed program | 4 h | **UNTESTED**: `to_uarchifi_script()` emits `fault_rtlil -cnt N -timing a:b -effect X` from option names in its README |
| k-FRP (Couroussé/Jan et al., eprint 2024/247) | Claimed unbounded, program-independent gate-level k-fault proofs; OpenTitan secure-boot step (snippets only; paper NOT read, R10) | Open toy, teaching, min search | **cite-only until read** | Code availability and licence UNKNOWN | 0 | **open question** (section 4 of IN_REPORT) |
| VerFI (emsec, HOST 2020) | Gate-level fault *simulation* with detected/ineffective/non-detected categories | Formal search instead of sampled simulation | cite-only; the campaign JSON can carry its fault lists later | BSD-3-Clause (R2 OPENED, README only). Not run (only SYNFI authorised) | 3 h if wanted | cite-only |
| FIESTA, SHADOWFI, NAIL and similar | Statistical / simulation-based campaigns at scale | Formal minimum | cite-only | various / unknown | 0 | cite-only |
| Commercial (Riscure/Keysight Inspector FI, Synopsys VC Z01X, Cadence, Siemens Austemper, OneSpin) | Physical glitching of real chips; ISO 26262 fault simulation | Free, teachable | cite-only | proprietary; nothing to run | 0 | cite-only |

Interchange between all of the above: `campaign.py` (schema `fault-campaign/0.1`, section 5). It is our own format. No third-party tool reads it natively; each tool needs an adapter.

## 3. Non-fault tools worth integrating

| Tool | Gives | Mode | Licence (as recorded in `THIRD_PARTY.md`) | Effort | Status |
|---|---|---|---|---|---|
| Yosys | Synthesis and netlist JSON (already the base). Its build changes the V2 verdict (0.33: 85 gates, 2-fault attack; 0.38+92: 83 gates, none; MEASURED, `docs/ENGINE_STATUS.md`) | **provenance reader** | ISC (verified there) | 2 h done | **DONE, MEASURED**: `yosys_provenance.py` reads `creator`, banners, optional `yosys -V`; test compares real 0.33 and 0.38+92 netlists |
| SymbiYosys / ABC-PDR | BMC and unbounded proofs already in `formal/` | already integrated; the campaign JSON can carry a `.sby` counterexample as a fault set | ISC / MIT-style (UNVERIFIED) | 2 h to read a counterexample VCD into fault sets | DESIGNED (not done) |
| OpenSTA / OpenROAD timing data | Per-endpoint slack, to rank fault sites by timing fragility; an engineering heuristic only, not a fault model | **import** slack report text -> annotation on targets; no run | OpenROAD BSD-3 (UNVERIFIED); OpenSTA licence not recorded here (UNVERIFIED, check before use) | 6 h | DESIGNED only; `research/c2/el1_spice` is empty in this bundle, no timing data exists locally |
| ngspice / sky130 | Circuit-level simulation for the electronics bridge. Not silicon | **cross-check** of a single gate-level fault against a transistor-level cell (circuit-level simulation, not silicon) | ngspice licence not recorded (UNVERIFIED); sky130 PDK Apache-2.0 (UNVERIFIED in `THIRD_PARTY.md`) | 8 h | DESIGNED only; an earlier `research/c1/spice/dff_template.cir` exists, not re-run here. Owner has not said yes to the SPICE bridge (`OPEN_DECISIONS.md` item 4) |
| SARIF 2.1.0 (GitHub code scanning consumer) | Findings shown in CI/PR UI | **export** (`ci_formats.to_sarif`) | format only | 2 h done | **DONE, MEASURED structurally** (tests build and inspect the document). Not uploaded anywhere; whether GitHub accepts the netlist-as-location mapping is UNTESTED |
| JUnit XML | Any CI test dashboard | **export** (`ci_formats.to_junit`) | format only | 1 h done | DONE (parsed with `xml.etree` in tests; no CI consumer tried) |

## 4. SYNFI re-run decision (constraint (a))
Time box was 20 min. The earlier venv is not in the bundle and `ray==1.8.0` has no wheel for this Python. In `/tmp/work_in/venv` (Python 3.13.18) the same package names *without pins* installed from PyPI in under 5 min (versions in `data/synfi_rerun_pip_freeze.txt`), but SYNFI first failed with `No module named 'pkg_resources'`; installing `setuptools<81` fixed it (MEASURED). Then:
- `rerun_v1_k1.log`: V1, k=1, all gates: 53 sets, 1 effective (the `ok` AND gate). Same counts as the earlier recorded run (MEASURED, 29.5 s).
- `replay_v1.log`, `replay_v2.log`: SYNFI fed the specs our exporter wrote from the solver's attack sets (`data/v1_replay.json`, `data/v2_replay.json`): both sets effective (MEASURED, 19.6 s and 14.4 s). The V2 set differs from the one in the earlier explicit spec (three OR-type gates `...parse_blif$252` in copies c0, c1, c2, versus the earlier NAND-type triple); SYNFI calling it effective means it is one more member of the effective triples (the earlier full run counted 182, MEASURED).
- Not repeated: V2 k=2 (50 s earlier) and k=3 full enumeration (11 min); V0 (no flop-Q replay).
Caveat: newer package versions than the pinned ones (SYNFI results here depend on that, as before); the run wrote `/root/.ray` and `/tmp/ray`.

## 5. Interchange schema (`fault-campaign/0.1`)
JSON object: `schema`, `label` (one of the five labels), `generator{tool,command?}`, `design{name,top?,netlist_file?,netlist_sha256?,yosys?}`, `threat_model{max_faults,cycles,fault_model,attacker_input,goal}`, `verdict`, `fault_sets[{id,effective,source,faults[{target{kind: net|cell|flop_q|port, name, id?}, cycle, type: bit_flip|set|reset|stuck_at_0|stuck_at_1|gate_replace, replacement?, duration?}]}]`. Validator: `campaign.validate()` (no external dependency). `schema/fault_campaign.schema.json` is a documentation copy for JSON-Schema users; it was not checked with a JSON-Schema validator. Examples: `examples/ex1..ex4`.

## 6. Order of work if the owner approves more
1. Read a k-FRP paper copy and decide whether it changes what we may say (blocks any "unbounded" wording).
2. Multi-stage SYNFI export that actually runs (needs a SYNFI workaround; our attempt crashed).
3. Counterexample-VCD -> fault-set importer for SymbiYosys runs (we already run these).
4. Only after an explicit OK: FIRMER / FIVER / uArchiFI runs, with `byo_adapters.run_external` and the provenance record.
