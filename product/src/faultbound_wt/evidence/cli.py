"""glitchsat evidence: margin estimate, evidence report, SARIF and CI check from GlitchSAT result files (no z3 needed,
except `check` on targets that have no recorded result: those call `glitchsat analyze`).

  glitchsat margin   --result R.json [...] [--surface S.json] [--assume key=value ...] [--json OUT]
  glitchsat evidence --design NAME --result R.json [...] [--surface S.json ...] [--lint L.json ...] [--netlist N.json ...]
                     [--unbounded U_k0.json ...]
                     [--assume ...] [--html OUT.html] [--md OUT.md]
  glitchsat sarif    --result R.json [...] [--surface ...] [--lint ...] [--netlist ...] [--target-min-faults N]
                     [--target-psa-level L] [--repo-root DIR] --out OUT.sarif
  glitchsat check    --targets glitchsat.toml [--sarif OUT.sarif] [--report-dir DIR]
  glitchsat validate-sarif FILE [--schema FULL_SCHEMA.json]
  glitchsat evidence-example OUTDIR            (regenerates the bundled V0/V1/V2 example outputs)
Exit codes: 0 ok / margin met; 1 margin below target (check) or SARIF invalid (validate-sarif); 2 no verdict; 3 input error.
"""
import argparse, json, os, sys
try:
    import tomllib
except ModuleNotFoundError:          # Python 3.10: the same parser, from the tomli package
    import tomli as tomllib

from .. import __version__
from . import loaders as L, margin as M, report as R, sarif as SA, sarif_check as SC

EXIT_OK, EXIT_BELOW, EXIT_UNKNOWN, EXIT_ERROR = 0, 1, 2, 3
SUBCOMMANDS = ("margin", "evidence", "sarif", "check", "validate-sarif", "evidence-example")
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


class _P(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_ERROR)


def _netlist_meta(path):
    meta = dict(path=path, sha256=L.sha256_file(path), creator="")
    try:
        with open(path, encoding="utf-8") as f:
            meta["creator"] = json.load(f).get("creator", "")
    except (OSError, ValueError):
        pass
    return meta


def _match_unbounded(ubs, h, goal):
    """Unbounded results for this netlist hash and goal, summarised; plus a contradiction message or ''."""
    items = [u for u in ubs if L.sha_matches(u["netlist_sha256"], h) and (not goal or not u["goal"] or L.goal_key(u["goal"]) == L.goal_key(goal))]
    return L.summarize_unbounded(items) if items else None


def _ub_contradiction(g, ub):
    if not ub:
        return ""
    m, up, us = g["min_faults"], ub.get("proved_up_to"), ub.get("smallest_attack")
    if m is not None and up is not None and up >= m:
        return f"the unbounded check proves no attack with up to {up} flip(s), but a bounded run found one with {m}"
    if m is not None and us is not None and us > m:
        return f"the bounded runs found an attack with {m} flip(s), but the unbounded check's smallest attack has {us}"
    return ""


def assemble(results, surfaces=(), lints=(), netlists=(), assume=None, design=None, repo_root=".", src_map=None, unbounded=()):
    rs = []
    for p in results:
        rs.extend(L.load_results(p, design))
    if not rs:
        raise L.InputError("no results matched")
    sfs = [L.load_surface(p) for p in surfaces]
    lns = [L.load_lint(p) for p in lints]
    nls = [_netlist_meta(p) for p in netlists]
    ubs = [L.load_unbounded(p) for p in unbounded]
    entries = []
    for g in L.group_variants(rs):
        h = g["netlist_sha256"]
        hs = g["representative"]["provenance"].get("hash_scope", "")
        is_nl = "netlist" in hs
        sf = next((s for s in sfs if is_nl and L.sha_matches(s.get("netlist_sha256"), h)), None)
        ln = next((x for x in lns if is_nl and L.sha_matches(x.get("netlist_sha256"), h)), None)
        nl = next((n for n in nls if is_nl and L.sha_matches(n["sha256"], h)), None)
        if nl is None and len(nls) == 1 and len({(x["top"], x["variant"]) for x in rs}) == 1:
            nl = nls[0]
        nlp = nl["path"] if nl else None
        if nlp is None:
            cand = g["representative"]["provenance"].get("netlist_path")
            if cand and os.path.isfile(os.path.join(repo_root, cand)):
                c2 = os.path.join(repo_root, cand)
                if is_nl and L.sha_matches(L.sha256_file(c2), h):
                    nlp = c2
        rec_path = g["representative"]["provenance"].get("netlist_path") or ""
        disp = rec_path if (nl and rec_path and not os.path.isabs(rec_path) and ".." not in rec_path.split("/")) else None
        ub = _match_unbounded(ubs, h, g["representative"].get("goal", "")) if is_nl else None
        ubc = _ub_contradiction(g, ub)
        if ubc:
            g["consistent"] = False
            g.setdefault("contradictions", []).append(ubc)
        entries.append(dict(name=f"{g['top']} / {g['variant']}", group=g, rating=M.rate_group(g, assume, sf, ub), surface=sf, lint=ln,
                            unbounded=ub,
                            netlist_path=nlp, netlist_creator=(nl or {}).get("creator", ""),
                            locator=SA.Locator(nlp or g["representative"]["provenance"].get("netlist_path"), g["top"], repo_root, src_map, disp,
                                           g["representative"]["provenance"].get("source_path"))))
    return entries


def _common(ap):
    ap.add_argument("--result", action="append", default=[], required=True, metavar="FILE",
                    help="result JSON: product report, engine run, or reproduce_summary.json (repeatable)")
    ap.add_argument("--design", help="with a reproduce summary: only rows of this design (e.g. v2); also the report title")
    ap.add_argument("--surface", action="append", default=[], metavar="FILE", help="attack-surface JSON (matched by netlist hash)")
    ap.add_argument("--lint", action="append", default=[], metavar="FILE", help="merge-lint JSON (matched by netlist hash)")
    ap.add_argument("--netlist", action="append", default=[], metavar="FILE", help="netlist JSON for hash check and source lines")
    ap.add_argument("--unbounded", action="append", default=[], metavar="FILE",
                    help="unbounded-proof result JSON, one per flip budget (matched by netlist hash and goal; repeatable)")
    ap.add_argument("--assume", action="append", default=[], metavar="KEY=VALUE",
                    help="override an assumption of the margin estimate; keys: " + ", ".join(sorted(M.DEFAULTS)))
    ap.add_argument("--repo-root", default=".", help="root for relative paths in SARIF (default: current directory)")
    ap.add_argument("--src-map", action="append", default=[], metavar="FROM=TO", help="rewrite a Yosys src path prefix (SARIF lines)")


def _src_map(pairs):
    return dict(p.split("=", 1) for p in pairs if "=" in p)


def _print_margin(entries, out=None):
    out = out or sys.stdout
    for e in entries:
        r = e["rating"]
        print(f"== {e['name']}", file=out)
        print(f"   {r['headline']}", file=out)
        if r.get("status") == "rated":
            for w in r["events_reasoning"] + r["notes"]:
                print(f"   - {w}", file=out)
            for s in r.get("sensitivity", []):
                print(f"   if {s['assumption']}: events {s['events']}, PSA {s['psa']}, JIL {s['jil']} ({s['jil_band']})", file=out)
            if r.get("timing"):
                print(f"   timing (not scored): {r['timing']['text']}", file=out)
        if e.get("unbounded"):
            print(f"   {R._ub_sentence(e['unbounded'])}", file=out)
        for c in e["group"].get("contradictions", []):
            print(f"   CONTRADICTION: {c}", file=out)
    print(f"Note: {M.LAB_DISCLAIMER}", file=out)


def _strip(entries):
    out = []
    for e in entries:
        r = e["rating"]
        d = dict(name=e["name"], min_faults=e["group"]["min_faults"], no_attack_up_to=e["group"]["no_attack_up_to"],
                 consistent=e["group"]["consistent"], status=r.get("status"), headline=r.get("headline"))
        if r.get("status") == "rated":
            d.update(events=r["events"], psa_total=r["psa"]["total"], psa_levels=r["psa"]["levels"], jil_total=r["jil"]["total"],
                     jil_band=r["jil"]["band"], assumptions=r["assumptions"], events_reasoning=r["events_reasoning"],
                     sensitivity=r["sensitivity"], disclaimer=r["disclaimer"], minimum_source=r.get("minimum_source"),
                     timing=r.get("timing"))
        ub = e.get("unbounded")
        if ub:
            d["unbounded"] = dict(init=ub["init"], proved_up_to=ub["proved_up_to"], smallest_attack=ub["smallest_attack"],
                                  checked_up_to=ub["checked_up_to"], by_k=ub["by_k"])
        if e["group"].get("contradictions"):
            d["contradictions"] = e["group"]["contradictions"]
        out.append(d)
    return out


def write_reports(design, entries, html_path=None, md_path=None, inputs=None, generated=None):
    model = R.build_model(design, entries, __version__, generated=generated, inputs=inputs)
    for path, fn in ((html_path, R.to_html), (md_path, R.to_markdown)):
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(fn(model))
    return model


def write_sarif(entries, path, targets, command="", repo_root="."):
    arts, seen = [], set()
    for e in entries:
        if e.get("netlist_path"):
            uri = e["locator"].physical()["artifactLocation"]["uri"]
            if uri not in seen:
                seen.add(uri)
                arts.append(dict(uri=uri, sha256=L.sha256_file(e["netlist_path"])))
    doc = SA.build(entries, targets, __version__, command, arts)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    return doc


def cmd_check(args):
    try:
        with open(args.targets, "rb") as f:
            cfg = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        print(f"error: cannot read targets file: {e}", file=sys.stderr)
        return EXIT_ERROR
    base = os.path.dirname(os.path.abspath(args.targets))
    dflt = cfg.get("defaults", {})
    tgts = cfg.get("target", [])
    if not tgts:
        print("error: no [[target]] entries", file=sys.stderr)
        return EXIT_ERROR
    os.makedirs(args.report_dir, exist_ok=True)
    all_entries, worst, lines = [], EXIT_OK, []

    def P(x):
        return x if os.path.isabs(x) else os.path.join(base, x)

    for t in tgts:
        t = dict(dflt, **t)
        name = t.get("name") or os.path.splitext(os.path.basename(t.get("netlist", "target")))[0]
        if not all(c.isalnum() or c in "-_." for c in name):
            print(f"error: target name {name!r} may contain only letters, digits, - _ .", file=sys.stderr)
            return EXIT_ERROR
        results = t.get("result")
        results = [results] if isinstance(results, str) else (results or [])
        if not results:
            if "netlist" not in t:
                print(f"error: target {name}: give `netlist` (to run the analysis) or `result` (recorded)", file=sys.stderr)
                return EXIT_ERROR
            from .. import cli as main_cli
            out = os.path.join(args.report_dir, f"{name}.result.json")
            argv = ["analyze", P(t["netlist"]), f"--report={out}", "--exit-zero"]
            for k, flag in (("config", "--config"), ("top", "--top")):
                if t.get(k):
                    argv.append(f"{flag}={P(t[k]) if k == 'config' else t[k]}")
            for k, flag in (("max_flips", "--max-flips"), ("cycles", "--cycles")):
                if t.get(k) is not None:
                    argv.append(f"{flag}={int(t[k])}")
            code = main_cli.main(argv)
            if code not in (0, 1) or not os.path.isfile(out):
                print(f"error: target {name}: analysis failed (exit {code})", file=sys.stderr)
                worst = max(worst, EXIT_ERROR if code == 3 else EXIT_UNKNOWN)
                continue
            results = [out]
        else:
            results = [P(x) for x in results]
        assume = M.parse_assumptions([f"{k}={v}" for k, v in (t.get("assume") or {}).items()])
        if t.get("fault_type"):
            assume.setdefault("fault_type", t["fault_type"])
        if t.get("target_psa_level"):
            assume.setdefault("target_psa_level", int(t["target_psa_level"]))
        ents = assemble(results, [P(x) for x in _aslist(t.get("surface"))], [P(x) for x in _aslist(t.get("lint"))],
                        [P(x) for x in _aslist(t.get("netlist"))] if str(t.get("netlist", "")).endswith(".json") else [],
                        assume, t.get("design"), args.repo_root, _src_map(_aslist(t.get("src_map"))),
                        [P(x) for x in _aslist(t.get("unbounded"))])
        for e in ents:
            e["name"] = f"{name}: {e['name']}"
        write_reports(name, ents, os.path.join(args.report_dir, f"{name}.evidence.html"), os.path.join(args.report_dir, f"{name}.evidence.md"),
                      inputs=dict(files=results, root=args.repo_root))
        tmin, tlvl = t.get("target_min_faults"), t.get("target_psa_level")
        for e in ents:
            g, r = e["group"], e["rating"]
            if g["unknown"] and g["min_faults"] is None and g["no_attack_up_to"] is None:
                worst = max(worst, EXIT_UNKNOWN)
                lines.append(f"UNKNOWN  {e['name']}: no verdict")
                continue
            below = []
            m_eff = r["min_flips"] if r.get("status") == "rated" and not r["min_flips_is_lower_bound"] else g["min_faults"]
            if tmin is not None and m_eff is not None and m_eff < int(tmin):
                below.append(f"min flips {m_eff} < target {tmin}")
            if tlvl is not None and r.get("status") == "rated" and not r["psa"]["above_target"]:
                below.append(f"PSA estimate {r['psa']['total']} within L{tlvl} ceiling {M.F.PSA_LEVELS[int(tlvl)]}")
            if r.get("status") == "no_fault_needed":
                below.append("goal reached with 0 flips")
            if not g["consistent"]:
                below.append("contradictory runs")
            state = "BELOW" if below else "OK"
            if below:
                worst = max(worst, EXIT_BELOW) if worst != EXIT_ERROR else worst
            lines.append(f"{state:8s} {e['name']}: {r['headline']}" + (f"  [{'; '.join(below)}]" if below else ""))
        e_targets = dict(min_faults=int(tmin) if tmin is not None else None, psa_level=int(tlvl) if tlvl is not None else None)
        for e in ents:
            e["targets"] = e_targets
        all_entries.extend(ents)
    if args.sarif and all_entries:
        # one SARIF for all targets; per-target thresholds are applied entry by entry
        results = []
        for e in all_entries:
            results.extend(SA.design_results(e, e["targets"]))
        doc = SA.build([], {}, __version__, f"glitchsat check --targets {os.path.basename(args.targets)}")
        doc["runs"][0]["results"] = results
        with open(args.sarif, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=1)
            f.write("\n")
    for l in lines:
        print(l)
    print(f"Note: {M.LAB_DISCLAIMER}")
    return worst


def _aslist(x):
    return [] if x is None else ([x] if isinstance(x, str) else list(x))


def cmd_example(outdir):
    """Regenerate the example outputs from the recorded V0/V1/V2 results bundled with the package."""
    rec = os.path.join(DATA, "recorded")
    os.makedirs(outdir, exist_ok=True)
    allent = []
    for v in ("v0", "v1", "v2"):
        res = sorted(os.path.join(rec, "reproduce", f) for f in os.listdir(os.path.join(rec, "reproduce")) if f.startswith(v + "_"))
        sf = [os.path.join(rec, "surface", f"{v}_spike_surface.json")]
        ln = [os.path.join(rec, "lint", f"{v}_spike_lint.json")]
        nl = [os.path.join(os.path.dirname(DATA), "..", "examples", f"{v}.json")]
        nl = [os.path.normpath(p) for p in nl if os.path.isfile(p)]
        ub = sorted(os.path.join(rec, "unbounded", f) for f in os.listdir(os.path.join(rec, "unbounded")) if f.startswith(v + "_"))
        ents = assemble(res, sf, ln, nl, {}, None, rec, None, ub)
        write_reports(v.upper(), ents, os.path.join(outdir, f"{v}_evidence.html"), os.path.join(outdir, f"{v}_evidence.md"),
                      inputs=dict(files=res + sf + ln + nl + ub, root=os.path.dirname(os.path.dirname(DATA))), generated="(example: regenerate to stamp the time)")
        allent.extend(ents)
        with open(os.path.join(outdir, f"{v}_margin.json"), "w", encoding="utf-8") as f:
            json.dump(_strip(ents), f, indent=1, default=str)
            f.write("\n")
    write_sarif(allent, os.path.join(outdir, "glitchsat.sarif"), dict(min_faults=2, psa_level=None),
                "glitchsat evidence-example (recorded V0/V1/V2 results)", rec)
    return EXIT_OK


def main(argv):
    cmd, rest = argv[0], argv[1:]
    ap = _P(prog=f"glitchsat {cmd}", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    try:
        if cmd == "validate-sarif":
            ap.add_argument("file")
            ap.add_argument("--schema", help="full SARIF 2.1.0 schema file (default: bundled transcribed subset)")
            a = ap.parse_args(rest)
            r = SC.check(a.file, a.schema)
            print(f"schema ({os.path.basename(r['schema_used'])}): " + ("not checked (pip install jsonschema)" if not r["schema_checked"]
                                                                        else ("OK" if not r["schema"] else f"{len(r['schema'])} error(s)")))
            for x in (r["schema"] or []) + r["github"]:
                print("  " + x)
            print("GitHub code-scanning rules: " + ("OK" if not r["github"] else f"{len(r['github'])} problem(s)"))
            return EXIT_OK if r["ok"] or (not r["schema_checked"] and not r["github"]) else EXIT_BELOW
        if cmd == "evidence-example":
            ap.add_argument("outdir")
            return cmd_example(ap.parse_args(rest).outdir)
        if cmd == "check":
            ap.add_argument("--targets", default="glitchsat.toml")
            ap.add_argument("--sarif", default="glitchsat.sarif")
            ap.add_argument("--report-dir", default="glitchsat-evidence")
            ap.add_argument("--repo-root", default=".")
            return cmd_check(ap.parse_args(rest))
        _common(ap)
        if cmd == "margin":
            ap.add_argument("--json", metavar="FILE")
        elif cmd == "evidence":
            ap.add_argument("--html", metavar="FILE")
            ap.add_argument("--md", metavar="FILE")
        elif cmd == "sarif":
            ap.add_argument("--out", required=True)
            ap.add_argument("--target-min-faults", type=int)
            ap.add_argument("--target-psa-level", type=int, choices=[2, 3, 4])
        a = ap.parse_args(rest)
        assume = M.parse_assumptions(a.assume)
        ents = assemble(a.result, a.surface, a.lint, a.netlist, assume, a.design, a.repo_root, _src_map(a.src_map), a.unbounded)
        if cmd == "margin":
            _print_margin(ents)
            if a.json:
                with open(a.json, "w", encoding="utf-8") as f:
                    json.dump(_strip(ents), f, indent=1, default=str)
            return EXIT_OK
        if cmd == "evidence":
            if not (a.html or a.md):
                ap.error("give --html and/or --md")
            write_reports(a.design or ents[0]["group"]["top"], ents, a.html, a.md,
                          inputs=dict(files=a.result + a.surface + a.lint + a.netlist + a.unbounded, root=a.repo_root))
            print(f"wrote {' and '.join(x for x in (a.html, a.md) if x)}")
            return EXIT_OK
        if cmd == "sarif":
            write_sarif(ents, a.out, dict(min_faults=a.target_min_faults, psa_level=a.target_psa_level),
                        "glitchsat sarif " + " ".join(rest), a.repo_root)
            print(f"wrote {a.out}")
            return EXIT_OK
    except (L.InputError, M.AssumptionError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_ERROR
    ap.error(f"unknown command {cmd}")


def entry():
    """console script `glitchsat-evidence SUBCOMMAND ...`"""
    if len(sys.argv) < 2 or sys.argv[1] not in SUBCOMMANDS:
        print(__doc__)
        return EXIT_ERROR if len(sys.argv) >= 2 else EXIT_OK
    return main(sys.argv[1:])
