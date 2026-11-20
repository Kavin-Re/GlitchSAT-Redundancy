"""Report writers: JSON, SARIF 2.1.0, JUnit XML."""
import json, os, re, tempfile
from xml.sax.saxutils import escape, quoteattr

RULE_ATTACK, RULE_UNKNOWN, RULE_CONFIG = "FBWT001", "FBWT002", "FBWT003"
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"


_XML_BAD = re.compile("[^\\x09\\x0A\\x0D\\x20-\\uD7FF\\uE000-\\uFFFD\\U00010000-\\U0010FFFF]")


def _xml_clean(s):
    """H1: replace characters outside the XML 1.0 Char production (e.g. U+0001) by U+FFFD so the JUnit file stays well-formed."""
    return _XML_BAD.sub("\ufffd", str(s))


def _summary(rep):
    b = rep["bound"]
    return f"{rep['verdict']} (<= {b['max_flips']} flips, {b['cycles']} cycles)"


def to_json(rep):
    return json.dumps(rep, indent=2, sort_keys=False) + "\n"


def to_sarif(rep):
    prov, b = rep["provenance"], rep["bound"]
    uri = prov["netlist_path"]
    rules = [
        dict(id=RULE_ATTACK, name="BoundedFaultAttackFound",
             shortDescription=dict(text="Modelled bit-flip attack reaches the target property"),
             fullDescription=dict(text="Within the stated flip budget and cycle bound, a set of modelled single-cycle bit "
                                       "flips plus an attacker input makes the target output equal the bad value."),
             defaultConfiguration=dict(level="error")),
        dict(id=RULE_UNKNOWN, name="SolverInconclusive",
             shortDescription=dict(text="Solver did not decide within the timeout"),
             defaultConfiguration=dict(level="warning")),
        dict(id=RULE_CONFIG, name="ConfigurationProblem",
             shortDescription=dict(text="Honest input does not reach the goal in the fault-free design"),
             defaultConfiguration=dict(level="error")),
    ]
    results = []
    if rep["verdict"] == "ATTACK_FOUND":
        logical = [dict(name=f["net"], fullyQualifiedName=f"{prov['top']}.{f['net']}", kind="member") for f in rep["faults"]]
        det = "; ".join(f"{f['net']} ({f['kind']}) @cycle {f['cycle']}" for f in rep["faults"])
        results.append(dict(
            ruleId=RULE_ATTACK, level="error",
            message=dict(text=f"{_summary(rep)}: minimum {rep['min_faults']} flip(s): {det}. {rep['explanation']['summary']} "
                              f"MODELLED faults on this synthesized netlist only; {rep['scope']['statement']}."),
            locations=[dict(physicalLocation=dict(artifactLocation=dict(uri=uri)), logicalLocations=logical)],
            properties=dict(faults=rep["faults"], attacker_input=rep["attacker_input_value"])))
    elif rep["verdict"] == "UNKNOWN_TIMEOUT":
        results.append(dict(ruleId=RULE_UNKNOWN, level="warning",
                            message=dict(text=f"{_summary(rep)}: solver timeout; no verdict."),
                            locations=[dict(physicalLocation=dict(artifactLocation=dict(uri=uri)))]))
    elif rep["verdict"] == "CONFIGURATION_PROBLEM":
        results.append(dict(ruleId=RULE_CONFIG, level="error", message=dict(text=rep["note"]),
                            locations=[dict(physicalLocation=dict(artifactLocation=dict(uri=uri)))]))
    run = dict(
        tool=dict(driver=dict(name=prov["tool"], version=prov["tool_version"], rules=rules)),
        artifacts=[dict(location=dict(uri=uri), hashes={"sha-256": prov["netlist_sha256"]})],
        invocations=[dict(executionSuccessful=rep["verdict"] not in ("UNKNOWN_TIMEOUT", "CONFIGURATION_PROBLEM"),
                          commandLine=prov.get("command") or "")],
        results=results,
        properties=dict(verdict=rep["verdict"], scope=rep["scope"], bound=b, note=rep["note"], config_warnings=rep.get("config_warnings", []), provenance=prov,
                        threat_model=rep["threat_model"]))
    return json.dumps({"$schema": SARIF_SCHEMA, "version": "2.1.0", "runs": [run]}, indent=2) + "\n"


def to_junit(rep):
    prov, b = rep["provenance"], rep["bound"]
    name = f"{prov['top']}: no attack with <= {b['max_flips']} flips in {b['cycles']} cycles"
    v = rep["verdict"]
    props = {"verdict": v, "netlist_sha256": prov["netlist_sha256"], "gates": prov["netlist_stats"]["gates"],
             "flops": prov["netlist_stats"]["flops"], "z3": prov["z3"], "yosys": prov.get("synthesis_yosys") or prov.get("netlist_yosys_creator") or "",
             "command": prov.get("command") or ""}
    for k, val in rep["scope"].items():
        props["scope_" + k] = json.dumps(val, sort_keys=True) if isinstance(val, (dict, list)) else val
    props["tool_version"] = prov["tool_version"]
    body, f, e = "", 0, 0
    if v == "ATTACK_FOUND":
        f = 1
        det = "\n".join(f"  {x['net']} ({x['kind']}) cycle {x['cycle']}" for x in rep["faults"])
        body = (f"<failure message={quoteattr(_summary(rep) + ': min ' + str(rep['min_faults']) + ' flip(s)')} type=\"AttackFound\">"
                f"{escape(det + chr(10) + rep['explanation']['summary'])}</failure>")
    elif v == "CONFIGURATION_PROBLEM":
        e = 1
        body = f'<error message="configuration problem: honest input does not reach the goal" type="ConfigurationProblem">{escape(rep["note"])}</error>'
    elif v == "UNKNOWN_TIMEOUT":
        e = 1
        body = '<error message="solver timeout; no verdict" type="Unknown"/>'
    out = escape(rep["note"] + "\n" + "\n".join(f"scope {k}: {val}" for k, val in rep["scope"].items() if isinstance(val, str)))
    x = ['<?xml version="1.0" encoding="UTF-8"?>',
         f'<testsuites name="faultbound-wt" tests="1" failures="{f}" errors="{e}">',
         f'<testsuite name={quoteattr(prov["top"])} tests="1" failures="{f}" errors="{e}" time="{rep["runtime_s"]}">',
         "<properties>" + "".join(f"<property name={quoteattr(k)} value={quoteattr(str(val))}/>" for k, val in props.items()) + "</properties>",
         f'<testcase classname="faultbound-wt" name={quoteattr(name)} time="{rep["runtime_s"]}">{body}<system-out>{out}</system-out></testcase>',
         "</testsuite></testsuites>"]
    return _xml_clean("\n".join(x) + "\n")


def atomic_write_text(path, text, encoding="utf-8"):
    """H2 (N5): write to a UNIQUE temp file in the same directory, flush+fsync, then os.replace onto `path`. Concurrent writers can no longer interleave
    or truncate each other: the file is always one complete document (the last writer wins). A symlink at `path` is replaced, not followed."""
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix="." + os.path.basename(path) + ".", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        um = os.umask(0); os.umask(um)
        os.chmod(tmp, 0o666 & ~um)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def csv_cell(x):
    """H2 (N11): quoted CSV cell; a cell whose text starts with = + - @ TAB or CR gets a leading apostrophe (spreadsheet formula injection)."""
    t = str(x).replace('"', "'")
    if t[:1] in ("=", "+", "-", "@", "\t", "\r"):
        t = "'" + t
    return '"%s"' % t


def write(rep, path):
    p = path.lower()
    if p.endswith(".sarif") or p.endswith(".sarif.json"):
        s = to_sarif(rep)
    elif p.endswith(".junit.xml") or p.endswith(".xml"):
        s = to_junit(rep)
    elif p.endswith(".json"):
        s = to_json(rep)
    else:
        raise ValueError(f"cannot infer report format from {path!r}; use .json, .sarif or .junit.xml")
    atomic_write_text(path, s)


def badge(rep):
    """Shields.io endpoint-style JSON (schemaVersion 1). Always carries the bound and the word 'scoped'; never says secure/safe."""
    b = rep["bound"]
    k, n = b["max_flips"], b["cycles"]
    v = rep["verdict"]
    if v == "NO_ATTACK_UP_TO_BOUND":
        msg, col = f"no attack <={k} flips @ {n} cycles (scoped)", "yellowgreen"
    elif v == "ATTACK_FOUND":
        f = rep.get("min_faults", 0)
        msg, col = f"attack found: {f} flips @ {n} cycles (scoped)", "red"
    elif v == "CONFIGURATION_PROBLEM":
        msg, col = "config problem, no verdict (scoped)", "lightgrey"
    else:
        msg, col = f"unknown <={k} flips @ {n} cycles (scoped)", "orange"
    return dict(schemaVersion=1, label="fault check", message=msg, color=col)


def write_badge(rep, path):
    atomic_write_text(path, json.dumps(badge(rep), indent=1) + "\n")


def write_sweep(sw, path):
    """Sweep table as .json or .csv (one row per cell)."""
    p = path.lower()
    if p.endswith(".json"):
        s = json.dumps(sw, indent=2) + "\n"
    elif p.endswith(".csv") and sw.get("schema") == "faultbound-wt-synthsweep/1":   # PS6
        from . import synth_sweep
        s = synth_sweep.write_csv(sw, path)
    elif p.endswith(".csv"):
        rows = ["goal,input_sites,init,verdict,cost,runtime_s,count_rule"]
        for c in sw["cells"]:
            rows.append(",".join(csv_cell(c[k]) for k in ("goal", "input_sites", "init", "verdict", "cost", "runtime_s", "count_rule")))
        s = "\n".join(rows) + "\n"
    else:
        raise ValueError(f"unknown sweep output extension for {path!r}: use .json or .csv")
    atomic_write_text(path, s)
