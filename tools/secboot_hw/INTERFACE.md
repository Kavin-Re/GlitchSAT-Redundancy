# Secure-boot hardware: register interface and fit with the firmware

This page describes `rtl/secboot_mmio.v`, the 32-bit register front end of the boot core, and how it lines up
with the boot SoC contract in `../firmware/INTERFACE.md` (the firmware page is the master for the memory map; this
page only describes the HMAC window and what differs). Python reference: `model/mmio_model.py`; bench:
`tb/gen/tb_mmio.v` with `vectors/mmio.vec`; tests: `tests/test_mmio.py` (which also compares the offsets with
`../firmware/src/mmio.h` when that file is present).

## Where it sits

The engine occupies the firmware's `HMAC` region at `0x5000_0000`. Offsets `0x00`..`0x3C` are the ones the
firmware driver `src/hmac_hw.c` already uses; `0x40`..`0x48` and `0x60`..`0x7C` are additions.

| Offset | Name | Access | Meaning | Same as firmware? |
|---|---|---|---|---|
| `0x00` | `CTRL` | W | `1` = START: clear the message buffer and `EXPECTED`, restart the core (the key block is the synthesis parameter `KEY`, see below). `2` = FINISH: end of message; copies `EXPECTED` into the core's shadow registers and lets the core finish; sets ERR if the message length is wrong. Other values ignored. | yes |
| `0x04` | `STATUS` | R | bit 0 `DONE` (digest valid, or ERR), bit 1 `ERR`, bit 2 `ACCEPT` (verdict is `0x96`), bit 3 `ALARM_SEEN`, bit 4 `BUSY` | bit 0 yes; bits 1..4 added |
| `0x08` | `MSG` | W | append 4 message bytes (the word's bytes in little-endian order, byte 0 = bits 7:0) | yes |
| `0x20`..`0x3C` | `DIGEST[0..7]` | R | digest bytes `4i..4i+3` as a little-endian word `i`; reads 0 until the core is done (gated by the core's done only, not by ERR) | yes (layout); algorithm differs, see below |
| `0x40` | `VERDICT` | R | the core's boot word: `0x96` ACCEPT, `0x69` REJECT, `0x5A` ALARM, other codes while busy | added |
| `0x44` | `TOKEN` | R | release token: `0xA5C3B007` (= `FLASH_EXEC_KEY`) after a genuine boot, 0 or a corrupted value otherwise | added |
| `0x48` | `INFO` | R | bits 31:16 image blocks expected, bits 15:0 words per block | added |
| `0x60`..`0x7C` | `EXPECTED[0..7]` | W | expected tag of this image (the image header's `mac` field), same layout as `DIGEST`; write after START and before FINISH; writes outside that window are ignored; reads 0 | added |

The additions need the HMAC region to be 128 B (`0x5000_0000..0x5000_007F`) instead of the 64 B listed in the
firmware memory map. `../firmware/INTERFACE.md` now lists the 128 B window and the firmware driver (`mac_sha3_hw.c`) uses
`VERDICT`, `TOKEN`, `INFO` and `EXPECTED`. The SoC build sets `IMG_BLOCKS = 8` (the RTL default is 2); the firmware
reads `INFO`, while its image tool and simulator assume 8 blocks.

Driver sequence (default build, `EXP_SRC = 1`): START, `EXPECTED[0..7]` = the image's `mac` words, the message
words (`IMG_BLOCKS` x 136 B), FINISH, poll `STATUS` until DONE, then read `VERDICT` / `TOKEN` (and `DIGEST` if
wanted). The core absorbs its last (pad) block only after FINISH, so a slow driver gets the same result as a
back-to-back one; without FINISH the core waits and DONE stays low.

Bus timing: one access per clock; a write is taken at the rising edge; read data is combinational in the
address (valid in the same cycle). Output `stall` is a wait state: a `MSG` write while the block buffer is still
full is held off, and the bus master keeps the write on the bus until `stall` is low. A back-to-back writer such
as `hmac_hw.c` therefore needs no change to its loop. Synchronous reset only.

## What the hardware computes

- Digest = SHA3-256(K || M), where K is one 136-byte key block and M is the message written to `MSG`.
  K is the synthesis parameter `KEY` (1088 bits); there is no OTP key port. A build for the SoC must set it to
  the OTP provisioning value: the 32 key bytes (`OTP HMAC_KEY[0..7]`, byte i = byte i % 4 of word i / 4), then
  104 zero bytes (`model/mmio_model.py: key_block_from_otp`). An OTP key port is future work.
- The message must be exactly `IMG_BLOCKS` x 136 bytes (`INFO`). Writing more words, or FINISH after a
  different number of words, sets ERR; with ERR set `VERDICT` reads REJECT and `TOKEN` reads 0 (an error can
  only deny). `DIGEST` reads 0 until the core is done and is not gated by ERR: an error found before the last
  block stops the core, so `DIGEST` stays 0; an error raised after DONE (for example an extra `MSG` write) sets
  ERR, but `DIGEST` still returns the tag.
- The hardware also compares the digest with the expected tag and runs the countermeasures of SPEC.md: `VERDICT`,
  `TOKEN` and the `boot_word` / `boot_token` outputs carry that decision. Default (`EXP_SRC = 1`): the expected
  tag is the value written to `EXPECTED[0..7]`, copied at FINISH into the shadow registers (one per consumer
  with `OTP_REG = 2`), so one chip build accepts every image whose `mac` field matches its key. A missing,
  wrong or late (after FINISH) `EXPECTED` gives REJECT. With `EXP_SRC = 0` the expected tag is the synthesis
  parameter `EXP_TAG`: fixed at synthesis, so that build accepts exactly one image; `EXPECTED` writes are then
  ignored. The fault experiments (`d_*`, `h_*`) use `EXP_SRC = 0` and do not use the bus.

Default build of `secboot_mmio` (EXACT, parameters in the RTL): full-size SHA3-256 engine (W = 64, rate 1088,
24 rounds), one key block, two image blocks, triplicated owned-bit compare, multi-bit flags, alarm, step counter,
per-copy shadow registers of the expected tag loaded from `EXPECTED` (`OTP_REG = 2`, `EXP_SRC = 1`), infection
spread 3, token `0xA5C3B007`. A genuine boot takes 104 core cycles after START plus the bus writes (the bench
counts its STATUS polls).

## Differences from the firmware's engine, and what a firmware variant would change

| Item | Firmware today (`hmac_hw.c`, simulator) | This hardware | Change needed for firmware to use it |
|---|---|---|---|
| Algorithm | HMAC-SHA-256 | SHA3-256(K \|\| M) with K as above | image builder (`faultsim/image.py`) computes the `mac` field with the same formula |
| Message length | header 16 B + payload (<= 1024 B, any multiple of 4) | exactly `IMG_BLOCKS` x 136 B | build with `IMG_BLOCKS = 8` (1088 B) and write zero words after the payload up to 1088 B |
| Key | 32 B from OTP | parameter `KEY` = the same 32 B, zero-filled to 136 B, set at synthesis | the SoC build sets `KEY` to the provisioned OTP key (no OTP key port yet) |
| Completion | DONE in STATUS bit 0 | same; DONE also on ERR so polling always ends | none |
| Compare | software compares 8 words | hardware compares with `EXPECTED[0..7]` and gives `VERDICT` / `TOKEN` | driver writes the header `mac` words to `EXPECTED` before FINISH; then read `VERDICT`, or route `boot_token` to `SYSCTRL EXEC_EN` (the software compare becomes optional) |

Token and flash execute enable: the firmware unlocks flash by writing `FLASH_EXEC_KEY` (`0xA5C3B007`) to
`SYSCTRL EXEC_EN`. This hardware's token is that same value, so the SoC can drive the execute-enable flop from
`boot_token` directly (EXEC_EN set only when `boot_token == 0xA5C3B007`). A forced ACCEPT with a wrong digest then
still leaves flash locked, because the infection path corrupts the token; that is what the `*_infect` and `*_all`
experiments measure.

## Experiment wrappers

The fault experiments do not use this bus. Each experiment is a wrapper `rtl/tops/top_<name>.v` with only
`clk`, the attacker input `sig[7:0]` and one goal output (`boot_word`, or `boot_grant = {boot_word,
boot_token}`); see SPEC.md section 12 and `build/manifest.json` (written by `python3 -m engine.wrappers`).
