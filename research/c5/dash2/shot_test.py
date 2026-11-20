import sys
from playwright.sync_api import sync_playwright
url=sys.argv[1]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    for w in (390,1366):
        pg=b.new_page(viewport={'width':w,'height':900}); errs=[]
        pg.on('console',lambda m:errs.append(m.text) if m.type=='error' else None)
        pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.goto(url); res={}
        for tab in ('V0 naive FSM','V1 duplicated + sparse FSM','V2 triplicated + split word','Scope'):
            pg.get_by_role('button',name=tab,exact=True).click()
            res[tab]=pg.evaluate('[document.documentElement.scrollWidth,innerWidth]')
        # focus test
        sc=pg.get_by_role('button',name='Scope',exact=True); sc.focus(); pg.keyboard.press('Enter')
        foc=pg.evaluate('document.activeElement.textContent')
        pg.keyboard.press('Shift+Tab'); foc2=pg.evaluate('document.activeElement.textContent'); pg.keyboard.press('Enter'); foc3=pg.evaluate('document.activeElement.textContent')
        pg.get_by_role('button',name='Scope',exact=True).click()
        small=pg.evaluate("""[...document.querySelectorAll('body *')].filter(e=>[...e.childNodes].some(n=>n.nodeType==3&&n.textContent.trim())&&e.offsetParent!==null).map(e=>parseFloat(getComputedStyle(e).fontSize)).reduce((a,x)=>Math.min(a,x),99)""")
        tabs_ok=pg.evaluate("document.querySelectorAll('#scopeview table').length")
        pg.screenshot(path=f'/tmp/work_dash2/shot_{w}.png',full_page=True)
        print(w,res,'minfont',small,'focus',foc,'|',foc2,'|',foc3,'tables',tabs_ok,'errs',errs)
    b.close()
