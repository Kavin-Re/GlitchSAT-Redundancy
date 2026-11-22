"""The engine CLI must explain itself without z3: --help and --version always work, and a missing z3 gives one clear line
(exit 3), never a traceback."""
import importlib.util, os, subprocess, sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GS = os.path.join(ROOT, 'scripts', 'glitchsat.py')
HAVE_Z3 = importlib.util.find_spec('z3') is not None


def run(*args):
    return subprocess.run([sys.executable, GS, *args], capture_output=True, text=True, timeout=60, cwd=ROOT)


@pytest.mark.parametrize('args', [('--help',), ('check', '--help'), ('--version',)])
def test_help_and_version_work(args):
    r = run(*args)
    assert r.returncode == 0, r.stderr
    assert 'Traceback' not in r.stderr
    assert 'GlitchSAT' in r.stdout or 'NETLIST' in r.stdout


def test_every_check_option_has_help():
    """Each option line in `check --help` is followed by a description (on the same line or the next indented line)."""
    lines = run('check', '--help').stdout.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith('options:'))
    for opt in ('--top', '--k', '--cycles', '--out', '--reduce', '--goal-out', '--goal-value', '--attack-input', '--key',
                '--timeout-ms', '--amk', '--flow'):
        i = next(i for i in range(start, len(lines)) if lines[i].strip().split(' ')[0] == opt)
        same = lines[i].strip()[len(opt):].split('  ', 1)
        nxt = lines[i + 1] if i + 1 < len(lines) else ''
        assert (len(same) == 2 and same[1].strip()) or (nxt.startswith(' ' * 10) and nxt.strip()), f'{opt} has no help text'


@pytest.mark.skipif(HAVE_Z3, reason='z3 is installed: the missing-z3 message cannot be shown')
def test_missing_z3_is_one_line():
    r = run('check', 'reference/spike_netlists/v2.json', '--top', 'v2', '--k', '1', '--cycles', '6')
    assert r.returncode == 3
    assert r.stderr.strip() == 'error: z3-solver is not installed: pip install z3-solver'
    assert 'Traceback' not in r.stderr
