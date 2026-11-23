"""STAND-IN for the packaged CLI (plumbing tests only): answers `analyze` from the project's recorded study files. No solver."""
import csv, json, os, sys, time
REAL = os.environ.get('GS_STANDIN_REAL') or open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '_standin_real')).read().strip()   # set by make_overlay
def main(argv=None):
    a = list(argv or sys.argv[1:]); time.sleep(float(os.environ.get('STANDIN_CELL_SLEEP', '0.05')))
    opt = lambda n, d=None: a[a.index(n) + 1] if n in a else d
    path, top, K = a[1], opt('--top'), int(opt('--max-flips', '3'))
    goal = 'boot_ok' if opt('--goal-out') == 'boot_ok' else 'boot_word'
    mask = opt('--consumer-bits'); ins = opt('--input-sites', 'none') == 'all'; init = opt('--init', 'known'); rule = opt('--count-rule', 'stem')
    doc = json.load(open(path)); m = doc['modules'][top]
    if any(c['type'] in ('$_NAND_', '$_NOR_', '$_XNOR_') for c in m['cells'].values()):
        print('error: unsupported or malformed netlist: cell has type $_NAND_', file=sys.stderr); return 3
    gates = sum(1 for c in m['cells'].values() if c['type'] not in ('$_DFF_P_', '$scopeinfo'))
    stored = os.path.realpath(path).startswith(os.path.realpath(REAL + '/reference'))
    v = None
    if init == 'arbitrary': v = 0
    elif mask and stored and top == 'v2':
        for r in csv.DictReader(open(REAL + '/research/c3/m1/m1_all_masks.csv')):
            if int(r['mask_hex'], 16) == int(mask, 16): v = int(r['v2_spike_min_flips'])
    elif goal == 'boot_ok' or ins or init == 'free_nongoal': v = 1
    elif rule != 'stem': v = 3 if top.startswith('v2') else 2
    elif stored: v = {'v0': 1, 'v1': 1, 'v2': 3}[top]
    else: v = {18: 1, 25: 1, 72: 1, 85: 2, 89: 3, 83: 3, 63: 1}.get(gates, 2)      # by gate count of the stand-in netlists
    if os.environ.get('STANDIN_MISMATCH') == '1' and ins and goal == 'boot_word' and init == 'known': v = 2   # deliberate disagreement with the record
    if os.environ.get('STANDIN_UNKNOWN_CELL') == '1' and mask == '0x07': return 2
    rep = dict(schema='faultbound-wt-report/1', label='STAND-IN (plumbing test)', verdict='ATTACK_FOUND' if (v is not None and v <= K) else 'NO_ATTACK_UP_TO_BOUND', runtime_s=0.05)
    if rep['verdict'] == 'ATTACK_FOUND':
        rep['min_faults'] = v; rep['faults'] = [dict(net='standin_net_%d' % i, cycle=1) for i in range(v)]
        if rule != 'stem': rep['min_cost'] = v
    json.dump(rep, open(a[a.index('--report') + 1], 'w'))
    return 1 if rep['verdict'] == 'ATTACK_FOUND' else 0
