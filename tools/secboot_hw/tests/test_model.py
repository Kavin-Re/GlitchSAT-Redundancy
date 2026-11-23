import hashlib, itertools, random
import pytest
from model import spec as S
from model.spec import Cfg, IDLE, LOAD, HASH, COMPARE, ALARM, ACCEPT, REJECT
from model.secboot_model import Core, In, mac
from tools import encoding_analysis


def decision_cfg(**kw):
    base = dict(W=4, RATE_LANES=4, TAG_LANES=4, HASH_EN=0, EXP_TAG=0xC35A, TKW=8, TOKEN=0xDE)
    base.update(kw)
    return Cfg(**base)


ALL_DECISION = [dict(CMP_MODE=m, FLAG_MUBI=f, ALARM_EN=a, CFI_EN=c, INFECT_SPREAD=i, OTP_REG=o)
                for m in range(4) for f in (0, 1) for a in (0, 1) for c in (0, 1) for i in (0, 3) for o in (0, 1, 2)]


def test_state_code_rules_hold():
    assert encoding_analysis.analyse()['errors'] == []


@pytest.mark.parametrize('kw', ALL_DECISION)
def test_decision_only_accepts_exactly_the_expected_tag(kw):
    cfg = decision_cfg(**kw)
    m = Core(cfg)
    tr = m.run(tag_in=cfg.EXP_TAG)
    t = cfg.cycles_to_word()
    assert t == 6
    assert tr[t]['boot_word'] == ACCEPT and tr[t]['boot_token'] == cfg.TOKEN
    assert all(o['boot_word'] != ACCEPT for o in tr[:t])
    assert not any(o['alarm'] for o in tr)
    rng = random.Random(5)
    bad = [cfg.EXP_TAG ^ (1 << b) for b in range(cfg.TAG)] + [rng.getrandbits(cfg.TAG) for _ in range(20)]
    for tag in bad:
        if tag == cfg.EXP_TAG:
            continue
        tr = m.run(tag_in=tag)
        assert all(o['boot_word'] != ACCEPT for o in tr)
        assert tr[t]['boot_word'] == REJECT and tr[-1]['boot_token'] == 0
        assert not any(o['alarm'] for o in tr)


def test_state_sequence_and_cycle_formula_decision_only():
    m = Core(decision_cfg(CMP_MODE=2))
    tr = m.run(tag_in=0xC35A, max_cycles=8)
    assert [o['st'] for o in tr] == [IDLE, LOAD, HASH, COMPARE, COMPARE, ACCEPT, ACCEPT, ACCEPT]
    assert [o['boot_word'] for o in tr][5:8] == [COMPARE, ACCEPT, ACCEPT]


def hash_cfg(**kw):
    base = dict(W=2, RATE_LANES=8, TAG_LANES=8, NR=3, KEY_BLOCKS=1, IMG_BLOCKS=1, KEY=0xB3C5, TKW=8, TOKEN=0xDE,
                CMP_MODE=2)
    base.update(kw)
    cfg = Cfg(**base)
    return cfg


@pytest.mark.parametrize('kw', [dict(), dict(HASH_COPIES=2), dict(NR=0), dict(W=1, KEY=0xA7), dict(W=8, RATE_LANES=4, TAG_LANES=4, KEY=0x1234ABCD, KEY_BLOCKS=1, IMG_BLOCKS=3, NR=0),
                                dict(KEY_BLOCKS=2, KEY=0x1234B3C5, IMG_BLOCKS=2, CFI_EN=1, ALARM_EN=1, FLAG_MUBI=1, INFECT_SPREAD=2, OTP_REG=2, HASH_COPIES=2)])
def test_hash_flow_tag_equals_reference_mac_and_accepts(kw):
    cfg = hash_cfg(**kw)
    rng = random.Random(11)
    img = [rng.getrandbits(cfg.R) for _ in range(cfg.IMG_BLOCKS)]
    cfg = cfg.but(EXP_TAG=mac(cfg, img))
    m = Core(cfg)
    tr = m.run(image_blocks=img)
    t = cfg.cycles_to_word()
    assert tr[t]['boot_word'] == ACCEPT and tr[t - 1]['boot_word'] != ACCEPT
    assert tr[t]['dbg_tag'] == cfg.EXP_TAG
    assert not any(o['alarm'] for o in tr)
    img2 = list(img); img2[-1] ^= 1
    tr = m.run(image_blocks=img2)
    assert tr[t]['boot_word'] == REJECT and all(o['boot_word'] != ACCEPT for o in tr)


def test_full_size_configuration_is_sha3_256_of_key_and_image():
    rng = random.Random(3)
    key = rng.getrandbits(1088)
    img = [rng.getrandbits(1088) for _ in range(2)]
    cfg = Cfg(W=64, RATE_LANES=17, TAG_LANES=4, NR=0, KEY_BLOCKS=1, IMG_BLOCKS=2, KEY=key, TKW=32, TOKEN=0xB007C0DE)
    digest = hashlib.sha3_256(b''.join(v.to_bytes(136, 'little') for v in [key] + img)).digest()
    cfg = cfg.but(EXP_TAG=int.from_bytes(digest, 'little'))
    tr = Core(cfg).run(image_blocks=img)
    t = cfg.cycles_to_word()
    assert t == 1 + 4 * 25 + 3
    assert tr[t]['boot_word'] == ACCEPT and tr[t]['boot_token'] == 0xB007C0DE
    assert tr[t]['dbg_tag'].to_bytes(32, 'little') == digest


def test_image_stream_stalls_until_valid_and_reset_restarts():
    cfg = hash_cfg()
    img = [0x1234]
    cfg = cfg.but(EXP_TAG=mac(cfg, img))
    m = Core(cfg)
    seen_ready = 0
    out = None
    for t in range(60):
        w = m.comb(In())
        valid = 1 if t > 20 else 0
        out = m.step(In(start=1, blk_valid=valid, blk_data=img[0] if valid else 0xFFFF))
        seen_ready += out['blk_ready']
    assert out['boot_word'] == ACCEPT
    assert seen_ready >= 15
    m.step(In(rst=1))
    assert m.r == m.reset_value
    out = [m.step(In(start=0)) for _ in range(5)][-1]
    assert out['st'] == IDLE and out['busy'] == 0


def test_alarm_on_invalid_state_and_on_accept_without_evidence():
    cfg = decision_cfg(CMP_MODE=2, ALARM_EN=1)
    m = Core(cfg)
    tr = m.run(tag_in=cfg.EXP_TAG, flips={2: [('st', 0)]})
    assert tr[2]['alarm'] == 1 and tr[3]['st'] == ALARM and tr[-1]['boot_word'] == ALARM
    # four state-register flips turn REJECT-bound COMPARE into ACCEPT only through an invalid word; here: force
    # ACCEPT directly in the state register with a wrong tag (8 - 4 = 4 flips from COMPARE)
    diff = COMPARE ^ ACCEPT
    flips = [('st', b) for b in range(8) if diff >> b & 1]
    tr = m.run(tag_in=cfg.EXP_TAG ^ 1, flips={3: flips})
    assert tr[3]['st'] == ACCEPT and tr[3]['alarm'] == 1
    assert all(o['boot_word'] != ACCEPT for o in tr)
    # without the alarm the same four flips release the accept word
    m0 = Core(cfg.but(ALARM_EN=0))
    tr = m0.run(tag_in=cfg.EXP_TAG ^ 1, flips={3: flips})
    assert any(o['boot_word'] == ACCEPT for o in tr)


def test_step_counter_detects_a_skipped_step():
    cfg = decision_cfg(CMP_MODE=2, CFI_EN=1, ALARM_EN=0)
    m = Core(cfg)
    # flip LOAD -> COMPARE in the state register (4 bits): the step count is then one short at the decision
    diff = LOAD ^ COMPARE
    tr = m.run(tag_in=cfg.EXP_TAG, flips={1: [('st', b) for b in range(8) if diff >> b & 1]})
    assert all(o['boot_word'] != ACCEPT for o in tr) and tr[-1]['boot_word'] == REJECT
    m1 = Core(cfg.but(CFI_EN=0))
    tr = m1.run(tag_in=cfg.EXP_TAG, flips={1: [('st', b) for b in range(8) if diff >> b & 1]})
    assert tr[-1]['boot_word'] == ACCEPT       # same faults, genuine tag: flow is shorter but still accepts
    m2 = Core(cfg.but(ALARM_EN=1))
    tr = m2.run(tag_in=cfg.EXP_TAG, flips={1: [('st', b) for b in range(8) if diff >> b & 1]})
    assert tr[-1]['boot_word'] == ALARM


def test_infection_changes_the_token_for_every_single_bit_tag_error():
    for spread in (1, 2, 3):
        cfg = decision_cfg(CMP_MODE=0, INFECT_SPREAD=spread)
        m = Core(cfg)
        for b in range(cfg.TAG):
            m.reset()
            for _ in range(4):
                m.step(In(tag_in=cfg.EXP_TAG ^ (1 << b)))
            assert bin(m.r['tok'] ^ cfg.TOKEN).count('1') == spread


def test_mubi_flag_values():
    cfg = decision_cfg(CMP_MODE=3, FLAG_MUBI=1)
    m = Core(cfg)
    assert (m.r['flag0'], m.r['flag1']) == (S.MUBI4_FALSE, S.MUBI4_TRUE)     # reset = "no match" on both rails
    for _ in range(4):
        m.step(In(tag_in=cfg.EXP_TAG))
    assert (m.r['flag0'], m.r['flag1']) == (S.MUBI4_TRUE, S.MUBI4_FALSE)     # match: true rail 6, complement rail 9


# ---------- expected tag from a port (EXP_SRC = 1, used by the bus front end)

def _run_exp_src(cfg, img, exp, load_at, pad_ok_at, n):
    """Core with EXP_SRC = 1: exp_load pulses at cycle load_at, pad_ok goes high from cycle pad_ok_at."""
    m = Core(cfg)
    tr = []
    for t in range(n):
        bi = m.r['blk'] - cfg.KB
        data = img[bi] if 0 <= bi < len(img) else 0
        tr.append(m.step(In(start=1, blk_valid=1, blk_data=data, exp_in=exp, exp_load=int(t == load_at),
                            pad_ok=int(t >= pad_ok_at))))
    return m, tr


@pytest.mark.parametrize('kw', [dict(OTP_REG=1), dict(OTP_REG=2), dict(OTP_REG=1, CMP_MODE=3), dict(OTP_REG=2, CMP_MODE=3),
                                dict(OTP_REG=2, INFECT_SPREAD=3, ALARM_EN=1, CFI_EN=1, FLAG_MUBI=1)])
def test_exp_src_port_equals_parameter_build_and_accepts_any_image(kw):
    cfg0 = hash_cfg(**kw)
    rng = random.Random(23)
    for _ in range(3):
        img = [rng.getrandbits(cfg0.R) for _ in range(cfg0.IMG_BLOCKS)]
        tag = mac(cfg0, img)
        ref = Core(cfg0.but(EXP_TAG=tag)).run(image_blocks=img)
        cfg1 = cfg0.but(EXP_SRC=1)                    # EXP_TAG stays 0: not used
        n = len(ref)
        _, tr = _run_exp_src(cfg1, img, tag, load_at=1, pad_ok_at=0, n=n)
        assert [o['boot_word'] for o in tr] == [o['boot_word'] for o in ref]
        assert [o['boot_token'] for o in tr] == [o['boot_token'] for o in ref]
        assert tr[cfg0.cycles_to_word()]['boot_word'] == ACCEPT
        _, tr = _run_exp_src(cfg1, img, tag ^ 1, load_at=1, pad_ok_at=0, n=n)
        assert all(o['boot_word'] != ACCEPT for o in tr) and tr[-1]['boot_token'] == 0


def test_exp_src_pad_block_waits_for_pad_ok_and_clear_wipes_the_shadow():
    cfg = hash_cfg(OTP_REG=2, EXP_SRC=1, CFI_EN=1, ALARM_EN=1)
    img = [0x5A5A]
    tag = mac(cfg, img)
    t = cfg.cycles_to_word()
    m, tr = _run_exp_src(cfg, img, tag, load_at=2, pad_ok_at=40, n=t + 60)
    first = next(i for i, o in enumerate(tr) if o['boot_word'] == ACCEPT)
    assert first > t and not any(o['alarm'] for o in tr)      # delayed by the wait, accepted, step counter still fine
    _, tr = _run_exp_src(cfg, img, tag, load_at=0, pad_ok_at=0, n=t + 3)   # load in the clear cycle: clear wins
    assert all(o['boot_word'] != ACCEPT for o in tr)


def test_exp_src_needs_shadow_registers():
    with pytest.raises(AssertionError):
        hash_cfg(OTP_REG=0, EXP_SRC=1)
