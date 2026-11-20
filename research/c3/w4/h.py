from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    br=p.chromium.launch(executable_path="/usr/bin/google-chrome",args=["--no-sandbox"])
    pg=br.new_page(viewport={"width":390,"height":844},reduced_motion="reduce")
    pg.goto("file://<repo>/docs/wow/explainer.html")
    print(pg.evaluate("document.documentElement.scrollHeight"))
    print(pg.evaluate("[...document.querySelectorAll('section,.ask,.fig,.res,details,.oh,.scope,.cnt')].map(e=>e.tagName+'.'+(e.id||e.className)+' '+Math.round(e.getBoundingClientRect().height))"))
