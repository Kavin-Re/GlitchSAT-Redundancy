import copy
import os

import pytest

from conftest import Builder, eq_const
from survival import gnet, intent_rtl, margin
from survival import stage_netlist as SN
from survival.model import Countermeasure, SURVIVED, WEAKENED, REMOVED, UNTRACKED


def _ref(root, top="v2"):
    cms = [c for c in intent_rtl.scan([os.path.join(root, "rtl", top + ".v")]) if c.intent.get("module") == top]
    g = gnet.load(os.path.join(root, "reference", "spike_netlists", top + ".json"), top)
    res = {c.kind: SN.check(c, g, "ref", True) for c in cms}
    return cms, g, res


def test_rtl_scan_v2(root):
    cms = intent_rtl.scan([os.path.join(root, "rtl", "v2.v")])
    kinds = {c.kind: c for c in cms}
    c = kinds["redundant_copies"]
    assert c.intent["copies"] == 3 and c.intent["instances"] == ["c0", "c1", "c2"] and c.intent["cell"] == "cmp8"
    e = kinds["sparse_encoding"]
    assert e.intent["register"] == "st" and e.intent["codes"] == [0x69, 0x96, 0xCC, 0xF0] and e.intent["min_distance"] == 4
    assert "boot_word" in e.intent["aliases"]


def test_rtl_scan_v0_has_nothing(root):
    assert intent_rtl.scan([os.path.join(root, "rtl", "v0.v")]) == []


def test_rtl_annotations(tmp_path):
    p = tmp_path / "a.v"
    p.write_text('''module a(input clk, input [3:0] x, output alarm_o, output y);
  (* cm_copies = "chk" *) wire k0;  (* cm_copies = "chk" *) wire k1;
  (* cm_sparse = "5,a,c" *) reg [3:0] fsm;
  (* cm_mubi = "6" *) wire [3:0] en;
  (* cm_dup = "cnt" *) reg [2:0] cnt;  (* cm_dup = "cnt" *) reg [2:0] cnt_other;
  reg [3:0] step; reg [3:0] step_n;
  always @(posedge clk) begin step <= step + 1; step_n <= ~(step + 1); end
endmodule''')
    got = {c.id: c for c in intent_rtl.scan([str(p)])}
    assert got["copies:a.chk"].intent["nets"] == ["k0", "k1"] and got["copies:a.chk"].origin == "annotation"
    assert got["encoding:a.fsm"].intent["codes"] == [0x5, 0xA, 0xC] and got["encoding:a.fsm"].intent["min_distance"] == 2
    assert got["mubi:a.en"].intent["true"] == 6 and got["mubi:a.en"].intent["false"] == 9
    assert got["dup:a.cnt"].intent["registers"] == ["cnt", "cnt_other"]
    assert got["dup:a.step"].origin == "rtl-scan"
    assert got["alarm:a.alarm_o"].kind == "alarm"


def test_enum_scan(tmp_path):
    p = tmp_path / "f.sv"
    p.write_text('''module f(input logic clk_i);
  typedef enum logic [5:0] { IDLE = 6'b001001, RUN = 6'b100011, DONE = 6'b111101 } st_e;
  st_e st_q, st_d;
endmodule''')
    c = intent_rtl.scan([str(p)])[0]
    assert c.kind == "sparse_encoding" and c.intent["register"] == "st_q" and c.intent["min_distance"] == 3 and c.intent["width"] == 6


def test_reference_survives(root):
    cms, g, res = _ref(root)
    assert res["redundant_copies"].verdict == SURVIVED and res["redundant_copies"].measured["independent"] == 3
    assert res["redundant_copies"].measured["exact_function"] is True
    assert res["sparse_encoding"].verdict == SURVIVED and res["sparse_encoding"].measured["distance"] == 4


@pytest.mark.parametrize("path,verdict,indep", [
    ("validation/nl/v2.json", REMOVED, 1),                              # flattened before optimisation, names gone
    ("research/c2/reviews/ct/tests/v2_inbuf.json", REMOVED, 1),          # shared input buffers
    ("research/c2/e2_variance/baseline_netlists/apt0.33_v2.json", SURVIVED, 3),
    ("research/c4/layout/nl/v2_layout.json", SURVIVED, 3),
])
def test_copies_on_stored_netlists(root, path, verdict, indep):
    cms, g0, _ = _ref(root)
    g = gnet.load(os.path.join(root, path), "v2")
    cm = next(c for c in cms if c.kind == "redundant_copies")
    r = SN.check(cm, g, "s", False)
    assert r.verdict == verdict and r.measured["independent"] == indep
    if verdict == REMOVED:
        assert r.measured["shared_cells"] > 0 and any("more than one copy" in e for e in r.evidence)


def test_function_tracking_needs_no_names(root):
    """flow B has no hierarchy names at all: the copies are found by their function."""
    cms, g0, _ = _ref(root)
    g = gnet.load(os.path.join(root, "validation/nl/v2.json"), "v2")
    assert not g.find(r"(^|[./])c0[./]")
    r = SN.check(next(c for c in cms if c.kind == "redundant_copies"), g, "s", False)
    assert r.measured["distinct_nets"] == 2 and r.measured["exact_function"]


def test_detect_without_rtl(root):
    g = gnet.load(os.path.join(root, "reference/spike_netlists/v2.json"), "v2")
    found = {c.kind: c for c in SN.detect(g)}
    assert found["redundant_copies"].intent["copies"] == 3
    assert found["sparse_encoding"].intent["min_distance"] == 4
    g1 = gnet.load(os.path.join(root, "validation/nl/v2.json"), "v2")
    assert "redundant_copies" not in {c.kind for c in SN.detect(g1)}       # merged: nothing left to detect


def test_untracked_without_reference(root):
    cms = [c for c in intent_rtl.scan([os.path.join(root, "rtl", "v2.v")]) if c.kind == "redundant_copies"]
    g = gnet.load(os.path.join(root, "validation/nl/v2.json"), "v2")
    assert SN.check(cms[0], g, "s", True).verdict == UNTRACKED          # names gone and no stage gave the function


def _two_copies(shared=False, merged=False, top="t"):
    b = Builder(top)
    b.port("clk", "input")
    x = b.port("x", "input", 4)
    o = b.port("o", "output", 2)
    src = [b.gate("$_AND_", A=v, B=v) for v in x] if shared else x      # buffer-like cells in front of both copies
    m0 = eq_const(b, src, 0xA)
    m1 = m0 if merged else eq_const(b, src, 0xA)
    b.name("u0.m", [m0])
    b.name("u1.m", [m1])
    b.dff(m0, o[0], "ff0")
    b.dff(m1, o[1], "ff1")
    return b


def _cm2():
    return Countermeasure("copies:t.u", "redundant_copies", "yaml",
                          intent=dict(copies=2, instances=["u0", "u1"], outputs={"u0": {"m": "m0"}, "u1": {"m": "m1"}}))


def test_synthetic_copies(tmp_path):
    cm = _cm2()
    g0 = gnet.load(_two_copies().write(tmp_path / "a.json"), "t")
    assert SN.check(cm, g0, "ref", True).verdict == SURVIVED
    r = SN.check(cm, gnet.load(_two_copies(merged=True).write(tmp_path / "b.json"), "t"), "s", False)
    assert r.verdict == REMOVED and any("one and the same net" in e for e in r.evidence)
    r = SN.check(cm, gnet.load(_two_copies(shared=True).write(tmp_path / "c.json"), "t"), "s", False)
    assert r.verdict == REMOVED and r.measured["shared_on_inputs"] is True


def test_three_copies_weakened(tmp_path):
    """Two of three copies share a gate, the third stays apart: WEAKENED, not REMOVED."""
    def build(share):
        b = Builder()
        b.port("clk", "input")
        x = b.port("x", "input", 4)
        o = b.port("o", "output", 3)
        common = b.gate("$_AND_", A=x[1], B=x[3])
        ms = []
        for i in range(3):
            hi = common if (share and i < 2) else b.gate("$_AND_", A=x[1], B=x[3])
            lo = b.gate("$_AND_", A=b.gate("$_NOT_", A=x[0]), B=b.gate("$_NOT_", A=x[2]))
            m = b.gate("$_AND_", A=hi, B=lo)
            b.name(f"u{i}.m", [m])
            b.dff(m, o[i], f"ff{i}")
            ms.append(m)
        return b
    cm = Countermeasure("copies:t.u", "redundant_copies", "yaml", intent=dict(copies=3, nets=["u0.m", "u1.m", "u2.m"]))
    assert SN.check(cm, gnet.load(build(False).write(tmp_path / "a.json"), "t"), "ref", True).verdict == SURVIVED
    r = SN.check(cm, gnet.load(build(True).write(tmp_path / "b.json"), "t"), "s", False)
    assert r.verdict == WEAKENED and r.measured["independent"] == 2 and r.measured["shared_cells"] == 1


def test_alarm_constant(tmp_path):
    b = Builder()
    b.port("clk", "input")
    x = b.port("x", "input", 2)
    a = b.port("alarm", "output")
    m = b.gate("$_AND_", A=x[0], B=x[1])
    b.gate("$_XOR_", out=a[0], A=m, B=m)                      # copy != copy after a merge: constant 0
    cm = Countermeasure("alarm:t.alarm", "alarm", "yaml", intent=dict(signal="alarm"))
    r = SN.check(cm, gnet.load(b.write(tmp_path / "a.json"), "t"), "s", False)
    assert r.verdict == REMOVED and "never change" in r.evidence[0]
    b2 = Builder()
    b2.port("clk", "input")
    x = b2.port("x", "input", 2)
    a = b2.port("alarm", "output")
    b2.gate("$_XOR_", out=a[0], A=x[0], B=x[1])
    assert SN.check(cm, gnet.load(b2.write(tmp_path / "b.json"), "t"), "s", False).verdict == SURVIVED


def test_redundant_register(tmp_path):
    def build(merge):
        b = Builder()
        b.port("clk", "input")
        x = b.port("x", "input", 2)
        qa = [b.dff(v, name=f"a{i}") for i, v in enumerate(x)]
        qb = qa if merge else [b.dff(v, name=f"b{i}") for i, v in enumerate(x)]
        b.name("cnt", qa)
        b.name("cnt_n", qb)
        return b
    cm = Countermeasure("dup:t.cnt", "redundant_register", "yaml", intent=dict(registers=["cnt", "cnt_n"], width=2))
    assert SN.check(cm, gnet.load(build(False).write(tmp_path / "a.json"), "t"), "s", True).verdict == SURVIVED
    r = SN.check(cm, gnet.load(build(True).write(tmp_path / "b.json"), "t"), "s", False)
    assert r.verdict == REMOVED and "same flop" in r.evidence[0]


def test_other_gate_types_are_read(tmp_path):
    b = Builder()
    b.port("clk", "input")
    x = b.port("x", "input", 3)
    o = b.port("o", "output")
    n = b.gate("$_NAND_", A=x[0], B=x[1])
    b.gate("$_ANDNOT_", out=o[0], A=x[2], B=n)                # x2 & x0 & x1
    g = gnet.load(b.write(tmp_path / "a.json"), "t")
    v = g.signatures()[o[0]]
    ref = g.signatures()[x[0]] & g.signatures()[x[1]] & g.signatures()[x[2]]
    assert (v == ref).all()


def test_word_level_cells_are_refused(tmp_path):
    b = Builder()
    b.port("clk", "input")
    b.cells["w"] = dict(type="$eq", connections=dict(A=[2], B=[3], Y=[4]))
    with pytest.raises(gnet.NetlistError, match="techmap"):
        gnet.load(b.write(tmp_path / "a.json"), "t")


FSM = """module f(input clk, input rst, input go, output done);
  reg [3:0] st;
  always @(posedge clk) begin
    if (rst) st <= 4'h3;
    else case (st)
      4'h3: if (go) st <= 4'h5;
      4'h5: st <= 4'hA;
      4'hA: st <= 4'hC;
      4'hC: st <= 4'h3;
      default: st <= 4'h3;
    endcase
  end
  assign done = (st == 4'hC);
endmodule
"""


def test_fsm_recoding_is_reported(yosys, tmp_path):
    """Yosys `synth` extracts the FSM and re-encodes it; `synth -nofsm` keeps the codes. Both are measured here."""
    from survival import pipeline
    (tmp_path / "f.v").write_text(FSM)
    cfg = dict(name="fsm", top="f", intent=dict(rtl=["f.v"]), stages=[
        dict(name="synth", verilog=["f.v"], flow="synth -top f; abc -g AND,OR,XOR,MUX; opt_clean"),
        dict(name="nofsm", verilog=["f.v"], flow="synth -top f -nofsm; abc -g AND,OR,XOR,MUX; opt_clean")])
    rep = pipeline.run(cfg, str(tmp_path), workdir=str(tmp_path / "w"), bisect=True)
    enc = next(c for c in rep["countermeasures"] if c["kind"] == "sparse_encoding")
    by = {r["stage"]: r for r in enc["stages"]}
    assert by["rtl"]["verdict"] == SURVIVED and by["nofsm"]["verdict"] == SURVIVED
    assert by["synth"]["verdict"] == REMOVED and by["synth"]["measured"]["distance"] == 1 and by["synth"]["measured"]["recoded"]
    assert "MEASURED" in by["synth"]["cause"] and "`synth -top f`" in by["synth"]["cause"] and "FSM extraction" in by["synth"]["cause"]
    assert any("fsm_encoding" in f for f in by["synth"]["fix"])
    assert rep["summary"]["exit_code"] == 1


def test_opt_merge_is_bisected(root, yosys, tmp_path):
    from survival import pipeline
    rtl = os.path.join(root, "rtl", "v2.v")
    flow = ("proc; opt_clean; techmap; opt_clean; abc -g AND,OR,XOR,MUX; opt_clean; setattr -mod -unset keep_hierarchy *; "
            "flatten; opt_clean; techmap; opt_clean; opt_merge; opt_clean")
    cfg = dict(name="v2", top="v2", intent=dict(rtl=[rtl]), goal=dict(output="boot_word", value=0x96, input="sig", key=0xC3),
               stages=[dict(name="synth", verilog=[rtl], flow=flow)])
    rep = pipeline.run(cfg, str(tmp_path), workdir=str(tmp_path / "w"), bisect=True)
    cp = next(c for c in rep["countermeasures"] if c["kind"] == "redundant_copies")
    by = {r["stage"]: r for r in cp["stages"]}
    assert by["rtl"]["verdict"] == SURVIVED and by["synth"]["verdict"] == REMOVED
    assert "`opt_merge`" in by["synth"]["cause"] and "one command at a time" in by["synth"]["cause"]
    m = {s["name"]: s["margin"]["min_faults"] for s in rep["stages"]}
    assert m == {"rtl": 3, "synth": 1}
    assert rep["summary"]["margin_drop"]["explained_by"]


def test_margin_engines(root):
    m = margin.measure(os.path.join(root, "validation/nl/v2.json"), "v2", {})
    assert m["status"] == "attack" and m["min_faults"] == 1 and m["engine"] == "exhaustive"
    m = margin.measure(os.path.join(root, "research/c2/e2_variance/baseline_netlists/apt0.33_v2.json"), "v2", {})
    assert m["min_faults"] == 2
    m = margin.measure(os.path.join(root, "reference/spike_netlists/v1.json"), "v1", {})
    assert m["min_faults"] == 1 and m["witness"][0]["net"] == "ok"


def test_margin_k3_matches_recorded(root):
    m = margin.measure(os.path.join(root, "reference/spike_netlists/v2.json"), "v2", {})
    assert m["min_faults"] == 3 and "fastsat" in m["engine"]
