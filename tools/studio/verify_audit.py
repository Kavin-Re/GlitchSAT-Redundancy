"""Checks for the fixes of the multi-angle audit (AUDIT_FIXES.md): Playwright/Chromium, recorded mode, own port.
Screens go to shots_audit/. Usage: python3 verify_audit.py"""
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', '/opt/pw-browsers')
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'shots_audit') + '/'
ROOT = os.environ.get('GLITCHSAT_ROOT') or os.path.normpath(os.path.join(HERE, '..', '..'))
EXT = os.environ.get('GLITCHSAT_EXT') or os.path.dirname(HERE)
PORT = 8887
URL = f'http://127.0.0.1:{PORT}/'
os.makedirs(OUT, exist_ok=True)
errs, checks = [], []


def check(name, ok, detail=''):
    checks.append((name, bool(ok), str(detail)[:300]))
    print(('  ok   ' if ok else '  FAIL ') + name + ('' if ok else ' : ' + str(detail)[:300]))


def wording():
    spec = importlib.util.spec_from_file_location('check_wording', os.path.join(EXT, 'check_wording.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def withheld_ids(text):
    """Identifiers withheld pending responsible disclosure (hashed list of the shared check), found in text."""
    return [k for _, k in wording().scan_text(text) if k.startswith('disclose:')]


def get(path, port=PORT, headers=None):
    rq = urllib.request.Request(f'http://127.0.0.1:{port}{path}', headers=headers or {})
    try:
        with urllib.request.urlopen(rq, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def post(path, body, port=PORT):
    rq = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=json.dumps(body).encode(),
                                headers={'X-GlitchSAT': '1', 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(rq, timeout=20) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def start(port, root, log):
    env = dict(os.environ, GLITCHSAT_ROOT=root, XDG_CACHE_HOME=tempfile.mkdtemp(prefix='gsacache-'))
    p = subprocess.Popen([sys.executable, os.path.join(HERE, 'studio.py'), '--no-browser', '--port', str(port), '--no-autostop'],
                         env=env, stdout=open(log, 'w'), stderr=subprocess.STDOUT)
    for _ in range(60):
        try:
            get('/api/status', port)
            break
        except Exception:                      # noqa: BLE001
            time.sleep(0.1)
    return p


def page(b, w, h, theme='dark', view='plain', fresh=True):
    ctx = b.new_context(viewport={'width': w, 'height': h})
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: errs.append(('pageerror', str(e))))
    pg.on('console', lambda m: m.type == 'error' and 'status of 403' not in m.text and errs.append(('console', m.text)))
    pg.add_init_script("try{if(!sessionStorage.getItem('i')){sessionStorage.setItem('i','1');localStorage.clear();localStorage.setItem('gs_theme','\"%s\"');"
                       "localStorage.setItem('gs_view','\"%s\"');localStorage.setItem('gs_seen3','1');localStorage.setItem('gs_seen','1')}}catch(e){}" % (theme, view))
    pg.goto(URL)
    pg.wait_for_timeout(1500)
    return pg


def words(pg, sel):
    return len(pg.evaluate("s=>{const e=document.querySelector(s);return e?e.innerText:''}", sel).split())


def contrast(pg, sel):
    return pg.evaluate("""s=>{const e=document.querySelector(s);if(!e)return null;const p=c=>c.match(/[\\d.]+/g).slice(0,3).map(Number);
     const L=([r,g,b])=>{const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)};return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b)};
     let bg=null,n=e;while(n&&!bg){const c=getComputedStyle(n).backgroundColor;if(c&&!/rgba\\(0, 0, 0, 0\\)|transparent/.test(c))bg=c;n=n.parentElement}
     bg=bg||'rgb(255,255,255)';const a=L(p(getComputedStyle(e).color)),b=L(p(bg));return (Math.max(a,b)+0.05)/(Math.min(a,b)+0.05)}""", sel)


def run():
    # ---- command line: --help and --version print and exit, no server (audit 6-S2)
    t0 = time.time()
    r = subprocess.run([sys.executable, os.path.join(HERE, 'studio.py'), '--help', '--port', str(PORT + 5)], capture_output=True, text=True, timeout=20)
    s5 = socket.socket()
    free = s5.connect_ex(('127.0.0.1', PORT + 5)) != 0
    s5.close()
    check('--help prints usage, exits at once and starts no server', r.returncode == 0 and 'usage:' in r.stdout and time.time() - t0 < 10 and free, r.stdout[:120])
    r = subprocess.run([sys.executable, os.path.join(HERE, 'studio.py'), '--version'], capture_output=True, text=True, timeout=20,
                       env=dict(os.environ, GLITCHSAT_ROOT=ROOT))
    check('--version prints the versions', r.returncode == 0 and 'Studio interface' in r.stdout, r.stdout)

    # ---- no project folder (audit 6-S1)
    empty = tempfile.mkdtemp(prefix='gsa-empty-')
    p2 = start(PORT + 1, empty, '/tmp/gsaudit_empty.log')
    try:
        st = json.loads(get('/api/status', PORT + 1)[1])
        time.sleep(0.3)
        log = open('/tmp/gsaudit_empty.log').read()
        check('not a project folder: status says so and the start-up text warns', st.get('project_found') is False and 'not a GlitchSAT project folder' in log, log[:200])
    finally:
        p2.terminate()

    srv = start(PORT, ROOT, '/tmp/gsaudit.log')
    try:
        c, html = get('/')
        check('page: no absolute developer path or listed word in the served page', not wording().scan_text(html), wording().scan_text(html)[:3])
        st = json.loads(get('/api/status')[1])
        check('status: project found, boot id present', st.get('project_found') is True and st.get('boot'), st.get('boot'))
        check('ping answers with the boot id (a window notices a restart)', json.loads(get('/api/ping?cid=t')[1]).get('boot') == st['boot'])
        c, b = post('/api/analyze', {'design': ['v0']})
        check('analyze with a list as design: "unknown design", not an internal error (audit 4-N3)', c == 400 and 'unknown design' in b, (c, b))
        ch = json.loads(get('/api/chip')[1])
        labs = {g['label'] for c_ in ch.get('chips', []) for v in c_['variants'] for g in v['goals']}
        check('chip data: whole-chip results are BOUNDED, never PROVED (audit 3-S1)', labs == {'BOUNDED'}, labs)
        ib = next((c_ for c_ in ch.get('chips', []) if c_['id'] == 'ibex_demo'), {})
        check('chip data: lockstep caveat (source edits for this study) is in the data', any('source edits' in x for x in ib.get('read_with_care', []))
              and any((v.get('note') or '').find('lowRISC does not ship') >= 0 for v in ib.get('variants', [])))
        check('chip data: Earl Grey summary', (ch.get('next_rung') or {}).get('summary') == 'Read in full; the gate step needs a bigger machine.')
        lb = json.loads(get('/api/labs')[1])
        mc = next((m for m in lb.get('modules', []) if m["id"] == "bootloader"), {})
        txt = json.dumps(mc)
        check('Labs data: bootloader card withholds names and addresses (audit 3-B1)', mc.get('withheld') and 'details withheld pending responsible disclosure' in txt
              and not re.search(r'0x[0-9a-f]{3}|\.c line', txt) and not withheld_ids(txt), txt[:300])
        c, rd = get('/labs/readme/bootloader')
        check('Labs README of the bootloader module: no function names or addresses, limits first', c == 200 and not re.search(r'0x[0-9a-f]{3}|weaknesses of', rd) and not withheld_ids(rd)
              and rd.find('Limits first') < rd.find('WHAT WORKS'))
        c, b = get('/api/byod/examples', headers={'X-GlitchSAT-Token': 'old-session-key'})
        check('plug-in: an old session key gets "the Studio was restarted: reload" (audit 6-S3)', c == 403 and 'STALE_SESSION' in b, (c, b[:100]))

        with sync_playwright() as p:
            b = p.chromium.launch()
            # ---- Start: progressive disclosure (audit 1-S5)
            pg = page(b, 1366, 768)
            n = words(pg, '#v-start')
            check(f'Start: at most 450 words visible ({n}); findings and Explore cards behind "More on this page"', n <= 450 and not pg.evaluate("document.querySelector('#start-more').open"), n)
            pg.screenshot(path=OUT + 'start_1366_dark.png')
            # ---- predict first on steps 1 to 3 by default (audit 1-S2)
            pg.click('#h-try')
            pg.wait_for_timeout(1500)
            check('step 1: asks for a prediction first, result veiled', pg.is_visible('[data-pred="1"]') and pg.evaluate("document.querySelector('#result').classList.contains('veil')"))
            check('step 1: a skip link is there', pg.is_visible('[data-pred="skip"]') and pg.is_visible('[data-pred="never"]'))
            pg.screenshot(path=OUT + 'step1_predict_1366_dark.png')
            pg.click('[data-pred="1"]')
            pg.wait_for_timeout(500)
            check('step 1: after the guess the result shows, with "you predicted"', not pg.evaluate("document.querySelector('#result').classList.contains('veil')") and 'You predicted' in pg.inner_text('#story'))
            check('live region announces the result (audit 5-S3)', 'Result' in pg.inner_text('#sr-live'), pg.inner_text('#sr-live'))
            # ---- plain-words findings on the path (severity first, how we found it)
            fc = pg.evaluate("""(()=>{const c=document.querySelector('#result .findings .fcard');if(!c)return null;const b=c.querySelector('.sev');
              return {sum:document.querySelector('#result .findings .fsum').innerText,badge:b.textContent.replace(/\\s+/g,' ').trim(),first:c.firstElementChild.contains(b),
                details:[...c.querySelectorAll(':scope>details>summary')].map(x=>x.innerText.trim()),steps:c.querySelectorAll('.fsteps li').length,
                trace:!!c.querySelector('.ftrace'),where:c.querySelector('.fhow p').textContent}})()""")
            check('path step 1: a plain-words finding with a summary line at the top', fc and fc['sum'].startswith('1 critical'), fc)
            check('finding: severity first, as a word and an icon (not colour alone)', fc and fc['first'] and fc['badge'] == '!!! Critical', fc and fc['badge'])
            check('finding: why/what to do, how we found it, technical details one click away', fc and fc['details'] == [
                'Why it is rated Critical, and what to do', 'How we found it', 'Show technical details'], fc and fc['details'])
            check('how we found it: six steps, where (with the step), and a before/after trace from the replay', fc and fc['steps'] == 6
                  and fc['trace'] and 'step' in fc['where'], fc)
            pg.click('#result .findings [data-sevrules]') if pg.evaluate("!!document.querySelector('#result .findings details[open] [data-sevrules]')") else pg.evaluate("sevRules()")
            pg.wait_for_timeout(1200)
            mt = pg.evaluate("document.querySelector('#modal').textContent")
            check('"How we decide severity" shows the one rule table', 'Fewest glitches needed' in mt, mt[:200])
            pg.evaluate("closeDlg()")
            n1 = pg.evaluate("S.last.min_faults")
            pg.evaluate("document.querySelector('#result .findings .fhow').open=true")
            pg.click('#result .findings [data-ftry]')
            pg.wait_for_timeout(1500)
            if pg.is_visible('[data-pred="1"]'):
                pg.click('[data-pred="1"]')
                pg.wait_for_timeout(400)
            check('"Replay this step" reproduces the same result', pg.evaluate("S.last.min_faults") == n1, n1)
            # ---- See how (audit 1-S1)
            n = words(pg, '#v-analyze')
            check(f'step 1: under 360 words visible ({n}, of which about 100 are the plain-words finding); replay, table and map behind "See how"', n < 360 and pg.evaluate("!document.querySelector('#seehow').open"), n)
            pg.evaluate("document.querySelector('#seehow').open=true")
            pg.wait_for_timeout(400)
            check('"See how" opens and draws the replay and map', pg.evaluate("document.querySelectorAll('#wavebox svg, #mapbox svg').length") >= 1)
            pg.evaluate("loadStep(1)")
            pg.wait_for_timeout(1500)
            check('step 2: still asks first; skip shows the result', pg.is_visible('[data-pred="skip"]'))
            pg.click('[data-pred="skip"]')
            pg.wait_for_timeout(400)
            check('"See how" stays open once the learner has opened it', pg.evaluate("document.querySelector('#seehow').open"))
            pg.evaluate("loadStep(3)")
            pg.wait_for_timeout(1500)
            n = words(pg, '#v-analyze')
            check('step 4: no prediction asked by default', not pg.is_visible('[data-pred="1"]'))
            pg.evaluate("loadStep(2)")
            pg.wait_for_timeout(1200)
            pg.click('[data-pred="never"]')
            pg.wait_for_timeout(300)
            check('"stop asking" turns it off (kept on this computer)', pg.evaluate("localStorage.getItem('gs_predict')") == 'false')
            # ---- Plain-view phrase bugs (audit 1-S4)
            ph = pg.evaluate("[plainText('GlitchSAT needs the free chip build tool Yosys to read a design.'),plainText('No Verilog source is needed: only the cell netlist and the cell library.')]")
            check('Plain words: no "build tool the build tool", no "cell chip plan"', not any(re.search(r'build tool the build tool|cell chip plan', x) for x in ph), ph)
            # ---- lesson screen 9: real links (audit 1-S3)
            pg.evaluate("show('learn');LearnView.goTo(8)")
            pg.wait_for_timeout(600)
            gos = pg.evaluate("[...document.querySelectorAll('#v-learn .lz-how [data-go]')].map(b=>[b.dataset.go,b.textContent.trim()])")
            titles = pg.evaluate("Object.fromEntries(EXPLORE.map(v=>[v.id,v.title]))")
            ok = len(gos) >= 7 and all(t == titles.get(g, t if g == 'p0' else None) for g, t in gos)
            check('lesson screen 9: every page name is a link with the name the app uses', ok, gos)
            pg.click('#v-learn .lz-how [data-go="x-spots"]')
            pg.wait_for_timeout(600)
            check('lesson link opens that Explore page', pg.evaluate("[S.tab,S.xv]") == ['explore', 'x-spots'])
            # ---- Explore a real chip (audit 2-B2, 3-S1, 3-S2)
            pg.evaluate("openExplore('x-chip')")
            pg.wait_for_timeout(1200)
            t = pg.inner_text('#xbody')
            chips_ = pg.evaluate("[...document.querySelectorAll('#xbody .chip')].map(c=>c.textContent.trim().toLowerCase())")
            check('Explore lists "Explore a real chip"', 'Explore a real chip' in pg.inner_text('#xnav'))
            check('chip page: what the chip is, where its decisions live, what was found', all(x in t for x in ('What this chip is', 'Where its security decisions live', 'What was found')))
            check('chip page: results labelled bounded, "proved" only in the sentence that explains why not', chips_.count('bounded') >= 3 and chips_.count('proved') <= 1, chips_)
            check('chip page (PicoSoC): same design, three builds, 3, 2, 1', '3, 2, 1 glitches' in t, t[:200])
            fs = pg.evaluate("[...document.querySelectorAll('#xbody .fcard .sev')].map(b=>b.textContent.replace(/\\s+/g,' ').trim())")
            check('chip page: plain-words findings with severities (a 1-glitch start bypass is Critical)', fs and fs[0] == '!!! Critical', fs)
            pa = pg.evaluate("JSON.stringify(S.chip.chips.map(c=>(c.findings||[]).map(f=>(f.patterns.find(p=>p.tag==='(a)')||{}).status)))")
            st_ = [x for c_ in json.loads(pa) for x in c_ if x]
            ys_ = [x for x in st_ if x.startswith('yes')]
            check('chip page: pattern (a) "yes" only where the chip inventory names a protection that survived as written and is missing after a build (review 2 B-3, review 3 S-9)',
                  ys_ and all('SURVIVED as written' in x and ('REMOVED' in x or 'WEAKENED' in x) for x in ys_)
                  and not [x for x in st_ if x.startswith('maybe') and 'inventory' not in x], pa[:300])
            check('chip page: Earl Grey "read in full, gate step needs a bigger machine"', 'Read in full, gate step needs a bigger machine' in t)
            pg.screenshot(path=OUT + 'chip_picosoc_1366_dark.png', full_page=True)
            pg.click('#chipsel [data-v="ibex_demo"]')
            pg.wait_for_timeout(600)
            t = pg.inner_text('#xbody')
            check('chip page (Ibex): the lockstep caveat sits next to the lockstep rows', 'configured by editing the source for this study' in t and 'lowRISC does not ship' in t)
            pg.screenshot(path=OUT + 'chip_ibex_1366_dark.png', full_page=True)
            pg.evaluate("document.documentElement.dataset.view='plain'")
            pg.evaluate("openExplore('x-fw')")
            pg.wait_for_timeout(2000)
            check('boot program page: a plain-words finding for the chosen version', pg.evaluate("document.querySelectorAll('#xbody .fcard').length") >= 1)
            pg.evaluate("openExplore('x-gal')")
            pg.wait_for_timeout(1500)
            check('example gallery: a plain-words finding per saved run', pg.evaluate("document.querySelectorAll('#xbody .fcard').length") >= 4)
            # ---- Labs: in More at every width, ISO dates, withheld card (audit 1-N1, 1-N3, 3-B1)
            check('Labs is not a top-level tab at 1366; it is in More', not pg.is_visible('#tabs .tab[data-v=labs]') and pg.is_visible('#tab-more'))
            pg.click('#tab-more')
            pg.wait_for_timeout(200)
            items = pg.evaluate("[...document.querySelectorAll('#tmenu [data-v]')].map(b=>b.dataset.v)")
            check('More menu at 1366 lists Labs only (Compare, Studies, About stay as tabs)', items == ['labs'], items)
            pg.click('#tmenu [data-v=labs]')
            pg.wait_for_timeout(1200)
            lt = pg.inner_text('#v-labs')
            check('Labs dates are ISO (2026-11-21 10:20), not US order', re.search(r'\(\d{4}-\d\d-\d\d \d\d:\d\d\)', lt) and not re.search(r'\d+/\d+/\d{4}', lt), lt[:200])
            card = pg.inner_text('#v-labs .lb-card.withheld')
            check('Labs bootloader card: only the withheld sentence, no names or addresses', 'details withheld pending responsible disclosure' in card
                  and not re.search(r'0x|-O0|-O2', card) and not withheld_ids(card), card)
            check('Labs label chips are separated from the text', not re.search(r'(SIMULATED|MEASURED|UNTESTED)[a-z]', lt))
            pg.screenshot(path=OUT + 'labs_1366_dark.png', full_page=True)
            # ---- dark theme link contrast (audit 5-S1)
            pg.evaluate("show('about')")
            pg.wait_for_timeout(500)
            cr = contrast(pg, '#v-about a.keep')
            check(f'dark theme: teacher links readable (contrast {cr and round(cr, 2)} >= 4.5)', cr and cr >= 4.5, cr)
            # ---- restart noticed (audit 3-S5, 6-S3)
            pg.evaluate("S.boot='an-earlier-start';ping()")
            pg.wait_for_timeout(800)
            check('a restart is noticed: footer offers "reload this window"', 'reload this window' in pg.inner_text('#foot'))
            # ---- Open my design: labels, Show verb in recorded mode, page column (audit 5-S5, 1-N2, 10-S1)
            if pg.evaluate("VIEWS.some(v=>v.id==='mine')"):
                pg.evaluate("show('mine')")
                pg.wait_for_timeout(1500)
                lab = pg.evaluate("['by-path','by-yp'].map(i=>{const e=document.getElementById(i);return e&&(e.labels.length>0||!!e.getAttribute('aria-label'))})")
                check('Open my design: both path fields have a label', lab == [True, True], lab)
                bt = pg.evaluate("[...document.querySelectorAll('#by-ex [data-ex]')].map(b=>b.textContent.trim())")
                live = pg.evaluate("[...document.querySelectorAll('#by-ex [data-ex]')].some(b=>b.dataset.live==='1')")
                check('Open my design: saved-result buttons say "Show", never "Run ... (saved result)"', bt and all(not re.search(r'\bRun\b.*saved result', x) for x in bt)
                      and (live or all(re.match(r'(\d+\.\s*)?Show\b', x) for x in bt)), bt[:4])
                pg.click('#by-ex [data-ex]')
                pg.wait_for_timeout(2500)
                check('Open my design: the saved result starts with the plain-words finding', pg.evaluate("!!document.querySelector('#v-mine .findings .fcard .sev')"))
                pg.evaluate("show('start');show('mine')")
                w = pg.evaluate("document.querySelector('#v-mine').getBoundingClientRect().width")
                check(f'Open my design: page column like the other tabs (width {int(w)} <= 1180)', w <= 1181, w)
            pg.context.close()
            # ---- 200 % zoom: no sideways scrolling (audit 5-S4)
            for (w, h) in ((683, 384), (640, 360)):
                pg = page(b, w, h, 'light')
                bad = []
                for js in ("show('start')", "show('analyze');tryAttack()", "openExplore('x-chip')", "show('about')", "show('learn')"):
                    pg.evaluate(js)
                    pg.wait_for_timeout(900)
                    sw = pg.evaluate("document.documentElement.scrollWidth")
                    if sw > w + 1:
                        bad.append((js, sw))
                check(f'{w}x{h} (200 % zoom): no page scrolls sideways', not bad, bad)
                pg.evaluate("show('analyze')")
                pg.wait_for_timeout(300)
                ow = pg.evaluate("(document.querySelector('#story .orient')||document.body).getBoundingClientRect().width")
                check(f"{w}x{h}: the orientation boxes are stacked, not squeezed side by side", ow >= w * 0.6, ow)
                pg.screenshot(path=OUT + f'zoom_{w}_analyze.png')
                pg.context.close()
            b.close()
    finally:
        srv.terminate()
        srv.wait()
    print('JS errors:', len(errs), errs[:5])
    check('0 JS errors', not errs, errs[:3])
    bad = [c for c in checks if not c[1]]
    print('checks: %d of %d passed' % (len(checks) - len(bad), len(checks)))
    json.dump(dict(errors=errs, checks=checks), open(OUT + 'verify_audit.json', 'w'), indent=1)
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(run())
