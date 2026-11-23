# Boot SoC interface: memory map, MMIO registers, image format, boot flow

This page is the contract between the boot ROM firmware in `firmware/` and any
hardware that runs it (the Python simulator `rv32sim/` today; an RTL SoC with
the `secboot_hw` SHA3-256 engine later). The same numbers live in three places that must
change together: `src/mmio.h` and `src/image.h` (firmware), `rv32sim/cpu.py`
(simulator), and this page. `tests/test_interface.py` checks that the C header
and the simulator agree.

CPU: RV32IMC (`-march=rv32imc -mabi=ilp32`), little-endian, no CSRs used, no
interrupts. Reset PC = `0x00000000` (`_start`).

## Memory map

| Region | Base | Size | Access | Contents |
|---|---|---|---|---|
| ROM | `0x0000_0000` | 16 KiB | read, execute | boot ROM code and constants |
| RAM | `0x1000_0000` | 4 KiB | read, write | `.bss` (zero at reset), stack (top `0x1000_1000`) |
| FLASH | `0x2000_0000` | 4 KiB | read; execute only after `EXEC_EN` | boot image (header + payload), external, attacker-writable |
| SYSCTRL | `0x3000_0000` | 16 B | see below | boot status, alarm, TRNG, flash execute enable |
| OTP | `0x4000_0000` | 40 B | read (32-bit aligned words only) | HMAC key, anti-rollback minimum version |
| HMAC | `0x5000_0000` | 128 B | see below | MAC engine: SHA3-256 engine of `secboot_hw` (SoC interface), or the legacy HMAC-SHA-256 model |

Any other access is a bus error. The simulator turns every exception (bus
error, illegal instruction including `unimp`, misaligned PC, `ecall`, `ebreak`,
fetch from FLASH while execute-locked) into a halt (outcome `trap`). Hardware
should do the equivalent: a ROM trap handler that halts or resets without
running the image. Misaligned loads/stores inside one region are allowed (Ibex
behaviour).

## SYSCTRL registers (`0x3000_0000`)

| Offset | Name | Access | Meaning |
|---|---|---|---|
| `0x00` | `BOOT_STATUS` | W | Last boot status code. Bit 31 set = boot failed: the core halts (simulator outcome `reject`). `0x0000_B007` (`BS_JUMP`) = about to jump to the image. Failure reasons in bits 7:0: 1 bad magic, 2 bad length/entry, 3 rollback, 4 bad MAC, 5 MAC engine error (SHA3 driver). |
| `0x04` | `ALARM` | W | Any write = a redundant check disagreed (fault detected). The core halts (outcome `alarm`). Value = reason code. |
| `0x08` | `TRNG` | R | One 32-bit random word per read (simulator: xorshift32 from a seed). Used only by the random-delay variant. |
| `0x0C` | `EXEC_EN` | W | Writing exactly `0xA5C3_B007` (`FLASH_EXEC_KEY`) allows instruction fetch from FLASH until reset; other values are ignored. Before that, a FLASH fetch traps. `rom_jump()` writes it right before `jr`. |

Why `EXEC_EN` exists: with flash executable from reset, one flipped bit in a
return address (`ra`, bit 29: `0x0000_xxxx` -> `0x2000_xxxx`) jumps straight into
attacker-controlled flash; the fault search found this single-flip attack in
all 18 builds searched without the lock (all nine variants, `-O2`, plain and
barrier styles; MEASURED, `results/TABLES.md`, "Flash executable from reset"). The lock is the same idea as
OpenTitan's use of ePMP to keep flash non-executable until the ROM has
verified it. In hardware it should be a sticky flop set only by the exact key
value (a multi-bit key, so one flipped bit in the written value does not set
it).

## OTP words (`0x4000_0000`, read-only)

| Offset | Name | Meaning |
|---|---|---|
| `0x00`..`0x1C` | `HMAC_KEY[0..7]` | 32-byte HMAC key; byte `i` is byte `i % 4` (little-endian) of word `i / 4` |
| `0x20` | `MIN_VERSION` | lowest image `version` allowed to boot (anti-rollback) |
| `0x24` | `MIN_VERSION_INV` | bitwise complement of `MIN_VERSION`; the hardened variants check `MIN_VERSION ^ MIN_VERSION_INV == 0xFFFF_FFFF` |

Every OTP read is a real bus read (`volatile`), so the compiler cannot merge two
reads ("double read of OTP" survives every optimisation level; see results).
Simulator demo provisioning: key = bytes `0x40..0x5F`, `MIN_VERSION` = 5.

## MAC engine window (`0x5000_0000`, 128 B)

Decision (2026-11-21, after the independent review of the hardware design):
the SoC's MAC engine is the **SHA3-256 engine of `secboot_hw`**
(`rtl/secboot_mmio.v`), and the firmware's hardware-hash path follows it. The
window is 128 B (`0x5000_0000`..`0x5000_007F`). Two engine models exist in the
simulator; a build selects one by its MAC driver:

| build suffix | driver | engine model in `rv32sim` | used for |
|---|---|---|---|
| `-sha3` | `src/mac_sha3_hw.c` | SHA3-256 engine, the interface below (**the SoC interface**) | builds matching the hardware |
| `-hw` | `src/hmac_hw.c` | HMAC-SHA-256 engine, offsets `0x00`..`0x3C` only (legacy) | the main fault matrix recorded on 2026-11-20/21; kept unchanged so no recorded result changes |
| `-sw` | `src/hmac_sw.c` | none (HMAC-SHA-256 in software, key read from OTP) | software-only builds |

The simulator picks the SHA3 model when the ELF defines the symbol
`mac_engine_sha3` (in `mac_sha3_hw.c`). `tests/test_boot.py` checks the SHA3
model against the hardware's own register model `secboot_hw/model/mmio_model.py`
(same digest, verdict and token for a good and a tampered image).

### SHA3-256 engine registers

| Offset | Name | Access | Meaning |
|---|---|---|---|
| `0x00` | `CTRL` | W | `1` = START: clear the message buffer and ERR, restart the core. `2` = FINISH: end of message; sets ERR if not exactly `INFO` blocks were written; latches `EXPECTED`. Other values ignored. |
| `0x04` | `STATUS` | R | bit 0 `DONE` (digest valid, or ERR: polling always ends), bit 1 `ERR`, bit 2 `ACCEPT` (verdict `0x96`), bit 3 `ALARM_SEEN`, bit 4 `BUSY` |
| `0x08` | `MSG` | W | append 4 message bytes (the word's bytes in little-endian order). A write before START, after FINISH or beyond the message length sets ERR. The RTL may hold a write with a wait state (`stall`); a back-to-back writer needs no change. |
| `0x20`..`0x3C` | `DIGEST[0..7]` | R | digest bytes `4i..4i+3` as little-endian word `i`; reads 0 until DONE |
| `0x40` | `VERDICT` | R | the hardware boot word: `0x96` ACCEPT, `0x69` REJECT (also whenever ERR), `0x5A` ALARM, other codes while busy |
| `0x44` | `TOKEN` | R | `0xA5C3_B007` (= `FLASH_EXEC_KEY`) after a hardware ACCEPT; otherwise 0 (ERR) or a value corrupted by the infection path |
| `0x48` | `INFO` | R | bits 31:16 message blocks expected, bits 15:0 32-bit words per block. SoC build: 8 blocks x 34 words = 1088 B |
| `0x60`..`0x7C` | `EXPECTED[0..7]` | W | expected tag, little-endian words like `DIGEST`; the driver writes the image header `mac` here before FINISH; latched into the per-consumer shadow registers at FINISH |

Other offsets in the window: reads return 0, writes are ignored.

What the engine computes: `DIGEST = SHA3-256(K136 || M)`.
- `K136` = the key block: the 32 OTP key bytes (`OTP HMAC_KEY[0..7]`, byte `i` =
  byte `i % 4` of word `i / 4`), then 104 zero bytes. In the RTL the key is the
  synthesis parameter `KEY` (1088 bits); a build for this SoC sets it to that
  value. An OTP key port is future work.
- `M` = exactly `INFO` blocks x 136 B = 1088 B in the SoC build (`IMG_BLOCKS = 8`; the RTL default
  is `IMG_BLOCKS = 2`, so the SoC build sets it, and `faultsim/image.py` and the simulator assume 8;
  1088 >= 16 + 1024, the largest image): header bytes `0x00..0x0F`, the
  payload, then zero words up to 1088 B. Zero padding is unambiguous because
  `length` is inside the hashed header. `mac_sha3_hw.c` reads `INFO` instead of
  hard-coding the length and fails with `BS_ENGINE` (5) if the message cannot
  hold the image, or if STATUS shows ERR.
- The hardware also compares the digest with `EXPECTED` and runs its own
  counter-measures; `VERDICT`, `TOKEN` and the `boot_word`/`boot_token`
  outputs carry that decision. The simulator models the decision ideally
  (ACCEPT iff digest = latched `EXPECTED`, TOKEN = key or 0); the hardware's
  fault behaviour is analysed at gate level in `secboot_hw`.

Note on the RTL as of 2026-11-21: `EXPECTED` is the change agreed in the
review; until it lands in `secboot_mmio.v`, the hardware compares with its
`EXP_TAG` parameter. The firmware writes `EXPECTED` either way (writes to an
unknown offset are ignored).

### HMAC-SHA-256 engine model (legacy, `-hw` builds)

| Offset | Name | Access | Meaning |
|---|---|---|---|
| `0x00` | `CTRL` | W | `1` = START: clear the message, load the key from OTP `HMAC_KEY`. `2` = FINISH: pad, compute HMAC-SHA-256, set DONE. |
| `0x04` | `STATUS` | R | bit 0 `DONE` |
| `0x08` | `MSG` | W | append 4 message bytes (little-endian); any length in whole words |
| `0x20`..`0x3C` | `DIGEST[0..7]` | R | HMAC bytes `4i..4i+3` as little-endian word `i` (0 until DONE) |

Any other offset in the window is a bus error in this model (as when the
recorded results were produced). The `-hw` image `mac` is
`HMAC-SHA-256(key, header[0..15] || payload)`. Both engine models are atomic
in the simulator (DONE right after FINISH); a real engine takes cycles and the
driver polls `DONE`.

Fault analysis does not inject faults into the MAC driver or computation
(`hmac_sw.c`, `hmac_hw.c`, `mac_sha3_hw.c`; see README "fault window"); the
hardware engine has its own gate-level analysis in `secboot_hw`.

### Using the hardware verdict (proposed, not built or measured here)

With `EXPECTED` and `TOKEN`, the ROM need not decide in software: the SoC can
drive the `EXEC_EN` flop from `boot_token` (set only when it equals
`FLASH_EXEC_KEY`), or the ROM can write the value read from `TOKEN` to
`SYSCTRL.EXEC_EN`. Then the instruction-level attacks on the software compare
measured here have nothing to hit, and the decision moves to the gate-level
analysis. For this to hold, the ROM must not contain the constant
`0xA5C3_B007` (today `rom_jump` in `crt0.S` loads it as an immediate, so a PC
fault that reaches `rom_jump` unlocks flash), and one register bit flip on a
loaded rejected token must not turn it into the key (the infection should
change several token bits). Today all `rom_*.c` variants still compare `mac[]`
in software and ignore `VERDICT`/`TOKEN`.

## Image format (FLASH, little-endian)

| Offset | Field | Rule checked by the ROM |
|---|---|---|
| `0x00` | `magic` | must be `0x4942_5347` (`"GSBI"`) |
| `0x04` | `version` | must be `>= OTP.MIN_VERSION` |
| `0x08` | `length` | payload bytes: `<= 1024`, multiple of 4 |
| `0x0C` | `entry` | `< length`: offset of the first instruction in the payload |
| `0x10` | `mac[32]` | SoC (`-sha3` builds): `SHA3-256(K136 || bytes 0x00..0x0F || payload[0..length) || zeros up to 1088 B)`; legacy `-hw` / `-sw` builds: `HMAC-SHA-256(key, bytes 0x00..0x0F || payload[0..length))` |
| `0x30` | payload | code/data of the next stage |

`faultsim/image.py` builds images with Python's `hashlib`/`hmac` (`compute_mac`,
independent of the C code and of the engine models).

## Boot flow (all variants)

1. `magic` check, then `length`/`entry` bounds (before any hashing, so a huge
   `length` cannot make the hash read past flash).
2. `mac_image(length, mac)`: the tag over header bytes `0x00..0x0F` and the payload,
   with the OTP key: SHA3-256 engine (`mac_sha3_hw.c`, which also writes the header
   `mac` to `EXPECTED`), or HMAC-SHA-256 (`hmac_hw.c` engine model, `hmac_sw.c` software).
3. Anti-rollback: `version >= MIN_VERSION` (from OTP).
4. MAC compare with `mac[]` in the header (8 words).
5. `rom_jump(0x2000_0030 + entry)`: `EXEC_EN = FLASH_EXEC_KEY`, `BOOT_STATUS = BS_JUMP`, `jr`.

Any failed check: `BOOT_STATUS = 0x8000_0000 | reason` (halt). Any redundant check
that disagrees: `ALARM = reason` (halt), or `unimp` (trap) in the assembly checks.

## Outcomes the simulator reports

`image_runs` (first fetch from FLASH; with a tampered image this is the attacker's
success, and any FLASH address counts because the attacker controls all of
flash), `reject`, `alarm`, `trap`, `timeout`.
