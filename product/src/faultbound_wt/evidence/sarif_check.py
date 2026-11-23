"""Check a SARIF file: (1) JSON schema (bundled transcribed subset, or a full schema file given with --schema) and
(2) the GitHub code-scanning rules that a schema cannot express (documented at
https://docs.github.com/en/code-security/code-scanning/integrating-with-code-scanning/sarif-support-for-code-scanning,
read 2026-11-21). Without the optional `jsonschema` package only check (2) and a structural check run."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
SUBSET = os.path.join(HERE, "data", "sarif-2.1.0-subset.schema.json")

GITHUB_LIMITS = dict(runs=20, results_per_run=25000, rules_per_run=25000, locations_per_result=1000, tags_per_rule=20,
                     rule_name=255, description=1024)


def schema_errors(doc, schema_path=None):
    try:
        import jsonschema
    except ImportError:
        return None
    with open(schema_path or SUBSET, encoding="utf-8") as f:
        schema = json.load(f)
    v = jsonschema.Draft7Validator(schema, format_checker=jsonschema.FormatChecker())
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}" for e in v.iter_errors(doc)]


def github_errors(doc):
    err = []
    if doc.get("version") != "2.1.0":
        err.append("version must be 2.1.0")
    runs = doc.get("runs") or []
    if len(runs) > GITHUB_LIMITS["runs"]:
        err.append(f"more than {GITHUB_LIMITS['runs']} runs")
    for ri, run in enumerate(runs):
        drv = (run.get("tool") or {}).get("driver") or {}
        if not drv.get("name"):
            err.append(f"runs/{ri}: tool.driver.name missing")
        rules = drv.get("rules") or []
        ids = [r.get("id") for r in rules]
        if len(set(ids)) != len(ids):
            err.append(f"runs/{ri}: duplicate rule ids")
        if len(rules) > GITHUB_LIMITS["rules_per_run"]:
            err.append(f"runs/{ri}: too many rules")
        for r in rules:
            if len(r.get("name", "")) > GITHUB_LIMITS["rule_name"]:
                err.append(f"rule {r.get('id')}: name longer than 255")
            for k in ("shortDescription", "fullDescription"):
                if len((r.get(k) or {}).get("text", "")) > GITHUB_LIMITS["description"]:
                    err.append(f"rule {r.get('id')}: {k} longer than 1024")
            props = r.get("properties") or {}
            if len(props.get("tags", [])) > GITHUB_LIMITS["tags_per_rule"]:
                err.append(f"rule {r.get('id')}: more than 20 tags")
            sev = props.get("security-severity")
            if sev is not None:
                try:
                    if not 0.0 < float(sev) <= 10.0:
                        err.append(f"rule {r.get('id')}: security-severity outside (0, 10]")
                except ValueError:
                    err.append(f"rule {r.get('id')}: security-severity not a number string")
            if props.get("precision") not in (None, "very-high", "high", "medium", "low"):
                err.append(f"rule {r.get('id')}: bad precision")
        results = run.get("results") or []
        if len(results) > GITHUB_LIMITS["results_per_run"]:
            err.append(f"runs/{ri}: more than 25000 results")
        seen_fp = {}
        for i, res in enumerate(results):
            p = f"runs/{ri}/results/{i}"
            # GitHub code scanning uses only primaryLocationLineHash; two results of one rule with the same value are
            # folded into one alert, so distinct findings must not share it
            plh = (res.get("partialFingerprints") or {}).get("primaryLocationLineHash")
            if plh is not None:
                key = (res.get("ruleId"), plh)
                if key in seen_fp:
                    err.append(f"{p}: same ruleId and primaryLocationLineHash as results/{seen_fp[key]} (would fold into one alert)")
                else:
                    seen_fp[key] = i
            if res.get("ruleId") not in ids:
                err.append(f"{p}: ruleId {res.get('ruleId')!r} not in tool.driver.rules")
            elif "ruleIndex" in res and (res["ruleIndex"] >= len(ids) or ids[res["ruleIndex"]] != res["ruleId"]):
                err.append(f"{p}: ruleIndex does not point at ruleId")
            if not (res.get("message") or {}).get("text"):
                err.append(f"{p}: message.text empty")
            locs = res.get("locations") or []
            if not locs:
                err.append(f"{p}: at least one location is required for code scanning to display a result")
            if len(locs) > GITHUB_LIMITS["locations_per_result"]:
                err.append(f"{p}: too many locations")
            for li, loc in enumerate(locs):
                al = ((loc.get("physicalLocation") or {}).get("artifactLocation") or {})
                uri = al.get("uri", "")
                if not uri:
                    err.append(f"{p}/locations/{li}: artifactLocation.uri empty")
                elif uri.startswith("/") or "://" in uri or uri.startswith(".."):
                    err.append(f"{p}/locations/{li}: uri {uri!r} should be relative to the repository root")
    return err


def check(path, schema_path=None):
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    s = schema_errors(doc, schema_path)
    g = github_errors(doc)
    return dict(schema=s, github=g, ok=(not s) and not g, schema_used=schema_path or SUBSET, schema_checked=s is not None)
