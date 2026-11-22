#!/usr/bin/env python3
"""check_numbers.py: scan the docs for stale headline numbers listed in docs/NUMBERS.md.

Read-only: it never edits a scanned file.

NUMBERS.md carries a fenced ```json block with: scan_globs, skip, hist_re, owners and rules.
Each rule is {id, re, should, label, hist}: a line matching `re` in any scanned file is a mismatch.
If rule.hist is true (an OLD value) and the line also matches hist_re ("stale", "superseded",
"first writing", ...) it is reported as HISTORICAL (old value quoted as history; does not fail the run).
Rules with hist false (a wrong value presented as current) are always STALE.

Usage (from any directory; run on the tree or on a copy):
  python3 scripts/check_numbers.py [--root DIR] [--numbers docs/NUMBERS.md]
                                   [--verify] [--pytest] [--md OUT.md] [--json]
  --verify  recompute the stored-data numbers (E2 180/60/24, M1 88/96/44, REP 26/6/32,
            reproduce 36 rows, held-out 144 raw / 150 corrected) and compare with NUMBERS.md
  --pytest  also run `pytest --co -q` on tests/ and product/tests (needs pytest, and
            `pip install ./product[test]` for the second) and compare the collected counts
Exit code: 0 no STALE lines, 1 STALE lines found, 2 NUMBERS.md unreadable.
"""
import argparse, csv, glob, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load_block(path):
    txt = open(path, encoding="utf-8").read()
    for m in re.finditer(r"```json\s*\n(.*?)\n```", txt, re.S):
        try:
            d = json.loads(m.group(1))
        except ValueError:
            continue
        if "rules" in d and "scan_globs" in d:
            return d
    raise SystemExit("no machine-readable json block with rules/scan_globs in %s" % path)


def owner_of(rel, owners):
    best = ""
    for k in owners:
        if (rel == k or (k.endswith("/") and rel.startswith(k))) and len(k) > len(best):
            best = k
    return owners.get(best, "author")


def scan(root, blk):
    skip = set(blk.get("skip", []))
    hist = re.compile(blk["hist_re"]) if blk.get("hist_re") else None
    files = []
    for g in blk["scan_globs"]:
        for p in sorted(glob.glob(os.path.join(root, g))):
            rel = os.path.relpath(p, root)
            if rel not in skip and rel not in files and os.path.isfile(p):
                files.append(rel)
    rules = [(r, re.compile(r["re"])) for r in blk["rules"]]
    out = []
    for rel in files:
        try:
            lines = open(os.path.join(root, rel), encoding="utf-8", errors="replace").read().split("\n")
        except OSError:
            continue
        for n, line in enumerate(lines, 1):
            for r, rx in rules:
                m = rx.search(line)
                if not m:
                    continue
                kind = "HISTORICAL" if (hist and r.get("hist", True) and hist.search(line)) else "STALE"
                out.append(dict(id=r["id"], file=rel, line=n, found=m.group(0).strip(), should=r["should"],
                                label=r.get("label", ""), kind=kind, owner=owner_of(rel, blk.get("owners", {})),
                                context=line.strip()[:160]))
    return files, out


# ---------------- recomputation of stored-data numbers
def v_heldout(root):
    p = os.path.join(root, "research/c4/ver/heldout.csv")
    h = list(csv.DictReader(open(p)))
    raw = sum(x["pred"] == x["solver"] for x in h)
    rx = {}
    rp = os.path.join(root, "research/c4/ver/rerun_x.json")
    if os.path.exists(rp):
        for o in json.load(open(rp)):
            rx[(os.path.basename(o["json"]), o["mask"])] = str(o["new"])
    exact = 0
    for r in h:
        s = rx.get((os.path.basename(r["json"]), r["mask"]), r["solver"])
        sv = 4 if s == ">3" else int(s)
        exact += (sv == min(int(r["pred"]), 4))
    return (len(h) == 163 and raw == 144 and exact == 150), "cells %d raw %d corrected %d (expect 163/144/150)" % (len(h), raw, exact)


def v_e2(root):
    from collections import Counter
    c = Counter()
    n = 0
    for r in csv.DictReader(open(os.path.join(root, "research/c2/e2_variance/raw/matrix.csv"))):
        n += 1
        if r["status"] == "SOLVED":
            c[(r["design"], r["min_flips"])] += 1
    got = [c[("v2", k)] for k in ("1", "2", "3")]
    v1 = [c[("v1", k)] for k in ("1", "2", "3")]
    v0 = [c[("v0", k)] for k in ("1", "2", "3")]
    ok = n == 864 and got == [180, 60, 24] and v1 == [233, 31, 0] and v0 == [264, 0, 0]
    return ok, "configs %d V2 %s V1 %s V0 %s (expect 864, 180/60/24, 233/31/0, 264/0/0)" % (n, got, v1, v0)


def v_m1(root):
    rows = list(csv.DictReader(open(os.path.join(root, "research/c3/m1/m1_all_masks.csv"))))
    nc = [r for r in rows if r["collides_with_legit_state"] == "0"]
    cnt = {k: sum(r["v2_spike_min_flips"] == k for r in nc) for k in "123"}
    coll = len(rows) - len(nc)
    # sentinel for ">2"/">3" cells may be text; count anything else as 3
    other = len(nc) - sum(cnt.values())
    curve = []
    for n in range(1, 9):
        m = "0x%02X" % ((1 << n) - 1)
        r = [x for x in rows if x["mask_hex"].upper().replace("0X", "0x") in (m, m.lower(), m.upper())]
        curve.append(r[0]["v2_spike_min_flips"] if r else "?")
    ok = (len(rows) == 255 and coll == 27 and cnt["1"] == 88 and cnt["2"] + 0 == 96 and cnt["3"] + other == 44
          and curve == ["0", "1", "1", "2", "2", "3", "3", "3"])
    return ok, "masks %d colliding %d split 1/2/3 = %d/%d/%d width curve %s (expect 255, 27, 88/96/44, 0,1,1,2,2,3,3,3)" % (
        len(rows), coll, cnt["1"], cnt["2"], cnt["3"] + other, ",".join(curve))


def v_rep(root):
    rows = list(csv.DictReader(open(os.path.join(root, "research/c3/rep/rep_results.csv"))))
    v2 = [r for r in rows if r["netlist"].startswith("v2")]
    v1 = [r for r in rows if r["netlist"].startswith("v1")]
    u2 = (sum(r["rep_unit_cli"] == "2" for r in v2), sum(r["rep_unit_cli"] == "3" for r in v2))
    f2 = sum(r["rep_fanout_pins"] == "3" for r in v2)
    f1 = sum(r["rep_fanout_pins"] == "2" for r in v1)
    ag = sum(r["agree_unit"] == "True" and r["agree_fanout"] == "True" for r in rows)
    ok = (len(v2), len(v1)) == (32, 32) and u2 == (26, 6) and f2 == 32 and f1 == 32 and ag == 64
    return ok, "V2 n=%d unit(2,3)=%s fanout3=%d; V1 n=%d fanout2=%d; agree rows %d (expect 32, (26,6), 32, 32, 32, 64)" % (
        len(v2), u2, f2, len(v1), f1, ag)


def v_repro(root):
    d = json.load(open(os.path.join(root, "results/reproduce_summary.json")))
    n = len(d["rows"])
    return n == 36, "reproduce_summary.json rows %d (expect 36)" % n


VERIFY = [("heldout 144 raw / 150 corrected", v_heldout), ("E2 matrix 180/60/24", v_e2),
          ("M1 masks 88/96/44 and width curve", v_m1), ("REP 26/6 and 32/32 and 64/64", v_rep),
          ("reproduce rows 36", v_repro)]


# ---------------- RECON2 additions: recount stored data of the C4 steps (no solver is run)
def v_m1b(root):
    a = os.path.join(root, "research/c4/m1b/m1b_all_masks.csv")
    b = os.path.join(root, "research/c3/m1/m1_all_masks.csv")
    same = open(a, "rb").read() == open(b, "rb").read()
    return same, "m1b_all_masks.csv byte-identical to m1_all_masks.csv: %s (expect True; 0 of 1785 cells changed)" % same


def v_b3(root):
    rows = [json.loads(l) for l in open(os.path.join(root, "research/c4/b3/matrix_T6.jsonl")) if l.strip()]
    def cell(d, m, g):
        r = [x for x in rows if x["design"] == d and x["model"] == m and x["goal"] == g]
        return r[0]["min"] if r else "?"
    rail = all(cell(d, m, g) == ">3" for d in ("v2", "v2_apt033", "v5_apt033", "v1", "v0")
               for m in ("rail_all", "rail_half", "rail_unions") for g in ("word", "ok"))
    cone = (cell("v0", "rail_cone", "word") == "1" and cell("v2", "rail_cone", "word") == ">3"
            and cell("v5_apt033", "rail_cone", "word") == ">3")
    sub = all(r["min"] == "1" for r in rows if r["model"] == "dip_subset")
    unk = sum(1 for r in rows if "unknown" in str(r.get("status", "")).lower() or r["min"] == "unknown")
    ok = rail and cone and sub and unk == 0
    return ok, "rows %d; rail_all/half/unions >3 everywhere %s; rail_cone V0 1, V2/V5 >3 %s; dip_subset 1 in every row %s; unknown %d" % (
        len(rows), rail, cone, sub, unk)


def v_layout(root):
    d = json.load(open(os.path.join(root, "research/c4/layout/minsets_v2.json")))
    rs = {g: sorted(round(x["r_um"], 2) for x in l) for g, l in d["minimal_sets"].items()}
    ok = rs.get("word") == [2.95, 3.06, 3.29, 4.58] and rs.get("ok") == rs.get("word")
    return ok, "minimal one-event sets word %s ok %s (expect 4 sets, r 2.95 3.06 3.29 4.58)" % (rs.get("word"), rs.get("ok"))


def v_l2(root):
    base = os.path.join(root, "research/c4/l2/data")
    s = json.load(open(os.path.join(base, "summary_flow.json")))
    wl0 = s["base"]["wl_detailed_um"]
    pct = {v: round(100.0 * (s[v]["wl_detailed_um"] / wl0 - 1)) for v in ("v8", "s8", "v15", "rr")}
    lvs = {v: s[v]["lvs"].startswith("Circuits match") for v in s}
    drc0 = all(str(s[v]["route_violations"]) == "0" for v in s)
    ant0 = all(str(s[v]["antenna_pin_net"][0]) == "0" for v in s)
    gap = {}
    for v in ("base", "v8", "s8", "v15", "rr"):
        m = json.load(open(os.path.join(base, "metrics_%s.json" % v)))
        gap[v] = min(x["min_centre_um"] for x in m["pairwise_copy_distance"].values())
    rad = {}
    for v in ("base", "v8", "s8", "v15", "rr"):
        m = json.load(open(os.path.join(base, "minsets_%s.json" % v)))
        rad[v] = round(min(x["r_um"] for x in m["minimal_sets"]["word"]), 2)
    rall = True
    for v in ("base", "v8", "s8", "v15", "rr"):
        for l in open(os.path.join(base, "fam_%s.jsonl" % v)):
            r = json.loads(l)
            if r["family"] == "rail_all" and r["mode"] == "subset" and r["min"] != "1":
                rall = False
    ok = ((pct["v8"], pct["s8"], pct["rr"]) == (29, 31, 36) and pct["v15"] in (49, 50) and lvs == {"base": True, "v8": False, "s8": False, "v15": False, "rr": False}
          and drc0 and ant0 and [round(gap[v], 1) for v in ("base", "v8", "rr", "s8", "v15")] == [1.8, 9.2, 16.3, 17.9, 23.5]
          and rad == {"base": 2.95, "v8": 11.15, "s8": 17.91, "v15": 15.16, "rr": 15.3} and rall)
    return ok, "wire %% %s; LVS match %s; router DRC 0 %s antenna 0 %s; min copy distance %s; min set radius %s; rail_all SUB 1 everywhere %s" % (
        pct, lvs, drc0, ant0, {k: round(v, 2) for k, v in gap.items()}, rad, rall)


def v_ps4(root):
    d = json.load(open(os.path.join(root, "research/c4/ps4/data/sweep_v2.json")))
    rows = {}
    for c in d["cells"]:
        rows.setdefault(c["goal"], []).append(c["cost"])
    got = [",".join(v) for v in rows.values()]
    ok = got == ["3,1,0,0", "2,1,0,0", "3,1,0,0", "1,1,0,0"]
    return ok, "scope sweep rows (word, 0xF, 0x6A, boot_ok) %s (expect 3,1,0,0 / 2,1,0,0 / 3,1,0,0 / 1,1,0,0)" % got


VERIFY += [("M1b CSV identical to M1 CSV", v_m1b), ("B3 matrix claims (T=6)", v_b3), ("layout minimal sets 4", v_layout),
           ("L2 spacing, wire, LVS, radius, rail_all", v_l2), ("PS4 scope sweep 3,1,0,0 ...", v_ps4)]


def pytest_count(root, path):
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", path, "--co", "-q"], cwd=root, capture_output=True,
                           text=True, timeout=300)
    except Exception as e:  # noqa
        return None, str(e)
    m = re.search(r"(\d+) tests? collected", r.stdout + r.stderr)
    return (int(m.group(1)) if m else None), (r.stdout + r.stderr).strip().split("\n")[-1][:120]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.dirname(HERE))
    ap.add_argument("--numbers", default=None)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--pytest", action="store_true")
    ap.add_argument("--md", default=None, help="also write the mismatch table as markdown to this file")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    num = a.numbers or os.path.join(root, "docs/NUMBERS.md")
    try:
        blk = load_block(num)
    except (OSError, SystemExit) as e:
        print("cannot read %s: %s" % (num, e))
        return 2
    files, hits = scan(root, blk)
    stale = [h for h in hits if h["kind"] == "STALE"]
    hist = [h for h in hits if h["kind"] == "HISTORICAL"]
    if a.json:
        print(json.dumps(hits, indent=1))
    else:
        print("check_numbers: %d files scanned, %d STALE, %d HISTORICAL (rules: %d)" % (
            len(files), len(stale), len(hist), len(blk["rules"])))
        print("%-4s | %-10s | %-34s | %-5s | %-34s | %-30s | %s" % ("kind", "row", "file", "line", "found", "should be", "fix by"))
        for h in sorted(hits, key=lambda x: (x["kind"] != "STALE", x["file"], x["line"])):
            print("%-4s | %-10s | %-34s | %-5d | %-34s | %-30s | %s" % (
                h["kind"][:4], h["id"][:10], h["file"][-34:], h["line"], h["found"][:34], h["should"][:30], h["owner"]))
    if a.md:
        with open(a.md, "w") as f:
            f.write("| kind | row | file | line | found | should be | fix by |\n|---|---|---|---|---|---|---|\n")
            for h in sorted(hits, key=lambda x: (x["kind"] != "STALE", x["file"], x["line"])):
                f.write("| %s | %s | `%s` | %d | `%s` | %s | %s |\n" % (
                    h["kind"], h["id"], h["file"], h["line"], h["found"].replace("|", "/"),
                    h["should"].replace("|", "/"), h["owner"]))
    bad = False
    if a.verify:
        print("\n--verify (recomputed from stored data files):")
        for name, fn in VERIFY:
            try:
                ok, det = fn(root)
            except Exception as e:  # noqa
                ok, det = False, "error: %s" % e
            bad |= not ok
            print("  %-4s %-36s %s" % ("OK" if ok else "FAIL", name, det))
    if a.pytest:
        print("\n--pytest (collect-only):")
        for key, path in (("T.root.collected", "tests"), ("T.prod.collected", "product/tests")):
            n, det = pytest_count(root, path)
            exp = blk.get("current", {}).get(key)
            ok = n is not None and exp is not None and str(n) == str(exp)
            bad |= not ok
            print("  %-4s %-18s collected %s, NUMBERS.md says %s (%s)" % ("OK" if ok else "DIFF", path, n, exp, det))
    return 1 if (stale or bad) else 0


if __name__ == "__main__":
    sys.exit(main())
