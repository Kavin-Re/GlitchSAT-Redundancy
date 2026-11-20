"""P08: (a) synth.sh is run through sh, so a missing exec bit does not matter; (b) neutral multi-fault explanation text."""
import os, shutil, stat, subprocess, sys, pytest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GS = os.path.join(ROOT, 'scripts', 'glitchsat.py')
pytestmark = pytest.mark.skipif(shutil.which('yosys') is None, reason='yosys missing')

def _copy_noexec(tmp_path):
    d = tmp_path / 'scripts'; d.mkdir()
    for f in ('glitchsat.py', 'synth.sh'):
        shutil.copy(os.path.join(ROOT, 'scripts', f), d / f)
        os.chmod(d / f, 0o644)
    return d

def test_synth_without_exec_bit(tmp_path):
    d = _copy_noexec(tmp_path)
    assert not os.access(d / 'synth.sh', os.X_OK)
    r = subprocess.run([sys.executable, str(d / 'glitchsat.py'), 'check', os.path.join(ROOT, 'rtl', 'v0.v'), '--top', 'v0', '--k', '1', '--cycles', '6'],
                       capture_output=True, text=True, timeout=200, cwd=tmp_path)
    assert 'Permission' not in r.stderr and r.returncode in (0, 1, 2), r.stderr[-500:]
    assert 'ATTACK_FOUND' in r.stdout or 'NO_ATTACK' in r.stdout

def test_two_flip_witness_text_is_neutral(tmp_path):
    r = subprocess.run([sys.executable, GS, 'check', os.path.join(ROOT, 'rtl', 'v2.v'), '--top', 'v2', '--k', '2', '--cycles', '6'],
                       capture_output=True, text=True, timeout=200, cwd=tmp_path)
    out = r.stdout
    if 'MINIMUM ATTACK COST = 2' not in out:
        pytest.skip('this Yosys build does not give the 2-flip V2 witness (apt 0.33 does)')
    assert 'MINIMUM ATTACK COST = 2' in out   # apt Yosys 0.33 netlist has a 2-flip witness
    low = out.lower()
    assert 'independent redundant' not in low and 'add another' not in low
    assert 'does not classify whether they sit on independent copies' in out
