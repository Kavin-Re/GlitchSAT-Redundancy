# Shared interface: physical fault models of GlitchSAT

Two software models give GlitchSAT a second fault model, closer to the physical mechanism, for its
abstract single-cycle bit-flip attacks (a timing-based one and a spatial one), on the **same** placed
sky130 designs. Both are SIMULATED, with ASSUMED delays or ASSUMED spot rules; neither is a measurement:

| Mechanism | Folder | What it models |
|---|---|---|
| `clock_glitch` | `tools/vlab` (this lab) | shortened clock period / supply droop -> **setup-timing violations** at flop capture |
| `laser_em` | `tools/shots` | laser / EM **single-event upsets** located in the placement |

Both reduce a physical attack to the object GlitchSAT already reasons about: at one or more cycles a set
of the **8 state flip-flops** (boot_word bit *i* = flop *i*) takes a wrong value, and the boot check does
or does not accept a wrong key. Shared constants (identical to `tools/shots/shotmodel`):
`KEY = 0xC3`, `GOOD = 0x96`, `INIT = 0xF0`; flops ordered by the boot_word bit they drive.

## Schema `physical-fault-campaign/1`

Emitted by `vlab.interface.from_vlab_campaign(...)` (see `results/<design>_shared.json`); the spatial
model emits the same shape so the comparison consumes both uniformly.

```
{
  "schema": "physical-fault-campaign/1",
  "mechanism": "clock_glitch" | "laser_em",
  "design": "v1", "top": "v1",
  "key": 195, "good": 150, "init": 240,          # 0xC3 / 0x96 / 0xF0
  "realizable_wrong_key_accept": bool,           # did this mechanism accept a wrong key anywhere?
  "min_cost": number|null,                        # cheapest successful knob value, or null
  "cost_unit": "glitch_period_ps" | "shot_radius_um" | null,
  "realized_flip_sets": [                         # flop-flip sets this mechanism's simulation produced
    { "cycle": int, "flops": [int 0..7], "sig": "0x..|null", "outcome": "SUCCESS" }
  ],
  "honesty": "SIMULATION, not measurement",
  "extra": { ... mechanism-specific ... }
}
```

`vlab.interface.validate(record)` checks the required fields and that every flop index is 0..7.

## How GlitchSAT / Studio uses it
- `realized_flip_sets` is in **abstract-flip space**, so each entry can be matched directly against a
  GlitchSAT witness (`results/reproduce/*.json` `faults[].net/cycle`, restricted to flop sites).
- `realizable_wrong_key_accept = false` with an empty `realized_flip_sets` means *the simulated campaign
  of this mechanism produced no wrong-key accept* on that design (for vlab: V1/V2, ASSUMED delays, the
  offset x period grid of the campaign). It is a result of that sweep, not a proof for other delays.

## The full campaign schema `vlab-glitch-campaign/1`
`results/<design>_campaign.json` additionally carries the whole offset × period sweep (`cells[]` with
per-outcome `counts`), the static-timing per-flop arrivals (`sta_flop_arrival_ps`), the clock-tree
latencies, and the delay-model provenance (`ASSUMED` or `SOURCED(sdf)`) — enough for Studio to draw a
"virtual glitch campaign" success/crash/no-effect map.
