# scale: the GlitchSAT question on designs of thousands of gates

## 1. In plain language

GlitchSAT asks one question about a chip design: *what is the smallest number of momentary bit flips that lets an
attacker get past a protection?* The original engine answers it well for designs of a hundred gates. On the
first design with two thousand gates (two copies of an AES S-box that check each other) it needed a minute for
"one flip is not enough" and did not finish within 250 seconds when asked about three flips.

This folder makes the same question answerable on blocks of thousands to tens of thousands of gates. It does not
change the question or the fault model. It changes how much work the question costs:

1. **Fewer places to flip.** Most flips have exactly the same visible effect as some other flip further down the
   wire, or no visible effect at all. Those are found and left out, with a proof for each that leaving it out
   cannot hide an attack. On the two-thousand-gate design 6,248 candidate flips shrink to 1,275.
2. **Blocks instead of gates.** A block such as one S-box copy is first treated as a box that is either intact or
   broken, with a short list of facts about what breaking it costs ("to make two of its outputs wrong at once you
   need two flips"). The whole design is then analysed with those facts. Anything this says is impossible is really
   impossible; anything it says is possible is rebuilt with real flips and replayed before it is reported.
3. **One formula for every budget and every run length.** The solver is asked about 0, 1, 2, 3 flips and about
   1, 2, ... N clock cycles without starting again; what it learned for one question is kept for the next.
4. **Both processor cores.** One process pushes the proven lower bound up while the other looks for cheaper attacks.
5. **Always an answer.** With a time limit the result is never "timeout". It is a range such as *"between 2 and 4
   flips: an attack with 4 was found and replayed, fewer than 2 is proved impossible"*.

What it does not do: it does not make the fault model more physical, it does not prove anything beyond the stated
number of flips and cycles, and its speed on a new design is not guaranteed. Section 8 lists the limits.

## 2. Status

Labels: **MEASURED HERE** = produced by a command run in the build environment (2 vCPU, shared with other jobs
during every run, so times are indicative; Python 3.13; Yosys 0.33, CaDiCaL 3.1.0 and Kissat 4.0.4 built from
source; no z3, no PySAT). **TO CONFIRM** = written, not run here, or run only against a stand-in.

| Item | Status |
|---|---|
| Fault-site reduction, module summaries, incremental search, intervals, symmetry breaking | MEASURED HERE: every check of section 7 passes |
| R20 open cell (`sbox_dmr`, 2,040 gates, k=3, T=4; z3: not finished in 250 s) | MEASURED HERE on the netlist re-synthesised with Yosys 0.33 (same gate, flop and site counts as R20 recorded): minimum 2, proved, 0.6 s with the bundled Python solver, 0.3 s with CaDiCaL |
| Largest design run | MEASURED HERE: 32,641 gates / 512 flops (16 bytes through two S-box lookups each), k=3: minimum 2 proved in 10.8 s (Kissat), 13.1 to 20.9 s (CaDiCaL) |
| OpenTitan AES cipher control (3 rails, 2,130 primitives after mapping Nangate45 cells), Ibex fetch stage (3,272) | MEASURED HERE, with goals written for this benchmark (section 6.3); minimums equal to an independent encoder |
| CaDiCaL and Kissat | MEASURED HERE through DIMACS files: one process per query, nothing kept between queries |
| In-process incremental native solver (PySAT) | TO CONFIRM: the PySAT path is the adapter of `tools/fastsat`, never run with a real PySAT here |
| Speed against the z3 engine on one machine | TO CONFIRM: z3 is not installed here. z3 times quoted below are the ones recorded in `research/c3/r20/R20_REPORT.md` on another machine; they are not a like-for-like comparison |
| Ibex lockstep, `rom_ctrl`, Caliptra, full AES control with its data path | NOT RUN: no netlists of these here. Nothing is claimed for them beyond "designs of that size ran" |

## 3. Use

Needs the repository (`scripts/glitchsat.py` for the netlist parser) and `tools/fastsat` (CNF gates, cardinality,
solvers). Set `GLITCHSAT_ROOT` / `GLITCHSAT_FASTSAT` if the folder is not at `<repo>/ext/scale`.

```
# the engine's question, exact answer
python3 tools/scale/scripts/glitchsat_scale.py check reference/spike_netlists/v2.json --top v2 --k 3 --cycles 6

# a time limit: exact answer if it fits, otherwise an interval (exit code 2)
python3 tools/scale/scripts/glitchsat_scale.py check big.json --top top --k 4 --cycles 8 --time-s 60 --workers 2

# the minimum for every run length 1..N from one formula
python3 tools/scale/scripts/glitchsat_scale.py deepen reference/spike_netlists/v2.json --top v2 --k 3 --cycles 8

# a block with many ports: free inputs change every cycle, some are tied, an alert must stay silent
python3 tools/scale/scripts/glitchsat_scale.py check aes_ctrl.json --top aes_cipher_control --k 4 --cycles 3 \
    --inputs cycle --no-key --sites-meta aes_ctrl.meta.json \
    --goal out_valid_o=3 --quiet alert_o=0 --fix in_valid_i=4 --backend dimacs:cadical
```

| Option | Meaning |
|---|---|
| `--goal-out/--goal-value/--attack-input/--key` | as in `glitchsat.py check` (defaults `boot_word`, 0x96, `sig`, 0xC3) |
| `--goal PORT=VALUE` (repeatable) | all listed output values at one cycle (the "hit") |
| `--quiet PORT=VALUE` | must hold at every cycle up to the hit (for example the alert output stays 0) |
| `--fix PORT=VALUE`, `--inputs const\|cycle`, `--no-key` | tie an input; free inputs keep one value per run or get a new one each cycle; drop the "differs from key" condition |
| `--sites-meta FILE` | JSON with `sites` (net ids that may be flipped) and `resets` (tied inactive), as written by the Nangate45 adapter |
| `--reduce time\|struct\|full` | no site reduction / post-dominators (default) / plus simulation signatures with SAT confirmation |
| `--modules auto\|prefix\|islands\|none\|FILE.json` | how modules are found (section 4.3); any choice is sound |
| `--time-s S`, `--workers 1\|2`, `--mode race\|cubes`, `--symmetry` | time limit, processes, two-core strategy, symmetry breaking |
| `--backend auto\|py\|dimacs:<binary>\|pysat:<name>` | solver (`py` = bundled Python CDCL of `tools/fastsat`) |

Exit codes: 0 exact answer, 2 interval or undecided part, 3 input error, 4 internal error (a witness that does not
replay, a solver model with missing variables). Result JSON (`--out`): `status` (`EXACT`,
`NO_ATTACK_UP_TO_BOUND`, `INTERVAL`, `LOWER_BOUND_ONLY`), `lo`, `hi`, `lo_by`/`hi_by` (which formula gave each
bound), `events` (when each bound moved), `witness` (flips, inputs, hit cycle), `reduction`, `modules`, `parts`.

Python: `gscale.search.analyse(P, kmax, time_s=None, reduce='struct', modules='auto', workers=1, ...)` with
`P = gscale.spec.load_problem(...)` or `gscale.circuit.engine_problem(netlist, N, ...)`.

## 4. Method and soundness

Fault model and question are those of `scripts/glitchsat.py`: a fault flips one net (a gate output or a flop Q)
for one cycle; at most k faults in cycles 0..N-1; the goal is a set of output values at some cycle, optionally with
"alert outputs stayed quiet until then" and "attacker input differs from the key". An *attack* is a pair (inputs,
set of flips) that reaches the goal. *Observed nodes* are the goal and quiet nets at every cycle.

Every positive answer is checked independently of all of the following: the flips and inputs are replayed on a
plain gate-level simulator (`gscale/sim.py`, `replay`), which shares no code with the unrolling, the reductions or
the encoder. A witness that does not replay stops the run with exit 4. "No attack" answers have no such
certificate; they rest on the arguments below and on the tests of section 7.

### 4.1 Unrolling (`gscale/unroll.py`)

The circuit is unrolled into one DAG: a node per net and cycle. Four simplifications are applied while it is built.

- *Cone and timing.* A net at cycle t is built only if it can reach an observed net by cycle N-1.
- *Hard constants.* A value is a hard constant when no input and no modelled fault can change it: a tied input, a
  power-up value of a flop that is not a fault site, and whatever those force through gates that are not fault
  sites. Hard constants are folded, and with them the edges they kill (an AND with a hard 0 no longer reads its
  other input). A fault site is never folded away: `sig & 0` with a faultable output becomes "constant 0 XOR its
  own flip". This is the sound form of controllability pruning for bit flips: a flip is always "activated", so
  the only thing a constant can remove is what feeds it.
- *Hashing.* Identical nodes that are not fault sites are merged.
- *Sweep.* Nodes with no path to an observed node are dropped.

Each step replaces a node by one with the same value under every input and every set of flips, or removes a node
whose value no observed node depends on. The observed values, hence the set of attacks, are unchanged.

### 4.2 Fault-site reduction (`gscale/reduce.py`)

**Definition (toggle dominance).** Site a is *covered* by site d, written a <= d, if for every input and every set
F of other flips, flipping a on top of F changes the observed values either not at all or exactly as toggling d in
F would (adding d if absent, removing it if present). "Covered by nothing" means flipping a never changes anything.

**Lemma 1.** Let K be a set of sites such that every site outside K is covered by a site in K or by nothing. Then
for every k there is an attack with at most k flips if and only if there is one with at most k flips that uses
only sites in K.
*Proof.* Take an attack A and a flip a in A outside K, and let F = A \ {a}. By the definition the observed values
under A equal those under F, or those under F toggled at d with d in K. Both sets are no larger than A, do not
contain a, contain no new site outside K, and reach the goal because the goal, the quiet condition and the key
condition depend only on observed values and inputs. Each step lowers the number of flips outside K by one, so
after at most |A| steps the attack uses K only. The other direction is immediate (K is a subset of the sites). []

The relation is transitive (toggling d is itself "nothing or toggling e"), so covers can be chained. Lemma 1 holds
for every budget, every horizon prefix and with or without the quiet condition; the reduction is computed once.

**Structural rule (post-dominators).** If every path from a to an observed node passes through d, then a <= d: all
observed values are functions of d's value and of nodes not downstream of a; a's flip leaves the latter alone and
either changes d's value or not. `structural()` computes immediate post-dominators of the DAG in one backward pass
and keeps the sites that have no site above them in the post-dominator tree. No solver is involved.
The single-reader rule of FIRMER (Tan et al., arXiv 2307.00561, Theorem 2: a gate whose output feeds one gate can
be replaced by that gate when bit flips are allowed) and the fault collapsing of `tools/fastsat` are the special case
"a has one reader". Post-dominators also cover reconvergent fan-out, and they see through redundancy: in a
duplicated design every node of the checking copy reaches the outside only through the alarm bit, so the whole
copy collapses onto that one site.

**Functional rule (signatures + SAT).** Among the sites that remain, `functional()`
1. simulates 512 random samples (random inputs; half of the samples with a few random other flips), toggles each
   site in turn (event driven) and records its effect on the observed nodes;
2. takes sites with an all-zero record as candidates for "covered by nothing" and sites with equal records as
   candidates for covering each other (the latest in topological order is the representative);
3. confirms each candidate with a SAT miter: three copies of the logic downstream of the two sites (a flipped;
   nothing flipped; d toggled), every other fault site and every input a free variable shared by the copies, and
   the requirement "copy 1 differs from copy 2 on some observed node and from copy 3 on some observed node".
   Unsatisfiable means a <= d for all inputs and all contexts, because a free variable on a site stands for every
   value any combination of other flips could give it. Satisfiable or not decided within the limit: a is kept.
Only confirmed pairs are used, so Lemma 1 applies. Simulation is a filter and plays no part in soundness.

*Observability pruning needs care and is done only in the all-context form.* Dropping a site because flipping it
alone is never visible would be unsound for k >= 2 (in a voter, one wrong copy is invisible and two are not). The
miter therefore asks for invisibility under every set of other flips.

Honest size of the functional rule (MEASURED HERE): on the netlists of section 6 it removes few or no sites
beyond the structural rule (on R20 `sbox_dmr`: 103 candidates, all refuted). It pays off when the fault sites are
a subset of the nets (cell-level sites on a netlist mapped to primitives), where post-dominators often end on a
net that is not a site; `tests/designs.py` has two such cases.

### 4.3 Modules and their composition (`gscale/modular.py`)

A *module* is any set of combinational gates. In each cycle its nodes form an *instance* with input nodes (fan-ins
from outside) and output nodes (read outside, or observed). Flops and all other logic are *glue*.

**Composed formula.** Glue is encoded as in the exact formula, with fault variables on the kept glue sites. An
instance I with at least one fault site gets a unary cost c_1 >= c_2 >= ... and, for every output, a fresh variable
y with the clauses "c_1 or y = o", where o is the fault-free function of the instance inputs. So an instance with
cost 0 behaves correctly on whatever inputs it receives, and with cost >= 1 its outputs are free, subject to the
*summary facts* of its module. Costs and glue fault variables go under one "at most j" bound.

**Summary facts** (each proved on the module alone, with free inputs, so it holds wherever the module is used):

| Fact | Meaning | How it is proved |
|---|---|---|
| `sup (i, j), 2` / `sup (i, j, l), 3` | outputs i and j (and l) wrong at once needs 2 (3) flips | no fault site of the module reaches both (any two) of them structurally |
| `e pattern, 2` | this output error pattern needs 2 flips | exhaustive fault simulation of every site over every input (modules with at most 12 inputs and 10 outputs): the pattern is not in the set E1 that one flip can produce |
| `e pattern, m` | this error pattern needs m flips for any input | SAT on the module: "some input, at most m-1 flips, exactly this error" is unsatisfiable |
| `xy x, y, m` | inputs x with outputs y need m flips | SAT on the module with inputs and outputs fixed: minimum found by ascending budgets |

The first two are computed once per module *shape* before solving; the last two are found on demand (below).
Instances with the same structure, which includes other cycles and structurally identical copies, share one shape
and therefore every fact (this is where identical copies are exploited without any symmetry argument).

**Theorem 2 (composition).** If the design has an attack with j flips, the composed formula is satisfiable with
bound j. Hence "composed formula unsatisfiable at j" proves "no attack with at most j flips".
*Proof.* By Lemma 1 take an attack A with at most j flips on kept sites. Assign inputs and glue fault variables as
in A, every glue node its value under A, every instance output y its value under A, and each instance the cost
min(number of flips of A inside it, its cap). (i) Glue clauses hold: they are the gate equations under A.
(ii) An instance with no flip inside computes, under A, the fault-free function of its actual inputs, so y = o
holds with cost 0; an instance with flips has c_1 true, which satisfies its output clauses. (iii) Every fact holds:
it states a lower bound on the number of flips inside the module for a behaviour, the instance shows that
behaviour under A with the flips of A inside it, and a fact whose bound exceeds the cap can only forbid a
behaviour that A does not show. (iv) The cost total is at most |A| <= j. []

The theorem does not need modules to be convex, disjoint from each other's fan-in, or well chosen; a bad choice
costs time, not correctness.

**From an abstract solution to a real attack (refinement).** When the composed formula is satisfiable at budget
j, each broken instance is handed to its module with the inputs x and outputs y of the solution: "fewest flips
inside that turn x into y". If every instance is realised within its abstract cost, the union of the real flips is
replayed and reported; with "unsatisfiable at j-1" already proved this is the exact minimum. If an instance needs
more, the fact that explains why is added (first the input-independent `e` fact if it is strong enough, else the
`xy` fact) and the composed formula is solved again. Every round removes the current abstract solution; an attack
that could be built with more flips than j is still recorded as an upper bound. After 200 rounds without a
verdict the loop hands over to the exact formula, starting from the lower bound it has proved.

**Finding modules** (`find_modules`): `prefix` uses the hierarchy left in cell and net names by a flattening
synthesis (`$flatten\g[0].A.$abc...`, `A.new_sboxw`); in the hierarchy tree a node is taken when it has at least
8 fault sites, at most 24 output nets and 4 sites per output, and more sites per output than what would be chosen
inside it (so `g[0].A` and `g[0].B` are taken rather than `g[0]`, which would hide the redundancy). `islands`
groups gates connected through gate-to-gate wires. `auto` tries both with the same quality filter and uses no
modules when nothing passes.

Relation to Tollec et al. (ePrint 2024/247, "Fault-Resistant Partitioning of Secure CPUs..."): that work also
avoids one monolithic check by reasoning per part, but its parts are sets of *registers*, its property is
confinement ("faults do not spread to more partitions without an alert") checked over a window of one or a few
cycles, and its result is an unbounded proof of k-fault security for redundancy-based countermeasures. Here the
parts are combinational blocks, the summaries are costs of output error patterns, and the result is the exact
bounded minimum for an arbitrary goal. The two are complementary; a partition-style inductive argument is what
`tools/unbounded` aims at.

### 4.4 One incremental formula; two cores (`gscale/cnf.py`, `gscale/search.py`)

- *Across budgets.* The fault variables (and module costs) feed one totalizer; "at most j" is one assumption
  literal, as in `tools/fastsat`.
- *Across cycles.* The formula is built for the largest horizon N with a chain of prefix literals: assuming
  `prefix[n]` means "the goal is hit at a cycle below n". `deepen` returns the minimum for every n from one solver
  instance; since the minimum cannot grow with n, horizon n starts just below the answer for n-1. The reduction for
  horizon N is valid for every prefix (fewer observed nodes can only make more sites coverable, and Lemma 1 keeps
  all observed values).
- Budgets, horizons and (in the cube mode) cubes enter only as assumptions, so every learned clause is implied by
  the formula alone and stays valid for the next query.
- *Two cores, portfolio* (`--workers 2`): process L raises the lower bound (composed formula with refinement, then
  the exact formula from the bound reached); process U lowers the upper bound (exact formula, descending budgets,
  each attack trimmed and replayed). The parent replays every witness again, merges, and stops both when the
  bounds meet.
- *Two cores, cube and conquer* (`--mode cubes`): each budget of the ascending search is split into the 8 sign
  patterns of the 3 input variables that occur most often in the clauses; two persistent workers, each with its
  own incremental solver, take cubes from a queue. The patterns cover every assignment, so "all cubes
  unsatisfiable" is "unsatisfiable"; one satisfiable cube gives the attack.

### 4.5 Symmetry breaking (`gscale/symmetry.py`), only where it is proved

A permutation s of the DAG nodes is used only after a complete check that it maps the encoded problem onto
itself: same operator, same fan-ins (as a multiset for AND/OR/XOR, pin by pin for MUX), same site flag, same
membership in the kept sites, same role in the goal and quiet conditions of every cycle, inputs and constants
fixed. Candidates come from colour refinement and are grown from one swapped pair; a candidate that fails the
check is dropped.

**Lemma 3.** For such s, and any budget and horizon, adding "F is not lexicographically larger than s(F)" (F =
the chosen flips, in node order) keeps satisfiability and the minimum.
*Proof.* s maps an attack (inputs, F) to an attack (same inputs, s(F)) of the same size. The attacks of one size
form orbits under the group generated by all used s; the lexicographically smallest member of an orbit satisfies
the constraint for each s. []

Where it applies and where it does not (MEASURED HERE): in a three-copy design whose voter is written
`(a&b)|(a&c)|(b&c)` the swap of copies b and c is found and used (the swap of a and b is not a syntactic symmetry
of that voter and is not used). In the duplicated S-box design the copies are **not** exchangeable, because the
goal reads the output of copy A only; no copy swap is used there, only small symmetries between output bits that
have the same goal value. Identical copies are exploited mainly through shared module summaries (4.3), which needs
no symmetry of the surrounding logic. Symmetry breaking is off by default and is applied to the exact formula only.

### 4.6 Answers under a time limit

Two numbers are kept and only move towards each other: `lo` (proved: no attack with fewer than `lo` flips; from
unsatisfiable answers of the exact or the composed formula) and `hi` (an attack with `hi` flips, replayed).

| Status | Meaning | Text |
|---|---|---|
| `EXACT` | lo = hi | "the smallest attack uses 2 flips (minimum proved)" |
| `NO_ATTACK_UP_TO_BOUND` | lo = k+1, no attack found | "no attack with up to k flips" |
| `INTERVAL` | lo < hi | "between 2 and 4 flips (an attack with 4 was found and replayed; fewer than 2 is proved impossible)" |
| `LOWER_BOUND_ONLY` | no attack found, lo <= k | "no attack with fewer than 2 flips; budgets 2..k were not decided in the time given" |

With one process and a time limit the order is: composed formula (if modules exist), a short look for any attack
at the full budget (a quarter of the remaining time), then ascending budgets. An attack with more than k flips is
outside the question and is never reported as `hi`.

## 5. What is taken from the two papers, and what is not

- FIRMER (Tan, Gao, Chen, Song, Wu; arXiv 2307.00561) encodes fault-resistance as SAT with a selector per
  vulnerable gate and removes gates whose output feeds a single gate; it reports an average reduction of
  vulnerable gates above 72% and solves with the parallel solver Glucose. Taken: selector-per-site encoding (already
  in `tools/fastsat`) and the reduction idea, here generalised from single readers to post-dominators and to
  SAT-confirmed equivalence. Not taken: set/reset fault types, its per-cycle fault limits, its definition of the
  property (output differs from the fault-free run before the flag rises); GlitchSAT keeps its own goal.
- Tollec et al. (ePrint 2024/247): see 4.3. Taken: the lesson that redundancy must be analysed per part to scale,
  and CaDiCaL in incremental mode as the solver to aim at. Not taken: register partitioning and the inductive
  (unbounded) argument.
- Reduction rates measured here are in section 6.1; they are for this fault model and these netlists and are not
  comparable with the 72% of the paper (other circuits, other site definition).

## 6. Benchmarks (MEASURED HERE unless marked)

Command: `python3 tools/scale/bench/bench_scale.py --set core proxy r20 wide real repo --limit-s 60` (run in parts;
raw output in `bench/results/*.json`, logs next to them). Time limit per cell 60 s (45 s for the `wide` set). The
machine was shared with other jobs during every run (load average 3 to 5 on 2 cores), single runs: read the times
as orders of magnitude.

### 6.1 Sizes

Each cell: fault variables / CNF variables / CNF clauses of the formula for budget k (cardinality included). "sites x cycles" is every fault site in every cycle (what the engine models without reduction). "cone+timing" is this layer without site reduction. "fastsat collapsing" is `tools/fastsat` (single-reader rule). "module formula": first number = glue fault variables plus module cost variables; "-" = no module passed the filter.

| design | gates / flops | T | sites x cycles | cone+timing | fastsat collapsing | post-dominators | + functional | module formula |
|---|---|---|---|---|---|---|---|---|
| v2 spike | 68 / 8 | 6 | 456 | 353 / 1774 / 4623 | 83 / 535 / 1419 | 83 / 540 / 1423 | 83 / 540 / 1423 | 118 / 685 / 1688 |
| v2 spike T=20 | 68 / 8 | 20 | 1520 | 1319 / 6631 / 17418 | 293 / 1908 / 5186 | 293 / 1927 / 5204 | 293 / 1927 / 5204 | 426 / 2477 / 6210 |
| v5 (apt 0.33) | 208 / 9 | 6 | 1302 | 1028 / 5157 / 13173 | 193 / 1354 / 3639 | 163 / 1208 / 3272 | 163 / 1208 / 3272 | 273 / 1695 / 4031 |
| R20 sbox_unprot | 1012 / 16 | 4 | 4112 | 3092 / 15456 / 39983 | 1271 / 8163 / 21765 | 1271 / 8166 / 21767 | 1271 / 8166 / 21767 | 65 / 3340 / 9702 |
| R20 sbox_par | 2040 / 17 | 4 | 8228 | 6189 / 30994 / 80275 | 2490 / 16122 / 43204 | 1275 / 11238 / 31023 | 1275 / 11238 / 31023 | 78 / 3471 / 10074 |
| R20 sbox_par2 | 2040 / 25 | 4 | 8260 | 6213 / 31106 / 80507 | 2514 / 16237 / 43445 | 1275 / 9224 / 24966 | 1275 / 9224 / 24966 | 78 / 4472 / 13077 |
| R20 sbox_dmr | 2040 / 32 | 4 | 8288 | 6248 / 31252 / 80835 | 2514 / 16237 / 43417 | 1275 / 9231 / 24966 | 1275 / 9231 / 24966 | 78 / 4472 / 13049 |
| R20 crc_plain | 40 / 9 | 4 | 196 | 148 / 784 / 1805 | 49 / 308 / 736 | 4 / 46 / 100 | 4 / 46 / 100 | 13 / 87 / 180 |
| R20 crc_tmr | 44 / 11 | 4 | 220 | 172 / 902 / 2093 | 60 / 369 / 888 | 4 / 46 / 100 | 4 / 46 / 100 | 13 / 87 / 180 |
| R20 uart T=6 | 368 / 34 | 6 | 2412 | 1496 / 7443 / 18577 | 350 / 2483 / 6483 | 318 / 2304 / 6044 | 318 / 2304 / 6044 | - |
| R20 uart T=30 | 368 / 34 | 30 | 12060 | 11076 / 49730 / 122824 | 2524 / 17273 / 45424 | 2468 / 17026 / 44829 | 2468 / 17026 / 44829 | - |
| R20 uart T=60 | 368 / 34 | 60 | 24120 | 23136 / 115477 / 291623 | 5254 / 38724 / 102965 | 5168 / 38329 / 101986 | 5168 / 38329 / 101986 | - |
| proxy dmr trees | 1790 / 32 | 4 | 7288 | 5498 / 27502 / 88341 | 90 / 2899 / 14749 | 63 / 1945 / 9825 | 63 / 1945 / 9825 | 86 / 2036 / 9877 |
| proxy dmr shared | 834 / 32 | 4 | 3464 | 2630 / 13162 / 46725 | 534 / 4705 / 20149 | 279 / 2824 / 12447 | 279 / 2824 / 12447 | 86 / 2036 / 9877 |
| proxy tmr2 trees | 2693 / 48 | 4 | 10964 | 8279 / 41423 / 132946 | 121 / 4298 / 22047 | 67 / 1965 / 9873 | 67 / 1965 / 9873 | 107 / 2193 / 10257 |
| proxy tmr2 shared | 1259 / 48 | 4 | 5228 | 3977 / 19914 / 70523 | 787 / 7006 / 30146 | 283 / 2844 / 12495 | 283 / 2844 / 12495 | 107 / 2193 / 10257 |
| tmr2 x1 bytes | 3068 / 48 | 4 | 12464 | 9404 / 47048 / 121687 | 3757 / 24305 / 65049 | 1279 / 9251 / 25014 | 1279 / 9251 / 25014 | 91 / 4597 / 13373 |
| dmr x4 bytes | 8161 / 128 | 4 | 33156 | 24996 / 125016 / 323423 | 10044 / 64893 / 173589 | 5088 / 36860 / 99779 | 5088 / 36860 / 99779 | 300 / 17824 / 52111 |
| tmr2 x4 bytes | 12274 / 192 | 4 | 49864 | 37624 / 188220 / 486887 | 15004 / 97107 / 259995 | 5092 / 36880 / 99835 | 5092 / 36880 / 99835 | 340 / 18270 / 53289 |
| dmr x10 bytes | 20400 / 320 | 4 | 82880 | 62480 / 312484 / 808467 | 25104 / 162217 / 433945 | 12714 / 92130 / 249417 | 12714 / 92130 / 249417 | 744 / 44540 / 130247 |
| dmr x16 bytes | 32641 / 512 | 4 | 132612 | 99972 / 499992 / 1293599 | 40164 / 259533 / 694293 | 20340 / 147392 / 399047 | 20340 / 147392 / 399047 | 1188 / 71248 / 208375 |
| OT AES cipher control FSM: out_valid without in_valid, alert silent | 537 / 7 | 4 | 948 | 381 / 2428 / 5576 | - | 178 / 1434 / 3367 | 178 / 1434 / 3367 | - |
| OT AES cipher control (3 rails): out_valid=011 with in_valid=100, alert silent | 2130 / 44 | 3 | 2892 | 1990 / 12642 / 31398 | - | 648 / 5571 / 14481 | 648 / 5571 / 14481 | 652 / 5589 / 14519 |
| same, 8 cycles | 2130 / 44 | 8 | 7712 | 6190 / 39577 / 98793 | - | 2174 / 18654 / 48822 | 2174 / 18654 / 48822 | 2198 / 18762 / 49050 |
| Ibex fetch stage: fetch address 0x40400 with no PC set and no mispredict, mismatch alert silent | 3272 / 284 | 3 | 5811 | 1406 / 9061 / 21150 | - | 400 / 4096 / 9893 | 400 / 4096 / 9893 | - |
| same, 8 cycles | 3272 / 284 | 8 | 15496 | 4472 / 28381 / 67657 | - | 1481 / 13812 / 34117 | 1481 / 13812 / 34117 | - |


### 6.2 Answers and runtimes

Each cell: answer, seconds (wall, including unrolling, reduction and CNF build). Answer = proved minimum, or `[lo,hi]` / `[lo,?]` when the time limit ended the search (`?` = no attack found yet; for `fastsat`, `[?,n]` = attack with n found, minimum not proved). Columns: `fastsat` = `tools/fastsat` default with the bundled Python solver; `time`, `struct`, `modules`, `race2` = this layer with the Python solver (no site reduction / post-dominators / plus module summaries / two processes); `cadical`, `cadical+mod`, `kissat` = post-dominators (plus modules) with the native binary. "recorded" = minimum recorded in the repository (R20_REPORT.md, results/reproduce, tools/fastsat README); in brackets = known by construction, not recorded. "all equal" = every finished cell gives the same minimum, it equals the recorded one, and every interval contains it.

| design | k | recorded | fastsat | time | struct | modules | race2 | cadical | cadical+mod | kissat | all equal |
|---|---|---|---|---|---|---|---|---|---|---|---|
| v2 spike | 3 | 3 | 3, 0.3 | 3, 0.6 | 3, 0.3 | 3, 0.2 | 3, 0.4 | 3, 0.0 | 3, 0.0 | 3, 0.1 | yes |
| v2 spike T=20 | 3 | 3 | 3, 3.5 | [3,?], 60.0 | 3, 5.3 | 3, 9.3 | 3, 12.7 | 3, 0.7 | 3, 0.2 | 3, 0.4 | yes |
| v5 (apt 0.33) | 3 | 3 | 3, 2.7 | 3, 5.6 | 3, 1.0 | 3, 0.8 | 3, 1.7 | 3, 0.1 | 3, 0.1 | 3, 0.2 | yes |
| R20 sbox_unprot | 3 | 1 | 1, 0.5 | 1, 0.3 | 1, 0.2 | 1, 0.1 | 1, 0.2 | 1, 0.1 | 1, 0.6 | 1, 0.2 | yes |
| R20 sbox_par | 3 | 1 | 1, 0.9 | 1, 1.3 | 1, 0.4 | 1, 0.2 | 1, 0.4 | 1, 0.3 | 1, 5.5 | 1, 0.5 | yes |
| R20 sbox_par2 | 3 | 1 | 1, 2.2 | 1, 1.1 | 1, 3.0 | 1, 0.3 | 1, 0.6 | 1, 0.2 | 1, 0.3 | 1, 0.4 | yes |
| R20 sbox_dmr | 3 | 2 | 2, 3.4 | 2, 11.2 | 2, 0.6 | 2, 3.0 | 2, 2.8 | 2, 0.3 | 2, 0.3 | 2, 0.3 | yes |
| R20 crc_plain | 3 | 1 | 1, 0.0 | 1, 0.0 | 1, 0.0 | 1, 0.0 | 1, 0.0 | 1, 0.0 | 1, 0.0 | 1, 0.0 | yes |
| R20 crc_tmr | 3 | 1 | 1, 0.0 | 1, 0.0 | 1, 0.0 | 1, 0.0 | 1, 0.0 | 1, 0.0 | 1, 0.0 | 1, 0.0 | yes |
| R20 uart T=6 | 3 | 1 | 1, 0.1 | 1, 0.1 | 1, 0.0 | - | 1, 0.1 | 1, 0.1 | - | 1, 0.1 | yes |
| R20 uart T=30 | 2 | 1 | 1, 0.2 | 1, 0.8 | 1, 0.7 | - | 1, 0.7 | 1, 0.4 | - | 1, 0.4 | yes |
| R20 uart T=60 | 3 | 1 | 1, 0.6 | 1, 1.8 | 1, 0.4 | - | 1, 0.8 | 1, 0.7 | - | 1, 0.5 | yes |
| proxy dmr trees | 3 | 2 | 2, 1.1 | 2, 15.2 | 2, 0.5 | 2, 0.6 | 2, 1.0 | 2, 0.2 | 2, 0.3 | 2, 0.3 | yes |
| proxy dmr shared | 3 | 2 | 2, 1.8 | 2, 6.9 | 2, 0.4 | 2, 0.6 | 2, 1.3 | 2, 0.1 | 2, 0.1 | 2, 0.2 | yes |
| proxy tmr2 trees | 3 | 3 | 3, 5.0 | [2,3], 61.0 | 3, 0.5 | 3, 1.7 | 3, 1.2 | 3, 0.2 | 3, 0.4 | 3, 0.4 | yes |
| proxy tmr2 shared | 3 | 3 | 3, 13.1 | [2,3], 60.7 | 3, 0.6 | 3, 1.4 | 3, 1.3 | 3, 0.2 | 3, 0.6 | 3, 0.4 | yes |
| tmr2 x1 bytes | 3 | (3) | [?,3], 46.0 | [2,?], 46.0 | 3, 0.9 | 3, 1.0 | 3, 1.2 | 3, 0.3 | 3, 2.9 | 3, 0.5 | yes |
| dmr x4 bytes | 3 | (2) | [?,2], 48.3 | [1,2], 47.5 | 2, 13.5 | 2, 8.4 | - | 2, 2.4 | 2, 1.8 | 2, 2.2 | yes |
| tmr2 x4 bytes | 3 | (3) | [?,3], 47.9 | [1,?], 49.9 | 3, 16.5 | 3, 15.8 | - | 3, 2.6 | 3, 10.2 | 3, 2.1 | yes |
| dmr x10 bytes | 3 | (2) | [?,2], 54.2 | [1,?], 45.5 | [1,?], 46.4 | 2, 24.3 | - | 2, 4.8 | 2, 8.8 | 2, 5.0 | yes |
| dmr x16 bytes | 3 | (2) | [?,?], 56.1 | [0,?], 47.4 | [1,?], 45.6 | [1,?], 45.3 | - | 2, 20.9 | 2, 13.1 | 2, 10.8 | yes |
| OT AES cipher control FSM: out_valid without in_valid, alert silent | 3 | - | - | 1, 0.1 | 1, 0.0 | - | 1, 0.1 | 1, 0.0 | - | 1, 0.0 | yes |
| OT AES cipher control (3 rails): out_valid=011 with in_valid=100, alert silent | 4 | - | - | 3, 16.3 | 3, 7.9 | 3, 9.9 | 3, 9.2 | 3, 0.4 | 3, 0.4 | 3, 0.4 | yes |
| same, 8 cycles | 4 | - | - | [2,4], 60.2 | [2,?], 60.1 | [2,?], 60.2 | [2,3], 60.5 | 3, 2.7 | 3, 2.5 | 3, 2.9 | yes |
| Ibex fetch stage: fetch address 0x40400 with no PC set and no mispredict, mismatch alert silent | 3 | - | - | 1, 0.2 | 1, 0.1 | - | 1, 0.1 | 1, 0.1 | - | 1, 0.1 | yes |
| same, 8 cycles | 3 | - | - | 1, 0.6 | 1, 0.7 | - | 1, 0.5 | 1, 0.4 | - | 1, 0.4 | yes |


### 6.3 The questions asked of the OpenTitan netlists

Netlists: SYNFI's Yosys + Nangate45 examples of OpenTitan (AES cipher control FSM, AES cipher control with three
FSM rails and the round counter, Ibex fetch stage), mapped cell by cell to primitives by the Nangate45 adapter of
the real-designs work. Fault sites are the outputs of the original cells and flops only (948 / 2,892 / 5,811 site
instances at the shortest horizon). Reset is tied inactive; every other input is free in every cycle unless tied.
- AES FSM: `out_valid_o` rises although `in_valid_i` is tied 0, `alert_o` stays 0. Minimum 1 (the output itself).
- AES control, three rails: `out_valid_o` shows the multi-rail "true" code 011 although `in_valid_i` is tied to
  the "false" code 100, `alert_o` stays 0. Minimum 3 at 3 and at 8 cycles: one flip per rail.
- Ibex fetch stage: `instr_addr_o` = 0x40400 with `pc_set_i` and `nt_branch_mispredict_i` tied 0,
  `pc_mismatch_alert_o` stays 0. Minimum 1 (a select net of the address path; the other address inputs are free).
These goals were written for this benchmark (section 8).



### 6.4 Reading the tables

- **Site reduction.** Post-dominators keep 20% of the cone+timing sites on R20 `sbox_dmr` (6,248 -> 1,275) and
  half of what single-reader collapsing keeps (2,514). On the designs with a checking copy the whole copy
  collapses onto its alarm bit, which is why `sbox_par`, `sbox_par2` and `sbox_dmr` end at the same 1,275 and
  `crc_tmr` at 4. Where logic is one cone with little reconvergence (`sbox_unprot`, `uart`, `v2`) the gain over
  single-reader collapsing is zero to a few percent. On the Nangate45 netlists 28% to 47% of the live sites stay.
- **Functional rule.** The "+ functional" column equals the "post-dominators" column in every row: it found
  nothing more on these netlists (section 4.2).
- **Module formula.** 78 variables under the cardinality bound instead of 1,275 on R20 `sbox_dmr`; 1,188 instead of
  20,340 on the 32,641-gate design. With the Python solver this is what lets the 20,400-gate design finish
  (24 s; the exact formula does not within 45 s). With CaDiCaL it is sometimes faster, sometimes slower: the
  module queries run on the Python solver, and each refinement round rewrites the whole DIMACS file.
- **R20's open cell.** `sbox_dmr`, k=3, T=4: minimum 2, proved, 0.6 s (Python solver) and 0.3 s (CaDiCaL/Kissat).
  R20 recorded 62 s (k=1), 46 s (k=2) and no result within 250 s (k=3) for the z3 engine on another machine. `uart`
  at T=60, k=3 (z3: no result within 200 s in R20): minimum 1 in 0.4 to 1.8 s.
- **Thousands to tens of thousands of gates.** Every design up to 32,641 gates gets an exact answer from
  CaDiCaL or Kissat in at most 21 s. The bundled Python solver gets exact answers up to 12,274 gates (20,400 with
  modules) within the limit and intervals beyond.
- **Intervals.** Rows with `[lo,hi]` show the time-limited mode: AES control at 8 cycles with the Python solver
  ends as "between 2 and 3" (two processes), "between 2 and 4" or "at least 2"; the native solvers prove 3.
- **Two processes** did not beat one on this machine (both cores were shared with other jobs). The cube mode is
  tested for correctness (section 7) and not benchmarked. No speed-up from parallelism is claimed.
- **Many cycles.** `v2` at T=20 and `uart` at T=30/60 show the cost growing with the horizon; the reduction
  ratio is about the same at every horizon.

### 6.5 Repository netlists (T=6, k<=3)

120 netlists with sig/boot_word ports (0 more rejected by the engine parser): minimum from tools/fastsat compared with this layer at levels time, struct, full and with island modules: **0 disagreements**. Minimum histogram: {'1': 69, '3': 17, '0': 11, '2': 16, 'none': 7}. For the 75 of them with a minimum recorded in `research/c4/ver/heldout.csv` (z3), all 75 are equal.

## 7. Correctness evidence (MEASURED HERE)

`cd tools/scale && python3 -m pytest -q tests` : 41 tests, 41 passed (24 s here).

| Check | Result |
|---|---|
| Exhaustive reference (`tests/oracle.py`: every input, every flip set, no solver, no DAG) on random netlists with random input modes, site subsets, quiet conditions and random module partitions; levels time/struct/full, with and without modules and symmetry | test-suite: 300 problems x 4 configurations, 0 mismatches. Runs of the same generator during development: 1,650 problems x 5 configurations, 0 mismatches. One earlier run found a bug (an attack with more flips than the asked budget was reported as the minimum); it is fixed and has a test |
| Toggle dominance checked directly by exhaustive simulation (dropped site vs its cover, with and without one other flip) | all pairs hold |
| Functional rule: proves the two hand-built cases structure cannot; refutes non-equivalent pairs of V2 | pass |
| Module summaries: E1 and support facts of the shared-mux S-box against brute force over all sites and inputs | equal |
| Composition theorem: composed formula with no refinement is satisfiable at the true minimum, random partitions | every case |
| Refinement: design where the first abstract solution needs twice its price | converges to the exhaustive minimum |
| Symmetry: all attacks of minimum size enumerated with and without the constraints | fewer with; every orbit keeps a member |
| Intervals: time limits 0.3, 1 and 3 s on a design with minimum 3 | lo <= 3 <= hi always; witnesses replay |
| Recorded minimums (V0/V1/V2 = 1/1/3; R20: see table 6.2, column "recorded") | equal |
| Repository netlists against `tools/fastsat` and the recorded z3 minimums | 120 netlists, 0 disagreements (6.5) |
| OpenTitan netlists against the independent sequential model of the real-designs work (`bench/xcheck_real.py`) | 3 of 3 equal (AES FSM 1, AES control 3, Ibex fetch stage 1) |
| External solver models | a model with missing variables is refused (tested with a stand-in; found with CaDiCaL 3.1.0, see section 8) |

## 8. Limits, findings, not done

- **Bounded and modelled**, exactly as the engine: k flips, N cycles, single-cycle bit flips of nets. No statement
  about more flips, longer runs, stuck-at or multi-bit faults, timing or physical feasibility.
- **"No attack" answers are not certified.** They rest on sections 4.1 to 4.5 and the tests. No proof log (DRAT)
  is produced or checked.
- **The benchmark goals on the OpenTitan netlists are written for this benchmark.** They are not SYNFI's
  specifications and not a published threat model; the numbers say that designs of this size and kind are
  tractable, nothing about OpenTitan's security.
- **The wide S-box designs are stress tests by construction** (bytes do not interact), so they scale more kindly
  than a real 20,000-gate control block would. The largest real netlists run here have about 3,300 primitives.
- **Modules help only where a block has a narrow output interface.** In dense control logic `auto` finds none (or
  one island) and the exact formula does the work. Summary facts are per error pattern; a block that needs many
  flips for most patterns but is priced at one can need many refinement rounds (capped at 200, then exact).
- **The functional reduction added nothing on the synthesised netlists here** (4.2). It is kept because it is sound
  and cheap to skip, not because it was shown to pay off at scale.
- **Symmetry breaking** rarely applies to real countermeasures as written (4.5) and is off by default.
- **Solvers.** CaDiCaL/Kissat run as one process per query (DIMACS files); nothing learned is kept between
  queries, and for the smallest designs the file handling costs more than the solving. The in-process path (PySAT)
  is TO CONFIRM. Time limits for PySAT rely on the two-process mode or on the caller.
- **Finding (affects `tools/fastsat` too):** CaDiCaL 3.1.0 prints only "used" variables in its `v` lines unless
  `--modelalllits=true` is given. A reader that takes missing variables as false gets a wrong witness (caught
  here by the replay, exit 4). This layer adds the option when the binary offers it and refuses incomplete
  models; `tools/fastsat`'s `dimacs:` backend should get the same treatment.
- **Not done:** per-cycle or per-region fault limits; reset modelled as an event; modules that contain flops
  (sequential summaries); one-directional functional dominance (a covered by d without equal effect); cube
  selection by look-ahead; wiring into `scripts/glitchsat.py` or the product CLI (this is a separate entry point).

## 9. Files

```
tools/scale/
  scripts/glitchsat_scale.py   CLI: check / deepen / sizes
  scripts/gscale/circuit.py    Circuit, Problem (inputs per run or per cycle, site set, goal, quiet, key)
  scripts/gscale/spec.py       Problem from a netlist file and plain options
  scripts/gscale/unroll.py     unrolled DAG: cone, timing, hard constants, hashing            (4.1)
  scripts/gscale/reduce.py     post-dominator reduction; signatures + SAT miter               (4.2)
  scripts/gscale/modular.py    modules, summary facts, composed formula, refinement           (4.3)
  scripts/gscale/cnf.py        CNF with budgets and horizons as assumptions                   (4.4)
  scripts/gscale/search.py     bounds, exact/composed search, portfolio, cubes, deepen, sizes (4.4, 4.6)
  scripts/gscale/symmetry.py   verified automorphisms, lex-leader clauses                     (4.5)
  scripts/gscale/sat.py        incremental solver handle; strict DIMACS backend
  scripts/gscale/sim.py        gate-level replay (the referee) and bit-parallel DAG simulation
  tests/                       pytest suite; oracle.py = exhaustive reference; designs.py = hand-built cases
  bench/bench_scale.py         sizes, runtimes, agreement; --table writes the tables of section 6
  bench/gen_wide.py            Verilog for the N-byte duplicated / triplicated S-box stress designs
  bench/xcheck_real.py         cross-check on the OpenTitan netlists against the independent sequential model
  bench/results/               MEASURED outputs quoted in this file
```
