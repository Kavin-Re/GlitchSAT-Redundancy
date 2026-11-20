# RT red-team report

Scope: attack `scripts/glitchsat.py` (original engine), `product/src/faultbound_wt/*` (copy), report writers, and the reproducibility checks.
Nothing in the tree was edited. All runs were on copies under `/tmp/work_rt/` (z3 5.4.1, apt yosys 0.33, Python 3.13). Scripts kept in this folder:
`xcheck.py` (random cross-check), `edge.py` (edge cases, run with `python3 -I edge.py`), `pcli.py` (product CLI wrapper), `hostile.json`, `h.junit.xml`.
Labels: MEASURED = I ran it and saw the output quoted; INFERRED = read from code, not run.

## Summary table
| # | Finding | Severity | Label |
|---|---|---|---|
| A1 | Multi-driver net: silently order-dependent verdict (last cell in JSON wins), exit 0 | HIGH (silent wrong verdict, though only on malformed input) | MEASURED |
| A2 | Flop Q net also driven by a gate: gate silently ignored | MEDIUM | MEASURED |
| A3 | `init` = `x` treated as 0; constant `x` nets treated as 0; verdict NO_ATTACK where init=1 gives an attack | MEDIUM | MEASURED |
| A4 | `--goal-value` wider than the output port is silently truncated (0x101 on 2-bit port => "ATTACK_FOUND" for goal 0x1) in glitchsat.py; product validates | MEDIUM (glitchsat.py), none (product) | MEASURED |
| A5 | `--cycles 0` and negative `--k` give NO_ATTACK_UP_TO_BOUND (vacuous) in glitchsat.py; product validates (cycles>=1, non-negative) | LOW-MEDIUM | MEASURED |
| A6 | Product CLI: Python crash exits with code 1 == EXIT_ATTACK ("attack found") | MEDIUM (CI semantics) | MEASURED |
| A7 | Combinational loop and long combinational chains crash with RecursionError; max chain depth about 493 gates in both engines | LOW (loud) but real designs may exceed | MEASURED |
| A8 | Undriven net, latch, async/enable/negedge flops, `$dff`, other cells: loud failure (KeyError traceback or Exception), not a wrong verdict. Product turns only unsupported cell types into a clean `error:`; KeyErrors still tracebacks | LOW (loud) | MEASURED |
| A9 | glitchsat.py: an unsupported cell outside the goal cone is silently ignored (fine); inside the cone loud | informational | MEASURED |
| B1 | Random cross-check vs brute force: 0 disagreements | none | MEASURED |
| C1 | JUnit XML: net names with control chars (U+0001..U+001F) produce NOT well-formed XML | MEDIUM | MEASURED |
| C2 | Dashboard build: `json.dumps` inside `<script>`, no `</script>` escaping; `d.explanation` and `d.verdict` injected via `innerHTML` unescaped | MEDIUM (stored XSS if results JSON comes from a hostile netlist/PR) | MEASURED (string present in built HTML; not executed in a browser) |
| C3 | CLI prints raw net names (newlines, bidi U+202E, ANSI) to the terminal | LOW | MEASURED |
| D1 | `check_reproduce.py` is not tamper-evident: no hashes, never re-runs, duplicate rows let a later row override, hand-written summary passes | HIGH for any claim that "CI verifies reproduction" | MEASURED |

## A. Wrong-verdict hunt

Harness: `edge.py` builds 2-bit-input Yosys-JSON netlists by hand (key=3) and runs `scripts/glitchsat.py check ... --top t`, then the product CLI.

**A1 multi-driver (MEASURED).** Cells g1 (AND) and g2 (OR) both drive net 5, goal bit0=1, k=0, key 3.
`glitchsat.py check e_multidriver.json ...` -> `ATTACK_FOUND` (rc 0; OR wins, listed last). Same two cells in swapped JSON order -> `NO_ATTACK_UP_TO_BOUND` (rc 0; AND wins). Product CLI: identical (ATTACK_FOUND / NO_ATTACK_UP_TO_BOUND). Cause: `self.drivers[con['Y'][0]] = ...` overwrites. A duplicate JSON key for a cell name behaves the same (Python `json.load` keeps the last; MEASURED `dup_json_key`). Yosys itself would reject real multi-driver RTL in most flows, but hand-edited/merged netlists or `-nofsm` oddities are exactly what an adversary supplies.
Fix: in `Netlist.__init__`, if `Y` net already in `drivers` or in `qs` raise `InputError("net N has multiple drivers")`; use `object_pairs_hook` in `json.load` to reject duplicate keys.

**A2 flop Q also gate-driven (MEASURED).** `get()` checks `state` before `drivers`, so the gate is silently ignored. Same fix as A1.

**A3 unknown values (MEASURED).** Self-looping flop (D=Q) with `init="x"`; goal bit0=1; k=0: both engines `NO_ATTACK_UP_TO_BOUND`, but an init of 1 reaches the goal. Constant `x`/`z` bits map to 0 (`get`). Docs say "known power-up state" so this is a stated assumption, but the tool does not warn when an `x` init or `x` constant is seen. Fix: treat `x` init as an attacker-free or pessimistic bit, or at least raise a warning field in the report (`unknown_init_bits: n`) and refuse `x` constants in the goal cone.

**A4 goal/key width (MEASURED, glitchsat.py only).** 2-bit `boot_word`, `--goal-value 0x101`: ATTACK_FOUND at k=0 (compared on bit 0 only, `for i in range(len(w))`). `--goal-value 0x5` is likewise accepted. Product `_check_ports` rejects both. `--key 0x103` on a 2-bit input is reduced mod 4 by z3 silently. Fix: port the product's width checks to `run_check`.

**A5 degenerate bounds (MEASURED, glitchsat.py only).** `--cycles 0` -> `NO_ATTACK_UP_TO_BOUND` (empty goal disjunction); `--k -1` -> `NO_ATTACK_UP_TO_BOUND`. The bound block would say "<= -1 faults, 0 cycles". Product rejects (cycles must be >= 1; flips non-negative). Fix: validate in argparse.

**A6 exit code collision (MEASURED).** `python3 -I pcli.py analyze e_undriven.json ...` and the comb-loop file: traceback, rc=1. Product contract: 1 = attack found, 3 = input error. A CI job that treats rc 1 as "attack found" mislabels a crash (and one that treats rc 1 as "tool broke" mislabels an attack). Fix: wrap `main` in `except Exception` -> print `internal error`, return 3 (or a distinct 4); catch `KeyError`/`RecursionError` in `runner.analyze` and raise `InputError` with the net id.

**A7 recursion (MEASURED).** NOT-chain of 1500 gates, k=0: `RecursionError` in both engines. Bisection (script in this report's session): chain of 493 gates OK, deeper crashes (`sys.getrecursionlimit()` 1000, about 2 frames per level). Combinational loop: RecursionError (it should be a clear "combinational loop" error). Real datapaths with >490 logic levels will crash (loud, not silent). Fix: iterative topological evaluation with explicit loop detection, or `sys.setrecursionlimit` plus threading stack size as a stop-gap.

**A8 other cells (MEASURED).** `$_DLATCH_P_`: `KeyError: 'Y'` (glitchsat.py and product). `$_DFF_N_`, `$_DFFE_PP_`, `$_SDFF_PP0_`, `$_DFF_PN0_`, `$dff`: `KeyError: 'Y'` (they have no Y so the code never reaches the unsupported-type check). `$_TBUF_`, `$_BUF_`, `$mem_v2` in cone: `Exception: unsupported cell ...` (glitchsat.py), clean `error: unsupported netlist` (product, loaded eagerly, even outside the cone). Undriven net in cone: `KeyError: 99`. Zero flops, goal net being an input bit, constant goal bits, huge fanout (3000 consumers), k=0, cycles=1, duplicate net names: all gave a correct verdict (checked by hand against the netlist: see `edge.py` names `zero_flops_k0`, `goal_is_input_k0`, `goal_const_k0`, `fanout3000_k1`). No silent NO_ATTACK was produced by an unsupported construct. Caveat: the product's type check only fires for cells having a `Y` output (`for b,(cn,t,con) in self.drivers`), so a flop-like cell is a KeyError. Fix: check every cell's type up front against `SUPPORTED | {'$_DFF_P_'}`.

**A9 other inputs are attacker-controlled (INFERRED from code, `extra_input_free` ran without error).** Every input port except the literal name `clk` becomes a free constant; a reset/enable/test-mode pin can be chosen by the attacker. That can create attacks that a real system (reset held by the SoC) would not allow, or, with a differently named clock port, adds a harmless free bit. The report's "attacker input" line names only `sig`. Fix: list all free inputs in the report and let the config pin them.

## B. Cross-check against brute force (MEASURED)
`xcheck.py <seed> <count>`: random netlists (1 to 3 input bits, 0 to 3 flops with random init, 2 to 9 random AND/OR/XOR/NOT/MUX gates, 1 to 3 output bits incl. outputs wired to inputs/constants/flop Qs), random key and goal, random N in 1..4 and k in 0..2. The oracle enumerates every input (not equal to the key) and every fault set of size <= k over all gate outputs and flop Qs at all cycles, with an independent simulator. Compared: verdict and minimum fault count, for `glitchsat.py` and the product engine, each with `reduce` none/coi/full.
Seeds 1, 2, 3 -> 40 + 150 + 150 = 340 netlists, 2040 engine runs: **0 disagreements** (outcomes: 260 attack, 80 no-attack). Limits: tiny circuits; the oracle shares my reading of the fault semantics (a flop-Q flip changes only that cycle's read, not the stored state; faults not applied to input nets), so this validates the z3 encoding and the reductions, not the model; no multi-driver/latch cases in the generator; random gates never produce long-horizon behaviour (N<=4).

## C. Report generators (product/src/faultbound_wt/reports.py)
Input: `hostile.json` (net names contain `"`, `'`, `<script>`, `&amp;`, `]]>`, `--`, newline, U+202E, `../../etc/passwd`, U+0001, U+001F, U+2028, `</failure></testcase><x y="1">`, `${jndi:x}`, `%s`).
- **JSON**: valid (`json.load` OK). **SARIF**: valid JSON, 2.1.0; the name is carried verbatim in `logicalLocations[].name` and `message.text` (JSON-escaped, so safe as data; consumers that render SARIF messages as HTML/Markdown are the risk, INFERRED).
- **JUnit (C1)**: `xml.sax.saxutils.escape/quoteattr` handle `< > & "` and the fake closing tags correctly (injection did not work, MEASURED by parse), but U+0001/U+001F pass through, and `xml.etree.ElementTree.parse` fails: `not well-formed (invalid token): line 6, column 17` (`h.junit.xml` here). Many CI systems reject the whole file. A malicious net name can thus blank the CI result. Fix: strip/replace characters outside the XML 1.0 `Char` production (`re.sub('[^\\x09\\x0A\\x0D\\x20-\\uD7FF\\uE000-\\uFFFD\\U00010000-\\U0010FFFF]','\\ufffd',s)`) in `to_junit`; also in SARIF message text for tidiness.
- **Terminal (C3)**: the CLI prints net names raw (newline and U+202E visible in the run output; ANSI escapes INFERRED identical). Fix: print `repr`-style escaped names.
- **Dashboard (C2)**: `dashboard/build.py` does `tpl.replace("/*DATA*/", "const DATA = " + json.dumps(data) + ";")`. With `results/v1.json` containing a fault net `n</script><img src=x onerror=alert(1)>` and `explanation` `<img src=x onerror=alert(2)>`, the built `index.html` contains both strings raw (MEASURED by grep on a copy in `/tmp/work_rt/dash`); the first terminates the script block, the second goes through `innerHTML` at template line 159 (`${d.explanation}`; also `${d.verdict}` at line 148), while the fault name at line 157 is passed through `esc()`. I did not open it in a browser, so script execution is INFERRED. Fix: escape `<`, `>`, `&`, U+2028/9 in the embedded JSON (`.replace('<','\\u003c')`) and run `esc()` on explanation/verdict, or use `textContent`.
- Product `to_sarif` also uses a constant `informationUri="about:working-title-tbd"` (not a valid http URI; schema validators may complain; INFERRED).

## D. Reproducibility checks: what is and is not tamper-evident
Facts (MEASURED on the copy):
- `ci/check_reproduce.py` reads only `results/reproduce_summary.json` and compares `verdict`+`min_faults` per `design|netlist|k` to `ci/expected_reproduce.json`. It never runs the engine and never reads `results/reproduce/*.json` or the netlists.
- **D1a** Replacing `reference/spike_netlists/v2.json` with the V0 netlist and running `check_reproduce.py` alone: `36/36 rows match`. (`make ci` runs `reproduce` first so would catch it; `make check-reproduce` alone would not.)
- **D1b** Falsifying a row (v2 spike k=2 -> ATTACK_FOUND, min 2) and appending the genuine row after it: `36/36 rows match`, rc=0. The dict comprehension keeps the last duplicate; extra and duplicate rows are not rejected.
- **D1c** A summary file written by hand from `expected_reproduce.json` alone (no engine run): `36/36 rows match`.
- No manifest or hash covers `results/`: `grep` found no checksum file except the unrelated `real_designs/second/src/SHA256SUMS`. Per-run JSONs carry `design_sha256_16` = first 16 hex chars (64 bits) of the input file hash only, nothing verifies it, it excludes the synthesized netlist for `.v` inputs, the tool code, Yosys build and z3 version, and the `label: "MEASURED"` is a self-asserted string in an editable file.
- `expected_reproduce.json` is a plain file in the same tree; whoever edits results can edit expectations (the file's own note says "never to silence CI", which is policy, not control).
What IS evident: a full `make reproduce` + `check-reproduce` on a clean machine re-derives the verdicts from the netlists and RTL, so a reviewer who re-runs it and reads the log gets real evidence; the matrix (verdict + min) is compared. What is NOT tamper-evident: stored `results/*.json`, `results/logs/*`, dashboard numbers, the formal (SymbiYosys/PDR) logs referenced by `docs/ENGINE_STATUS.md` (not examined here), and the sha-16 provenance fields.
Proposed fixes: (1) make `check_reproduce.py` reject duplicate/unknown/missing keys and compare the row count exactly; (2) have `reproduce.py` write a `results/MANIFEST.sha256` (full SHA-256 of each input netlist/RTL, `glitchsat.py`, expected file, each result JSON, plus yosys/z3 versions) and have the check recompute those hashes; (3) in CI, run `reproduce` then `check` in the same job (already the `make ci` chain) and say plainly that a manifest in the same repo is integrity (accident) evidence, not authenticity: for authenticity publish the manifest hash out-of-band (signed tag or release notes); (4) pin full 64-hex hashes, not 16.

## Not done / limits
No Verilator/other-tool differential; no fuzzing of the Verilog path (`synth.sh` with hostile Verilog was not tried, Yosys reads `$readmem`/include paths from the source: INFERRED risk, untested); no time-varying input engine (E1) attacked; PDR/sby certificates not re-checked; dashboard XSS not executed in a browser; tens of random netlists per seed only up to N=4.
