# Fresh-eyes enhancement plan (chair's synthesis)

Inputs: six independent reviewer lenses (technical, communication engineering, wow/demo, product/adoption, reviewer, story/editing), each judging only the shipped bundle, and 40 ranked items scored as impact x2 + feasibility + honesty x1.5 (files_ok from a rote path check). Every reviewer measurement quoted below was run once, in a scratch copy, by that reviewer. It is a **hypothesis to re-run**, not a project number, until it is reproduced and registered in `docs/NUMBERS.md`.

Model tiers used in the briefs: **sonnet** = rote (scripted runs, file moves, tests that pin known values); **opus** = decisions (what to claim, what to cut, wording of verdicts, merge of engines); **fable** = creative or difficult (root-cause work, new experiments, hero interactives, narrative).

---

## 1. Verdict

All six lenses agree on three things. The engine is sound and unusually well cross-checked on what it covers (reviewers reproduced `make reproduce` 36/36, 136 root tests and 324 product tests once the `synth.sh` exec bit was restored). The project has one excellent idea ("three guards on one wire are really one guard") that the front door buries under audit trail, codenames, three names, no licence and repeated caveats. And the effort went wide and shallow: about 975 research files and 43 MB re-check three 20-line toy designs, while cheap, high-yield measurements were never taken. The lenses diverge on where the next hours should go. The technical lens wants depth: root-cause the 3-to-2 drop, which it traces to the RTL encoding (0xCC xor 0x96 touches only two of three copy groups; a one-line re-encoding to 0xA5/0x5A restores 3 in every non-merging flow), then scale and real primitives. The communication-engineering and reviewer lenses want the "not applicable" verdict on communication engineering reversed, since the repo already holds a weight enumerator, an RM(1,3) codebook and burst-sensitive complement pairs. The wow and story lenses want one measured hero experience and one thesis ("the meeting point moves; it never disappears") in place of illustrations labelled "not computed". The product lens wants the ten-minute adopter path fixed (name, licence, async reset, RTL line numbers) before any new research. They do not conflict on substance. They conflict on order, and this plan sets the order: correct what is wrong, then add the communication-engineering chapter, then the measured demo, then packaging.

## 2. What was missed (consolidated, deduplicated, ranked)

Ranked by how much each changes a reader's judgement of the project.

1. **The headline result is misattributed.** "V2 needs 3 flips stored but 2 after Yosys 0.33" is framed as a synthesis-version effect. The technical reviewer measured an RTL encoding flaw: 0xCC xor 0x96 differs only in bits {1,3,4,6}, which belong to two of the three comparator copies, so two cycle-0 next-state stem flips (`$abc$275$new_n58_`, `new_n74_`) jump IDLE to BOOT. Re-encoding gives 3,1,1,3,3,3,3,3 against 2,1,1,2,2,2,2,2 in the product's own 8-flow sweep. The communication reviewer independently found that the accept constant itself changes the outcome (0xC3/0x3C, 0x1B/0xE4 and 0x2B/0xD4 give 3 on the same build). (Technical, Comms, Story.)
2. **The root CLI prints a wrong explanation.** `scripts/glitchsat.py` line 404 says the faults "hit independent redundant copies" whenever net names differ, and advises adding a copy. For the apt V2 witness that advice is false. (Technical.)
3. **Communication engineering is waved off although the material exists.** Dossier section 12 says "not applicable beyond Hamming-distance state encoding". Yet F0, CC, 96, 69 and C3 are RM(1,3) codewords, V1 and V2 are repetition codes, `research/c5/anchor/bf_*.json` is a weight enumerator, and the complementary pair 96/69 explains why one all-flop burst breaks every design. The reviewer scores this criterion 1/10. (Comms, Reviewer.)
5. **The demo performs nothing measured.** The best interactions are labelled "Picture, not computed" or "ILLUSTRATIVE". No waveform, animation, GIF or video exists, although the solver emits JSON witnesses and the testbenches dump VCD. There is no 3-minute script, no booth plan, a "60-second" script that runs 75-85 s, and a poster that is a text file. (Wow, Story, Reviewer.)
7. **No licence.** Nobody may legally reuse the code, so the Action, Docker and PyPI paths are blocked. The owner must decide. (Product, Technical, Reviewer.)
8. **Fragile invocation.** `glitchsat.py:426` executes `synth.sh` directly, so an extraction that drops exec bits gives `make test` 8 failed and `make reproduce` a PermissionError. (Technical, Reviewer.)
9. **The protection boundary is undrawn.** Only the comparator is triplicated. FSM, state decode, `sig`, clock, power-up and `boot_ok = (st==8'h96)` are single copies. The untold thesis: V2 moves the meeting point to `boot_ok`; it does not remove it. (Technical, Story.)
10. **Three incompatible headline datasets for synthesis variance:** 32 rebuilds (26/6), 264 configs (180/60/24) and 152 distinct netlists (94/38/20). (Story.)
11. **Findings are not actionable.** Culprits are ABC names with no RTL file:line, although `src` attributes exist. The "fix pattern" is canned text, and SARIF uses absolute paths with no region. (Product, Technical.)
12. **Real-design reach.** Async-reset flops are refused, there is no reset or stimulus sequence, attacker input is constant over the run, no hardened real primitive (OpenTitan) was analysed, and SYNFI's numbers were never reproduced. (Technical, Product, Reviewer.)
13. **Scale is unstated and poor.** No verdict within 300 s at about 2k and 7k gates, no gates-versus-time curve, and SIGTERM is not honoured during a long solve. (Technical, Product.)
14. **No probability view.** Every result is an adversarial minimum. No curve with a slope exists anywhere, although 182 attacking triples, 3 apt pairs, 15 V0 singles and 1 V1 single are already counted. (Comms, Reviewer, Wow.)
15. **Engine sprawl.** At least five diverging copies with different exit codes and explanation texts. (Technical, Product.)
16. **Physical track loose ends.** Spread layouts fail LVS 4/4 on a known filler bug, door-lock LVS fails pin matching, there is no extraction or per-endpoint STA, and the SPICE arrangement is clean-rail. (Technical, Reviewer.)
18. **Toy designs cannot show skip-the-check attacks.** No loop or retry counter exists, so clock_skip reports ">3" for V0 too. (Technical.)
19. **Unexplained quality signals.** Mutation scores of 72.5% and 67.6% with unexplained survivors, the `opt` flow's partial-x init silently skipping variants, the `--badge` silent write, and the exact z3 pin with Python ≥3.11. (Technical, Product.)
20. **Wasted effort to stop repeating:** the 1,190-line NUMBERS registry passes, predictor reconciliation, V4-V6, eight wow-fix rounds of disclaimer wording, 30 simulated personas and no real reader. (All lenses.)

## 3. Top 12 enhancements

Selection: the top 13 by score less P38. P38 (owner evidence pack, 32) is the highest-honesty item, but no agent can do it, so it runs as a separate owner track (section 6). P01 is promoted within the list because it corrects a wrong headline claim and gates P11, P21, P23 and P24.

| # | id | title | category | hours | impact | feas. | honesty | files_ok | total |
|---|---|---|---|---|---|---|---|---|---|
| 1 | P01 | Root-cause 3→2 as an encoding flaw; V2e; group-distance lint; two-netlist diff | engineering | 8 | 8 | 7 | 6 | yes | 32 |
| 2 | P11 | Code distance against measured fault budget (staircase and ceiling) | comms | 4 | 9 | 9 | 8 | yes | 39 |
| 3 | P13 | Coding-theory chapter: repetition, RM(1,3), fault-capacity table, Q&A cards | comms | 6 | 8 | 8 | 8 | yes | 36 |
| 4 | P12 | Noisy-channel waterfall: P(false accept) against p | comms | 5 | 9 | 8 | 6 | yes | 35 |
| 5 | P40 | Verdict Dial: measured hero interactive | wow-demo | 6 | 8 | 7 | 8 | yes | 35 |
| 6 | P18 | Decoder variants: SECDED state and syndrome consumer (predict, then measure) | comms | 6 | 7 | 7 | 9 | yes | 34.5 |
| 7 | P24 | "Same blueprint, 264 builders" reveal wall | wow-demo | 5 | 8 | 8 | 7 | yes | 34.5 |
| 8 | P21 | Solver Replay Theatre with waveform strips | wow-demo | 14 | 9 | 4 | 8 | yes | 34 |
| 9 | P14 | Burst against random errors: complement-pair experiment, burst event model | comms | 6 | 8 | 7 | 7 | yes | 33.5 |
| 10 | P15 | Hold against trap FSM; per-cycle fault budget | comms | 5 | 6 | 7 | 9 | yes | 32.5 |
| 11 | P23 | "Beat the Solver" game: predict, timer, win state, kiosk | wow-demo | 7 | 8 | 6 | 7 | yes | 32.5 |
| 12 | P36 | Verdict card and Claim Label (`--label`, `--report html`) | honesty | 10 | 7 | 5 | 9 | yes | 32.5 |

Next in line: P38 (owner track), P22 (story spine, 31.5; partly folded into the WOW plan), P08 (one engine, 29.5; its invocation fix is pulled into "do tonight"), P31 (front door, 29).

### Implementation briefs

**P01 — Root-cause the 3-to-2 drop.** Tier: **fable** for the diagnosis and write-up, **sonnet** for the sweep runs, **opus** for the README wording change.
- Create `rtl/v2e.v` (`sed "s/8'hCC/8'hA5/g" rtl/v2.v`; keep module name `v2` or rename it to `v2e` consistently). Create `docs/report/WHY_TWO_FLIPS.md`.
- Run `faultbound-wt analyze rtl/v2.v --top v2 --max-flips 3 --synth-sweep` and the same on `rtl/v2e.v`, on Yosys 0.33 and on the 0.38 build. Re-run the `research/c2/e2_variance` scripts with v2e added. Repeat for 0x5A and for one negative control (a code whose difference from 0x96 touches two groups).
- Trace the witness: from the apt netlist, list the fan-out of `new_n58_` and `new_n74_` to D bits and the copy membership of each bit. Render both netlists with `dashboard/real/render.py`, with the witness nets highlighted.
- Add `group_distance()` to `product/src/faultbound_wt/runner.py` behind `--lint-encoding`, with `tests/test_group_distance.py` (V2 warns, V2e does not).
- Acceptance: (a) the v2 row reproduces 2,1,1,2,2,2,2,2 and the v2e row 3,1,1,3,3,3,3,3 on 0.33 (or the doc states the measured row if it differs); (b) the 0.38 result is recorded; (c) WHY_TWO_FLIPS.md names both nets with the bits they drive; (d) the README row reads "encoding weakness exposed by some synthesis runs" only if (a) holds; (e) new numbers are in NUMBERS.md and `check_numbers.py` reports 0 stale.

**P11 — Distance sweep.** Tier: **sonnet** for build and run; **fable** for codebook selection and the figure.
- Create `scripts/comms/distance_sweep.py` (parametric V2 template: I, C, accept W, fail B), `results/comms/distance_sweep.csv`, `docs/comms/staircase.png` and `tests/test_distance_sweep.py`, which pins at least 4 rows.
- Two site sets per codebook: flops only and all nets. At least 13 codebooks, including 96/69, 2B/95, C3/3C, A5-encoded and {00,F8,1F,E7}. Run on 0.33 and 0.38.
- Acceptance: the CSV has columns `codebook, d_to_accept, min_flops, min_all, yosys, T, k_max, netlist_sha`; the plot shows the diagonal and the ceiling; the pytest passes in `make test`; runtime under 5 min is logged.

**P13 — Coding-theory chapter.** Tier: **opus** for claims and wording, **sonnet** for tests and edits.
- Create `docs/comms/CODING_VIEW.md` (about 800 words) and `docs/dossier/test_rm13.py` (span of the RM(1,3) generator; assert F0, CC, 96, 69 and C3 are members; minimum distance 4), plus `docs/edu/LAB4_CODES.md`.
- Edit: `PROJECT_DOSSIER.md` section 12 (replace "not applicable"), `EVIDENCE_MAP.md` row 7, `OWNER_DERIVATION_SHEET.md` (add question 6, G and H, left blank for the owner), `QA_ANSWER_CARDS.md` (8 cards), and deck slides 18-19 through `build_deck.py`.
- Acceptance: test_rm13 passes; the fault-capacity table has columns `design, code, n, k, d, detect, correct, measured min (flops), measured min (all), code gap`, and every measured cell cites a CSV row from P11, P14 or P18; no sentence claims novelty.

**P12 — Waterfall curve.** Tier: **fable** for method and figure; **sonnet** for the MC runs.
- Create `scripts/comms/bsc_channel.py`, `results/comms/waterfall.csv` and `docs/comms/waterfall.png`. The exact low-p series is Σ A_d p^d (1−p)^(N−d) from `research/c5/anchor/bf_*.json`; overlay an MC series via `anchor_sim.py` for p in [1e-3, 1e-1], with at least 100 hits per plotted point.
- Acceptance: the MC points agree with the enumerator series within the 95% binomial CI where both exist; the measured slope at low p equals the minimum flips (V0 1, V1 1, V2-stored 3, V2-apt 2); the caption reads "random-flip teaching model, not an attacker model and not physics". The reviewer's 0.132/0.0074/0.00012 values are re-derived, not copied.

**P40 — Verdict Dial.** Tier: **fable** for the interaction; **sonnet** for the data export and checker.
- Create `docs/wow/build_dial.py` (reads `research/c2/b2_scope/matrix.jsonl` and `research/c3/m1/m1_all_masks.csv`, writes `docs/wow/dial.json`). Embed the dial in `explainer.html` as the first-screen hero, replacing the "Picture, not computed" block. Extend `check_game_answers.py`.
- Four switches: reader (word / 4 bits / boot_ok), build (stored / 0.33, plus V2e once P01 lands), inputs attackable, power-up.
- Acceptance: every displayed digit equals its source row (the checker asserts all combinations); unsolved cells show "not measured"; the bound string sits under the digit; it renders at 390 px without horizontal scroll; keyboard operable.

**P18 — Decoder variants.** Tier: **fable** for design and pre-registration; **sonnet** for runs.
- Write `research/c6/comms/P18_PREREG.md` *before* running (predictions: SECDED flops-only 3; all-nets 1-2; V2c all-nets ≤3). Then create `rtl/v2_secded.v` and `rtl/v2c.v`, with a 256-input iverilog functional testbench each.
- Run the P11 site sets and `faultbound-wt analyze --scope-sweep --sweep-widths`.
- Acceptance: the prereg file is timestamped before the results file; predicted and measured columns are kept separate in CODING_VIEW; the functional testbench passes before any solver run.

**P24 — Reveal wall.** Tier: **sonnet** for the export; **fable** for animation and staging.
- Create `scripts/export_e2_wall.py`, `docs/wow/e2_wall.json` and `docs/wow/wall.html`. Toggle: 264 configs or 152 distinct netlists. Once P01 lands, add a V2e wall beside it.
- Acceptance: a check_numbers assertion for 180/60/24 and 94/38/20; per-tile tooltip with config and netlist sha; reduced-motion fallback; the four on-screen caveats from the item text; the "152 distinct" view is the default headline (see P28 rule).

**P21 — Solver Replay Theatre.** Tier: **fable**.
- Create `scripts/export_witness.py` (runs `glitchsat check` on the v0/v1/v2/apt/boot_ok netlists, replays them through `tb/generated/*_tb_faulted.v`, and parses VCD), `docs/wow/witness.json` and `docs/wow/theatre.html`.
- Acceptance: witness.json matches `results/reproduce_summary.json` (checker in `make test`); each frame shows its source file and netlist sha; the right-hand V2 side says "no 1- or 2-flip attack found within 6 ticks", never "safe"; the waveform strips come from the parsed VCD, not hand data; Play/Step/Reset and keyboard controls; `?kiosk=1` loop.

**P14 — Burst model.** Tier: **fable** for the model; **sonnet** for the product flag and tests.
- Create `scripts/comms/burst_sweep.py` and `results/comms/burst.csv`. Add `--event-model burst` to `product/.../config.py` and `_engine.py`, plus a `reports.py` lint for an all-ones word (global or per group) in the difference set.
- Acceptance: a 2x2 table (random-robust or not by burst-robust or not) with 96/69, {00,01,FF,02}, 2B/95 and {00,F8,1F,E7}; results re-checked with `--reduce none`; tests pin the 96/69 = 1-event row; labelled SIMULATED; closes EL2-3 in the dossier next-steps list.

**P15 — Trap against hold, per-cycle cap.** Tier: **sonnet** for the flag and runs; **opus** for the negative-result wording.
- Create `rtl/v2_trap.v` and `scripts/comms/trap_vs_hold.py`. Add `--per-cycle-cap N` to `scripts/glitchsat.py` and the product config.
- Acceptance: the table reports hold and trap at cap 1, 2 and none, for flops-only and all nets; the 1-flip trap witness is named with its net and explained; the wording is "this trap variant".

**P23 — Beat the Solver.** Tier: **fable**.
- Edit `docs/wow/game.html` only: a levels order, predict-first, a timer, a win banner, WebAudio with mute (default off), a scorecard, `?kiosk=1` auto-reset after 45 s, and the evidence moved to a "How we know" `<details>`. Store the best time in `localStorage` inside try/catch. Solve the 3-copy shared-wire level, or remove it.
- Acceptance: `check_game_answers.py` passes; no level shows "not checked"; Wiring B is either derived from the real apt witness (after P21) or keeps its illustration label; the persona-found defects (label overlap, 390 px clipping, unexplained "holds") are fixed and re-screenshotted with `research/c5/w8/shoot.py`.

**P36 — Verdict card and Claim Label.** Tier: **fable** for the visual design; **sonnet** for the template code and golden tests.
- Create `product/src/faultbound_wt/label.py` and `report_html.py` and `docs/labels/{v0,v1,v2_word,v2_bootok}.svg`. Add a step-summary line to `product/action/action.yml`.
- Acceptance: golden SVG tests; the footer "Model only. Not a security proof." is present in every output and has no flag to remove it; neutral colours, no ticks, no badge resemblance; every label field is taken from the run JSON, none hard-coded.

## 4. Communication engineering mini-programme

**Thesis:** "Redundancy is a code; the fault budget is its distance until the decoder sets a ceiling; random, burst and adversarial channels rank the same codes differently." Three experiments, in order, each feeding one table in `docs/comms/CODING_VIEW.md` (P13 is the write-up that wraps them).

- **E-C1: Distance and ceiling (P11, 4 h).** Question: does the measured minimum equal code distance? Set-up: 13 or more codebooks × {flops only, all nets} × {0.33, 0.38}, T=6, k≤min(d,6). Prediction (pre-register in `research/c6/comms/PREREG.md`): flops-only minimum = d_to_accept on every row; all-nets minimum ≤3 on every row. Falsifier: any flops-only row off the diagonal. Output: the staircase plot.
- **E-C2: Channel view (P12, 5 h).** Question: what does the same design look like under random flips? Set-up: exact enumerator sums from `bf_*.json` plus MC. Prediction: log-log slope = minimum flips; V2-apt sits one diversity order above V2-stored at low p. Falsifier: MC outside the CI of the enumerator series. Output: the waterfall and a column "A_d at d_min" for the fault-capacity table.
- **E-C3: Burst against random, and the decoder as attack surface (P14 + P18, 12 h).** Question: does the best random-flip code survive bursts, and does adding a decoder help an adversary? Set-up: the burst event model on four codebooks; SECDED and syndrome variants with pre-registered predictions. Predictions: 96/69 breaks in 1 burst (difference 0xFF); a correcting decoder lowers the flops-only cost from d to d−t. Output: the 2x2 burst table and the fault-capacity rows for V2_secded and V2c.

Deliverables: `CODING_VIEW.md`, three figures, three CSVs, two slides, one lab worksheet and 8 Q&A cards. P15 (trap/hold) is an optional fourth row. P16 (channel page), P17 (`code-report`) and P20 (telecommand receiver) come later. P20 is the strongest "real comms block" story, but it needs per-cycle input (P33) for its serial form, so it is deferred.

## 5. WOW/demo plan

**Spine (from P22):** "Three guards on one wire are one guard. Separate the wires and it takes three. But the reader is a wire too, and rebuilding the chip can move the meeting point. The meeting point moves; it never disappears." Every asset uses the guards metaphor only, and the 152-distinct-netlist dataset is the synthesis headline.

Three pieces, one experience:
1. **Verdict Dial (P40)** is the first screen of the explainer and the stage opener. The audience calls out a prediction, and the presenter flips switches: 3 → 2 → 1 → 0, every digit measured.
2. **Solver Replay Theatre (P21)** is the "see it happen" beat. The real witness flips `ok` at cycle 1 and the lock opens, beside the fault-free run. Split screen with V1 against V2, and the waveform strip under each.
3. **Reveal wall (P24)** is the climax and the booth attract loop. 264 tiles flip red, amber and green, then (after P01) a second wall for V2e turns mostly green: "found the cause, fixed it in one line".

Stage plan (3 minutes, zero typing): 0:00 show of hands on "three guards, how many glitches?"; 0:20 Dial on V1 (1); 0:40 Theatre on V1 against V2; 1:20 Dial reader switch to boot_ok (1); 1:50 wall (V2 then V2e); 2:30 one sentence plus the "What we did NOT show" panel; one live command (`glitchsat check` on V1, 0.1 s) with a recorded fallback. Booth: `theatre.html?kiosk=1` alternating with `wall.html`, plus P23 "Beat the Solver" on a second screen. Write the script as `docs/wow/DEMO_3MIN.md` (time/show/say table, timed aloud once by the owner).

## 6. Do tonight against do later

**Do tonight** (each under 3 h; agent items need no owner decision):

| id | task | hours | tier | acceptance |
|---|---|---|---|---|
| P08a | Call `synth.sh` via `['bash', path, ...]` at `scripts/glitchsat.py:426` and its product equivalent; also fix `validation/synth.sh` invocation | 0.5 | sonnet | `make test` and `make reproduce` pass on a tree extracted with Python `zipfile` (exec bits dropped) |
| P08b | Replace the "independent redundant copies / add another copy" text at `glitchsat.py:404` with a neutral "faults at N distinct nets; see explain for structure" until the structural classifier exists | 0.5 | opus | test asserting the apt V2 witness output no longer contains "independent" or "add another" |
| P01a | Create `rtl/v2e.v`; run `--synth-sweep` on v2 and v2e (0.33, then 0.38 if available); write the first draft of WHY_TWO_FLIPS.md with the measured rows | 2.5 | fable (runs: sonnet) | both rows recorded with netlist shas; no README change until reviewed |
| P11a | `scripts/comms/distance_sweep.py` on Yosys 0.33 only; CSV and staircase.png | 2.5 | sonnet (figure: fable) | at least 13 codebooks × 2 site sets in the CSV; a pinned pytest for 4 rows |
| P13a | `docs/dossier/test_rm13.py` plus a dossier section 12 correction to "covered in docs/comms/CODING_VIEW.md (in progress)" | 1.5 | opus | test passes; the words "not applicable" are gone from section 12 |
| P38a | **Owner only:** run the 3 START commands and the V1 demo yourself, do OWNER_DERIVATION_SHEET questions 1-3 by hand, write five sentences of your own for dossier section 17 | 2 | owner | handwritten page photographed; section 17 non-empty in the owner's words |


## 7. Cut or archive

Move these out of the front door into an evidence archive (`archive/` or a separate zip with `ARCHIVE_INDEX.md`). Delete nothing that a registered number cites.
- `docs/wow/W1_REPORT.md` … `W8_REPORT.md` and `docs/wow/persona_tests/`: archive. Remove persona scores from slides and front docs.
- `docs/wow/script_90s.md`: retire (replaced by DEMO_3MIN.md and a 150-word 60 s script). Retire DEMO_5MIN commands 5 and 6 from the stage path.
- Deck slides 7 (SPICE), 8 (layout), 9 (test counts) and A5 (ledger image): move to the appendix; A5 becomes a table.
- The structural predictor, V4-V6 sketches, rail-dip ledger columns, the numerics and fuzzing side tracks, and the 150-versus-155 reconciliation passes: archive with a one-line outcome each in `docs/STATUS.md`.
- Seven of the eight analogies in `analogies.md`: keep the guards only on front-door assets.
- Stop: further disclaimer-wording rounds, simulated-persona gates, NUMBERS.md reconciliation passes not triggered by a new number.
- Do not restart the closed physical track (P07) or OpenTitan (P02) before the top 12 are done.

## 8. Honesty rules for every new item

Global rules (enforce through banned and required phrase checks in `scripts/check_numbers.py`, run in `make test`):
- Every number carries its scope: design, netlist sha or Yosys version, T, k bound, fault sites, counting rule. Never "secure", "glitch-proof", "certified", "hardened" (unqualified), "proven safe" or "works on real chips".
- A reviewer's measurement is not a project number until reproduced and registered. Never quote 0.132/0.0074/0.00012, 3,1,1,3,… or 13-codebook results from this plan.
- No novelty claims over SYNFI, FIRMER, k-FRP or standard coding theory. Say "textbook coding theory measured on toy designs".
- Results for a fault model are labelled SIMULATED (model) or MEASURED (tool output on a stored netlist). Never physical.
- Pre-registered predictions are timestamped before results, and predicted and measured columns stay separate.

Per item:
- **P01:** say "encoding weakness that some synthesis runs expose; re-encoding restored 3 in N of M flows on Yosys X" with N, M and X filled in from the run. Do not say "the cause" unless the 0.38 run and the negative control agree. Do not say "fixed" beyond the measured flows, and state the merging flows that stay at 1.
- **P11:** "flops-only minimum matched code distance in N of N codebooks tested" — never "always equals". The ceiling is "observed", not a theorem.
- **P12:** "random-flip teaching model; not an attacker model, not a physical error rate". No BER claims for silicon, and no plotted points with fewer than 20 hits.
- **P13:** name the codes as facts with the test that checks them; no claim that the designers chose RM(1,3) on purpose.
- **P14:** "one modelled burst event = all state flops (or one group) inverted"; do not equate it with a real overclock or voltage glitch.
- **P15 and P18:** "this trap variant / this decoder"; report negative results at full prominence; no general rule about trap states or ECC.
- **P40, P24, P21, P23:** only measured values on screen; "not measured" where no row exists; the right-hand side of a comparison says "no attack found within the bound", never "safe". Illustrations stay labelled until they are derived from a witness. Keep one "What we did NOT show" panel per asset.
- **P24:** the on-screen caveats (one toy design, settings not independent, 120 of 180 from one merge option, effect previously reported by SYNFI).
- **P36:** the footer cannot be removed; no badge styling; no implication of certification.
- **P38:** agents ship only blank templates; they must not fill, draft or "suggest text" for owner sections.
