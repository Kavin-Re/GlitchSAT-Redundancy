"""Runs the (copied) engine under a threat model and builds the provenance-carrying result dict."""
import fnmatch, hashlib, json, os, platform, re, shutil, signal, subprocess, sys, tempfile, time, datetime

from . import __version__, _engine as eng
from .config import ConfigError

NO_ATTACK, ATTACK, UNKNOWN = "NO_ATTACK_UP_TO_BOUND", "ATTACK_FOUND", "UNKNOWN_TIMEOUT"
CONFIG_PROBLEM = "CONFIGURATION_PROBLEM"
STATEMENT = "bounded result under this model; not a proof of security"
CONFIG_MSG = ("CONFIGURATION PROBLEM: the honest input does not reach the goal in the fault-free design. With `{inp}` = {key} (legitimate_value) "
              "and no flips, `{out}` never equals {bad} within {n} cycles. The legitimate_value, the goal output/value, the cycle count or the "
              "reset behaviour in the config is probably wrong, so any 'attack' or 'no attack' verdict would be meaningless. No verdict was computed. "
              "(Override with --no-honest-check only if the goal is deliberately not reachable by the honest input.)")
# Same Yosys flow as scripts/synth.sh (flow 'plain'). H2 (N1): this is a FIXED script template; the only user-derived text that reaches it are the
# validated top name and the validated source path (as one double-quoted token), and it is run as `yosys -q -s flow.ys` (a script FILE, never `-p`, never a shell).
YOSYS_PLAIN = ("read_verilog {v}\nhierarchy -top {top}\nproc; opt_clean; techmap; opt_clean\nabc -g AND,OR,XOR,MUX\nopt_clean; setattr -mod -unset keep_hierarchy *; flatten; opt_clean\n"
               "techmap; opt_clean\nwrite_json {out}\n")
TOP_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]{0,254}\Z")
_BAD_PATH_CH = re.compile(r"[\x00-\x1f\x7f\"'`;\\#]")


class InputError(Exception):
    pass


def check_top(top):
    """H2 (N1): a Verilog top module name must be a plain identifier ([A-Za-z_$][A-Za-z0-9_$]*, at most 255 chars). Escaped identifiers
    (leading backslash), dots, spaces, quotes, ';' and everything else are refused (conservative)."""
    if not isinstance(top, str) or not TOP_RE.match(top):
        raise InputError(f"top {top!r} is not a plain module identifier ([A-Za-z_$][A-Za-z0-9_$]*); refusing to put it into a Yosys script "
                         "(escaped Verilog identifiers are not supported)")
    return top


def check_path(p, what="file"):
    """H2 (N1): a path that is written into a Yosys script as one double-quoted token. Refused: empty, leading '-', control characters (newline
    included), quotes, backtick, ';', backslash and '#'. Spaces, '$', ',' and '!' are fine inside the quotes."""
    if not isinstance(p, str) or not p or p.startswith("-") or _BAD_PATH_CH.search(p):
        raise InputError(f"{what} path {p!r} is not accepted: it must be non-empty, must not start with '-', and must not contain control characters, "
                         "quotes, backticks, ';', backslash or '#' (the path is written into a Yosys script)")
    return p


def sha256_file(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def yosys_env():
    """Minimal environment for Yosys (no inherited secrets/tokens)."""
    env = {k: os.environ[k] for k in ("PATH", "TMPDIR", "SYSTEMROOT") if k in os.environ}
    env["LC_ALL"] = "C"
    return env


def _pdeathsig():
    try:   # Linux: the child dies with its parent (so a killed worker never leaves yosys behind)
        import ctypes
        ctypes.CDLL(None).prctl(1, int(signal.SIGKILL))
    except Exception:
        pass


def run_yosys(args, cwd=None, timeout=600):
    """H2 (N9): run yosys WITHOUT a shell, in its own process group (unless this process is the --timeout-s worker, whose whole group the parent
    kills); on timeout or on any exception the whole group is killed (yosys starts abc as a child). Returns (returncode, stdout, stderr);
    raises subprocess.TimeoutExpired."""
    worker = bool(os.environ.get("FBWT_WORKER"))
    p = subprocess.Popen(args, cwd=cwd, env=yosys_env(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         errors="replace", start_new_session=not worker, preexec_fn=_pdeathsig)

    def kill():
        try:
            if worker:
                p.kill()
            else:
                os.killpg(p.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill(); p.communicate()
        raise
    except BaseException:
        kill(); p.wait()
        raise
    return p.returncode, out, err


def yosys_version():
    exe = shutil.which("yosys")
    if not exe:
        return None
    try:
        return subprocess.run([exe, "-V"], capture_output=True, text=True, timeout=30, env=yosys_env()).stdout.strip()
    except Exception:
        return None


def synthesize(verilog, top, out):
    if not shutil.which("yosys"):
        raise InputError("yosys not found on PATH (needed to read Verilog); pass a Yosys JSON netlist instead")
    check_top(top)
    check_path(verilog, "Verilog")
    check_path(out, "output")
    script = YOSYS_PLAIN.format(v='"' + verilog + '"', top=top, out='"' + out + '"')
    ys = os.path.join(os.path.dirname(os.path.abspath(out)), "flow.ys")
    with open(ys, "w", encoding="utf-8") as f:
        f.write(script)
    try:
        rc, _, err = run_yosys([shutil.which("yosys"), "-q", "-s", ys], timeout=600)
    except subprocess.TimeoutExpired:
        raise InputError("yosys synthesis timed out after 600 s")
    if rc:
        raise InputError("yosys synthesis failed:\n" + err[-2000:])


def _site_filter(nl, th):
    kinds = set(th.kinds)

    def ok(b, kind):
        if kind != "input" and kind not in kinds:   # PS4: input sites are governed by input_sites, not by `kinds`
            return False
        names = nl.aliases.get(b, [str(b)])
        if th.include and not any(fnmatch.fnmatchcase(n, g) for n in names for g in th.include):
            return False
        if any(fnmatch.fnmatchcase(n, g) for n in names for g in th.exclude):
            return False
        return True
    return ok


def analyze(netlist, th, command=None, top=None, workdir=None, on_scope=None):
    """Returns the report dict. Raises InputError / ConfigError for bad inputs. H2 (N10): the temp dir is removed on every path, errors included."""
    box = []
    try:
        return _analyze(netlist, th, command, top, workdir, on_scope, box)
    finally:
        for d in box:
            shutil.rmtree(d, ignore_errors=True)


def _analyze(netlist, th, command, top, workdir, on_scope, box):
    if not os.path.isfile(netlist):
        raise InputError(f"no such file: {netlist}")
    top = top or th.top
    prov = dict(tool="faultbound-working-title", tool_version=__version__, command=command,
                python=platform.python_version(), z3=_z3v(), yosys_on_path=yosys_version(),
                utc=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    tmp = None
    jpath = netlist
    if netlist.endswith(".v") or netlist.endswith(".sv"):
        if not top:
            raise InputError("Verilog input needs --top (or [netlist] top in the config)")
        tmp = tempfile.mkdtemp(prefix="fbwt_", dir=workdir)
        box.append(tmp)
        jpath = os.path.join(tmp, "netlist.json")
        synthesize(netlist, top, jpath)
        prov["input_kind"] = "verilog (synthesized here, flow 'plain', same script as scripts/synth.sh)"
        prov["synthesis_yosys"] = yosys_version()
        prov["source_sha256"] = sha256_file(netlist)
    else:
        prov["input_kind"] = "yosys-json"
    try:
        doc = eng.load_json_strict(jpath)   # H1: rejects duplicate JSON keys
    except eng.NetlistError as e:
        raise InputError(f"cannot parse {netlist} as Yosys JSON: {e}")
    if not isinstance(doc, dict) or "modules" not in doc:
        raise InputError(f"{netlist}: not a Yosys JSON netlist (no 'modules')")
    mods = list(doc["modules"])
    if top is None:
        if len(mods) != 1:
            raise InputError(f"netlist has modules {mods}; pass --top")
        top = mods[0]
    if top not in doc["modules"]:
        raise InputError(f"top {top!r} not in netlist modules {mods}")
    prov["netlist_yosys_creator"] = doc.get("creator")   # string written by whichever Yosys produced the JSON
    prov["netlist_path"] = netlist
    prov["netlist_sha256"] = sha256_file(jpath)
    try:
        nl = eng.Netlist(jpath, top)
    except eng.NetlistError as e:   # includes UnsupportedCell, multi-driver, loops, x init, duplicate keys
        raise InputError(f"unsupported or malformed netlist: {e}")
    prov["top"] = top
    prov["netlist_stats"] = dict(nl.stats(), basis="gates = combinational cells, flops = $_DFF_P_ (MEASURED from the netlist)")
    _check_ports(nl, th)
    kw = engine_kw(nl, th)
    scope = build_scope(nl, th, prov, kw)
    if on_scope:
        on_scope(prov, scope)
    try:
        honest = eng.honest_boots(nl, th.cycles, **kw)
    except eng.NetlistError as e:
        raise InputError(f"unsupported or malformed netlist: {e}")
    if not honest and th.honest_check:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
        return dict(
            schema="faultbound-wt-report/1", label="MEASURED (this run; tool)",
            provenance=prov, threat_model=th.as_dict(), verdict=CONFIG_PROBLEM, scope=scope,
            bound=_bound(th), note=CONFIG_MSG.format(inp=th.attacker_input, key=th.legitimate_value, out=th.output, bad=th.bad_value, n=th.cycles),
            honest_input_reaches_goal_fault_free=False, config_warnings=[x for x in _warnings(th, honest) if x.startswith("these config")], runtime_s=0.0)
    t0 = time.time()
    try:
        verdict, info, res = eng.solve(nl, th.cycles, th.max_flips, timeout_ms=th.timeout_ms, count_rule=th.count_rule, **kw)
    except eng.NothingToAttack as e:   # H2 (N4)
        raise InputError(str(e))
    except eng.NetlistError as e:   # undriven net / x constant found lazily in the cone
        raise InputError(f"unsupported or malformed netlist: {e}")
    wall = round(time.time() - t0, 3)
    rep = dict(
        schema="faultbound-wt-report/1", label="MEASURED (this run; tool)",
        provenance=prov, threat_model=th.as_dict(), verdict=verdict, scope=scope,
        bound=_bound(th),
        note=eng.NOTE.format(k=th.max_flips, n=th.cycles) + ('' if th.count_rule == 'stem' else f' Counting rule {th.count_rule}: max_flips is a COST budget (sum over the flipped nets of their pin counts), so fewer than {th.max_flips} flips may be the whole budget.'),
        sites=dict(modelled=info["sites_modelled"], of_unfiltered_budget=info["sites_total"]),
        honest_input_reaches_goal_fault_free=honest,
        config_warnings=_warnings(th, honest),
        runtime_s=wall,
    )
    if info.get("minimize_incomplete"):
        rep["minimize_incomplete"] = True   # PS4: timeout while minimizing: min_faults is an upper bound
    if res:
        rep["min_faults"] = len(res["faults"])
        if th.count_rule != "stem":   # PS6 (addition): cost of the found set under the counting rule; max_flips is a COST budget then
            rep["min_cost"] = res["cost"]
        rep["faults"] = [dict(net=nl.names.get(b, str(b)), net_id=b, cycle=t,
                              kind="flop_Q" if b in nl.dq else ("gate_output" if b in nl.drivers else "input_net"),
                              aliases=nl.aliases.get(b, [])[:4], **({"cost": res["weights"][b]} if res.get("weights") else {})) for t, b in res["faults"]]
        rep["attacker_input_value"] = {p: v for p, v in res["inputs"].items()}
        rep["explanation"] = eng.explain(nl, res, len(res["faults"]), th.cycles, th.output, th.attacker_input)
        if th.count_rule != "stem":
            rep["explanation"]["summary"] += f" [Counting rule {th.count_rule}: the figure above counts flipped nets; the COST under this rule is {res['cost']} (min_cost).]"
        rep["explanation"]["scope_line"] = scope_line(th, nl)
        rep["explanation"]["summary"] += " [Scope: " + rep["explanation"]["scope_line"] + "]"
        if th.init == "arbitrary" and not res["faults"]:
            rep["explanation"]["summary"] = ("ZERO FLIPS NEEDED under ARBITRARY power-up state: a power-up state exists from which the goal is already met, "
                                             "so no fault is needed. With no reset this is expected for every design (the accept state can itself be a power-up "
                                             "state): it shows the design has no reset, it is not a fault-tolerance result. Run with init=known for the fault question.")
            rep["explanation"]["fix_pattern"] = "(Generic.) Add a synchronous reset and model it, or state that power-up state is controlled by the platform."
        if "init_ones" in res:
            rep["initial_state_witness_flops_set_to_1"] = [nl.names.get(q, str(q)) for q in res["init_ones"]]
    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    return rep


def effective_mask(nl, th):
    """None when the consumer reads every bit of the output (identical to the pre-PS4 goal), else the int mask."""
    w = len(nl.ports[th.output]["bits"])
    if th.consumer_bits is None or th.consumer_bits == (1 << w) - 1:
        return None
    return th.consumer_bits


def engine_kw(nl, th):
    return dict(goal_out=th.output, goal_value=th.bad_value, attack_in=th.attacker_input, key=th.legitimate_value,
                reduce="full", site_filter=_site_filter(nl, th), goal_mask=effective_mask(nl, th),
                input_sites=(th.input_sites == "all"), init_mode=th.init)


def _bound(th):
    return dict(max_flips=th.max_flips, cycles=th.cycles,
                fault_model="single-cycle bit flip of a gate output or flop Q (MODELLED, not physical)" + ("" if th.count_rule == "stem" else f"; max_flips is a COST budget under count rule {th.count_rule}"),
                attacker_input=f"`{th.attacker_input}` free, constant over the run, != 0x{th.legitimate_value:X}",
                property=f"attack goal: {th.output} == 0x{th.bad_value:X}" + (f" on bits mask 0x{th.consumer_bits:X} only" if th.consumer_bits is not None else "")
                         + f" at some cycle < {th.cycles}")


_DEFAULT_TXT = {"attacker.input": lambda th: f"`{th.attacker_input}`", "attacker.legitimate_value": lambda th: f"0x{th.legitimate_value:X}",
                "property.output": lambda th: f"`{th.output}`", "property.bad_value": lambda th: f"0x{th.bad_value:X}"}


def _warnings(th, honest):
    w = []
    if th.defaulted:
        w.append("these config values were NOT set and the built-in defaults are in use: " +
                 ", ".join(f"{k} (default {_DEFAULT_TXT[k](th) if k in _DEFAULT_TXT else '?'})" for k in th.defaulted) +
                 " (a wrong default legitimate_value makes the honest input fail; check them)")
    if not honest and not th.honest_check:
        w.append("honest input does not reach the goal in the fault-free design: configuration problem (check was disabled by --no-honest-check)")
    return w


def scope_line(th, nl=None):
    """One plain line that says what the verdict is about (used in the explanation)."""
    mask = "" if th.consumer_bits is None else f" on bits 0x{th.consumer_bits:X} only"
    init = {"known": "known power-up state", "arbitrary": "arbitrary power-up state (no reset)",
            "free_nongoal": "arbitrary power-up state from which the fault-free run never accepts"}[th.init]
    return (f"modelled single-cycle bit flips of gate/flop nets{' and input nets' if th.input_sites == 'all' else ' (input nets are not fault sites)'}, "
            f"at most {th.max_flips}{'' if th.count_rule == 'stem' else ' cost units (' + th.count_rule + ')'} in {th.cycles} cycles, goal `{th.output}` == 0x{th.bad_value:X}{mask}, {init}; "
            "a bounded result for this toy model, not a proof of security")


def build_scope(nl, th, prov, kw):
    """The 'scope block': what the verdict is about. Same dict goes into JSON, SARIF properties, JUnit properties and the text report."""
    ports = nl.ports
    free = sorted(p for p, v in ports.items() if v["direction"] == "input" and p != "clk")
    explicit = set()
    for n, x in nl.m["netnames"].items():
        if x.get("attributes", {}).get("init"):
            explicit.update(b for b in x["bits"] if isinstance(b, int))
    n_expl = sum(1 for q in nl.qs if q in explicit)
    w = len(nl.ports[th.output]["bits"])
    em = effective_mask(nl, th)
    if em is None:
        goal_bits_txt = "all bits, combinationally evaluated"
    else:
        bl = [i for i in range(w) if (em >> i) & 1]
        goal_bits_txt = (f"ONLY the consumed bits 0x{em:X} (bits {','.join(map(str, bl))}) must equal the accept value 0x{th.bad_value & em:X}; "
                         "the other bits are ignored by the consumer, combinationally evaluated")
    arb = th.init == "arbitrary"
    nong = th.init == "free_nongoal"
    return dict(
        goal=f"output port `{th.output}` equals 0x{th.bad_value:X} ({goal_bits_txt}) at some cycle 0..{th.cycles - 1}, "
             f"while `{th.attacker_input}` != 0x{th.legitimate_value:X}",
        input_treatment=(f"every input port except the clock `clk` is a free value chosen by the solver and held CONSTANT for the whole run "
                         f"(free inputs here: {', '.join(free) or 'none'}); `{th.attacker_input}` must differ from legitimate_value; "
                         + ("input ports are NOT fault sites" if th.input_sites == "none" else
                            "every input-port bit (clock excepted) IS a fault site: one flip of the input net, seen by all its fanout, counts as 1 flip")
                         + "; the clock is implicit (one rising edge per cycle) and is not modelled as a signal"),
        init_state=((f"POWER-UP STATE ARBITRARY BUT NEVER ACCEPTING (free_nongoal): each of the {len(nl.qs)} flops may start as 0 or 1, chosen by the solver, but only "
                     "states from which the fault-free run (same inputs) never reaches the goal are allowed, so at least one flip is always needed; no reset is simulated") if nong else
                    (f"ARBITRARY power-up state: each of the {len(nl.qs)} flops may start as 0 or 1, chosen by the solver, and no reset is simulated. "
                     "With no reset this normally gives 0 flips for every design: the accept state can itself be a power-up state, so that result is a "
                     "statement about the missing reset, not about fault tolerance") if arb else
                    (f"all {len(nl.qs)} flops start at a known value: {n_expl} from an explicit Yosys `init` attribute, "
                     f"{len(nl.qs) - n_expl} default to 0; no reset sequence is simulated and unknown (x) power-up state is not modelled")),
        options=dict(goal_output=th.output, accept_value=f"0x{th.bad_value:X}",
                     consumer_bits=("all" if em is None else f"0x{em:X}"), input_sites=th.input_sites, init=th.init,
                     count_rule=th.count_rule + RULE_TXT[th.count_rule]),
        fault_model=("one fault = one flip of one net (gate output or flop Q; kinds allowed: " + "/".join(th.kinds) + ") at one cycle; a flip is "
                     "XORed onto the net for that cycle only and propagates through all its fanout (" + FLIP_COST[th.count_rule] + "); flips of the same net "
                     "in different cycles count separately; at most max_flips " + ("faults" if th.count_rule == "stem" else "COST units") + " in total over all cycles; no stuck-at, multi-bit, "
                     "timing or voltage effects"
                     + (f"; fault sites restricted by include={th.include} exclude={th.exclude}" if th.include or th.exclude else "")),
        bounds=dict(max_flips=th.max_flips, cycles=th.cycles, solver_timeout_ms=th.timeout_ms or "none"),
        netlist_sha256=prov["netlist_sha256"], tool_version=prov["tool_version"],
        defaulted_config_values=list(th.defaulted),
        statement=STATEMENT)


RULE_TXT = {
    "stem": " (flip of a net counts once for all its fanout)",
    "fanout_pins": " (a flip of a net costs the number of gate input pins, flop D pins and output-port bits it feeds, at least 1; max_flips is a COST budget; "
                   "research/c3/rep rule 'fanout_pins', alias 'fanout')",
    "fanout_gates": " (as fanout_pins but output-port bits are not counted; max_flips is a COST budget; research/c3/rep rule 'fanout_gates')",
}
FLIP_COST = {"stem": "counts as 1", "fanout_pins": "costs its fanout_pins pin count", "fanout_gates": "costs its fanout_gates pin count"}


def scope_lines(scope):
    return [f"  scope: goal: {scope['goal']}",
            f"  scope: inputs: {scope['input_treatment']}",
            f"  scope: init state: {scope['init_state']}",
            f"  scope: options: " + ", ".join(f"{k}={v}" for k, v in scope["options"].items()),
            f"  scope: fault model: {scope['fault_model']}",
            f"  scope: bounds: max_flips={scope['bounds']['max_flips']}, cycles={scope['bounds']['cycles']}, timeout_ms={scope['bounds']['solver_timeout_ms']}",
            f"  scope: netlist sha256 {scope['netlist_sha256']}; tool version {scope['tool_version']}",
            f"  scope: {scope['statement']}."]


def _check_ports(nl, th):
    p = nl.ports
    a = p.get(th.attacker_input)
    if not a or a["direction"] != "input":
        raise ConfigError(f"attacker input {th.attacker_input!r} is not an input port; inputs: "
                          f"{[k for k, v in p.items() if v['direction'] == 'input']}")
    o = p.get(th.output)
    if not o or o["direction"] != "output":
        raise ConfigError(f"property output {th.output!r} is not an output port; outputs: "
                          f"{[k for k, v in p.items() if v['direction'] == 'output']}")
    if th.consumer_bits is not None and th.consumer_bits >= 1 << len(o["bits"]):
        raise ConfigError(f"consumer bits 0x{th.consumer_bits:X} select bits beyond the {len(o['bits'])}-bit output `{th.output}`")
    if th.legitimate_value >= 1 << len(a["bits"]):
        raise ConfigError("legitimate_value does not fit the attacker input width")
    if th.bad_value >= 1 << len(o["bits"]):
        raise ConfigError("bad_value does not fit the output width")


def _z3v():
    import z3
    return z3.get_version_string()


# ---------------------------------------------------------------- PS4: scope sweep
SWEEP_SCHEMA = "faultbound-wt-sweep/1"


def _goals(nl, th, masks):
    """Goal rows of the sweep: the configured goal; each extra consumer mask on the configured output; `boot_ok` (1 bit) if present."""
    w = len(nl.ports[th.output]["bits"])
    rows = [dict(label=f"{th.output}==0x{th.bad_value:X}" + ("" if th.consumer_bits is None else f" bits 0x{th.consumer_bits:X}"),
                 output=th.output, accept=th.bad_value, mask=th.consumer_bits)]
    for m in masks:
        if m >= 1 << w:
            raise ConfigError(f"sweep mask 0x{m:X} selects bits beyond the {w}-bit output `{th.output}`")
        if m != th.consumer_bits and m != (1 << w) - 1:
            rows.append(dict(label=f"{th.output} bits 0x{m:X}", output=th.output, accept=th.bad_value, mask=m))
    ok = nl.ports.get("boot_ok")
    if th.output != "boot_ok" and ok and ok["direction"] == "output" and len(ok["bits"]) == 1:
        rows.append(dict(label="boot_ok==1", output="boot_ok", accept=1, mask=None))
    return rows


def _cell(rep, k):
    v = rep["verdict"]
    if v == ATTACK:
        n = rep.get("min_cost", rep["min_faults"]) if rep.get("faults") else 0
        return ("<=" if rep.get("minimize_incomplete") else "") + str(n)
    if v == NO_ATTACK:
        return f">{k}"
    if v == UNKNOWN:
        return "unknown"
    return "config-problem"


def sweep(netlist, th, masks=(), cell_timeout_ms=120000, command=None, top=None, workdir=None, input_sites=("none", "all"), inits=("known", "arbitrary"), widths=False, count_rules=None):
    """Run the scope matrix goal x input-sites x init with the other options of `th`; one cost per cell ('unknown' on a per-cell solver timeout)."""
    import copy
    top = top or th.top
    tmp = None
    path = netlist
    if netlist.endswith(".v") or netlist.endswith(".sv"):
        if not top:
            raise InputError("Verilog input needs --top (or [netlist] top in the config)")
        if not os.path.isfile(netlist):
            raise InputError(f"no such file: {netlist}")
        tmp = tempfile.mkdtemp(prefix="fbwt_", dir=workdir)
    try:
        if tmp:
            path = os.path.join(tmp, "netlist.json")
            synthesize(netlist, top, path)
        if not os.path.isfile(path):
            raise InputError(f"no such file: {path}")
        doc = eng.load_json_strict(path)
        mods = list(doc["modules"]) if isinstance(doc, dict) and isinstance(doc.get("modules"), dict) else []
        if not mods:
            raise InputError(f"{netlist}: not a Yosys JSON netlist (no 'modules')")
        top = top or (mods[0] if len(mods) == 1 else None)
        if top is None or top not in mods:
            raise InputError(f"pass --top (netlist modules: {mods})")
        try:
            nl = eng.Netlist(path, top)
        except eng.NetlistError as e:
            raise InputError(f"unsupported or malformed netlist: {e}")
        _check_ports(nl, th)
        if widths:   # PS5: consumer width curve: masks 'lowest n bits', n = 1..W, in the single scope given by th (input_sites, init)
            w = len(nl.ports[th.output]["bits"])
            goals = [dict(label=f"{th.output} low {n} bit{'s' if n > 1 else ''} (0x{(1 << n) - 1:X})", output=th.output, accept=th.bad_value,
                          mask=((1 << n) - 1 if n < w else None), width=n) for n in range(1, w + 1)]
            cols = [(th.input_sites, th.init, th.count_rule)]
        else:
            goals = _goals(nl, th, masks)
            rules = list(count_rules) if count_rules else [th.count_rule]   # PS6: optional counting-rule axis
            cols = [(i, n, r) for r in rules for n in inits for i in input_sites]
        cells, t0 = [], time.time()
        for g in goals:
            for isite, init, crule in cols:
                c = copy.deepcopy(th)
                c.count_rule = crule
                c.output, c.bad_value, c.consumer_bits = g["output"], g["accept"], g["mask"]
                c.input_sites, c.init, c.timeout_ms = isite, init, cell_timeout_ms
                c.attacker_model = th.attacker_model
                r = analyze(path, c, top=top, workdir=workdir)
                cells.append(dict(goal=g["label"], width=g.get("width"), input_sites=isite, init=init, count_rule=crule, verdict=r["verdict"], cost=_cell(r, th.max_flips),
                                  min_faults=r.get("min_faults"), runtime_s=r["runtime_s"],
                                  faults=[f"{f['net']}@{f['cycle']}" for f in r.get("faults", [])]))
        return dict(schema=SWEEP_SCHEMA, label="MEASURED (this run; tool)", netlist_sha256=sha256_file(path), top=top,
                    command=command, tool_version=__version__, bounds=dict(max_flips=th.max_flips, cycles=th.cycles, cell_timeout_ms=cell_timeout_ms),
                    mode="widths" if widths else "matrix", count_rule=",".join(dict.fromkeys(r for _, _, r in cols)), columns=[dict(input_sites=i, init=n, count_rule=r) for i, n, r in cols], goals=[g["label"] for g in goals],
                    cells=cells, runtime_s=round(time.time() - t0, 3),
                    note=("cell = minimum number of flips found (exact when no '<='), '>k' = no attack with <= k flips within the cycle bound, "
                          "'unknown' = solver timeout in that cell (NOT 'no attack'). " + STATEMENT + ". Faults are modelled bit flips."))
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def sweep_text(sw):
    cols = sw["columns"]
    multi = len({c.get("count_rule") for c in cols}) > 1   # PS6: name the rule in the header only when the sweep varies it
    head = ["goal \\ scope"] + [f"in-sites={c['input_sites']} init={c['init']}" + (f" rule={c['count_rule']}" if multi else "") for c in cols]
    rows = []
    for g in sw["goals"]:
        row = [g]
        for c in cols:
            x = next(z for z in sw["cells"] if z["goal"] == g and z["input_sites"] == c["input_sites"] and z["init"] == c["init"] and z.get("count_rule") == c.get("count_rule"))
            row.append(f"{x['cost']} ({x['runtime_s']}s)")
        rows.append(row)
    wd = [max(len(r[i]) for r in [head] + rows) for i in range(len(head))]
    fmt = lambda r: "  " + " | ".join(x.ljust(wd[i]) for i, x in enumerate(r))
    b = sw["bounds"]
    out = [f"{sw['top']}: scope sweep (minimum flips per cell; max_flips={b['max_flips']}, cycles={b['cycles']}, per-cell timeout {b['cell_timeout_ms']} ms; "
           f"count rule {sw['count_rule']}; netlist sha256 {sw['netlist_sha256']})", fmt(head), "  " + "-+-".join("-" * w for w in wd)]
    out += [fmt(r) for r in rows]
    out.append("  " + sw["note"])
    return "\n".join(out)


def width_text(sw):
    """Flips-versus-consumer-width table of a `widths` sweep (one row per mask 'lowest n bits')."""
    b, c0 = sw["bounds"], sw["columns"][0]
    out = [f"{sw['top']}: consumer width curve (minimum flips if the consumer reads only the lowest n bits of the output; input-sites={c0['input_sites']}, "
           f"init={c0['init']}; max_flips={b['max_flips']}, cycles={b['cycles']}, per-cell timeout {b['cell_timeout_ms']} ms; netlist sha256 {sw['netlist_sha256']})",
           "   n | mask | min flips | time", "  ---+------+-----------+-------"]
    for x in sw["cells"]:
        out.append(f"  {x['width']:>2} | 0x{(1 << x['width']) - 1:<2X} | {x['cost']:<9} | {x['runtime_s']}s")
    out.append("  " + sw["note"] + " A cost of 0 at small n can mean the idle state already looks like acceptance on those bits.")
    return "\n".join(out)


# ---------------------------------------------------------------- PS5: hard wall-clock timeout
def run_with_timeout(kind, netlist, th, timeout_s, command=None, top=None, **extra):
    """Run analyze/sweep in a worker process and kill it at the deadline. Returns ('ok', result) or ('timeout', partial_scope_or_None).
    Raises ConfigError / InputError / ValueError / RuntimeError as the in-process call would."""
    import json
    d = tempfile.mkdtemp(prefix="fbwt_w_")
    jp, op = os.path.join(d, "job.json"), os.path.join(d, "out.json")
    try:
        with open(jp, "w", encoding="utf-8") as f:
            json.dump(dict(kind=kind, netlist=netlist, th=th.as_dict(), command=command, top=top, **extra), f)
        env = dict(os.environ)
        pkg_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env["PYTHONPATH"] = pkg_parent + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        env["TMPDIR"] = d   # H2 (N9): every temp dir of the worker (and of its yosys) lives under d and is removed with it, even if the worker is killed
        env["FBWT_WORKER"] = "1"
        # H2 (N9): the worker runs in its own session/process group, so the deadline kill (or our own death by SIGTERM) takes its yosys/abc children too;
        # the worker additionally dies with its parent (prctl PDEATHSIG, parent poll as fallback; see _worker.py).
        p = subprocess.Popen([sys.executable, "-m", "faultbound_wt._worker", jp, op], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                             start_new_session=True)

        def killgroup():
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
        try:
            _, err = p.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            killgroup()
            p.communicate()
            partial = None
            try:
                with open(op + ".scope", encoding="utf-8") as f:
                    partial = json.load(f)
            except (OSError, ValueError):
                pass
            return "timeout", partial
        except BaseException:   # e.g. SIGTERM turned into SystemExit, KeyboardInterrupt
            killgroup()
            p.wait()
            raise
        killgroup()   # the worker exited: make sure no child it started is left
        try:
            with open(op, encoding="utf-8") as f:
                out = json.load(f)
        except (OSError, ValueError):
            raise RuntimeError(f"worker process died without a result (exit {p.returncode}): {err.decode('utf-8', 'replace')[-500:]}")
        if "result" in out:
            return "ok", out["result"]
        exc = {"ConfigError": ConfigError, "InputError": InputError, "ValueError": ValueError}.get(out["exc"], RuntimeError)
        raise exc(out["msg"] if exc is not RuntimeError else f"{out['exc']}: {out['msg']}")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def timeout_report(netlist, th, timeout_s, partial, command=None, top=None):
    """Report dict (schema faultbound-wt-report/1, verdict UNKNOWN_TIMEOUT) for a run killed at the wall-clock deadline."""
    if partial:
        prov, scope = partial["provenance"], partial["scope"]
    else:
        sha = sha256_file(netlist) if os.path.isfile(netlist) else "unavailable"
        prov = dict(tool="faultbound-working-title", tool_version=__version__, command=command, python=platform.python_version(), z3=None,
                    yosys_on_path=None, utc=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), input_kind="unavailable (timeout)",
                    netlist_path=netlist, netlist_sha256=sha, top=top or "?", netlist_stats=dict(gates="?", flops="?"))
        na = "unavailable: the wall-clock timeout was reached before the netlist was analysed"
        scope = dict(goal=na, input_treatment=na, init_state=na, options=dict(goal_output=th.output, accept_value=f"0x{th.bad_value:X}",
                     consumer_bits="all" if th.consumer_bits is None else f"0x{th.consumer_bits:X}", input_sites=th.input_sites, init=th.init, count_rule=th.count_rule),
                     fault_model=na, bounds=dict(max_flips=th.max_flips, cycles=th.cycles, solver_timeout_ms=th.timeout_ms or "none"),
                     netlist_sha256=sha, tool_version=__version__, defaulted_config_values=list(th.defaulted), statement=STATEMENT)
    scope = dict(scope, bounds=dict(scope["bounds"], wall_clock_timeout_s=timeout_s))
    return dict(schema="faultbound-wt-report/1", label="MEASURED (this run; tool)", provenance=prov, threat_model=th.as_dict(),
                verdict=UNKNOWN, scope=scope, bound=_bound(th),
                note=(f"WALL-CLOCK TIMEOUT: the analysis was stopped after {timeout_s} s before it reached a verdict. This is NOT 'no attack found'; "
                      "nothing is established for this bound. Raise --timeout-s, lower --max-flips/--cycles, or narrow the fault sites."),
                honest_input_reaches_goal_fault_free=None, config_warnings=_warnings(th, True), runtime_s=float(timeout_s), timed_out=True)
