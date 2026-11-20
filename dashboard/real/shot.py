from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium-1243/chrome-linux64/chrome',args=['--no-sandbox']); pg=b.new_page(viewport={'width':1200,'height':900},device_scale_factor=2)
    errs=[]; pg.on('console',lambda m: m.type=='error' and errs.append(m.text)); pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto('file://<repo>/dashboard/real/index.html'); pg.wait_for_timeout(500)
    pg.screenshot(path='dashboard/real/page.png',full_page=True); print('errors',errs); b.close()
