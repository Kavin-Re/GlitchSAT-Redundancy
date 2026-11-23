"""Constants and derived parameters of the secure-boot core. This file is the machine-readable half of SPEC.md:
the Python model, the Verilog generators, the test-vector generator and the engine wrappers all import it."""
from dataclasses import dataclass, replace
from . import keccak as K

# ---- FSM state codes (SPEC.md section 3; chosen by tools/encoding_analysis.py) ----
IDLE, LOAD, HASH, COMPARE, ALARM, ACCEPT, REJECT = 0xF0, 0xCC, 0xAA, 0x66, 0x5A, 0x96, 0x69
STATES = dict(IDLE=IDLE, LOAD=LOAD, HASH=HASH, COMPARE=COMPARE, ALARM=ALARM, ACCEPT=ACCEPT, REJECT=REJECT)
STATE_NAME = {v: k for k, v in STATES.items()}
STATE_BITS = 8

# ---- multi-bit booleans (4-bit, Hamming distance 4, values as used by OpenTitan's mubi4_t) ----
MUBI4_TRUE, MUBI4_FALSE = 0x6, 0x9

CMP_SINGLE, CMP_DUP, CMP_TRIP, CMP_COMPL = 0, 1, 2, 3
CMP_NAMES = {0: 'single', 1: 'duplicated, shared AND', 2: 'triplicated, owned result bits', 3: 'complemented pair, owned result bits'}
INFECT_TAPS = (0, 1, 3)


@dataclass(frozen=True)
class Cfg:
    W: int = 8                # lane width; permutation width b = 25 * W
    RATE_LANES: int = 4       # rate r = RATE_LANES * W bits (= one image block)
    TAG_LANES: int = 4        # tag = first TAG_LANES lanes
    NR: int = 0               # rounds per permutation; 0 = full Keccak-f (12 + 2*log2 W)
    KEY_BLOCKS: int = 1
    IMG_BLOCKS: int = 1
    HASH_EN: int = 1          # 0: no hash engine, the tag comes from port tag_in (decision-only experiments)
    HASH_COPIES: int = 1      # 1 or 2 independent hash engines
    CMP_MODE: int = 0
    FLAG_MUBI: int = 0        # compare-result registers: 0 = one bit per copy, 1 = mubi4 per copy
    SEPARATE: int = 1         # 1: every compare copy is its own keep_hierarchy module; 0: inline (tool may merge)
    ALARM_EN: int = 0
    INFECT_SPREAD: int = 0    # 0 = no infection; 1..3 = token bits disturbed per wrong tag bit
    CFI_EN: int = 0
    OTP_REG: int = 0          # 0 constants; 1 one shared shadow register per rail; 2 one shadow register per consumer
    EXP_SRC: int = 0          # expected tag: 0 parameter EXP_TAG; 1 input exp_in, loaded on exp_load (needs OTP_REG >= 1)
    TKW: int = 8              # token width (<= tag width)
    KEY: int = 0
    EXP_TAG: int = 0
    TOKEN: int = 0

    def __post_init__(self):
        K.ell(self.W)
        assert 1 <= self.TAG_LANES <= self.RATE_LANES <= 24 and self.R >= 4
        assert 0 <= self.NR <= K.full_rounds(self.W)
        assert self.KEY_BLOCKS >= 1 and self.IMG_BLOCKS >= 1
        assert self.HASH_EN in (0, 1) and self.HASH_COPIES in (1, 2)
        assert self.CMP_MODE in (0, 1, 2, 3) and self.OTP_REG in (0, 1, 2) and 0 <= self.INFECT_SPREAD <= 3
        assert 1 <= self.TKW <= self.TAG
        assert self.EXP_SRC in (0, 1) and (self.EXP_SRC == 0 or self.OTP_REG >= 1)
        assert 0 <= self.KEY < (1 << (self.KEY_BLOCKS * self.R)) and 0 <= self.EXP_TAG < (1 << self.TAG)
        assert 0 <= self.TOKEN < (1 << self.TKW)

    # ---- derived (same names as the Verilog localparams) ----
    @property
    def R(self): return self.RATE_LANES * self.W
    @property
    def TAG(self): return self.TAG_LANES * self.W
    @property
    def B(self): return 25 * self.W
    @property
    def NR_E(self): return self.NR or K.full_rounds(self.W)
    @property
    def RND_FIRST(self): return (K.full_rounds(self.W) - self.NR_E) if self.HASH_EN else 0
    @property
    def RND_LAST(self): return (K.full_rounds(self.W) - 1) if self.HASH_EN else 0
    @property
    def KB(self): return self.KEY_BLOCKS if self.HASH_EN else 0
    @property
    def IB(self): return self.IMG_BLOCKS if self.HASH_EN else 0
    @property
    def NABS(self): return self.KB + self.IB + 1
    @property
    def NRC(self): return self.RND_LAST - self.RND_FIRST + 1        # cycles spent in HASH per block
    @property
    def EXP_STEPS(self): return self.NABS * (1 + self.NRC) + 2
    @property
    def STEPW(self): return max(1, (self.EXP_STEPS).bit_length())   # = $clog2(EXP_STEPS + 1)
    @property
    def BLKW(self): return 1 if self.NABS <= 2 else (self.NABS - 1).bit_length()   # = $clog2(NABS)
    @property
    def NC(self): return {0: 1, 1: 2, 2: 3, 3: 2}[self.CMP_MODE]
    @property
    def FW(self): return 4 if self.FLAG_MUBI else 1
    @property
    def PAD(self): return K.pad_block(self.R)
    @property
    def NHASH(self): return self.HASH_COPIES if self.HASH_EN else 0

    def compl(self, c):
        """Copy c works on the complemented rail (only copy 1 of CMP_COMPL)."""
        return 1 if (self.CMP_MODE == CMP_COMPL and c == 1) else 0

    def flag_true(self, c):
        if self.FLAG_MUBI:
            return MUBI4_FALSE if self.compl(c) else MUBI4_TRUE
        return 0 if self.compl(c) else 1

    def flag_false(self, c):
        if self.FLAG_MUBI:
            return MUBI4_TRUE if self.compl(c) else MUBI4_FALSE
        return 1 if self.compl(c) else 0

    def owner(self, i):
        """Compare copy that decides state bit i (None = AND of all copies, CMP_DUP)."""
        return {0: 0, 1: None, 2: i % 3, 3: i % 2}[self.CMP_MODE]

    def hash_of(self, consumer):
        """Hash engine read by a consumer: compare copies 0..NC-1, infection = NC."""
        return (self.HASH_COPIES - 1) if consumer == self.NC else consumer % self.HASH_COPIES

    # expected-value registers (OTP shadow): list of rails, and consumer -> register index
    def otp_regs(self):
        if self.OTP_REG == 0:
            return []
        if self.OTP_REG == 1:
            return [0, 1] if self.CMP_MODE == CMP_COMPL else [0]
        n = self.NC + (1 if self.INFECT_SPREAD else 0)
        return [self.compl(c) if c < self.NC else 0 for c in range(n)]

    def otp_reg_of(self, consumer):
        rail = self.compl(consumer) if consumer < self.NC else 0
        return rail if self.OTP_REG == 1 else consumer

    def cycles_to_word(self):
        """Clock cycle index (cycle 0 = first cycle with start high, state IDLE) at which boot_word first shows
        the verdict, when image blocks are always valid."""
        return 1 + self.NABS * (1 + self.NRC) + 2 + 1

    def but(self, **kw):
        return replace(self, **kw)


def decision_groups(cfg, per_flag_bit=False):
    """Groups of state bits that switch together between REJECT and ACCEPT.
    Default: one group per compare copy (all flag bits of a copy come from that copy's one result net).
    per_flag_bit=True: one group per flag-register bit (what single flag-bit flips can move)."""
    g = {}
    for i in range(STATE_BITS):
        key = (cfg.owner(i), i % 4 if (cfg.FLAG_MUBI and per_flag_bit) else 0)
        g.setdefault(key, []).append(i)
    return list(g.values())
