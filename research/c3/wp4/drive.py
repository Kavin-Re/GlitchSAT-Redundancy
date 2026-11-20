from playwright.sync_api import sync_playwright
import json
O='/home/user/project/research/c3/wp4/shots/'
B='file:///home/user/project/docs/wow/'
log=[]
def L(*a): log.append(' '.join(map(str,a))); print(*a)
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    for w,h,tag in [(390,844,'m'),(1366,800,'d')]:
        pg=b.new_page(viewport={'width':w,'height':h}); errs=[]
        pg.on('console',lambda m:errs.append(m.text) if m.type=='error' else None)
        pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.goto(B+'explainer.html'); pg.wait_for_timeout(1500)
        pg.screenshot(path=O+f'ex_{tag}_top.png')
        L(tag,'scrollW',pg.evaluate('document.documentElement.scrollWidth'),'vs',w)
        pg.screenshot(path=O+f'ex_{tag}_full.png',full_page=True)
        hero=pg.locator('[data-btn=hero]'); L('hero btn text',hero.inner_text(), hero.bounding_box())
        hero.click(); pg.wait_for_timeout(1500); pg.screenshot(path=O+f'ex_{tag}_hero1.png')
        L('hero btn after',hero.inner_text())
        fig=pg.locator('[data-fig=hero]'); L('hero fig text:',fig.inner_text().replace('\n',' | '))
        hero.click(); pg.wait_for_timeout(800); L('hero btn after2',hero.inner_text(),'| fig:',fig.inner_text().replace('\n',' | '))
        # wiring
        pg.locator('[data-pick=tool2]').scroll_into_view_if_needed(); pg.locator('[data-pick=tool2]').click(); pg.wait_for_timeout(500)
        L('pickhint',pg.locator('#pickhint').inner_text())
        pb=pg.locator('[data-btn=pick]')
        for i in range(3):
            pb.click(); pg.wait_for_timeout(500); L('pick click',i,pb.inner_text(),'|',pg.locator('#pickfig').inner_text().replace('\n',' | ')[:300])
        pg.screenshot(path=O+f'ex_{tag}_wiringB.png')
        pg.locator('[data-all=pick]').click(); pg.wait_for_timeout(800); L('showfewest:',pg.locator('#pickfig').inner_text().replace('\n',' | ')[:300]); pg.screenshot(path=O+f'ex_{tag}_wiringB_all.png')
        pg.locator('[data-pick=tool1]').click(); pg.locator('[data-all=pick]').click(); pg.wait_for_timeout(800); L('A fewest:',pg.locator('#pickfig').inner_text().replace('\n',' | ')[:300])
        pg.locator('[data-reset=pick]').click()
        pg.locator('#cntd summary').click(); pg.wait_for_timeout(500)
        L('count out 1:',pg.locator('#cntout').inner_text()); pg.screenshot(path=O+f'ex_{tag}_count1.png')
        pg.locator('[data-count="2"]').click(); pg.wait_for_timeout(800); L('count out 2:',pg.locator('#cntout').inner_text()); pg.screenshot(path=O+f'ex_{tag}_count2.png')
        pg.locator('#evd summary').click(); pg.wait_for_timeout(300)
        pg.locator('#ask').scroll_into_view_if_needed(); pg.locator('#ask').screenshot(path=O+f'ex_{tag}_ask.png')
        L('errors',errs)
        # game
        pg2=b.new_page(viewport={'width':w,'height':h}); pg2.on('pageerror',lambda e:L('GAMEERR',e))
        pg2.goto(B+'game.html'); pg2.wait_for_timeout(1000); pg2.screenshot(path=O+f'g_{tag}_top.png')
        L('game scrollW',pg2.evaluate('document.documentElement.scrollWidth'))
        tabs=pg2.locator('#tabs button'); n=tabs.count(); L('tabs',n,[tabs.nth(i).inner_text() for i in range(n)])
        for i in range(n):
            tabs.nth(i).click(); pg2.wait_for_timeout(300)
            L('--tab',i,'par',pg2.locator('#par').inner_text(),'hint',pg2.locator('#hint').inner_text()[:150])
            nodes=pg2.locator('#fig .node'); k=nodes.count()
            nodes.nth(0).click(); pg2.wait_for_timeout(200)
            L(' 1 tap used',pg2.locator('#used').inner_text(),'status:',pg2.locator('#status').inner_text())
            if i==0: pg2.screenshot(path=O+f'g_{tag}_tap1.png')
            for j in range(1,k):
                nodes.nth(j).click(); pg2.wait_for_timeout(150)
                L(f' tap{j+1} used',pg2.locator('#used').inner_text(),'status:',pg2.locator('#status').inner_text())
            pg2.screenshot(path=O+f'g_{tag}_tab{i}_all.png')
            pg2.locator('#reset').click(); pg2.locator('#best').click(); pg2.wait_for_timeout(200)
            L(' best used',pg2.locator('#used').inner_text(),pg2.locator('#status').inner_text())
            pg2.locator('#reset').click()
        pg2.locator('#cards').scroll_into_view_if_needed(); pg2.screenshot(path=O+f'g_{tag}_cards.png')
        pg2.screenshot(path=O+f'g_{tag}_full.png',full_page=True)
        L('cards',pg2.locator('#cards').inner_text().replace('\n',' | '))
    b.close()
open('/home/user/project/research/c3/wp4/drive_log.txt','w').write('\n'.join(log))
