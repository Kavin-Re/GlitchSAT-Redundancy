# Review notes (documents refresh, 2026-11-19)

Plain summary: the six documents in `docs/report/` were updated to the final state of the project. Checks (a) to (d) were done and are recorded here. Tool builds: Yosys 0.33, iverilog 12.0, z3-solver 5.4.1, LibreOffice (soffice) for slide rendering, SymbiYosys from the `formal` env.

## (a) Every command in DEMO_5MIN.md, run in a fresh shell (`env -i`, minimal PATH, from `/home/user/project`)
| Command | Result |
|---|---|
| `make test` | PASS: 10 passed in 20.2 s (at review time; now 189 passed (2 skipped), re-measured by RECON6 on the unpacked bundle 2026-11-20; 133 at RECON3/RECON4) |
| `make reproduce` | PASS: exit 0; V2 spike k=3 min 3 as before. Times differ from the stored file (k=2 1.326 s vs 1.178 s; k=3 7.17 s vs 5.139 s) |
| `make check-reproduce` (added to the doc) | PASS: "36/36 rows match" |
| `python3 scripts/glitchsat.py check rtl/v1.v --top v1 --k 1 --cycles 6 --out results/x.json` | PASS: ATTACK_FOUND, min 1, net `ok` |
| `python3 scripts/replay.py results/x.json` | PASS: `agrees_with_solver: true`; fault-free `boot_word=69` |
| `python3 scripts/glitchsat.py check rtl/v2.v --top v2 --k 2 ... --out results/y.json` | PASS: ATTACK_FOUND, min 2 (this machine, Yosys 0.33). This matches the doc's wording |
| `python3 scripts/glitchsat.py check reference/spike_netlists/v2.json --top v2 --k 2 ...` (added) | PASS: NO_ATTACK_UP_TO_BOUND |
| sby PDR run on `formal/runs/s2_v2_k2_prove_abc_pdr_d6.sby` (added, from a copy with `formal/gen`) | PASS: "Property proved", 0.83 s, `DONE (PASS, rc=0)`; run twice |
| Opening `dashboard/index.html` and `v1_zoom_ok.png` | files exist; the dashboard was NOT opened in a browser by this worker |
Fixes to the doc: the old text said V2 "resists 2 on the original netlist" without a command; a spike-netlist command was added so both halves can be shown. The sby block needed `formal/gen` copied next to the `.sby` file (the `.sby` uses relative paths), so the doc now shows that. Exit codes of piped commands were read from the tool output, not from `$?` of a pipe. Side effects: `make reproduce` overwrote `results/reproduce_summary.json` and `results/logs/*`, and replay wrote `tb/generated/*`; I restored `results/` and `tb/` from a tar taken before (the summary file is byte-identical to the original). `results/logs/` was restored too.

## (b) SLIDES.pptx
Rebuilt with python-pptx (the earlier build script was in the scratchpad; this is a new script in the scratchpad, not saved in the repo). Now 18 slides (was 13): added the unbounded proof, depth sweep, netlist caveat, layout checks, repository health; real-designs slide updated. Rendered with LibreOffice to PDF, then PNG, and **all 18 slide images were viewed** (a second look at slides 8, 12 and 17 after a wording change). Problems found and fixed: text was small and the slides looked empty (raised bullets to 26 pt, tables to 17-18 pt); a clumsy sentence on slide 8 and the title of slide 12 were reworded. No overflow, no missing image (the V1 layout picture on slide 11 shows; its annotation text inside the picture is tiny, as in the source PNG). Speaker notes carry the longer caveats. Not checked: PowerPoint itself (only LibreOffice rendering). `SLIDES_OUTLINE.md` was regenerated from the same script.

## (c) CLAIMS_CHECK.md
Rebuilt with a "Re-checked" column. More than 25 rows were compared with files or re-run (examples: 36 rows in the summary, 90 sweep entries DONE, 294.27 s and 474.94 s, antenna 47 and 48 nets, grid 0 off-grid, 85 gates by re-synthesis, door-lock slack and 28 devices / 20 nets, PDR proof re-run). Rows marked "no" were copied from sources and not re-checked. One finding: the stored `reproduce_summary.json` times are not exactly reproduced on re-run (they vary), the verdicts are identical.

## (d) Framing check
Kept: strong evaluated project, not novel, no hardware, modelled faults, layouts not DRC-clean as a whole. Changed: "bounded" now carries the exception (one unbounded proof, V2 spike netlist, 2 flips, this fault model, no independent certificate); every V2 claim names the netlist and tool build; "SymbiYosys not installed" was removed everywhere; "antenna and off-grid not run" was replaced by the results. SYNFI: "SYNFI run: result pending; see compare/synfi_run/SYNFI_RESULT.md if present". `compare/COMPARISON.md` was not touched.

## Open points I could not settle
1. Why two syntheses of the same Verilog differ. Note a detail: FORMAL.md says Yosys 0.33 and 0.38 both gave the 83-gate netlist, but `scripts/synth.sh` on this machine (Yosys 0.33) gave 85 gates (40 AND, 25 OR, 20 NOT). The 83-gate netlist was not re-created here.
2. The dashboard and `docs/FINAL_STATUS.md`/`README.md` (owned by the lead) may still say "SymbiYosys not installed" or "antenna not run"; I did not check or edit them. `ci/README.md` also still says SymbiYosys is not installed anywhere in the project.
3. The door-lock numbers are the worker's report (I checked slack and device/net counts against its logs, not the LVS "port errors" wording).
4. Not re-run: layout flow, validation exhaustive runs, depth sweep, fuzzing, numerics, browser view of the dashboard.


Later note (2026-11-19 about 19:30 UTC, F1): the line above that says "Kept: strong evaluated project" is superseded; PROJECT_REPORT now says "reproducible, independently cross-checked teaching project on toy designs" (finding CC-1 in `research/c2/critics/cc/CC_FINDINGS.md`; fix log `research/c2/f1/F1_FIX_LOG.md`).
