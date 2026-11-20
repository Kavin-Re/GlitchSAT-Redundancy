from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/usr/bin/google-chrome",args=["--no-sandbox","--trace","off"][:2])
    for name in ['explainer','game']:
        for w,h,t in [(390,844,'phone'),(1366,768,'desk')]:
            pg=b.new_page(viewport={'width':w,'height':h},device_scale_factor=1)
            pg.goto(f'file://<repo>/docs/wow/{name}.html')
            pg.wait_for_timeout(800)
            pg.screenshot(path=f'{name}_{t}.png',full_page=True)
            print(name,t,pg.evaluate('[document.documentElement.scrollWidth,document.documentElement.scrollHeight]'))
            if t=='phone':
                print(pg.evaluate('document.body.innerText')[:3500] if name=='explainer' else pg.evaluate('document.body.innerText')[:2500])
                # small fonts
                print(pg.evaluate('''[...document.querySelectorAll("body *")].filter(e=>e.children.length==0&&e.innerText&&e.innerText.trim()&&parseFloat(getComputedStyle(e).fontSize)<12).map(e=>e.innerText.trim().slice(0,30)+"|"+getComputedStyle(e).fontSize).slice(0,15)'''))
            pg.close()
