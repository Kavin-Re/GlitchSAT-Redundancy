import os
import sys

import pytest

TESTS = os.path.dirname(os.path.abspath(__file__))
SOC = os.path.dirname(TESTS)
if SOC not in sys.path:
    sys.path.insert(0, SOC)


@pytest.fixture(scope='session')
def root():
    import gsoc
    try:
        return gsoc.setup_paths()
    except ImportError:
        pytest.skip('repository root not found; set GLITCHSAT_ROOT')


def cell(t, **con):
    dirs = {p: ('output' if p in ('Y', 'Q') else 'input') for p in con}
    return dict(type=t, connections={p: (v if isinstance(v, list) else [v]) for p, v in con.items()}, port_directions=dirs)


def netlist(ports, cells, names=None, top='t'):
    """ports: {name: (direction, [bits])}."""
    nn = {n: dict(bits=b, attributes={}, hide_name=0) for n, (d, b) in ports.items()}
    for n, b in (names or {}).items():
        nn[n] = dict(bits=b if isinstance(b, list) else [b], attributes={}, hide_name=0)
    return dict(modules={top: dict(attributes={'top': '00000000000000000000000000000001'},
                                   ports={n: dict(direction=d, bits=b) for n, (d, b) in ports.items()},
                                   cells=cells, netnames=nn)})
