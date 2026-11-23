"""Attack-potential rating tables, transcribed only where a section or table number could be cited.

Sources (read on 2026-11-20/21; every value below re-checked against both PDFs on 2026-11-21):
  PSA  = "PSA Certified Attack Methods", document JSADEN004, version 1.3 Rel 01, date of issue 01/02/2024,
         https://www.psacertified.org/app/uploads/2024/04/JSADEN004-PSA_Certified_Attack_Methods-V1.3.pdf
  JIL  = Joint Interpretation Library, "Application of Attack Potential to Smartcards and Similar Devices", v3.2.1, Feb 2024,
         https://www.commoncriteriaportal.org/files/ccfiles/JIL-Application-of-Attack-Potential-to-Smartcards-v3.2.1.pdf

Every value below carries the table/section it was taken from. Nothing here is a lab rating: the point values are the
schemes' own, the choice of factor levels for a GlitchSAT result is an ASSUMPTION that the user can and should override.
"""

PSA_DOC = "PSA Certified Attack Methods, JSADEN004 v1.3 (issue 01/02/2024)"
JIL_DOC = "JIL Application of Attack Potential to Smartcards and Similar Devices v3.2.1 (Feb 2024)"
PSA_URL = "https://www.psacertified.org/app/uploads/2024/04/JSADEN004-PSA_Certified_Attack_Methods-V1.3.pdf"
JIL_URL = "https://www.commoncriteriaportal.org/files/ccfiles/JIL-Application-of-Attack-Potential-to-Smartcards-v3.2.1.pdf"

# Factor level keys shared by both schemes; labels follow each document's wording.
ELAPSED = ["hour", "day", "week", "month", "gt_month", "gt_4_months"]
EXPERTISE = ["layman", "proficient", "expert", "multiple_expert"]
KNOWLEDGE = ["public", "restricted", "sensitive", "critical", "critical_plus"]
ACCESS = ["lt10", "lt30", "lt100", "gt100"]
EQUIPMENT = ["none", "standard", "specialized", "bespoke", "multiple_bespoke"]
OPEN_SAMPLES = ["public", "restricted", "sensitive", "critical"]
FACTORS = {"elapsed": ELAPSED, "expertise": EXPERTISE, "knowledge": KNOWLEDGE, "access": ACCESS, "equipment": EQUIPMENT,
           "open_samples": OPEN_SAMPLES}
FACTOR_LABEL = {"elapsed": "Elapsed time", "expertise": "Expertise", "knowledge": "Knowledge of the TOE",
                "access": "Access to TOE (samples)", "equipment": "Equipment", "open_samples": "Open samples"}

# (identification, exploitation); None = level not defined in that document.
PSA_TABLE1 = {
    "_source": "PSA JSADEN004 v1.3, section 4.2, Table 1 (page 19)",
    "elapsed": {"hour": (0, 0), "day": (1, 3), "week": (2, 4), "month": (3, 6), "gt_month": (5, 8)},
    "expertise": {"layman": (0, 0), "proficient": (2, 2), "expert": (5, 4)},
    "knowledge": {"public": (0, 0), "restricted": (2, 2), "sensitive": (4, 3), "critical": (6, 5)},
    "access": {"lt10": (0, 0), "lt30": (1, 2), "lt100": (2, 4), "gt100": (3, 6)},
    "equipment": {"none": (0, 0), "standard": (1, 2), "specialized": (3, 4), "bespoke": (5, 6), "multiple_bespoke": (7, 8)},
}
PSA_LEVEL_LABEL = {
    "elapsed": {"hour": "<= one hour", "day": "<= one day", "week": "<= one week", "month": "<= one month", "gt_month": "> one month"},
}

JIL_TABLE13 = {
    "_source": "JIL v3.2.1, section 4.8, Table 13 'Final table for the rating factors' (para. 120)",
    "elapsed": {"hour": (0, 0), "day": (1, 3), "week": (2, 4), "month": (3, 6), "gt_month": (5, 8), "gt_4_months": (6, 10)},
    "expertise": {"layman": (0, 0), "proficient": (2, 2), "expert": (5, 4), "multiple_expert": (7, 6)},
    "knowledge": {"public": (0, 0), "restricted": (2, 2), "sensitive": (4, 3), "critical": (6, 5), "critical_plus": (9, None)},
    "access": {"lt10": (0, 0), "lt30": (1, 2), "lt100": (2, 4), "gt100": (3, 6)},
    "equipment": {"none": (0, 0), "standard": (1, 2), "specialized": (3, 4), "bespoke": (5, 6), "multiple_bespoke": (7, 8)},
    "open_samples": {"public": (0, None), "restricted": (2, None), "sensitive": (5, None), "critical": (9, None)},
}
JIL_LEVEL_LABEL = {
    "elapsed": {"hour": "< one hour", "day": "< one day", "week": "< one week", "month": "< one month", "gt_month": "> one month",
                "gt_4_months": "> four months (Table 1a, justified exception only)"},
    "open_samples": {"public": "Public / not required"},
}

# PSA level ceilings: an attack rated <= ceiling must be considered at that level; above it is out of scope.
PSA_LEVELS = {2: 15, 3: 20, 4: 24}
PSA_LEVELS_SOURCE = "PSA JSADEN004 v1.3, section 4.2, Table 2 (page 20)"
PSA_SCOPE_NOTES = [
    ("At PSA Level 2 physical attacks on the TOE are out of scope during the exploitation phase.", "PSA JSADEN004 v1.3, section 5.1.3 (page 24)"),
    ("At PSA Level 3 and Level 4, physical attacks on the device are permitted in the exploitation phase.", "PSA JSADEN004 v1.3, section 5.1.3 (page 24)"),
    ("For Level 4, laser fault injection needs to be considered as an attack method.", "PSA JSADEN004 v1.3, section 5.1.3 (page 27)"),
    ("Elapsed time assumes the attacker works eight hours a day or runs scripts twenty-four hours a day; for probabilistic attacks take the time for a 50/50 chance.",
     "PSA JSADEN004 v1.3, section 4.1.1 (pages 16-17)"),
    ("Combined attacks are rated factor by factor for the combination, not by adding the totals of the parts.", "PSA JSADEN004 v1.3, section 4.3 (page 20)"),
]

# JIL Table 14: final attack potential -> 'TOE resistant to attackers with attack potential of'.
JIL_BANDS = [(0, 15, "No rating"), (16, 20, "Basic"), (21, 24, "Enhanced-Basic"), (25, 30, "Moderate"), (31, 10 ** 9, "High")]
JIL_BANDS_SOURCE = "JIL v3.2.1, Table 14 'Rating of vulnerabilities and TOE resistance' (para. 121)"

# JIL Table 10 (para. 67): tool categorisation, for the fault types GlitchSAT users name.
JIL_TOOL_CLASS = {
    "voltage": ("standard", "Electrical glitches workstation"),
    "clock": ("standard", "Electrical glitches workstation (a clock glitch is taken as an electrical glitch: interpretation, not a Table 10 row)"),
    "em": ("specialized", "EMFI workstation"),
    "laser": ("specialized", "High-end laser workstation"),
    "light": ("standard", "Low-end light injection (UV, flash light)"),
}
JIL_TOOL_SOURCE = "JIL v3.2.1, Table 10 'Categorisation of Tools' (para. 67)"
JIL_EQUIPMENT_NOTE = ("Table 13 adds one point when several similar specialized tools are needed; this tool never adds it on its own "
                      "(set jil_equipment or rate by hand).", "JIL v3.2.1, Table 13 footnote (para. 120) and section 4.4 (para. 59)")
JIL_ELAPSED_NOTE = ("The '> four months' level (Table 1a) 'only applies as a reasonable exception' and must be justified with analysis or "
                    "measurement results; it is used only when set explicitly.", "JIL v3.2.1, section 2, paras. 14-15")
JIL_EXAMPLE_LFI = dict(
    title="Annex A.3 Example 1: LFI on CSP or bare die", printed_total=18, printed_band="Basic",
    identification=dict(elapsed="month", expertise="proficient", knowledge="public", access="lt10", equipment="specialized", open_samples="public"),
    exploitation=dict(elapsed="week", expertise="proficient", knowledge="public", access="lt10", equipment="specialized"),
    source="JIL v3.2.1, Annex A.3, Example 1, Table 15 (para. 286)")

# PSA worked examples used as anchors (section 5.1.3, 'Glitch against initialization', pages 25-27).
PSA_EXAMPLES = {
    "one_glitch_each_device": dict(
        title="Glitch required on each target device", printed_total=20,
        identification=dict(elapsed="month", expertise="expert", knowledge="public", access="lt10", equipment="specialized"),
        exploitation=dict(elapsed="day", expertise="proficient", knowledge="public", access="lt10", equipment="specialized"),
        source="PSA JSADEN004 v1.3, section 5.1.3, example rating 'glitch required on each target device' (page 26, total 20)"),
    "two_glitches": dict(
        title="Two successful glitches required", printed_total=23,
        identification=dict(elapsed="month", expertise="expert", knowledge="public", access="lt10", equipment="specialized"),
        exploitation=dict(elapsed="week", expertise="proficient", knowledge="public", access="lt10", equipment="specialized"),
        source="PSA JSADEN004 v1.3, section 5.1.3, rating 'two glitches required' (page 27, total printed as 23)",
        discrepancy=("The printed table scores the exploitation elapsed time '<= one week' as 6 points; Table 1 gives 4 points "
                     "for '<= one week' in exploitation (6 is the '<= one month' value). With Table 1 values the total is 21, "
                     "not 23. This tool scores with Table 1 and shows the printed figure next to it.")),
}
PSA_RARE_NOTE = ("If the probability of successful glitches is very low, exploitation takes more than one month and the two-glitch "
                 "total rises to 25 (above the Level 4 ceiling of 24).", "PSA JSADEN004 v1.3, section 5.1.3 (two-glitch example, page 27)")
PSA_MULTI_GLITCH_NOTE = ("Under defence in depth 'a successful exploit may take multiple glitches at separate times to carry out'.",
                         "PSA JSADEN004 v1.3, section 5.1.3 (page 25)")
PSA_COUNTERMEASURE_NOTE = ("For voltage-glitch bypass of firmware rollback protection (total 21), the document notes that with "
                           "countermeasures two glitches might still fall in scope for Level 4.", "PSA JSADEN004 v1.3, section 5.4.3 (pages 38-39)")
JIL_SYNC_NOTE = ("Several perturbations may be required (one per firewall check); performing them is 'difficult, however still "
                 "feasible' because the check can be found by synchronisation. No point value is given for this.",
                 "JIL v3.2.1, section 5.9.10, paras. 273-274")
JIL_TIMING_NOTE = ("For fault analysis, a lack of accuracy in the synchronisation requirements 'can render the analysis to recover the "
                   "key much more complex'; no point value is attached to timing precision.", "JIL v3.2.1, section 5.4, para. 148")
JIL_PERTURBATION_NOTE = ("Perturbation attacks: an effect that occurs only in one of 10 or 100 attempts may still be usable, "
                         "depending on the application context.", "JIL v3.2.1, section 5.3, para. 145")

# Number of injection events -> exploitation elapsed time. Only 1 and 2 have an anchor in a published example.
EVENTS_TO_ELAPSED = {
    1: ("day", "PSA JSADEN004 v1.3, section 5.1.3, 'glitch required on each target device': exploitation <= one day"),
    2: ("week", "PSA JSADEN004 v1.3, section 5.1.3, 'two glitches required': exploitation <= one week"),
}
NO_ANCHOR_3PLUS = ("No published example rates three or more required glitch events; this tool does not extrapolate and keeps the "
                   "two-event value ('<= one week'). Override with --assume exploit_elapsed=... if you can justify more.")


def points(table, factor, level, phase):
    """phase 0 = identification, 1 = exploitation. Raises KeyError for a level the document does not define."""
    pair = table[factor][level]
    return pair[phase]


def level_label(scheme, factor, level):
    lab = (PSA_LEVEL_LABEL if scheme == "psa" else JIL_LEVEL_LABEL).get(factor, {})
    if level in lab:
        return lab[level]
    if factor == "access":
        return {"lt10": "< 10 samples", "lt30": "< 30 samples", "lt100": "< 100 samples", "gt100": "> 100 samples"}[level]
    return {"critical_plus": "Critical+", "multiple_expert": "Multiple Expert", "multiple_bespoke": "Multiple Bespoke"}.get(
        level, level.capitalize())


def jil_band(total):
    for lo, hi, name in JIL_BANDS:
        if lo <= total <= hi:
            return name
    return "No rating"
