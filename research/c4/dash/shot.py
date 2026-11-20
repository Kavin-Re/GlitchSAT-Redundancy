import sys,json
from playwright.sync_api import sync_playwright
url=sys.argv[1]; out=sys.argv[2]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    for w in (390,1366):
        pg=b.new_page(viewport={'width':w,'height':900}); errs=[]
        pg.on('console',lambda m:errs.append((m.type,m.text)) if m.type=='error' else None)
        pg.on('pageerror',lambda e:errs.append(('pageerror',str(e))))
        pg.on('requestfailed',lambda r:errs.append(('reqfail',r.url)))
        pg.goto(url)
        res={}
        for tab in ('V0 naive FSM','V1 duplicated + sparse FSM','V2 triplicated + split word','Scope'):
            pg.get_by_role('button',name=tab,exact=True).click()
            res[tab]=pg.evaluate('[document.documentElement.scrollWidth,innerWidth]')
        pg.screenshot(path=f'{out}_{w}.png',full_page=True)
        small=pg.evaluate("""[...document.querySelectorAll('body *')].filter(e=>e.childNodes.length&&[...e.childNodes].some(n=>n.nodeType==3&&n.textContent.trim())&&e.offsetParent!==null).map(e=>parseFloat(getComputedStyle(e).fontSize)).reduce((a,x)=>Math.min(a,x),99)""")
        print(w,res,'minfont',small,errs)
    b.close()
