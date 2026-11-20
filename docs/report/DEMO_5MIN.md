# 5-minute demo script (no hardware, modelled flips only)

Licence UNDECIDED; title TBD. Replaces the 19:30 version (kept in `research/c4/pres/backup/DEMO_5MIN.md.orig`). Everything below is a bounded result on toy designs under a model; nothing is physical and nothing is claimed as new.

Every command was run on a copy of the project on 2026-11-19 (agent PRES, `/tmp/work_pres/copy`, venv with `pip install ./product`, z3-solver 5.4.1; timings are wall-clock on that machine, MEASURED, they vary with load). Do NOT run `make` in the live tree (it rewrites `results/` and `tb/`); everything here only reads the tree and writes to `/tmp`.

**Shorter, zero-typing version:** `docs/DEMO_3MIN.md` (3 minutes: Verdict Dial, Solver Replay, 264-builders wall, staircase; plus a 10-minute booth loop). Use this 5-minute script when live commands are wanted.

## Prep, not on stage (about 2 minutes, do it the day before and again 10 minutes before)
```
cp -r /home/user/project /tmp/demo && cd /tmp/demo
python3 -m venv .venv && . .venv/bin/activate
pip install ./product z3-solver                  # needs PyPI; installs the command faultbound-wt
EX="$(faultbound-wt example-path)"; A="analyze $EX/v2.json --config $EX/threat.toml"
mkdir -p /tmp/demo_saved
```
Then pre-run every command below once with `| tee /tmp/demo_saved/<name>.txt`, so there is a saved output to show if a live run is slow or the laptop misbehaves. Open slides 1 to 14 (deck re-ordered by INT2a, 2026-11-20: old slides 5 to 9 are now appendix A6 to A10) (`docs/report/SLIDES.pptx`) and, in a browser, `docs/wow/explainer.html` (the three-guards picture, hero button). In the same terminal keep `EX` and `A` set (re-run the `EX=...` line in each new shell).

## Minute by minute
| Time | What you show | What you say (plain words) |
|---|---|---|
| 0:00 to 0:30 | Slides 1 and 2, or the explainer hero | "A lock has three guards, but all three answers go down one shared wire. Flip that wire once and the door opens. Three guards on one wire are really one guard. Everything I show is a model of a toy: modelled bit flips, no chip, nothing physical." |
| 0:30 to 1:15 | Terminal, command 1 (V1) | "Here is the toy design V1 with two copies of the check. I ask the solver for the fewest flips." Run it. "One flip, on the net `ok`. Two copies, one wire." |
| 1:15 to 2:15 | Commands 2 and 3 (V2) | "V2 has three copies, each owning its own result bits." Run k=2: "no attack with two flips." Run k=3: "an attack, and it needs three flips, one in each copy." Say the scope: "that is the full 8-bit word, inputs not attackable, known power-up state, the stored netlist." |
| 2:15 to 2:45 | Command 4 (boot_ok) | "Same design. If the consumer only reads the accept flag `boot_ok`, one flip is enough." |
| 2:45 to 3:45 | Command 5 (scope sweep); slide 4 | "Here is the same design under four scopes and four goals in one table. The answer moves between 0, 1, 2 and 3. 'Resists two flips' was true in exactly one cell." (0 under arbitrary power-up means no reset: a design gap, not a tool finding.) |
| 3:45 to 4:30 | Command 6 (width curve); slide A6 (page 20) | "If the consumer reads only the lowest n bits: 0, 1, 1, 2, 2, 3, 3, 3. A claim has to say how wide the reader is." |
| 4:30 to 4:50 | Slides A7, A8, A9 (pages 21 to 23), or slide 7 (the wall), no live commands | "Synthesis settings give 1, 2 or 3 flips: 180, 60 and 24 of 264 solved configs (94, 38 and 20 over 152 distinct netlists). Circuit simulation (1-to-0 only) says a supply dip hits a whole rail, and a 0->1 event on the three compare copies breaks V2 with one event in our model (polarity open; the domain is the netlist hierarchy, not a physical rail; physical track closed); the layout puts the three copies within 2.95 um on one supply net. Simulated, not silicon." |
| 4:50 to 5:00 | Slides 12 and 14 | "Not proven: anything physical, anything beyond toy designs and 3 flips, anything new. The sentence to keep: three copies resist two faults means nothing unless it says what counts as a fault, which output, how the chip starts and which netlist." |

## The six commands (verified 2026-11-19 on a copy; `EX` and `A` as in the prep block)
```
# 1. V1: two copies, one shared wire (0.5 s)
python3 scripts/glitchsat.py check reference/spike_netlists/v1.json --top v1 --k 1 --cycles 6 --out /tmp/demo_saved/v1.json
#    expect: ATTACK_FOUND; min faults: 1 [('ok', 1)]; "SINGLE POINT OF FAILURE ... net `ok`"

# 2. V2, 2 flips (about 2 s)
faultbound-wt $A --max-flips 2 --timeout-s 60
#    expect: NO_ATTACK_UP_TO_BOUND (<= 2 flips, 6 cycles; 68 gates, 8 flops), exit 0

# 3. V2, 3 flips (about 8 s)
faultbound-wt $A --max-flips 3 --timeout-s 90
#    expect: ATTACK_FOUND, MINIMUM ATTACK COST = 3 flips, three nets (c0, c1, c2 copies) at cycle 1, exit 1

# 4. V2, the accept flag only (0.5 s)
faultbound-wt $A --max-flips 1 --goal-out boot_ok --accept-value 1 --timeout-s 30
#    expect: ATTACK_FOUND, minimum attack: boot_ok@1, "SINGLE POINT OF FAILURE", exit 1

# 5. Scope sweep (about 18 s)
faultbound-wt $A --max-flips 3 --scope-sweep --sweep-masks 0x0F,0x6A --cell-timeout-ms 60000 --timeout-s 120
#    expect the table rows (min flips; columns in-sites=none/init=known, in-sites=all/known, none/arbitrary, all/arbitrary):
#      boot_word==0x96     3   1   0   0
#      boot_word bits 0xF  2   1   0   0
#      boot_word bits 0x6A 3   1   0   0
#      boot_ok==1          1   1   0   0        (exit 1: some cell found an attack)

# 6. Consumer width curve (about 19 s)
faultbound-wt $A --max-flips 3 --sweep-widths --timeout-s 120
#    expect n=1..8: 0, 1, 1, 2, 2, 3, 3, 3 (exit 1)
```
Notes on what you see: the tool always prints `scope:` lines (goal, inputs, init state, counting rule, bounds, netlist SHA-256) and "bounded result under this model; not a proof of security". Read one aloud; it is the honest part. Do not run `make test` or `make reproduce` on stage (about 27 s and 25 s, and they write files).

## If a command is slow or fails
- Every live command above carries `--timeout-s`. When it fires you get verdict `UNKNOWN_TIMEOUT`, exit 2, and the tool says it is NOT "no attack". Verified: `faultbound-wt $A --max-flips 3 --timeout-s 2` stops after 2.1 s with exactly that message. Say: "The solver ran out of my time budget. That is not a result; here is the saved run." Then `cat /tmp/demo_saved/<name>.txt`.
- Slow sweep (commands 5 and 6 are the longest): lower the bound, `--max-flips 2` (cells that need 3 print `>2`), or show the saved table and slide 4 or A6.
- No PyPI or no venv on the day: use only command 1 (needs only Python and z3 from the system, as in `START.md`) and the saved outputs.
- Never improvise a number. If something prints a number that is not on slides 3, 4, A6 or A7, say "that is a different scope than the slide" and read the `scope:` line.

## Questions to expect (full cards: `docs/dossier/VIVA_ANSWER_CARDS.md`; backup slides A1 to A4)
1. Is this new? No. SYNFI, FIRMER, k-FRP, CLEAVE, FIVER and uArchiFI cover the base method; the k-FRP full text is unread. Nothing established as new (`docs/PRIOR_ART.md`).
2. Is V2 secure? No such claim. "No attack up to 2 flips" is bounded (6 cycles) and holds in one narrow cell; the accept flag falls to 1 flip. One unbounded proof exists for one netlist and k <= 2 (slide A3).
3. Which counting rule? One flipped net is one fault (the convention of SYNFI and FIRMER); fanout counting is a stress test; neither is shown physical (slide A1).
4. Is the layout real? A flow demonstration. Router DRC 0, LVS match uniquely for the original; four spread variants failed LVS (a known filler flow bug); no extraction, no IR-drop, no silicon (slide A4).
5. Does the predictor replace the solver? No. Exact on 150 of 163 fresh toy cells (92%), against 62% for always predicting 1 and 83% for the sound lower bound alone (DA3; LEDGER: 71 of 71 on a stratified sample of the same E2 family, 4 of 6 on fresh RTLs (wrong on the voter designs V2m and V5); 58% on cells needing 2+ flips; 1.4x slower; the solver is the reference (slide A2).
