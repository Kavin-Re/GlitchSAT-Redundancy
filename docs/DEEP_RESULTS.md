# Deep results: solver depth sweep (MEASURED, bounded)

**Re-run note (F1, CC-18):** `results/deep/work/nl/` is not stored and `run_one.py` uses absolute paths under `<repo>`, so do not run it on a copy expecting isolation; re-run single cells with `scripts/glitchsat.py check`. The stored per-run JSON in `results/deep/json/` is the checkable record. Scope of V2 rows: see the V2 scope paragraph in `docs/FINAL_STATUS.md` (word goal only; `boot_ok` falls to 1 flip; input nets not fault sites).

All numbers below were produced by `scripts/glitchsat.py` (unmodified, `run_check`, default `reduce=full`) via the wrappers in `results/deep/`. Nothing here is an unbounded proof. Every verdict holds only for: at most k modelled single-cycle bit flips (gate output or flop Q), within the stated number of cycles, attacker input `sig` free but held constant for the whole run (and != key 0xC3), goal `boot_word == 0x96` at some cycle < N, on the specific netlist named. Toy 8-bit designs.

## Commands
```
cd results/deep
python3 -I sweep.py deepk     # k=4,5 on V2 spike at cycles 4 and 6 -> sweep_deepk.json / .out
python3 -I sweep.py main      # 90-run grid below -> sweep_main.json / .out
# each run is: python3 -I run_one.py work/nl/<design>_<route>.json <top> <k> <cycles> json/<tag>.json
```
`sweep.py` runs 4 chains in parallel (wall times include some CPU contention; treat as roughly +-30 percent), 600 s hard timeout per run. Per-run JSON in `results/deep/json/`, per-run logs (command, verdict, wall seconds) in `results/deep/logs/`. Netlists in `results/deep/work/nl/`: `*_spike.json` are the spike's netlists (V2 verified byte-identical to `reference/spike_netlists/v2.json` with cmp); `*_rtl.json` are the repo's synthesis of `rtl/*.v` (scripts/synth.sh).

Resume note: a previous worker's sweep was still producing results when this job resumed. Its 86 finished runs were kept untouched; the sweep itself completed the 4 remaining ones (V2 spike k=2,3 at cycles 16 and 20). No run was redone or overwritten.

## 1. Grid: cycles 8, 10, 12, 16, 20 x k 1, 2, 3 (wall time per run)
No timeouts occurred: all 90 runs DONE, 0 TIMEOUT, 0 ERROR. In every run the fault-free legitimate key boots. "min n" is the minimized fault count.

| design | netlist | k | 8 | 10 | 12 | 16 | 20 |
|---|---|---|---|---|---|---|---|
| V0 | spike | 1 | ATTACK min 1 (0.5 s) | ATTACK min 1 (0.7 s) | ATTACK min 1 (0.4 s) | ATTACK min 1 (1.5 s) | ATTACK min 1 (2.1 s) |
| V0 | spike | 2 | ATTACK min 1 (0.5 s) | ATTACK min 1 (0.8 s) | ATTACK min 1 (0.7 s) | ATTACK min 1 (0.6 s) | ATTACK min 1 (0.7 s) |
| V0 | spike | 3 | ATTACK min 1 (0.7 s) | ATTACK min 1 (0.9 s) | ATTACK min 1 (0.6 s) | ATTACK min 1 (1.5 s) | ATTACK min 1 (1.2 s) |
| V0 | rtl | 1 | ATTACK min 1 (0.9 s) | ATTACK min 1 (1.0 s) | ATTACK min 1 (0.9 s) | ATTACK min 1 (0.6 s) | ATTACK min 1 (0.6 s) |
| V0 | rtl | 2 | ATTACK min 1 (1.0 s) | ATTACK min 1 (0.7 s) | ATTACK min 1 (0.7 s) | ATTACK min 1 (0.8 s) | ATTACK min 1 (0.9 s) |
| V0 | rtl | 3 | ATTACK min 1 (0.5 s) | ATTACK min 1 (1.0 s) | ATTACK min 1 (1.6 s) | ATTACK min 1 (1.4 s) | ATTACK min 1 (1.2 s) |
| V1 | spike | 1 | ATTACK min 1 (1.1 s) | ATTACK min 1 (1.3 s) | ATTACK min 1 (1.1 s) | ATTACK min 1 (2.6 s) | ATTACK min 1 (2.6 s) |
| V1 | spike | 2 | ATTACK min 1 (1.5 s) | ATTACK min 1 (1.4 s) | ATTACK min 1 (1.6 s) | ATTACK min 1 (1.8 s) | ATTACK min 1 (1.8 s) |
| V1 | spike | 3 | ATTACK min 1 (1.6 s) | ATTACK min 1 (1.4 s) | ATTACK min 1 (1.6 s) | ATTACK min 1 (2.0 s) | ATTACK min 1 (2.1 s) |
| V1 | rtl | 1 | ATTACK min 1 (1.0 s) | ATTACK min 1 (2.1 s) | ATTACK min 1 (1.8 s) | ATTACK min 1 (2.9 s) | ATTACK min 1 (3.0 s) |
| V1 | rtl | 2 | ATTACK min 1 (1.4 s) | ATTACK min 1 (1.0 s) | ATTACK min 1 (1.4 s) | ATTACK min 1 (2.2 s) | ATTACK min 1 (2.9 s) |
| V1 | rtl | 3 | ATTACK min 1 (1.3 s) | ATTACK min 1 (1.3 s) | ATTACK min 1 (3.2 s) | ATTACK min 1 (3.4 s) | ATTACK min 1 (3.2 s) |
| V2 | spike | 1 | no attack (0.9 s) | no attack (1.0 s) | no attack (2.1 s) | no attack (2.1 s) | no attack (4.0 s) |
| V2 | spike | 2 | no attack (12.0 s) | no attack (55.8 s) | no attack (53.6 s) | no attack (150.4 s) | no attack (294.3 s) |
| V2 | spike | 3 | ATTACK min 3 (45.4 s) | ATTACK min 3 (68.2 s) | ATTACK min 3 (48.4 s) | ATTACK min 3 (188.4 s) | ATTACK min 3 (474.9 s) |
| V2 | rtl | 1 | no attack (1.2 s) | no attack (1.4 s) | no attack (1.2 s) | no attack (3.1 s) | no attack (5.0 s) |
| V2 | rtl | 2 | ATTACK min 2 (1.4 s) | ATTACK min 2 (1.6 s) | ATTACK min 2 (3.3 s) | ATTACK min 2 (4.6 s) | ATTACK min 2 (5.4 s) |
| V2 | rtl | 3 | ATTACK min 2 (3.6 s) | ATTACK min 2 (2.1 s) | ATTACK min 2 (4.2 s) | ATTACK min 2 (2.6 s) | ATTACK min 2 (4.1 s) |

## 2. Deeper k on the V2 spike netlist
| k | cycles 4 | cycles 6 |
|---|---|---|
| 4 | ATTACK min 3 (3.3 s) | ATTACK min 3 (3.3 s) |
| 5 | ATTACK min 3 (1.4 s) | ATTACK min 3 (9.3 s) |

A larger budget does not lower the minimum: it stays 3 for k=3, 4, 5.

## 3. Is the minimum attack size stable as cycles grow?
Yes. In all 18 design/netlist/k series the verdict class and minimum fault count are identical at all five bounds 8 to 20, and agree with the N=6 results in `docs/ENGINE_STATUS.md`.
- V0: min 1 everywhere. V1: min 1 everywhere (spike and RTL netlists).
- V2 spike netlist: k=1 and k=2 give NO ATTACK at every bound 8, 10, 12, 16, 20; k=3 gives an attack of exactly 3 faults at every bound. **V2 spike never breaks with 2 faults at longer bounds up to 20 cycles; the earlier result is not overturned.** (Bounded: nothing beyond 20 cycles.)
- V2 re-synthesized from RTL: k=1 no attack; min 2 at every bound for k=2 and k=3. The weakness of the re-synthesized netlist persists at all depths.
- Fault cycles of the V2 spike k=3 attacks across the five bounds: [1] (the attacks are found at early cycles; the engine reports a minimal set, not all attacks).

## 4. Runtime versus cycles
V2 spike netlist, the expensive case (seconds, wall):

| cycles | 4 | 6 | 8 | 10 | 12 | 16 | 20 |
|---|---|---|---|---|---|---|---|
| k=2 (no attack, UNSAT) | 0.34 | 1.28 | 12.0 | 55.8 | 53.6 | 150.4 | 294.3 |
| k=3 (attack, min 3) | not run | not run | 45.4 | 68.2 | 48.4 | 188.4 | 474.9 |

(4 and 6 cycles for k=2 are from the existing `docs/ENGINE_STATUS.md` reduction benchmark, not from this sweep.) All other cases (V0, V1, V2 RTL, V2 spike k=1) stay under about 6 s even at 20 cycles. For V2 spike, growth is roughly 2x to 3x per +4 cycles between 12 and 20 (k=2: x2.8 then x2.0; k=3: x3.9 then x2.5); the 12-cycle values being below the 10-cycle ones is solver search variance. At 20 cycles k=3 uses 475 s of the 600 s budget, so about 20 to 22 cycles is the practical limit for V2 spike k=3 on this machine with this engine. For k=2, extrapolation (NOT measured) puts the 10-minute timeout around 26 to 32 cycles. Beyond that a different technique (induction, IC3-style) would be needed; none is implemented.

## 5. Honest limits
- Bounded model checking only: no induction, no unbounded proof. NO_ATTACK means none within k faults and N cycles.
- Fault model: single-cycle bit flips on gate outputs and flop Q only; no stuck-at, multi-bit/spatial, clock or voltage faults; no claim of physical feasibility.
- Attacker input is constant for the whole run; a time-varying `sig` is not covered, so NO_ATTACK for V2 spike k<=2 might not survive a dynamic input.
- Results depend on the exact netlist: V2 spike (min 3) versus V2 re-synthesized (min 2) from the same RTL.
- The independent validator (`validation/VALIDATION.md`) checked V2 exhaustively only to T=6, k<=2. The longer bounds here rest on glitchsat alone; no second solver or exhaustive check was run at 8 to 20 cycles.
- Wall times were measured with 4 jobs in parallel.
