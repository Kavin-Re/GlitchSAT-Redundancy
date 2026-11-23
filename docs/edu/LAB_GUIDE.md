# Lab guide: "Three guards, one wire" (about 100 minutes; timings ESTIMATED, UNPILOTED)


## What this lab is, and is not
A computer-model lab. Students take small gate-level netlists, ask a solver for the smallest set of **modelled** single-cycle bit flips that makes a design accept a wrong input, and see how that number moves when the consumer, the synthesis step or the counting rule changes. **Nothing physical:** no chip, no FPGA, no glitch, no laser, no voltage. A "flip" is an XOR on a net in a model. Every result is "bounded result under this model; not a proof of security". The lab does not teach how to attack real devices.

Why it is a useful lab (INFERENCE, not a survey): the closest classroom material found in research (`research/c3/r24/R24_REPORT.md` section 2) is FPGA- or board-based. This lab needs only a laptop and runs in seconds. The report found no pure-software netlist-level TMR lab, but absence of search results is not proof that none exists.

## Learning outcomes
After the lab a student can:
1. Read a gate-level netlist verdict (`ATTACK_FOUND` / `NO_ATTACK_UP_TO_BOUND`, exit codes 1 / 0) and state exactly what it covers: goal, bound (flips, cycles), start state, input treatment, netlist hash.
2. Explain why duplicated checks that recombine in one net (V1) give one flip, and why three copies with disjoint outputs (V2) raise the cost.
3. Show that "flips needed" depends on **what the consumer reads** (4 bits vs 8 bits vs the accept flag).
4. Show that it depends on **the netlist, not the RTL**: one extra synthesis command (`opt_merge`) can merge the copies.
5. Compare two fault-counting rules (stem = 1 vs cost = fanout) and say why the rule is a stated assumption, not a fact.
6. Edit a small design, re-run the flow, and report the result with its scope and hash.

## Prerequisites
- Digital design basics: gates, flip-flops, a finite-state machine, Verilog `assign` / `always @(posedge clk)`.
- Command line and Python 3.10+. No SMT or formal-methods background needed (the solver is a black box that returns the smallest attack or "none up to the bound").
- Instructor: read `docs/edu/INSTRUCTOR_NOTES.md` first; do the lab once (about 25 minutes of work, most of it reading).

## Setup in 5 lines (details: `product/QUICKSTART.md`)
Run in a **copy** of the repository (the research scripts and `make` rewrite files; the lab only writes to `edu_work/`).
```
cp -r <project> ~/lab && cd ~/lab && mkdir -p edu_work
python3 -m venv .venv && . .venv/bin/activate && pip install ./product      # pulls z3-solver from PyPI (shipped CLI `faultbound-wt`; add [test] only if you want pytest)
sudo apt install yosys                      # needed for Exercise 3 and 5 only (Verilog to netlist)
faultbound-wt analyze reference/spike_netlists/v2.json --top v2 --config product/src/faultbound_wt/examples/threat.toml --max-flips 2   # expect NO_ATTACK_UP_TO_BOUND, exit 0
```
Check: the last line prints `v2: NO_ATTACK_UP_TO_BOUND ... 68 gates, 8 flops` and `netlist sha256 289355dc...`. If students have another Yosys build, **only** the exercises that re-run Yosys can differ (see Instructor notes, pitfalls). The stored netlists in `reference/spike_netlists/` and `docs/edu/starter_designs/*.json` do not depend on the student's Yosys.

Tool set (updated by EDU2, 2026-11-19). **Every exercise uses the shipped CLI** `faultbound-wt analyze` (with `--consumer-bits`, `--sweep-widths`, `--scope-sweep`) and `product/scripts/yosys_flow.sh`, except one: the fanout-cost counting rule of Exercise 4, which is **not in the product** and still needs the research wrapper `docs/edu/tools/edu_scope.py` (it imports `research/c3/m1/gs_mask.py`, so run it inside the repository copy). `docs/edu/tools/synth_merge.sh` is the shipped Yosys recipe plus one line (`opt_merge`). All answer-key numbers were re-run on the shipped CLI in a clean venv: `research/c4/edu2/verification.log`.

## Run sheet (about 100 minutes; ESTIMATE, UNPILOTED)
No class has run this. The times below are the author's estimate of reading and typing time plus measured solver time (MEASURED, `research/c4/edu2/verification.log`: V2 at 3 flips 8 s; the whole lab's solver time is about 1 minute). Expect to adjust after one real session; please record your own times.
| Min | Block | What happens | Instructor |
|---|---|---|---|
| 0-10 | Setup and story | Students run setup. Open `docs/explainers/explainer.html` (3 min, "Three guards, one wire"); state the scope sentence above. | Put "model only" on the board. Collect setup problems. |
| 10-20 | Ex 1 | Predict V0/V1/V2 minimum flips, then run (V2 with 3 flips takes about 8 s). | Ask for predictions as a show of hands before anyone runs. |
| 20-30 | Ex 2 | Consumer width with `--consumer-bits`: 0xFF, 0x0F, 0x1B, 0x4E. | Let students guess which 4-bit mask is cheapest. |
| 30-42 | Ex 3 | Re-synthesise V2 two ways (project recipe vs plus `opt_merge`). | The surprise block: same RTL, 2 flips vs 1 flip. |
| 42-50 | Ex 4 | Count the same attack under stem = 1 (CLI) and cost = fanout (`edu_scope.py`). | Draw a fanout-3 net on the board. Say that rule B is not in the product. |
| 50-55 | Break | | Check slow machines on Ex 5. |
| 55-73 | Ex 5 | Design a variant of `mini_v1` and test it. | Walk around; look for "improvements" that synthesis undoes. |
| 73-80 | Ex 6 | Which asset? Accept flag vs word; config sanity exit code 3. | |
| 80-86 | Ex 7 (extension) | `--sweep-widths` curve on V2 (0,1,1,2,2,3,3,3). | Run the V2 command first on a projector (18 s). |
| 86-94 | Ex 8 (extension) | `--scope-sweep` table; discussion question 8a. | Let pairs argue before you give the model answer. |
| 94-100 | Debrief | Three-sentence summary per student; `docs/explainers/game.html` as optional follow-up. | Discussion questions in the Instructor notes. |

Cut list if time is short: Ex 7 and 8 are extensions (20 extra points, run as homework or as a board demo); then the lab is about 86 minutes (ESTIMATE; drop the Ex 7-8 rows). Further: drop Ex 6 and the second half of Ex 2 (keep 0xFF and 0x0F); Ex 4 can be a board demo.

## Materials
- Worksheet `docs/edu/WORKSHEET.md` (students). Answer key `docs/edu/ANSWER_KEY.md` and `docs/edu/INSTRUCTOR_NOTES.md` (instructor only).
- Starter designs `docs/edu/starter_designs/` (3 Verilog files, netlists, threat configs, `MANIFEST.md` with Yosys version and sha256).
- Background (optional reading): `README.md` one-glance table; `docs/DERIVATION_SHEET.md` (pencil derivations of the same numbers); `research/c3/m1/M1_REPORT.md`, `research/c2/e2_variance/E2_REPORT.md`.

## Safety and honesty rules for the class
- Say "modelled flip", never "glitch" or "hack". No exercise concerns a real product.
- Every number a student writes carries a label (MEASURED = produced by a command they ran, with that command) and the netlist hash prefix.
- "No attack up to the bound" is never written as "secure".
