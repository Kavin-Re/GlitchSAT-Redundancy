"""GlitchSAT Studio: the first-run story ("Why GlitchSAT?") and Presenter mode.

Loaded by studio.py through one marked hook (FIRST-RUN-VIEW) that calls install(PAGE) and handle(...). Everything else
lives here:
  * a 7-screen welcome story in a full-window overlay (#fr). Each screen has a "Say this" cue for a presenter, one
    action, and a result line with its label and its source file. It replaces the old 6-card story on first launch
    only; the old story stays on Start ("Watch the short story again").
  * Presenter mode: 9 fixed stops through the real views of the Studio, driven with one key; speaker cues in a second
    window (/present-notes) on the presenting computer.
  * the server side: /api/firstrun/facts (every number the story shows, read from the project files at request time),
    /api/firstrun/seen (a "seen" flag in the Studio's cache folder), /firstrun/src/<fact> (the source file of a fact,
    as plain text) and /present-notes.
Nothing in the page script types a result number: they all come from /api/firstrun/facts or from a live run.
Design: ext/FIRST_RUN_DESIGN.md (kept next to the Studio's work tree, not shipped).
"""
import json
import os
import re
import tempfile
import time

VERSION = 1
_HERE = os.path.dirname(os.path.abspath(__file__))
_UP = os.path.dirname(_HERE)


# ------------------------------------------------------------------ where the project files are
def _dirs(root, ext=None, real=None):
    ext = ext or os.environ.get('GLITCHSAT_EXT') or os.path.join(_UP, 'ext')
    real = real or os.environ.get('GLITCHSAT_REAL') or os.path.join(_UP, 'real')
    return root, ext, real


def _module(root, ext, name):
    """A module folder: tools/<name> in the project, else <ext>/<name> (same order as the Studio)."""
    for d in (os.path.join(root, 'tools', name), os.path.join(ext, name)):
        if os.path.isdir(d):
            return d
    return None


def _show(path, root, ext, real):
    """The path shown on screen: relative to the project, or to the folder that holds ext/ and real/."""
    for base in (root, os.path.dirname(ext), os.path.dirname(real)):
        try:
            r = os.path.relpath(path, base)
        except ValueError:
            continue
        if not r.startswith('..'):
            return r.replace(os.sep, '/')
    return os.path.basename(path)


def _read(p):
    with open(p, encoding='utf-8', errors='replace') as fh:
        return fh.read()


# ------------------------------------------------------------------ the facts (section 2 of the design)
def facts(root, ext=None, real=None, with_paths=False):
    """Every number the story shows: {key: {value, label, src}}. A fact whose file is missing or unreadable is left out."""
    root, ext, real = _dirs(root, ext, real)
    out, paths = {}, {}

    def put(key, path, value, label, **more):
        out[key] = dict(value=value, label=label, src=_show(path, root, ext, real), **more)
        paths[key] = path

    # Table 7.1: the three toy locks, stored netlists and the plain rebuild (k <= 3, 6 cycles)
    p = os.path.join(root, 'results', 'reproduce_summary.json')
    try:
        d = json.loads(_read(p))
        rows = {(r.get('design'), r.get('netlist'), r.get('k')): r for r in d.get('rows', [])}
        cyc = d.get('cycles')

        def row(des, nl):
            r = rows.get((des, nl, 3))
            return r if r and r.get('verdict') == 'ATTACK_FOUND' and isinstance(r.get('min_faults'), int) else None
        r = row('v0', 'spike/given-netlist')
        if r: put('v0', p, r['min_faults'], r.get('label') or 'MEASURED', cycles=cyc)
        r = row('v1', 'spike/given-netlist')
        if r:
            nets = sorted({f[0] for f in r.get('faults') or [] if isinstance(f, list) and f})
            put('v1', p, r['min_faults'], r.get('label') or 'MEASURED', cycles=cyc, shared=nets[0] if len(nets) == 1 else None)
        r = row('v2', 'spike/given-netlist')
        if r: put('v2_stored', p, r['min_faults'], r.get('label') or 'MEASURED', cycles=cyc)
        r = row('v2', 'rtl/plain')
        if r: put('v2_rebuilt', p, r['min_faults'], r.get('label') or 'MEASURED', cycles=cyc)
    except (OSError, ValueError, AttributeError, TypeError):
        pass

    # WHY_TWO_FLIPS: the re-encoded Armed word brings back 3 flips
    p = os.path.join(root, 'docs', 'report', 'WHY_TWO_FLIPS.md')
    try:
        t = _read(p)
        a = re.search(r'"armed" value (0x[0-9A-Fa-f]{2})', t)
        b = re.search(r'armed constant to (0x[0-9A-Fa-f]{2})[^\n]*?gives (\d+) on every flow', t)
        c = re.search(r'and the accept word (0x[0-9A-Fa-f]{2}) differ in bits [\d,]+, which belong to only (\w+) copies', t)
        if a and b and c:
            put('reencode', p, dict(old=a.group(1), new=b.group(1), flips=int(b.group(2)), accept=c.group(1), copies=c.group(2)), 'MEASURED')
    except OSError:
        pass

    # the design sources: short excerpts shown verbatim (V0 one check, V2 three copies)
    pats = {'code_v0': (r"assign m = \(a == ", r"cmp8 c\(", r"1: st <= m \?", r"assign boot_ok = "),
            'code_v2': (r"assign m = \(a == ", r"cmp8 c0\(", r"wire \[7:0\] sel = ", r"wire \[7:0\] word = ", r": st <= word;", r"assign boot_ok = ")}
    for key, pp in pats.items():
        p = os.path.join(root, 'rtl', key[5:] + '.v')
        try:
            lines = _read(p).split('\n')
            ex = [dict(n=i + 1, text=l.strip(), hl=bool(re.search(r'== 8\'h|cmp8 c', l))) for i, l in enumerate(lines) if any(re.search(x, l) for x in pp)]
            k = re.search(r"a == 8'h([0-9A-Fa-f]{2})", _read(p))
            acc = re.search(r"8'h([0-9A-Fa-f]{2}) : 8'h[0-9A-Fa-f]{2}|good = 8'h([0-9A-Fa-f]{2})", _read(p))
            if len(ex) == len(pp) and k:
                put(key, p, dict(lines=ex, key='0x' + k.group(1).upper(), accept='0x' + ((acc.group(1) or acc.group(2)).upper() if acc else '')), 'source')
        except OSError:
            pass

    # E2: V2 over the solved build settings
    p = os.path.join(root, 'research', 'c2', 'e2_variance', 'E2_REPORT.md')
    try:
        m = re.search(r'^\| V2 \| (\d+) \| (\d+) \| (\d+) \|\s*$', _read(p), re.M)
        if m:
            a, b, c = (int(x) for x in m.groups())
            put('e2', p, dict(min1=a, min2=b, min3=c, total=a + b + c), 'MEASURED')
    except OSError:
        pass

    # OpenTitan blocks: agreement with SYNFI, protected round counter
    p = os.path.join(real, 'README.md')
    try:
        t = _read(p)
        m = re.search(r'Every one of\s+the ([\d,]+) fault injections SYNFI made got the same answer', t)
        if m:
            n = int(m.group(1).replace(',', ''))
            put('real_agree', p, dict(agree=n, total=n), 'recorded')
        m = re.search(r'the protected round counter needs \*\*(\d+)\*\*', t)
        if m:
            put('real_ctr', p, int(m.group(1)), 'BOUNDED')
    except OSError:
        pass

    # whole chips (soc module): PicoSoC with the added boot check, Ibex demo system
    soc = _module(root, ext, 'soc')
    p = os.path.join(soc, 'studio', 'explore_chip.json') if soc else ''
    try:
        d = json.loads(_read(p)) if p else {}
        chips = {c.get('id'): c for c in d.get('chips', [])}

        def goal(chip, variant, flow, gid):
            for v in (chips.get(chip) or {}).get('variants', []):
                if v.get('variant') == variant and (flow is None or v.get('flow') == flow):
                    for g in v.get('goals', []):
                        if g.get('id') == gid:
                            try:
                                return int(g.get('faults_needed')), g.get('cycles')
                            except (TypeError, ValueError):
                                return None
            return None
        by = {f: goal('picosoc', 'tmr', f, 'boot_release') for f in ('written', 'keep', 'flat')}
        if all(by.values()):
            put('chip_pico', p, {f: v[0] for f, v in by.items()}, 'BOUNDED', cycles=by['written'][1])
        rd = os.path.join(soc, 'README.md')
        m = re.search(r'\*\*(\d+) / (\d+) / (\d+)\*\* \(written / keep / flat\)', _read(rd)) if os.path.isfile(rd) else None
        if m:
            put('soc_build', rd, dict(written=int(m.group(1)), keep=int(m.group(2)), flat=int(m.group(3))), 'BOUNDED')
        al = goal('ibex_demo', 'lockstep', None, 'alarm_suppressed')
        if al:
            put('chip_ibex_alarm', p, al[0], 'BOUNDED', cycles=al[1])
        ds, dl = goal('ibex_demo', 'stock', None, 'debug_entry'), goal('ibex_demo', 'lockstep', None, 'debug_entry_silent')
        if ds and dl:
            put('chip_ibex_debug', p, dict(stock=ds[0], lockstep=dl[0]), 'BOUNDED', cycles=dict(stock=ds[1], lockstep=dl[1]))
    except (OSError, ValueError, AttributeError, TypeError):
        pass

    # boot program (ROM), compiler builds
    fw = _module(root, ext, 'firmware')
    p = os.path.join(fw, 'README.md') if fw else ''
    try:
        t = _read(p) if p else ''
        m = re.search(r'In (\d+) of the (\d+) builds a single', t)
        o = re.search(r'At `(-O\d)`, the\s+three MAC compares of the triple-check version become one compare', t)
        if m:
            put('fw_rom', p, dict(fall=int(m.group(1)), total=int(m.group(2)), opt=o.group(1) if o else None), 'SIMULATED')
    except OSError:
        pass

    # masking gadget (Labs): the ISW gadget after synthesis
    mk = _module(root, ext, 'masking')
    p = os.path.join(mk, 'README.md') if mk else ''
    try:
        t = _read(p) if p else ''
        m = re.search(r'^\| `isw_and2` \| \*\*synth\*\* \| \*\*(leaks|no leak found)\*\*', t, re.M)
        if m:
            put('mask', p, m.group(1), 'SIMULATED')
    except OSError:
        pass

    return (out, paths) if with_paths else out


# ------------------------------------------------------------------ the "seen" flag
def cache_dir():
    return os.path.join(os.environ.get('XDG_CACHE_HOME') or os.path.join(os.path.expanduser('~'), '.cache'), 'glitchsat-studio')


def _seen_file():
    return os.path.join(cache_dir(), 'first_run.json')


def read_seen():
    """{seen, screen, version, started}; a missing or broken file reads as not seen."""
    try:
        d = json.loads(_read(_seen_file()))
        if not isinstance(d, dict):
            raise ValueError
        sc = d.get('screen')
        return dict(seen=d.get('seen') is True, screen=sc if isinstance(sc, int) and 0 <= sc < 20 else 0,
                    version=d.get('version'), started=True)
    except (OSError, ValueError):
        return dict(seen=False, screen=0, version=VERSION, started=False)


def write_seen(seen, screen):
    d = cache_dir()
    os.makedirs(d, exist_ok=True)
    sc = screen if isinstance(screen, int) and not isinstance(screen, bool) and 0 <= screen < 20 else 0
    body = json.dumps(dict(seen=seen is True, screen=sc, version=VERSION, when=time.strftime('%Y-%m-%dT%H:%M:%S')))
    fd, tmp = tempfile.mkstemp(dir=d, prefix='.first_run.', suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as fh:
        fh.write(body)
    os.replace(tmp, _seen_file())
    return read_seen()


# ------------------------------------------------------------------ requests
def handle(h, method, path, q, root):
    """Answer the add-on's own requests. h is the Studio's request handler (h._send, h.headers). True when answered."""
    if method == 'GET':
        if path == '/api/firstrun/facts':
            h._send(200, json.dumps(facts(root)))
            return True
        if path == '/api/firstrun/seen':
            h._send(200, json.dumps(read_seen()))
            return True
        if path.startswith('/firstrun/src/'):
            key = path[len('/firstrun/src/'):]
            _, paths = facts(root, with_paths=True)
            p = paths.get(key)
            if not p or not os.path.isfile(p):
                h._send(404, '{"error":"not found"}')
                return True
            with open(p, 'rb') as fh:
                h._send(200, fh.read(), 'text/plain; charset=utf-8')
            return True
        if path == '/present-notes':
            h._send(200, NOTES_PAGE, 'text/html')
            return True
        return False
    if method == 'POST' and path == '/api/firstrun/seen':
        if h.headers.get('X-GlitchSAT') != '1':
            h._send(403, '{"error":"forbidden"}')
            return True
        q = q if isinstance(q, dict) else {}
        try:
            h._send(200, json.dumps(write_seen(q.get('seen'), q.get('screen'))))
        except OSError as e:
            h._send(200, json.dumps(dict(error='could not save', detail=str(e)[:120])))
        return True
    return False


def install(page):
    """Return the page with the add-on's style and script added (after the main script and the other add-ons)."""
    if 'id="fr-css"' in page:
        return page                                 # already installed: no change
    page = page.replace('</style></head>', '</style><style id="fr-css">' + CSS + '</style></head>', 1)
    i = page.rfind('</body>')
    off = '<script>window.GS_NO_WELCOME=1</script>' if os.environ.get('GLITCHSAT_FIRSTRUN') == '0' else ''
    return page[:i] + off + '<script id="fr-js">' + JS + '</script>' + page[i:]


# ------------------------------------------------------------------ style
CSS = r"""
#fr{position:fixed;inset:0;z-index:30;background:color-mix(in srgb,var(--bg) 82%,#000 18%);display:flex;align-items:flex-start;justify-content:center;overflow:auto;padding:4vh 12px 24px}
#fr[hidden],#fr-pbar[hidden],#fr-blank[hidden],#fr-toast[hidden]{display:none}
.fr-card{width:100%;max-width:760px;min-width:0;background:var(--panel);border:1px solid var(--line2);border-radius:10px;box-shadow:0 18px 60px #0006;padding:1em 1.3em .9em;font-size:15px;line-height:1.5;color:var(--txt)}
.fr-top{display:flex;align-items:center;gap:.7em;flex-wrap:wrap;font-size:.87em;color:var(--mut)}
.fr-top .fr-kick{font-weight:650}
.fr-bar{flex:1;min-width:4em;height:.4em;background:var(--inset);border:1px solid var(--line);border-radius:3px;overflow:hidden}
.fr-bar i{display:block;height:100%;background:var(--acc)}
.fr-card h2{font-size:1.55em;line-height:1.2;margin:.45em 0 .3em}
.fr-card h2:focus{outline:none}.fr-card h2:focus-visible{outline:2px solid var(--acc);outline-offset:3px}
.fr-lead{margin:0 0 .7em;font-size:1.03em}
.fr-int{background:var(--inset);border:1px solid var(--line);border-radius:8px;padding:.7em .8em;display:flex;flex-direction:column;align-items:center;gap:.6em}
.fr-int svg{display:block;width:100%;max-width:440px;height:auto}
.fr-int svg text{fill:var(--txt)}.fr-int svg text.m{fill:var(--mut)}
.fr-act{font-size:1.07em;padding:.45em 1.3em;border-radius:7px;border:1px solid var(--acc);background:var(--acc);color:var(--acc-t);font-weight:700;min-height:44px}
.fr-act[disabled]{opacity:.7;cursor:progress}
.fr-seg{display:inline-flex;flex-wrap:wrap;justify-content:center;background:var(--panel);border:1px solid var(--line2);border-radius:7px;padding:3px;gap:3px}
.fr-seg button{min-height:40px;background:none;border:1px solid transparent;border-radius:5px;padding:.3em .9em;font-size:1em;color:var(--txt)}
.fr-seg button[aria-checked=true]{background:var(--acc);color:var(--acc-t);font-weight:700}
.fr-res{margin:.7em 0 0;min-height:3em}
.fr-res p{margin:.25em 0}
.fr-res:empty{display:none}
.fr-n{display:inline-block;font-size:1.15em;font-weight:750;margin-right:.35em;color:var(--txt);border-bottom:3px solid var(--acc)}
.fr-src{display:inline-flex;gap:.4em;align-items:center;flex-wrap:wrap;font-size:.82em;color:var(--mut)}
.fr-src a{color:var(--acc);overflow-wrap:anywhere}
.fr-card .chip{font-size:.75em}
.chip.h-measured{color:var(--ok);border-color:var(--ok)}.chip.h-sampled{color:var(--warn);border-color:var(--warn);border-style:dotted}
.fr-wait{color:var(--mut)}
.fr-e2{width:100%;margin:.6em 0 0}
.fr-e2 .bar{display:flex;height:1.5em;border-radius:4px;overflow:hidden;border:1px solid var(--line2)}
.fr-e2 .bar span{display:block;height:100%}
.fr-e2 .s1{background:var(--hot)}.fr-e2 .s2{background:var(--warn);background-image:repeating-linear-gradient(45deg,transparent 0 5px,rgba(0,0,0,.18) 5px 8px)}.fr-e2 .s3{background:var(--ok)}
.fr-e2 p{margin:.3em 0 0;font-size:.93em}
.fr-small{font-size:.87em;color:var(--mut);margin:.7em 0 0}
.fr-small b{color:var(--txt)}
.fr-cardx{width:100%;background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--acc);border-radius:6px;padding:.5em .8em}
.fr-cardx h3{margin:0 0 .2em;font-size:1.05em;text-transform:none;letter-spacing:0;color:var(--txt)}.fr-cardx p{margin:.2em 0}
.fr-cardx .cav{font-size:.87em;color:var(--mut)}
.fr-tl{list-style:none;margin:0;padding:0;width:100%}
.fr-tl li{display:flex;gap:.6em;align-items:flex-start;padding:.25em 0}
.fr-tl .d{flex:none;width:1.6em;height:1.6em;border-radius:50%;border:2px solid var(--line2);display:inline-flex;align-items:center;justify-content:center;font-size:.8em;font-weight:700;color:var(--mut);background:var(--panel)}
.fr-tl li.on .d{background:var(--acc);border-color:var(--acc);color:var(--acc-t)}
.fr-tl li.off{color:var(--mut)}.fr-tl li.off span.t{visibility:hidden}
.fr-end{font-weight:700;margin:.5em 0 0}
.fr-code2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.6em;width:100%}
.fr-codebox{min-width:0;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:.5em .7em}
.fr-codebox h3{margin:0 0 .3em;font-size:1em;text-transform:none;letter-spacing:0;color:var(--txt)}
.fr-codebox p{margin:.3em 0 0;font-size:.9em}
.fr-codebox pre{margin:0;font:.8em/1.5 var(--mono);white-space:pre-wrap;overflow-wrap:anywhere;background:var(--inset);border:1px solid var(--line);border-radius:4px;padding:.3em .4em;color:var(--txt)}
.fr-codebox .ln{display:grid;grid-template-columns:2.2em minmax(0,1fr);padding-left:.2em}.fr-codebox .ln i{color:var(--mut);font-style:normal}.fr-codebox .ln span{min-width:0}
.fr-codebox .ln.hl{background:color-mix(in srgb,var(--warn) 18%,transparent);box-shadow:inset 3px 0 0 var(--warn)}
.fr-codebox .gap{display:block;color:var(--mut);padding-left:.2em}
.fr-int svg.fr-gsvg{max-width:600px}
.chip.h-source{color:var(--acc);border-color:var(--acc)}
.fr-ways ul{margin:.2em 0 0;padding-left:1.1em;font-size:.87em}.fr-ways li{margin:.2em 0}.fr-tech{vertical-align:1px}
.fr-row{display:flex;gap:.6em;flex-wrap:wrap;justify-content:center;align-items:center}
.fr-row .btn{min-height:44px;font-size:.95em;padding:.3em 1em}
.fr-how{font-size:.95em}.fr-how li.off{display:none}
.fr-bridge{margin:.5em 0 0;padding:.5em .8em;border-left:4px solid var(--acc);background:var(--inset);border-radius:4px}
.fr-glitch:focus{outline:none}.fr-glitch:focus-visible rect{stroke:var(--acc);stroke-width:2.5}
.fr-glitch{touch-action:none}
.fr-dot-go{animation:frdot 1.1s ease-out both}.fr-dot-late{animation:frdot 2.2s ease-in both}
@keyframes frdot{from{transform:translateX(var(--fr-from))}to{transform:none}}

.fr-chips{display:flex;gap:.5em;flex-wrap:wrap;justify-content:center}
.fr-chips button{min-height:40px;border-radius:6px;border:2px solid var(--line2);background:var(--panel);padding:.2em .9em;font-weight:700;letter-spacing:.05em;color:var(--txt)}
.fr-chips button[aria-pressed=true]{border-color:var(--acc);box-shadow:inset 0 -3px 0 var(--acc)}
.fr-lim{margin:.6em 0 0;padding-left:1.3em}.fr-lim li{margin:.15em 0}
.fr-doors{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.6em;width:100%}
.fr-doors button{min-height:3.4em;text-align:left;border-radius:8px;border:1px solid var(--line2);background:var(--panel);padding:.5em .8em;font-size:1em;color:var(--txt)}
.fr-doors button:hover{border-color:var(--acc)}
.fr-doors b{display:block;font-size:1.05em}.fr-doors span{color:var(--mut);font-size:.87em}
details.fr-say{margin:.7em 0 0;border:1px dashed var(--line2);border-radius:6px;font-size:.9em}
details.fr-say>summary{cursor:pointer;padding:.3em .7em;color:var(--mut)}
details.fr-say>p{margin:0;padding:0 .8em .5em}
.fr-foot{display:flex;gap:.6em;align-items:center;flex-wrap:wrap;margin-top:.9em;border-top:1px solid var(--line);padding-top:.7em}
.fr-foot .sp{flex:1}
.fr-foot .btn{font-size:.9em;padding:.35em 1em;min-height:36px}
.fr-foot .linkb{font-size:.9em}
.fr-skip{margin-left:auto}
.fr-shackle{transition:transform .4s ease}
.fr-lock.open .fr-shackle{transform:translate(10px,-9px)}
.fr-why{font-size:12px;margin:0 6px 0 2px;white-space:nowrap}.fr-why .s{display:none}
@media (max-width:1500px){.fr-why .l{display:none}.fr-why .s{display:inline}.fr-why{margin:0 4px 0 0}}
.fr-startline{margin:8px 0 0;font-size:13px}
#fr-toast{position:fixed;left:50%;bottom:40px;transform:translateX(-50%);z-index:25;max-width:min(560px,94vw);background:var(--raised);border:1px solid var(--line2);border-left:4px solid var(--acc);border-radius:7px;padding:8px 12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;box-shadow:0 8px 30px #0006;font-size:13.5px}
/* Presenter mode */
#fr-pbar{position:fixed;left:0;right:0;bottom:0;z-index:35;display:flex;gap:.8em;align-items:center;flex-wrap:wrap;padding:.35em 1em;background:var(--raised);border-top:1px solid var(--line2);font-size:clamp(13px,1.1vw,18px);color:var(--mut)}
#fr-pbar b{color:var(--txt)}#fr-pbar .sp{flex:1}
#fr-ptop{position:fixed;left:0;right:0;top:0;z-index:35;padding:.3em 1em;background:var(--acc);color:var(--acc-t);font-weight:700;font-size:clamp(14px,1.2vw,20px)}
#fr-ptop[hidden]{display:none}
#fr-blank{position:fixed;inset:0;z-index:50;background:#000}
html.present .app{grid-template-columns:minmax(0,1fr)!important;grid-template-rows:44px minmax(0,1fr)!important;padding-top:2em;padding-bottom:2.4em;height:100vh}
html.present .app>aside,html.present #foot,html.present #logdock{display:none!important}
html.present .app>*{grid-column:1/-1!important}
html.present #fr{padding-bottom:3.5em;scroll-padding:1em 0 3.5em}
html.present main .view{scroll-padding:1em 0 3em}
html.present #f-all{display:none!important}
html.present .fr-card h2:focus-visible{outline:none}
html.present .fr-card{max-width:min(1180px,96vw);font-size:clamp(18px,1.6vw,28px)}
html.present .fr-int svg{max-width:min(720px,100%)}
html.present #views>.view{zoom:1.15}
@media (max-width:640px){.fr-doors,.fr-code2{grid-template-columns:minmax(0,1fr)}#fr{padding:8px 6px 16px}.fr-card{padding:.8em .8em .7em;font-size:14.5px}.fr-card h2{font-size:1.35em}.fr-foot .sp{flex-basis:100%;order:3;height:0}}
"""

# ------------------------------------------------------------------ page script
JS = r"""
/* ==== "Why GlitchSAT?" welcome story and Presenter mode (first_run_view.py). Every number comes from
   /api/firstrun/facts or from a live run; none is typed here. Uses Studio.onGo, Studio.startExtra, Studio.aboutExtra. ==== */
(()=>{if(window.FirstRun)return;
const FR={i:0,open:false,mode:null,F:{},st:{},res:{},opener:null,P:null,ready:null};
const Q=new URLSearchParams(location.search),FRESH=Q.get('fresh')==='1';
const F=k=>FR.F[k]||null,V=k=>FR.F[k]?FR.F[k].value:null;
const fl=n=>n==null?'?':n+' flip'+(n===1?'':'s'),fa=n=>n+' fault'+(n===1?'':'s');
const WORD=['zero','One','Two','Three','Four','Five'],word=n=>WORD[n]||String(n);
const fmt=n=>typeof n==='number'?n.toLocaleString('en-US'):String(n);
const LBL={source:'source code',MEASURED:'measured',SIMULATED:'simulated',BOUNDED:'bounded',recorded:'recorded',live:'live',PROVED:'proved',SAMPLED:'sampled'};
const LTIP={measured:'Measured: a command was run and its output was read.',simulated:'Simulated: modelled in software, nothing measured on a real chip.',bounded:'Bounded: exact, but only up to a stated number of clock steps.',recorded:'Recorded: computed earlier and saved in the project files.',live:'Live: computed on this computer just now.',proved:'Proved: true for any waiting time, inside the model.',sampled:'Sampled: many cases tried, not all of them.'};
const chip=l=>{const k=LBL[l]||String(l||'').toLowerCase();return `<span class="chip h-${esc(k)}" title="${esc(LTIP[k]||'')}">${esc(k)}</span>`};
const srcA=k=>{const f=F(k);return f?`<a href="/firstrun/src/${esc(k)}" target="_blank" rel="noopener">${esc(f.src)}</a>`:''};
const srcL=(k,lab)=>{const f=F(k);return f?`<span class="fr-src">${chip(lab||f.label)}${f.cycles&&typeof f.cycles==='number'?`<span>${f.cycles} clock steps</span>`:''}<span>source: ${srcA(k)}</span></span>`:''};
const MISS='<span class="fr-wait">(not in this folder)</span>';
const go_=g=>{if(typeof go==='function')go(g)};
const hasView=id=>typeof VIEWS!=='undefined'&&VIEWS.some(v=>v.id===id);
/* ---- live calls: each has a recorded fallback, so the presenter always sees the predicted number */
const REC={v0:'v0',v1:'v1',v2:'v2_stored',v2_rtl:'v2_rebuilt'};
function recorded(design,why){const f=F(REC[design]);return f?{n:f.value,how:'recorded',fb:why||'',fact:REC[design]}:{n:null,how:'missing',fb:why||'',fact:REC[design]}}
function live(design){if(FR.res[design])return Promise.resolve(FR.res[design]);
 if(FR.noLive)return Promise.resolve(recorded(design,'no live run'));
 const slow=new Promise(r=>setTimeout(()=>r({_slow:1}),8000));
 const call=api.post('/api/analyze',{design,flow:'plain',goal:'word',k:3,cycles:6,time_limit_s:20}).catch(()=>({error:'offline'}));
 return Promise.race([call,slow]).then(r=>{let x;
  if(r&&!r.error&&!r._slow&&r.verdict==='ATTACK_FOUND'&&typeof r.min_faults==='number')x={n:r.min_faults,how:r._src==='live'?'live':'recorded',fact:REC[design],nets:(r.faults||[]).map(f=>f.net)};
  else x=recorded(design,r&&r._slow?'slow':'failed');
  FR.res[design]=x;return x})}
const resChip=x=>x.how==='live'?chip('live')+chip(F(x.fact)?F(x.fact).label:'MEASURED'):chip('recorded');
const resLine=(x,text)=>x.n==null?`<p>${MISS}</p>`:`<p><b class="fr-n">${fl(x.n)}</b>${text}</p><p class="fr-src">${resChip(x)}${x.fb?'<span>live result not ready: recorded value shown</span>':x.how==='live'?'<span>computed on this computer just now</span>':''}<span>source: ${srcA(x.fact)}</span></p>`;
/* ---- pictures (role=img, the result in words in the label) */
const lockSVG=(open,label)=>`<svg viewBox="0 0 420 150" role="img" aria-label="${esc(label)}"><g transform="translate(110,82)">${svgKey(-70,6,'var(--hot)',0)}<text x="-52" y="40" font-size="13" text-anchor="middle" class="m">wrong key</text></g><g class="fr-lock${open?' open':''}" transform="translate(226,78)"><path class="fr-shackle" d="M-21,-9V-30a21,21 0 0 1 42,0V-9" fill="none" stroke="${open?'var(--hot)':'var(--ok)'}" stroke-width="7"/><rect x="-33" y="-12" width="66" height="54" rx="9" fill="${open?'var(--hot)':'var(--ok)'}"/><circle cx="0" cy="9" r="7" fill="var(--panel)"/><rect x="-3" y="12" width="6" height="15" fill="var(--panel)"/></g>${open?'<path d="M300,30l-12,26h11l-7,22 21,-30h-11l8,-18z" fill="var(--warn)"/>':''}<text x="226" y="142" font-size="14" text-anchor="middle" font-weight="700">${open?'open':'shut'}</text></svg>`;
function guardsSVG(n){const W=420,cx=[[210],[150,270],[110,210,310]][n-1];let s='';
 cx.forEach((x,j)=>{s+=`<g transform="translate(${x},34)"><path d="M0,-20l18,7v12c0,12-8,20-18,25c-10,-5-18,-13-18,-25v-12z" fill="var(--c${j})" opacity=".9"/><text x="0" y="40" font-size="12" text-anchor="middle" class="m">${n===1?'check':'copy '+(j+1)}</text></g>`});
 if(n===2){s+=`<path d="M150,82V96H270V82" fill="none" stroke="var(--warn)" stroke-width="4" stroke-dasharray="7 4"/><path d="M210,96V118" stroke="var(--warn)" stroke-width="4" stroke-dasharray="7 4"/><text x="282" y="112" font-size="13" font-weight="700" fill="var(--warn)">shared wire</text>`}
 else cx.forEach((x,j)=>{s+=`<path d="M${x},82V118" stroke="var(--c${j})" stroke-width="3"/>`});
 s+=`<rect x="150" y="118" width="120" height="26" rx="5" fill="var(--raised)" stroke="var(--line2)"/><text x="210" y="136" font-size="13" text-anchor="middle">lock</text>`;
 return `<svg viewBox="0 0 ${W} 150" role="img" aria-label="${n===1?'One check of the key':n===2?'Two copies of the check, joined by one shared wire':'Three separate copies of the check, each with its own wire'}">${s}</svg>`}
const chipSVG=(t,s)=>`<svg viewBox="0 0 420 96" role="img" aria-label="${esc(t)}">${svgChip(150,22,120,52)}<text x="210" y="53" font-size="14" font-weight="700" text-anchor="middle">${esc(s)}</text></svg>`;
/* ---- "How a glitch attack works": 4 steps and a draggable glitch on the clock line */
const HOW=[['A chip runs on clock ticks.','On every tick it moves data from one storage cell (a flip-flop) to the next. In between, signals need a little time to travel through the logic.','A chip passes data from cell to cell on every clock tick. Signals need a moment to get there.'],
 ['The attacker disturbs the chip for a split second.','It can be a short dip in the power (signals slow down), a clock tick that is too short (less time), or a laser or electromagnetic pulse aimed at the chip (it pushes a transistor the wrong way).','The attacker disturbs the chip for a split second: a power dip, a tick that is too short, or a laser pulse.'],
 ['One value goes wrong.','A signal arrives late or gets pushed, so a storage cell keeps the wrong value: one bit flips. Or the processor skips or misreads one instruction.','So a signal is late, and a cell stores the wrong value. One bit flips.'],
 ['The check says yes.','If that bit was part of the security check (“is the key right?”), the check can say yes to a wrong key.','If that bit is part of the key check, the lock says yes to a wrong key. GlitchSAT models exactly that flip, in the design, with no hardware.']];
const TX=[130,230,330,430],HIT=2;
function glitchSVG(st){const n=st.s||1,g=st.g==null?0:st.g,hit=st.drop===HIT,miss=st.drop!=null&&!hit;
 const frame=hit?4:n;
 let t=TX.map((x,j)=>`<line x1="${x}" y1="22" x2="${x}" y2="146" stroke="var(--line2)" stroke-dasharray="3 4"/><text x="${x}" y="16" font-size="12" text-anchor="middle" class="m">tick ${j+1}</text>`).join('');
 t+=`<rect x="14" y="66" width="62" height="44" rx="5" fill="var(--raised)" stroke="var(--c0)" stroke-width="2"/><text x="45" y="92" font-size="12" text-anchor="middle">cell A</text>`;
 t+=`<rect x="178" y="75" width="204" height="26" rx="13" fill="var(--inset)" stroke="var(--line2)"/><text x="280" y="92" font-size="12" text-anchor="middle" class="m">logic (takes time)</text>`;
 t+=`<path d="M76,88H178M382,88H470" stroke="var(--mut)" stroke-width="2"/>`;
 t+=`<rect x="470" y="62" width="76" height="52" rx="5" fill="var(--raised)" stroke="${hit?'var(--hot)':'var(--ok)'}" stroke-width="${hit?3:2}"/><text x="508" y="80" font-size="11" text-anchor="middle" class="m">check cell</text><text x="508" y="104" font-size="19" font-weight="800" text-anchor="middle" fill="${hit?'var(--hot)':'var(--txt)'}">${hit?'yes':'no'}</text>`;
 const dx=hit?400:462,anim=st.anim?(hit?' fr-dot-late':' fr-dot-go'):'';
 t+=`<g class="fr-dot${anim}" style="--fr-from:${66-dx}px"><circle cx="${dx}" cy="88" r="8" fill="var(--c0)"/></g>`;
 if(hit)t+=`<text x="420" y="128" font-size="12" fill="var(--hot)" font-weight="700" text-anchor="middle">late!</text>`;
 if(n>=2)t+=`<g class="fr-glitch" tabindex="0" role="slider" aria-label="Glitch: drag it onto a clock tick" aria-valuemin="1" aria-valuemax="4" aria-valuenow="${g+1}" aria-valuetext="tick ${g+1}" transform="translate(${TX[g]},162)" style="cursor:grab"><rect x="-26" y="-14" width="52" height="34" rx="6" fill="transparent"/><path d="M4,-12l-12,16h9l-6,14 15,-19h-9l7,-11z" fill="var(--warn)" stroke="var(--txt)" stroke-width=".8"/><text x="0" y="31" font-size="11" text-anchor="middle" font-weight="700">glitch</text></g>`;
 const lbl=hit?`Frame 4: the glitch at tick ${HIT+1} made the signal late; the check cell stored yes for a wrong key; the lock opens`:miss?`The glitch at tick ${st.drop+1} missed; the check cell still says no`:`Frame ${n}: cell A sends data through the logic to the check cell on each clock tick`;
 return `<svg viewBox="0 0 560 200" class="fr-gsvg" role="img" aria-label="${esc(lbl)}"><text x="8" y="196" font-size="11" class="m">frame ${frame} of 4</text>${t}</svg>`}
function howStep(st){st.s=Math.min(HOW.length,(st.s||1)+1);st.anim=false;redraw(false);announce('Step '+st.s+' of '+HOW.length+': '+HOW[st.s-1][0]);sync()}
function dropAt(st,j){st.g=j;st.drop=j;if((st.s||1)<3)st.s=3;st.anim=true;redraw(false);announce(j===HIT?'The glitch hit the right tick: one bit flipped and the lock opened.':'The glitch at tick '+(j+1)+' missed. Try another tick.');sync()}
function wireGlitch(){const h=host().querySelector('.fr-glitch'),svg=host().querySelector('.fr-gsvg');if(!h||!svg)return;const st=FR.st.how;
 const toTick=cx=>{const pt=svg.createSVGPoint();pt.x=cx;pt.y=0;const x=pt.matrixTransform(svg.getScreenCTM().inverse()).x;let b=0;TX.forEach((t,j)=>{if(Math.abs(t-x)<Math.abs(TX[b]-x))b=j});return b};
 h.addEventListener('pointerdown',e=>{e.preventDefault();h.setPointerCapture(e.pointerId);h.style.cursor='grabbing';
  const mv=ev=>{const j=toTick(ev.clientX);h.setAttribute('transform',`translate(${TX[j]},162)`);st.g=j};
  const up=ev=>{h.removeEventListener('pointermove',mv);h.removeEventListener('pointerup',up);dropAt(st,toTick(ev.clientX));const x=host().querySelector('.fr-glitch');x&&x.focus()};
  h.addEventListener('pointermove',mv);h.addEventListener('pointerup',up)});
 h.addEventListener('keydown',e=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();e.stopPropagation();st.g=Math.max(0,Math.min(TX.length-1,(st.g||0)+(e.key==='ArrowRight'?1:-1)));st.drop=null;redraw(false);const x=host().querySelector('.fr-glitch');x&&x.focus()}
  else if(e.key==='Enter'||e.key===' '){e.preventDefault();e.stopPropagation();dropAt(st,st.g||0);const x=host().querySelector('.fr-glitch');x&&x.focus()}})}
const WAYS=[['Sparse state codes.','Store each state as a code far from the others in bits, so one flip can’t turn “locked” into “open”.'],
 ['Multi-bit yes/no signals.','Use four wires for one yes or no, with only one pattern meaning yes. OpenTitan calls these multi-bit booleans.'],
 ['Redundant counters.','Count with two counters, one up and one down, that must agree.'],
 ['Lockstep.','Run a second copy of the processor, and sound an alarm when the two disagree.'],
 ['In software.','Check twice, or compare a value with a stored inverted copy of it.']];
function codeBox(k,title,note){const c=V(k);if(!c)return `<div class="fr-codebox"><h3>${esc(title)}</h3><p>${MISS}</p></div>`;let prev=0;
 const rows=c.lines.map(l=>{const gap=prev&&l.n>prev+1?'<span class="gap">…</span>':'';prev=l.n;return gap+`<span class="ln${l.hl?' hl':''}"><i aria-hidden="true">${l.n}</i><span>${esc(l.text)}</span></span>`}).join('');
 return `<div class="fr-codebox"><h3>${esc(title)}</h3><pre aria-label="${esc(title)}: excerpt of ${esc(F(k).src)}">${rows}</pre><p>${note}</p><p class="fr-src">${chip('source')}<span>${srcA(k)}</span></p></div>`}
/* ---- the nine screens (design section 3, plus "How a glitch attack works") */
const SCR=[
 {id:'why',h:'Can a tiny glitch open a lock?',go:'p0',
  lead:()=>`Many chips check a secret key before they start, in a bank card, a car key or a phone. Right key: the lock opens. Wrong key: it stays shut. But a thief can “glitch” the chip, with a quick spike in its power or clock, so it makes one tiny mistake.`,
  body:st=>`${lockSVG(!!(st.r&&st.r.n),st.r&&st.r.n?`The lock is open: ${fl(st.r.n)} with the wrong key`:'A shut lock and a wrong key')}<button class="fr-act" id="fr-act" ${st.busy?'disabled':''}>${st.busy?'Glitching…':st.r?'Glitch it again':'Glitch it'}</button>`,
  result:st=>st.r?resLine(st.r,` ${st.r.n===1?'One flipped signal':word(st.r.n)+' flipped signals'} opened the lock with the wrong key.`):st.busy?'<p class="fr-wait">Looking for the smallest glitch…</p>':'<p class="fr-wait">Press <b>Glitch it</b>. The app finds the smallest glitch that opens this toy lock.</p>',
  acts:[st=>runAct(st,'v0',x=>`Result: ${fl(x.n)} opened the lock.`)],alab:['Glitch it'],
  say:()=>`This is a toy lock. I press Glitch, and the app finds the smallest glitch that opens it. Here, ${V('v0')===1?'one flipped signal is':fl(V('v0'))+' are'} enough.`,
  expect:()=>`Expect: ${fl(V('v0'))}`},
 {id:'how',h:'How a glitch attack works',go:'learn:5',
  lead:()=>`Four steps, from a real chip to what GlitchSAT checks. Press <b>Next step</b>, then drag the glitch onto the clock line.`,
  body:st=>{const n=st.s||1;return `${glitchSVG(st)}<ol class="fr-tl fr-how" aria-live="polite">${HOW.map((t,j)=>`<li class="${j<n?'on':'off'}"><span class="d" aria-hidden="true">${j+1}</span><span class="t"${j<n?'':' aria-hidden="true"'}><b>${t[0]}</b> ${t[1]}</span></li>`).join('')}</ol><div class="fr-row"><button class="fr-act" id="fr-act" ${n>=HOW.length?'disabled':''}>Next step</button><button class="btn" id="fr-drop" aria-describedby="fr-gl-help">Glitch at tick ${(st.g==null?0:st.g)+1}</button></div><p class="fr-small" id="fr-gl-help" style="margin:0">Drag the glitch, or focus it and use the arrow keys, then press Enter. Only one tick is the moment the check result is stored.</p>`},
  result:st=>`${st.drop==null?'':st.drop===HIT?`<p><b class="fr-n">1 bit flipped</b> The signal was late at tick ${HIT+1}, so the check cell kept the wrong value, and the lock opened with a wrong key.</p>`:`<p><b class="fr-n">nothing happened</b> The glitch at tick ${st.drop+1} missed the moment the check result is stored. Timing matters: try another tick.</p>`}${(st.s||1)>=HOW.length?`<p class="fr-bridge"><b>GlitchSAT doesn’t use real hardware.</b> It models step 3: it flips a wire’s value for one clock tick in the design, and asks a solver for the fewest flips that make the check say yes.</p>`:''}`,
  extra:()=>`<p class="fr-small">Real cases, with sources: game consoles, an AirTag, crypto wallets and cars, in the lesson <button class="linkb" data-go="learn:5">True stories</button>.</p>`,
  acts:[1,2,3].map(()=>st=>howStep(st)).concat([st=>dropAt(st,HIT)]),alab:['Step 2','Step 3','Step 4','Glitch at the right tick'],
  say:()=>{const st=FR.st.how||{};return HOW[Math.min(HOW.length,st.s||1)-1][2]},
  sayAll:()=>HOW.map((t,j)=>(j+1)+'. '+t[2]).join(' '),
  expect:()=>'Expect: four steps, then the glitch at tick '+(HIT+1)+' flips one bit and the lock opens'},
 {id:'code',h:'How a chip protects itself, in its code',go:'p2',
  lead:()=>{const c=V('code_v0');return `Chips are written as code (Verilog) before they are built. Here is the real code of two toy locks from this project. Left: one comparison decides${c?` if the key is ${esc(c.key)}`:''}. Right: the designer wrote the same check three times.`},
  body:st=>`<div class="fr-code2">${codeBox('code_v0','One check (V0)','One comparison decides. Flip its answer and the lock opens.')}${codeBox('code_v2','Three copies (V2)',`Each copy sets its own bits of the answer word. The lock opens only if the whole word is ${esc((V('code_v2')||{}).accept||'the open code')}, so all three copies must say yes.`)}</div><button class="fr-act" id="fr-act" ${st.built?'disabled':''}>See what the build tool made of it</button>`,
  result:st=>st.built?`<div class="fr-bridge"><p style="margin:0"><b>The build tool turns this code into gates</b> (the chip’s wiring list). In the stored build, the three copies stay apart, and the thief needs ${fl(V('v2_stored'))}. But <b>three guards that share one weak point are really one guard</b>. In one rebuilt version, a stored code${V('reencode')?` (${esc(V('reencode').old)})`:''} let two copies share a weak point: ${fl(V('v2_rebuilt'))}.${V('reencode')?` Changing it to ${esc(V('reencode').new)} restored ${fl(V('reencode').flips)}.`:''}</p><p class="fr-src">${chip('MEASURED')}<span>sources: ${srcA('v2_stored')} · ${srcA('reencode')}</span></p><p style="margin:.3em 0 0"><button class="linkb" data-go="p2">Open the gate-level view of the three copies →</button></p></div>`:'',
  extra:()=>`<div class="fr-ways"><p class="fr-small" style="margin:.2em 0"><b>Other ways designers write protection</b> (real-world techniques; this project checks some of them on <button class="linkb" data-go="x-real">real chip designs</button> and <button class="linkb" data-go="x-chip">whole chips</button>):</p><ul>${WAYS.map(w=>`<li><span class="chip h-sampled fr-tech">technique</span> <b>${w[0]}</b> ${w[1]}</li>`).join('')}</ul></div>`,
  acts:[st=>{st.built=true;redraw(false);announce('The build tool turns this code into gates.');sync()},()=>{if(FR.P){closeWhy(false,true);S.fr=true;bars()}goApp('p2')}],alab:['See what the build tool made of it','Open the gate-level view'],
  say:()=>`Without protection, one comparison decides. With protection, the designer writes the check three times, so one glitch can’t fool all three.`,
  expect:()=>`Expect: the code side by side, then the gates: ${fl(V('v2_stored'))} on the stored build`},
 {id:'copies',h:'Engineers add copies. Do copies help?',go:'p1',
  lead:()=>`The usual fix is to check the key two or three times. GlitchSAT counts the fewest flips a thief needs. It’s an exact answer, inside a stated model.`,
  body:st=>`${guardsSVG((st.sel||0)+1)}${seg('fr-seg2','How many checks',['1 check','2 copies','3 copies'],st.sel||0)}`,
  result:st=>{const x=st.r&&st.r[st.sel||0];if(!x)return st.busy?'<p class="fr-wait">Counting…</p>':'<p class="fr-wait">Pick <b>2 copies</b>, then <b>3 copies</b>.</p>';const sh=F('v1')&&F('v1').shared;
   return resLine(x,[` One check: ${x.n===1?'one flip':fl(x.n)} is enough.`,` ${x.n===V('v0')?'Still':'Now'} ${fl(x.n)}. Both copies feed one shared wire${sh?` (<code>${esc(sh)}</code>)`:''}; flip that wire and the copies never get a say.`,` The thief must fool all three.`][st.sel||0])},
  init:st=>{if(!st.r){st.r=[];pick(st,0)}},
  acts:[st=>pick(st,1),st=>pick(st,2)],alab:['2 copies','3 copies'],
  say:()=>`Two copies sound safer, but they share one wire, so it’s still ${V('v1')===1?'one flip':fl(V('v1'))}. With three separate copies the thief needs ${V('v2_stored')===3?'three':fl(V('v2_stored'))}.`,
  expect:()=>`Expect: ${fl(V('v0'))}, then ${fl(V('v1'))}, then ${fl(V('v2_stored'))}`},
 {id:'build',h:'But the finished design can be different',go:'x-chip',
  lead:()=>`We found this along the way. We added a boot check with three copies to a small open-source chip (PicoSoC). Then we built the same source in three ways. <b>The answer belongs to the finished design, not the source.</b> The middle build still keeps the three copies apart; its weak point is a stored code, as on the code screen. Only the last build merged the copies: design tools can weaken a protection without telling you, so check the finished design.`,
  body:st=>`${buildSVG(st.sel||0)}${seg('fr-seg3','How the chip was built',BUILDS.map(b=>b[1]),st.sel||0)}`,
  result:st=>{const v=V('soc_build');if(!v)return `<p>${MISS}</p>`;const b=BUILDS[st.sel||0],n=v[b[0]];
   return `<p><b class="fr-n">${fa(n)}</b> ${b[2]} Same source code${(st.sel||0)?`; as written it needed ${fa(v.written)}`:''}.</p><p class="fr-src">${chip('recorded')}${chip('BOUNDED')}<span>${F('chip_pico')?F('chip_pico').cycles+' clock steps':''}</span><span>source: ${srcA('soc_build')}</span><span>data: ${srcA('chip_pico')}</span></p>`},
  extra:()=>{const f=V('fw_rom');return `<p class="fr-small"><b>We saw it in other places too, and we were not first.</b> SYNFI, a published tool from the OpenTitan project, showed before us that synthesis can merge copies. In a masking circuit in Labs, the design tool regrouped the logic and it ${esc(V('mask')||'?')} (${chip('SIMULATED')}, <button class="linkb" data-go="labs">Labs</button>, ${srcA('mask')}). In a boot program, the compiler${f&&f.opt?' at '+esc(f.opt):''} turned three copies of a check into one; ${f?`${f.fall} of ${f.total} builds of that program fall to one fault`:MISS} (${chip('SIMULATED')}, <button class="linkb" data-go="x-fw">Boot program</button>, ${srcA('fw_rom')}).</p>`},
  init:st=>{if(st.sel==null)st.sel=0},
  acts:[st=>{st.sel=1;redraw(false);sync()},st=>{st.sel=2;redraw(false);sync()}],alab:['Copies kept apart','All optimised together'],
  say:()=>{const v=V('soc_build');return `The answer belongs to the finished design: on PicoSoC it is ${v?`${v.written} / ${v.keep} / ${v.flat}`:'different'} by build. The drop to ${v?v.keep:'the middle number'} comes from a weak stored code; the drop to ${v?v.flat:'the last number'} is the build tool merging the three copies.`},
  expect:()=>{const v=V('soc_build');return v?`Expect: ${fa(v.written)} as written, ${fa(v.keep)} kept apart, ${fa(v.flat)} all optimised together`:'Expect: the build screen'}},
 {id:'chips',h:'Does this happen outside a toy?',go:'x-chip',
  lead:()=>`We ran the same checks on parts of real open-source chips. These are designs, not physical chips. No hardware was used.`,
  body:st=>{const c=CHIPS[st.c||0];return `${chipSVG(c.t,c.s)}<div class="fr-cardx" aria-live="polite"><h3>${c.n} of ${CHIPS.length}: ${esc(c.t)}</h3>${c.html()}</div><button class="fr-act" id="fr-act">Next chip</button>`},
  result:()=>'',
  acts:[st=>{st.c=((st.c||0)+1)%CHIPS.length;redraw(false)},st=>{st.c=((st.c||0)+1)%CHIPS.length;redraw(false)}],
  alab:['Next chip','Next chip'],goFor:st=>(st.c||0)===0?'x-real':'x-chip',
  say:()=>{const a=V('real_agree');return `Real designs show the same pattern. And for OpenTitan, our answers match a published tool on every one of ${a?fmt(a.total):'its'} tests.`},
  expect:()=>{const p=V('chip_pico');return p?`Expect: cards 2 and 3 (PicoSoC ${p.written} / ${p.keep} / ${p.flat}, Ibex alarm ${V('chip_ibex_alarm')})`:'Expect: next two chip cards'}},
 {id:'grew',h:'We changed our minds, on purpose',go:'about',
  lead:()=>`The question changed as we learned. Each step came from finding a mistake in the step before.`,
  body:st=>{const n=st.s||1;return `<ol class="fr-tl" aria-live="polite">${STEPS().map((t,j)=>`<li class="${j<n?'on':'off'}"><span class="d" aria-hidden="true">${j+1}</span><span class="t"${j<n?'':' aria-hidden="true"'}>${t}</span></li>`).join('')}</ol>${n>=STEPS().length?`<p class="fr-end">In one sentence: three guards that share one weak point are really one guard.</p>`:''}<button class="fr-act" id="fr-act" ${n>=STEPS().length?'disabled':''}>Next step</button>`},
  result:()=>F('reencode')||F('e2')?`<p class="fr-src">${chip('MEASURED')}<span>sources: ${srcA('reencode')}${F('e2')?' · '+srcA('e2'):''}</span></p>`:'',
  acts:[1,2,3,4].map(()=>st=>{st.s=Math.min(STEPS().length,(st.s||1)+1);redraw(false);announce('Step '+st.s+' of '+STEPS().length)}),
  say:()=>`Our first headline was wrong, and the app shows why. Each step fixed a mistake in the last one. Three guards that share one weak point are really one guard.`,
  expect:()=>'Expect: five steps, one per press'},
 {id:'honest',h:'What it checks today, and what it doesn’t',go:'about',
  lead:()=>SCOPE,
  body:st=>`<div class="fr-chips" role="group" aria-label="How sure is a number?">${['PROVED','BOUNDED','SAMPLED'].map(k=>`<button data-chip="${k}" aria-pressed="${st.ch===k}">${k}</button>`).join('')}</div><p aria-live="polite" style="margin:0;text-align:center">${st.ch?CHIPTXT[st.ch]:'Tap a label to see what it means.'}</p><p class="fr-small" style="margin:0">MEASURED / SIMULATED / recorded say where a number came from.</p>`,
  result:()=>LIMITS,
  acts:[st=>{st.ch='BOUNDED';redraw(false)}],alab:['BOUNDED chip'],
  say:()=>`Today it checks glitch attacks only, not every security risk. Every number says how sure we are.`,
  expect:()=>'Expect: the BOUNDED sentence'},
 {id:'next',h:'Who it’s for, and where to go next',go:null,
  lead:()=>`Pick where you want to start. You can come back here any time from <b>Why GlitchSAT?</b> at the top.`,
  body:()=>DOORS(),
  result:()=>'',
  say:()=>`Newcomers start with the lesson, students try attacks, designers open their own design.`,
  expect:()=>'Expect: four doors'}];
const SCOPE=`The long-term aim is a place where anyone can check their own design for hardware security risks. <b>Today it checks one family of risks: fault injection (glitches).</b> That means one or more flipped bits, and skipped program steps. It checks gate-level designs (the chip’s wiring) and boot programs. It also checks if your protections survive the build. <b>Labs</b> holds early tests of side channels (masking). They are experimental. Constant-time code and secret-flow checks are <b>planned, not built</b>.`;
const CHIPTXT={PROVED:'<b>PROVED:</b> true for any waiting time, inside the model. Rare here.',BOUNDED:'<b>BOUNDED:</b> exact, but only up to a stated number of clock steps and flips. “No attack found” never means “secure”.',SAMPLED:'<b>SAMPLED:</b> we tried many cases, not all of them.'};
const LIMITS=`<ul class="fr-lim"><li>A model, no real hardware.</li><li>Toy-sized main designs; real-chip results are bounded and come with notes.</li><li>The counting rule is a choice, not physics.</li><li>No claim that the method is new.</li></ul>`;
const STEPS=()=>{const r=V('reencode'),e=V('e2');return ['Started from a worry about attacks on shop payment devices.','Built a solver that counts the fewest flips for a toy boot lock.',
 'Our first headline, “three copies resist two flips”, fell apart under questions. It held only for one set of choices: the goal, the start state, the build and the counting rule.',
 `We found that the answer depends on how a flip is counted, on the build, and on what is checked.${e?` Across ${e.total} build settings, the three-copy lock needed 1 flip in ${e.min1}, 2 in ${e.min2} and 3 in ${e.min3}.`:''} We also found that SYNFI had shown the build effect first. So we claim nothing new about the method.`,
 r?`Late twist: one rebuilt three-copy lock needed only ${fl(V('v2_rebuilt'))}. The design tool was not the cause. A stored code was: ${esc(r.old)} and the “open” code ${esc(r.accept)} differ only in bits that ${esc(r.copies)} of the three copies own. Changing ${esc(r.old)} to ${esc(r.new)} brought back ${fl(r.flips)}.`:'Late twist: one rebuilt result came from a stored code, not from the design tool.']};
const CHIPS=[
 {n:1,s:'OpenTitan',t:'OpenTitan (a security chip)',html:()=>{const a=V('real_agree'),c=V('real_ctr');return `<p>AES and Ibex blocks, from SYNFI’s own netlists (the chip’s wiring lists). ${a?`On <b>${fmt(a.agree)} of ${fmt(a.total)}</b> fault tests, our answer matched SYNFI’s answer.`:MISS} ${c!=null?`The protected round counter needs <b>${fa(c)}</b>.`:''}</p><p class="fr-src">${chip('recorded')}${chip('BOUNDED')}<span>source: ${srcA('real_agree')}</span></p>`}},
 {n:2,s:'PicoSoC',t:'PicoSoC with an added boot check, three copies',html:()=>{const p=V('chip_pico');return p?`<p><b>${p.written}, ${p.keep} or ${fa(p.flat)}</b>, depending on how it was built (the screen before). The same holds for a second goal: the processor starting with a wrong value.</p><p class="cav">The boot check is our addition, not part of PicoSoC.</p><p class="fr-src">${chip('BOUNDED')}<span>${F('chip_pico').cycles} clock steps</span><span>source: ${srcA('chip_pico')}</span></p>`:`<p>${MISS}</p>`}},
 {n:3,s:'Ibex',t:'Ibex demo system with lockstep',html:()=>{const a=V('chip_ibex_alarm'),d=V('chip_ibex_debug');return a!=null?`<p>Lockstep means a second processor copy plus an alarm. Fooling the alarm takes <b>${fa(a)}</b>.${d?` Entering debug mode takes <b>${d.lockstep}</b>.`:''}</p><p class="cav">Lockstep was switched on by editing the source for this study.</p><p class="fr-src">${chip('BOUNDED')}<span>${F('chip_ibex_alarm').cycles} clock steps</span><span>source: ${srcA('chip_ibex_alarm')}</span></p>`:`<p>${MISS}</p>`}}];
const DOORS=()=>`<div class="fr-doors">${[['learn','I’m new to chips','Start with the short lesson.'],['p0','I’m learning VLSI','Try an attack, step by step.'],['mine','I design chips',hasView('mine')?'Open your own design.':'See the example gallery.'],['teach','I teach','Print the class plan.']].map(d=>`<button data-door="${d[0]}"><b>${d[1]}</b><span>${d[2]}</span></button>`).join('')}</div><p style="margin:.2em 0 0"><button class="linkb" id="fr-present">Present this</button> <span class="fr-small">(full screen, one key. Press P any time.)</span></p>`;
const CLOSE={id:'close',h:'What it checks today, and where to go next',go:null,lead:()=>SCOPE,body:()=>DOORS(),result:()=>LIMITS,say:()=>`Today: glitch attacks only. Every number says how sure we are.`,expect:()=>'Expect: scope, limits and the doors'};
function seg(id,label,opts,sel){return `<div class="fr-seg" id="${id}" role="radiogroup" aria-label="${esc(label)}">${opts.map((o,j)=>`<button role="radio" data-sel="${j}" aria-checked="${j===sel}" tabindex="${j===sel?0:-1}">${esc(o)}</button>`).join('')}</div>`}
function runAct(st,design,say){if(st.busy)return;st.busy=true;redraw(false);live(design).then(x=>{st.busy=false;st.r=x;redraw(false);if(x.n!=null)announce(say(x));sync()})}
const SEGD={copies:['v0','v1','v2']};
const BUILDS=[['written','As written','As written, each copy stays apart.','as written'],['keep','Copies kept apart','After the usual clean-up, with the check kept as its own block. The three copies are still apart; the drop comes from a weak stored code.','kept apart'],['flat','All optimised together','The build tool saw the three copies together and merged them into one.','all together']];
function buildSVG(sel){const v=V('soc_build')||{};let g='';BUILDS.forEach((b,j)=>{const n=v[b[0]]||0,x=100+j*120,h=n*30,on=j===sel;g+=`<rect x="${x}" y="${118-h}" width="72" height="${h}" rx="4" fill="${on?'var(--acc)':'var(--raised)'}" stroke="var(--line2)"/><text x="${x+36}" y="${112-h}" font-size="15" font-weight="800" text-anchor="middle">${n}</text><text x="${x+36}" y="136" font-size="11" text-anchor="middle" class="m">${esc(b[3])}</text>`});return `<svg viewBox="0 0 420 146" role="img" aria-label="Faults needed by build: as written ${v.written}, copies kept apart ${v.keep}, all optimised together ${v.flat}">${g}<text x="8" y="14" font-size="11" class="m">faults needed</text></svg>`}
function pick(st,j){const sid=FR.cur().id;st.sel=j;if(sid==='build'){redraw(false);sync();announce(resText(sid,j));return}const d=SEGD[sid][j];if(st.r&&st.r[j]){redraw(false);announce(resText(sid,j,st.r[j]));sync();return}st.busy=true;redraw(false);
 live(d).then(x=>{st.busy=false;st.r[j]=x;if(FR.cur().id===sid)redraw(false);if(x.n!=null)announce(resText(sid,j,x));sync()})}
const resText=(sid,j,x)=>sid==='build'?(V('soc_build')?`${BUILDS[j][1]}: ${fa(V('soc_build')[BUILDS[j][0]])}.`:''):`Result: ${fl(x.n)}.`;
/* ---- drawing */
FR.cur=()=>FR.mode==='close'?CLOSE:SCR[FR.i];
function host(){let h=document.getElementById('fr');if(!h){h=document.createElement('div');h.id='fr';h.hidden=true;document.body.appendChild(h);h.addEventListener('click',onClick,true)}return h}
function focusKey(){const a=document.activeElement;if(!a||!host().contains(a))return null;return a.id?'#'+a.id:a.dataset.sel!=null?`.fr-seg [data-sel="${a.dataset.sel}"]`:a.dataset.chip?`[data-chip="${a.dataset.chip}"]`:a.dataset.door?`[data-door="${a.dataset.door}"]`:a.classList.contains('fr-glitch')?'.fr-glitch':null}
function redraw(focus){if(!FR.open)return;const keep=focus===false?focusKey():null;const s=FR.cur(),st=FR.st[s.id]=FR.st[s.id]||{},pres=!!FR.P,N=SCR.length,i=FR.i;
 const kick=FR.mode==='close'?'Why GlitchSAT? · the close':`Why GlitchSAT? · ${i+1} of ${N}`;const gid=s.goFor?s.goFor(st):s.go;
 host().innerHTML=`<div class="fr-card" role="dialog" aria-modal="true" aria-labelledby="fr-h" aria-describedby="fr-lead"><div class="fr-top"><span class="fr-kick">${kick}</span><span class="fr-bar" aria-hidden="true"><i style="width:${FR.mode==='close'?100:Math.round(100*(i+1)/N)}%"></i></span>${pres?'':'<button class="btn fr-skip" id="fr-skip">Skip</button>'}</div>
 <h2 id="fr-h" tabindex="-1">${esc(s.h)}</h2><p class="fr-lead" id="fr-lead">${s.lead()}</p><div class="fr-int">${s.body(st)}</div><div class="fr-res">${s.result(st)}</div>${s.extra?s.extra():''}
 ${pres?'':`<details class="fr-say"><summary>Presenting? Say this</summary><p>“${esc(s.sayAll?s.sayAll():s.say())}”</p></details>`}
 ${pres?'':`<div class="fr-foot"><button class="btn" id="fr-back" ${i===0?'disabled':''}>Back</button><span class="sp"></span>${gid?`<button class="linkb" id="fr-show" data-go="${gid}">Show me in the app →</button>`:''}<button class="btn primary" id="fr-next">${i===N-1?'Close':'Next'}</button></div>`}</div>`;
 if(focus!==false){const h=document.getElementById('fr-h');h&&h.focus({preventScroll:false})}else if(keep){const x=host().querySelector(keep);x&&x.focus({preventScroll:true})}if(s.id==='how')wireGlitch()}
function openWhy(n,opts){opts=opts||{};if(S.story!=null&&typeof closeStory==='function')closeStory(true);if(S.dlg&&typeof closeDlg==='function'){S.dlg.opener=null;closeDlg()}
 if(!FR.open)FR.opener=opts.opener||(document.activeElement!==document.body?document.activeElement:null);
 FR.mode=opts.mode||null;FR.i=Math.max(0,Math.min(SCR.length-1,n||0));FR.open=true;S.fr=true;hideToast();host().hidden=false;
 const s=FR.cur(),st=FR.st[s.id]=FR.st[s.id]||{};const draw=()=>{if(s.init)s.init(st);redraw();if(!FR.P)save(false)};FR.ready.then(draw);if(opts.hash!==false&&!FR.P)setHash('#why/'+(FR.i+1))}
function closeWhy(done,nofocus){if(!FR.open)return;FR.open=false;if(!FR.P)S.fr=false;host().hidden=true;host().innerHTML='';if(done)save(true);LS.set('gs_seen3',1);if(/^#why/.test(location.hash))setHash('');
 if(nofocus)return;const o=FR.opener;FR.opener=null;const b=(o&&document.contains(o)&&o!==document.body&&o)||$('#b-why')||$('#tabs .tab.on');b&&b.focus()}
function goScreen(n){if(n<0||n>=SCR.length)return;FR.i=n;const s=SCR[n],st=FR.st[s.id]=FR.st[s.id]||{};if(s.init)s.init(st);redraw();save(false);if(!FR.P)setHash('#why/'+(n+1))}
function setHash(h){try{history.replaceState(null,'',location.pathname+location.search+h)}catch(e){}}
/* ---- remembering (browser + server; Skip, Esc and the doors set done) */
function save(done){const cur=LS.get('gs_fr_seen',{})||{};const d={v:1,screen:FR.i,done:!!(done||cur.done)};LS.set('gs_fr_seen',d);if(done)LS.set('gs_seen3',1);
 api.post('/api/firstrun/seen',{seen:d.done,screen:d.screen}).catch(()=>{})}
/* ---- clicks inside the story */
function onClick(e){const t=e.target.closest&&e.target.closest('button,a');if(!t)return;const s=FR.cur(),st=FR.st[s.id]=FR.st[s.id]||{};
 if(t.tagName==='A')return;
 if(t.dataset.go){e.preventDefault();e.stopPropagation();const g=t.dataset.go;closeWhy(false,true);if(FR.P)exitPresent(true);goApp(g);return}
 if(t.dataset.door){e.preventDefault();e.stopPropagation();const d=t.dataset.door;closeWhy(true,true);if(FR.P)exitPresent(true);
  if(d==='learn')goApp('learn:1');else if(d==='p0')goApp('p0');else if(d==='mine'){if(hasView('mine'))show('mine');else goApp('x-gal')}else if(d==='teach'){try{window.open('/teach','_blank')}catch(x){}}return}
 if(t.id==='fr-skip'){closeWhy(true);return}
 if(t.id==='fr-next'){if(FR.i===SCR.length-1)closeWhy(true);else goScreen(FR.i+1);return}
 if(t.id==='fr-back'){goScreen(FR.i-1);return}
 if(t.id==='fr-present'){closeWhy(true,true);startPresent();return}
 if(t.id==='fr-act'){if(s.acts&&s.acts[0])s.acts[0](st);return}
 if(t.id==='fr-drop'){dropAt(st,st.g==null?0:st.g);return}
 if(t.dataset.sel!=null){t.focus();pick(st,+t.dataset.sel);const b=host().querySelector(`.fr-seg [data-sel="${t.dataset.sel}"]`);b&&b.focus();return}
 if(t.dataset.chip){st.ch=t.dataset.chip;redraw(false);const b=document.querySelector(`[data-chip="${st.ch}"]`);b&&b.focus();return}}
function goApp(g){if(g==='labs'){if(hasView('labs'))show('labs');else go_('studies');return}if(g==='mine'){if(hasView('mine'))show('mine');else go_('x-gal');return}go_(g)}
/* ---- keys: capture phase, only while the story or Presenter mode is active */
function focusables(){return [...host().querySelectorAll('button:not([disabled]),a[href],summary,[tabindex="0"]')].filter(x=>x.offsetParent!==null)}
addEventListener('keydown',e=>{if(e.ctrlKey||e.metaKey||e.altKey)return;const k=e.key,tn=(e.target.tagName||'');
 if(FR.P){if(FR.P.blank&&k!=='b'&&k!=='B'&&k!=='Escape'){e.preventDefault();e.stopPropagation();return}
  const m={ArrowRight:next,PageDown:next,' ':next,ArrowLeft:prev,PageUp:prev,ArrowDown:()=>presScrollBy(1),ArrowUp:()=>presScrollBy(-1),Home:()=>enterStop(0),n:openNotes,N:openNotes,b:blank,B:blank,Escape:()=>exitPresent()}[k];
  if(m){e.preventDefault();e.stopPropagation();m()}else if(FR.open&&k==='Tab')trap(e);else if(!FR.open&&/^[1-9`?vVtTsSfFlL]$/.test(k)){e.stopPropagation()}return}
 if(FR.open){if(e.target.classList&&e.target.classList.contains('fr-glitch')&&(k==='ArrowRight'||k==='ArrowLeft'||k==='Enter'||k===' '))return;
  e.stopPropagation();
  if(k==='Escape'){e.preventDefault();closeWhy(true);return}
  if(k==='Tab'){trap(e);return}
  const inSeg=e.target.closest&&e.target.closest('.fr-seg');
  if(inSeg&&(k==='ArrowRight'||k==='ArrowLeft')){e.preventDefault();const bs=[...inSeg.querySelectorAll('button')],j=bs.indexOf(document.activeElement),n=(j+(k==='ArrowRight'?1:-1)+bs.length)%bs.length;bs[n].click();return}
  if(k==='ArrowRight'&&tn!=='INPUT'){e.preventDefault();if(FR.mode!=='close')goScreen(FR.i+1);return}
  if(k==='ArrowLeft'&&tn!=='INPUT'){e.preventDefault();if(FR.mode!=='close')goScreen(FR.i-1);return}
  if(k==='p'||k==='P'){e.preventDefault();closeWhy(true,true);startPresent();return}
  return}
 if((k==='p'||k==='P')&&!(tn==='INPUT'||tn==='TEXTAREA'||tn==='SELECT')&&!S.dlg&&!S.help){e.preventDefault();e.stopPropagation();startPresent()}},true);
function trap(e){const f=focusables();if(!f.length)return;const a=f[0],b=f[f.length-1];if(!host().contains(document.activeElement)){e.preventDefault();a.focus();return}
 if(e.shiftKey&&document.activeElement===a){e.preventDefault();b.focus()}else if(!e.shiftKey&&document.activeElement===b){e.preventDefault();a.focus()}}
/* ---- Presenter mode (design section 5): nine stops through the real views */
const STOPS=[
 {t:'Can a tiny glitch open a lock?',kind:'story',i:0,pace:'1:00'},
 {t:'How a glitch attack works',kind:'story',i:1,pace:'2:30'},
 {t:'How a chip protects itself, in its code',kind:'story',i:2,pace:'2:00'},
 {t:'Do copies help?',kind:'story',i:3,pace:'1:00'},
 {t:'The finished design can be different',kind:'story',i:4,pace:'1:30'},
 {t:'The lesson: the hidden danger',kind:'app',pace:'0:45',enter:()=>goApp('learn:8'),view:'learn',say:()=>'Here’s the lesson that explains this for beginners.',expect:()=>'Expect: lesson screen “The hidden danger”'},
 {t:'Live example: two copies',kind:'app',pace:'1:00',enter:()=>{if(typeof loadStep==='function'&&!S.busy)loadStep(1);else show('analyze')},view:'analyze',say:()=>'Now live: two copies. Watch it find the one wire.',expect:()=>`Expect: ${fl(V('v1'))}${F('v1')&&F('v1').shared?' on the shared wire '+F('v1').shared:''}`},
 {t:'A whole open-source chip design',kind:'app',pace:'1:30',scrollTo:'#v-explore .take',enter:()=>{S.chipSel='picosoc';if(typeof openExplore==='function')openExplore('x-chip')},view:'explore',say:()=>{const p=V('chip_pico');return `The same check on a whole open-source chip design: ${p?`${p.written}, ${p.keep} or ${p.flat}`:'a different number'}, by build.`},expect:()=>{const p=V('chip_pico');return p?`Expect: PicoSoC ${p.written} / ${p.keep} / ${p.flat}`:'Expect: PicoSoC page'}},
 {t:'Open my design',kind:'app',pace:'1:00',enter:()=>goApp('mine'),view:()=>hasView('mine')?'mine':'explore',acts:[()=>{const b=document.querySelector('#v-mine #by-ex [data-ex]');if(b)b.click()}],alab:['Run example'],say:()=>'Designers can bring their own design. Here’s an example. Every finding says what, how bad, and how we found it.',expect:()=>hasView('mine')?'Expect: the first gallery example runs':'Expect: the example gallery'},
 {t:'Studies: many builds of one lock',kind:'app',pace:'1:00',enter:()=>show('findings'),view:'findings',say:()=>{const e=V('e2');return e?`The same three-copy lock, built ${e.total} ways: 1 flip in ${e.min1}, 2 in ${e.min2}, 3 in ${e.min3}. The answer depends on the build.`:'The same three-copy lock, built many ways: the answer depends on the build.'},expect:()=>'Expect: the Studies page (do not press “Run all studies”)'},
 {t:'What it checks today',kind:'close',pace:'1:00'}];
const SEC_MIN=6e1;function paceS(t){const m=/^(\d+):(\d\d)$/.exec(t||'1:00');return m?(+m[1])*SEC_MIN+(+m[2]):25}  /* the phone script's time for a stop, m:ss */
function stopSay(s){return s.kind==='story'?SCR[s.i].say():s.kind==='close'?CLOSE.say():s.say()}
function stopExpect(s){return s.kind==='story'?SCR[s.i].expect():s.kind==='close'?CLOSE.expect():s.expect()}
function stopActs(s){return s.kind==='story'?(SCR[s.i].acts||[]):(s.acts||[])}
function stopPress(s,step){const a=stopActs(s),l=s.kind==='story'?(SCR[s.i].alab||[]):(s.alab||[]);return step<a.length?(l[step]||'the action'):'the next stop'}
function startPresent(short){if(S.story!=null&&typeof closeStory==='function')closeStory(true);if(S.dlg&&typeof closeDlg==='function'){S.dlg.opener=null;closeDlg()}
 const order=short?[0,STOPS.findIndex(x=>x.kind==='story'&&SCR[x.i].id==='build'),STOPS.length-1]:STOPS.map((_,j)=>j);FR.P={order,k:0,step:0,t0:Date.now(),ts:Date.now(),blank:false,short:!!short,pred:S.predOn};S.fr=true;S.predOn=false;S.predPick={};
 document.documentElement.classList.add('present');try{const r=document.documentElement.requestFullscreen&&document.documentElement.requestFullscreen();if(r&&r.catch)r.catch(()=>{})}catch(e){}
 bars();FR.ready.then(()=>enterStop(0));setHash(short?'#present?short=30':'#present')}
function exitPresent(keep){if(!FR.P)return;S.predOn=FR.P.pred===undefined?LS.get('gs_predict',null):FR.P.pred;S.predPick={};FR.P=null;S.fr=false;document.documentElement.classList.remove('present');['fr-pbar','fr-ptop','fr-blank'].forEach(id=>{const n=document.getElementById(id);if(n)n.hidden=true});
 try{if(document.fullscreenElement&&document.exitFullscreen)document.exitFullscreen().catch(()=>{})}catch(e){}
 if(!keep){if(FR.open)closeWhy(false,true);show('start');const b=$('#b-why');b&&b.focus()}setHash('');sync()}
function enterStop(k){const P=FR.P;if(!P)return;P.k=Math.max(0,Math.min(P.order.length-1,k));P.step=0;P.ts=Date.now();const s=STOPS[P.order[P.k]];
 if(s.kind==='story'){FR.i=s.i;FR.st[SCR[s.i].id]={};openWhy(s.i,{mode:null,hash:false})}else if(s.kind==='close'){openWhy(0,{mode:'close',hash:false})}else{if(FR.open)closeWhy(false,true);S.fr=true;s.enter()}
 bars();sync();FR.ready.then(()=>setTimeout(()=>{if(FR.P&&FR.P.k===P.k){if(FR.open)host().scrollTop=0;if(s.scrollTo)presScroll(s.scrollTo)}},80))}
/* Presenter: what a press revealed is scrolled into view (the card is taller than the screen when the text is scaled up) */
function revealNew(id){if(!FR.P||!FR.open)return;const h=host(),st=FR.st[id]||{};let el=null;
 if(id==='how')el=st.drop!=null?h.querySelector('.fr-res p'):(h.querySelector('.fr-bridge')||[...h.querySelectorAll('.fr-how li.on')].pop());
 else if(id==='code')el=h.querySelector('.fr-res .fr-bridge');
 else el=h.querySelector('.fr-res');
 if(el)el.scrollIntoView({block:'nearest'})}
function presScroll(sel,tries){tries=tries==null?30:tries;const el=document.querySelector(sel);if(el){el.scrollIntoView({block:'center'});return}if(tries>0)setTimeout(()=>presScroll(sel,tries-1),100)}
/* Down / Up arrow: scroll what is on screen (the card, or the app view) by part of a screen, never change the stop */
function presScrollBy(dir){const v=FR.open?host():(document.querySelector('main .view:not(.hidden)')||document.scrollingElement);
 const box=v===document.scrollingElement?innerHeight:v.clientHeight;v.scrollBy({top:dir*Math.round(box*.4),behavior:'auto'})}
function next(){const P=FR.P;if(!P)return;const s=STOPS[P.order[P.k]],acts=stopActs(s);
 if(P.step<acts.length){const st=s.kind==='story'?(FR.st[SCR[s.i].id]=FR.st[SCR[s.i].id]||{}):null;acts[P.step](st);P.step++;bars();sync();if(s.kind==='story'){const id=SCR[s.i].id;setTimeout(()=>revealNew(id),80)}return}
 if(P.k<P.order.length-1)enterStop(P.k+1)}
function prev(){const P=FR.P;if(P&&P.k>0)enterStop(P.k-1)}
function blank(){const P=FR.P;if(!P)return;P.blank=!P.blank;let b=document.getElementById('fr-blank');if(!b){b=document.createElement('div');b.id='fr-blank';b.setAttribute('aria-label','Screen blanked; press B');document.body.appendChild(b)}b.hidden=!P.blank}
function bars(){const P=FR.P;let b=document.getElementById('fr-pbar'),t=document.getElementById('fr-ptop');
 if(!b){b=document.createElement('div');b.id='fr-pbar';b.setAttribute('role','region');b.setAttribute('aria-label','Presenter controls');document.body.appendChild(b)}
 if(!t){t=document.createElement('div');t.id='fr-ptop';document.body.appendChild(t)}
 if(!P){b.hidden=true;t.hidden=true;return}const s=STOPS[P.order[P.k]];b.hidden=false;
 b.innerHTML=`<b>stop ${P.k+1} of ${P.order.length}</b><span>${esc(s.t)}</span><span class="sp"></span><span>← → · N notes · B blank · Esc to leave</span><button class="btn" id="fr-prev" aria-label="Previous stop">←</button><button class="btn" id="fr-next-stop" aria-label="Next">→</button><button class="btn" id="fr-notes">Notes</button><button class="btn" id="fr-exit">Leave</button>`;
 const on=(id,f)=>{const x=b.querySelector('#'+id);if(x)x.onclick=e=>{e.stopPropagation();f()}};on('fr-prev',prev);on('fr-next-stop',next);on('fr-notes',openNotes);on('fr-exit',()=>exitPresent());
 t.hidden=s.kind!=='app';t.textContent=s.kind==='app'?`GlitchSAT · ${s.t}`:''}
/* ---- speaker notes in a second window on this computer (BroadcastChannel, else the storage event) */
let BC=null;try{BC=new BroadcastChannel('gs-present')}catch(e){BC=null}
function post(m){if(BC){try{BC.postMessage(m)}catch(e){}}else{try{localStorage.setItem('gs_present_sync',JSON.stringify(Object.assign({n:Date.now()},m)))}catch(e){}}}
function onMsg(m){if(!m||m.from!=='notes')return;if(m.cmd==='hello'){sync();return}if(m.cmd==='start'&&!FR.P){startPresent();return}if(!FR.P)return;if(m.cmd==='next')next();else if(m.cmd==='prev')prev();else if(m.cmd==='home')enterStop(0);else if(m.cmd==='blank')blank();else if(typeof m.stop==='number'&&m.cmd==='goto')enterStop(m.stop)}
if(BC)BC.onmessage=e=>onMsg(e.data);addEventListener('storage',e=>{if(e.key==='gs_present_sync'&&e.newValue){try{onMsg(JSON.parse(e.newValue))}catch(x){}}});
function sync(){const P=FR.P;if(!P){post({from:'main',on:false});return}const s=STOPS[P.order[P.k]],nx=STOPS[P.order[P.k+1]];
 const st=s.kind==='story'?FR.st[SCR[s.i].id]||{}:{};const rs=[st.r].flat().filter(Boolean);
 post({from:'main',on:true,stop:P.k,total:P.order.length,step:P.step,steps:stopActs(s).length,press:stopPress(s,P.step),title:s.t,say:stopSay(s),expect:stopExpect(s),next:nx?nx.t:'(last stop)',fb:rs.some(x=>x&&x.fb),t0:P.t0,ts:P.ts,pace:paceS(P.short?'0:30':s.pace)})}
function openNotes(){try{window.open('/present-notes','gs-notes','width=720,height=560')}catch(e){}}
/* ---- start-up: first launch, resume toast, addresses (#why, #why/3, #present, ?present=1) */
FR.ready=Promise.all([api.get('/api/firstrun/facts').then(f=>{FR.F=f&&!f.error?f:{}}).catch(()=>{FR.F={}}),
 api.get('/api/firstrun/seen').then(s=>{FR.srv=s}).catch(()=>{FR.srv=null})]);
function fromHash(){const h=location.hash;let m=/^#why(?:\/(\d+))?$/.exec(h);if(m){openWhy(m[1]?+m[1]-1:0,{hash:false});return true}
 if(/^#present/.test(h)||Q.get('present')==='1'){if(!FR.P)startPresent(/short=30/.test(h)||Q.get('short')==='30');return true}return false}
addEventListener('hashchange',()=>{if(/^#(why|present)/.test(location.hash)&&!FR.P&&!FR.open)fromHash()});
Studio.firstRun=()=>{if(FR.open||FR.P)return true;if(fromHash())return true;
 if(window.GS_NO_WELCOME||Q.get('firstrun')==='0')return false;   /* test harnesses: ?firstrun=0 or GLITCHSAT_FIRSTRUN=0 keep the old first-launch story */
 const b=LS.get('gs_fr_seen',null);
 if(!FRESH&&b&&b.done)return false;
 FR.ready.then(()=>{const s=FR.srv||{};if(FR.open||FR.P)return;
  if(!FRESH&&s.seen){LS.set('gs_fr_seen',{v:1,screen:s.screen||0,done:true});LS.set('gs_seen3',1);return}
  const started=!FRESH&&((b&&!b.done)||(s.started&&!s.seen));
  if(started){showToast(Math.max(b&&b.screen||0,s.screen||0));return}
  openWhy(0)});
 return true};
setTimeout(()=>{if(!FR.open&&!FR.P)fromHash()},0);
function showToast(n){let t=document.getElementById('fr-toast');if(!t){t=document.createElement('div');t.id='fr-toast';t.setAttribute('role','status');document.body.appendChild(t)}
 t.innerHTML=`<span>Continue <b>Why GlitchSAT?</b> (screen ${n+1} of ${SCR.length})</span><button class="btn primary" id="fr-cont">Continue</button><button class="btn" id="fr-dis">Dismiss</button>`;t.hidden=false;
 t.querySelector('#fr-cont').onclick=()=>{hideToast();openWhy(n,{opener:$('#b-why')})};t.querySelector('#fr-dis').onclick=()=>{hideToast();FR.i=n;save(true);const b=$('#b-why');b&&b.focus()}}
function hideToast(){const t=document.getElementById('fr-toast');if(t)t.hidden=true}
/* ---- links: data-go="why", "why:N", "present", "present:30" (chained: learn_view and others keep theirs) */
{const prev=Studio.onGo;Studio.onGo=g=>{const m=/^why(?::(\d+))?$/.exec(g);if(m){openWhy(m[1]?+m[1]-1:0);return true}
 if(/^present/.test(g)){startPresent(/30$/.test(g));return true}if(g==='labs'&&hasView('labs')){show('labs');return true}
 return prev?prev(g):false}}
/* ---- the top-bar link, a line on Start, a line in About */
function topLink(){if($('#b-why'))return;const lg=document.querySelector('header .logo');if(!lg)return;const b=document.createElement('button');b.className='linkb fr-why';b.id='b-why';b.dataset.go='why';b.innerHTML='<span class="l">Why GlitchSAT?</span><span class="s" aria-hidden="true">Why?</span>';b.setAttribute('aria-label','Why GlitchSAT?');b.setAttribute('data-tip','Why this app was built, how a glitch attack works, how chips protect themselves, what it found and what it checks today: nine short screens (also Presenter mode: P)');lg.insertAdjacentElement('afterend',b)}
topLink();
{const prevS=Studio.startExtra;Studio.startExtra=()=>(prevS?prevS():'')+`<p class="fr-startline"><b>First time here?</b> <button class="linkb" data-go="why">Why GlitchSAT?</button> explains in nine short screens why it was built, what it found and what it checks today. Presenting it? <button class="linkb" data-go="present">Presenter mode</button> (key P).</p>`}
{const prevA=Studio.aboutExtra;Studio.aboutExtra=()=>(prevA?prevA():'')+`<div class="panel"><div class="ph"><h4>Why GlitchSAT?</h4></div><div class="pb"><p style="margin:0">The nine-screen welcome story: <button class="linkb" data-go="why">open it</button> · <button class="linkb" id="fr-reset" onclick="FirstRun.reset()">Show the welcome again</button> at the next start · <button class="linkb" data-go="present">Presenter mode</button> (key P; key N opens the speaker notes in a second window on this computer).</p></div></div>`}
if(typeof S!=='undefined'&&S.tab==='start'&&typeof drawStart==='function')drawStart();
window.FirstRun={SCR,STOPS,CLOSE,FR,open:openWhy,close:closeWhy,present:startPresent,exit:exitPresent,next,prev,enterStop,goScreen,
 reset:()=>{LS.set('gs_fr_seen',{v:1,screen:0,done:false});FR.i=0;api.post('/api/firstrun/seen',{seen:false,screen:0}).then(()=>{try{fetch('/api/firstrun/seen')}catch(e){}}).catch(()=>{});announce('The welcome will show at the next start.')},
 noLive:v=>{FR.noLive=!!v;FR.res={}}};
})();
"""

# ------------------------------------------------------------------ the speaker-notes page (/present-notes)
NOTES_PAGE = r"""<!doctype html><html lang="en" data-theme="dark"><head><meta charset="utf-8"><title>GlitchSAT: speaker notes</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>
:root{--bg:#0e1116;--panel:#151a21;--line:#39434f;--txt:#e3e8ee;--mut:#9aa5b3;--acc:#6ea2ff;--acc-t:#0b1220;--warn:#e0a13a}
html[data-theme=light]{--bg:#f3f5f8;--panel:#fff;--line:#bcc5d0;--txt:#18212c;--mut:#4f5c6b;--acc:#1f63d8;--acc-t:#fff;--warn:#8a5700}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--txt);font:16px/1.45 system-ui,-apple-system,"Segoe UI",Ubuntu,"Noto Sans",sans-serif}
main{max-width:900px;margin:0 auto;padding:14px 18px 28px}
.top{display:flex;gap:10px;align-items:center;flex-wrap:wrap;color:var(--mut)}.top .sp{flex:1}
#say{font-size:clamp(24px,4.2vw,40px);line-height:1.3;font-weight:650;margin:14px 0 10px;min-height:3em}
#exp{font-size:20px;border-left:5px solid var(--acc);padding:4px 12px;background:var(--panel)}
#fb{color:var(--warn);font-weight:700;min-height:1.4em;margin:6px 0}
#nxt{color:var(--mut);margin:8px 0}#press{font-size:18px;margin:6px 0}
.tm{font-size:28px;font-variant-numeric:tabular-nums}.tm.over{color:var(--warn)}
.btns{display:flex;gap:10px;margin:14px 0}.btns button{font:inherit;font-size:22px;min-width:96px;min-height:56px;border-radius:8px;border:1px solid var(--line);background:var(--panel);color:var(--txt);cursor:pointer}
.btns button.p{background:var(--acc);border-color:var(--acc);color:var(--acc-t);font-weight:700}
:focus-visible{outline:3px solid var(--acc);outline-offset:2px}
.help{color:var(--mut);font-size:14px}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style></head><body><main>
<div class="top"><b>Speaker notes</b><span id="pos">waiting for the app…</span><span class="sp"></span><span class="tm" id="tall" aria-label="time since the start">0:00</span><span class="tm" id="tstop" aria-label="time on this stop">0:00</span></div>
<p id="say" aria-live="polite">Start Presenter mode in the app (key P), or press Start.</p>
<p id="exp"></p><p id="press"></p><p id="fb" role="status"></p><p id="nxt"></p>
<div class="btns"><button id="b-prev" aria-label="Previous stop">←</button><button id="b-next" class="p" aria-label="Next">→</button><button id="b-start">Start</button></div>
<p class="help">Use a second window on this computer. The app answers only this computer, so a phone cannot join. Keys here: ← → (or a clicker), Home.
Target pace: the time the phone script plans for each stop; the stop timer turns amber when a stop runs over it.</p>
</main><script>
"use strict";
try{const t=JSON.parse(localStorage.getItem('gs_theme')||'"dark"');document.documentElement.dataset.theme=t==='light'?'light':'dark'}catch(e){}
let BC=null;try{BC=new BroadcastChannel('gs-present')}catch(e){}
const post=m=>{m.from='notes';if(BC)BC.postMessage(m);else try{localStorage.setItem('gs_present_sync',JSON.stringify(Object.assign({n:Date.now()},m)))}catch(e){}};
let st=null;const $=s=>document.querySelector(s);
const mmss=ms=>{const s=Math.max(0,Math.floor(ms/1000));return Math.floor(s/60)+':'+String(s%60).padStart(2,'0')};
function draw(){if(!st||!st.on){$('#pos').textContent='Presenter mode is not running';$('#say').textContent='Start Presenter mode in the app (key P), or press Start.';$('#exp').textContent='';$('#press').textContent='';$('#fb').textContent='';$('#nxt').textContent='';return}
 $('#pos').textContent='stop '+(st.stop+1)+' of '+st.total+(st.steps?' · step '+Math.min(st.step,st.steps)+' of '+st.steps:'')+' · '+st.title;
 $('#say').textContent='“'+st.say+'”';$('#exp').textContent=st.expect||'';$('#press').textContent='→ does: '+(st.press||'the next stop');$('#fb').textContent=st.fb?'Live result not ready: recorded value shown':'';$('#nxt').textContent='Next: '+st.next}
function tick(){if(st&&st.on){$('#tall').textContent=mmss(Date.now()-st.t0);const d=Date.now()-st.ts;$('#tstop').textContent=mmss(d);$('#tstop').classList.toggle('over',d>(st.pace||25)*1000)}}
function onMsg(m){if(!m||m.from!=='main')return;st=m;draw();tick()}
if(BC)BC.onmessage=e=>onMsg(e.data);addEventListener('storage',e=>{if(e.key==='gs_present_sync'&&e.newValue)try{onMsg(JSON.parse(e.newValue))}catch(x){}});
$('#b-next').onclick=()=>post({cmd:'next'});$('#b-prev').onclick=()=>post({cmd:'prev'});$('#b-start').onclick=()=>post({cmd:'start'});
addEventListener('keydown',e=>{if(e.key==='ArrowRight'||e.key==='PageDown'||e.key===' '){e.preventDefault();post({cmd:'next'})}else if(e.key==='ArrowLeft'||e.key==='PageUp'){e.preventDefault();post({cmd:'prev'})}else if(e.key==='Home'){e.preventDefault();post({cmd:'home'})}});
setInterval(tick,500);post({cmd:'hello'});
</script></body></html>"""
