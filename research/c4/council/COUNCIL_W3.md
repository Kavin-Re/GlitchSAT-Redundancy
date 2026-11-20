# LLM Council W3: chairman report


Tags: **[F]** = fact the chair checked in a file at about 00:10 UTC (path given). **[F-rep]** = taken from an agent report and not re-run by the chair. **[I]** = inference.

Chair spot-checks done for this report (read-only greps): README.md, START.md, docs/FINAL_STATUS.md, docs/NUMBERS.md, dashboard/index.html and template.html, docs/dossier/PROJECT_DOSSIER.md s17, ci/check_reproduce.py, handoff/CONTINUATION/RUN_LOG.md entries 233-241, the research/c5 listing, and /tmp references in the research/c4 scripts.

---

## 1. Consensus (5 lines)

1. The measurement core is better anchored than at W2. ANCHOR brute force, the LEDGER encoding regression (16/16), and H2/H3 closing the HIGH command-execution bug all landed [F-rep]. The owner-only items are untouched: s17 is still "Left empty on purpose" [F: PROJECT_DOSSIER.md s17], and there is no LICENSE file [F: only LICENSE_CHOICE.md exists].
2. The front door contradicts the tree on safety. "until the fix lands (H2 in progress)" is still in README l.10 and l.54, START l.44, FINAL_STATUS l.12, dashboard/index.html l.64 and template.html l.63 [F], although H2 and H3 report the fix applied [F-rep: RUN_LOG 235-236].
3. Polarity result: keep it as one honest negative-control row and stop the physical track. Do no selectivity probe, no layout-domain 0->1 runs and no LVS fix. The control works mostly by construction, because the event raises the three match nets, which is the accept condition [I, shared by A, B and D].
4. Face A: the owner alone runs the 3 START commands, derives V2 spike = 3 and the mask bound on paper, and writes s17. No agent can substitute for this. Face B: no new features. Do one text sync of the safety notice and verify the shipped package as it stands.
5. Stop launching waves (W2 item 12 was violated again), freeze, and ship an allow-listed bundle that excludes third_party_derived/, compare/, handoff zips and backup/ folders.

## 2. Disagreements and who was likely right

| Topic | Positions | Likely right | Why |
|---|---|---|---|
| Are the test counts stale (99 / 139+1)? | A, B, C and D: stale | **Reviewers 2 and 4: no longer stale** | [F] README l.61 says 133 and l.64 says 310; START l.19 and FINAL_STATUS l.35 are updated; NUMBERS T.root.passed is 133 and T.prod.passed is 310 (RECON3). Still stale: NUMBERS l.22 ("99 passed") and `LEAD.verified` (l.74, "pytest tests 99 passed"). Both are arguably history but are not labelled HISTORICAL. The members read the tree before RECON3 landed. |
| W2 item 12 (cancel waves) | C: closed ("RT2 ran"); A, B and D: violated | **A, B, D** | [F] RUN_LOG 237-238 launched S3, RECON3, WP7, FP2, DS2, BP2 and BC3 at 00:01. research/c5 has wp7, w7 and w8 folders. C misread the item. |
| results/ and tb/ in the bundle | C: exclude ("regenerated"); A, B, D: include | **A, B, D** | [F] ci/check_reproduce.py l.2, l.6 and l.107 read results/reproduce_summary.json and results/reproduce/*.json, and the README cites results/. Excluding them breaks the reproduce check. |
| ENGINE_MANIFEST current? | A and B: hashes match; C: no evidence; H3: regenerate after review | **A and B, for the hash match** | A and B ran sha256 or check_reproduce without --rerun and saw matching hashes [F-rep from members]. Nobody showed `--rerun` output after H3 [I]. Make the --rerun on a clean copy the gate (to-do V2). |
| Code freeze time | A, B, C: 04:30; D: now | **D** | Every fix wave since W1 has created new staleness [F: RUN_LOG pattern; FIX2/FIX3 then H2 made the safety text stale]. Freezing code now costs nothing, because no code change is planned. |
| "Rail-wide" wording | A and C accept the reworded rail row; B and D: still overstated | **B and D** | [F] README l.26 says "a rail-wide 0-to-1 event on the three compare copies" and, in the same cell, "the domain is netlist hierarchy, not a physical rail". That is a self-contradiction inside one cell. |
| V0 under rail events | A and C: "V0 ties V2"; B and D: V0 whole-rail word >3 | **Unresolved; domain-dependent** | [F] README l.26 says "V0 does not under a cone event" for 1->0, and "(and on V1 and V0)" for the 0->1 union. B's ledger-cell domain mismatch (V0 "rail 1->0 = 1") is unchecked. Any sentence about V0 must name its domain. |
| Face B best action | A: text pass; B and D: clean-venv acceptance plus text; C: clean-clone demo on a foreign design | **B and D, scaled down** | RECON3 already measured the tests [F: NUMBERS l.56-61]. What is left: a clean-unzip run of START.md from the bundle itself, and the safety-text fix. The foreign-design demo (C, D-optional) is nice to have, capped at 40 min, and only if green. |
| Bundle shape | A, B, C: one allow-listed tree; D: viva kit (about 13 files) plus full tree | **D** | Two peer reviewers ranked it best. It shrinks what the owner must defend. The full tree remains the archive. |

## 3. Blind spots all four members missed

1. **They read a moving tree.** RECON3 had already fixed the test counts when they wrote [F]. Every "fix X" item must be re-grepped against the live tree right before the edit.
2. **Nobody defined the deliverable.** No one checked what the 11:00 IST submission must contain (rubric, format, size limit), so the bundle lists are guesses [I]. The lead must state this from the brief before building the zip.
3. **No member made the bundle self-reproducing.** /tmp paths remain in the research scripts [F: research/c4/b3/cmp_b3.py and minsubset.py, research/c4/t3/gate5.py, mutate_t3.py, score_merge.py and xcheck_t3.py, research/c4/l2/metrics.py]. The freeze gate should be: unzip in a clean directory, then run the START.md commands and `check_reproduce` from the unzipped copy. Mark the /tmp-dependent research scripts as "archive, not re-runnable".
4. **Owner availability is overnight in IST (05:30-11:00).** If the owner is asleep, every Face A plan is void. A fallback disclosure line needs a hard decision time (02:00 UTC). A 15-minute owner brief should be ready for 10:30 IST.
5. **The H2 semantic change to `--consumer-bits`.** A bare "3" used to mean bit 3 and now means mask 3 [F-rep: H2_REPORT s7]. Nobody grepped the docs, examples, viva cards or demo scripts for the old meaning. A live demo could show a wrong answer.
6. **The closure of the HIGH bug is self-verified only.** The cheap independent check is to replay RT2's original exploit inputs against the live tree (not a copy) and record pass or fail.
7. **The README is failing its own persona gate.** WP7 at 00:05: page gate 4/6 FAIL, and the README-top mean was 4.83 against a target of 6 [F: RUN_LOG 239]. That is a reason to cut the front door, not to run another persona wave.

## 4. Top 5 risks (ranked)

1. **Authorship and viva** [F: s17 empty; OWNER_DERIVATION_SHEET has blank slots per A, B, C and D]. No agent can mitigate this. The only mitigation is the owner's own work, or an honest disclosure line by 02:00 UTC.
2. **The safety notice is stale in 6 places** [F: README l.10 and l.54, START l.44, FINAL_STATUS l.12, dashboard index l.64 and template l.63]. An examiner sees either an unfixed HIGH bug or unmaintained docs. It is a 20-minute text fix, and check_numbers will not catch it unless a rule is added.
3. **Self-contradictory polarity and rail wording** [F: README l.26 "rail-wide ... the domain is netlist hierarchy, not a physical rail"]. The 0->1 cells come from one copied engine with no brute force [F-rep: LEDGER "Not done"]. This is easy for an examiner to attack.
4. **Churn and the size of the tree.** Waves are still launching [F: RUN_LOG 237-238]. The tree is about 770-790 MB with 348+ markdown files [F-rep: BC2]. A careless zip could ship third_party_derived/ (unlicensed CLEAVE-derived patch and a modified LGPL file) [F-rep: THIRD_PARTY.md, BC2 N6].
5. **Unverified reproducibility of the shipped bundle.** /tmp paths [F], the manifest was never shown with `--rerun` after H3 [I], and the semantic change to `--consumer-bits` was never grepped. The bundle may not reproduce, or the demo may mislead.

Also tracked (not in the top 5): deck slide 3 bare "V2 = 3"; slide 6 "build tool decides"; slide 8 "2.95 um" labelled as spacing; the PDF render (21:36) is older than the pptx (22:29) [F-rep: A]; the README predictor 92% and 180/60/24 [F-rep: C]; the "rule" wording at README l.47 is acceptable, because it already says "not a discovery" [F].

## 5. To-do list for 00:15-05:30 UTC

Each item is small and checkable. Role = agent type.

| # | When (UTC) | Role | Item | Check that proves it is done |
|---|---|---|---|---|
| C1 | 00:15 | CHAIR/lead | Cancel FP2, DS2, BP2 and BC3; trigger no fix round from WP7, W7 or W8. Code freeze now: no edits to scripts/, product/src, ci/ or ENGINE_MANIFEST unless V1 or V2 fails. | A RUN_LOG line "W3: queue cancelled; code frozen 00:15". |
| C2 | 00:15 | CHAIR/lead | Write down what the 05:30 deliverable is (format, recipient, size limit) from the course brief. | One line in CHECKPOINT. If it is unknown, ship both bundles from to-do B1. |
| O1 | 00:15-01:45 | OWNER | Run the 3 START.md commands on a copy. On paper, derive V2 spike = 3 and mask 0x0F = 2 via min(Hamming to idle, copies touched). Write s17 in 5 or more of your own sentences. Fill deck slide 11. | s17 no longer says "Left empty on purpose"; the paper is photographed or kept. No agent text is pasted in. |
| D1 | 00:30-01:00 | DOCS | Replace "until the fix lands (H2 in progress)" in all 6 places with: "RT2-N1 fixed by H2/H3 (research/c5/h2, h3; self-tested, not independently re-attacked); Yosys itself is not sandboxed; the GitHub Action has never run on GitHub." Rebuild the dashboard from the template. | `grep -rn "H2 in progress\|until the fix lands\|until the hardening fix" README.md START.md docs/FINAL_STATUS.md dashboard/` returns 0 hits. |
| D2 | same pass | DOCS | README l.26: replace "a rail-wide 0-to-1 event on the three compare copies" with "a 0-to-1 event confined to the three compare copies (netlist-hierarchy domain, not a physical rail; z3 only, not brute-force checked)". Make the same change in the deck, the outline, the explainer and the dashboard. | grep "rail-wide 0-to-1" returns 0 hits. |
| D3 | same pass | DOCS | Label NUMBERS l.22 and `LEAD.verified` (l.74) "99 passed" as HISTORICAL (pre-H3). Add check_numbers regexes for "H2 in progress" and "rail-wide 0-to-1". | `python3 scripts/check_numbers.py --verify` reports 0 STALE, and the new rules fire on a test string. |
| D4 | 01:00-01:30 | DOCS | Deck text only: on slide 3 add "full word, stored netlist, known power-up" next to V2 = 3; slide 6: "mostly opt_merge register merging (SYNFI-consistent)"; slide 8: label 2.95 um "selective-dip radius", separate from the 1.84 um copy spacing. Re-render the PDF from the current pptx. | The PDF modification time is later than the pptx; grep of the slide XML finds the new strings. |
| D5 | 01:00-01:30 | DOCS | Grep docs/, product/examples, the viva cards and DEMO_5MIN for bare decimal `--consumer-bits` values. Rewrite each one as an explicit mask (0x..) or bit list. | The list of hits is in RUN_LOG; each hit is fixed or marked as OK. |
| D6 | 01:30-02:00 | DOCS | Add a "What triplication bought" text table to README, built only from existing ledger cells (V1 vs V2 differ under: independent stem flips with hierarchy kept; fanout-branch counting; selective set size 2 vs 3; tie elsewhere; 0->1 union = 1 for both). | Every cell cites a ledger.csv row; no new numbers. |
| V1 | 01:00-01:45 | VER | Replay RT2's original N1 exploit inputs (the canary `--top 'm; exec -- touch X'`, and the path variant) against the live tree, in product and synth.sh. | The canary is not created and the exit code is not 0. One line in NUMBERS. |
| V2 | 02:00-03:00 | VER | Build bundle B from the allow-list (to-do B1) into a clean directory. In a clean venv, run the 3 START.md commands, `ci/check_reproduce.py --rerun` (no manifest warning), `pytest tests` and `pytest product/tests`. | 36/36 and 133/310 (or the new counts quoted). The output is saved as BUNDLE_CHECK.txt inside the bundle. |
| V3 | 03:00-03:40 (optional, only if V2 is green) | VER | Run `--synth-sweep` once on a real_designs/ design the project did not write. Paste the raw output into product/README as a demo, not a validation. | The output is pasted in, or a one-line stated limit if it fails. No code change. |
| F2 | 03:30-04:15 | VER | Final gate on the unzipped copy: check_numbers --verify (0 STALE); grep for "in progress", "until the fix lands", "rail-wide 0-to-1", "99 passed" (unlabelled) and "139 passed" (unlabelled), all returning 0; open the dashboard and the explainer once in a browser. | A gate log with 0 hits. |
| B1 | 04:30 | CHAIR/lead | **Bundle A, the viva kit** (about 13 files): START.md, README.md, docs/dossier/{ONE_PAGE_FOR_THE_OWNER, VIVA_SHEET, VIVA_ANSWER_CARDS, PROJECT_DOSSIER, AI_USE_DISCLOSURE_DRAFT, PROBLEM_STATEMENT_EVOLUTION}.md, docs/OWNER_DERIVATION_SHEET.md, docs/report/SLIDES.pptx and the PDF, DEMO_5MIN.md, ledger.png, docs/wow/explainer.html. **Bundle B, the full tree.** Include: README.md, START.md, README_FIRST.txt, Makefile, LICENSE_CHOICE.md, NOTICE.md, THIRD_PARTY.md, CONTRIBUTING.md; ci/, rtl/, tb/, tests/, scripts/, reference/, results/, validation/, formal/src and a summary, product/ (no egg-info, __pycache__ or build), dashboard/, docs/; research/c2-c5 reports, CSV/JSON and scripts, plus research/c4/b3_inputs and l2_inputs; layout scripts and reports; council reports; handoff/CONTINUATION/{RUN_LOG, CHECKPOINT, AGENT_RULES}.md. **Exclude:** third_party_derived/ (put it in a separate local-only zip so named), compare/, handoff/*.zip, the ui_pack zip, every */backup/ folder, shots/ folders, numerics_audit/, formal/runs, .odb/.vcd/.fst/.vvp/GDS files, venvs, work/dl folders, __pycache__, .pytest_cache, and files over 3 MB. MANIFEST with sha256 values; no top-level folder, per CHECKPOINT. | V2 passed on this exact zip; `unzip -l` shows no third_party_derived or backup paths. |
| B2 | 05:00 | CHAIR | A short owner brief: 3 things true; 3 not done (s17 status, Action never run on GitHub, licence UNDECIDED); the bundle names; the one sentence never to say ("V2 resists 2 flips" without its 4 qualifiers). | The message is sent and saved in CHECKPOINT. |


## 6. Aim higher: a redundancy-ROI diff (from D, endorsed by 3 of 4 reviewers)

The ledger's real content is a difference, not an absolute number: V1 and V2 tie in almost every row [F-rep: LEDGER s5; F: README l.26 says so]. The useful question for a designer is: "what did the extra copy buy, and at which flow stage did it stop paying?"

**Tonight:** write it only as the text table in to-do D6, built from existing cells, and name it as the next step. Build no code. The owner can derive and defend this table by hand, so it doubles as the Face A artefact.

**Evidence needed before claiming it as a contribution:**
- One baseline/hardened design pair the project did not write, run through the shipped CLI with the scope tuple printed.
- The diff cells anchored by the z3-free brute-force simulator.
- A prior-art check, because SYNFI and FIRMER already compare protected and unprotected designs [F-rep: SWEEP_S3 per RUN_LOG 240]. State "nothing established as new" until that check is done.

## 7. Claims in the answers that need verification before use

| Claim (who) | Status |
|---|---|
| README/START/FINAL_STATUS test counts 99 / 139+1 are stale (A, B, C, D) | **Wrong now** [F]: 133/310 since RECON3. Only NUMBERS l.22 and LEAD.verified still say 99. |
| W2 item 12 closed because "RT2 ran" (C) | **Wrong** [F: RUN_LOG 237-238]. |
| Exclude results/ and tb/ (C) | **Wrong** [F: check_reproduce.py reads results/]. |
| ENGINE_MANIFEST matches the tree (A, B) | Partly checked by the members; needs `--rerun` on a clean copy (to-do V2). |
| H2 310 / H3 133 (all members) | Confirmed as RECON3 MEASURED values in NUMBERS l.57-59 [F], measured on a copy, not in the tree. |
| The 0->1 control is "near-tautological" (A, D) | [I]. b3pol.py and pol.jsonl were not inspected. Phrase it as "largely by construction" only after reading the witness. |
| The LEDGER V0 "rail 1->0 = 1 (S)" cell contradicts DA3 whole-rail >3 (B) | Unchecked. Read ledger.csv before editing any V0 sentence. |
| Dashboard template l.172 "by the formal proof" reads as general (C) | Unchecked by the chair. Grep before D1, and scope it to "one netlist, result-word goal". |
| Dockerfile never built; Action never run (D) | The Action claim is consistent with README and H2 [F-rep]; the Dockerfile claim is unchecked. |
| PDF render older than pptx (A) | Unchecked by the chair; check the timestamps in D4. |
| No selectivity probe or pre-registration exists (A, B, C, D) | Consistent with the research/c5 listing [F: no PHYS folder]. A probe under another name is not excluded. The recommendation does not depend on it (the track stops either way). |
| WP6 persona gate status (B) | The newer WP7 result supersedes it: gate FAIL 4/6, README-top 4.83 [F: RUN_LOG 239]. |
| H2 changed the meaning of a bare `--consumer-bits` value (D) | [F-rep: H2_REPORT s7]. Downstream usage is unchecked (to-do D5). |
| Polarity "EM literature reports set-to-1" | Sourced only as SNIPPET-level in S3 [F-rep: RUN_LOG 240]. Do not cite it as established. |
