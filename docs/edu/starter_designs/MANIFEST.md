# Starter designs manifest

Generated 2026-11-19 with `product/scripts/yosys_flow.sh <file>.v <top> <file>.json` (the project's documented recipe) using **Yosys 0.33 (git sha1 2584903a060)** (apt build). Regenerating on this Yosys reproduced all three JSON files byte for byte (`research/c4/edu/verification.log`). On another Yosys build the JSON may differ; use the committed JSON when you need the numbers in the answer key.

| Design | Top | What it is | netlist JSON sha256 | .v sha256 |
|---|---|---|---|---|
| `mini_v0.v` | `mini0` | One comparator for key 4'h5, 4-bit state (naive) | `5a46ec6cf0bb0b538768ee0b320b95eb2570344ba4a9f5163c65ad3fd47716da` | `c65a4eab90f42961a84614e216e7e8beb7fe97013f946a4569e50858fe9cb547` |
| `mini_v1.v` | `mini1` | Two comparators recombined by one AND `ok` | `b3b890dad575aa43a4dfe6063ed337f0dc140b3d57fb662e299b7cef4b04f550` | `023907c3b947dc2aaa7aea07b995b8a72aadb21f462a8c8264c83e06ff31fd02` |
| `mini_v2.v` | `mini2` | Three comparators, each result bit follows one copy | `dc7cee2528f36b3999ccccb27e73d467a70544ac1004230a5af51dd314aa808b` | `cd9735f9e293ebac2140c92d779298b4462e0ae351a42781c04edc1c6424b35f` |

Configs: `mini.toml` (goal word == 9, key 5, 6 cycles), `mini_bootok.toml` (goal `boot_ok` == 1), `v2_bootok.toml` (same for the 8-bit V2 in `reference/spike_netlists/`).

Measured minimum flips (MEASURED, 6 cycles, `mini.toml`): mini0 = 1, mini1 = 1 (`ok`), mini2 = 2 (45 gates). After `docs/edu/tools/synth_merge.sh` (extra `opt_merge`): mini2 = 1. Goal `boot_ok`: mini2 = 1. These are toy 4-bit designs; the numbers do not transfer to any real design.
