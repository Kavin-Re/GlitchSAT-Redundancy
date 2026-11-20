# Licence choice (owner decision, NOT made)

No `LICENSE` file exists on purpose. Until the owner adds one, default copyright applies: nobody else may legally reuse, fork or redistribute this code. This file lists the options. Nothing here is legal advice.

## Options

| Option | What it means | Consequences |
|---|---|---|
| **MIT** | Short permissive licence. Anyone may use, modify, sell, relicense; must keep the copyright notice. | Simplest. No patent grant. Compatible with every third-party tool used here (all are run as separate programs, not linked). |
| **Apache-2.0** | Permissive, explicit patent grant, requires keeping a NOTICE file (`NOTICE.md` is prepared) and marking changes. | Slightly more paperwork. Better if others may contribute code (patent clarity). Compatible with the pip dependencies (z3-solver MIT, pytest MIT). |
| **None yet** | Keep all rights reserved (current state). | Safe to defer; but no one can legally reuse it, and graders/forks have no permission. Dashboards or reports that are published stay "all rights reserved". |

Either permissive licence works for the files this project wrote. The folder also holds copied Apache-2.0 design files (`real_designs/second/src/`, `layout/second/rtl/door.v`, `real_designs/fsm.v`; see `THIRD_PARTY.md`); they keep their own licence and notices and must not be relabelled. Caveats: `compare/synfi_run/` contains a cloned SYNFI source tree (licence read from `compare/synfi_run/src/LICENSE`: Apache-2.0) and a 353 MB venv that are NOT this project's code; exclude them from any release.
Also decide the copyright holder name for the notice line (not guessed here).

## Third-party tools and their licences

"Verified" = read from an installed package's copyright file or metadata in this environment on 2026-11-19. UNVERIFIED = general knowledge, not checked.

| Tool | Licence | Status |
|---|---|---|
| yosys 0.33 (Debian pkg) | ISC (some bundled files GPL-2+, MIT, BSD per Debian copyright) | verified (/usr/share/doc/yosys/copyright) |
| iverilog 12.0 | GPL-2+ (some parts LGPL-2+, MIT, BSD-2) | verified |
| verilator 5.020 | LGPL-3.0 or Artistic-2.0 | verified |
| z3 binary 5.4.1 (Debian pkg) | MIT (Expat) | verified |
| z3-solver 5.4.1.0 (pip) | MIT | verified (pip metadata) |
| pytest 9.1.1 (pip) | MIT | verified (dist-info LICENSE) |
| graphviz 2.43.0 | EPL-1.0 (parts MIT, zlib-style) | verified (Debian copyright) |
| OpenROAD | BSD-3-Clause | UNVERIFIED (not installed here) |
| magic | MIT-style (Berkeley/UC licence) | UNVERIFIED |
| netgen | MIT-style | UNVERIFIED |
| KLayout | GPL-3.0 | UNVERIFIED |
| SkyWater sky130 PDK (open_pdks sky130A) | Apache-2.0 | UNVERIFIED |

Running a GPL or LGPL tool as a separate program does not make this project's inputs or outputs GPL. Any bundling or redistribution of those tools (a container image, for example) would need its own licence review.

## To finish
1. Pick an option. 2. Add the `LICENSE` file with the full text yourself. 3. Update `NOTICE.md` and the README licence line.
