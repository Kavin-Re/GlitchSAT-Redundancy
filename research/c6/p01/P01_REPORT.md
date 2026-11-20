# P01a report: why V2 = 2 flips on apt 0.33

Deliverables: `rtl/v2e.v`, `docs/report/WHY_TWO_FLIPS.md`, this folder. Work copy: /tmp/work_p01. All numbers MEASURED on 2026-11-20 unless marked.

## State sequence (MEASURED, `nl_info.py`, `nl_info.log`)
F0 (power-up, `init` attr, all three v2 netlists) -> CC (armed, one cycle) -> word (96 honest / 69 wrong key) -> hold.
The machine sits in F0 for cycle 0 and CC for cycle 1 only. The apt witness acts in cycle 0: it corrupts the LOAD of CC, it does not "jump from idle CC".

## Witness trace (MEASURED, `witness_apt_v2.txt`, `cycle0_delta.log`)
apt 0.33 netlist sha256 214a2987...4466, 85 gates. `new_n58_` = AND(c1.m, new_n54_), fan-out 3, moves next-state bits {1,4} (copy m1) in cycle 0; structurally also reaches bit 7 (m1). `new_n74_` = OR(new_n56_, new_n69_), fan-out 2, moves bits {3,6} (copy m0). 0x12 xor 0x48 = 0x5A = CC xor 96.
Brute force also finds the pair split over cycles (n74@0, n58@2): after n74@0 the state is 0x84, an unlisted value that holds forever, so the second flip can come later (3 attacking pairs at T=4).

## Surprises
1. The stored netlist `reference/spike_netlists/v2.json` has creator `Yosys 0.33 (git sha1 2584903a060)`: the SAME version as apt. "Stored vs apt" is not a version effect; it is source/flow (`src/boot.v`, MUX-per-bit mapping, 68 gates).
2. conda 0.38 is not immune for rtl/v2.v: flows abc_fast, opt_flow, opt_flow_keep_off give 2 (README says "conda 0.38 ... no 2-flip attack": true only for the plain flow).
3. The task's example control 0x5A touches three copies (5A^96=CC: bits 2,3,6,7), not two; it measures 3.
4. Unlisted states hold (`default: st <= st`), which lets a multi-flip attack be spread over cycles. Not fixed in v2e (only the constant was changed, as scoped).
5. `opt_flow` variants are "unsupported" for 6 control constants (Yosys leaves init x bits: `x111000x`); no verdict, not "no attack".
6. Hypothesis verdict: partly right. Encoding sets the floor (copies touched); synthesis decides whether the floor is reached. v2e does not help on the 2 flows that merge the three compares (1 flip).

## Numbers for NUMBERS.md (all MEASURED; stem rule, goal boot_word==0x96, T=6, k<=3, init known)
| id | value | command / file |
|---|---|---|
| P01.v2.apt.sweep | 2 1 1 2 2 2 2 2 (8 flows) | `faultbound-wt analyze rtl/v2.v --top v2 --max-flips 3 --cycles 6 --synth-sweep`; sweeps/sweep_apt_v2.json |
| P01.v2.conda.sweep | 3 1 1 2 3 2 3 2 | same with conda Yosys 0.38+92 first in PATH; sweeps/sweep_conda_v2.json |
| P01.v2e.apt.sweep | 3 1 1 3 3 3 3 3 | sweeps/sweep_apt_v2e.json |
| P01.v2e.conda.sweep | 3 1 1 3 3 3 3 3 | sweeps/sweep_conda_v2e.json |
| P01.v2e.gates | apt plain 89 gates, conda plain 81 gates, 8 flops | same files |
| P01.ctrl.3copies | 5A, 3C: 3 1 1 3 3 3 3 3 on both versions | sweeps/ |
| P01.ctrl.2copies | BB apt 2 1 1 3 2 u 2 u, conda 3 1 1 3 3 u 3 u; 4D apt 2 1 1 2 2 u 2 u, conda 3 1 1 2 3 u 3 u; 0F 2 1 1 2 2 u 2 u both | sweeps/ |
| P01.ctrl.1copy | 04: 1 1 1 1 1 u 1 u both; B2 apt 1 1 1 2 1 u 1 u, conda 2 1 1 2 2 u 2 u | sweeps/ |
| P01.bf | T=4, k<=2, z3-free: apt v2 3 pairs of 69,379 sets; apt v2e 0 of 75,467; conda v2 0 of 66,431; conda v2e 0 of 63,547; 5A 0 (73,921 each); 4D apt 3, conda 0; 04 1 single + 336/337 pairs | bf/*.json |
| P01.tb | 9 designs x 256 keys x 6 cycles: boots=1 errors=0 | tb_all.log, controls/tb_all.v |
| P01.xcheck | glitchsat.py k=3 T=6: apt v2 2, conda v2 3, apt v2e 3, conda v2e 3 | glitchsat_cross.txt |
| P01.stored.creator | Yosys 0.33 (git sha1 2584903a060), 68 gates | nl_info.log |

Netlist sha256 (synth.sh plain): `netlist_sha256.txt`; stored 289355dc483b9e6a74fea40b2d33a782350a2fd626468e97dd1c10b1cfe781ec. Per-row sweep hashes: `sweep_rows.csv` (144 rows).

## Not done
All 253 armed constants; netlist images (dashboard/real/render.py not run); recovery of the stored netlist's recipe; Docker 0.52; v2e under fanout rules, arbitrary init, or consumer masks. No file outside my scope was edited. Nothing refused or blocked.
