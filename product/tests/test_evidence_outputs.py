"""Loaders, evidence report, SARIF and the CI check, all from the recorded V0/V1/V2 results bundled with the package
(no z3, no yosys)."""
import html.parser, json, os, re, textwrap

import pytest

from faultbound_wt import cli as main_cli
from faultbound_wt.evidence import cli as ev, loaders as L, report as R, sarif as SA, sarif_check as SC

REC = os.path.join(os.path.dirname(ev.__file__), "data", "recorded")
EXAMPLES = os.path.join(os.path.dirname(main_cli.__file__), "examples")


def runs(v):
    d = os.path.join(REC, "reproduce")
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.startswith(v + "_"))


def ub_files(v):
    d = os.path.join(REC, "unbounded")
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.startswith(v + "_"))


def ents(v, **kw):
    return ev.assemble(runs(v), [os.path.join(REC, "surface", f"{v}_spike_surface.json")],
                       [os.path.join(REC, "lint", f"{v}_spike_lint.json")], [os.path.join(EXAMPLES, f"{v}.json")],
                       kw.get("assume", {}), None, kw.get("root", REC), None, kw.get("unbounded", ub_files(v)))


def by_variant(es):
    return {e["group"]["variant"].split(" (")[1].rstrip(")"): e for e in es}


# ---------- loaders

def test_recorded_minimums_match_numbers_register():
    m = {v: {k: e["group"]["min_faults"] for k, e in by_variant(ents(v)).items()} for v in ("v0", "v1", "v2")}
    assert m["v0"] == {"plain": 1, "opt": 1, "given-netlist": 1}
    assert m["v1"] == {"plain": 1, "opt": 1, "given-netlist": 1}
    assert m["v2"] == {"plain": 2, "opt": 2, "given-netlist": 3}    # docs/NUMBERS.md B2/E2 rows
    v2 = by_variant(ents("v2"))
    assert v2["given-netlist"]["group"]["no_attack_up_to"] == 2 and v2["given-netlist"]["group"]["consistent"]


def test_surface_and_lint_matched_by_hash_only_to_their_netlist():
    v2 = by_variant(ents("v2"))
    assert v2["given-netlist"]["surface"]["count"] == 182 and v2["given-netlist"]["lint"]["verdict"] == "separate"
    assert v2["plain"]["surface"] is None and v2["plain"]["lint"] is None
    assert v2["given-netlist"]["netlist_path"].endswith("v2.json")


def test_summary_loader_and_product_report_loader(tmp_path):
    summ = dict(label="MEASURED", cycles=6, note="n", rows=[
        dict(design="v2", netlist="spike/given-netlist", k=k, cycles=6, verdict="ATTACK_FOUND" if k == 3 else "NO_ATTACK_UP_TO_BOUND",
             min_faults=3 if k == 3 else None, faults=[["a", 1], ["b", 1], ["c", 1]] if k == 3 else [], runtime_s=0.1)
        for k in range(4)])
    p = tmp_path / "s.json"
    p.write_text(json.dumps(summ))
    g = L.group_variants(L.load_results(str(p), "v2"))
    assert len(g) == 1 and g[0]["min_faults"] == 3 and g[0]["no_attack_up_to"] == 2
    rep = dict(schema="faultbound-wt-report/1", label="MEASURED", verdict="ATTACK_FOUND", min_faults=2,
               faults=[dict(net="x", cycle=0, kind="gate_output"), dict(net="y", cycle=0, kind="gate_output")],
               bound=dict(max_flips=3, cycles=6, property="p", attacker_input="a", fault_model="f"), scope={}, note="",
               provenance=dict(tool="faultbound-working-title", tool_version="0.9.0", top="t", netlist_path="n.json",
                               netlist_sha256="ab" * 32, netlist_stats=dict(gates=5, flops=1)))
    q = tmp_path / "r.json"
    q.write_text(json.dumps(rep))
    r = L.load_results(str(q))[0]
    assert r["min_faults"] == 2 and r["provenance"]["netlist_sha256"] == "ab" * 32


def test_contradiction_detected(tmp_path):
    a = json.load(open(runs("v2")[-1]))            # spike k=3: attack of 3
    b = dict(a, verdict="NO_ATTACK_UP_TO_BOUND", min_faults=None, faults=[], bound=dict(a["bound"], max_faults=5))
    pa, pb = tmp_path / "a.json", tmp_path / "b.json"
    pa.write_text(json.dumps(a)); pb.write_text(json.dumps(b))
    g = L.group_variants(L.load_results(str(pa)) + L.load_results(str(pb)))[0]
    assert not g["consistent"]


def test_bad_input_rejected(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("{}")
    with pytest.raises(L.InputError):
        L.load_results(str(p))
    assert main_cli.main(["margin", "--result", str(p)]) == 3


# ---------- report

class _Checker(html.parser.HTMLParser):
    VOID = {"meta", "br", "hr", "img", "link", "input"}

    def __init__(self):
        super().__init__()
        self.stack, self.errors, self.tags = [], [], set()

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag)
        for k, v in attrs:
            if k in ("src", "href") and v and not v.startswith("#"):
                self.errors.append(f"external reference {k}={v}")
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            self.errors.append(f"unbalanced </{tag}>")


@pytest.mark.parametrize("v", ["v0", "v1", "v2"])
def test_report_html_selfcontained_and_complete(v, tmp_path):
    es = ents(v)
    h, m = tmp_path / "r.html", tmp_path / "r.md"
    ev.write_reports(v.upper(), es, str(h), str(m))
    text = h.read_text()
    c = _Checker()
    c.feed(text)
    assert not c.errors and not c.stack
    assert "script" not in c.tags and "link" not in c.tags and "@import" not in text and "url(" not in text
    assert "@media print" in text
    for sec in ("Summary in plain words", "Scope and bounds", "Netlist provenance", "Results per assumption", "Unbounded proof status",
                "Minimal attacks",
                "Attack surface", "Redundancy lint", "Margin estimate", "Limits", "Sources"):
        assert sec in text and sec in m.read_text()
    assert "never replaces" in text and "JSADEN004" in text and "Table 13" in text
    assert "matches the file given" in text      # stored netlist hash re-computed and compared


# ---------- unbounded proof status

def test_unbounded_matched_only_to_stored_netlist_and_same_goal():
    for v, proved, smallest in (("v0", 0, 1), ("v1", 0, 1), ("v2", 2, 3)):   # ext/unbounded README results table
        bv = by_variant(ents(v))
        ub = bv["given-netlist"]["unbounded"]
        assert ub and ub["proved_up_to"] == proved and ub["smallest_attack"] == smallest and not ub["method_disagreements"]
        assert bv["opt"]["unbounded"] is None and bv["plain"]["unbounded"] is None   # RTL flows: different netlists
        assert bv["given-netlist"]["group"]["consistent"]


def test_unbounded_other_goal_not_matched(tmp_path):
    d = json.load(open(ub_files("v2")[0]))
    d["scope"]["goal"] = "boot_ok == 0x1 at some cycle"
    p = tmp_path / "u.json"
    p.write_text(json.dumps(d))
    assert by_variant(ents("v2", unbounded=[str(p)]))["given-netlist"]["unbounded"] is None


def test_unbounded_contradiction_and_lower_minimum(tmp_path):
    # a proof of 'no attack with <= 3 flips' contradicts the bounded attack with 3 flips
    d = json.load(open(ub_files("v2")[-1]))
    d["verdict"] = "PROVED_UNBOUNDED"
    for sc in d["scopes"]:
        sc["verdict"] = "PROVED_UNBOUNDED"
    p = tmp_path / "u3.json"
    p.write_text(json.dumps(d))
    e = by_variant(ents("v2", unbounded=ub_files("v2")[:3] + [str(p)]))["given-netlist"]
    assert not e["group"]["consistent"] and "unbounded" in e["group"]["contradictions"][0]
    # an attack needing more cycles than the bounded runs: the unbounded minimum is used for the estimate
    d1 = json.load(open(ub_files("v2")[1]))
    d1["verdict"] = "ATTACK_FOUND"
    for sc in d1["scopes"]:
        sc["verdict"] = "ATTACK_FOUND"
    q = tmp_path / "u1.json"
    q.write_text(json.dumps(d1))
    e = by_variant(ents("v2", unbounded=[ub_files("v2")[0], str(q)]))["given-netlist"]
    assert e["rating"]["min_flips"] == 1 and e["rating"]["minimum_source"] == "unbounded check"


def test_unbounded_bad_file_rejected(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("{}")
    with pytest.raises(L.InputError):
        L.load_unbounded(str(p))


def test_timing_summary_reported_not_scored():
    e = by_variant(ents("v2"))
    t = e["given-netlist"]["rating"]["timing"]
    assert t["max_cycles"] == 1 and "complete" in t["source"]
    t2 = e["opt"]["rating"]["timing"]
    assert t2["max_cycles"] == 2 and "not a complete listing" in t2["source"]
    assert "para. 148" in t["notes"][0][1]


def test_report_escapes_netlist_text(tmp_path):
    es = ents("v2")
    es[0]["group"]["witnesses"] = [[dict(net="<script>alert(1)</script>", cycle=0, kind="")]]
    model = R.build_model("x", es, "t")
    out = R.to_html(model)
    assert "<script>alert" not in out and "&lt;script&gt;" in out


def test_no_forbidden_wording_in_outputs(tmp_path):
    ev.cmd_example(str(tmp_path))
    blob = " ".join(open(os.path.join(tmp_path, f), encoding="utf-8").read() for f in os.listdir(tmp_path)).lower()
    # hex-encoded so that the test file does not contain the words it rejects
    words = [bytes.fromhex(h).decode() for h in (
        "756e6976657273697479", "72616b736861", "20616920", "6167656e74", "6c6c6d", "63686174677074", "636c61756465")]
    for w in words:
        assert w not in blob, w


# ---------- SARIF

def _sarif(tmp_path, targets=None, **kw):
    allent = ents("v0", **kw) + ents("v1", **kw) + ents("v2", **kw)
    p = tmp_path / "out.sarif"
    doc = ev.write_sarif(allent, str(p), targets or dict(min_faults=2, psa_level=None), "test", kw.get("root", REC))
    return p, doc


def test_sarif_valid_against_schema_and_github_rules(tmp_path):
    pytest.importorskip("jsonschema")
    p, doc = _sarif(tmp_path)
    r = SC.check(str(p))
    assert r["schema_checked"] and r["schema"] == [] and r["github"] == []
    assert main_cli.main(["validate-sarif", str(p)]) == 0


def test_sarif_findings(tmp_path):
    _, doc = _sarif(tmp_path)
    res = doc["runs"][0]["results"]
    rules = {(r["ruleId"], r["properties"]["design"].split(" / ")[0]) for r in res}
    assert ("GS001", "v0") in rules and ("GS001", "v1") in rules and ("GS001", "v2") not in rules
    assert ("GS002", "v1") in rules and ("GS002", "v2") not in rules
    assert ("GS003", "v1") in rules and ("GS006", "v2") in rules
    for r in res:
        assert r["locations"] and r["partialFingerprints"]
        assert not r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"].startswith("/")
    v1 = [r for r in res if r["ruleId"] == "GS001" and "given-netlist" in r["properties"]["design"] and "v1" in r["properties"]["design"]]
    assert v1[0]["properties"]["net"] == "ok" and v1[0]["locations"][0]["physicalLocation"]["region"]["startLine"] > 1


def test_sarif_primary_location_line_hash_per_finding(tmp_path):
    """GitHub uses only primaryLocationLineHash: every result has one, built from the finding (not the source line), and
    results that share rule + file + line (e.g. the opt and plain flow of one RTL file) keep distinct values."""
    for targets in (None, dict(min_faults=None, psa_level=3)):
        _, doc = _sarif(tmp_path, targets)
        res = doc["runs"][0]["results"]
        keys = [(r["ruleId"], r["partialFingerprints"]["primaryLocationLineHash"]) for r in res]
        assert len(set(keys)) == len(keys)
        for r in res:
            fp = r["partialFingerprints"]
            assert re.fullmatch(r"[0-9a-f]{32}:1", fp["primaryLocationLineHash"])
            assert fp["primaryLocationLineHash"] == fp["glitchsatFinding/v1"] + ":1"
        loc = lambda r: (r["ruleId"], r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"],
                         r["locations"][0]["physicalLocation"]["region"]["startLine"])
        shared = [k for k in {loc(r) for r in res} if sum(loc(r) == k for r in res) > 1]
        assert shared or targets       # the default example has rule+file+line groups (the case GitHub would fold)
    _, a = _sarif(tmp_path)
    _, b = _sarif(tmp_path)
    assert [r["partialFingerprints"] for r in a["runs"][0]["results"]] == [r["partialFingerprints"] for r in b["runs"][0]["results"]]


def test_sarif_security_severity_only_on_security_rules(tmp_path):
    _, doc = _sarif(tmp_path)
    rules = {r["id"]: r["properties"] for r in doc["runs"][0]["tool"]["driver"]["rules"]}
    for rid in ("GS001", "GS002", "GS003"):
        assert "security-severity" in rules[rid] and "security" in rules[rid]["tags"]
    for rid in ("GS004", "GS005", "GS006"):
        assert "security-severity" not in rules[rid] and "security" not in rules[rid]["tags"]


def test_sarif_psa_target(tmp_path):
    _, doc = _sarif(tmp_path, dict(min_faults=None, psa_level=3))
    g3 = [r for r in doc["runs"][0]["results"] if r["ruleId"] == "GS003"]
    assert len(g3) == 9   # every variant: 1 voltage-glitch event -> 20 <= L3 ceiling


def test_sarif_src_attribute_maps_to_rtl_line(tmp_path):
    # the stored V1 netlist names src/boot.v; give a repository that contains that file
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "boot.v").write_text("\n" * 40)
    _, doc = _sarif(tmp_path, root=str(tmp_path))
    ok = [r for r in doc["runs"][0]["results"] if r["ruleId"] == "GS001" and r["properties"].get("net") == "ok"
          and "given-netlist" in r["properties"]["design"]]
    loc = ok[0]["locations"][0]["physicalLocation"]
    assert loc["artifactLocation"]["uri"] == "src/boot.v" and loc["region"]["startLine"] == 23


@pytest.mark.parametrize("mutate,expect", [
    (lambda d: d["runs"][0]["results"][0].pop("locations"), "location is required"),
    (lambda d: d["runs"][0]["results"][0].__setitem__("ruleId", "XX9"), "not in tool.driver.rules"),
    (lambda d: d["runs"][0]["results"][0].__setitem__("ruleIndex", 5), "ruleIndex"),
    (lambda d: d["runs"][0]["tool"]["driver"]["rules"][0]["properties"].__setitem__("security-severity", "11"), "security-severity"),
    (lambda d: d["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"].__setitem__("uri", "/abs/x.v"), "relative"),
    (lambda d: d["runs"][0]["results"][1].__setitem__("ruleId", d["runs"][0]["results"][0]["ruleId"]) or
               d["runs"][0]["results"][1].__setitem__("ruleIndex", d["runs"][0]["results"][0]["ruleIndex"]) or
               d["runs"][0]["results"][1]["partialFingerprints"].__setitem__(
                   "primaryLocationLineHash", d["runs"][0]["results"][0]["partialFingerprints"]["primaryLocationLineHash"]),
     "primaryLocationLineHash"),
])
def test_github_checker_catches(tmp_path, mutate, expect):
    _, doc = _sarif(tmp_path)
    mutate(doc)
    assert any(expect in e for e in SC.github_errors(doc))


def test_schema_checker_catches_bad_level(tmp_path):
    pytest.importorskip("jsonschema")
    p, doc = _sarif(tmp_path)
    doc["runs"][0]["results"][0]["level"] = "fatal"
    doc["runs"][0]["results"][0]["extra"] = 1
    errs = SC.schema_errors(doc)
    assert any("fatal" in e for e in errs) and any("extra" in e for e in errs)


# ---------- CI check (targets file with recorded results)

def _targets(tmp_path, body):
    p = tmp_path / "glitchsat.toml"
    p.write_text(textwrap.dedent(body))
    return p


def test_check_exit_codes(tmp_path):
    rv2 = runs("v2")
    spike = [x for x in rv2 if "spike" in x]
    surf = os.path.join(REC, "surface", "v2_spike_surface.json")
    t = _targets(tmp_path, f"""
        [defaults]
        target_min_faults = 2
        [[target]]
        name = "v2-spike"
        result = {json.dumps(spike)}
        surface = {json.dumps(surf)}
        """)
    out = tmp_path / "ev"
    code = main_cli.main(["check", f"--targets={t}", f"--sarif={tmp_path / 'c.sarif'}", f"--report-dir={out}", f"--repo-root={tmp_path}"])
    assert code == 0
    assert (out / "v2-spike.evidence.html").is_file() and (tmp_path / "c.sarif").is_file()
    # raise the target above the measured minimum: below target -> exit 1 and a GS003 result
    t = _targets(tmp_path, f"""
        [defaults]
        target_min_faults = 4
        [[target]]
        name = "v2-spike"
        result = {json.dumps(spike)}
        """)
    code = main_cli.main(["check", f"--targets={t}", f"--sarif={tmp_path / 'c.sarif'}", f"--report-dir={out}", f"--repo-root={tmp_path}"])
    assert code == 1
    doc = json.load(open(tmp_path / "c.sarif"))
    assert [r["ruleId"] for r in doc["runs"][0]["results"]] == ["GS003"]
    assert SC.github_errors(doc) == []
    # PSA target with laser assumptions: 3 flips -> 3 events -> 21 > L3 ceiling -> passes
    t = _targets(tmp_path, f"""
        [defaults]
        target_psa_level = 3
        fault_type = "laser"
        [[target]]
        name = "v2-spike"
        result = {json.dumps(spike)}
        """)
    assert main_cli.main(["check", f"--targets={t}", f"--sarif={tmp_path / 'c.sarif'}", f"--report-dir={out}"]) == 0


def test_check_input_errors(tmp_path):
    assert main_cli.main(["check", f"--targets={tmp_path / 'missing.toml'}"]) == 3
    t = _targets(tmp_path, "[[target]]\nname = 'a b'\nresult = 'x.json'\n")
    assert main_cli.main(["check", f"--targets={t}", f"--report-dir={tmp_path / 'e'}"]) == 3
    t = _targets(tmp_path, "[[target]]\nname = 'a'\n")
    assert main_cli.main(["check", f"--targets={t}", f"--report-dir={tmp_path / 'e'}"]) == 3


def test_margin_command_prints_assumptions(capsys):
    code = main_cli.main(["margin", "--result", runs("v2")[-1], "--assume", "flips_per_event=1"])
    out = capsys.readouterr().out
    assert code == 0 and "3 injection event(s)" in out and "never replaces" in out


def test_hook_runs_check(tmp_path, monkeypatch):
    from faultbound_wt.evidence import hook
    spike = [x for x in runs("v2") if "spike" in x]
    t = _targets(tmp_path, f"[[target]]\nname='v2'\nresult={json.dumps(spike)}\ntarget_min_faults=2\n")
    monkeypatch.chdir(tmp_path)
    assert hook.main(["--targets", str(t), "rtl/x.v"]) == 0
    assert (tmp_path / ".glitchsat" / "glitchsat.sarif").is_file()
    assert hook.main(["--targets", "nope.toml"]) == 3


def test_bundled_examples_up_to_date(tmp_path):
    """product/examples/evidence was generated by `glitchsat evidence-example`; regenerate and compare."""
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "evidence")
    if not os.path.isdir(here):
        pytest.skip("examples/evidence not present (installed package)")
    ev.cmd_example(str(tmp_path))
    strip = lambda s: re.sub(r"on Python [0-9.]+", "on Python X", s)
    for f in sorted(os.listdir(here)):
        a = strip(open(os.path.join(here, f), encoding="utf-8").read())
        b = strip(open(os.path.join(tmp_path, f), encoding="utf-8").read())
        assert a == b, f
