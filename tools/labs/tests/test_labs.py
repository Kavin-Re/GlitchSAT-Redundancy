"""Labs index: the result files of every EXPERIMENTAL module are valid labs-result/1, and the command line works."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import labs  # noqa: E402
import labs_result as LR  # noqa: E402


def test_results_valid():
    for mid, m in labs.MODULES.items():
        if m['status'] == 'PLANNED':
            assert labs.summary(mid)['findings'] == []
            continue
        d = labs.result(mid)
        assert d is not None, mid
        assert LR.validate(d) == [] and d['module'] == mid
        assert {f['label'] for f in d['findings']} <= set(LR.LABELS)
        assert os.path.exists(labs.summary(mid)['readme'])


def test_validator_rejects_bad():
    assert LR.validate({'schema': 'x'})
    d = LR.make('m', 't', 'q', dict(name='n', description='d', command='c'),
                [LR.finding('f', 'text', 'SIMULATED')], ['c'], dict(started='s', seconds=0, ok=True, errors=[]))
    assert LR.validate(d) == []
    d['findings'][0]['label'] = 'PROVED'
    assert LR.validate(d)


def test_cli():
    r = subprocess.run([sys.executable, os.path.join(HERE, 'labs.py'), 'list'], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and 'consttime' in r.stdout and 'PLANNED' in r.stdout
    r = subprocess.run([sys.executable, os.path.join(HERE, 'labs.py'), 'run', 'secretflow'], capture_output=True, text=True, timeout=60)
    assert r.returncode == 2
