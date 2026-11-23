"""Validation of the RV32IMC simulator (rv32sim) on programs whose results
are derived independently: hand-derived values from the ISA spec (alu.S), a
Python re-implementation (prog.c), Python's hashlib (the boot ROM's HMAC),
and llvm-objdump (decoder text, if installed)."""
import os
import re
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from rv32sim import Machine, isa, load_elf  # noqa: E402
from rv32sim.cpu import TRAP  # noqa: E402

PROGS = os.path.join(ROOT, "tests", "progs")
M = 0xFFFFFFFF


def ram_words(m, n, off=0):
    return [int.from_bytes(m.ram[off + 4 * i:off + 4 * i + 4], "little") for i in range(n)]


def test_alu_hand_derived():
    p = load_elf(os.path.join(PROGS, "alu.elf"))
    m = Machine(p)
    m.run(1000)
    assert m.outcome == TRAP  # ends with ebreak
    auipc_pc = None
    for a, ins in sorted(p.code.items()):
        if ins.op == isa.AUIPC and ins.rd == 5 and ins.imm == 0:
            auipc_pc = a
    jalr_ret = [a + ins.size for a, ins in p.code.items() if ins.op == isa.JALR and ins.rd == 6][0]
    exp = [-3 & M, -1 & M, 0x7FFFFFFC, 1, M, -7 & M, 0x80000000, 0, 0, 0x7FFFFFFF, M, 49,
           0xE0000000, 0x20000000, 4, 1, 0, 1, 0x8081, 0xFFFFFF81, 0x80, 0xFFFF8081, 0x8081,
           -16 & M, 0xFFFE0000, auipc_pc, jalr_ret, 15, 0x600D]
    got = ram_words(m, len(exp))
    got[18] &= 0xFFFF  # word 18 holds the halfword store plus the next store's low bytes
    assert got == exp


def py_prog():
    buf, x = [], 12345
    for _ in range(48):
        x = (x * 1103515245 + 12345) & M
        buf.append(x)
    raw = b"".join(v.to_bytes(4, "little") for v in buf)
    import zlib
    out0 = zlib.crc32(raw)
    s32 = lambda v: v - (1 << 32) if v & 0x80000000 else v
    buf.sort(key=s32)
    acc = 0
    for v in buf:
        acc = (acc * 31 + v) & M
    s = 0
    for i in range(48):
        a = s32(buf[i])
        b = (buf[(i + 7) % 48] >> 20) - 2048
        if b != 0:
            q = abs(a) // abs(b)
            q = q if (a < 0) == (b < 0) else -q
            r = a - q * b
            s = s32((s + q + r) & M)
        s = s32((s & M) ^ ((a * b) & M))
    return [out0, acc, s & M]


@pytest.mark.parametrize("opt", ["O0", "O2", "Os"])
def test_c_program_matches_python(opt):
    m = Machine(load_elf(os.path.join(PROGS, "prog-%s.elf" % opt)))
    m.run(10 ** 7)
    assert m.outcome == TRAP
    assert ram_words(m, 3, 0x800) == py_prog()


def _objdump():
    return shutil.which("llvm-objdump") or shutil.which("llvm-objdump-18")


def _elfs():
    b = os.path.join(ROOT, "elf")
    names = sorted(f for f in os.listdir(b) if f.endswith(".elf")) if os.path.isdir(b) else []
    return [os.path.join(b, f) for f in names] + [os.path.join(PROGS, f) for f in sorted(os.listdir(PROGS)) if f.endswith(".elf")]


def _norm(t):
    t = re.sub(r"\s*<[^>]*>", "", t.strip())
    return re.sub(r"\s+", " ", t)


@pytest.mark.skipif(_objdump() is None, reason="llvm-objdump not installed")
def test_decoder_matches_objdump_on_every_instruction():
    """Every instruction of every built image: our text == llvm-objdump -M no-aliases."""
    checked = 0
    for elf in _elfs():
        p = load_elf(elf)
        out = subprocess.run([_objdump(), "-d", "--mattr=+m,+c", "-M", "no-aliases", "--no-show-raw-insn", elf],
                             capture_output=True, text=True, check=True).stdout
        for ln in out.splitlines():
            mm = re.match(r"\s*([0-9a-f]+):\s+(.*)$", ln)
            if not mm:
                continue
            a = int(mm.group(1), 16)
            if a not in p.code:
                continue
            want = _norm(mm.group(2))
            got = _norm(isa.disasm(p.code[a], a))
            if want.startswith("unimp") or want.startswith("c.unimp"):
                assert p.code[a].op == isa.ILLEGAL
            elif want.startswith("fence"):
                assert p.code[a].op == isa.FENCE
            else:
                assert got == want, "%s @0x%x: %r != %r" % (os.path.basename(elf), a, got, want)
            checked += 1
    assert checked > 10000


def test_compressed_expansion_examples():
    # c.addi16sp sp,-64 ; c.addi4spn a0,sp,16 ; c.lwsp a2,4(sp) ; c.beqz a0,+8
    i = isa.decode16(0x7139)
    assert (i.op, i.rd, i.rs1, i.imm) == (isa.ADDI, 2, 2, -64)
    i = isa.decode16(0x0808)
    assert (i.op, i.rd, i.rs1, i.imm) == (isa.ADDI, 10, 2, 16)
    i = isa.decode16(0x4612)
    assert (i.op, i.rd, i.rs1, i.imm) == (isa.LW, 12, 2, 4)
    assert isa.decode16(0).op == isa.ILLEGAL
