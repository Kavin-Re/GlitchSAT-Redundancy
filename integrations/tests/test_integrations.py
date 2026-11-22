"""Tests for integrations/. They exercise OUR adapters on project data; they do not validate
SYNFI or any other third-party tool. Tests that need project data files skip if the file is absent."""
import glob, json, os, sys
import pytest
from conftest import ROOT
import campaign as C, synfi_adapter as S, yosys_provenance as Y, ci_formats as F, byo_adapters as B

EX = os.path.join(ROOT, "integrations", "examples")
SY = os.path.join(ROOT, "compare", "synfi_run")
SPIKE = os.path.join(ROOT, "reference", "spike_netlists")


def need(p):
    if not os.path.exists(p):
        pytest.skip(f"missing {p}")
    return p


# ---------------- schema / validator
@pytest.mark.parametrize("f", sorted(glob.glob(os.path.join(EX, "*.json"))))
def test_examples_valid(f):
    assert C.validate(json.load(open(f))) == []


def test_three_required_examples_present():
    assert len(glob.glob(os.path.join(EX, "ex*.json"))) >= 3


def test_validator_rejects_bad_docs():
    good = json.load(open(os.path.join(EX, "ex3_external_mixed_types.json")))
    bad = json.loads(json.dumps(good)); bad["label"] = "PROVED"
    assert any("label" in e for e in C.validate(bad))
    bad = json.loads(json.dumps(good)); bad["fault_sets"][0]["faults"][0]["cycle"] = -1
    assert any("cycle" in e for e in C.validate(bad))
    bad = json.loads(json.dumps(good)); bad["fault_sets"][1]["faults"][0].pop("replacement")
    assert any("replacement" in e for e in C.validate(bad))
    bad = json.loads(json.dumps(good)); bad["fault_sets"][1]["id"] = "ext1"
    assert any("duplicated" in e for e in C.validate(bad))
    bad = json.loads(json.dumps(good)); bad["fault_sets"][0]["faults"][0]["type"] = "laser"
    assert any("type" in e for e in C.validate(bad))
    bad = json.loads(json.dumps(good)); bad["fault_sets"][0]["faults"] = []
    assert any("non-empty" in e for e in C.validate(bad))
    assert C.validate([]) and C.validate({})


def test_dump_refuses_invalid(tmp_path):
    with pytest.raises(ValueError):
        C.dump({"schema": "x"}, str(tmp_path / "a.json"))


def test_load_roundtrip(tmp_path):
    d = C.load(os.path.join(EX, "ex2_v2_three_faults.json"))
    C.dump(d, str(tmp_path / "o.json"))
    assert C.load(str(tmp_path / "o.json")) == d


def test_from_glitchsat_no_attack_has_no_sets():
    d = C.load(os.path.join(EX, "ex4_v2_no_attack_k1.json"))
    assert d["verdict"] == "NO_ATTACK_UP_TO_BOUND" and d["fault_sets"] == []


# ---------------- Yosys provenance
def test_banner_parsing():
    b = Y.parse_banner("Yosys 0.38+92 (git sha1 84116c9a3, x86_64-conda-linux-gnu-cc 11.2.0 -O2 -fdebug-prefix-map=/a=/b)")
    assert (b["version"], b["plus_commits"], b["git_sha1"]) == ("0.38", 92, "84116c9a3")
    assert b["version_string"] == "0.38+92" and "conda" in b["channel_hint"]
    b = Y.parse_banner("Yosys 0.33 (git sha1 2584903a060)")
    assert b["version_string"] == "0.33" and b["plus_commits"] == 0
    assert Y.parse_banner("nothing here") is None and Y.parse_banner(None) is None


def test_netlist_provenance_033_vs_038():
    a = Y.read_netlist(need(os.path.join(SPIKE, "v2.json")))
    b = Y.read_netlist(need(os.path.join(ROOT, "formal", "gen", "v2.json")))
    assert a["yosys"]["version_string"] == "0.33" and b["yosys"]["version_string"] == "0.38+92"
    d = Y.diff(a, b)
    assert not d["same_yosys"] and not d["same_netlist_bytes"] and d["notes"]
    assert Y.diff(a, a)["same_yosys"] and Y.diff(a, a)["same_netlist_bytes"]


def test_log_reader(tmp_path):
    p = tmp_path / "l.log"; p.write_text("junk\nYosys 0.38+92 (git sha1 84116c9a3, cc)\n")
    assert Y.read_log(str(p))["version_string"] == "0.38+92"
    p.write_text("no banner"); assert Y.read_log(str(p)) is None


def test_missing_creator(tmp_path):
    p = tmp_path / "n.json"; p.write_text(json.dumps({"modules": {"m": {"cells": {}, "netnames": {}}}}))
    r = Y.read_netlist(str(p)); assert r["yosys"] is None
    assert Y.to_campaign_design_block(r)["yosys"]["version_string"] == "UNKNOWN"


def test_yosys_binary_optional():
    b = Y.run_yosys_version("definitely-not-a-binary-xyz")
    assert b is None


# ---------------- SYNFI export
def _base(v):
    return next(iter(json.load(open(need(os.path.join(SY, "inputs", f"fm_{v}_cycle1_flip.json"))))["fimodels"].values()))


def _solver_campaign(v, k):
    p = os.path.join(EX, "ex1_v1_single_fault.json" if v == "v1" else "ex2_v2_three_faults.json")
    return C.load(p)


def test_export_v1_hits_ok_gate_and_matches_synfi_result():
    camp = _solver_campaign("v1", 3)
    fm, rep = S.export_fimodel(camp, "min_attack_set", need(os.path.join(SY, "inputs", "v1_synfi.json")), _base("v1"))
    assert fm["simultaneous_faults"] == 1 and len(fm["fault_locations"]) == 1
    cell = next(iter(fm["fault_locations"]))
    assert cell.endswith("parse_blif$280")           # SYNFI log: ok[386:parse_blif$280]
    assert fm["node_fault_mapping"]["AND2_X1"] == ["NAND2_X1"]
    assert fm["input_values"] == _base("v1")["input_values"]   # start state untouched


def test_export_v2_three_sets_each_cell_exists_and_k_is_3():
    camp = _solver_campaign("v2", 3)
    fm, rep = S.export_fimodel(camp, "min_attack_set", need(os.path.join(SY, "inputs", "v2_synfi.json")), _base("v2"))
    assert fm["simultaneous_faults"] == 3 and len(fm["fault_locations"]) == 3 and not rep["skipped"]
    idx = S.NetlistIndex(os.path.join(SY, "inputs", "v2_synfi.json"))
    assert all(c in idx.cells for c in fm["fault_locations"])


def test_export_import_roundtrip_reproduces_existing_explicit_spec():
    spec = json.load(open(need(os.path.join(SY, "inputs", "fm_v2_cycle1_explicit3.json"))))
    camp = S.campaign_from_synfi_spec(spec, "v2_cycle1_flip", "v2")
    assert C.validate(camp) == []
    base = spec["fimodels"]["v2_cycle1_flip"]
    fm, rep = S.export_fimodel(camp, "synfi_spec", os.path.join(SY, "inputs", "v2_synfi.json"), base)
    assert fm["fault_locations"] == base["fault_locations"]
    assert fm["simultaneous_faults"] == base["simultaneous_faults"] == 3


def test_export_v0_flop_faults_reported_not_dropped():
    r = json.load(open(need(os.path.join(ROOT, "integrations", "data", "v0_k3.json")))) if os.path.exists(os.path.join(ROOT, "integrations", "data", "v0_k3.json")) else None
    if r is None:
        pytest.skip("solver output for v0 not available")
    camp = C.from_glitchsat(r)
    fm, rep = S.export_fimodel(camp, "min_attack_set", os.path.join(SY, "inputs", "v0_synfi.json"), _base("v0"))
    assert fm is None and rep["skipped"] and "flop" in rep["skipped"][0]["reason"]


def test_export_synthetic_flop_and_multi_cycle_warning():
    camp = {"schema": C.SCHEMA_ID, "label": "ILLUSTRATIVE", "generator": {"tool": "t"}, "design": {"name": "d"},
            "fault_sets": [{"id": "s", "faults": [
                {"target": {"kind": "cell", "name": "$abc$255$auto$blifparse.cc:386:parse_blif$280"}, "cycle": 1, "type": "bit_flip"},
                {"target": {"kind": "cell", "name": "$abc$255$auto$blifparse.cc:386:parse_blif$280"}, "cycle": 3, "type": "bit_flip"},
                {"target": {"kind": "net", "name": "ok"}, "cycle": 2, "type": "set"}]}]}
    fm, rep = S.export_fimodel(camp, "s", os.path.join(need(SY), "inputs", "v1_synfi.json"), _base("v1"))
    assert any("UNTESTED" in w for w in rep["warnings"])
    assert any("set" in s["reason"] for s in rep["skipped"])
    assert fm["fault_locations"][next(iter(fm["fault_locations"]))] == ["stage_1", "stage_2"]
    with pytest.raises(KeyError):
        S.export_fimodel(camp, "nope", os.path.join(SY, "inputs", "v1_synfi.json"), _base("v1"))


# ---------------- SYNFI reader and comparison on recorded logs (V0/V1/V2)
def _log(name):
    return S.parse_synfi_log(open(need(os.path.join(SY, "out", name))).read())


def test_reader_counts_match_synfi_result_md():
    assert (_log("fm_v1_cycle1_flip_k1.log")["total_fault_sets"], _log("fm_v1_cycle1_flip_k1.log")["effective"]) == (53, 1)
    v0 = _log("fm_v0_cycle1_flip_k1.log"); assert (v0["total_fault_sets"], v0["effective"], len(v0["effective_sets"])) == (16, 11, 11)
    assert (_log("fm_v2_cycle1_flip_k1.log")["effective"], _log("fm_v2_cycle1_flip_k1.log")["total_fault_sets"]) == (0, 61)
    k2 = _log("fm_v2_cycle1_flip_k2.log"); assert (k2["effective"], k2["total_fault_sets"]) == (0, 1830)
    assert k2["stock_injecting"] == 3660     # stock line double-counts; we do not use it as the set total
    k3 = _log("fm_v2_cycle1_flip_k3.log")
    assert (k3["effective"], k3["total_fault_sets"], len(k3["effective_sets"]), k3["unlisted_effective"]) == (182, 35990, 60, 122)
    assert k3["runtime_s"] == pytest.approx(660.1)


def test_reader_stock_summary_only():
    t = "Injecting 6 faults...\nFound 4 (66.67%) effective combinational faults, 0 (0.0%) effective sequential faults, and 2 ineffective faults.\n"
    r = S.parse_synfi_log(t)
    assert r["format"] == "stock_summary" and r["effective"] == 4 and r["total_fault_sets"] is None


def test_compare_v1_agrees_with_solver():
    ours = _solver_campaign("v1", 3)
    runs = {1: _log("fm_v1_cycle1_flip_k1.log")}
    res = S.compare(ours, runs, os.path.join(SY, "inputs", "v1_synfi.json"))
    assert res["agree"] is True and res["ours_min_faults"] == 1 and res["synfi_min_k"] == 1
    setchk = [c for c in res["checks"] if c["check"] == "our set listed by SYNFI"][0]
    assert setchk["ok"] is True       # the `ok` AND gate is the single effective set in SYNFI's list


def test_compare_v2_min_three_and_no_attack_k1_k2():
    runs = {1: _log("fm_v2_cycle1_flip_k1.log"), 2: _log("fm_v2_cycle1_flip_k2.log"), 3: _log("fm_v2_cycle1_flip_k3.log")}
    ours = _solver_campaign("v2", 3)
    res = S.compare(ours, runs)          # no netlist: verdict-level only
    assert res["agree"] is True and res["ours_min_faults"] == 3 and res["synfi_min_k"] == 3
    # solver's no-attack at k=1 vs SYNFI k=1 only
    ours1 = C.load(os.path.join(EX, "ex4_v2_no_attack_k1.json"))
    r1 = S.compare(ours1, {1: runs[1]})
    assert r1["agree"] is True
    # and a disagreement is detected: pretend SYNFI k=3 effective set count against a no-attack-at-k3 claim
    ours3 = json.loads(json.dumps(ours1)); ours3["threat_model"]["max_faults"] = 3
    r3 = S.compare(ours3, runs)
    assert r3["agree"] is False


def test_compare_v0_min_agrees_but_set_check_skipped_for_flop():
    r = json.load(open(os.path.join(ROOT, "integrations", "data", "v0_k1.json"))) if os.path.exists(os.path.join(ROOT, "integrations", "data", "v0_k1.json")) else None
    if r is None:
        pytest.skip("v0 solver output not available")
    ours = C.from_glitchsat(r)
    res = S.compare(ours, {1: _log("fm_v0_cycle1_flip_k1.log")}, os.path.join(SY, "inputs", "v0_synfi.json"))
    assert res["agree"] is True
    assert [c for c in res["checks"] if c["check"] == "our set listed by SYNFI"][0]["ok"] is None


def test_compare_set_level_on_explicit_v2_log():
    spec = json.load(open(need(os.path.join(SY, "inputs", "fm_v2_cycle1_explicit3.json"))))
    camp = S.campaign_from_synfi_spec(spec, "v2_cycle1_flip", "v2")
    camp["verdict"] = "ATTACK_FOUND"; camp["fault_sets"][0]["id"] = "min_attack_set"
    res = S.compare(camp, {3: _log("fm_v2_cycle1_explicit3_k3.log")}, os.path.join(SY, "inputs", "v2_synfi.json"))
    chk = [c for c in res["checks"] if c["check"] == "our set listed by SYNFI"][0]
    assert chk["ok"] is True and "weak" in chk["note"]   # two tails coincide ($257): flagged as a weak match


# ---------------- SARIF / JUnit
def test_sarif_and_junit():
    att = C.load(os.path.join(EX, "ex1_v1_single_fault.json"))
    s = F.to_sarif(att)
    assert s["version"] == "2.1.0" and s["runs"][0]["results"][0]["level"] == "error"
    assert "not physical" in s["runs"][0]["results"][0]["message"]["text"]
    clean = F.to_sarif(C.load(os.path.join(EX, "ex4_v2_no_attack_k1.json")))
    assert clean["runs"][0]["results"] == []
    import xml.etree.ElementTree as ET
    x = ET.fromstring(F.to_junit(att)); assert x.find("testsuite").get("failures") == "1"
    x = ET.fromstring(F.to_junit(C.load(os.path.join(EX, "ex4_v2_no_attack_k1.json")))); assert x.find("testsuite").get("failures") == "0"
    unk = C.load(os.path.join(EX, "ex3_external_mixed_types.json"))
    assert ET.fromstring(F.to_junit(unk)).find("testsuite").get("skipped") == "1"
    json.dumps(s)


# ---------------- bring-your-own wrappers (stand-in command only)
def test_run_external_requires_ack_and_records(tmp_path):
    with pytest.raises(PermissionError):
        B.run_external([sys.executable, "-c", "print(1)"], str(tmp_path), False)
    r = B.run_external([sys.executable, "-c", "open('o.txt','w').write('x');print('hi')"], str(tmp_path), True, timeout_s=20)
    assert r["exit_code"] == 0 and r["stdout"].strip() == "hi" and r["files_new_or_changed"] == ["o.txt"]
    r = B.run_external([sys.executable, "-c", "import time;time.sleep(5)"], str(tmp_path), True, timeout_s=1)
    assert r["timed_out"] is True


def test_attack_list_import_and_untested_renderers():
    d = B.from_attack_list("# sig,cycle,effect\nc0.n10,1\nstate[2],3,set\nx,0,stuck1\n", "demo")
    assert C.validate(d) == [] and [f["type"] for f in d["fault_sets"][0]["faults"]] == ["bit_flip", "set", "stuck_at_1"]
    d2 = B.from_attack_list(json.dumps([{"signal": "a", "cycle": 2, "effect": "reset"}]), "demo", fmt="json")
    assert C.validate(d2) == []
    with pytest.raises(ValueError):
        B.from_attack_list("a,1,laser\n", "demo")
    camp = C.load(os.path.join(EX, "ex2_v2_three_faults.json"))
    txt = B.to_uarchifi_script(camp)
    assert "fault_rtlil -cnt 3 -timing 1:1 -effect flip" in txt and "UNTESTED" in txt
    cfg = B.to_fiver_config("d.v", "top", "model/m.txt", "cell/Library.txt", "LIB", fault_number=2)
    assert "[fault]" in cfg and "number = 2" in cfg and "UNTESTED" in cfg


# ---------------- recorded SYNFI re-run in this run (python 3.13, unpinned PyPI + setuptools<81) replaying OUR exported specs
DATA = os.path.join(ROOT, "integrations", "data")


def test_recorded_replays_consistent_with_exporter():
    """data/v*_replay.json were produced by `synfi_adapter.py export` and replayed by SYNFI (logs in data/)."""
    for v, k, n in (("v1", 1, "parse_blif$280"), ("v2", 3, "parse_blif$252")):
        spec = json.load(open(os.path.join(DATA, f"{v}_replay.json")))
        fm = next(iter(spec["fimodels"].values()))
        assert fm["simultaneous_faults"] == k and all(c.endswith(n) for c in fm["fault_locations"])
        log = S.parse_synfi_log(open(os.path.join(DATA, f"replay_{v}.log")).read())
        assert (log["total_fault_sets"], log["effective"]) == (1, 1)      # SYNFI says: the exported set is effective
        assert all(it["mapping"] in ("NAND2_X1", "NOR2_X1") for it in log["effective_sets"][0])
    r = S.parse_synfi_log(open(os.path.join(DATA, "rerun_v1_k1.log")).read())
    assert (r["total_fault_sets"], r["effective"]) == (53, 1)           # same counts as the earlier recorded run
