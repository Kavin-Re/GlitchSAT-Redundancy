import json,sys
from playwright.sync_api import sync_playwright
B="/home/user/project/docs/wow/"
sizes=[("390",390,844,2),("1366",1366,800,1),("320",320,640,2),("zoom200",640,400,2),("zoom200phone",195,420,2)]
res=[]
with sync_playwright() as p:
    br=p.chromium.launch(executable_path="/usr/bin/google-chrome",args=["--no-sandbox"],headless=True)
    for page_name in ["explainer","game"]:
        for nm,w,h,dsf in sizes:
            for scheme in ["light","dark"]:
                if scheme=="dark" and nm not in("390","1366"):continue
                ctx=br.new_context(viewport={"width":w,"height":h},device_scale_factor=dsf if nm!="1366" else 1,color_scheme=scheme,reduced_motion="reduce")
                pg=ctx.new_page();errs=[]
                pg.on("console",lambda m:errs.append(m.text) if m.type=="error" else None)
                pg.on("pageerror",lambda e:errs.append(str(e)))
                pg.goto("file://"+B+page_name+".html");pg.wait_for_timeout(400)
                if page_name=="explainer":
                    pg.click("[data-btn=hero]");pg.click("[data-pick=tool2]");pg.click("[data-all=pick]");pg.click("[data-count='2']")
                else:
                    pg.click("#tabs button:nth-child(6)");pg.click("#best")
                pg.wait_for_timeout(300)
                info=pg.evaluate("""()=>{const de=document.documentElement;let small=[];
                 document.querySelectorAll('body *').forEach(e=>{if(!e.childNodes.length)return;let t=[...e.childNodes].some(n=>n.nodeType==3&&n.textContent.trim());if(!t)return;const cs=getComputedStyle(e);if(e.closest('svg')){const r=e.getBoundingClientRect();if(r.width&&r.height>0&&parseFloat(cs.fontSize)*r.width/e.getBBox().width<11.5)small.push('svg:'+e.textContent.slice(0,20));return}
                  if(parseFloat(cs.fontSize)<12&&e.offsetParent!==null)small.push(e.tagName+':'+e.textContent.slice(0,20))});
                 const sm=[...document.querySelectorAll('button,.go,summary')].filter(b=>b.offsetParent!==null).map(b=>{const r=b.getBoundingClientRect();return [b.textContent.trim().slice(0,25),Math.round(r.width),Math.round(r.height)]}).filter(x=>x[2]<44||x[1]<44);
                 const lights=[...document.querySelectorAll('.lightc')].map(c=>Math.round(c.getBoundingClientRect().width));
                 const ev=document.getElementById('evd');
                 return {sw:de.scrollWidth,cw:de.clientWidth,small,sm,lights:lights.slice(0,1),evopen:ev&&ev.open,evtext:ev?ev.innerText.length:0,h:de.scrollHeight}}""")
                pg.screenshot(path=f"shots/{page_name}_{nm}_{scheme}.png",full_page=True)
                res.append((page_name,nm,scheme,errs,info))
                ctx.close()
    br.close()
for r in res:print(r)
