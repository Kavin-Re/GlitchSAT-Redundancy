"""INT wording edits. Exact-string replacements; logs before/after to edits_log.json."""
import json, sys, pathlib
ROOT = pathlib.Path('<repo>')
S = ("Encoding sets the floor (idle word touches 2 of 3 copies => 2 flips); the synthesis flow decides whether "
     "the floor is reached (1 when a flow merges the copies). A build or flow difference changes the netlist, "
     "not the underlying weakness.")
SRC = "`docs/report/WHY_TWO_FLIPS.md`, `research/c6/p01/P01_REPORT.md`"
E = []
def rep(path, old, new):
    p = ROOT / path; t = p.read_text()
    if old not in t and new in t:
        E.append({'file': path, 'before': old, 'after': new}); return
    if t.count(old) != 1:
        print('MISS', path, t.count(old), old[:80]); sys.exit(1)
    p.write_text(t.replace(old, new)); E.append({'file': path, 'before': old, 'after': new})

# ---------- README ----------
rep('README.md',
 "| Full 8-bit word, re-synthesized with apt Yosys 0.33 (85 gates; conda 0.38 and Docker 0.52 give 83 gates and no 2-flip attack: verdict depends on the Yosys version) | **2** | same |",
 "| Full 8-bit word, `rtl/v2.v` re-synthesized with apt Yosys 0.33 (85 gates). Not a version effect: the stored netlist is also Yosys 0.33 (68 gates, another flow). Cause: the armed word 0xCC differs from 0x96 only in bits of 2 of the 3 copies. Over the 8 `--synth-sweep` flows: 2 1 1 2 2 2 2 2; re-encoded `rtl/v2e.v` (0xA5): 3 1 1 3 3 3 3 3; conda 0.38 (83 gates) gives 3 on the plain flow only. " + S + " | **2** | " + SRC + " |")
rep('README.md',
 "<img src=\"docs/report/ledger.png\" alt=\"redundancy survival ledger\" width=\"520\">\n",
 "<img src=\"docs/report/ledger.png\" alt=\"redundancy survival ledger\" width=\"520\">\n\n"
 "**Redundancy is a code** (MEASURED, `results/comms/distance_sweep.csv`, `research/c6/p11/P11_REPORT.md`; toy design, modelled flips, observed not a theorem, nothing new). The state words F0, CC, 96, 69 are codewords of the textbook Reed-Muller code RM(1,3) (distance 4), and the copies are a repetition code. Over 19 codebooks: with only the state flops as fault sites the minimum equals the distance to the nearest non-accept word in 15 of 15 codebooks with distance <= 6; with all nets it never exceeds that (19 of 19), and it stays at about one flip per comparator copy. Failed predictions, kept: (a) 'flops-only = idle-to-accept distance' fails where a fail word is nearer; (c) 3 of 16 three-copy codebooks sit at 2, not 3, on the project flow; word order matters under ABC (F0 then CC gives 2, CC then F0 gives 3); the mechanism was not dissected. More: `docs/comms/CODING_VIEW.md`, `docs/report/WHY_TWO_FLIPS.md`.\n\n"
 "<img src=\"docs/comms/staircase.png\" alt=\"flips needed against code distance: flops only and all nets\" width=\"420\">\n")
rep('README.md',
 "The apt 0.33 and conda 0.38 builds give different V2 netlists (85 vs 83 combinational gates), so CI on another Yosys may not reproduce `ci/expected_reproduce.json`.",
 "The apt 0.33 and conda 0.38 builds give different V2 netlists (85 vs 83 combinational gates; a build or flow difference changes the netlist, not the underlying weakness, `docs/report/WHY_TWO_FLIPS.md`), so CI on another Yosys may not reproduce `ci/expected_reproduce.json`.")

# ---------- FINAL_STATUS ----------
rep('docs/FINAL_STATUS.md',
 "The difference tracks the tool build (apt Yosys 0.33 versus conda Yosys 0.38+92); the reason inside ABC or Yosys was not analysed (a hypothesis, not a located cause; see also the synthesis-recipe and counting-rule bullet above).",
 "CORRECTED 2026-11-20 (step P01a, `research/c6/p01/P01_REPORT.md`, `docs/report/WHY_TWO_FLIPS.md`; the earlier text called this a Yosys-build/version effect, which was an error): the stored netlist's header also reads Yosys 0.33, so stored-vs-apt is a flow/source difference (one mux per bit, 68 gates). The root cause is the encoding: the armed word 0xCC differs from 0x96 in bits {1,3,4,6}, owned by only two of the three comparator copies, so two flips of next-state stems can turn the cycle-0 load of CC into 96. Re-encoding that one constant to 0xA5 (`rtl/v2e.v`) gives 3 1 1 3 3 3 3 3 over the 8 `--synth-sweep` flows (v2: 2 1 1 2 2 2 2 2; MEASURED, apt 0.33, re-verified at integration 2026-11-20); the 1s are flows that merge the copies (opt_merge / flatten before ABC), which no encoding fixes. " + S)
rep('docs/FINAL_STATUS.md',
 "Yosys version dependence (H5, 2026-11-20, MEASURED): the same V2 source at <=2 flips gives an attack with apt Yosys 0.33 (85 gates) but no attack with conda 0.38 and Docker/Debian 0.52 (83 gates each); verdicts belong to a netlist hash and tool build.",
 "Build differences (H5, 2026-11-20, MEASURED): on the plain flow at <=2 flips apt Yosys 0.33 (85 gates) gives an attack, conda 0.38 and Docker/Debian 0.52 (83 gates each) do not; but conda 0.38 gives 2 on three other flows (P01a), so this is not a version immunity. Verdicts belong to a netlist hash and flow.")

# ---------- ENGINE_STATUS ----------
rep('docs/ENGINE_STATUS.md',
 "The countermeasure's strength therefore depends on the synthesized netlist and the Yosys build, not just the RTL.",
 "The countermeasure's strength therefore depends on the synthesized netlist, not just the RTL. Root cause (CORRECTED 2026-11-20, P01a, `docs/report/WHY_TWO_FLIPS.md`; earlier wording blamed the Yosys version, an error: the stored netlist is also Yosys 0.33): the armed word 0xCC differs from 0x96 only in bits of two of the three copies; `rtl/v2e.v` (0xA5) gives 3 1 1 3 3 3 3 3 over the 8 flows versus 2 1 1 2 2 2 2 2. " + S)
rep('docs/ENGINE_STATUS.md',
 "Yosys version dependence (H5, 2026-11-20, MEASURED): the same V2 source at <=2 flips gives an attack with apt Yosys 0.33 (85 gates) but no attack with conda 0.38 and Docker/Debian 0.52 (83 gates each); verdicts belong to a netlist hash and tool build.",
 "Build differences (H5, 2026-11-20, MEASURED): on the plain flow at <=2 flips apt 0.33 (85 gates) gives an attack, conda 0.38 and Docker/Debian 0.52 (83 gates each) do not; conda 0.38 gives 2 on three other flows (P01a). Verdicts belong to a netlist hash and flow.")

# ---------- PROJECT_REPORT ----------
rep('docs/report/PROJECT_REPORT.md',
 "8. The Yosys 0.33 versus 0.38 difference is unexplained; Yosys 0.52 (Docker, H5) behaves like 0.38 (83 gates, no 2-flip attack): the V2 verdict at <=2 flips depends on the Yosys version.",
 "8. CORRECTED (2026-11-20; the earlier item said the V2 verdict depends on the Yosys version, an error found by a fresh-eyes review and measured by P01a, `docs/report/WHY_TWO_FLIPS.md`): the stored netlist is also Yosys 0.33 (68 gates, another flow); the 85 vs 83 gates (apt 0.33 vs conda 0.38; 0.52 like 0.38 on the plain flow, H5) are flow/build differences in the netlist. The cause of 2 flips is the encoding: 0xCC xor 0x96 touches only two of three copies; `rtl/v2e.v` (0xA5) gives 3 1 1 3 3 3 3 3 over 8 flows (v2: 2 1 1 2 2 2 2 2); conda 0.38 gives 3 only on the plain flow. " + S)

# ---------- DOSSIER ----------
rep('docs/dossier/PROJECT_DOSSIER.md',
 "Docker Debian Yosys 0.52 = 83 gates, no attack at <=2 flips (H5, MEASURED; toolchain-dependent verdict);",
 "Docker Debian Yosys 0.52 = 83 gates, no attack at <=2 flips on the plain flow (H5, MEASURED; a netlist difference, not a version immunity: conda 0.38 gives 2 on three other flows, P01a);")
rep('docs/dossier/PROJECT_DOSSIER.md',
 "The exact Yosys/ABC change responsible was NOT located: \"build\" is a correlate, not an identified cause. This is the honest answer to \"why 85 vs 83?\": we do not know the cause; we know where it is not (not the compare copies) and which options remove it.",
 "The exact Yosys/ABC change behind 85 vs 83 gates was NOT located. CORRECTED 2026-11-20 (P01a, `docs/report/WHY_TWO_FLIPS.md`): why V2 can fall to 2 is now explained by the encoding, not the build: the stored netlist is also Yosys 0.33; 0xCC xor 0x96 touches only two of three copies; `rtl/v2e.v` (0xA5) gives 3 1 1 3 3 3 3 3 over 8 flows (v2 2 1 1 2 2 2 2 2). " + S)

# ---------- edu ----------
rep('docs/edu/INSTRUCTOR_NOTES.md',
 "H5 also measured 83 gates and no 2-flip attack on Yosys 0.52 (Docker): the verdict depends on the Yosys version.",
 "H5 also measured 83 gates and no 2-flip attack on Yosys 0.52 (Docker, plain flow). Do not teach this as a version effect (corrected 2026-11-20, `docs/report/WHY_TWO_FLIPS.md`): " + S + " Conda 0.38 gives 2 on three other flows.")
rep('docs/edu/ANSWER_KEY.md',
 "(H5); the verdict depends on the Yosys version;",
 "(H5); not a version effect: " + S + " (`docs/report/WHY_TWO_FLIPS.md`);")

# ---------- SLIDES_OUTLINE ----------
rep('docs/report/SLIDES_OUTLINE.md',
 "(Yosys version dependence: 0.33 gives 85 gates with a 2-flip attack; 0.38 and 0.52 give 83 gates with none.)",
 "(Not a version effect: the stored netlist is also Yosys 0.33. " + S + " See slide 'Why 2 and not 3?'.)")

# ---------- dashboard template ----------
rep('dashboard/template.html',
 "with Yosys 0.38 and with Yosys 0.52 (Docker, H5): the verdict depends on the Yosys version. Always name the tool build.",
 "with Yosys 0.38 and with Yosys 0.52 (Docker, H5) on the plain flow. That is not a version effect (the stored netlist is also Yosys 0.33): " + S + " Always name the netlist hash and flow (<code>docs/report/WHY_TWO_FLIPS.md</code>).")

# ---------- NUMBERS ----------
rep('docs/NUMBERS.md',
 "The verdict is toolchain-dependent (consistent with E2); state the Yosys version with every V2 result |",
 "Netlist-dependent, not a version effect (CORRECTED 2026-11-20 by P01a: stored netlist also Yosys 0.33; conda 0.38 gives 2 on three other flows; cause = encoding, see `P01.*`); state the netlist hash and flow with every V2 result |")

# ---------- QA_SHEET / ONE_PAGE ----------
rep('docs/dossier/QA_SHEET.md',
 "**D-bonus. Why 85 gates (apt 0.33) versus 83 (conda 0.38)?** We do not know the exact cause.",
 "**D-bonus. Why 85 gates (apt 0.33) versus 83 (conda 0.38)?** We do not know the exact gate-count cause, but we now know why V2 can fall to 2 (P01a, `docs/report/WHY_TWO_FLIPS.md`): " + S + " Earlier E2 notes:")
rep('docs/dossier/QA_SHEET.md',
 "[flag] WE DO NOT KNOW the exact tool change.",
 "[flag] The exact tool change behind the gate count is unknown; the 2-flip weakness is the encoding (0xCC xor 0x96 touches 2 of 3 copies; `rtl/v2e.v` gives 3 on 6 of 8 flows; WHY_TWO_FLIPS.md).")
rep('docs/dossier/QA_SHEET.md',
 "| \"I do not know the exact cause. Synthesis is deterministic,",
 "| \"The gate counts differ by flow and build; the 2-flip weakness is the encoding: the armed word touches only two of three copies, and re-encoding it gives 3 on 6 of 8 flows (WHY_TWO_FLIPS.md). Synthesis is deterministic,")
rep('docs/dossier/ONE_PAGE_KEY_POINTS.md',
 "why two Yosys versions disagree (we do not know the exact cause).",
 "the exact tool change behind 85 vs 83 gates (unknown). Corrected 2026-11-20: the 2-vs-3 flips is not a version effect but the encoding (`docs/report/WHY_TWO_FLIPS.md`).")

rep('dashboard/template.html',
 "So the answer depends on the exact netlist the tool produces: always name the tool build.",
 "So the answer depends on the exact netlist the tool produces. It is not a version effect (the spike netlist is also Yosys 0.33): the armed word 0xCC touches only 2 of the 3 copies, so encoding sets the floor at 2 and the flow decides whether it is reached (docs/report/WHY_TWO_FLIPS.md). Always name the netlist hash and flow.")
rep('dashboard/template.html',
 "built with Yosys 0.38 it gave a different netlist with no 2-flip attack. A countermeasure",
 "built with Yosys 0.38 (plain flow) it gave a different netlist with no 2-flip attack. The weakness is the encoding (the armed word touches 2 of 3 copies; re-encoded rtl/v2e.v gives 3 on 6 of 8 flows); a build or flow difference changes the netlist, not the weakness. A countermeasure")

json.dump(E, open(ROOT/'research/c6/int/edits_log.json','w'), indent=1)
print(len(E), 'edits')
