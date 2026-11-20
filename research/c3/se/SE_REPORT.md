# SE report: security / ethics / dual-use review
Working title TBD. Licence: UNDECIDED. Read-only review; nothing run in third_party_derived/. V = verified by reading the file/line named; I = inferred.

## Prioritised table
| # | Item | Type | Evidence |
|---|---|---|---|
| 1 | Decide fate of `third_party_derived/` (see s2): exclude from any public/submitted bundle, or get licences first | OWNER | V |
| 3 | Adopt a responsible-use + disclosure paragraph (s1 text) | OWNER (approve), agent drafts | V |
| 4 | Licence and copyright holder (LICENSE_CHOICE.md); also decide whether `real_designs/` Apache copies stay in a release | OWNER | V |
| 5 | Remove `real_designs/second/dl_repo/` (unused fetched repos, licences unchecked, contains a third party's personal email + LinkedIn at `v5run_DE1-SoC-ComboLock.md:115`) from any bundle | agent-can-fix (in bundle script) | V |
| 6 | Wording fixes in s4 (FINAL_STATUS "validated", "real chip layout", "prove it") | agent-can-fix (lead edits) | V |
| 7 | Pin commit for `real_designs/fsm.v` / `work/` (none pinned; licence "per earlier report", UNVERIFIED) or drop it | agent-can-fix or OWNER | V |
| 8 | Absolute paths `/home/user/...` in 258 text files (logs, handoff, tb/generated); scrub or exclude `results/deep/logs`, `handoff/`, `formal/runs` from a public bundle | agent-can-fix | V (count) |
| 9 | Handoff zips (`handoff/*.zip`, 4 bundles) and `handoff/CONTINUATION/` hold internal agent chatter and rules; exclude from public/submitted bundle | OWNER decides, agent excludes | V |
| 10 | Persona files (`docs/wow/persona_tests/P1..P6`) must stay labelled simulated | agent-can-fix | V (label present in explainer.html:205) |

## 1. Dual-use
- Capability: given a gate-level netlist, finds a minimum set of modelled single-cycle bit flips reaching a goal (V: THREAT_MODEL_ONE_PAGE.md). Uplift beyond SYNFI/FIRMER/CLEAVE/uArchiFI: I judge none that matters. Method is covered by cited prior art (V: README.md:9, FINAL_STATUS.md:13); the repo says "nothing established as new". It outputs net names and cycles, not physical parameters; no voltage/clock/laser/EM timing, no device targets, no glitch recipe (V: threat model "Not modelled"). Residual: a solver that runs on arbitrary Yosys JSON could be pointed at a real netlist (I). That is the same as SYNFI.
- Real third-party designs: `real_designs/REPORT.md` says "**This is not a finding to publish or disclose as a vulnerability.**" and "would first need a prior-art check and responsible disclosure" (V). Wording is accurate and cautious: the only result is a flip of the decision flop itself, generic. Door lock (second): 6-gate combinational comparator, password 1010 is public in the repo's own docs (V). Both are hobby Tiny Tapeout designs, not products. Small caveat: "no disclosure needed" (FINAL_STATUS.md line ~30; threat model "nothing needs disclosure") is slightly stronger than the evidence; better "no design-specific weakness was found in the bounds tried". Both tools also use author-named repos; consider whether naming the authors beside the word "attack" is wanted (I; low risk since results are generic).
- Nothing in the dashboard "Play: break the lock" game gives uplift: toy lock (V: explainer.html:184, 201 states "ILLUSTRATION").
- Recommended responsible-use statement (draft for owner):
  "This toolkit analyses modelled bit flips in gate-level netlists to help designers decide where redundancy is needed. It contains no physical fault-injection parameters and was not used on any product or hardware. Do not use it to attack systems you do not own or have permission to test. Results are bounded model results, not proofs of security or of insecurity of a real device."
- Recommended disclosure policy paragraph (draft for owner):
  "If this tool is used to find a design-specific weakness in a third-party open design, report it privately to the maintainers (for OpenTitan: its published security contact, security@opentitan.org appears in the repo's research notes; policy text not opened, UNVERIFIED) before any public statement, allow a reasonable fix period, and do a prior-art check first. No such finding exists today; the two real-design runs found only generic decision-register flips and are not disclosures. No outward report has been made."

## 2. Third-party code and data
Folder `third_party_derived/` (V by listing, headers read, nothing executed). It is NOT covered by THIRD_PARTY.md or NOTICE.md (I: grep shows only handoff/research files mention it, so the notice files are incomplete).
| Path | Holds | Licence status |
|---|---|---|
| `firmer_cleave/fm_model.py`, `fm_export_nl.py`, `fm_nl_check.py`, `tests/test_fm_model.py` | z3 re-implementation of FIRMER/CLEAVE checks | Header says "no code copied; re-implemented from papers and from reading the C++" (V). Origin S3L-official/CLEAVE commit 0b9f052 has "No licence file found". Ideas not copyrightable, but "from reading the C++" leaves a derivation question (I). |
| `firmer_cleave/patches/FIRMER_extend_build_fix.patch` | a patch to the unlicensed CLEAVE source (V: HEADER_TEXT.txt) | Unlicensed origin. A patch against it is a derived work of unlicensed code. Highest exposure. |
| `uarchifi_kfrp_fiver/uarchifi_plugin/fault_rtlil.cc` + `LICENSE-LGPL-2.1.txt` | modified copy of CEA-LIST/uArchiFI file, build-fixed for Yosys 0.38 | LGPL-2.1, notice retained (V). Compatible if kept separable with notice and source available; owner must accept LGPL obligations. Header copyright "2026 CEA". Not unlicensed, but needs NOTICE entry. |
The name `uarchifi_kfrp_fiver` suggests k-FRP and FIVER material, but only the plugin is present (V). Prior reports (research/c3/bc BC_REPORT Q8) flag it as an open owner decision (V).
Must NOT be in a public or submitted bundle: `third_party_derived/` (at least the CLEAVE patch, and the whole folder until the owner decides); `compare/synfi_run/venv` (353 MB, own licences) and, unless NOTICE kept, `compare/synfi_run/src`; `real_designs/second/dl_repo/` (unvetted, includes third-party personal contact data); `real_designs/work/` + `fsm.v` unless a commit is pinned and licence re-read; `real_designs/work/` called "untrusted downloads" (V: REPORT.md); `formal/runs/`, `results/deep/logs` (paths, bulk); `handoff/*.zip`; tool-generated logs carry the Yosys banner/copyright line (claire@yosyshq.com, 156 hits; this is tool banner text, harmless but remove in a clean bundle). Also: `THIRD_PARTY.md` and `NOTICE.md` say "the project's own code is not a copy of any third-party source"; this is untrue/unqualified while third_party_derived/ exists (V) - fix wording. Apache-2.0 copies: keep LICENSE.apache2 and notices; `layout/second/rtl/door.v` is a modified copy, needs "changed" mark (I; Apache s4b), currently only mentioned in THIRD_PARTY.md.

Gaps against the real workflow (I from files read; V that the draft does not mention):
4. Does not cover third-party-derived code reading by agents (FIRMER/CLEAVE/uArchiFI) and its licence consequence.
5. Option B says the owner "ran the main commands" and "read and checked the results": a statement that is only true if it happened. Option C leaves placeholders (good). Option A says "I reviewed the results": same risk. Flag these as conditional.
6. No statement on which model(s) and how autonomous the overnight runs were (agents ran unattended; owner in chat only intermittently, I).
Wording risks to avoid (implying human testing, silicon, certification or novelty): "validated solver" (FINAL_STATUS.md:11), "reproducible, validated analysis project" (:13; validation is agent-run cross-checks with the same fault model), "Tested in a real browser" (FINAL_STATUS.md:52; it was an automated headless browser, not a person), "tested by users/readers" anywhere (explainer.html:205 correctly says simulated readers), "real chip layout"/"Real sky130 GDS" (:11,:18; flow-demo, LVS top-level not passed on door design, no fabrication), "tangible artifact", "Achieved", "lay it out", "prove it" (README.md:11), "independent validation" (same fault model), "independent" for the REP re-run (shares recipe list). No hit implying certification found (V by grep).

## 4. Claim-honesty scan (README.md, docs/FINAL_STATUS.md, product/QUICKSTART.md, docs/wow/explainer.html)
| File:line | Phrase | Problem | Fix |
|---|---|---|---|
| FINAL_STATUS.md:11 | "a validated solver" | validation = agent cross-checks, same fault model | "a solver cross-checked against two other tools on the same fault model" |
| FINAL_STATUS.md:11 | "real open-source layouts" / :18 "real chip layout", "Real sky130 GDS" | no fab, no sign-off; door LVS top-level failed pin matching (second/REPORT.md:314) | "sky130 flow-demo layouts (open-source tools, not signed off, never fabricated)" |
| FINAL_STATUS.md:11 | `"safe" design stays safe` | in quotes, ok; but add "within the model" | add qualifier |
| FINAL_STATUS.md:52 | "Tested in a real browser" | automated browser, not human test | "Checked with a headless browser" |
| FINAL_STATUS.md:20 | "real upstream bug" | row title, status "Not achieved": ok | keep |
| README.md:11 | "**prove it**" act title and "(bounded checks and one narrow unbounded proof)" | title overstates; qualified in same line | keep qualifier on dashboard heading too ("check it") ; owner choice, dashboard not to be restyled |
| README.md:3 / FINAL_STATUS.md:3 | "" | good, keep | none |
| README.md:9 "Not a novel research result" | good | none | |
| README.md quickstart line | "tested with yosys 0.33" | fine | none |
| explainer.html:177 | "No real product was tested or shown weak" | good | none |
| explainer.html:188 | "'No attack found' means none up to that bound, not 'secure'" | good | none |
| explainer.html:169, 201, 202 | counting-rule claims | carries MEASURED/UNVERIFIED labels; fine | none |
| explainer.html:184 | "Play: break the lock" | game on toy; fine, labelled ILLUSTRATIVE | none |
| QUICKSTART.md:6 | "not a proof of security" | good | none |
Greps for 'verified', 'proved', 'certified', 'silicon', 'novel', 'first', 'guarantee', 'real-world' in the four files: only negated or qualified uses (V), except the items above. Residual (I): README one-sentence headline says "V2 held against 2 flips on only 6 of 32" - correct and labelled.

## 5. Privacy
V: no owner name or email found in the tree by grep (not exhaustive; handoff zips not opened). Found: third party's personal data (Varun Pathak, LinkedIn, mcmaster.ca email) in `real_designs/second/dl_repo/v5run_DE1-SoC-ComboLock.md:115` (fetched repo README; delete from bundle). Design authors' GitHub handles appear in THIRD_PARTY.md/NOTICE.md/reports (public attribution, acceptable, required by Apache). 258 files contain `/home/user` paths (generic, not identifying; I). `.git` absent at root (V: not a git repo listing), so no commit-author leakage to check. Check zips and `.github/` before release (not done).

## Not done
Did not open handoff zips, did not read persona files or all handoff/research text, did not check licences online, did not exhaustively grep every file for names.
