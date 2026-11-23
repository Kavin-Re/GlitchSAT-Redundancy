"""Shared helpers of the bench/verification scripts: locate the repository, import the backend, list netlists."""
import os, sys, json, hashlib, csv

HERE = os.path.dirname(os.path.abspath(__file__))
FASTSAT = os.path.dirname(HERE)
ROOT = os.environ.get('GLITCHSAT_ROOT') or os.path.normpath(os.path.join(FASTSAT, '..', '..'))
if not os.path.isfile(os.path.join(ROOT, 'scripts', 'glitchsat.py')):
    sys.exit(f'repository root not found at {ROOT}; set GLITCHSAT_ROOT')
os.environ['GLITCHSAT_ROOT'] = ROOT
sys.path.insert(0, os.path.join(FASTSAT, 'scripts'))
sys.path.insert(0, os.path.join(FASTSAT, 'tests'))
import glitchsat_sat as S          # noqa: E402

SKIP_DIRS = {'.git', 'node_modules', '__pycache__', 'work'}


def repo_netlists():
    """Every distinct (by content hash) Yosys JSON netlist under the repository, except under ext/.
    Returns list of dict(path (relative), top, sha, ports, dups)."""
    seen = {}
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = sorted(d for d in dn if d not in SKIP_DIRS and not (dp == ROOT and d == 'ext'))
        for f in sorted(fn):
            if not f.endswith('.json'):
                continue
            p = os.path.join(dp, f)
            try:
                raw = open(p, 'rb').read()
                if b'"modules"' not in raw:
                    continue
                doc = json.loads(raw)
            except (OSError, ValueError):
                continue
            if not isinstance(doc, dict) or not isinstance(doc.get('modules'), dict):
                continue
            h = hashlib.sha256(raw).hexdigest()[:16]
            if h in seen:
                seen[h]['dups'] += 1
                continue
            for top, m in doc['modules'].items():
                if isinstance(m, dict) and 'ports' in m and 'cells' in m:
                    seen[h] = dict(path=os.path.relpath(p, ROOT), top=top, sha=h, dups=0,
                                   ports={k: (v.get('direction'), len(v.get('bits', []))) for k, v in m['ports'].items()})
                    break
    return sorted(seen.values(), key=lambda d: d['path'])


def heldout_params():
    """research/c4/ver: key and accept value per generated netlist (manifest.json) and the recorded z3 minimum at
    T=6, k<=3 for the full-width goal (heldout.csv rows whose mask covers every output bit).
    Returns {json basename: dict(top, key, acc, OW, recorded)}; recorded is an int, '>3', or None when not recorded."""
    out = {}
    man = os.path.join(ROOT, 'research', 'c4', 'ver', 'manifest.json')
    if not os.path.isfile(man):
        return out
    for m in json.load(open(man)):
        out[os.path.basename(m['json'])] = dict(top=m['top'], key=m['key'], acc=m['acc'], OW=m['OW'], recorded=None)
    gen = os.path.join(ROOT, 'research', 'c4', 'ver', 'gen')
    for f in sorted(os.listdir(gen)) if os.path.isdir(gen) else []:
        if f.startswith('V456_') and f.endswith('.json'):
            out[f] = dict(top=f.split('_')[1], key=0xC3, acc=0x96, OW=8, recorded=None)
    hc = os.path.join(ROOT, 'research', 'c4', 'ver', 'heldout.csv')
    if os.path.isfile(hc):
        for r in csv.DictReader(open(hc)):
            b = os.path.basename(r['json'])
            if b in out and int(r['mask'], 16) == (1 << out[b]['OW']) - 1 and r.get('solver') not in (None, '', 'unk'):
                out[b]['recorded'] = r['solver'] if r['solver'] == '>3' else int(r['solver'])
    # heldout.csv's `solver` column predates research/c4/ver/rerun_x.py (netlists with x init bits were first solved with a
    # parser that mapped x to 0); rerun_x.json holds the corrected values, which win where it has a full-width cell
    rx = os.path.join(ROOT, 'research', 'c4', 'ver', 'rerun_x.json')
    if os.path.isfile(rx):
        for e in json.load(open(rx)):
            b = os.path.basename(e['json'])
            if b in out and int(e['mask'], 16) == (1 << out[b]['OW']) - 1 and out[b]['recorded'] is not None:
                out[b]['recorded'] = e['new'] if e['new'] == '>3' else int(e['new'])
    return out


def default_params(n):
    """Goal/key used for a repository netlist in the cross-checks: the recorded ones where the repository states them,
    else the engine defaults (0x96 / 0xC3) cut to the port widths."""
    ho = heldout_params()
    b = os.path.basename(n['path'])
    wi, wo = n['ports']['sig'][1], n['ports']['boot_word'][1]
    if 'research/c4/ver/gen' in n['path'].replace(os.sep, '/') and b in ho:
        return dict(goal_value=ho[b]['acc'], key=ho[b]['key']), ho[b]['recorded']
    return dict(goal_value=0x96 & ((1 << wo) - 1), key=0xC3 & ((1 << wi) - 1)), None
