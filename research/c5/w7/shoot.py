from playwright.sync_api import sync_playwright
out='research/c5/w7/shots/'
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--headless=new','--no-sandbox'])
    for page in ['explainer','game']:
        for w,h in [(390,844),(1366,768),(320,640),(640,400)]:
            c=b.new_page(viewport={'width':w,'height':h}); errs=[]
            c.on('console',lambda m:errs.append(m.text) if m.type=='error' else None); c.on('pageerror',lambda e:errs.append(str(e)))
            c.goto(f'file://<repo>/docs/wow/{page}.html'); c.wait_for_timeout(300)
            sw=c.evaluate('document.documentElement.scrollWidth-innerWidth')
            small=c.evaluate('''[...document.querySelectorAll('body *')].filter(e=>!(e instanceof SVGElement)&&e.childNodes.length&&[...e.childNodes].some(n=>n.nodeType==3&&n.textContent.trim())&&e.offsetParent!==null&&parseFloat(getComputedStyle(e).fontSize)<12).map(e=>e.tagName+':'+e.textContent.slice(0,20))''')
            btn=c.evaluate('''[...document.querySelectorAll('button,a.go,a.skip,summary')].filter(e=>e.offsetParent!==null).map(e=>[e.textContent.trim().slice(0,25),Math.round(e.getBoundingClientRect().height),Math.round(e.getBoundingClientRect().width)]).filter(x=>x[1]<44||x[2]<44)''')
            if page=='explainer':
                pos=c.evaluate('''(()=>{var r=e=>{var q=document.querySelector(e).getBoundingClientRect();return Math.round(q.top)+'-'+Math.round(q.bottom)};return {btn:r('#herobtn'),fig:r('#herofig')}})()''')
            else:
                pos=c.evaluate('''(()=>{var q=document.getElementById('fig').getBoundingClientRect();return {figtop:Math.round(q.top),figbottom:Math.round(q.bottom)}})()''')
            print(page,w,h,'errs',errs,'sideways',sw,'small',small,'smallbtn',btn,pos)
            c.screenshot(path=f'{out}{page}_{w}_fold.png')
            c.screenshot(path=f'{out}{page}_{w}.png',full_page=(w!=640)); c.close()
    b.close()
