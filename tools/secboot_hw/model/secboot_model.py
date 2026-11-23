"""Cycle-accurate model of rtl/secboot_core.v, written from SPEC.md (not from the Verilog).

One call of Core.step() is one rising clock edge. It returns the outputs as they are during that cycle (before
the edge), then updates the registers. Every register of the RTL has an entry of the same name in Core.r, so a
single-cycle flip of a flip-flop output can be modelled exactly: step(..., flips=[('st', 3)]) inverts bit 3 of
register `st` for that cycle (all readers see the flipped value, including the register's own next-state logic).
Register names: st rel blk rnd cph tok flag<c> step step_n hash<h> otp<n>.
"""
from dataclasses import dataclass
from . import keccak as K
from . import spec as S
from .spec import Cfg, IDLE, LOAD, HASH, COMPARE, ALARM, ACCEPT, REJECT

VALID = frozenset(S.STATES.values())


@dataclass
class In:
    rst: int = 0
    start: int = 1
    blk_valid: int = 1
    blk_data: int = 0
    tag_in: int = 0
    exp_in: int = 0       # EXP_SRC = 1 only: expected tag, loaded into the shadow registers when exp_load = 1
    exp_load: int = 0
    pad_ok: int = 1       # EXP_SRC = 1 only: the pad block waits for pad_ok


def mac(cfg, image_blocks):
    """The tag the hardware computes for the given image blocks (pure function, no clocking)."""
    r = cfg.R
    key = [(cfg.KEY >> (j * r)) & ((1 << r) - 1) for j in range(cfg.KEY_BLOCKS)]
    assert len(image_blocks) == cfg.IMG_BLOCKS
    return K.sponge_tag(key + list(image_blocks), cfg.W, cfg.RATE_LANES, cfg.TAG_LANES, cfg.NR_E)


class Core:
    def __init__(self, cfg: Cfg):
        self.c = cfg
        self.width = {}
        self.reset_value = {}
        c = cfg
        def reg(name, width, rv):
            self.width[name] = width
            self.reset_value[name] = rv
        reg('st', 8, IDLE)
        reg('rel', 8, IDLE)
        reg('blk', c.BLKW, 0)
        reg('rnd', 5, c.RND_FIRST)
        reg('cph', 1, 0)
        reg('tok', c.TKW, 0)
        for i in range(c.NC):
            reg(f'flag{i}', c.FW, c.flag_false(i))
        if c.CFI_EN:
            reg('step', c.STEPW, 0)
            reg('step_n', c.STEPW, (1 << c.STEPW) - 1)
        for h in range(c.NHASH):
            reg(f'hash{h}', c.B, 0)
        for n, _rail in enumerate(c.otp_regs()):
            reg(f'otp{n}', c.TAG, 0)
        self.r = dict(self.reset_value)       # power-up state = reset state (the RTL has matching `initial`s)
        self.cycle = 0

    # ---------------------------------------------------------------- combinational view
    def comb(self, inp: In, r=None):
        c = self.c
        r = self.r if r is None else r
        tmask = (1 << c.TAG) - 1
        st = r['st']
        w = {}
        clear = int(st == IDLE and inp.start)
        is_key = int(r['blk'] < c.KB)
        is_img = int((not is_key) and r['blk'] < c.KB + c.IB)
        is_pad = int(not is_key and not is_img)
        avail = inp.blk_valid if is_img else (inp.pad_ok if (is_pad and c.EXP_SRC) else 1)
        absorb = int(st == LOAD and avail)
        round_en = int(st == HASH)
        cap = int(st == COMPARE and not r['cph'])
        is_cmp1 = int(st == COMPARE and r['cph'])
        step_inc = int(absorb or round_en or st == COMPARE)
        # tags and expected values per consumer (compare copies 0..NC-1, infection = NC)
        def tag_of(consumer):
            return (r[f'hash{c.hash_of(consumer)}'] & tmask) if c.HASH_EN else (inp.tag_in & tmask)
        def exp_of(consumer):
            rail = c.compl(consumer) if consumer < c.NC else 0
            if c.OTP_REG == 0:
                return (~c.EXP_TAG & tmask) if rail else c.EXP_TAG
            return r[f'otp{c.otp_reg_of(consumer)}']
        raw = []
        for i in range(c.NC):
            if c.compl(i):
                raw.append(int((((~tag_of(i)) & tmask) ^ exp_of(i)) != 0))      # 1 = mismatch
            else:
                raw.append(int((tag_of(i) ^ exp_of(i)) == 0))                   # 1 = match
        infect = 0
        for s in range(c.INFECT_SPREAD):
            x = tag_of(c.NC) ^ exp_of(c.NC)
            for j in range(c.TAG):
                if (x >> j) & 1:
                    infect |= 1 << ((j + S.INFECT_TAPS[s]) % c.TKW)
        flags = [r[f'flag{i}'] for i in range(c.NC)]
        flags_true = int(all(flags[i] == c.flag_true(i) for i in range(c.NC)))
        flags_false = int(all(flags[i] == c.flag_false(i) for i in range(c.NC)))
        flags_bad = int(any(flags[i] not in (c.flag_true(i), c.flag_false(i)) for i in range(c.NC)))
        if c.CFI_EN:
            ones = (1 << c.STEPW) - 1
            cross_ok = int((r['step'] ^ r['step_n']) == ones)
            cfi_ok = int(r['step'] == c.EXP_STEPS - 1 and cross_ok)
            a_cfi = int((not cross_ok) or (st == ACCEPT and r['step'] != c.EXP_STEPS)
                        or (is_cmp1 and r['step'] != c.EXP_STEPS - 1))
        else:
            cfi_ok, a_cfi = 1, 0
        a_state = int(st not in VALID)
        a_flags = int((st == ACCEPT and not flags_true) or (is_cmp1 and not flags_true and not flags_false)
                      or flags_bad)
        alarm = int(bool(c.ALARM_EN) and (a_state or a_flags or a_cfi))
        # decision word, bit by bit
        dec = 0
        for i in range(8):
            def t(cp):
                if c.FLAG_MUBI:
                    k = i % 4
                    fbit = (flags[cp] >> k) & 1
                    says = fbit if (S.MUBI4_TRUE >> k) & 1 else 1 - fbit
                else:
                    says = flags[cp]
                return says ^ c.compl(cp)
            own = c.owner(i)
            sel = (t(0) & t(1)) if own is None else t(own)
            sel &= cfi_ok
            dec |= (((ACCEPT if sel else REJECT) >> i) & 1) << i
        w.update(clear=clear, is_key=is_key, is_img=is_img, avail=avail, absorb=absorb, round_en=round_en, cap=cap,
                 is_cmp1=is_cmp1, step_inc=step_inc, raw=raw, infect=infect, alarm=alarm, dec=dec,
                 a_state=a_state, a_flags=a_flags, a_cfi=a_cfi, cfi_ok=cfi_ok,
                 tag0=tag_of(0), blk_ready=int(st == LOAD and is_img),
                 busy=int(st in (LOAD, HASH, COMPARE)), done=int(st in (ACCEPT, REJECT, ALARM)))
        return w

    def outputs(self, inp: In, r=None):
        r = self.r if r is None else r
        w = self.comb(inp, r)
        return dict(st=r['st'], boot_word=r['rel'], boot_token=r['tok'], alarm=w['alarm'], blk_ready=w['blk_ready'],
                    busy=w['busy'], done=w['done'], dbg_tag=w['tag0'])

    # ---------------------------------------------------------------- one clock edge
    def step(self, inp: In = None, flips=()):
        c = self.c
        inp = inp or In()
        r = dict(self.r)
        for name, bit in flips:
            if not 0 <= bit < self.width[name]:
                raise ValueError(f'no bit {bit} in register {name}')
            r[name] ^= 1 << bit
        w = self.comb(inp, r)
        out = self.outputs(inp, r)
        n = dict(r)
        st = r['st']
        rst = inp.rst
        clr = rst or w['clear']
        # main FSM: st, blk, rnd, cph, rel
        if rst:
            n['st'], n['blk'], n['rnd'], n['cph'], n['rel'] = IDLE, 0, c.RND_FIRST, 0, IDLE
        else:
            n['rel'] = ALARM if w['alarm'] else st
            if st == IDLE:
                if inp.start:
                    n['st'], n['blk'], n['rnd'], n['cph'] = LOAD, 0, c.RND_FIRST, 0
            elif st == LOAD:
                if w['avail']:
                    n['st'], n['rnd'] = HASH, c.RND_FIRST
            elif st == HASH:
                if r['rnd'] == c.RND_LAST:
                    if r['blk'] == c.NABS - 1:
                        n['st'], n['cph'] = COMPARE, 0
                    else:
                        n['st'], n['blk'] = LOAD, (r['blk'] + 1) & ((1 << c.BLKW) - 1)
                else:
                    n['rnd'] = (r['rnd'] + 1) & 31
            elif st == COMPARE:
                if not r['cph']:
                    n['cph'] = 1
                else:
                    n['st'] = w['dec']
            # ACCEPT, REJECT, ALARM and invalid codes: hold
            if w['alarm']:
                n['st'] = ALARM
        # compare-result flags
        for i in range(c.NC):
            if clr:
                n[f'flag{i}'] = c.flag_false(i)
            elif w['cap']:
                if c.FLAG_MUBI:
                    n[f'flag{i}'] = S.MUBI4_TRUE if w['raw'][i] else S.MUBI4_FALSE
                else:
                    n[f'flag{i}'] = w['raw'][i]
        # token
        if clr or w['alarm']:
            n['tok'] = 0
        elif w['cap']:
            n['tok'] = c.TOKEN ^ w['infect']
        elif st == REJECT:
            n['tok'] = 0
        # step counter pair
        if c.CFI_EN:
            m = (1 << c.STEPW) - 1
            if clr:
                n['step'], n['step_n'] = 0, m
            elif w['step_inc']:
                n['step'], n['step_n'] = (r['step'] + 1) & m, (r['step_n'] - 1) & m
        # hash engines
        for h in range(c.NHASH):
            s = r[f'hash{h}']
            if clr:
                n[f'hash{h}'] = 0
            elif w['absorb']:
                if w['is_key']:
                    blk = (c.KEY >> (r['blk'] * c.R)) & ((1 << c.R) - 1)
                elif w['is_img']:
                    blk = inp.blk_data & ((1 << c.R) - 1)
                else:
                    blk = c.PAD
                n[f'hash{h}'] = s ^ blk
            elif w['round_en']:
                ir = r['rnd']
                n[f'hash{h}'] = K.keccak_round(s, c.W, ir) if ir < 24 else _round_no_rc(s, c.W)
        # expected-value shadow registers
        tmask = (1 << c.TAG) - 1
        for k, rail in enumerate(c.otp_regs()):
            if rst:
                n[f'otp{k}'] = 0
            elif c.EXP_SRC == 0:
                if w['clear']:
                    n[f'otp{k}'] = (~c.EXP_TAG & tmask) if rail else c.EXP_TAG
            elif w['clear']:
                n[f'otp{k}'] = 0
            elif inp.exp_load:
                e = inp.exp_in & tmask
                n[f'otp{k}'] = (~e & tmask) if rail else e
        self.r = n
        self.cycle += 1
        return out

    def reset(self):
        self.r = dict(self.reset_value)
        self.cycle = 0

    def run(self, image_blocks=(), tag_in=0, max_cycles=None, flips=None):
        """Run from power-up with start held high and image blocks always valid. flips: {cycle: [(reg, bit)]}.
        Returns the list of per-cycle outputs."""
        c = self.c
        self.reset()
        n = max_cycles or (c.cycles_to_word() + 3)
        trace = []
        for t in range(n):
            w = self.comb(In())
            bi = self.r['blk'] - c.KB
            data = image_blocks[bi] if (c.HASH_EN and 0 <= bi < len(image_blocks)) else 0
            trace.append(self.step(In(rst=0, start=1, blk_valid=1, blk_data=data, tag_in=tag_in),
                                   flips=(flips or {}).get(t, ())))
        return trace


def _round_no_rc(s, w):
    """Round index 24..31 can only be reached through a fault on `rnd`; the RTL's constant table gives 0 there."""
    t = K.keccak_round(s, w, 0)
    return t ^ (K.RC64[0] & ((1 << w) - 1))
