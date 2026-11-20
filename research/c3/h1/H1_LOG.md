# H1 hardening log
Work done on copies in /tmp/work_h1/{base,work}; applied to the tree only after the copy passed. Backups: research/c3/h1/backup/ (original of every changed file). Nothing run with make in the tree.
Labels: MEASURED = I ran it.

## Changes (tree files)
1. Engine (scripts/glitchsat.py and product/src/faultbound_wt/_engine.py, same patch): `NetlistError` (UnsupportedCell is a subclass).
   - multi-driver nets (two gates, gate + flop Q, two flops, gate driving an input-port bit) -> error naming the net and both cells;
   - duplicate JSON keys -> error (`object_pairs_hook`, also used by the product runner);
   - `init` containing x/other (on a flop) -> error; constant `x`/`z` in the logic cone/flop inputs -> error (no repo netlist contains x: scanned 60 JSON files);
   - undriven net, combinational loop (static iterative DFS), cells without Y (latch/enable/async flops/$dff) -> clean error instead of KeyError/RecursionError;
   - recursion removed: `get()` (evaluation) and `support()` (explain) are iterative (3000-gate NOT chain works, was ~493 max). z3 terms are built in the same order as before (`sexpr()` of the solver identical on V0 and V2 spike netlists, MEASURED).
2. glitchsat.py CLI: --k<0, --cycles<1, --goal-value/--key wider than the port, unknown ports, missing file -> `error:` exit 3; internal exceptions exit 4; synthesis failure exit 3 (was 1). Exit 0 still means "verdict printed" (attack or no attack, as before; read the text), 2 = solver unknown. Net names escaped before printing.
3. Product CLI: 0 no attack, 1 attack found (only ever a verdict), 2 solver unknown, 3 usage/input/netlist error (argparse usage errors now exit 3, they were 2 = collision with "unknown"), 4 internal error (any other exception incl. RecursionError). Printed net names escaped (newline, ANSI, bidi).
4. JUnit: characters outside the XML 1.0 Char production replaced by U+FFFD (whole document); report files written as UTF-8.
5. dashboard/build.py (escaping only): every string in the data is html.escape()d except the `faults` lists (the template already esc()s them); embedded JSON writes < > & U+2028/9 as \uXXXX so `</script>` cannot occur. Template untouched. Result: rendered text of the normal page is identical to before in headless Chromium at 390 and 1280 px (verdict `k<=2` is stored as `k&lt;=2` and displays as before); hostile fault name / verdict / explanation / sig / evidence: no script run, no injected img, no dialog; scrollWidth == viewport (390) in all cases; no console errors except one `ERR_FILE_NOT_FOUND` resource that the unmodified page also gives when opened from /tmp (not investigated). dashboard/index.html in the tree was NOT regenerated (it is a build output; run `make dashboard` after the next reproduce).
6. ci/check_reproduce.py: rejects duplicate / missing / unexpected rows and wrong row count; cross-checks every summary row against results/reproduce/<row>.json (verdict, min_faults, k, cycles) and against the input file (design_sha256_16 must match the actual file); `--rerun` re-runs the engine on all 36 rows (~23 s) and compares; `--write-manifest/--manifest` SHA-256 manifest; `-v` prints all SHA-256. Docstring states what it does not prove: a summary + expected file in the same tree can both be edited, so without --rerun it is an accident check, not tamper evidence; a manifest in the same tree is not authentic either (publish its hash out of band); --rerun shows this engine reproduces the table, not that the fault model is right. Exit codes 0 / 1 mismatch / 3 missing input.

## Tests added
tests/test_hardening.py (15), tests/test_check_reproduce.py (5), product/tests/test_hardening.py (11). Copy results: `pytest tests` 30 passed; product tests (PYTHONPATH=src) 21 passed. They fail on the old code for the cases above (RT's findings A1-A8, C1).

## Equivalence evidence (MEASURED, copy)
- `make reproduce` in /tmp/work_h1/work vs an unmodified copy (/tmp/work_h1/base): all 36 rows have identical verdict, min_faults, cycles, honest_key_boots; `check_reproduce.py` 36/36 and `--rerun` 36/36; `make replay` agrees_with_solver true (2/2).
- The reported witness (which fault set of minimal size) differs in 11 of 36 rows between the two runs. It is not unique: the UNMODIFIED code gives a different witness for V0 spike k=3 when only gc timing changes (gc.disable()), and per-process history already changes it. The solver constraint system (`sexpr`) is textually identical old vs new, so this is z3 internal state, not logic. Size of the minimal set is unchanged in every row.
- RT's cross-check (research/c3/rt/xcheck.py, paths pointed at the copy): seeds 1,2,3 = 40+150+150 netlists x (glitchsat, product) x (none, coi, full) = 2040 engine runs vs brute force: 0 disagreements.

## Not fixed / limits
- A9 (all non-clk inputs are free attacker inputs; report lists only `sig`): not changed (semantics decision).
- SARIF informationUri "about:working-title-tbd" not a valid http URI: not changed. SARIF/JSON keep raw net names (JSON-escaped, safe as data).
- Verilog path (`$readmem`/include in hostile source) untested. product/README, docs and the stale header comment of _engine.py ("original not modified") not edited.
- glitchsat.py still exits 0 for ATTACK_FOUND (existing contract; Makefile/reproduce do not use its exit code); product has the distinct codes.
- Dashboard: `/` to `&#x27;` etc. escaping applies to the whole data; the template's `esc()` leaves `"`/`'` unescaped but only in element-content positions (not examined exhaustively; headless test only).
- Tree files dashboard/index.html and results/ untouched.
