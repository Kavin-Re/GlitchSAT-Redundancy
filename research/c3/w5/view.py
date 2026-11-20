from playwright.sync_api import sync_playwright
B="file://<repo>/docs/wow/"
with sync_playwright() as p:
    br=p.chromium.launch(executable_path="/usr/bin/google-chrome",args=["--no-sandbox"],headless=True)
    for nm,w,h in [("390",390,844),("320",320,640)]:
        ctx=br.new_context(viewport={"width":w,"height":h},device_scale_factor=1,has_touch=True,is_mobile=True)
        pg=ctx.new_page();errs=[];pg.on("pageerror",lambda e:errs.append(str(e)))
        pg.goto(B+"explainer.html");pg.wait_for_timeout(300)
        pg.screenshot(path=f"shots/hero_before_{nm}.png")
        pg.tap("#herobtn");pg.wait_for_timeout(300)
        pg.screenshot(path=f"shots/hero_after_{nm}.png")
        pg.goto(B+"game.html");pg.wait_for_timeout(300)
        pg.tap("#tabs button:nth-child(3)");pg.wait_for_timeout(300)
        pg.screenshot(path=f"shots/game_tab_{nm}.png")
        pg.tap("svg#fig .node >> nth=3");pg.wait_for_timeout(300)
        pg.screenshot(path=f"shots/game_flip_{nm}.png"); print(nm,errs)
    br.close()
