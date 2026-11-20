from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox']);pg=b.new_page(viewport={'width':1366,'height':900})
    pg.goto('file:///tmp/work_dash/dashboard/index.html')
    pg.focus('#tabs button:nth-child(4)'); pg.keyboard.press('Enter')
    print('after Enter on Scope tab, focused:',pg.evaluate("document.activeElement.textContent"),'| scope visible',pg.evaluate("!document.getElementById('scopeview').hidden"))
    pg.keyboard.press('ArrowLeft'); pg.keyboard.press('Shift+Tab'); print('shift-tab focused:',pg.evaluate("document.activeElement.textContent"))
    pg.focus('#tabs button:nth-child(3)'); pg.keyboard.press('Space'); print('space V2 focus:',pg.evaluate("document.activeElement.textContent"),pg.evaluate("document.querySelector('#tabs [aria-pressed=true]').textContent"))
    pg.screenshot(path='/tmp/work_dash/sc.png',clip={'x':0,'y':0,'width':1366,'height':900})
    pg.focus('#tabs button:nth-child(4)');pg.keyboard.press('Enter');pg.locator('#scopeview').screenshot(path='/tmp/work_dash/scope.png')
