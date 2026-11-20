"""Threat-model config (TOML) loading and validation."""
import re, tomllib
from dataclasses import dataclass, field, asdict


class ConfigError(Exception):
    pass


MAX_BIT = 4095        # H2 (N7): bit indices above this are refused at once (before any loop); the output width check follows once the netlist is known
MAX_CYCLES = 200      # H4 (F2): documented maximum of faults.cycles / --cycles (unrolled solver memory grows with it; 1000000000 was OOM-killed)
MAX_FLIPS = 64        # H2 (N8): documented maximum of faults.max_flips / --max-flips (cost of the at-most-k counter grows with k)
_LIST_RE = re.compile(r"\d+(-\d+)?(,\d+(-\d+)?)*\Z")


def _bits_mask(lst):
    """'3,5' / '0-3,6' (both ends of a range required) -> mask, without looping over the range."""
    if not _LIST_RE.match(lst):
        raise ValueError
    m = 0
    for part in lst.split(","):
        lo, _, hi = part.partition("-")
        lo, hi = int(lo), int(hi or lo)
        if hi < lo or hi > MAX_BIT:
            raise ValueError
        m |= ((1 << (hi - lo + 1)) - 1) << lo
    return m


def parse_mask(v):
    """Consumer-bit mask. UNAMBIGUOUS SYNTAX (H2, N6/N7/N14):
      * MASK: an int (TOML `consumer_bits = 15`), a plain decimal string ("15"), `0x..` hex ("0xF0") or `0b..` binary ("0b1010"). "3" = mask 3 = bits 0 and 1.
      * BIT LIST: `bits:3,5` or `bits:0-3,6` (ranges need both ends), a bracketed list "[3,5]", or a TOML list [3,5] (bit 0 = least significant).
        The legacy bare list form with ',' or '-' in it ("0-3,6") is still read as a bit list (it cannot be mistaken for a decimal mask).
    A bare single number is NEVER a bit index. Returns an int > 0; bit indices above 4095 or masks wider than 4096 bits are refused immediately."""
    try:
        if isinstance(v, bool):
            raise ValueError
        if isinstance(v, int):
            m = v
        elif isinstance(v, (list, tuple)):
            m = 0
            for b in v:
                if isinstance(b, bool) or not isinstance(b, int) or b < 0 or b > MAX_BIT:
                    raise ValueError
                m |= 1 << b
        elif isinstance(v, str):
            t = v.strip().lower()
            if t.startswith("bits:"):
                m = _bits_mask(t[5:].strip().replace(" ", ""))
            elif t.startswith("[") and t.endswith("]"):
                m = _bits_mask(t[1:-1].strip().replace(" ", ""))
            elif re.fullmatch(r"0x[0-9a-f]+", t):
                m = int(t, 16)
            elif re.fullmatch(r"0b[01]+", t):
                m = int(t, 2)
            elif re.fullmatch(r"[0-9]+", t):
                if len(t) > 1300:
                    raise ValueError
                m = int(t)
            elif re.fullmatch(r"[0-9,\-]+", t):   # legacy bare bit list
                m = _bits_mask(t)
            else:
                raise ValueError
        else:
            raise ValueError
        if m.bit_length() > MAX_BIT + 1:
            raise ValueError
    except ValueError:
        raise ConfigError(f"cannot read consumer bits {v!r}: a MASK is 0xF0, 0b1010 or a plain decimal number (15 = bits 0..3); a BIT LIST is 'bits:0-3,6' or '[0,1,2,3]' "
                          f"(bit 0 = least significant, ranges need both ends, bit index <= {MAX_BIT})")
    if m <= 0:
        raise ConfigError("consumer bits mask selects no bit (an empty mask would make every design trivially 'attacked')")
    return m


@dataclass
class Threat:
    max_flips: int = 1
    cycles: int = 6
    kinds: list = field(default_factory=lambda: ["gate", "flop"])
    include: list = field(default_factory=list)
    exclude: list = field(default_factory=list)
    attacker_input: str = "sig"
    attacker_model: str = "constant"
    legitimate_value: int = 0xC3
    output: str = "boot_word"
    bad_value: int = 0x96
    top: str | None = None
    timeout_ms: int = 0
    defaulted: list = field(default_factory=list)   # PS2: keys NOT given by the user (built-in defaults in use)
    honest_check: bool = True
    # PS4 scope options (defaults = the pre-PS4 behaviour)
    consumer_bits: int | None = None   # None = all bits of the output; else bit mask: only these bits must equal bad_value
    input_sites: str = "none"          # none | all: whether primary-input bits are fault sites
    init: str = "known"                # known | arbitrary: power-up state of flops
    count_rule: str = "stem"           # stem (implemented) | branch (NOT implemented: exit 3)

    def as_dict(self):
        return asdict(self)


_ALLOWED = {
    "faults": {"max_flips", "cycles", "kinds", "include", "exclude", "input_sites", "init", "count_rule"},
    "attacker": {"input", "model", "legitimate_value"},
    "property": {"output", "bad_value", "consumer_bits"},
    "netlist": {"top"},
    "solver": {"timeout_ms"},
}


def load(path):
    t = Threat()
    _KEYS = [("attacker", "input"), ("attacker", "legitimate_value"), ("property", "output"), ("property", "bad_value")]
    if path is None:
        t.defaulted = [f"{a}.{b}" for a, b in _KEYS]
        return t
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ConfigError(f"cannot read config {path}: {e}")
    for sec, body in raw.items():
        if sec not in _ALLOWED:
            raise ConfigError(f"unknown section [{sec}]; allowed: {sorted(_ALLOWED)}")
        for k in body:
            if k not in _ALLOWED[sec]:
                raise ConfigError(f"unknown key [{sec}] {k}; allowed: {sorted(_ALLOWED[sec])}")
    f, a, p = raw.get("faults", {}), raw.get("attacker", {}), raw.get("property", {})
    t.max_flips = f.get("max_flips", t.max_flips)
    t.cycles = f.get("cycles", t.cycles)
    t.kinds = list(f.get("kinds", t.kinds))
    t.include = list(f.get("include", t.include))
    t.exclude = list(f.get("exclude", t.exclude))
    t.attacker_input = a.get("input", t.attacker_input)
    t.attacker_model = a.get("model", t.attacker_model)
    t.legitimate_value = a.get("legitimate_value", t.legitimate_value)
    t.output = p.get("output", t.output)
    t.bad_value = p.get("bad_value", t.bad_value)
    if "consumer_bits" in p:
        t.consumer_bits = parse_mask(p["consumer_bits"])
    t.input_sites = f.get("input_sites", t.input_sites)
    t.init = f.get("init", t.init)
    t.count_rule = f.get("count_rule", t.count_rule)
    t.top = raw.get("netlist", {}).get("top")
    t.timeout_ms = raw.get("solver", {}).get("timeout_ms", 0)
    t.defaulted = [f"{a}.{b}" for a, b in _KEYS if b not in raw.get(a, {})]
    return t


def validate(t):
    if t.attacker_model != "constant":
        # TODO(E1): per-cycle attacker input is not supported by the copied engine. research/c2/e1_timevarying/ holds
        # unfinished SymbiYosys-based work only; nothing was copied from it.
        raise ConfigError(f"attacker.model={t.attacker_model!r} unsupported; only 'constant' (per-cycle is a TODO)")
    for name in ("max_flips", "cycles", "legitimate_value", "bad_value", "timeout_ms"):
        v = getattr(t, name)
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise ConfigError(f"{name} must be a non-negative integer, got {v!r}")
    if t.cycles < 1:
        raise ConfigError("cycles must be >= 1")
    if t.cycles > MAX_CYCLES:   # H4 (F2)
        raise ConfigError(f"cycles {t.cycles} is above the supported maximum of {MAX_CYCLES} (the unrolled model grows with the cycle count and a larger value can exhaust memory)")
    if t.max_flips > MAX_FLIPS:   # H2 (N8)
        raise ConfigError(f"max_flips {t.max_flips} is above the supported maximum of {MAX_FLIPS} (the at-most-k counter and the solve time grow with it; "
                          f"a bound at or above the number of fault sites is the same as 'any number of flips')")
    bad = set(t.kinds) - {"gate", "flop"}
    if bad or not t.kinds:
        raise ConfigError(f"kinds must be a non-empty subset of ['gate','flop'], got {t.kinds}")
    if t.input_sites not in ("none", "all"):
        raise ConfigError(f"input_sites must be 'none' or 'all', got {t.input_sites!r}")
    if t.init not in ("known", "arbitrary", "free_nongoal"):
        raise ConfigError(f"init must be 'known', 'arbitrary' or 'free_nongoal', got {t.init!r}")
    if t.count_rule == "fanout":   # PS6: alias, recorded under its canonical name
        t.count_rule = "fanout_pins"
    if t.count_rule not in ("stem", "fanout_pins", "fanout_gates", "branch"):
        raise ConfigError(f"count_rule must be 'stem', 'fanout' (= 'fanout_pins'), 'fanout_gates' or 'branch', got {t.count_rule!r}")
    if t.count_rule == "branch":
        raise ConfigError("count_rule='branch' (each fanout branch of a net is a separate fault site; research/c2/b1_faultmodels) is NOT IMPLEMENTED "
                          "in this tool: the research engine did not finish on the spike V2 (z3 timeout) and was not ported. Use 'stem'.")
    if t.consumer_bits is not None:
        t.consumer_bits = parse_mask(t.consumer_bits)
