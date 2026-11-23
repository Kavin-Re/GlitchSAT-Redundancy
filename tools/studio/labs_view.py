"""GlitchSAT Studio: the "Labs" tab - experiments in progress (try them, don't rely on them).

Loaded by studio.py through one marked hook (LABS-VIEW): install(PAGE) adds the style and script, and handle(...)
answers two requests:
  GET /api/labs                 the Labs modules and their last results (read from labs-result/1 files)
  GET /labs/readme/<module>     the module's README.md as a simple, printable page
The tab is added with the page's extension point Studio.registerView({id:'labs', ...}). It sits at the end of the tab
bar's "More" menu (at every window size) and is not linked from Start, the story or the guided path.
Nothing here runs a Labs module; the page only shows the saved result files (ext/labs/labs.py runs them).
"""
import html
import importlib.util
import json
import os
import re

CSS = r"""
.lb{max-width:1180px;margin:0 auto}
.lb h2{font-size:22px;margin:4px 0 6px}
.lb-intro{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--warn);border-radius:8px;padding:12px 16px;margin:0 0 12px}
.lb-intro p{margin:5px 0;line-height:1.5;max-width:900px}
.lb-intro .lead{font-size:16px}
.lb-legend{display:flex;flex-wrap:wrap;gap:8px 18px;margin-top:8px;font-size:13px;color:var(--mut)}
.lb-legend span{display:inline-flex;gap:6px;align-items:center}
.lb-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:12px}
.lb-card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px;display:flex;flex-direction:column;gap:6px;min-width:0}
.lb-card.planned{border-style:dashed}
.lb-card h3{margin:0;font-size:16px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.lb-badge{font:700 11px var(--sans);letter-spacing:.6px;padding:2px 7px;border-radius:3px;border:1px solid var(--warn);color:var(--warn);white-space:nowrap}
.lb-badge.planned{border-color:var(--line2);color:var(--mut)}
.lb-q{margin:0;line-height:1.45}
.lb-q b,.lb-sub{font-size:11.5px;letter-spacing:.5px;text-transform:uppercase;color:var(--mut);font-weight:700}
.lb-sub{display:block;margin-top:4px}
.lb-f{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:5px}
.lb-f li{font-size:13.5px;line-height:1.42;background:var(--inset);border:1px solid var(--line);border-radius:6px;padding:5px 8px;overflow-wrap:anywhere}
.lb-lab{display:inline-block;font:700 10.5px var(--sans);letter-spacing:.5px;padding:0 6px;border-radius:3px;border:1px solid var(--line2);margin-right:6px;vertical-align:1px;white-space:nowrap}
.lb-lab.MEASURED{border-color:var(--ok);color:var(--ok)}
.lb-lab.SIMULATED{border-color:var(--acc);color:var(--acc)}
.lb-lab.UNTESTED{border-color:var(--line2);color:var(--mut);border-style:dashed}
.lb-card details{font-size:13px}
.lb-card summary{cursor:pointer;color:var(--acc);margin:2px 0}
.lb-card details ul{margin:4px 0 2px 18px;padding:0}.lb-card details li{margin:2px 0}
.lb-foot{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:auto;padding-top:6px;border-top:1px solid var(--line);font-size:12.5px;color:var(--mut)}
.lb-foot a{color:var(--acc)}
.lb-foot code{font-size:12px;overflow-wrap:anywhere}
.lb-f code{font-size:12.5px;background:var(--panel);border:1px solid var(--line);border-radius:3px;padding:0 3px}
.lb-empty{color:var(--mut);font-size:13.5px;margin:0}
"""

JS = r"""
/* ==== Labs tab (labs_view.py). Uses the extension point Studio.registerView. Shows saved Labs results only. ==== */
(function(){
const esc=Studio.esc, LAB={MEASURED:'measured with real tools',SIMULATED:'result of a model, not a real chip',UNTESTED:'not checked yet'};
let data=null, err=null;
function lab(l){return `<span class="lb-lab ${esc(l)}" title="${esc(LAB[l]||'')}">${esc(l)}</span> `}
/* dates as in the rest of the app: 2026-11-21 10:20 (local time), never the browser's US order */
function isoWhen(x){const d=new Date(x);if(isNaN(d))return String(x||'');const p=n=>String(n).padStart(2,'0');
 return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`}
function card(m){
 const pl=m.status==='PLANNED', f=m.findings||[], first=f.slice(0,4), rest=f.slice(4);
 const li=x=>`<li>${lab(x.label)}${esc(x.text).replace(/`([^`]+)`/g,'<code>$1</code>')}</li>`;
 const when=m.last_run?isoWhen(m.last_run):null;
 if(m.withheld)return `<section class="lb-card withheld" aria-labelledby="lb-h-${esc(m.id)}">
  <h3 id="lb-h-${esc(m.id)}">${esc(m.title)} <span class="lb-badge">EXPERIMENTAL</span></h3>
  <ul class="lb-f">${(f.length?f.slice(0,1):[{label:'UNTESTED',text:m.question}]).map(li).join('')}</ul>
  <div class="lb-foot"><a href="/labs/readme/${encodeURIComponent(m.id)}" target="_blank" rel="noopener">README: limits and what can be shown</a></div>
 </section>`;
 return `<section class="lb-card${pl?' planned':''}" aria-labelledby="lb-h-${esc(m.id)}">
  <h3 id="lb-h-${esc(m.id)}">${esc(m.title)} <span class="lb-badge${pl?' planned':''}">${pl?'PLANNED':'EXPERIMENTAL'}</span></h3>
  <p class="lb-q"><b>What it tries to answer</b><br>${esc(m.question)}</p>
  ${pl?`<p class="lb-empty">No code yet. The idea and the rule format are described in the Labs notes.</p>`:
   f.length?`<span class="lb-sub">What the last try found${when?' ('+esc(when)+')':''}</span><ul class="lb-f">${first.map(li).join('')}</ul>
   ${rest.length?`<details><summary>Show the other ${rest.length} finding${rest.length>1?'s':''}</summary><ul class="lb-f">${rest.map(li).join('')}</ul></details>`:''}
   ${(m.caveats||[]).length?`<details><summary>How far to trust this</summary><ul>${m.caveats.map(c=>`<li>${esc(c)}</li>`).join('')}</ul></details>`:''}`
   :`<p class="lb-empty">Not run on this computer yet.</p>`}
  <div class="lb-foot"><a href="/labs/readme/${encodeURIComponent(m.id)}" target="_blank" rel="noopener">${pl?'Labs notes':'README'}: what works, what doesn't</a>
   ${pl?'':`<span class="tech-only">run: <code>${esc(m.run_cmd||('python3 labs.py run '+m.id))}</code></span>`}</div>
 </section>`}
function draw(el){
 const intro=`<div class="lb-intro"><h2 id="lb-top" tabindex="-1">Labs: experiments in progress</h2>
  <p class="lead"><b>Try them, don't rely on them.</b> These are new checks that are only partly built. Each one already works on a small example, but it has not been finished or checked as carefully as the rest of GlitchSAT.</p>
  <p>Every result carries a label that says where it comes from:</p>
  <div class="lb-legend"><span>${lab('MEASURED')} counted by running real tools</span><span>${lab('SIMULATED')} the answer of a model, not of a real chip</span><span>${lab('UNTESTED')} not checked yet</span></div></div>`;
 let body;
 if(err)body=`<p class="lb-empty">The Labs results could not be read (${esc(err)}).</p>`;
 else if(!data)body=`<p class="lb-empty">Loading…</p>`;
 else if(data.missing)body=`<p class="lb-empty">The Labs folder was not found on this computer, so there is nothing to show.</p>`;
 else body=`<div class="lb-grid keep">${data.modules.map(card).join('')}</div>`;   /* keep: saved result text is shown word for word (no Plain-view word changes) */
 el.innerHTML=`<div class="lb">${intro}${body}</div>`;
}
function load(el){if(data||err){draw(el);return}draw(el);Studio.api.get('/api/labs').then(d=>{data=d;draw(el)}).catch(e=>{err=String(e&&e.message||e);draw(el)})}
function reg(){if(typeof TAB_OVF!=='undefined'&&!TAB_OVF.includes('labs'))TAB_OVF.push('labs');
 if(typeof TAB_MORE_ONLY!=='undefined'&&!TAB_MORE_ONLY.includes('labs'))TAB_MORE_ONLY.push('labs');   /* always in the More menu, never beside About */
 Studio.registerView({id:'labs',title:'Labs',tip:'Labs: experiments in progress. Try them, don\'t rely on them',show:el=>load(el)})}
/* registered after every other add-on, so the number keys of the existing tabs stay the same */
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',reg);else reg();
window.LabsView={draw:()=>load(document.querySelector('#v-labs'))};
})();
"""


def install(page):
    """Return the page with the Labs style and script added (after the main script, so its helpers exist)."""
    page = page.replace('</style></head>', CSS + '</style></head>', 1)
    i = page.rfind('</body>')
    return page[:i] + '<script>' + JS + '</script>' + page[i:]


def _labs_module(ext):
    """The Labs registry (labs.py): $GLITCHSAT_LABS, <ext>/labs (the Studio passes the folder it found the modules in),
    then the Studio's own neighbours: tools/labs beside tools/studio (repository layout), ext/labs (development layout)."""
    here = os.path.dirname(os.path.abspath(__file__))
    cands = [os.environ.get('GLITCHSAT_LABS', ''), os.path.join(ext, 'labs') if ext else '',
             os.path.join(os.path.dirname(here), 'labs'), os.path.join(os.path.dirname(here), 'ext', 'labs')]
    for d in cands:
        p = os.path.join(d, 'labs.py')
        if d and os.path.isfile(p):
            spec = importlib.util.spec_from_file_location('glitchsat_labs', p)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            return m
    return None


def modules(ext):
    m = _labs_module(ext)
    if m is None:
        return dict(missing=True)
    out = []
    for mid in m.MODULES:
        s = m.summary(mid)
        out.append({k: s.get(k) for k in ('id', 'title', 'status', 'question', 'last_run', 'ok', 'counts', 'findings', 'caveats', 'withheld')})
    return dict(modules=out)


def _inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1', s)       # links to other files: text only (files are not served)
    return s


def md_to_html(md):
    """Small Markdown subset: headings, paragraphs, lists, tables, code blocks. Enough for the Labs READMEs."""
    out, para, lst, tbl, code = [], [], False, [], None
    def flush():
        nonlocal para, lst, tbl
        if para:
            out.append('<p>%s</p>' % _inline(' '.join(para)))
            para = []
        if lst:
            out.append('</ul>')
            lst = False
        if tbl:
            rows = [r for r in tbl if not re.match(r'^\|[\s\-:|]+\|$', r)]
            cells = [[c.strip() for c in r.strip('|').split('|')] for r in rows]
            h = ''.join('<th>%s</th>' % _inline(c) for c in cells[0])
            b = ''.join('<tr>%s</tr>' % ''.join('<td>%s</td>' % _inline(c) for c in r) for r in cells[1:])
            out.append('<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (h, b))
            tbl = []
    for line in md.splitlines():
        if code is not None:
            if line.startswith('```'):
                out.append('<pre>%s</pre>' % html.escape('\n'.join(code)))
                code = None
            else:
                code.append(line)
            continue
        if line.startswith('```'):
            flush()
            code = []
        elif line.startswith('#'):
            flush()
            n = len(line) - len(line.lstrip('#'))
            out.append('<h%d>%s</h%d>' % (min(n, 4), _inline(line.lstrip('#').strip()), min(n, 4)))
        elif line.startswith('|'):
            if para or lst:
                t, tbl = tbl, []
                flush()
                tbl = t
            tbl.append(line)
        elif re.match(r'^\s*[-*] ', line) or re.match(r'^\d+\. ', line):
            if para or tbl:
                flush()
            if not lst:
                out.append('<ul>')
                lst = True
            out.append('<li>%s</li>' % _inline(re.sub(r'^\s*([-*]|\d+\.) ', '', line)))
        elif line.strip() == '':
            flush()
        elif lst and line.startswith('  '):
            out[-1] = out[-1][:-5] + ' ' + _inline(line.strip()) + '</li>'
        else:
            if tbl:
                flush()
            para.append(line.strip())
    flush()
    return '\n'.join(out)


PAGE_CSS = """:root{--bg:#f3f5f8;--panel:#fff;--line:#cfd6df;--txt:#18212c;--mut:#4f5c6b;--acc:#1f63d8;--warn:#8a5700}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Ubuntu,"Noto Sans",sans-serif}
main{max-width:980px;margin:0 auto;padding:18px 22px 40px}.ban{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--warn);border-radius:6px;padding:8px 14px;margin:0 0 10px}
h1{font-size:24px;margin:10px 0 6px}h2{font-size:19px;margin:22px 0 6px;padding-top:8px;border-top:2px solid var(--line)}h3{font-size:16px}
code,pre{font-family:ui-monospace,"DejaVu Sans Mono",Menlo,Consolas,monospace;font-size:13px;background:#eef1f5;border:1px solid var(--line);border-radius:4px}
code{padding:0 4px}pre{padding:8px 10px;overflow:auto}table{border-collapse:collapse;width:100%;margin:6px 0 10px;background:var(--panel)}
th,td{border:1px solid var(--line);padding:4px 7px;text-align:left;vertical-align:top;font-size:13.5px}th{background:#eef1f5}
@media print{.ban{border-left-color:#000}}"""


def readme_page(ext, mid):
    m = _labs_module(ext)
    if m is None or mid not in m.MODULES:
        return None
    p = m.summary(mid)['readme']
    if not os.path.isfile(p):
        return None
    body = md_to_html(open(p, encoding='utf-8').read())
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>GlitchSAT Labs: %s</title><style>%s</style></head><body><main><div class="ban"><b>GlitchSAT Labs, EXPERIMENTAL.</b> '
            'Experiments in progress: try them, don\'t rely on them.</div>%s</main></body></html>') % (
        html.escape(m.MODULES[mid]['title']), PAGE_CSS, body)


def handle(h, path, q, ext):
    """Answer the Labs requests; True when answered."""
    if path == '/api/labs':
        try:
            h._send(200, json.dumps(modules(ext)))
        except Exception as e:               # noqa: BLE001 - the tab shows the reason
            h._send(500, json.dumps(dict(error=str(e)[:200])))
        return True
    if path.startswith('/labs/readme/'):
        page = readme_page(ext, path.rsplit('/', 1)[1])
        if page is None:
            h._send(404, '{"error":"no such Labs module"}')
        else:
            h._send(200, page, 'text/html')
        return True
    return False
