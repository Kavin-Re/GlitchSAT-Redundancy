"""Adapted primitive netlist (through the GlitchSAT engine parser) == original netlist with SYNFI semantics."""
import random
import pytest
from conftest import load
from glitchsat_real import nangate as ng, refsim, engine


def cosim(doc, top, lib, mode, W=128, T=6, seed=3, corrupt=False):
    nd, meta = ng.convert(doc, top, lib=lib, reset_mode=mode)
    if corrupt:
        cells = nd['modules'][top]['cells']
        name = next(n for n, c in cells.items() if c['type'] == '$_AND_')
        cells[name]['type'] = '$_OR_'
    nl = engine.netlist_from_doc(nd, top)
    ref, prim = refsim.RefSim(doc, top, lib), refsim.PrimSim(nl)
    rng = random.Random(seed)
    rst = {r['net']: 1 - r['active'] for r in meta['resets']}
    ins = refsim.random_inputs(doc['modules'][top]['ports'], T, W, rng, hold=rst if mode == 'deasserted' else None)
    init = {c: f['init'] for c, f in meta['flops'].items()}
    a, b = ref.run(T, ins, W, init), prim.run(T, ins, W)
    return sum(1 for t in range(T) for n in ref.drv if a[t][n] != b[t][n])


@pytest.mark.parametrize('name', ['aes_fsm', 'aes_ctrl', 'ibex'])
@pytest.mark.parametrize('mode', ['deasserted', 'sync'])
def test_cosim_zero_mismatch(name, mode, lib):
    doc, top = load(name)
    assert cosim(doc, top, lib, mode) == 0


def test_cosim_detects_corruption(lib):
    doc, top = load('aes_fsm')
    assert cosim(doc, top, lib, 'deasserted', corrupt=True) > 0


def test_flop_reset_values(lib):
    doc, top = load('aes_fsm')
    nd, meta = ng.convert(doc, top, lib=lib)
    inits = sorted((f['type'], f['init']) for f in meta['flops'].values())
    assert inits.count(('DFFS_X1', 1)) == 2 and inits.count(('DFFR_X1', 0)) == 5
    assert meta['resets'][0]['active'] == 0 and len(meta['resets'][0]['cells']) == 7


def test_sites_are_real_nets_only(lib):
    doc, top = load('aes_fsm')
    nd, meta = ng.convert(doc, top, lib=lib)
    real_nets = {b for x in doc['modules'][top]['netnames'].values() for b in x['bits']}
    assert set(meta['sites']) <= real_nets
    assert len([s for s in meta['sites'].values() if s['kind'] == 'cell']) == 223
