"""Read GlitchSAT result files into one plain structure (no z3 needed).

Accepted inputs
  * product CLI report      `glitchsat analyze ... --report x.json`          (schema "faultbound-wt-report/1")
  * reference-engine run    `scripts/glitchsat.py check ... --out x.json`  (results/reproduce/*.json)
  * reproduce summary       results/reproduce_summary.json (rows; no hashes, so provenance is thinner)
  * attack surface          ext/surface attack_surface.py --json        (schema "glitchsat-attack-surface/1")
  * redundancy lint         ext/surface merge_lint.py --json            (schema "glitchsat-merge-lint/1")
  * unbounded proof run     ext/unbounded unbounded.py (one file per design and flip budget, e.g. v2_stored_k2.json)
"""
import hashlib, json, os


class InputError(ValueError):
    pass


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise InputError(f"cannot read JSON {path!r}: {e}")


def _fault_list(raw):
    out = []
    for f in raw or []:
        if isinstance(f, dict):
            out.append(dict(net=str(f["net"]), cycle=int(f["cycle"]), kind=f.get("kind", "")))
        else:   # [net, cycle] as in the reproduce summary / surface listing
            out.append(dict(net=str(f[0]), cycle=int(f[1]), kind=""))
    return out


def from_product_report(d, path):
    prov, b = d.get("provenance", {}), d.get("bound", {})
    return dict(
        source_file=path, source_format="product-report", label=d.get("label", ""),
        top=prov.get("top", ""), variant=os.path.basename(prov.get("netlist_path", "") or path),
        verdict=d["verdict"], bound_k=int(b.get("max_flips", 0)), cycles=int(b.get("cycles", 0)),
        min_faults=d.get("min_faults"), faults=_fault_list(d.get("faults")),
        attacker_input=d.get("attacker_input_value"), goal=b.get("property", ""), attacker=b.get("attacker_input", ""),
        fault_model=b.get("fault_model", ""), scope=d.get("scope", {}), note=d.get("note", ""),
        explanation=(d.get("explanation") or {}).get("summary", ""), fix_pattern=(d.get("explanation") or {}).get("fix_pattern", ""),
        gates=(prov.get("netlist_stats") or {}).get("gates"), flops=(prov.get("netlist_stats") or {}).get("flops"),
        runtime_s=d.get("runtime_s"),
        provenance=dict(tool=prov.get("tool", ""), tool_version=prov.get("tool_version", ""), command=prov.get("command", ""),
                        netlist_path=prov.get("netlist_path", ""), netlist_sha256=prov.get("netlist_sha256", ""),
                        hash_scope="synthesized netlist (full SHA-256)",
                        yosys=prov.get("synthesis_yosys") or prov.get("netlist_yosys_creator") or "",
                        z3=prov.get("z3", ""), python=prov.get("python", ""), utc=prov.get("utc", ""),
                        source_sha256=prov.get("source_sha256", "")))


def from_engine_run(d, path):
    b = d.get("bound", {})
    flow = d.get("synth_flow", "")
    design = d.get("design", "")
    given = flow == "given-netlist"
    return dict(
        source_file=path, source_format="engine-run", label=d.get("label", ""),
        top=d.get("top", ""), variant=f"{design} ({flow})" if flow else design,
        verdict=d["verdict"], bound_k=int(b.get("max_faults", 0)), cycles=int(b.get("cycles", 0)),
        min_faults=d.get("min_faults"), faults=_fault_list(d.get("faults")),
        attacker_input=d.get("attacker_input"), goal=b.get("goal", ""), attacker=b.get("attacker_input", ""),
        fault_model=b.get("fault_model", ""), scope={}, note=d.get("note", ""),
        explanation=(d.get("explanation") or {}).get("summary", ""), fix_pattern=(d.get("explanation") or {}).get("fix_pattern", ""),
        gates=(d.get("netlist") or {}).get("gates"), flops=(d.get("netlist") or {}).get("flops"),
        runtime_s=(d.get("runtime_s") or {}).get("solve_and_minimize") if isinstance(d.get("runtime_s"), dict) else d.get("runtime_s"),
        provenance=dict(tool=d.get("tool", ""), tool_version="", command="", netlist_path=d.get("netlist_json", ""),
                        netlist_sha256=d.get("design_sha256_16", ""),
                        hash_scope=("netlist file, first 16 hex digits of SHA-256" if given else
                                    f"RTL source {design}, first 16 hex digits of SHA-256 (the synthesized netlist is not stored with this result)"),
                        yosys="", z3="", python="", utc="", source_sha256="" if given else d.get("design_sha256_16", ""),
                        source_path="" if given else design))


def from_summary(d, path, design=None):
    out = []
    for i, r in enumerate(d.get("rows", [])):
        if design and r.get("design") != design:
            continue
        out.append(dict(
            source_file=f"{path}#rows[{i}]", source_format="reproduce-summary", label=r.get("label", ""),
            top=r.get("design", ""), variant=f"{r.get('design')} ({r.get('netlist')})",
            verdict=r["verdict"], bound_k=int(r["k"]), cycles=int(r.get("cycles", d.get("cycles", 0))),
            min_faults=r.get("min_faults"), faults=_fault_list(r.get("faults")), attacker_input=None, goal="", attacker="",
            fault_model="", scope={}, note=d.get("note", ""), explanation="", fix_pattern="", gates=None, flops=None,
            runtime_s=r.get("runtime_s"),
            provenance=dict(tool="", tool_version="", command="", netlist_path="", netlist_sha256="", hash_scope="not recorded in the summary",
                            yosys="", z3="", python="", utc="", source_sha256="")))
    return out


def load_results(path, design=None):
    d = _read(path)
    if isinstance(d, dict) and d.get("schema", "").startswith("faultbound-wt-report"):
        return [from_product_report(d, path)]
    if isinstance(d, dict) and "rows" in d and isinstance(d["rows"], list):
        return from_summary(d, path, design)
    if isinstance(d, dict) and "verdict" in d and "bound" in d:
        return [from_engine_run(d, path)]
    raise InputError(f"{path}: not a GlitchSAT result (expected a product report, an engine run JSON or reproduce_summary.json)")


def load_surface(path):
    d = _read(path)
    if d.get("schema") != "glitchsat-attack-surface/1":
        raise InputError(f"{path}: not an attack-surface JSON (schema glitchsat-attack-surface/1)")
    d["_path"] = path
    return d


def load_lint(path):
    d = _read(path)
    if d.get("schema") != "glitchsat-merge-lint/1":
        raise InputError(f"{path}: not a merge-lint JSON (schema glitchsat-merge-lint/1)")
    d["_path"] = path
    return d


def group_variants(results):
    """Group per-k runs of the same netlist and derive the established minimum.

    min_faults  smallest minimum reported by any ATTACK_FOUND run (each run already minimises within its bound)
    lower_bound largest k with NO_ATTACK_UP_TO_BOUND (no attack with <= k flips), so min > lower_bound
    consistent  False if a no-attack bound is >= a found minimum (contradiction between runs)"""
    groups = {}
    for r in results:
        key = (r["top"], r["variant"], r["provenance"].get("netlist_sha256", ""), r["cycles"])
        groups.setdefault(key, []).append(r)
    out = []
    for key, runs in groups.items():
        runs.sort(key=lambda r: r["bound_k"])
        found = [r for r in runs if r["verdict"] == "ATTACK_FOUND" and r.get("min_faults") is not None]
        none = [r for r in runs if r["verdict"] == "NO_ATTACK_UP_TO_BOUND"]
        other = [r for r in runs if r["verdict"] not in ("ATTACK_FOUND", "NO_ATTACK_UP_TO_BOUND")]
        mn = min((r["min_faults"] for r in found), default=None)
        lb = max((r["bound_k"] for r in none), default=None)
        consistent = not (mn is not None and lb is not None and lb >= mn)
        witnesses, seen = [], set()
        for r in found:
            if r["min_faults"] == mn:
                sig = tuple(sorted((f["net"], f["cycle"]) for f in r["faults"]))
                if sig not in seen:
                    seen.add(sig)
                    witnesses.append(r["faults"])
        rep = (found or none or other)[-1]
        out.append(dict(top=key[0], variant=key[1], netlist_sha256=key[2], cycles=key[3], runs=runs, min_faults=mn,
                        no_attack_up_to=lb, consistent=consistent, witnesses=witnesses, representative=rep,
                        unknown=[r for r in other], max_bound=max(r["bound_k"] for r in runs)))
    return out


def sha_matches(a, b):
    """Compare a full and/or prefix hash (16-hex prefixes are used by the reference engine)."""
    a, b = (a or "").lower(), (b or "").lower()
    if not a or not b:
        return None
    n = min(len(a), len(b))
    return a[:n] == b[:n]


def load_unbounded(path):
    """One result of the unbounded (any number of cycles) checker: verdict per power-up assumption for one flip budget."""
    d = _read(path)
    if not (isinstance(d, dict) and "scopes" in d and "max_faults" in d and "verdict" in d and "netlist_sha256_16" in d):
        raise InputError(f"{path}: not an unbounded-proof result (expected keys scopes, max_faults, verdict, netlist_sha256_16)")
    scopes = {}
    for sc in d["scopes"]:
        meth = {k: (v.get("verdict") if isinstance(v, dict) else v) for k, v in (sc.get("methods") or {}).items()}
        scopes[sc["init"]] = dict(verdict=sc.get("verdict", ""), methods=meth,
                                  agree=len({v for v in meth.values()}) <= 1 if meth else None)
    return dict(_path=path, design=d.get("design", ""), netlist=d.get("netlist", ""), netlist_sha256=d["netlist_sha256_16"],
                top=d.get("top", ""), k=int(d["max_faults"]), verdict=d["verdict"], verdict_init=d.get("verdict_init", "known"),
                goal=(d.get("scope") or {}).get("goal", ""), fault_model=(d.get("scope") or {}).get("fault_model", ""),
                count_rule=(d.get("scope") or {}).get("count_rule", ""), scopes=scopes, note=d.get("note", ""),
                tool=d.get("tool", ""), backend=d.get("backend", ""), python=d.get("python", ""), label=d.get("label", ""))


def goal_key(goal):
    """'boot_word == 0x96 at some cycle < 6' and 'boot_word == 0x96 at some cycle' -> 'boot_word == 0x96'."""
    return (goal or "").split(" at some cycle")[0].strip().lower()


def summarize_unbounded(items, init="known"):
    """Per-budget verdicts of one netlist and goal -> proved_up_to (largest k proved with every k' <= k proved) and
    smallest_attack (smallest k with ATTACK_FOUND), for one power-up assumption."""
    if not items:
        return None
    by_k = {}
    for u in items:
        v = (u["scopes"].get(init) or {}).get("verdict") or (u["verdict"] if u["verdict_init"] == init else "")
        by_k[u["k"]] = v
    ks = sorted(by_k)
    proved_up_to = None
    for k in range(0, max(ks) + 1):
        if by_k.get(k) == "PROVED_UNBOUNDED":
            proved_up_to = k
        else:
            break
    attacks = [k for k in ks if by_k[k] == "ATTACK_FOUND"]
    disagree = [f"k={u['k']} {i}" for u in items for i, sc in u["scopes"].items() if sc.get("agree") is False]
    srt = sorted(items, key=lambda u: u["k"])
    note_from = next((u for u in srt if u["k"] == proved_up_to), srt[-1])
    return dict(init=init, by_k=by_k, proved_up_to=proved_up_to, smallest_attack=min(attacks) if attacks else None,
                checked_up_to=max(ks), unknown=[k for k in ks if by_k[k] not in ("PROVED_UNBOUNDED", "ATTACK_FOUND")],
                method_disagreements=disagree, other_inits={i: {u["k"]: (u["scopes"].get(i) or {}).get("verdict", "") for u in items}
                                                            for i in sorted({i for u in items for i in u["scopes"]}) if i != init},
                files=[u["_path"] for u in sorted(items, key=lambda u: u["k"])], tool=items[0]["tool"], backend=items[0]["backend"],
                python=items[0]["python"], note=note_from["note"], goal=items[0]["goal"], netlist=items[0]["netlist"],
                netlist_sha256=items[0]["netlist_sha256"], design=items[0]["design"], label=items[0]["label"])
