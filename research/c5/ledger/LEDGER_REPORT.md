# LEDGER_REPORT

Toy designs, modelled single-cycle bit flips and modelled rail events, T=6, at most 3 events, z3. No hardware or physical-glitch claim; `>3` = no attack found up to 3 events (bound, not "secure"). Nothing established as new. Work dirs `/tmp/work_ledger/*` (tree copy, no make run, product used via PYTHONPATH, nothing built in the tree). Raw data and scripts copied to `research/c5/ledger/data/`.

## 1. The ledger
`LEDGER.md` (table + PNG), `ledger.csv` (one row per cell with label and source), `ledger.png`, generator `build_ledger.py`. Rows V0, V1, V2, V5; five stages (synthesis flow, consumer bits, counting rule, fault model, placement). Cells copied from E2, B2, B3, B1, M1, L2, LAYOUT reports, or measured now (labelled in the CSV source column). Measured now (MEASURED): V5 under apt opt, apt plain + opt_merge, conda plain/opt (3, 3, 1, 3, 3 via product CLI); V5 4-bit mask 2, boot_ok 1; branch counting for V2 spike (3) and V5 (3) with B1's faultpack, which B1 left "not finished" at 60 s (finished here in 11 s, 100 s limit); all 0->1 cells. UNMEASURED: V5 spike netlist (does not exist), placement for V0/V5, spread layouts for V1, and every 0->1 event on layout-derived domains.
Reading: V2's 3 survives in one corner (spike or conda plain flow, full word, stem counting). It drops to 2 (apt, 4-bit mask), to 1 after opt_merge-after-flatten (V2 and V5), to 1 for boot_ok, to 1 under any selective or 0->1 event. V5 behaves like V2 everywhere it was measured (no better).

## 2. 0->1 polarity control (b3pol.py = copy of B3 engine, new events gates1/d1/gatesx; `data/pol.jsonl`, 196 cells, 0 unknown)
Controls reproduce B3 (`data/ctrl.jsonl`: stem 1/1/3/2/3, rail_any V0 1 else >3, dip_subset 1). New events: `rise_*` = all gate outputs at 0 in a domain go to 1 for one cycle (domains all/half/unions/cone, flop D capture forced to 1 in the domain), `rise_subset`, `both_any` (one polarity per event, any domain), `inv_*` (domain inverted).
Word goal, T=6, k<=3: rise_unions and rise_half = 1 for V0, V1, V2, V5 (spike and apt netlists alike); witness for V2/V5: the union c0+c1+c2 (the three compare copies) rises at cycle 1, i.e. all three match nets go 0->1 together. Same domain with 1->0 (rail_unions/rail_any): >3. rise_all (whole design) and rise_cone: >3 for word, but 1 for boot_ok. boot_ok goal: every rise family = 1 on all designs (1->0: >3 on V1, V2, V5).
Plain answer: yes. V2 and V5 "survive" the rail event only because B3's rail model is 1->0-only. With the same hierarchy-derived domain and the opposite polarity one event suffices (V1 too). V1 also survives 1->0 (>3), so that survival never depended on triplication. Caveat: the c0+c1+c2 domain is netlist hierarchy, not a physical rail; whether such a domain exists depends on placement (base layout: copies within 3 um; L2 `rr`: different rails). Not run on layout domains.

## 3. T3 regression, `--amk counter` vs `legacy` (`data/reg.py`, `reg.json`)
17 cells: 10 on scripts/glitchsat.py CLI (V2 spike k=2 none, k=3 min 3, boot_ok k=1, V1 spike k=1, V0 spike k=1, V2 apt k=1 none, k=2 min 2, E2 conda plain k=2 none / k=3 min 3, E2 apt opt_merge k=1) and 7 on the product CLI with env FAULTBOUND_AMK (masks 0x02/0x0E/0x3E = 1/2/3; B2 input-sites=all 1, init free_nongoal 1, init arbitrary 0), because the scripts CLI has no mask/scope options. Result: 16 of 16 real cells agree on verdict and min (counter 0.6-2.2 s, legacy 1-22 s). The 17th (`--count-rule branch` on product) errors identically in both modes (not implemented, exit 3): not a test, not counted. Limit: the tested cells are the same family T3 already cross-checked; it is agreement on headline cells, not a proof.

## 4. E2 predictor confusion matrix (frozen predictor, sha a9e43ef9... verified; `data/samp.py`, `e2_sample.json`)
71 netlists: 62 unique-sha E2 netlists (stratified, seed fixed: V2 min3/2/1 x12, V1 min2 x10, V1 min1 x8, V0 x8; E2's stored re-synthesised netlists, apt and conda builds) + the 9 baselines. Rows solver (E2 matrix.csv), columns predictor:
| solver \ pred | 1 | 2 | 3 |
|---|---|---|---|
| 1 | 34 | 0 | 0 |
| 2 | 0 | 23 | 0 |
| 3 | 0 | 0 | 14 |
Exact 71/71 = 100%, same as TEST (928/928 pooled, E2 407/407). Weakness: same netlist family as TEST (overlap, not independent). Fresh out-of-family check, I synthesised six other RTLs (apt 0.33 plain) and compared to the product-CLI solver minimum: v2s 1/1, v4 1/1, v4b 1/1, v6 1/1 match; **v2m predicted 4, solver 2; v5 predicted 4, solver 3**. So 4/6 exact; the two misses are the designs with voter structure, both overestimates (est > solver, so TEST's C1 holds but exactness does not). Only 6 cells; the 100% rate should be quoted as "on the E2 family", not generally.

## 5. Triplication under the selective model
Smallest selective 1->0 domain (B3 minsubset, MEASURED/SIMULATED): V1 2 gates, V2 3, V5 3 (one per compare copy). Triplication buys one extra gate. Under every other row of the ledger V1 and V2 are tied: rail 1->0 >3 both, 0->1 rise 1 both, boot_ok 1 both, selective subset 1 event both, after opt_merge 1 both. Triplication separates them only under independent stem flips with kept hierarchy (V1 1 vs V2 3 on spike/conda, 2 on apt) and fanout-branch counting (2 vs 3). LAYOUT adds: V1 has a single-cell sufficient set in the layout, V2 needs 3 cells within 2.95 um. So the claim "triplication helps" holds for independent flips (and only while the synthesis flow keeps the copies), and not for rail events of either polarity: there, survival is a property of polarity/selectivity.

## Not done
Layout-domain 0->1 runs; V5 placement; V5 spike netlist; brute-force validation of the new 0->1 events (only B3 controls reproduced, no independent checker); predictor sample is single-seed; fresh predictor set is 6 cells.
