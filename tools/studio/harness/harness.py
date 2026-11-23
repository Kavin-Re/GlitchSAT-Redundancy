"""PLUMBING TESTS with stand-ins (see README.md). Usage: python3 harness.py [api]"""
import json, os, subprocess, sys, time, urllib.request, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_overlay
STUDIO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'studio.py')
def start(port, live=True, extra_env=None, cache=None):
    ov = make_overlay.make(tempfile.mkdtemp(prefix='gs-overlay-') + '/root')
    env = dict(os.environ, GLITCHSAT_ROOT=ov if live else make_overlay.REAL, XDG_CACHE_HOME=cache or tempfile.mkdtemp(prefix='gs-cache-'))
    if live:
        env['PYTHONPATH'] = ov + '/_standin_py'; env['PATH'] = ov + '/_standin_bin:' + env['PATH']
    env.update(extra_env or {})
    p = subprocess.Popen([sys.executable, STUDIO, '--no-browser', '--port', str(port), '--no-autostop'], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for _ in range(60):
        try: get(port, '/api/status'); break
        except Exception: time.sleep(0.1)
    return p
def get(port, path):
    return json.loads(urllib.request.urlopen(f'http://127.0.0.1:{port}{path}', timeout=20).read())
def post(port, path, body, hdr=True, timeout=120):
    rq = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=json.dumps(body).encode(), headers={'X-GlitchSAT': '1', 'Content-Type': 'application/json'} if hdr else {})
    return json.loads(urllib.request.urlopen(rq, timeout=timeout).read())
def wait_job(port, jid, t=180):
    t0 = time.time()
    while time.time() - t0 < t:
        j = get(port, '/api/job?id=' + jid)
        if j['status'] != 'running': return j
        time.sleep(0.3)
    raise TimeoutError(jid)
def api_tests():
    import threading
    P = 8811; s = start(P); ok = []
    def chk(name, cond, extra=''):
        ok.append(bool(cond)); print(('PASS ' if cond else 'FAIL ') + name, extra)
    try:
        st = get(P, '/api/status'); chk('status live + version', st['live'] and st['version'] == '0.9.0' and st['yosys_short'] == '0.33', str({k: st[k] for k in ('z3', 'yosys', 'version', 'workers')}))
        for des, flow, goal, k, exp in [('v0', 'plain', 'word', 3, 1), ('v1', 'plain', 'word', 3, 1), ('v2', 'plain', 'word', 3, 3), ('v2', 'plain', 'word', 2, None), ('v2_rtl', 'plain', 'word', 3, 2),
                                         ('v2_rtl', 'opt', 'word', 3, 3), ('v2e_rtl', 'plain', 'word', 3, 3), ('v2', 'plain', 'flag', 3, 1), ('v2', 'plain', 'word', 4, 3)]:
            r = post(P, '/api/analyze', dict(design=des, flow=flow, goal=goal, k=k, cycles=6, run_id='t'))
            good = 'error' not in r and r['_src'] == 'live' and r.get('min_faults') == exp and (exp is None or (r['_replay'] and r['_replay']['verified'])) and 'explanation' not in r and r['_map']
            chk(f'analyze live {des} {flow} {goal} k={k}', good, f"-> {r.get('verdict')} {r.get('min_faults')} cmp={r.get('_cmp') and (r['_cmp']['min'], r['_cmp']['same'])} reach={[f.get('reach') for f in r.get('faults', [])]} err={r.get('error')}")
        r = post(P, '/api/analyze', dict(design='v2', k='x'))
        chk('bad settings', r.get('error_kind') == 'bad_settings')
        try: post(P, '/api/analyze', dict(design='v2'), hdr=False); chk('POST without header refused', False)
        except Exception as e: chk('POST without header refused', '403' in str(e))
        try:
            rq = urllib.request.Request(f'http://127.0.0.1:{P}/api/status', headers={'Host': 'evil.example:80'}); urllib.request.urlopen(rq); chk('foreign Host refused', False)
        except Exception as e: chk('foreign Host refused', '403' in str(e))
        # jobs
        ss = get(P, '/api/studies'); chk('studies available', all(v['available'] for v in ss.values()), str({k: (v.get('run') or {}).get('cells') for k, v in ss.items()}))
        for sid in ('scope', 'enc', 'count', 'width', 'valid', 'dial', 'synth'):
            j = wait_job(P, post(P, '/api/job', dict(study=sid, params={}))['id'], 400)
            c = j['counts']; chk(f'job {sid}', j['status'] == 'done' and j['done'] == j['total'], f"{j['total']} cells {j['elapsed']} s counts={c}")
            if sid == 'valid': print('     valid results:', {k: (v.get('v'), v.get('rec'), v['cmp']) for k, v in j['results'].items()})
            if sid == 'synth': print('     synth states:', {k: v for k, v in c.items() if k.startswith('state_')}, 'example error:', next((v.get('note') for v in j['results'].values() if v['state'] == 'error'), None))
        j = wait_job(P, post(P, '/api/job', dict(study='scope', params={}))['id']); chk('second run comes from the cache', j['counts'].get('src_cached') == j['total'], str(j['counts']))
        j = wait_job(P, post(P, '/api/job', dict(study='ladder', params=dict(design='v2', goal='word', cycles=6, upto=3)))['id']); chk('ladder', all(v['cmp'] == 'match' for v in j['results'].values()), str({k: (v['state'], v.get('v')) for k, v in j['results'].items()}))
        f = get(P, '/api/findings'); chk('findings carry cached live cells', len(f['studies']['scope'].get('cached', {})) == 12 and 'error' not in f['synth'], str({k: len(v.get('cached', {})) for k, v in f['studies'].items()}))
    finally:
        s.terminate()
    # time limit, stop, engine error, unknown, mismatch
    s = start(P + 1, extra_env=dict(STANDIN_SLEEP='30', STANDIN_CELL_SLEEP='30'))
    try:
        t0 = time.time(); r = post(P + 1, '/api/analyze', dict(design='v2', k=3, cycles=6, time_limit_s=2, run_id='a')); dt = time.time() - t0
        chk('time limit -> UNKNOWN, never no-attack', r['verdict'] == 'UNKNOWN_TIMEOUT' and r['_stop']['why'] == 'timeout' and r['_replay'] is None and dt < 5 and 'no attack' not in r['_log'][-1]['plain'].split('not')[0], f'{dt:.1f} s; log: ' + r['_log'][-1]['plain'])
        res = {}
        th = threading.Thread(target=lambda: res.update(r=post(P + 1, '/api/analyze', dict(design='v2', k=3, cycles=6, time_limit_s=60, run_id='b')))); t0 = time.time(); th.start()
        time.sleep(1.0); post(P + 1, '/api/stop', dict(run_id='b')); th.join(); dt = time.time() - t0
        chk('Stop button -> UNKNOWN', res['r']['verdict'] == 'UNKNOWN_TIMEOUT' and res['r']['_stop']['why'] == 'stopped' and dt < 4, f'{dt:.1f} s')
        t0 = time.time(); r2 = {}; th = threading.Thread(target=lambda: r2.update(r=post(P + 1, '/api/analyze', dict(design='v1', k=1, cycles=6, time_limit_s=3, run_id='c')))); th.start()
        r3 = post(P + 1, '/api/analyze', dict(design='v0', k=1, cycles=6, time_limit_s=3, run_id='d')); th.join(); chk('two runs in parallel do not queue', time.time() - t0 < 5, f'{time.time() - t0:.1f} s')
        jid = post(P + 1, '/api/job', dict(study='scope', params=dict(time_limit_s=60)))['id']; time.sleep(1.0); post(P + 1, '/api/job/cancel', dict(id=jid)); j = wait_job(P + 1, jid, 20)
        chk('job cancel', j['status'] == 'cancelled' and not any(v['state'] == 'ok' for v in j['results'].values()), str(j['counts']))
        jid = post(P + 1, '/api/job', dict(study='width', params=dict(time_limit_s=2)))['id']; j = wait_job(P + 1, jid, 40)
        chk('cell time limit -> unknown, not a value', all(v['state'] == 'unknown' and v.get('v') is None for v in j['results'].values()), str(j['counts']))
    finally:
        s.terminate()
    s = start(P + 2, extra_env=dict(STANDIN_FAIL='synth', STANDIN_MISMATCH='1', STANDIN_UNKNOWN_CELL='1'))
    try:
        r = post(P + 2, '/api/analyze', dict(design='v2_rtl', k=3, cycles=6)); chk('engine error in plain words + fallback offered', r.get('error_kind') == 'engine' and 'could not turn' in r['error'] and r.get('can_fallback') and 'Module' in r['error_detail'], r.get('error'))
        r = post(P + 2, '/api/analyze', dict(design='v2_rtl', k=3, cycles=6, force_recorded=True)); chk('fallback to the saved result', r.get('_src') == 'recorded' and r.get('min_faults') == 2)
        j = wait_job(P + 2, post(P + 2, '/api/job', dict(study='scope', params={}))['id']); chk('mismatch is reported', j['counts'].get('mismatch') == 1, str(j['counts']))
        j = wait_job(P + 2, post(P + 2, '/api/job', dict(study='width', params={}))['id']); chk('solver-unknown cell stays unknown', j['counts'].get('state_unknown') == 1, str(j['counts']))
    finally:
        s.terminate()
    s = start(P + 3, extra_env=dict(STANDIN_UNKNOWN='1'))
    try:
        r = post(P + 3, '/api/analyze', dict(design='v2', k=3, cycles=6)); chk('solver unknown -> UNKNOWN', r['verdict'] == 'UNKNOWN_TIMEOUT' and r['_stop']['why'] == 'solver' and r['_replay'] is None)
    finally:
        s.terminate()
    print('RESULT', sum(ok), 'of', len(ok), 'passed (plumbing tests with stand-ins; not a test of z3 or Yosys)')
if __name__ == '__main__':
    api_tests()
