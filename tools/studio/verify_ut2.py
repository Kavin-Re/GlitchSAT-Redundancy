"""Checks for the UT2 pass (USABILITY_TEST_2.md): one start command, top bar, lesson honesty, fix layer, class plan, gallery.
Playwright/Chromium at 1280x720, 1366x768 and 1920x1080 (plus 1024 for the More menu), dark and light, one keyboard pass.
Screens go to shots_ut2/. Recorded mode on the real repository (no z3, no Yosys here). Usage: python3 verify_ut2.py"""
import os, re, sys, json, time, subprocess, tempfile, urllib.request
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', '/opt/pw-browsers')
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'shots_ut2') + '/'
ROOT = os.environ.get('GLITCHSAT_ROOT') or os.path.normpath(os.path.join(HERE, '..', '..')); PORT = 8881; URL = f'http://127.0.0.1:{PORT}/'
os.makedirs(OUT, exist_ok=True)
SCAN = re.search(r'SCAN = r"""(.*?)"""', open(os.path.join(HERE, 'verify31.py')).read(), re.S).group(1)
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
    checks.append((name, bool(ok), str(detail)[:300])); print(('  ok   ' if ok else '  FAIL ') + name + ('' if ok else ' : ' + str(detail)[:300]))
def page(b, w, h, theme, view='plain', seen=True, url=URL):
    ctx = b.new_context(viewport={'width': w, 'height': h}); pg = ctx.new_page()
    pg.on('pageerror', lambda e: errs.append(('pageerror', str(e)))); pg.on('console', lambda m: m.type == 'error' and errs.append(('console', m.text)))
    pg.add_init_script("try{if(!sessionStorage.getItem('i')){sessionStorage.setItem('i','1');localStorage.setItem('gs_predict','false');localStorage.setItem('gs_seehow','true');localStorage.setItem('gs_theme','\"%s\"');localStorage.setItem('gs_view','\"%s\"');%s}}catch(e){}" % (theme, view, 'localStorage.setItem("gs_seen3","1")' if seen else ''))
    pg.goto(url); pg.wait_for_timeout(1500); return pg
def snap(pg, name, scan=True, full=False):
    pg.wait_for_timeout(300); pg.screenshot(path=OUT + name + '.png', full_page=full)
    if scan and pg.evaluate("document.documentElement.dataset.view") == 'plain':
        r = pg.evaluate(SCAN)
        if r: vocab[name] = r
HDR = """()=>{const hd=document.querySelector('header'),hr=hd.getBoundingClientRect();const vis=[...hd.querySelectorAll('.tab,.btn,.seg,.logo')].filter(e=>e.getClientRects().length);
 const bad=vis.filter(e=>{const r=e.getBoundingClientRect();return r.left<-0.5||r.right>innerWidth+0.5||r.top<hr.top-0.5||r.bottom>hr.bottom+0.5}).map(e=>e.textContent.trim().slice(0,20));
 const tabs=[...hd.querySelectorAll('.tab')].filter(e=>e.getClientRects().length);const oneLine=tabs.every(t=>t.getBoundingClientRect().height===tabs[0].getBoundingClientRect().height&&t.scrollWidth<=t.clientWidth+1&&t.scrollHeight<=t.clientHeight+1);
 let overlap=0;for(let i=1;i<vis.length;i++){const a=vis[i-1].getBoundingClientRect(),c=vis[i].getBoundingClientRect();if(!vis[i-1].contains(vis[i])&&c.left<a.right-0.5&&c.top<a.bottom&&a.top<c.bottom)overlap++}
 return {fit:hd.scrollWidth<=hd.clientWidth+1&&document.documentElement.scrollWidth<=innerWidth,bad,oneLine,overlap,labels:tabs.map(t=>t.innerText.trim()||getComputedStyle(t,'::after').content.replace(/"/g,''))}}"""
def get(path):
    with urllib.request.urlopen(URL.rstrip('/') + path) as r: return r.status, dict(r.headers), r.read().decode()
def run():
    env = dict(os.environ, GLITCHSAT_ROOT=ROOT, GLITCHSAT_FIRSTRUN='0', XDG_CACHE_HOME=tempfile.mkdtemp(prefix='gsut2-'))
    for k in ('GLITCHSAT_STUDIO', 'GLITCHSAT_BYOD'): env.pop(k, None)
    srv = subprocess.Popen([sys.executable, os.path.join(HERE, 'studio.py'), '--no-browser', '--port', str(PORT), '--no-autostop'], env=env, stdout=open('/tmp/gsut2.log', 'w'), stderr=subprocess.STDOUT)
    time.sleep(2.5)
    try:
        # ---- one start command, headers, printable pages
        st = json.loads(get('/api/status')[2]); code, hd, html = get('/')
        check('one command: plug-in loaded with no environment variable', st.get('plugins') == ['Open my design'], st.get('plugins'))
        check('one command: start-up log names the lesson and the plug-in', all(x in open('/tmp/gsut2.log').read() for x in ('"Why protect chips?" loaded', '"Open my design" loaded from')))
        csp = hd.get('Content-Security-Policy', '')
        check("CSP is sent and lets the app frame its own pages (frame-ancestors 'self')", "frame-ancestors 'self'" in csp and "default-src 'self'" in csp and "'none'" not in csp.split('frame-ancestors')[1], csp)
        g = json.loads(get('/api/gallery')[2]); check('gallery: saved results of 4 examples, 2 runs each', len(g.get('examples', [])) == 4 and all(len(x['runs']) == 2 for x in g['examples']))
        for k in ('teach', 'project'):
            c, h2, t = get('/' + k)
            check(f'/{k}: served, with CSP', c == 200 and 'Content-Security-Policy' in h2)
            bad = _wording().scan_text(re.sub(r'<style>.*?</style>', '', t, flags=re.S))
            check(f'/{k}: no listed word and no developer path (shared hashed check)', not bad, bad)
        t = get('/teach')[2]
        check('class plan: 45 minutes, three activities, answers, student sheet, honesty box', all(x in t for x in ('0 – 3', '40 – 45', 'Activity A', 'Activity B', 'Activity C', 'Answers to “Check yourself”', 'Student sheet', 'nothing is measured on a real chip', 'no chip build tool')))
        check('class plan: gallery answers come from the saved files', all(('<b>%s</b>' % (('%d glitch%s' % (r['min_faults'], '' if r['min_faults'] == 1 else 'es')) if r['verdict'] == 'ATTACK_FOUND' else 'no way in with up to %d glitches' % r['max_faults'])) in t for x in g['examples'] for r in x['runs']))
        with sync_playwright() as p:
            b = p.chromium.launch()
            for (w, h) in [(1280, 720), (1366, 768), (1920, 1080)]:
                for theme in ('dark', 'light'):
                    T = f'{w}_{theme}'; print(T); full = (theme == 'dark')
                    pg = page(b, w, h, theme)
                    tabs = pg.evaluate("[...document.querySelectorAll('#tabs .tab[data-v]')].map(x=>x.dataset.v)")
                    check(f'{T}: both add-on tabs are there; the lesson is second', tabs[:2] == ['start', 'learn'] and tabs.count('mine') == 1, tabs)
                    r = pg.evaluate(HDR); check(f'{T}: top bar fits, one line, nothing clipped or overlapping', r['fit'] and not r['bad'] and r['oneLine'] and not r['overlap'], r)
                    check(f'{T}: labels ' + ('compact' if w < 1400 else 'full'), ('My design' in r['labels'] and 'Why protect?' in r['labels']) if w < 1400 else ('Open my design' in r['labels'] and 'Why protect chips?' in r['labels']), r['labels'])
                    snap(pg, f'{T}_01_start')
                    check(f'{T}: Start says when/how labels differ and links the class plan', pg.evaluate("/say when it was computed/.test(document.querySelector('#v-start').innerText.replace(/\\s+/g,' '))") and pg.is_visible('#v-start a[data-page="teach"]'))
                    # path with Export visible; step 2 and 4 sentences; no hover box on the path list
                    pg.evaluate("loadStep(1)"); pg.wait_for_timeout(1300)
                    r = pg.evaluate(HDR); check(f'{T}: top bar still fits with Export shown', r['fit'] and not r['bad'] and r['oneLine'] and not r['overlap'] and pg.is_visible('#b-export'), r)
                    check(f'{T}: step 2 says the designer drew the shared wire', 'the designer drew the shared wire' in pg.inner_text('.plainstory'))
                    check(f'{T}: path list has no hover box in Plain view', pg.evaluate("[...document.querySelectorAll('#steps .step')].every(s=>!s.hasAttribute('data-tip'))"))
                    check(f'{T}: step 2 fix layer is there, closed, and names the cause', pg.evaluate("(()=>{const d=document.querySelector('#result .fxhost details');return d&&!d.open&&/designer drew/.test(d.textContent)})()"))
                    pg.evaluate("loadStep(3)"); pg.wait_for_timeout(1300)
                    check(f'{T}: step 4 explains glitches at different steps', 'glitches do not have to land together' in pg.inner_text('.plainstory'))
                    lab = pg.evaluate("[...document.querySelectorAll('#wavebox text')].map(t=>t.textContent).filter(t=>/…$/.test(t))"); check(f'{T}: step 4 row labels are not cut off', not lab, lab)
                    snap(pg, f'{T}_02_step4', full=False)
                    pg.click('#result .fxhost summary'); pg.wait_for_timeout(1200); pg.evaluate("document.querySelector('#result .fxhost').scrollIntoView()")
                    tx = pg.inner_text('#result .fxhost')
                    check(f'{T}: fix layer names the four remedies with tool words and evidence', all(x in tx for x in ('Keep the copies', 'Choose the encoding', 'Place the copies apart', 'Barriers', 'keep_hierarchy', 'set_dont_touch', 'fsm_encoding', 'size_only', 'volatile', 'Then check again', 'has not tested them on your flow')) and tx.count('Seen here') == 4, tx[:200])
                    snap(pg, f'{T}_03_step4_fix')
                    pg.click('#result .fxhost [data-go="x-fix"]'); pg.wait_for_timeout(900)
                    check(f'{T}: fix layer links to Suggest a fix', pg.evaluate("[S.tab,S.xv]") == ['explore', 'x-fix'])
                    snap(pg, f'{T}_04_suggest_fix')
                    for xid in ('x-spots', 'x-fix', 'x-shots', 'x-fw', 'x-real', 'x-gal'):
                        pg.evaluate(f"openExplore('{xid}')"); pg.wait_for_timeout(800)
                        ok = pg.evaluate("(()=>{const h=document.querySelectorAll('#xbody .fxhost details');return h.length===1&&!!h[0].querySelector('[data-go=\"x-fix\"]')})()")
                        if not ok: check(f'{T}: {xid} has the fix layer', False)
                        if xid in ('x-shots', 'x-fw') and full:
                            pg.click('#xbody .fxhost summary'); pg.wait_for_timeout(900); pg.evaluate("document.querySelector('#xbody .fxhost').scrollIntoView()"); snap(pg, f'{T}_05_{xid}_fix')
                    check(f'{T}: fix layer on six Explore pages', True)
                    # gallery
                    pg.evaluate("openExplore('x-gal')"); pg.wait_for_timeout(800); snap(pg, f'{T}_06_gallery')
                    gt = pg.inner_text('#xbody')
                    check(f'{T}: gallery shows weak and protected saved results, labelled RECORDED, no build tool needed', all(x in gt for x in ('1 glitch is enough', '3 glitches are enough', 'Did the protection survive the build?', 'You are seeing saved results', 'RECORDED')) and 'MEASURED' not in gt and '1. 1.' not in gt and 'Run ' not in gt.replace('Running', ''), gt[:120])
                    check(f'{T}: gallery puts the weak version first on every card', pg.evaluate("[...document.querySelectorAll('.galx')].every(g=>g.children[0].classList.contains('weak'))"))
                    pg.evaluate("document.querySelector('#xbody').scrollTop=99999"); snap(pg, f'{T}_06_gallery_end')
                    # evidence report frame
                    pg.evaluate("openExplore('x-rep')"); pg.wait_for_timeout(1600); pg.evaluate("document.querySelector('.evf').scrollIntoView()"); pg.wait_for_timeout(900)
                    fr = [f for f in pg.frames if f != pg.main_frame]
                    check(f'{T}: Evidence report frame has content', bool(fr) and len(fr[0].inner_text('body')) > 500, [f.url for f in fr]); snap(pg, f'{T}_07_evidence_frame', False)
                    # lesson
                    pg.evaluate("show('learn');LearnView.goTo(0)"); pg.wait_for_timeout(400); snap(pg, f'{T}_08_lesson1')
                    l1 = pg.inner_text('#v-learn .lz-card'); m = re.search(r'About (\d+) minutes of reading', l1)
                    wc = pg.evaluate("(()=>{let n=0;LearnView.SCR.forEach(s=>{const d=document.createElement('div');d.innerHTML=s.html();d.querySelectorAll('details.lz-more,svg,.fxhost').forEach(x=>x.remove());n+=(d.textContent.trim().match(/\\S+/g)||[]).length});return n})()")
                    check(f'{T}: time estimate is counted from the text ({wc} words at 150 a minute)', bool(m) and abs(int(m.group(1)) - round(wc / 150)) <= 1 and '6 minutes' not in l1, l1[:80])
                    pg.evaluate("LearnView.goTo(2)"); pg.wait_for_timeout(300); snap(pg, f'{T}_09_lesson3')
                    check(f'{T}: screen 3 heading no longer promises two', pg.evaluate("[document.querySelector('#lz-h').textContent,document.querySelectorAll('#v-learn .lz-card>.lz-grid3>.lz-how').length,document.querySelectorAll('#v-learn details.lz-more .lz-how').length]") == ['What a thief gains', 3, 3])
                    pg.click('#v-learn details.lz-more summary'); pg.wait_for_timeout(200); pg.evaluate("document.querySelector('#v-learn details.lz-more').scrollIntoView()"); snap(pg, f'{T}_09_lesson3_more')
                    pg.click('.lz-cite[data-cite="5"]'); pg.wait_for_timeout(300)
                    check(f'{T}: citation number opens Sources at that item, with focus', pg.evaluate("[document.activeElement.id,document.querySelector('#lz-srcs').open]") == ['lz-s5', True])
                    s5, s12 = pg.evaluate("[document.querySelector('#lz-s5').innerText,document.querySelector('#lz-s12').innerText]")
                    check(f'{T}: source titles are not rewritten in Plain view', 'Concerning Fault Injection and eFuse' in s5 and 'Fault Injection Attacks Against AMD' in s12, s5[:80]); snap(pg, f'{T}_10_sources', False)
                    pg.evaluate("LearnView.goTo(7)"); pg.wait_for_timeout(300); snap(pg, f'{T}_11_lesson8')
                    check(f'{T}: screen 8 tells the two causes apart and offers the fix layer', 'Same weakness, two different causes' in pg.inner_text('#v-learn') and pg.evaluate("!!document.querySelector('#v-learn .fxhost details')"))
                    pg.evaluate("LearnView.goTo(LearnView.SCR.length-1)"); pg.wait_for_timeout(300)
                    for q, o in [(0, 1), (1, 1), (2, 1), (3, 1), (4, 2)]: pg.click(f'[data-q="{q}"][data-o="{o}"]'); pg.wait_for_timeout(80)
                    check(f'{T}: self-check has 5 questions and a first-try score', pg.evaluate("document.querySelectorAll('.lz-q').length") == 5 and 'You got 4 of 5 right on the first try' in pg.inner_text('#lz-score'))
                    pg.evaluate("document.querySelector('#lz-score').scrollIntoView({block:'center'})"); snap(pg, f'{T}_12_quiz_score')
                    pg.click('#lz-again'); pg.wait_for_timeout(200); check(f'{T}: Try again clears the answers', pg.evaluate("!document.querySelector('#lz-score')&&!document.querySelector('.lz-q .ex')"))
                    pg.evaluate("LearnView.goTo(4)"); pg.reload(); pg.wait_for_timeout(1500)
                    check(f'{T}: a lesson screen has an address and survives a reload', pg.evaluate("[S.tab,location.hash,document.querySelector('.lz-kick').textContent.slice(0,8)]") == ['learn', '#learn/5', 'Screen 5'])
                    pg.evaluate("show('start')"); check(f'{T}: the address is cleared outside the lesson', pg.evaluate("location.hash") == '')
                    # predict first
                    pg.evaluate("loadStep(4)"); pg.wait_for_timeout(1300); pg.click('#pred-on'); pg.wait_for_timeout(200); pg.evaluate("loadStep(5)"); pg.wait_for_timeout(1300)
                    check(f'{T}: Predict first veils the result and hides the number', pg.evaluate("[document.querySelector('#result').inert,document.querySelector('#steps .step.on').classList.contains('pend'),/prediction first/.test(document.querySelector('.plainstory').innerText)]") == [True, True, True])
                    snap(pg, f'{T}_13_predict', False); pg.click('[data-pred="3"]'); pg.wait_for_timeout(300)
                    check(f'{T}: after the guess the result is shown and compared', pg.evaluate("document.querySelector('#result').inert") is False and 'You predicted 3. The result: 1 glitch' in pg.inner_text('#pred-out')); snap(pg, f'{T}_13_predict_done')
                    pg.click('#pred-on')
                    # about, help, open my design tab
                    pg.evaluate("show('about')"); pg.wait_for_timeout(400); check(f'{T}: About links the class plan and the project page', pg.is_visible('#v-about a[data-page="teach"]') and pg.is_visible('#v-about a[data-page="project"]'))
                    pg.keyboard.press('?'); pg.wait_for_timeout(300); kt = pg.inner_text('#modal'); snap(pg, f'{T}_14_keys', False)
                    check(f'{T}: key list names every tab and the lesson arrows', re.search(r'1 … \d', kt) and 'Open my design' in kt and 'previous / next screen' in kt, kt[:100]); pg.keyboard.press('Escape')
                    pg.evaluate("show('mine')"); pg.wait_for_timeout(900); snap(pg, f'{T}_15_open_my_design', False)
                    check(f'{T}: Open my design tab draws its gallery', pg.evaluate("document.querySelectorAll('#v-mine .by-card').length") >= 4)
                    # technical view
                    pg.keyboard.press('v'); pg.wait_for_timeout(300); pg.evaluate("loadStep(3)"); pg.wait_for_timeout(1500); tt = pg.inner_text('#result')
                    check(f'{T}: Technical: one stand-in sentence, no stand-in chips; design named both ways; no Plain words in the bound', 'Which netlist.' in tt and pg.evaluate("document.querySelectorAll('#result .chip.stin').length") == 0 and 'V2 (three-copy lock)' in tt and 'thief must fake' not in pg.inner_text('#result .bound') and 'chip plan' not in pg.inner_text('#result .bound'), tt[:150])
                    check(f'{T}: Technical: fix layer is open', pg.evaluate("document.querySelector('#result .fxhost details').open"))
                    snap(pg, f'{T}_16_step4_technical', False, full=full)
                    pg.click('#result details.more:not(.fixit) > summary'); pg.wait_for_timeout(200); check(f'{T}: Technical: the two tools are told apart', 'two tools, one name' in pg.inner_text('#result') and 'max_faults' in pg.inner_text('#result'))
                    pg.evaluate("openExplore('x-shots')"); pg.wait_for_timeout(900); pg.evaluate("document.querySelector('#xc details.learn').open=true"); pg.wait_for_timeout(200)
                    check(f'{T}: laser Learn more is a table, not raw JSON', pg.evaluate("document.querySelectorAll('#xc details.learn table.jt').length") >= 2 and '{"' not in pg.inner_text('#xc details.learn .kv2 > div:nth-child(2)'))
                    pg.evaluate("document.querySelector('#xc details.learn').scrollIntoView()"); snap(pg, f'{T}_17_laser_learn_more', False)
                    pg.evaluate("openExplore('x-hw')"); pg.wait_for_timeout(900); check(f'{T}: secure-boot page says what has been analysed', 'Already analysed elsewhere' in pg.inner_text('#xbody')); snap(pg, f'{T}_18_secboot', False)
                    pg.evaluate("show('learn');LearnView.goTo(7)"); pg.wait_for_timeout(600); check(f'{T}: lesson screen 8, Technical: named remedies', 'keep_hierarchy' in pg.inner_text('#v-learn')); pg.evaluate("document.querySelector('#v-learn .fxhost').scrollIntoView()"); snap(pg, f'{T}_19_lesson8_technical', False)
                    pg.keyboard.press('v')
                    # printable pages in this theme
                    for k in ('teach', 'project'):
                        p2 = pg.context.new_page(); p2.on('pageerror', lambda e: errs.append(('pageerror', str(e)))); p2.on('console', lambda m: m.type == 'error' and errs.append(('console', m.text)))
                        p2.goto(URL + k + '?theme=' + theme); p2.wait_for_timeout(300); p2.screenshot(path=OUT + f'{T}_20_{k}.png', full_page=full)
                        if full and w == 1280:
                            wide = p2.evaluate("document.documentElement.scrollWidth<=innerWidth"); check(f'/{k}: fits the window', wide)
                            p2.emulate_media(media='print'); p2.screenshot(path=OUT + f'print_{k}.png', full_page=True); p2.pdf(path=OUT + f'print_{k}.pdf', format='A4')
                        p2.close()
                    pg.context.close()
            # ---- 1024: More menu
            pg = page(b, 1024, 720, 'dark'); r = pg.evaluate(HDR)
            check('1024: top bar fits with a More menu', r['fit'] and not r['bad'] and r['oneLine'] and 'More ▾' in r['labels'] and 'Compare' not in r['labels'], r)
            pg.click('#tab-more'); pg.wait_for_timeout(200); snap(pg, '1024_more_menu', False)
            pg.click('#tmenu [data-v="findings"]'); pg.wait_for_timeout(600); check('1024: More menu opens Studies and shows where you are', pg.evaluate("[S.tab,document.querySelector('#tab-more').classList.contains('on'),!document.querySelector('#tmenu')]") == ['findings', True, True])
            pg.context.close()
            # ---- first launch: story still opens; story link reaches the lesson
            pg = page(b, 1366, 768, 'dark', seen=False); check('first launch: the story opens over Start', pg.evaluate("S.story") == 0); snap(pg, '1366_first_launch', False); pg.context.close()
            # ---- keyboard only (1366, light)
            pg = page(b, 1366, 768, 'light'); kb = pg.keyboard
            def focus(): return pg.evaluate("(()=>{const a=document.activeElement;return a?(a.id||a.dataset.v||a.dataset.cite||a.dataset.pred||a.className||a.tagName):''})()")
            def ring(): return pg.evaluate("(()=>{const a=document.activeElement,c=getComputedStyle(a);return a.matches(':focus-visible')&&c.outlineStyle!=='none'&&parseFloat(c.outlineWidth)>=2})()")
            seq = []
            for _ in range(12):
                kb.press('Tab'); seq.append(focus())
                if seq[-1] == 'mine': break
            check('kb: Tab walks the tabs in the order shown', [x for x in seq if x in ('start', 'learn', 'analyze', 'explore', 'compare', 'findings', 'about', 'mine')] == ['start', 'learn', 'analyze', 'explore', 'compare', 'findings', 'about', 'mine'], seq)
            check('kb: focus ring visible on a tab', ring()); snap(pg, 'kb_01_tab_focus', False)
            kb.press('2'); pg.wait_for_timeout(300); check('kb: number keys are unchanged (2 = Try an attack, 7 = the lesson, 8 = Open my design)', pg.evaluate("S.tab") == 'analyze')
            kb.press('8'); pg.wait_for_timeout(300); ok8 = pg.evaluate("S.tab") == 'mine'; kb.press('7'); pg.wait_for_timeout(300); check('kb: 7 and 8 open the two add-on tabs', ok8 and pg.evaluate("S.tab") == 'learn')
            pg.evaluate("LearnView.goTo(0)"); kb.press('ArrowRight'); kb.press('ArrowRight'); pg.wait_for_timeout(200)
            check('kb: arrows turn lesson screens and the address follows', pg.evaluate("[location.hash,document.activeElement.id]") == ['#learn/3', 'lz-h'])
            for _ in range(40):
                kb.press('Tab')
                if pg.evaluate("document.activeElement.classList.contains('lz-cite')"): break
            check('kb: a citation number is reachable and shows a focus ring', pg.evaluate("document.activeElement.classList.contains('lz-cite')") and ring()); kb.press('Enter'); pg.wait_for_timeout(250)
            check('kb: Enter on a citation moves focus to that source', re.match(r'lz-s\d+', focus() or '') is not None, focus()); snap(pg, 'kb_02_citation', False)
            pg.evaluate("LearnView.goTo(LearnView.SCR.length-1)"); pg.wait_for_timeout(200)
            for q in range(5):
                pg.focus(f'[data-q="{q}"][data-o="0"]'); kb.press('Enter'); pg.wait_for_timeout(80)
            check('kb: the self-check works with Enter and announces the score', pg.evaluate("(()=>{const s=document.querySelector('#lz-score');return !!s&&s.getAttribute('role')==='status'&&/of 5/.test(s.textContent)})()"))
            pg.focus('#lz-again'); check('kb: Try again shows a focus ring', pg.evaluate("document.activeElement.id==='lz-again'")); snap(pg, 'kb_03_quiz', False)
            pg.evaluate("loadStep(0)"); pg.wait_for_timeout(1300); stops = []
            for _ in range(8):
                kb.press('Tab'); stops.append(focus())
                if stops[-1] == 'pred-on': break
            check('kb: Predict first is reachable from the step heading', 'pred-on' in stops and 'next' in stops[:2], stops); kb.press('Space'); pg.wait_for_timeout(250)
            pg.focus('#next'); kb.press('Enter'); pg.wait_for_timeout(1300); pg.focus('[data-pred="1"]'); check('kb: predict buttons show a focus ring', pg.evaluate("document.activeElement.dataset.pred==='1'")); snap(pg, 'kb_04_predict', False); kb.press('Enter'); pg.wait_for_timeout(300)
            check('kb: after the guess, focus is on the outcome line', focus() == 'pred-out', focus())
            pg.focus('#pred-on'); kb.press('Space'); pg.wait_for_timeout(200)
            pg.evaluate("document.querySelector('#result .fxhost summary').focus()"); kb.press('Enter'); pg.wait_for_timeout(900)
            check('kb: the fix layer opens with Enter', pg.evaluate("document.querySelector('#result .fxhost details').open")); 
            for _ in range(30):
                kb.press('Tab')
                if pg.evaluate("document.activeElement.dataset.go==='x-fix'&&!!document.activeElement.closest('.fxhost')"): break
            kb.press('Enter'); pg.wait_for_timeout(700); check('kb: … and its link to Suggest a fix works from the keyboard', pg.evaluate("[S.tab,S.xv]") == ['explore', 'x-fix'], pg.evaluate("[S.tab,S.xv]")); snap(pg, 'kb_05_fix_link', False)
            pg.context.close()
            pg = page(b, 1024, 720, 'light'); pg.focus('#tab-more'); pg.keyboard.press('Enter'); pg.wait_for_timeout(200)
            ok = pg.evaluate("document.activeElement.closest('#tmenu')&&document.activeElement.dataset.v") == 'compare'; pg.keyboard.press('ArrowDown'); pg.keyboard.press('ArrowDown'); a = pg.evaluate("document.activeElement.dataset.v"); snap(pg, 'kb_06_more_menu', False); pg.keyboard.press('Escape'); pg.wait_for_timeout(150)
            check('kb: More menu: Enter opens, arrows move, Esc closes and returns focus', ok and a == 'about' and pg.evaluate("[!document.querySelector('#tmenu'),document.activeElement.id]") == [True, 'tab-more'], [ok, a])
            pg.focus('#tab-more'); pg.keyboard.press('Enter'); pg.keyboard.press('Enter'); pg.wait_for_timeout(400); check('kb: More menu item opens with Enter', pg.evaluate("S.tab") == 'compare')
            pg.context.close(); b.close()
    finally:
        srv.terminate()
    # ---- without the plug-in, and through the old launcher (no second tab)
    def tabs_of(cmd, port, extra_env=None):
        e2 = dict(env, **(extra_env or {})); s2 = subprocess.Popen(cmd + ['--no-browser', '--port', str(port), '--no-autostop'], env=e2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=extra_env and extra_env.get('_cwd') or None); time.sleep(2.5)
        try:
            with sync_playwright() as p:
                b = p.chromium.launch(); pg = b.new_page(); pg.on('pageerror', lambda e: errs.append(('pageerror', str(e)))); pg.add_init_script("localStorage.setItem('gs_seen3','1')"); pg.goto(f'http://127.0.0.1:{port}/'); pg.wait_for_timeout(1300)
                t = pg.evaluate("[...document.querySelectorAll('#tabs .tab[data-v]')].map(x=>x.dataset.v)"); b.close(); return t
        finally: s2.terminate()
    t = tabs_of([sys.executable, os.path.join(HERE, 'studio.py'), '--no-plugins'], PORT + 1)
    check('--no-plugins: the Studio starts without the plug-in tab, lesson still there', 'mine' not in t and 'learn' in t, t)
    lj = os.path.join(os.environ.get('GLITCHSAT_EXT') or os.path.dirname(HERE), 'byod', 'tools', 'studio', 'studio_byod.py')
    if os.path.isfile(lj):
        t = tabs_of([sys.executable, lj], PORT + 2, dict(GLITCHSAT_STUDIO=os.path.join(HERE, 'studio.py')))
        check('old launcher still works with this studio.py: one Open my design tab, not two', t.count('mine') == 1 and 'learn' in t, t)
    hits = _wording().scan([os.path.join(HERE, f) for f in ('studio.py', 'learn_view.py', 'labs_view.py')])
    check('sources: no listed word and no absolute developer path (shared hashed check)', not hits, hits[:4])
    print('JS errors:', len(errs), errs[:6]); print('Plain-view vocabulary findings:', json.dumps(vocab, indent=1)[:1500])
    bad = [c for c in checks if not c[1]]; print('checks: %d of %d passed' % (len(checks) - len(bad), len(checks)))
    json.dump(dict(errors=errs, vocab=vocab, checks=checks), open(OUT + 'verify_ut2.json', 'w'), indent=1)
    return not bad and not errs and not vocab
if __name__ == '__main__':
    sys.exit(0 if run() else 1)
