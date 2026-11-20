# P13a report: coding-theory chapter (claims and wording)

License: UNDECIDED. Working title TBD. Faults are modelled bit flips; nothing physical; nothing established as new. Work copy: `/tmp/work_p13/` (venv with `pip install ./product`). No file outside my scope was edited; the edits in section 3 are for a later agent to apply.

## 1. What was done (all MEASURED here unless labelled)
- `docs/comms/test_rm13.py` (copy `docs/dossier/test_rm13.py`): 16 tests, **16 passed** (`test_output.txt`, both copies). Facts checked: RM(1,3) = span{FF,0F,33,55}, n=8, k=4, d=4, weight enumerator 1 + 14z^4 + z^8; F0, CC, 96, 69, C3 are all members under the stated LSB-first truth-table convention **and** under MSB-first (RM(1,3) is invariant under bit reversal), so no word had to be dropped; state-code distances 4,4,4,4,4,8; 0x69 xor 0xFF = 0x96; CC xor 96 = 0x5A touches only copy groups m0, m1.
- Comparison with repo data: anchor `bf_*.json` counts are attack-set counts over all netlist sites, **not** a codeword weight enumerator; only bounds are comparable (all-nets min 3 / 2 < d=4; no V2-spike attacking set of size 1 or 2). M1 CSV: the 27 colliding masks equal the masks of masked distance 0 from {F0,CC} to 96; solver minimum <= masked distance on 255/255 masks (v1 spike, v2 spike, v2 apt-0.33 columns).
- Re-ran `docs/dossier/test_hamming.py` (z3, T=6): flops-only min 4 on V1 spike, V2 spike, V1 apt-0.33, V2 apt-0.33; all sites 1, 3, 1, 2 (`hamming_runs.txt`). This turns the previously unstored D1 numbers (EVIDENCE_INDEX row 21) into a stored output; V0 flops-only (1) was not re-run.
- Product CLI (`cli_runs.txt`, `cli_masks.txt`): V1 spike 1 (`ok`@1); V2 spike 3; V2 `--consumer-bits` 0x03/0x0F/0x4E = 1/2/3, witnesses on state flops only; V2 `boot_ok` goal 1.
- Wrote `docs/comms/CODING_VIEW.md` (about 1100 words of prose plus the table; longer than the 800 asked because of the table) and `docs/edu/LAB4_CODES.md` (45 min).

## 2. Surprises / open points
- The product CLI has **no flops-only fault-site option** (`faultbound-wt analyze --help`); the lab uses `docs/dossier/test_hamming.py` for that column. A `--fault-sites flops` option would be a small product item (not done; not my scope).
- With a narrow consumer the CLI's cheapest attack is flops only, so the punctured-code distance is directly visible in the product: a clean teaching row.
- V2m (per-bit vote) all-nets 2 = d - t for a [3,1,3] repetition code with t=1 correction (M1 s5): consistent with the plan's E-C3 prediction, one row only.
- Not done: P11 codebook sweep (cells "pending P11"), burst measurement (pending P14), random-channel numbers (P12). `results/comms/distance_sweep.csv` did not exist at the time of writing.

## 3. Edits for a later agent to apply

### 3a. PROJECT_DOSSIER.md section 12
Replace the last sentence "Communication engineering: not applicable beyond Hamming-distance state encoding." with:
"Communication engineering: covered in `docs/comms/CODING_VIEW.md` (in progress). The state words F0, CC, 96, 69 and the key C3 are codewords of RM(1,3) [8,4,4] (FACT, `docs/comms/test_rm13.py`, 16 passed); the copies form repetition codes (V1 n=2 merged into one net, V2 n=3 detection only); flops-only minimum 4 = d on four netlists, all-nets 1/3/2 (MEASURED, `research/c6/p13/hamming_runs.txt`); the gap is set by the decoder. The complementary pair 96/69 (distance 8) is mapped onto itself by one all-flop inversion (arithmetic; circuit burst run pending P14). Textbook coding theory measured on toy designs; nothing new; no claim that RM(1,3) was chosen on purpose."
Also change "D1 re-run" in s12 to "D1, re-run by P13a 2026-11-20, `research/c6/p13/hamming_runs.txt`".

### 3b. EVIDENCE_MAP.md row 7 (Analysis)
Append to Evidence: "`docs/comms/CODING_VIEW.md`, `docs/comms/test_rm13.py`". Append to Strength: "coding view: state code is a subset of RM(1,3) (tested); fault-capacity table separates code distance (flops-only 4) from decoder ceiling (all nets 1 to 3); narrow consumers read as punctured codes (masked distance matches CLI on 3 masks and bounds M1 on 255/255)". Append to Gap: "codebook sweep (P11), burst run (P14), random channel (P12) pending; textbook material, no new theory". Estimate: leave at 6 until P11 lands (do not raise on this alone). If the criteria include a communication-engineering row, map it to CODING_VIEW and replace any "not applicable".

### 3c. OWNER_DERIVATION_SHEET.md: add question 6 (leave answer blank)
```
## 6. The state code is a Reed-Muller code: what does its distance buy?
- Question: show that F0, CC, 96, 69 are codewords of RM(1,3) (span of FF, 0F, 33, 55; bit i of the byte = f(binary(i))). What is the minimum distance d? Predict the flips needed if only the 8 state flops may flip, and say why V1 needs only 1 flip when every net may flip.
- Data: `rtl/v1.v`, `rtl/v2.v`; `docs/comms/CODING_VIEW.md`.
- Hand steps: (leave for the owner)
- Expected answer: (leave for the owner; the agent's check values are in `research/c6/p13/hamming_runs.txt` and `docs/comms/test_rm13.py`)
- Check against: `python3 -m pytest -q docs/comms/test_rm13.py`; `python3 docs/dossier/test_hamming.py <copy> reference/spike_netlists/v1.json v1 6`.
- My derivation: ______
```

## 4. Q&A cards (8) for `docs/dossier/QA_ANSWER_CARDS.md`
1. **Q: Is there any communications content in this project?** - The state words are codewords of RM(1,3) [8,4,4], and the copied comparators are repetition codes. - The measured flops-only cost equals the code distance; the all-nets cost is set by the decoder. - It is textbook coding theory measured on toy designs, nothing new. **Number:** d=4, flops-only 4 on 4 of 4 netlists (MEASURED). **File:** `docs/comms/CODING_VIEW.md`, `research/c6/p13/hamming_runs.txt`.
2. **Q: Prove F0, CC, 96, 69 are RM(1,3) codewords.** - Bit i = f(binary(i)); x2 = F0, x1 = CC. - 69 = 0F+33+55 = 1+x0+x1+x2 and 96 is its complement x0+x1+x2. - Also true if the byte is read MSB-first (bit reversal is an affine change of variables). **Number:** 16 codewords, all 5 RTL words members (FACT). **File:** `docs/comms/test_rm13.py`.
3. **Q: What is the minimum distance and what does it guarantee?** - Weight enumerator 1 + 14z^4 + z^8, so d=4. - Detects any 3 bit errors, would correct 1 if a decoder corrected (none does). - Guarantee holds for errors on the stored bits only. **Number:** d=4, detect 3, correct 1 (FACT). **File:** `research/c6/p13/test_output.txt`.
4. **Q: If d=4, why does V1 fall to 1 flip?** - The two copies are a [2,1,2] repetition code merged by `ok = m1 & m2` into one net. - That net is a point where all codewords decode alike; flipping it at cycle 1 writes 96. - A code protects the codeword, not the circuit that decodes it. **Number:** 1 (`ok`@1), flops-only 4 (MEASURED). **File:** `research/c6/p13/cli_runs.txt`, `hamming_runs.txt`.
5. **Q: Why is V2 3 on the stored netlist but 2 after re-synthesis?** - Three copies with disjoint bit groups: a [3,1,3] repetition code used for detection, so 3 = its distance. - Re-synthesis can share logic so the copies are no longer independent; CC xor 96 touches only two of three groups (arithmetic). - The root cause is P01's question, not claimed here. **Number:** 3 spike, 2 apt-0.33 (MEASURED; anchor brute force 182 triples / 3 pairs). **File:** `research/c5/anchor/ANCHOR_REPORT.md`, `hamming_runs.txt`.
6. **Q: What happens if the consumer reads only some bits?** - It reads a punctured code: the distance on those bits only. - For masks 0x03, 0x0F, 0x4E the masked distance from F0/CC to 96 is 1, 2, 3 and the CLI measures 1, 2, 3 with flop flips only. - On all 255 masks the solver never exceeds the masked distance. **Number:** 1/2/3; 255/255 (MEASURED). **File:** `research/c6/p13/cli_masks.txt`, `research/c3/m1/m1_all_masks.csv`.
7. **Q: Is the complementary pair 96/69 a good choice?** - Against independent flips yes: distance 8, the maximum. - Against one event that inverts all 8 flops no: 69 xor FF = 96, and FAIL holds, so a later burst turns reject into accept. - Interleaving or separating copies is the classic answer; not measured here. **Number:** distance 8; burst = 1 event (ARITHMETIC; circuit run pending P14). **File:** `docs/comms/CODING_VIEW.md`.
8. **Q: What may you not claim from the coding view?** - No novelty; no claim that RM(1,3) was chosen on purpose. - Modelled flips, T=6, four netlists: "matched in 4 of 4", not "always". - No bit-error rates or physical glitch claims. **Number:** 4 of 4 (MEASURED). **File:** `docs/comms/CODING_VIEW.md` "Limits".

## Files written
`docs/comms/CODING_VIEW.md`, `docs/comms/test_rm13.py`, `docs/dossier/test_rm13.py` (copy), `docs/edu/LAB4_CODES.md`, `research/c6/p13/{P13_REPORT.md, test_output.txt, hamming_runs.txt, cli_runs.txt, cli_masks.txt}`.
