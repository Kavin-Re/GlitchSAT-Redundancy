"""Synthesis-flow sweep: the same Verilog is synthesized by a small documented set of Yosys flows
(research/c2/e2_variance axes: flow plain/opt, flatten before/after abc, abc script, opt_merge, keep on/off) and the minimum number of
modelled bit flips is computed on each resulting netlist. A verdict belongs to ONE netlist hash; this shows how much it moves with the build.
Every Yosys script is generated from the template below (kept in the JSON result) and run as `yosys -q -s flow.ys` in a private directory that holds
a copy of the source as design.v (single-file Verilog: `include of other files is not supported here)."""
import copy, hashlib, json, os, re, shutil, subprocess, tempfile, time
try:
    import tomllib
except ModuleNotFoundError:          # Python 3.10: the same parser, from the tomli package
    import tomli as tomllib

from . import __version__, _engine as eng
from . import runner
from .config import ConfigError

SYNTH_SCHEMA = "faultbound-wt-synthsweep/1"

# Script template (one Yosys command per line; a script FILE is used because newer Yosys splits `-p` on ',' inside `abc -g AND,OR`).
TEMPLATE = "read_verilog {src}\nhierarchy -top {top}\n{pre}\n{abc}\n{post}\nwrite_json {out}\n"
PRE_PLAIN = "proc; opt_clean; techmap; opt_clean"
PRE_OPT = "synth -top {top}; dffunmap"
PRE_FLAT = "proc; setattr -mod -unset keep_hierarchy *; flatten; opt_clean; techmap; opt_clean"
ABC_DEF = "abc -g AND,OR,XOR,MUX"
POST_PLAIN = "opt_clean; setattr -mod -unset keep_hierarchy *; flatten; opt_clean; techmap; opt_clean"
POST_MERGE = "opt_clean; setattr -mod -unset keep_hierarchy *; flatten; opt_clean; techmap; opt_merge; opt_clean"
POST_FLAT = "opt_clean"

# name -> (description, pre, abc, post, strip_keep)
BUILTIN = {
    "plain": ("project flow (scripts/synth.sh plain): map each module with abc, THEN flatten, no opt_merge", PRE_PLAIN, ABC_DEF, POST_PLAIN, False),
    "plain_opt_merge": ("plain + opt_merge after flatten (identical logic over the same input collapses)", PRE_PLAIN, ABC_DEF, POST_MERGE, False),
    "flatten_before_abc": ("flatten BEFORE abc (abc sees all module copies at once)", PRE_FLAT, ABC_DEF, POST_FLAT, False),
    "abc_fast": ("plain with `abc -fast`", PRE_PLAIN, "abc -fast -g AND,OR,XOR,MUX", POST_PLAIN, False),
    "abc_no_mux": ("plain with abc gate set AND,OR,XOR (no MUX)", PRE_PLAIN, "abc -g AND,OR,XOR", POST_PLAIN, False),
    "opt_flow": ("full Yosys `synth` + dffunmap, then abc and the plain tail (scripts/synth.sh opt)", PRE_OPT, ABC_DEF, POST_PLAIN, False),
    "plain_keep_off": ("plain, with every `(* keep *)` attribute stripped from the source (keep_hierarchy is kept)", PRE_PLAIN, ABC_DEF, POST_PLAIN, True),
    "opt_flow_keep_off": ("opt flow, `(* keep *)` stripped", PRE_OPT, ABC_DEF, POST_PLAIN, True),
}
_KEEP_RE = re.compile(r"\(\*\s*keep\s*\*\)\s*")

# H2 (N1/PS6): ALLOW-LIST of Yosys commands per step (replaces the PS6 deny-list). A custom `pre` / `post` step may contain ONLY the commands
# below with ONLY the listed options; the `abc` step may contain ONLY `abc` with the listed options (or be empty). Anything else is refused (exit 3).
# No command that reads or writes a file, runs a program, loads code or opens a shell is on the list (techmap -map, read_*, write_*, script, exec,
# shell, plugin, tee, ... are all refused). Custom variants files are nevertheless TRUSTED INPUT: they are written by the person who runs the tool,
# the allow-list is a safety net against mistakes and malicious pull requests, not a sandbox for hostile Yosys features not on the list.
_GATES = {"AND", "NAND", "OR", "NOR", "XOR", "XNOR", "ANDNOT", "ORNOT", "MUX", "NMUX", "AOI3", "OAI3", "AOI4", "OAI4"}
_IDENT = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*\Z")
ALLOWED_PRE_POST = {   # command -> (flags without value, flags with a value validated by ('ident'|'gates'))
    "proc": (set(), {}), "opt_clean": ({"-purge"}, {}), "clean": ({"-purge"}, {}), "opt": ({"-fast", "-full", "-purge"}, {}),
    "opt_merge": ({"-share_all", "-nomux"}, {}), "opt_expr": ({"-mux_undef", "-mux_bool", "-fine", "-full"}, {}), "opt_muxtree": (set(), {}),
    "opt_reduce": ({"-fine", "-full"}, {}), "opt_dff": (set(), {}), "flatten": (set(), {}), "techmap": (set(), {}), "dffunmap": (set(), {}),
    "synth": ({"-flatten", "-noabc"}, {"-top": "ident"}),
}
ALLOWED_ABC = {"abc": ({"-fast"}, {"-g": "gates"})}
_SETATTR = ["setattr", "-mod", "-unset", "keep_hierarchy", "*"]   # the one setattr form the flows use
_STEP_TABLE = {"pre": ALLOWED_PRE_POST, "post": ALLOWED_PRE_POST, "abc": ALLOWED_ABC}
_TOKEN = re.compile(r"[A-Za-z0-9_,\-.*{}$]+\Z")


def _cmds(txt):
    return [c.strip() for c in re.split(r"[;\n]", txt or "") if c.strip()]


def _check_cmds(name, field, txt):
    table = _STEP_TABLE[field]
    for c in _cmds(txt):
        bad = lambda why: ConfigError(f"synth variant {name!r}: command {c!r} in `{field}` is not allowed ({why}). Allowed in `{field}`: "
                                      + ", ".join(sorted(table) + (["setattr -mod -unset keep_hierarchy *"] if field != "abc" else [])) + "; see QUICKSTART 4c")
        toks = c.split()
        if any(not _TOKEN.match(t) for t in toks):
            raise bad("characters outside letters, digits and _ , - . * { } $")
        w = toks[0]
        if field != "abc" and w == "setattr":
            if toks != _SETATTR:
                raise bad("only `setattr -mod -unset keep_hierarchy *` is allowed")
            continue
        if w not in table:
            raise bad("command is not on the allow-list for this step")
        flags, valued = table[w]
        i = 1
        while i < len(toks):
            t = toks[i]
            if t in flags:
                i += 1
            elif t in valued:
                if i + 1 >= len(toks):
                    raise bad(f"option {t} needs a value")
                val = toks[i + 1]
                if valued[t] == "ident" and not (val == "{top}" or _IDENT.match(val)):
                    raise bad(f"value of {t} must be a plain identifier or {{top}}")
                if valued[t] == "gates" and not (val and all(g in _GATES for g in val.split(","))):
                    raise bad(f"value of {t} must be a comma list of {sorted(_GATES)}")
                i += 2
            else:
                raise bad(f"option {t!r} is not on the allow-list")


def builtin_variants():
    return [dict(name=n, description=d, pre=p, abc=a, post=po, strip_keep=k, source="built-in") for n, (d, p, a, po, k) in BUILTIN.items()]


def load_variants(path):
    """Custom flows from a .toml ([[variant]] tables) or .json ({"variant": [...]}, or a bare list). Each: name, optional description,
    optional extends (a built-in name; unset fields default to the `plain` flow), pre, abc, post (Yosys commands separated by ';'),
    strip_keep (bool)."""
    try:
        if path.lower().endswith(".json"):
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        elif path.lower().endswith(".toml"):
            with open(path, "rb") as f:
                raw = tomllib.load(f)
        else:
            raise ConfigError(f"--synth-variants {path!r}: use a .toml or .json file")
    except (OSError, ValueError) as e:   # tomllib.TOMLDecodeError and json.JSONDecodeError are ValueErrors
        raise ConfigError(f"cannot read --synth-variants {path}: {e}")
    items = raw if isinstance(raw, list) else (raw.get("variant") or raw.get("variants") if isinstance(raw, dict) else None)
    if not isinstance(items, list) or not items:
        raise ConfigError(f"--synth-variants {path}: expected a non-empty list of variants ([[variant]] in TOML, or a JSON list / {{\"variant\": [...]}})")
    out, seen = [], set(BUILTIN)
    base = {n: dict(pre=p, abc=a, post=po, strip_keep=k) for n, (d, p, a, po, k) in BUILTIN.items()}
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            raise ConfigError(f"--synth-variants {path}: entry {i} is not a table")
        bad = set(it) - {"name", "description", "extends", "pre", "abc", "post", "strip_keep"}
        if bad:
            raise ConfigError(f"--synth-variants {path}: entry {i} has unknown keys {sorted(bad)}")
        name = it.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,40}", name):
            raise ConfigError(f"--synth-variants {path}: entry {i} needs a `name` of letters, digits, _ . - (max 40)")
        if name in seen:
            raise ConfigError(f"--synth-variants {path}: variant name {name!r} is duplicated or collides with a built-in name")
        seen.add(name)
        ext = it.get("extends", "plain")
        if ext not in base:
            raise ConfigError(f"variant {name!r}: extends={ext!r} is not a built-in variant ({sorted(base)})")
        v = dict(base[ext])
        for k in ("pre", "abc", "post"):
            if k in it:
                if not isinstance(it[k], str):
                    raise ConfigError(f"variant {name!r}: `{k}` must be a string")
                _check_cmds(name, k, it[k])
                v[k] = it[k]
        if "strip_keep" in it:
            if not isinstance(it["strip_keep"], bool):
                raise ConfigError(f"variant {name!r}: strip_keep must be true/false")
            v["strip_keep"] = it["strip_keep"]
        out.append(dict(name=name, description=str(it.get("description", f"custom (extends {ext})")), source=os.path.basename(path), **v))
    return out


def make_script(v, src, top, out):
    runner.check_top(top)
    for k in ("pre", "abc", "post"):   # defence in depth: also variants that did not come through load_variants (e.g. via the worker job file)
        _check_cmds(v.get("name", "?"), k, v[k])
    lines = TEMPLATE.format(src=src, top=top, pre="\n".join(_cmds(v["pre"].replace("{top}", top))), abc="\n".join(_cmds(v["abc"])),
                            post="\n".join(_cmds(v["post"])), out=out)
    return "\n".join(l for l in lines.split("\n") if l.strip()) + "\n"


def _yosys_exe():
    exe = shutil.which("yosys")
    if not exe:
        raise runner.InputError("--synth-sweep needs `yosys` on PATH (it synthesizes the Verilog several ways); it was not found. "
                                "Install Yosys or pass a Yosys JSON netlist to `analyze` instead.")
    return exe


def synth_sweep(verilog, th, top=None, variants=None, cell_timeout_ms=120000, command=None, workdir=None, extra_variants=None, synth_timeout_s=300):
    top = top or th.top
    if not (verilog.endswith(".v") or verilog.endswith(".sv")):
        raise runner.InputError("--synth-sweep needs a Verilog input (.v / .sv) with --top: it synthesizes the source several ways")
    if not top:
        raise runner.InputError("--synth-sweep needs --top (or [netlist] top in the config)")
    if not os.path.isfile(verilog):
        raise runner.InputError(f"no such file: {verilog}")
    exe = _yosys_exe()
    ver = runner.yosys_version()
    vs = builtin_variants() + list(extra_variants or [])
    if variants:
        keep = set(variants)
        unk = keep - {v["name"] for v in vs}
        if unk:
            raise ConfigError(f"unknown synth variant(s) {sorted(unk)}; available: {[v['name'] for v in vs]}")
        vs = [v for v in vs if v["name"] in keep]
    tmp = tempfile.mkdtemp(prefix="fbwt_ss_", dir=workdir)
    src = os.path.realpath(verilog)
    t0 = time.time()
    rows, by_sha = [], {}
    try:
        for v in vs:
            d = os.path.join(tmp, v["name"])
            os.makedirs(d)
            # The source is copied to `design.v` in a private directory and Yosys runs there with relative names, so the `src` attributes
            # (and therefore the netlist hash) do not depend on where the file lives or on the temp directory name.
            with open(src, encoding="utf-8", errors="replace") as f:
                txt = f.read()
            with open(os.path.join(d, "design.v"), "w", encoding="utf-8") as f:
                f.write(_KEEP_RE.sub("", txt) if v["strip_keep"] else txt)
            out = os.path.join(d, "netlist.json")
            script = make_script(v, "design.v", top, "netlist.json")
            ys = os.path.join(d, "flow.ys")
            with open(ys, "w", encoding="utf-8") as f:
                f.write(script)
            row = dict(name=v["name"], description=v["description"], source=v["source"], script=script, yosys_command="yosys -q -s flow.ys  (run in a directory holding design.v)")
            try:
                rc, _, serr = runner.run_yosys([exe, "-q", "-s", "flow.ys"], cwd=d, timeout=synth_timeout_s)
                err = serr[-600:] if rc else None
            except subprocess.TimeoutExpired:
                err = f"yosys timed out after {synth_timeout_s} s"
            if err or not os.path.isfile(out):
                row.update(status="synthesis_failed", cost="synth-failed", verdict=None, error=err or "no netlist written")
                rows.append(row)
                continue
            sha = runner.sha256_file(out)
            row["netlist_sha256"] = sha
            if sha in by_sha:   # identical bytes: same verdict by construction, reuse it
                prev = by_sha[sha]
                row.update({k: prev[k] for k in ("status", "cost", "verdict", "gates", "flops", "min_faults", "runtime_s", "faults") if k in prev}, same_netlist_as=prev["name"])
                rows.append(row)
                continue
            try:
                nl = eng.Netlist(out, top)
                row.update(gates=nl.stats()["gates"], flops=nl.stats()["flops"])
            except eng.NetlistError as e:
                row.update(status="engine_unsupported", cost="unsupported", verdict=None, error=str(e)[:300])
                by_sha[sha] = row
                rows.append(row)
                continue
            c = copy.deepcopy(th)
            c.timeout_ms = cell_timeout_ms
            c.top = top
            r = runner.analyze(out, c, top=top, workdir=workdir)
            row.update(status="ok", verdict=r["verdict"], cost=runner._cell(r, th.max_flips), min_faults=r.get("min_faults"), runtime_s=r["runtime_s"],
                       faults=[f"{f['net']}@{f['cycle']}" for f in r.get("faults", [])])
            by_sha[sha] = row
            rows.append(row)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    summ = summarize(rows, th.max_flips)
    return dict(schema=SYNTH_SCHEMA, label="MEASURED (this run; tool)", source_sha256=runner.sha256_file(verilog), top=top, yosys=ver,
                command=command, tool_version=__version__, count_rule=th.count_rule,
                scope=dict(input_sites=th.input_sites, init=th.init, consumer_bits=("all" if th.consumer_bits is None else f"0x{th.consumer_bits:X}"),
                           goal=f"{th.output} == 0x{th.bad_value:X}", count_rule=th.count_rule),
                bounds=dict(max_flips=th.max_flips, cycles=th.cycles, cell_timeout_ms=cell_timeout_ms), template=TEMPLATE,
                variants=rows, summary=summ, runtime_s=round(time.time() - t0, 3),
                note=("one row = one synthesis flow = one netlist hash; cost = minimum number of flips found (exact when no '<='), '>k' = none within <= k flips and the cycle bound, "
                      "'unknown' = solver timeout (NOT 'no attack'), 'unsupported' = the engine cannot read that netlist (no verdict), 'synth-failed' = Yosys error. "
                      + runner.STATEMENT + ". Faults are modelled bit flips; the variants are a small sample of synthesis choices, not all of them."))


def _num(c):
    m = re.fullmatch(r"(<=)?(\d+)", c or "")
    return int(m.group(2)) if m else None


def summarize(rows, k):
    ok = [r for r in rows if r.get("status") == "ok"]
    nums = [n for n in (_num(r["cost"]) for r in ok) if n is not None]
    lows = [r for r in ok if str(r["cost"]).startswith(">")]
    unk = [r for r in ok if r["cost"] == "unknown"]
    lo = min(nums) if nums else None
    hi = (f">{k}" if lows else (max(nums) if nums else None))
    if lo is None and lows:
        lo = f">{k}"
    n_attack = sum(1 for r in ok if r["verdict"] == runner.ATTACK)
    n_none = len(lows)
    rng = f"{lo}..{hi}" if lo is not None else "n/a"
    other = []
    if unk: other.append(f"{len(unk)} unknown")
    bad = [r for r in rows if r.get("status") not in ("ok", None)]
    if bad: other.append(f"{len(bad)} not analysed ({', '.join(sorted({r['status'] for r in bad}))})")
    line = f"verdict changes across {len(rows)} variants: min flips ranged {rng}"
    changed = len({r["cost"] for r in ok}) > 1
    tail = (f" (at max_flips={k}: ATTACK_FOUND in {n_attack}, NO_ATTACK_UP_TO_BOUND in {n_none}"
            + (f"; " + ", ".join(other) if other else "") + ")")
    return dict(line=line + tail + ("" if changed else " [no change across the analysed variants]"), changed=changed, min_low=lo, min_high=hi,
                n_variants=len(rows), n_attack=n_attack, n_no_attack=n_none, n_unknown=len(unk), n_not_analysed=len(bad),
                distinct_netlists=len({r.get("netlist_sha256") for r in rows if r.get("netlist_sha256")}))


def text(sw):
    b = sw["bounds"]
    hd = ["variant", "netlist sha256 (16)", "gates", "flops", "min flips", "time"]
    rows = [[r["name"], (r.get("netlist_sha256") or "-")[:16] + ("*" if r.get("same_netlist_as") else ""), str(r.get("gates", "-")), str(r.get("flops", "-")),
             str(r["cost"]), (f"{r['runtime_s']}s" if r.get("runtime_s") is not None else "-")] for r in sw["variants"]]
    wd = [max(len(x[i]) for x in [hd] + rows) for i in range(len(hd))]
    fmt = lambda x: "  " + " | ".join(c.ljust(wd[i]) for i, c in enumerate(x))
    out = [f"{sw['top']}: synthesis sweep ({sw['yosys']}; count rule {sw['count_rule']}; max_flips={b['max_flips']}, cycles={b['cycles']}, per-cell timeout {b['cell_timeout_ms']} ms; "
           f"source sha256 {sw['source_sha256']})",
           fmt(hd), "  " + "-+-".join("-" * w for w in wd)] + [fmt(r) for r in rows]
    if any(r.get("same_netlist_as") for r in sw["variants"]):
        out.append("  * = byte-identical to an earlier variant's netlist (" + ", ".join(f"{r['name']}={r['same_netlist_as']}" for r in sw["variants"] if r.get("same_netlist_as")) + ")")
    for r in sw["variants"]:
        if r.get("error"):
            out.append(f"  {r['name']}: {r['status']}: {r['error'][:200]}")
    out.append("  " + sw["summary"]["line"])
    out.append("  " + sw["note"])
    return "\n".join(out)


def write_csv(sw, path):
    from .reports import csv_cell
    rows = ["variant,netlist_sha256,gates,flops,verdict,cost,runtime_s,status,yosys,count_rule"]
    for r in sw["variants"]:
        vals = [r["name"], r.get("netlist_sha256", ""), r.get("gates", ""), r.get("flops", ""), r.get("verdict") or "", r["cost"], r.get("runtime_s", ""), r.get("status"), sw["yosys"], sw["count_rule"]]
        rows.append(",".join(csv_cell(x) for x in vals))
    return "\n".join(rows) + "\n"
