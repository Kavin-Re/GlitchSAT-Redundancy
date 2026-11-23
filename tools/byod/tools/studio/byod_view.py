"""Studio module: "Open my design".

A learner opens an example or their own design, answers five plain questions, and sees the same kind of answer the
Studio gives for its built-in designs: how many glitches are needed, how the cheapest attack works, whether the
protection survived the build, and whether it holds for any waiting time. The wizard writes the same commented
glitchsat.yaml as `glitchsat init`; the analysis is the `glitchsat run` command, started as a separate process
that can be stopped.

Loaded by tools/studio/studio_byod.py (no change to studio.py), or by a two-line hook in studio.py (see
INSTALL.md). Everything stays on this computer: the server answers 127.0.0.1 only (Studio's Host/Origin checks),
every request of this module needs a per-session token, pages get a strict Content-Security-Policy, and nothing is
fetched from the network.

A project file is data, but it names Yosys commands and files. So a project that is not one of the built-in gallery
examples (or a file this wizard just wrote) is never run on one click: "Open and run" first shows the resolved Yosys
commands, and the run request must carry the confirmation code of exactly that file content. Gallery examples run on a
copy in a scratch folder, so nothing is written into the install folder. Without Yosys the gallery shows the saved
results of the same runs, labelled RECORDED.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BYOD = os.environ.get('GLITCHSAT_BYOD') or next((d for d in (os.path.dirname(os.path.dirname(HERE)), os.path.join(os.path.dirname(os.path.dirname(HERE)), 'byod')) if os.path.isdir(os.path.join(d, 'glitchsat_byod'))), None)
if BYOD and BYOD not in sys.path:
    sys.path.insert(0, BYOD)

TOKEN = secrets.token_urlsafe(24)
CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'")
JOBS = {}
ROOTS = [os.path.expanduser('~'), os.path.join(BYOD or '', 'examples')] + [
    os.path.abspath(os.path.expanduser(r)) for r in (os.environ.get('GLITCHSAT_ALLOW_ROOTS') or '').split(os.pathsep) if r.strip()]
# the Studio's --allow-root DIR (repeatable) adds folders outside the home folder (audit 2-S5)
for _i, _a in enumerate(sys.argv[:-1]):
    if _a == '--allow-root':
        ROOTS.append(os.path.abspath(os.path.expanduser(sys.argv[_i + 1])))


def _ok_path(p):
    """Only folders under the home folder or the examples; no hidden folders."""
    rp = os.path.realpath(os.path.expanduser(p or '~'))
    if not any(rp == os.path.realpath(r) or rp.startswith(os.path.realpath(r) + os.sep) for r in ROOTS if r):
        return None
    if any(part.startswith('.') for part in rp.split(os.sep) if part):
        return None
    return rp


def browse(q):
    p = _ok_path(q.get('path') or '~')
    if not p or not os.path.isdir(p):
        return dict(error='That folder cannot be opened here (only folders in your home folder).',
                    help='To allow a folder elsewhere, start the Studio with --allow-root /that/folder '
                         '(or set GLITCHSAT_ALLOW_ROOTS), then reload this window.')
    items = []
    for n in sorted(os.listdir(p), key=str.lower):
        if n.startswith('.'):
            continue
        fp = os.path.join(p, n)
        if os.path.isdir(fp):
            items.append(dict(name=n, kind='dir'))
        elif n.endswith(('.v', '.sv', '.yaml', '.yml', '.json')):
            items.append(dict(name=n, kind='file'))
    return dict(path=p, parent=os.path.dirname(p) if _ok_path(os.path.dirname(p)) else None, items=items[:400],
                has_yaml=os.path.isfile(os.path.join(p, 'glitchsat.yaml')))


EXAMPLES = os.path.join(BYOD or '', 'examples')
_TOOLS = {}


def tools_status():
    """Is Yosys here? (cached; the gallery falls back to saved results without it)."""
    if 'y' not in _TOOLS:
        try:
            from glitchsat_byod.flows import find_yosys
            y = find_yosys()
            _TOOLS['y'] = dict(yosys=True, version=y.short())
            try:                                   # the SystemVerilog frontend: only some Yosys builds have it (0.67+)
                find_yosys(need_slang=True)
                _TOOLS['y']['slang'] = True
            except Exception:                  # noqa: BLE001
                _TOOLS['y']['slang'] = False
        except Exception as e:             # noqa: BLE001
            _TOOLS['y'] = dict(yosys=False, why=str(getattr(e, 'msg', e)))
    return _TOOLS['y']


def _saved_name(key):
    return key.replace('.yaml', '').replace(' --task ', '.') + '.report.json'


def _lesson(n):
    lp = os.path.join(EXAMPLES, n, 'lesson.json')
    if not re.match(r'^[A-Za-z0-9_-]+$', n or '') or not os.path.isfile(lp):
        return None
    return json.load(open(lp))


def _needs(n, fname):
    """What one gallery run needs beyond a plain Yosys: [(id, plain text)] for the parts not found on this computer."""
    out = []
    try:
        text = open(os.path.join(EXAMPLES, n, fname or 'glitchsat.yaml'), encoding='utf-8').read()
    except OSError:
        return out
    t = tools_status()
    if re.search(r'^\s*frontend:\s*slang\b', text, re.M) and t.get('yosys') and not t.get('slang'):
        out.append(('slang', 'needs Yosys 0.67 or newer (SystemVerilog reader read_slang); this computer has Yosys %s'
                    % (t.get('version') or '?')))
    if re.search(r'^\s*frontend:\s*slang\b', text, re.M) and not os.path.isfile(os.path.join(EXAMPLES, n, 'ot', 'prim_count.sv')) \
            and n == 'opentitan_count':
        out.append(('sources', 'needs the OpenTitan sources (sh fetch_ot.sh in the example folder)'))
    m = re.search(r'\$GLITCHSAT_LIBS/([^\s\],]+)', text)
    if m:
        try:
            from glitchsat_byod.flows import libs_dir
            if not os.path.isfile(os.path.join(libs_dir(), m.group(1))):
                out.append(('liberty', 'needs the %s cell library (scripts/fetch_libs.sh downloads it once)' % m.group(1).split('/')[0]))
        except Exception:                  # noqa: BLE001
            pass
    return out


def examples():
    out = []
    for n in sorted(os.listdir(EXAMPLES)):
        x = _lesson(n)
        if x is None:
            continue
        x['id'] = n
        x['folder'] = os.path.join(EXAMPLES, n)
        for r in x.get('runs') or []:
            key = (r.get('file') or 'glitchsat.yaml') + (' --task ' + r['task'] if r.get('task') else '')
            r['saved'] = os.path.isfile(os.path.join(EXAMPLES, n, 'saved', _saved_name(key)))
            nd = _needs(n, r.get('file') or 'glitchsat.yaml') if tools_status().get('yosys') else []
            r['needs'] = [t for _, t in nd]          # empty: this run can be computed live here
        out.append(x)
    out.sort(key=lambda x: x.get('order', 99))
    t = dict(tools_status())
    import importlib.util
    t['pyyaml'] = importlib.util.find_spec('yaml') is not None     # the wizard and the templates read YAML (audit 9-S1)
    return dict(examples=out, tools=t)


def saved(q):
    """The saved full report of one gallery run (RECORDED), for computers without Yosys."""
    n = q.get('ex') or ''
    x = _lesson(n)
    if x is None:
        return dict(error='No such example.')
    for r in x.get('runs') or []:
        if (r.get('file') or 'glitchsat.yaml') == q.get('file') and (r.get('task') or '') == (q.get('task') or ''):
            key = r.get('file', 'glitchsat.yaml') + (' --task ' + r['task'] if r.get('task') else '')
            p = os.path.join(EXAMPLES, n, 'saved', _saved_name(key))
            if not os.path.isfile(p):
                return dict(error='No saved result for this run.')
            rep = json.load(open(p))
            from glitchsat_byod.report import plain, plain_findings
            rep['plain_findings'] = plain_findings(rep)
            return dict(report=rep, plain=plain(rep), recorded=True, when=time.strftime('%Y-%m-%d', time.localtime(os.path.getmtime(p))))
    return dict(error='No such run in this example.')


def _nonce(path):
    """Confirmation code for exactly this file content (changes when the file changes)."""
    with open(path, 'rb') as f:
        h = hashlib.sha256(f.read()).hexdigest()
    return hmac.new(TOKEN.encode(), (os.path.realpath(path) + '\0' + h).encode(), 'sha256').hexdigest()[:32]


def plan(path, task=None):
    """What running this project would do: the Yosys commands of every flow, resolved from the file (no Yosys run)."""
    from glitchsat_byod import project as PRJ
    from glitchsat_byod import flows as FL
    spec, W = PRJ.load(path, task)
    top = spec.get('top') or '<top>'
    flows = {}
    for fl in spec['flows']:
        try:
            libs = FL.lib_path(FL.FLOWS[fl]['lib'], spec) if FL.FLOWS.get(fl, {}).get('lib') else []
        except Exception as e:             # noqa: BLE001
            flows[fl] = ['(%s)' % getattr(e, 'msg', e)]
            continue
        try:
            reads = FL.read_cmds(spec, None, top=None if top == '<top>' else top, preview=True)
        except Exception as e:             # noqa: BLE001
            reads = ['(%s)' % getattr(e, 'msg', e)]
        if fl == 'netlist' or spec['frontend'] in ('netlist', 'json'):
            body = ['hierarchy -check -top %s' % top, FL.KEEPH, 'flatten', 'opt_clean'] + FL.NORMALISE
        else:
            body = FL.flow_cmds(fl, top, libs, None, spec)
        flows[fl] = reads + body + ['write_json "<work folder>/netlist.json"']
    return dict(path=path, name=spec['name'], flows=flows, custom=bool(spec.get('yosys_script')),
                files=[os.path.relpath(x, spec['base']) for x in spec['sources']], nonce=_nonce(path),
                gallery=_in_gallery(path))


def _in_gallery(p):
    rp, rg = os.path.realpath(p), os.path.realpath(EXAMPLES)
    return rp.startswith(rg + os.sep)


def open_design(q):
    from glitchsat_byod import init as INIT
    from glitchsat_byod.errors import GSError
    folder = _ok_path(q.get('folder'))
    if not folder or not os.path.isdir(folder):
        return dict(error='Choose a folder in your home folder.')
    srcs = q.get('sources') or INIT.find_sources(folder)
    if not srcs:
        return dict(error='No Verilog (.v) or SystemVerilog (.sv) files were found in this folder, or in rtl/ or src/ inside it.',
                    help='Pick the folder that holds your design files.')
    try:
        det = INIT.suggest(folder, srcs, q.get('top') or None)
    except GSError as e:
        return dict(error=e.msg, help=e.help, code=e.code, note=e.note, candidates=getattr(e, 'candidates', None), sources=srcs)
    det['sources'] = srcs
    det['folder'] = folder
    det['ports'] = {k: list(v) for k, v in det['ports'].items()}
    return det


def write_yaml(q):
    from glitchsat_byod import init as INIT
    from glitchsat_byod import project as PRJ
    from glitchsat_byod.errors import GSError
    folder = _ok_path(q.get('folder'))
    if not folder:
        return dict(error='Choose a folder in your home folder.')
    a = q.get('answers') or {}
    fn = q.get('file') or 'glitchsat.yaml'
    if not isinstance(fn, str) or not re.match(r'^[A-Za-z0-9_.-]+\.ya?ml$', fn) or fn.startswith('.'):
        return dict(error='The project file name must be a plain name ending in .yaml (no folders).')
    try:
        text = INIT.make_yaml(a)
    except (GSError, KeyError, TypeError, ValueError) as e:
        return dict(error='These answers cannot be written: %s' % getattr(e, 'msg', e))
    path = os.path.join(folder, fn)
    if _ok_path(path) != os.path.realpath(path):
        return dict(error='That file cannot be written here.')
    if os.path.exists(path) and not q.get('overwrite'):
        return dict(error='%s already exists.' % os.path.basename(path), exists=True, text=text)
    if q.get('dry'):
        return dict(text=text)
    with open(path, 'w') as f:
        f.write(text)
    try:
        PRJ.load(path)
    except GSError as e:
        return dict(error=e.msg, help=e.help, code=e.code, path=path, text=text)
    return dict(path=path, text=text, nonce=_nonce(path))


def read_yaml(q):
    p = _ok_path(q.get('path'))
    if not p or not os.path.isfile(p) or not p.endswith(('.yaml', '.yml')):
        return dict(error='That file cannot be opened here (only .yaml project files in your home folder).')
    from glitchsat_byod import project as PRJ
    from glitchsat_byod.errors import GSError
    try:
        spec, W = PRJ.load(p)
        pl = plan(p, q.get('task') or None)
    except GSError as e:
        return dict(error=e.msg, help=e.help, code=e.code, text=open(p).read())
    tasks = list((spec['raw'].get('tasks') or {}).keys())
    return dict(path=p, text=open(p).read(), name=spec['name'], tasks=tasks, checks=[c['id'] for c in spec['checks']], plan=pl,
                nonce=pl['nonce'])


SCRATCH = []                               # gallery copies made by this Studio session: removed when it stops


def _scratch_base():
    return os.path.join(tempfile.gettempdir(), 'glitchsat-studio-%d' % os.getuid() if hasattr(os, 'getuid') else 'glitchsat-studio')


def _clean_scratch(max_age_s=12 * 3600):
    """Remove gallery copies of earlier sessions (older than max_age_s, so a second Studio window keeps its own)."""
    base = _scratch_base()
    try:
        for n in os.listdir(base):
            d = os.path.join(base, n)
            if os.path.isdir(d) and not os.path.islink(d) and time.time() - os.path.getmtime(d) > max_age_s:
                shutil.rmtree(d, ignore_errors=True)
    except OSError:
        pass


def _clean_session():
    for d in SCRATCH:
        shutil.rmtree(d, ignore_errors=True)


import atexit                              # noqa: E402
atexit.register(_clean_session)
_clean_scratch()


def _gallery_copy(ex, fname):
    """Copy a gallery example to a scratch folder and return the project path there (the install folder stays clean)."""
    if _lesson(ex) is None or not re.match(r'^[A-Za-z0-9_.-]+\.ya?ml$', fname or ''):
        return None
    src = os.path.join(EXAMPLES, ex)
    if not os.path.isfile(os.path.join(src, fname)):
        return None
    base = _scratch_base()
    os.makedirs(base, mode=0o700, exist_ok=True)
    dst = tempfile.mkdtemp(prefix=ex + '-', dir=base)
    SCRATCH.append(dst)
    shutil.copytree(src, os.path.join(dst, ex), ignore=shutil.ignore_patterns('.glitchsat', '*.lock', 'saved', 'expected_*'))
    return os.path.join(dst, ex, fname)


def start_run(q):
    if q.get('example'):
        if not tools_status()['yosys']:
            return dict(error='Running an example live needs the build tool (Yosys), which is not installed here.',
                        code='GS021', cause='no_yosys', saved=True)
        nd = _needs(str(q['example']), str(q.get('file') or 'glitchsat.yaml')) if _lesson(str(q['example'])) else []
        if nd:
            return dict(error='This example cannot be computed live on this computer: it %s.' % '; it '.join(t for _, t in nd),
                        code='GS021', cause=nd[0][0], saved=True)
        p = _gallery_copy(str(q['example']), str(q.get('file') or 'glitchsat.yaml'))
        if not p:
            return dict(error='No such example.')
    else:
        p = _ok_path(q.get('path'))
        if not p or not os.path.isfile(p) or not p.endswith(('.yaml', '.yml')):
            return dict(error='That project file cannot be opened here.')
        if not hmac.compare_digest(str(q.get('confirm') or ''), _nonce(p)):
            return dict(error='This project was not confirmed. Look at the commands it runs and confirm them first.',
                        confirm_needed=True)
    if q.get('task') and not re.match(r'^[A-Za-z_][A-Za-z0-9_-]*$', str(q['task'])):
        return dict(error='That task name cannot be used.')
    jid = secrets.token_hex(6)
    cmd = [sys.executable, os.path.join(BYOD, 'glitchsat'), 'run', p, '--json-only']
    if q.get('task'):
        cmd += ['--task', str(q['task'])]
    if q.get('quick'):
        cmd += ['--quick']
    env = dict(os.environ)
    jt = tempfile.mkdtemp(prefix='glitchsat-run-')
    env['TMPDIR'] = jt                       # solver files of this run stay in a folder of its own
    j = dict(id=jid, path=p, task=q.get('task'), status='running', lines=[], started=time.time(), out='', err='')
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=os.path.dirname(p), env=env)
    j['proc'] = proc

    def pump_err():
        for ln in proc.stderr:
            ln = ln.rstrip()
            if ln.startswith('  ... '):
                j['lines'].append(dict(t=round(time.time() - j['started'], 1), msg=ln[6:]))
            else:
                j['err'] += ln + '\n'

    def pump_out():
        j['out'] = proc.stdout.read()
        proc.wait()
        th.join()
        j['code'] = proc.returncode
        if proc.returncode in (0, 1, 2) and j['out'].strip():
            try:
                j['report'] = json.loads(j['out'])
                from glitchsat_byod.report import plain
                j['plain'] = plain(j['report'])
            except ValueError:
                j['status'] = 'error'
        j['status'] = j.get('status') if j.get('status') == 'stopped' else ('done' if j.get('report') else 'error')
        shutil.rmtree(jt, ignore_errors=True)
    th = threading.Thread(target=pump_err, daemon=True)
    th.start()
    threading.Thread(target=pump_out, daemon=True).start()
    JOBS[jid] = j
    return dict(id=jid)


def job(q):
    j = JOBS.get(q.get('id', ''))
    if not j:
        return dict(error='no such run')
    return {k: v for k, v in j.items() if k not in ('proc', 'out')}


def stop(q):
    j = JOBS.get(q.get('id', ''))
    if j and j['status'] == 'running':
        j['status'] = 'stopped'
        j['proc'].terminate()
    return dict(ok=bool(j))


def prefill(q):
    from glitchsat_byod import init as INIT
    from glitchsat_byod import templates as TPL
    import yaml
    t = q.get('template')
    if t not in TPL.NAMES:
        return dict(error='unknown template')
    det = dict(inputs=list(q.get('inputs') or []), outputs=list(q.get('outputs') or []), ports=q.get('ports') or {})
    p = os.path.join(BYOD, 'templates', t + '.yaml')
    doc = yaml.safe_load(open(p)) if os.path.isfile(p) else {}
    params = ((doc.get('checks') or [{}])[0].get('params') or {})
    return dict(params=INIT.prefill(t, params, det),
                must_hold=INIT.must_hold_example(det, q.get('clock'), q.get('reset')))


def templates():
    from glitchsat_byod import templates as TPL
    import yaml
    out = []
    for n in TPL.NAMES:
        p = os.path.join(BYOD, 'templates', n + '.yaml')
        doc = yaml.safe_load(open(p)) if os.path.isfile(p) else {}
        params = ((doc.get('checks') or [{}])[0].get('params') or {})
        out.append(dict(id=n, plain=TPL.PLAIN[n], params=params, snippet=open(p).read() if os.path.isfile(p) else ''))
    return dict(templates=out)


GET = {'/api/byod/examples': lambda q: examples(), '/api/byod/templates': lambda q: templates(), '/api/byod/job': job,
       '/api/byod/saved': saved}
POST = {'/api/byod/browse': browse, '/api/byod/open': open_design, '/api/byod/write': write_yaml, '/api/byod/read': read_yaml,
        '/api/byod/run': start_run, '/api/byod/stop': stop, '/api/byod/prefill': prefill}


def handle(h, method, path, q):
    """Called by the Studio's request handler. Returns True when this module answered."""
    if not path.startswith('/api/byod/'):
        return False
    tok = h.headers.get('X-GlitchSAT-Token')
    if not tok or not hmac.compare_digest(tok, TOKEN):
        # A key from an earlier start of the Studio: say so in plain words (the page cannot recover without a reload).
        h._send(403, json.dumps(dict(error='The Studio was restarted, so this window still holds the key of the earlier '
                                           'session. Reload this window to continue.', code='STALE_SESSION'))
                if tok else '{"error":"forbidden"}')
        return True
    fn = (GET if method == 'GET' else POST).get(path)
    if not fn:
        h._send(404, '{"error":"not found"}')
        return True
    try:
        h._send(200, json.dumps(fn(q), default=str))
    except Exception as e:                 # noqa: BLE001
        h._send(200, json.dumps(dict(error='The design tools hit an internal error.', detail='%s: %s' % (type(e).__name__, e))))
    return True


def install(page):
    page = page.replace('</style></head>', CSS + '</style></head>', 1)
    i = page.rfind('</body>')
    return page[:i] + '<script>' + JS.replace('__TOKEN__', TOKEN) + '</script>' + page[i:]


CSS = r'''
#v-mine .sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
#v-mine{max-width:1180px;margin-left:auto;margin-right:auto}
.by-note{border:1px solid var(--line);border-left:3px solid var(--acc);border-radius:6px;padding:4px 12px;margin:0 0 10px;background:var(--panel)}
.by-card .btn{white-space:normal;text-align:left}
.by-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}
.by-card{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:12px}
.by-card h4{margin:0 0 6px}.by-card p{margin:4px 0;color:var(--mut);font-size:12.5px}
.by-steps{display:flex;gap:6px;margin:6px 0 12px;flex-wrap:wrap}.by-steps span{padding:3px 8px;border:1px solid var(--line);border-radius:12px;font-size:11.5px;color:var(--mut)}
.by-steps span.on{border-color:var(--acc);color:var(--txt)}
.by-big{font-size:17px;font-weight:650;margin:4px 0 8px}
.by-ev{font-size:12px;color:var(--mut);margin:2px 0 2px 14px}
.by-row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:6px 0}
.by-row input[type=text]{min-width:320px;flex:1}
.by-list{max-height:260px;overflow:auto;border:1px solid var(--line);border-radius:5px}
.by-list button{display:block;width:100%;text-align:left;background:none;border:0;border-bottom:1px solid var(--line);padding:5px 9px;color:var(--txt)}
.by-list button:hover{background:var(--raised)}
.by-log{font:12px var(--mono,monospace);background:var(--inset);border:1px solid var(--line);border-radius:5px;padding:8px;max-height:200px;overflow:auto}
.by-wave text{font:11px var(--mono,monospace);fill:var(--txt)}.by-wave .f{fill:var(--hot,#e5484d)}
.by-pill{display:inline-block;padding:1px 7px;border-radius:9px;border:1px solid var(--line2);font-size:11px}
.by-pill.bad{border-color:var(--hot,#e5484d)}.by-pill.good{border-color:var(--ok,#30a46c)}
table.by-t{border-collapse:collapse;font-size:12.5px}table.by-t td,table.by-t th{border-bottom:1px solid var(--line);padding:3px 8px;text-align:left}
'''

JS = r'''
(function(){
const TOKEN='__TOKEN__';
const q=s=>document.querySelector(s), qa=s=>Array.from(document.querySelectorAll(s));
const H={'X-GlitchSAT':'1','X-GlitchSAT-Token':TOKEN,'Content-Type':'application/json'};
const get=p=>fetch(p,{headers:H}).then(r=>r.json());
const post=(p,b)=>fetch(p,{method:'POST',headers:H,body:JSON.stringify(b||{})}).then(r=>r.json());
const e=s=>esc(s);
const TECH=()=>typeof tech==='function'&&tech();
const HONK=k=>typeof hon==='function'&&typeof HON!=='undefined'&&HON[k]?hon(k):`<span class="by-pill">${e(k)}</span>`;
const CSSE=x=>(window.CSS&&CSS.escape)?CSS.escape(x):String(x).replace(/["\\\]\[]/g,'\\$&');
const B={step:'home',det:null,ans:null,tpl:null,yaml:null,job:null,rep:null,browse:null,tools:null};
// Plain view: progress lines in the app's own words (the exact tool words stay in Technical view)
const PLAINMSG=[[/^reading the design/,'reading your design'],[/^synthesising with flow `([^`]+)`/,'building the chip plan ($1 build)'],
 [/^reading the (\S+) netlist into the fault model/,'turning the $1 chip plan into the glitch model'],[/building the monitor/,'writing the question as a small circuit'],
 [/elaborating the RTL reference/,'reading your written design again, to compare'],[/validating by simulation/,'checking the chip plan behaves like the written design'],
 [/searching the smallest attack/,'searching the cheapest attack'],[/listing every smallest attack/,'listing every cheapest attack'],
 [/smallest attack for flow (\S+)/,'searching the cheapest attack on the $1 build'],[/merge lint/,'checking the copies are still separate in each build'],
 [/unbounded proof/,'checking it holds for any waiting time']];
const siteName=x=>{if(TECH())return `<code>${e(x)}</code>`;let m;
 if((m=/^(\S+) \(.* flip-flop (?:stored value|output)\)$/.exec(x)))return `the memory cell behind <code>${e(m[1])}</code>`;
 if((m=/^(\S+) \((\w+) gate output\)$/.exec(x)))return `the ${e(m[2])} gate that drives <code>${e(m[1])}</code>`;
 if((m=/^(?:(.*): )?(\w+) gate #\d+$/.exec(x)))return `a ${e(m[2])} gate inside the circuit${m[1]?' (in <code>'+e(m[1])+'</code>)':''}`;
 return `<code>${e(x)}</code>`};
const plainMsg=m=>{if(TECH())return m;for(const [rx,t] of PLAINMSG)if(rx.test(m))return m.replace(/^check `[^`]*`(, flow \S+)?: /,'').replace(rx,t).replace(/^(.*?)(\(.*\))?$/,'$1');return m};
const STEPS=['Your design','Clock and reset','Who can do what','What must never happen','Check and run'];
function steps(i){return `<div class="by-steps">${STEPS.map((s,k)=>`<span class="${k===i?'on':''}">${k+1}. ${e(s)}</span>`).join('')}</div>`}
/* GS021 covers several missing parts; tell them apart so the advice fits the real cause (audit 2-S3) */
function gsCause(r){if(r.cause)return r.cause==='no_yosys'?'yosys':r.cause;const t=[r.error,r.help,r.note].join(' ');
 if(/read_slang|SystemVerilog frontend/.test(t))return 'slang';if(/liberty|cell library|GLITCHSAT_LIBS/i.test(t))return 'liberty';
 if(/repository|engine `|scripts\/glitchsat\.py|GLITCHSAT_ROOT/.test(t))return 'engine';return 'yosys'}
/* In recorded mode a button shows a saved result: its verb is "Show", never "Run" (audit 1-N2) */
const runShow=l=>String(l||'').replace(/^(\d+\.\s*)?Run\b/,(m,n)=>(n||'')+'Show');
function err(r){if(r.code==='STALE_SESSION')return `<div class="err" role="alert"><b>The Studio was restarted: reload this window.</b><p>${e(r.error)}</p><p><button class="btn primary" onclick="location.reload()">Reload this window</button></p></div>`;

 if(r.code==='GS021'){const why=gsCause(r);const det=`<details class="raw"><summary>Details</summary><pre>${e((r.error||'')+'\n'+(r.help||'')+'\n'+(r.note||''))}</pre><p class="hint">Code ${e(r.code)}: <code>glitchsat explain ${e(r.code)}</code>; <code>glitchsat doctor</code> shows what is installed.</p></details>`;
  const saved=r.saved?'<p>The saved result of the same run is still there: press the example\'s button again to see it, labelled RECORDED.</p>':'';
  if(why==='slang')return `<div class="err"><b>This example needs a newer build tool.</b><p>It is written in SystemVerilog, which needs <span class="keep">Yosys 0.67</span> or newer (with the <code class="keep">read_slang</code> reader). The build tool on this computer is older${B.tools&&B.tools.version?' (<span class="keep">'+e(B.tools.version)+'</span>)':''}, so installing it again from the system packages will not help.</p><p>Install a newer one (for example the OSS CAD Suite) and start the Studio again, or point <code class="keep">GLITCHSAT_YOSYS_SLANG</code> at it.</p>${saved}${det}</div>`;
  if(why==='liberty')return `<div class="err"><b>This example needs a cell library that is not on this computer.</b><p>${e(r.error||'')}</p><p>Run <code class="keep">sh scripts/fetch_libs.sh</code> once (it downloads the library), then start the Studio again.</p>${saved}${det}</div>`;
  if(why==='sources')return `<div class="err"><b>This example needs its source files first.</b><p>${e(r.error||'')}</p>${saved}${det}</div>`;
  if(why==='engine')return `<div class="err"><b>A part of GlitchSAT was not found on this computer.</b><p>${e(r.error||'')}</p>${r.help?`<p>${e(r.help)}</p>`:''}${det}</div>`;
  if(!TECH())return `<div class="err"><b>The build tool is not installed on this computer.</b><p>GlitchSAT needs the free chip build tool (<span class="keep">Yosys</span>) to read a design. The gallery above shows the saved results of the same runs, so you can still look at every example.</p><p>To run designs live, install it (Debian/Ubuntu: <code class="keep">sudo apt-get install -y yosys</code>) and start the Studio again.</p>${det}</div>`}
 return `<div class="err"><b>${e(r.error)}</b>${r.help?`<p>${e(r.help)}</p>`:''}${r.note||r.code?`<details class="raw"><summary>Details</summary>${r.note?`<pre>${e(r.note)}</pre>`:''}${r.code?`<p class="hint">Code ${e(r.code)}: run <code>glitchsat explain ${e(r.code)}</code> for more.</p>`:''}</details>`:''}</div>`}
function el(){return q('#v-mine')}
function draw(root){root=root||el();if(!root)return;
 if(B.step==='home')return home(root);if(B.step==='w1')return w1(root);if(B.step==='w2')return w2(root);if(B.step==='w3')return w3(root);
 if(B.step==='w4')return w4(root);if(B.step==='w5')return w5(root);if(B.step==='run')return run(root)}
function home(root){
 root.innerHTML=`<h2 class="vt">Open my design</h2>
 <p>GlitchSAT asks one question about a chip: <b>how many tiny glitches does an attacker need to make it do something it must never do?</b> Start with an example, or bring your own Verilog design.</p>
 <div class="panel"><div class="ph"><h4>1. Try an example</h4></div><div class="pb"><div id="by-ban"></div><div class="by-cards" id="by-ex">Loading the examples…</div></div></div>
 <div class="panel"><div class="ph"><h4>2. My own design</h4></div><div class="pb"><p>Choose the folder that holds your design files (.v or .sv). Nothing leaves this computer.</p>
 <div class="by-row"><label class="sr" for="by-path">Folder of your design</label><input type="text" id="by-path" aria-label="Folder of your design" placeholder="/home/you/my_chip" value="${e(B.browse&&B.browse.path||'')}"><button class="btn" id="by-br">Browse…</button><button class="btn primary" id="by-go">Use this folder</button></div><div id="by-bl"></div></div></div>
 <div class="panel"><div class="ph"><h4>3. I already have a glitchsat.yaml</h4></div><div class="pb"><div class="by-row"><label class="sr" for="by-yp">Path of your glitchsat.yaml</label><input type="text" id="by-yp" aria-label="Path of your glitchsat.yaml" placeholder="/home/you/my_chip/glitchsat.yaml"><button class="btn primary" id="by-yo">Open and run</button></div><div id="by-ye"></div></div></div>
 <p class="hint">Everything is computed on this computer. Each result carries the Studio's labels: ${HONK('live')} computed now, ${HONK('recorded')} a saved result, and ${HONK('proved')} only for "for any waiting time"; every other number holds within the stated number of steps and glitches.</p>`;
 get('/api/byod/examples').then(r=>{if(r.code==='STALE_SESSION'){q('#by-ex').innerHTML=err(r);return}B.tools=r.tools||{};const live=!!B.tools.yosys;
  const ban=live?'':`<div class="by-note" role="note"><p><b>Running an example live needs the build tool (<span class="keep">Yosys</span>), which is not installed here.</b> You are seeing the saved results of the same runs, labelled ${HONK('recorded')}. To run them live, install it (Debian/Ubuntu: <code class="keep">sudo apt-get install -y yosys</code>) and start the Studio again.</p></div>`;
  q('#by-ban').innerHTML=ban+(B.tools.pyyaml===false?`<div class="by-note" role="note"><p><b>The design wizard needs the Python package PyYAML</b>, which is not installed here. Install it (<code class="keep">python3 -m pip install pyyaml</code>, or <code class="keep">sudo apt-get install -y python3-yaml</code>) and start the Studio again. The saved results below work without it.</p></div>`:'');q('#by-ex').innerHTML=((r.examples||[]).map(x=>`<div class="by-card"><h4>${e(x.title)}</h4><p><b>What it is:</b> ${e(x.what)}</p><p><b>Why the protection matters:</b> ${e(x.why)}</p><p><b>What it teaches:</b> ${e(x.teaches)}</p><div class="by-row">${(x.runs||[]).map((rr,i)=>{const nd=(rr.needs||[]);const canLive=live&&!nd.length;if(!canLive&&!rr.saved)return '';
   return `<button class="btn${i===0?' primary':''}" data-ex="${e(x.id)}" data-task="${e(rr.task||'')}" data-file="${e(rr.file||'glitchsat.yaml')}" data-live="${canLive?1:0}"${nd.length?` title="${e(nd.join('; '))}"`:''}>${e(canLive?rr.label:runShow(rr.label))}${canLive?'':' (saved result)'}</button>`}).join('')}</div>${live&&(x.runs||[]).some(rr=>(rr.needs||[]).length)?`<p class="hint by-needs">Shown from saved results here: this example ${e([...new Set((x.runs||[]).flatMap(rr=>rr.needs||[]))].join('; it '))}.</p>`:''}</div>`).join('')||'No examples found.');
  qa('#by-ex [data-ex]').forEach(b=>b.onclick=()=>{const x=(r.examples||[]).find(y=>y.id===b.dataset.ex);if(b.dataset.live==='1')startRun({example:x.id,file:b.dataset.file,task:b.dataset.task},x);else showSaved(x,b.dataset.file,b.dataset.task)});
  if(!live){q('#by-go').disabled=true;q('#by-yo').disabled=true;q('#by-bl').innerHTML='<p class="hint">Your own design needs the build tool (<span class="keep">Yosys</span>), which is not installed here.</p>'}});
 q('#by-br').onclick=()=>doBrowse(q('#by-path').value||'~');
 q('#by-go').onclick=()=>openFolder(q('#by-path').value);
 q('#by-yo').onclick=()=>post('/api/byod/read',{path:q('#by-yp').value}).then(r=>{if(r.error){q('#by-ye').innerHTML=err(r);return}showPlan(r)})}
function showPlan(r){const pl=r.plan||{};const ye=q('#by-ye');
 ye.innerHTML=`<div class="panel" style="margin-top:8px"><div class="pb"><p class="by-big">Check before running: <code>${e(pl.name||'')}</code></p>
 <p>A project file can name build commands and files. This is everything it would do on this computer. Run it only if you trust where the file came from.</p>
 ${pl.custom?'<p><b>This project runs its own Yosys commands (flow <code>custom</code>).</b> Each was checked against the list of allowed synthesis commands.</p>':''}
 <p>Design files read: ${(pl.files||[]).map(f=>'<code>'+e(f)+'</code>').join(', ')}</p>
 ${Object.entries(pl.flows||{}).map(([f,c])=>`<details class="more"${pl.custom?' open':''}><summary>Build <code>${e(f)}</code>: ${c.length} Yosys commands</summary><pre class="keep">${e(c.join('\n'))}</pre></details>`).join('')}
 ${(r.tasks||[]).length?`<div class="by-row">Variant: <select id="by-task"><option value="">(the file as it is)</option>${r.tasks.map(t=>`<option>${e(t)}</option>`).join('')}</select></div>`:''}
 <div class="by-row"><button class="btn" id="by-cn">Cancel</button><button class="btn primary" id="by-ok">I checked these commands: run it</button></div></div></div>`;
 ye.scrollIntoView({block:'start'});q('#by-cn').onclick=()=>{ye.innerHTML=''};q('#by-ok').onclick=()=>startRun({path:r.path,task:(q('#by-task')||{}).value||'',confirm:r.nonce},null)}
function showSaved(x,file,task){B.step='run';B.ex=x;B.task=task;B.job=null;const root=el();
 root.innerHTML=`<h2 class="vt">${e(x.title)}${task?' <span class="by-pill">'+e(task)+'</span>':''}</h2><div id="by-res"><div class="empty"><b>Loading the saved result…</b></div></div><div class="by-row"><button class="btn" id="by-home">Back to the start</button></div>`;
 q('#by-home').onclick=()=>{B.step='home';draw()};
 get('/api/byod/saved?ex='+encodeURIComponent(x.id)+'&file='+encodeURIComponent(file)+'&task='+encodeURIComponent(task||'')).then(r=>{
  if(r.error){q('#by-res').innerHTML=err(r);return}B.rep=r.report;q('#by-res').innerHTML=`<p class="hint">Saved result of <code class="keep">glitchsat run</code>, file from ${e(r.when||'')}.</p>`+results(r.report,r.plain,'recorded')})}
function doBrowse(p){post('/api/byod/browse',{path:p}).then(r=>{const bl=q('#by-bl');if(r.error){bl.innerHTML=err(r);return}B.browse=r;q('#by-path').value=r.path;
 bl.innerHTML=`<p class="hint">Folders inside <code>${e(r.path)}</code>:</p><div class="by-list">${r.parent?`<button data-d="${e(r.parent)}">⬑ up</button>`:''}${r.items.map(i=>i.kind==='dir'?`<button data-d="${e(r.path+'/'+i.name)}">📁 ${e(i.name)}</button>`:`<button disabled>${e(i.name)}</button>`).join('')}</div>${r.has_yaml?'<p class="hint">This folder already has a glitchsat.yaml (use box 3 to run it).</p>':''}`;
 qa('#by-bl [data-d]').forEach(b=>b.onclick=()=>doBrowse(b.dataset.d));bl.scrollIntoView({block:'nearest'})})}
function openFolder(p,top){B.step='w1';B.folder=p;const root=el();root.innerHTML=steps(0)+'<div class="empty"><b>Reading your design…</b><p>Yosys elaborates it; this takes a few seconds.</p></div>';
 post('/api/byod/open',{folder:p,top:top||null}).then(r=>{if(r.error){root.innerHTML=steps(0)+(r.candidates&&r.candidates.length?`<div class="panel"><div class="pb"><p class="by-big">Which module is your chip?</p><p>Several modules are not used inside any other module. Pick the one at the top of your design:</p><div class="by-row">${r.candidates.map(c=>`<button class="btn" data-top="${e(c)}">${e(c)}</button>`).join('')}</div></div></div>`:err(r))+'<button class="btn" id="by-back">Back</button>';q('#by-back').onclick=()=>{B.step='home';draw()};qa('[data-top]').forEach(b=>b.onclick=()=>openFolder(p,b.dataset.top));return}
  B.det=r;const ins=r.inputs.filter(x=>x!==r.clock&&!(r.reset&&x===r.reset.port));
  B.ans={name:r.top,sources:r.sources,top:r.top,clock:r.clock,reset:r.reset,attacker:ins.filter(x=>!r.test_inputs.includes(x)),secret:[],
   fixed:Object.fromEntries(r.test_inputs.filter(x=>ins.includes(x)).map(x=>[x,0])),evidence:r.evidence,template:null,params_t:{},must_hold:'',horizon:20,max_faults:3};draw()})}
function w1(root){const d=B.det;root.innerHTML=steps(0)+`<div class="panel"><div class="pb"><p class="by-big">Your design is <code>${e(d.top)}</code>, with ${d.flops} flip-flop(s).</p>
 <p>Files: ${d.sources.map(s=>'<code>'+e(s)+'</code>').join(', ')}</p><p>Inputs: ${d.inputs.map(s=>'<code>'+e(s)+'</code>').join(' ')}<br>Outputs: ${d.outputs.map(s=>'<code>'+e(s)+'</code>').join(' ')}</p>
 <div class="by-row"><button class="btn" id="b0">Back</button><button class="btn primary" id="b1">Next</button></div></div></div>`;
 q('#b0').onclick=()=>{B.step='home';draw()};q('#b1').onclick=()=>{B.step='w2';draw()}}
function w2(root){const d=B.det,a=B.ans;root.innerHTML=steps(1)+`<div class="panel"><div class="pb"><p>A chip moves in steps, one per tick of its <b>clock</b>. The <b>reset</b> puts it into a known starting state. This is what was found:</p>
 ${d.evidence.map(x=>`<div class="by-ev">• ${e(x)}</div>`).join('')}
 <div class="by-row">Clock: <select id="ck">${['none'].concat(d.inputs).map(x=>`<option ${x===(a.clock||'none')?'selected':''}>${e(x)}</option>`).join('')}</select>
 Reset: <select id="rs">${['none'].concat(d.inputs).map(x=>`<option ${x===((a.reset||{}).port||'none')?'selected':''}>${e(x)}</option>`).join('')}</select>
 resets when <select id="ra"><option value="low" ${(a.reset||{}).active==='low'?'selected':''}>low (0)</option><option value="high" ${(a.reset||{}).active==='high'?'selected':''}>high (1)</option></select></div>
 <div class="by-row"><button class="btn" id="b0">Back</button><button class="btn primary" id="b1">Next</button></div></div></div>`;
 q('#b0').onclick=()=>{B.step='w1';draw()};q('#b1').onclick=()=>{a.clock=q('#ck').value==='none'?null:q('#ck').value;const r=q('#rs').value;a.reset=r==='none'?null:{port:r,active:q('#ra').value};B.step='w3';draw()}}
function w3(root){const d=B.det,a=B.ans;const ins=d.inputs.filter(x=>x!==a.clock&&!(a.reset&&x===a.reset.port));
 const role=x=>a.secret.includes(x)?'secret':(x in a.fixed)?'fixed':'attacker';
 root.innerHTML=steps(2)+`<div class="panel"><div class="pb"><p><b>Which inputs can the attacker change?</b> An attacker can usually drive the pins of the chip, but not its secret key. Inputs you tie to a fixed value (for example a test-mode pin) stay at that value.</p>
 <table class="by-t"><tr><th>input</th><th>width</th><th>who controls it</th><th>value if fixed</th></tr>${ins.map(x=>`<tr><td><code>${e(x)}</code></td><td>${d.ports[x][1]}</td><td><select data-r="${e(x)}"><option value="attacker" ${role(x)==='attacker'?'selected':''}>the attacker (any value, every cycle)</option><option value="secret" ${role(x)==='secret'?'selected':''}>a secret (unknown, constant)</option><option value="fixed" ${role(x)==='fixed'?'selected':''}>fixed</option></select></td><td><input type="text" data-v="${e(x)}" value="${e(a.fixed[x]??0)}" size="8"></td></tr>`).join('')}</table>
 ${d.secrets.length?`<p class="hint">These look like a secret by their name: ${d.secrets.map(x=>'<code>'+e(x)+'</code>').join(', ')}. They are not ticked. Choose "a secret" only if the attacker really cannot drive the input: a secret is held at one unknown value, and the result then shows which key value the attack needs.</p>`:''}
 <div class="by-row"><button class="btn" id="b0">Back</button><button class="btn primary" id="b1">Next</button></div></div></div>`;
 q('#b0').onclick=()=>{B.step='w2';draw()};q('#b1').onclick=()=>{a.attacker=[];a.secret=[];a.fixed={};qa('[data-r]').forEach(s=>{const x=s.dataset.r;if(s.value==='attacker')a.attacker.push(x);else if(s.value==='secret')a.secret.push(x);else a.fixed[x]=q(`[data-v="${CSSE(x)}"]`).value||0});B.step='w4';draw()}}
function w4(root){const d=B.det,a=B.ans;get('/api/byod/templates').then(r=>{const T0=r.templates||[];
 root.innerHTML=steps(3)+`<div class="panel"><div class="pb"><p><b>What must never happen?</b> Pick the sentence closest to your design. You can change the details next.</p>
 <div class="by-cards">${T0.map(t=>`<button class="by-card" data-t="${e(t.id)}" style="text-align:left;cursor:pointer${a.template===t.id?';border-color:var(--acc)':''}"><h4>${e(t.plain)}</h4><p class="hint">${e(t.id)}</p></button>`).join('')}</div>
 <div id="tp"></div><div class="by-row"><button class="btn" id="b0">Back</button><button class="btn primary" id="b1" ${a.template?'':'disabled'}>Next</button></div></div></div>`;
 const fill=()=>{const t=T0.find(x=>x.id===a.template);if(!t){q('#tp').innerHTML='';return}
  post('/api/byod/prefill',{template:t.id,inputs:d.inputs,outputs:d.outputs,ports:d.ports,clock:a.clock,reset:a.reset&&a.reset.port}).then(pf=>{
  const P0=(pf&&pf.params)||t.params;const keys=t.id==='custom'?['bad']:Object.keys(P0);if(t.id==='custom'&&!a.bad)a.bad=d.outputs[0]?d.outputs[0]+' != 0':'';
  const mh=a.must_hold||'';
  q('#tp').innerHTML=`<div class="panel" style="margin-top:10px"><div class="pb"><p>Fill in the names from your design (ports: ${d.inputs.concat(d.outputs).map(x=>'<code>'+e(x)+'</code>').join(' ')}). Conditions are Verilog expressions, for example <code>${e(d.outputs[0]||'out')} == 1</code>.</p>
  ${keys.map(k=>`<div class="by-row"><label style="min-width:120px">${e(k)}</label><input type="text" data-p="${e(k)}" value="${e(t.id==='custom'?a.bad:(a.params_t[k]??P0[k]??''))}"></div>`).join('')}
  <p style="margin-top:12px"><b>What may a legitimate user do that is allowed?</b> Without this, the right code (or the normal unlock) is itself counted as an attack, and the answer is "it happens without any glitch". For a lock: the right code is never typed.</p>
  <div class="by-row"><label style="min-width:120px">must hold</label><input type="text" id="by-mh" value="${e(mh)}" placeholder="${e(pf&&pf.must_hold||"!(code_i == 8'hA5)")}"></div>
  <p class="hint"><span class="plain-only">Leave it empty if nothing is allowed.</span><span class="tech-only">This is an assumption on the inputs in every cycle up to the success, like an <code>assume</code> in formal verification (<code>checks[].must_hold</code>).</span></p>
  <details class="more learn"><summary>Learn more: the same in glitchsat.yaml</summary><pre>${e(t.snippet)}</pre></details></div></div>`})};
 qa('[data-t]').forEach(b=>b.onclick=()=>{a.template=b.dataset.t;a.params_t={};qa('[data-t]').forEach(x=>x.style.borderColor=x===b?'var(--acc)':'');q('#b1').disabled=false;fill()});fill();
 q('#b0').onclick=()=>{B.step='w3';draw()};q('#b1').onclick=()=>{qa('[data-p]').forEach(i=>{if(a.template==='custom')a.bad=i.value;else a.params_t[i.dataset.p]=i.value});const m=q('#by-mh');a.must_hold=m?m.value.trim():'';B.step='w5';draw()}})}
function answers(){const a=Object.assign({},B.ans);a.must_hold=a.must_hold?[a.must_hold]:[];return a}
function w5(root){const a=B.ans;post('/api/byod/write',{folder:B.det.folder,answers:answers(),dry:true}).then(r=>{
 root.innerHTML=steps(4)+`<div class="panel"><div class="pb"><p><b>How hard should GlitchSAT look?</b></p>
 <div class="by-row">Look at the first <input type="text" id="hz" value="${a.horizon}" size="4"> clock cycles after reset, and try up to <input type="text" id="mf" value="${a.max_faults}" size="3"> glitches.</div>
 <p class="hint">20 cycles and 3 glitches are good first values. A glitch here flips one wire for one cycle.</p>
 <details class="more learn"><summary>Learn more: the project file that will be saved (glitchsat.yaml)</summary><pre id="yy">${e(r.text||'')}</pre></details>
 <div id="we"></div><div class="by-row"><button class="btn" id="b0">Back</button><button class="btn primary" id="b1">Save and find the cheapest attack</button></div></div></div>`;
 q('#b0').onclick=()=>{B.step='w4';draw()};
 q('#b1').onclick=(ev,over)=>{a.horizon=+q('#hz').value||20;a.max_faults=+q('#mf').value||3;const save=ow=>post('/api/byod/write',{folder:B.det.folder,answers:answers(),overwrite:ow}).then(w=>{
   if(w.exists){q('#we').innerHTML=`<div class="err"><b>${e(w.error)}</b><p>Replace it with these answers?</p><button class="btn" id="ow">Replace</button></div>`;q('#ow').onclick=()=>save(true);return}
   if(w.error){q('#we').innerHTML=err(w);return}startRun({path:w.path,task:'',confirm:w.nonce},null)});save(false)}})}
function startRun(req,ex){B.step='run';B.rep=null;B.ex=ex;B.task=req.task||'';const root=el();root.innerHTML='<div class="empty"><b>Starting…</b></div>';
 post('/api/byod/run',req).then(r=>{if(r.error){root.innerHTML=`<h2 class="vt">Could not start</h2>`+err(r)+'<div class="by-row"><button class="btn" id="by-home">Back to the start</button></div>';q('#by-home').onclick=()=>{B.step='home';draw()};return}B.job=r.id;draw()})}
function run(root){
 root.innerHTML=`<h2 class="vt">${e(B.ex?B.ex.title:'Your design')}${B.task?' <span class="by-pill">'+e(B.task)+'</span>':''}</h2><div id="by-prog"></div><div id="by-res"></div><div class="by-row"><button class="btn" id="by-home">Back to the start</button><button class="btn" id="by-stop">Stop</button></div>`;
 q('#by-home').onclick=()=>{B.step='home';draw()};q('#by-stop').onclick=()=>post('/api/byod/stop',{id:B.job});
 const poll=()=>get('/api/byod/job?id='+B.job).then(j=>{if(B.step!=='run')return;const pr=q('#by-prog');if(!pr)return;
  const head=j.status==='running'?'Working…':j.status==='done'?'Finished':j.status==='stopped'?'Stopped':'Could not finish';
  const log=`<div class="by-log">${(j.lines||[]).map(l=>`${l.t.toFixed(1)} s · ${e(plainMsg(l.msg))}`).join('<br>')||'starting…'}</div>`;
  pr.innerHTML=`<div class="panel"><div class="ph"><h4>${head}</h4></div><div class="pb">${j.status==='running'||TECH()?log:`<details class="more"><summary>Details: what was done (${(j.lines||[]).length} steps)</summary>${log}</details>`}</div></div>`;
  if(j.status==='running'){setTimeout(poll,700);return}const sb=q('#by-stop');if(sb)sb.remove();
  if(j.report){B.rep=j.report;q('#by-res').innerHTML=results(j.report,j.plain)}else{const m=(j.err||'').match(/error\[(GS\d+)\]: (.*)/);const help=(j.err||'').match(/= help: (.*)/);
   q('#by-res').innerHTML=err({error:m?m[2]:'The analysis stopped.',help:help?help[1]:null,code:m?m[1]:null,note:j.err})}});poll()}
const FW={flip:'flipped (0 and 1 swapped)',set:'forced to 1',reset:'forced to 0'};
function wave(w,c){const tr=w.trace||[];if(!tr.length)return '';const keys=Object.keys(tr[0]).filter(k=>!['cycle','faults'].includes(k));const N=tr.length,cw=56,x0=150,h=20;
 let s=`<svg class="by-wave keep" width="${x0+N*cw+10}" height="${(keys.length+2)*h+10}" role="img" aria-label="Signal values per clock cycle during the attack">`;
 s+=tr.map((r,i)=>`<text x="${x0+i*cw+4}" y="14">cycle ${r.cycle}</text>`).join('');
 keys.forEach((k,j)=>{const y=(j+1)*h+14;s+=`<text x="4" y="${y}">${e(k==='bad'?'must-never-happen':k==='ok'?'must-hold OK':k.startsWith('in:')?k.slice(3)+' (input)':k)}</text>`+tr.map((r,i)=>`<text x="${x0+i*cw+4}" y="${y}" ${k==='bad'&&r[k]?'class="f"':''}>${e(k.startsWith('in:')&&r[k]>1?'0x'+r[k].toString(16).toUpperCase():r[k])}</text>`).join('')});
 const yF=(keys.length+1)*h+14;s+=`<text x="4" y="${yF}">glitches</text>`+tr.map((r,i)=>r.faults.length?`<text class="f" x="${x0+i*cw+4}" y="${yF}">⚡ ${r.faults.length}</text>`:'').join('');
 return s+'</svg>'}
const ALLOWED_TAGS=new Set(['live','recorded']);
function results(rep,plain,tag){let o='';tag=ALLOWED_TAGS.has(tag)?tag:'live';
 if((rep.plain_findings||[]).length&&typeof Studio!=='undefined'&&Studio.findings)o+=Studio.findings.html(rep.plain_findings);   /* plain words first */
 const fls=rep.flows||{};const bbo=[...new Set(Object.values(fls).flatMap(f=>(f.blackbox_outputs||[]).map(b=>b.cell+'.'+b.pin)))];
 if(bbo.length)o+=`<div class="panel" role="note"><div class="pb"><p><b>Part of this design is a black box</b> (no source was given). Its outputs (${bbo.map(x=>'<code>'+e(x)+'</code>').join(', ')}) can take any value in every step here, and nothing inside it is analysed. The answers below cover the logic around it only.</p></div></div>`;
 const scan=Object.entries(fls).filter(([f,x])=>(x.scan_enable_attacker||[]).length);
 if(scan.length)o+=`<div class="panel" role="note"><div class="pb"><p><b>Risk:</b> the test (scan) switch of ${scan[0][1].scan_flops} memory cell(s) is driven by the attacker input ${scan[0][1].scan_enable_attacker.map(x=>'<code>'+e(x)+'</code>').join(', ')}. If that is a test pin, tie it to 0.</p></div></div>`;
 for(const c of rep.checks){if(c.status==='NOT_RUN'){o+=`<div class="panel"><div class="pb">Check <code>${e(c.id)}</code>: not run (${e(c.why)})</div></div>`;continue}
  const A=c.analyses,mf=A.min_faults||{},v=mf.verdict;
  let big,cls;if(v==='ATTACK_FOUND'){big=`${mf.min_faults} glitch${mf.min_faults===1?' is':'es are'} enough.`;cls='bad'}else if(v==='NO_ATTACK_UP_TO_BOUND'){big=`No attack with up to ${c.max_faults} glitches.`;cls='good'}else if(v==='FAILS_WITHOUT_FAULTS'){big='It happens even without any glitch.';cls='bad'}else{big='Not decided: '+(mf.why||v);cls=''}
  const sv0=(A.survival||{}).rows||[];const fnd=sv0.filter(r=>r.min_faults!=null);const weakest=fnd.length?fnd.reduce((x,y)=>y.min_faults<x.min_faults?y:x):null;
  const mixed=weakest&&sv0.length>1&&(v==='NO_ATTACK_UP_TO_BOUND'||(mf.min_faults!=null&&weakest.min_faults<mf.min_faults));
  const gl=n=>n+' glitch'+(n===1?'':'es');
  if(mixed){big=`Main build (${sv0[0].flow}): ${v==='NO_ATTACK_UP_TO_BOUND'?'no attack with up to '+gl(c.max_faults):gl(mf.min_faults)+' needed'}. Weakest build (${weakest.flow}): ${gl(weakest.min_faults)}.`;cls='bad'}
  const pill=v==='FAILS_WITHOUT_FAULTS'||(v==='ATTACK_FOUND'&&mf.min_faults<=1)||mixed&&weakest.min_faults<=1?'weak':v==='ATTACK_FOUND'?'harder':v==='NO_ATTACK_UP_TO_BOUND'?'held':'open';
  if(v==='ATTACK_FOUND'&&mf.min_faults>1&&!mixed)cls='';
  o+=`<div class="panel"><div class="ph"><h4>${e(c.explain||c.id)}</h4> ${HONK(tag)}</div><div class="pb"><p class="by-big"><span class="by-pill ${cls}">${pill}</span> ${e(big)}</p>
   <p class="hint">Within ${c.horizon} clock cycles after reset. ${v==='NO_ATTACK_UP_TO_BOUND'?'This is a bounded answer: it says nothing about more glitches or more cycles, unless a proof is shown below.':v==='FAILS_WITHOUT_FAULTS'?'The design does this by itself: either a bug, or the condition also covers a legitimate case (for example the right code being typed). Add a must-hold condition that rules the legitimate case out.':mf.proved_minimum?'The smallest number is proved: no attack with fewer glitches exists in that time.':''}</p>`;
  const w=mf.witness;if(w){o+=`<h4>${w.faults.length?'How the cheapest attack works':'How it happens without any glitch'}</h4><ol>${w.faults.map(f=>`<li>In cycle ${f.cycle}, ${siteName(f.site)} is ${e(FW[f.type]||f.type)}${f.src?` <span class="hint">(written in <code>${e(f.src)}</code>)</span>`:''}.</li>`).join('')}${Object.entries(w.free||{}).map(([p,vals])=>`<li>The black-box output <code>${e(p)}</code> takes <code class="keep">${e(vals.join(', '))}</code> (it is free here).</li>`).join('')}${Object.entries(w.inputs).map(([p,iv])=>`<li>The attacker sets <code>${e(p)}</code> to <code class="keep">${e(iv.values.join(', '))}</code>${iv.values.length>1?' (cycle 0, 1, 2, …)':''}.</li>`).join('')}<li>In cycle ${w.hit_cycle} the must-never-happen condition is true${w.replayed?' (checked again on a separate gate-level simulator)':''}${w.shortest?'; no attack with this many glitches succeeds earlier':''}.</li></ol><div style="overflow:auto">${wave(w,c)}</div>`}
  const u=A.unbounded||{};if(u.verdict&&u.verdict!=='NOT_RUN')o+=`<h4>Does it hold for any waiting time?</h4><p>${u.verdict==='PROVED_UNBOUNDED'?HONK('proved')+'</p><p>'+e(u.k===0?'Without any glitch it never happens, however long the chip runs.':`With up to ${u.k} glitch(es) it can never happen, however long the chip runs.`):u.verdict==='ATTACK_FOUND'?e(u.meaning):'Not decided ('+e(u.why||u.verdict)+').'}</p>`;
  const sv=A.survival;if(sv)o+=`<h4>Did the protection survive the build?</h4><p class="hint">The same design built in different ways (synthesis flows). A build can merge copies of a check and make the chip weaker.</p><table class="by-t"><tr><th>build</th><th>glitches needed</th><th></th></tr>${sv.rows.map(r=>`<tr><td>${e(r.flow)}</td><td>${r.min_faults!=null?r.min_faults:r.verdict==='NO_ATTACK_UP_TO_BOUND'?'more than '+c.max_faults:e(r.verdict)}</td><td>${e(r.change&&r.change!=='same'?r.change:'')}</td></tr>`).join('')}</table>`;
  const VW={SURVIVED:'still there',REMOVED:'not there',WEAKENED:'partly merged',UNTRACKED:'not followed'};
  const ml=A.merge_lint;if(ml&&ml.countermeasures&&ml.countermeasures.length){const cmv=ml.countermeasures.map(cm=>Object.assign({},cm,{stages:cm.stages.filter(s=>TECH()||String(s.verdict).trim()!=='UNTRACKED')})).filter(cm=>cm.stages.length);
   if(cmv.length)o+=`<h4>Protections found in the source, and what each build kept</h4><table class="by-t">${cmv.map(cm=>`<tr><td>${e(cm.title)}</td>${cm.stages.map(s=>{const vv=String(s.verdict).trim();return `<td>${e(s.stage)}: <b>${e(TECH()?vv:(VW[vv]||vv.toLowerCase()))}</b></td>`}).join('')}</tr>`).join('')}</table>${TECH()&&cmv.some(cm=>cm.stages.some(s=>String(s.verdict).trim()==='UNTRACKED'))?'<p class="hint">UNTRACKED: could not be followed through that build, so nothing is said about it.</p>':''}`}
  const s=A.attack_surface||{};if(s.count)o+=`<h4>Weak spots</h4><p>${s.count} cheapest attack(s)${s.complete?'':' (list stopped: '+e(s.stop_reason)+')'}. The parts they use most:</p><table class="by-t">${s.sites.slice(0,8).map(([k,n])=>`<tr><td>${siteName(k)}</td><td>${n}</td></tr>`).join('')}</table>`;
  const todo=c.what_to_do||[];if(todo.length)o+=`<h4>What to do</h4><ul>${todo.map(t=>`<li>${e(t.text)}</li>`).join('')}</ul>`;
  const va=Object.entries(c.flows).map(([f,x])=>x.validation&&x.validation.runs?`${e(f)}: ${x.validation.runs} random runs × ${x.validation.cycles} cycles`:'').filter(Boolean);
  if(va.length)o+=`<p class="hint">Checked: the circuit GlitchSAT analysed behaved like ${rep.frontend==='netlist'?'the build tool\'s own reading of the same cells':'your design as written'} without glitches (${va.join('; ')}). This check runs without glitches, so parts that only act after a glitch (alarms, extra copies) are not covered by it.</p>`;
  o+='</div></div>'}
 if(B.ex&&B.ex.lesson_after)o+=`<div class="panel"><div class="ph"><h4>What this teaches</h4></div><div class="pb"><p>${e(B.ex.lesson_after)}</p></div></div>`;
 o+=`<details class="more learn"><summary>Learn more (technical details): the full report</summary><pre>${e(plain||'')}</pre><p class="hint">Saved next to the project file in .glitchsat/. Faults are modelled (a wire flipped for one clock cycle), not measured on a chip.</p></details>`;
 return o}
Studio.registerView({id:'mine',title:'Open my design',tip:'Analyse an example or your own Verilog design: five plain questions, then the cheapest glitch attack',show:x=>draw(x)});
})();
'''
