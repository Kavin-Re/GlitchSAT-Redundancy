"""Verilog and Yosys scripts written for a candidate."""
import importlib, os, re, sys
import pytest
from harden import resynth, spec as S


def test_v2_verilog_matches_repository_wiring(repo):
    v = S.verilog(S.PRESETS['v2'])
    rtl = open(repo('rtl/v2.v')).read()
    sel = re.search(r'sel\s*=\s*\{([^}]*)\}', rtl).group(1).replace(' ', '')
    assert '{' + sel.replace(',', ', ') + '}' in v
    for word in ("8'hF0", "8'hCC", "8'h96", "8'h69", "8'hC3"):
        assert word in v


def test_scripts_without_guard_equal_the_repository_matrix(repo):
    """guard off = command for command research/c2/e2_variance/scripts/matrix.py (the configurations already studied)."""
    sys.path.insert(0, repo('research/c2/e2_variance/scripts'))
    try:
        matrix = importlib.import_module('matrix')
    finally:
        sys.path.pop(0)
    sp = S.PRESETS['v2']
    n = 0
    for c in resynth.grid():
        if c['guard']:
            continue
        mine = S.yosys_script(sp, 'in.v', 'out.json', top='v2', guard=False, flow=c['flow'], abc=resynth.ABCS[c['abc']],
                              order=c['order'], merge=c['merge']).strip().splitlines()
        theirs = matrix.script('v2', 'in.v', 'out.json', c['flow'], c['order'], c['abc'], 'opt_merge' if c['merge'] else 'nomerge')
        assert mine == theirs, c
        n += 1
    assert n == 96


def test_guard_marks_kept_modules_before_flatten():
    sp = S.PRESETS['v2'].replace(voter='per_bit_and', owner=())
    L = S.yosys_script(sp, 'a.v', 'b.json', merge=True).splitlines()
    i_keep = [i for i, x in enumerate(L) if x.startswith('setattr -set keep 1')]
    assert [L[i] for i in i_keep] == ['setattr -set keep 1 cmp8/c:*', 'setattr -set keep 1 vote3/c:*']
    assert max(i_keep) < L.index('flatten') < L.index('opt_merge')


def test_problems_are_reported():
    assert S.Spec(idle=0x96).problems()
    assert S.Spec(owner=(0, 0, 0, 0, 0, 0, 0, 0)).problems()
    assert not S.PRESETS['v2'].problems()


def test_dry_run_writes_every_configuration(tmp_path, repo):
    import json
    d = tmp_path / 'specs'
    d.mkdir()
    json.dump(dict(before=S.PRESETS['v2'].as_dict(), after=S.PRESETS['v2e'].as_dict() | {'name': 'v2h'}, goal=3, top='v2h'),
              open(d / 'v2_g3.spec.json', 'w'))
    rows = resynth.main(str(d), str(tmp_path / 'out'), dry_run=True, root=os.path.dirname(repo('scripts')), workers=1, log=lambda *a: None)
    assert len(rows) == 3 * 192 and {r['status'] for r in rows} == {'SCRIPT_ONLY'}
    assert (tmp_path / 'out' / 'work' / 'v2_g3' / 'before_repo_rtl' / 'v2_keep_off.v').exists()
    assert '(* keep *)' not in (tmp_path / 'out' / 'work' / 'v2_g3' / 'after' / 'v2h_keep_off.v').read_text()


FAKE_YOSYS = '''#!/usr/bin/env python3
import os, shutil, sys
if sys.argv[1:] == ['-V']:
    print('Yosys 0.33 (stand-in for the test)'); sys.exit(0)
ys = open(sys.argv[sys.argv.index('-s') + 1]).read().splitlines()
top = next(x.split()[-1] for x in ys if x.startswith('hierarchy -top'))
out = next(x.split()[-1] for x in ys if x.startswith('write_json'))
open(os.environ['FAKE_LOG'], 'a').write(top + '\\n')
shutil.copy(os.path.join(os.environ['FAKE_NETLISTS'], top + '.json'), out)
'''


def test_resynth_pipeline_with_stand_in_yosys(tmp_path, monkeypatch):
    """The non-dry path end to end (synthesis call, verification, match nets, cache) with a stand-in that returns
    the reference mapping instead of running Yosys. Real Yosys runs are cloud/run_cloud.sh."""
    import json
    from harden import search
    d = tmp_path / 'specs'; d.mkdir()
    nd = tmp_path / 'nl'; nd.mkdir()
    before, after = S.PRESETS['v2'], S.PRESETS['v2'].replace(armed=0xC8)
    S.build_mapping(before, 'select-shared').write(str(nd / 'v2.json'))
    S.build_mapping(after.replace(name='v2h'), 'select-shared').write(str(nd / 'v2h.json'))
    json.dump(dict(before=before.as_dict(), after=after.as_dict() | {'name': 'v2h'}, goal=3, top='v2h'), open(d / 'v2_g3.spec.json', 'w'))
    fy = tmp_path / 'yosys'; fy.write_text(FAKE_YOSYS); fy.chmod(0o755)
    log = tmp_path / 'calls.txt'
    monkeypatch.setenv('FAKE_NETLISTS', str(nd)); monkeypatch.setenv('FAKE_LOG', str(log))
    kw = dict(quick=True, yosys=str(fy), root='', workers=2, log=lambda *a: None)
    monkeypatch.delenv('GLITCHSAT_ROOT', raising=False)      # no before_repo_rtl rows: the stand-in has no netlist for them
    rows = resynth.main(str(d), str(tmp_path / 'out'), **kw)
    assert len(rows) == 2 * 16 and {r['status'] for r in rows} == {'MEASURED'}
    b = [r for r in rows if r['which'] == 'before']
    a = [r for r in rows if r['which'] == 'after']
    assert {r['min_flips'] for r in b} == {2} and not any(r['meets_goal'] for r in b)
    assert all(r['meets_goal'] is True and r['function_ok'] and r['match_nets'] == 3 for r in a)
    n = len(log.read_text().split())
    assert n == 32
    rows2 = resynth.main(str(d), str(tmp_path / 'out'), **kw)
    assert len(log.read_text().split()) == n and all('(cached)' in r['note'] for r in rows2)
    assert [r['min_flips'] for r in rows2] == [r['min_flips'] for r in rows]
    s = (tmp_path / 'out' / 'resynth_summary.md').read_text()
    assert '| v2_g3 | after | >= 3 | 16 | 16 / 16 |' in s
