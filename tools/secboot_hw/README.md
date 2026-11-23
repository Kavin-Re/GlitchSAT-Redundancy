# Secure-boot hardware for GlitchSAT

## In plain words

Before a small computer runs a program, a "boot check" decides whether the program is genuine. An attacker who
cannot forge the program may instead try to disturb the chip for an instant (a glitch) so that the check says
"yes" anyway. GlitchSAT counts how many such disturbances, modelled as single bit flips, are needed.

This folder is our own boot-check hardware, written so that it can be measured. It reads the program, computes a
fingerprint of it with a key (a MAC), compares the fingerprint with the expected one, and then says ACCEPT or
REJECT. Every protection is a switch that can be turned on or off: two or three comparators instead of one,
comparators that work on inverted data, 4-bit "yes" codes instead of a single bit, an alarm, a step counter that
notices skipped steps, and a "token" that gets scrambled when the fingerprint is wrong. Each combination becomes
one experiment, and each experiment asks the same question: how many bit flips make the hardware accept a wrong
program?

Where the key and the expected fingerprint come from: the key is fixed when the hardware is built (a synthesis
parameter; a build for the chip sets it to the provisioned key). In the fault experiments the expected
fingerprint is fixed at build time too, so such a build accepts exactly one program. The register front end used
by the firmware instead takes the expected fingerprint from the program's header through the `EXPECTED`
registers (INTERFACE.md), so one build accepts every program signed with its key.

**No fault-analysis results are in this folder yet.** The tools that produce them (Yosys, Icarus Verilog and the
z3 solver) are not installed on the machine where this was written. `cloud/cloud_run.sh` runs everything on a
cloud machine and writes the results; until then every result in the Studio panel says NOT_RUN.

## What is here

| Path | What |
|---|---|
| `rtl/secboot_core.v` | the boot controller: sparse-coded state machine, compare copies, flags, alarm, step counter, token |
| `rtl/sb_hash.v`, `rtl/sb_keccak_round.v` | keyed sponge MAC engine, one Keccak round per clock (full size = SHA3-256) |
| `rtl/sb_cmp.v` | one digest compare copy (true or complemented rail), kept as its own module |
| `rtl/secboot_mmio.v` | 32-bit register front end at the firmware's HMAC offsets (INTERFACE.md) |
| `rtl/tops/top_<name>.v` | one wrapper per experiment: `clk`, attacker input `sig`, one goal output (generated) |
| `model/` | exact Python models: Keccak (`keccak.py`), constants (`spec.py`), cycle-accurate core (`secboot_model.py`), register front end (`mmio_model.py`), experiment list (`variants.py`) |
| `vectors/`, `tb/gen/` | expected values from the model and self-checking Icarus testbenches (generated) |
| `engine/` | generators (`wrappers.py`, `benches.py`, `studio.py`), gate-level replay (`netsim.py`), cloud runner (`run_glitchsat.py`) |
| `tools/encoding_analysis.py` | exhaustive check of the state codes |
| `cloud/cloud_run.sh` | the full run on a cloud VM |
| `studio/secboot_hw.json` | Studio panel skeleton (every result empty) |
| `SPEC.md` | the specification; `INTERFACE.md` the register map and the fit with `../firmware` |

## The experiments

23 configurations (`model/variants.py`). `d_*` check a given tag (no hash engine, 8 cycles to analyse); `h_*`
also compute the MAC in hardware (15 cycles; the two `*_full` ones use all rounds, 51 cycles, and run only with
`LARGE=1`). The attacker always chooses the 8-bit input `sig`; the genuine value is `0xC3`.

| Experiment | Protection | Goal |
|---|---|---|
| `d_single` | one compare | `boot_word == 0x96` |
| `d_dup`, `d_dup_inline` | two compares ANDed per state bit; kept separate / free to merge | same |
| `d_trip`, `d_trip_inline` | three compares, each owning its own state bits; kept separate / free to merge | same |
| `d_compl` | true and inverted compare, each owning half the bits | same |
| `d_trip_mubi`, `d_compl_mubi` | as above with 4-bit result codes | same |
| `d_trip_alarm`, `d_trip_mubi_alarm` | plus the alarm | same |
| `d_trip_cfi`, `d_trip_cfi_alarm` | plus the step counter (and alarm) | same |
| `d_trip_otp1`, `d_trip_otp2` | expected value in one shared / one-per-compare register | same |
| `d_single_infect`, `d_trip_infect` | token scrambled by wrong tag bits | `{boot_word, token} == 0x96B7` |
| `d_all` | everything above | same |
| `h_single`, `h_trip`, `h_trip_2hash` | hash in hardware; one or two hash engines | `boot_word == 0x96` |
| `h_all` | hash with everything | `{boot_word, token} == 0x96B7` |
| `h_single_full`, `h_all_full` | as `h_single` / `h_all`, all rounds | as above |

All countermeasures, the state codes and the timing are specified in SPEC.md.

## Checks that run here (Python only)

```
python3 -m pytest -q tests          # about 530 tests, under 30 s
python3 tools/encoding_analysis.py  # state-code rules
```

They cover: the Keccak model against Python's `hashlib` (SHA3-256, SHA3-512, SHAKE128) and a literal bit-level
version; the state-code rules; every experiment boots with `0xC3` at the predicted cycle and never with any of the
other 255 inputs (without faults); the register front end against SHA3-256; the Verilog text (Verilog-2005
subset, synchronous resets, power-up values, constants equal to FIPS 202, wrapper ports); and that every
generated file is up to date.

After changing `rtl/` or `model/`, regenerate:

```
python3 -m engine.wrappers && python3 -m engine.benches && python3 -m engine.studio
```

## The cloud run

On an Ubuntu 24.04 cloud VM with this folder inside (or next to) the GlitchSAT repository:

```
GLITCHSAT_ROOT=/path/to/glitchsat sh tools/secboot_hw/cloud/cloud_run.sh
```

It installs `yosys` and `iverilog` (apt) and `z3-solver` (pip, in a venv), runs the tests, compiles the RTL with
`iverilog -g2005`, runs every testbench (each replays the model vectors, including injected register flips), reads
every design with Yosys, synthesises each experiment with the repository's `scripts/synth.sh` (plain and opt
flows), replays the vectors on the gate-level netlist, and runs `scripts/glitchsat.py` at k = 1, 2, 3. Options
(`KMAX`, `TIMEOUT`, `FLOWS`, `LARGE`, `ONLY`, ...) are listed at the top of the script. Output:
`cloud_out/<time>/summary.md`, `summary.json`, `studio_secboot_hw.json` and a tarball.

Size: the register counts per experiment are exact (24 to 184 bits). Gate counts and run times are unknown until
the cloud run; ESTIMATE: the `d_*` runs should take seconds to minutes each, the `h_*` runs may hit the 30-minute
timeout at k = 2 or 3. A timeout is reported as UNKNOWN, never as "no attack".

## Limits

Modelled bit flips only (gate outputs and flip-flop outputs, one cycle each); bounded results (at most k flips,
a fixed number of cycles) on one netlist; small experiment sizes chosen for solver time. See SPEC.md section 14.
