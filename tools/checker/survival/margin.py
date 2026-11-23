"""Security margin of one netlist: the minimum number of modelled faults that reach the stated goal.

Nothing is re-implemented here. Engines (config `margin.engines`, default `auto` = exhaustive up to
two flips, then fastsat for the rest of the budget; then z3 if that gave no verdict):
  exhaustive  ext/surface attack_surface.exhaustive  (complete within the bound; small designs)
  fastsat     ext/fastsat glitchsat_sat.solve        (direct CNF; PySAT/CaDiCaL when installed, bundled solver else)
  z3          scripts/glitchsat.py solve             (when z3 is installed)
and, on request (`margin.unbounded: true`), ext/unbounded for "any number of cycles".

Every figure is bounded and modelled: single-cycle bit flips of gate outputs and flop Q nets, at most k flips, within
T cycles (or all time when the unbounded proof succeeds), goal `output == value` while the attacker input != key.
"""
import time

from . import paths


_BACKEND = "auto"     # SAT back end handed to ext/fastsat (config margin.backend): auto | py | cadical | dimacs:kissat ...


def _engine():
    paths.setup()
    return paths.optional("glitchsat")


def measure(path, top, goal, kmax=3, cycles=6, engines=("auto", "z3"), timeout_s=120, unbounded=False, backend="auto"):
    """Returns dict(status, min_faults, lower_bound, engine, label, bound, witness, seconds, reason)."""
    GS = _engine()
    out = dict(status="not_computed", min_faults=None, lower_bound=None, engine=None, witness=None,
               bound=dict(k=kmax, cycles=cycles), label="untested")
    if GS is None:
        out["reason"] = "scripts/glitchsat.py not found (set GLITCHSAT_ROOT)"
        return out
    global _BACKEND
    _BACKEND = backend or "auto"
    kw = dict(goal_out=goal.get("output", "boot_word"), goal_value=int(goal.get("value", 0x96)),
              attack_in=goal.get("input", "sig"), key=int(goal.get("key", 0xC3)))
    try:
        nl = GS.Netlist(str(path), top)
    except Exception as e:
        out["reason"] = f"the bounded engines cannot read this netlist: {str(e)[:200]}"
        return out
    for port in (kw["goal_out"], kw["attack_in"]):
        if port not in nl.ports:
            out["reason"] = f"port {port!r} named in the goal does not exist in this netlist"
            return out
    t0 = time.time()
    for eng in engines:
        try:
            r = {"auto": _auto, "exhaustive": _exhaustive, "fastsat": _fastsat, "z3": _z3}[eng](GS, nl, cycles, kmax, kw, timeout_s)
        except Exception as e:      # an engine that is not installed or fails must not hide the others
            r = dict(status="error", reason=f"{eng}: {type(e).__name__}: {str(e)[:160]}")
        if r.get("status") in ("attack", "none_up_to_k"):
            out.update(r)
            out["engine"] = r.pop("via", eng)
            out["seconds"] = round(time.time() - t0, 2)
            out["label"] = "MEASURED (bounded search on this netlist)"
            break
        if r.get("lower_bound") and (out.get("lower_bound") or 0) < r["lower_bound"]:
            out["lower_bound"] = r["lower_bound"]
        out.setdefault("tried", []).append({eng: r.get("reason") or r.get("status")})
    if unbounded and out["status"] in ("attack", "none_up_to_k"):
        out["unbounded"] = _unbounded(path, top, kw, (out["min_faults"] - 1) if out["min_faults"] else kmax, timeout_s)
    return out


def _exhaustive(GS, nl, cycles, kmax, kw, timeout_s):
    asf = paths.optional("attack_surface")
    if asf is None:
        return dict(status="unavailable", reason="ext/surface not found")
    r = asf.exhaustive(nl, cycles, kmax, cap=1, timeout_s=timeout_s, **kw)
    if r["verdict"] == "ATTACK_FOUND":
        sim = r["sim"]
        sites, n_in = r["attacks"][0]
        wit = []
        for s in sites:
            try:
                cyc, net = s
                wit.append(dict(net=nl.names.get(net, str(net)), cycle=int(cyc)))
            except Exception:
                wit.append(dict(site=str(s)))
        return dict(status="attack", min_faults=r["min_faults"], lower_bound=r["min_faults"], witness=wit,
                    sets_simulated=r["sets_simulated"], complete_minimum=True)
    if r["verdict"] == "NO_ATTACK_UP_TO_BOUND":
        return dict(status="none_up_to_k", min_faults=None, lower_bound=kmax + 1, sets_simulated=r["sets_simulated"])
    return dict(status="incomplete", lower_bound=r.get("searched_below"), reason=f"exhaustive search stopped ({r['stop_reason']})")


def _fastsat(GS, nl, cycles, kmax, kw, timeout_s):
    fs = paths.optional("glitchsat_sat")
    if fs is None:
        return dict(status="unavailable", reason="ext/fastsat not found")
    verdict, info, res = fs.solve(nl, cycles, kmax, timeout_ms=int(timeout_s * 1000), minimize=True, backend=_BACKEND, **kw)
    r = _from_solver(verdict, info, res, kmax, nl)
    r["sat_backend"] = info.get("backend", _BACKEND) if isinstance(info, dict) else _BACKEND
    return r


def _auto(GS, nl, cycles, kmax, kw, timeout_s):
    """Exhaustive for up to two flips (fast and complete), then the SAT back end for the rest of the budget."""
    r = _exhaustive(GS, nl, cycles, min(kmax, 2), kw, timeout_s)
    if r.get("status") != "none_up_to_k" or kmax <= 2:
        r["via"] = "exhaustive"
        return r
    try:
        r2 = _fastsat(GS, nl, cycles, kmax, kw, timeout_s)
        r2["via"] = "exhaustive (<= 2 flips) + fastsat"
    except Exception:
        r2 = dict(status="error")
    if r2.get("status") not in ("attack", "none_up_to_k"):
        r2 = _exhaustive(GS, nl, cycles, kmax, kw, timeout_s)
        r2["via"] = "exhaustive"
    return r2


def _z3(GS, nl, cycles, kmax, kw, timeout_s):
    try:
        import z3  # noqa: F401
    except ImportError:
        return dict(status="unavailable", reason="z3 not installed")
    verdict, info, res = GS.solve(nl, cycles, kmax, timeout_ms=int(timeout_s * 1000), minimize=True, **kw)
    return _from_solver(verdict, info, res, kmax, nl)


def _from_solver(verdict, info, res, kmax, nl=None):
    v = str(verdict).upper()
    if res and res.get("faults") is not None and ("ATTACK" in v or "SAT" == v or "FOUND" in v):
        f = res["faults"]
        wit = []
        for x in f:
            if isinstance(x, (tuple, list)) and len(x) >= 2:
                wit.append(dict(net=(nl.names.get(x[1], str(x[1])) if nl else str(x[1])), cycle=int(x[0])))
            else:
                wit.append(dict(site=str(x)))
        return dict(status="attack", min_faults=len(f), lower_bound=len(f), witness=wit)
    if "NO" in v or "UNSAT" in v or "SAFE" in v:
        return dict(status="none_up_to_k", min_faults=None, lower_bound=kmax + 1)
    return dict(status="incomplete", reason=f"solver verdict {verdict}")


def _unbounded(path, top, kw, k, timeout_s):
    ub = paths.optional("unbounded")
    if ub is None or k < 0:
        return dict(status="unavailable")
    try:
        P = ub.Problem(str(path), top, **kw)
        r = ub.analyse(P, k, "known", methods=("oracle",), timeout_s=timeout_s)
        return dict(status=r.get("verdict"), k=k, label="proved by explicit reachability (ext/unbounded), power-up state known")
    except Exception as e:
        return dict(status="error", reason=f"{type(e).__name__}: {str(e)[:160]}")


def text(m):
    if not m:
        return "not computed"
    if m["status"] == "attack":
        s = f"{m['min_faults']} fault(s)"
    elif m["status"] == "none_up_to_k":
        s = f"more than {m['bound']['k']} faults"
    else:
        return "not computed" + (f" ({m.get('reason')})" if m.get("reason") else "")
    s += f" (within {m['bound']['cycles']} cycles, {m['engine']})"
    u = m.get("unbounded")
    if u and u.get("status") == "PROVED_UNBOUNDED":
        s += f"; proved for any number of cycles: no attack with <= {u['k']} flips"
    return s
