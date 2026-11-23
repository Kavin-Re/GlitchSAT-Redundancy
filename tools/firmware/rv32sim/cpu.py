"""A small, exact RV32IMC instruction-set simulator for the boot ROM images.

Memory map (must match src/mmio.h, src/link.ld and INTERFACE.md):
  ROM     0x00000000 .. 0x00004000   code + constants, read/execute
  RAM     0x10000000 .. 0x10001000   data, stack, read/write
  FLASH   0x20000000 .. 0x20001000   boot image, read/execute (XIP)
  SYSCTRL 0x30000000  +0 BOOT_STATUS (W; bit 31 set = boot failed, halts)
                      +4 ALARM (W; halts) +8 TRNG (R; xorshift32, seeded)
                      +0xC EXEC_EN (W; FLASH_EXEC_KEY unlocks fetch from FLASH;
                      with exec_lock=False flash is executable from reset)
  OTP     0x40000000  +0x00..0x1C HMAC key, +0x20 MIN_VERSION, +0x24 ~MIN_VERSION (R)
  HMAC    0x50000000  MAC engine, one of two models chosen by the program (Program.engine):
          "hmac": HMAC-SHA-256 (src/hmac_hw.c): +0 CTRL (W) +4 STATUS (R) +8 MSG (W)
                  +0x20..0x3C DIGEST (R); other offsets are bus errors (unchanged model of
                  the recorded results)
          "sha3": SHA3-256(K136 || M) engine of secboot_hw (src/mac_sha3_hw.c), 128 B
                  window: also +0x40 VERDICT, +0x44 TOKEN, +0x48 INFO (R), +0x60..0x7C
                  EXPECTED (W, latched at FINISH); message exactly SHA3_BLOCKS x 136 B

Outcome of a run:
  IMAGE   the core fetched an instruction from FLASH (the image runs);
          with a tampered or rolled-back image this is the attacker's goal
  REJECT  BOOT_STATUS written with bit 31 set (ordinary refusal)
  DETECT  ALARM written (a redundant check disagreed)
  TRAP    any exception: illegal instruction (incl. unimp; RV32C HINTs with rd = 0 also trap), fetch outside
          the ROM .text (the only predecoded part), fetch from FLASH while it is execute-locked, misaligned PC, access outside a region, store to a
          read-only region, ecall/ebreak. A ROM that halts on any exception.
  TIMEOUT step budget used up

Simplifications (README.md lists them): one instruction per step, no
pipeline, caches or interrupts; misaligned loads/stores inside a region are
performed (as Ibex does); no CSRs; the HMAC engine is atomic (DONE is set
by the FINISH write); the SHA3 engine omits STATUS bits 3 (ALARM_SEEN) and 4 (BUSY); SHA3_BLOCKS is fixed at the SoC
build value 8 (the RTL default is 2).
"""
import hashlib
import hmac as _hmac

from . import isa
from .isa import (LUI, AUIPC, JAL, JALR, BEQ, BNE, BLT, BGE, BLTU, BGEU,
                  LB, LH, LW, LBU, LHU, SB, SH, SW,
                  ADDI, SLTI, SLTIU, XORI, ORI, ANDI, SLLI, SRLI, SRAI,
                  ADD, SUB, SLL, SLT, SLTU, XOR, SRL, SRA, OR, AND,
                  MUL, MULH, MULHSU, MULHU, DIV, DIVU, REM, REMU,
                  FENCE, ECALL, EBREAK, ILLEGAL)

ROM_BASE, ROM_SIZE = 0x00000000, 0x4000
RAM_BASE, RAM_SIZE = 0x10000000, 0x1000
FLASH_BASE, FLASH_SIZE = 0x20000000, 0x1000
SYSCTRL = 0x30000000
OTP_BASE, OTP_SIZE = 0x40000000, 0x28
HMAC_BASE = 0x50000000
HMAC_SIZE = 0x80
SHA3_BLOCKS, SHA3_WORDS_PER_BLOCK = 8, 34      # INFO of the SoC build (IMG_BLOCKS = 8, rate 1088 bits)
SHA3_MSG_BYTES = SHA3_BLOCKS * SHA3_WORDS_PER_BLOCK * 4
V_ACCEPT, V_REJECT, V_IDLE = 0x96, 0x69, 0xF0
FLASH_EXEC_KEY = 0xA5C3B007

M32 = 0xFFFFFFFF

RUNNING, IMAGE, REJECT, DETECT, TRAP, TIMEOUT = range(6)
OUTCOME_NAMES = ["running", "image_runs", "reject", "alarm", "trap", "timeout"]

F_NONE, F_SKIP, F_BRINV, F_PCOFF, F_RDFLIP, F_IWFLIP = range(6)


def make_otp(key32, min_version):
    """OTP contents: key bytes, MIN_VERSION, ~MIN_VERSION."""
    assert len(key32) == 32
    return bytes(key32) + (min_version & M32).to_bytes(4, "little") + ((~min_version) & M32).to_bytes(4, "little")


def _s(v):
    return v - 0x100000000 if v & 0x80000000 else v


class Program:
    """Static part of a machine: ROM image, predecoded code, symbols."""

    def __init__(self, rom, ram_init, symbols, text_range, lines=None, engine=None):
        self.rom = bytes(rom)
        self.ram_init = bytes(ram_init)
        self.symbols = symbols            # name -> (addr, size)
        self.text_lo, self.text_hi = text_range
        self.lines = lines or {}          # addr -> (file, line)
        # MAC engine model: "sha3" if the ELF carries the marker of src/mac_sha3_hw.c
        self.engine = engine or ("sha3" if "mac_engine_sha3" in symbols else "hmac")
        # predecode every 2-byte aligned address of .text (faults can land mid-instruction)
        self.code = {}
        for a in range(self.text_lo, self.text_hi, 2):
            self.code[a] = isa.decode_at(self.rom, a - ROM_BASE)

    def sym(self, name):
        return self.symbols[name][0]

    def func_at(self, addr):
        best = None
        for n, (a, s) in self.symbols.items():
            if a <= addr < a + max(s, 1) and not n.startswith("."):
                if best is None or a > self.symbols[best][0]:
                    best = n
        return best

    @classmethod
    def from_elf(cls, path):
        from .elf import load_elf
        return load_elf(path)


class Machine:
    __slots__ = ("p", "regs", "pc", "ram", "flash", "otp", "trng", "steps", "outcome", "status",
                 "alarm", "entry", "hm_msg", "hm_dig", "hm_on", "code", "rom", "rk", "exec_en",
                 "sha3", "hm_exp", "hm_lat", "hm_err")

    def __init__(self, prog, flash=b"", otp=None, trng_seed=1, exec_lock=True):
        self.p = prog
        self.code = prog.code
        self.rom = prog.rom
        self.regs = [0] * 32
        self.pc = prog.sym("_start")
        self.ram = bytearray(RAM_SIZE)
        self.ram[:len(prog.ram_init)] = prog.ram_init
        self.flash = bytes(flash).ljust(FLASH_SIZE, b"\xff")[:FLASH_SIZE]
        self.otp = otp if otp is not None else make_otp(bytes(32), 0)
        self.trng = (trng_seed & M32) or 1
        self.steps = 0
        self.outcome = RUNNING
        self.status = None   # last BOOT_STATUS value
        self.alarm = None
        self.entry = None    # first FLASH address fetched
        self.hm_msg = b""    # HMAC engine message buffer
        self.hm_dig = None   # digest (bytes) once FINISH was written
        self.hm_on = False
        self.rk = None       # cached RAM digest for key(); None after a store
        self.exec_en = not exec_lock   # flash fetch allowed? (EXEC_EN register)
        self.sha3 = prog.engine == "sha3"
        self.hm_exp = (0,) * 8         # SHA3 engine: EXPECTED registers
        self.hm_lat = None             # EXPECTED latched at FINISH
        self.hm_err = False            # SHA3 engine: ERR

    def copy(self):
        m = Machine.__new__(Machine)
        m.p = self.p; m.code = self.code; m.rom = self.rom
        m.regs = self.regs[:]
        m.pc = self.pc
        m.ram = bytearray(self.ram)
        m.flash = self.flash; m.otp = self.otp
        m.trng = self.trng; m.steps = self.steps; m.outcome = self.outcome
        m.status = self.status; m.alarm = self.alarm; m.entry = self.entry
        m.hm_msg = self.hm_msg; m.hm_dig = self.hm_dig; m.hm_on = self.hm_on
        m.rk = self.rk
        m.exec_en = self.exec_en
        m.sha3 = self.sha3; m.hm_exp = self.hm_exp; m.hm_lat = self.hm_lat; m.hm_err = self.hm_err
        return m

    def key(self):
        """Architectural + peripheral state (step count excluded). RAM enters as
        a 128-bit BLAKE2b digest to bound memory; see faultsim/search.py."""
        if self.rk is None:
            self.rk = hashlib.blake2b(self.ram, digest_size=16).digest()
        return (self.pc, tuple(self.regs), self.rk, self.trng, self.outcome,
                self.status, self.hm_msg, self.hm_dig, self.hm_on, self.exec_en,
                self.hm_exp, self.hm_lat, self.hm_err)

    # ------------------------------------------------------------ memory
    def load(self, addr, n, signed):
        addr &= M32
        if RAM_BASE <= addr and addr + n <= RAM_BASE + RAM_SIZE:
            o = addr - RAM_BASE
            b = self.ram[o:o + n]
        elif addr + n <= ROM_BASE + len(self.rom):
            b = self.rom[addr:addr + n]
        elif FLASH_BASE <= addr and addr + n <= FLASH_BASE + FLASH_SIZE:
            o = addr - FLASH_BASE
            b = self.flash[o:o + n]
        elif OTP_BASE <= addr and addr + n <= OTP_BASE + OTP_SIZE and n == 4 and not addr & 3:
            o = addr - OTP_BASE
            b = self.otp[o:o + 4]
        elif addr == SYSCTRL + 8 and n == 4:
            x = self.trng
            x ^= (x << 13) & M32
            x ^= x >> 17
            x ^= (x << 5) & M32
            self.trng = x
            return x
        elif self.sha3 and HMAC_BASE <= addr < HMAC_BASE + HMAC_SIZE:
            return self._sha3_load(addr - HMAC_BASE, n)
        elif addr == HMAC_BASE + 4 and n == 4:
            return 1 if self.hm_dig is not None else 0
        elif HMAC_BASE + 0x20 <= addr < HMAC_BASE + 0x40 and n == 4 and not addr & 3:
            if self.hm_dig is None:
                return 0
            o = addr - HMAC_BASE - 0x20
            return int.from_bytes(self.hm_dig[o:o + 4], "little")
        else:
            return None
        v = int.from_bytes(b, "little")
        if signed and v >> (8 * n - 1):
            v -= 1 << (8 * n)
        return v & M32

    def store(self, addr, n, v):
        addr &= M32
        if RAM_BASE <= addr and addr + n <= RAM_BASE + RAM_SIZE:
            o = addr - RAM_BASE
            self.ram[o:o + n] = (v & ((1 << (8 * n)) - 1)).to_bytes(n, "little")
            self.rk = None
            return True
        if n != 4:
            return False
        v &= M32
        if addr == SYSCTRL:
            self.status = v
            if v & 0x80000000:
                self.outcome = REJECT
            return True
        if addr == SYSCTRL + 12:
            if v == FLASH_EXEC_KEY:
                self.exec_en = True
            return True
        if addr == SYSCTRL + 4:
            self.alarm = v
            self.outcome = DETECT
            return True
        if self.sha3 and HMAC_BASE <= addr < HMAC_BASE + HMAC_SIZE:
            return self._sha3_store(addr - HMAC_BASE, v)
        if addr == HMAC_BASE:
            if v == 1:
                self.hm_on = True; self.hm_msg = b""; self.hm_dig = None
            elif v == 2 and self.hm_on:
                key = self.otp[0:32]
                self.hm_dig = _hmac.new(key, self.hm_msg, hashlib.sha256).digest()
                self.hm_on = False
            return True
        if addr == HMAC_BASE + 8:
            if self.hm_on:
                self.hm_msg += v.to_bytes(4, "little")
            return True
        return False

    # ------------------------------------------------------------ SHA3-256 engine
    def _sha3_accept(self):
        return (not self.hm_err and self.hm_dig is not None and self.hm_lat is not None
                and self.hm_dig == b"".join(w.to_bytes(4, "little") for w in self.hm_lat))

    def _sha3_load(self, o, n):
        if n != 4 or o & 3:
            return None
        if o == 0x04:
            done = self.hm_dig is not None or self.hm_err
            return (int(self._sha3_accept()) << 2) | (int(self.hm_err) << 1) | int(done)
        if 0x20 <= o < 0x40:
            if self.hm_dig is None:
                return 0
            return int.from_bytes(self.hm_dig[o - 0x20:o - 0x1C], "little")
        if o == 0x40:
            if self.hm_err:
                return V_REJECT
            if self.hm_dig is None:
                return V_IDLE
            return V_ACCEPT if self._sha3_accept() else V_REJECT
        if o == 0x44:
            return FLASH_EXEC_KEY if self._sha3_accept() else 0
        if o == 0x48:
            return (SHA3_BLOCKS << 16) | SHA3_WORDS_PER_BLOCK
        return 0                       # write-only or reserved offsets read 0 (as the RTL)

    def _sha3_store(self, o, v):
        if o & 3:
            return False
        if o == 0x00:
            if v == 1:                 # START
                self.hm_on = True; self.hm_msg = b""; self.hm_dig = None
                self.hm_lat = None; self.hm_err = False; self.hm_exp = (0,) * 8
            elif v == 2:               # FINISH
                if not self.hm_on or len(self.hm_msg) != SHA3_MSG_BYTES:
                    self.hm_err = True
                else:
                    key = self.otp[0:32] + bytes(104)
                    self.hm_dig = hashlib.sha3_256(key + self.hm_msg).digest()
                    self.hm_lat = self.hm_exp
                self.hm_on = False
        elif o == 0x08:                # MSG
            if self.hm_on and len(self.hm_msg) < SHA3_MSG_BYTES:
                self.hm_msg += v.to_bytes(4, "little")
            else:
                self.hm_err = True
        elif 0x60 <= o < 0x80 and self.hm_on:    # EXPECTED: taken only between START and FINISH
            e = list(self.hm_exp)
            e[(o - 0x60) // 4] = v
            self.hm_exp = tuple(e)
        return True                    # other offsets: write ignored (as the RTL)

    # ------------------------------------------------------------ one step
    def step(self, fmode=F_NONE, farg=0):
        """Execute one instruction, optionally under a fault. Returns outcome."""
        if self.outcome != RUNNING:
            return self.outcome
        pc = self.pc
        ins = self.code.get(pc)
        if ins is None:
            if FLASH_BASE <= pc < FLASH_BASE + FLASH_SIZE and self.exec_en:
                self.entry = pc
                self.outcome = IMAGE
                return IMAGE
            self.outcome = TRAP
            return TRAP
        self.steps += 1
        if fmode:
            if fmode == F_SKIP:
                self.pc = (pc + ins.size) & M32
                return RUNNING
            if fmode == F_IWFLIP:
                o = pc - ROM_BASE
                w = int.from_bytes(self.rom[o:o + 4].ljust(4, b"\0"), "little") ^ (1 << farg)
                ins = isa.decode_at(w.to_bytes(4, "little"), 0)
        r = self.regs
        op = ins.op
        npc = (pc + ins.size) & M32
        wr = 0
        val = 0
        if op == ADDI:
            val = (r[ins.rs1] + ins.imm) & M32; wr = ins.rd
        elif op in (BEQ, BNE, BLT, BGE, BLTU, BGEU):
            a = r[ins.rs1]; b = r[ins.rs2]
            if op == BEQ: t = a == b
            elif op == BNE: t = a != b
            elif op == BLT: t = _s(a) < _s(b)
            elif op == BGE: t = _s(a) >= _s(b)
            elif op == BLTU: t = a < b
            else: t = a >= b
            if fmode == F_BRINV:
                t = not t
            if t:
                npc = (pc + ins.imm) & M32
        elif op in (LB, LH, LW, LBU, LHU):
            n = 1 if op in (LB, LBU) else (2 if op in (LH, LHU) else 4)
            v = self.load(r[ins.rs1] + ins.imm, n, op in (LB, LH))
            if v is None:
                self.outcome = TRAP
                return TRAP
            val = v; wr = ins.rd
        elif op in (SB, SH, SW):
            n = 1 if op == SB else (2 if op == SH else 4)
            if not self.store(r[ins.rs1] + ins.imm, n, r[ins.rs2]):
                self.outcome = TRAP
                return TRAP
        elif op == ADD:
            val = (r[ins.rs1] + r[ins.rs2]) & M32; wr = ins.rd
        elif op == SUB:
            val = (r[ins.rs1] - r[ins.rs2]) & M32; wr = ins.rd
        elif op == JAL:
            val = npc; wr = ins.rd
            npc = (pc + ins.imm) & M32
        elif op == JALR:
            val = npc; wr = ins.rd
            npc = (r[ins.rs1] + ins.imm) & 0xFFFFFFFE
        elif op == LUI:
            val = ins.imm; wr = ins.rd
        elif op == AUIPC:
            val = (pc + ins.imm) & M32; wr = ins.rd
        elif op == ANDI:
            val = r[ins.rs1] & (ins.imm & M32); wr = ins.rd
        elif op == ORI:
            val = r[ins.rs1] | (ins.imm & M32); wr = ins.rd
        elif op == XORI:
            val = r[ins.rs1] ^ (ins.imm & M32); wr = ins.rd
        elif op == SLTI:
            val = 1 if _s(r[ins.rs1]) < ins.imm else 0; wr = ins.rd
        elif op == SLTIU:
            val = 1 if r[ins.rs1] < (ins.imm & M32) else 0; wr = ins.rd
        elif op == SLLI:
            val = (r[ins.rs1] << ins.imm) & M32; wr = ins.rd
        elif op == SRLI:
            val = r[ins.rs1] >> ins.imm; wr = ins.rd
        elif op == SRAI:
            val = (_s(r[ins.rs1]) >> ins.imm) & M32; wr = ins.rd
        elif op == AND:
            val = r[ins.rs1] & r[ins.rs2]; wr = ins.rd
        elif op == OR:
            val = r[ins.rs1] | r[ins.rs2]; wr = ins.rd
        elif op == XOR:
            val = r[ins.rs1] ^ r[ins.rs2]; wr = ins.rd
        elif op == SLL:
            val = (r[ins.rs1] << (r[ins.rs2] & 31)) & M32; wr = ins.rd
        elif op == SRL:
            val = r[ins.rs1] >> (r[ins.rs2] & 31); wr = ins.rd
        elif op == SRA:
            val = (_s(r[ins.rs1]) >> (r[ins.rs2] & 31)) & M32; wr = ins.rd
        elif op == SLT:
            val = 1 if _s(r[ins.rs1]) < _s(r[ins.rs2]) else 0; wr = ins.rd
        elif op == SLTU:
            val = 1 if r[ins.rs1] < r[ins.rs2] else 0; wr = ins.rd
        elif MUL <= op <= REMU:
            a = r[ins.rs1]; b = r[ins.rs2]
            if op == MUL:
                val = (a * b) & M32
            elif op == MULH:
                val = ((_s(a) * _s(b)) >> 32) & M32
            elif op == MULHSU:
                val = ((_s(a) * b) >> 32) & M32
            elif op == MULHU:
                val = ((a * b) >> 32) & M32
            elif op == DIV:
                sa, sb = _s(a), _s(b)
                if sb == 0:
                    val = M32
                elif sa == -0x80000000 and sb == -1:
                    val = a
                else:
                    q = abs(sa) // abs(sb)
                    val = (q if (sa < 0) == (sb < 0) else -q) & M32
            elif op == DIVU:
                val = M32 if b == 0 else a // b
            elif op == REM:
                sa, sb = _s(a), _s(b)
                if sb == 0:
                    val = a
                elif sa == -0x80000000 and sb == -1:
                    val = 0
                else:
                    m_ = abs(sa) % abs(sb)
                    val = (m_ if sa >= 0 else -m_) & M32
            else:
                val = a if b == 0 else a % b
            wr = ins.rd
        elif op == FENCE:
            pass
        else:  # ECALL, EBREAK, ILLEGAL
            self.outcome = TRAP
            return TRAP
        if wr:
            if fmode == F_RDFLIP:
                val ^= 1 << farg
            r[wr] = val
        if fmode == F_PCOFF:
            npc = (npc + farg) & M32
        if npc & 1:
            self.outcome = TRAP
            return TRAP
        self.pc = npc
        return self.outcome

    def run(self, max_steps=100000):
        st = self.step
        while self.outcome == RUNNING and self.steps < max_steps:
            st()
        if self.outcome == RUNNING:
            self.outcome = TIMEOUT
        return self.outcome
