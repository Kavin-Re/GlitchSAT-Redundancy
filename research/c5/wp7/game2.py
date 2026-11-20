from playwright.sync_api import sync_playwright
R='docs/wow/'
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox','--headless=new'])
    for w,h,tag in [(390,844,'m'),(1366,768,'d')]:
        pg=b.new_context(viewport={'width':w,'height':h}).new_page()
        pg.goto('file://'+R+'game.html'); pg.wait_for_timeout(300)
        pg.locator('#tabs button').nth(3).click(); pg.wait_for_timeout(200)
        nodes=pg.locator('#fig g').filter(has=pg.locator('.fring'))
        print(tag,'nodes',nodes.count(), pg.inner_text('#hint'))
        for i in [0,0,1,2]:
            nodes.nth(i).click(force=True); pg.wait_for_timeout(200)
            print(i,pg.inner_text('#used'),pg.inner_text('#status')[:250])
            if i==0 : pg.screenshot(path=f'shots/g3_{tag}_step{i}.png')
        pg.screenshot(path=f'shots/g3_{tag}_end.png',full_page=(tag=='m'))
        nodes.nth(1).click(force=True); pg.wait_for_timeout(200); print('after',pg.inner_text('#used'),pg.inner_text('#status')[:100])
        # hold tab: 4 flips? 
        pg.locator('#tabs button').nth(2).click(); pg.wait_for_timeout(200)
        nodes=pg.locator('#fig g').filter(has=pg.locator('.fring')); print('tab2',nodes.count(),pg.inner_text('#hint'))
        nodes.nth(0).click(force=True); pg.wait_for_timeout(200); print(pg.inner_text('#status')[:200])
        pg.screenshot(path=f'shots/g2_{tag}.png')
    b.close()
