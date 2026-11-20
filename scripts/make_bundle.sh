#!/usr/bin/env bash
# Allow-list bundle builder (replaces the earlier exclude-list dry run).
# DRY RUN by default: prints file count, size, 20 largest, .md count, exclusions hit, PII scan result.
# --build builds two zips (A review kit, B full tree) + SHA256SUMS into OUT_DIR (default /tmp/bundle_out).
# Never writes inside the project tree, never modifies it. Output dir must not be inside the tree.
# Usage: scripts/make_bundle.sh [--build] [--out DIR] [--only A|B]
# Env: BUNDLE_ROOT (tree root), BUNDLE_TS (UTC stamp override, YYYYmmddTHHMMSSZ), BUNDLE_ALLOWLIST.
set -eu
ROOT="${BUNDLE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
ALLOW="${BUNDLE_ALLOWLIST:-$ROOT/scripts/bundle_allowlist.txt}"
OUT=/tmp/bundle_out; BUILD=0; ONLY=""
while [ $# -gt 0 ]; do case "$1" in
  --build) BUILD=1;; --out) OUT="$2"; shift;; --only) ONLY="$2"; shift;;
  *) echo "unknown option $1" >&2; exit 2;; esac; shift; done
TS="${BUNDLE_TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
case "$(cd "$ROOT" && realpath -m "$OUT")/" in "$ROOT"/*) echo "refusing: OUT inside the tree" >&2; exit 2;; esac
exec python3 -I - "$ROOT" "$ALLOW" "$OUT" "$BUILD" "$TS" "$ONLY" <<'PY'
import sys, os, re, fnmatch, hashlib, zipfile, shutil, time
root, allow, out, build, ts, only = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1", sys.argv[5], sys.argv[6]
sec = None; S = {}
for ln in open(allow, encoding="utf-8"):
    ln = ln.rstrip("\n")
    if not ln.strip() or ln.lstrip().startswith("#"): continue
    m = re.fullmatch(r"\[(.+)\]", ln.strip())
    if m: sec = m.group(1); S[sec] = []; continue
    S[sec].append(ln.strip())
dirs, paths, globs, keeps, maxb = set(), [], [], [], 3 * 1024 * 1024
for e in S["EXCLUDE"]:
    k, v = e.split(":", 1)
    if k == "dir": dirs.add(v)
    elif k == "path": paths.append(v)
    elif k == "glob": globs.append(v)
    elif k == "keep": keeps.append(v.rstrip("/"))
    elif k == "maxbytes": maxb = int(v)
hits = {}
def kept(rel): return any(rel == k or rel.startswith(k + "/") for k in keeps)
def excluded(rel, size):
    parts = rel.split("/")
    if not kept(rel):
        for d in parts[:-1]:
            if d in dirs: return "dir:" + d
    for p in paths:
        if rel == p or rel.startswith(p + "/"): return "path:" + p
    for g in globs:
        if fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(parts[-1], g): return "glob:" + g
    if size > maxb: return "size>%d" % maxb
    return None
def walk(prefix):
    full = os.path.join(root, prefix)
    if os.path.isfile(full): yield prefix; return
    if not os.path.isdir(full): return
    for dp, dn, fn in os.walk(full):
        dn[:] = sorted(d for d in dn if d not in dirs or kept(os.path.relpath(os.path.join(dp, d), root)))  # prune, count at dir level below
        for f in sorted(fn): yield os.path.relpath(os.path.join(dp, f), root)
def note(reason, rel): hits.setdefault(reason, []).append(rel)
# count pruned dirs too (for the report)
for prefix in S["B-include"]:
    full = os.path.join(root, prefix)
    if os.path.isdir(full):
        for dp, dn, fn in os.walk(full):
            for d in dn:
                if d in dirs and not kept(os.path.relpath(os.path.join(dp, d), root)):
                    n = sum(len(f) for _, _, f in os.walk(os.path.join(dp, d)))
                    note("dir:" + d, os.path.relpath(os.path.join(dp, d), root) + "/ (%d files)" % n)
B = {}
for prefix in S["B-include"]:
    for rel in walk(prefix):
        fp = os.path.join(root, rel)
        if os.path.islink(fp) or not os.path.isfile(fp): continue
        why = excluded(rel, os.path.getsize(fp))
        if why: note(why, rel); continue
        B[rel] = rel
A, missing = {}, []
for ln in S["A"]:
    if "=>" in ln:
        src, dst = [x.strip() for x in ln.split("=>")]
        if dst in A or os.path.exists(os.path.join(root, dst)): continue
    else: src = dst = ln
    fp = os.path.join(root, src)
    if os.path.isfile(fp): A[dst] = src
    else: missing.append((src, dst))
missing = [s for s, d in missing if d not in A]
PIIre = [(l.split("|", 1)[0], re.compile(l.split("|", 1)[1], re.I)) for l in S["PII"]]
ok_lit = S["PII-ALLOW"]
def is_text(fp):
    with open(fp, "rb") as f: b = f.read(4096)
    return b"\0" not in b
def scan(files):
    found = []
    for dst, src in files.items():
        fp = os.path.join(root, src)
        if not is_text(fp): continue
        for i, line in enumerate(open(fp, encoding="utf-8", errors="replace"), 1):
            for name, rx in PIIre:
                for m in rx.finditer(line):
                    if any(a in line for a in ok_lit): continue
                    found.append((name, dst, i, m.group(0)[:60]))
    return found
def report(tag, files):
    sizes = sorted(((os.path.getsize(os.path.join(root, s)), d) for d, s in files.items()), reverse=True)
    tot = sum(s for s, _ in sizes); md = sum(1 for d in files if d.endswith(".md"))
    print("== BUNDLE %s: files=%d bytes=%d (%.1f MB) md_files=%d" % (tag, len(files), tot, tot / 1e6, md))
    print("   top 20 largest:")
    for s, d in sizes[:20]: print("   %10d  %s" % (s, d))
fail = 0
for tag, files in (("A", A), ("B", B)):
    if only and only != tag: continue
    report(tag, files)
    if tag == "A" and missing: print("   MISSING from A (not shipped): " + ", ".join(missing))
    f = scan(files)
    if f:
        fail = 1
        print("   PII/SECRET SCAN: %d HIT(S) -> BUILD FAILS" % len(f))
        for h in f[:40]: print("     %s %s:%d %r" % h)
    else: print("   PII/SECRET SCAN: clean (%d text files checked)" % len(files))
print("== exclusions hit in B (reason: count, examples):")
for r, l in sorted(hits.items(), key=lambda x: -len(x[1])):
    print("   %-28s %6d  %s" % (r, len(l), "; ".join(l[:2])))
if fail: print("FAILED: scan hits; nothing built"); sys.exit(3)
if not build: print("DRY RUN: nothing written. Use --build [--out DIR]."); sys.exit(0)
if os.path.realpath(out).startswith(os.path.realpath(root) + os.sep): sys.exit("OUT inside tree")
os.makedirs(out, exist_ok=True)
sums = []
for tag, name, files in (("A", "review_kit", A), ("B", "full_tree", B)):
    if only and only != tag: continue
    zp = os.path.join(out, "project_%s_%s.zip" % (name, ts))
    if os.path.exists(zp): os.remove(zp)
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for dst in sorted(files):
            zi = zipfile.ZipInfo(dst, date_time=(2026, 1, 1, 0, 0, 0))  # fixed mtime: content-deterministic
            zi.compress_type = zipfile.ZIP_DEFLATED
            mode = os.stat(os.path.join(root, files[dst])).st_mode & 0o777
            zi.external_attr = ((mode | 0o100000) & 0xFFFF) << 16
            with open(os.path.join(root, files[dst]), "rb") as f: z.writestr(zi, f.read())
    h = hashlib.sha256(open(zp, "rb").read()).hexdigest()
    sums.append("%s  %s" % (h, os.path.basename(zp)))
    print("built %s (%d bytes) sha256 %s" % (zp, os.path.getsize(zp), h))
sp = os.path.join(out, "SHA256SUMS" if not only else "SHA256SUMS.%s" % only)
open(sp, "w").write("\n".join(sums) + "\n"); print("wrote", sp)
PY
