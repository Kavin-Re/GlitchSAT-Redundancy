#!/usr/bin/env python3
"""Screenshots of docs/wow/dial.html with headless Chrome. No tracing.
Usage: python3 research/c6/p40/shoot.py   (writes research/c6/p40/shots/*.png and prints console errors / scroll widths)"""
import os, sys
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
URL = "file://" + os.path.join(ROOT, "docs/wow/dial.html"); OUT = os.path.join(HERE, "shots"); os.makedirs(OUT, exist_ok=True)
SHOTS = [  # name, width, height, scheme, hash, full_page
    ("390_light_default", 390, 844, "light", "", True),
    ("390_dark_flag", 390, 844, "dark", "#v2.flag.stored.no.known", True),
    ("390_light_notmeasured", 390, 844, "light", "#v2.m0x4E.merge.no.known", True),
    ("390_light_predict", 390, 844, "light", "#v2.word.plain.no.known;predict", True),
    ("1366_light_default", 1366, 768, "light", "", False),
    ("1366_dark_plain", 1366, 768, "dark", "#v2.word.plain.no.known", False),
    ("1366_light_mask", 1366, 768, "light", "#v2.m0x4E.stored.no.known", True),
    ("1366_light_big", 1366, 768, "light", "#v2.word.v2e.no.known;big", False),
    ("1366_dark_big_predict", 1366, 768, "dark", "#v2.word.stored.no.any;predict;big", False),
    ("1920_light_big", 1920, 1080, "light", "#v2.word.stored.no.known;big", False),
]
bad = 0
with sync_playwright() as pw:
    br = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True, args=["--no-sandbox"])
    for name, w, h, scheme, hsh, full in SHOTS:
        ctx = br.new_context(viewport={"width": w, "height": h}, color_scheme=scheme, reduced_motion="reduce")
        pg = ctx.new_page(); errs = []
        pg.on("console", lambda m: errs.append(m.text) if m.type in ("error", "warning") else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(URL + hsh); pg.wait_for_timeout(250)
        sw = pg.evaluate("document.documentElement.scrollWidth"); sh = pg.evaluate("document.documentElement.scrollHeight")
        small = pg.evaluate("""()=>{let m=99,b=[];for(const e of document.querySelectorAll('body *')){const s=getComputedStyle(e);
          if(e.checkVisibility&&!e.checkVisibility())continue; if([...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())){m=Math.min(m,parseFloat(s.fontSize))}
          if((e.tagName==='BUTTON'||e.classList.contains('box')||e.tagName==='SUMMARY')){const r=e.getBoundingClientRect();if(r.width&&(r.height<44||r.width<44))b.push(e.textContent.slice(0,20)+' '+Math.round(r.width)+'x'+Math.round(r.height))}}
          return {minFont:m,smallTargets:b}}""")
        pg.screenshot(path=os.path.join(OUT, name + ".png"), full_page=full)
        ok = sw <= w and not errs and small["minFont"] >= 12 and not small["smallTargets"]
        bad += 0 if ok else 1
        print(("PASS " if ok else "FAIL ") + "%s: scrollWidth %d (viewport %d), page height %d, console %s, min font %s px, targets<44 %s" % (
            name, sw, w, sh, errs or "clean", small["minFont"], small["smallTargets"] or "none"))
        ctx.close()
    br.close()
sys.exit(1 if bad else 0)
