# M1b: recheck of the M1 consumer-mask matrix under a trustworthy engine
Step M1b, 2026-11-19. All numbers MEASURED with the commands below (work dir /tmp/work_m1b; nothing in the tree edited, no make, no build dirs created in product/). Faults are modelled single-cycle bit flips, T=6, k<=3, toy designs; nothing about hardware.

## Result in one line
The x-init handling in M1's gs_mask.py affected **0 of 1785 CSV cells**: none of the 7 netlists contains an x init bit (nor conflicting init on aliased bits). Recomputing all 255 masks x 7 designs with two independent trustworthy engines gives **0 changed cells**; the corrected CSV `m1b_all_masks.csv` is byte-identical to `m1_all_masks.csv`. No published claim changes.

## 1. Which cells could be affected (scan)
- Mechanism (VER_REPORT 3.3): gs_mask.py (old Netlist parse) skips nothing for 'x' in init strings: it maps x to 0 and a later alias of the same flop net can overwrite the real init. `scripts/glitchsat.py` raises NetlistError on an x init bit of a flop net.
- Scan: `python3 -I scanx.py nl` (any init char not in 01, all nets, all 7 netlists) -> nothing printed. `python3 -I scanalias.py` (same bit given different init by two aliases) -> 0 conflicts in all 7. Init bits per netlist: v0 2, all others 8. So the x-init path is never exercised for the M1 designs; only netlists from the opt synthesis flow (held-out rc*_opt in VER) have 'xx1001'-style init.
- Demonstration that the failure mode is real elsewhere (`xtest.json`, v2 spike with the last init bit of `st` changed to x): old gs_mask loads it silently (init False); product engine raises `NetlistError ... init value '1111000x' contains 'x' (unknown)`.
- M1's own raw cells: 1785 rows, all status MEASURED, 0 unknown.

## 2. Recompute
Netlists: the exact files M1 used (spike v0/v1/v2 = reference/spike_netlists, md5 equal; apt-0.33 v1/v2 and v2m/v2s from /tmp/work_m1). Note: /tmp/work_m1/nl/v?_apt033.json are NOT the same files as research/c2/b1_faultmodels/netlists/v?_apt033.json (md5 differ); M1's own copies were used so cells compare 1:1.
- Engine A (product): `python3 -m venv venv; venv/bin/pip install ./pcopy` (pcopy = copy of product/ under /tmp), `faultbound_wt._engine.Netlist/solve(goal_mask=m)`, same loop as M1 mat.py (k=0..3, T=6, 90 s timeout): `sh runall.sh mat2.py` -> out/prod_*.jsonl (255 each, 0 unknown).
- Engine B (patched scripts/glitchsat.py): `gs_main.py` = copy of scripts/glitchsat.py + the 2-line mask patch (`diff` shows only goal_mask arg and the `if (goal_mask>>i)&1` filter); it rejects x init loudly. `sh runmain.sh mat2.py` -> out/main_*.jsonl.
- Diff old vs new per cell: `python3 diff.py prod` and `python3 diff.py main`: every design 255 cells, **changed 0** (both engines). Total 1785/1785 cells equal.
- CLI spot check (`faultbound-wt analyze nl/v2_spike.json --top v2 --consumer-bits 0xFF/0x0F --max-flips 2/3 --cycles 6`): full word NO_ATTACK at k=2, ATTACK_FOUND 3 flips at k=3 (word[0] + the same internal node of copies c1,c2 @1); mask 0x0F = 2 flips (CSV 2). Consistent.
- Changed-cell list: empty. (Reason column: n/a.)

## 3. M1 exact rule re-check (pred.py, `python3 mkcsv.py`)
- Spike V2: rule matches the solver on 255/255 masks (0 mismatches). Unchanged.
- Apt-0.33 V2: 68 mismatches. Unchanged. (Other designs, not claimed by the rule: V0 167, V1 spike 140, V2m 46, V2s 140, V1 apt 140.)

## 4. B2 headline re-check (`python3 b2chk.py prod|main`, 30 cells each: v0/v1/v2 x 5 netlist flows x goal boot_word/boot_ok, known init, input nets not sites, const input)
- V2 boot_word: spike 3, conda038_plain 3, apt033_plain 2, apt033_opt 2, conda038_opt 2. V2 boot_ok: 1 in all five. Both engines identical; all 30 cells equal B2's matrix.jsonl (0 differences). The B2 netlists (/tmp/work_b2/nl) also have no x init.
- README table claims "full word 3 spike / 2 apt; boot_ok 1": confirmed.

## 5. Published claims
| claim | old | recomputed | change |
|---|---|---|---|
| V2 full word spike / apt | 3 / 2 | 3 / 2 | none |
| V2 spike split over 228 non-colliding masks (min 1 / 2 / 3) | 88 / 96 / 44 (27 collide) | 88 / 96 / 44 (27 collide) | none |
| V2 spike 4-bit consumers | 1 to 2 typically, 4 of 68 need 3 | pop 4: 28 / 36 / 4 | none |
| V2 apt non-colliding | 1:112 2:116 | 112 / 116 | none |
| V2m full word, masks >=6 bits | 2, all 2 | 2 | none |
| V2s | 1 for every non-colliding mask | same | none |
| boot_ok | 1 | 1 | none |

## 6. Limits
- Only the 7 netlists in M1 were checked; claim "no x init" is for them, scanned by script. Other corpus netlists (opt flow, VER held-out) may be affected; not rechecked here.
- Two engines share the same solver model lineage (glitchsat); this recheck tests the init handling and the mask patch, not the model itself. Brute-force validation of M1 (T=4,k<=2) was not repeated.
- Wall times: product matrix 7 designs about 7.5 min, patched main similar, on 4 cores.

## Files
`M1B_REPORT.md`, `m1b_all_masks.csv`, `mat2.py`, `gs_main.py`, `b2chk.py`, `diff.py`, `mkcsv.py`, `scanx.py`, `scanalias.py`, `runall.sh`, `runmain.sh`, `raw/` (prod_*/main_* jsonl, b2_prod.json, b2_main.json).
