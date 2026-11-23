"""SARIF 2.1.0 for GitHub code scanning: one rule per finding type, locations mapped back to source through Yosys `src`
attributes when the source file is in the repository, else to the net's line in the netlist JSON.

Rules
  GS001 single-point-of-failure   a minimum attack of ONE modelled flip exists (one result per distinct net)
  GS002 merged-redundant-copies   the redundancy lint finds nets shared by, or combining, the intended copies
  GS003 margin-below-target       minimum flips below the configured target, or PSA estimate within the target level's ceiling
  GS004 solver-inconclusive       a run ended without a verdict
  GS005 configuration-problem     the honest input does not reach the goal, or the runs contradict each other
  GS006 minimum-attack-reported   informational: the minimum attack and its margin estimate (no target set or target met)
Only GS001-GS003 are security rules (tag `security` and a `security-severity`, which makes GitHub show their results as
security alerts); GS004-GS006 report tool or configuration state and carry neither. The security-severity values are a
fixed tool convention for sorting alerts, not a measured severity.
Fingerprints: every result carries partialFingerprints.primaryLocationLineHash (GitHub code scanning uses only this one)
= the 32-hex finding hash of rule + design (incl. flow) + top + net, plus ":1". Results that share rule, file and line
therefore stay separate alerts instead of folding into one hash computed from the source line.
"""
import hashlib, json, os, re

from . import margin as M

SCHEMA_URI = "https://json.schemastore.org/sarif-2.1.0.json"
INFO_URI = "https://github.com/Kavin-Re/GlitchSAT-Redundancy"
SCOPE = ("Bounded result on modelled single-cycle bit flips of this synthesized netlist; not a proof of security and not a "
         "lab rating.")

RULES = [
    dict(id="GS001", name="SinglePointOfFailure", level="error", sev="8.0",
         short="One modelled bit flip defeats the check",
         full="Within the stated bounds, a single-cycle flip of one net makes the netlist accept a wrong input. A redundant "
              "check should need at least two independent faults.",
         help="Every listed net is, on its own, a minimum attack under the model. Duplicate the decision in independent logic, "
              "keep each copy's result in its own output bits, and check that synthesis did not merge the copies (rule GS002)."),
    dict(id="GS002", name="MergedRedundantCopies", level="error", sev="7.0",
         short="Redundant copies share or combine logic before the decision",
         full="The structural lint found nets that lie in the cones of two or more intended copies, or that combine copies "
              "before the decision bits. One fault there can act on several copies at once.",
         help="Typical causes are opt_merge / structural hashing in synthesis or an AND of the copies' results. Keep the copies "
              "apart (keep_hierarchy, keep attributes, separate output bits) and re-run the bounded search to measure the effect."),
    dict(id="GS003", name="MarginBelowTarget", level="error", sev="6.0",
         short="Fault margin below the project's target",
         full="The minimum number of modelled flips, or the attack-potential estimate derived from it, is below the target set "
              "in the targets file.",
         help="The estimate's assumptions (fault type, flips per injection event, factor levels) are listed in the message and in "
              "the evidence report. The estimate supports, and never replaces, lab evaluation."),
    dict(id="GS004", name="SolverInconclusive", level="warning", sev=None,
         short="Solver did not decide within the limit", full="At least one run ended without a verdict (timeout or unknown).",
         help="Raise the timeout, reduce the cycle bound, or restrict fault sites; a missing verdict is not a pass."),
    dict(id="GS005", name="ConfigurationProblem", level="error", sev=None,
         short="Configuration problem: no valid verdict",
         full="The honest input does not reach the goal in the fault-free design, or two runs on the same netlist contradict.",
         help="Check attacker.legitimate_value, property.output and property.bad_value in the threat model."),
    dict(id="GS006", name="MinimumAttackReported", level="note", sev=None,
         short="Minimum modelled attack and margin estimate",
         full="Informational record of the smallest attack found within the bound and the attack-potential estimate.",
         help="No action needed if the margin meets your target. See the evidence report for scope and limits."),
]
RULE_INDEX = {r["id"]: i for i, r in enumerate(RULES)}

_SRC = re.compile(r"^(?P<file>[^:|]+):(?P<l1>\d+)(?:\.(?P<c1>\d+))?(?:-(?P<l2>\d+)(?:\.(?P<c2>\d+))?)?$")


def _rule_objs():
    out = []
    for r in RULES:
        props = {"tags": (["security"] if r["sev"] else []) + ["hardware", "fault-injection"], "precision": "high"}
        if r["sev"]:
            props["security-severity"] = r["sev"]
        out.append(dict(id=r["id"], name=r["name"], shortDescription=dict(text=r["short"]), fullDescription=dict(text=r["full"]),
                        help=dict(text=r["help"], markdown=r["help"]), defaultConfiguration=dict(level=r["level"]),
                        helpUri=INFO_URI, properties=props))
    return out


class Locator:
    """Net name -> SARIF physicalLocation. Prefers the RTL line from Yosys `src` (only if that file exists under repo_root,
    optionally after src_map prefix rewriting); else the line of the net's entry in the netlist JSON."""

    def __init__(self, netlist_path, top, repo_root, src_map=None, display_uri=None, source_path=None):
        self.repo_root = os.path.abspath(repo_root)
        self.display_uri = display_uri
        self.source_path = source_path
        self.netlist_path = netlist_path
        self.src_map = src_map or {}
        self.netnames, self.lines = {}, []
        if netlist_path and os.path.isfile(netlist_path):
            with open(netlist_path, encoding="utf-8") as f:
                text = f.read()
            self.lines = text.split("\n")
            try:
                d = json.loads(text)
                mods = d.get("modules", {})
                mod = mods.get(top) or (next(iter(mods.values())) if len(mods) == 1 else {})
                self.netnames = mod.get("netnames", {})
            except ValueError:
                pass

    def rel(self, path):
        ap = os.path.abspath(path)
        r = os.path.relpath(ap, self.repo_root)
        return r.replace(os.sep, "/") if not r.startswith("..") else None

    def _src_region(self, net):
        nn = self.netnames.get(net) or self.netnames.get(net.split("[")[0]) or {}
        src = (nn.get("attributes") or {}).get("src", "")
        for part in str(src).split("|"):
            m = _SRC.match(part.strip())
            if not m:
                continue
            f = m["file"]
            for a, b in self.src_map.items():
                if f.startswith(a):
                    f = b + f[len(a):]
            cand = f if os.path.isabs(f) else os.path.join(self.repo_root, f)
            if os.path.isfile(cand) and self.rel(cand):
                reg = dict(startLine=int(m["l1"]))
                if m["l2"]:
                    reg["endLine"] = int(m["l2"])
                return self.rel(cand), reg
        return None

    def _json_line(self, net):
        for name in (net, net.split("[")[0]):
            key = json.dumps(name) + ":"
            for i, line in enumerate(self.lines):
                if key in line:
                    return i + 1
        return 1

    def physical(self, net=None):
        if net:
            hit = self._src_region(net)
            if hit:
                return dict(artifactLocation=dict(uri=hit[0]), region=hit[1])
        uri = self.display_uri or (self.rel(self.netlist_path) if self.netlist_path and os.path.isfile(self.netlist_path) else None)
        if uri is None and self.source_path and not os.path.isabs(self.source_path):
            uri = self.source_path   # RTL the netlist was synthesized from (the netlist itself is not stored)
            return dict(artifactLocation=dict(uri=uri), region=dict(startLine=1))
        if uri is None:
            uri = os.path.basename(self.netlist_path or "netlist.json")
        return dict(artifactLocation=dict(uri=uri), region=dict(startLine=self._json_line(net) if net and self.lines else 1))


def _fp(*parts):
    return hashlib.sha256("\x1f".join(str(p) for p in parts).encode()).hexdigest()[:32]


def _result(rule, msg, loc, logical=None, props=None, fp_parts=()):
    fp = _fp(rule, *fp_parts)
    r = dict(ruleId=rule, ruleIndex=RULE_INDEX[rule], level=next(x["level"] for x in RULES if x["id"] == rule),
             message=dict(text=msg), locations=[dict(physicalLocation=loc)],
             partialFingerprints={"glitchsatFinding/v1": fp, "primaryLocationLineHash": f"{fp}:1"})
    if logical:
        r["locations"][0]["logicalLocations"] = logical
    if props:
        r["properties"] = props
    return r


def design_results(entry, targets):
    """entry: dict(name, group, rating, surface, lint, locator). targets: dict(min_faults=int|None, psa_level=int|None)."""
    g, rt, loc = entry["group"], entry["rating"], entry["locator"]
    top, name = g["top"], entry["name"]
    res = []
    mtxt = (f"minimum {g['min_faults']} flip(s)" if g["min_faults"] is not None else
            (f"no attack with <= {g['no_attack_up_to']} flip(s)" if g["no_attack_up_to"] is not None else "no verdict"))
    bound = f"(<= {g['max_bound']} flips, {g['cycles']} cycles)"

    def logical(net):
        return [dict(name=net, fullyQualifiedName=f"{top}.{net}", kind="variable")]

    # GS001
    if g["min_faults"] == 1:
        nets = {}
        sf = entry.get("surface")
        if sf and sf.get("min_faults") == 1:
            for a in sf.get("attacks", []):
                (net, cyc), = a["faults"]
                nets.setdefault(net, set()).add(cyc)
        for w in g["witnesses"]:
            for f in w:
                nets.setdefault(f["net"], set()).add(f["cycle"])
        for net in sorted(nets):
            cyc = ",".join(str(c) for c in sorted(nets[net]))
            res.append(_result("GS001", f"[{name}] One modelled flip of `{net}` (cycle {cyc}) defeats the check {bound}. {SCOPE}",
                               loc.physical(net), logical(net), dict(design=name, net=net, cycles=sorted(nets[net])),
                               (name, top, net)))
    # GS002
    lint = entry.get("lint")
    if lint and lint.get("verdict") in ("merged", "partially_shared"):
        sps = lint.get("single_points", [])
        firsts = [p for p in lint.get("merge_points", []) if p.get("first")] or sps[:1]
        for p in (firsts or [dict(net=None)])[:20]:
            net = p.get("net")
            copies = "+".join(p.get("copies", []))
            res.append(_result("GS002", f"[{name}] Redundancy lint: copies {copies or '(see lint)'} meet at `{net}` before the decision "
                                        f"({len(sps)} single point(s) in total, verdict '{lint['verdict']}'). The lint does not by itself "
                                        f"show that one fault there suffices; the bounded search reports {mtxt}. {SCOPE}",
                               loc.physical(net), logical(net) if net else None,
                               dict(design=name, lint_verdict=lint["verdict"], single_points=len(sps)), (name, top, "lint", net)))
    # GS004 / GS005
    for r in g["unknown"]:
        rule = "GS005" if r["verdict"] == "CONFIGURATION_PROBLEM" else "GS004"
        res.append(_result(rule, f"[{name}] {r['verdict']} at k={r['bound_k']}: no verdict. {r.get('note', '')}", loc.physical(),
                           None, dict(design=name), (name, top, r["verdict"], r["bound_k"])))
    if not g["consistent"]:
        why = "; ".join(g.get("contradictions", [])) or (f"no attack up to {g['no_attack_up_to']} flips, but an attack of "
                                                          f"{g['min_faults']} flips was reported")
        res.append(_result("GS005", f"[{name}] Runs contradict: {why}. Check that all runs used the same netlist and scope.",
                           loc.physical(), None, dict(design=name), (name, top, "contradiction")))
    ub = entry.get("unbounded")
    ubp = dict(unbounded_proved_up_to=ub["proved_up_to"], unbounded_smallest_attack=ub["smallest_attack"],
               unbounded_init=ub["init"]) if ub else {}
    ubtxt = (f" Unbounded check ({ub['init']} power-up): " + ("no budget proved" if ub["proved_up_to"] is None else
             f"no attack with <= {ub['proved_up_to']} flip(s) at any cycle") +
             ("" if ub["smallest_attack"] is None else f", smallest attack at any cycle {ub['smallest_attack']} flip(s)") + ".") if ub else ""
    # GS003 / GS006
    if rt.get("status") == "rated":
        tmin, tlvl = targets.get("min_faults"), targets.get("psa_level")
        m_eff = rt["min_flips"]
        below = []
        if tmin is not None and not rt["min_flips_is_lower_bound"] and m_eff < tmin:
            below.append(f"{m_eff} flip(s) < target {tmin}")
        if tlvl is not None and rt["psa"]["total"] <= M.F.PSA_LEVELS[tlvl]:
            below.append(f"PSA estimate {rt['psa']['total']} <= L{tlvl} ceiling {M.F.PSA_LEVELS[tlvl]}")
        a = rt["assumptions"]
        amsg = (f"Assumptions: fault_type={a['fault_type']}, flips_per_event={a['flips_per_event']}, events={rt['events']}. "
                f"{M.LAB_DISCLAIMER}")
        net = (g["witnesses"][0][0]["net"] if g["witnesses"] and g["witnesses"][0] else None)
        if below:
            res.append(_result("GS003", f"[{name}] Margin below target: {'; '.join(below)} {bound}.{ubtxt} {rt['headline']}. {amsg}",
                               loc.physical(net), logical(net) if net else None,
                               dict(design=name, min_flips=m_eff, psa=rt["psa"]["total"], jil=rt["jil"]["total"],
                                    events=rt["events"], **ubp), (name, top, "margin")))
        else:
            res.append(_result("GS006", f"[{name}] {mtxt} {bound}.{ubtxt} {rt['headline']}. {amsg}", loc.physical(net),
                               logical(net) if net else None,
                               dict(design=name, min_flips=m_eff, min_flips_is_lower_bound=rt["min_flips_is_lower_bound"],
                                    psa=rt["psa"]["total"], jil=rt["jil"]["total"], events=rt["events"], **ubp), (name, top, "info")))
    elif rt.get("status") == "no_fault_needed":
        res.append(_result("GS001", f"[{name}] The goal is reached with 0 flips: logical or configuration flaw. {SCOPE}",
                           loc.physical(), None, dict(design=name), (name, top, "zero")))
    return res


def build(entries, targets, tool_version, command="", artifacts=None):
    results = []
    for e in entries:
        results.extend(design_results(e, targets))
    arts = []
    for a in artifacts or []:
        art = dict(location=dict(uri=a["uri"]))
        if a.get("sha256") and len(a["sha256"]) == 64:
            art["hashes"] = {"sha-256": a["sha256"]}
        arts.append(art)
    run = dict(tool=dict(driver=dict(name="GlitchSAT", version=tool_version, semanticVersion=tool_version,
                                     informationUri=INFO_URI, rules=_rule_objs())),
               invocations=[dict(executionSuccessful=True, commandLine=command)],
               results=results,
               properties=dict(scope=SCOPE, disclaimer=M.LAB_DISCLAIMER, targets=targets))
    if arts:
        run["artifacts"] = arts
    return {"$schema": SCHEMA_URI, "version": "2.1.0", "runs": [run]}
