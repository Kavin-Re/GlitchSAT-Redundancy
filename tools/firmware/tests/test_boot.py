"""Functional correctness of every built boot ROM: good images boot, and
every tampered, rolled-back or malformed image is refused (no faults)."""
import glob
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from faultsim import image  # noqa: E402
from rv32sim import Machine, load_elf  # noqa: E402
from rv32sim.cpu import FLASH_BASE, IMAGE, OUTCOME_NAMES  # noqa: E402

ELFS = sorted(glob.glob(os.path.join(ROOT, "elf", "rom_*.elf")))
FAST = os.environ.get("FW_FULL") is None   # default: hw-engine builds + O2 software builds


def selected():
    if not FAST:
        return ELFS
    return [e for e in ELFS if e.endswith("-hw.elf") or e.endswith("-sha3.elf") or "-O2-" in e]


@pytest.mark.skipif(not ELFS, reason="run scripts/build.py first")
@pytest.mark.parametrize("elf", selected(), ids=lambda e: os.path.basename(e)[:-4])
def test_scenarios(elf):
    p = load_elf(elf)
    otp = image.otp()
    for name, (img, should_boot) in image.scenarios(image.mac_kind(p)).items():
        m = Machine(p, img, otp)
        m.run(300000)
        assert (m.outcome == IMAGE) == should_boot, (name, OUTCOME_NAMES[m.outcome])
        if should_boot:
            entry = 16 if name == "good_entry_offset" else 0
            assert m.entry == FLASH_BASE + 0x30 + entry
            assert m.status == 0xB007
        else:
            assert OUTCOME_NAMES[m.outcome] == "reject", name


def test_hw_engine_matches_python_hmac():
    import hashlib
    import hmac
    elf = os.path.join(ROOT, "elf", "rom_naive-O2-plain-hw.elf")
    if not os.path.exists(elf):
        pytest.skip("not built")
    m = Machine(load_elf(elf), image.make_image(), image.otp())
    m.run(10000)
    img = image.make_image()
    assert m.hm_dig == hmac.new(image.OTP_KEY, img[:16] + img[0x30:0x70], hashlib.sha256).digest()


def test_sha3_engine_digest_and_verdict():
    """The simulator's SHA3 engine: digest = SHA3-256(K136 || 1088-byte message), hardware verdict and
    token follow the EXPECTED registers written by mac_sha3_hw.c."""
    import hashlib
    elf = os.path.join(ROOT, "elf", "rom_naive-O2-plain-sha3.elf")
    if not os.path.exists(elf):
        pytest.skip("not built")
    p = load_elf(elf)
    assert p.engine == "sha3"
    good = image.scenarios("sha3")["good"][0]
    m = Machine(p, good, image.otp())
    m.run(10 ** 5)
    assert m.outcome == IMAGE
    msg = good[:16] + good[0x30:0x70] + bytes(1088 - 16 - 64)
    assert m.hm_msg == msg
    assert m.hm_dig == hashlib.sha3_256(image.OTP_KEY + bytes(104) + msg).digest() == good[0x10:0x30]
    assert m.load(0x50000040, 4, False) == 0x96 and m.load(0x50000044, 4, False) == 0xA5C3B007
    bad = image.scenarios("sha3")["tampered_payload"][0]
    m = Machine(p, bad, image.otp())
    m.run(10 ** 5)
    assert OUTCOME_NAMES[m.outcome] == "reject"
    assert m.load(0x50000040, 4, False) == 0x69 and m.load(0x50000044, 4, False) == 0


HW = os.environ.get("SECBOOT_HW", os.path.join(os.path.dirname(ROOT), "secboot_hw"))


@pytest.mark.skipif(not os.path.exists(os.path.join(HW, "model", "mmio_model.py")),
                    reason="secboot_hw not next to firmware/")
def test_sha3_engine_matches_secboot_hw_model():
    """Replay the exact bus writes of mac_sha3_hw.c (START, 272 MSG words, EXPECTED[0..7], FINISH) on the
    hardware's own register model (secboot_hw/model/mmio_model.py, IMG_BLOCKS = 8, EXPECTED from the bus):
    same digest, and ACCEPT with the release token for a good image, REJECT for a tampered one."""
    sys.path.insert(0, HW)
    from model import mmio_model as MM
    if not hasattr(MM, "A_EXPECTED"):
        pytest.skip("secboot_hw model has no EXPECTED registers")
    p = load_elf(os.path.join(ROOT, "elf", "rom_naive-O2-plain-sha3.elf"))

    class Logged(Machine):
        __slots__ = ("bus",)

        def _sha3_store(self, o, v):
            self.bus.append((o, v))
            return Machine._sha3_store(self, o, v)

    for name, accept in (("good", True), ("tampered_payload", False)):
        img = image.scenarios("sha3")[name][0]
        m = Logged(p, img, image.otp())
        m.bus = []
        m.run(10 ** 5)
        assert m.bus[0] == (0, 1) and m.bus[-1] == (0, 2) and len(m.bus) == 1 + 272 + 8 + 1
        hw = MM.Mmio(MM.mmio_cfg(IMG_BLOCKS=8, KEY=MM.key_block_from_otp(image.OTP_KEY)))
        for o, v in m.bus:
            while True:
                hw.step(1, o, v)
                if not hw.stall:
                    break
        for _ in range(5000):
            if hw.step(0, MM.A_STATUS) & MM.ST_DONE:
                break
        dig = sum(hw.step(0, MM.A_DIGEST + 4 * i) << (32 * i) for i in range(8))
        assert dig.to_bytes(32, "little") == m.hm_dig
        assert (hw.step(0, MM.A_VERDICT) == 0x96) == accept == (m.load(0x50000040, 4, False) == 0x96)
        assert (hw.step(0, MM.A_TOKEN) == 0xA5C3B007) == accept == (m.load(0x50000044, 4, False) == 0xA5C3B007)
