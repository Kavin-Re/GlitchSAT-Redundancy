from playwright.sync_api import sync_playwright
import json
R='docs/explainers/'
out={}
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox','--headless=new'])
    for w,h,tag in [(390,844,'m'),(1366,768,'d')]:
        ctx=b.new_context(viewport={'width':w,'height':h},permissions=['clipboard-read','clipboard-write'])
        pg=ctx.new_page(); errs=[]
        pg.on('console',lambda m:errs.append(m.text) if m.type=='error' else None)
        pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.goto('file://'+R+'explainer.html')
        pg.screenshot(path=f'shots/ex_{tag}_top.png')
        pg.screenshot(path=f'shots/ex_{tag}_full.png',full_page=True)
        o={}
        o['hscroll']=pg.evaluate('document.documentElement.scrollWidth>innerWidth')
        o['hero_before']=pg.inner_text('#herostate')
        pg.click('#herobtn'); pg.wait_for_timeout(700)
        o['hero_after']=pg.inner_text('#herostate'); o['oh']=pg.inner_text('#hero-oh'); o['herobtn']=pg.inner_text('#herobtn')
        pg.screenshot(path=f'shots/ex_{tag}_hero.png')
        pg.click('#herobtn'); pg.wait_for_timeout(300); o['hero_again']=pg.inner_text('#herostate')
        pg.click('[data-pick=tool2]'); o['pick2']=pg.inner_text('#pickhint')
        for i in range(3): pg.click('[data-btn=pick]'); pg.wait_for_timeout(200)
        pg.click('[data-all=pick]'); pg.wait_for_timeout(300)
        pg.locator('#pickfig').scroll_into_view_if_needed()
        pg.screenshot(path=f'shots/ex_{tag}_wiring.png')
        o['pickfig_text']=pg.inner_text('#pickfig')[:300]
        pg.click('[data-reset=pick]')
        o['cnt1']=pg.inner_text('#cntout')
        pg.click('[data-count="2"]'); pg.wait_for_timeout(300); o['cnt2']=pg.inner_text('#cntout')
        pg.locator('#cntd').scroll_into_view_if_needed(); pg.screenshot(path=f'shots/ex_{tag}_count.png')
        for c in ['fq10','fq25']:
            pg.click(f'[data-copy={c}]'); pg.wait_for_timeout(300)
            o['copy_'+c]=pg.inner_text('#copymsg')
            try: o['clip_'+c]=pg.evaluate('navigator.clipboard.readText()')
            except Exception as e: o['clip_'+c]='ERR '+str(e)[:80]
        pg.locator('#friend').scroll_into_view_if_needed(); pg.screenshot(path=f'shots/ex_{tag}_friend.png')
        pg.locator('#ask').scroll_into_view_if_needed(); pg.screenshot(path=f'shots/ex_{tag}_ask.png')
        o['errs']=errs
        # overflow check
        o['wide']=pg.evaluate('[...document.querySelectorAll("body *")].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,5).map(e=>e.tagName+"."+e.className)')
        o['smallfont']=pg.evaluate('[...document.querySelectorAll("p,span,small,li,button,summary")].filter(e=>e.innerText&&e.innerText.trim()&&parseFloat(getComputedStyle(e).fontSize)<13).length')
        out['ex_'+tag]=o
        # game
        pg=ctx.new_page(); ge=[]
        pg.on('pageerror',lambda e:ge.append(str(e)))
        pg.goto('file://'+R+'game.html'); pg.wait_for_timeout(300)
        pg.screenshot(path=f'shots/g_{tag}_top.png')
        g={}
        g['hscroll']=pg.evaluate('document.documentElement.scrollWidth>innerWidth')
        g['tabs']=pg.evaluate('[...document.querySelectorAll("#tabs button, #tabs *")].map(e=>e.innerText).filter(x=>x)')
        g['status0']=pg.inner_text('#status'); g['hint']=pg.inner_text('#hint'); g['par']=pg.inner_text('#par')
        nodes=pg.locator('#fig g').filter(has=pg.locator('.fring'))
        n=nodes.count(); g['nodes']=n
        # wrong tap on first design
        for i in range(n):
            nodes.nth(i).click(force=True); pg.wait_for_timeout(150)
            g[f'after{i}']=(pg.inner_text('#used'),pg.inner_text('#status')[:160])
            if 'opened' in pg.inner_text('#status'): break
        pg.screenshot(path=f'shots/g_{tag}_open.png')
        # tap after lock opens
        nodes.nth(0).click(force=True); pg.wait_for_timeout(200)
        g['tap_after_open']=(pg.inner_text('#used'),pg.inner_text('#status')[:200])
        pg.click('#reset'); pg.wait_for_timeout(200); g['reset']=(pg.inner_text('#used'),pg.inner_text('#status'))
        pg.click('#best'); pg.wait_for_timeout(600); g['best']=(pg.inner_text('#used'),pg.inner_text('#status')[:200])
        pg.screenshot(path=f'shots/g_{tag}_best.png')
        # other tabs
        tabs=pg.locator('#tabs button'); g['ntabs']=tabs.count()
        for t in range(tabs.count()):
            tabs.nth(t).click(); pg.wait_for_timeout(200)
            g[f'tab{t}']=(tabs.nth(t).inner_text().replace('\n',' | '),pg.inner_text('#par'),pg.inner_text('#status')[:120])
            if t==tabs.count()-1: pg.screenshot(path=f'shots/g_{tag}_lasttab.png')
        g['errs']=ge
        g['smallfont']=pg.evaluate('[...document.querySelectorAll("p,span,small,li,button")].filter(e=>e.innerText&&e.innerText.trim()&&parseFloat(getComputedStyle(e).fontSize)<13).length')
        out['g_'+tag]=g
        ctx.close()
    b.close()
json.dump(out,open('run.json','w'),indent=1,ensure_ascii=False)
print(json.dumps(out,indent=1,ensure_ascii=False))
