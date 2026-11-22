# H5 report (MEASURED) - Yosys >= 0.38 `$scopeinfo` cells

Change: loader skips cells of type `$scopeinfo` (no gate, no net) when none of its `port_directions` is non-input (Yosys emits empty ports/connections). A `$scopeinfo` with any output/inout port falls through to the normal rejection. All other unknown types still fail loudly.
Files: product/src/faultbound_wt/_engine.py, scripts/glitchsat.py (same rejection existed; same patch), product/tests/test_h5.py, tests/test_h5.py, product/QUICKSTART.md (1 bullet). Originals in research/c5/h5/backup/. synth.sh untouched, flow untouched.

## Verification (tree)
- ci/check_reproduce.py --rerun: 36/36 rows match, 0 failed. It prints ONE WARNING: glitchsat.py differs from ENGINE_MANIFEST.
  NEW sha256 scripts/glitchsat.py = 78ecea0813051f2a6e962cf6c42983afd34754245b99651f026bef6df45cfe40 (old 0747950d...77cd). synth.sh unchanged (99686d4e...6af27d82a6ae2aa4f14af6fc as before). check_reproduce.py NOT edited: integration step must update the manifest (or revert the glitchsat.py change, which is not needed for the Docker path).
- root tests: 136 pass in the work copy (incl. 3 new); tree: 134 passed, 2 skipped (conda Yosys on PATH). product tests (pip install ./product[test]): 324 passed in copy; 314 passed, 10 skipped in tree run.
- New tests: scopeinfo-bearing netlist gives identical stats/drivers (product) and same verdict NO_ATTACK_UP_TO_BOUND (glitchsat); unknown type `$mystery` errors; `$scopeinfo` with an output port still errors.
- Note (pre-existing, not changed): glitchsat.py accepts an unknown cell type that has a `Y` output at load time (product engine rejects it).

## Docker (image faultbound-wt:h5, sandbox-CA Dockerfile, build needed `--network host` this time: default bridge missing)
Yosys in image: 0.52. Before fix (faultbound-wt:dev): error "cell c1 has type $scopeinfo".
- analyze v2.v --top v2 --max-flips 2 --cycles 6: NO_ATTACK_UP_TO_BOUND, 83 gates, 8 flops (build difference vs 85 gates).
- analyze v1.v --top v1 --max-flips 1: ATTACK_FOUND (min attack ok@1), 70 gates, 8 flops.

## Yosys versions now working (same command, v2 / v1)
- apt 0.33 (sandbox): v2 ATTACK_FOUND <=2 flips, 85 gates; (v1 same as other versions in gates=70 expected, not rerun)
- conda 0.38+92 (/tmp/mm_root/envs/eda): v2 NO_ATTACK_UP_TO_BOUND, 83 gates; v1 ATTACK_FOUND, 70 gates
- Docker 0.52: v2 NO_ATTACK_UP_TO_BOUND, 83 gates; v1 ATTACK_FOUND, 70 gates
FINDING: the v2 verdict at 2 flips DIFFERS between Yosys 0.33 (attack, 85 gates) and 0.38/0.52 (no attack, 83 gates). Verdicts are per-synthesised-netlist; this is a toolchain-dependent result and should be stated in docs (not investigated further here).
