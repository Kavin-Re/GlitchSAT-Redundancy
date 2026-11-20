#!/usr/bin/env python3
"""Licence: UNDECIDED.
Checks the reveal wall against its sources. Read-only; writes nothing.

  1. Recounts the V2 rows of research/c2/e2_variance/raw/matrix.csv with its own code
     (not the exporter's): 264 solved settings with min flips 1/2/3 = 180/60/24, and
     152 distinct canonical netlists with 94/38/20; 120 of the 180 one-flip settings use opt_merge.
  2. docs/wow/e2_wall.json: counts, every tile and every netlist equal the source rows.
  3. docs/wow/wall.html: the embedded data equals e2_wall.json; every number written in the
     page text (data-n spans) equals the data in the default (distinct netlists) view;
     the four caveats, the SYNFI caption and the required labels are present.
  4. The V2 / V2e second wall equals research/c6/p01/sweep_rows.csv.

Usage: python3 docs/wow/check_wall.py [--root DIR]      exit code 0 = all PASS
"""
import collections
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if "--root" in sys.argv:
    ROOT = sys.argv[sys.argv.index("--root") + 1]
MATRIX = "research/c2/e2_variance/raw/matrix.csv"
SWEEP = "research/c6/p01/sweep_rows.csv"
fails = 0


def rep(ok, msg):
    global fails
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok:
        fails += 1


def h3(c):
    return [c.get(1, 0), c.get(2, 0), c.get(3, 0)]


def j3(d):
    return [d["1"], d["2"], d["3"]]


# ---------- 1. independent recount from the source ----------
with open(os.path.join(ROOT, MATRIX), newline="", encoding="utf-8") as f:
    src = [(i + 2, r) for i, r in enumerate(csv.DictReader(f))]
v2 = [(ln, r) for ln, r in src if r["design"] == "v2"]
solved = [(ln, r) for ln, r in v2 if r["status"] == "SOLVED"]
per_setting = collections.Counter(int(r["min_flips"]) for _, r in solved)
by_sha = collections.defaultdict(list)
for ln, r in solved:
    by_sha[r["sha256_canon"]].append((ln, r))
conflict = sum(1 for v in by_sha.values() if len({r["min_flips"] for _, r in v}) != 1)
per_netlist = collections.Counter(int(v[0][1]["min_flips"]) for v in by_sha.values())
merge1 = sum(1 for _, r in solved if r["min_flips"] == "1" and r["merge"] == "opt_merge")
rep(len(v2) == 288 and len(solved) == 264, "source: 288 V2 rows, 264 solved (got %d, %d)" % (len(v2), len(solved)))
rep(h3(per_setting) == [180, 60, 24], "source: per setting min 1/2/3 = 180/60/24 (got %s)" % h3(per_setting))
rep(len(by_sha) == 152, "source: 152 distinct canonical netlists (got %d)" % len(by_sha))
rep(conflict == 0, "source: no netlist has two different verdicts (%d conflicts)" % conflict)
rep(h3(per_netlist) == [94, 38, 20], "source: per distinct netlist min 1/2/3 = 94/38/20 (got %s)" % h3(per_netlist))
rep(merge1 == 120 and per_setting[1] == 180, "source: 120 of the 180 one-flip settings use opt_merge (got %d of %d)" % (merge1, per_setting[1]))
rep(not any(r["min_flips"] == "3" and r["merge"] == "opt_merge" for _, r in solved), "source: no opt_merge setting needs 3 flips")

rep(all(r["abc"] == "dff" for _, r in solved if r["min_flips"] == "1" and r["merge"] == "nomerge" and r["order"] == "abc_then_flatten"),
    "source: every one-flip setting with neither opt_merge nor flatten-first uses abc -dff")
# ---------- 2. e2_wall.json ----------
data = json.load(open(os.path.join(HERE, "e2_wall.json"), encoding="utf-8"))
C = data["counts"]
rep(C["settings"]["n"] == 264 and j3(C["settings"]["min"]) == h3(per_setting), "json: settings 264 with 180/60/24")
rep(C["netlists"]["n"] == 152 and j3(C["netlists"]["min"]) == h3(per_netlist), "json: netlists 152 with 94/38/20")
rep(C["settings"]["unsupported"] == len(v2) - len(solved) == 24, "json: 24 settings without a verdict")
rep(C["settings"]["by_cause"]["merge"]["1"] == merge1, "json: caveat number 120 (one-flip settings with opt_merge)")
rep(C["settings"]["pct3"] == round(100 * 24 / 264) and C["netlists"]["pct3"] == round(100 * 20 / 152), "json: percentages 9 and 13")


def cls(merges, order):
    return "merge" if "opt_merge" in merges else ("flat" if order == "flatten_then_abc" else "other")


for view, items in (("settings", [({r["merge"]}, r) for _, r in solved]),
                    ("netlists", [({r["merge"] for _, r in v}, v[0][1]) for v in by_sha.values()])):
    want = {c: {"1": 0, "2": 0, "3": 0} for c in ("merge", "flat", "other")}
    for merges, r in items:
        want[cls(merges, r["order"])][r["min_flips"]] += 1
    rep(C[view]["by_cause"] == want, "json: cause table for %s equals the recount %s" % (view, json.dumps(want, sort_keys=True)))
rep(C["netlists"]["built_with_and_without_merge"] == sum(1 for v in by_sha.values() if len({r["merge"] for _, r in v}) > 1),
    "json: netlists built both with and without opt_merge = %d" % C["netlists"]["built_with_and_without_merge"])

srcmap = dict(v2)
bad = 0
for t in data["tiles"]:
    r = srcmap.get(t["line"])
    ok = r is not None and all(t[k] == r[k] for k in ("build", "flow", "order", "abc", "merge", "keep", "status"))
    ok = ok and r["sha256_canon"].startswith(t["sha"]) and len(t["sha"]) == 16 and r["sha256_raw"].startswith(t["sha_raw"])
    if ok and r["status"] == "SOLVED":
        ok = (t["min"], t["gates"], t["flops"]) == (int(r["min_flips"]), int(r["gates"]), int(r["flops"]))
        ok = ok and t["same"] == len(by_sha[r["sha256_canon"]])
    elif ok:
        ok = t["min"] is None
    bad += not ok
rep(len(data["tiles"]) == 288 and len({t["line"] for t in data["tiles"]}) == 288 and bad == 0,
    "json: 288 tiles, each equal to its matrix.csv line (options, min, gates, flops, sha) (%d bad)" % bad)
bad = 0
short = {k[:16]: v for k, v in by_sha.items()}
for n in data["netlists"]:
    v = short.get(n["sha"])
    ok = v is not None and sorted(n["lines"]) == sorted(ln for ln, _ in v) and n["min"] == int(v[0][1]["min_flips"])
    ok = ok and n["rep_line"] == min(n["lines"]) and n["n_settings"] == len(v)
    bad += not ok
rep(len(data["netlists"]) == 152 and bad == 0, "json: 152 netlists, each with the right source lines and verdict (%d bad)" % bad)
rep(sum(n["n_settings"] for n in data["netlists"]) == 264, "json: netlists cover all 264 solved settings")

# ---------- 4. second wall ----------
with open(os.path.join(ROOT, SWEEP), newline="", encoding="utf-8") as f:
    sw = {i + 2: r for i, r in enumerate(csv.DictReader(f))}
bad, rows = 0, {}
for b in data["v2e"]["blocks"]:
    for c in b["cells"]:
        r = sw[c["line"]]
        ok = r["design"] == b["design"] and r["yosys"].strip() == b["yosys"] and r["variant"] == c["variant"]
        ok = ok and r["min_flips"] == c["min_raw"] and r["netlist_sha256"].startswith(c["sha"]) and int(r["gates"]) == c["gates"]
        bad += not ok
    rows[(b["yosys"][:10], b["design"])] = b["row"]
    rep(b["n3"] == b["row"].split().count("3"), "v2e: %s %s row %s has %d flows at 3" % (b["yosys"][:10], b["design"], b["row"], b["n3"]))
rep(len(data["v2e"]["blocks"]) == 4 and bad == 0, "v2e: 4 blocks x 8 flows equal sweep_rows.csv (%d bad)" % bad)
rep(rows.get(("Yosys 0.33", "v2")) == "2 1 1 2 2 2 2 2" and rows.get(("Yosys 0.33", "v2e")) == "3 1 1 3 3 3 3 3",
    "v2e: Yosys 0.33 rows are 2 1 1 2 2 2 2 2 (v2) and 3 1 1 3 3 3 3 3 (v2e), as in WHY_TWO_FLIPS.md")
rep(data["v2e"]["constants_tried"] == len({r["armed_const"] for r in sw.values()}), "v2e: constants tried = %d" % data["v2e"]["constants_tried"])

# ---------- 3. the page ----------
html = open(os.path.join(HERE, "wall.html"), encoding="utf-8").read()
m = re.search(r'<script type="application/json" id="wall-data">(.*?)</script>', html, re.S)
emb = json.loads(m.group(1)) if m else None
rep(emb == data, "page: embedded data equals docs/wow/e2_wall.json")


def get(path):
    o = data
    for k in path.split("."):
        o = o[int(k)] if isinstance(o, list) else o[k]
    return o


spans = re.findall(r'<(\w+)[^>]*\bdata-n="([^"]+)"[^>]*>([^<]*)</\1>', html)
bad = [(p, txt) for _, p, txt in spans if str(get(p.replace("{view}", "netlists"))) != txt.strip()]
rep(len(spans) >= 30 and not bad, "page: all %d numbers in the text equal the data (default view) %s" % (len(spans), bad[:5] if bad else ""))
static = re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->", " ", html, flags=re.S)
text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", static))
stray = re.findall(r"(?<![.=\w])(?:264|152|180|120|94|38|60)\b", re.sub(r'<(\w+)[^>]*\bdata-n="[^"]+"[^>]*>[^<]*</\1>', " ", static))
rep(not stray, "page: no headline count is hard-coded outside a checked data-n span %s" % stray)
for i, needle in ((1, "One toy design"), (2, "not independent"), (3, "opt_merge"), (4, "SYNFI")):
    mm = re.search(r'<li data-caveat="%d">(.*?)</li>' % i, html, re.S)
    rep(bool(mm) and needle in mm.group(1), "page: caveat %d present (%s)" % (i, needle))
rep('id="caveats"' in html and not re.search(r'\[data-stage[^{]*(#caveats|\.caveats)[^{]*\{', html)
    and "hide0" not in re.search(r'<div class="([^"]*)" id="caveats"', html).group(1),
    "page: caveat box is never hidden by a stage step")
rep("Same blueprint," in text and "only a minority give the full 3-flip protection" in text, "page: headline wording")
rep("Previously shown by SYNFI" in text, "page: cause caption says 'Previously shown by SYNFI'")
rep("Nothing established as new" in text or "nothing established as new" in text.lower(), "page: 'nothing established as new'")
rep("" in text and "UNDECIDED" in text and "MEASURED" in text, "page: draft / licence / MEASURED labels")
rep(re.search(r'id="vN" aria-pressed="true"', html) is not None and "view=(Q.view===\"264\"" in html, "page: default view is the 152 distinct netlists")
rep("prefers-reduced-motion" in html and "prefers-color-scheme:dark" in html, "page: reduced-motion and dark rules present")
rep(not re.search(r'(?:src|href)\s*=\s*"(?:https?:)?//', html) and "@import" not in html and "fetch(" not in html,
    "page: no network resource (works from file://)")
low = text.lower()
rep(not any(w in low for w in (" proved", "proves", "novel", "first to")), "page: no proved / novel / first wording")

print("\n%s: %d check(s) failed" % ("FAIL" if fails else "ALL PASS", fails))
sys.exit(1 if fails else 0)
