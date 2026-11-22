# Third-party components

Copied third-party design files (Apache-2.0, listed at the bottom) are in the folder. The project's own code (outside `third_party_derived/`, see the last section) is not a copy of any third-party source; `third_party_derived/` does hold third-party-derived material. Licences marked "verified" were read from installed packages on 2026-11-19; the rest are UNVERIFIED. Details and consequences: `LICENSE_CHOICE.md`.

## Needed for the CI / quickstart path (`make test`, `make reproduce`, `make replay`)
| Component | Version used | How obtained | Licence |
|---|---|---|---|
| yosys | 0.33 | apt | ISC (verified) |
| iverilog | 12.0 | apt | GPL-2+ (verified) |
| z3-solver | 5.4.1.0 (pinned in `ci/requirements-ci.txt`) | pip | MIT (verified) |
| pytest | >=8 (9.1.1 and 9.2.0 seen) | pip | MIT (verified) |

## Optional / nightly
| Component | Version | Used for | Licence |
|---|---|---|---|
| verilator | 5.020 | informational lint (nightly) | LGPL-3.0 or Artistic-2.0 (verified) |
| z3 binary | 5.4.1 | solver cross-checks | MIT (verified) |
| graphviz | 2.43.0 | dashboard rendering | EPL-1.0 (verified) |

## Layout flow only (not covered by CI; `scripts/setup_layout_tools.sh`)
| Component | Licence |
|---|---|
| OpenROAD | BSD-3-Clause (UNVERIFIED) |
| magic | MIT-style (UNVERIFIED) |
| netgen | MIT-style (UNVERIFIED) |
| KLayout (pip `klayout`) | GPL-3.0 (UNVERIFIED) |
| SkyWater sky130A PDK / open_pdks | Apache-2.0 (UNVERIFIED) |

## Copied Apache-2.0 design files (not this project's code)
| Files | Origin | Licence |
|---|---|---|
| `real_designs/second/src/` (`door_lock.v`, `LICENSE.apache2`, `SHA256SUMS`) | Rameshwar-12/Door_lock_system, commit d05eab5 | Apache-2.0 |
| `layout/second/rtl/door.v` | the same `door_lock.v` with only the top-module name changed | Apache-2.0 (derived, keep the notice) |
| `real_designs/fsm.v`, `real_designs/work/` (downloaded OTP design files) | raghul-g1322/tiny_hardware_authentication_tto, no commit pinned | Apache-2.0 per the earlier report; not re-read here (UNVERIFIED) |
| `real_designs/second/dl_repo/` (fetched candidate repos, not used) | various | licences not checked; remove before any release |
`real_designs/src/` does not exist.

## Present in the folder but not this project's code
`compare/synfi_run/src` (SYNFI clone; licence read from `compare/synfi_run/src/LICENSE`: Apache-2.0) and `compare/synfi_run/venv` (about 353 MB of pip packages, own licences). Excluded by `.gitignore` for the venv; keep the SYNFI licence and notices if the src clone is published.


## `third_party_derived/` (local only; NOT part of any shipped bundle; author decides)
This folder is not covered by the statements above and its status is an open AUTHOR decision (`research/c3/se/SE_REPORT.md` s2). It holds:
| Path | What | Licence status |
|---|---|---|
| `third_party_derived/firmer_cleave/` (`fm_model.py`, `fm_export_nl.py`, `fm_nl_check.py`, tests) | z3 re-implementation of the FIRMER/CLEAVE checks. Header says no code copied, re-implemented from the papers and from reading the C++ | origin S3L-official/CLEAVE (commit 0b9f052) has NO licence file; whether reading the C++ makes this derived is unclear (UNVERIFIED) |
| `third_party_derived/firmer_cleave/patches/FIRMER_extend_build_fix.patch` | a patch against the CLEAVE source | origin has NO licence file; a patch against it is a derived work of unlicensed code (highest exposure) |
| `third_party_derived/uarchifi_kfrp_fiver/uarchifi_plugin/fault_rtlil.cc` | modified copy (build fix for Yosys 0.38) of the CEA-LIST/uArchiFI file | LGPL-2.1 (`LICENSE-LGPL-2.1.txt` kept; header "2026 CEA"); the author must accept LGPL obligations |
It must be excluded from any public or submitted bundle until the author decides (see `scripts/make_bundle.sh`).


## Licences of the compared tools (S3 sweep; 2026-11-20; read from raw LICENSE files, `research/c4/sweeps/SWEEP_S3.md` s2.3)
| Tool | Licence read | Status in this folder |
|---|---|---|
| SYNFI (lowRISC) | Apache-2.0 (per-file headers not checked) | local clone `compare/synfi_run/src`; keep LICENSE and notices if published |
| uArchiFI (CEA-LIST) | LGPL-2.1 | modified `fault_rtlil.cc` in `third_party_derived/` (local only); whether a runtime-loaded Yosys plugin counts as linking is unresolved (author decision) |
| PROLEAD | BSD-3-Clause | no code in this project |
| rIC3 | BSD-3-Clause on current master (older snippets say GPL-3.0 with a possible non-commercial notice) | pin the commit actually used before quoting a licence |
| FIRMER / CLEAVE | NOT established (no licence file found at S3L-official/CLEAVE commit 0b9f052; a raw fetch returned 404, which does not prove absence) | re-implemented in `third_party_derived/` (local only) |
| VerFI (emsec) | NOT established (raw LICENSE returned 404) | not used |
| k-FRP (CEA-LIST/Fault-Resistant-Partitioning @75929f60) | Apache-2.0 (established by RUN2) | built and run locally; derived files (config, run script) in `third_party_derived/uarchifi_kfrp_fiver/` (local only, never in a bundle) |
| FIVER (Chair-for-Security-Engineering/FIVER @176a1db7) | custom NON-COMMERCIAL licence (established by RUN2): do not redistribute | not built, not run; nothing derived from it |
`third_party_derived/` stays local and is never part of a bundle (`scripts/make_bundle.sh`); whether to keep, remove or publish it is the author's decision.
