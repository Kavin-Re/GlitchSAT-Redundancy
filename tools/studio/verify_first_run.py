"""Checks for the welcome story "Why GlitchSAT?" and Presenter mode (first_run_view.py): Playwright/Chromium, light and
dark, 1366x768 and 375x812, 200 % zoom, reduced motion, keyboard only, the notes window. Screens go to shots_first_run/.
The Studio runs live when z3 and Yosys are installed, else in recorded mode; both give the same numbers.
Usage: python3 verify_first_run.py   ($STUDIO_PY may point to another copy of studio.py, for trying the hook)"""
import os, re, sys, json, time, subprocess, tempfile
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'shots_first_run') + '/'
ROOT = os.environ.get('GLITCHSAT_ROOT') or os.path.normpath(os.path.join(HERE, '..', '..')); PORT = 8885          # its own port: verify_ut2 uses 8881, verify_labs 8883
STUDIO = os.environ.get('STUDIO_PY') or os.path.join(HERE, 'studio.py')
os.makedirs(OUT, exist_ok=True)
errs, checks = [], []
URL = f'http://127.0.0.1:{PORT}/'

def check(name, ok, detail=''):
    checks.append((name, bool(ok), str(detail)[:240])); print(('  ok   ' if ok else '  FAIL ') + name + ('' if ok else ' : ' + str(detail)[:240]))

def ctx(b, w=1366, h=768, theme='light', rm=None, fr=None, pred=True):
    c = b.new_context(viewport={'width': w, 'height': h}, reduced_motion=rm or 'no-preference')
    init = (f"localStorage.setItem('gs_predict','false');" if pred else '') + f"localStorage.setItem('gs_seehow','true');localStorage.setItem('gs_theme','\"{theme}\"');localStorage.setItem('gs_view','\"plain\"');"
    if fr: init += "localStorage.setItem('gs_fr_seen',JSON.stringify(%s));" % json.dumps(fr)
    c.add_init_script("try{if(!sessionStorage.getItem('i')){sessionStorage.setItem('i','1');%s}}catch(e){}" % init)
    return c

def newpage(c, path=''):
    pg = c.new_page(); pg.on('pageerror', lambda e: errs.append(('pageerror', str(e)))); pg.on('console', lambda m: m.type == 'error' and errs.append(('console', m.text)))
    pg.goto(URL + path); pg.wait_for_timeout(1500); return pg

def snap(pg, name):
    pg.wait_for_timeout(250); pg.screenshot(path=OUT + name + '.png')

def heading(pg):
    return pg.evaluate("(document.querySelector('#fr-h')||{}).textContent||null")

def res(pg):
    return pg.evaluate("(document.querySelector('#fr .fr-res')||{}).innerText||''")

def wait_res(pg, rx, ms=20000):
    t = time.time()
    while time.time() - t < ms / 1000:
        if re.search(rx, res(pg)): return True
        pg.wait_for_timeout(200)
    return False

CONTRAST = r"""(sel)=>{const lum=c=>{const m=c.match(/[\d.]+/g).map(Number);const f=v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)};return .2126*f(m[0])+.7152*f(m[1])+.0722*f(m[2])};
 const bgOf=e=>{for(let x=e;x;x=x.parentElement){const b=getComputedStyle(x).backgroundColor;const m=b.match(/[\d.]+/g);if(m&&(m.length<4||+m[3]>0.9))return b}return 'rgb(255,255,255)'};
 return [...document.querySelectorAll(sel)].filter(e=>e.offsetParent!==null).map(e=>{const a=lum(getComputedStyle(e).color),b=lum(bgOf(e));const r=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);return [e.textContent.trim().slice(0,30),Math.round(r*100)/100]})}"""

def run():
    env = dict(os.environ, GLITCHSAT_ROOT=ROOT, XDG_CACHE_HOME=tempfile.mkdtemp(prefix='gsfrcache-'))
    srv = subprocess.Popen([sys.executable, STUDIO, '--no-browser', '--port', str(PORT), '--no-autostop'], env=env, stdout=open('/tmp/gsfr.log', 'w'), stderr=subprocess.STDOUT)
    time.sleep(2.2)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            facts = json.loads(subprocess.run(['curl', '-s', URL + 'api/firstrun/facts'], capture_output=True, text=True).stdout or '{}')
            check('facts: all sixteen facts are served', len(facts) == 16, sorted(facts))
            # 1. first launch: the welcome, not the old story; Skip; reload; a second browser (server flag)
            c = ctx(b); pg = newpage(c)
            check('first launch opens the welcome, not the old story', pg.evaluate("[!!document.querySelector('#fr:not([hidden]) .fr-card'),S.story]") == [True, None])
            check('focus starts on the heading', pg.evaluate("document.activeElement.id") == 'fr-h')
            check('dialog is labelled by its heading and is modal', pg.evaluate("(d=>[d.getAttribute('role'),d.getAttribute('aria-modal'),d.getAttribute('aria-labelledby')])(document.querySelector('#fr .fr-card'))") == ['dialog', 'true', 'fr-h'])
            check('Skip is visible on screen 1', pg.is_visible('#fr-skip'))
            pg.click('#fr-skip'); pg.wait_for_timeout(300)
            check('Skip closes it and focus returns to the top-bar link', pg.evaluate("[document.querySelector('#fr').hidden,document.activeElement.id]") == [True, 'b-why'])
            pg.reload(); pg.wait_for_timeout(1500)
            check('a reload does not show it again', pg.evaluate("[!!document.querySelector('#fr:not([hidden]) .fr-card'),S.story]") == [False, None])
            c.close()
            c = ctx(b); pg = newpage(c)
            check('a new browser profile on the same Studio does not show it again (server flag)', pg.evaluate("[!!document.querySelector('#fr:not([hidden]) .fr-card'),S.story]") == [False, None])
            check('top bar has the "Why GlitchSAT?" link and the header does not overflow', pg.is_visible('#b-why') and pg.evaluate("(h=>h.scrollWidth<=h.clientWidth+1)(document.querySelector('header'))"))
            check('Start has the "Why GlitchSAT?" line', pg.is_visible('#v-start .fr-startline [data-go="why"]'))
            pg.evaluate("show('about')"); pg.wait_for_timeout(300)
            check('About has "Show the welcome again"', pg.is_visible('#fr-reset'))
            c.close()
            c = ctx(b); pg = newpage(c, '?firstrun=0')
            check('?firstrun=0 (for test harnesses) keeps the old first-launch story and no welcome', pg.evaluate("[S.story,!!document.querySelector('#fr:not([hidden]) .fr-card')]") == [0, False])
            c.close()
            # 2-3. the nine screens, light and dark, 1366 and 375, live results
            for theme in ('light', 'dark'):
                for (w, h, tag) in ((1366, 768, '1366'), (375, 812, '375')):
                    t = f'{tag}_{theme}'; c = ctx(b, w, h, theme); pg = newpage(c, '?fresh=1')
                    check(f'{t}: ?fresh=1 opens the welcome', heading(pg) == 'Can a tiny glitch open a lock?')
                    snap(pg, f'{t}_s1_before'); pg.click('#fr-act')
                    check(f'{t}: screen 1 Glitch it shows "1 flip"', wait_res(pg, r'^1 flip') and 'One flipped signal opened the lock' in res(pg), res(pg))
                    check(f'{t}: screen 1 result has a label and its source file', 'results/reproduce_summary.json' in res(pg) and re.search(r'(?i)measured|recorded', res(pg)))
                    snap(pg, f'{t}_s1'); pg.click('#fr-next'); pg.wait_for_timeout(250)
                    check(f'{t}: screen 2 is "How a glitch attack works", 2 of 9', heading(pg) == 'How a glitch attack works' and pg.inner_text('.fr-kick').endswith('2 of 9'))
                    snap(pg, f'{t}_s2_how_step1')
                    for j in range(3):
                        pg.click('#fr-act'); pg.wait_for_timeout(150)
                        if j == 0: snap(pg, f'{t}_s2_how_step2')
                    txt = pg.inner_text('#fr .fr-card')
                    check(f'{t}: how: four steps and the bridge sentence', all(x in txt for x in ('A chip runs on clock ticks.', 'flip-flop', 'short dip in the power', 'too short', 'electromagnetic pulse', 'one bit flips', 'say yes to a wrong key', 'GlitchSAT doesn’t use real hardware.', 'It models step 3: it flips a wire’s value for one clock tick in the design, and asks a solver for the fewest flips that make the check say yes.')), txt[:200])
                    check(f'{t}: how: links to the sourced real cases in the lesson', pg.is_visible('#fr [data-go="learn:5"]'))
                    pg.click('#fr-real'); pg.wait_for_timeout(250)
                    check(f'{t}: how: "See 6 real attacks" shows six cards, each with Why it matters and a source', pg.evaluate("[document.querySelectorAll('#fr .fr-rc').length,document.querySelectorAll('#fr .fr-rc .why').length,document.querySelectorAll('#fr .fr-rc .src a').length]") == [6, 6, 6] and heading(pg) == 'Real attacks: glitches that worked')
                    snap(pg, f'{t}_s2_real'); pg.click('#fr-next'); pg.wait_for_timeout(250)
                    check(f'{t}: how: "Back to the story" returns to screen 2', heading(pg) == 'How a glitch attack works')
                    sayvis = "(b=>!!b&&!b.hidden&&b.getClientRects().length>0)(document.querySelector('#fr-saybox'))"
                    check(f'{t}: Say-this lines hidden by default (no .fr-say on the audience screen)', not pg.evaluate(sayvis) and not pg.evaluate("!!document.querySelector('#fr details.fr-say')"))
                    pg.keyboard.press('Control+f'); pg.wait_for_timeout(150); on1 = pg.evaluate(sayvis); txt1 = pg.evaluate("(document.querySelector('#fr-saybox')||{}).textContent||''")
                    pg.keyboard.press('Control+f'); pg.wait_for_timeout(150); off1 = not pg.evaluate(sayvis)
                    pg.keyboard.press('s'); pg.wait_for_timeout(150); on2 = pg.evaluate(sayvis); pg.keyboard.press('S'); pg.wait_for_timeout(150); off2 = not pg.evaluate(sayvis)
                    check(f'{t}: Ctrl+F and S show and hide the Say-this line (and the story stays put)', on1 and off1 and on2 and off2 and txt1.startswith('Say this:') and heading(pg) == 'How a glitch attack works', [on1, off1, on2, off2, txt1[:40]])
                    g = pg.locator('#fr .fr-glitch').bounding_box(); tk = pg.evaluate("(()=>{const s=document.querySelector('.fr-gsvg'),p=s.createSVGPoint();p.x=330;p.y=162;const q=p.matrixTransform(s.getScreenCTM());return [q.x,q.y]})()")
                    pg.mouse.move(g['x'] + g['width'] / 2, g['y'] + g['height'] / 2); pg.mouse.down(); pg.mouse.move(tk[0] - 30, tk[1], steps=6); pg.mouse.move(tk[0], tk[1], steps=3); pg.mouse.up(); pg.wait_for_timeout(2600)
                    check(f'{t}: how: dragging the glitch onto tick 3 flips one bit and opens the lock', res(pg).startswith('1 bit flipped') and 'check cell kept the wrong value' in res(pg) and pg.evaluate("document.querySelector('.fr-gsvg').getAttribute('aria-label')").startswith('Frame 4'), res(pg)[:120])
                    snap(pg, f'{t}_s2_how_hit')
                    pg.focus('#fr .fr-glitch'); pg.keyboard.press('ArrowLeft'); pg.keyboard.press('Enter'); pg.wait_for_timeout(300)
                    check(f'{t}: how: keyboard moves the glitch; tick 2 misses', res(pg).startswith('nothing happened') and 'tick 2' in res(pg) and heading(pg) == 'How a glitch attack works', res(pg)[:100])
                    pg.click('#fr-next'); pg.wait_for_timeout(250)
                    txt = pg.inner_text('#fr .fr-card')
                    check(f'{t}: screen 3 shows the real Verilog of V0 and V2 side by side, with line numbers and sources', heading(pg) == 'How a chip protects itself, in its code' and "assign m = (a == 8'hC3);" in txt and 'cmp8 c0(.a(sig), .m(m0)); cmp8 c1(.a(sig), .m(m1)); cmp8 c2(.a(sig), .m(m2));' in txt and 'rtl/v0.v' in txt and 'rtl/v2.v' in txt and pg.evaluate("document.querySelectorAll('#fr .fr-codebox .ln.hl').length") >= 3, txt[:200])
                    check(f'{t}: screen 3 lists five other protection techniques, labelled as techniques, with links', pg.evaluate("document.querySelectorAll('#fr .fr-ways li .fr-tech').length") == 5 and all(x in txt for x in ('Sparse state codes.', 'Multi-bit yes/no signals.', 'Redundant counters.', 'Lockstep.', 'In software.')) and pg.is_visible('#fr .fr-ways [data-go="x-real"]'))
                    snap(pg, f'{t}_s3_code'); pg.click('#fr-act'); pg.wait_for_timeout(200)
                    check(f'{t}: screen 3 "See what the build tool made of it" ties to one weak point and the stored code, with a link to the gate-level view', 'three guards that share one weak point are really one guard' in res(pg) and 'Changing it to 0xA5 restored 3 flips' in res(pg) and 'WHY_TWO_FLIPS.md' in res(pg) and pg.is_visible('#fr .fr-res [data-go="p2"]'), res(pg)[:200])
                    snap(pg, f'{t}_s3_code_built')
                    pg.click('#fr-next'); wait_res(pg, r'flip')
                    got = [re.match(r'(\d+) flip', res(pg)).group(1)]
                    for j in (1, 2):
                        pg.click(f'#fr-seg2 [data-sel="{j}"]'); wait_res(pg, r'Still|three' if j == 1 else r'all three')
                        got.append(re.match(r'(\d+) flip', res(pg)).group(1))
                        if j == 1:
                            check(f'{t}: screen 4 "2 copies" names the shared wire', 'shared wire (ok)' in res(pg), res(pg)); snap(pg, f'{t}_s4_two')
                    check(f'{t}: screen 4 toggles give 1 / 1 / 3', got == ['1', '1', '3'], got); snap(pg, f'{t}_s5')
                    pg.click('#fr-next'); wait_res(pg, r'fault')
                    got = [re.match(r'(\d+) fault', res(pg)).group(1)]
                    for j in (1, 2):
                        pg.click(f'#fr-seg3 [data-sel="{j}"]'); pg.wait_for_timeout(150); got.append(re.match(r'(\d+) fault', res(pg)).group(1))
                    check(f'{t}: screen 5 (PicoSoC boot check by build) gives 3 / 2 / 1 faults, labelled bounded, from soc/README.md', got == ['3', '2', '1'] and 'soc/README.md' in res(pg) and 'BOUNDED' in res(pg).upper(), (got, res(pg)[:160]))
                    txt = pg.inner_text('#fr .fr-card')
                    check(f'{t}: screen 5 has the corrected claim, SYNFI credit and evidence links',
                          'The answer belongs to the finished design, not the source.' in txt and 'Only the last build merged the copies: design tools can weaken a protection without telling you, so check the finished design.' in txt
                          and 'we were not first' in txt and 'SYNFI, a published tool from the OpenTitan project, showed before us that synthesis can merge copies.' in txt
                          and 'compiler at -O2 turned three copies of a check into one; 90 of 108 builds' in txt and 'firmware/README.md' in txt and 'masking/README.md' in txt
                          and 'WHY_TWO_FLIPS' not in txt and 'merged them' in txt, txt[:300])
                    snap(pg, f'{t}_s5'); pg.click('#fr-next'); pg.wait_for_timeout(200)
                    cards = []
                    for j in range(3):
                        cards.append(pg.inner_text('#fr .fr-cardx'))
                        snap(pg, f'{t}_s6_chip{j+1}'); pg.click('#fr-act'); pg.wait_for_timeout(150)
                    check(f'{t}: screen 6 cycles three chips, each with a label', all(re.search(r'(?i)bounded', x) for x in cards) and '4,226 of 4,226' in cards[0] and '3, 2 or 1 fault' in cards[1] and '3 faults' in cards[2], [x[:60] for x in cards])
                    check(f'{t}: screen 6 wraps back to chip 1', 'OpenTitan' in pg.inner_text('#fr .fr-cardx'))
                    pg.click('#fr-next'); pg.wait_for_timeout(200)
                    for j in range(4): pg.click('#fr-act'); pg.wait_for_timeout(80)
                    txt = pg.inner_text('#fr .fr-card')
                    check(f'{t}: screen 7 reveals five steps and the end line', 'Changing 0xCC to 0xA5 brought back 3 flips' in txt and 'The design tool was not the cause' in txt and '0x96' in txt and 'Across 264 build settings, the three-copy lock needed 1 flip in 180, 2 in 60 and 3 in 24.' in txt and 'three guards that share one weak point are really one guard' in txt and 'WHY_TWO_FLIPS.md' in txt, txt[-300:])
                    snap(pg, f'{t}_s8'); pg.click('#fr-next'); pg.wait_for_timeout(200); pg.click('[data-chip="BOUNDED"]'); pg.wait_for_timeout(150)
                    txt = pg.inner_text('#fr .fr-card')
                    check(f'{t}: screen 8 has the exact scope wording and the BOUNDED sentence', 'Today it checks one family of risks: fault injection (glitches).' in txt and 'planned, not built' in txt and 'never means “secure”' in txt and 'No claim that the method is new.' in txt)
                    snap(pg, f'{t}_s7'); pg.click('#fr-next'); pg.wait_for_timeout(200)
                    check(f'{t}: screen 9 has four doors and "Present this"', pg.evaluate("document.querySelectorAll('#fr [data-door]').length") == 4 and pg.is_visible('#fr-present'))
                    snap(pg, f'{t}_s9')
                    wide = pg.evaluate("(c=>[c.scrollWidth<=c.clientWidth+1,document.querySelector('#fr').scrollWidth<=document.querySelector('#fr').clientWidth+1])(document.querySelector('#fr .fr-card'))")
                    check(f'{t}: no sideways scrolling', all(wide), wide)
                    if tag == '1366':
                        chips = pg.evaluate(CONTRAST, '#fr .chip, #fr .fr-doors span, #fr .fr-small, #fr .fr-lead')
                        pg.evaluate("FirstRun.goScreen(4)"); wait_res(pg, r'fault'); chips += pg.evaluate(CONTRAST, '#fr .chip, #fr .fr-src, #fr .fr-small a, #fr .fr-small')
                        pg.evaluate("FirstRun.goScreen(1)"); pg.wait_for_timeout(200); chips += pg.evaluate(CONTRAST, '#fr .fr-how li, #fr .fr-small, #fr .fr-act')
                        low = [x for x in chips if x[1] < 4.5]
                        check(f'{t}: text and label chips reach 4.5:1 contrast ({len(chips)} checked)', not low, low[:5])
                    pg.click('#fr-skip'); c.close()
            # recorded fallback: the analysis call fails; the predicted number still shows, labelled recorded
            c = ctx(b); pg = c.new_page(); pg.on('pageerror', lambda e: errs.append(('pageerror', str(e))))
            pg.route('**/api/analyze', lambda r: r.abort()); pg.goto(URL + '?fresh=1'); pg.wait_for_timeout(1500)
            pg.click('#fr-act'); wait_res(pg, r'flip')
            check('fallback: a failed live call shows the recorded "1 flip" with the label recorded', res(pg).startswith('1 flip') and 'RECORDED' in res(pg).upper() and 'recorded value shown' in res(pg), res(pg))
            snap(pg, '1366_light_s1_fallback'); c.close()
            # 4. resume: close on screen 5, reload -> toast; #why/7
            c = ctx(b); pg = newpage(c, '?fresh=1'); pg.evaluate("api.post('/api/firstrun/seen',{seen:false,screen:0})"); pg.wait_for_timeout(200)
            pg.click('#fr-next'); pg.click('#fr-next'); pg.click('#fr-next'); pg.click('#fr-next'); pg.wait_for_timeout(400)
            pg.goto(URL); pg.wait_for_timeout(1800)
            check('resume: after leaving on screen 5, a toast offers "screen 5 of 9" and the story does not reopen', pg.is_visible('#fr-toast') and 'screen 5 of 9' in pg.inner_text('#fr-toast') and not pg.evaluate("!!document.querySelector('#fr:not([hidden]) .fr-card')"))
            snap(pg, '1366_light_resume_toast')
            pg.click('#fr-cont'); pg.wait_for_timeout(500)
            check('resume: Continue opens screen 5', heading(pg) == 'But the finished design can be different')
            pg.keyboard.press('Escape'); pg.wait_for_timeout(200)
            pg.goto(URL + '#why/7'); pg.wait_for_timeout(1500)
            check('#why/7 opens screen 7', heading(pg) == 'We changed our minds, on purpose')
            pg.keyboard.press('Escape'); pg.wait_for_timeout(400); c.close()
            # 5. keyboard only
            c = ctx(b, theme='dark'); pg = newpage(c, '?fresh=1'); ok = []
            for i in range(8):
                pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(250)
                ok.append(pg.evaluate("[document.activeElement.id,document.querySelector('.fr-kick').textContent]") == ['fr-h', f'Why GlitchSAT? · {i+2} of 9'])
            check('keyboard: ArrowRight goes through all 9 screens and focus is on the heading after each', all(ok), ok)
            pg.keyboard.press('ArrowLeft'); pg.wait_for_timeout(200)
            check('keyboard: ArrowLeft goes back', heading(pg) == 'What it checks today, and what it doesn’t')
            names, n = [], 0
            for _ in range(30):
                pg.keyboard.press('Tab'); n += 1
                names.append(pg.evaluate("document.activeElement.id||document.activeElement.textContent.trim().slice(0,20)"))
                if not pg.evaluate("document.querySelector('#fr').contains(document.activeElement)"): break
            check('keyboard: Tab stays inside the dialog (focus trap)', pg.evaluate("document.querySelector('#fr').contains(document.activeElement)"), names[-3:])
            check('keyboard: Tab reaches Skip, the label chips, Back, Show me and Next', all(x in names for x in ('fr-skip', 'PROVED', 'fr-back', 'fr-show', 'fr-next')), names)
            pg.goto(URL + '?fresh=1'); pg.wait_for_timeout(1500); pg.focus('#fr-act'); pg.keyboard.press('Enter'); wait_res(pg, r'flip')
            check('keyboard: Enter on "Glitch it" runs it', res(pg).startswith('1 flip'))
            pg.keyboard.press('ArrowRight'); pg.keyboard.press('ArrowRight'); pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(300); pg.focus('#fr-seg2 [data-sel="0"]'); pg.keyboard.press('ArrowRight'); wait_res(pg, r'Still')
            check('keyboard: arrows inside the copies toggle move the toggle, not the screen', heading(pg) == 'Engineers add copies. Do copies help?' and pg.evaluate("document.activeElement.dataset.sel") == '1', res(pg))
            pg.keyboard.press('v'); pg.keyboard.press('1'); pg.wait_for_timeout(150)
            check('keyboard: the Studio keys (v, 1) do nothing while the welcome is open', pg.evaluate("[S.view,!!document.querySelector('#fr:not([hidden])')]") == ['plain', True])
            pg.keyboard.press('Escape'); pg.wait_for_timeout(200)
            check('keyboard: Esc closes and focus returns', pg.evaluate("[document.querySelector('#fr').hidden,document.activeElement.id]") == [True, 'b-why'])
            pg.keyboard.press('Enter'); pg.wait_for_timeout(500)
            check('keyboard: Enter on the top-bar link opens the story again', heading(pg) == 'Can a tiny glitch open a lock?')
            pg.keyboard.press('Escape'); pg.wait_for_timeout(400); c.close()
            # 6. Presenter mode: 12 stops through the real views, one key
            c = ctx(b, 1366, 768, 'dark', fr={'v': 1, 'screen': 0, 'done': True}, pred=False); pg = newpage(c); pg.wait_for_function("S.status&&S.story!=null"); pg.keyboard.press('p'); pg.wait_for_timeout(800)   # pred=False: a new profile, Predict first on (B-1)
            check('presenter: P enters (html.present, stop 1 of 12)', pg.evaluate("document.documentElement.classList.contains('present')") and 'stop 1 of 12' in pg.inner_text('#fr-pbar'), pg.evaluate("[document.documentElement.className,S.story,!!FirstRun.FR.P,(document.querySelector('#fr-pbar')||{}).innerText]"))
            check('presenter: no "Say this" cue and no Skip in the audience window', not pg.evaluate("!!document.querySelector('#fr .fr-say,#fr-skip')") and not pg.evaluate("(b=>!!b&&!b.hidden)(document.querySelector('#fr-saybox'))"))
            pg.keyboard.press('Control+f'); pg.wait_for_timeout(150); pon = pg.evaluate("(b=>!!b&&!b.hidden&&(b.textContent||'').includes('toy lock'))(document.querySelector('#fr-saybox'))")
            pg.keyboard.press('s'); pg.wait_for_timeout(150); poff = pg.evaluate("(b=>!b||b.hidden)(document.querySelector('#fr-saybox'))")
            check('presenter: Ctrl+F shows the Say-this line of the stop, S hides it, the stop does not change', pon and poff and pg.evaluate("[FirstRun.FR.P.k,FirstRun.FR.P.step]") == [0, 0], [pon, poff])
            snap(pg, 'present_dark_stop1'); seen, views = [], []
            want = [None, None, None, None, None, None, 'v-learn', 'v-analyze', 'v-explore', 'v-mine', 'v-findings', None]
            for k in range(12):
                st = pg.evaluate("FirstRun.FR.P&&[FirstRun.FR.P.k,FirstRun.FR.P.step]"); seen.append(st)
                acts = pg.evaluate("(s=>s.kind==='story'?(FirstRun.SCR[s.i].acts||[]).length:(s.acts||[]).length)(FirstRun.STOPS[FirstRun.FR.P.order[FirstRun.FR.P.k]])")
                vis = pg.evaluate("[...document.querySelectorAll('main .view')].filter(v=>!v.classList.contains('hidden')).map(v=>v.id)[0]||null")
                if want[k]: views.append((k + 1, vis == want[k] and not pg.evaluate("!!document.querySelector('#fr:not([hidden])')"), vis))
                if k == 8: views.append(('x-chip', pg.evaluate("S.xv") == 'x-chip' and pg.evaluate("S.chipSel") == 'picosoc', pg.evaluate("S.xv")))
                if k in (1, 2, 3, 5): check(f'presenter B-3: stop {k+1} arrives scrolled to the top', pg.evaluate("document.querySelector('#fr').scrollTop") == 0)
                if k == 2:
                    check('presenter: stop 3 shows the real attacks (six cards, each with a Why it matters line and a source link)', pg.evaluate("[document.querySelectorAll('#fr .fr-rc').length,document.querySelectorAll('#fr .fr-rc .why').length,document.querySelectorAll('#fr .fr-rc .src a[href^=\"https://\"]').length]") == [6, 6, 6], pg.evaluate("document.querySelectorAll('#fr .fr-rc').length"))
                if k == 5:
                    pg.keyboard.press('ArrowDown'); pg.wait_for_timeout(200)
                    check('presenter: Down arrow scrolls the card and stays on the stop', pg.evaluate("[document.querySelector('#fr').scrollTop>0,FirstRun.FR.P.k,FirstRun.FR.P.step]") == [True, 5, 0])
                    pg.keyboard.press('ArrowUp'); pg.wait_for_timeout(200)
                if k == 7:
                    pg.wait_for_timeout(1500)
                    check('presenter B-1: stop 8 does not ask for a prediction (no blurred result)', pg.evaluate("[S.predOn,typeof predPending==='function'?predPending():null,!!document.querySelector('#v-analyze .predict .blur,#v-analyze [data-pred]')]") == [False, False, False], pg.evaluate("[S.predOn,typeof predPending==='function'?predPending():null]"))
                if k == 8:
                    pg.wait_for_timeout(800)
                    check('presenter S-4: stop 9 scrolls the 3 / 2 / 1 line into view', pg.evaluate("(e=>{if(!e)return null;const r=e.getBoundingClientRect(),pb=document.querySelector('#fr-pbar'),lim=pb&&!pb.hidden?pb.getBoundingClientRect().top:innerHeight;return r.top>=0&&r.bottom<=lim+1})(document.querySelector('#v-explore .take'))") is True)
                    pg.keyboard.press('ArrowDown'); pg.wait_for_timeout(200)
                    check('presenter: Down arrow in an app stop does not change the stop', pg.evaluate("FirstRun.FR.P.k") == 8)
                if k == 10:
                    check('presenter S-3: "Run all studies" is hidden in Presenter mode', not pg.evaluate("(b=>!!b&&b.offsetParent!==null)(document.querySelector('#f-all'))"))
                if k == 6: views.append(('learn:8', 'hidden danger' in (pg.evaluate("(document.querySelector('#lz-h')||{}).textContent||''").lower()), ''))
                for a in range(acts):
                    pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(900)
                    if k == 1 and a == 2:
                        check('presenter B-3: stop 2, third press: the bridge line it reveals is scrolled into view', pg.evaluate("(e=>{if(!e)return null;const r=e.getBoundingClientRect(),pb=document.querySelector('#fr-pbar'),lim=pb&&!pb.hidden?pb.getBoundingClientRect().top:innerHeight;return r.top>=0&&r.bottom<=lim+1})(document.querySelector('#fr .fr-bridge'))") is True, pg.evaluate("document.querySelector('#fr').scrollTop"))
                    if k == 1 and a == 3:
                        check('presenter B-3: stop 2, fourth press: the result line is in view', pg.evaluate("(e=>{if(!e)return null;const r=e.getBoundingClientRect(),pb=document.querySelector('#fr-pbar'),lim=pb&&!pb.hidden?pb.getBoundingClientRect().top:innerHeight;return r.top>=0&&r.bottom<=lim+1})(document.querySelector('#fr .fr-res p'))") is True)
                    if k == 3 and a == 0:
                        check('presenter B-3: stop 4, first press: the build text it reveals is scrolled into view', pg.evaluate("(e=>{if(!e)return null;const r=e.getBoundingClientRect(),pb=document.querySelector('#fr-pbar'),lim=pb&&!pb.hidden?pb.getBoundingClientRect().top:innerHeight;return r.top>=0&&r.bottom<=lim+1})(document.querySelector('#fr .fr-res .fr-bridge'))") is True, pg.evaluate("document.querySelector('#fr').scrollTop"))
                    if k == 1 and a == 3:
                        check('presenter: stop 2 (how a glitch attack works): three → reveal the steps, the fourth drops the glitch on the right tick', res(pg).startswith('1 bit flipped'), res(pg)[:80])
                    if k == 0 and a == 0:
                        wait_res(pg, r'flip'); check('presenter: the first → on stop 1 runs "Glitch it" and stays on the stop', res(pg).startswith('1 flip') and pg.evaluate("FirstRun.FR.P.k") == 0)
                    if k == 3 and a == 1:
                        check('presenter: stop 4 (code): → reveals the build, → opens the gate-level view of the three copies', pg.evaluate("[S.tab,S.ti]") == ['analyze', 2], pg.evaluate("[S.tab,S.ti]"))
                        check('presenter B-2: stop 4, second press: the story card closes so the gate view is in front', pg.evaluate("[document.querySelector('#fr').hidden,!document.querySelector('#v-analyze').classList.contains('hidden'),FirstRun.FR.P.k]") == [True, True, 3], pg.evaluate("[document.querySelector('#fr').hidden,FirstRun.FR.P.k]"))
                    if k == 4 and a == 1:
                        wait_res(pg, r'all three'); check('presenter: stop 5 → → gives 3 copies', res(pg).startswith('3 flips'))
                    if k == 5 and a == 1:
                        check('presenter: stop 6 → → steps the build from 3 to 2 to 1 fault', res(pg).startswith('1 fault'), res(pg)[:60])
                pg.wait_for_timeout(700 if k in (3, 7, 9) else 300)
                snap(pg, f'present_dark_stop{k+1}')
                if k < 11: pg.keyboard.press('PageDown'); pg.wait_for_timeout(700)
            check('presenter: twelve stops in order, reached with one key', [s[0] for s in seen] == list(range(12)), seen)
            check('presenter: stops 7-11 show the real views (lesson, Try an attack, Explore x-chip PicoSoC, Open my design, Studies)', all(v[1] for v in views), views)
            check('presenter: stop 12 is the close (scope, limits, doors)', 'Today it checks one family of risks' in pg.inner_text('#fr') and pg.evaluate("document.querySelectorAll('#fr [data-door]').length") == 4)
            pg.keyboard.press('b'); pg.wait_for_timeout(150); blank = pg.is_visible('#fr-blank'); pg.keyboard.press('b'); pg.wait_for_timeout(150)
            check('presenter: B blanks the screen and B brings it back', blank and not pg.is_visible('#fr-blank'))
            pg.keyboard.press('Home'); pg.wait_for_timeout(400)
            check('presenter: Home goes to stop 1', pg.evaluate("FirstRun.FR.P.k") == 0)
            pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
            check('presenter B-1: leaving gives back the stored Predict-first choice', pg.evaluate("S.predOn") is None, pg.evaluate("S.predOn"))
            check('presenter: Esc leaves (no html.present, no bar, Start shown)', pg.evaluate("[document.documentElement.classList.contains('present'),!!document.querySelector('#fr-pbar:not([hidden])'),S.tab]") == [False, False, 'start'])
            pg.evaluate("FirstRun.FR.st={};FirstRun.open(1)"); pg.wait_for_timeout(300)
            for _ in range(3): pg.click('#fr-act'); pg.wait_for_timeout(150)
            pg.evaluate("FirstRun.goScreen(2)"); pg.wait_for_timeout(200); pg.click('#fr-act'); pg.wait_for_timeout(200)
            pg.evaluate("FirstRun.goScreen(4)"); pg.wait_for_timeout(200); pg.click('#fr-seg3 [data-sel="2"]'); pg.wait_for_timeout(200)
            pg.keyboard.press('Escape'); pg.wait_for_timeout(200); pg.keyboard.press('p'); pg.wait_for_timeout(800)
            pg.evaluate("FirstRun.enterStop(1)"); pg.wait_for_timeout(400)
            s2 = pg.evaluate("[document.querySelectorAll('#fr .fr-how li.on').length,!!document.querySelector('#fr .fr-bridge')]")
            pg.evaluate("FirstRun.enterStop(3)"); pg.wait_for_timeout(400); s3 = pg.evaluate("!!document.querySelector('#fr .fr-res .fr-bridge')")
            pg.evaluate("FirstRun.enterStop(5)"); pg.wait_for_timeout(400); s5 = res(pg)
            check('presenter B-4: stops start fresh after the story ran in the same tab (stop 2 one step, stop 4 no build text, stop 6 on 3 faults)', s2 == [1, False] and s3 is False and s5.startswith('3 faults'), [s2, s3, s5[:30]])
            pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(300); pg.keyboard.press('ArrowLeft'); pg.wait_for_timeout(500)   # stop 6 played once, back to stop 5
            for _ in range(3): pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(900)                                            # stop 5: two actions, then on to stop 6
            check('presenter B-4: going back to a stop shows its start again', pg.evaluate("[FirstRun.FR.P.k,FirstRun.FR.P.step]") == [5, 0] and res(pg).startswith('3 faults'), [pg.evaluate("[FirstRun.FR.P.k,FirstRun.FR.P.step]"), res(pg)[:30]])
            check('notes S-11: every stop has its own time limit from the script (45 s to 2 min 30 s)', pg.evaluate("FirstRun.STOPS.every(s=>{const m=/^(\\d+):(\\d\\d)$/.exec(s.pace||'');const t=m?m[1]*60+(+m[2]):0;return t>=45&&t<=150})"))
            pg.keyboard.press('Escape'); pg.wait_for_timeout(300)
            pg.goto(URL + '#present?short=30'); pg.wait_for_timeout(1500)
            check('presenter: #present?short=30 has 3 stops (glitch, rebuilt, close)', pg.evaluate("FirstRun.FR.P&&FirstRun.FR.P.order") == [0, 5, 11])
            pg.keyboard.press('Escape'); pg.goto(URL + '?present=1'); pg.wait_for_timeout(1500)
            check('presenter: ?present=1 starts it too', pg.evaluate("!!FirstRun.FR.P"))
            # 7. notes window on the same computer
            notes = c.new_page(); notes.on('pageerror', lambda e: errs.append(('notes', str(e)))); notes.goto(URL + 'present-notes'); notes.wait_for_timeout(800)
            say = notes.inner_text('#say')
            check('notes: shows the cue of the current stop and what to expect', 'toy lock' in say and 'Expect: 1 flip' in notes.inner_text('#exp'), say)
            check('notes: the cue text is not in the audience window', say.strip('“”')[:40] not in pg.evaluate("document.body.innerText"))
            snap(notes, 'present_notes_stop1')
            notes.keyboard.press('ArrowRight'); pg.wait_for_timeout(1200); notes.keyboard.press('ArrowRight'); pg.wait_for_timeout(900)
            check('notes: → in the notes window runs the action, then moves the main window to stop 2', pg.evaluate("FirstRun.FR.P.k") == 1, pg.evaluate("FirstRun.FR.P.k"))
            notes.wait_for_timeout(400)
            check('notes: follows the main window (stop 2 of 12)', 'stop 2 of 12' in notes.inner_text('#pos'), notes.inner_text('#pos'))
            snap(notes, 'present_notes_stop2')
            pg.keyboard.press('Escape'); notes.close(); c.close()
            # 8. reduced motion
            c = ctx(b, rm='reduce'); pg = newpage(c, '?fresh=1'); pg.click('#fr-act'); wait_res(pg, r'flip')
            mv = pg.evaluate("[...document.querySelectorAll('#fr *')].filter(e=>{const s=getComputedStyle(e);return parseFloat(s.transitionDuration)>0||s.animationName!=='none'}).length")
            check('reduced motion: nothing in the story moves', mv == 0, mv)
            c.close()
            # 9. 200 % zoom (683 CSS px wide) and 320 px
            for (w, h, tag) in ((683, 384, 'zoom200'), (320, 640, '320')):
                for theme in ('light', 'dark'):
                    c = ctx(b, w, h, theme); pg = newpage(c, '?fresh=1'); bad = []
                    for i in range(9):
                        if i: pg.evaluate(f"FirstRun.goScreen({i})"); pg.wait_for_timeout(250)
                        o = pg.evaluate("(c=>[c.scrollWidth<=c.clientWidth+1,document.querySelector('#fr').scrollWidth<=document.querySelector('#fr').clientWidth+1])(document.querySelector('#fr .fr-card'))")
                        if not all(o): bad.append((i + 1, o))
                        if i in (0, 1, 2, 4, 8): snap(pg, f'{tag}_{theme}_s{i+1}')
                    check(f'{tag} {theme}: one column, no sideways scrolling on any screen', not bad, bad)
                    c.close()
            # 10. every button in the story has a name
            c = ctx(b); pg = newpage(c, '?fresh=1'); nameless = []
            for i in range(9):
                pg.evaluate(f"FirstRun.goScreen({i})"); pg.wait_for_timeout(200)
                nameless += pg.evaluate("[...document.querySelectorAll('#fr button')].filter(x=>!(x.getAttribute('aria-label')||x.textContent.trim())).map(x=>x.outerHTML.slice(0,60))")
                nameless += pg.evaluate("[...document.querySelectorAll('#fr svg')].filter(x=>!x.getAttribute('aria-label')&&x.getAttribute('aria-hidden')!=='true').map(x=>'svg on '+%d)" % (i + 1))
            check('every button has an accessible name and every picture a label', not nameless, nameless[:4])
            pg.click('#fr-skip'); c.close()
            # the doors and the deep links close the story and land on the real view
            c = ctx(b); pg = newpage(c, '?fresh=1'); pg.evaluate("FirstRun.goScreen(8)"); pg.wait_for_timeout(300)
            pg.click('[data-door="learn"]'); pg.wait_for_timeout(500)
            check('door "I’m new to chips" opens the lesson at screen 1 and marks the story seen', pg.evaluate("[S.tab,document.querySelector('#fr').hidden,JSON.parse(localStorage.getItem('gs_fr_seen')).done]") == ['learn', True, True])
            pg.evaluate("FirstRun.open(0)"); pg.wait_for_timeout(300); pg.click('#fr-show'); pg.wait_for_timeout(1500)
            check('"Show me in the app" on screen 1 opens path step 1 in Try an attack', pg.evaluate("[S.tab,S.ti]") == ['analyze', 0])
            pg.evaluate("FirstRun.open(8)"); pg.wait_for_timeout(300); pg.click('[data-door="mine"]'); pg.wait_for_timeout(600)
            check('door "I design chips" opens Open my design', pg.evaluate("S.tab") == 'mine')
            pg.evaluate("go('why:6')"); pg.wait_for_timeout(400)
            check('data-go="why:6" opens screen 6 (chained Studio.onGo)', heading(pg) == 'Does this happen outside a toy?')
            pg.keyboard.press('Escape'); pg.evaluate("go('learn:2')"); pg.wait_for_timeout(300)
            check('the lesson links still work (learn_view keeps its Studio.onGo)', pg.evaluate("S.tab") == 'learn')
            c.close(); b.close()
    finally:
        srv.terminate()
    import importlib.util
    pth = os.path.join(os.environ.get('GLITCHSAT_EXT') or os.path.dirname(HERE), 'check_wording.py')
    sp = importlib.util.spec_from_file_location('check_wording', pth); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    hits = m.scan([os.path.join(HERE, 'first_run_view.py'), os.path.abspath(__file__)])
    check('wording: no listed word and no absolute developer path (shared hashed check)', not hits, hits[:4])
    real = [e for e in errs if 'favicon' not in e[1]]
    check('no JavaScript errors', not real, real[:5])
    bad = [x for x in checks if not x[1]]; print('checks: %d of %d passed' % (len(checks) - len(bad), len(checks)))
    json.dump(dict(errors=errs, checks=checks), open(OUT + 'verify_first_run.json', 'w'), indent=1)
    return 1 if bad else 0

if __name__ == '__main__':
    sys.exit(run())
