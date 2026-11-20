#!/usr/bin/env python3
"""Checks the Verdict Dial against its source rows. Writes nothing.

Part A (always): re-reads the source data files with its OWN parsing code (does not import build_dial.py) and asserts,
  for ALL control combinations, that dial.json holds the source row's value, or 'not_measured' where no source row exists;
  that the data block inlined in dial.html equals dial.json; and that banned words are absent from the page.
Part B (--browser, needs playwright + /usr/bin/google-chrome): opens dial.html from file://, sets every combination and
  asserts that the digit ON SCREEN equals the source row (or the words 'not measured'), that the bound string and the
  source file + row are shown for measured cells, plus predict-first, the 3->2->1->0 count-down and the F key.
Usage: python3 docs/wow/check_dial.py [--browser]        exit code 0 = all pass
"""
import csv, itertools, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
fails = 0; passes = 0
def rep(ok, msg, quiet=False):
    global fails, passes
    if ok: passes += 1
    else: fails += 1
    if not ok or not quiet: print(("PASS " if ok else "FAIL ") + msg)

# ---- the expected table, straight from the sources ------------------------------------------------------------
matrix = {}
for n, line in enumerate(open(os.path.join(ROOT, "research/c2/b2_scope/matrix.jsonl"), encoding="utf-8"), 1):
    if line.strip():
        r = json.loads(line)
        matrix[(r["design"], r["netlist"], r["goal"], r["input_sites"], r["init"], r["free_input"])] = (n, r)
masks = {}
for n, r in enumerate(csv.DictReader(open(os.path.join(ROOT, "research/c3/m1/m1_all_masks.csv"), encoding="utf-8", newline="")), 2):
    masks[r["mask_hex"]] = (n, r)
p01 = {}
for n, r in enumerate(csv.DictReader(open(os.path.join(ROOT, "research/c6/p01/sweep_rows.csv"), encoding="utf-8", newline="")), 2):
    if r["yosys"].startswith("Yosys 0.33"):
        p01[(r["design"], r["variant"])] = (n, r)

def expected(design, reader, build, inputs, power):
    """-> (value, file, line) or None if no source row covers this combination."""
    if reader in ("word", "flag") and build in ("stored", "plain"):
        k = (design, {"stored": "spike", "plain": "apt033_plain"}[build], {"word": "boot_word", "flag": "boot_ok"}[reader],
             inputs == "yes", {"known": "known", "nonopen": "free_nongoal", "any": "free"}[power], False)
        if k in matrix and matrix[k][1]["verdict"] == "ATTACK_FOUND":
            return (matrix[k][1]["min_cost"], "research/c2/b2_scope/matrix.jsonl", matrix[k][0])
        return None
    if reader.startswith("m") and inputs == "no" and power == "known":
        col = {("v0", "stored"): "v0_spike_min_flips", ("v1", "stored"): "v1_spike_min_flips", ("v1", "plain"): "v1_apt033_min_flips",
               ("v2", "stored"): "v2_spike_min_flips", ("v2", "plain"): "v2_apt033_min_flips"}.get((design, build))
        if col and reader[1:] in masks:
            return (int(masks[reader[1:]][1][col]), "research/c3/m1/m1_all_masks.csv", masks[reader[1:]][0])
        return None
    if design == "v2" and reader == "word" and inputs == "no" and power == "known" and build in ("merge", "v2e"):
        k = {"merge": ("v2", "plain_opt_merge"), "v2e": ("v2e", "plain")}[build]
        if k in p01:
            return (int(p01[k][1]["min_flips"]), "research/c6/p01/sweep_rows.csv", p01[k][0])
    return None

# ---- Part A ---------------------------------------------------------------------------------------------------
data = json.load(open(os.path.join(HERE, "dial.json"), encoding="utf-8"))
C = data["controls"]
combos = list(itertools.product(*[[o["id"] for o in C[k]] for k in ("design", "reader", "build", "inputs", "power")]))
rep(len(combos) == len(data["cells"]) == data["meta"]["cells_total"], "dial.json has one cell for each of the %d control combinations" % len(combos))
EXP = {}; n_meas = 0
for c in combos:
    key = "|".join(c); e = expected(*c); EXP[key] = e; cell = data["cells"].get(key)
    if cell is None: rep(False, key + ": missing from dial.json"); continue
    if e is None:
        rep(cell["status"] == "not_measured" and cell["value"] is None, "%s: no source row -> not_measured (got %r)" % (key, cell.get("value")), quiet=True)
    else:
        n_meas += 1
        ok = (cell["status"] == "measured" and cell["value"] == e[0] and cell["source"]["file"] == e[1] and cell["source"]["row"] == "line %d" % e[2]
              and cell["reason"] in data["reasons"] and cell["bound"]["ticks"] == 6 and cell["bound"]["kmax"] == 3)
        rep(ok, "%s: expected %s from %s line %d, dial.json has %r" % (key, e[0], e[1], e[2], cell.get("value")), quiet=True)
rep(n_meas == data["meta"]["cells_measured"], "%d measured cells, %d not measured (every one checked against its source row)" % (n_meas, len(combos) - n_meas))
# the scope matrix says attacker input constant vs fresh makes no difference: the dial uses the constant rows; confirm the claim
diff = [k for k in matrix if not k[5] and matrix[k][1]["min_cost"] != matrix[k[:5] + (True,)][1]["min_cost"]]
rep(not diff, "scope matrix: constant-input and fresh-input rows agree in all %d pairs (dial shows the constant-input row)" % (len(matrix) // 2))
# the two sources for 'V2, plain re-build, whole word' agree
rep(expected("v2", "word", "plain", "no", "known")[0] == int(p01[("v2", "plain")][1]["min_flips"]), "V2 plain re-build: matrix.jsonl and sweep_rows.csv (Yosys 0.33, plain) give the same digit")
# the V2e note is a count of source rows
v2e = [int(r["min_flips"]) for (d, _), (_, r) in p01.items() if d == "v2e"]
note = data["cells"]["v2|word|v2e|no|known"].get("note", "")
rep(note == "Measured 3 in %d of %d recipes on Yosys 0.33; %d merging recipes stay at 1." % (v2e.count(3), len(v2e), v2e.count(1)), "V2e note matches the 8 source rows: " + note)
# the story the dial is built for: 3 -> 2 -> 1 -> 0
story = [data["cells"][k]["value"] for k in ("v2|word|stored|no|known", "v2|word|plain|no|known", "v2|flag|plain|no|known", "v2|flag|plain|no|any")]
rep(story == [3, 2, 1, 0], "stage path stored -> re-built -> accept flag -> any power-up reads %s" % story)

html = open(os.path.join(HERE, "dial.html"), encoding="utf-8").read()
m = re.search(r'<script type="application/json" id="dial-data">(.*?)</script>', html, re.S)
rep(bool(m) and json.loads(m.group(1)) == data, "data inlined in dial.html equals dial.json")
visible = re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->", " ", html, flags=re.S)
text = re.sub(r"<[^>]+>", " ", visible) + " " + " ".join(data["reasons"].values())
for w in ("secure", "glitch-proof", "certified", "hardened", "proven", "proved", "works on real chips", "novel"):
    rep(not re.search(r"\b" + re.escape(w), text, re.I), "banned word absent: " + w, quiet=True)
safe_uses = re.findall(r".{0,12}\bsafe\b.{0,3}", text, re.I)
rep(all("Not" in u or "not" in u for u in safe_uses), "'safe' appears only as 'Not \"safe\"' (%d use)" % len(safe_uses))
rep("What we did NOT show" in html and "not measured" in html, "page has the 'What we did NOT show' panel and the words 'not measured'")
rep(not re.search(r'(src|href)\s*=\s*"(https?:)?//', html), "page loads no external resource")

# ---- Part B ---------------------------------------------------------------------------------------------------
if "--browser" in sys.argv:
    from playwright.sync_api import sync_playwright
    url = "file://" + os.path.join(HERE, "dial.html")
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True, args=["--no-sandbox"])
        for width in (390, 1366):
            ctx = br.new_context(viewport={"width": width, "height": 844 if width == 390 else 768}, reduced_motion="reduce")
            pg = ctx.new_page(); errs = []
            pg.on("console", lambda mm: errs.append(mm.text) if mm.type in ("error", "warning") else None)
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(url)
            rep(sorted(pg.evaluate("window.__dial.keys()")) == sorted(EXP), "[%d px] page offers exactly the %d checked combinations" % (width, len(EXP)))
            bad = 0; wide = 0
            for key, e in EXP.items():
                pg.evaluate("k => window.__dial.set(k)", key)
                # also confirm the radios on screen really are in this state (the digit is driven by the visible switches)
                state = pg.evaluate("""() => { const v = n => document.querySelector('input[name="'+n+'"]:checked').value;
                    const k = v('kind'); return [v('design'), k==='four' ? 'm'+v('mask') : k, v('build'), v('inputs'), v('power')].join('|') }""")
                s = pg.evaluate("window.__dial.screen()")
                if e is None:
                    ok = s["digit"] == "not measured" and s["tag"] == "Not measured" and not re.search(r"\d", s["digit"]) and "none" in s["src"]
                else:
                    ok = (s["digit"] == str(e[0]) and s["tag"] == "Measured" and s["src"] == "Source: %s, line %d" % (e[1], e[2])
                          and "6 ticks" in s["bound"] and (e[0] == 0 or "No attack found" in s["bound"]) and s["reason"] == data["reasons"][data["cells"][key]["reason"]])
                ok = ok and state == key
                if not ok: bad += 1; rep(False, "[%d px] %s: expected %s, screen shows %r" % (width, key, e and e[0], s))
                if pg.evaluate("document.documentElement.scrollWidth") > width: wide += 1
            rep(bad == 0, "[%d px] digit on screen equals the source row in all %d combinations (%d digits, %d 'not measured')" % (width, len(EXP), n_meas, len(EXP) - n_meas))
            rep(wide == 0, "[%d px] no horizontal scroll in any combination" % width)
            # real clicks + keyboard on the visible switches
            pg.goto(url); pg.evaluate("location.reload()"); pg.wait_for_timeout(100)
            pg.goto(url.split("#")[0] + "#v2.word.stored.no.known"); pg.reload()
            rep(pg.inner_text("#digit") == "3", "[%d px] default shows 3" % width)
            pg.locator('input[name="build"][value="plain"]').check(force=True); a = pg.inner_text("#digit")
            pg.locator('input[name="kind"][value="flag"]').check(force=True); b = pg.inner_text("#digit")
            pg.locator('input[name="power"][value="known"]').focus(); pg.keyboard.press("ArrowRight"); pg.keyboard.press("ArrowRight"); c = pg.inner_text("#digit")
            rep((a, b, c) == ("2", "1", "0"), "[%d px] clicking and arrow keys walk 3 -> %s -> %s -> %s" % (width, a, b, c))
            # predict first: the digit is hidden until a guess is made
            pg.keyboard.press("p"); hid = pg.inner_text("#digit"); dis = pg.is_disabled("#bReveal")
            leak = pg.evaluate("() => ['reason','bound','src'].every(i => document.getElementById(i).hidden)")
            pg.locator('input[name="power"][value="known"]').check(force=True); hid2 = pg.inner_text("#digit")
            pg.keyboard.press("2"); pg.keyboard.press("r")
            rep(hid == "?" and hid2 == "?" and dis and leak and pg.inner_text("#digit") == "1" and pg.inner_text("#said") == "You said 2. Measured: 1.",
                "[%d px] predict first hides digit, reason and source until a guess; reveal shows the measured 1" % width)
            pg.keyboard.press("p"); pg.keyboard.press("f"); big = pg.evaluate("document.body.classList.contains('big')")
            rep(big and pg.evaluate("document.documentElement.scrollWidth") <= width, "[%d px] F switches to big-screen mode, no horizontal scroll" % width)
            rep(not errs, "[%d px] no console errors or warnings %s" % (width, errs or ""))
            ctx.close()
        # with motion allowed the digit counts through every step
        ctx = br.new_context(viewport={"width": 1366, "height": 768}); pg = ctx.new_page(); pg.goto(url + "#v2.word.stored.no.known")
        pg.evaluate("""() => { window.__seen = []; new MutationObserver(() => window.__seen.push(document.getElementById('digit').textContent))
            .observe(document.getElementById('digit'), {childList: true, characterData: true, subtree: true}) }""")
        pg.locator('input[name="power"][value="any"]').check(force=True); pg.wait_for_timeout(1500)
        seen = pg.evaluate("window.__seen")
        rep(seen == ["2", "1", "0"] and pg.evaluate("document.body.dataset.shown") == "0", "motion allowed: digit counts %s and lands on the measured 0" % seen)
        ctx.close(); br.close()
else:
    print("NOTE browser part skipped (run with --browser to check the digits on screen)")
print("%d checks passed, %d failed" % (passes, fails))
sys.exit(1 if fails else 0)
