"""The experiment variants: one secure-boot core configuration per countermeasure combination, each with the
single attacker input and single goal output that scripts/glitchsat.py needs.

Every variant is wrapped by a generated top module (engine/wrappers.py -> rtl/tops/top_<name>.v):
    input  clk
    input  [7:0] sig     the attacker input, held constant for the whole run
    output boot_word     (goal 'word')    = core boot_word, goal value 0x96 (ACCEPT)
       or  boot_grant    (goal 'grant') = {core boot_word, core boot_token}, goal value {0x96, TOKEN}
All other core inputs are tied inside the wrapper: rst = 0, start = 1, blk_valid = 1.
  family 'decision' (HASH_EN = 0): sig is the tag; the legitimate key is the expected tag 0xC3.
  family 'hash'     (HASH_EN = 1): sig is the one image block; the legitimate key is the image 0xC3, and the
                                   expected tag is the MAC of that image under a fixed MAC key.
The repository default key is 0xC3, so `--key 0xC3` is used for every variant.

Sizes in this file are the model's register counts (exact for the RTL as written). Gate counts are not known here:
they come from the cloud run (cloud/cloud_run.sh). Nothing in this file is a measured fault-analysis result.
"""
from dataclasses import dataclass, field
from . import spec as S
from .spec import Cfg
from .secboot_model import Core, In, mac

KEY_SIG = 0xC3
TOKEN8 = 0xB7
GOAL_WORD = S.ACCEPT

DECISION_BASE = dict(W=2, RATE_LANES=4, TAG_LANES=4, HASH_EN=0, EXP_TAG=KEY_SIG, TKW=8, TOKEN=TOKEN8)
HASH_BASE = dict(W=2, RATE_LANES=4, TAG_LANES=4, NR=2, KEY_BLOCKS=1, IMG_BLOCKS=1, HASH_EN=1, TKW=8, TOKEN=TOKEN8)

# Countermeasure labels shown in the docs and in the Studio panel.
CM_TEXT = {
    'sparse': 'sparse 8-bit state codes (distance 4)',
    'single': 'one digest compare',
    'dup': 'two compares, results ANDed in one gate per state bit',
    'trip': 'three compares, each owning its own state bits',
    'compl': 'two compares, second one on the complemented rail',
    'mubi': 'compare results stored as 4-bit multi-bit booleans',
    'inline': 'compare copies written inline (synthesis may merge them)',
    'separate': 'compare copies kept as separate module instances',
    'alarm': 'alarm path (invalid state, accept without evidence)',
    'cfi': 'step counter with complemented copy',
    'otp1': 'expected digest loaded into one shadow register',
    'otp2': 'expected digest loaded into one shadow register per compare',
    'infect': 'infection: wrong tag bits corrupt the release token',
    'hash2': 'two independent hash engines',
    'hash': 'keyed sponge MAC computed in hardware',
}


@dataclass(frozen=True)
class Variant:
    name: str
    family: str           # 'decision' | 'hash'
    cfg: Cfg
    goal: str             # 'word' | 'grant'
    cms: tuple            # countermeasure labels (keys of CM_TEXT)
    plain: str            # one plain-language sentence
    large: bool = False   # True: slow in the solver; the cloud run does it only with LARGE=1
    intent: str = ''      # what the countermeasure is meant to achieve (a design intent, NOT a result)

    @property
    def top(self):
        return f'top_{self.name}'

    @property
    def goal_port(self):
        return 'boot_word' if self.goal == 'word' else 'boot_grant'

    @property
    def goal_width(self):
        return 8 if self.goal == 'word' else 8 + self.cfg.TKW

    @property
    def goal_value(self):
        return GOAL_WORD if self.goal == 'word' else (GOAL_WORD << self.cfg.TKW) | self.cfg.TOKEN

    @property
    def key(self):
        return KEY_SIG

    @property
    def cycles(self):
        """Unrolling depth for the solver: the honest boot shows ACCEPT at cycle cycles_to_word(); one spare cycle."""
        return self.cfg.cycles_to_word() + 2

    def core_inputs(self, sig):
        c = self.cfg
        if c.HASH_EN:
            return In(rst=0, start=1, blk_valid=1, blk_data=sig & ((1 << c.R) - 1), tag_in=0)
        return In(rst=0, start=1, blk_valid=1, blk_data=0, tag_in=sig & ((1 << c.TAG) - 1))

    def goal_of(self, out):
        if self.goal == 'word':
            return out['boot_word']
        return (out['boot_word'] << self.cfg.TKW) | out['boot_token']

    def cone_registers(self):
        """Register bits that can influence the goal output (what synthesis should keep). The token register only
        reaches the goal when the goal is 'grant'."""
        m = Core(self.cfg)
        return {n: w for n, w in m.width.items() if not (n == 'tok' and self.goal == 'word')}

    def flop_bits(self):
        return sum(self.cone_registers().values())


def wrapper_trace(v: Variant, sig, cycles=None, flips=None, core=None):
    """Cycle-by-cycle outputs of the wrapper top: list of dicts with 'goal' plus the core outputs.
    flips: {cycle: [(register, bit), ...]} (single-cycle flip of a flop output, as in Core.step)."""
    m = core or Core(v.cfg)
    m.reset()
    n = cycles or v.cycles
    tr = []
    for t in range(n):
        o = m.step(v.core_inputs(sig), flips=(flips or {}).get(t, ()))
        o = dict(o)
        o['goal'] = v.goal_of(o)
        tr.append(o)
    return tr


def unique_preimage_key(cfg, image=KEY_SIG, start=0x5A):
    """Smallest MAC key >= start (mod 2^R) for which `image` is the only 8-bit image with its tag. Without this a
    different sig could give the same tag, and the solver would report a 0-flip 'attack' that is a plain collision."""
    r = cfg.R
    for d in range(1 << (cfg.KEY_BLOCKS * r)):
        k = (start + d) % (1 << (cfg.KEY_BLOCKS * r))
        c = cfg.but(KEY=k)
        tags = [mac(c, [x]) for x in range(1 << r)]
        t = tags[image]
        if tags.count(t) == 1:
            return k, t
    raise ValueError('no key gives a unique preimage')


def _decision(name, cms, plain, intent='', goal='word', **kw):
    p = dict(DECISION_BASE); p.update(kw)
    return Variant(name, 'decision', Cfg(**p), goal, ('sparse',) + tuple(cms), plain, False, intent)


def _hash(name, cms, plain, intent='', goal='word', large=False, **kw):
    p = dict(HASH_BASE); p.update(kw)
    c = Cfg(**p)
    k, t = unique_preimage_key(c)
    return Variant(name, 'hash', c.but(KEY=k, EXP_TAG=t), goal, ('sparse', 'hash') + tuple(cms), plain, large, intent)


ALL_CM = dict(CMP_MODE=2, FLAG_MUBI=1, ALARM_EN=1, CFI_EN=1, OTP_REG=2, INFECT_SPREAD=3)


def build_variants():
    v = [
        _decision('d_single', ['single', 'separate'], 'One comparator decides; the state codes are sparse.', CMP_MODE=0,
                  intent='baseline: one wrong gate in the compare or the decision logic may be enough'),
        _decision('d_dup', ['dup', 'separate'], 'Two comparators, but one AND gate per state bit combines them.', CMP_MODE=1,
                  intent='duplication with a shared combining gate'),
        _decision('d_dup_inline', ['dup', 'inline'], 'Same as d_dup, written so that synthesis is free to merge the two comparators.',
                  CMP_MODE=1, SEPARATE=0, intent='shows what merging of copies does'),
        _decision('d_trip', ['trip', 'separate'], 'Three comparators; each one alone decides a third of the state bits.', CMP_MODE=2,
                  intent='no single comparator decides the whole state word'),
        _decision('d_trip_inline', ['trip', 'inline'], 'Same as d_trip, written so that synthesis may merge the comparators.',
                  CMP_MODE=2, SEPARATE=0, intent='shows what merging of copies does'),
        _decision('d_compl', ['compl', 'separate'], 'Two comparators, one on the true and one on the inverted digest; each owns half the bits.',
                  CMP_MODE=3, intent='a stuck or flipped net cannot look like "match" on both rails'),
        _decision('d_trip_mubi', ['trip', 'mubi', 'separate'], 'Three comparators whose results are stored as 4-bit codes, not single bits.',
                  CMP_MODE=2, FLAG_MUBI=1, intent='one flipped result bit is not a valid "true"'),
        _decision('d_compl_mubi', ['compl', 'mubi', 'separate'], 'Complemented pair with 4-bit result codes.', CMP_MODE=3, FLAG_MUBI=1),
        _decision('d_trip_alarm', ['trip', 'alarm', 'separate'], 'Triplicated compare plus an alarm on any invalid state or unsupported accept.',
                  CMP_MODE=2, ALARM_EN=1, intent='partial faults land on invalid codes and raise the alarm'),
        _decision('d_trip_mubi_alarm', ['trip', 'mubi', 'alarm', 'separate'], 'Triplicated compare, 4-bit result codes and the alarm.',
                  CMP_MODE=2, FLAG_MUBI=1, ALARM_EN=1),
        _decision('d_trip_cfi', ['trip', 'cfi', 'separate'], 'Triplicated compare; the decision also needs the right step count.',
                  CMP_MODE=2, CFI_EN=1, intent='skipping a step makes the decision REJECT'),
        _decision('d_trip_cfi_alarm', ['trip', 'cfi', 'alarm', 'separate'], 'Step counter and alarm together.',
                  CMP_MODE=2, CFI_EN=1, ALARM_EN=1),
        _decision('d_trip_otp1', ['trip', 'otp1', 'separate'], 'Expected digest copied from OTP into one register that all comparators read.',
                  CMP_MODE=2, OTP_REG=1, intent='one shared register: its flops become a common point'),
        _decision('d_trip_otp2', ['trip', 'otp2', 'separate'], 'Expected digest copied into one register per comparator.',
                  CMP_MODE=2, OTP_REG=2),
        _decision('d_single_infect', ['single', 'infect', 'separate'], 'One comparator, but the release token is corrupted by every wrong tag bit.',
                  goal='grant', CMP_MODE=0, INFECT_SPREAD=3, intent='forcing ACCEPT is not enough: the token must also be right'),
        _decision('d_trip_infect', ['trip', 'infect', 'separate'], 'Triplicated compare plus the infected release token.',
                  goal='grant', CMP_MODE=2, INFECT_SPREAD=3),
        _decision('d_all', ['trip', 'mubi', 'alarm', 'cfi', 'otp2', 'infect', 'separate'], 'Every decision countermeasure at once.',
                  goal='grant', **ALL_CM),
        _hash('h_single', ['single', 'separate'], 'The hardware hashes the image and one comparator checks the result.', CMP_MODE=0),
        _hash('h_trip', ['trip', 'separate'], 'Hash in hardware, three comparators reading the same hash engine.', CMP_MODE=2,
              intent='the shared hash engine is a common point for all three comparators'),
        _hash('h_trip_2hash', ['trip', 'hash2', 'separate'], 'Two independent hash engines feed the comparators.', CMP_MODE=2, HASH_COPIES=2),
        _hash('h_all', ['trip', 'hash2', 'mubi', 'alarm', 'cfi', 'otp2', 'infect', 'separate'], 'Hash in hardware with every countermeasure.',
              goal='grant', HASH_COPIES=2, **ALL_CM),
        _hash('h_single_full', ['single', 'separate'], 'h_single with the full round count (slow in the solver).', CMP_MODE=0, NR=0,
              large=True),
        _hash('h_all_full', ['trip', 'hash2', 'mubi', 'alarm', 'cfi', 'otp2', 'infect', 'separate'], 'h_all with the full round count (slow).',
              goal='grant', HASH_COPIES=2, NR=0, large=True, **ALL_CM),
    ]
    names = [x.name for x in v]
    assert len(names) == len(set(names))
    return v


VARIANTS = build_variants()
BY_NAME = {v.name: v for v in VARIANTS}
