import json,sys
from playwright.sync_api import sync_playwright
out='research/c5/w8/shots/'
res={}
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    for page in ['explainer','game']:
        for w,h,name in [(390,844,'390'),(1366,800,'1366'),(320,640,'320'),(640,800,'640z')]:
            pg=b.new_page(viewport={'width':w,'height':h}); errs=[]
            pg.on('console',lambda m:errs.append(m.text) if m.type=='error' else None); pg.on('pageerror',lambda e:errs.append(str(e)))
            pg.goto('file://<repo>/docs/explainers/%s.html'%page); pg.wait_for_timeout(300)
            r=pg.evaluate('''()=>{const de=document.documentElement;let small=[],btn=[];
            const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let n;
            while(n=w.nextNode()){if(!n.textContent.trim())continue;const e=n.parentElement;if(e.closest('svg'))continue;const cs=getComputedStyle(e);if(cs.display==='none'||e.closest('details:not([open]) :not(summary)')&&false)continue;const fs=parseFloat(cs.fontSize);if(fs<12)small.push([fs,n.textContent.trim().slice(0,30)])}
            document.querySelectorAll('button,a.go,a.skip,summary').forEach(b=>{const r=b.getBoundingClientRect();if(r.width&&(r.height<44||r.width<44))btn.push([b.textContent.trim().slice(0,25),r.width,r.height])});
            return {sw:de.scrollWidth,cw:de.clientWidth,small,btn}}''')
            r['errs']=errs; res[page+name]=r
            pg.screenshot(path=out+page+'_'+name+'.png',full_page=(name!='1366'))
            if page=='game' and name=='390':
                pg.screenshot(path=out+'game_390_top.png')
            pg.close()
    b.close()
print(json.dumps(res,indent=1))
