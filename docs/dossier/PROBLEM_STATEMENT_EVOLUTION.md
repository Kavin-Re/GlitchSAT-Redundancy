# Problem statement: evolution record (owner gave free rein on 2026-11-19; every version is kept so the owner can revert)
Status: DRAFT written by the lead agent during the overnight run. The owner decides which version to present. All versions are scope-limited, model-only (no physical test), and make no novelty claim.

## P0 (original): supermarket cyberattacks -> a hardware circuit
Dropped earlier: no evidence it could be built or defended as electronics.

## P1: "Does redundancy protect a boot decision against glitches?" (V0/V1/V2 + solver)
Headline was "V2 resists 2 flips". Collapsed under critics (CT-1, DA2, B2): the number depends on goal, input treatment, power-up state, netlist, and consumer width.

## P2 (pivot S2, 2026-11-19): "Verdicts depend on how a fault is counted and on the exact netlist and scope"
Weak alone: DS judged it close to a tautology unless a counting rule is justified; R22 found no physical justification for any single rule.

## P3 (proposed tonight): "Which redundant copies really protect a decision, and against what? A design-time check of redundancy against what the consumer reads"
One-sentence form: Given a gate-level netlist and the bits a consumer actually checks, report how many single-cycle flips defeat it, which nets the supposed copies share, and how that answer changes with synthesis build, fault-counting rule and scope.
Why this is the stronger problem: it names a user (a designer adding redundancy), an input (netlist + consumer bits), an output (cost + shared nets + scope block), and a measurable question.
Evidence already in hand (reported, see each report): M1 consumer-mask rule (min of Hamming distance to idle states and comparator copies touched; known-style cut/Hamming reasoning, not a discovery) exact on spike V2 (255/255) but 187/255 on apt re-synthesis (68 mismatches); E2 V2 min 1/2/3 in 180/60/24 of 264 solved configs (94/38/20 over 152 distinct netlists, DA3); B2 360-cell scope matrix; REP replicated 6/32 vs 32/32; R20 six real designs; V456 countermeasure patterns (only V5 beats V2 in the apt flow, V6 refuted).
Open test (BP's ONE experiment, being run by agents PRE then TEST): a pre-registered structural predictor, no solver, tested on held-out netlists. If it passes, P3 becomes "a linter with a validated predictor"; if it fails, P3 is stated as "a solver-backed scope reporter" (smaller claim).
What P3 is NOT: not a vulnerability finding, not a security proof, not physical validation, not new as a method (prior art: SYNFI, FIRMER, k-FRP, CLEAVE, FIVER, uArchiFI).

## Decision rule for the owner
Present P3 if the PRE/TEST result passes or is clearly reported either way; present P2 plus the scope table if time is short. Never present P1.

## UPDATE 21:07 UTC (after PRE/TEST/VER): result of BP's ONE experiment
Pre-registered predictor frozen 20:52 UTC (hashes in research/c4/pre/FROZEN.sha256). TEST: all six criteria passed on 928 held-out cells (reported; leakage audit found none). VER (independent audit): the 928/928 is real but the corpus is easy (684 cells need only 1 flip; effective independent sample about 3-5 designs); on 163 fresh cells from 76 new netlists the predictor was exact on 150 (92.0%(always predicting 1: 62%; sound lower bound alone: 83%; DA3) and within one flip on 156 (95.7%), which FAILS the pre-registered 98% bar; on cells needing 2 or more flips it was exact on only 18 of 31; it was slower than the solver outside the heavy cases.
Consequence: P3 is stated at the smaller, honest level: a solver-backed scope reporter (the solver is the reference) with a sound structural lower bound and a heuristic upper estimate as a quick pre-check; NOT 'a validated linter'. The method claim 'verdicts belong to (netlist, consumer, counting rule, scope)' stands on measured data (E2, B2, M1, REP).
