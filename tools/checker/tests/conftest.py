import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from survival import paths  # noqa: E402

paths.setup()
try:
    ROOT = paths.repo_root()
except FileNotFoundError:
    ROOT = None
EXT = paths.ext_root()


@pytest.fixture(scope="session")
def root():
    if ROOT is None:
        pytest.skip("GlitchSAT repository not found (set GLITCHSAT_ROOT)")
    return ROOT


@pytest.fixture(scope="session")
def yosys():
    y = paths.tool("yosys")
    if not y:
        pytest.skip("Yosys not installed")
    return y


class Builder:
    """Tiny Yosys-JSON netlist builder for synthetic test designs."""

    def __init__(self, top="t"):
        self.top, self.n = top, 2
        self.ports, self.cells, self.netnames = {}, {}, {}

    def net(self, name=None):
        b = self.n
        self.n += 1
        if name:
            self.name(name, [b])
        return b

    def name(self, name, bits, init=None):
        self.netnames[name] = dict(bits=list(bits), attributes=({"init": init} if init else {}))

    def port(self, name, direction, width=1):
        bits = [self.net() for _ in range(width)]
        self.ports[name] = dict(direction=direction, bits=bits)
        self.name(name, bits)
        return bits

    def gate(self, typ, out=None, **pins):
        out = out if out is not None else self.net()
        self.cells[f"g{len(self.cells)}"] = dict(type=typ, connections=dict({k: [v] for k, v in pins.items()}, Y=[out]))
        return out

    def dff(self, d, q=None, name=None):
        q = q if q is not None else self.net()
        self.cells[name or f"ff{len(self.cells)}"] = dict(type="$_DFF_P_", connections=dict(C=[self.ports["clk"]["bits"][0]], D=[d], Q=[q]))
        return q

    def doc(self):
        return dict(creator="test", modules={self.top: dict(attributes={}, ports=self.ports, cells=self.cells, netnames=self.netnames)})

    def write(self, path):
        with open(path, "w") as f:
            json.dump(self.doc(), f)
        return str(path)


def eq_const(b, bits, const):
    """AND-tree for bits == const."""
    lits = [x if (const >> i) & 1 else b.gate("$_NOT_", A=x) for i, x in enumerate(bits)]
    acc = lits[0]
    for x in lits[1:]:
        acc = b.gate("$_AND_", A=acc, B=x)
    return acc


@pytest.fixture
def builder():
    return Builder
