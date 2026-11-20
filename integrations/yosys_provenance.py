"""Yosys-version provenance reader.

Why: in this project the V2 verdict depends on the Yosys build (docs/ENGINE_STATUS.md: apt 0.33 gives an 85-gate
netlist with a 2-fault attack, conda 0.38+92 an 83-gate netlist without). Every verdict should carry the build that
made the netlist. Sources read here, in order of trust:
  1. the `creator` field of a Yosys `write_json` netlist (it is written by Yosys itself),
  2. a version banner in a text log ("Yosys 0.38+92 (git sha1 84116c9a3, ...)"),
  3. (optional, off by default) running `yosys -V` with a timeout.
Pure standard library.
"""
import collections
import hashlib
import json
import re
import subprocess

_BANNER = re.compile(r"Yosys\s+(?P<ver>\d+\.\d+(?:\.\d+)?)(?:\+(?P<plus>\d+))?(?:\s*\(git sha1\s+(?P<sha>[0-9a-f]{6,40})(?:,\s*(?P<build>[^)]*(?:\([^)]*\)[^)]*)*))?\))?")


def parse_banner(text):
    """Parse a Yosys banner/creator string. Returns dict or None. Never invents fields that are absent."""
    m = _BANNER.search(text or "")
    if not m:
        return None
    ver, plus, sha, build = m.group("ver"), m.group("plus"), m.group("sha"), m.group("build")
    major_minor = ".".join(ver.split(".")[:2])
    out = {"version": ver, "plus_commits": int(plus) if plus else 0, "git_sha1": sha,
           "version_string": f"{ver}+{plus}" if plus else ver, "major_minor": major_minor}
    if build:
        cc = build.split()[0]
        out["build_compiler_hint"] = cc
        out["channel_hint"] = "conda-forge/litex-hub style build" if "conda" in build else "distro/other build"
    else:
        out["channel_hint"] = "unknown (banner has no compiler field)"
    return out


def _netlist_stats(doc):
    stats = {}
    for mname, m in (doc.get("modules") or {}).items():
        hist = collections.Counter(c.get("type", "?") for c in (m.get("cells") or {}).values())
        flops = sum(n for t, n in hist.items() if "DFF" in t or "dff" in t)
        stats[mname] = {"cells": sum(hist.values()), "flops": flops, "combinational": sum(hist.values()) - flops,
                        "cell_types": dict(sorted(hist.items()))}
    return stats


def read_netlist(path):
    """Provenance record for a Yosys JSON netlist: yosys version (from `creator`), sha256, per-module cell counts."""
    raw = open(path, "rb").read()
    doc = json.loads(raw)
    creator = doc.get("creator")
    rec = {"file": path, "sha256": hashlib.sha256(raw).hexdigest(), "creator_field": creator,
           "yosys": parse_banner(creator) if creator else None,
           "source": "netlist creator field" if creator else "no creator field", "modules": _netlist_stats(doc)}
    return rec


def read_log(path):
    """First Yosys banner found in a text log, or None."""
    for line in open(path, errors="replace"):
        b = parse_banner(line)
        if b:
            b["source"] = f"log {path}"
            return b
    return None


def run_yosys_version(binary="yosys", timeout=20):
    """Ask a Yosys binary for its version (`-V`). Opt-in; returns parsed banner or None."""
    try:
        r = subprocess.run([binary, "-V"], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    b = parse_banner(r.stdout + r.stderr)
    if b:
        b["source"] = f"`{binary} -V`"
    return b


def diff(a, b):
    """Compare two read_netlist records. Returns dict(same_yosys, same_netlist_bytes, cell_count_a/b per module, notes)."""
    ya, yb = (a.get("yosys") or {}), (b.get("yosys") or {})
    same_yosys = bool(ya) and bool(yb) and (ya.get("version_string"), ya.get("git_sha1")) == (yb.get("version_string"), yb.get("git_sha1"))
    notes = []
    if not ya or not yb:
        notes.append("at least one netlist has no readable Yosys version: provenance incomplete")
    elif not same_yosys:
        notes.append(f"different Yosys builds ({ya['version_string']} vs {yb['version_string']}): a verdict on one netlist "
                     "must not be reused for the other without re-running the solver")
    counts = {}
    for m in sorted(set(a["modules"]) | set(b["modules"])):
        counts[m] = (a["modules"].get(m, {}).get("cells"), b["modules"].get(m, {}).get("cells"))
    return {"same_yosys": same_yosys, "same_netlist_bytes": a["sha256"] == b["sha256"], "cells_a_vs_b": counts, "notes": notes}


def to_campaign_design_block(rec):
    """Block for fault-campaign `design` (keys netlist_sha256, yosys)."""
    return {"netlist_sha256": rec["sha256"], "yosys": rec["yosys"] or {"version_string": "UNKNOWN"}}


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        r = read_netlist(p)
        print(p, (r["yosys"] or {}).get("version_string"), r["sha256"][:12], {m: s["cells"] for m, s in r["modules"].items()})
