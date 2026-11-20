"""ci/check_reproduce.py must reject duplicate rows, swapped inputs, summary-only forgeries."""
import json, os, shutil, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def tree(tmp):
    t = os.path.join(str(tmp), 't')
    for d in ('ci', 'results', 'reference', 'rtl'):
        src = os.path.join(ROOT, d)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(t, d), ignore=shutil.ignore_patterns('work', 'mutants', 'deep', 'logs'))
    os.makedirs(os.path.join(t, 'scripts'), exist_ok=True)
    shutil.copy(os.path.join(ROOT, 'scripts', 'glitchsat.py'), os.path.join(t, 'scripts'))
    return t


def chk(t, *a):
    return subprocess.run([sys.executable, os.path.join(t, 'ci', 'check_reproduce.py'), *a], capture_output=True, text=True, timeout=300)


def need_results():
    import pytest
    if not os.path.isfile(os.path.join(ROOT, 'results', 'reproduce_summary.json')): pytest.skip('run make reproduce first')


def test_clean_tree_passes(tmp_path):
    need_results(); r = chk(tree(tmp_path)); assert r.returncode == 0, r.stdout + r.stderr


def test_duplicate_row_rejected(tmp_path):
    need_results(); t = tree(tmp_path); p = os.path.join(t, 'results', 'reproduce_summary.json'); j = json.load(open(p))
    forged = dict(j['rows'][-1], verdict='ATTACK_FOUND', min_faults=2); j['rows'].insert(len(j['rows']) - 1, forged); json.dump(j, open(p, 'w'))
    r = chk(t); assert r.returncode == 1 and 'DUPLICATE ROW' in r.stdout


def test_swapped_netlist_detected(tmp_path):
    need_results(); t = tree(tmp_path)
    shutil.copy(os.path.join(t, 'reference/spike_netlists/v0.json'), os.path.join(t, 'reference/spike_netlists/v2.json'))
    r = chk(t); assert r.returncode == 1 and 'INPUT HASH' in r.stdout


def test_handwritten_summary_without_run_files_detected(tmp_path):
    need_results(); t = tree(tmp_path); shutil.rmtree(os.path.join(t, 'results', 'reproduce'))
    r = chk(t); assert r.returncode == 1 and 'RUN FILE' in r.stdout


def test_manifest_roundtrip_and_tamper(tmp_path):
    need_results(); t = tree(tmp_path); m = os.path.join(str(tmp_path), 'm.txt')
    assert chk(t, '--write-manifest', m).returncode == 0 and chk(t, '--manifest', m).returncode == 0
    with open(os.path.join(t, 'rtl', 'v0.v'), 'a') as f: f.write('\n// x\n')
    assert chk(t, '--manifest', m).returncode == 1
