"""Lifecycle checks (real server, recorded mode): two windows, bye, reload, second launch, --port without value."""
import json, os, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
STUDIO = os.path.join(os.path.dirname(HERE), 'studio.py'); P = 8841
env = dict(os.environ, GLITCHSAT_ROOT=os.environ.get('GLITCHSAT_ROOT') or os.path.normpath(os.path.join(HERE, '..', '..', '..')))
def get(path): return urllib.request.urlopen(f'http://127.0.0.1:{P}{path}', timeout=5).read()
def post(path, body): return urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{P}{path}', data=json.dumps(body).encode(), headers={'X-GlitchSAT': '1'}), timeout=5).read()
s = subprocess.Popen([sys.executable, STUDIO, '--no-browser', '--port', str(P)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True); time.sleep(1.2)
get('/api/ping?cid=A'); get('/api/ping?cid=B')
post('/api/bye', dict(cid='A')); time.sleep(13); print('PASS' if s.poll() is None else 'FAIL', 'one of two windows closed: server stays up')
try:
    urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{P}/api/bye', data=b'{"cid":"B"}'), timeout=5); print('FAIL cross-site bye accepted')
except Exception as e: print('PASS' if '403' in str(e) else 'FAIL', 'bye without the header is refused')
time.sleep(1); post('/api/bye', dict(cid='B')); time.sleep(2); get('/api/ping?cid=C'); time.sleep(11); print('PASS' if s.poll() is None else 'FAIL', 'reload (bye, then a new window id): server stays up')
r = subprocess.run([sys.executable, STUDIO, '--no-browser', '--port', str(P)], env=env, capture_output=True, text=True, timeout=20); print('PASS' if 'already running' in r.stdout else 'FAIL', 'second launch reuses the first:', r.stdout.strip()[:70])
r = subprocess.run([sys.executable, STUDIO, '--port'], env=env, capture_output=True, text=True, timeout=20); print('PASS' if 'needs a value' in (r.stderr + r.stdout) else 'FAIL', '--port without a value:', (r.stderr + r.stdout).strip()[:60])
get('/pages/dial.html'); post('/api/bye', dict(cid='C')); time.sleep(13); print('PASS' if s.poll() is None else 'FAIL', 'explainer page open: server stays up after the last window closed')
s.terminate(); s.wait()
s = subprocess.Popen([sys.executable, STUDIO, '--no-browser', '--port', str(P)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True); time.sleep(1.2)
get('/api/ping?cid=A'); time.sleep(25); print('PASS' if s.poll() is None else 'FAIL', '25 s of silence: server stays up')
post('/api/bye', dict(cid='A')); time.sleep(13); print('PASS' if s.poll() is not None else 'FAIL', 'last window closed: server stops')
if s.poll() is None: s.terminate()
