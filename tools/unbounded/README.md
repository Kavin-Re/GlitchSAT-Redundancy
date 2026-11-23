# unbounded: GlitchSAT fault analysis for any number of clock cycles

## 1. In plain words

The GlitchSAT engine (`scripts/glitchsat.py`) answers a **bounded** question: "can an attacker who flips at most `k`
bits make the design show the boot word within the first `N` clock cycles?" A "no" from it says nothing about cycle
`N+1`.

This tool answers the **unbounded** question: "can an attacker who flips at most `k` bits in total, each flip lasting
one clock cycle, make the design show the boot word **at any time at all**, after 1 cycle or after a million?"
It gives one of three answers:

| Answer | Meaning |
|---|---|
| `PROVED_UNBOUNDED` | No such attack exists, for any number of cycles. A proof for this netlist, this fault model, the known power-up state and budget k (see the list below), not "we searched for a long time and found nothing". |
| `ATTACK_FOUND` | An attack exists. The tool prints the flips (which net, which cycle) and the attacker input, and replays them in a separate simulator to show that the boot word appears. |
| `UNKNOWN` | A time or depth limit was hit. No claim either way. (No cell of the stored results is UNKNOWN.) |

**Why a finite computation can cover infinite time.** The design has only a few flip-flops (8 or 9 here), so it
can be in only a few hundred different states. Add the number of flips used so far (0..k) and the attacker input, and
the list of everything the design can ever reach is still finite. The tool lists all of it: it starts from the
power-up state, tries every allowed combination of flips in every reachable state, and stops when no new state
appears. If the boot word is not shown anywhere in that complete list, it can never be shown, no matter how long the
attacker waits. Two other methods (k-induction and IC3, both using a SAT solver) reach the same answer by a different
route, and the tool refuses to give an answer if any two methods disagree.

**What "proved for all time" still assumes.** A `PROVED_UNBOUNDED` verdict is a statement about a model, not about
a chip:

1. **This netlist.** One gate-level netlist (one synthesis run). Another netlist of the same RTL can differ; the
   stored results show this directly (`v2_apt` falls to 2 flips, `v2_conda` needs 3, same RTL).
2. **This fault model.** A fault inverts the value of one net (a gate output or a flip-flop output) for one clock
   cycle, as every reader of that net sees it. At most `k` such flips in the whole run. One flipped net counts as one
   fault however many gates read it. Not covered: stuck-at faults, faults lasting more than one cycle, clock or
   voltage glitches that skip or corrupt several things at once, faults on wires between two specific gates, timing
   effects, and anything physical. Input nets are fault sites only with `--input-sites`.
3. **This attacker.** The attacker chooses the input `sig` once; it stays constant for the whole run and is not the
   key (0xC3). Same as the engine.
4. **This goal.** The goal is "`boot_word` == 0x96 is visible in some cycle" (one design, `v2_stored_ok`, uses
   `boot_ok` == 1 instead). Other ways of misusing the design are not checked.
5. **This power-up assumption** (see section 2). With the "known" assumption, the flip-flops start at their netlist
   init values.
6. **At most 3 flips.** The stored run covers budgets 0..3. Every design here has an attack at or below 3 flips, so
   larger budgets add nothing for them.
7. **The software is correct.** Mitigated, not eliminated: three methods that share little code, independent
   re-checking of every proof certificate and every attack (section 4), and tests against the bounded results of the
   repository and against brute force on random netlists.

These are toy designs and modelled faults. The results say nothing about physical attack feasibility.

## 2. Power-up assumptions (scope options)

| Option | Flip-flops at the start of the run | When it is the right question |
|---|---|---|
| `known` (default; the engine's assumption) | their netlist init values | the design is reset properly before the attacker acts |
| `arbitrary` | any value at all | the attacker can also control or corrupt the power-up state. **Uninformative** for these designs: trivially ATTACK_FOUND at k = 0, because the power-up state may already be 0x96 |
| `free_nongoal` | any value from which the fault-free run never shows the goal | "is the design robust from any harmless-looking state?" The tool reports how many (state, input) pairs are admissible and gives `VACUOUS` instead of a proof if none are |

The verdict in each result file (`verdict` field) is for `known` (stated next to it in `verdict_init`, with the scope in
`scope` and `note`); the other two are in `scopes`.

## 3. Results (MEASURED)

Machine: cloud VM (Ubuntu 24.04), 2 vCPU Intel Xeon 2.10 GHz, Python 3.13.18, pure-Python SAT solver only
(`tools/fastsat/scripts/minicdcl.py`, SHA-256 `47a450c9...c7c6`, see section 5; no z3, no PySAT). Command:

```
GLITCHSAT_ROOT=<repository> python3 src/unbounded.py all --backend minicdcl --kmax 3 --plain-depth 12 --out-dir results
```

22 designs x 4 budgets x 3 power-up options = 264 cells, each decided by all three methods; 0 disagreements,
0 UNKNOWN. Sum of method times 234.5 s; the slowest single method run (explicit search, `free_nongoal`, `v5_apt033`,
k = 3) took 13.0 s. Files: `results/<design>_k<k>.json` (one per design and budget), `results/summary.json`,
`results/run_all.log`.

**Known power-up (the engine's assumption).** "Proved" = no attack with that many flips at any time. Every count is for the
netlist file named in the table; "V2" in `tools/vlab` and `tools/shots` is a different (placed-and-routed) netlist,
`layout/v_designs/out_patched/v2_pnr.v`, which is not analysed here.

| Design | Netlist | Proved for k = | Smallest attack (any time) | Engine / repo, within 6 cycles |
|---|---|---|---|---|
| v0_stored | reference/spike_netlists/v0.json | 0 | 1 | 1 |
| v1_stored | reference/spike_netlists/v1.json | 0 | 1 | 1 |
| **v2_stored** | reference/spike_netlists/v2.json | **0, 1, 2** | 3 | 3 |
| v0_apt | formal/gen/w0.json | 0 | 1 | 1 |
| v1_apt | formal/gen/w1.json | 0 | 1 | 1 |
| **v2_apt** | research/c6/p01/netlists/nl_apt_v2.json | **0, 1** | 2 | 2 |
| **v2_conda** | research/c6/p01/netlists/nl_conda_v2.json | **0, 1, 2** | 3 | 3 |
| **v2e_apt** | research/c6/p01/netlists/nl_apt_v2e.json | **0, 1, 2** | 3 | 3 |
| **v2e_conda** | research/c6/p01/netlists/nl_conda_v2e.json | **0, 1, 2** | 3 | 3 |
| v2_stored_ok (goal boot_ok) | reference/spike_netlists/v2.json | 0 | 1 | 1 |
| v0_apt033 | research/c4/b3_inputs/nl/v0_apt033.json | 0 | 1 | 1 |
| v1_apt033 | research/c4/b3_inputs/nl/v1_apt033.json | 0 | 1 | 1 |
| v2_apt033 | research/c4/b3_inputs/nl/v2_apt033.json | 0, 1 | 2 | 2 |
| v5_apt033 (9 flops, 217 cells) | research/c4/b3_inputs/nl/v5_apt033.json | 0, 1, 2 | 3 | 3 |
| v2_flowB | validation/nl/v2.json | 0 | 1 | 1 |
| v2_inbuf | research/c2/reviews/ct/tests/v2_inbuf.json | 0 | 1 | 1 |
| v2c04_apt / v2c04_conda | research/c6/p01/netlists/nl_{apt,conda}_v2c04.json | 0 | 1 | 1 |
| v2c4d_apt | research/c6/p01/netlists/nl_apt_v2c4d.json | 0, 1 | 2 | 2 |
| v2c4d_conda | research/c6/p01/netlists/nl_conda_v2c4d.json | 0, 1, 2 | 3 | 3 |
| v2c5a_apt / v2c5a_conda | research/c6/p01/netlists/nl_{apt,conda}_v2c5a.json | 0, 1, 2 | 3 | 3 |

What this adds to the bounded numbers: for every design, the smallest attack over unlimited time equals the
smallest attack within 6 cycles. Waiting longer never helps the attacker with these netlists at these budgets. For
example V2 (stored netlist) is proved safe against any 2 flips at any time (this netlist, this fault model, known
power-up).

**Agreement with `F.pdr`** (docs/NUMBERS.md; `formal/FORMAL.md` lines 40-43): ABC PDR on the same netlist
(`reference/spike_netlists/v2.json`) proves k = 1 and k = 2 for any number of cycles and gives a counterexample at
k = 3. This tool gives the same verdicts for `v2_stored` (k = 0, 1, 2 PROVED_UNBOUNDED, k = 3 ATTACK_FOUND) with three
methods that share no code with ABC, every proof certificate re-checked (section 4). So the repository's single
unbounded result is now replicated by a second, independent set of engines; the report sentences that call it
"reported by one tool" and "not replicated" predate this module.

**Other power-up assumptions.** `arbitrary`: ATTACK_FOUND for every design and budget, including k = 0 (some
power-up states already show the boot word without any flip). `free_nongoal`: PROVED only at k = 0 for every design,
ATTACK_FOUND at k = 1 for every design. So the 2-flip and 3-flip results above depend on the flip-flops starting at
their init values: from some harmless-looking states, one flip is enough.

**Size of the proofs** (known power-up, largest proved budget): the explicit search lists up to 40,545 reachable
(state, input, flips-used) combinations (`v5_apt033`, k = 2); k-induction with simple-path constraints closes at
depth k + 1; IC3 invariants have 2 to 12 clauses. Plain k-induction (no simple-path constraints) does not close
within depth 12 on any proved cell with k >= 1 (19 cells), which is why the simple-path form is used.

**Agreement with the bounded results** (`consistency` in `results/summary.json`, all `consistent: true`):
- the minimum above equals the explicit bounded search here (6 cycles) and the number recorded in the repository
  (`results/reproduce_summary.json`, `research/c6/p01/glitchsat_cross.txt`, `research/c6/p01/sweep_summary.txt`,
  `research/c4/b3/matrix_T6.jsonl`, docs/NUMBERS.md) for all 22 designs;
- for the 6 designs that `tools/surface` enumerated exhaustively (v0, v1, v2 stored; v2_apt033, v2_flowB, v2_inbuf;
  6 cycles), its minimum is the same, and every attack it lists (219 in total) replays in this tool's simulator with
  exactly the number of attacker inputs it lists;
- with the key as input and no flips, the boot word appears (solver and simulator), so a proof is not an accident of
  an unreachable goal.

## 4. Methods

| Method | File | Kind of answer | Independent check |
|---|---|---|---|
| Explicit reachability with a fault-budget counter | `src/oracle.py` | exact; complete list of reachable states (a fixed point) | own netlist reader and simulator, no solver, no CNF |
| k-induction with simple-path constraints | `src/kind.py` | proof at depth d, or a concrete attack | every attack replayed in the explicit simulator; power-up state re-checked |
| IC3 / PDR | `src/ic3.py` | inductive invariant, or a concrete attack | invariant re-checked in fresh solvers (holds at power-up, excludes the goal, preserved by every step); every state the explicit search reached must satisfy it; plain 1-induction with it must succeed |

The transition system (`src/ts.py`) uses the engine's own netlist reader. State = design flip-flops + attacker input
(chosen at the start, then frozen) + a unary fault counter saturating at k + a sticky "goal seen" bit. Each cycle
has one free flip variable per fault site in the cone of influence. Simple-path k-induction is sound and complete
for a finite system (a shortest attack never repeats a state).

SAT backends (`src/sat.py`): `minicdcl` (pure Python, from `tools/fastsat`; used for every stored result),
`pysat[:NAME]` and `z3`, both imported only when asked for.

## 5. Use

```
export GLITCHSAT_ROOT=/path/to/glitchsat            # repository with scripts/glitchsat.py (read only)
python3 src/unbounded.py check $GLITCHSAT_ROOT/reference/spike_netlists/v2.json --top v2 --k 2
python3 src/unbounded.py check NETLIST --top TOP --k 1 --init free_nongoal --method ic3
python3 src/unbounded.py all --kmax 3 --out-dir results          # every design above
python3 src/unbounded.py compare results/summary.json other/summary_pysat_cadical153.json
python3 -m pytest -q tests                                       # 49 passed, 3 skipped; about 1 min (machine dependent)
```

Options of `check`: `--init known|arbitrary|free_nongoal`, `--method all|oracle|kind|ic3`, `--goal-out`,
`--goal-value`, `--goal-mask`, `--attack-in`, `--key`, `--input-sites`, `--backend`, `--timeout`, `--plain-depth`,
`--out FILE`. Exit codes: 0 verdict, 2 unknown or vacuous, 3 input error, 4 methods disagree (no verdict printed).
The explicit method is limited to 20 flip-flops and 16 input bits; larger designs need the SAT methods.
**Hard dependency on `tools/fastsat`.** The `minicdcl` backend, which produced every stored result, is
`tools/fastsat/scripts/minicdcl.py`; `src/sat.py` loads it from `$GLITCHSAT_MINICDCL_DIR`, else from `tools/fastsat/scripts`
next to this directory. Land `tools/fastsat` in the same change as `tools/unbounded`. This is enforced: the test suite
stops with exit code 3 ("tools/unbounded requires tools/fastsat") when the solver is missing (set
`GLITCHSAT_ALLOW_NO_FASTSAT=1` to skip the SAT tests instead), `cloud_run.sh` refuses to start without it, and a test
checks that the loaded file has the SHA-256 recorded in `src/sat.py` (`MINICDCL_SHA256`), i.e. the version that
produced `results/`. The native backends (`--backend pysat|z3`) do not need fastsat.

## 6. Status labels

| Item | Status |
|---|---|
| All three methods, pure-Python SAT backend, all results in section 3 | MEASURED |
| Test suite: 49 passed, 3 skipped (the 3 need real python-sat / z3) | MEASURED |
| PySAT backend (CaDiCaL etc., with unsat cores in IC3) | UNTESTED HERE: run only against a stand-in module (`tests/fake_pysat`) |
| z3 backend | UNTESTED HERE: z3-solver is not installed on this cloud VM (and pip has no network access there) |
| `cloud_run.sh` | UNTESTED HERE: written for an Ubuntu 24.04 cloud VM with pip; installs nothing itself, runs the tests (including the real-backend ones), reruns every design with CaDiCaL and z3, and compares all verdicts with `results/summary.json` |
| Speed of the native solvers | NOT MEASURED; no speed-up is claimed |
| Backend parity (minicdcl = PySAT = z3 verdicts) | NOT CLAIMED until `cloud_run.sh` has run once and its `results/cloud_*/summary_*.json` are stored |
| Budgets above 3, larger designs | NOT RUN |

Cloud run:

```
sudo apt-get install -y python3-venv
python3 -m venv ~/gsat-venv && . ~/gsat-venv/bin/activate
pip install python-sat z3-solver pytest
GLITCHSAT_ROOT=/path/to/glitchsat sh cloud_run.sh       # results in results/cloud_<timestamp>/
```
