# Instructor notes

*Not reviewed by the project owner. Licence Apache-2.0. Model-only lab; nothing physical; nothing here is established as new (prior art: SYNFI, FIRMER, k-FRP, CLEAVE, FIVER, uArchiFI; `docs/PRIOR_ART.md`).*

## Before class (about 25 minutes)
1. Do the whole lab once in a copy (`docs/edu/LAB_GUIDE.md` setup). The slowest command is V2 at `--max-flips 3`, about 8 s here (MEASURED once, EDU2 copy; ESTIMATED for your machine).
2. Check `yosys -V`. The answer key's gate counts and hashes (85 and 63 gates; hashes `f954078f`, `d776226e`) are for **Yosys 0.33**. On another build, run Exercise 3 yourself and write your own numbers on the key. The relation to teach is stable in the project's data (plain recipe at least 2, `opt_merge` gives 1), the counts are not.
3. The worksheet uses the shipped options `--consumer-bits`, `--sweep-widths`, `--scope-sweep` (run `faultbound-wt analyze --help` to confirm your install lists them). Only Exercise 4 rule B needs `docs/edu/tools/edu_scope.py`; run it inside the repository copy.
4. Decide whether students may see the reference design (`starter_designs/mini_v2.v`). Default: it is in the folder; if you want the Exercise 5 task to be a design task, hand out `mini_v1.v` and `mini.toml` only.

## Common misconceptions (and the exercise that addresses them)
| Misconception | Why it is wrong here | Ex |
|---|---|---|
| "Duplicating the check doubles the cost." | In V1 both copies feed one AND net; one flip on it decides all 8 bits: cost stays 1. | 1 |
| "V2 needs 3 flips" as a property of V2. | It is a property of V2, this netlist, a consumer reading all 8 bits, and this counting rule. Narrow consumer or accept flag: 1 to 2 flips. | 2, 6 |
| "The RTL is what is verified." | The solver reads the netlist. Same RTL: 68, 85, 63 gates and 3, 2, 1 flips. | 3 |
| "Synthesis keeps my redundant copies." | Common-subexpression elimination removes identical logic by design. | 3, 5 |
| "More fanout means a bigger attack." | Under the headline rule a flip of a wide net is one fault, so wide nets are cheap for the attacker. | 4 |
| "No attack up to the bound = secure." | Only inside the model: fixed input, known start, k flips, 6 cycles. | all |
| "A flip is a glitch / laser pulse." | It is an XOR in a model. Say "modelled flip" every time. | all |
| "The solver found the shortest attack, so nothing shorter exists in reality." | Shortest in the modelled fault space; other fault types are not modelled. | 4, 6 |
| "If the tool exits 0 the design passes." | Exit 0 means no attack up to that bound; see exit codes and the scope lines. | 5 |

## Discussion questions
1. V1 breaks with one flip on `ok`. Where would you put the second wire in a real design so that no single net decides the result? What new single point appears (the consumer; the flag; the state register)?
2. Is "stem = 1" or "cost = fanout" the better model of a real transient? (Honest answer from the project: neither is shown physical; stem = 1 matches a driver-node upset, fanout cost is a stress test. `research/c3/r22/R22_REPORT.md`.)
3. The accept flag `boot_ok` needs 1 flip even though the word needs 3. Who reads the flag? What should the "asset" be in a security requirement?
4. A tool report prints the netlist hash. Why is that more useful than a bare "PASS"? What would you put in a CI log?
5. Our flips happen in one cycle, `sig` is constant, the start state is known. Name an attacker capability that is outside these assumptions and say whether it would help or hurt the attacker.
6. Why is a bounded "no attack up to k = 2" still worth having? What would an unbounded statement need (see `formal/FORMAL.md`: one unbounded result exists in the project for one netlist and was not replicated by a second tool)?
7. After `opt_merge` a hardened design collapses. How would you tell a synthesis tool to keep redundancy, and how would you check that it did?

## Notes for Exercises 7 and 8 (added by EDU2)
- Ex 7: the curve 0,1,1,2,2,3,3,3 on V2 is the measured width curve; n=1 shows 0 because the idle state already looks like acceptance on bit 0 (a collision, not a fault result). Do not let students read the step as "one flip per comparator copy": n=3 touches all three copies yet costs 1 (state-bit route, `research/c3/m1/M1_REPORT.md`).
- Ex 8 discussion question (the one to spend time on): "The same netlist has cells from 0 to 3. What does the table mean?" Target: it is a map of how the claim depends on scope, not a score; each cell is a different statement; quote one cell with scope, bound and hash; a 0 under `init=arbitrary` means no reset is modelled. Misconception to watch: "take the minimum of the table as the design's strength" (that mixes scopes, including the artefact column) or "take the maximum as the design's strength" (that picks the attacker's least favourable scope).
- Time: Ex 7 plus Ex 8 add about 15 minutes; they are extensions (20 extra points) and can be homework.

## Link to the wow page and the game
- `docs/wow/explainer.html` ("Three guards, one wire", toy-labelled page): use it as the 3-minute opening. It makes the V1 idea visual before the CLI numbers. Exercise 1a is its text in numbers.
- Companion docs: `docs/wow/script_90s.md`, `docs/wow/poster.md`. Check them for current wording before reuse (not reviewed for this kit).

## Pitfalls
- **Verdicts belong to a netlist hash and build.** The same `rtl/v2.v` gives 85 gates on apt Yosys 0.33 (2 flips) and 83 gates on a conda 0.38 build (3 flips) in the project's own measurement (`research/c2/e2_variance/E2_REPORT.md`, `README.md`). H5 also measured 83 gates and no 2-flip attack on Yosys 0.52 (Docker, plain flow). Do not teach this as a version effect (corrected 2026-11-20, `docs/report/WHY_TWO_FLIPS.md`): Encoding sets the floor (idle word touches 2 of 3 copies => 2 flips); the synthesis flow decides whether the floor is reached (1 when a flow merges the copies). A build or flow difference changes the netlist, not the underlying weakness. Conda 0.38 gives 2 on three other flows. This kit could only run 0.33, so the 83-gate case is not re-measured here. Tell students to copy the hash prefix next to every number.
- Minimum-attack net names differ between runs and between k values (the solver returns any minimum attack). Grade numbers.
- `faultbound-wt analyze x.v` re-runs Yosys; a student's edited Verilog gives a new hash each time. That is intended.
- **Top module names:** students who rename the module in Exercise 5 must change `--top`.
- Exercise 5 designs that "pass" at `--max-flips 1` can still fall to 2: raise the bound. A pass is not secure.
- Only plain gates and rising-edge flops without reset pins are read. A student who writes `always @(posedge clk or posedge rst)` gets exit 3 (`$_DFF_PP0_` not modelled): use a synchronous reset. (Demonstrated: `product/examples/pin_lock/pin_async.v`, exit 3.)
- Per-cycle attacker input is not in the shipped tool (constant input only). Do not promise otherwise.
- The goal is evaluated at any cycle 0..5, and the goal output itself can be flipped: for a single-bit output such as `boot_ok` or `unlock` one flip on the output net always suffices. Students sometimes try to "fix" the PIN lock and cannot; that is the lesson of Exercise 6.
- Timing: V2 at 3 flips is the slowest step. Slow VMs with many students: tell them to start it first, or use `--max-flips 3` once per group.
- Do not let students run `make reproduce` in the repository tree (it rewrites `results/`, `tb/`).
- Tool scope: only the fanout rule (Exercise 4, rule B) comes from a research script and is not a product feature; it is not independently reviewed. Rule A in Exercise 4 was cross-checked with the CLI (2 flips on both). Exercise 2 now uses the shipped `--consumer-bits`, whose numbers equal `m1_all_masks.csv` for the masks used.
- Sweeps: a sweep that hits `--timeout-s` prints no partial table (exit 2). `unknown` in a sweep cell is not 'no attack'. `--sweep-widths` offers lowest-n-bit masks only; use `--sweep-masks` for other masks.

## Assessment rubric (100 points; Ex 7-8 are 20 extension points on top)
| Criterion | Weight | Full marks | Partial | None |
|---|---|---|---|---|
| Correct numbers with commands (Ex 1-4, 6) | 40 | Every table cell matches the key (or the student's own recorded Yosys build) | Within one flip on a minority of cells | Numbers without commands |
| Scope discipline | 20 | Every verdict carries bound, goal, consumer and hash prefix; "model only" stated | Hash or bound missing in some places | Words "secure/safe/proved" used for a bounded result (deduct 5 each, max 10) |
| Explanations (Ex 1b, 2a-c, 3a-c, 4a-c, 6a-c) | 20 | Mentions the shared wire, consumer width, netlist-not-RTL, counting rule | Right idea, missing mechanism | Off-topic |
| Design exercise (Ex 5) | 20 | Valid design, recorded k=1 and k=2, honest `opt_merge` result | Valid design, partial record | No valid design |
Bonus (up to 5): finds and documents a design in which `opt_merge` does not drop the minimum, with its hash and Yosys version. (Not known to exist; do not promise.)

Autograding idea: exit code of `faultbound-wt analyze edu_work/mine.v --top mini1 --config docs/edu/starter_designs/mini.toml --max-flips 1` is 0 for a pass; the JUnit report option (`--report out.junit.xml`) feeds an LMS. Run each student in a sandbox: the tool calls Yosys on student-supplied Verilog (do not run untrusted Verilog outside a throwaway container).

## What this lab does not show
Anything about silicon, glitching hardware, power or EM, real vendor netlists (only plain gates and sync flops are read), scaling beyond toy designs, or a vulnerability in any deployed product. Say so at the start and at the end.
