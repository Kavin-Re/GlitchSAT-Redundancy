"""Output: console text, Markdown, SARIF 2.1.0 (through ext/product's conventions and validator), and the diff."""
import json
import os

from . import margin as M
from . import paths
from .model import SURVIVED, WEAKENED, REMOVED, UNTRACKED, NOT_CHECKED, ORDER, fingerprint

SCOPE = ("Structural check of this netlist / layout / binary against the countermeasures found in the source. Margins are "
         "bounded results on modelled faults; not a proof of security and not a lab rating.")

RULES = [
    dict(id="GSS001", name="CountermeasureRemoved", level="error", sev="8.0",
         short="A fault countermeasure in the source is gone in the build",
         full="Redundant copies were merged into one, a sparse state encoding was replaced, or a repeated firmware check "
              "was compiled into a single check. One fault can now defeat what was written as several.",
         help="The message names the cells, flops or source lines and the tool step. Keep the copies apart "
              "(keep_hierarchy / keep / dont_touch, no merging pass after flatten), keep the encoding "
              "(fsm_encoding none), or add a compiler barrier, then re-run."),
    dict(id="GSS002", name="CountermeasureWeakened", level="error", sev="6.5",
         short="A fault countermeasure lost part of its redundancy",
         full="Some copies now share cells, the code distance dropped, copies sit within one fault spot, or fewer "
              "repeated checks remain than were written.",
         help="See the evidence in the message; the fixes are the same as for a removed countermeasure."),
    dict(id="GSS003", name="SurvivalMarginBelowTarget", level="error", sev="6.0",
         short="Minimum number of modelled faults below the target, or lower than at the reference stage",
         full="The bounded fault search on this stage's netlist needs fewer faults than the configured minimum, or fewer "
              "than the same search on the reference stage.",
         help="Bounded and modelled (single-cycle bit flips, k flips, T cycles). Compare the stages in the report."),
    dict(id="GSS004", name="CountermeasureUntracked", level="warning", sev=None,
         short="A countermeasure could not be followed into this stage",
         full="The checker could not locate the countermeasure in this stage, so it gives no verdict. Not a pass.",
         help="Provide an unoptimised reference netlist, keep names, or declare the countermeasure in the YAML."),
    dict(id="GSS005", name="SurvivalRegression", level="error", sev="7.0",
         short="A countermeasure is weaker than in the baseline run",
         full="Compared with the baseline report (for example the main branch), a countermeasure's verdict got worse, "
              "a countermeasure disappeared, or a margin dropped.",
         help="Look at what changed in the RTL, the synthesis script, the placement constraints or the compiler flags."),
]


def _mark(v):
    return {SURVIVED: "SURVIVED", WEAKENED: "WEAKENED", REMOVED: "REMOVED ", UNTRACKED: "UNTRACKED", NOT_CHECKED: "not run "}[v]


def stage_margin_text(s):
    out = []
    if s.get("margin"):
        out.append(M.text(s["margin"]))
    if s.get("margin_shots"):
        ms = s["margin_shots"]
        out.append(f"{ms['min_shots'] if ms['min_shots'] is not None else '> ' + str(ms.get('searched_k'))} shot(s) of radius "
                   f"{ms['spot_radius_um']} um ({ms['label']})")
    if s.get("margin_faults"):
        mf = s["margin_faults"]
        out.append(f"{mf['text']} instruction fault(s) ({mf['label']})")
    return "; ".join(out)


def text(rep, verbose=True):
    s = rep["summary"]
    L = [f"GlitchSAT countermeasure survival: {rep['name']}    {s['verdict']} (exit {s['exit_code']})", ""]
    if not rep["countermeasures"]:
        L.append("  No countermeasure found or declared. Nothing was checked.")
    for c in rep["countermeasures"]:
        L.append(f"  {c['title']}   [{c['kind']}; {c['origin']}{'; ' + paths.rel(c['where']) if c.get('where') else ''}]")
        for r in c["stages"]:
            L.append(f"    {r['stage']:<12} {_mark(r['verdict'])}  {r['evidence'][0] if r['evidence'] else ''}")
            if r["verdict"] in (SURVIVED, NOT_CHECKED) and not verbose:
                continue
            if r["verdict"] not in (SURVIVED, NOT_CHECKED):
                for e in r["evidence"][1:]:
                    L.append(f"                   - {e}")
                if r.get("cause"):
                    L.append(f"        why:  {r['cause']}")
                for i, f in enumerate(r.get("fix") or []):
                    L.append(f"        {'fix:  ' if i == 0 else '      '}{f}")
        L.append("")
    ms = [(st["name"], stage_margin_text(st)) for st in rep["stages"] if stage_margin_text(st)]
    if ms:
        g = rep.get("goal") or {}
        L.append("  Security margin per stage" + (f" (goal: {g.get('output', 'boot_word')} == {g.get('value', 0x96):#x} with a wrong "
                                                 f"{g.get('input', 'sig')})" if g else "") + ":")
        for n, t in ms:
            L.append(f"    {n:<12} {t}")
        if s.get("margin_drop"):
            d = s["margin_drop"]
            L.append(f"    -> margin dropped from {d['reference']} ({d['reference_stage']}) to {d['min_faults']} ({d['stage']}); {d.get('text', '')}")
        for b in s.get("margin_below_target", []):
            L.append(f"    -> {b['stage']}: {b['min_faults']} is below the target {b['target']}")
        L.append("")
    for st in rep["stages"]:
        for n in st.get("notes", []):
            L.append(f"  note [{st['name']}]: {n}")
        b = st.get("bisect")
        if b:
            L.append(f"  bisect [{st['name']}]: " + "; ".join(
                f"{x['command']} -> " + (x.get("error") or ", ".join(f"{k.split(':')[0]} {v}" for k, v in x["verdicts"].items()))
                for x in b["steps"]))
    if rep.get("diff"):
        d = rep["diff"]
        L.append("")
        L.append(f"  Compared with baseline {d.get('baseline', '')}: {len(d['regressions'])} regression(s), "
                 f"{len(d['improvements'])} improvement(s)")
        for x in d["regressions"]:
            L.append(f"    REGRESSION  {x['text']}")
        for x in d["improvements"]:
            L.append(f"    improved    {x['text']}")
    c = s["counts"]
    L.append("")
    L.append(f"  {c[SURVIVED]} survived, {c[WEAKENED]} weakened, {c[REMOVED]} removed, {c[UNTRACKED]} untracked, "
             f"{c[NOT_CHECKED]} not run.  " + SCOPE)
    return "\n".join(L)


def markdown(rep):
    s = rep["summary"]
    stages = [st["name"] for st in rep["stages"]]
    L = [f"# Countermeasure survival: {rep['name']}", "", f"**{s['verdict']}** (exit code {s['exit_code']})", "",
         "| countermeasure | found by | " + " | ".join(stages) + " |", "|---|---|" + "---|" * len(stages)]
    for c in rep["countermeasures"]:
        by = {r["stage"]: r["verdict"] for r in c["stages"]}
        L.append(f"| {c['title']} | {c['origin']} | " + " | ".join(by.get(n, "-") for n in stages) + " |")
    row = [stage_margin_text(st) or "-" for st in rep["stages"]]
    if any(x != "-" for x in row):
        L.append("| **margin** | engines | " + " | ".join(row) + " |")
    L.append("")
    for c in rep["countermeasures"]:
        for r in c["stages"]:
            if r["verdict"] in (WEAKENED, REMOVED, UNTRACKED):
                L += [f"## {r['verdict']}: {c['title']} at stage `{r['stage']}`", ""]
                L += [f"- {e}" for e in r["evidence"]]
                if r.get("cause"):
                    L += ["", f"**Why:** {r['cause']}"]
                if r.get("fix"):
                    L += ["", "**Fix:**"] + [f"{i + 1}. {f}" for i, f in enumerate(r["fix"])]
                L.append("")
    if rep.get("diff"):
        L += ["## Compared with the baseline", ""] + [f"- REGRESSION: {x['text']}" for x in rep["diff"]["regressions"]] + \
             [f"- improved: {x['text']}" for x in rep["diff"]["improvements"]] + [""]
    L += [SCOPE, ""]
    return "\n".join(L)


# ---------------------------------------------------------------------- diff
def _margin_of(st):
    m = st.get("margin") or {}
    if m.get("status") == "attack":
        return m["min_faults"]
    if m.get("status") == "none_up_to_k":
        return m["bound"]["k"] + 1
    return None


def diff(base, cur, baseline_name=""):
    """Did any countermeasure weaken between two reports? Returns dict(regressions, improvements)."""
    reg, imp = [], []
    cur_by = {c["id"]: c for c in cur["countermeasures"]}
    for c in base["countermeasures"]:
        n = cur_by.get(c["id"])
        if n is None:
            reg.append(dict(kind="disappeared", id=c["id"], where=c.get("where"),
                            text=f"{c['title']} ({c['id']}) is no longer found in the source or netlist"))
            continue
        bs = {r["stage"]: r for r in c["stages"]}
        for r in n["stages"]:
            b = bs.get(r["stage"])
            if b is None:
                continue
            if ORDER[r["verdict"]] > ORDER[b["verdict"]]:
                reg.append(dict(kind="verdict", id=c["id"], stage=r["stage"], was=b["verdict"], now=r["verdict"], where=n.get("where"),
                                text=f"{n['title']} at {r['stage']}: {b['verdict']} -> {r['verdict']}"
                                     + (f" ({r['evidence'][0]})" if r["evidence"] else "")))
            elif ORDER[r["verdict"]] < ORDER[b["verdict"]]:
                imp.append(dict(kind="verdict", id=c["id"], stage=r["stage"],
                                text=f"{n['title']} at {r['stage']}: {b['verdict']} -> {r['verdict']}"))
            else:
                bi, ni = _indep(b), _indep(r)
                if bi is not None and ni is not None and ni < bi:
                    reg.append(dict(kind="count", id=c["id"], stage=r["stage"], where=n.get("where"),
                                    text=f"{n['title']} at {r['stage']}: independent copies {bi} -> {ni}"))
    bst = {s["name"]: s for s in base["stages"]}
    for s in cur["stages"]:
        b = bst.get(s["name"])
        if not b:
            continue
        mb, mc = _margin_of(b), _margin_of(s)
        if mb is not None and mc is not None and mc < mb:
            reg.append(dict(kind="margin", stage=s["name"], was=mb, now=mc,
                            text=f"margin at {s['name']}: {mb} -> {mc} modelled faults"))
        elif mb is not None and mc is not None and mc > mb:
            imp.append(dict(kind="margin", stage=s["name"], text=f"margin at {s['name']}: {mb} -> {mc} modelled faults"))
        for key in ("margin_shots", "margin_faults"):
            vb = (b.get(key) or {}).get("min_shots" if key == "margin_shots" else "min_faults")
            vc = (s.get(key) or {}).get("min_shots" if key == "margin_shots" else "min_faults")
            if vb is not None and vc is not None and vc < vb:
                reg.append(dict(kind="margin", stage=s["name"], was=vb, now=vc, text=f"{key} at {s['name']}: {vb} -> {vc}"))
    return dict(baseline=baseline_name, regressions=reg, improvements=imp)


def _indep(r):
    m = r.get("measured") or {}
    if "netlist" in m:
        m = m["netlist"]
    return m.get("independent")


# ---------------------------------------------------------------------- SARIF
def _product():
    return paths.optional("faultbound_wt.evidence.sarif"), paths.optional("faultbound_wt.evidence.sarif_check")


def _loc(where, root, fallback):
    f, line = fallback, 1
    if where:
        p, _, ln = where.rpartition(":")
        if p and ln.isdigit():
            f, line = p, int(ln)
        else:
            f = where
    ap = os.path.abspath(f)
    rel = os.path.relpath(ap, root).replace(os.sep, "/")
    if rel.startswith(".."):
        rel = os.path.relpath(os.path.abspath(fallback), root).replace(os.sep, "/")
        line = 1
        if rel.startswith(".."):        # config outside the repository root: SARIF needs a repo-relative path
            rel = os.path.basename(fallback)
    return dict(physicalLocation=dict(artifactLocation=dict(uri=rel, uriBaseId="%SRCROOT%"), region=dict(startLine=max(1, line))))


def sarif(rep, repo_root=".", config_path="survival.yaml", command=""):
    """SARIF 2.1.0 document. Uses ext/product's schema URI, info URI and fingerprint convention when available."""
    ps, _ = _product()
    schema_uri = getattr(ps, "SCHEMA_URI", "https://json.schemastore.org/sarif-2.1.0.json")
    info_uri = getattr(ps, "INFO_URI", "https://github.com/Kavin-Re/GlitchSAT-Redundancy")
    root = os.path.abspath(repo_root)
    rules = []
    for r in RULES:
        props = {"tags": (["security"] if r["sev"] else []) + ["hardware", "fault-injection", "countermeasure-survival"],
                 "precision": "high"}
        if r["sev"]:
            props["security-severity"] = r["sev"]
        rules.append(dict(id=r["id"], name=r["name"], shortDescription=dict(text=r["short"]), fullDescription=dict(text=r["full"]),
                          help=dict(text=r["help"], markdown=r["help"]), defaultConfiguration=dict(level=r["level"]),
                          helpUri=info_uri, properties=props))
    idx = {r["id"]: i for i, r in enumerate(RULES)}
    level = {r["id"]: r["level"] for r in RULES}
    results = []

    def add(rule, msg, where, fp, props=None):
        results.append(dict(ruleId=rule, ruleIndex=idx[rule], level=level[rule], message=dict(text=msg),
                            locations=[_loc(where, root, config_path)],
                            partialFingerprints={"primaryLocationLineHash": fingerprint(*fp) + ":1"},
                            properties=props or {}))
    for c in rep["countermeasures"]:
        for r in c["stages"]:
            rule = {REMOVED: "GSS001", WEAKENED: "GSS002", UNTRACKED: "GSS004"}.get(r["verdict"])
            if not rule:
                continue
            msg = f"{c['title']}: {r['verdict']} at stage '{r['stage']}'. " + " ".join(e.rstrip(".") + "." for e in r["evidence"][:4])
            if r.get("cause"):
                msg += " Why: " + r["cause"]
            if r.get("fix"):
                msg += " Fix: " + r["fix"][0]
            add(rule, msg + " " + SCOPE, c.get("where"), (rule, rep["name"], c["id"], r["stage"]),
                dict(countermeasure=c["id"], kind=c["kind"], stage=r["stage"], verdict=r["verdict"], label=r.get("label")))
    s = rep["summary"]
    for b in s.get("margin_below_target", []):
        add("GSS003", f"Stage '{b['stage']}': the bounded search finds an attack with {b['min_faults']} modelled fault(s); "
                      f"the target is {b['target']}. " + SCOPE, None, ("GSS003", rep["name"], b["stage"], "target"))
    if s.get("margin_drop"):
        d = s["margin_drop"]
        add("GSS003", f"The minimum number of modelled faults drops from {d['reference']} at stage '{d['reference_stage']}' to "
                      f"{d['min_faults']} at stage '{d['stage']}'; {d.get('text', '')}. " + SCOPE, None, ("GSS003", rep["name"], d["stage"], "drop"))
    for x in (rep.get("diff") or {}).get("regressions", []):
        add("GSS005", "Regression against the baseline: " + x["text"] + ". " + SCOPE, x.get("where"),
            ("GSS005", rep["name"], x.get("id", ""), x.get("stage", ""), x["kind"]))
    run = dict(tool=dict(driver=dict(name="GlitchSAT check-survival", version=rep["tool"]["version"], informationUri=info_uri,
                                     rules=rules)),
               results=results,
               invocations=[dict(executionSuccessful=True, commandLine=command or "glitchsat check-survival")],
               properties=dict(summary=s, scope=SCOPE))
    return {"$schema": schema_uri, "version": "2.1.0", "runs": [run]}


def validate_sarif(doc):
    """Errors from ext/product's SARIF checks (schema subset + GitHub upload rules); None when it is not available."""
    _, chk = _product()
    if chk is None:
        return None
    errs = []
    try:
        errs += list(chk.schema_errors(doc) or [])
    except Exception as e:           # jsonschema missing: the GitHub rule check below still runs
        errs += [] if "jsonschema" in str(e).lower() else [f"schema check failed: {e}"]
    errs += list(chk.github_errors(doc) or [])
    return errs


def write(rep, json_path=None, md_path=None, sarif_path=None, repo_root=".", config_path="survival.yaml", command=""):
    if json_path:
        with open(json_path, "w") as f:
            json.dump(rep, f, indent=1, default=str)
    if md_path:
        with open(md_path, "w") as f:
            f.write(markdown(rep))
    if sarif_path:
        with open(sarif_path, "w") as f:
            json.dump(sarif(rep, repo_root, config_path, command), f, indent=1)
