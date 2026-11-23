"""End to end on the added boot check alone (needs Yosys; skipped without it), campaign against proof, and
honesty checks on the stored result files."""
import glob
import json
import os
import shutil
import subprocess
import sys

import pytest

SOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _yosys():
    return os.environ.get('GSOC_YOSYS') or shutil.which('yosys')


@pytest.fixture(scope='module')
def bootcheck(root, tmp_path_factory):
    if not _yosys():
        pytest.skip('yosys not found')
    from gsoc import frontend
    work = str(tmp_path_factory.mktemp('fe'))
    out = {}
    for variant, top in (('plain', 'bootcheck_plain'), ('tmr', 'bootcheck_tmr')):
        cfg = dict(name='bc_' + variant, top=top, frontend='verilog', files=['rtl/bootcheck.v'],
                   _dir=os.path.join(SOC, 'chips', 'picosoc'), memory_map_max_words=64)
        for flow in ('written', 'keep', 'flat'):
            out[(variant, flow)] = (frontend.run(cfg, flow, work, work)['netlist'], top)
    return out


GOAL = dict(id='boot', hit=['boot_release=1'], hold=4, attacker=dict(port='sig', differs_from=0xC3), cycles=8, kmax=4)
RESET = dict(port='resetn', active=0)


def _session(path, top):
    from gsoc import chip, sim
    ch = chip.load(path, top, clock='clk')
    st, info = sim.reset_state(ch, {ch.circ.ports['resetn'][1][0]: False}, 8)
    assert info['flops_unknown'] == 0            # the boot check resets every flop it has
    return ch, st


def test_bootcheck_minimum_per_flow(root, bootcheck):
    """The added check alone: one fault for the plain variant in every flow; the triplicated variant needs three as
    written and fewer once the optimiser has seen the copies together. (The exact keep/flat numbers depend on the
    Yosys version; what must hold is the order.)"""
    from gsoc import slicer, sim, gscale
    G = gscale()
    res = {}
    for (variant, flow), (path, top) in bootcheck.items():
        ch, st = _session(path, top)
        b = slicer.build(ch, GOAL, RESET, st)
        o = G.search.analyse(b.P, 4, backend='py')
        assert o['status'] == 'EXACT'
        assert slicer.replay_on_chip(ch, b, sim.Compiled(ch.circ), o['_witness_raw'], st)['ok']
        res[(variant, flow)] = o['hi']
    assert all(res[('plain', f)] == 1 for f in ('written', 'keep', 'flat'))
    assert res[('tmr', 'written')] == 3
    assert res[('tmr', 'written')] >= res[('tmr', 'keep')] >= res[('tmr', 'flat')] >= 1


def test_single_fault_sweep_agrees_with_proof(root, bootcheck):
    """Every cell flipped in every cycle, all 255 wrong attacker values as lanes: a success exists exactly when the
    proved minimum is 1."""
    from gsoc import slicer, sim, gscale
    G = gscale()
    for (variant, flow), (path, top) in bootcheck.items():
        ch, st = _session(path, top)
        b = slicer.build(ch, GOAL, RESET, st)
        proved = G.search.analyse(b.P, 4, backend='py')['hi']
        comp = sim.Compiled(ch.circ)
        sig = ch.circ.ports['sig'][1]
        rn = ch.circ.ports['resetn'][1][0]
        vals = [v for v in range(256) if v != 0xC3]
        L = len(vals)
        words = {x: sum(((v >> i) & 1) << lane for lane, v in enumerate(vals)) for i, x in enumerate(sig)}
        words[rn] = (1 << L) - 1
        net = ch.net('boot_release')
        found = False
        for t in range(8):
            for s in sorted(ch.sites):
                tr = comp.run(L, 8, {q: ((1 << L) - 1 if v else 0) for q, v in st.items()}, lambda _t: words,
                              lambda tt, t=t, s=s: {s: (1 << L) - 1} if tt == t else None, [net])
                run = [r[net] for r in tr]
                if any(run[i] & run[i + 1] & run[i + 2] & run[i + 3] for i in range(5)):
                    found = True
        assert found == (proved == 1), (variant, flow, proved, found)


def test_cli_list_and_bad_chip(root):
    r = subprocess.run([sys.executable, os.path.join(SOC, 'glitchsat_soc.py'), 'list'], capture_output=True, text=True)
    assert r.returncode == 0 and 'picosoc' in r.stdout and 'ibex_demo' in r.stdout
    r = subprocess.run([sys.executable, os.path.join(SOC, 'glitchsat_soc.py'), 'analyse', 'no_such_chip'], capture_output=True, text=True)
    assert r.returncode == 3


def test_stored_results_are_labelled_honestly():
    runs = sorted(glob.glob(os.path.join(SOC, 'results', 'runs', '*.json')))
    if not runs:
        pytest.skip('no stored results')
    goals = camps = 0
    for p in runs:
        r = json.load(open(p))
        if r['schema'].startswith('glitchsat-soc-goal'):
            goals += 1
            assert r['label'] in ('BOUNDED', 'PARTIAL')       # never PROVED: no result here is an unbounded proof
            if r['label'] == 'BOUNDED':                        # exact minimum within T cycles
                assert r['status'] == 'EXACT' and r['lo'] == r['hi'] == r['min_faults']
                assert r['witness']['replayed_on_whole_chip'] and len(r['witness']['faults']) == r['min_faults']
            else:
                assert r['min_faults'] is None
            assert r['slice']['slice_cells'] <= r['slice']['chip_cells'] and r['spec']['cycles'] >= 1
        elif r['schema'].startswith('glitchsat-soc-campaign'):
            camps += 1
            assert r['label'] == 'SAMPLED'
            assert r['no_fault']['goal_reached'] == 0          # no goal is reachable by the environment alone
    assert goals and camps


def test_campaigns_do_not_contradict_proofs():
    """A proved minimum of 2 or more forbids any single-fault success; a proved minimum of 1 does not force a
    sampled environment to find one, so only the first direction is an invariant."""
    d = os.path.join(SOC, 'results', 'runs')
    n = 0
    for p in sorted(glob.glob(os.path.join(d, '*.campaign.*.json'))):
        c = json.load(open(p))
        g = p.replace('.campaign.', '.goal.')
        if not os.path.exists(g):
            continue
        g = json.load(open(g))
        if g['label'] == 'BOUNDED' and g['min_faults'] >= 2:
            assert c['single']['goal_reached'] == 0, p
            n += 1
        if g['lo'] >= 3:
            assert c['pairs']['goal_reached'] == 0, p
    if not n:
        pytest.skip('no stored campaign with a proved minimum >= 2')


def test_no_forbidden_wording():
    """Shared check (ext/check_wording.py): no listed word and no absolute developer path. The word list is kept there
    as hashes only, so this test does not put the words into the repository."""
    import importlib.util
    p = os.path.join(os.path.dirname(SOC), 'check_wording.py')
    if not os.path.isfile(p):
        pytest.skip('check_wording.py not found next to the modules')
    spec = importlib.util.spec_from_file_location('check_wording', p)
    cw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cw)
    hits = cw.scan([SOC])
    assert not hits, hits[:10]


def test_studio_view_labels_and_caveats():
    """The Studio's "Explore a real chip" data: bounded results are never called PROVED (in the Studio PROVED means
    "for any waiting time"), the lockstep chip carries the source-edit caveat next to its rows, and Earl Grey says how
    far it got."""
    p = os.path.join(SOC, 'studio', 'explore_chip.json')
    if not os.path.exists(p):
        pytest.skip('no Studio data')
    d = json.load(open(p))
    assert 'PROVED' not in json.dumps(d['intro']['labels']) or 'not called proved' in d['intro']['labels']['BOUNDED']
    labels = {g['label'] for c in d['chips'] for v in c['variants'] for g in v['goals']}
    assert labels <= {'BOUNDED', 'PARTIAL'}, labels
    ib = next(c for c in d['chips'] if c['id'] == 'ibex_demo')
    assert any('source edits' in x for x in ib['read_with_care'])
    assert all('lowRISC does not ship' in (v.get('note') or '') for v in ib['variants'] if v['variant'] == 'lockstep')
    assert d['next_rung']['summary'] == 'Read in full; the gate step needs a bigger machine.'
