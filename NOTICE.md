# Notice

Project: GlitchSAT: How Many Glitches Does Redundancy Stop? (Bounded SAT-Based Fault Analysis of Redundant Boot Checks).
Copyright 2026 Kavin K K
Licence: Apache License 2.0 (see `LICENSE`; decision recorded in `LICENSE_CHOICE.md`). Third-party files listed below keep their own licences.

This repository does not include or redistribute the source of the external tools it drives (yosys, iverilog, verilator, z3, OpenROAD, magic, netgen, KLayout, graphviz) or the SkyWater sky130 PDK. They are installed separately and run as separate programs. See `THIRD_PARTY.md`.

Generated files under `results/`, `layout/` and `tb/generated/` contain output or banner text from those tools (for example the yosys log header with its copyright line). That text belongs to the tools' authors.

This repository does contain copied Apache-2.0 design files: `real_designs/second/src/` and `layout/second/rtl/door.v` (Digital Door Lock by Rameshwar-12, commit d05eab5, top-module name changed in the second copy) and `real_designs/fsm.v` with `real_designs/work/` (OTP design by raghul-g1322, Apache-2.0 per the earlier report, UNVERIFIED here). Their copyright belongs to their authors; see `THIRD_PARTY.md`.

`compare/synfi_run/` holds a cloned copy of another project (SYNFI) and its Python environment, used only for comparison. It is not part of this project's own code and carries its own licences (SYNFI: Apache-2.0, read from `compare/synfi_run/src/LICENSE`).

Prior work cited in `docs/PRIOR_ART.md` is referenced, not copied.

`third_party_derived/` (local only; NOT part of any shipped bundle; the owner decides its fate; text) holds: a z3 re-implementation of the FIRMER/CLEAVE checks (`firmer_cleave/fm_*.py`); a patch against the CLEAVE source (`firmer_cleave/patches/`), whose origin (S3L-official/CLEAVE) has NO licence file; and a modified copy of `fault_rtlil.cc` from CEA-LIST/uArchiFI under LGPL-2.1 (licence text kept beside it). So this repository is not free of third-party-derived source while that folder exists. Details: `THIRD_PARTY.md`.

Update 2026-11-20 (owner-authorised third-party tool run, `research/c5/run2/RUN2_REPORT.md`): `third_party_derived/uarchifi_kfrp_fiver/` additionally holds the uArchiFI plugin source (CEA-LIST/uArchiFI @8a2d792f, LGPL-2.1), a k-FRP run configuration and its origin note (CEA-LIST/Fault-Resistant-Partitioning @75929f60, Apache-2.0), and run scripts; FIVER (Chair-for-Security-Engineering/FIVER @176a1db7, custom NON-COMMERCIAL licence) was NOT built or run and none of its code is held. The whole `third_party_derived/` folder stays local and is excluded from every bundle; do not redistribute it.
