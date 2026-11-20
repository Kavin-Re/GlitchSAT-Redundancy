import json, re
exec(open('/home/user/project/research/c6/int/apply_edits.py').read().split('# ---------- README')[0])
E[:] = json.load(open(ROOT/'research/c6/int/edits_log.json'))
N='docs/NUMBERS.md'
t=(ROOT/N).read_text()
l78=[l for l in t.split('\n') if l.startswith('| `T.root.collected` | 136 |')][0]
rep(N, l78, l78.replace('| 136 |','| 150 |',1).replace('test_h3)','test_h3, test_h5, test_distance_sweep, test_p08; INT 2026-11-20)'))
l79=[l for l in t.split('\n') if l.startswith('| `T.root.passed` | 136 |')][0]
rep(N, l79, l79.replace('| 136 | pytest tests: passed, 0 failed (15.4 s on the RECON5 copy). 136 = 99','| 150 | pytest tests: passed, 0 failed (19.9 s on the INT fresh copy, 2026-11-20 05:13 UTC; 136 at RECON5, 15.4 s). 150 = 136 + 12 in `tests/test_distance_sweep.py` (P11) + 2 in `tests/test_p08.py` (P08); 136 = 99',1))
rep(N, ' "current": {\n  "T.root.passed": "136",', ' "current": {\n  "T.root.passed": "150",')
rep(N, '  "T.root.collected": "136"\n }', '  "T.root.collected": "150"\n }')
for s_old in ['"should": "136 root passed, 324 product passed (RECON5, 2026-11-20); 133 / 321 only as history (RECON4)"',
              '"should": "136 passed (root `pytest tests`, 2026-11-20, RECON5); or \'run `make test` and quote your own count\'"',
              '"should": "136 passed (10 only as history with a marker such as \'first writing\')"',
              '"should": "136 passed (root, RECON5; 99 + 34 in test_h3.py + 3 in test_h5.py); 99 only as history"',
              '"should": "136 passed (root, RECON5); 98 only as history"']:
    rep(N, s_old, s_old.replace('136 root passed', '150 root passed').replace('"136 passed', '"150 passed').replace('RECON5, 2026-11-20', 'INT, 2026-11-20').replace('2026-11-20, RECON5', '2026-11-20, INT').replace('(root, RECON5', '(root, INT'))
rep(N, '   "id": "T.root.collected",\n   "value": "136",', '   "id": "T.root.collected",\n   "value": "150",')
t=(ROOT/N).read_text()
m=re.search(r'   "id": "T.root.passed",\n   "value": "136",\n   "source": "tests/",\n   "status": "MEASURED",\n   "date": "2026-11-20 RECON5"', t)
rep(N, m.group(0), m.group(0).replace('"136"','"150"').replace('2026-11-20 RECON5','2026-11-20 INT'))
rep(N, ' "rules": [\n', ''' "rules": [
  {
   "id": "T.root.136",
   "hist": true,
   "re": "\\\\b136\\\\s+(?:passed|root|main tests|tests?\\\\b)|\\\\*\\\\*136 passed|now 136\\\\b",
   "should": "150 root passed (INT, 2026-11-20; 136 + 12 test_distance_sweep + 2 test_p08); 136 only as history (RECON5)",
   "label": "stale root test count 136 (before P08/P11 tests)"
  },
  {
   "id": "YOSYS.version.cause",
   "hist": true,
   "re": "(?i)verdict depends on the Yosys version|Yosys version dependence|depends on the Yosys version",
   "should": "not a version effect: encoding sets the floor (0xCC touches 2 of 3 copies), the flow decides whether it is reached (docs/report/WHY_TWO_FLIPS.md, P01a)",
   "label": "misattribution corrected 2026-11-20 (fresh-eyes review, P01a)"
  },
''')
SEC = '''## 13 Encoding root cause, coding view, P08 (agent INT, 2026-11-20)
Toy designs, modelled single-cycle bit flips, nothing physical, nothing established as new. Flow order of `--synth-sweep`: plain, plain_opt_merge, flatten_before_abc, abc_fast, abc_no_mux, opt_flow, plain_keep_off, opt_flow_keep_off.
| id | value | meaning | source | how measured | status | date |
|---|---|---|---|---|---|---|
| `P01.v2.apt.sweep` | 2 1 1 2 2 2 2 2 (8 flows) | V2 min flips per flow, apt Yosys 0.33, goal boot_word==0x96, stem rule, T=6, k<=3, known init | research/c6/p01/P01_REPORT.md; sweeps/sweep_apt_v2.json | `faultbound-wt analyze rtl/v2.v --top v2 --max-flips 3 --cycles 6 --synth-sweep` | MEASURED (P01a; re-run by the lead 2026-11-20 05:06 UTC, identical) | 2026-11-20 |
| `P01.v2e.apt.sweep` | 3 1 1 3 3 3 3 3 | `rtl/v2e.v` (armed 0xA5, touches 3 copies), same command; conda 0.38 identical | P01_REPORT.md; sweeps/sweep_apt_v2e.json, sweep_conda_v2e.json | same with `rtl/v2e.v --top v2e` | MEASURED (P01a; lead re-run identical) | 2026-11-20 |
| `P01.v2.conda.sweep` | 3 1 1 2 3 2 3 2 | V2 with conda Yosys 0.38+92: 3 only on plain (and abc_no_mux, plain_keep_off), 2 on abc_fast, opt_flow, opt_flow_keep_off | P01_REPORT.md; sweeps/sweep_conda_v2.json | conda yosys first in PATH | MEASURED (P01a) | 2026-11-20 |
| `P01.stored.creator` | stored V2 netlist creator `Yosys 0.33 (git sha1 2584903a060)`, 68 gates | stored vs apt is a flow/source difference, not a version difference | P01_REPORT.md; nl_info.log | `nl_info.py` | MEASURED (P01a) | 2026-11-20 |
| `P01.cause` | 0xCC xor 0x96 = 0x5A = bits {1,3,4,6}, copies m1 and m0 only; apt witness `new_n58_` (bits 1,4) and `new_n74_` (bits 3,6) at cycle 0 | encoding sets the floor; the flow decides whether it is reached; the 1s are copy-merging flows | WHY_TWO_FLIPS.md; witness_apt_v2.txt | arithmetic + solver witness | MEASURED (P01a) | 2026-11-20 |
| `P01.controls` | 3 copies (5A, 3C): 3 1 1 3 3 3 3 3 on both versions; 2 copies (BB, 4D, 0F): 2 or 3; 1 copy (04): 1 everywhere, B2 1 or 2; brute force T=4 k<=2: apt v2 3 pairs, apt v2e 0 of 75,467, conda v2 0, conda v2e 0; 9 designs boot only for key 0xC3 | controls for the encoding hypothesis | P01_REPORT.md; bf/*.json; tb_all.log | anchor_sim.py; iverilog 256 keys | MEASURED (P01a) | 2026-11-20 |
| `P11.codebooks` | 19 codebooks measured (+2 negative controls rejected before any solver run) | code distance as fault budget | research/c6/p11/P11_REPORT.md; results/comms/distance_sweep.csv | `python3 scripts/comms/distance_sweep.py --out results/comms/distance_sweep.csv --cli faultbound-wt` | MEASURED (P11a) | 2026-11-20 |
| `P11.flops` | flops-only min = nearest non-accept distance d_min in 15 of 15 codebooks with d_min <= 6; 4 of 4 with d_min > 6 no attack up to 6 (bounded) | prediction (a) held | same | same | MEASURED (P11a) | 2026-11-20 |
| `P11.allnets` | all nets <= flops-only in 19 of 19 (both flows); no-ABC structural netlist equals the copy rule 19 of 19 | prediction (b) held | same | same | MEASURED (P11a) | 2026-11-20 |
| `P11.failed` | FAILED: flops-only = d(I,W) (2 B-variant codebooks: 3 and 6 vs 8); 3 of 16 three-copy codebooks at 2 on the apt plain flow; complement pairs give 3, not 2; word order: F0 then CC 2, CC then F0 3 (mechanism not dissected) | failed predictions, kept | same | same | MEASURED (P11a) | 2026-11-20 |
| `P13.rm13` | RM(1,3) [8,4,4], d=4, weight enumerator 1 + 14z^4 + z^8; F0, CC, 96, 69, C3 all members (LSB- and MSB-first) | coding view | docs/comms/test_rm13.py; research/c6/p13/test_output.txt | `pytest -q docs/comms/test_rm13.py`: 16 passed (INT fresh copy, 2026-11-20) | FACT (test); lead re-ran membership | 2026-11-20 |
| `P13.hamming` | flops-only min 4 on V1 spike, V2 spike, V1 apt, V2 apt; all nets 1 / 3 / 1 / 2 | distance = flops-only budget; decoder = ceiling | research/c6/p13/hamming_runs.txt | `python3 docs/dossier/test_hamming.py` (z3, T=6) | MEASURED (P13a) | 2026-11-20 |
| `P08.glitchsat` | `scripts/glitchsat.py` sha256 1ad037ef07e23c2aabcea75b87a99616591957bd61ed8e0b80abae6b737a9f3c (old 78ecea08...); synth.sh run via `sh`; 'add another independent copy' advice removed; ENGINE_MANIFEST updated by the lead | engine change | research/c6/p08/P08_REPORT.md; tests/test_p08.py (2 tests) | sha256sum | MEASURED (P08; lead) | 2026-11-20 |
| `INT.tests` | root `pytest tests` 150 passed (19.9 s; incl. test_distance_sweep 12, test_p08 2, test_h5 3); product `pytest product/tests` 324 passed (82.4 s); `docs/comms/test_rm13.py` 16 passed (not under tests/, not counted in 150) | current test counts | /tmp/work_int/m1 (fresh tar copy, venv with ci/requirements-ci.txt and ./product[test]) | `pytest -q tests`; `pytest -q product/tests` | MEASURED (INT, 2026-11-20 05:13 UTC) | 2026-11-20 |
| `INT.repro` | `ci/check_reproduce.py` 36/36 rows match; `--rerun` 36/36 (engine re-run), 0 FAILED, no manifest warning | reproduce gate after P08 | same copy | `python3 ci/check_reproduce.py [--rerun]` | MEASURED (INT) | 2026-11-20 |

## Machine-readable block'''
rep(N, '## Machine-readable block', SEC)
json.dump(E, open(ROOT/'research/c6/int/edits_log.json','w'), indent=1); print(len(E))
