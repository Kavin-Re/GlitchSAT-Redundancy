"""One `glitchsat` command: own-design verbs, Studio, engine and evidence tools; `check` has one meaning per form."""
import os
import sys

import pytest

from faultbound_wt import glitchsat_main as G


@pytest.fixture
def calls(monkeypatch):
    seen = []
    from faultbound_wt import cli, studio_launcher
    monkeypatch.setattr(cli, 'main', lambda a: seen.append(('engine', list(a))) or 0)
    monkeypatch.setattr(studio_launcher, 'main', lambda a: seen.append(('studio', list(a))) or 0)
    monkeypatch.setattr(G, '_own_design_main', lambda: (lambda a: seen.append(('own', list(a))) or 0))
    return seen


def test_routes(calls):
    for argv, want in ((['run', 'glitchsat.yaml', '--task', 'hardened'], ('own', ['run', 'glitchsat.yaml', '--task', 'hardened'])),
                       (['init', '--yes'], ('own', ['init', '--yes'])),
                       (['explain', 'GS052'], ('own', ['explain', 'GS052'])),
                       (['check', 'glitchsat.yaml'], ('own', ['check', 'glitchsat.yaml'])),
                       (['check', '--targets', 'glitchsat.toml'], ('engine', ['check', '--targets', 'glitchsat.toml'])),
                       (['check', '--targets=glitchsat.toml', '--sarif', 'o.sarif'], ('engine', ['check', '--targets=glitchsat.toml', '--sarif', 'o.sarif'])),
                       (['check-targets', '--targets', 't.toml'], ('engine', ['check', '--targets', 't.toml'])),
                       (['studio', '--no-browser'], ('studio', ['--no-browser'])),
                       (['analyze', 'n.json', '--top', 't'], ('engine', ['analyze', 'n.json', '--top', 't'])),
                       (['margin', 'r.json'], ('engine', ['margin', 'r.json']))):
        calls.clear()
        assert G.main(argv) == 0
        assert calls == [want], (argv, calls)


def test_help_lists_every_family(capsys):
    assert G.main(['--help']) == 0
    out = capsys.readouterr().out
    for w in ('run', 'init', 'check', 'explain', 'studio', 'analyze', '--targets'):
        assert w in out


def test_own_design_tool_runs_through_the_dispatcher(monkeypatch, capsys):
    """With the own-design package importable (the module folder beside this overlay in a work tree), `glitchsat
    templates` reaches it."""
    byod = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'byod')
    if not os.path.isdir(os.path.join(byod, 'glitchsat_byod')) and os.environ.get('GLITCHSAT_EXT'):
        byod = os.path.join(os.environ['GLITCHSAT_EXT'], 'byod')
    if not os.path.isdir(os.path.join(byod, 'glitchsat_byod')):
        pytest.skip('own-design tool not beside this overlay')
    monkeypatch.syspath_prepend(byod)
    assert G.main(['templates']) == 0
    assert 'secure_boot_wrong_key' in capsys.readouterr().out
