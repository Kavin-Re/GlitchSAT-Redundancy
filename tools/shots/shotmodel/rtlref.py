"""Hand transcription of the RTL (rtl/v1.v, rtl/v2.v, rtl/v2e.v, rtl/v0.v) as next-state / output functions.

Used as the reference in the exhaustive equivalence check of the placed netlists (equiv.py). The text of each function
follows the Verilog line by line; the Verilog itself is not parsed (no Verilog simulator is needed).
"""
KEY, GOOD, BAD = 0xC3, 0x96, 0x69


def _m(sig):
    return 1 if sig == KEY else 0


def v1_next(st, sig):
    ok = _m(sig) & _m(sig)                       # two cmp8 copies, ok = m1 & m2
    if st == 0xF0:
        return 0xCC
    if st == 0xCC:
        return GOOD if ok else BAD
    return st


def _v2_word(sig):
    m0 = m1 = m2 = _m(sig)
    sel = [m0, m1, m2, m0, m1, m2, m0, m1]       # sel = {m1,m0,m2,m1,m0,m2,m1,m0}, listed LSB first
    return sum((((GOOD >> i) & 1) if sel[i] else ((BAD >> i) & 1)) << i for i in range(8))


def v2_next(st, sig, armed=0xCC):
    if st == 0xF0:
        return armed
    if st == armed:
        return _v2_word(sig)
    return st


def v2e_next(st, sig):
    return v2_next(st, sig, armed=0xA5)


def out(st):
    """(boot_word, boot_ok) of V1, V2, V2e"""
    return st, 1 if st == GOOD else 0


NEXT = {"v1": v1_next, "v2": v2_next, "v2e": v2e_next}
