#!/usr/bin/env python3
"""Licence: UNDECIDED. Working title TBD.

Export the E2 synthesis-variance data for the "same blueprint, many builders" wall.

Reads (read-only):
  research/c2/e2_variance/raw/matrix.csv   864 rows; the 288 V2 rows are used
  research/c6/p01/sweep_rows.csv           v2 / v2e rows on the 8 project flows
Writes:
  docs/wow/e2_wall.json                    the data file
  docs/wow/wall.html                       only the embedded copy of the data, between the
                                           <script type="application/json" id="wall-data"> tags
                                           (skipped if the page does not exist; --no-embed to skip)

Every number is MEASURED by the E2 / P01 runs (bounded: goal boot_word == 0x96, 6 cycles,
at most 3 modelled single-cycle bit flips, one toy design). This script only counts rows.
The output is deterministic (no timestamp), so docs/wow/check_wall.py can re-derive it.

Usage: python3 scripts/export_e2_wall.py [--root DIR] [--no-embed]
"""
import argparse
import csv
import hashlib
import json
import os
import re
import sys

MATRIX = "research/c2/e2_variance/raw/matrix.csv"
SWEEP = "research/c6/p01/sweep_rows.csv"
OUT_JSON = "docs/wow/e2_wall.json"
OUT_HTML = "docs/wow/wall.html"

# display order of the option values (also the tile order inside a group)
BUILDS = ["apt0.33", "conda-formal0.38", "conda-eda0.38"]
KEEPS = ["keep_on", "keep_off"]
ABCS = ["default", "noMUX", "AND_OR", "fast", "dff", "noabc"]
MERGES = ["nomerge", "opt_merge"]
ORDERS = ["abc_then_flatten", "flatten_then_abc"]
FLOWS = ["plain", "opt"]

LABELS = {
    "build": {"apt0.33": "Yosys 0.33 (apt)",
              "conda-formal0.38": "Yosys 0.38+92 (conda env formal)",
              "conda-eda0.38": "Yosys 0.38+92 (conda env eda, same git sha as formal)"},
    "flow": {"plain": "plain (proc; techmap)", "opt": "opt (synth -top; dffunmap)"},
    "order": {"abc_then_flatten": "ABC per module, then flatten",
              "flatten_then_abc": "flatten first, then ABC"},
    "abc": {"default": "abc -g AND,OR,XOR,MUX", "noMUX": "abc -g AND,OR,XOR",
            "AND_OR": "abc -g AND,OR", "fast": "abc -fast", "dff": "abc -dff",
            "noabc": "no abc"},
    "merge": {"nomerge": "no opt_merge", "opt_merge": "opt_merge after flatten"},
    "keep": {"keep_on": "(* keep *) attributes as written",
             "keep_off": "(* keep *) attributes stripped"},
}
V2E_FLOWS = ["plain", "plain_opt_merge", "flatten_before_abc", "abc_fast", "abc_no_mux",
             "opt_flow", "plain_keep_off", "opt_flow_keep_off"]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hist(values):
    out = {"1": 0, "2": 0, "3": 0}
    for v in values:
        out[str(v)] += 1
    return out


def cause_class(merges, order):
    """Which option family could have merged the three compare copies.
    'merge' = opt_merge switched on (for a netlist: in at least one setting that builds it);
    'flat'  = no opt_merge, but flattened before ABC; 'other' = neither."""
    if "opt_merge" in merges:
        return "merge"
    return "flat" if order == "flatten_then_abc" else "other"


def build(root):
    mpath = os.path.join(root, MATRIX)
    with open(mpath, newline="", encoding="utf-8") as f:
        allrows = list(csv.DictReader(f))
    tiles = []
    for i, r in enumerate(allrows):
        if r["design"] != "v2":
            continue
        line = i + 2  # 1-based line in matrix.csv; line 1 is the header
        solved = r["status"] == "SOLVED"
        if not solved and r["status"] != "ENGINE_UNSUPPORTED":
            raise SystemExit("unexpected status %r at line %d" % (r["status"], line))
        tiles.append({
            "line": line,
            "build": r["build"], "flow": r["flow"], "order": r["order"],
            "abc": r["abc"], "merge": r["merge"], "keep": r["keep"],
            "status": r["status"],
            "min": int(r["min_flips"]) if solved else None,
            "gates": int(r["gates"]) if solved else None,
            "flops": int(r["flops"]) if solved else None,
            "match_nets": int(r["distinct_match_nets"]) if solved else None,
            "sha": r["sha256_canon"][:16],
            "sha_raw": r["sha256_raw"][:16],
            "sha_full": r["sha256_canon"],
            "note": r["note"],
        })
    if len(tiles) != 288:
        raise SystemExit("expected 288 V2 rows, found %d" % len(tiles))

    def key(t):
        return (MERGES.index(t["merge"]), ORDERS.index(t["order"]), FLOWS.index(t["flow"]),
                BUILDS.index(t["build"]), KEEPS.index(t["keep"]), ABCS.index(t["abc"]))
    tiles.sort(key=key)

    solved = [t for t in tiles if t["status"] == "SOLVED"]
    # distinct netlists = distinct canonical SHA-256 (netlist with the 'creator' field dropped)
    netlists, index = [], {}
    for t in sorted(solved, key=lambda t: t["line"]):
        k = t["sha_full"]
        if k not in index:
            index[k] = len(netlists)
            netlists.append({"id": len(netlists) + 1, "sha": t["sha"], "min": t["min"],
                             "gates": t["gates"], "flops": t["flops"], "flow": t["flow"],
                             "order": t["order"], "lines": [], "merges": [], "first": t})
        n = netlists[index[k]]
        for f in ("min", "gates", "flops", "flow", "order"):
            if n[f] != t[f]:
                raise SystemExit("netlist %s: field %s differs between settings" % (n["sha"], f))
        n["lines"].append(t["line"])
        if t["merge"] not in n["merges"]:
            n["merges"].append(t["merge"])
    if len({n["sha"] for n in netlists}) != len(netlists):
        raise SystemExit("16-hex prefixes of the canonical sha are not unique")
    for t in tiles:
        t["netlist"] = index[t["sha_full"]] + 1 if t["status"] == "SOLVED" else None
        t["cls"] = cause_class([t["merge"]], t["order"])
        t["same"] = len(netlists[index[t["sha_full"]]]["lines"]) if t["status"] == "SOLVED" else None
    for n in netlists:
        n["cls"] = cause_class(n["merges"], n["order"])
        n["merges"].sort(key=MERGES.index)
        # the wall shows a netlist at the place of the first setting (lowest csv line) that built it
        n["rep_line"] = n.pop("first")["line"]
        n["n_settings"] = len(n["lines"])

    def by_cls(items):
        return {c: hist(x["min"] for x in items if x["cls"] == c) for c in ("merge", "flat", "other")}

    counts = {
        "v2_rows": len(tiles),
        "settings": {"n": len(solved), "min": hist(t["min"] for t in solved),
                     "unsupported": len(tiles) - len(solved), "by_cause": by_cls(solved)},
        "netlists": {"n": len(netlists), "min": hist(n["min"] for n in netlists),
                     "by_cause": by_cls(netlists),
                     "built_with_and_without_merge": sum(1 for n in netlists if len(n["merges"]) > 1)},
    }
    for view in ("settings", "netlists"):
        c = counts[view]
        c["pct3"] = round(100.0 * c["min"]["3"] / c["n"])
        c["one_flip_merge_or_flat"] = c["by_cause"]["merge"]["1"] + c["by_cause"]["flat"]["1"]
    for t in tiles:
        del t["sha_full"]

    # ---- second, separate experiment: v2 against v2e on the 8 project flows (P01) ----
    spath = os.path.join(root, SWEEP)
    v2e = None
    if os.path.exists(spath):
        with open(spath, newline="", encoding="utf-8") as f:
            srows = list(csv.DictReader(f))
        blocks = []
        yosys_seen = []
        for r in srows:
            if r["yosys"] not in yosys_seen:
                yosys_seen.append(r["yosys"])
        for y in yosys_seen:
            for design in ("v2", "v2e"):
                cells = []
                for i, r in enumerate(srows):
                    if r["yosys"] == y and r["design"] == design:
                        m = r["min_flips"]
                        cells.append({"line": i + 2, "variant": r["variant"],
                                      "armed": r["armed_const"], "copies": int(r["groups_touched"]),
                                      "gates": int(r["gates"]), "flops": int(r["flops"]),
                                      "min": int(m) if m.isdigit() else None, "min_raw": m,
                                      "sha": r["netlist_sha256"][:16], "witness": r["witness"]})
                if [c["variant"] for c in cells] != V2E_FLOWS:
                    raise SystemExit("sweep_rows.csv: %s %s does not list the 8 project flows" % (y, design))
                blocks.append({"yosys": y.strip(), "design": design, "armed": cells[0]["armed"],
                               "copies": cells[0]["copies"], "cells": cells,
                               "n3": sum(1 for c in cells if c["min"] == 3),
                               "row": " ".join(c["min_raw"] for c in cells)})
        v2e = {"source": SWEEP, "source_sha256": sha256_file(spath), "flows": V2E_FLOWS,
               "blocks": blocks, "constants_tried": len({r["armed_const"] for r in srows}),
               "constants_possible": 253}

    return {
        "meta": {
            "label": "",
            "licence": "UNDECIDED",
            "generated_by": "python3 scripts/export_e2_wall.py",
            "evidence": "MEASURED (counts of rows in the source files; the minimum-flip values were "
                        "measured by the E2 and P01 solver runs)",
            "bound": "goal boot_word == 0x96, attacker input held constant and != key, 6 cycles, "
                     "at most 3 modelled single-cycle bit flips; one toy design (rtl/v2.v)",
            "source": MATRIX,
            "source_sha256": sha256_file(mpath),
            "source_rows": len(allrows),
            "distinct_rule": "distinct netlist = distinct sha256_canon (SHA-256 of the netlist with "
                             "the 'creator' field dropped); sha fields here are the first 16 hex digits",
        },
        "labels": LABELS,
        "order": {"merge": MERGES, "order": ORDERS, "flow": FLOWS, "build": BUILDS,
                  "keep": KEEPS, "abc": ABCS},
        "counts": counts,
        "tiles": tiles,
        "netlists": netlists,
        "v2e": v2e,
    }


def dumps(data):
    return json.dumps(data, indent=None, separators=(",", ":"), sort_keys=True, ensure_ascii=True)


EMBED_RE = re.compile(r'(<script type="application/json" id="wall-data">)(.*?)(</script>)', re.S)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--no-embed", action="store_true")
    a = ap.parse_args()
    data = build(a.root)
    text = dumps(data)
    if "</" in text:
        raise SystemExit("data contains '</', unsafe to embed")
    out = os.path.join(a.root, OUT_JSON)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    c = data["counts"]
    print("wrote %s (%d bytes)" % (OUT_JSON, len(text) + 1))
    print("settings: %d solved, min 1/2/3 = %s, unsupported %d" % (
        c["settings"]["n"], "/".join(str(c["settings"]["min"][k]) for k in "123"), c["settings"]["unsupported"]))
    print("distinct netlists: %d, min 1/2/3 = %s" % (
        c["netlists"]["n"], "/".join(str(c["netlists"]["min"][k]) for k in "123")))
    print("one-flip settings with opt_merge: %d of %d" % (
        c["settings"]["by_cause"]["merge"]["1"], c["settings"]["min"]["1"]))
    page = os.path.join(a.root, OUT_HTML)
    if not a.no_embed and os.path.exists(page):
        html = open(page, encoding="utf-8").read()
        if not EMBED_RE.search(html):
            raise SystemExit("%s has no wall-data script tag" % OUT_HTML)
        new = EMBED_RE.sub(lambda m: m.group(1) + "\n" + text + "\n" + m.group(3), html, count=1)
        if new != html:
            with open(page, "w", encoding="utf-8") as f:
                f.write(new)
            print("updated the embedded data in %s" % OUT_HTML)
        else:
            print("embedded data in %s already current" % OUT_HTML)
    return 0


if __name__ == "__main__":
    sys.exit(main())
