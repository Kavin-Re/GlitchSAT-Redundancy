"""The C header (src/mmio.h, src/image.h) and the simulator agree on the map."""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from rv32sim import cpu  # noqa: E402
from faultsim import image  # noqa: E402


def defines(*files):
    d = {}
    for f in files:
        for m in re.finditer(r"#define\s+(\w+)\s+(0x[0-9A-Fa-f]+|\d+)u?\b", open(os.path.join(ROOT, "src", f)).read()):
            d[m.group(1)] = int(m.group(2), 0)
    return d


def test_memory_map_matches():
    d = defines("mmio.h", "image.h")
    assert d["ROM_BASE"] == cpu.ROM_BASE
    assert d["RAM_BASE"] == cpu.RAM_BASE
    assert d["FLASH_BASE"] == cpu.FLASH_BASE
    assert d["SYSCTRL_BASE"] == cpu.SYSCTRL
    assert d["OTP_BASE"] == cpu.OTP_BASE
    assert d["HMAC_BASE"] == cpu.HMAC_BASE
    assert d["FLASH_EXEC_KEY"] == cpu.FLASH_EXEC_KEY
    assert d["HMAC_SIZE"] == cpu.HMAC_SIZE == 0x80
    assert (d["HMAC_VERDICT"], d["HMAC_TOKEN"], d["HMAC_INFO"], d["HMAC_EXPECTED"]) == (0x40, 0x44, 0x48, 0x60)
    assert cpu.SHA3_BLOCKS * cpu.SHA3_WORDS_PER_BLOCK * 4 == image.SHA3_MSG_BYTES == 1088
    assert d["IMG_MAGIC"] == image.MAGIC and d["IMG_HDR_SIZE"] == image.HDR
    assert d["OTP_MIN_VERSION"] == 0x20 and d["OTP_MIN_VERSION_INV"] == 0x24
    assert len(image.otp()) == cpu.OTP_SIZE


def test_linker_script_matches():
    s = open(os.path.join(ROOT, "src", "link.ld")).read()
    assert "ORIGIN = 0x00000000, LENGTH = 16K" in s and cpu.ROM_SIZE == 16 * 1024
    assert "ORIGIN = 0x10000000, LENGTH = 4K" in s and cpu.RAM_SIZE == 4 * 1024


def test_crt0_exec_key():
    s = open(os.path.join(ROOT, "src", "crt0.S")).read()
    assert "0xA5C3B007" in s
