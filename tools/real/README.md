# GlitchSAT on real silicon netlists: OpenTitan AES and Ibex blocks from SYNFI

## In plain words

**What real design.** Three gate-level netlists of real OpenTitan hardware, as published by lowRISC in the SYNFI
repository (github.com/lowRISC/synfi, Apache-2.0, pinned at commit `2d08c4c`). They were synthesised with the
open-source tool Yosys onto the Nangate45 standard-cell library:

| Netlist | What it is | Cells | Flip-flops |
|---|---|---|---|
| `aes_cipher_control_fsm` | the state machine that steps the AES cipher through its rounds | 230 | 7 |
| `aes_cipher_control` | the hardened version: three copies ("rails") of that state machine, an up and a down round counter and an error check | 920 | 44 |
| `ibex_if_stage` | the instruction-fetch stage of the Ibex RISC-V core, which holds the program counter (PC) | 1,653 | 284 |

**What GlitchSAT now does with them.** A new adapter translates every Nangate45 cell into the five logic primitives
the GlitchSAT engine understands, so GlitchSAT can read these netlists directly. The translation was proved
correct cell by cell (every input combination) and on the whole netlists (44 million simulated net values, no
difference from SYNFI's own description of the cells).

**What we found.**

1. **GlitchSAT and SYNFI agree.** We ran SYNFI itself, unchanged, on its own five example experiments. Every one of
   the 4,226 fault injections SYNFI made got the same answer from GlitchSAT (yes, this fault set works / no, it does
   not). For the one experiment the paper ran on exactly this kind of netlist (Ibex, "glitch the PC"), SYNFI's
   published 78.1% effective faults out of 557 is reproduced exactly; for "set the PC to a chosen value" the
   exhaustive two-fault count on this netlist is 80 of 309,580 faults (40 of 154,790 fault sets). That is
   SYNFI's own count here: SYNFI's code builds exactly that list, and SYNFI's injector marks all 40 sets effective.
   The paper prints 62 of 309,500 (31 of 154,750 sets). No unlimited run of the published code, netlist and
   specification gives the paper's figure (section 3, "E5 reconciliation").
2. **GlitchSAT gives the security margin directly.** SYNFI asks "if I inject exactly k faults, what fraction works?"
   and tries every combination. GlitchSAT asks "what is the smallest number of faults that works?" and answers with
   one solver query (under a second here), then lists every attack of that size. Results: the unprotected round
   counter falls to **1** fault, the protected round counter needs **2**, the Ibex PC can be changed by **1** fault
   but set to a chosen value only with **2**.
3. **Where the attacks are.** In the protected round counter, the single NAND3 gate that combines the error
   signals (`rnd_ctr_err_d`) and the error register after it appear in 37 of the 224 two-fault attacks each.
   For the Ibex PC, 51 of the 64 fault positions in the 32 minimal attacks are *signals outside the analysed
   region* that SYNFI's method leaves free; we therefore re-checked the same question on the whole Ibex netlist over
   three clock cycles: still 2 faults (267 different two-fault attacks, all found).
4. **The state-machine encoding.** One AES state machine stores its state with a code where any two valid states
   differ in at least 3 bits. Flipping only state bits, GlitchSAT finds that 3 flips are needed, as the paper says
   (Table 4). But flipping the logic that computes the next state, **1** fault is enough for 4 of the 33 forbidden
   transitions. In the three-rail version no single fault was found for the question we checked: from reset,
   skipping straight to the final round (FINISH) needs **2** faults; the attack found sits on the two OR gates
   that merge the rails' round-count outputs.
5. **Did the redundancy survive synthesis?** Yes for the three rails: no cell of one rail feeds another rail.
   What the rails do share is by design (six inputs, the round-counter and a few control registers, two gates
   that combine error inputs, and the gates that merge the rails' outputs), and the two-fault attacks above use
   such shared points.

**How this compares with SYNFI.** Same netlists, same fault specifications, same answers. GlitchSAT adds the
minimum fault count, the complete list of minimum attacks, a bit-flip fault model next to SYNFI's gate-replacement
model, whole-netlist multi-cycle checks, and a structural redundancy lint. SAT-based fault analysis itself is not
new (SYNFI is SAT-based); what is reported here is a reproduction and an extension on real netlists.

**Limits.** Everything is about *modelled* faults in a netlist, not a measured chip. Multi-cycle results are
*bounded*: they hold for the stated number of clock cycles and fault budget only. SYNFI's paper numbers for the AES
experiments (Tables 1 and 4) come from a commercial synthesis flow and cell library, so those rows describe a
different netlist; only the Ibex rows (Table 7) used the same open flow as the files here.

---

## 1. Inputs (pinned)

| Item | Version | Use |
|---|---|---|
| lowRISC/synfi | `2d08c4c84b04a4ed9998e1f09033691ca88f447e` (2023-08-29), Apache-2.0, cloned to `synfi/` | netlists (`examples/*/netlist_*.json`, Yosys 0.10+1, Nangate45), fault specifications, cell library `cell_lib_nangate45_autogen.py`, the SYNFI tool itself |
| lowRISC/opentitan | `097521294cd43a3e059bed8c0cd2a710b4f7f73e` (sparse: `hw/ip/aes/rtl`), in `ot_097521/` | the FSM state encodings (`aes_cipher_control_fsm.sv`, minimum Hamming distance 3) |
| SYNFI paper | Nasahl et al., *SYNFI: Pre-Silicon Fault Analysis of an Open-Source Secure Element*, IACR TCHES 2022(4), arXiv:2205.04775v2 | published numbers, transcribed in `tools/datasets/published_results.json` (id `synfi_2022`); text statements checked against the arXiv PDF |
| GlitchSAT engine | `scripts/glitchsat.py` (read only) | `Netlist` parser used for every adapted netlist |
| `tools/fastsat` | CNF `Encoding`, totalizer, backends (`minicdcl` pure-Python CDCL, DIMACS binaries) | all solving |
| `tools/surface` | `merge_lint.py` | redundancy-merge lint (run unchanged) |

Solvers: every number in `results/experiments.json`, `results/fsm_state_single.json` was produced by the bundled
pure-Python CDCL (`minicdcl`). CaDiCaL 3.1.0 (`cadical`, built from source by a separate
step) re-ran all of `run_experiments.py` (`results/experiments_cadical.json`) and the single-FSM table
(`results/fsm_state_single_cadical.json`): identical minimum fault counts, effective counts and numbers of minimum
attacks in every row. The three-rail FSM run (`fsm_state_multirail_from_reset.json`) and the whole-netlist Ibex run
(`ibex_pc_native.json`) were produced with CaDiCaL (field `backend`). z3 and Yosys were not available.

## 2. The Nangate45 adapter (`glitchsat_real/nangate.py`)

* **Source of the cell functions:** SYNFI's `cell_lib_nangate45_autogen.py` (generated by SYNFI from
  `NangateOpenCellLibrary_typical.lib`). For each (cell, output pin) the documented function
  (`ZN = !((A1 & A2) | (B1 & B2))`) is parsed into `$_AND_ / $_OR_ / $_XOR_ / $_NOT_ / $_MUX_`; `((S & B) | (A & !S))`
  becomes one `$_MUX_`; buffers become two inverters.
* **Exhaustive check:** for all 98 (cell, pin) functions of the library, all 1,326 input rows: primitive tree ==
  documented function == the unique output value allowed by SYNFI's own CNF clauses for that cell (the clauses are
  generated by calling SYNFI's function with a recording solver). A failing cell is refused.
* **Flip-flops:** SYNFI models a register as Q = D. Here `DFF`, `DFFR` (RN clears), `DFFS` (SN sets), `DFFRS`, `SDFF*`
  (scan mux) become `$_DFF_P_` plus logic. Reset mode `deasserted` (default): reset held inactive, flops start at
  their reset value (exact for a run without reset). Mode `sync`: reset folded into D (exact at clock edges when
  reset is held across the edge; an asynchronous pulse between edges is not modelled). Enables in these netlists
  are ordinary `MUX2_X1` cells in front of `DFF_X1` (Yosys `dffe` mapping) and need no special handling. Latches,
  clock gates and tie cells are refused; tristate cells only on request (SYNFI ignores their enable).
* **Fault sites stay real:** a multi-primitive cell creates internal nets, but only the original cell outputs and
  flop outputs are fault sites (`meta['sites']`).
* **Whole-netlist proof (`scripts/validate_adapter.py`, `results/adapter_validation.json`):** the original netlist
  evaluated with SYNFI's clause semantics and Liberty flop behaviour (`refsim.RefSim`) against the adapted netlist
  parsed by the GlitchSAT engine (`refsim.PrimSim`), 512 random lanes x 12 cycles, every net of the original netlist,
  four netlists (the three above and `examples/circuit.json`) x two reset modes: **43,929,600 comparisons, 0
  mismatches**; plus the engine-side scalar simulator (`fastsat.simulate`) on 712 output-port traces: 0 mismatches.
  A deliberately corrupted netlist (one AND turned into OR) is caught (`tests/test_adapter_cosim.py`).

## 3. Reproducing SYNFI's experiments (`scripts/run_experiments.py`, `results/experiments.json`)

**SYNFI re-run here.** `scripts/run_synfi_reference.py` runs SYNFI's unmodified `parse.py` and `fi_injector.py`. Three
packages cannot be installed here, so `shims/` replaces them: `ray` runs sequentially, `pysat.solvers.Minisat22` is
backed by the pure-Python CDCL, `sympy.Symbol` is a stub (used only as a type hint on this path). Every injection
SYNFI makes is stored in `results/synfi_reference/`. The 2-fault runs over all gates are too slow here (about
0.3 s per injection), so they were run on the first 2,000 faults of SYNFI's own order (`-l 2000`), and 8 GlitchSAT
attacks were handed back to SYNFI as explicit fault locations (`scripts/synfi_targeted_check.py`): SYNFI confirms
all 8.

**GlitchSAT's SYNFI-compatible model (`glitchsat_real/region.py`, `synfi_model.py`).** Written from SYNFI's
documented behaviour, not by calling SYNFI: the target region between the stage end points (`region.py`; its node
sets equal SYNFI's extracted graphs for all three netlists, and its size in GE equals SYNFI's log: 23.67, 556.33,
488.0), side inputs free, registers inside the region transparent, SYNFI's gate-replacement options with its pin
re-mapping, and SYNFI's goal (golden output = expected, faulty output differs or equals the target, alerts quiet).
One CNF with a selector per (location, option) answers every injection by assumptions.

| Exp | SYNFI paper (cited) | SYNFI re-run here | GlitchSAT, same model | per-injection agreement | GlitchSAT minimum faults: gate replacement / bit flip |
|---|---|---|---|---|---|
| E1 round counter, change (FE) | 1 fault, 55.56% of 18, 4.4 s, 20.25 GE (Table 1 row 1; DC netlist) | 46.43% of 28 (23.67 GE) | 46.43% of 28 | 28/28 | 1 / 1 |
| E2 round counter, set to 4 (FS) | 2 faults, 2.65% of 302, 4.47 s (Table 1 row 2; DC netlist) | 1 fault: 1 of 28; 2 faults: 6.45% of 744 | same: 1 of 28; 6.45% of 744 | 400/400 | **1** / 1 |
| E3 protected round counter (FD) | 2 faults, 0.13% of 34,652 (printed "34.652"), 366.81 s, 156 GE (Table 1 row 3; DC netlist) | 1 fault: 0 of 675; first 2,000 2-fault: 0 effective; explicit 2-fault locations: 9 of 9 | 1 fault: 0%; 2 faults: 0.28% of 454,218 (SYNFI counting), 0.2817% of 225,762 distinct | 1,684/1,684 (+4/4 targeted) | 2 / 2 |
| E4 Ibex PC, change (FE) | 1 fault, 78.1% of 557, 185.07 s, 488 GE (Table 7 row 1; Yosys + Nangate45) | **78.1% of 557** (55.3% comb. + 22.8% seq.), 488 GE | **78.1% of 557**; 77.59% of 473 distinct | 557/557 | 1 / 1 |
| E5 Ibex PC, set to 0x40400 (FS) | 2 faults, 0.02% (62 of 309,500), 0.72 h (Table 7 row 2) | 1 fault: 0 of 557; first 2,000 2-fault: 0 effective | 1 fault: 0%; 2 faults: 80 of 309,580 = 0.026% (SYNFI counting); 34 of 111,572 distinct | 1,557/1,557 (+4/4 targeted) | 2 / 2 |
| Ibex lockstep (Table 7 row 3) | 1 fault, 6.31% of 111 | not reproducible: no lockstep netlist in the repository | - | - | - |

Notes on the table:
* "SYNFI counting" reproduces SYNFI's own enumeration exactly: its fault-location list repeats some entries (84 of
  557 in Ibex, 2 in the AES control), because locations are keyed by parent cell, so a register and the free inputs
  cut from it are listed again. The paper's 78.1% includes the repeats; over distinct injections it is 77.59%.
  The exhaustive 2-fault numbers are computed from GlitchSAT's exact pair verdicts applied to SYNFI's list (a pair
  that names one node twice acts as one fault there), with no solver call. For E5 this gives 309,580 injected
  faults and 80 effective, against 309,500 and 62 in the paper; see "E5 reconciliation" below.
* **E5 reconciliation** (`scripts/synfi_e5_enumeration.py`, `scripts/e5_reconcile.py`,
  `results/e5_reconciliation.json`, raw data in `runs/e5_reconcile/`).
  * *Units.* SYNFI counts faults, not fault sets. With `-s 2` it logs `len(sets) x 2` and
    `evaluate_fault_results` adds 1 for each location of an effective set. In fault sets the comparison is
    154,790 sets with 40 effective (here) against 154,750 with 31 (paper). The gap is 40 sets and 9 effective
    sets, not 80 and 18.
  * *How SYNFI forms the sets* (pinned code, `--auto_fl`, no `-l`). Every node of the target graph except
    in/out nodes and registers is a location: cells, side inputs, the stage input and output, and the input copies
    that `unroll_circuit` cuts from each register in a loop. `handle_fault_locations` then lists every node
    of a parent cell once for each such node. A register cut into c copies therefore has itself and each copy
    listed c times. That gives 516 entries for 432 locations: 18 registers have 2 or 3 copies, giving 84 repeated
    entries. The sets are `itertools.combinations(entries, 2)`, each crossed with both entries'
    `node_fault_mapping` lists: 557 single options, Σn² = 669, (557² − 669)/2 = 154,790 sets. Nothing else is
    excluded (`exclude_auto_fl` and `exclude_cells_graph` are empty). There is no cycle handling beyond the
    register cut, and pairs that name the same node twice stay in the list.
  * *SYNFI's own run on this netlist.* SYNFI's functions (`extract_graph`, `handle_fault_locations`,
    `fault_combinations`, unmodified, with `shims/`) build 154,790 sets ("Injecting 309580 faults") under two
    `PYTHONHASHSEED` values. The order changes with the seed because networkx iterates a Python set, but the
    content is the same. SYNFI's own `FiInjector` ran on 1,893 sets: all 40 sets GlitchSAT finds effective
    (40/40 effective), every set formed only from locations that occur in some effective set (853 sets, 40
    effective), and 1,000 random sets (0 effective). GlitchSAT's verdict matches on all 1,893.
    GlitchSAT's effective-pair search is complete, so SYNFI's exhaustive result on this netlist is 80 of 309,580.
    The full SYNFI run (about 0.5 s per set, about 21 h on one core here) was not done.
  * *The 40 effective sets.* 31 sets pair two entries that are each listed once. The other 9 are 3 distinct
    pairs, each listed 3 times. Each pairs the side input from BUF `$8937` with one node of the PC bit-18
    register `$898` (cut into 3 copies): the register itself (`prim_flop_fault`) or its copies feeding `$9032`
    or `$9034`. Over distinct injections there are 34 effective of 111,572 sets.
  * *The paper's figure.* The location list is pinned down by the single-fault row: 557 injections and 78.1%
    reproduce exactly, and the E4 and E5 specifications have identical mappings. The netlist and specification
    are unchanged since they were added (commit `78dbbc8`, Feb 2022). Later code changes (`ea6c15b` cell-library
    refactor, `be68852` regex matching) do not touch the location list or the pairing. A different location
    list cannot give 154,750: adding or removing one entry moves the count by about 556 sets. Changing the
    mapping of some or all cells of one type gives no exact match either. A `-l 309500` limit would give
    exactly "309500", but under both orders the last 40 sets contain 0 effective sets, so the numerator would
    stay 80. The paper (arXiv:2205.04775, Sec. 4.3) does not say whether the run was exhaustive or limited, or
    which revision it used. **Conclusion:** both the denominator gap and the numerator gap come from the paper's
    run, not from GlitchSAT. On the published netlist, specification and code, SYNFI and GlitchSAT agree on
    80 of 309,580. The paper's run cannot be reproduced from the public files. One numerical fact: 31, the
    paper's number of effective sets, equals the number of effective sets that avoid the triplicated
    register-`$898` entries. That points to a different register cut in the paper's run, but it is not proof.
* E2 on this open netlist needs only 1 fault (cell `$abc$14726...$14921`, a NAND2 that combines `rnd_ctr_q[0]` and
  `rnd_ctr_q[1]`, replaced by NOR2). SYNFI's own run on the same file confirms it (1 effective of 28). The paper's
  "2" is for a different netlist.
* Runtimes: SYNFI here (pure-Python solver, one core) took 0.3 s to 729 s per run (E4: 270 s); GlitchSAT
  answered all 473 distinct E4 injections in 9.1 s and the minimum-fault question in 0.14-0.62 s (bundled solver). The paper
  ran on 16 cores with Minisat; none of these times is a like-for-like speed comparison.

**Fault-model differences (stated once, they matter for reading the numbers).**

| | SYNFI (and GlitchSAT's "gate replacement" model) | GlitchSAT "bit flip" model |
|---|---|---|
| cell fault | cell type replaced (e.g. NAND2 -> NOR2 or OR2); INV, MUX2 and OAI33 map to themselves, i.e. cannot be faulted | the cell output is inverted |
| stage input | `input_fault` inverts every bit of the port at once (one fault) | one bit per fault |
| side input | made arbitrary in the faulty copy (one fault) | one bit made arbitrary |
| observed output | `output_fault` inverts all bits (E1, E2, E4, E5); identity in E3 | one bit; not faulted where the spec maps it to identity |
| scope | one combinational evaluation of the region, side inputs free | same region (sections 3); whole netlist, N cycles (section 4) |

## 4. Beyond SYNFI

**Security margin and attack surface** (`surface_*` in `results/experiments.json`): every minimum attack, complete
(no cap hit) in every experiment.

| Exp | minimum | minimum attacks (gate repl. / bit flip) | hot spots |
|---|---|---|---|
| E1 | 1 | 12 / 25 | each attack is a different single location; 7 cells, 3 side inputs, the input and the output port |
| E2 | 1 | 1 / 2 | one NAND2 (`$14921`) in both models |
| E3 | 2 | 224 / 317 location pairs | NAND3 `$18250` driving `rnd_ctr_err_d` and the error register `u_rnd_ctr_err_reg` in 37 / 53 attacks each; an OAI21 of rail 0's FSM in 26 / 33 |
| E4 | 1 | 349 / 519 | 165 side inputs, 159 cells, 23 registers |
| E5 | 2 | 32 / 20 | side input from BUF `$8937` in 17 / 20 attacks; side input `nt_branch_addr_i` in 16 (gate-replacement model) |

**Ibex PC on the whole netlist** (`scripts/ibex_pc_native.py`, `results/ibex_pc_native.json`, CaDiCaL). The
side-input dominance in E5 means SYNFI's answer depends on its region boundary. Here the whole `ibex_if_stage`
netlist is unrolled for 3 cycles from reset, all PC sources pinned to 0, every other input free in every cycle,
goal `pc_if_o == 0x40400`: 0 and 1 flips impossible, **2 flips** suffice (e.g. the two PC register bits 10 and 18
in cycle 2), **267** different minimum attacks (complete), every one replayed on the reference simulator. The
netlist was synthesised with `PCIncrCheck = 0`, so its PC-consistency alarm `pc_mismatch_alert_o` is tied to 0:
the analysed Ibex has no PC countermeasure.

**AES FSM sparse encoding** (`scripts/fsm_state_experiment.py`). Bit flips of Nangate cell outputs and flop
outputs, inputs free every cycle, reset released, alert `alert_o` must stay 0.
* Single FSM (`results/fsm_state_single.json`; 2 cycles; all 42 ordered pairs of valid states): 9 pairs are legal
  moves. For the other 33, state-register flips alone need 3 in 32 pairs and 4 in one (never fewer than 3, the
  minimum Hamming distance, which agrees with the paper's Table 4: 3 faults). With any cell as a site: 1 fault in 4
  pairs (ROUND->CLEAR_S and FINISH->CLEAR_S via NAND2 `$14753`; FINISH->ROUND via NOR4 `$14778`; PRNG_RESEED->IDLE
  via the `prng_reseed_done_q` flop), 2 in 26, 3 in 3. The sparse code protects the state register, not the
  next-state logic.
* Three-rail FSM (`results/fsm_state_multirail_from_reset.json`; from reset; 6 cycles; the target must be reached
  by cycle 3 and the alert must stay 0 through cycle 5): IDLE->FINISH (skipping all rounds) needs **2** faults
  (1 is impossible within this bound). The attack found flips, in cycle 1, the OR gates that merge the three
  rails' outputs `rnd_ctr_rem_d[3]` and `num_rounds_d[3]` (OR3 cells): both counters shrink together, so the
  up/down counter check stays consistent. Other minimum attacks were not enumerated for this run. IDLE->PRNG_RESEED: none
  with up to 5 faults. A first run that started the rails directly in non-reset states with reset-value counters
  (an unreachable combination) is kept only in `runs/` and not used.
* Not reproduced: the paper's statement that aggressive Yosys FSM optimisation lowers the needed faults from 3 to 2
  (Sec. 4.1.3). That needs a fresh Yosys run on the RTL, and Yosys was not available. The shipped netlist keeps the
  sparse code (the state sits in `prim_sparse_fsm_flop`, reset value `001001` = IDLE).

**Did redundancy survive synthesis?** (`scripts/run_lints.py`, `results/lint.json`)
* `glitchsat_real/hier_lint.py` (cell ownership by hierarchy name): the three rails have 240 / 240 / 234 cells and 7
  flops each, rails 0 and 1 have identical cell-type histograms, and **0** nets go from a cell of one rail to a cell
  of another: no merging between rails. Shared by all rails: input ports `data_out_clear_i, key_clear_i, key_len_i,
  op_i, prng_reseed_ack_i, rst_ni`, 16 flops (the 12 round-counter flops `num_rounds`, `rnd_ctr`, `rnd_ctr_rem`,
  which the RTL does not triplicate, the error flop and three other control flops), and two gates computing
  `mux_sel_err` (OR4) and `sp_enc_err` (NAND3). The up and down counters are separate
  registers (4 + 4 flops, plus parity and error flops).
* `tools/surface/merge_lint.py` (unchanged) on the adapted netlist reports `merged` for 10 of 11 three-rail outputs.
  Its copy cones include all upstream logic, so the 467 "shared nets" are the intended shared inputs and counters,
  not synthesis merging; for this kind of design its verdict should not be read as "the rails were merged".

**Unbounded.** `tools/unbounded` proves goals of the form used by the GlitchSAT toy designs (`boot_word` with an
attacker input `sig`); it was not applied here. SYNFI-model results are exact for one evaluation of the region;
the sequential results are bounded (2, 3 or 6 cycles, as stated).

## 5. Files

```
glitchsat_real/
  nangate.py        Nangate45 -> GlitchSAT primitives; exhaustive cell check; flop/reset handling; fault sites
  refsim.py         reference simulator (SYNFI clause semantics) and primitive simulator (engine Netlist)
  region.py         SYNFI-compatible region extraction (reachability, exact simple paths where needed)
  synfi_model.py    SYNFI-compatible CNF model: check(), min_faults(), all_min_attacks(); models synfi / flip
  seq_model.py      whole-netlist N-cycle bit-flip model with witness replay on the reference simulator
  hier_lint.py      cell-ownership redundancy lint
  engine.py         imports of the read-only engine and ext/ modules
scripts/
  validate_adapter.py         adapter proof -> results/adapter_validation.json
  run_synfi_reference.py      SYNFI unmodified (with shims/) -> runs/synfi_ref/*.json
  run_all_synfi_reference.sh  SYNFI's examples/*/run.sh experiments
  dump_synfi_target.py        SYNFI's extracted target graphs (for tests/data/synfi_targets.json)
  compare_with_synfi.py       per-injection agreement on any SYNFI result file
  run_experiments.py          E1-E5 -> results/experiments.json (--backend py | dimacs:<binary>)
  synfi_targeted_check.py     GlitchSAT attacks re-run in SYNFI -> results/synfi_targeted_check.json
  synfi_e5_enumeration.py     SYNFI's own E5 2-fault list and SYNFI verdicts on chosen sets (resumable)
  e5_reconcile.py             E5 count reconciliation -> results/e5_reconciliation.json
  fsm_state_experiment.py     sparse-FSM questions -> results/fsm_state_*.json
  ibex_pc_native.py           whole-netlist Ibex PC -> results/ibex_pc_native.json
  run_lints.py                redundancy lints -> results/lint.json
  summarise.py                -> results/results.json
shims/                        sequential ray, Minisat22 stand-in, sympy stub (only for running SYNFI)
tests/                        pytest (35 tests, about 30 s)
reproduce.sh                  everything above in order (--quick skips the SYNFI runs)
```

Run: `./reproduce.sh` (about 40 min, mostly SYNFI with the Python solver) or `./reproduce.sh --quick`;
tests: `python3 -m pytest -q tests`. Requirements: Python 3.10+, numpy, networkx, pytest, git; optionally a
DIMACS solver (`SOLVER=/path/to/cadical`).

`results/results.json` collects everything above, with the citation of every published number.
