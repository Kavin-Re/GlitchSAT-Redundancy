from playwright.sync_api import sync_playwright
P='file://<repo>/docs/explainers/game.html'
out='research/c3/wp5/shots/'
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    for w,h in((390,844),(1366,800)):
        g=b.new_page(viewport={'width':w,'height':h}); g.goto(P); g.wait_for_timeout(400)
        def st(): return g.evaluate("document.body.innerText.split('3. Fewest')[0].slice(-0,900)").replace('\n',' | ')
        nodes=g.locator('g.node')
        print(w,'nodes',nodes.count())
        g.click('text=No backup'); 
        print('nobackup',st()[-300:])
        # wrong tap then right
        g.click('text=2 guards, 1 wire'); n=g.locator('g.node'); print('nodes2',n.count())
        for i in range(n.count()):
            n.nth(i).click(force=True); g.wait_for_timeout(150); print(i,st()[-260:])
        g.screenshot(path=out+f'game_{w}_1play.png')
        g.click('#reset')
        g.click('text=Rebuilt: Wiring B'); n=g.locator('g.node'); print('nodesB',n.count())
        for i in range(n.count()):
            n.nth(i).click(force=True); g.wait_for_timeout(150)
        print('B after all taps',st()[-300:])
        g.screenshot(path=out+f'game_{w}_2B.png')
        g.click('#best'); g.wait_for_timeout(200); print('best',st()[-300:])
        g.screenshot(path=out+f'game_{w}_3best.png',full_page=True)
    b.close()
