"""H3: synth.sh / glitchsat.py check must not execute text from --top or file names (canary tests) and still synthesize normally."""
import os, subprocess, sys, hashlib, shutil, pytest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYNTH = os.path.join(ROOT, 'scripts', 'synth.sh')
GS = os.path.join(ROOT, 'scripts', 'glitchsat.py')
V0 = os.path.join(ROOT, 'rtl', 'v0.v')
pytestmark = pytest.mark.skipif(shutil.which('yosys') is None, reason='yosys missing')

def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)

TOPS = ['v0; exec -- touch CANARY', 'v0\n exec -- touch CANARY', 'v0 ; exec -- touch CANARY; hierarchy -top v0', '-v0', '', 'a b', '\\v0 ', 'v0"', 'v0.x']
NAMES = ['x.v; exec -- touch CANARY; .v', 'x"\nexec -- touch CANARY\n.v', "x'.v", 'x`id`.v', 'x\\.v', 'x#.v']

@pytest.mark.parametrize('top', TOPS)
def test_synth_sh_bad_top(tmp_path, top):
    r = run(['sh', SYNTH, V0, top, str(tmp_path / 'o.json')], tmp_path)
    assert r.returncode != 0 and not (tmp_path / 'CANARY').exists() and not (tmp_path / 'o.json').exists()

@pytest.mark.parametrize('top', TOPS)
def test_glitchsat_check_bad_top(tmp_path, top):
    r = run([sys.executable, GS, 'check', V0, '--top', top, '--k', '1', '--cycles', '2', '--out', str(tmp_path / 'r.json')], tmp_path)
    assert r.returncode != 0 and not (tmp_path / 'CANARY').exists()

@pytest.mark.parametrize('name', NAMES)
def test_synth_sh_bad_paths(tmp_path, name):
    try: shutil.copy(V0, tmp_path / name)   # the file really exists, so only the validation can refuse it
    except OSError: pass
    r = run(['sh', SYNTH, name, 'v0', 'o.json'], tmp_path)
    assert r.returncode != 0 and not (tmp_path / 'CANARY').exists() and not (tmp_path / 'o.json').exists()
    r = run(['sh', SYNTH, V0, 'v0', name + '.json'], tmp_path)
    assert r.returncode != 0 and not (tmp_path / 'CANARY').exists()

@pytest.mark.parametrize('name', NAMES)
def test_glitchsat_check_bad_path(tmp_path, name):
    try: shutil.copy(V0, tmp_path / name)
    except OSError: pass
    r = run([sys.executable, GS, 'check', name, '--top', 'v0', '--k', '1', '--cycles', '2'], tmp_path)
    assert r.returncode != 0 and not (tmp_path / 'CANARY').exists()
    r = run([sys.executable, GS, 'check', V0, '--top', 'v0', '--k', '1', '--cycles', '2', '--out', name], tmp_path)
    assert not (tmp_path / 'CANARY').exists()

def test_leading_dash_path(tmp_path):
    shutil.copy(V0, tmp_path / '-x.v')
    r = run(['sh', SYNTH, '-x.v', 'v0', 'o.json'], tmp_path)
    assert r.returncode != 0 and not (tmp_path / 'o.json').exists()

def test_path_with_space_and_dollar_works(tmp_path):
    shutil.copy(V0, tmp_path / 'my v$0.v')
    assert run(['sh', SYNTH, 'my v$0.v', 'v0', 'o.json'], tmp_path).returncode == 0
    assert run(['sh', SYNTH, 'my v$0.v', 'v0', 'o2.json'], tmp_path).returncode == 0   # deterministic
    assert (tmp_path / 'o.json').read_bytes() == (tmp_path / 'o2.json').read_bytes() and b'"modules"' in (tmp_path / 'o.json').read_bytes()

@pytest.mark.parametrize('flow', ['plain', 'opt'])
def test_known_netlist_hashes_unchanged(tmp_path, flow):
    """sha256 prefixes of the netlists produced by the pre-H3 synth.sh (apt Yosys 0.33), measured by H3."""
    exp = {('v0', 'plain'): '018b3d96715bdde8', ('v0', 'opt'): '0bbd470a18d1320d', ('v1', 'plain'): '1973089cf74a0a30',
           ('v1', 'opt'): '34027b09234f8ea9', ('v2', 'plain'): 'f954078f944ab7a2', ('v2', 'opt'): '79d6236f6c26337f'}
    if '0.33' not in run(['yosys', '-V'], tmp_path).stdout: pytest.skip('hashes recorded with Yosys 0.33')
    for v in ('v0', 'v1', 'v2'):
        # the netlist embeds the source path (src attributes), so run from ROOT with the relative path used for the recorded hashes
        r = run(['sh', SYNTH, 'rtl/' + v + '.v', v, str(tmp_path / 'o.json'), flow], ROOT)
        assert r.returncode == 0, r.stderr
        h = hashlib.sha256((tmp_path / 'o.json').read_bytes()).hexdigest()
        assert h.startswith(exp[(v, flow)])
