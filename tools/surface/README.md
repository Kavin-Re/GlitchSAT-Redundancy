# tools/surface: attack surface and redundancy-merge lint

Two analyses on GlitchSAT gate-level netlists (Yosys JSON). Both import `scripts/glitchsat.py` (`Netlist`, `build`,
`seq_counter`) and do not modify it. z3 is imported only inside the z3 path, so everything else runs without it.

Labels used below: **MEASURED** = tool output on the cloud VM (Ubuntu 24.04, 2 vCPU, Python 3.13, numpy 2.5, no z3, no Yosys);
**FROM-FILE** = copied from a repository file; **UNTESTED HERE** = written but not run on that cloud VM (needs z3).

**Which netlist "V2" means.** Every count in this README is for the netlist file named next to it. "V2 stored" is
`reference/spike_netlists/v2.json` (the reference Yosys JSON, 182 minimum triples at 6 cycles). The placed-and-routed
V2 that `tools/vlab` and `tools/shots` use (`v2_pnr.v`) is a different netlist with **22** minimum triples, so 182 must not
be compared with the vlab/shots numbers.

| file | what |
|---|---|
| `scripts/attack_surface.py` | every minimum-size attack, with per-net / per-cycle / per-copy counts |
| `scripts/merge_lint.py` | do the redundant copies still use separate logic? (structural, no solver) |
| `scripts/lint_validation.py` | runs the lint and the exhaustive minimum on every stored V1/V2-family netlist |
| `scripts/compare_methods.py` | z3 enumeration vs exhaustive simulator, attack set by attack set (needs z3) |
| `tests/` | pytest; the z3 file skips itself without z3; one slow test runs with `GLITCHSAT_SLOW=1` |
| `cloud_check.sh` | tests + z3 comparison on a machine with z3 (exit 2 `INCOMPLETE` without z3) |
| `results/` | outputs quoted in this file |

Set `GLITCHSAT_ROOT` to the repository root if `tools/surface` is not inside the repository (default: two levels up).

## 1. Attack surface

**Question it answers.** The engine reports one smallest attack. This lists *all* attacks of that smallest size m
(within the bound) and counts how many of them use each gate/flop, each cycle and each copy (c0/c1/c2). A net that
appears in many minimum attacks is a hot spot; an attack that touches only one or two copies shows which copies the
design really depends on.

Same modelled fault model and goal as `glitchsat.py build()`: single-cycle bit flip of a gate output or flop Q at a cycle
t < N, free inputs held constant, goal `boot_word == 0x96` at some cycle while `sig != 0xC3`. Fault sites are the
engine's `--reduce` set (default `full`). The set of minimum attacks does not depend on the reduction (a minimum attack
cannot contain a flip that never reaches the goal); MEASURED: V2 stored at 6 cycles gives the same 182 attacks with
`--reduce none` (456 sites, 15,699,320 triples) and `--reduce full` (353 sites), and V0 the same 19 with none/coi/full.

Methods:
* `exhaustive` (no z3): simulates every set of s flips for s = 0, 1, 2, ... until the first size with an attack,
  bit-parallel over all values of the free inputs (numpy, up to 16 input bits), batches of fault sets as array rows.
  Exact and complete when it finishes.
* `sat` (z3): finds m with the engine's counter encoding, then repeatedly takes a model with m flips and adds the blocking
  clause `Or(Not f_i)` over its fault-selector variables until UNSAT, the cap (`--cap`, default 100000) or the timeout
  (`--timeout-s`). Each attack found is re-simulated with the exhaustive simulator (`confirmed_by_simulation`).
  **UNTESTED HERE** (z3 not installed on this cloud VM): run `cloud_check.sh` on a machine with z3.

```
python3 tools/surface/scripts/attack_surface.py reference/spike_netlists/v2.json --top v2 --cycles 6 --k 3 \
        [--method auto|sat|exhaustive] [--timeout-s S] [--cap N] [--groups "0,3,6;1,4,7;2,5"] [--json out.json]
```
Exit code 0, or 2 when the result is INCOMPLETE.

JSON (`glitchsat-attack-surface/1`, full description in the module docstring): `method`, `bound` (cycles, max_faults,
goal, reduce, ...), `verdict`, `min_faults`, `count`, `complete` (true only if no smaller attack exists and every attack
of size m was found), `stop_reason` (`exhausted`/`cap`/`timeout`/`solver_unknown`/`no_attack`), `nets[]`
(`net, net_id, kind, gate, copy, count, share, cycles{t: n}`), `cycles{t: {faults, attacks}}`,
`copies{label: {faults, share, attacks}}`, `copies_touched{n: attacks}`, `attacks[]` (first 200 in full, with the number
of wrong inputs that work; when more exist, `note` says `TRUNCATED LIST`; all stored results list every attack), `note`.
`netlist` is stored relative to the repository root when the file is inside it.
Copy labels come from the lint: `c0` (inside copy c0's cone), `c0:path` (downstream of c0 only, e.g. its result-word
gate), `shared`, `merge`, `outside` (state/decode logic, no copy).

### Results (MEASURED, exhaustive, `results/surface_*.json`)

| netlist | cycles | m | minimum attacks | runtime |
|---|---|---|---|---|
| V0 stored | 6 / 4 | 1 | 19 / 15 | 0.1 s |
| V1 stored | 6 | 1 | 1 (`ok` @ cycle 1, all 255 wrong inputs) | 0.1 s |
| V2 stored | 6 | none with <= 2 flips (1 + 353 + 62,128 sets) | 0 | 0.8-1.1 s |
| V2 stored | 4 | 3 | 182 | 6.6-11.4 s |
| V2 stored | 6 | 3 | **182, complete** (7,331,458 sets simulated, sizes 0..3) | 44-80 s (varied with machine load) |
| V2 apt 0.33 (`research/c4/b3_inputs/nl/v2_apt033.json`) | 6 / 4 | 2 | 5 / 3 | 1.4 s / 0.3 s |
| V2 flow B (`validation/nl/v2.json`) | 6 | 1 | 4 | 0.1 s |
| V2 with input buffers (`research/c2/reviews/ct/tests/v2_inbuf.json`) | 6 | 1 | 8 (one per shared `sig` buffer) | 0.1 s |

V2 stored, 6 cycles, all 182 minimum attacks:
* every flip is in cycle 1 (the one cycle the state is CC); all 182 touch all three copies;
* top nets: `c1.m` and `c2.m` in 44 attacks each (24.2%), `c0.m` 36, `word[0]` 36 (c0's result-word gate),
  then the internal compare gates `c1/c2 new_n12_, new_n13_` (28 each) and `c0 new_n12_, new_n13_` (23 each);
* per-copy share of flips: c0 26.7%, c0:path 6.6%, c1 33.3%, c2 33.3%.

V2 apt 0.33: 5 attacks, all `new_n74_`@0 plus `new_n58_`@0..4; one flip on c0's path and one on c1's path; c2 never
needed (matches `docs/report/WHY_TWO_FLIPS.md`: 0xCC^0x96 touches copies m0, m1 only).

Agreement with independent files: 182 triples at T=4 and 3 pairs for V2-apt at T=4 equal `research/c6/p12/enum.json`;
V0 19 / V1 1 / V2 0 single flips and 0 pairs at T=6 equal `validation/VALIDATION.md` (FROM-FILE). The 182 attacks at
T=6 are the same *sets* as those found by `validation/netsim.py` for the slice "all three flips in cycle 1" (MEASURED,
one-off cross-check, 14 s). `validation/VALIDATION.md` l.20 lists the full k=3 enumeration of V2 at T=6 (all cycle
combinations) as not run; this module covers it (7,331,458 sets of size 0..3 simulated with `--reduce full`; all 15,699,320 triples over 456 sites with `--reduce none`).
An independent enumerator with its own netlist parser and simulator, no reduction, found the same 182 sets with the
same number of working wrong inputs for each set (review script `rv_enum.py`, kept outside this module; compared against
`results/surface_v2_T6.json`).

## 2. Redundancy-merge lint

**Question it answers.** Did synthesis keep the intended copies of the check apart, or do two copies now share nets, so
that one fault site acts on several copies? Instant (milliseconds), no solver.

How: decision bits = goal-port bits (flop Q replaced by its D net). Copy groups from hierarchy names (`c0.`, `\c0.`,
`c0/`; regex `--copy-regex`) or, when names are gone, from the decision bits: bits whose input-dependent logic overlaps
form one group. Reported: shared nets (inside two copy cones), merge points (combine copies before the decision bits;
the first ones are listed first), single points (either kind, reaching a decision bit), decision-bit ownership,
canonical structural hashes (copies with equal hashes are replicas that a structural-hashing pass could fold).
Verdicts: `merged`, `partially_shared`, `separate`, `single_group` (structural mode without `--copies N`), `no_copies`.

```
python3 tools/surface/scripts/merge_lint.py NETLIST.json --top v2 [--mode auto|names|structural] [--copies 3] \
        [--groups "0,3,6;1,4,7;2,5"] [--goal-out boot_word] [--json out.json|-]
```
JSON (`glitchsat-merge-lint/1`): `mode, verdict, copies{label: {named_nets, cone_size, hash, decision_bits}},
decision_bits[], shared_nets[], merge_points[], single_points[{net, kind, copies, decision_bits_reached}],
identical_copies, duplicate_hash_groups, structural_groups, findings[], runtime_s`.

MEASURED on the required cases:
* `reference/spike_netlists/v1.json`: MERGED, first merge point `ok` (c1+c2), reaches all 8 decision bits.
* `reference/spike_netlists/v2.json`: SEPARATE, no shared net, no merge point; bit ownership c0 {0,3,6}, c1 {1,4,7},
  c2 {2,5}, which is `sel` in `rtl/v2.v`. Structural mode (names ignored) recovers the same three groups. The three
  copies have the same canonical hash (replicas).
* `validation/nl/v2.json` (flattened, no names): one group; MERGED with `--copies 3`. The 4 nets it lists as reaching
  all decision bits are exactly the 4 single-flip attacks the attack surface finds.
* `v2_inbuf.json`: MERGED, the 8 input buffers are shared by c0+c1+c2; the attack surface finds exactly 8 one-flip attacks.

### Validation on every stored V1/V2-family netlist (MEASURED, `results/lint_validation.{md,json}`)

32 distinct netlists (by SHA-256; 9 V1 as a control, 23 V2 family: v2, v2e, v2c04, v2c4d, v2c5a, v2_wi), lint verdict vs
the exhaustive minimum at 6 cycles, k <= 3. Where a repository file records the minimum for the same file (12 netlists),
the measured value equals it in 12 of 12.

| V2 family | measured min 1 | measured min > 1 |
|---|---|---|
| lint merged | 2 | 0 |
| lint not merged | 2 | 19 |

V1 control: 9 of 9 merged and min 1 (by design: `ok = m1 & m2`).

Reading it honestly:
* Only 2 merged V2-family netlists are stored (flow B and the hand-built input-buffer case), so "merged predicts 1 flip"
  rests on 2 cases plus the V1 control. It is not a measured rate.
* The 2 misses are `v2c04` (apt and conda): copies separate, yet 1 flip. Cause is the encoding, not merging:
  0x04 xor 0x96 = 0x92 touches the bits of one copy only (`research/c6/p01`). The lint answers "are copies merged?",
  not "how many flips".
* "Separate" does not mean 3: 5 separate netlists need 2 (three apt 0.33 v2 builds, `formal/gen/w2o.json`, `v2c4d` apt).
* The repo's E2 matrix has a related column (FROM-FILE, `research/c2/e2_variance/raw/matrix.csv`, 264 solved V2
  builds): `distinct_match_nets == 1` gives min 1 in 129 of 147 rows, so even a merged compare is not always 1 flip
  there. Those netlists are not stored, so this lint was not run on them.

## 3. Tests and cloud check

`python3 -m pytest -q tools/surface/tests` MEASURED here: 23 passed, 2 skipped (z3 file, slow test), 43-48 s;
with `GLITCHSAT_SLOW=1`: 24 passed, 1 skipped, 93 s. Exhaustive tests: V0/V1 m=1 counts at T=4 and T=6, V1 `ok`@1,
V2 none with <= 2 flips at T=6 (exact set count), V2 182 at T=4 (and at T=6, slow), V2-apt 3 pairs, recorded witness
replays, honest key boots, reduction independence, cap/timeout give `complete: false`, JSON fields, CLI. Lint tests:
the verdicts above.

z3 path (UNTESTED HERE): `tests/test_sat_enumeration.py` (sat set == exhaustive set for V0, V1, V2 T=4, V2-apt T=4;
V2 k<=2 none; cap) and `bash tools/surface/cloud_check.sh [--slow]` (tests, then `compare_methods.py` over 7 cases,
8 with `--slow`, then a timed sat run on V2 stored). Without z3 it prints `CLOUD CHECK INCOMPLETE (z3 missing)` and
exits 2, so a CI job cannot mistake it for a full pass; `CLOUD CHECK PASSED` (exit 0) means every part ran.

## 4. Limits

* Bounded and modelled: N cycles, single-cycle flips of gate outputs and flop Q, inputs held constant and never faulted
  (input pins are fault sites only if the netlist has buffers on them, as `v2_inbuf.json` shows). Nothing about other
  fault models, longer runs or silicon.
* Exhaustive cost grows as C(sites, m): fine for m <= 2 on these designs, about a minute for m = 3 at 353 sites,
  out of reach for m = 4. Free inputs are limited to 16 bits.
* SAT enumeration: one solver call per attack; stops at `--cap` (default 100000) or `--timeout-s`; then `complete` is
  false and counts are lower bounds. Runtimes not measured here.
* The lint is structural: it cannot see encoding effects (v2c04) and does not say how many flips are needed. Structural
  mode without names cannot tell a one-copy design from merged copies unless `--copies N` or `--groups` is given.
  Copy names depend on the Yosys flow keeping hierarchy prefixes.
