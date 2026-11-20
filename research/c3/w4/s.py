from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    br=p.chromium.launch(executable_path="/usr/bin/google-chrome",args=["--no-sandbox"])
    pg=br.new_page(viewport={"width":390,"height":844},reduced_motion="reduce")
    pg.goto("file:///home/user/project/docs/wow/explainer.html")
    pg.screenshot(path="shots/full390.png",full_page=True)
    from PIL import Image
    im=Image.open("shots/full390.png");h=im.height
    for i in range(0,h,1500): im.crop((0,i,390,min(h,i+1500))).save(f"shots/part{i//1500}.png")
