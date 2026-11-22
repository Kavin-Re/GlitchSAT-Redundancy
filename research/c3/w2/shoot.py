import asyncio,sys
from playwright.async_api import async_playwright
ROOT="file://<repo>/docs/explainers/"
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path='/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell',args=['--no-sandbox'])
        for w,h,tag in((390,800,'390'),(1366,768,'1366')):
            for page_name in('explainer','game'):
                for scheme in('light','dark'):
                    ctx=await b.new_context(viewport={'width':w,'height':h},color_scheme=scheme,reduced_motion='reduce')
                    pg=await ctx.new_page(); errs=[]
                    pg.on('console',lambda m:errs.append(m.text) if m.type=='error' else None)
                    pg.on('pageerror',lambda e:errs.append(str(e)))
                    await pg.goto(ROOT+page_name+'.html')
                    if page_name=='game':
                        for i in range(6):
                            await pg.locator('.tab').nth(i).click()
                            await pg.click('#best')
                            if scheme=='light' : await pg.locator('#fig').screenshot(path=f'shots/game_{tag}_d{i}.png')
                    else:
                        await pg.click('[data-btn=hero]'); await pg.click('[data-pick=tool2]')
                        for _ in range(3): await pg.click('[data-btn=own]')
                    sw=await pg.evaluate('document.documentElement.scrollWidth'); 
                    small=await pg.evaluate('''[...document.querySelectorAll('body *')].filter(e=>e.children.length==0&&e.textContent.trim()&&parseFloat(getComputedStyle(e).fontSize)<12).length''')
                    h2=await pg.evaluate('document.documentElement.scrollHeight')
                    print(page_name,tag,scheme,'scrollW',sw,'vw',w,'height',h2,'tiny',small,'errors',errs)
                    if scheme=='light': await pg.screenshot(path=f'shots/{page_name}_{tag}_full.png',full_page=True)
                    await ctx.close()
        await b.close()
asyncio.run(main())
