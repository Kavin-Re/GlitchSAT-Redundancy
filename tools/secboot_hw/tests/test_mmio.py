"""Register front end (model/mmio_model.py, the reference for rtl/secboot_mmio.v and tb/gen/tb_mmio.v)."""
import hashlib, os, re
import pytest
from model import spec as S
from model.mmio_model import (Mmio, mmio_cfg, key_block_from_otp, run_boot, A_CTRL, A_STATUS, A_MSG, A_DIGEST,
                              A_VERDICT, A_TOKEN, A_INFO, A_EXPECTED, ST_DONE, ST_ERR, ST_ACCEPT)
from engine import benches

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FW = os.path.join(os.path.dirname(HERE), 'firmware')
FLASH_EXEC_KEY = 0xA5C3B007


@pytest.fixture(scope='module')
def results():
    return benches.mmio_ops()[2]


def test_genuine_boot_digest_is_sha3_256_of_key_block_and_message(results):
    cfg, msg, words, d = benches.mmio_setup()
    r = results['genuine']
    assert r['digest'].to_bytes(32, 'little') == d
    assert r['digest'].to_bytes(32, 'little') == hashlib.sha3_256(benches.OTP_KEY32 + bytes(104) + msg).digest()
    assert r['status'] & (ST_DONE | ST_ACCEPT) == ST_DONE | ST_ACCEPT and not r['status'] & ST_ERR
    assert r['verdict'] == S.ACCEPT and r['token'] == FLASH_EXEC_KEY
    assert r['stalls'] >= 1          # the second block's first word waits for the core


def test_tampered_short_long_all_reject(results):
    assert results['tampered']['verdict'] == S.REJECT and results['tampered']['token'] == 0
    assert results['tampered']['digest'] != 0
    for name in ('short', 'long'):
        r = results[name]
        assert r['status'] & ST_ERR and r['status'] & ST_DONE
        assert r['verdict'] == S.REJECT and r['token'] == 0 and r['digest'] == 0


def test_restart_and_repeat_boot(results):
    for name in ('genuine_again', 'restart'):
        assert results[name]['verdict'] == S.ACCEPT and results[name]['token'] == FLASH_EXEC_KEY


def test_digest_reads_zero_until_done_and_info_register():
    cfg, msg, words, d = benches.mmio_setup()
    m = Mmio(cfg)
    m.step(1, A_CTRL, 1)
    for w in words[:34]:
        m.step(1, A_MSG, w)
    assert all(m.step(0, A_DIGEST + 4 * i) == 0 for i in range(8))
    assert m.step(0, A_INFO) == (2 << 16) | 34


def test_key_block_layout():
    k = key_block_from_otp(bytes(range(32)))
    assert k.to_bytes(136, 'little') == bytes(range(32)) + bytes(104)


def test_offsets_agree_with_the_firmware_header_when_present():
    p = os.path.join(FW, 'src', 'mmio.h')
    if not os.path.isfile(p):
        pytest.skip('firmware/src/mmio.h not present')
    t = open(p).read()
    def d(name):
        return int(re.search(rf'#define {name}\s+(0x[0-9A-Fa-f]+)u', t).group(1), 16)
    assert (d('HMAC_CTRL'), d('HMAC_STATUS'), d('HMAC_MSG'), d('HMAC_DIGEST')) == (A_CTRL, A_STATUS, A_MSG, A_DIGEST)
    assert d('FLASH_EXEC_KEY') == FLASH_EXEC_KEY == benches.mmio_setup()[0].TOKEN


def test_rtl_offsets_agree_with_model():
    t = open(os.path.join(HERE, 'rtl', 'secboot_mmio.v')).read()
    for name, val in (('A_CTRL', A_CTRL), ('A_STATUS', A_STATUS), ('A_MSG', A_MSG), ('A_VERDICT', A_VERDICT),
                      ('A_TOKEN', A_TOKEN), ('A_INFO', A_INFO)):
        assert re.search(rf"{name} = 8'h{val:02X}", t), name
    assert "TOKEN   = 32'hA5C3B007" in t


# ---------- expected tag from the bus (EXPECTED[0..7], EXP_SRC = 1)

def test_default_bus_build_takes_the_expected_tag_from_the_bus():
    cfg = benches.mmio_setup()[0]
    assert cfg.EXP_SRC == 1 and cfg.OTP_REG == 2 and cfg.EXP_TAG == 0      # the parameter is not used


def test_one_build_accepts_a_second_image_with_its_own_tag(results):
    _, msg2, words2, d2 = (None,) + benches.mmio_second_image()
    r = results['second_image']
    assert r['digest'].to_bytes(32, 'little') == d2 == hashlib.sha3_256(benches.OTP_KEY32 + bytes(104) + msg2).digest()
    assert r['verdict'] == S.ACCEPT and r['token'] == FLASH_EXEC_KEY


def test_wrong_missing_or_late_expected_tag_rejects(results):
    d = benches.mmio_setup()[3]
    for name in ('wrong_expected', 'no_expected', 'late_expected'):
        r = results[name]
        assert r['digest'].to_bytes(32, 'little') == d, name          # the image itself is genuine
        assert r['verdict'] == S.REJECT and r['token'] == 0, name
        assert not r['status'] & ST_ERR and r['status'] & ST_DONE, name
    late = results['late_expected']
    assert late['late_verdict'] == S.REJECT and late['late_token'] == 0 and late['late_expected_read'] == 0


def test_pad_block_waits_for_finish_and_shadow_registers_hold_the_bus_value():
    cfg, msg, words, d = benches.mmio_setup()
    e = int.from_bytes(d, 'little')
    m = Mmio(cfg)
    m.step(1, A_CTRL, 1)
    for i in range(8):
        m.step(1, A_EXPECTED + 4 * i, (e >> (32 * i)) & 0xFFFFFFFF)
    for w in words:
        while True:
            m.step(1, A_MSG, w)
            if not m.stall:
                break
    for _ in range(300):                   # no FINISH yet: the core never leaves the pad block's LOAD
        assert not m.step(0, A_STATUS) & ST_DONE
    assert all(m.core.r[f'otp{k}'] == 0 for k in range(len(cfg.otp_regs())))
    m.step(1, A_CTRL, 2)
    assert all(m.core.r[f'otp{k}'] == e for k in range(len(cfg.otp_regs())))
    polls = 0
    while not m.step(0, A_STATUS) & ST_DONE:
        polls += 1
        assert polls < 400
    assert m.step(0, A_VERDICT) == S.ACCEPT and m.step(0, A_TOKEN) == FLASH_EXEC_KEY


def test_parameter_build_ignores_expected_writes():
    cfg, msg, words, d = benches.mmio_setup()
    e = int.from_bytes(d, 'little')
    for exp_tag, want in ((e, S.ACCEPT), (0, S.REJECT)):
        m = Mmio(cfg.but(EXP_SRC=0, EXP_TAG=exp_tag))
        r = run_boot(m, words, expected=e)
        assert r['verdict'] == want


def test_rtl_has_expected_registers_and_passes_exp_src():
    t = open(os.path.join(HERE, 'rtl', 'secboot_mmio.v')).read()
    assert re.search(rf"A_EXPECTED = 8'h{A_EXPECTED:02X}", t) and A_EXPECTED == 0x60
    assert 'parameter EXP_SRC       = 1' in t and '.EXP_SRC(EXP_SRC)' in t
    assert '.exp_in(exp_tag_bus), .exp_load(exp_load), .pad_ok(fin)' in t
    c = open(os.path.join(HERE, 'rtl', 'secboot_core.v')).read()
    assert 'parameter EXP_SRC       = 0' in c and 'q <= ORAIL ? ~exp_in : exp_in;' in c
