import json, sys
sys.argv=['x']
exec(open('research/c6/int/apply_edits.py').read().split('# ---------- README')[0])
E[:] = json.load(open(ROOT/'research/c6/int/edits_log.json'))
def app(path, text):
    p = ROOT/path; t = p.read_text()
    if text.strip() in t: E.append({'file': path, 'before': '(appended)', 'after': text}); return
    p.write_text(t.rstrip('\n') + '\n' + text); E.append({'file': path, 'before': '(appended at end)', 'after': text})

rep('docs/dossier/PROJECT_DOSSIER.md',
 "Test (SIMULATED fault model, D1 re-run, T=6,",
 "Test (SIMULATED fault model, D1, re-run by P13a 2026-11-20, `research/c6/p13/hamming_runs.txt`, T=6,")
rep('docs/dossier/PROJECT_DOSSIER.md',
 "Communication engineering: not applicable beyond Hamming-distance state encoding.",
 "Communication engineering (coding-theory view, `docs/comms/CODING_VIEW.md`): the state words F0, CC, 96, 69 and the key C3 are codewords of the Reed-Muller code RM(1,3) [8,4,4] (FACT, `docs/comms/test_rm13.py`, 16 passed; weight enumerator 1 + 14z^4 + z^8, d=4; re-checked by the lead 2026-11-20); the copies form repetition codes (V1 n=2 merged into one net `ok`, V2 n=3 used for detection only). Distance is the flops-only budget: flops-only minimum 4 = d on four netlists, all nets 1/3/1/2 (V1 spike, V2 spike, V1 apt, V2 apt; MEASURED, `research/c6/p13/hamming_runs.txt`); over 19 codebooks flops-only equals the nearest non-accept distance in 15 of 15 with distance <= 6 (P11, `results/comms/distance_sweep.csv`). The decoder sets the ceiling: about one flip per comparator copy, lower when synthesis shares logic (3 of 16 three-copy codebooks at 2). Burst caveat pending: the complementary pair 96/69 (distance 8) is mapped onto itself by one all-flop inversion (arithmetic; circuit burst run pending P14). Textbook coding theory measured on toy designs; nothing new; no claim that RM(1,3) was chosen on purpose.")

rep('docs/dossier/EVIDENCE_MAP.md',
 "| 7 | Analysis | dossier s7, s12; DS synthesis; FP derived-vs-chosen table | States what is derived (shared wire; SAT answer; Hamming distance) versus chosen (fault, counting, goal, input, init); M1 explains V2's '3' by a Hamming-plus-cut rule (known-style reasoning, not a discovery) that matches 255/255 masks on the spike netlist (187/255 on apt) | 85 vs 83 cause not located (E2);",
 "| 7 | Analysis | dossier s7, s12; DS synthesis; FP derived-vs-chosen table; `docs/comms/CODING_VIEW.md`, `docs/comms/test_rm13.py`, `results/comms/distance_sweep.csv`; `docs/report/WHY_TWO_FLIPS.md` | States what is derived (shared wire; SAT answer; Hamming distance) versus chosen (fault, counting, goal, input, init); M1 explains V2's '3' by a Hamming-plus-cut rule (known-style reasoning, not a discovery) that matches 255/255 masks on the spike netlist (187/255 on apt); coding view: state code is a subset of RM(1,3) (tested); fault-capacity table separates code distance (flops-only 4) from decoder ceiling (all nets 1 to 3); P11 codebook sweep (19 codebooks, failed predictions kept); P01a root cause of 2 vs 3 flips is the encoding (0xCC touches 2 of 3 copies; v2e restores 3 on 6 of 8 flows) | exact tool change behind 85 vs 83 gates not located (E2), but the 2-flip weakness is explained (P01a); burst run (P14) and random channel (P12) pending; textbook material, no new theory;")

rep('docs/OWNER_DERIVATION_SHEET.md',
 "## After you finish",
 """## 6. From the armed word to the accept word in two flips (V2, encoding root cause)
- Question: derive, by hand, the flip count to reach 0x96 from 0xCC at the load and show which copies the flipped bits belong to.
- Data: `rtl/v2.v` (bit groups: m0 bits 0,3,6; m1 bits 1,4,7; m2 bits 2,5); `docs/report/WHY_TWO_FLIPS.md`.
- Hand steps: (leave for the owner)
- Expected answer: (leave for the owner; the agent's check values are in `research/c6/p01/P01_REPORT.md`)
- Check against: `research/c6/p01/sweeps/sweep_apt_v2.json`, `research/c6/p01/sweeps/sweep_apt_v2e.json`.
- My derivation: ______

## After you finish""")

rep('docs/dossier/QA_ANSWER_CARDS.md',
 """**E2-7. 85 gates (apt 0.33) vs 83 (conda 0.38)?** IDK
- I do not know the exact cause.
- Known: synthesis deterministic; compare cones disjoint in both; difference in next-state mapping (one MUX on conda).
- Not shown: that the Yosys version is the cause.""",
 """**E2-7. 85 gates (apt 0.33) vs 83 (conda 0.38)?** PARTLY KNOWN (corrected 2026-11-20)
- I do not know the exact tool change behind the gate counts.
- But the 2-vs-3 flips is not a version effect: the stored netlist is also Yosys 0.33; the cause is the encoding (see card ENC-1).
- Known: synthesis deterministic; compare cones disjoint in both; difference in next-state mapping (one MUX on conda).""")

app('docs/dossier/QA_ANSWER_CARDS.md', """
## Coding view and encoding root cause (added by agent INT, 2026-11-20; cards C-1 to C-8 from `research/c6/p13/P13_REPORT.md`)

**C-1. Is there any communications content in this project?**
- The state words are codewords of RM(1,3) [8,4,4], and the copied comparators are repetition codes.
- The measured flops-only cost equals the code distance; the all-nets cost is set by the decoder.
- It is textbook coding theory measured on toy designs, nothing new.
Number: **d=4, flops-only 4 on 4 of 4 netlists** (MEASURED). File: `docs/comms/CODING_VIEW.md`, `research/c6/p13/hamming_runs.txt`.

**C-2. Prove F0, CC, 96, 69 are RM(1,3) codewords.**
- Bit i = f(binary(i)); x2 = F0, x1 = CC.
- 69 = 0F+33+55 = 1+x0+x1+x2 and 96 is its complement x0+x1+x2.
- Also true if the byte is read MSB-first (bit reversal is an affine change of variables).
Number: **16 codewords, all 5 RTL words members** (FACT). File: `docs/comms/test_rm13.py`.

**C-3. What is the minimum distance and what does it guarantee?**
- Weight enumerator 1 + 14z^4 + z^8, so d=4.
- Detects any 3 bit errors, would correct 1 if a decoder corrected (none does).
- Guarantee holds for errors on the stored bits only.
Number: **d=4, detect 3, correct 1** (FACT). File: `research/c6/p13/test_output.txt`.

**C-4. If d=4, why does V1 fall to 1 flip?**
- The two copies are a [2,1,2] repetition code merged by `ok = m1 & m2` into one net.
- That net is a point where all codewords decode alike; flipping it at cycle 1 writes 96.
- A code protects the codeword, not the circuit that decodes it.
Number: **1 (`ok`@1), flops-only 4** (MEASURED). File: `research/c6/p13/cli_runs.txt`, `hamming_runs.txt`.

**C-5. Why is V2 3 on the stored netlist but 2 after re-synthesis?**
- Three copies with disjoint bit groups: a [3,1,3] repetition code used for detection, so 3 = its distance.
- CC xor 96 touches only two of three groups, so a netlist with one shared next-state net per group falls to 2 (card ENC-1).
- Re-encoded `rtl/v2e.v` gives 3 on 6 of 8 flows.
Number: **3 spike, 2 apt-0.33** (MEASURED; anchor brute force 182 triples / 3 pairs). File: `research/c5/anchor/ANCHOR_REPORT.md`, `docs/report/WHY_TWO_FLIPS.md`.

**C-6. What happens if the consumer reads only some bits?**
- It reads a punctured code: the distance on those bits only.
- For masks 0x03, 0x0F, 0x4E the masked distance from F0/CC to 96 is 1, 2, 3 and the CLI measures 1, 2, 3 with flop flips only.
- On all 255 masks the solver never exceeds the masked distance.
Number: **1/2/3; 255/255** (MEASURED). File: `research/c6/p13/cli_masks.txt`, `research/c3/m1/m1_all_masks.csv`.

**C-7. Is the complementary pair 96/69 a good choice?**
- Against independent flips yes: distance 8, the maximum.
- Against one event that inverts all 8 flops no: 69 xor FF = 96, and FAIL holds, so a later burst turns reject into accept.
- Interleaving or separating copies is the classic answer; not measured here.
Number: **distance 8; burst = 1 event** (ARITHMETIC; circuit run pending P14). File: `docs/comms/CODING_VIEW.md`.

**C-8. What may you not claim from the coding view?**
- No novelty; no claim that RM(1,3) was chosen on purpose.
- Modelled flips, T=6, four netlists: "matched in 4 of 4", not "always".
- No bit-error rates or physical glitch claims.
Number: **4 of 4** (MEASURED). File: `docs/comms/CODING_VIEW.md` "Limits".

**ENC-1. Why does V2 need 2 flips and not 3 on the apt 0.33 netlist?**
- The machine loads the armed word 0xCC at cycle 0; 0xCC xor 0x96 = 0x5A, bits {1,3,4,6}, owned by copies m1 and m0 only.
- On this netlist one net moves bits {1,4} and another moves {3,6}: two flips turn the load of CC into 96.
- Encoding sets the floor (2 copies touched => 2); the synthesis flow decides whether the floor is reached.
Number: **2 1 1 2 2 2 2 2 over 8 flows** (MEASURED, P01a; re-verified by the lead 2026-11-20). File: `docs/report/WHY_TWO_FLIPS.md`, `research/c6/p01/P01_REPORT.md`. Trap: "it is a Yosys version effect" (the stored netlist is also Yosys 0.33; that wording was an error, now corrected).

**ENC-2. Does re-encoding fix it?**
- Changing only the armed constant to 0xA5 (xor 96 = bits 0,1,4,5, all three copies) gives 3 on 6 of 8 flows.
- The two flows that merge the comparators (opt_merge, flatten before ABC) stay at 1: no encoding fixes merged copies.
- Conda 0.38 with 0xCC: 3 only on the plain flow; three other flows give 2.
Number: **v2e 3 1 1 3 3 3 3 3** (MEASURED, apt and conda). File: `rtl/v2e.v`, `research/c6/p01/sweeps/`. Trap: "v2e is secure" (bounded: T=6, k<=3, toy, modelled flips).
""")

rep('docs/dossier/EVIDENCE_INDEX.md',
 "| 6 | Verdict table depends on the Yosys build (apt 0.33 vs conda 0.38+92); only 0.33 was run in the tree |",
 "| 6 | Verdict table depends on the netlist (apt 0.33 vs conda 0.38+92 builds give different netlists); only 0.33 was run in the tree. CORRECTED 2026-11-20: the old reading 'depends on the Yosys version' was an error (row 78) |")
app('docs/dossier/EVIDENCE_INDEX.md', """| 77 | Coding view: state words F0, CC, 96, 69, C3 are RM(1,3) codewords, d=4, enumerator 1,14,1; flops-only 4 on V1/V2 spike and apt; all nets 1/3/1/2 | FACT (test) + MEASURED | `docs/comms/CODING_VIEW.md`, `docs/comms/test_rm13.py`, `research/c6/p13/hamming_runs.txt` | `python3 -m pytest -q docs/comms/test_rm13.py` | P13a; lead re-ran membership |
| 78 | CORRECTED ERROR: 'V2 needs 3 flips stored and 2 on apt 0.33 because of the Yosys version' was wrong (found by a fresh-eyes review, measured by P01a): stored netlist is also Yosys 0.33; cause is the encoding (0xCC touches 2 of 3 copies); v2 rows 2 1 1 2 2 2 2 2, v2e rows 3 1 1 3 3 3 3 3 | MEASURED | `docs/report/WHY_TWO_FLIPS.md`, `research/c6/p01/P01_REPORT.md`, `research/c6/fresh_eyes/ENHANCEMENT_PLAN.md` | `faultbound-wt analyze rtl/v2.v --top v2 --max-flips 3 --cycles 6 --synth-sweep` | P01a; lead re-verified 2026-11-20 05:06 UTC |
| 79 | Codebook sweep: 19 codebooks; flops-only = nearest non-accept distance in 15/15 (d<=6); all nets <= flops-only 19/19; failed predictions (a) literal, (c) 3 of 16 at 2, word order | MEASURED | `results/comms/distance_sweep.csv`, `research/c6/p11/P11_REPORT.md`, `docs/comms/staircase.png` | `python3 scripts/comms/distance_sweep.py --out results/comms/distance_sweep.csv --cli faultbound-wt` | P11a |
| 80 | glitchsat.py runs synth.sh via `sh` and no longer advises 'add another independent copy'; sha256 1ad037ef... | MEASURED | `research/c6/p08/P08_REPORT.md`, `tests/test_p08.py` | `pytest -q tests/test_p08.py` | P08; lead updated ENGINE_MANIFEST |
""")
app('docs/dossier/CRITIQUE.md', """| FE-1 | fresh-eyes review (P01a measured) | HIGH | Headline misattribution: '3 flips stored, 2 on apt 0.33' was explained as a Yosys-VERSION effect; the stored netlist is also Yosys 0.33 (flow/source difference); the cause is the encoding (0xCC xor 0x96 touches 2 of 3 copies); `rtl/v2e.v` (0xA5) gives 3 1 1 3 3 3 3 3 over 8 flows | `docs/report/WHY_TWO_FLIPS.md`, `research/c6/p01/P01_REPORT.md` | FIXED (agent INT 2026-11-20: old wording marked as a corrected error in README, FINAL_STATUS, ENGINE_STATUS, dossier, report, dashboard, edu, slides, review) |
| FE-2 | P11a | MED | Coding-view predictions partly failed: flops-only = d(I,W) fails for 2 B-variant codebooks; 3 of 16 three-copy codebooks at 2 on the project flow; word order matters under ABC; mechanism undissected | `research/c6/p11/P11_REPORT.md` | OPEN (stated in README) |
""")
json.dump(E, open(ROOT/'research/c6/int/edits_log.json','w'), indent=1)
print(len(E))
