"""The fault search against a plain brute force without de-duplication, and
witness replay. Builds are small hw-engine builds (short runs)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from faultsim import image  # noqa: E402
from faultsim.search import Searcher, fault_options, replay  # noqa: E402
from rv32sim import load_elf  # noqa: E402
from rv32sim.cpu import IMAGE, RUNNING  # noqa: E402


def brute_k2(prog, flash, otp, model):
    """Smallest k <= 2 by plain enumeration (no memo, no pruning); None if none."""
    s = Searcher(prog, flash, otp, model)
    sites, limit = s.sites, s.limit

    def finish(m):
        while m.outcome == RUNNING and m.steps < limit:
            m.step()
        return m.outcome == IMAGE

    def walk(m, depth):
        best = None
        while m.outcome == RUNNING and m.steps < limit:
            if m.pc in sites:
                for mode, arg in fault_options(model, m.code[m.pc]):
                    m2 = m.copy()
                    m2.step(mode, arg)
                    if depth == 1:
                        if finish(m2):
                            return 1
                    else:
                        if finish(m2.copy()):
                            return 1
                        if walk(m2, 1):
                            best = 2
            m.step()
        return best

    return walk(s.fresh(), 2)


CASES = [("rom_naive-O1-plain-hw", "skip"), ("rom_double-O1-plain-hw", "skip"),
         ("rom_triple-Os-barrier-hw", "brinv"), ("rom_naive-O2-plain-hw", "skip"),
         ("rom_double-O2-vol-hw", "brinv"), ("rom_triple-O1-plain-hw", "skip"),
         ("rom_compl-Os-plain-hw", "skip")]


@pytest.mark.parametrize("stem,model", CASES)
def test_dfs_equals_brute_force(stem, model):
    elf = os.path.join(ROOT, "elf", stem + ".elf")
    if not os.path.exists(elf):
        pytest.skip("not built")
    p = load_elf(elf)
    flash, otp = image.scenarios()["tampered_payload"][0], image.otp()
    r = Searcher(p, flash, otp, model, budget_s=600).minimum(2)
    assert r["completed_k"] >= 1
    assert r["min_faults"] == brute_k2(p, flash, otp, model)
    if r["witness"]:
        assert replay(p, flash, otp, r["witness"]).outcome == IMAGE
