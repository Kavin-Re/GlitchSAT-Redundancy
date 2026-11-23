"""Every experiment variant, through its wrapper: the legitimate key boots at the predicted cycle, no other value of
the attacker input ever reaches the goal without faults (exhaustive over all 256 values), and the vector files
contain fault scenarios that actually change the behaviour."""
import os
import pytest
from model import spec as S
from model.secboot_model import Core, mac
from model.variants import VARIANTS, BY_NAME, wrapper_trace, unique_preimage_key, KEY_SIG
from engine import wrappers, netsim

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SMALL = [v for v in VARIANTS if not v.large]


@pytest.mark.parametrize('v', VARIANTS, ids=lambda v: v.name)
def test_legitimate_key_reaches_goal_exactly_at_the_accept_cycle(v):
    tr = wrapper_trace(v, v.key)
    t = v.cfg.cycles_to_word()
    assert t < v.cycles
    assert tr[t]['goal'] == v.goal_value
    assert all(o['goal'] != v.goal_value for o in tr[:t])
    assert not any(o['alarm'] for o in tr)


@pytest.mark.parametrize('v', SMALL, ids=lambda v: v.name)
def test_no_other_input_reaches_the_goal_without_faults(v):
    m = Core(v.cfg)
    for sig in range(256):
        if sig == v.key:
            continue
        tr = wrapper_trace(v, sig, core=m)
        assert all(o['goal'] != v.goal_value for o in tr), f'sig 0x{sig:02X} boots without faults'
        assert tr[v.cfg.cycles_to_word()]['boot_word'] == S.REJECT


@pytest.mark.parametrize('v', [v for v in VARIANTS if v.family == 'hash'], ids=lambda v: v.name)
def test_hash_variants_have_a_unique_preimage(v):
    tags = [mac(v.cfg, [x]) for x in range(256)]
    assert tags.count(v.cfg.EXP_TAG) == 1 and tags[KEY_SIG] == v.cfg.EXP_TAG
    assert unique_preimage_key(v.cfg.but(KEY=0))[0] == v.cfg.KEY


def test_variant_set_covers_every_countermeasure_option():
    seen = set()
    for v in VARIANTS:
        c = v.cfg
        seen |= {('cmp', c.CMP_MODE), ('mubi', c.FLAG_MUBI), ('sep', c.SEPARATE), ('alarm', c.ALARM_EN),
                 ('cfi', c.CFI_EN), ('otp', c.OTP_REG), ('inf', c.INFECT_SPREAD > 0), ('hash', c.HASH_EN),
                 ('copies', c.HASH_COPIES)}
    want = {('cmp', m) for m in range(4)} | {('mubi', 0), ('mubi', 1), ('sep', 0), ('sep', 1), ('alarm', 0),
            ('alarm', 1), ('cfi', 0), ('cfi', 1), ('otp', 0), ('otp', 1), ('otp', 2), ('inf', False), ('inf', True),
            ('hash', 0), ('hash', 1), ('copies', 1), ('copies', 2)}
    assert want <= seen


def test_cycles_and_register_counts():
    assert BY_NAME['d_single'].cycles == 8 and BY_NAME['h_single'].cycles == 15
    assert BY_NAME['d_single'].flop_bits() == 8 + 8 + 1 + 5 + 1 + 1          # st rel blk rnd cph flag
    assert BY_NAME['d_single_infect'].flop_bits() == 24 + 8                     # + token (goal includes it)
    assert BY_NAME['h_trip_2hash'].flop_bits() - BY_NAME['h_trip'].flop_bits() == 50


@pytest.mark.parametrize('v', SMALL, ids=lambda v: v.name)
def test_vector_file_has_meaningful_fault_scenarios(v):
    sc = netsim.read_vectors(os.path.join(HERE, 'vectors', f'{v.name}.vec'))
    assert sc[0]['sig'] == v.key and not sc[0]['flips']
    faulty = [s for s in sc if s['flips']]
    assert len(faulty) >= 30
    changed = 0
    for s in faulty:
        clean = [o['goal'] for o in wrapper_trace(v, s['sig'], cycles=len(s['goal']))]
        changed += clean != s['goal']
    assert changed >= 5, 'too few fault scenarios change the goal output'


def test_four_state_flips_force_accept_only_without_alarm():
    """The COMPARE -> ACCEPT forcing scenario of the vector files: a wrong tag reaches ACCEPT in d_trip (no alarm)
    and not in d_trip_alarm (the state is ACCEPT, but boot_word shows ALARM)."""
    for name, expect in (('d_trip', True), ('d_trip_alarm', False)):
        v = BY_NAME[name]
        sc = [s for s in netsim.read_vectors(os.path.join(HERE, 'vectors', f'{name}.vec')) if s['flips']]
        forced = sc[-3]
        assert len(forced['flips'][v.cfg.cycles_to_word() - 2]) == 1      # one register (st), mask with 4 bits
        assert (v.goal_value in forced['goal']) == expect
