"""GlitchSAT Studio 3.1: screenshots, JS-error check, Plain-view vocabulary scan, label census and behaviour checks (Playwright, Chromium).
Usage: python3 verify31.py [quick]   Screens go to shots31/. Recorded mode on the real repository (no z3, no Yosys here)."""
import sys, os, json, time, subprocess, tempfile
from playwright.sync_api import sync_playwright
SEEN3 = 'localStorage.setItem("gs_seen3","1")'   # outside the f-string: Python 3.10 and 3.11 allow no backslash there
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'shots31') + '/'
ROOT = os.environ.get('GLITCHSAT_ROOT') or os.path.normpath(os.path.join(HERE, '..', '..')); PORT = 8872
QUICK = 'quick' in sys.argv
SCAN = r"""() => {
 const bad=[[/0x[0-9a-fA-F]/,'hex'],[/\bk\s*[=≤<]/,'k bound'],[/\bT\s*=\s*\d/,'T bound'],[/\bN\s*=\s*\d/,'N bound'],[/netlist/i,'netlist'],[/synthes/i,'synthesis'],[/\b(UN)?SAT\b/,'SAT'],
  [/\$abc|\$flatten|new_n\d|boot_word|boot_ok|\bsig\b/,'net name'],[/\bYosys\b/,'Yosys'],[/\bz3\b/,'z3'],[/\bflips?\b/i,'flip'],[/\bticks?\b/i,'tick'],[/\bfaults?\b/i,'fault'],[/\bflop/i,'flop'],
  [/\bV[012]e?\b/,'V name'],[/\/home\/|\/root\/|\.sh\b|\.json\b/,'file path'],[/accept flag|the flag itself/i,'flag'],[/\bnibble\b|\bconsumer\b|\bapt 0/i,'internal word'],[/glitch-memory|bit glitch|Step the box/i,'replace artifact'],
  [/not run yet|run in progress|come back later/i,'unfinished'],[/saved plan|this build\b|saved gate list|code number/i,'old noun']];
 const out=[];const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
 while(w.nextNode()){const n=w.currentNode,p=n.parentElement;if(!p||!n.nodeValue.trim())continue;
  if(p.closest('.tech-only,.keep,code,script,style,#tip,iframe,details:not([open])>:not(summary)'))continue;
  const r=p.getClientRects();if(!r.length)continue;const cs=getComputedStyle(p);if(cs.visibility==='hidden'||cs.display==='none')continue;
  let el=p,hid=false;while(el){if(el.classList&&el.classList.contains('hidden')){hid=true;break}el=el.parentElement}if(hid)continue;
  for(const [rx,lab] of bad){const m=n.nodeValue.match(rx);if(m)out.push(lab+': '+n.nodeValue.trim().slice(0,90))}}
 return [...new Set(out)]}"""
CHIPS = r"""() => [...document.querySelectorAll('.chip')].filter(c=>c.getClientRects().length&&!c.closest('.tech-only,.hidden,details:not([open])>:not(summary)')).map(c=>c.textContent.trim().toLowerCase())"""
errs, vocab, chips, checks = [], {}, {}, []
def check(name, ok, detail=''):
    checks.append((name, bool(ok), str(detail)[:160])); print(('  ok   ' if ok else '  FAIL ') + name + (' : ' + str(detail)[:160] if detail and not ok else ''))
def start():
    env = dict(os.environ, GLITCHSAT_ROOT=ROOT, GLITCHSAT_FIRSTRUN='0', XDG_CACHE_HOME=tempfile.mkdtemp(prefix='gs31cache-'))
    p = subprocess.Popen([sys.executable, os.path.join(HERE, 'studio.py'), '--no-browser', '--port', str(PORT), '--no-autostop'], env=env, stdout=open('/tmp/gs31.log', 'w'), stderr=subprocess.STDOUT)
    time.sleep(2.0); return p
def page(b, w, h, theme, view='plain', seen=False, scheme=None):
    ctx = b.new_context(viewport={'width': w, 'height': h}, **({'color_scheme': scheme} if scheme else {})); pg = ctx.new_page()
    pg.on('pageerror', lambda e: errs.append(('pageerror', str(e)))); pg.on('console', lambda m: m.type == 'error' and errs.append(('console', m.text)))
    if theme:
        pg.add_init_script(f"try{{if(!sessionStorage.getItem('i')){{sessionStorage.setItem('i','1');localStorage.setItem('gs_predict','false');localStorage.setItem('gs_seehow','true');localStorage.setItem('gs_theme','\"{theme}\"');localStorage.setItem('gs_view','\"{view}\"');{SEEN3 if seen else ''}}}}}catch(e){{}}")
    pg.goto(f'http://127.0.0.1:{PORT}/'); pg.wait_for_timeout(1300); return pg
def scan(pg, name):
    if pg.evaluate("document.documentElement.dataset.view") != 'plain': return
    r = pg.evaluate(SCAN)
    if r: vocab[name] = r
    for c in pg.evaluate(CHIPS): chips.setdefault(c, set()).add(name)
def snap(pg, name, do_scan=True):
    pg.wait_for_timeout(350); pg.screenshot(path=OUT + name + '.png')
    if do_scan: scan(pg, name)
EXPL_PLAIN = ['x-spots', 'x-fix', 'x-forever', 'x-shots', 'x-lab', 'x-fw', 'x-rep', 'x-real']
def run():
    s = start()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            for (w, h, tag) in [(1366, 768, '1366'), (1920, 1080, '1920')]:
                for theme in ('dark', 'light'):
                    t = f'{tag}_{theme}'; full = theme == 'dark' or not QUICK
                    pg = page(b, w, h, theme)
                    for i in range(6):                              # the story, first launch
                        snap(pg, f'{t}_story{i+1}')
                        if i < 5: pg.click('#snx')
                    pg.click('#sk'); pg.wait_for_timeout(500); snap(pg, f'{t}_start')
                    pg.evaluate("document.querySelector('#v-start').scrollTop=520"); snap(pg, f'{t}_start_2'); pg.evaluate("document.querySelector('#v-start').scrollTop=99999"); snap(pg, f'{t}_start_3'); pg.evaluate("document.querySelector('#v-start').scrollTop=0")
                    pg.keyboard.press('f'); snap(pg, f'{t}_found_dialog'); pg.keyboard.press('Escape')
                    pg.keyboard.press('l'); snap(pg, f'{t}_live_dialog'); pg.keyboard.press('Escape')
                    pg.click('#h-try'); pg.wait_for_timeout(900)
                    for i in range(6):                              # the path
                        snap(pg, f'{t}_path{i+1}')
                        if full:
                            pg.evaluate("document.querySelector('#v-analyze').scrollTop=99999"); snap(pg, f'{t}_path{i+1}_lower'); pg.evaluate("document.querySelector('#v-analyze').scrollTop=0")
                        if i < 5: pg.click('#next'); pg.wait_for_timeout(900)
                    for x in EXPL_PLAIN:
                        pg.evaluate(f"openExplore('{x}')"); pg.wait_for_timeout(900); snap(pg, f'{t}_{x}')
                        if full:
                            pg.evaluate("document.querySelector('#v-explore').scrollTop=99999"); snap(pg, f'{t}_{x}_lower'); pg.evaluate("document.querySelector('#v-explore').scrollTop=0")
                    for tab in ('compare', 'findings', 'about'):
                        pg.evaluate(f"show('{tab}')"); pg.wait_for_timeout(800); snap(pg, f'{t}_{tab}')
                        if tab != 'compare':
                            pg.evaluate(f"document.querySelector('#v-{tab}').scrollTop=600"); snap(pg, f'{t}_{tab}_2'); pg.evaluate(f"document.querySelector('#v-{tab}').scrollTop=99999"); snap(pg, f'{t}_{tab}_3'); pg.evaluate(f"document.querySelector('#v-{tab}').scrollTop=0")
                    pg.keyboard.press('?'); snap(pg, f'{t}_help_keys'); pg.keyboard.press('Escape'); pg.click('#b-help'); snap(pg, f'{t}_glossary'); pg.keyboard.press('Escape')
                    # change the experiment yourself: settings changed notice, no-attack badge
                    pg.evaluate("show('analyze')"); pg.click('#setdet > summary'); pg.wait_for_timeout(200); pg.select_option('#design', 'v2'); pg.evaluate("document.querySelector('#goal button[data-v=word]').click()")
                    pg.evaluate("(()=>{const k=document.querySelector('#k');k.value=1;k.dispatchEvent(new Event('input',{bubbles:true}))})()"); pg.wait_for_timeout(250); snap(pg, f'{t}_custom_changed')
                    pg.click('#run'); pg.wait_for_timeout(1000); snap(pg, f'{t}_custom_noattack'); pg.click('#setdet > summary')
                    # Technical view
                    pg.click('#viewseg button[data-v=tech]'); pg.wait_for_timeout(300)
                    pg.evaluate("loadStep(5)"); pg.wait_for_timeout(900); snap(pg, f'{t}_tech_path6', False)
                    if full:
                        for x in ('x-spots', 'x-hw', 'x-real', 'x-forever'):
                            pg.evaluate(f"openExplore('{x}')"); pg.wait_for_timeout(800); snap(pg, f'{t}_tech_{x}', False)
                        pg.evaluate("show('findings')"); pg.wait_for_timeout(800); snap(pg, f'{t}_tech_findings', False)
                        pg.evaluate("show('about')"); pg.wait_for_timeout(500); snap(pg, f'{t}_tech_about', False)
                    pg.click('#viewseg button[data-v=plain]'); pg.wait_for_timeout(300)
                    pg.context.close()
            # ---------------- behaviour checks (1366x768, dark, Plain)
            print('behaviour checks'); pg = page(b, 1366, 768, 'dark', seen=True)
            check('start: one-minute summary present with findings', pg.evaluate("document.querySelectorAll('#found ol:not(.next) li').length") >= 4, pg.evaluate("document.querySelectorAll('#found ol:not(.next) li').length"))
            check('start: summary has "what to do next"', pg.evaluate("document.querySelectorAll('#found ol.next li').length") == 3)
            check('start: unfinished boot-check hardware card hidden in Plain', pg.evaluate("!document.querySelector('.xcard[data-x=x-hw]')"))
            check('start: one label per Explore card at most', pg.evaluate("[...document.querySelectorAll('.xcard')].every(c=>c.querySelectorAll('.chip').length<=1)"))
            check('start: legend lists six labels with a gloss (bounded added for whole-chip results)', pg.evaluate("document.querySelectorAll('.legend5 .tg .gloss').length") == 6)
            check('start: Export hidden until there is a result', pg.evaluate("document.querySelector('#b-export').classList.contains('hidden')"))
            check('start: how-to-run-live link present', pg.evaluate("!!document.querySelector('#v-start [data-go=live]')"))
            pg.click('#h-try'); pg.wait_for_timeout(900)
            check('path: focus moves to the step heading', pg.evaluate("document.activeElement&&document.activeElement.id") == 'sth2')
            pg.keyboard.press('Tab')
            check('path: Tab from the heading reaches Next step (Back is disabled on step 1)', pg.evaluate("document.activeElement&&document.activeElement.id") == 'next', pg.evaluate("document.activeElement&&(document.activeElement.id||document.activeElement.className)"))
            check('chart: glitch step selected by default', pg.evaluate("S.cursor===S.last._replay.fault_ticks[0]"), pg.evaluate("[S.cursor,S.last._replay.fault_ticks]"))
            check('chart: header names the glitch', 'value at the glitch' in pg.evaluate("document.querySelector('#wsvg').textContent"))
            check('chart: accessible name is plain', pg.evaluate("document.querySelector('#wsvg').getAttribute('aria-label')").startswith('step by step'))
            check('result: the replay is not a provenance tag', pg.evaluate("![...document.querySelectorAll('#result .chip')].some(c=>/replay/i.test(c.textContent))"))
            check('result: RECORDED has a gloss', 'saved earlier' in pg.evaluate("document.querySelector('#result .chiprow').textContent"))
            check('result: Export visible after a result', pg.evaluate("!document.querySelector('#b-export').classList.contains('hidden')"))
            pg.evaluate("loadStep(5)"); pg.wait_for_timeout(1000)
            txt = pg.evaluate("document.querySelector('#v-analyze').innerText")
            check('step 6: headline says the lock stays shut', 'stays shut' in pg.evaluate("document.querySelector('.sentence0').textContent"), pg.evaluate("document.querySelector('.sentence0').textContent"))
            check('step 6: no "accept flag" / "the flag itself" in Plain', 'accept flag' not in txt and 'the flag itself' not in txt)
            check('step 6: chart explains Shut', 'never opened' in pg.evaluate("document.querySelector('#wsvg').textContent"))
            check('step 6: map label not cropped', pg.evaluate("(()=>{const sv=document.querySelector('#msvg'),b=sv.getBBox(),vb=sv.viewBox.baseVal;return b.x+b.width<=vb.width+1})()"), pg.evaluate("(()=>{const sv=document.querySelector('#msvg'),b=sv.getBBox(),vb=sv.viewBox.baseVal;return [b.x+b.width,vb.width]})()"))
            pg.evaluate("show('start')"); pg.wait_for_timeout(300)
            check('start: button says Continue after progress', 'Continue: step' in pg.inner_text('#h-try'), pg.inner_text('#h-try'))
            pg.reload(); pg.wait_for_timeout(1300)
            check('start: progress survives a reload', 'Continue: step' in pg.inner_text('#h-try'), pg.inner_text('#h-try'))
            pg.evaluate("openExplore('x-real')"); pg.wait_for_timeout(900); rt = pg.inner_text('#xbody')
            check('real: agreement sentence', 'all 4,226' in rt, rt[:200])
            check('real: Ibex 80-vs-62 row shown as reconciled, in plain words (module README has the reconciliation)', 'under investigation' not in rt and 'reconciled' in rt and '80 of 309,580' in rt and '62 of 309,500' in rt and '40 of 154,790' in rt and '31 of 154,750' in rt and 'cannot be reproduced' in rt, rt[-900:])
            check('real: no "run in progress"', 'run in progress' not in rt.lower() and 'come back later' not in rt.lower())
            pg.evaluate("openExplore('x-forever')"); pg.wait_for_timeout(900); ft = pg.inner_text('#xbody')
            check('proved: assumptions stated on the page', 'starts normally' in ft and 'one chip plan' in ft)
            pg.evaluate("openExplore('x-hw')"); pg.wait_for_timeout(600)
            check('explore: boot-check hardware not reachable in Plain', pg.evaluate("S.xv") != 'x-hw')
            pg.click('#b-help'); pg.wait_for_timeout(300); gt = pg.inner_text('#modal')
            check('glossary: no replace artifacts', 'glitch-memory' not in gt and 'bit glitch' not in gt and 'build tool: the build tool' not in gt and 'flip-flop' in gt and 'answer signal' in gt)
            pg.keyboard.press('Escape')
            pg.evaluate("show('about')"); pg.wait_for_timeout(500); at = pg.inner_text('#v-about')
            check('about: summary, live how-to, no cache path, no Findings tab reference', 'What we found' in at and 'pip install z3-solver' in at and '/.cache' not in at and 'see Findings' not in at)
            pg.evaluate("show('findings')"); pg.wait_for_timeout(900); st = pg.inner_text('#v-findings')
            check('studies: finding first', 'need only 1 glitch' in st.split('\n')[0] + st[:900], st[:120])
            pg.context.close()
            # theme follows the system on first launch
            pg = page(b, 1366, 768, None, scheme='light'); check('theme: follows a light system on first launch', pg.evaluate("document.documentElement.dataset.theme") == 'light'); pg.context.close()
            pg = page(b, 1366, 768, None, scheme='dark'); check('theme: follows a dark system on first launch', pg.evaluate("document.documentElement.dataset.theme") == 'dark')
            # ---------------- keyboard-only pass (first launch)
            print('keyboard pass')
            check('kb: story opens with focus on Next', pg.evaluate("document.activeElement&&document.activeElement.id") == 'snx')
            for _ in range(5): pg.keyboard.press('ArrowRight')
            snap(pg, 'kb_01_story_last', False); pg.keyboard.press('Escape'); pg.wait_for_timeout(300)
            check('kb: Esc from the story puts focus on the main button', pg.evaluate("document.activeElement&&document.activeElement.id") == 'h-try', pg.evaluate("document.activeElement&&document.activeElement.id"))
            snap(pg, 'kb_02_start_focus', False); pg.keyboard.press('Enter'); pg.wait_for_timeout(1000)
            check('kb: Enter starts the path; focus on the step heading', pg.evaluate("[S.ti,document.activeElement&&document.activeElement.id]") == [0, 'sth2'])
            snap(pg, 'kb_03_step1', False)
            stops = []
            for _ in range(14):
                pg.keyboard.press('Tab'); stops.append(pg.evaluate("document.activeElement?(document.activeElement.id||document.activeElement.className||document.activeElement.tagName):''"))
            check('kb: Next step within two Tabs of the heading', 'next' in stops[:2], stops[:6])
            words = pg.evaluate("[...document.querySelectorAll('#v-analyze .term[tabindex=\"0\"]')].map(e=>e.textContent.trim().toLowerCase().replace(/s$/,''))")
            check('kb: each glossary word is a keyboard stop once per step (%d stops; was about 10)' % len(words), len(words) == len(set(words)) and len(words) <= 4, words)
            for i in range(5): pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(800)
            check('kb: arrow keys walk the six steps', pg.evaluate("S.ti") == 5 and pg.evaluate("Object.keys(S.tourRes).length") == 6, pg.evaluate("[S.ti,Object.keys(S.tourRes).length]"))
            snap(pg, 'kb_04_step6', False)
            pg.keyboard.press('Enter'); pg.wait_for_timeout(500); check('kb: Enter does not start a hidden custom run in Plain view', pg.evaluate("S.ti") == 5)
            for key, name in (('f', 'found'), ('l', 'live'), ('?', 'help'), ('s', 'story')):
                pg.keyboard.press(key); pg.wait_for_timeout(250); ok = pg.evaluate("!!document.querySelector('#modal .dlg')"); snap(pg, f'kb_05_{name}', False); pg.keyboard.press('Escape'); pg.wait_for_timeout(150)
                check(f'kb: key {key} opens a dialog and Esc closes it', ok and pg.evaluate("!document.querySelector('#modal .dlg')"))
            for i, tab in enumerate(['start', 'analyze', 'explore', 'compare', 'findings', 'about']):
                pg.keyboard.press(str(i + 1)); pg.wait_for_timeout(350)
                if pg.evaluate("S.tab") != tab: check(f'kb: key {i+1} opens {tab}', False, pg.evaluate("S.tab"))
            check('kb: keys 1-6 switch tabs', pg.evaluate("S.tab") == 'about')
            pg.keyboard.press('v'); pg.wait_for_timeout(300); check('kb: V switches to Technical', pg.evaluate("S.view") == 'tech'); pg.keyboard.press('v')
            pg.keyboard.press('t'); pg.wait_for_timeout(200); check('kb: T switches the theme', pg.evaluate("document.documentElement.dataset.theme") == 'light')
            pg.context.close(); b.close()
    finally:
        s.terminate()
    five = {'live', 'recorded', 'simulated', 'bounded', 'proved', 'estimate'}   # the six labels (bounded: whole chip, exact within T steps)
    extra = {k: sorted(v)[:4] for k, v in chips.items() if k not in five}
    print('JS errors:', len(errs)); [print('  ', e) for e in errs[:20]]
    print('Plain-view vocabulary findings:', sum(len(v) for v in vocab.values()))
    for k, v in vocab.items(): print('  ', k, v[:8])
    print('Distinct labels seen in Plain view:', sorted(chips), '| outside the five:', extra)
    bad = [c for c in checks if not c[1]]
    print('Behaviour checks: %d of %d passed' % (len(checks) - len(bad), len(checks)))
    json.dump(dict(errors=errs, vocab=vocab, labels={k: sorted(v) for k, v in chips.items()}, checks=checks), open(OUT + 'verify31.json', 'w'), indent=1)
run()
