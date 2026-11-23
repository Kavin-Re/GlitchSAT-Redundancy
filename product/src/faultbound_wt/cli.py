"""GlitchSAT command line: glitchsat analyze NETLIST ... (the older command name faultbound-wt is kept as an alias)."""
import argparse, os, shlex, signal, sys

from . import __version__
from .config import ConfigError, load, validate, parse_mask
try:   # the solver modules need z3; --help and --version must work without it
    from . import reports, runner
except ModuleNotFoundError as _e:
    if _e.name != "z3":
        raise
    reports = runner = None
Z3_MISSING = ("z3-solver is not installed; the solver is an optional extra: pip install 'glitchsat[solver]' "
              "(exact version of the recorded results: pip install -r ci/requirements-ci.txt)")
_EVIDENCE_CMDS = ("margin", "evidence", "sarif", "check", "validate-sarif", "evidence-example")

EXIT_OK, EXIT_ATTACK, EXIT_UNKNOWN, EXIT_ERROR, EXIT_INTERNAL = 0, 1, 2, 3, 4
# H1: 0 = no attack within bound; 1 = attack found (ONLY a verdict ever returns 1); 2 = solver unknown/timeout;
# 3 = usage / input / netlist error (incl. argparse usage errors); 4 = internal error (a Python exception, never reported as 1).


def _safe(s):
    """Escape control, ANSI and bidi characters of netlist-derived text before it reaches a terminal."""
    bidi = "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
    return "".join(c if (c.isprintable() and c not in bidi) else (c.encode("unicode_escape").decode("ascii") if ord(c) < 0x10000 else "\\U%08x" % ord(c)) for c in str(s))


class _Parser(argparse.ArgumentParser):
    def error(self, message):   # argparse exits 2 by default, which would collide with 'solver unknown'
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_ERROR)


def _safe_block(t):
    return "\n".join(_safe(l) for l in t.split("\n"))


def example_dir():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples")


def build_parser():
    invoked = os.path.basename(sys.argv[0]) if sys.argv and sys.argv[0] else ""
    ap = _Parser(prog=invoked if invoked in ("glitchsat", "faultbound-wt") else "glitchsat",
                 description="GlitchSAT CLI: bounded analysis of modelled single-cycle bit flips in a Yosys gate-level netlist. "
                             "It reports the smallest number of flips that makes the netlist accept a wrong input, within the stated "
                             "bounds; a result is not a proof of security. Further commands (no z3 needed): margin, evidence, sarif, check, "
                             "validate-sarif, evidence-example; run `glitchsat margin --help`.")
    ap.add_argument("--version", action="version", version=f"GlitchSAT CLI {__version__}")
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("analyze", help="search for a bounded bit-flip attack",
                      epilog="exit codes: 0 no attack up to bound; 1 attack found; 2 solver unknown/timeout; 3 usage/input/netlist error; 4 internal error")
    a.add_argument("netlist", help="Yosys JSON netlist (.json) or Verilog (.v, needs --top and yosys)")
    a.add_argument("--config", help="threat-model TOML")
    a.add_argument("--max-flips", type=int, help="override faults.max_flips")
    a.add_argument("--cycles", type=int, help="override faults.cycles (maximum 200; above it: exit 3)")
    a.add_argument("--top", help="top module (needed for Verilog or multi-module JSON)")
    a.add_argument("--report", action="append", default=[], metavar="FILE",
                   help="write a report; format from extension: .json | .sarif | .junit.xml (repeatable)")
    a.add_argument("--badge", metavar="FILE", help="write a shields.io endpoint JSON badge (label 'fault check'; message always carries the bound and 'scoped')")
    g = a.add_argument_group("scope options (each one is also a config key; the scope block of every report states them)")
    g.add_argument("--goal-out", metavar="PORT", help="override property.output: the output port the goal is judged on (e.g. boot_word, or boot_ok for the single-net flag)")
    g.add_argument("--accept-value", metavar="N", help="override property.bad_value: the value the goal output must take (int, 0x.. allowed)")
    g.add_argument("--consumer-bits", metavar="MASK", help="only these output bits are consumed: the goal holds when they equal the accept value on those bits only "
                   "(mask: 0xF0, 0b1010 or plain decimal 15 = bits 0..3; bit list: 'bits:0-3,6' or '[0,1,2,3]'; default all bits; see QUICKSTART)")
    g.add_argument("--input-sites", choices=["none", "all"], help="all = every primary-input bit (clock excepted) is also a fault site (default none)")
    g.add_argument("--init", choices=["known", "arbitrary", "free_nongoal"], help="known = flops power up at their netlist init value (default); arbitrary = any power-up state; "
                   "free_nongoal = any power-up state from which the fault-free run never accepts (so >= 1 flip is needed)")
    g.add_argument("--count-rule", choices=["stem", "fanout", "fanout_pins", "fanout_gates", "branch"],
                   help="how a flip is counted: stem (default; a net flip costs 1) | fanout = fanout_pins (a net flip costs the number of gate input pins, flop D pins and output-port bits it feeds; "
                   "max_flips becomes a COST budget) | fanout_gates (same without output-port bits); 'branch' is not implemented (exit 3)")
    g.add_argument("--sweep-count-rules", metavar="R1,R2,..", help="with --scope-sweep: add a counting-rule axis, e.g. stem,fanout_pins,fanout_gates")
    g.add_argument("--synth-sweep", action="store_true", help="Verilog input only (.v with --top, needs yosys): synthesize the design with a documented set of Yosys flows and "
                   "print the minimum flips of each resulting netlist (hash, gate/flop counts, Yosys version) and the range over the variants")
    g.add_argument("--synth-variants", metavar="FILE", help="with --synth-sweep: extra custom flows from a .toml ([[variant]]) or .json file")
    g.add_argument("--synth-select", metavar="N1,N2,..", help="with --synth-sweep: run only these variants (by name)")
    g.add_argument("--scope-sweep", action="store_true", help="run the matrix goal x input-sites x init and print one table of minimum flips per cell")
    g.add_argument("--sweep-masks", metavar="M1,M2,..", help="with --scope-sweep: extra consumer masks (hex) of the configured output to add as rows")
    g.add_argument("--cell-timeout-ms", type=int, default=120000, help="with --scope-sweep: solver timeout per cell (default 120000); a timed-out cell prints 'unknown'")
    g.add_argument("--sweep-widths", action="store_true", help="consumer width curve: minimum flips for the masks 'lowest n bits' of the goal output, n=1..W, in the one scope given "
                   "by --input-sites/--init (use with --scope-sweep or alone); prints the flips-versus-width table")
    g.add_argument("--timeout-s", type=float, metavar="SEC", help="hard wall-clock limit for the whole run (model build included): the work runs in a worker process that is killed "
                   "at the deadline; result is exit 2 'unknown', never 'no attack'")
    g.add_argument("--sweep-out", metavar="FILE", help="with --scope-sweep: also write the table to FILE (.json or .csv)")
    a.add_argument("--no-honest-check", action="store_true",
                   help="downgrade the 'honest input does not reach the goal' configuration error to a warning")
    a.add_argument("--exit-zero", action="store_true", help="always exit 0 unless there is an input error")
    sp.add_parser("example-path", help="print the directory of the bundled examples")
    # listed for --help only: main() hands these to evidence.cli before argparse runs (no z3 needed)
    for name, hlp in (("margin", "attack-potential margin estimate from result files"),
                      ("evidence", "evidence report (HTML and/or Markdown) from result files"),
                      ("sarif", "SARIF 2.1.0 for code scanning from result files"),
                      ("check", "CI check over a targets file (runs or reads results; exit 1 below target)"),
                      ("validate-sarif", "check a SARIF file against the schema subset and GitHub's upload rules"),
                      ("evidence-example", "write the example V0/V1/V2 outputs from the bundled recorded results")):
        sp.add_parser(name, help=hlp + "; see `glitchsat " + name + " --help`", add_help=False)
    return ap


def main(argv=None):
    """H2 (N9): SIGTERM/SIGHUP become SystemExit so `finally` blocks run (temp dirs removed, --timeout-s worker and its yosys killed)."""
    lst = list(sys.argv[1:] if argv is None else argv)
    if lst and lst[0] in _EVIDENCE_CMDS:   # evidence tools (margin, evidence report, SARIF, CI check): no z3 needed
        from .evidence import cli as evidence_cli
        return evidence_cli.main(lst)
    old = {}
    try:
        for sg in (signal.SIGTERM, signal.SIGHUP):
            old[sg] = signal.signal(sg, lambda n, f: (_ for _ in ()).throw(SystemExit(128 + n)))
    except ValueError:   # not in the main thread
        old = {}
    try:
        return _main(argv)
    finally:
        for sg, h in old.items():
            signal.signal(sg, h)


def _main(argv=None):
    args = build_parser().parse_args(argv)
    if args.cmd == "example-path":
        print(example_dir())
        return EXIT_OK
    if runner is None:
        print(f"error: {Z3_MISSING}", file=sys.stderr)
        return EXIT_ERROR
    command = "faultbound-wt " + " ".join(shlex.quote(x) for x in (argv if argv is not None else sys.argv[1:]))
    try:
        th = load(args.config)
        if args.max_flips is not None:
            th.max_flips = args.max_flips
        if args.cycles is not None:
            th.cycles = args.cycles
        if args.no_honest_check:
            th.honest_check = False
        if args.goal_out is not None:
            th.output = args.goal_out
        if args.accept_value is not None:
            try:
                th.bad_value = int(args.accept_value, 0)
            except ValueError:
                raise ConfigError(f"--accept-value {args.accept_value!r} is not an integer")
        if args.consumer_bits is not None:
            th.consumer_bits = parse_mask(args.consumer_bits)
        if args.input_sites is not None:
            th.input_sites = args.input_sites
        if args.init is not None:
            th.init = args.init
        if args.count_rule is not None:
            th.count_rule = args.count_rule
        validate(th)
        if args.timeout_s is not None and not args.timeout_s > 0:
            raise ConfigError("--timeout-s must be > 0")
        sweep_mode = bool(args.synth_sweep or args.scope_sweep or args.sweep_widths)
        if sweep_mode:   # H2 (N3): sweeps write their table to --report (.json or .csv); --badge/.sarif/.junit.xml have no meaning for a table: exit 3
            if args.badge:
                raise ConfigError("--badge is not supported with --scope-sweep/--sweep-widths/--synth-sweep (a sweep has no single verdict); use --report FILE.json or FILE.csv")
            for r in args.report:
                if not r.lower().endswith((".json", ".csv")):
                    raise ConfigError(f"--report {r!r}: with a sweep only .json or .csv reports are supported (not supported: .sarif, .junit.xml)")
        for r in list(args.report) + ([args.badge] if args.badge else []) + ([args.sweep_out] if args.sweep_out else []):   # H4 (F5): fail before the solve
            d = os.path.dirname(os.path.abspath(r))
            if not os.path.isdir(d):
                raise ConfigError(f"output file {r!r}: directory {d!r} does not exist (checked before the analysis; create it first)")
        if args.goal_out is not None:   # a CLI flag overrides the config key, so the 'built-in default in use' warning must not name it
            th.defaulted = [x for x in th.defaulted if x != "property.output"]
        if args.accept_value is not None:
            th.defaulted = [x for x in th.defaulted if x != "property.bad_value"]
        if args.synth_sweep:   # PS6
            from . import synth_sweep
            if args.scope_sweep or args.sweep_widths or args.sweep_count_rules:
                raise ConfigError("--synth-sweep cannot be combined with --scope-sweep/--sweep-widths/--sweep-count-rules (run them separately; the scope of the synth sweep is the configured one)")
            extra = synth_sweep.load_variants(args.synth_variants) if args.synth_variants else None
            sel = [x.strip() for x in args.synth_select.split(",") if x.strip()] if args.synth_select else None
            if args.cell_timeout_ms < 0:
                raise ConfigError("--cell-timeout-ms must be >= 0")
            if not args.netlist.endswith((".v", ".sv")):
                raise runner.InputError("--synth-sweep needs a Verilog input (.v / .sv) with --top")
            if args.timeout_s:
                st, sw = runner.run_with_timeout("synth_sweep", args.netlist, th, args.timeout_s, command=command, top=args.top, variants=sel,
                                                 cell_timeout_ms=args.cell_timeout_ms, extra_variants=extra)
                if st == "timeout":
                    print(f"unknown: wall-clock timeout of {args.timeout_s} s reached before the synthesis sweep finished; this is NOT 'no attack' (no table produced).", file=sys.stderr)
                    return EXIT_OK if args.exit_zero else EXIT_UNKNOWN
            else:
                sw = synth_sweep.synth_sweep(args.netlist, th, top=args.top, variants=sel, cell_timeout_ms=args.cell_timeout_ms, command=command, extra_variants=extra)
            for r in dict.fromkeys(([args.sweep_out] if args.sweep_out else []) + args.report):
                reports.write_sweep(sw, r)
            print(_safe_block(synth_sweep.text(sw)))
            for r in dict.fromkeys(([args.sweep_out] if args.sweep_out else []) + args.report):
                print(f"  wrote {r}")
            vs = sw["variants"]
            if any(v["cost"] == "config-problem" for v in vs):
                print("error: the honest input does not reach the goal in the fault-free design (see config-problem rows)", file=sys.stderr)
                return EXIT_ERROR
            if args.exit_zero:
                return EXIT_OK
            if any(v.get("verdict") == runner.ATTACK for v in vs):
                return EXIT_ATTACK
            return EXIT_UNKNOWN if any(v["cost"] in ("unknown",) for v in vs) else EXIT_OK
        if args.sweep_count_rules and not args.scope_sweep:
            raise ConfigError("--sweep-count-rules needs --scope-sweep")
        if args.scope_sweep or args.sweep_widths:
            rules = None
            if args.sweep_count_rules:
                rules = []
                for x in (y.strip() for y in args.sweep_count_rules.split(",") if y.strip()):
                    x = "fanout_pins" if x == "fanout" else x
                    if x not in ("stem", "fanout_pins", "fanout_gates"):
                        raise ConfigError(f"--sweep-count-rules: {x!r} is not one of stem, fanout_pins, fanout_gates (fanout = fanout_pins; 'branch' is not implemented)")
                    if x not in rules:
                        rules.append(x)
                if not rules:
                    raise ConfigError("--sweep-count-rules is empty")
            masks = [parse_mask(x) for x in args.sweep_masks.split(",") if x.strip()] if args.sweep_masks else []
            if args.cell_timeout_ms < 0:
                raise ConfigError("--cell-timeout-ms must be >= 0")
            if args.timeout_s:
                st, sw = runner.run_with_timeout("sweep", args.netlist, th, args.timeout_s, command=command, top=args.top, masks=masks,
                                                 cell_timeout_ms=args.cell_timeout_ms, widths=args.sweep_widths, count_rules=rules)
                if st == "timeout":
                    print(f"unknown: wall-clock timeout of {args.timeout_s} s reached before the sweep finished; this is NOT 'no attack' (no table produced). "
                          "Raise --timeout-s or --cell-timeout-ms/lower --max-flips.", file=sys.stderr)
                    return EXIT_OK if args.exit_zero else EXIT_UNKNOWN
            else:
                sw = runner.sweep(args.netlist, th, masks=masks, cell_timeout_ms=args.cell_timeout_ms, command=command, top=args.top, widths=args.sweep_widths, count_rules=rules)
            outs = list(dict.fromkeys(([args.sweep_out] if args.sweep_out else []) + args.report))
            for r in outs:
                reports.write_sweep(sw, r)
            print(runner.width_text(sw) if sw.get("mode") == "widths" else runner.sweep_text(sw))
            for r in outs:
                print(f"  wrote {r}")
            costs = [c["cost"] for c in sw["cells"]]
            if any(c == "config-problem" for c in costs):
                print("error: for at least one goal the honest input does not reach the goal in the fault-free design (see config-problem cells)", file=sys.stderr)
                return EXIT_ERROR
            if args.exit_zero:
                return EXIT_OK
            if any(c["verdict"] == runner.ATTACK for c in sw["cells"]):
                return EXIT_ATTACK
            return EXIT_UNKNOWN if "unknown" in costs else EXIT_OK
        if args.timeout_s:
            st, rep = runner.run_with_timeout("analyze", args.netlist, th, args.timeout_s, command=command, top=args.top)
            if st == "timeout":
                rep = runner.timeout_report(args.netlist, th, args.timeout_s, rep, command=command, top=args.top)
        else:
            rep = runner.analyze(args.netlist, th, command=command, top=args.top)
        for r in args.report:
            reports.write(rep, r)
        if args.badge:
            reports.write_badge(rep, args.badge)
    except (ConfigError, runner.InputError, ValueError) as e:
        print(f"error: {_safe(e)}", file=sys.stderr)
        return EXIT_ERROR
    except Exception as e:   # H1: a crash must never look like 'attack found' (python's default exit code is 1)
        print(f"internal error ({type(e).__name__}: {_safe(e)}); no verdict was produced", file=sys.stderr)
        return EXIT_INTERNAL
    b = rep["bound"]
    for w in rep.get("config_warnings", []):
        print("warning: " + _safe(w), file=sys.stderr)
    if rep["verdict"] == runner.CONFIG_PROBLEM:
        print(f"error: {rep['note']}", file=sys.stderr)
        for r in args.report:
            print(f"  wrote {r}")
        for line in runner.scope_lines(rep["scope"]):
            print(line)
        return EXIT_ERROR
    if rep.get("timed_out"):
        print(f"{rep['provenance']['top']}: {rep['verdict']}  (wall-clock timeout {args.timeout_s} s reached; <= {b['max_flips']} flips, {b['cycles']} cycles)")
        print("  " + rep["note"])
        for line in runner.scope_lines(rep["scope"]) if rep["scope"].get("init_state") else []:
            print(_safe(line))
        for r in args.report:
            print(f"  wrote {r}")
        return EXIT_OK if args.exit_zero else EXIT_UNKNOWN
    print(f"{rep['provenance']['top']}: {rep['verdict']}  (<= {b['max_flips']} flips, {b['cycles']} cycles; "
          f"{rep['provenance']['netlist_stats']['gates']} gates, {rep['provenance']['netlist_stats']['flops']} flops; {rep['runtime_s']}s)")
    if rep.get("faults"):
        print("  minimum attack:", ", ".join(f"{_safe(f['net'])}@{f['cycle']}" for f in rep["faults"]))
    elif rep["verdict"] == runner.ATTACK:
        print("  minimum attack: NONE NEEDED (0 flips)")
    if rep.get("explanation"):
        print("  " + _safe(rep["explanation"]["summary"]))
    print("  " + rep["note"])
    for line in runner.scope_lines(rep["scope"]):
        print(_safe(line))
    for r in args.report:
        print(f"  wrote {r}")
    if args.exit_zero:
        return EXIT_OK
    return {"NO_ATTACK_UP_TO_BOUND": EXIT_OK, "ATTACK_FOUND": EXIT_ATTACK}.get(rep["verdict"], EXIT_UNKNOWN)


if __name__ == "__main__":
    sys.exit(main())
