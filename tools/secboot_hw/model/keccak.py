"""Keccak-p[25*w, nr] for every lane width w in {1,2,4,8,16,32,64}, written twice from FIPS 202 section 3:

  keccak_p_bits   literal bit-level transcription of the step mappings (3.2.1 - 3.2.5), slow, used as the oracle
  keccak_p        lane-level version (integers per lane), used by the hardware model

Conventions (FIPS 202 3.1.2): lane (x, y) has index i = x + 5*y; bit z of lane i is bit i*w + z of the state
string S. The state is held here as one Python int whose bit number n is S[n].
Nothing in this file is copied from another implementation. The constants (rho offsets, round constants) are
computed by the algorithms in the standard, not typed in. tests/test_keccak.py checks the w = 64 instance against
hashlib (SHA3-256, SHA3-512, SHAKE128), and checks that the two versions agree for every w.
"""

WIDTHS = (1, 2, 4, 8, 16, 32, 64)


def ell(w):
    if w not in WIDTHS:
        raise ValueError(f"lane width {w} not in {WIDTHS}")
    return w.bit_length() - 1


def full_rounds(w):
    return 12 + 2 * ell(w)


def rc_bit(t):
    """Algorithm 5: rc(t)."""
    if t % 255 == 0:
        return 1
    R = [1, 0, 0, 0, 0, 0, 0, 0]
    for _ in range(t % 255):
        R = [0] + R
        R[0] ^= R[8]
        R[4] ^= R[8]
        R[5] ^= R[8]
        R[6] ^= R[8]
        R = R[:8]
    return R[0]


def round_constant64(ir):
    """Algorithm 6 with l = 6: the 64-bit RC for round index ir. Narrower lanes use the low w bits (same rule)."""
    rc = 0
    for j in range(7):
        rc |= rc_bit(j + 7 * ir) << ((1 << j) - 1)
    return rc


def rho_offsets():
    """Algorithm 2 offsets before the mod-w reduction, indexed [x + 5*y]."""
    off = [0] * 25
    x, y = 1, 0
    for t in range(24):
        off[x + 5 * y] = (t + 1) * (t + 2) // 2
        x, y = y, (2 * x + 3 * y) % 5
    return off


RHO = rho_offsets()
RC64 = [round_constant64(i) for i in range(24)]
# rho followed by pi moves lane (x, y) to lane (y, 2x + 3y): destination index for each source index.
PI_DST = [((i // 5) + 5 * ((2 * (i % 5) + 3 * (i // 5)) % 5)) for i in range(25)]


def _rol(v, n, w):
    n %= w
    return ((v << n) | (v >> (w - n))) & ((1 << w) - 1) if n else v


def to_lanes(s, w):
    m = (1 << w) - 1
    return [(s >> (i * w)) & m for i in range(25)]


def from_lanes(a, w):
    s = 0
    for i in range(25):
        s |= a[i] << (i * w)
    return s


def keccak_round(s, w, ir):
    """One round Rnd(A, ir) = iota(chi(pi(rho(theta(A)))), ir), lane-level."""
    m = (1 << w) - 1
    a = to_lanes(s, w)
    c = [a[x] ^ a[x + 5] ^ a[x + 10] ^ a[x + 15] ^ a[x + 20] for x in range(5)]
    d = [c[(x + 4) % 5] ^ _rol(c[(x + 1) % 5], 1, w) for x in range(5)]
    t = [a[i] ^ d[i % 5] for i in range(25)]
    b = [0] * 25
    for i in range(25):
        b[PI_DST[i]] = _rol(t[i], RHO[i], w)
    e = [0] * 25
    for y in range(5):
        for x in range(5):
            e[x + 5 * y] = b[x + 5 * y] ^ (~b[(x + 1) % 5 + 5 * y] & m & b[(x + 2) % 5 + 5 * y])
    e[0] ^= RC64[ir] & m
    return from_lanes(e, w)


def keccak_p(s, w, nr=None):
    """Keccak-p[25w, nr]: rounds ir = 12 + 2l - nr ... 12 + 2l - 1 (FIPS 202 3.3)."""
    full = full_rounds(w)
    nr = full if nr is None else nr
    if not 1 <= nr <= full:
        raise ValueError("nr out of range for this model (1 .. 12 + 2l)")
    for ir in range(full - nr, full):
        s = keccak_round(s, w, ir)
    return s


# ---------------------------------------------------------------- literal bit-level oracle
def keccak_p_bits(s, w, nr=None):
    full = full_rounds(w)
    nr = full if nr is None else nr
    A = [[[(s >> (w * (5 * y + x) + z)) & 1 for z in range(w)] for y in range(5)] for x in range(5)]
    for ir in range(full - nr, full):
        # theta
        C = [[A[x][0][z] ^ A[x][1][z] ^ A[x][2][z] ^ A[x][3][z] ^ A[x][4][z] for z in range(w)] for x in range(5)]
        D = [[C[(x - 1) % 5][z] ^ C[(x + 1) % 5][(z - 1) % w] for z in range(w)] for x in range(5)]
        A = [[[A[x][y][z] ^ D[x][z] for z in range(w)] for y in range(5)] for x in range(5)]
        # rho
        B = [[[0] * w for _ in range(5)] for _ in range(5)]
        B[0][0] = list(A[0][0])
        x, y = 1, 0
        for t in range(24):
            for z in range(w):
                B[x][y][z] = A[x][y][(z - (t + 1) * (t + 2) // 2) % w]
            x, y = y, (2 * x + 3 * y) % 5
        # pi
        A = [[[B[(x + 3 * y) % 5][x][z] for z in range(w)] for y in range(5)] for x in range(5)]
        # chi
        A = [[[A[x][y][z] ^ ((A[(x + 1) % 5][y][z] ^ 1) & A[(x + 2) % 5][y][z]) for z in range(w)]
              for y in range(5)] for x in range(5)]
        # iota
        for j in range(ell(w) + 1):
            A[0][0][(1 << j) - 1] ^= rc_bit(j + 7 * ir)
    out = 0
    for x in range(5):
        for y in range(5):
            for z in range(w):
                out |= A[x][y][z] << (w * (5 * y + x) + z)
    return out


# ---------------------------------------------------------------- sponge (FIPS 202 section 4, pad10*1, suffix 01)
def pad_block(rate_bits):
    """The block absorbed after a message that is a whole number of rate blocks: SHA-3 suffix bits 0,1 then
    pad10*1 = 1, 0..0, 1. As an integer (bit n = n-th bit absorbed): bits 1, 2 and rate-1 set."""
    if rate_bits < 4:
        raise ValueError("rate must be at least 4 bits")
    return 0b110 | (1 << (rate_bits - 1))


def sponge_tag(blocks, w, rate_lanes, tag_lanes, nr=None, perm=keccak_p):
    """KECCAK-style sponge over whole rate blocks `blocks` (ints of rate_lanes*w bits), then the suffix/pad
    block, then the first tag_lanes lanes of the state. With w = 64, rate_lanes = 17, tag_lanes = 4, nr = 24 this
    is SHA3-256 of the concatenated blocks."""
    if not 1 <= tag_lanes <= rate_lanes <= 24:
        raise ValueError("need 1 <= tag_lanes <= rate_lanes <= 24")
    r = rate_lanes * w
    s = 0
    for blk in list(blocks) + [pad_block(r)]:
        if blk >> r:
            raise ValueError("block wider than the rate")
        s = perm(s ^ blk, w, nr)
    return s & ((1 << (tag_lanes * w)) - 1)
