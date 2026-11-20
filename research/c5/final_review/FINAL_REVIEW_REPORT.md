# FINAL REVIEW REPORT
All gates ran on a copy at /tmp/work_fr/p (tar copy, excludes as instructed); product venv /tmp/work_fr/v; product/build and egg-info deleted afterwards. Nothing in the project tree was changed except this file.

## 1. GATES
| Gate | Command (in the copy) | Result |
|---|---|---|
| reproduce check | `python3 ci/check_reproduce.py` | PASS: 36/36 rows match, 0 failed (engine not re-run) |
| reproduce --rerun | `python3 ci/check_reproduce.py --rerun` | PASS: 36/36 (engine re-run), 0 failed, no manifest warning (only the standing TAMPER-EVIDENCE text) |
| root tests | `python3 -m pytest tests -q` | PASS: 133 passed (17.6 s) |
| product tests | `pip install ./product[test]` in a fresh venv, `pytest product/tests` | PASS: 321 passed (85 s) |
| numbers | `python3 scripts/check_numbers.py` | PASS: 52 files, 0 STALE, 15 HISTORICAL (labelled as history) |
| numbers --verify | `python3 scripts/check_numbers.py --verify` | PASS: every line OK (M1b CSV identical, B3, layout 2.95 um sets, PS4 sweep rows 3,1,0,0 / 2,1,0,0 / 3,1,0,0 / 1,1,0,0) |
| dashboard | `python3 dashboard/build.py` | PASS: index.html md5 6992e082... before and after (identical) |
| START.md commands | the three `glitchsat.py check` lines | PASS: v1 k=1 attack on `ok`; v2 k=2 NO_ATTACK_UP_TO_BOUND; v2 k=1 goal boot_ok attack at cycle 3 |
| V2 product CLI | `faultbound-wt analyze reference/spike_netlists/v2.json --top v2 --max-flips 2 / 3 / 1 [--goal-out boot_ok --accept-value 1]` | PASS: k=2 none; k=3 minimum attack 3 flips (c2.m, c0.m, c1 net); boot_ok 1 flip. Note: without `--config` it prints a defaults warning (legitimate_value 0xC3, bad_value 0x96); START.md does not use the CLI, product/README does with `--config` |
| bundle dry run | `BUNDLE_ROOT=<copy> scripts/make_bundle.sh --out /tmp/work_fr/bout` | PASS: dry run only, PII scan clean (18 and 1891 text files), B = 1891 files 83.2 MB, largest 3.0 MB, exclusions hit as designed |

## 2. CLAIM GATE (unscoped uses; searched README, START, FINAL_STATUS, ONE_PAGE_SUMMARY, ONE_PAGE_FOR_THE_OWNER, explainer.html text, poster.md, script_60s.md, SLIDES_OUTLINE.md, deck slides+notes, dashboard/index.html)
Overall: clean. Every "secure", "proved", "novel", "first", "new" in these files is a negation or a quoted "not" statement. poster.md and script_60s.md have zero hits. No "real chip" claim, no "tested by" except "Tested by simulated readers, not real people" (explainer, correct), "users" none.
Hits worth a one-line fix (none is a hard claim error):
- docs/FINAL_STATUS.md:19 "four-act dashboard (break it, fix it, prove it, lay it out)". Fix: "(break it, fix it, bound it, lay it out)" and the same for the Act 3 heading in dashboard/build.py ("Act 3: Prove it, within a bound" is scoped, but the bare "prove it" is the word an examiner quotes). Frozen: owner/lead decision.
- docs/FINAL_STATUS.md:19 "a 'safe' design stays safe (within the model)": already scoped and quoted; acceptable.
- docs/wow/explainer.html "How you count changes who looks safe." (line ~357 of text): headline-level and not scoped; fix: "who looks protected in the model".
- docs/FINAL_STATUS.md:51 "Property proved" is the ABC PDR tool text and is scoped (k<=2, one netlist, not replicated): OK.

## 3. CONSISTENCY (appearances counted per file; all agreed where present)
| Number | README | FINAL_STATUS | ONE_PAGE(S) | deck | dashboard | Verdict |
|---|---|---|---|---|---|---|
| 3/2/1 flips (word stored / apt / boot_ok) | yes | yes | yes | yes | yes | identical |
| 133 root tests | yes | yes | yes | yes | n/a (build text) | identical, matches run |
| 321 product tests | yes | yes | yes | yes | n/a | identical, matches run |
| 72.5% / 67.6% mutation | yes | not in FINAL_STATUS (0 hits) | yes | 72.5 yes, 67.6 no | n/a | gap only, no conflict |
| 180/60/24 of 264 | yes | yes | yes | yes | yes | identical |
| 94/38/20 (152 netlists) | yes | yes | yes | yes | yes | identical |
| 150 of 163 | yes | yes | summary yes, owner page says 92% only | yes | not present | ok |
| 92% (62% / 83% baselines) | yes | yes | yes | yes | not present | identical |
| 36/36 | yes | yes | summary yes | no | no | ok |
| 255/255 | yes | yes | yes | no | no | ok |
| 182 triples | yes | yes | summary yes | no | no | ok |
| 2.95 um | not in README | yes | yes | yes | not present | gap only |
| 6/32 vs 32/32 | yes | yes | yes | yes | yes | identical |
Conflicts found: none in the front documents. Stale: `handoff/CONTINUATION/MORNING_NOTE_DRAFT.md` says "310 product" tests (now 321) and is not scanned by check_numbers; fix: edit the note before the owner reads it. check_numbers excluded: dashboard text and the deck are not scanned for 133/321 (deck agrees by hand check).

## 4. BRUTAL CRITIC (what an examiner still destroys tomorrow)
2. "Your headline numbers are one solver on toy designs the agents wrote, under a counting rule (stem = 1) nobody has shown physical." Everything in the 3/2/1 table is z3 plus a small brute-force anchor at T=4, k<=2. File: README.md "One glance" table. Fix: one sentence directly under the table: "toy designs written by the agents, one solver, counting rule not physical; the lesson is that the answer moves, not the value."
3. "No novelty, so why is this a project?" The method is SYNFI/FIRMER; E2 only replicates. File: docs/FINAL_STATUS.md, README.md. Fix (owner): choose the one-line contribution you will defend (a worked, reproducible teaching specimen with scope sweeps) and never claim more.
5. Front-door density: the README top-screen table has a single rail-dip cell of about 200 words; the examiner will read it as hiding, and a non-expert cannot parse it. File: README.md (one glance table, last row). Fix: shorten that cell to two sentences and move the rest to FINAL_STATUS.
Also open: LICENSE UNDECIDED means an all-rights-reserved bundle; the layouts are flow demos (LVS failed 4/4 on spread layouts); the unbounded proof is one tool and not replicated; unlicensed-code exposure sits in third_party_derived (kept out of the bundle).

- Allow-list audit (scripts/bundle_allowlist.txt, dry run 1891 files): third_party_derived, compare, numerics_audit, backup, shots, dl_repo, venv, __pycache__, .git, product/build are excluded (EXCLUDE section; verified hit counts). Nothing over 3 MB ships (desktop2.png excluded by size). PII scan clean.
- Things to consider (owner decides, none is a leak):
  a. 83 MB bundle B contains about 20 dashboard screenshots (research/c2/critics/cu/*.png, research/c5/dash2/*.png, dashboard/screens/*.png) and about 12 layout *.gds/*.png; shrink by adding `dir:critics` or `glob:*.png` under research/ if a smaller zip is wanted.
  b. Several shipped docs link to paths that the bundle excludes (third_party_derived/..., compare/..., backups): dangling links in the zip; harmless but an examiner may click. A line in README saying "some referenced paths are deliberately not in the bundle" is the cheap fix.
  c. layout GDS files derive from the sky130 open PDK cells; confirm THIRD_PARTY.md names the PDK and its Apache-2.0 licence before release.
  d. handoff/CONTINUATION/RUN_LOG.md, CHECKPOINT.md, AGENT_RULES.md ship; they contain agent logs and the owner's chat directions (no name or email found by the PII scan). Owner to skim before release.
  e. research/c5/rt3/synth_merge.sh.orig is excluded by glob (good); formal/runs (1020 files) excluded by path.
