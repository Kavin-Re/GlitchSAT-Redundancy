"""pytest helper: assert that no modelled bit-flip attack exists within a bound.

    from faultbound_wt.pytest_helper import assert_no_attack
    def test_lock():
        assert_no_attack("build/pin.json", goal=("unlock", 1), k=1, cycles=4,
                         attacker_input="code", legitimate_value=10)

`goal` is (output_name, bad_value) or the string "unlock==1". Passing means ONLY: no attack up to k flips and `cycles` cycles under
the scope block's model; it is not a proof of security. Raises AssertionError on ATTACK_FOUND (lists the minimal fault set and scope),
on UNKNOWN (solver gave up) and on CONFIGURATION_PROBLEM. Input errors raise faultbound_wt.runner.InputError / ConfigError."""
from . import config, runner
from .cli import _safe

__all__ = ["assert_no_attack", "check"]


def _parse_goal(goal):
    if isinstance(goal, str):
        if "==" not in goal:
            raise ValueError("goal string must look like 'unlock==1'")
        name, val = goal.split("==", 1)
        return name.strip(), int(val.strip(), 0)
    name, val = goal
    return str(name), int(val)


def check(netlist, goal, k, cycles, *, attacker_input=None, legitimate_value=None, top=None, config_file=None,
          include=None, exclude=None, timeout_ms=None, honest_check=True):
    """Run the analysis and return the report dict (schema faultbound-wt-report/1)."""
    th = config.load(config_file)
    th.output, th.bad_value = _parse_goal(goal)
    th.max_flips, th.cycles = k, cycles
    if attacker_input is not None: th.attacker_input = attacker_input
    if legitimate_value is not None: th.legitimate_value = legitimate_value
    if include is not None: th.include = list(include)
    if exclude is not None: th.exclude = list(exclude)
    if timeout_ms is not None: th.timeout_ms = timeout_ms
    th.honest_check = honest_check
    th.defaulted = [x for x in th.defaulted if not (
        (x == "property.output" or x == "property.bad_value")
        or (x == "attacker.input" and attacker_input is not None)
        or (x == "attacker.legitimate_value" and legitimate_value is not None))]
    config.validate(th)
    return runner.analyze(str(netlist), th, top=top)


def assert_no_attack(netlist, goal, k, cycles, **kw):
    rep = check(netlist, goal, k, cycles, **kw)
    v = rep["verdict"]
    if v == runner.NO_ATTACK:
        return rep
    lines = [f"{v}: {rep['provenance'].get('top')} (<= {k} flips, {cycles} cycles)"]
    if v == runner.ATTACK:
        faults = rep.get("faults", [])
        lines.append("minimal fault set (%d): " % len(faults) + (", ".join(f"{f['net']}@{f['cycle']}" for f in faults) or "none needed (0 flips)"))
        if rep.get("attacker_input_value"):
            lines.append("attacker input values: " + ", ".join(f"{p}={v_}" for p, v_ in rep["attacker_input_value"].items()))
    else:
        lines.append(rep.get("note", ""))
    lines.append("scope (modelled bit flips only; " + rep["scope"]["statement"] + "):")
    for key in ("goal", "input_treatment", "init_state", "fault_model", "bounds", "netlist_sha256", "tool_version"):
        lines.append(f"  {key}: {rep['scope'][key]}")
    raise AssertionError("\n".join(_safe(x) for x in lines))
