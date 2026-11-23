import hashlib, random
import pytest
from model import keccak as K


def test_constants_from_the_standard_algorithms():
    # Spot values that anyone can compare with FIPS 202 Table 2 / the usual 64-bit round-constant list.
    assert K.RC64[0] == 0x0000000000000001
    assert K.RC64[1] == 0x0000000000008082
    assert K.RC64[23] == 0x8000000080008008
    assert K.RHO[1] == 1 and K.RHO[0] == 0
    assert sorted(o % 64 for o in K.RHO) == sorted([0, 1, 62, 28, 27, 36, 44, 6, 55, 20, 3, 10, 43, 25, 39, 41, 45,
                                                    15, 21, 8, 18, 2, 61, 56, 14])
    assert sorted(K.PI_DST) == list(range(25))


def _sha3(data, rate_bytes, out_bytes, perm, suffix=0x06):
    r = rate_bytes * 8
    msg = bytearray(data)
    msg.append(suffix)
    while len(msg) % rate_bytes:
        msg.append(0)
    msg[-1] |= 0x80
    s = 0
    for o in range(0, len(msg), rate_bytes):
        s = perm(s ^ int.from_bytes(msg[o:o + rate_bytes], 'little'), 64, 24)
    assert out_bytes <= rate_bytes
    return (s & ((1 << (8 * out_bytes)) - 1)).to_bytes(out_bytes, 'little')


@pytest.mark.parametrize('n', [0, 1, 3, 135, 136, 137, 300])
def test_w64_matches_hashlib_sha3_256(n):
    data = bytes((i * 7 + 3) & 0xFF for i in range(n))
    assert _sha3(data, 136, 32, K.keccak_p) == hashlib.sha3_256(data).digest()


def test_w64_matches_hashlib_sha3_512_and_shake128():
    data = b'GlitchSAT secure boot subsystem'
    assert _sha3(data, 72, 64, K.keccak_p) == hashlib.sha3_512(data).digest()
    assert _sha3(data, 168, 32, K.keccak_p, suffix=0x1F) == hashlib.shake_128(data).digest(32)


def test_bit_level_oracle_matches_hashlib_once():
    data = b'abc'
    assert _sha3(data, 136, 32, K.keccak_p_bits) == hashlib.sha3_256(data).digest()


@pytest.mark.parametrize('w', K.WIDTHS)
def test_lane_and_bit_versions_agree_for_every_width(w):
    rng = random.Random(1000 + w)
    full = K.full_rounds(w)
    for trial in range(12 if w < 64 else 3):
        s = rng.getrandbits(25 * w)
        for nr in {1, 2, full - 1, full}:
            assert K.keccak_p(s, w, nr) == K.keccak_p_bits(s, w, nr)


def test_reduced_round_instances_use_the_last_rounds():
    s = 0x1234567
    w = 2
    full = K.full_rounds(w)
    t = s
    for ir in range(full - 3, full):
        t = K.keccak_round(t, w, ir)
    assert K.keccak_p(s, w, 3) == t


def test_w1_permutation_is_a_bijection_on_a_sample():
    seen = {K.keccak_p(s, 1) for s in range(1 << 14)}
    assert len(seen) == 1 << 14


def test_sponge_tag_is_sha3_256_for_the_full_size_parameters():
    rng = random.Random(7)
    blocks = [rng.getrandbits(1088) for _ in range(3)]
    data = b''.join(b.to_bytes(136, 'little') for b in blocks)
    tag = K.sponge_tag(blocks, 64, 17, 4, 24)
    assert tag.to_bytes(32, 'little') == hashlib.sha3_256(data).digest()


def test_pad_block_shape():
    assert K.pad_block(1088).to_bytes(136, 'little') == b'\x06' + b'\x00' * 134 + b'\x80'
    assert K.pad_block(4) == 0b1110
