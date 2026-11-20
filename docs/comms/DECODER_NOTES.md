# What a real error-correcting decoder did to two toy designs

License: UNDECIDED. Toy designs, modelled bit flips, bounded (T=6, k<=4). Nothing established as new. **These two decoders only: no general rule about ECC.**

## In plain words

The boot state of `rtl/v2.v` is an 8-bit codeword; the accept word 0x96 is 4 bits from the pre-boot words. We added a SECDED decoder (corrects one flipped bit, flags two) in front of the state (`rtl/v2_secded.v`), and separately a check-only version (`rtl/v2c.v`: boot needs syndrome zero and word 0x96). The corrector made the attack on the stored bits **cheaper**: 3 flips where v2 needs 4, because the decoder supplies the fourth bit. Neither decoder changed the cost when every wire may be flipped.

## Predicted (before any solver run) vs measured

Pre-registration: `research/c6/comms/P18_PREREG.md`. MEASURED: product CLI `--synth-sweep`, stem rule, yosys 0.33, flow `plain`; `results/comms/decoder_variants.csv` from `scripts/comms/decoder_variants.py`.

| design | goal | sites | predicted | measured |
|---|---|---|---|---|
| v2_secded | boot_word==0x96 | flops | 3 | 3 |
| v2_secded | boot_word==0x96 | all nets | 2 | 2 |
| v2c | boot_word==0x96 | flops | 4 | 4 |
| v2c | boot_word==0x96 | all nets | 2 | 2 |
| v2_secded / v2c | boot_ok | flops | 3 / 4 | 3 / 4 |
| all four designs | boot_ok | all nets | 1 | 1 |
| v2 / v2e (reference) | boot_word==0x96 | flops; all nets | none | 4; 2 / 4; 3 |

The task brief suggested flops-only would *rise*; the pre-registration predicted 3.

## Negative results

- **The decoder opened no cheaper all-nets route.** In all 9 synthesis flows the all-nets minimum of v2_secded and v2c equals v2's (2,1,1,2,2,2,2,2,3). "Every added decoder is attack surface" is not supported as a cost effect here: gates grew 85 to 143 (plain), the minimum stayed.
- **The check-only consumer bought nothing measurable**: every v2c minimum equals v2's; boot_ok remains one net.

## Function checks (SIMULATED, iverilog)

`tb/tb_v2_secded.v`, `tb/tb_v2c.v`: 256 keys; every single state-flop flip is corrected (v2_secded) or never boots (v2c). Triple flips boot a wrong key in 8 of 280 cases on v2_secded, 0 on v2c.

## Limits

No timeout occurred (no `unknown` cell). Witnesses were not attributed to decoder versus compare logic. One code, one decoder, one FSM.
