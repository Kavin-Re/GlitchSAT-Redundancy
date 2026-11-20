from playwright.sync_api import sync_playwright
R='/home/user/project/docs/wow/'
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox','--headless=new'])
    for w,h,tag in [(390,844,'m'),(1366,768,'d')]:
        pg=b.new_context(viewport={'width':w,'height':h}).new_page()
        pg.goto('file://'+R+'game.html'); pg.wait_for_timeout(300)
        pg.locator('#tabs button').nth(3).click(); pg.wait_for_timeout(200)
        nodes=pg.locator('#fig g').filter(has=pg.locator('.fring'))
        for i in [0,1,2]:
            nodes.nth(i).click(force=True); pg.wait_for_timeout(200)
        print(tag,pg.inner_text('#used'),pg.inner_text('#status'))
        pg.screenshot(path=f'shots/g3_{tag}_open.png')
        nodes.nth(1).click(force=True); pg.wait_for_timeout(200); print('after open tap',pg.inner_text('#used'),pg.inner_text('#status')[:100])
    b.close()
