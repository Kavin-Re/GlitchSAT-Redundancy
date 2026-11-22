# P18 pre-registration: error-correcting decoder variants of rtl/v2.v

License: UNDECIDED. Working title TBD.
Written at 2026-11-20T05:20:07Z (UTC, `date -u`), BEFORE any solver run on either variant and before their RTL was synthesised.
Toy designs, modelled single-cycle bit flips, bounded search. Nothing established as new. No general claim about ECC.

## Designs (fixed here)

Both keep the v2 interface (clk, sig, boot_ok, boot_word), the three cmp8 copies, the grouping and the words F0 -> CC -> 96 (accept) / 69 (fail).
All state words lie in RM(1,3) = extended Hamming [8,4,4]. Checks: par = XOR of all 8 state bits; syn[j] = XOR of state bits whose index has bit j set (masks AA, CC, F0).

- **v2_secded** (rtl/v2_secded.v): a SECDED decoder sits between the state flops and every user. If par=1 the bit at index syn is flipped (single-error correction) giving `dec`; if par=0 and syn!=0 a double error is flagged (`ded`). The FSM runs on `dec` and writes `dec` back (scrub); on `ded` the next state is 69. boot_word = dec; boot_ok = (dec == 96) and not ded.
- **v2c** (rtl/v2c.v): v2 unchanged except boot_ok = (syn == 0 and par == 0) AND (st == 96). No correction. boot_word = st.

## Measurement plan (fixed here)

Product CLI, stem rule, init known, inputs not fault sites, T=6, k up to 4, apt yosys 0.33, scripts/synth.sh plain flow (headline); other flows (synth.sh opt, no-ABC struct, --synth-sweep) secondary and reported separately. Goals: boot_word == 0x96, and boot_ok == 1. Sites: flops only (kinds=["flop"]) and all nets. Reference rows: v2 and v2e measured the same way in the same run. Timeout => 'unknown', never 'safe'.

## Predictions (plain flow, goal boot_word == 0x96 unless stated)

Note: the work plan suggested "flops-only rises" for v2_secded. I do NOT predict that; I predict the opposite, and register it as my own.

| design | sites | predicted min | reason |
|---|---|---|---|
| v2_secded | flops only | **3** (lower than v2's 4) | a t=1 corrector accepts every word within distance 1 of 96. From CC or F0 (d=4), 3 flop flips in one cycle land in the decoding sphere of 96 and the decoder itself supplies the 4th bit and scrubs 96 into the state. 1 flip is corrected; 2 flips are flagged (ded) or scrubbed. So d - t = 4 - 1 = 3. |
| v2_secded | all nets | **2** (range 1..2; never above flops-only) | v2 already costs 2 under this flow via shared compare/select logic; the decoder adds nets (syndrome, par, fix, dec) and removes none of the v2 routes cheaper than 3 for sure. I cannot name a 1-flip route (syndrome nets move at most one dec bit), so point prediction 2. |
| v2c | flops only | **4** (= v2 = d) | no correction; boot_word = st; the accept word is still at distance 4 from F0 and CC. |
| v2c | all nets | **2** (= v2 under this flow) | boot_word's cone does not contain the syndrome logic; the added check cannot raise the cost of a goal that does not read it. |
| any design | all nets, goal boot_ok | **1** | boot_ok is one gate output; flipping that net is the attack. A code cannot protect its own 1-bit verdict. |
| v2_secded | flops only, goal boot_ok | 3 | same route as boot_word. |
| v2c | flops only, goal boot_ok | 4 | boot_ok needs st == 96 exactly. |
| v2, v2e (reference) | flops / all nets | 4 / 2 and 4 / 3 | prior project results (P11 F0_96_stored 4/2; v2e expected 3 on all nets per P01a); re-measured here, not predicted by me. |

## Falsifiers

- v2_secded flops-only != 3: the d - t argument is wrong for this circuit (4 or more would mean the work plan's "rises" reading is right and mine is wrong).
- v2_secded all-nets >= 3: "the decoder is shared attack surface" fails for this decoder. All-nets = 1 is inside my range but misses my point prediction; I will report it as a point miss.
- v2c flops-only != 4, or v2c all-nets (boot_word) != v2's measured value in the same run: the "consumer check does not change the word goal" claim is wrong.
- any all-nets boot_ok minimum > 1: the "1-bit verdict" claim is wrong.
- Any 'unknown' cell is neither confirmation nor falsification.

## Function checks that must pass before any solver run

iverilog, all 256 sig values: honest key boots, 255 wrong keys never boot, power-up not accepted. v2_secded: every single state-flop flip (8 bits x each cycle) leaves boot_word/boot_ok identical to the fault-free run (corrected). v2c: every single state-flop flip never makes a wrong key boot, and on the honest key after boot it makes boot_ok drop (detected, not corrected).
