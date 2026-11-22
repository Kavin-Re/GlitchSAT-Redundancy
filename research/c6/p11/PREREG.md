# P11 pre-registration: code distance as fault budget, decoder as ceiling

Written 2026-11-20T05:02Z (UTC), BEFORE any sweep run (no solver has been run on any generated codebook; only the project files were read). Nothing here is a result. Faults are modelled single-cycle bit flips on a toy design; nothing physical; nothing established as new.

## Prior knowledge I already had when writing this (so these are not blind predictions)
- `research/c3/m1/M1_REPORT.md`: on the stored spike netlist of `rtl/v2.v` the full-word minimum is 3 and the mask rule is exact; on the apt-0.33 plain re-synthesis the full word is 2 (ABC shares nodes), so the rule over-predicts there.
- The spike netlist flow is not reproducible in this repo (`spike_curve_UNREPRODUCED_by_this_repo.json`), so I cannot build a "stored-style" netlist for new constants. I will use (1) the project flow `scripts/synth.sh plain` (apt yosys 0.33) as the headline, and (2) a no-ABC structural flow (proc; techmap; flatten) as the nearest stand-in for "stored-style".

## Setup (fixed before running)
- Generator: `rtl/v2.v` with constants substituted. Words: idle I (flop init), optional step word C (the template's second pre-boot state; omitted when no word at the needed distance exists), accept W, fail B. Wrong-key runs visit I, (C), B.
- Definitions: d(I,W) = Hamming distance idle to accept. d_min = min of d(X,W) over the non-accept words X in {I, C, B} that a wrong-key run visits ("d_to_accept" in the CSV is d(I,W); d_min is a separate column).
- Rule prediction (M1 rule, full-word consumer): rule = min( d_min , min over subsets S of comparator copies of |S| + number of bits of (B xor W) not owned by S ).
- Measurement: product CLI, stem rule, goal boot_word == W, attacker input sig != 0xC3, known init, T = 6, k_max = min(d(I,W), 6). Site sets: flops only (`[faults] kinds = ["flop"]` in the threat-model TOML) and all nets (default gate + flop). Timeout per run; a timeout or "no attack up to k_max" is written as unknown / ">k_max", never "safe".
- Codebook list (fixed now, 21 entries): F0/96 (stored), CC/96, 69/96, 2B/95, C3/3C, A5/5A, A5/96, A5/A6, 00/1F with C=F8 B=E7, families d=1..7 (W=96, I = W xor low d bits, C = W xor high d bits, B=69), B-variants (B xor W inside one copy: B=DF; inside two copies: B=4D; I=69), one-copy grouping control (all 8 bits owned by m0), and two generator negative controls (B == W; I == W) that the functional check must REJECT before any solver run.

## Predictions
- (a) Flops-only minimum == d_min for every codebook where d_min <= 6. As literally posed at integration, "flops-only == d(I,W)": I predict this literal form holds whenever d(I,W) = d_min and FAILS (measured lower) for the B-variants (d(I,W)=8, d(B,W)=3 or 6), because the fail word is also a word the attacker can start from. Where d_min > 6 (69/96, C3/3C, A5/5A) I predict "no attack up to 6" (reported ">6", unknown beyond).
- (b) All-nets minimum <= flops-only minimum for every codebook (site superset). On the no-ABC structural netlist it equals the rule. On the apt-0.33 plain netlist I predict <= rule, with equality NOT guaranteed (M1 saw 2 where the rule says 3).
- (c) The all-nets curve saturates: on the structural netlist at 3 for the 3-copy grouping when B xor W touches all three copies; at 1 when it touches one copy or with one-copy grouping; at 2 for two copies. On apt-0.33 plain I predict the plateau is 2 or 3 (2 more likely for complement pairs, from M1).
- (d) Complementary pairs (69/96, C3/3C, A5/5A; d=8) show the largest gap d - all-nets minimum (ceiling lowest relative to d).

## Falsifiers
- Any codebook where flops-only != d_min (with d_min <= 6) falsifies (a). Any where flops-only != d(I,W) falsifies the literal (a) (expected for the two B-variants; any other is a surprise).
- Any codebook where all-nets > flops-only falsifies (b) (would also indicate a tool bug).
- Any structural-netlist all-nets value != rule falsifies the rule part of (b).
- Any all-nets value above 3 with the 3-copy grouping falsifies (c).
- A d<8 codebook with a larger gap than every d=8 codebook falsifies (d).

All failed predictions will be reported at full prominence in `P11_REPORT.md`.
