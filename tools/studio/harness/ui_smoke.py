"""Quick UI smoke test in recorded mode and stand-in live mode: page errors only."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness
from playwright.sync_api import sync_playwright
def go(port, live, shot):
    s = harness.start(port, live=live); errs = []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_context(viewport={'width': 1366, 'height': 768}).new_page()
            pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: m.type == 'error' and errs.append(m.text))
            pg.goto(f'http://127.0.0.1:{port}/'); pg.wait_for_timeout(600); pg.click('#hclose')
            for i in range(6):
                pg.click(f'.step[data-i="{i}"]'); pg.wait_for_timeout(1500 if live else 600)
            pg.screenshot(path=shot + '_step6.png')
            pg.click('.step[data-i="2"]'); pg.wait_for_timeout(2500 if live else 600); pg.screenshot(path=shot + '_step3.png')
            pg.keyboard.press('3'); pg.wait_for_timeout(1200); pg.screenshot(path=shot + '_findings.png')
            pg.keyboard.press('2'); pg.wait_for_timeout(300); pg.keyboard.press('4'); pg.wait_for_timeout(300); pg.keyboard.press('v'); pg.wait_for_timeout(300)
            b.close()
    finally: s.terminate()
    print('live' if live else 'recorded', 'errors:', errs)
go(8821, False, '/tmp/smoke_rec'); go(8822, True, '/tmp/smoke_live')
