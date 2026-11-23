"""Boot images and OTP contents for the simulated SoC (layout: src/image.h).

The MAC is computed here with Python's hashlib/hmac, independently of the C
code, so a good image booting in the simulator checks the C HMAC-SHA-256.
"""
import hashlib
import hmac
import struct

from rv32sim.cpu import make_otp

MAGIC = 0x49425347
HDR = 0x30
OTP_KEY = bytes(range(0x40, 0x60))   # demo provisioning key (not secret: a model)
MIN_VERSION = 5

# payload: a tiny program at offset 0 (the simulator stops at the first fetch
# from flash, so only the entry address matters), then filler data
PAYLOAD_CODE = bytes.fromhex(
    "b7020030"   # lui  t0, 0x30000
    "37b3d016"   # lui  t1, 0x16d0b      (marker)
    "23a06200"   # sw   t1, 0(t0)
    "6f000000"   # j    .
)


def payload(n=64, fill=0x11):
    body = bytearray(PAYLOAD_CODE)
    while len(body) < n:
        body.append((fill + len(body)) & 0xFF)
    return bytes(body[:n])


SHA3_RATE = 136            # SHA3-256 rate in bytes
SHA3_BLOCKS = 8            # IMG_BLOCKS of the SoC build; the RTL default is 2 (secboot_hw model MMIO_DEFAULTS)
SHA3_MSG_BYTES = SHA3_BLOCKS * SHA3_RATE   # message length of the SHA3-256 engine in the SoC build


def compute_mac(head, body, key=OTP_KEY, mac="hmac", blocks=SHA3_BLOCKS):
    """The header mac field.
    hmac: HMAC-SHA-256(key, head || body)                      (hmac_sw.c, hmac_hw.c)
    sha3: SHA3-256(key || 104 zero bytes || head || body || zeros up to blocks*136 B)
          (the secboot_hw engine, mac_sha3_hw.c). blocks = IMG_BLOCKS of the build; 8 (1088 B)
          for the SoC build, which is the only value the firmware and its tests assume."""
    if mac == "hmac":
        return hmac.new(key, head + body, hashlib.sha256).digest()
    if mac == "sha3":
        m = head + body
        total = blocks * SHA3_RATE
        assert len(m) <= total
        return hashlib.sha3_256(key + bytes(SHA3_RATE - len(key)) + m + bytes(total - len(m))).digest()
    raise ValueError(mac)


def make_image(version=MIN_VERSION, body=None, entry=0, key=OTP_KEY, magic=MAGIC, length=None, mac="hmac"):
    body = payload() if body is None else body
    length = len(body) if length is None else length
    head = struct.pack("<IIII", magic, version, length, entry)
    tag = compute_mac(head, body[:length], key, mac)
    return head + tag + body


def tamper_payload(img, offset=8, xor=0x01):
    """Change one payload byte, keep the old MAC (the attacker cannot compute a MAC)."""
    b = bytearray(img)
    b[HDR + offset] ^= xor
    return bytes(b)


def otp(min_version=MIN_VERSION, key=OTP_KEY):
    return make_otp(key, min_version)


# The scenarios used everywhere (name -> (image bytes, should_boot))
def mac_kind(prog):
    """Which mac formula a built ROM checks: 'sha3' for the secboot_hw engine builds, else 'hmac'."""
    return "sha3" if getattr(prog, "engine", "hmac") == "sha3" else "hmac"


def scenarios(mac="hmac"):
    def make_image_(**kw):
        return make_image(mac=mac, **kw)
    good = make_image_()
    return {
        "good": (good, True),
        "good_newer_version": (make_image_(version=MIN_VERSION + 3), True),
        "good_entry_offset": (make_image_(entry=16), True),
        "tampered_payload": (tamper_payload(good), False),
        "tampered_mac": (good[:0x10] + bytes([good[0x10] ^ 0x80]) + good[0x11:], False),
        "tampered_version_field": (good[:4] + struct.pack("<I", MIN_VERSION + 1) + good[8:], False),
        "rollback_signed_old": (make_image_(version=MIN_VERSION - 1), False),
        "wrong_key": (make_image_(key=bytes(32)), False),
        "bad_magic": (make_image_(magic=0x12345678), False),
        "length_too_big": (make_image(length=2048, body=payload(64)), False),
        "length_unaligned": (make_image(length=62, body=payload(64)), False),
        "entry_out_of_range": (make_image_(entry=64), False),
        "erased_flash": (b"\xff" * 0x100, False),
    }
