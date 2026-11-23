# tools/soc: GlitchSAT on whole chips

## 1. In plain language

Until now GlitchSAT looked at one small block at a time: a comparison, a state machine, a counter. A real chip is
tens of thousands of gates: a processor, memory, a serial port, a debug port. Somewhere inside it a handful of
wires decide the questions that matter for security: *may this chip start? may a debugger take over? did the alarm
fire?*

"Analysing a whole chip" means four things here.

1. **Read the entire chip.** The source code of a complete open-source chip is turned into one list of gates and
   flip-flops (43,000 to 68,000 cells for the chips below).
2. **Pick a security decision and cut out what can influence it.** For a goal such as "the chip leaves reset
   although the authorisation value is wrong", everything that can affect that wire within the next T clock cycles
   is kept, and the rest is dropped. Sometimes that is 20 cells out of 43,660. Sometimes it is 99 % of the chip.
3. **Ask the GlitchSAT question on that piece:** what is the smallest number of momentary bit flips that reaches
   the goal? The answer is then replayed on the *whole* chip by a separate simulator.
4. **Scan everything else quickly:** list every protective structure the checker recognises across the chip and
   say whether it survived each way of building the chip; and try every single flip on the whole chip in
   simulation as a cross-check.

What it does not mean:

- A bit flip in a gate list is a **model** of a fault. Nothing here was measured on silicon.
- Every answer covers a **stated number of clock cycles after reset** (6 to 10 here), not the life of the chip.
- Big memories are **black boxes**: the analysis allows them to hold anything. That keeps "this cannot happen"
  answers safe, and it means an attack that is reported may rely on memory contents the solver chose.
- The chips were built with an open flow **without a cell library**. A production flow gives a different gate
  list and may give different numbers. Section 7 lists the limits in full.

## 2. What was measured

Everything in this table was produced by the commands of section 3 on a 2-core machine with about 7 GB of memory.
Full tables: `results/RESULTS.md`. Labels are defined in section 5.

| chip (variant) | cells (gates + flops) | security goal | T | slice of chip | faults needed, per build | label |
|---|---|---|---|---|---|---|
| PicoSoC + plain boot check | 43,660 (32,954 + 10,706) | boot accepted with a wrong value | 8 | 20 cells, 0.05 % | 1 / 1 / 1 | BOUNDED (within T) |
| PicoSoC + triplicated boot check | 43,720 (33,009 + 10,711) | boot accepted with a wrong value | 8 | 71 cells, 0.16 % | **3 / 2 / 1** (written / keep / flat) | BOUNDED (within T) |
| same | same | processor starts fetching with a wrong value | 8 | 43,426 cells, 99.3 % | **3 / 2 / 1** | BOUNDED (within T) |
| same | same | flash controller switched to manual pin control | 6 | 42,886 cells, 98.1 % | 2 / 2 / 2 | BOUNDED (within T) |
| Ibex demo system, as published | 43,554 (36,354 + 7,200) | processor in debug mode, debug port idle | 6 | 32,630 cells, 74.9 % | 1 | BOUNDED (within T) |
| Ibex demo system, lockstep on (this project's configuration, made by source edits; see section 7) | 67,641 (56,932 + 10,709) | same, and the alarm stays silent | 10 | 59,423 cells, 87.9 % | 1 (see caveats) | BOUNDED (within T) |
| same | same | processor copies disagree, alarm silent | 6 | 57,666 cells, 85.3 % | 3 | BOUNDED (within T) |
| OpenTitan Earl Grey | not known yet (read in full; the gate step needs a bigger machine) | (three goals drafted) | | | not run | NOT RUN |

Cell counts are for the `keep` flow (PicoSoC) and the `flat` flow (Ibex). Search times: 0.1 s for the small
slices, 9 to 118 s for the slices that are most of a chip. Synthesis: 11 to 26 s per PicoSoC netlist, 45 s and
71 s for the two Ibex netlists.

Three things these numbers say:

- **The build decides the protection.** The triplicated boot check needs 3 faults as written, 2 after ordinary
  synthesis with the check kept as its own block, and 1 when the optimiser sees the three copies together. The
  whole-chip inventory reports the same thing from the structure alone (copies SURVIVED, SURVIVED, REMOVED) and
  the merge lint says `separate`, `separate`, `merged`.
- **A check is only as strong as what it guards.** On PicoSoC the processor-side goal needs exactly as many faults
  as the check itself in every build: within eight cycles no cheaper way around the check exists in the 99 % of
  the chip that the slice contains. The flash-controller goal needs 2 in every build, with or without the hardened
  check, because that register is not protected by it.
- **Lockstep compares outputs.** On the Ibex demo system with lockstep, making the two processor copies visibly
  disagree while keeping the alarm quiet needs 3 faults. Setting the debug-mode register of the main copy needs 1,
  and the alarm stays quiet for the ten cycles analysed: the flip comes right after reset, before the comparison
  is armed, and the outputs of the two copies do not differ in that window. `chips/ibex_demo/chip.yaml` (`caveats`)
  says what this does and does not mean.

Whole-chip simulation campaigns (SAMPLED): every cell of the chip flipped once in every cycle, 261,324 to 676,410
scenarios per goal in 7 to 43 s, plus 20,000 random pairs. In all 21 goal/netlist combinations single-fault
successes appear exactly where the exact minimum within T cycles is 1, and no goal is reached without a fault.

Countermeasure inventory (whole chip): PicoSoC with the triplicated check: 4 entries found in the RTL, all four
read by hand (2 are deliberate, 2 are not countermeasures). Ibex demo system with lockstep: 46 entries, 4 read by
hand; the other 42 are unreviewed candidates (section 6).

### OpenTitan

| step | result here |
|---|---|
| Earl Grey: read and elaborate `top_earlgrey` at tag Earlgrey-PROD-M6 | done: 38 s, 2.7 GB peak, 675,182 word-level cells, 34 memories declared (1,933,364 bits) |
| Earl Grey: clean-up to word-level cells (`coarse`) | done: 148 s, 2.9 GB peak, 280,436 cells |
| Earl Grey: map to gates, flat | **stopped**: the process was killed for lack of memory at 6.1 GB, inside `techmap`, after 35 s |
| Earl Grey: map to gates, hierarchical | **stopped**: same, at 6.1 GB after 139 s |
| English Breakfast | **not possible here**: its top-level RTL is not in the tag; generating it needs two Python packages that cannot be installed in the build environment |

So no gate or flop count and no fault result exists for an OpenTitan top. `cloud/run_opentitan.sh` (Ubuntu
24.04, 4 cores, 16 GB) continues from the step that stopped; it is written and has not been run. The three Earl
Grey goals in `chips/earlgrey/chip.yaml` are drafts whose net names come from reading the RTL.

## 3. Use

Needs Python 3.11+ with PyYAML, the repository (`scripts/glitchsat.py`), `tools/scale`, `tools/fastsat`,
`tools/checker`, `tools/surface`; Yosys for the front end (Yosys with `read_slang` for the Ibex and OpenTitan chips:
set `GSOC_YOSYS_SLANG=/path/to/yosys`, and `GSOC_SLANG_PLUGIN=1` if `read_slang` is a plugin in that build);
CaDiCaL or Kissat on `PATH` (otherwise the bundled Python solver is used, which is slow on chip-size slices).

```
bash tools/soc/chips/picosoc/fetch.sh            # pinned sources into tools/soc/work/src (not committed)
bash tools/soc/chips/ibex_demo/fetch.sh

python3 tools/soc/glitchsat_soc.py list
python3 tools/soc/glitchsat_soc.py build     picosoc                    # six netlists, about 2 minutes
python3 tools/soc/glitchsat_soc.py analyse   picosoc --variant tmr --time-s 170 --workers 2
python3 tools/soc/glitchsat_soc.py campaign  picosoc --variant tmr --flow keep
python3 tools/soc/glitchsat_soc.py inventory picosoc --variant tmr
python3 tools/soc/glitchsat_soc.py report                               # RESULTS.md, soc_results.json, Studio JSON
python3 -m pytest -q tools/soc/tests                                    # 31 tests, a few seconds
```

Every step writes one file under `results/runs/` and is skipped when that file exists (`--force` redoes it), so an
interrupted run continues where it stopped. No step of the measured chips takes more than about two minutes; the
longest command above (`analyse picosoc --variant plain`, nine searches) took 6.5 minutes. The stored results
were made with `GSOC_BACKEND=dimacs:kissat --workers 2`.

Exit codes: 0 done, 2 at least one result is PARTIAL only, 3 input error, 4 internal error (a witness that does
not replay on the whole chip).

A chip is described by `chips/<name>/chip.yaml`: sources and pinned commit, top module, variants, flows, clock,
reset, and the goals. A goal:

```yaml
- id: boot_release
  hit: ["soc_resetn=1"]          # these nets have these values in one cycle ...
  hold: 4                        # ... for this many cycles in a row
  quiet: ["alarm_o=0"]           # these stayed at these values up to then (optional)
  attacker: {port: sig, differs_from: 0xC3}   # an input the attacker holds at a wrong value (optional)
  fix: {trst_ni: 0}              # inputs tied for the whole run (optional)
  cycles: 8                      # T
  kmax: 4                        # largest fault budget tried
```

Goals must name ports, registers or nets marked `(* keep *)`: other names may not survive synthesis.

| file | what |
|---|---|
| `gsoc/frontend.py` | RTL to gate-level netlist with Yosys, three flows, resumable |
| `gsoc/chip.py` | netlist loader: gates, flop kinds, clock domains, clock gates, black boxes |
| `gsoc/sim.py` | three-valued reset analysis; compiled bit-parallel whole-chip simulator |
| `gsoc/slicer.py` | goals, the slice, the hold monitor, replay of a witness on the whole chip |
| `gsoc/run.py` | the steps and their result files |
| `gsoc/inventory.py` | whole-chip countermeasure inventory, survival, merge lint (reuses tools/checker, tools/surface) |
| `gsoc/campaign.py` | whole-chip fault campaigns (SAMPLED) |
| `gsoc/report.py` | tables and the Studio "Explore a real chip" JSON |
| `chips/` | one folder per chip: `chip.yaml`, `fetch.sh`, added RTL |
| `chips/earlgrey/frontend.sh`, `gen_prim_shims.py` | the OpenTitan front end as far as it runs here |
| `cloud/run_opentitan.sh` | prepared continuation on a larger machine (not run) |
| `results/` | `runs/*.json` (one per step), `RESULTS.md`, `soc_results.json`, `opentitan_attempt.json` |
| `studio/explore_chip.json` | guided view: what the chip is, where its security decisions live, what was found |

## 4. Method and soundness

Fault model and question are those of `scripts/glitchsat.py` and `tools/scale`: a fault flips the output of one
cell (a gate output or a flop Q) for one cycle; at most k faults in cycles 0..T-1. An *attack* is a choice of
inputs, of the free values defined below, and of at most k flips that reaches the goal.

### 4.1 Front end and loader

*Flows.* `written`: elaborate, flatten, map to gates, constant folding only. `keep`: Yosys `synth` up to the
coarse stage, then `techmap`, `abc -g AND,OR,XOR,MUX`; modules marked `keep_hierarchy` are optimised on their own
and flattened afterwards. `flat`: the same with `keep_hierarchy` removed first. No cell library is used.

*Fault sites.* One per cell: its output. Cells that are not one of the engine's five gate types (NAND, AOI3, ...)
and flops with enable or reset are expanded into primitives whose inner nets are not fault sites, so the number
of fault sites equals the number of cells. Tested: `tests/test_chip_loader.py` checks every gate type against its
truth table and every flop kind against its waveform.

*Free values.* Four things are replaced by a value that the solver may choose anew in every cycle: the outputs
of black boxes (memories above `memory_map_max_words`, any cell that is not a gate or a flop), constant `x` bits,
undriven nets, and the "tick" of a clock that is neither the reference clock nor a recognised clock gate.

**Claim A (over-approximation).** Let M be the model and C the chip with any memory contents, any resolution of
`x`, and any schedule of the other clocks in which no clock has more than one edge per reference cycle. Every run
of C under faults is a run of M under the same faults with some choice of the free values. Hence if M has no
attack with at most k faults within T cycles, C has none.
*Argument.* Each replaced object has, in each cycle of a run of C, one definite Boolean value; M allows both.
The rest of M is C's logic unchanged. []

The converse does not hold: an attack found in M may use free values that C cannot produce. Every result
therefore records how many free values the witness sets (`free_values_set_to_1`) and says so in its note.

*Clock gates.* A latch that is transparent while the reference clock is low, ANDed with the reference clock, is
modelled exactly: the gated domain loads in the cycles whose enable is 1 (the latch passes the enable of the low
phase to the following edge). No free value is used, and a fault on the enable logic stops or starts that domain,
as it would on the chip. Ibex's core clock (5,916 flops in the lockstep chip) is handled this way.

*Asynchronous resets* are modelled as a reset that takes effect at the next edge, outside the clock tick (the
usual async2sync abstraction): a fault on a reset net still resets the flops it reaches, one cycle late. A fault
that produces a reset pulse shorter than a cycle is the same event in this model.

*Negative-edge flops* (4 in PicoSoC's flash controller, 1 in the Ibex debug port) and the JTAG clock domain of
the Ibex chip (225 flops) get a free tick. For a truly unrelated or faster clock, Claim A's side condition is an
**assumption**, not something checked.

### 4.2 Reset state

The analysed window starts when reset is released. `sim.reset_state` simulates the reset with three values
(0, 1, unknown): reset pin active, every other input unknown, every flop without a Verilog initial value unknown.
After R cycles (16) the state is widened (`s := join(s, next(s))`) until it is stable.

**Claim B.** For every reset lasting at least R cycles, from every power-up state and under every input, each
flop reported 0 or 1 has that value at release.
*Argument.* Three-valued gate evaluation is monotone: a definite output is the output for every completion of the
unknowns. By induction the state after i steps contains every reachable state after i reset cycles. The join only
replaces values by "unknown", and its fixed point contains the states after R, R+1, ... cycles. []

Flops reported unknown get a free start value in the search (one free input per flop, used in cycle 0 only).
PicoSoC: 606 known, 10,105 unknown (the processor's data path has no reset). Ibex lockstep: 4,875 / 5,834.

### 4.3 Goal-directed slice

For a goal with observed nets O (hit and quiet nets), let d(n) be the least number of flops on a path from net n
to a net of O. The slice for horizon T keeps every net with d(n) <= T-1. A flop with d = T-1 keeps its start
value and its D input is cut.

**Claim C (exactness).** For the same inputs, start values and faults, every net of O has the same value in the
slice and in the chip in cycles 0..T-1. So the slice and the chip have the same attacks, for every k.
*Argument.* The value of an observed net in cycle t <= T-1 depends on a net n only through paths with at most t
flops, so only on nets with d(n) <= T-1, and on a net with d(n) = j only in cycles <= T-1-j. A flop with
d = T-1 is therefore read only in cycle 0, where it shows its start value; what it loads later is never read.
Faults on dropped cells cannot change an observed value for the same reason. []

Tested: `tests/test_slice_and_search.py` compares the sliced search with a brute force over all fault sets of size
up to 2 on the whole circuit for random sequential circuits and T = 1, 2, 3, and with the repository's reference
designs (minimum 1, 1, 3) with and without unrelated logic attached.

*Hold.* "For h cycles in a row" is built from fault-free monitor logic outside the chip (an AND of the hit
condition with h-1 delayed copies). The monitor is not a fault site, so it cannot be attacked.

### 4.4 Minimum faults

The slice is handed to `tools/scale` unchanged in method: unrolling with hard-constant folding, post-dominator
fault-site reduction (Lemma 1 of `tools/scale/README.md`), module summaries with refinement (its composition
argument: anything the abstraction rules out is impossible; anything it allows is rebuilt with real flips and
replayed), one incremental formula for budgets 0..k, two processes racing lower and upper bound, interval answers
at the time limit. On the 43,426-cell slice of PicoSoC that is 347,408 candidate flips (cells times
cycles) reduced to 54,953 fault variables before the solver starts.

Every attack is replayed twice: by `gscale.sim.replay` on the slice, and by `slicer.replay_on_chip` on the whole
chip with the compiled simulator of `gsoc/sim.py`, which shares no code with the unrolling, the reductions or the
encoder. A witness that does not replay on the whole chip stops the run with exit code 4. "No attack with fewer
faults" has no such certificate; it rests on Claims A to C, on `tools/scale`, and on the solver.

### 4.5 Whole-chip scans

`inventory` runs `tools/checker` (RTL scan, netlist scan, survival verdicts) and `tools/surface` (merge lint) on the
whole-chip netlists of every flow. Black boxes are removed for the checker and their outputs become inputs (the
same free-value treatment). RTL-scan entries whose module left no cell in the netlist are dropped (a source file
can hold modules the variant does not use). They took under a minute per chip variant.

### 4.6 Campaigns

`campaign` flips every cell once in every cycle (single faults: complete) and a sample of random pairs, each with
one random draw of the environment. It can exhibit attacks and can contradict a proof; it cannot replace one.
Verilator was not built; the simulator is the compiled Python one (349,760 whole-chip scenarios in about 13 s).

## 5. Labels

| label | meaning |
|---|---|
| **BOUNDED** (within T cycles) | exact minimum within T cycles: an attack of that size was replayed on the whole chip, and the solver showed that no smaller one exists in the model within those T cycles. Not an unbounded proof, so it is never called PROVED (in the Studio PROVED means "for any waiting time") |
| **PARTIAL** | only bounds within T cycles: an interval lo..hi, or "no attack with up to k faults" |
| **SAMPLED** | a simulation campaign: counts over the scenarios that were run |
| **MEASURED** | sizes and times read from a run in the build environment |
| **NOT RUN** | written and not executed (everything about OpenTitan tops beyond the front-end table) |

BOUNDED is a statement about the model on one netlist and T cycles. It is never "the chip needs n glitches".

## 6. Reading the inventory

The checker's scans were designed on blocks of a few hundred gates. On a whole chip:

- the RTL scan calls any output named `*err*`, `*alert*`, `*fault*` an alarm, and any group of instances of one
  module with common inputs "copies". Ibex's eight control registers are reported as "8 copies of ibex_csr";
  they are not redundant.
- the netlist scan finds incidental duplication (two unrelated places computing the same function): 132 entries
  in PicoSoC as written, 5 after synthesis.
- UNTRACKED means the name-based tracking did not find the object in the flattened chip, not that it is gone.
- with a single flow (Ibex) there is no "as written" reference, so a verdict compares the netlist with the RTL
  text only.

Entries listed under `reviewed:` in a `chip.yaml` were read against the RTL by hand, and the note says what they
are. Everything else is a candidate. Two examples of why the review matters: `alert_minor_o` of the Ibex chip is
REMOVED because it is constant 0 by configuration (its only source is an instruction cache the chip does not
have), not because synthesis lost it; PicoRV32's one-hot `cpu_state` is reported as a sparse encoding and is not
a countermeasure.

One oddity: in the `written` netlist of the triplicated check the merge lint names two copies, not three. Constant
folding removed a double inversion behind copy c0, so its named output is no longer read; the copy's logic is
still there and separate.

## 7. Limits

- Model, not measurement. Single-cycle bit flips on cell outputs; no timing, no layout, no multi-cell spots.
- Bounded: T cycles from reset release. Nothing is said about later cycles or about a chip that has been running.
- Free memory contents and free start values: sound for "cannot happen", possibly optimistic for the attacker in
  "can happen". The Ibex results in particular are for *some* RAM content.
- Inputs other than those tied in the goal are free in every cycle.
- Multi-clock designs: exact for recognised clock gates; an assumption for other domains (section 4.1).
- One open synthesis flow, no cell library, no scan insertion, no placement.
- PicoSoC has no security feature of its own; its boot check is this project's addition. The Ibex "lockstep"
  variant is this project's configuration of the demo system (source edits listed in
  `chips/ibex_demo/fetch.sh`), not something lowRISC ships in that form.
- Speed is measured on these chips only. Slices of 60,000 cells and ten cycles took up to two minutes; a chip ten
  times larger was not tried, and Earl Grey could not even be mapped to gates here.

## 8. Sources and licences

| chip | repository | pinned commit | licence |
|---|---|---|---|
| PicoSoC | github.com/YosysHQ/picorv32 (`picosoc/`) | ef203c2b0a3fb793280f5114941416c425c5b461 | ISC |
| Ibex demo system | github.com/lowRISC/ibex-demo-system (vendored Ibex 594ea976c9da) | d37beb753e19482eb054aefac73a27289bf72e47 | Apache-2.0 |
| OpenTitan | github.com/lowRISC/opentitan, tag Earlgrey-PROD-M6 | a78922f14a8cc20c7ee569f322a04626f2ac6127 | Apache-2.0 |

No third-party source is committed: the `fetch.sh` scripts download it into `work/` and check commit and licence
file. Code in this folder is this project's own (Apache-2.0; the two Verilog files added to PicoSoC are ISC).
