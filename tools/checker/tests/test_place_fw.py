import os

import pytest

from conftest import EXT
from survival import gnet, intent_fw, intent_rtl
from survival import stage_netlist as SN
from survival.model import SURVIVED, WEAKENED, REMOVED

FW = os.path.join(EXT, "firmware")


def _placed(root, radius):
    from survival import stage_place as SP
    cms = [c for c in intent_rtl.scan([os.path.join(root, "rtl", "v2.v")]) if c.kind == "redundant_copies"]
    ref = gnet.load(os.path.join(root, "reference/spike_netlists/v2.json"), "v2")
    SN.check(cms[0], ref, "ref", True)
    g = gnet.load(os.path.join(root, "layout/v_designs/out_patched/v2_pnr.v"), "v2")
    pl = SP.Placement(os.path.join(root, "layout/v_designs/out_patched/v2.def"))
    return SP.check(cms[0], g, pl, "placed", radius), pl


def test_placed_netlist_is_read(root):
    g = gnet.load(os.path.join(root, "layout/v_designs/out_patched/v2_pnr.v"), "v2")
    assert len(g.flops) == 8 and len(g.in_bits) == 8 and "clk" not in {p for p, _ in g.in_bits.values()}


@pytest.mark.parametrize("radius,verdict", [(0.5, SURVIVED), (1.0, WEAKENED), (1.75, REMOVED)])
def test_v2_layout_radii(root, radius, verdict):
    """The geometric steps (0.92 um: two copies, 1.665 um: all three) bracket the shot-search steps recorded by
    ext/shots for this layout (3 shots up to 0.5 um, 2 at 1.0-1.5 um, 1 from 1.75 um)."""
    from survival import stage_place as SP
    r, pl = _placed(root, radius)
    assert r.verdict == verdict
    assert r.measured["r_pair_um"] == pytest.approx(0.92, abs=0.01) and r.measured["r_all_um"] == pytest.approx(1.665, abs=0.01)
    rec = SP.recorded_shots(pl, radius)
    assert rec and rec["min_shots"] == {SURVIVED: 3, WEAKENED: 2, REMOVED: 1}[verdict]


def test_mec():
    from survival import stage_place as SP
    assert SP._mec([(0, 0), (2, 0)])[0] == pytest.approx(1.0)
    assert SP._mec([(0, 0), (2, 0), (1, 0.1)])[0] == pytest.approx(1.0)
    assert SP._mec([(0, 0), (1, 0), (0, 1)])[0] == pytest.approx(2 ** 0.5 / 2)


def test_c_scan_groups_repeats(tmp_path):
    p = tmp_path / "b.c"
    p.write_text('''
static int cmp(const int *a, const int *b) { for (int i = 0; i < 4; i++) if (a[i] != b[i]) return 1; return 0; }
void boot(int *a, int *b) {
  int r1 = cmp(a, b);
  if (LAUNDER(r1) != 0) fail(1);
  int r2 = cmp(a, b);
  if (r2 != 0)
    alarm(2);
  if (a[0] > 3) fail(3);
  step += 1;
  step += 2;
  if (step != 3) alarm(9);
  go();
}''')
    got = {c.kind: c for c in intent_fw.scan([str(p)])}
    rep = got["fw_repeated_check"]
    assert rep.intent["copies"] == 2 and [g["handler"] for g in rep.intent["guards"]] == ["fail", "alarm"]
    assert rep.intent["callees"] == ["cmp"] and rep.intent["function"] == "boot"
    assert got["fw_flow_counter"].intent["variable"] == "step" and len(got["fw_flow_counter"].intent["steps"]) == 2


def _fw(build, variant="rom_triple"):
    from survival import stage_fw as SF
    src = os.path.join(FW, "src", variant + ".c")
    elf = os.path.join(FW, "elf", build + ".elf")
    if not os.path.isfile(elf):
        pytest.skip("ext/firmware builds not present")
    cms = intent_fw.scan([src], {"rom_main"})
    b = SF.Binary(elf)
    return {c.intent.get("condition", c.id): SF.check(c, b, "fw", open(src).read()) for c in cms}


def test_o2_merge_is_flagged():
    r = _fw("rom_triple-O2-plain-hw")
    mac = next(v for k, v in r.items() if "r1" in k)
    assert mac.verdict == REMOVED and mac.measured["guards_present"] == 1 and mac.measured["evaluations"] == 1
    assert sum("no instruction of the binary belongs to this line" in e for e in mac.evidence) == 2
    rb = next(v for k, v in r.items() if "version" in k)
    assert rb.verdict == SURVIVED          # the OTP reads are volatile bus reads: all three rollback checks stay


@pytest.mark.parametrize("build", ["rom_triple-O0-plain-hw", "rom_triple-O1-plain-hw", "rom_triple-O2-vol-hw",
                                   "rom_triple-O2-barrier-hw", "rom_triple-Os-barrier-hw"])
def test_kept_checks_are_not_flagged(build):
    r = _fw(build)
    assert all(v.verdict == SURVIVED for v in r.values())
    assert next(v for k, v in r.items() if "r1" in k).measured["guards_present"] == 3
