"""Hostile / malformed netlists must fail loudly (exit 3), never give a silent verdict.
Netlists are hand-built Yosys-JSON (2-bit input `sig`, key 3, 2-bit `boot_word`)."""
import json, os, subprocess, sys
import pytest
pytest.importorskip('z3', reason='z3-solver is not installed: pip install z3-solver')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import glitchsat as g
CLI = [sys.executable, '-I', os.path.join(ROOT, 'scripts', 'glitchsat.py'), 'check']


def base():
    return dict(modules=dict(t=dict(ports=dict(clk=dict(direction='input', bits=[2]), sig=dict(direction='input', bits=[3, 4]),
                boot_word=dict(direction='output', bits=[5, 6])), cells={}, netnames={})))


def add(d, name, ty, **con):
    d['modules']['t']['cells'][name] = dict(type=ty, connections={k: (v if isinstance(v, list) else [v]) for k, v in con.items()})


def run(tmp, d, args=('--k', '0', '--cycles', '2', '--key', '3', '--goal-value', '1'), raw=None):
    p = os.path.join(str(tmp), 'n.json')
    if raw is not None: open(p, 'w').write(raw)
    else: json.dump(d, open(p, 'w'))
    return subprocess.run(CLI + [p, '--top', 't', *args], capture_output=True, text=True, timeout=120)


def good():
    d = base(); add(d, 'a', '$_XOR_', A=3, B=4, Y=5); add(d, 'z', '$_AND_', A=3, B='0', Y=6); return d


def test_control_valid_netlist_still_gives_verdict(tmp_path):
    r = run(tmp_path, good())
    assert r.returncode == 0 and 'ATTACK_FOUND' in r.stdout          # sig=1 -> xor=1, no fault needed


def test_multidriver_fails_in_both_orders(tmp_path):
    for order in (('g1', 'g2'), ('g2', 'g1')):
        d = base()
        for n in order: add(d, n, '$_AND_' if n == 'g1' else '$_OR_', A=3, B=4, Y=5)
        add(d, 'z', '$_AND_', A=3, B='0', Y=6)
        r = run(tmp_path, d); assert r.returncode == 3 and 'multiple drivers' in r.stderr, r.stderr


def test_gate_driving_flop_q_fails(tmp_path):
    d = good(); add(d, 'f', '$_DFF_P_', C=2, D=3, Q=5)
    r = run(tmp_path, d); assert r.returncode == 3 and 'multiple drivers' in r.stderr


def test_gate_driving_input_bit_fails(tmp_path):
    d = good(); add(d, 'bad', '$_NOT_', A=3, Y=4)
    r = run(tmp_path, d); assert r.returncode == 3 and 'input port' in r.stderr


def test_duplicate_json_key_fails(tmp_path):
    raw = ('{"modules":{"t":{"ports":{"clk":{"direction":"input","bits":[2]},"sig":{"direction":"input","bits":[3,4]},'
           '"boot_word":{"direction":"output","bits":[5,6]}},"cells":{"g":{"type":"$_AND_","connections":{"A":[3],"B":[4],"Y":[5]}},'
           '"g":{"type":"$_OR_","connections":{"A":[3],"B":[4],"Y":[5]}}},"netnames":{}}}}')
    r = run(tmp_path, None, raw=raw); assert r.returncode == 3 and 'duplicate JSON key' in r.stderr


def test_x_init_fails(tmp_path):
    d = base(); add(d, 'f', '$_DFF_P_', C=2, D=7, Q=7); add(d, 'z', '$_AND_', A=3, B='0', Y=6); add(d, 'b', '$_AND_', A=7, B=7, Y=5)
    d['modules']['t']['netnames']['q'] = dict(bits=[7], attributes=dict(init='x'))
    r = run(tmp_path, d); assert r.returncode == 3 and 'unknown' in r.stderr


def test_x_constant_fails(tmp_path):
    d = base(); add(d, 'a', '$_OR_', A=3, B='x', Y=5); add(d, 'z', '$_AND_', A=3, B='0', Y=6)
    r = run(tmp_path, d); assert r.returncode == 3 and 'x/z' in r.stderr


def test_undriven_and_comb_loop_and_latch_fail_cleanly(tmp_path):
    d = base(); add(d, 'a', '$_AND_', A=3, B=99, Y=5); add(d, 'z', '$_AND_', A=3, B='0', Y=6)
    r = run(tmp_path, d); assert r.returncode == 3 and 'undriven' in r.stderr and 'Traceback' not in r.stderr
    d = base(); add(d, 'a', '$_NOT_', A=7, Y=5); add(d, 'b', '$_NOT_', A=5, Y=7); add(d, 'z', '$_AND_', A=3, B='0', Y=6)
    r = run(tmp_path, d); assert r.returncode == 3 and 'combinational loop' in r.stderr and 'Traceback' not in r.stderr
    d = base(); add(d, 'l', '$_DLATCH_P_', D=3, E=4, Q=5); add(d, 'z', '$_AND_', A=3, B='0', Y=6)
    r = run(tmp_path, d); assert r.returncode == 3 and 'Traceback' not in r.stderr


@pytest.mark.parametrize('args', [
    ('--k', '0', '--cycles', '2', '--key', '3', '--goal-value', '0x101'),   # wider than the 2-bit port
    ('--k', '0', '--cycles', '2', '--key', '3', '--goal-value', '0x5'),
    ('--k', '0', '--cycles', '2', '--key', '0x103', '--goal-value', '1'),
    ('--k', '0', '--cycles', '0', '--key', '3', '--goal-value', '1'),
    ('--k', '-1', '--cycles', '2', '--key', '3', '--goal-value', '1')])
def test_cli_argument_validation(tmp_path, args):
    r = run(tmp_path, good(), args); assert r.returncode == 3 and r.stderr.startswith('error:'), (r.returncode, r.stderr)


def test_deep_chain_no_recursion_error(tmp_path):
    d = base(); prev = 3
    n = 3000
    for i in range(n):
        add(d, f'n{i}', '$_NOT_', A=prev, Y=100 + i); prev = 100 + i
    d['modules']['t']['ports']['boot_word']['bits'] = [prev, 6]
    add(d, 'z', '$_AND_', A=3, B='0', Y=6)
    r = run(tmp_path, d, ('--k', '0', '--cycles', '1', '--key', '3', '--goal-value', '1'))
    assert r.returncode == 0 and 'ATTACK_FOUND' in r.stdout          # even number of NOTs: out = sig0; sig=1 reaches goal 1
    assert 'Traceback' not in r.stderr


def test_safe_escapes_terminal_controls():
    assert g._safe('a\n\x1b[31m‮b') == 'a\\n\\x1b[31m\\u202eb'
