#!/usr/bin/env python3
"""Checks the Solver Replay Theatre (docs/wow/theatre.html + docs/wow/witness.json).
Writes nothing in the project tree (solver and simulator work files go to a temporary directory).

Part A (always; needs z3, iverilog, vvp):
  A1 witness.json: every frame carries source file, netlist sha256 (re-hashed here), command line and solver verdict text;
  A2 it agrees with results/reproduce_summary.json (verdict, minimum faults) on the stored-netlist rows;
  A3 it agrees with a FRESH solver run on the stored netlists (verdict, minimum faults, site counts);
  A4 each witness is replayed again from the faults listed in witness.json: (a) with scripts/replay.py (iverilog), the VCD
     parsed by this file's own reader and compared signal by signal with witness.json; (b) with a small pure-Python
     netlist simulator written here (no iverilog, no replay.py). The faulted run must reach the goal, the fault-free run
     must not; the honest key must open with no faults;
  A5 the data inlined in theatre.html equals witness.json; the page loads no external resource; required and banned wording.
Part B (--browser; needs playwright + /usr/bin/google-chrome): at 390 px and 1366 px, every step: no console errors,
  no horizontal scroll, text >= 12 px, buttons >= 44 px, source file + sha on every frame, on-screen numbers equal
  witness.json; keyboard operation; reduced motion; ?kiosk=1.
Usage: python3 docs/wow/check_theatre.py [--browser] [--shots DIR]        exit code 0 = all pass
"""
import hashlib, json, os, re, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import glitchsat as g      # noqa: E402
import replay as rp        # noqa: E402

fails = 0; passes = 0
def rep(ok, msg, quiet=False):
    global fails, passes
    if ok: passes += 1
    else: fails += 1
    if not ok or not quiet: print(('PASS ' if ok else 'FAIL ') + msg, flush=True)

W = json.load(open(os.path.join(HERE, 'witness.json'), encoding='utf-8'))
FR = {f['id']: f for f in W['frames']}
N = W['meta']['cycles']; KEY = W['meta']['key']; ACC = W['meta']['accept_word']
tmp = tempfile.mkdtemp(prefix='p21_check_')

# ---- A1 provenance on every frame ----------------------------------------------------------------------------
rep(set(FR) == {'v1_faultfree', 'v2_faultfree', 'v1_k1', 'v2_k1', 'v2_k2', 'v2_k3', 'v2_flag_k1'}, 'witness.json has the 7 expected frames')
for fid, f in FR.items():
    path = os.path.join(ROOT, f['source_file'])
    ok = (os.path.isfile(path) and hashlib.sha256(open(path, 'rb').read()).hexdigest() == f['netlist_sha256']
          and f['solver']['command'].startswith('python3 scripts/glitchsat.py check ' + f['source_file'])
          and f['solver']['verdict_text'].startswith(f['design'] + ': ' + f['solver']['verdict']) and f['solver']['cycles'] == N)
    rep(ok, f'{fid}: source file exists, sha256 matches the file, command line and solver verdict text present')
rep(W['meta']['what'] == "replay of the solver's witness in a gate-level simulation", 'meta.what carries the required label')

# ---- A2 against results/reproduce_summary.json ---------------------------------------------------------------
S = json.load(open(os.path.join(ROOT, 'results', 'reproduce_summary.json')))
rows = {(r['design'], r['netlist'], r['k']): r for r in S['rows']}
rep(S['cycles'] == N, f'reproduce_summary.json uses the same number of ticks ({N})')
WORD = {'v1_faultfree': ('v1', 0), 'v1_k1': ('v1', 1), 'v2_faultfree': ('v2', 0), 'v2_k1': ('v2', 1), 'v2_k2': ('v2', 2), 'v2_k3': ('v2', 3)}
for fid, (d, k) in WORD.items():
    r = rows[(d, 'spike/given-netlist', k)]; s = FR[fid]['solver']
    rep(s['verdict'] == r['verdict'] and s['min_faults'] == r['min_faults'] and s['max_faults'] == k and s['honest_key_boots_fault_free'] == r['honest_key_boots'],
        f"{fid}: verdict {s['verdict']}, min faults {s['min_faults']} == reproduce_summary row ({d}, spike/given-netlist, k={k})")
rep(FR['v1_k1']['solver']['faults'][0]['net'] == 'ok' and FR['v1_k1']['solver']['faults'][0]['cycle'] == 1 and rows[('v1', 'spike/given-netlist', 1)]['faults'] == [['ok', 1]],
    'V1 witness is one flip of `ok` at tick 1, the same net and tick as the reproduce_summary row')
rep(rows[('v2', 'rtl/plain', 3)]['min_faults'] == 2, "page claim 'a fresh build of V2 needs only 2 flips' == reproduce_summary row (v2, rtl/plain, k=3)")
mj = os.path.join(ROOT, 'research/c2/b2_scope/matrix.jsonl')
if os.path.isfile(mj):
    hit = [json.loads(l) for l in open(mj) if l.strip()]
    hit = [r for r in hit if (r['design'], r['netlist'], r['goal'], r['input_sites'], r['init'], r['free_input']) == ('v2', 'spike', 'boot_ok', False, 'known', False)]
    rep(len(hit) == 1 and hit[0]['min_cost'] == FR['v2_flag_k1']['solver']['min_faults'] == 1, 'accept-flag caveat: 1 flip == research/c2/b2_scope/matrix.jsonl row (v2, spike, boot_ok)')
else:
    print('NOTE accept-flag frame: reproduce_summary.json has no boot_ok row and matrix.jsonl is absent; checked against the fresh solver run only')

# ---- A3 fresh solver run -------------------------------------------------------------------------------------
fresh = {}
for fid, f in FR.items():
    s = f['solver']; goal_out = s['goal'].split()[0]; gv = int(re.search(r'== 0x([0-9A-Fa-f]+)', s['goal']).group(1), 16)
    r = g.run_check(os.path.join(ROOT, f['source_file']), f['design'], s['max_faults'], N, None, goal_out=goal_out, goal_value=gv, workdir=tmp)
    fresh[fid] = r
    rep(r['verdict'] == s['verdict'] and r.get('min_faults') == s['min_faults'] and r['model']['sites_total'] == s['sites_total']
        and r['model']['sites_modelled'] == s['sites_modelled'] and r['netlist']['gates'] == s['gates'] and r['netlist']['flops'] == s['flops'],
        f"{fid}: fresh solver run gives {r['verdict']}, min faults {r.get('min_faults')}, {r['model']['sites_total']} sites == witness.json")
for fid in ('v2_k1', 'v2_k2'):
    rep(FR[fid]['solver']['verdict'] == 'NO_ATTACK_UP_TO_BOUND' and FR[fid]['kind'] == 'solver_only', f'{fid}: bounded none-found result (no replay claimed)')
s2 = FR['v2_k2']['solver']
rep(s2['sites_total'] == (s2['gates'] + s2['flops']) * N, f"V2 site count shown on the page: {s2['sites_total']} = ({s2['gates']} gates + {s2['flops']} flops) x {N} ticks")

# ---- A4 replay again, two independent ways -------------------------------------------------------------------
def read_vcd(path):
    """own VCD reader -> {dotted name: [[t, value]]} (collapsed), independent of scripts/export_witness.py"""
    names, cur, scope, t = {}, {}, [], 0
    out = {}
    for line in open(path):
        p = line.split()
        if not p: continue
        if p[0] == '$scope': scope.append(p[2])
        elif p[0] == '$upscope': scope.pop()
        elif p[0] == '$var': names.setdefault(p[3], []).append('.'.join(scope + [p[4]]))
        elif p[0][0] == '#': t = int(p[0][1:])
        elif p[0][0] in 'bB' and len(p) == 2: cur[p[1]] = (t, p[0][1:])
        elif p[0][0] in '01xz' and len(p) == 1 and p[0][1:] in names: cur[p[0][1:]] = (t, p[0][0])
        else: continue
        for ident, (tt, v) in list(cur.items()):
            val = None if set(v) & set('xzXZ') else int(v, 2)
            for n in names.get(ident, ()):
                ch = out.setdefault(n, [])
                if ch and ch[-1][0] == tt: ch[-1][1] = val
                elif not ch or ch[-1][1] != val: ch.append([tt, val])
            del cur[ident]
    for ch in out.values():      # drop same-time rewrites that restored the earlier value
        i = 1
        while i < len(ch):
            if ch[i][1] == ch[i - 1][1]: del ch[i]
            else: i += 1
    return out

def pysim(nl, sig, faults):
    """Pure-Python gate-level simulation: returns per-tick (boot_word, boot_ok). faults = {(tick, net_id)}."""
    state = {q: int(nl.init[q]) for _, d, q in nl.dffs}
    sigbits = nl.ports['sig']['bits']; res = []
    for c in range(N):
        val = {}
        def get(b):
            if b in ('0', 'x'): return 0
            if b == '1': return 1
            if b in val: return val[b]
            if b in sigbits: v = (sig >> sigbits.index(b)) & 1
            elif b in state: v = state[b]
            else:
                _, ty, con = nl.drivers[b]; a = lambda p: get(con[p][0])
                v = {'$_AND_': lambda: a('A') & a('B'), '$_OR_': lambda: a('A') | a('B'), '$_XOR_': lambda: a('A') ^ a('B'),
                     '$_NOT_': lambda: 1 - a('A'), '$_MUX_': lambda: a('B') if a('S') else a('A')}[ty]()
            if (c, b) in faults: v ^= 1
            val[b] = v; return v
        word = sum(get(b) << i for i, b in enumerate(nl.ports['boot_word']['bits']))
        res.append((word, get(nl.ports['boot_ok']['bits'][0])))
        state = {q: get(d) for _, d, q in nl.dffs}
    return res

NL = {d: g.Netlist(os.path.join(ROOT, m['file']), d) for d, m in W['meta']['netlists'].items()}
def again(fid, f, runname, run, faults, goal_port, goal_value, expect_hit):
    """replay one run of one frame from witness.json; compare with what witness.json stores"""
    stim = dict(verdict='ATTACK_FOUND', netlist_json=f['source_file'], top=f['design'], faults=faults,
                bound=dict(cycles=N, goal=f'{goal_port} == 0x{goal_value:X} at some cycle < {N}'), attacker_input_raw=dict(sig=run['sig']))
    sp = os.path.join(tmp, f'{fid}_{runname}.json'); json.dump(stim, open(sp, 'w'))
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        res = rp.replay(sp, os.path.join(tmp, 'tb'), f'{fid}_{runname}')
    which = 'faulted' if run['run_faults'] else 'faultfree'
    vcd = read_vcd(os.path.join(tmp, 'tb', f'{fid}_{runname}_{which}.vcd'))
    same = all(vcd.get(('tb.' if k in ('clk', 'sig', 'boot_ok', 'boot_word') else 'tb.dut.') + k) == v['changes'] for k, v in run['signals'].items())
    hit = res[which]['goal_hit_cycle']
    pt = run['signals'][goal_port]['per_tick']
    first = next((c for c, v in enumerate(pt) if v == goal_value), -1)
    py = pysim(NL[f['design']], run['sig'], {(x['cycle'], x['net_id']) for x in faults} if run['run_faults'] else set())
    py_same = [p[0] for p in py] == run['signals']['boot_word']['per_tick'] and [p[1] for p in py] == run['signals']['boot_ok']['per_tick']
    ok = same and hit == run['goal_hit_cycle'] == first and (hit >= 0) == expect_hit and py_same
    rep(ok, f"{fid}/{runname}: re-simulated (iverilog VCD identical: {same}; pure-Python simulator agrees: {py_same}); goal "
            + (f'reached at tick {hit}' if hit >= 0 else f'not reached in {N} ticks') + (' as expected' if (hit >= 0) == expect_hit else ' UNEXPECTED'))

for fid in ('v1_k1', 'v2_k3', 'v2_flag_k1'):
    f = FR[fid]; s = f['solver']; r = f['replay']
    rep(len(s['faults']) == s['min_faults'] and r['runs']['faulted']['sig'] != KEY and r['runs']['faulted']['sig'] == s['attacker_input_raw']['sig'] == r['runs']['faultfree']['sig'],
        f"{fid}: {s['min_faults']} listed flip(s); replay uses the solver's wrong key 0x{r['runs']['faulted']['sig']:02X} (not the key 0x{KEY:02X})")
    again(fid, f, 'faulted', r['runs']['faulted'], s['faults'], r['goal_port'], r['goal_value'], True)
    again(fid, f, 'faultfree', r['runs']['faultfree'], s['faults'], r['goal_port'], r['goal_value'], False)
    for x in s['faults']:
        n = r['runs']['faulted']['signals'][f"n{x['net_id']}"]['per_tick']; rr = r['runs']['faulted']['signals'][f"r{x['net_id']}"]['per_tick']
        n0 = r['runs']['faultfree']['signals'][f"n{x['net_id']}"]['per_tick']; r0 = r['runs']['faultfree']['signals'][f"r{x['net_id']}"]['per_tick']
        rep([c for c in range(N) if n[c] != rr[c]] == [x['cycle']] and n0 == r0, f"{fid}: net `{x['net']}` differs from its driver only at tick {x['cycle']} in the faulted run, never in the fault-free run")
    rep(r['agrees_with_solver'] is True, f'{fid}: export recorded agrees_with_solver')
rep(FR['v1_k1']['solver']['min_faults'] == 1 and FR['v2_k3']['solver']['min_faults'] == 3 and FR['v2_flag_k1']['solver']['min_faults'] == 1
    and FR['v2_flag_k1']['solver']['goal'].startswith('boot_ok == 0x1'), 'headline digits: V1 1 flip, V2 3 flips (boot word), V2 1 flip (accept flag)')
fw = FR['v2_flag_k1']['replay']['runs']['faulted']['signals']
rep(ACC not in fw['boot_word']['per_tick'], 'accept-flag caveat: the boot word never reads open in that replay (the page says so)')
for fid in ('v1_faultfree', 'v2_faultfree'):
    f = FR[fid]; r = f['replay']
    rep(r['runs']['honest']['sig'] == KEY and r['runs']['wrong']['sig'] != KEY, f'{fid}: honest run uses the key, wrong run does not')
    again(fid, f, 'honest', r['runs']['honest'], [], 'boot_word', ACC, True)
    again(fid, f, 'wrong', r['runs']['wrong'], [], 'boot_word', ACC, False)
    rep(r['honest_opens'] is True and r['wrong_stays_shut'] is True, f'{fid}: honest key opens, wrong key stays shut (flags in witness.json)')

# ---- A5 the page ---------------------------------------------------------------------------------------------
page = os.path.join(HERE, 'theatre.html'); html = open(page, encoding='utf-8').read()
m = re.search(r'<script type="application/json" id="witness-data">(.*?)</script>', html, re.S)
rep(bool(m) and json.loads(m.group(1)) == W, 'data inlined in theatre.html equals witness.json')
code = html.replace(m.group(0), '') if m else html
ext = re.findall(r'(?:https?:)?//[A-Za-z0-9.-]+\.[a-z]{2,}|<link\b|<img\b|<iframe\b|\bsrc\s*=|@import|url\(|fetch\(|XMLHttpRequest|sendBeacon|WebSocket|localStorage|document\.cookie', code)
rep(not ext, 'page has no external resources, no network calls, no storage, no cookies' + (f' (found {ext[:4]})' if ext else ''))
text = re.sub(r'<[^>]+>', ' ', code)
for need in ("replay of the solver's witness in a gate-level simulation", 'simplified diagram', 'What we did NOT show', 'No 1- or 2-flip attack found within',
             '', 'License: UNDECIDED', 'Working title TBD', 'No hardware'):
    rep(need in code, f'required wording present: {need!r}', quiet=True)
for w in ('safe', 'secure', 'glitch-proof', 'certified', 'hardened', 'proven', 'proved', 'works on real chips', 'novel', 'first to'):
    rep(not re.search(r'\b' + re.escape(w), text, re.I), f'banned word absent: {w!r}', quiet=True)
rep(all(k in code for k in ('prefers-reduced-motion', 'kiosk=1', 'aria-live')), 'page handles reduced motion, ?kiosk=1 and announces step changes')

# ---- Part B --------------------------------------------------------------------------------------------------
if '--browser' in sys.argv:
    from playwright.sync_api import sync_playwright
    shots = sys.argv[sys.argv.index('--shots') + 1] if '--shots' in sys.argv else None
    if shots: os.makedirs(shots, exist_ok=True)
    url = 'file://' + page
    AUDIT = r"""() => {
      const vis = e => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
      let minFont = 99, minWhat = '';
      for (const e of document.querySelectorAll('body *')) {
        if (!vis(e) || ['SCRIPT','STYLE','TITLE'].includes(e.tagName)) continue;
        if (![...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
        let px = parseFloat(getComputedStyle(e).fontSize);
        const svg = e.ownerSVGElement;
        if (svg && svg.viewBox && svg.viewBox.baseVal && svg.viewBox.baseVal.width) px *= svg.getBoundingClientRect().width / svg.viewBox.baseVal.width;
        if (px < minFont) { minFont = px; minWhat = e.tagName + ':' + e.textContent.trim().slice(0, 30); }
      }
      let minBtn = 99;
      for (const b of document.querySelectorAll('button, input')) { if (!vis(b)) continue; const r = b.getBoundingClientRect(); minBtn = Math.min(minBtn, r.height, b.tagName === 'BUTTON' ? r.width : 99); }
      const de = document.documentElement;
      const over = [...document.querySelectorAll('body *')].filter(e => vis(e) && !e.ownerSVGElement && e.getBoundingClientRect().right > innerWidth + 1).length;
      const provs = [...document.querySelectorAll('.side .prov')].filter(vis).map(p => p.textContent);
      return { minFont, minWhat, minBtn, hscroll: de.scrollWidth > de.clientWidth + 1, over, provs, sides: [...document.querySelectorAll('.side')].map(s => s.textContent),
               bad: [...document.querySelectorAll('.result.bad')].map(e => e.textContent), all: document.body.innerText, state: window.__theatre.state(),
               svgs: document.querySelectorAll('.wave svg').length, hot: document.querySelectorAll('.schem .hot').length, flips: document.querySelectorAll('.wave .flip').length };
    }"""
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox', '--headless=new'])
        for w, h in ((390, 844), (1366, 900)):
            ctx = br.new_context(viewport={'width': w, 'height': h}, reduced_motion='reduce'); pg = ctx.new_page(); errs = []
            pg.on('console', lambda mm: errs.append(mm.text) if mm.type in ('error', 'warning') else None); pg.on('pageerror', lambda e: errs.append(str(e)))
            pg.goto(url)
            for step in range(1, 6):
                a = pg.evaluate(AUDIT)
                if shots: pg.screenshot(path=os.path.join(shots, f'step{step}_{w}.png'), full_page=True)
                rep(a['state']['step'] == step and not a['hscroll'] and a['over'] == 0 and a['minFont'] >= 12 and a['minBtn'] >= 44,
                    f"{w}px step {step}: no horizontal scroll, smallest text {a['minFont']:.1f}px ({a['minWhat']}), smallest control {a['minBtn']:.0f}px")
                shas = [W['meta']['netlists'][d]['sha256'] for d in ('v1', 'v2')]
                rep(len(a['provs']) >= 2 and all('reference/spike_netlists/' in t and any(s in t for s in shas) and 'glitchsat.py check' in t for t in a['provs'])
                    and all(any(s in sd for s in shas) for sd in a['sides']), f"{w}px step {step}: every frame on screen shows source file, netlist sha256 and command ({len(a['provs'])} frames)")
                rep(not re.search(r'\bsafe|\bsecure|\bproved|\bproven', a['all'], re.I), f'{w}px step {step}: no banned word on screen', quiet=True)
                if step == 1:
                    rep(a['svgs'] == 4 and a['flips'] == 0 and a['all'].count('Right key: the lock opens at tick %d' % FR['v1_faultfree']['replay']['runs']['honest']['goal_hit_cycle']) == 2
                        and a['all'].count('Lock stays shut for all 6 ticks') == 2, f'{w}px step 1: four fault-free strips; right key opens, wrong key stays shut, on both sides')
                if step == 2:
                    f = FR['v1_k1']
                    rep(a['bad'] == ['Wrong key, and the lock opens at tick %d.' % f['replay']['runs']['faulted']['goal_hit_cycle']] and a['hot'] == 1 and a['flips'] == 1
                        and 'attack found with 1 flip: ok at tick 1' in a['all'] and 'boot word 0x96 = open' in a['all'], f'{w}px step 2: V1 one flip of ok at tick 1, lock opens (digits equal witness.json), flip marked on diagram and strip')
                if step == 3:
                    f = FR['v2_k3']; s = f['solver']
                    names = all(x['net'] in a['sides'][1] for x in s['faults'])
                    rep('No 1- or 2-flip attack found within 6 ticks.' in a['sides'][1] and f"{s['sites_total']} places a flip could go" in a['sides'][1]
                        and f"{s['sites_modelled']} kept" in a['sides'][1] and 'attack found with 3 flips' in a['sides'][1] and names and a['flips'] == 1 + 3 and a['hot'] == 1 + 3,
                        f"{w}px step 3: V2 side says 'No 1- or 2-flip attack found within 6 ticks.', shows {s['sites_total']} sites from the solver output, then the 3-flip witness with its 3 nets")
                if step == 4:
                    f = FR['v2_flag_k1']
                    rep('Wrong key, and the accept flag reads open at tick %d.' % f['replay']['runs']['faulted']['goal_hit_cycle'] in a['bad'] and 'attack found with 1 flip: boot_ok' in a['sides'][1]
                        and 'boot word 0x69 = shut' in a['sides'][1], f'{w}px step 4: accept-flag caveat shown as a separate step, 1 flip of boot_ok, boot word stays shut')
                if step == 5:
                    rep(pg.is_visible('#notpanel') and 'What we did NOT show' in a['all'] and 'No hardware' in a['all'] and 'needs only 2 flips' in a['all'], f'{w}px step 5: "What we did NOT show" panel visible')
                else:
                    rep(not pg.is_visible('#notpanel'), f'{w}px step {step}: caveat panel hidden until step 5', quiet=True)
                rep(a['state']['tick'] == N - 1 and not a['state']['sweeping'], f'{w}px step {step}: reduced motion -> no tick animation (rests on the last tick)', quiet=True)
                pg.keyboard.press('Space')
            st = lambda: pg.evaluate('window.__theatre.state()')
            rep(st()['step'] == 5, f'{w}px: Space on the last step does not run past the end')
            pg.keyboard.press('ArrowLeft'); a1 = st()['step']; pg.keyboard.press('r'); a2 = st()['step']; pg.keyboard.press('ArrowRight'); a3 = st()['step']
            rep((a1, a2, a3) == (4, 1, 2), f'{w}px keyboard: Left goes back, R resets, Right steps')
            pg.keyboard.press('r'); pg.focus('#bBack'); pg.keyboard.press('Tab'); f1 = pg.evaluate('document.activeElement.id'); pg.keyboard.press('Enter'); a4 = st()['step']
            pg.keyboard.press('Space'); a5 = st()['step']
            rep(f1 == 'bStep' and a4 == 2 and a5 == 3, f'{w}px keyboard: Tab reaches Step; Enter and Space on the focused button each step once')
            pg.focus('#tick'); pg.keyboard.press('Home'); t0 = st()['tick']; pg.keyboard.press('ArrowRight'); pg.keyboard.press('ArrowRight'); t2 = st(); chip = pg.inner_text('#left .chips')
            rep(t0 == 0 and t2['tick'] == 2 and t2['step'] == 3 and 'tick 2' in chip, f'{w}px keyboard: the tick slider moves the tick (arrow keys there do not change step); chips follow')
            pg.keyboard.press('p'); pl = st()['playing']; pg.keyboard.press('p')
            rep(pl and not st()['playing'], f'{w}px keyboard: P toggles play')
            rep(not errs, f'{w}px: no console errors or warnings' + (f' {errs[:3]}' if errs else ''))
            ctx.close()
        ctx = br.new_context(viewport={'width': 1366, 'height': 900}, reduced_motion='no-preference'); pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e))); pg.goto(url + '?kiosk=1')
        s0 = pg.evaluate('window.__theatre.state()'); pg.wait_for_timeout(3600); s1 = pg.evaluate('window.__theatre.state()')
        rep(s0['kiosk'] and s0['playing'] and s0['sweeping'] and s0['tick'] == 0 and s1['tick'] == N - 1 and not s1['sweeping'], 'motion allowed + ?kiosk=1: auto-play on, tick sweeps 0 -> 5 then rests')
        for _ in range(5): pg.keyboard.press('ArrowRight')
        rep(pg.evaluate('window.__theatre.state()')['step'] == 1 and not errs, '?kiosk=1: stepping past the last step loops to step 1')
        br.close()

shutil.rmtree(tmp, ignore_errors=True)
print(f'{passes} passed, {fails} failed')
sys.exit(1 if fails else 0)
