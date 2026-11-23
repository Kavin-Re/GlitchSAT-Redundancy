#!/usr/bin/env python3
"""Build every boot-routine variant at -O0/-O1/-O2/-Os in the plain, vol and
barrier modes, bare-metal rv32imc, with clang + ld.lld.

Outputs (one stem per build, e.g. rom_double-O2-plain-sw):
  elf/<stem>.elf          linked image (code in ROM at 0x0)            kept
  elf/<stem>.lines.json   address -> [file, line] from the DWARF line
                          table (the fault search needs it to tell the
                          MAC unit apart from the decision code)        kept
  elf/manifest.json       commands, tool versions, sha256 of each ELF   kept
  build/<stem>.s          compiler assembly of the variant's own unit   not kept (.gitignore)
  build/<stem>.dis        llvm-objdump -d -M no-aliases of the ELF      not kept (.gitignore)

Usage: python3 scripts/build.py [--variants rom_naive,rom_double] [--opts O0,O2] [--hashes sw]
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
BUILD = os.path.join(ROOT, "build")
ELF_DIR = os.path.join(ROOT, "elf")

VARIANTS = ["rom_naive", "rom_double", "rom_triple", "rom_compl", "rom_ctres",
            "rom_cfi", "rom_delay", "rom_infective", "rom_hardened"]
HASHES = ["sw", "hw", "sha3"]
# MAC unit per build suffix: software HMAC-SHA-256, HMAC-SHA-256 engine model, secboot_hw SHA3-256 engine
MAC_SRC = {"sw": "hmac_sw.c", "hw": "hmac_hw.c", "sha3": "mac_sha3_hw.c"}
OPTS = ["O0", "O1", "O2", "Os"]
MODES = {"plain": [], "vol": ["-DFW_VOL"], "barrier": ["-DFW_BARRIER"]}
ARCH = ["--target=riscv32-unknown-elf", "-march=rv32imc", "-mabi=ilp32"]
CFLAGS = ["-ffreestanding", "-fno-builtin", "-nostdlib", "-g", "-fno-pic",
          "-ffile-prefix-map=%s=src" % SRC, "-fdebug-prefix-map=%s=src" % SRC,
          "-ffile-prefix-map=%s=." % ROOT, "-fdebug-prefix-map=%s=." % ROOT, "-I", SRC]


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.stderr.write(" ".join(cmd) + "\n" + r.stdout + r.stderr)
        raise SystemExit(1)
    return r.stdout


def tool(name):
    p = shutil.which(name) or shutil.which(name + "-18")
    if not p:
        raise SystemExit("missing tool: %s" % name)
    return p


def parse_lines(dump, lo, hi):
    """llvm-dwarfdump --debug-line text -> {addr: [file, line]} for every
    2-byte aligned address in [lo, hi)."""
    rows = []          # (addr, file, line, end)
    files = {}
    cur_idx = None
    for ln in dump.splitlines():
        if ln.startswith("debug_line["):
            files = {}
        m = re.match(r"file_names\[\s*(\d+)\]:", ln)
        if m:
            cur_idx = int(m.group(1))
            continue
        m = re.match(r'\s+name: "(.*)"', ln)
        if m and cur_idx is not None:
            files[cur_idx] = os.path.basename(m.group(1))
            cur_idx = None
            continue
        m = re.match(r"0x([0-9a-f]{16})\s+(\d+)\s+(\d+)\s+(\d+)\s+\d+\s+\d+\s+\d+\s*(.*)", ln)
        if m:
            rows.append((int(m.group(1), 16), files.get(int(m.group(4)), "?"), int(m.group(2)),
                         "end_sequence" in m.group(5)))
    out = {}
    seqs = []
    cur = []
    for r in rows:
        cur.append(r)
        if r[3]:
            seqs.append(cur)
            cur = []
    for seq in seqs:
        for i in range(len(seq) - 1):
            a0, f, line, end = seq[i]
            a1 = seq[i + 1][0]
            for a in range(a0 & ~1, a1, 2):
                if lo <= a < hi and (a not in out or line):
                    out[a] = [f, line]
    return out


def build_one(variant, opt, mode, hsh, clang, lld, objdump, dwarfdump):
    stem = "%s-%s-%s-%s" % (variant, opt, mode, hsh)
    tmp = os.path.join(BUILD, "obj", stem)
    os.makedirs(tmp, exist_ok=True)
    flags = ARCH + CFLAGS + ["-" + opt] + MODES[mode]
    objs = []
    cmds = []
    for src in ["crt0.S", MAC_SRC[hsh], variant + ".c"]:
        o = os.path.join(tmp, src.split(".")[0] + ".o")
        cmd = [clang] + flags + ["-c", os.path.join(SRC, src), "-o", o]
        run(cmd)
        cmds.append(cmd)
        objs.append(o)
    elf = os.path.join(ELF_DIR, stem + ".elf")
    cmd = [lld, "-T", os.path.join(SRC, "link.ld"), "--no-relax"] + objs + ["-o", elf]
    run(cmd)
    cmds.append(cmd)
    asm = run([clang] + flags + ["-S", "-g0", os.path.join(SRC, variant + ".c"), "-o", "-"])
    open(os.path.join(BUILD, stem + ".s"), "w").write(asm)
    dis = run([objdump, "-d", "--mattr=+m,+c", "-M", "no-aliases", "--no-show-raw-insn", elf])
    open(os.path.join(BUILD, stem + ".dis"), "w").write(dis.replace(ELF_DIR + "/", ""))
    hdr = run([objdump, "-h", elf])
    m = re.search(r"\.text\s+([0-9a-f]+)\s+([0-9a-f]+)", hdr)
    size, lo = int(m.group(1), 16), int(m.group(2), 16)
    lines = parse_lines(run([dwarfdump, "--debug-line", elf]), lo, lo + size)
    json.dump(lines, open(os.path.join(ELF_DIR, stem + ".lines.json"), "w"), sort_keys=True)
    sha = hashlib.sha256(open(elf, "rb").read()).hexdigest()
    rel = lambda c: [x.replace(ROOT + "=", "<firmware dir>=").replace(ROOT + "/", "") for x in c]
    return stem, {"variant": variant, "opt": opt, "mode": mode, "hash": hsh, "elf": "elf/%s.elf" % stem,
                  "sha256": sha, "text_bytes": size, "commands": [rel(c) for c in cmds]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default=",".join(VARIANTS))
    ap.add_argument("--opts", default=",".join(OPTS))
    ap.add_argument("--modes", default=",".join(MODES))
    ap.add_argument("--hashes", default=",".join(HASHES))
    a = ap.parse_args()
    clang, lld, objdump, dwarfdump = tool("clang"), tool("ld.lld"), tool("llvm-objdump"), tool("llvm-dwarfdump")
    os.makedirs(BUILD, exist_ok=True)
    os.makedirs(ELF_DIR, exist_ok=True)
    mf_path = os.path.join(ELF_DIR, "manifest.json")
    mf = json.load(open(mf_path)) if os.path.exists(mf_path) else {"builds": {}}
    mf["clang"] = run([clang, "--version"]).splitlines()[0]
    mf["lld"] = run([lld, "--version"]).strip()
    for v in a.variants.split(","):
        for o in a.opts.split(","):
            for md in a.modes.split(","):
                for h in a.hashes.split(","):
                    stem, info = build_one(v, o, md, h, clang, lld, objdump, dwarfdump)
                    mf["builds"][stem] = info
                    print("built", stem, info["text_bytes"], "bytes .text")
    shutil.rmtree(os.path.join(BUILD, "obj"), ignore_errors=True)
    json.dump(mf, open(mf_path, "w"), indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
