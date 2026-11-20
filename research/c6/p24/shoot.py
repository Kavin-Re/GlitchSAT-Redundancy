#!/usr/bin/env python3
"""Screenshots + console check of docs/wow/wall.html via headless Chrome.
Usage: python3 research/c6/p24/shoot.py [ROOT]   (writes research/c6/p24/shots/*.png and shots/shoot_log.txt)"""
import os, sys, json
from playwright.sync_api import sync_playwright
ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
URL = "file://" + os.path.join(ROOT, "docs/wow/wall.html")
OUT = os.path.join(ROOT, "research/c6/p24/shots"); os.makedirs(OUT, exist_ok=True)
log = []
def say(s):
    print(s); log.append(s)
METRICS = """() => {
 const de=document.documentElement; const small=[]; const tiny=[];
 for (const e of document.querySelectorAll('body *')) {
   if (!e.offsetParent && getComputedStyle(e).position!=='fixed') continue;
   const cs=getComputedStyle(e);
   const hasText=[...e.childNodes].some(n=>n.nodeType===3 && n.textContent.trim()) || (e.classList.contains('sh'));
   if (hasText && parseFloat(cs.fontSize)<12) small.push(e.tagName+'.'+e.className+':'+cs.fontSize);
   if (e.tagName==='BUTTON' && !e.classList.contains('tile')) { const r=e.getBoundingClientRect(); if (r.width && (r.height<44||r.width<44)) tiny.push((e.id||e.textContent.trim().slice(0,20))+':'+Math.round(r.width)+'x'+Math.round(r.height)); }
 }
 const t=[...document.querySelectorAll('.wall .tile')].filter(b=>!b.hidden); const r=t[0].getBoundingClientRect();
 const cav=document.getElementById('caveats').getBoundingClientRect();
 return {scrollW:de.scrollWidth, clientW:de.clientWidth, docH:de.scrollHeight, small:[...new Set(small)], tinyButtons:tiny, tilesVisible:t.length, tilePx:Math.round(r.width*10)/10,
   tileFont:getComputedStyle(t[0].firstChild).fontSize, wallBottom:Math.round(document.getElementById('wall').getBoundingClientRect().bottom), caveatsBottom:Math.round(cav.bottom), caveatsVisible:getComputedStyle(document.getElementById('caveats')).visibility, headline:document.getElementById('headline').textContent,
   sub:document.getElementById('subline').textContent.trim().slice(0,90)};
}"""
with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--headless=new", "--no-sandbox"])
    def page(w, h, scheme="light", reduced=False):
        ctx = br.new_context(viewport={"width": w, "height": h}, color_scheme=scheme, reduced_motion="reduce" if reduced else "no-preference")
        pg = ctx.new_page(); errs = []
        pg.on("console", lambda m: errs.append(m.type + ": " + m.text) if m.type in ("error", "warning") else None)
        pg.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
        pg.on("requestfailed", lambda r: errs.append("requestfailed: " + r.url))
        return ctx, pg, errs
    def shot(pg, name, full=False):
        pg.screenshot(path=os.path.join(OUT, name), full_page=full)
    allerrs = []
    for (w, h) in ((1366, 768), (390, 844)):
        ctx, pg, errs = page(w, h)
        pg.goto(URL); pg.wait_for_timeout(300)
        m = pg.evaluate(METRICS); say("%dx%d default(152): %s" % (w, h, json.dumps(m)))
        assert m["scrollW"] <= m["clientW"], "horizontal scroll at %d" % w
        shot(pg, "wall_%d_152_top.png" % w); shot(pg, "wall_%d_152_full.png" % w, True)
        pg.click("#vS"); pg.wait_for_timeout(200)
        m = pg.evaluate(METRICS); say("%dx%d every(264): %s" % (w, h, json.dumps(m)))
        assert m["scrollW"] <= m["clientW"]
        shot(pg, "wall_%d_264_top.png" % w); shot(pg, "wall_%d_264_full.png" % w, True)
        # stage reveal, stepped with the space key
        pg.click("#vN"); pg.evaluate("document.activeElement.blur(); window.scrollTo(0,0)")
        for i, nm in enumerate(("blueprint", "builders", "verdicts", "cause")):
            pg.keyboard.press("Space"); pg.wait_for_timeout(3600)
            st = pg.evaluate("document.body.getAttribute('data-stage')")
            assert st == str(i), "space key: expected stage %d got %s" % (i, st)
            m = pg.evaluate(METRICS)
            say("%dx%d stage %d %s: caveats visible=%s caveatsBottom=%d wallBottom=%d viewportH=%d smallText=%s" % (w, h, i, nm, m["caveatsVisible"], m["caveatsBottom"], m["wallBottom"], h, m["small"]))
            if w < 700: pg.evaluate("document.getElementById('wall').scrollIntoView()")
            shot(pg, "wall_%d_stage%d_%s.png" % (w, i + 1, nm))
            if w < 700: pg.evaluate("window.scrollTo(0,0)")
        pg.keyboard.press("Escape")
        assert pg.evaluate("document.body.getAttribute('data-stage')") is None
        # tooltip: keyboard on desktop, tap on phone
        if w >= 700:
            pg.focus(".wall .tile[tabindex='0']"); pg.keyboard.press("ArrowRight"); pg.keyboard.press("ArrowDown"); pg.keyboard.press("Enter"); pg.wait_for_timeout(150)
        else:
            pg.evaluate("document.getElementById('wall').scrollIntoView()"); pg.locator(".wall .tile:not([hidden])").nth(8).click(); pg.wait_for_timeout(150)
        tip = pg.evaluate("document.getElementById('tip').hidden ? null : document.getElementById('tip').innerText")
        assert tip and "sha256" in tip and "line" in tip, "tooltip missing"
        say("%dx%d tooltip (netlist view): %s" % (w, h, " | ".join(tip.split("\n"))[:400]))
        shot(pg, "wall_%d_tooltip_152.png" % w)
        pg.keyboard.press("Escape")
        assert pg.evaluate("document.getElementById('tip').hidden") is True
        pg.click("#vS"); pg.locator(".wall .tile:not([hidden])").nth(40).click(); pg.wait_for_timeout(150)
        tip = pg.evaluate("document.getElementById('tip').innerText")
        assert "gates" in tip and "Merge" in tip
        say("%dx%d tooltip (setting view): %s" % (w, h, " | ".join(tip.split("\n"))[:400]))
        shot(pg, "wall_%d_tooltip_264.png" % w)
        pg.keyboard.press("Escape")
        pg.locator("#v2e-sec").scroll_into_view_if_needed(); pg.wait_for_timeout(100)
        pg.locator(".vtile").nth(8).click(); pg.wait_for_timeout(100)
        shot(pg, "wall_%d_v2e.png" % w)
        say("%dx%d v2e tooltip: %s" % (w, h, " | ".join(pg.evaluate("document.getElementById('tip').innerText").split("\n"))[:300]))
        say("%dx%d console errors/warnings: %d %s" % (w, h, len(errs), errs)); allerrs += errs; ctx.close()
    # dark, and reduced motion (static: the step must be complete at once)
    for (w, h) in ((1366, 768), (390, 844)):
        ctx, pg, errs = page(w, h, "dark"); pg.goto(URL); pg.wait_for_timeout(300)
        shot(pg, "wall_%d_dark_152.png" % w); pg.goto(URL + "?stage=4"); pg.wait_for_timeout(1200)
        if w < 700: pg.evaluate("document.getElementById('wall').scrollIntoView()")
        shot(pg, "wall_%d_dark_cause.png" % w)
        say("%dx%d dark console errors: %d %s" % (w, h, len(errs), errs)); allerrs += errs; ctx.close()
    ctx, pg, errs = page(1366, 768, "light", True); pg.goto(URL + "?stage=2"); pg.keyboard.press("Space"); pg.wait_for_timeout(60)
    op = pg.evaluate("(()=>{const t=[...document.querySelectorAll('.wall .tile:not([hidden]) .sh')];const c=getComputedStyle(t[t.length-1]);return [document.body.dataset.stage,c.opacity,c.transitionDuration,c.transform]})()")
    say("reduced motion, 60 ms after Space to 'verdicts', last tile: stage=%s opacity=%s transition=%s transform=%s" % tuple(op))
    assert op[0] == "2" and op[1] == "1" and op[3] in ("none", "matrix(1, 0, 0, 1, 0, 0)")
    shot(pg, "wall_1366_reduced_motion_verdicts.png"); allerrs += errs; ctx.close()
    ctx, pg, errs = page(1920, 1080); pg.goto(URL + "?stage=3"); pg.wait_for_timeout(3600)
    m = pg.evaluate(METRICS); say("1920x1080 stage 3: tile %spx caveatsBottom=%d" % (m["tilePx"], m["caveatsBottom"])); shot(pg, "wall_1920_stage3_verdicts.png"); allerrs += errs; ctx.close()
    br.close()
say("TOTAL console errors/warnings/page errors/failed requests: %d" % len(allerrs))
open(os.path.join(OUT, "shoot_log.txt"), "w").write("\n".join(log) + "\n")
sys.exit(1 if allerrs else 0)
