from playwright.sync_api import sync_playwright
import os
P='file://<repo>/docs/explainers/'
out='research/c3/wp5/shots/'
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    for w,h in((390,844),(1366,800)):
        pg=b.new_page(viewport={'width':w,'height':h}); errs=[]
        pg.on('pageerror',lambda e:errs.append(str(e))); pg.on('console',lambda m:errs.append(m.text) if m.type=='error' else None)
        pg.goto(P+'explainer.html'); pg.wait_for_timeout(500)
        pg.screenshot(path=out+f'ex_{w}_0top.png')
        print(w,'overflowX',pg.evaluate('document.documentElement.scrollWidth'),'hero before:',pg.inner_text('#herostate'))
        pg.click('#herobtn'); pg.wait_for_timeout(500)
        print('hero after:',pg.inner_text('#herostate'),pg.get_attribute('#herobtn','aria-pressed'))
        pg.screenshot(path=out+f'ex_{w}_1hero.png')
        # wiring
        pg.click('[data-pick=tool2]'); 
        for i in range(3):
            pg.click('[data-btn=pick]'); pg.wait_for_timeout(200)
        print('pick state:',pg.inner_text('#s2')[:700].replace('\n',' | '))
        pg.click('[data-all=pick]'); pg.wait_for_timeout(200)
        pg.locator('#pickfig').scroll_into_view_if_needed(); pg.screenshot(path=out+f'ex_{w}_2wiring.png')
        pg.click('[data-reset=pick]'); pg.click('[data-pick=tool1]'); pg.click('[data-btn=pick]'); pg.click('[data-all=pick]')
        pg.click('#cntd > summary'); print('cntd summary:',pg.inner_text('#cntd > summary'))
        pg.click('[data-count="2"]'); pg.wait_for_timeout(200)
        print('count2:',pg.inner_text('#cntout')[:200])
        pg.locator('#cntfig').scroll_into_view_if_needed(); pg.screenshot(path=out+f'ex_{w}_3count.png')
        pg.click('[data-count="1"]'); print('count1:',pg.inner_text('#cntout')[:200])
        pg.screenshot(path=out+f'ex_{w}_4full.png',full_page=True)
        print('errs',errs)
        # game
        g=b.new_page(viewport={'width':w,'height':h}); g.on('pageerror',lambda e:print('GERR',e))
        g.goto(P+'game.html'); g.wait_for_timeout(500)
        g.screenshot(path=out+f'game_{w}_0.png'); print('game overflow',g.evaluate('document.documentElement.scrollWidth'))
        print(g.evaluate('''()=>[...document.querySelectorAll('button,[role=button],[tabindex],circle,.node,.wire')].slice(0,40).map(e=>e.tagName+'|'+(e.id||'')+'|'+(e.className.baseVal??e.className)+'|'+(e.textContent||'').trim().slice(0,30))'''))
    b.close()
