"""Fault-resilience evidence report: one self-contained HTML file (no scripts, no external resources, printable) and the same
content as Markdown. Both are rendered from one document model so they cannot drift apart."""
import datetime, html, json, os, platform

from . import factors as F, loaders as L, margin as M

LIMITS = [
    "Faults are MODELLED single-cycle bit flips of gate outputs and flop Q nets. Stuck-at, multi-bit spatial, timing and voltage "
    "effects are not modelled, and nothing here was measured on hardware.",
    "Every verdict is bounded: at most the stated number of flips within the stated number of cycles, on this exact synthesized "
    "netlist. Another synthesis run, flow or tool version can change the minimum (the netlist hash identifies what was analysed).",
    "'No attack up to k' is not a proof of security; it says nothing about more flips, longer runs or other fault types.",
    "The number of flips is not the number of physical glitches. One supply, clock or EM glitch can flip several nets in one cycle; "
    "the margin estimate states which assumption it uses and shows the result under both extremes.",
    "The attack-potential figures use the PSA Certified and JIL point tables, but the factor levels are assumptions about a modelled "
    "result. Only an evaluation lab rates a real attack path; this report is design evidence that supports, and never replaces, "
    "that evaluation.",
    "An unbounded proof removes the cycle bound only. It keeps every other bound: this netlist, this fault model and count rule, "
    "this attacker input, this goal, this power-up assumption and the flip budgets that were checked.",
    "No source was found in which an evaluation lab states that it accepts formal pre-silicon fault results as evaluation evidence.",
]


def _ub_sentence(ub):
    up, us = ub.get("proved_up_to"), ub.get("smallest_attack")
    parts = []
    if up is not None:
        parts.append(f"proved: no attack with {'0' if up == 0 else 'up to ' + str(up)} flip(s) at any cycle")
    else:
        parts.append("no budget proved")
    if us is not None:
        parts.append(f"smallest attack at any cycle: {us} flip(s)")
    elif ub.get("checked_up_to") is not None:
        parts.append(f"no attack found at any cycle up to {ub['checked_up_to']} flip(s)")
    if ub.get("unknown"):
        parts.append("no verdict for k = " + ", ".join(map(str, ub["unknown"])))
    return "Unbounded check (" + ub["init"] + " power-up state): " + "; ".join(parts) + "."


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fmt_faults(fs):
    return ", ".join(f"{f['net']} @ cycle {f['cycle']}" for f in fs) or "-"


def _file_sha(p):
    try:
        return L.sha256_file(p)
    except OSError:
        return ""


def build_model(design, entries, tool_version, generated=None, inputs=None):
    """entries: list of dict(name, group, rating, surface, lint, netlist_path). Returns a list of sections."""
    S = []
    gen = generated or _now()
    # 0 summary
    blocks = [("p", "This report collects what GlitchSAT measured about how many modelled bit flips it takes to make the design "
                    "accept a wrong input, and what that could mean in the attack-potential language of PSA Certified and Common "
                    "Criteria (JIL). Plain reading first; details and every assumption follow.")]
    items = []
    for e in entries:
        g, r = e["group"], e["rating"]
        if g["min_faults"] is not None:
            s = f"{e['name']}: the smallest attack found needs {g['min_faults']} modelled flip(s)"
            s += f" (no attack with fewer, checked up to {g['max_bound']} flips in {g['cycles']} cycles)."
        elif g["no_attack_up_to"] is not None:
            s = f"{e['name']}: no attack with up to {g['no_attack_up_to']} modelled flip(s) in {g['cycles']} cycles (more flips not checked)."
        else:
            s = f"{e['name']}: no verdict."
        ub = e.get("unbounded")
        if ub:
            s += " " + _ub_sentence(ub)
        if r.get("status") == "rated":
            s += f" Margin estimate: {r['headline']}."
        items.append(s)
    blocks.append(("ul", items))
    blocks.append(("note", M.LAB_DISCLAIMER))
    S.append(("Summary in plain words", blocks))
    # 1 scope
    rows = []
    for e in entries:
        rep = e["group"]["representative"]
        sc = rep.get("scope") or {}
        rows.append([e["name"], rep.get("fault_model") or sc.get("fault_model", ""), rep.get("goal", "") or sc.get("goal", ""),
                     rep.get("attacker", "") or sc.get("input_treatment", ""), f"<= {e['group']['max_bound']} flips, {e['group']['cycles']} cycles",
                     sc.get("init_state", "known power-up state from the netlist (engine default)")])
    S.append(("Scope and bounds", [
        ("p", "Each result holds only inside these bounds. A 'minimum' is the smallest attack within them."),
        ("table", ["netlist variant", "fault model", "attack goal", "attacker input", "bound", "initial state"], rows),
        ("p", "Note recorded with the results: " + (entries[0]["group"]["representative"].get("note") or "-") if entries else "-")]))
    # 2 provenance
    rows = []
    for e in entries:
        g, p = e["group"], e["group"]["representative"]["provenance"]
        nl = e.get("netlist_path")
        actual = _file_sha(nl) if nl else ""
        match = L.sha_matches(actual, p.get("netlist_sha256")) if (actual and "netlist" in p.get("hash_scope", "")) else None
        chk = ("matches the file given" if match else "DOES NOT MATCH the file given" if match is False else
               "file not given or hash refers to the RTL source")
        sf, ln = e.get("surface"), e.get("lint")
        sfm = L.sha_matches(sf.get("netlist_sha256"), p.get("netlist_sha256")) if sf and "netlist" in p.get("hash_scope", "") else None
        lnm = L.sha_matches(ln.get("netlist_sha256"), p.get("netlist_sha256")) if ln and "netlist" in p.get("hash_scope", "") else None
        yosys = p.get("yosys") or e.get("netlist_creator") or "not recorded"
        rows.append([e["name"], p.get("netlist_path") or "-", f"{p.get('netlist_sha256') or '-'} ({p.get('hash_scope', '')})",
                     chk, {True: "same netlist", False: "DIFFERENT netlist", None: "-"}[sfm] + " / " +
                     {True: "same netlist", False: "DIFFERENT netlist", None: "-"}[lnm],
                     f"{e['group']['representative'].get('gates', '-')} gates, {e['group']['representative'].get('flops', '-')} flops",
                     yosys, f"{p.get('tool') or '-'} {p.get('tool_version') or ''}; z3 {p.get('z3') or 'not recorded'}"])
    files = [[os.path.relpath(f, inputs["root"]) if inputs and inputs.get("root") else f, _file_sha(f)[:16] or "-"]
             for f in (inputs or {}).get("files", [])]
    S.append(("Netlist provenance", [
        ("p", "The verdict depends on the exact synthesized netlist. Keep the hash with the result."),
        ("table", ["variant", "netlist", "SHA-256 (as recorded)", "hash check", "surface / lint netlist", "size", "Yosys", "solver"], rows),
        ("p", f"Report generated {gen} by GlitchSAT evidence {tool_version} on Python {platform.python_version()}."),
        ("table", ["input file", "SHA-256 (first 16)"], files) if files else ("p", "")]))
    # 3 results per assumption
    rows = []
    for e in entries:
        for r in e["group"]["runs"]:
            rows.append([e["name"], str(r["bound_k"]), str(r["cycles"]), r["verdict"],
                         "-" if r.get("min_faults") is None else str(r["min_faults"]), _fmt_faults(r["faults"]),
                         "-" if r.get("runtime_s") is None else f"{r['runtime_s']}", r.get("label", "")])
    blocks = [("p", "One row per solver run. Different netlist variants of the same RTL (stored netlist, Yosys flows) are different "
                    "assumptions about what gets fabricated; they are listed separately because synthesis can change the minimum."),
              ("table", ["variant", "max flips k", "cycles", "verdict", "min flips", "witness (net @ cycle)", "runtime s", "label"], rows)]
    bad = [e["name"] for e in entries if not e["group"]["consistent"]]
    if bad:
        blocks.append(("note", "Contradictory runs (a no-attack bound at or above a found minimum): " + ", ".join(bad)))
    for e in entries:
        for c in e["group"].get("contradictions", []):
            blocks.append(("note", f"Contradiction for {e['name']}: {c}."))
    S.append(("Results per assumption", blocks))
    # 3b unbounded proof status
    blocks = [("p", "The bounded runs above look at a fixed number of clock cycles. The unbounded check asks the same question for "
                    "any number of cycles: 'PROVED_UNBOUNDED' for k flips means no attack with k flips exists at any time, under the "
                    "same fault model, on the same netlist (matched by its hash) and for the same goal. It is a proof about the model, "
                    "not about a chip.")]
    rows = []
    for e in entries:
        ub = e.get("unbounded")
        if not ub:
            rows.append([e["name"], "not run for this netlist (no unbounded result with this netlist hash and goal)", "-", "-", "-", "-"])
            continue
        per = ", ".join(f"k={k}: {v}" for k, v in sorted(ub["by_k"].items()))
        oth = "; ".join(f"{i}: " + ", ".join(f"k={k} {v}" for k, v in sorted(d.items())) for i, d in ub["other_inits"].items())
        rows.append([e["name"], _ub_sentence(ub), per, oth or "-",
                     "all methods agree" if not ub["method_disagreements"] else "DISAGREEMENT: " + ", ".join(ub["method_disagreements"]),
                     f"{ub['tool']} ({ub['backend']}, Python {ub['python']}); netlist {ub['netlist']} {ub['netlist_sha256']}"])
    blocks.append(("table", ["variant", "status (known power-up state)", "verdict per flip budget", "other power-up assumptions",
                             "method agreement", "tool and netlist"], rows))
    notes = {e["unbounded"]["note"] for e in entries if e.get("unbounded") and e["unbounded"].get("note")}
    for n in sorted(notes):
        blocks.append(("note", "Recorded with the unbounded result: " + n))
    S.append(("Unbounded proof status", blocks))
    # 4 minimal attacks
    blocks = []
    for e in entries:
        g, sf = e["group"], e.get("surface")
        blocks.append(("h3", e["name"]))
        if g["witnesses"]:
            blocks.append(("ul", [f"witness {i + 1}: {_fmt_faults(w)}" for i, w in enumerate(g["witnesses"])]))
            rep = g["representative"]
            if rep.get("attacker_input"):
                blocks.append(("p", f"Attacker input used by the witness: {json.dumps(rep['attacker_input'])}."))
            if rep.get("explanation"):
                blocks.append(("p", "Engine explanation: " + rep["explanation"]))
            if rep.get("fix_pattern"):
                blocks.append(("p", "Generic fix pattern (not derived from this netlist): " + rep["fix_pattern"]))
        else:
            blocks.append(("p", "No attack within the bound."))
        if sf:
            st = M.surface_cycle_stats(sf)
            blocks.append(("p", f"Attack surface listing: {sf.get('count')} distinct minimum attack(s) of {sf.get('min_faults')} flip(s); "
                                f"complete = {sf.get('complete')} (stop reason: {sf.get('stop_reason')}; method: {sf.get('method')}). "
                                + (f"Distinct cycles per attack: {st['min_cycles']} to {st['max_cycles']}; "
                                   f"{st['single_cycle_attacks']} attack(s) fit in one cycle." if st else "")))
            lst = sf.get("attacks", [])[:15]
            blocks.append(("table", ["#", "flips (net @ cycle)", "attacker inputs that work"],
                           [[str(i + 1), ", ".join(f"{n} @ {c}" for n, c in a["faults"]), str(a.get("inputs", "-"))] for i, a in enumerate(lst)]))
            if sf.get("count", 0) > len(lst):
                blocks.append(("p", f"... {sf['count'] - len(lst)} more in {os.path.basename(sf.get('_path', 'the surface file'))}."))
    S.append(("Minimal attacks", blocks))
    # 5 attack surface
    blocks = []
    for e in entries:
        sf = e.get("surface")
        if not sf:
            continue
        blocks.append(("h3", e["name"]))
        blocks.append(("table", ["net", "kind", "copy", "used by attacks", "share", "cycles"],
                       [[n["net"], n.get("kind", ""), n.get("copy", ""), str(n["count"]), f"{100 * n.get('share', 0):.1f}%",
                         ", ".join(f"{c}:{k}" for c, k in sorted(n.get("cycles", {}).items()))] for n in sf.get("nets", [])[:15]]))
        blocks.append(("p", "Flips per copy: " + ", ".join(f"{k} {100 * v['share']:.1f}%" for k, v in sf.get("copies", {}).items())
                       + f" (copies identified from {sf.get('copy_source')}). Attacks by number of copies touched: "
                       + ", ".join(f"{k}: {v}" for k, v in sf.get("copies_touched", {}).items()) + "."))
        if sf.get("note"):
            blocks.append(("note", sf["note"]))
    if not blocks:
        blocks = [("p", "No attack-surface listing was given (run ext/surface attack_surface.py and pass --surface).")]
    S.append(("Attack surface", blocks))
    # 6 lint
    blocks = []
    for e in entries:
        ln = e.get("lint")
        if not ln:
            continue
        blocks.append(("h3", e["name"]))
        blocks.append(("p", f"Redundancy lint verdict: {ln.get('verdict')} (mode: {ln.get('mode')}); copies: "
                            + (", ".join(ln.get("copies", {})) or "-") + f"; single points: {len(ln.get('single_points', []))}."))
        blocks.append(("ul", ln.get("findings", [])))
    if not blocks:
        blocks = [("p", "No redundancy lint was given (run ext/surface merge_lint.py and pass --lint).")]
    S.append(("Redundancy lint (structural, no solver)", blocks))
    # 7 margin
    blocks = [("note", M.LAB_DISCLAIMER)]
    for e in entries:
        r = e["rating"]
        blocks.append(("h3", e["name"]))
        if r.get("status") != "rated":
            blocks.append(("p", r["headline"]))
            continue
        blocks.append(("p", "Result: " + r["headline"] + "."))
        a = r["assumptions"]
        blocks.append(("table", ["assumption (override with --assume key=value)", "value"], [[k, str(v)] for k, v in a.items()]))
        blocks.append(("ul", r["events_reasoning"] + r["notes"]))
        p = r["psa"]
        blocks.append(("table", ["PSA factor", "identification", "pts", "exploitation", "pts", "basis"],
                       [[x["factor"], x["id_level"], str(x["id_points"]), x["ex_level"], str(x["ex_points"]), x["basis"]] for x in p["rows"]]
                       + [["total", "", str(p["id_total"]), "", str(p["ex_total"]), f"= {p['total']} ({p['table_source']})"]]))
        blocks.append(("table", ["PSA level", "ceiling", "this estimate", "reading"],
                       [[f"L{l}", str(v["ceiling"]), str(p["total"]),
                         "within ceiling: in scope, must be resisted" if v["in_scope"] else f"above ceiling by {v['margin']}: out of scope"]
                        for l, v in p["levels"].items()]))
        if p.get("printed_example"):
            blocks.append(("note", f"{p['printed_example']['note']} ({p['printed_example']['source']})"))
        j = r["jil"]
        blocks.append(("table", ["JIL factor", "identification", "pts", "exploitation", "pts", "basis"],
                       [[x["factor"], x["id_level"], str(x["id_points"]), x["ex_level"], str(x["ex_points"]), x["basis"]] for x in j["rows"]]
                       + [["total", "", str(j["id_total"]), "", str(j["ex_total"]), f"= {j['total']}: '{j['band']}' ({j['band_source']})"]]))
        if r.get("minimum_source") and r["minimum_source"] != "bounded runs":
            blocks.append(("p", f"The flip count used here comes from the {r['minimum_source']}."))
        if r.get("timing"):
            t = r["timing"]
            blocks.append(("p", "Timing precision (reported, not scored): " + t["text"] + "."))
        if r.get("sensitivity"):
            blocks.append(("table", ["if ...", "events", "PSA", "JIL", "JIL band"],
                           [[s["assumption"], str(s["events"]), str(s["psa"]), str(s["jil"]), s["jil_band"]] for s in r["sensitivity"]]))
    blocks.append(("p", "Scheme rules that bear on the reading:"))
    blocks.append(("ul", [f"{t} ({s})" for t, s in F.PSA_SCOPE_NOTES + [F.PSA_MULTI_GLITCH_NOTE, F.PSA_RARE_NOTE, F.PSA_COUNTERMEASURE_NOTE,
                                                                         F.JIL_SYNC_NOTE, F.JIL_TIMING_NOTE, F.JIL_PERTURBATION_NOTE,
                                                                         F.JIL_EQUIPMENT_NOTE, F.JIL_ELAPSED_NOTE]]))
    blocks.append(("p", "Not scored, because no cited factor covers them: the number of distinct minimum attacks (more alternatives "
                        "plausibly make identification easier) and the timing precision between flips in different cycles. Both are "
                        "reported above for the evaluator to weigh."))
    S.append(("Margin estimate (attack potential)", blocks))
    S.append(("Limits", [("ul", LIMITS)]))
    S.append(("Sources", [("ul", [f"{F.PSA_DOC}: {F.PSA_URL}", f"{F.JIL_DOC}: {F.JIL_URL}",
                                  "Section, table and paragraph numbers are given next to every factor above."])]))
    return dict(title=f"Fault-resilience evidence report: {design}", generated=gen, sections=S)


CSS = """body{font:15px/1.45 Georgia,'Times New Roman',serif;color:#1d1d1f;max-width:62rem;margin:2rem auto;padding:0 1.2rem}
h1{font-size:1.6rem;margin:.2rem 0}h2{font-size:1.2rem;border-bottom:1px solid #888;padding-bottom:.15rem;margin-top:2rem}
h3{font-size:1.02rem;margin:1.2rem 0 .4rem}.meta{color:#555;font-size:.85rem}
table{border-collapse:collapse;width:100%;margin:.5rem 0 1rem;font:12.5px/1.35 'DejaVu Sans',Arial,sans-serif}
th,td{border:1px solid #bbb;padding:.25rem .4rem;vertical-align:top;text-align:left;word-break:break-word}th{background:#eee}
.note{border-left:4px solid #8a6d00;background:#fbf6e6;padding:.5rem .8rem;margin:.6rem 0}
.status{display:inline-block;border:1px solid #8a6d00;padding:.1rem .5rem;font:12px Arial,sans-serif;color:#5c4900}
code{font-size:.9em}@media print{body{margin:0;max-width:none;font-size:11pt}h2{break-after:avoid}table,.note{break-inside:avoid}
a{color:inherit;text-decoration:none}}"""


def to_html(model):
    e = html.escape
    out = ["<!DOCTYPE html>", '<html lang="en"><head><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width,initial-scale=1">', f"<title>{e(model['title'])}</title>",
           f"<style>{CSS}</style></head><body>", f"<h1>{e(model['title'])}</h1>",
           f'<p class="meta"><span class="status">Design evidence - not a certification or lab result</span> &nbsp; generated {e(model["generated"])}</p>']
    toc = "".join(f'<li><a href="#s{i}">{e(t)}</a></li>' for i, (t, _) in enumerate(model["sections"]))
    out.append(f"<nav><ol>{toc}</ol></nav>")
    for i, (title, blocks) in enumerate(model["sections"]):
        out.append(f'<h2 id="s{i}">{i + 1}. {e(title)}</h2>')
        for b in blocks:
            out.append(_html_block(b))
    out.append("</body></html>")
    return "\n".join(out) + "\n"


def _html_block(b):
    e = html.escape
    k = b[0]
    if k == "p":
        return f"<p>{e(b[1])}</p>" if b[1] else ""
    if k == "h3":
        return f"<h3>{e(b[1])}</h3>"
    if k == "note":
        return f'<div class="note">{e(b[1])}</div>'
    if k == "ul":
        return "<ul>" + "".join(f"<li>{e(str(x))}</li>" for x in b[1]) + "</ul>" if b[1] else ""
    if k == "table":
        head = "".join(f"<th>{e(h)}</th>" for h in b[1])
        body = "".join("<tr>" + "".join(f"<td>{e(str(c))}</td>" for c in row) + "</tr>" for row in b[2])
        return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    raise ValueError(k)


def _md_cell(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def to_markdown(model):
    out = [f"# {model['title']}", "", f"Design evidence - not a certification or lab result. Generated {model['generated']}.", ""]
    for i, (title, blocks) in enumerate(model["sections"]):
        out += [f"## {i + 1}. {title}", ""]
        for b in blocks:
            k = b[0]
            if k == "p" and b[1]:
                out += [b[1], ""]
            elif k == "h3":
                out += [f"### {b[1]}", ""]
            elif k == "note":
                out += [f"> {b[1]}", ""]
            elif k == "ul" and b[1]:
                out += [f"- {x}" for x in b[1]] + [""]
            elif k == "table":
                out.append("| " + " | ".join(_md_cell(h) for h in b[1]) + " |")
                out.append("|" + "---|" * len(b[1]))
                out += ["| " + " | ".join(_md_cell(c) for c in row) + " |" for row in b[2]]
                out.append("")
    return "\n".join(out).rstrip() + "\n"
