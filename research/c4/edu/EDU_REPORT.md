# EDU report: classroom kit
Agent EDU, 2026-11-19. Licence UNDECIDED; title TBD. Model only: modelled single-cycle bit flips; nothing physical; nothing established as new.

## Delivered
`docs/edu/LAB_GUIDE.md` (outcomes, prerequisites, 5-line setup, 90-minute run sheet), `WORKSHEET.md` (6 exercises, 100 points), `ANSWER_KEY.md`, `INSTRUCTOR_NOTES.md` (misconceptions, discussion questions, links to `docs/wow/explainer.html` and `game.html`, pitfalls, rubric), `starter_designs/` (3 Verilog designs `mini_v0..2.v`, their netlist JSON, threat configs, `MANIFEST.md` with Yosys version and sha256), `tools/edu_scope.py`, `tools/synth_merge.sh`. Verification: `research/c4/edu/verification.log` (every command, filtered output, exit code), driver `research/c4/edu/verify_edu.sh`.

## Verified (MEASURED, in a copy at /tmp/work_edu, Yosys 0.33, z3 5.4.1, faultbound-wt 0.0.1.dev0, fresh venv `pip install ./product`)
- Ex1: stored V0 = 1, V1 = 1 (`ok`), V2 = 3 (k=1,2 none, k=3 found in about 12 s). 
- Ex2: V2 masks 0xFF 3, 0x0F 2, 0x1B 1, 0x4E 3; V1 0x0F 1. Equal to `research/c3/m1/m1_all_masks.csv`; 0xFF equals the CLI result.
- Ex3: `rtl/v2.v` with the project recipe: 85 gates, min 2; plus `opt_merge`: 63 gates, min 1.
- Ex4: on the 85-gate netlist, stem rule 2 (fanouts 3 and 2), fanout rule 3; merged netlist 1 under both; stored V2 3 under both.
- Ex5: mini_v0 1, mini_v1 1 (`ok`), mini_v2 2 (k=1 exit 0 via the .v and the .json path); mini_v2 after `opt_merge`: 1.
- Ex6: `boot_ok` goal 1 flip (stored V2 and mini_v2); bad legitimate_value gives exit 3; pin_lock exit 1; async variant exit 3.
- The three starter JSONs regenerate byte-identically with `product/scripts/yosys_flow.sh`.

## Not verified / limits
- Only Yosys 0.33. The 83-gate / min-3 build (conda 0.38) quoted from E2 was not re-run here; a student on another Yosys will see other counts in Ex3 (the key says so).
- Scope options: `product/` had no consumer option when I finished (grep of `product/src` for "consumer": none), so Ex2 and Ex4 use `docs/edu/tools/edu_scope.py`, a wrapper of the research script `research/c3/m1/gs_mask.py` (mask) plus my own re-implementation of the fanout weighting of `research/c3/rep/scripts/rep_measure.py`. These are research scripts, not product features. Cross-checked only as stated above; not independently reviewed. UPDATE: `product/` gained `--consumer-bits` before I finished; I re-installed it in the copy and it gives 0xFF 3, 0x0F 2, 0x4E 3 (explicit MINIMUM ATTACK COST lines) and 0x1B an ATTACK_FOUND at k<=3 (cost line 1 not captured in my grep; edu_scope gives 1), agreeing with edu_scope.py. The docs mention the CLI form but still use edu_scope.py in the worksheet; the fanout rule exists only in edu_scope.py.
- `edu_scope.py` expects to sit inside the repository (imports `research/c3/m1/gs_mask.py`; override with `EDU_REPO`).
- No student ran the lab; timings (90 min) are my estimate; solver time total under 60 s is measured. Nothing about learning outcomes is measured.
- Misconception list and discussion questions are my inference, not classroom data. Classroom claim "no pure-software netlist TMR lab exists" is not made.
- The wow pages were skimmed for title and purpose only; `script_90s.md` and `poster.md` not reviewed.
- Net names in minimum attacks vary between runs; the key says to grade numbers.
- Product run in a venv with Python 3.13; the Quickstart says 3.11+.
