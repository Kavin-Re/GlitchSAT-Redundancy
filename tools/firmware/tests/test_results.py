"""The stored fault-search results: every witness replays on the simulator,
the summary files agree with results/raw/, the ELFs are the ones in the
manifest, and the compiler effects the README describes are present."""
import glob
import hashlib
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from faultsim import image  # noqa: E402
from faultsim.search import MODELS, replay  # noqa: E402
from faultsim.static import count_calls  # noqa: E402
from rv32sim import Machine, load_elf  # noqa: E402
from rv32sim.cpu import IMAGE  # noqa: E402

RAW = sorted(glob.glob(os.path.join(ROOT, "results", "raw", "*.json")))
ELF = os.path.join(ROOT, "elf")
SUMMARY = os.path.join(ROOT, "results", "summary.json")
need_raw = pytest.mark.skipif(not RAW, reason="no stored results")
need_summary = pytest.mark.skipif(not os.path.exists(SUMMARY), reason="run scripts/summarize.py")


def elf(stem):
    return os.path.join(ELF, stem + ".elf")


@need_raw
def test_every_witness_replays():
    """Re-run each stored minimal attack with its faults: the tampered image must run."""
    scen = {k: image.scenarios(k) for k in ("hmac", "sha3")}
    otp = image.otp()
    progs = {}
    n = 0
    for f in RAW:
        r = json.load(open(f))
        if not r["min_faults"]:
            continue
        p = progs.get(r["build"]) or progs.setdefault(r["build"], load_elf(elf(r["build"])))
        faults = [(w["step"], int(w["pc"], 16), MODELS[w["model"]], w["arg"]) for w in r["witness"]]
        assert len(faults) == r["min_faults"]
        m = replay(p, scen[image.mac_kind(p)][r["scenario"]][0], otp, faults, exec_lock=r["exec_lock"])
        assert m.outcome == IMAGE, os.path.basename(f)
        n += 1
    assert n > 100


@need_raw
def test_no_fault_runs_are_refused():
    """Without faults every scenario searched is refused (golden run), so min_faults >= 1."""
    for f in RAW:
        r = json.load(open(f))
        assert r["golden_outcome"] == "reject", os.path.basename(f)
        assert r["min_faults"] is None or r["min_faults"] >= 1


@need_raw
def test_status_is_consistent():
    for f in RAW:
        r = json.load(open(f))
        if r["status"] == "attack_found":
            m = r["min_faults"]
            assert m >= 1 and r["completed_k"] == max(1, m - 1) and len(r["witness"]) == m
        elif r["status"] == "no_attack_up_to_kmax":
            assert r["min_faults"] is None and r["completed_k"] == r["kmax"]
        else:
            assert r["status"] == "budget_exhausted" and r["min_faults"] is None


@need_summary
def test_summary_matches_raw():
    s = json.load(open(SUMMARY))
    assert s["meta"]["label"] == "MEASURED"
    assert len(s["jobs"]) == len(RAW)
    raw = {os.path.basename(f)[:-5]: json.load(open(f)) for f in RAW}
    for j in s["jobs"]:
        assert j["min_faults"] == raw[j["job"]]["min_faults"]
        assert j["status"] == raw[j["job"]]["status"]
    # the headline is the minimum over the fault models of the per-model results
    for e in s["table"]:
        t = e["tampered_payload"]
        found = [c["exact"] for c in t["per_model"].values() if c["exact"] is not None]
        if t["any_model"]["exact"] is not None:
            assert t["any_model"]["exact"] == min(found)


@need_summary
def test_studio_file_matches_summary():
    s = json.load(open(SUMMARY))
    v = json.load(open(os.path.join(ROOT, "results", "studio_firmware.json")))
    assert v["view"] == "Firmware" and v["label"] == "MEASURED"
    head = s["headline_plain_tampered_four_models"]
    for c in v["cells"]:
        if c["mode"] == "plain":
            assert c["tampered"] == head[c["variant"]][c["opt"]]
    assert len(v["cells"]) == 9 * 4 * 3


def test_elfs_match_manifest():
    mf = json.load(open(os.path.join(ELF, "manifest.json")))
    assert len(mf["builds"]) == 324
    for stem, info in mf["builds"].items():
        data = open(os.path.join(ROOT, info["elf"]), "rb").read()
        assert hashlib.sha256(data).hexdigest() == info["sha256"], stem


def test_triple_compare_merged_at_O2():
    """rom_triple: three MAC compares in C. At -O2 in plain C the compiler keeps one compare
    (one pass over the header MAC) and removes the two MAC alarm calls; volatile or the
    asm barrier keeps all three."""
    good, otp = image.scenarios()["good"][0], image.otp()

    def mac_passes(stem):
        p = load_elf(elf(stem))

        class M(Machine):
            __slots__ = ("n",)

            def load(self, addr, n, signed):
                if 0x20000010 <= addr < 0x20000030:
                    self.n += 1
                return Machine.load(self, addr, n, signed)
        m = M(p, good, otp)
        m.n = 0
        m.run(10 ** 5)
        assert m.outcome == IMAGE
        return m.n / 8

    assert mac_passes("rom_triple-O1-plain-hw") == 3
    assert mac_passes("rom_triple-O2-plain-hw") == 1
    assert mac_passes("rom_triple-O2-vol-hw") == 3
    assert mac_passes("rom_triple-O2-barrier-hw") == 3
    a1 = count_calls(load_elf(elf("rom_triple-O1-plain-hw")), "rom_alarm")
    a2 = count_calls(load_elf(elf("rom_triple-O2-plain-hw")), "rom_alarm")
    a2b = count_calls(load_elf(elf("rom_triple-O2-barrier-hw")), "rom_alarm")
    assert a2 < a1 and a2 < a2b


def test_ctres_redundant_count_removed_at_O2():
    """rom_ctres: the independent equal-word count and its alarm are gone at -O2 in plain C."""
    assert count_calls(load_elf(elf("rom_ctres-O2-plain-hw")), "rom_alarm") == 0
    assert count_calls(load_elf(elf("rom_ctres-O2-barrier-hw")), "rom_alarm") == 1


def test_infective_mixing_removed_in_plain_C():
    """rom_infective: `target = ... + d * K` is computed before `if (d != 0) fail`. From -O1 on,
    plain C lets the compiler use d == 0 on the boot path and drop the multiply; the asm
    barrier and volatile keep it."""
    from rv32sim import isa
    from faultsim.static import count_op
    assert count_op(load_elf(elf("rom_infective-O0-plain-hw")), isa.MUL) == 1
    for o in ("O1", "O2", "Os"):
        assert count_op(load_elf(elf("rom_infective-%s-plain-hw" % o)), isa.MUL) == 0
        assert count_op(load_elf(elf("rom_infective-%s-barrier-hw" % o)), isa.MUL) == 1
        assert count_op(load_elf(elf("rom_infective-%s-vol-hw" % o)), isa.MUL) == 1
