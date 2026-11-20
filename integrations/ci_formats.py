"""Export a fault-campaign document to SARIF 2.1.0 (GitHub code scanning) and JUnit XML (
License: UNDECIDED). Standard library only.

Mapping (our choice, documented in INTEGRATION_PLAN.md):
  - a campaign with verdict ATTACK_FOUND -> one SARIF result (level "error") / one failing JUnit testcase per
    fault set, saying "attack with N modelled faults exists within the bound";
  - NO_ATTACK_UP_TO_BOUND -> no SARIF result (clean) / one passing testcase whose name carries the bound;
  - UNKNOWN / NOT_RUN -> SARIF note / JUnit skipped.
Nothing here says the design is secure: a pass only means no attack within the stated bound and fault model.
SARIF needs a physical location; netlists are not source files, so we point at the netlist file (artifactLocation)
with no region. Whether GitHub accepts/ingests this was NOT tested (no upload is made by this project).
"""
import xml.etree.ElementTree as ET

RULE_ID = "FI001"


def _bound_text(doc):
    tm = doc.get("threat_model", {})
    return f"<= {tm.get('max_faults', '?')} modelled single-cycle faults within {tm.get('cycles', '?')} cycles"


def to_sarif(doc, uri=None):
    uri = uri or doc["design"].get("netlist_file") or doc["design"]["name"]
    results = []
    verdict = doc.get("verdict", "UNKNOWN")
    if verdict == "ATTACK_FOUND":
        for s in doc["fault_sets"]:
            desc = ", ".join(f"{f['target']['name']}@cycle{f['cycle']}({f['type']})" for f in s["faults"])
            results.append({
                "ruleId": RULE_ID, "level": "error",
                "message": {"text": f"Attack with {len(s['faults'])} modelled fault(s) exists ({_bound_text(doc)}): {desc}. "
                                    f"Label: {doc['label']}. Modelled bit flips, not physical glitches."},
                "locations": [{"physicalLocation": {"artifactLocation": {"uri": uri}}}],
                "properties": {"faultSetId": s["id"], "faultCount": len(s["faults"])}})
    elif verdict in ("UNKNOWN", "NOT_RUN"):
        results.append({"ruleId": RULE_ID, "level": "note",
                        "message": {"text": f"No verdict ({verdict}); nothing is claimed."},
                        "locations": [{"physicalLocation": {"artifactLocation": {"uri": uri}}}]})
    return {"$schema": "https://json.schemastore.org/sarif-2.1.0.json", "version": "2.1.0",
            "runs": [{"tool": {"driver": {"name": doc["generator"]["tool"], "informationUri": "urn:project:working-title-TBD",
                                          "rules": [{"id": RULE_ID, "name": "FaultInjectionAttackWithinBound",
                                                     "shortDescription": {"text": "A bounded fault-injection attack exists on this netlist (modelled faults)"}}]}},
                      "results": results,
                      "properties": {"label": doc["label"], "verdict": verdict, "bound": _bound_text(doc)}}]}


def to_junit(doc):
    verdict = doc.get("verdict", "UNKNOWN")
    suite = ET.Element("testsuite", name=f"fault-campaign:{doc['design']['name']}")
    n_fail = n_skip = 0
    if verdict == "ATTACK_FOUND":
        for s in doc["fault_sets"]:
            tc = ET.SubElement(suite, "testcase", classname=doc["design"]["name"], name=f"no_attack_with_{len(s['faults'])}_faults/{s['id']}")
            f = ET.SubElement(tc, "failure", message=f"attack with {len(s['faults'])} modelled fault(s) ({_bound_text(doc)})")
            f.text = "; ".join(f"{x['target']['name']}@cycle{x['cycle']}:{x['type']}" for x in s["faults"])
            n_fail += 1
    elif verdict == "NO_ATTACK_UP_TO_BOUND":
        ET.SubElement(suite, "testcase", classname=doc["design"]["name"], name=f"no_attack_within({_bound_text(doc)})")
    else:
        tc = ET.SubElement(suite, "testcase", classname=doc["design"]["name"], name="verdict")
        ET.SubElement(tc, "skipped", message=f"verdict {verdict}")
        n_skip += 1
    suite.set("tests", str(len(suite))); suite.set("failures", str(n_fail)); suite.set("skipped", str(n_skip))
    root = ET.Element("testsuites"); root.append(suite)
    return ET.tostring(root, encoding="unicode")
