# Secure-boot hardware: specification

This is the specification of `rtl/secboot_core.v` (and the parts it instantiates) and of the experiment wrappers
in `rtl/tops/`. `model/spec.py` holds the same constants in machine-readable form, and
`model/secboot_model.py` is an executable, cycle-accurate version of this text: one `Core.step()` is one rising
clock edge of the RTL. Where this page and the model disagree, that is a bug in one of them.

Labels used here: **EXACT** (follows from the RTL as written, checked by the Python tests), **ESTIMATE** (an
expectation that has not been measured), **NOT RUN** (needs the cloud run, `cloud/cloud_run.sh`).

## 1. Scope

The core decides whether a boot image may run. It hashes key blocks and image blocks with a keyed sponge,
compares the tag with an expected value, and walks a finite-state machine to ACCEPT or REJECT. Every
countermeasure is a build parameter, so the same source gives an unprotected version and several protected ones.
The goal of the project is to measure, with GlitchSAT, how many modelled single-cycle bit flips each version needs
before it accepts a wrong image.

Language rules (checked by `tests/test_rtl_static.py`): Verilog-2005 only (no SystemVerilog), readable by Yosys
0.33 `read_verilog`; one clock `clk`, every `always` block is `@(posedge clk)` or `@(*)`; synchronous reset and
clear only; every flip-flop has an `initial` value equal to its reset value (GlitchSAT starts every flop at its
`init` attribute); no memories, no latches.

## 2. Parameters

| Parameter | Values | Meaning |
|---|---|---|
| `W` | 1, 2, 4, 8, 16, 32, 64 | Keccak lane width; state = 25 W bits |
| `RATE_LANES` | 1..24 | rate r = `RATE_LANES` x W bits = one key or image block (r >= 4) |
| `TAG_LANES` | 1..`RATE_LANES` | tag = the first `TAG_LANES` lanes of the state after the last block |
| `NR` | 0..12+2 log2 W | rounds per block; 0 = full Keccak-f (the last `NR` rounds of Keccak-f are used, as Keccak-p in FIPS 202 3.3) |
| `KEY_BLOCKS`, `IMG_BLOCKS` | >= 1 | blocks absorbed: key blocks, then image blocks, then one pad block |
| `HASH_EN` | 0, 1 | 0: no hash engine, the tag comes from port `tag_in` (decision-only experiments) |
| `HASH_COPIES` | 1, 2 | number of independent hash engines |
| `CMP_MODE` | 0..3 | 0 single compare; 1 duplicated, ANDed; 2 triplicated, owned bits; 3 complemented pair, owned bits |
| `FLAG_MUBI` | 0, 1 | compare result registers: 1 bit per copy, or a 4-bit multi-bit boolean per copy |
| `SEPARATE` | 0, 1 | 1: each compare copy is its own `sb_cmp` instance; 0: written inline (synthesis may merge copies) |
| `ALARM_EN` | 0, 1 | alarm path (section 7) |
| `INFECT_SPREAD` | 0..3 | infection of the release token (section 9): token bits disturbed per wrong tag bit |
| `CFI_EN` | 0, 1 | step counter with complemented copy (section 8) |
| `OTP_REG` | 0, 1, 2 | expected tag: 0 constant wires; 1 one shadow register per rail; 2 one shadow register per consumer |
| `EXP_SRC` | 0, 1 | where the expected tag comes from: 0 the parameter `EXP_TAG` (every experiment); 1 port `exp_in`, loaded on `exp_load` (bus front end; needs `OTP_REG >= 1`), section 10 |
| `TKW` | 1..tag width | token width |
| `KEY`, `EXP_TAG`, `TOKEN` | constants | MAC key blocks (block j = bits r j .. r j + r - 1), expected tag, release token |

Derived values (same names as the Verilog localparams and the properties of `model.spec.Cfg`):
`R = RATE_LANES*W`, `TAG = TAG_LANES*W`, `B = 25*W`, `NABS = KB + IB + 1` blocks
(`KB`, `IB` are 0 when `HASH_EN = 0`), `NRC` = cycles in HASH per block (`NR_E`, or 1 when `HASH_EN = 0`),
`NC` = compare copies (1, 2, 3, 2 for `CMP_MODE` 0..3).

## 3. State encoding

Seven states in an 8-bit register `st`. The codes are words of the [8,4,4] extended Hamming code with weight 4,
chosen and checked exhaustively by `tools/encoding_analysis.py` (EXACT):

| State | Code | | State | Code |
|---|---|---|---|---|
| IDLE | `0xF0` | | ALARM | `0x5A` |
| LOAD | `0xCC` | | ACCEPT | `0x96` |
| HASH | `0xAA` | | REJECT | `0x69` |
| COMPARE | `0x66` | | | |

- Any two codes differ in at least 4 bits (3-bit binary: 1; one-hot: 2).
- ACCEPT and REJECT are complements (distance 8): the decision drives all 8 state bits.
- No other pair is a complement pair.
- For every compare mode, a partial decision (some copies say "match", the others not) gives an invalid code
  (`0x04 0x20 0x3C 0x4D 0xB2 0xC3 0xDF 0xFB`), never a valid one.

`st` and the output register `rel` carry `(* fsm_encoding = "none" *)`, so the full `synth` flow does not extract
and re-encode the state machine.

## 4. Flow and timing

With `start` high and image blocks valid (EXACT; cycle 0 = first cycle with `st = IDLE` and `start = 1`):

```
IDLE -> LOAD -> HASH x NRC -> (LOAD -> HASH x NRC) x (NABS-1) -> COMPARE (cph = 0) -> COMPARE (cph = 1) -> ACCEPT | REJECT
```

- IDLE with `start`: clear (hash state, result flags, token, step counter; shadow registers load the expected
  tag), go to LOAD.
- LOAD: absorb the block (state XOR block) when it is available (key and pad blocks always are; an image block
  needs `blk_valid`, and `blk_ready` is high meanwhile), go to HASH.
- HASH: one round per clock, `rnd` from `RND_FIRST` to `RND_LAST`; then the next LOAD, or COMPARE after the pad
  block.
- COMPARE phase 0 (`cph = 0`): every compare copy's result is captured into its flag register; the token register
  takes `TOKEN xor infection`.
- COMPARE phase 1: the decision word `dec` (section 6) is written into `st`.
- ACCEPT, REJECT, ALARM and every invalid code hold. In REJECT the token is cleared.
- `boot_word` = `rel`, a registered copy of `st` (ALARM when the alarm condition holds). A consumer releases the
  boot only when `boot_word == 0x96`.

The verdict appears on `boot_word` at cycle `1 + NABS (1 + NRC) + 3` (`Cfg.cycles_to_word()`): 6 for the
decision-only experiments, 13 for the small hash experiments, 49 with full rounds, 104 at full size.

## 5. Hash/MAC engine (`rtl/sb_hash.v`, `rtl/sb_keccak_round.v`)

- One round of Keccak-p[25 W] per clock: theta, rho, pi, chi, iota of FIPS 202 section 3.2, written from the
  standard; constants are re-derived from the FIPS 202 algorithms by `model/keccak.py` and compared with the
  Verilog text by the tests. Round index 24..31 (reachable only by a fault on `rnd`) uses round constant 0.
- MAC: tag = first `TAG` bits of the sponge state after absorbing the key blocks, the image blocks and the pad
  block (SHA-3 suffix `01`, then pad10*1). With `W = 64`, `RATE_LANES = 17`, `TAG_LANES = 4`, full rounds this is
  SHA3-256(key blocks || image blocks) (prefix MAC; sound for SHA-3 because the sponge has no length extension).
  It is not a named standard construction; the standard keyed SHA-3 alternative is KMAC256 (NIST SP 800-185),
  which would add the `bytepad`/`encode_string` framing and the cSHAKE domain separation in front of the key.
- Known-answer test (`tb/gen/tb_kat.v`, values checked against `hashlib` by `tests/test_kat.py`): Keccak-f[1600]
  of the zero state (lane 0 = `F1258F7940E1DDE7`), SHA3-256("") and SHA3-256("abc") on the full-size engine, and
  the small engine of the hash experiments against the model.
- Small experiment engines (`W = 2`, rate 8 bits, tag 8 bits, 2 rounds) are size knobs for the solver, not a
  security level.

## 6. Redundant compare and what stays shared

Compare copy c reads tag `tagc[c]` and expected value `expc[c]`:

| `CMP_MODE` | copies | raw result | who decides state bit i |
|---|---|---|---|
| 0 single | 1 | `tag == exp` | copy 0, all bits |
| 1 duplicated | 2 | `tag == exp` (both) | AND of the two copies, one AND gate per bit |
| 2 triplicated | 3 | `tag == exp` | copy `i mod 3` only (bits 0,3,6 / 1,4,7 / 2,5) |
| 3 complemented | 2 | copy 0 `tag == exp`; copy 1 `(~tag) != ~exp` (1 = mismatch) | copy `i mod 2` |

Result flags: with `FLAG_MUBI = 0` one bit per copy (complement rail stores 0 for "match"); with `FLAG_MUBI = 1`
four bits per copy, `0x6` = true and `0x9` = false (`0x9` = "match" on the complement rail), and state bit i
reads flag bit `i mod 4`. A flag value that is neither true nor false counts as "no match" in the decision and
raises the alarm (section 7). Reset value of every flag is "no match".

Decision: `dec[i] = (says_match(owner(i)) AND cfi_ok) ? ACCEPT[i] : REJECT[i]`.

With `SEPARATE = 1` every copy is an instance of the `(* keep_hierarchy *)` module `sb_cmp`; the repository
`synth.sh` maps each module before it flattens and runs no `opt_merge` afterwards in the plain flow, so the copies
stay separate gates. With `SEPARATE = 0` the copies are inline expressions and the tool may merge them; the
`*_inline` experiments measure what that does.

The complemented rail (`d_compl`, `CMP_MODE = 3`) is not diverse logic. `|((~tag) ^ ~EXP)` equals
`|(tag ^ EXP)` after constant propagation, so with `OTP_REG = 0` copy 1 is the same gates as the true compare
plus an inverter, and with `SEPARATE = 0` synthesis can merge the two. What differs between the rails is only the
stored flag value (and, with `OTP_REG >= 1`, the shadow register that holds the complement).

Shared by every copy (single points by construction; the experiments show whether they matter):
the FSM registers `st`, `blk`, `rnd`, `cph`; the block selector inputs; the tag input `tag_in` (decision-only)
or the hash engine (when `HASH_COPIES = 1`); the expected value when `OTP_REG = 1`. With `HASH_COPIES = 2`
compare copy c reads engine `c mod 2` and the infection path reads the last engine; both engines are driven by
the same FSM.

## 7. Alarm (`ALARM_EN = 1`)

`alarm` is high (combinational) when any of these holds:
- `st` is not one of the seven codes;
- `st == ACCEPT` but the flags are not all "true" (accept without evidence);
- in COMPARE phase 1 the flags are neither all "true" nor all "false";
- some flag holds a value that is neither its "true" nor its "false" code;
- with `CFI_EN`, a step-counter check fails (section 8).

On alarm: `st <= ALARM`, `rel <= ALARM`, token cleared. ALARM holds until reset.

## 8. Step counter (`CFI_EN = 1`)

A counter `step` and its complement `step_n` count every LOAD-with-absorb, HASH and COMPARE cycle from the
clear. `cfi_ok = (step == EXP_STEPS - 1) and (step xor step_n == all ones)`, with
`EXP_STEPS = NABS (1 + NRC) + 2`. The decision gives ACCEPT only with `cfi_ok`; alarm conditions: the copies
disagree, or `st == ACCEPT` with `step != EXP_STEPS`, or COMPARE phase 1 with `step != EXP_STEPS - 1`. A skipped
or repeated step therefore gives REJECT (or ALARM with `ALARM_EN`).

## 9. Release token and infection

`boot_token` carries `TOKEN` after COMPARE phase 0 and is cleared in REJECT and on alarm. With
`INFECT_SPREAD = s > 0` every wrong tag bit j (tag xor expected, on the infection path's own tag and expected
value) flips token bits `(j + t) mod TKW` for taps t in (0, 1, 3)[:s]. A forced ACCEPT with a wrong tag then
releases a wrong token. The `*_infect` and `*_all` experiments use the goal `{boot_word, boot_token} ==
{0x96, TOKEN}`. In the SoC the token is the flash execute key (`0xA5C3B007`, see INTERFACE.md), so a wrong token
leaves flash non-executable.

## 10. Key and expected digest (OTP)

The MAC key blocks are the synthesis parameter `KEY` (modelled as constant wires; no fault on a constant). There
is no OTP key port: a build for the SoC sets `KEY` to the OTP provisioning value. An OTP key port is future work.

The expected tag is either constant wires (`OTP_REG = 0`) or held in shadow registers: `OTP_REG = 1` one register
per rail (true, and complement for `CMP_MODE = 3`), shared by all copies; `OTP_REG = 2` one register per consumer
(each compare copy and the infection path). Shadow registers reset to 0. Where the value comes from (`EXP_SRC`):

- `EXP_SRC = 0` (all fault experiments, `d_*` and `h_*`): the synthesis parameter `EXP_TAG`, loaded on the start
  clear. The expected tag is then fixed at synthesis: one chip build accepts exactly one image.
- `EXP_SRC = 1` (default of the bus front end `secboot_mmio`): port `exp_in`. The shadow registers are cleared on
  the start clear and loaded from `exp_in` (complemented for the complement rail) when `exp_load` is high; the
  start clear wins if both happen in one cycle. The pad block (the last absorb) waits in LOAD until `pad_ok` is
  high, so the compare can never use a value from before the load. In `secboot_mmio`, `exp_in` is the
  `EXPECTED[0..7]` registers, `exp_load` is FINISH and `pad_ok` is "FINISH seen" (INTERFACE.md). The step counter
  counts only absorbing LOAD cycles, so the wait does not disturb `cfi_ok`. The image's expected tag is then a
  value the image brings (its header `mac` field), and the key is what makes a forged image fail.

## 11. Ports of `secboot_core`

| Port | Dir | Width | Meaning |
|---|---|---|---|
| `clk` | in | 1 | clock |
| `rst` | in | 1 | synchronous reset |
| `start` | in | 1 | start a boot check (from IDLE) |
| `blk_valid`, `blk_data` | in | 1, R | image block handshake; absorbed when `blk_ready` and `blk_valid` |
| `tag_in` | in | TAG | tag when `HASH_EN = 0` |
| `exp_in`, `exp_load` | in | TAG, 1 | `EXP_SRC = 1`: expected tag and its load strobe (section 10); not read with `EXP_SRC = 0` |
| `pad_ok` | in | 1 | `EXP_SRC = 1`: the pad block is absorbed only when high; not read with `EXP_SRC = 0` |
| `state` | out | 8 | `st` |
| `boot_word` | out | 8 | registered verdict (0x96 = release) |
| `boot_token` | out | TKW | release token |
| `alarm` | out | 1 | alarm condition (combinational) |
| `blk_ready`, `busy`, `done` | out | 1 | handshake / status |
| `dbg_tag` | out | TAG | tag seen by compare copy 0 (the MMIO DIGEST window) |

## 12. Experiments (`model/variants.py`, `rtl/tops/`)

Each experiment wraps one configuration in `top_<name>` with exactly one attacker input and one goal output, as
`scripts/glitchsat.py` requires: `clk`, `sig[7:0]` (free, held constant, must differ from the key `0xC3`), and
`boot_word` (goal `0x96`) or `boot_grant = {boot_word, boot_token}` (goal `0x96B7`). Inside: `rst = 0`,
`start = 1`, `blk_valid = 1`, `EXP_SRC = 0` (`exp_in = 0`, `exp_load = 0`, `pad_ok = 1`). Decision-only experiments (`d_*`, `W = 2`, tag 8 bits) feed `sig` to `tag_in`,
expected tag `0xC3`. Hash experiments (`h_*`, `W = 2`, rate 8, tag 8, 2 rounds, one key block, one image block)
feed `sig` as the image block; the MAC key `0x5A` is chosen so that image `0xC3` is the only 8-bit image with its
tag `0x79` (otherwise a plain collision would be reported as a 0-flip attack). The solver depth is the accept
cycle + 2: 8 cycles (`d_*`), 15 (`h_*`), 51 (`h_*_full`, run only with `LARGE=1`).

Register bits in each goal cone (EXACT, `Variant.flop_bits()`): from 24 (`d_single`) to 81 (`d_all`), 75
(`h_single`) to 184 (`h_all`). Gate counts are NOT RUN. ESTIMATE: tens to a few hundred gates for the `d_*`
designs and several hundred to about two thousand for the `h_*` designs; the earlier benchmark report put a
2040-gate design at about a minute for a k = 1 "no attack" answer at 4 cycles, so the `h_*` runs at 15 cycles may
need the 30-minute timeout or more.

## 13. Verification

| What | How | Status |
|---|---|---|
| Keccak model vs `hashlib` SHA3-256/512, SHAKE128; lane vs bit-level versions, all widths | pytest | EXACT, runs here |
| State-code rules | `tools/encoding_analysis.py`, pytest | EXACT, runs here |
| Every variant: key boots at the predicted cycle; all 255 other inputs never reach the goal (fault-free) | pytest | EXACT, runs here |
| RTL constants, Verilog-2005 subset, sync resets, power-up values, wrapper ports | pytest (text checks) | runs here |
| RTL = model, cycle by cycle, with injected register flips (about 45 scenarios per variant) | `tb/gen/tb_<name>.v` + `vectors/<name>.vec`, Icarus | NOT RUN |
| Hash engine known answers | `tb/gen/tb_kat.v`, Icarus | NOT RUN |
| MMIO front end = `model/mmio_model.py` | `tb/gen/tb_mmio.v` + `vectors/mmio.vec`, Icarus | NOT RUN |
| Synthesised netlist = model (same vectors, gate level) and flop count | `engine/netsim.py` | NOT RUN |
| Minimum flips, k = 1..3, plain and opt flows | `scripts/glitchsat.py` via `engine/run_glitchsat.py` | NOT RUN |

## 14. Limits

- Faults are the GlitchSAT model: single-cycle bit flips of gate outputs and flop outputs. No stuck-at, no
  multi-bit spatial faults, no clock or voltage effects, no physical feasibility.
- Results will be bounded (k flips, fixed number of cycles) and specific to one netlist from one Yosys version.
- The attacker input is constant for the whole run; the image cannot change between blocks.
- The experiment sizes (8-bit tag, 50-bit state, 2 rounds) are chosen for solver run time; they say nothing about
  the cryptographic strength of the full-size MAC.
