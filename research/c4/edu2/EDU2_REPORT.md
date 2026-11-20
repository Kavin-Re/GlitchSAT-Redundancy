# EDU2 report: lab kit moved to the shipped CLI
Agent EDU2, 2026-11-19. Modelled single-cycle bit flips on toy netlists; nothing physical; nothing established as new. Licence UNDECIDED; title TBD. All numbers MEASURED with the commands in `research/c4/edu2/verification.log` (driver: `verify_edu2.sh`), in a copy `/tmp/work_edu2/p`, venv `pip install ./product[test]` (faultbound-wt 0.0.1.dev0, Yosys 0.33, z3 5.4.1, Python 3.13). The install was done from the copy, so nothing was created in the tree (`product/build` and `*.egg-info` absent, checked). No make run.

## Changed (docs/edu/)
- `WORKSHEET.md`: Ex 2 now uses `faultbound-wt analyze ... --consumer-bits MASK` (read the number of `net@cycle` entries on the `minimum attack:` line). Ex 4 keeps `edu_scope.py` for the fanout rule only, stated plainly as not in the product, plus a CLI cross-check of rule A. New Ex 7 (`--sweep-widths`, V2, V1 optional, mini_v2) and Ex 8 (`--scope-sweep` table over goal x input-sites x init, with the discussion question "what does the table mean"). Ex 7 and 8 are 20 extension points on top of 100.
- `ANSWER_KEY.md`: Ex 2 table rewritten for the CLI, Ex 4 note, Ex 7 and 8 keys, run header and timing.
- `INSTRUCTOR_NOTES.md`: pre-class step 3, tool-scope pitfall, notes for Ex 7-8, rubric line.
- `LAB_GUIDE.md`: tool set paragraph (the stale "UPDATE" and "scope note" paragraphs removed), run sheet about 100 minutes with Ex 7-8 (about 86 without them), marked ESTIMATE and UNPILOTED.
Backup of the previous versions: `/tmp/work_edu2/edu_backup` (not in the tree).

## Re-run result: answer-key numbers
Every command of the key was re-run (40 commands, exit codes in the log). No minimum-flip number differs from the old key. Corrections made:
- V2 at `--max-flips 3`: 8.0 s (key and guide said about 12 s; now "about 8 s", times are machine-dependent, ESTIMATED elsewhere).
- Ex 2 witnesses: the old key listed net ids from `edu_scope.py` (30,77,84 / 13,14 / 13 / 13,14,18). The CLI names other nets: 0xFF three `new_n11_` nodes, one per copy at cycle 1; 0x0F `boot_word[2]@0` plus a mux at cycle 3; 0x1B `boot_word[1]@0`; 0x4E `boot_word[6]@0, [1]@1, [2]@2`. Costs unchanged: 3, 2, 1, 3; V1 0x0F 1. Note for graders: a 1-flip result prints no `MINIMUM ATTACK COST` line, only `minimum attack:`.
- The earlier remark that the 0x1B 1-flip route is a comparator-side net was replaced: the measured witness is a state flop.
Unchanged and re-confirmed: Ex1 V0 1, V1 1, V2 3 (k=1,2 none); Ex3 plain 85 gates min 2 (hash f954078f), merge 63 gates min 1 (d776226e); Ex4 stem 2 (fanouts 3,2), fanout 3, merged 1, stored V2 3/3; Ex5 mini_v1 exit 1 hash b3b890da, mini_v2 45 gates k=1 exit 0, k=2 exit 1 (2 flips), merged 33 gates 1 flip; Ex6 boot_ok 1 flip on V2 and mini_v2, bad config exit 3.
New, MEASURED: `--sweep-widths` V2: 0,1,1,2,2,3,3,3 (18 s), V1: 0,1,1,1,1,1,1,1, mini_v2 n=1..4: 0,1,2,2. `--scope-sweep` V2 (columns none/known, all/known, none/arbitrary, all/arbitrary): word 3,1,0,0; bits 0xF 2,1,0,0; boot_ok 1,1,0,0 (13.5 s); mini_v2: word 2,1,0,0; boot_ok 1,1,0,0. Matches PS4 and PS5 reports.

## Not done / limits
- Fanout rule (Ex 4 rule B) exists only in the research wrapper `edu_scope.py`; not reviewed; run inside the repository copy.
- Unpiloted: no student ran this; the 100-minute schedule is an estimate. Learning outcomes not measured.
- The Ex 7 b/c and Ex 8 a-c model answers are my reading of the numbers plus the M1 and PS4 reports; not classroom data. The "state-bit route" explanation for n=3 and mask 0x1B follows M1 and was only checked by seeing a state flop in the witness.
- Yosys 0.33 only; counts and hashes in Ex 3 and 5 differ on other builds. Net names in witnesses vary; grade numbers.
- `--init free_nongoal` and `--timeout-s` not used in the worksheet. Exit code of the Ex 2 shell loop is that of the last `cut`, not of the tool.
