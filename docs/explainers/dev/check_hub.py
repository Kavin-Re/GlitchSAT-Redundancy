#!/usr/bin/env python3
"""Checks docs/explainers/index.html (the hub page). Writes nothing unless --shots DIR is given.
Part A (always): every relative link points to an existing file, no external resource, scope line present, text-only checks.
Part B (--browser, needs playwright + /usr/bin/google-chrome): at 390 and 1366 px: no console errors, no horizontal scroll,
  smallest visible text >= 12 px, links/buttons >= 44 px high; screenshots to --shots DIR.
Usage: python3 docs/explainers/dev/check_hub.py [--browser] [--shots DIR]     exit code 0 = all pass"""
import os, re, sys
from urllib.parse import urlsplit
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the pages folder docs/explainers (this script is in its dev/ subfolder)
page = os.path.join(HERE, "index.html")
html = open(page, encoding="utf-8").read()
fails = 0
def rep(ok, msg):
    global fails
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok: fails += 1
links = re.findall(r'href\s*=\s*"([^"]+)"', html)
rep(len(links) >= 9, "hub has %d links" % len(links))
for l in links:
    u = urlsplit(l)
    if u.scheme or l.startswith("//"):
        rep(False, "external link " + l); continue
    rep(os.path.isfile(os.path.normpath(os.path.join(HERE, u.path))), "linked file exists: " + l)
rep(not re.search(r'(src|href)\s*=\s*"(https?:)?//', html) and "url(http" not in html and "@import" not in html, "no external resource")
for w in ("dial.html", "theatre.html", "wall.html", "explainer.html", "game.html", "dashboard/index.html", "CODING_VIEW.md", "theatre.html?kiosk=1", "wall.html?kiosk=1"):
    rep(w in html, "hub links " + w)
rep("nothing physical" in html and "makes no claim to be new" in html, "scope line present")
if "--browser" in sys.argv:
    from playwright.sync_api import sync_playwright
    shots = sys.argv[sys.argv.index("--shots") + 1] if "--shots" in sys.argv else None
    if shots: os.makedirs(shots, exist_ok=True)
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox", "--headless=new"])
        for w in (390, 1366):
            for scheme in ("light", "dark"):
                pg = br.new_page(viewport={"width": w, "height": 800}, color_scheme=scheme); errs = []
                pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.goto("file://" + page)
                sw = pg.evaluate("[document.documentElement.scrollWidth, innerWidth]")
                mf = pg.evaluate("""[...document.querySelectorAll('body *')].filter(e=>[...e.childNodes].some(n=>n.nodeType==3&&n.textContent.trim())&&e.offsetParent!==null).map(e=>parseFloat(getComputedStyle(e).fontSize)).reduce((a,x)=>Math.min(a,x),99)""")
                mh = pg.evaluate("[...document.querySelectorAll('a')].map(a=>a.getBoundingClientRect().height).reduce((a,x)=>Math.min(a,x),999)")
                rep(not errs, "%d px %s: no console errors %s" % (w, scheme, errs))
                rep(sw[0] <= sw[1], "%d px %s: no horizontal scroll %s" % (w, scheme, sw))
                rep(mf >= 12, "%d px %s: smallest text %.1f px >= 12" % (w, scheme, mf))
                rep(mh >= 44, "%d px %s: smallest link height %.1f px >= 44" % (w, scheme, mh))
                if shots and scheme == "light": pg.screenshot(path=os.path.join(shots, "hub_%d.png" % w), full_page=True)
                pg.close()
        br.close()
print("OVERALL:", "FAIL" if fails else "PASS"); sys.exit(1 if fails else 0)
