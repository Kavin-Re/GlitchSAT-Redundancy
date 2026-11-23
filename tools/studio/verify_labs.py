"""Checks for the "Labs" tab (labs_view.py): Playwright/Chromium at 1366x768 (dark and light) plus 1024x720 for the More menu.
Screens go to shots_labs/. Recorded mode on the real repository. Usage: python3 verify_labs.py"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'shots_labs') + '/'
ROOT = os.environ.get('GLITCHSAT_ROOT') or os.path.normpath(os.path.join(HERE, '..', '..'))
PORT = 8883          # its own port: verify_ut2 uses 8881
os.makedirs(OUT, exist_ok=True)
errs, checks = [], []



def _boot_dir(ext):
    """tools/bootloader in the repository; in the development tree the study folder is named after the bootloader,
    which public files do not name: it is found by the hash of its name (sha256, first 16 hex digits)."""
    if os.path.isdir(os.path.join(ext, 'bootloader')):
        return os.path.join(ext, 'bootloader')
    import hashlib
    for n in sorted(os.listdir(ext)) if os.path.isdir(ext) else []:
        if hashlib.sha256(n.lower().encode()).hexdigest()[:16] == '2c5b41081632e17c':
            return os.path.join(ext, n)
    return os.path.join(ext, 'bootloader')


def _wording():
    """The shared wording and path check (tools/check_wording.py: the word list is stored there as hashes only)."""
    import importlib.util
    p = os.path.join(os.environ.get('GLITCHSAT_EXT') or os.path.dirname(HERE), 'check_wording.py')
    spec = importlib.util.spec_from_file_location('check_wording', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def check(name, ok, detail=''):
    checks.append((name, bool(ok), str(detail)[:200]))
    print(('  ok   ' if ok else '  FAIL ') + name + ('' if ok else ' : ' + str(detail)[:200]))


def page(b, w, h, theme, view='plain'):
    ctx = b.new_context(viewport={'width': w, 'height': h})
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: errs.append(('pageerror', str(e))))
    pg.on('console', lambda m: m.type == 'error' and errs.append(('console', m.text)))
    pg.add_init_script(f"try{{if(!sessionStorage.getItem('i')){{sessionStorage.setItem('i','1');localStorage.setItem('gs_predict','false');localStorage.setItem('gs_seehow','true');localStorage.setItem('gs_theme','\"{theme}\"');"
                       f"localStorage.setItem('gs_view','\"{view}\"');localStorage.setItem('gs_seen3','1')}}}}catch(e){{}}")
    pg.goto(f'http://127.0.0.1:{PORT}/')
    pg.wait_for_timeout(1500)
    return pg


def run():
    env = dict(os.environ, GLITCHSAT_ROOT=ROOT, XDG_CACHE_HOME=tempfile.mkdtemp(prefix='gslabs-'))
    srv = subprocess.Popen([sys.executable, os.path.join(HERE, 'studio.py'), '--no-browser', '--port', str(PORT), '--no-autostop'],
                           env=env, stdout=open('/tmp/gslabs.log', 'w'), stderr=subprocess.STDOUT)
    time.sleep(2.5)
    try:
        api = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/labs', timeout=20))
        mods = api.get('modules', [])
        check('api: 5 Labs modules (3 EXPERIMENTAL with results, 2 PLANNED)',
              [m['status'] for m in mods].count('EXPERIMENTAL') == 3 and [m['status'] for m in mods].count('PLANNED') == 2
              and all(m['findings'] for m in mods if m['status'] == 'EXPERIMENTAL'), [(m['id'], m['status'], len(m['findings'])) for m in mods])
        for m in mods:
            r = urllib.request.urlopen(f'http://127.0.0.1:{PORT}/labs/readme/{m["id"]}', timeout=20)
            body = r.read().decode()
            need = ['EXPERIMENTAL'] + (["WHAT WORKS", "WHAT DOESN", "HOW FAR TO TRUST"] if m['status'] == 'EXPERIMENTAL' else ['Planned'])
            check(f'readme page {m["id"]}: served, marked EXPERIMENTAL, has the required sections', r.status == 200 and all(x in body for x in need),
                  [x for x in need if x not in body])
        with sync_playwright() as p:
            b = p.chromium.launch()
            for theme in ('dark', 'light'):
                t = f'1366_{theme}'
                print(t)
                pg = page(b, 1366, 768, theme)
                pg.screenshot(path=OUT + f'{t}_start.png')
                tabs = pg.evaluate("[...document.querySelectorAll('#tabs .tab[data-v]')].map(x=>x.dataset.v)")
                check(f'{t}: Labs is registered last; the existing tabs keep their order', tabs[-1] == 'labs' and tabs[:2] == ['start', 'learn'], tabs)
                check(f'{t}: Labs sits in the More menu, not beside About (audit 1-N1)', not pg.is_visible('#tabs .tab[data-v="labs"]') and pg.is_visible('#tab-more'))
                check(f'{t}: Labs is not on Start or in the story (not on the learner path)',
                      'Labs' not in pg.inner_text('#v-start') and not pg.evaluate("STORY.some(c=>/Labs/.test(c.h+(c.t||'')))"))
                ov = pg.evaluate("(()=>{const n=document.querySelector('#tabs');const h=document.querySelector('header');return [n.scrollWidth<=n.clientWidth+1,h.scrollWidth<=h.clientWidth+1]})()")
                check(f'{t}: header fits without overflow', all(ov), ov)
                pg.keyboard.press('7'); pg.wait_for_timeout(200)
                k7 = pg.evaluate("S.tab")
                pg.keyboard.press('8'); pg.wait_for_timeout(200)
                check(f'{t}: keys 7 and 8 still open the lesson and Open my design', [k7, pg.evaluate("S.tab")] == ['learn', 'mine'], [k7, pg.evaluate("S.tab")])
                pg.click('#tab-more'); pg.wait_for_timeout(200); pg.click('#tmenu [data-v="labs"]'); pg.wait_for_timeout(900)
                pg.screenshot(path=OUT + f'{t}_labs.png')
                txt = pg.inner_text('#v-labs')
                check(f'{t}: intro says experiments in progress, try them, don\'t rely on them',
                      'experiments in progress' in txt and "Try them, don't rely on them" in txt)
                cards = pg.evaluate("[...document.querySelectorAll('#v-labs .lb-card')].map(c=>[c.querySelector('h3').textContent,c.querySelector('.lb-badge').textContent,c.querySelectorAll('.lb-f li').length,c.querySelectorAll('.lb-f .lb-lab').length,!!c.querySelector('.lb-q'),c.querySelector('.lb-foot a').getAttribute('href'),c.className])")
                check(f'{t}: one card per module (5), 3 EXPERIMENTAL and 2 PLANNED badges', len(cards) == 5 and [c[1] for c in cards].count('EXPERIMENTAL') == 3
                      and [c[1] for c in cards].count('PLANNED') == 2, cards)
                check(f'{t}: every card links its README; every card but the withheld one says what it tries to answer', all((c[4] or 'withheld' in c[6]) and c[5].startswith('/labs/readme/') for c in cards), cards)
                wh = [c for c in cards if 'withheld' in c[6]]
                check(f'{t}: the bootloader card shows only "details withheld pending responsible disclosure" (audit 3-B1)', len(wh) == 1 and wh[0][2] == 1, wh)
                check(f'{t}: every EXPERIMENTAL card lists findings, each with a label', all(c[2] > 0 and c[2] == c[3] for c in cards if c[1] == 'EXPERIMENTAL'), cards)
                labs = set(pg.evaluate("[...document.querySelectorAll('#v-labs .lb-f .lb-lab')].map(x=>x.textContent)"))
                check(f'{t}: labels are only MEASURED / SIMULATED / UNTESTED', labs <= {'MEASURED', 'SIMULATED', 'UNTESTED'} and labs, labs)
                wide = pg.evaluate("[...document.querySelectorAll('#v-labs *')].filter(e=>{const r=e.getBoundingClientRect();return r.width&&r.right>innerWidth+1}).length")
                check(f'{t}: nothing wider than the window', wide == 0, wide)
                pg.evaluate("document.querySelectorAll('#v-labs details').forEach(d=>d.open=true)"); pg.wait_for_timeout(200)
                sh = pg.evaluate("document.querySelector('#v-labs').scrollHeight")
                for i, y in enumerate(range(0, sh, 640)):
                    pg.evaluate(f"document.querySelector('#v-labs').scrollTop={y}"); pg.wait_for_timeout(120)
                    pg.screenshot(path=OUT + f'{t}_labs_open_{i}.png')
                check(f'{t}: Plain view hides the run commands', not pg.is_visible('#v-labs .tech-only'))
                pg.keyboard.press('v'); pg.wait_for_timeout(300)
                pg.evaluate("document.querySelector('#v-labs').scrollTop=0")
                check(f'{t}: Technical view shows the run commands', pg.is_visible('#v-labs .tech-only'))
                pg.screenshot(path=OUT + f'{t}_labs_tech.png')
                pg.keyboard.press('v')
                with pg.context.expect_page() as np_:
                    pg.click('#v-labs .lb-card .lb-foot a')
                rp = np_.value
                rp.wait_for_load_state(); rp.set_viewport_size({'width': 1366, 'height': 768})
                rp.screenshot(path=OUT + f'{t}_readme.png')
                check(f'{t}: README link opens the module README', 'WHAT WORKS' in rp.inner_text('body'))
                rp.close()
                pg.context.close()
            pg = page(b, 1024, 720, 'dark')
            vis = pg.evaluate("document.querySelector('#tabs .tab[data-v=\"labs\"]').getClientRects().length")
            pg.click('#tab-more'); pg.wait_for_timeout(200)
            items = pg.evaluate("[...document.querySelectorAll('#tmenu [data-v]')].map(x=>x.dataset.v)")
            pg.screenshot(path=OUT + '1024_more_menu.png')
            check('1024: More menu lists Compare, Studies, About, then Labs', vis == 0 and items[-1] == 'labs' and items[:3] == ['compare', 'findings', 'about'], [vis, items])
            pg.click('#tmenu [data-v="labs"]'); pg.wait_for_timeout(700)
            check('1024: More menu opens Labs', pg.evaluate("S.tab") == 'labs' and pg.is_visible('#v-labs .lb-card'))
            pg.screenshot(path=OUT + '1024_labs.png')
            pg.context.close()
            b.close()
    finally:
        srv.terminate()
        srv.wait()
    E = os.environ.get('GLITCHSAT_EXT') or os.path.dirname(HERE)
    RL = os.environ.get('GLITCHSAT_REAL') or os.path.join(os.path.dirname(HERE), 'real')
    BT = _boot_dir(E)      # the bootloader study: tools/bootloader, or its development folder (found by the hashed name)
    files = [os.path.join(HERE, 'labs_view.py')] + [os.path.join(E, f) for f in (
        'labs/README.md', 'labs/labs.py', 'labs/labs_result.py', 'masking/README.md',
        'masking/masking/probe.py', 'masking/scripts/run_labs.py', 'masking/results/labs_result.json')] + [
        os.path.join(BT, f) for f in ('README.md', os.path.join('to_report', 'README.md'), os.path.join('scripts', 'run_labs.py'),
                                      os.path.join('to_report', 'repro.py'), os.path.join('results', 'labs_result.json'))] + [
        os.path.join(RL, f) for f in ('opentitan_prims/README.md', 'opentitan_prims/labs/run_labs.py', 'opentitan_prims/labs/results/labs_result.json')]
    hits = [h for h in _wording().scan([f for f in files if os.path.isfile(f)])      # private notes may name the study
            if not (h[2].startswith('disclose:') and os.sep + 'to_report' + os.sep in h[0])]
    check('Labs text and results: no listed word and no absolute developer path (shared hashed check)', not hits, hits[:4])
    print('JS errors:', len(errs), errs[:5])
    check('0 JS errors', not errs, errs[:3])
    bad = [c for c in checks if not c[1]]
    print('checks: %d of %d passed' % (len(checks) - len(bad), len(checks)))
    json.dump(dict(errors=errs, checks=checks), open(OUT + 'verify_labs.json', 'w'), indent=1)
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(run())
