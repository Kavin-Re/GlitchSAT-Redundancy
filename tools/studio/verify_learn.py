"""Checks for the "Why protect chips?" lesson (learn_view.py): Playwright/Chromium at 1366x768 and 1920x1080, dark and light.
Screens go to shots_learn/. Recorded mode on the real repository. Usage: python3 verify_learn.py"""
import os, re, sys, json, time, subprocess, tempfile
from playwright.sync_api import sync_playwright
SEEN3 = 'localStorage.setItem("gs_seen3","1")'   # outside the f-string: Python 3.10 and 3.11 allow no backslash there
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'shots_learn') + '/'
ROOT = os.environ.get('GLITCHSAT_ROOT') or os.path.normpath(os.path.join(HERE, '..', '..')); PORT = 8879
os.makedirs(OUT, exist_ok=True)
SCAN = re.search(r'SCAN = r"""(.*?)"""', open(os.path.join(HERE, 'verify31.py')).read(), re.S).group(1)   # same Plain-view word scan as verify31
errs, vocab, checks = [], {}, []

def _wording():
    """The shared wording and path check (tools/check_wording.py: the word list is stored there as hashes only)."""
    import importlib.util
    p = os.path.join(os.environ.get('GLITCHSAT_EXT') or os.path.dirname(HERE), 'check_wording.py')
    spec = importlib.util.spec_from_file_location('check_wording', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def check(name, ok, detail=''):
    checks.append((name, bool(ok), str(detail)[:200])); print(('  ok   ' if ok else '  FAIL ') + name + ('' if ok else ' : ' + str(detail)[:200]))
def page(b, w, h, theme, view='plain', seen=False):
    ctx = b.new_context(viewport={'width': w, 'height': h}); pg = ctx.new_page()
    pg.on('pageerror', lambda e: errs.append(('pageerror', str(e)))); pg.on('console', lambda m: m.type == 'error' and errs.append(('console', m.text)))
    pg.add_init_script(f"try{{if(!sessionStorage.getItem('i')){{sessionStorage.setItem('i','1');localStorage.setItem('gs_predict','false');localStorage.setItem('gs_seehow','true');localStorage.setItem('gs_theme','\"{theme}\"');localStorage.setItem('gs_view','\"{view}\"');{SEEN3 if seen else ''}}}}}catch(e){{}}")
    pg.goto(f'http://127.0.0.1:{PORT}/'); pg.wait_for_timeout(1400); return pg
def snap(pg, name, scan=True):
    pg.wait_for_timeout(300); pg.screenshot(path=OUT + name + '.png')
    if scan and pg.evaluate("document.documentElement.dataset.view") == 'plain':
        r = pg.evaluate(SCAN)
        if r: vocab[name] = r
def run():
    env = dict(os.environ, GLITCHSAT_ROOT=ROOT, GLITCHSAT_FIRSTRUN='0', XDG_CACHE_HOME=tempfile.mkdtemp(prefix='gslcache-'))
    srv = subprocess.Popen([sys.executable, os.path.join(HERE, 'studio.py'), '--no-browser', '--port', str(PORT), '--no-autostop'], env=env, stdout=open('/tmp/gslearn.log', 'w'), stderr=subprocess.STDOUT)
    time.sleep(2.0)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            for (w, h, tag) in [(1366, 768, '1366'), (1920, 1080, '1920')]:
                for theme in ('dark', 'light'):
                    t = f'{tag}_{theme}'; print(t)
                    pg = page(b, w, h, theme)
                    titles = pg.evaluate("STORY.map(c=>c.h)")
                    check(f'{t}: story card added after the lock and thief cards', titles[:3] == ['A chip has a lock', 'A thief without the key', 'This really happens'], titles)
                    pg.click('#snx'); pg.click('#snx'); snap(pg, f'{t}_story3_really_happens')
                    pg.click('#modal [data-go="learn:5"]'); pg.wait_for_timeout(500)
                    check(f'{t}: story link opens the lesson at the true stories', pg.evaluate("[S.tab,S.story,document.querySelector('#lz-h')&&document.querySelector('#lz-h').textContent]") == ['learn', None, 'True stories: games, TV and gadgets'])
                    pg.evaluate("show('start')"); pg.wait_for_timeout(300); snap(pg, f'{t}_start')
                    check(f'{t}: Start shows the lesson link', pg.is_visible('#v-start .lz-start [data-go="learn:1"]'))
                    tabs = pg.evaluate("[...document.querySelectorAll('#tabs .tab')].map(x=>x.textContent)")
                    check(f'{t}: menu (tab bar) has the lesson second, after Start (UT2 S2), then the six existing tabs in their order', tabs[:2] == ['Start', 'Why protect chips?'] and [x for x in tabs if x in ('Start', 'Try an attack', 'Explore', 'Compare', 'Studies', 'About')] == ['Start', 'Try an attack', 'Explore', 'Compare', 'Studies', 'About'], tabs)
                    ov = pg.evaluate("(()=>{const n=document.querySelector('#tabs');const h=document.querySelector('header');return [n.scrollWidth<=n.clientWidth+1,h.scrollWidth<=h.clientWidth+1]})()")
                    check(f'{t}: header fits without overflow', all(ov), ov)
                    pg.click('#tabs .tab[data-v="learn"]'); pg.wait_for_timeout(300); pg.evaluate("LearnView.goTo(0)")
                    n = pg.evaluate("LearnView.SCR.length")
                    for i in range(n):
                        if i: pg.click('#lz-next'); pg.wait_for_timeout(250)
                        snap(pg, f'{t}_learn{i+1:02d}')
                        sh, ch = pg.evaluate("[document.querySelector('#v-learn').scrollHeight,document.querySelector('#v-learn').clientHeight]")
                        if sh > ch + 20:
                            pg.evaluate("document.querySelector('#v-learn').scrollTop=99999"); snap(pg, f'{t}_learn{i+1:02d}_end')
                        wide = pg.evaluate("[...document.querySelectorAll('#v-learn *')].filter(e=>{const r=e.getBoundingClientRect();return r.width&&r.right>innerWidth+1}).length")
                        if wide: check(f'{t}: screen {i+1} nothing wider than the window', False, wide)
                    # quiz
                    pg.click('[data-q="0"][data-o="1"]'); pg.wait_for_timeout(150)
                    check(f'{t}: quiz wrong answer marked and explained', pg.evaluate("[!!document.querySelector('[data-q=\"0\"][data-o=\"1\"].wrong'),!!document.querySelector('[data-q=\"0\"][data-o=\"0\"].right'),/Not quite/.test(document.querySelector('.lz-q .ex').textContent)]") == [True, True, True])
                    pg.click('[data-q="1"][data-o="1"]'); pg.click('[data-q="2"][data-o="1"]'); pg.wait_for_timeout(150)
                    pg.evaluate("document.querySelector('#v-learn').scrollTop=0"); snap(pg, f'{t}_quiz_answered')
                    pg.evaluate("document.querySelector('#v-learn').scrollTop=99999"); snap(pg, f'{t}_quiz_answered_end')
                    pg.click('#lz-srcs summary'); pg.wait_for_timeout(150); pg.evaluate("document.querySelector('#v-learn').scrollTop=99999"); snap(pg, f'{t}_sources')
                    links = pg.evaluate("[...document.querySelectorAll('#lz-srcs a')].map(a=>a.href)")
                    check(f'{t}: sources expander lists 13 web pages and the report', len(links) == 13 and pg.evaluate("document.querySelectorAll('#lz-srcs li').length") == 14, len(links))
                    # explore lines
                    ids = pg.evaluate("xlist().map(v=>v.id)"); miss = []
                    for i, xid in enumerate(ids):
                        pg.evaluate(f"openExplore('{xid}')"); pg.wait_for_timeout(700)
                        if not pg.is_visible('#xbody .lz-risk'): miss.append(xid)
                        if pg.evaluate("document.querySelectorAll('#xbody .lz-risk').length") != 1: miss.append(xid + ' (count)')
                        if i < 2 or tag == '1366': snap(pg, f'{t}_explore_{xid}')
                    check(f'{t}: every Explore page has one real-world risk line ({len(ids)} pages)', not miss, miss)
                    pg.click('#xbody .lz-risk [data-go]'); pg.wait_for_timeout(300)
                    check(f'{t}: risk line link opens the lesson', pg.evaluate("S.tab") == 'learn')
                    # keyboard
                    pg.evaluate("LearnView.goTo(0)"); pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(150)
                    check(f'{t}: arrow key moves to screen 2 and focus goes to the heading', pg.evaluate("[document.querySelector('.lz-kick').textContent.startsWith('Screen 2'),document.activeElement.id]") == [True, 'lz-h'])
                    pg.keyboard.press('7'); pg.wait_for_timeout(200); check(f'{t}: key 7 opens the lesson tab', pg.evaluate("S.tab") == 'learn')
                    pg.keyboard.press('1'); pg.wait_for_timeout(200); check(f'{t}: key 1 still opens Start', pg.evaluate("S.tab") == 'start')
                    # technical view
                    pg.keyboard.press('v'); pg.wait_for_timeout(200); pg.evaluate("show('learn');LearnView.goTo(7)"); snap(pg, f'{t}_tech_hidden_danger', False)
                    check(f'{t}: technical view names the build tool', 'Yosys' in pg.inner_text('#v-learn'))
                    pg.evaluate("LearnView.goTo(8)"); snap(pg, f'{t}_tech_who_checks', False)
                    pg.keyboard.press('v'); pg.context.close()
            b.close()
    finally:
        srv.terminate()
    hits = _wording().scan([os.path.join(HERE, 'learn_view.py')])
    check('lesson source: no listed word and no absolute developer path (shared hashed check)', not hits, hits[:4])
    print('JS errors:', len(errs), errs[:5]); print('Plain-view vocabulary findings:', vocab)
    bad = [c for c in checks if not c[1]]; print('checks: %d of %d passed' % (len(checks) - len(bad), len(checks)))
    json.dump(dict(errors=errs, vocab=vocab, checks=checks), open(OUT + 'verify_learn.json', 'w'), indent=1)
if __name__ == '__main__':
    run()
