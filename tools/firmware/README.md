# Secure-boot ROM firmware under instruction-level faults

All results on this page are **MEASURED** on a simulator (`rv32sim`, a pure-Python
model of an RV32IMC core). They are **not** measurements on silicon. Fault
counts are counts of modelled faults, not of physical glitches.

## In plain words

A secure-boot ROM is the first code a chip runs. It reads the next program
(the "image") from flash, checks that it carries a valid tag (a MAC computed
with a secret key), checks that it is not an older version than allowed
(anti-rollback), and only then jumps to it.

An attacker who can disturb the chip for a moment (a voltage or clock glitch)
may make the processor skip an instruction or take a wrong branch. If that
happens at the right moment, a tampered image runs anyway.

This folder contains our own boot ROM written in C in nine versions, from a
plain one to versions with the usual software counter-measures (checks done
two or three times, a complemented copy of each decision, a step counter, an
"infective" compare that spoils the jump address, random delays, and one that
combines all of them). Each version is compiled with clang at four
optimisation levels (`-O0`, `-O1`, `-O2`, `-Os`) and in three C styles
(ordinary C, `volatile`, and an assembly "barrier" that hides values from the
optimiser). Each of the 108 resulting programs runs on the simulator, and a
search tries every placement of 1, 2 and (for skips and branch inversions) 3
faults to find the **smallest
number of faults that makes a tampered image run**.

What we found, in short:

- **One fault is enough in most builds.** In 90 of the 108 builds a single
  fault boots the tampered image; every build falls to one fault at `-O0`.
  Only two builds resist two faults of every model (`rom_compl` at `-O2` in
  ordinary C, `rom_hardened` at `-O2` in the barrier style). The strongest
  single fault in our models is a small jump of the program counter (a few
  bytes), which steps over a whole check.
- **The compiler removes counter-measures written in plain C.** At `-O2`, the
  three MAC compares of the triple-check version become one compare and both of
  its MAC alarm branches disappear, so one skipped branch boots the tampered
  image (at `-O1` it takes two). The equal-word count of the constant-time
  version and its alarm are removed at `-O2`, and the infective multiply is
  removed from `-O1` on. The `volatile` and barrier styles keep these
  checks.
- **Keeping the checks is not the same as being strong.** With the checks kept
  (barrier style), the combined version resists three skips and three branch
  inversions at `-O1`, `-O2` and `-Os`, but two register-bit flips or two small
  program-counter jumps still win at `-O1` and `-Os`, and one fault of several kinds wins at `-O0`.
- **Random delays help only against an attacker who must fix the fault time in
  advance:** one skip at a fixed time worked for 32 of 32 random seeds without
  delays, and for 3 to 6 of 32 with them (`-O0`, `-O1`, `-Os`).
- **The hardware-matching hash path behaves the same.** Builds with the
  SHA3-256 engine driver of the hardware design agree with the HMAC-engine
  builds in 279 of 286 comparable searches (see "Interface change" below).
- **The hardware result has the same shape.** In the GlitchSAT hardware study,
  three compare copies with separate result bits (V2) needed 3 flips while one
  or two copies sharing one wire (V0, V1) needed 1. In software, three copies
  reach 3 skips only when the compiler is stopped from merging them.

The tables below and in [`results/TABLES.md`](results/TABLES.md) give every number.

## Headline: minimum faults that boot a tampered image

**Ordinary C** (minimum over skip, branch inversion, register bit flip, small PC offset; 36 builds each):

| variant | -O0 | -O1 | -O2 | -Os |
|---|---|---|---|---|
| rom_naive | 1 | 1 | 1 | 1 |
| rom_double | 1 | 2 | 1 | 1 |
| rom_triple | 1 | 2 | 1 | 2 |
| rom_compl | 1 | 1 | >2 | 2 |
| rom_ctres | 1 | 1 | 1 | 1 |
| rom_cfi | 1 | 2 | 1 | 2 |
| rom_delay | 1 | 1 | 1 | 1 |
| rom_infective | 1 | 1 | 1 | 1 |
| rom_hardened | 1 | 2 | 2 | 1 |

**`volatile` style** (minimum over skip, branch inversion, register bit flip, small PC offset; 36 builds each):

| variant | -O0 | -O1 | -O2 | -Os |
|---|---|---|---|---|
| rom_naive | 1 | 1 | 1 | 1 |
| rom_double | 1 | 2 | 1 | 1 |
| rom_triple | 1 | 1 | 2 | 2 |
| rom_compl | 1 | 1 | 1 | 1 |
| rom_ctres | 1 | 1 | 1 | 1 |
| rom_cfi | 1 | 1 | 1 | 2 |
| rom_delay | 1 | 1 | 1 | 1 |
| rom_infective | 1 | 1 | 1 | 1 |
| rom_hardened | 1 | 1 | 1 | 1 |

**Barrier style (asm value barrier)** (minimum over skip, branch inversion, register bit flip, small PC offset; 36 builds each):

| variant | -O0 | -O1 | -O2 | -Os |
|---|---|---|---|---|
| rom_naive | 1 | 1 | 1 | 1 |
| rom_double | 1 | 1 | 1 | 1 |
| rom_triple | 1 | 1 | 1 | 1 |
| rom_compl | 1 | 1 | 1 | 1 |
| rom_ctres | 1 | 1 | 1 | 1 |
| rom_cfi | 1 | 2 | 1 | 2 |
| rom_delay | 1 | 1 | 1 | 1 |
| rom_infective | 1 | 1 | 1 | 1 |
| rom_hardened | 1 | 2 | >2 | 2 |

**Instruction skip only, barrier style** (the classic glitch model; search up to 3 skips):

| variant | -O0 | -O1 | -O2 | -Os |
|---|---|---|---|---|
| rom_naive | 1 | 1 | >3 | 1 |
| rom_double | 2 | 2 | 2 | 2 |
| rom_triple | 2 | 3 | 3 | 3 |
| rom_compl | 1 | 1 | 1 | 1 |
| rom_ctres | 2 | 3 | 3 | 3 |
| rom_cfi | 2 | 2 | >3 | 2 |
| rom_delay | 1 | 1 | >3 | 1 |
| rom_infective | 1 | 2 | 2 | 2 |
| rom_hardened | 1 | >3 | >3 | >3 |

Reading a cell: `1` = one fault suffices; `2`, `3` = fewer do not work in any
of the four models; `>2` = no attack with two faults in any model (the search
for skip and branch inversion went to 3; register flip and PC offset to 2);
`>=k (k not completed)` = the search stopped at its time budget, so the cell
says only that fewer than k do not work. Each search uses one fault model at a
time; mixtures of models were not searched.

## Interface change (2026-11-21): SHA3-256 engine of the hardware design

After the independent review of the hardware design (`secboot_hw`), the SoC's
MAC engine is that design's SHA3-256 engine, and the firmware's hardware-hash
path now matches it ([`INTERFACE.md`](INTERFACE.md), "MAC engine window"):

- new driver `src/mac_sha3_hw.c` (build suffix `-sha3`): the message is padded
  with zero words to 8 blocks (1088 B, read from the `INFO` register), the
  header `mac` is written to the new `EXPECTED[0..7]` registers at
  `0x60`..`0x7C`, and the tag is `SHA3-256(K136 || message)`;
- the engine window is 128 B (`0x5000_0000`..`0x5000_007F`) in `src/mmio.h`,
  `rv32sim/cpu.py` and `INTERFACE.md`; `VERDICT`, `TOKEN` and `INFO` are decoded;
- `faultsim/image.py` computes the matching `mac` (`compute_mac(..., mac="sha3")`);
- `tests/test_boot.py` replays the driver's bus writes on the hardware's own
  register model (`secboot_hw/model/mmio_model.py`): same digest, ACCEPT and
  release token for a good image, REJECT for a tampered one.

The main fault matrix was recorded with the earlier HMAC-SHA-256 engine model
(`-hw` builds), which is kept unchanged, so no recorded result changes. The 108
`-sha3` builds were searched on a subset (plain and barrier styles; skip and
branch inversion up to 2 faults, register flip and PC offset 1 fault): 279 of
286 comparable searches give the same answer within that bound, 7 differ (all
single faults: a flipped return address or PC offset whose landing place
depends on where the code is linked), 2 are not comparable. The software-only
HMAC builds (`-sw`) are unchanged. In the simulator the `-sha3` engine's own
verdict is modelled ideally; the boot ROM variants still compare the MAC in
software and do not read `VERDICT` or `TOKEN` yet.

## What exactly was measured

- **Machine.** RV32IMC, one instruction per step, no pipeline, caches or
  interrupts; misaligned loads and stores inside one region are performed;
  any exception halts the core (a ROM that stops on a trap). Memory map,
  registers and image format: [`INTERFACE.md`](INTERFACE.md).
- **Images.** `faultsim/image.py` builds them with Python's `hmac`, independently
  of the C code. `tampered_payload` changes one payload byte and keeps the old
  MAC; `rollback_signed_old` is validly signed but its version (4) is below the
  OTP minimum (5).
- **Success.** The core fetches an instruction from flash. Flash is
  execute-locked until the ROM writes the unlock key (`EXEC_EN`) just before
  the jump, so a corrupted return address cannot simply land in flash. Without
  that lock, one flipped bit of a return address reaches flash (table
  "Flash executable from reset" in `results/TABLES.md`).
- **Fault models** (applied to one executed instruction each):
  `skip` (not executed), `brinv` (conditional branch goes the other way),
  `rdflip` (one bit of the value written to the destination register flips),
  `pcoff` (next PC off by -16..-2 or +2..+16 bytes), and, as an extra, `iwflip`
  (one bit of the fetched instruction word flips; single faults only).
- **Fault window.** Every executed ROM instruction except the MAC computation
  itself (`hmac_hw.c`, `mac_sha3_hw.c` for the hash-engine builds): start-up, header checks,
  rollback test, compare, alarm and jump code. The MAC unit needs its own
  analysis (in hardware: the GlitchSAT netlist engine).
- **Search.** `faultsim/search.py`. k = 1: every single fault is tried and every
  success listed. k >= 2: depth-first search over fault positions with
  de-duplication of equal machine states (state digest, see the module
  docstring); stops at the first success. A search that ran out of its time
  budget is reported as not completed, never as "no attack". Every attack
  found was replayed on a fresh simulator and booted the image
  (`tests/test_results.py` replays all of them again).
- **Builds.** clang 18.1.3 and ld.lld, `--target=riscv32-unknown-elf
  -march=rv32imc -mabi=ilp32 -ffreestanding -nostdlib`, the variant compiled
  as its own unit (no link-time optimisation). 9 variants x 4 levels x 3 styles
  x 3 MAC units = 324 ELFs. The main matrix uses the HMAC-engine model
  (`hmac_hw.c`); the SHA3-engine builds (`mac_sha3_hw.c`) were searched on a
  subset; the software HMAC-SHA-256 builds (`hmac_sw.c`) are boot-tested only.
- **Jobs.** 1,098 searches: 756 main matrix, 288 SHA3-engine builds, 54 with
  flash executable from reset. None ended at its time budget (three that did at
  150 s were re-run with 1,200 s and completed). Summed search time 1.7 h.

## Firmware next to the hardware V0/V1/V2

The hardware figures are quoted from GlitchSAT `docs/NUMBERS.md` (status there:
MEASURED); they were not re-run here.

Firmware cells: -O0 / -O1 / -O2 / -Os. 'four models' = minimum over skip, branch inversion, register flip, PC offset; 'skip' = instruction skip only (k <= 3).

| hardware | min flips (NUMBERS.md ids) | firmware | plain, four models | barrier, four models | plain, skip | barrier, skip |
|---|---|---|---|---|---|---|
| V0, one check | 1 (B2.v0v1) | rom_naive | 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 | 1 / 1 / >3 / 1 | 1 / 1 / >3 / 1 |
| V1, two checks joined by one AND gate | 1 (B2.v0v1) | rom_double | 1 / 2 / 1 / 1 | 1 / 1 / 1 / 1 | 2 / 2 / >3 / 2 | 2 / 2 / 2 / 2 |
| V2, three checks with separate output bits | 3 (stored netlist, full 8-bit word goal); 2 after re-synthesis with apt Yosys 0.33; 1 if only the boot_ok flag must be forced (B2.v2.spike.word, B2.v2.apt, B2.v2.conda, B2.v2.ok) | rom_triple | 1 / 2 / 1 / 2 | 1 / 1 / 1 / 1 | 2 / 2 / 1 / 2 | 2 / 3 / 3 / 3 |

The units differ. A hardware flip is one single-cycle bit flip on one net of an
8-bit toy netlist (6 cycles, at most 3 flips). A firmware fault is one
disturbed instruction. What carries over is the pattern: redundancy helps only
if the copies stay separate all the way to the decision. In hardware, V1's two
checks share one AND gate and one flip there wins; in firmware, the compiler
merges the three C-level compares at `-O2` and one skip wins. Separate copies
(V2; barrier-style `rom_triple`) push the skip/flip count to 3, and then a
different, stronger fault (a PC jump) is the cheapest way in.

## Other findings (all MEASURED, details in `results/TABLES.md`)

- **Flash executable from reset.** Without the `EXEC_EN` lock, 51 of 54
  single-fault searches (`-O2`, plain and barrier; register flip, PC offset,
  instruction-word flip) boot the image, against 24 of 54 with the lock. In all
  18 builds one flip of bit 29 of a return address points it into flash.
- **Unrolled compares.** At `-O2` the 8-word MAC compare is unrolled into 8
  branches. A tampered payload changes every MAC word, so skipping branches
  needs 8 skips; skip and branch inversion find nothing up to 3 for most
  variants at `-O2`. This is a property of this attack (all words differ), not
  a counter-measure.
- **Complemented check as written is weak in two styles.** In `rom_compl`
  (volatile and barrier), skipping the single `ok != HTRUE` branch boots: the
  later check only tests that `ok` and `nok` are complements, which they are
  when both still say "false".
- **Stale stack slot.** In the volatile style, `rom_hardened` falls to one
  skipped store: the stack slot for the MAC difference still holds 0 (RAM is
  zero at reset), so every later check sees "no difference".
- **Rollback.** One skip or branch inversion boots an old, validly signed
  image in 92 of 108 builds; the double and triple checks raise it to 2
  (volatile and barrier styles) or 3 (`rom_triple` at `-O0`).

## Reproduce

Needs Python 3 (standard library only) and pytest; clang/ld.lld/llvm-objdump
only to rebuild.

```
python3 scripts/build.py                     # 324 builds -> elf/ (kept), build/ (intermediates)
python3 scripts/run_faults.py --set main -j 2   # 756 searches -> results/raw/ (skips stored ones)
python3 scripts/run_faults.py --set xip -j 2    # flash executable from reset
python3 scripts/run_faults.py --set sha3 -j 2   # SHA3-256 engine builds (hardware interface), subset
python3 scripts/run_extra.py delay           # random delays vs a fixed-time attacker
python3 scripts/run_extra.py redund          # redundancy that survives compilation
python3 scripts/summarize.py                 # results/summary.json, TABLES.md, studio_firmware.json, compare_hw.json
python3 -m pytest -q tests
```

The searches took 1.7 h of summed search time (about 1.5 h wall time on two
cores of a shared machine; machine dependent). A search holds up to 4 million
visited states in memory (about 2.5 GB); set `FW_MEMO_MAX=1500000` for
machines with less memory (results unchanged, only slower). `scripts/build.py` maps the
build directory to `.` (`-ffile-prefix-map`, `-fdebug-prefix-map`), so the ELF files hold no
absolute path and the ROM bytes, line tables and sha256 in `elf/manifest.json` do not depend
on the directory the build runs in.

## Folder

| path | what |
|---|---|
| `src/` | boot ROM sources: `rom_*.c` (nine variants), `rom.h`, `mmio.h`, `image.h`, MAC units `mac_sha3_hw.c`, `hmac_hw.c`, `hmac_sw.c`, `crt0.S`, `link.ld` |
| `elf/` | the 324 linked ROM images, their address-to-source line tables (the search needs them) and `manifest.json` (commands, sha256) |
| `rv32sim/` | the instruction-set simulator |
| `faultsim/` | images, fault search, static checks of an ELF |
| `scripts/` | build, fault runs, extra experiments, summary |
| `results/raw/` | one JSON per search (status, minimum, witness, all single-fault hits) |
| `results/summary.json` | every job and the tables; `TABLES.md` is generated from it |
| `results/studio_firmware.json` | the numbers for the Studio "Firmware" view |
| `results/compare_hw.json` | firmware variants next to hardware V0/V1/V2 |
| `results/extra_redundancy.json` | compares and OTP reads executed in a good boot |
| `results/extra_delay.json` | random delays against a fixed-time attacker |
| `tests/` | simulator validation, boot tests for every build, interface consistency, search vs brute force, stored results |
| `INTERFACE.md` | memory map, MMIO registers, image format, boot flow, hardware verdict extension |
| `build/` | compiler assembly and disassembly; not kept (`.gitignore`), recreated by `build.py` |

## Limits

- Simulator, not silicon: real glitches can corrupt several instructions,
  registers or bus transfers at once, and their effect depends on the pipeline.
  The five models are idealisations.
- One fault model per search; bounds are k <= 3 (skip, branch inversion) and
  k <= 2 (register flip, PC offset), k = 1 for instruction-word flips (main
  matrix); smaller for the SHA3-engine subset.
- The MAC computation is outside the fault window.
- Simulator modelling choices that can only hide attacks (checked by re-running the k = 1 searches with
  both changed: some hit counts rise, no minimum changes):
  - RV32C HINT encodings with `rd = 0` (`c.mv`, `c.add`, `c.lui`, `c.slli` onto `zero`) trap as
    illegal, although the ISA defines them as no-ops;
  - only `.text` is decoded, so a fetch from ROM `.rodata` traps, although ROM is `rx` in `link.ld`.
- Simplifications of the SHA3-engine model: `STATUS` omits ALARM_SEEN (bit 3) and BUSY (bit 4), and
  `VERDICT` reads 0xF0 before FINISH where the RTL gives other codes while busy. The firmware reads none of them.
- Block count: the SHA3 builds assume the SoC configuration `IMG_BLOCKS = 8` (1088 B message, `INFO`
  = `(8 << 16) | 34`). The RTL default is `IMG_BLOCKS = 2`. The driver reads `INFO` and adapts;
  `faultsim/image.py` (`SHA3_BLOCKS`, `compute_mac(..., blocks=)`) and `rv32sim/cpu.py` (`SHA3_BLOCKS`) are fixed at 8.
- `iwflip` on a 16-bit instruction also flips bits 16..31, which belong to the next halfword; those runs
  are no-ops (wasted time, no wrong result).
- The SHA3 hardware-model replay test (`tests/test_boot.py::test_sha3_engine_matches_secboot_hw_model`) is
  skipped unless `secboot_hw/` sits next to `firmware/` (or `SECBOOT_HW` points to it).
- One compiler (clang 18.1.3), one target, one tampered image and one rolled-back
  image.
- "No attack up to k" is not "secure".
