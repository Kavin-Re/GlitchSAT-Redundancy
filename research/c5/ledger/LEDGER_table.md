Cell = minimum number of modelled events (single-cycle bit flips / rail events), T=6 cycles, at most 3 events, goal boot_word==0x96 unless stated; `>3` = no attack found up to 3 (a bound, not "secure"). Label: M = MEASURED, S = SIMULATED (modelled rail/dip/placement event, not physical), U = UNMEASURED (n/a).

**1 Synthesis flow (stem flip, full word)**

| design | stored spike | apt0.33 plain | apt0.33 opt | apt plain +opt_merge | conda0.38 plain | conda0.38 opt |
|---|---|---|---|---|---|---|
| V0 | 1 (M) | 1 (M) | 1 (M) | 1 (M) | 1 (M) | 1 (M) |
| V1 | 1 (M) | 1 (M) | 1 (M) | 1 (M) | 1 (M) | 1 (M) |
| V2 | 3 (M) | 2 (M) | 2 (M) | 1 (M) | 3 (M) | 2 (M) |
| V5 | n/a (U) | 3 (M) | 3 (M) | 1 (M) | 3 (M) | 3 (M) |

**2 Consumer bits (stem)**

| design | full word | 4-bit 0x0F | accept flag boot_ok |
|---|---|---|---|
| V0 | 1 (M) | 1 (M) | 1 (M) |
| V1 | 1 (M) | 1 (M) | 1 (M) |
| V2 | 3 (M) | 2 (M) | 1 (M) |
| V5 | 3 (M) | 2 (M) | 1 (M) |

**3 Counting rule**

| design | stem | fanout branch |
|---|---|---|
| V0 | 1 (M) | 1 (M) |
| V1 | 1 (M) | 2 (M) |
| V2 | 3 (M) | 3 (M) |
| V5 | 3 (M) | 3 (M) |

**4 Fault model (word goal)**

| design | stem flip | rail 1->0 | rail 0->1 CONTROL | either polarity | selective 1->0 subset | selective 0->1 subset |
|---|---|---|---|---|---|---|
| V0 | 1 (M) | 1 (S) | 1 (S) | 1 (S) | 1 (S) | 1 (S) |
| V1 | 1 (M) | >3 (S) | 1 (S) | 1 (S) | 1 (S) | 1 (S) |
| V2 | 3 (M) | >3 (S) | 1 (S) | 1 (S) | 1 (S) | 1 (S) |
| V5 | 3 (M) | >3 (S) | 1 (S) | 1 (S) | 1 (S) | 1 (S) |

**4b boot_ok goal**

| design | rail 1->0 | rail 0->1 CONTROL |
|---|---|---|
| V0 | 1 (S) | 1 (S) |
| V1 | >3 (S) | 1 (S) |
| V2 | >3 (S) | 1 (S) |
| V5 | >3 (S) | 1 (S) |

**5 Placement (V2, per-rail selective)**

| design | base | spread v8 | rr (diff. rails) | any: 0->1 event |
|---|---|---|---|---|
| V0 | n/a (U) | n/a (U) | n/a (U) | n/a (U) |
| V1 | 1 (S) | n/a (U) | n/a (U) | n/a (U) |
| V2 | 1 (S) | 2 (S) | 3 (S) | n/a (U) |
| V5 | n/a (U) | n/a (U) | n/a (U) | n/a (U) |
