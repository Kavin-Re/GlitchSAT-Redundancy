"""Fault-campaign interchange format.

A small JSON format for "a set of modelled faults" so that our solver's attack sets and other tools' fault lists
can be converted to and from one neutral shape. It is OUR OWN format: it is not the native format of any
third-party tool, and no third-party tool defines it. Faults are MODELLED, not physical glitches.

Schema id: fault-campaign/0.1 (human-readable copy: schema/fault_campaign.schema.json).
Pure standard library; `validate()` returns a list of error strings (empty list = valid).
"""
import json

SCHEMA_ID = "fault-campaign/0.1"
LABELS = ("MEASURED", "SIMULATED", "ESTIMATED", "ILLUSTRATIVE", "UNVERIFIED")
FAULT_TYPES = ("bit_flip", "set", "reset", "stuck_at_0", "stuck_at_1", "gate_replace")
TARGET_KINDS = ("net", "cell", "flop_q", "port")
VERDICTS = ("ATTACK_FOUND", "NO_ATTACK_UP_TO_BOUND", "UNKNOWN", "NOT_RUN")


def _is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def validate(doc):
    """Return a list of human-readable problems; [] means the document conforms to fault-campaign/0.1."""
    errs = []
    if not isinstance(doc, dict):
        return ["document must be a JSON object"]
    if doc.get("schema") != SCHEMA_ID:
        errs.append(f"schema must be {SCHEMA_ID!r}, got {doc.get('schema')!r}")
    if doc.get("label") not in LABELS:
        errs.append(f"label must be one of {LABELS}, got {doc.get('label')!r}")
    gen = doc.get("generator")
    if not isinstance(gen, dict) or not isinstance(gen.get("tool"), str) or not gen.get("tool"):
        errs.append("generator.tool (non-empty string) is required")
    des = doc.get("design")
    if not isinstance(des, dict) or not isinstance(des.get("name"), str) or not des.get("name"):
        errs.append("design.name (non-empty string) is required")
    elif "netlist_sha256" in des and not (isinstance(des["netlist_sha256"], str) and len(des["netlist_sha256"]) == 64):
        errs.append("design.netlist_sha256 must be a 64-char hex string")
    tm = doc.get("threat_model")
    if tm is not None:
        if not isinstance(tm, dict):
            errs.append("threat_model must be an object")
        else:
            for key in ("max_faults", "cycles"):
                if key in tm and not (_is_int(tm[key]) and tm[key] >= 0):
                    errs.append(f"threat_model.{key} must be an integer >= 0")
    if "verdict" in doc and doc["verdict"] not in VERDICTS:
        errs.append(f"verdict must be one of {VERDICTS}")
    fs = doc.get("fault_sets")
    if not isinstance(fs, list):
        errs.append("fault_sets (list) is required")
        return errs
    seen = set()
    for i, s in enumerate(fs):
        p = f"fault_sets[{i}]"
        if not isinstance(s, dict):
            errs.append(f"{p} must be an object"); continue
        sid = s.get("id")
        if not isinstance(sid, str) or not sid:
            errs.append(f"{p}.id (non-empty string) is required")
        elif sid in seen:
            errs.append(f"{p}.id {sid!r} duplicated")
        else:
            seen.add(sid)
        if "effective" in s and s["effective"] is not None and not isinstance(s["effective"], bool):
            errs.append(f"{p}.effective must be true, false or null")
        fl = s.get("faults")
        if not isinstance(fl, list) or not fl:
            errs.append(f"{p}.faults must be a non-empty list"); continue
        for j, f in enumerate(fl):
            q = f"{p}.faults[{j}]"
            if not isinstance(f, dict):
                errs.append(f"{q} must be an object"); continue
            t = f.get("target")
            if not isinstance(t, dict) or t.get("kind") not in TARGET_KINDS or not isinstance(t.get("name"), str) or not t.get("name"):
                errs.append(f"{q}.target needs kind in {TARGET_KINDS} and a non-empty name")
            elif "id" in t and not _is_int(t["id"]):
                errs.append(f"{q}.target.id must be an integer")
            if not (_is_int(f.get("cycle")) and f["cycle"] >= 0):
                errs.append(f"{q}.cycle must be an integer >= 0")
            ty = f.get("type")
            if ty not in FAULT_TYPES:
                errs.append(f"{q}.type must be one of {FAULT_TYPES}")
            elif ty == "gate_replace" and not isinstance(f.get("replacement"), str):
                errs.append(f"{q}.replacement (string, new cell type) is required for gate_replace")
            if "duration" in f and not (_is_int(f["duration"]) and f["duration"] >= 1):
                errs.append(f"{q}.duration must be an integer >= 1 (cycles)")
    return errs


def load(path):
    doc = json.load(open(path))
    errs = validate(doc)
    if errs:
        raise ValueError(f"{path}: invalid fault-campaign: " + "; ".join(errs))
    return doc


def dump(doc, path):
    errs = validate(doc)
    if errs:
        raise ValueError("refusing to write invalid fault-campaign: " + "; ".join(errs))
    with open(path, "w") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")


def from_glitchsat(result, label="MEASURED", command=None):
    """Convert one JSON written by scripts/glitchsat.py `check --out` into a fault-campaign document.

    The solver's `faults` list is its minimised attack set (one fault set). A NO_ATTACK verdict gives zero fault sets.
    """
    b = result.get("bound", {})
    doc = {
        "schema": SCHEMA_ID,
        "label": label,
        "generator": {"tool": result.get("tool", "glitchsat.py"), **({"command": command} if command else {})},
        "design": {"name": result.get("top", "unknown"), "top": result.get("top"),
                   "netlist_file": result.get("netlist_json"),
                   "synth_flow": result.get("synth_flow")},
        "threat_model": {"max_faults": b.get("max_faults"), "cycles": b.get("cycles"),
                         "fault_model": b.get("fault_model"), "attacker_input": b.get("attacker_input"),
                         "goal": b.get("goal")},
        "verdict": result.get("verdict", "UNKNOWN"),
        "fault_sets": [],
        "notes": result.get("note", ""),
    }
    doc["design"] = {k: v for k, v in doc["design"].items() if v is not None}
    doc["threat_model"] = {k: v for k, v in doc["threat_model"].items() if v is not None}
    if result.get("faults"):
        faults = []
        for f in result["faults"]:
            tgt = {"kind": "flop_q" if f.get("kind") == "flop_Q" else "net", "name": f["net"]}
            if "net_id" in f:
                tgt["id"] = f["net_id"]
            faults.append({"target": tgt, "cycle": f["cycle"], "type": "bit_flip", "duration": 1})
        doc["fault_sets"].append({"id": "min_attack_set", "label": f"minimum attack set, {len(faults)} fault(s)",
                                  "faults": faults, "effective": True, "source": "solver witness"})
    return doc
