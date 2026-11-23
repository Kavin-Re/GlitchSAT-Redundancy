"""Cycle-accurate model of rtl/secboot_mmio.v (the 32-bit register front end), written from INTERFACE.md.

One call of Mmio.step(we, addr, wdata) is one rising clock edge; it returns rdata as it is during that cycle (the
read port is combinational in addr), then updates every register, the core included.
"""
from dataclasses import dataclass
from . import spec as S
from .spec import Cfg
from .secboot_model import Core, In

A_CTRL, A_STATUS, A_MSG, A_DIGEST, A_VERDICT, A_TOKEN, A_INFO = 0x00, 0x04, 0x08, 0x20, 0x40, 0x44, 0x48
A_EXPECTED = 0x60          # EXPECTED[i] at 0x60 + 4i, i = 0..7, write-only
CTRL_START, CTRL_FINISH = 1, 2
ST_DONE, ST_ERR, ST_ACCEPT, ST_ALARM, ST_BUSY = 1, 2, 4, 8, 16

MMIO_DEFAULTS = dict(W=64, RATE_LANES=17, TAG_LANES=4, NR=0, KEY_BLOCKS=1, IMG_BLOCKS=2, HASH_EN=1, HASH_COPIES=1,
                     CMP_MODE=2, FLAG_MUBI=1, SEPARATE=1, ALARM_EN=1, INFECT_SPREAD=3, CFI_EN=1, OTP_REG=2, EXP_SRC=1, TKW=32,
                     TOKEN=0xA5C3B007)


def key_block_from_otp(key32: bytes, rate_bytes=136):
    """The core's one key block: the 32 OTP key bytes, then zeros up to the rate (INTERFACE.md, 'Key')."""
    assert len(key32) == 32
    return int.from_bytes(key32 + bytes(rate_bytes - 32), 'little')


def mmio_cfg(**kw):
    p = dict(MMIO_DEFAULTS); p.update(kw)
    return Cfg(**p)


class Mmio:
    def __init__(self, cfg: Cfg):
        assert cfg.HASH_EN and cfg.R % 32 == 0
        self.c = cfg
        self.rw = cfg.R // 32
        self.core = Core(cfg)
        self.reset_regs()

    def reset_regs(self):
        self.go = self.wcnt = self.full = self.nimg = self.err = self.fin = self.aseen = self.stall = 0
        self.words = [0] * self.rw
        self.expected = [0] * 8
        self.core.reset()

    def _core_in(self, rst, exp_load=0):
        blk = 0
        for j, w in enumerate(self.words):
            blk |= w << (32 * j)
        exp = 0
        for i, w in enumerate(self.expected):
            exp |= w << (32 * i)
        return In(rst=rst, start=self.go, blk_valid=int(self.full and not self.err), blk_data=blk, tag_in=0,
                  exp_in=exp & ((1 << self.c.TAG) - 1), exp_load=exp_load, pad_ok=self.fin)

    def verdict(self, co):
        return S.REJECT if self.err else co['boot_word']

    def token(self, co):
        return 0 if self.err else co['boot_token']

    def read(self, addr, co):
        if addr == A_STATUS:
            return (co['busy'] << 4) | (self.aseen << 3) | (int(self.verdict(co) == S.ACCEPT) << 2) | (self.err << 1) \
                   | int(co['done'] or self.err)
        if addr == A_VERDICT:
            return self.verdict(co)
        if addr == A_TOKEN:
            return self.token(co) & 0xFFFFFFFF
        if addr == A_INFO:
            return (self.c.IMG_BLOCKS << 16) | self.rw
        if 0x20 <= addr <= 0x3C and addr % 4 == 0:
            if not co['done']:
                return 0
            return (co['dbg_tag'] >> (32 * ((addr - 0x20) // 4))) & 0xFFFFFFFF
        return 0

    def step(self, we=0, addr=0, wdata=0, rst=0):
        c = self.c
        start_w = int(we and addr == A_CTRL and wdata == CTRL_START)
        finish_w = int(we and addr == A_CTRL and wdata == CTRL_FINISH)
        msg_w = int(we and addr == A_MSG)
        msg_stall = int(msg_w and self.go and self.full and not self.err and not self.fin)
        msg_bad = int(msg_w and not msg_stall and (not self.go or self.fin or self.nimg == c.IMG_BLOCKS))
        msg_ok = int(msg_w and not msg_stall and not msg_bad)
        exp_w = int(we and 0x60 <= addr <= 0x7C and addr % 4 == 0 and self.go and not self.fin)
        exp_load = int(finish_w and self.go and not self.fin)
        self.stall = msg_stall
        cin = self._core_in(int(rst or start_w), exp_load)
        co = self.core.outputs(cin)
        rdata = self.read(addr, co)
        consumed = int(co['blk_ready'] and self.full and not self.err)
        # next state (all registers update together)
        n_words = list(self.words)
        if rst:
            n_words = [0] * self.rw
        elif msg_ok:
            n_words[self.wcnt] = wdata & 0xFFFFFFFF
        n_exp = list(self.expected)
        if rst or start_w:
            n_exp = [0] * 8
        elif exp_w:
            n_exp[(addr - A_EXPECTED) // 4] = wdata & 0xFFFFFFFF
        if rst or start_w:
            ng = dict(go=0 if rst else 1, wcnt=0, full=0, nimg=0, err=0, fin=0, aseen=0)
        else:
            ng = dict(go=self.go, wcnt=self.wcnt, full=self.full, nimg=self.nimg, err=self.err, fin=self.fin, aseen=self.aseen)
            if msg_bad:
                ng['err'] = 1
            if msg_ok:
                if self.wcnt == self.rw - 1:
                    ng['wcnt'], ng['full'], ng['nimg'] = 0, 1, self.nimg + 1
                else:
                    ng['wcnt'] = self.wcnt + 1
            if consumed:
                ng['full'] = 0
            if finish_w:
                ng['fin'] = 1
                if self.wcnt != 0 or self.nimg != c.IMG_BLOCKS:
                    ng['err'] = 1
            if co['alarm']:
                ng['aseen'] = 1
        self.core.step(cin)
        self.words = n_words
        self.expected = n_exp
        for k, val in ng.items():
            setattr(self, k, val)
        return rdata


def boot_sequence(message_words, expected=None):
    """Bus operations of the firmware's mac_image() (hmac_hw.c) for this engine: START, EXPECTED[0..7] (when
    `expected`, a 256-bit int, is given), MSG words, FINISH; run_boot then polls STATUS until DONE and reads
    DIGEST[0..7], VERDICT and TOKEN. Yields (we, addr, wdata, label)."""
    yield 1, A_CTRL, CTRL_START, 'start'
    if expected is not None:
        for i in range(8):
            yield 1, A_EXPECTED + 4 * i, (expected >> (32 * i)) & 0xFFFFFFFF, 'expected'
    for w in message_words:
        yield 1, A_MSG, w, 'msg'
    yield 1, A_CTRL, CTRL_FINISH, 'finish'


def run_boot(m: Mmio, message_words, max_poll=400, expected=None):
    """Drive a whole boot through the bus; returns dict(digest=int, status=int, verdict=int, token=int, polls=n,
    stalls=n, ops=[...]). ops is the list of (we, addr, wdata, rdata, stall) bus cycles (the testbench vectors). A
    stalled write is repeated in the next cycle, as a bus master with wait states does."""
    ops = []
    stalls = [0]
    def op(we, addr, wdata=0):
        while True:
            r = m.step(we, addr, wdata)
            ops.append((we, addr, wdata, r, m.stall))
            if not m.stall:
                return r
            stalls[0] += 1
            if stalls[0] > 100000:
                raise RuntimeError('bus stalled forever')
    for we, addr, wdata, _ in boot_sequence(message_words, expected):
        op(we, addr, wdata)
    polls = 0
    while not (op(0, A_STATUS) & ST_DONE):
        polls += 1
        if polls > max_poll:
            break
    dig = 0
    for i in range(8):
        dig |= op(0, A_DIGEST + 4 * i) << (32 * i)
    status = op(0, A_STATUS)
    verdict = op(0, A_VERDICT)
    token = op(0, A_TOKEN)
    return dict(digest=dig, status=status, verdict=verdict, token=token, polls=polls, stalls=stalls[0], ops=ops)
