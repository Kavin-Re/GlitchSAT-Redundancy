"""RV32IMC decoder and disassembler (pure Python, no dependencies).

decode(raw16_or_32_bytes) -> Insn. Compressed (16-bit) instructions are
expanded to their base-ISA meaning; the C mnemonic is kept for
disassembly so the text can be compared with `llvm-objdump -M no-aliases`.

Only the unprivileged RV32I base, the M extension and the C extension are
decoded. CSR instructions, floating point and anything else decode as
ILLEGAL (the simulator traps on them), which matches a core that has no
CSR access in this ROM routine. `unimp` (csrrw x0, cycle, x0 and c.unimp)
is therefore ILLEGAL, as on hardware.
"""

# ---- operation codes (small ints for a fast if-chain in cpu.py) ----
(LUI, AUIPC, JAL, JALR, BEQ, BNE, BLT, BGE, BLTU, BGEU,
 LB, LH, LW, LBU, LHU, SB, SH, SW,
 ADDI, SLTI, SLTIU, XORI, ORI, ANDI, SLLI, SRLI, SRAI,
 ADD, SUB, SLL, SLT, SLTU, XOR, SRL, SRA, OR, AND,
 MUL, MULH, MULHSU, MULHU, DIV, DIVU, REM, REMU,
 FENCE, ECALL, EBREAK, ILLEGAL) = range(49)

NAMES = ["lui", "auipc", "jal", "jalr", "beq", "bne", "blt", "bge", "bltu", "bgeu",
         "lb", "lh", "lw", "lbu", "lhu", "sb", "sh", "sw",
         "addi", "slti", "sltiu", "xori", "ori", "andi", "slli", "srli", "srai",
         "add", "sub", "sll", "slt", "sltu", "xor", "srl", "sra", "or", "and",
         "mul", "mulh", "mulhsu", "mulhu", "div", "divu", "rem", "remu",
         "fence", "ecall", "ebreak", "unimp"]

BRANCHES = (BEQ, BNE, BLT, BGE, BLTU, BGEU)
LOADS = (LB, LH, LW, LBU, LHU)
STORES = (SB, SH, SW)

ABI = ["zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2", "s0", "s1",
       "a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7",
       "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9", "s10", "s11",
       "t3", "t4", "t5", "t6"]


def sext(v, bits):
    m = 1 << (bits - 1)
    v &= (1 << bits) - 1
    return (v ^ m) - m


class Insn:
    __slots__ = ("op", "rd", "rs1", "rs2", "imm", "size", "raw", "cname", "cfields")

    def __init__(self, op, rd=0, rs1=0, rs2=0, imm=0, size=4, raw=0, cname=None, cfields=None):
        self.op = op
        self.rd = rd
        self.rs1 = rs1
        self.rs2 = rs2
        self.imm = imm
        self.size = size
        self.raw = raw
        self.cname = cname      # compressed mnemonic, e.g. "c.addi"
        self.cfields = cfields  # operand tuple for the compressed text form

    def writes_rd(self):
        """Register written by this instruction (0 if none)."""
        if self.op in BRANCHES or self.op in STORES or self.op in (FENCE, ECALL, EBREAK, ILLEGAL):
            return 0
        return self.rd

    def __repr__(self):
        return "Insn(%s)" % disasm(self, 0)


# ------------------------------------------------------------------ 32-bit
def decode32(w):
    opc = w & 0x7F
    rd = (w >> 7) & 31
    f3 = (w >> 12) & 7
    rs1 = (w >> 15) & 31
    rs2 = (w >> 20) & 31
    f7 = w >> 25
    if (w & 3) != 3:
        return Insn(ILLEGAL, raw=w)
    if opc == 0x37:
        return Insn(LUI, rd, imm=w & 0xFFFFF000, raw=w)
    if opc == 0x17:
        return Insn(AUIPC, rd, imm=w & 0xFFFFF000, raw=w)
    if opc == 0x6F:
        imm = (((w >> 31) & 1) << 20) | (((w >> 12) & 0xFF) << 12) | (((w >> 20) & 1) << 11) | (((w >> 21) & 0x3FF) << 1)
        return Insn(JAL, rd, imm=sext(imm, 21), raw=w)
    if opc == 0x67:
        if f3 != 0:
            return Insn(ILLEGAL, raw=w)
        return Insn(JALR, rd, rs1, imm=sext(w >> 20, 12), raw=w)
    if opc == 0x63:
        imm = (((w >> 31) & 1) << 12) | (((w >> 7) & 1) << 11) | (((w >> 25) & 0x3F) << 5) | (((w >> 8) & 0xF) << 1)
        op = {0: BEQ, 1: BNE, 4: BLT, 5: BGE, 6: BLTU, 7: BGEU}.get(f3)
        if op is None:
            return Insn(ILLEGAL, raw=w)
        return Insn(op, 0, rs1, rs2, sext(imm, 13), raw=w)
    if opc == 0x03:
        op = {0: LB, 1: LH, 2: LW, 4: LBU, 5: LHU}.get(f3)
        if op is None:
            return Insn(ILLEGAL, raw=w)
        return Insn(op, rd, rs1, imm=sext(w >> 20, 12), raw=w)
    if opc == 0x23:
        op = {0: SB, 1: SH, 2: SW}.get(f3)
        if op is None:
            return Insn(ILLEGAL, raw=w)
        imm = ((w >> 25) << 5) | ((w >> 7) & 31)
        return Insn(op, 0, rs1, rs2, sext(imm, 12), raw=w)
    if opc == 0x13:
        imm = sext(w >> 20, 12)
        if f3 == 1:
            if f7 != 0:
                return Insn(ILLEGAL, raw=w)
            return Insn(SLLI, rd, rs1, imm=rs2, raw=w)
        if f3 == 5:
            if f7 == 0:
                return Insn(SRLI, rd, rs1, imm=rs2, raw=w)
            if f7 == 0x20:
                return Insn(SRAI, rd, rs1, imm=rs2, raw=w)
            return Insn(ILLEGAL, raw=w)
        op = {0: ADDI, 2: SLTI, 3: SLTIU, 4: XORI, 6: ORI, 7: ANDI}[f3]
        return Insn(op, rd, rs1, imm=imm, raw=w)
    if opc == 0x33:
        if f7 == 0:
            op = [ADD, SLL, SLT, SLTU, XOR, SRL, OR, AND][f3]
        elif f7 == 0x20 and f3 in (0, 5):
            op = SUB if f3 == 0 else SRA
        elif f7 == 1:
            op = [MUL, MULH, MULHSU, MULHU, DIV, DIVU, REM, REMU][f3]
        else:
            return Insn(ILLEGAL, raw=w)
        return Insn(op, rd, rs1, rs2, raw=w)
    if opc == 0x0F and f3 == 0:
        return Insn(FENCE, imm=(w >> 20) & 0xFF, raw=w)
    if opc == 0x73:
        if w == 0x00000073:
            return Insn(ECALL, raw=w)
        if w == 0x00100073:
            return Insn(EBREAK, raw=w)
    return Insn(ILLEGAL, raw=w)


# ------------------------------------------------------------------ 16-bit
def _r3(x):
    return 8 + (x & 7)


def decode16(h):
    q = h & 3
    f3 = h >> 13
    if h == 0:
        return Insn(ILLEGAL, size=2, raw=h, cname="c.unimp", cfields=())
    if q == 0:
        rdp = _r3(h >> 2)
        rs1p = _r3(h >> 7)
        if f3 == 0:  # c.addi4spn
            imm = (((h >> 6) & 1) << 2) | (((h >> 5) & 1) << 3) | (((h >> 11) & 3) << 4) | (((h >> 7) & 0xF) << 6)
            if imm == 0:
                return Insn(ILLEGAL, size=2, raw=h)
            return Insn(ADDI, rdp, 2, imm=imm, size=2, raw=h, cname="c.addi4spn", cfields=("r", rdp, "r", 2, "i", imm))
        if f3 in (2, 6):
            imm = (((h >> 6) & 1) << 2) | (((h >> 10) & 7) << 3) | (((h >> 5) & 1) << 6)
            if f3 == 2:
                return Insn(LW, rdp, rs1p, imm=imm, size=2, raw=h, cname="c.lw", cfields=("r", rdp, "m", imm, rs1p))
            return Insn(SW, 0, rs1p, rdp, imm=imm, size=2, raw=h, cname="c.sw", cfields=("r", rdp, "m", imm, rs1p))
        return Insn(ILLEGAL, size=2, raw=h)
    if q == 1:
        rd = (h >> 7) & 31
        imm6 = sext((((h >> 12) & 1) << 5) | ((h >> 2) & 31), 6)
        if f3 == 0:
            if rd == 0:
                return Insn(ADDI, 0, 0, imm=imm6, size=2, raw=h, cname="c.nop", cfields=() if imm6 == 0 else ("i", imm6))
            return Insn(ADDI, rd, rd, imm=imm6, size=2, raw=h, cname="c.addi", cfields=("r", rd, "i", imm6))
        if f3 in (1, 5):  # c.jal / c.j
            b = h
            imm = ((((b >> 12) & 1) << 11) | (((b >> 11) & 1) << 4) | (((b >> 9) & 3) << 8) | (((b >> 8) & 1) << 10)
                   | (((b >> 7) & 1) << 6) | (((b >> 6) & 1) << 7) | (((b >> 3) & 7) << 1) | (((b >> 2) & 1) << 5))
            imm = sext(imm, 12)
            if f3 == 1:
                return Insn(JAL, 1, imm=imm, size=2, raw=h, cname="c.jal", cfields=("t", imm))
            return Insn(JAL, 0, imm=imm, size=2, raw=h, cname="c.j", cfields=("t", imm))
        if f3 == 2:
            return Insn(ADDI, rd, 0, imm=imm6, size=2, raw=h, cname="c.li", cfields=("r", rd, "i", imm6))
        if f3 == 3:
            if rd == 2:
                b = h
                imm = ((((b >> 12) & 1) << 9) | (((b >> 6) & 1) << 4) | (((b >> 5) & 1) << 6)
                       | (((b >> 3) & 3) << 7) | (((b >> 2) & 1) << 5))
                imm = sext(imm, 10)
                if imm == 0:
                    return Insn(ILLEGAL, size=2, raw=h)
                return Insn(ADDI, 2, 2, imm=imm, size=2, raw=h, cname="c.addi16sp", cfields=("r", 2, "i", imm))
            if imm6 == 0 or rd == 0:
                return Insn(ILLEGAL, size=2, raw=h)
            return Insn(LUI, rd, imm=(imm6 << 12) & 0xFFFFFFFF, size=2, raw=h, cname="c.lui",
                        cfields=("r", rd, "i", (imm6 & 0xFFFFF)))
        if f3 == 4:
            rdp = _r3(h >> 7)
            f2 = (h >> 10) & 3
            shamt = (((h >> 12) & 1) << 5) | ((h >> 2) & 31)
            if f2 == 0:
                if shamt & 32:
                    return Insn(ILLEGAL, size=2, raw=h)
                return Insn(SRLI, rdp, rdp, imm=shamt, size=2, raw=h, cname="c.srli", cfields=("r", rdp, "i", shamt))
            if f2 == 1:
                if shamt & 32:
                    return Insn(ILLEGAL, size=2, raw=h)
                return Insn(SRAI, rdp, rdp, imm=shamt, size=2, raw=h, cname="c.srai", cfields=("r", rdp, "i", shamt))
            if f2 == 2:
                return Insn(ANDI, rdp, rdp, imm=imm6, size=2, raw=h, cname="c.andi", cfields=("r", rdp, "i", imm6))
            if (h >> 12) & 1:
                return Insn(ILLEGAL, size=2, raw=h)
            rs2p = _r3(h >> 2)
            op, nm = [(SUB, "c.sub"), (XOR, "c.xor"), (OR, "c.or"), (AND, "c.and")][(h >> 5) & 3]
            return Insn(op, rdp, rdp, rs2p, size=2, raw=h, cname=nm, cfields=("r", rdp, "r", rs2p))
        if f3 in (6, 7):
            rs1p = _r3(h >> 7)
            b = h
            imm = ((((b >> 12) & 1) << 8) | (((b >> 10) & 3) << 3) | (((b >> 5) & 3) << 6)
                   | (((b >> 3) & 3) << 1) | (((b >> 2) & 1) << 5))
            imm = sext(imm, 9)
            if f3 == 6:
                return Insn(BEQ, 0, rs1p, 0, imm, size=2, raw=h, cname="c.beqz", cfields=("r", rs1p, "t", imm))
            return Insn(BNE, 0, rs1p, 0, imm, size=2, raw=h, cname="c.bnez", cfields=("r", rs1p, "t", imm))
    if q == 2:
        rd = (h >> 7) & 31
        rs2 = (h >> 2) & 31
        b12 = (h >> 12) & 1
        if f3 == 0:
            shamt = (b12 << 5) | rs2
            if b12 or rd == 0:
                return Insn(ILLEGAL, size=2, raw=h)
            return Insn(SLLI, rd, rd, imm=shamt, size=2, raw=h, cname="c.slli", cfields=("r", rd, "i", shamt))
        if f3 == 2:
            if rd == 0:
                return Insn(ILLEGAL, size=2, raw=h)
            imm = (b12 << 5) | (((h >> 4) & 7) << 2) | (((h >> 2) & 3) << 6)
            return Insn(LW, rd, 2, imm=imm, size=2, raw=h, cname="c.lwsp", cfields=("r", rd, "m", imm, 2))
        if f3 == 4:
            if b12 == 0:
                if rs2 == 0:
                    if rd == 0:
                        return Insn(ILLEGAL, size=2, raw=h)
                    return Insn(JALR, 0, rd, imm=0, size=2, raw=h, cname="c.jr", cfields=("r", rd))
                if rd == 0:
                    return Insn(ILLEGAL, size=2, raw=h)  # HINT space; treat as illegal here
                return Insn(ADD, rd, 0, rs2, size=2, raw=h, cname="c.mv", cfields=("r", rd, "r", rs2))
            if rs2 == 0:
                if rd == 0:
                    return Insn(EBREAK, size=2, raw=h, cname="c.ebreak", cfields=())
                return Insn(JALR, 1, rd, imm=0, size=2, raw=h, cname="c.jalr", cfields=("r", rd))
            if rd == 0:
                return Insn(ILLEGAL, size=2, raw=h)
            return Insn(ADD, rd, rd, rs2, size=2, raw=h, cname="c.add", cfields=("r", rd, "r", rs2))
        if f3 == 6:
            imm = (((h >> 9) & 0xF) << 2) | (((h >> 7) & 3) << 6)
            return Insn(SW, 0, 2, rs2, imm=imm, size=2, raw=h, cname="c.swsp", cfields=("r", rs2, "m", imm, 2))
    return Insn(ILLEGAL, size=2, raw=h)


def decode_at(buf, off):
    """Decode the instruction at byte offset `off` of `buf` (little endian)."""
    if off + 2 > len(buf):
        return Insn(ILLEGAL, size=2, raw=0)
    h = buf[off] | (buf[off + 1] << 8)
    if (h & 3) != 3:
        return decode16(h)
    if off + 4 > len(buf):
        return Insn(ILLEGAL, size=4, raw=h)
    w = h | (buf[off + 2] << 16) | (buf[off + 3] << 24)
    return decode32(w)


# ------------------------------------------------------------------ disassembler
def _hx(v):
    return "-0x%x" % (-v) if v < 0 else "0x%x" % v


def _fmt_fields(fields, pc):
    out = []
    i = 0
    while i < len(fields):
        t = fields[i]
        if t == "r":
            out.append(ABI[fields[i + 1]])
            i += 2
        elif t == "i":
            out.append(_hx(fields[i + 1]))
            i += 2
        elif t == "t":
            out.append("0x%x" % ((pc + fields[i + 1]) & 0xFFFFFFFF))
            i += 2
        elif t == "m":
            out.append("%s(%s)" % (_hx(fields[i + 1]), ABI[fields[i + 2]]))
            i += 3
        else:
            out.append(str(t))
            i += 1
    return ", ".join(out)


def disasm(ins, pc):
    """Text in the style of `llvm-objdump -M no-aliases` (mnemonic, operands)."""
    if ins.cname is not None:
        f = _fmt_fields(ins.cfields, pc)
        return ins.cname + ("\t" + f if f else "")
    op = ins.op
    n = NAMES[op]
    R = ABI
    if op in (LUI, AUIPC):
        return "%s\t%s, 0x%x" % (n, R[ins.rd], (ins.imm >> 12) & 0xFFFFF)
    if op == JAL:
        return "%s\t%s, 0x%x" % (n, R[ins.rd], (pc + ins.imm) & 0xFFFFFFFF)
    if op == JALR:
        return "%s\t%s, %s(%s)" % (n, R[ins.rd], _hx(ins.imm), R[ins.rs1])
    if op in BRANCHES:
        return "%s\t%s, %s, 0x%x" % (n, R[ins.rs1], R[ins.rs2], (pc + ins.imm) & 0xFFFFFFFF)
    if op in LOADS:
        return "%s\t%s, %s(%s)" % (n, R[ins.rd], _hx(ins.imm), R[ins.rs1])
    if op in STORES:
        return "%s\t%s, %s(%s)" % (n, R[ins.rs2], _hx(ins.imm), R[ins.rs1])
    if ADDI <= op <= SRAI:
        return "%s\t%s, %s, %s" % (n, R[ins.rd], R[ins.rs1], _hx(ins.imm))
    if ADD <= op <= REMU:
        return "%s\t%s, %s, %s" % (n, R[ins.rd], R[ins.rs1], R[ins.rs2])
    if op == FENCE:
        return "fence"
    if op in (ECALL, EBREAK):
        return n
    return "<illegal 0x%x>" % ins.raw
