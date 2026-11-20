from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    br=p.chromium.launch(executable_path="/usr/bin/google-chrome",args=["--no-sandbox"])
    pg=br.new_page(viewport={"width":195,"height":420},reduced_motion="reduce")
    pg.goto("file:///home/user/project/docs/wow/explainer.html")
    print(pg.evaluate("[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>196&&!e.closest('svg')).map(e=>e.tagName+'.'+e.className+' '+Math.round(e.getBoundingClientRect().right)).slice(0,12)"))
