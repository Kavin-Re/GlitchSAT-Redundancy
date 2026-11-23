"""Attack-potential margin estimate from a GlitchSAT result.

What it does: takes the minimum number of modelled flips m (or the lower bound "more than K" when no attack was found
up to K), turns it into a number of physical injection EVENTS under an explicit, overridable assumption, and scores a
PSA Certified and a JIL rating with the schemes' own point tables (see factors.py for every citation).

What it does not do: it does not rate an attack the way a lab does. A lab rates an attack it has identified and,
usually, carried out on real devices. This estimate supports that work (design evidence, choosing what to test first);
it never replaces it.

The weakest link, stated plainly: GlitchSAT counts modelled single-cycle bit flips. One physical glitch can flip many
nets at once (a supply or clock glitch acts on the whole die). So m flips is NOT m glitches. By default this tool assumes
one voltage, clock or EM glitch can produce any number of flips within one clock cycle, which gives one event and no
extra points. Only a narrower assumption (for example one flip per laser spot, `flips_per_event=1`) turns m into m events.
"""
import math

from . import factors as F

LAB_DISCLAIMER = ("Estimate only. It supports, and never replaces, evaluation by an accredited lab: the scores use the schemes' "
                  "point tables, but the factor levels are assumptions about a modelled result, not a lab rating of a demonstrated attack.")

FAULT_TYPES = ("voltage", "clock", "em", "laser", "light")
DEFAULT_FLIPS_PER_EVENT = {"voltage": "any", "clock": "any", "em": "any", "laser": 1, "light": "any"}

DEFAULTS = dict(
    fault_type="voltage",
    flips_per_event=None,            # None -> DEFAULT_FLIPS_PER_EVENT[fault_type]; "any" or an integer >= 1
    events=None,                     # integer override of the derived number of injection events
    events_from_cycles=False,        # count one event per distinct clock cycle of the minimum attacks (needs a complete surface)
    success_rare=False,              # PSA 5.1.3 note: very rare success -> exploitation > one month
    id_elapsed="month", id_expertise="expert", id_knowledge="public", id_access="lt10", id_equipment="specialized",
    exploit_elapsed=None,            # None -> derived from events (EVENTS_TO_ELAPSED)
    exploit_expertise="proficient", exploit_knowledge="public", exploit_access="lt10", exploit_equipment="specialized",
    jil_equipment=None,              # None -> JIL Table 10 class of the fault type (both phases)
    jil_open_samples="public",
    target_psa_level=3,
)
DEFAULT_SOURCE = {
    "id_elapsed": F.PSA_EXAMPLES["one_glitch_each_device"]["source"],
    "id_expertise": F.PSA_EXAMPLES["one_glitch_each_device"]["source"],
    "id_knowledge": F.PSA_EXAMPLES["one_glitch_each_device"]["source"],
    "id_access": F.PSA_EXAMPLES["one_glitch_each_device"]["source"],
    "id_equipment": F.PSA_EXAMPLES["one_glitch_each_device"]["source"],
    "exploit_expertise": F.PSA_EXAMPLES["one_glitch_each_device"]["source"],
    "exploit_knowledge": F.PSA_EXAMPLES["one_glitch_each_device"]["source"],
    "exploit_access": F.PSA_EXAMPLES["one_glitch_each_device"]["source"],
    "exploit_equipment": F.PSA_EXAMPLES["one_glitch_each_device"]["source"],
    "jil_open_samples": "JIL v3.2.1, Table 12 (para. 98): open samples not required = 0",
}


class AssumptionError(ValueError):
    pass


def parse_assumptions(pairs):
    """['key=value', ...] -> dict with typed values; unknown keys or levels raise AssumptionError."""
    out = {}
    for p in pairs or []:
        if "=" not in p:
            raise AssumptionError(f"assumption {p!r} must be key=value")
        k, v = (x.strip() for x in p.split("=", 1))
        if k not in DEFAULTS:
            raise AssumptionError(f"unknown assumption {k!r}; known: {', '.join(sorted(DEFAULTS))}")
        if k in ("events", "target_psa_level"):
            try:
                v = int(v)
            except ValueError:
                raise AssumptionError(f"{k} must be an integer")
        elif k == "flips_per_event":
            v = "any" if v == "any" else _posint(k, v)
        elif k in ("events_from_cycles", "success_rare"):
            if v.lower() not in ("true", "false", "1", "0", "yes", "no"):
                raise AssumptionError(f"{k} must be true or false")
            v = v.lower() in ("true", "1", "yes")
        out[k] = v
    return out


def _posint(k, v):
    try:
        n = int(v)
    except ValueError:
        raise AssumptionError(f"{k} must be 'any' or an integer >= 1")
    if n < 1:
        raise AssumptionError(f"{k} must be >= 1")
    return n


def resolve(assume=None):
    a = dict(DEFAULTS)
    a.update(assume or {})
    if a["fault_type"] not in FAULT_TYPES:
        raise AssumptionError(f"fault_type must be one of {FAULT_TYPES}")
    if a["flips_per_event"] is None:
        a["flips_per_event"] = DEFAULT_FLIPS_PER_EVENT[a["fault_type"]]
    for k, v in a.items():
        fac = k.split("_", 1)[1] if k.startswith(("id_", "exploit_")) else None
        if fac in F.FACTORS and v is not None and v not in F.FACTORS[fac]:
            raise AssumptionError(f"{k}={v!r}: level must be one of {F.FACTORS[fac]}")
    if a["jil_equipment"] is not None and a["jil_equipment"] not in F.EQUIPMENT:
        raise AssumptionError(f"jil_equipment must be one of {F.EQUIPMENT}")
    if a["target_psa_level"] not in F.PSA_LEVELS:
        raise AssumptionError("target_psa_level must be 2, 3 or 4")
    return a


def surface_cycle_stats(surface):
    """Distinct clock cycles per minimum attack, from a complete attack-surface listing."""
    if not surface or not surface.get("attacks"):
        return None
    per = [len({c for _, c in a["faults"]}) for a in surface["attacks"]]
    listed = len(surface["attacks"])
    return dict(min_cycles=min(per), max_cycles=max(per), listed=listed, count=surface.get("count", listed),
                complete=bool(surface.get("complete")) and listed == surface.get("count", listed),
                single_cycle_attacks=sum(1 for x in per if x == 1))


def derive_events(m, m_is_lower_bound, a, cyc):
    """Return (events, explanation lines)."""
    why = []
    if a["events"] is not None:
        why.append(f"events = {a['events']} (set by the user)")
        return a["events"], why
    fpe = a["flips_per_event"]
    if fpe == "any":
        ev = 1
        why.append(f"flips_per_event = any (default for fault_type={a['fault_type']}): one injection event is assumed able to cause "
                   f"every flip of the attack in its clock cycle, so {m}{'+' if m_is_lower_bound else ''} flip(s) count as 1 event")
    else:
        ev = math.ceil(m / fpe)
        why.append(f"flips_per_event = {fpe}{' (default for laser: one flip per spot)' if a['fault_type'] == 'laser' and a['flips_per_event'] == 1 else ''}: "
                   f"ceil({m}{'+' if m_is_lower_bound else ''} / {fpe}) = {ev} event(s)")
    if a["events_from_cycles"]:
        if cyc and cyc["complete"]:
            if cyc["min_cycles"] > ev:
                why.append(f"events_from_cycles: every one of the {cyc['count']} minimum attacks spans at least {cyc['min_cycles']} distinct cycle(s); "
                           f"assuming one event acts in one cycle and the attacker uses a minimum-size attack, events = {cyc['min_cycles']}")
                ev = cyc["min_cycles"]
            else:
                why.append(f"events_from_cycles: some minimum attack fits in {cyc['min_cycles']} cycle(s); no change")
        else:
            why.append("events_from_cycles was requested but no complete attack-surface listing was given; ignored")
    return ev, why


def _rate(scheme, sel):
    table = F.PSA_TABLE1 if scheme == "psa" else F.JIL_TABLE13
    rows, tid, tex = [], 0, 0
    for fac in ("elapsed", "expertise", "knowledge", "access", "equipment") + (("open_samples",) if scheme == "jil" else ()):
        il, el = sel["id"].get(fac), sel["ex"].get(fac)
        ip = F.points(table, fac, il, 0) if il else 0
        ep = F.points(table, fac, el, 1) if el else None
        tid += ip or 0
        tex += ep or 0
        rows.append(dict(factor=F.FACTOR_LABEL[fac], id_level=F.level_label(scheme, fac, il) if il else "-", id_points=ip,
                         ex_level=F.level_label(scheme, fac, el) if el else "NA", ex_points=ep if ep is not None else "NA",
                         basis=sel["basis"].get(fac, "")))
    return rows, tid, tex


def rate(m, m_is_lower_bound=False, assume=None, surface=None, with_sensitivity=True):
    """m = minimum flips (or K+1 when no attack up to K). Returns a dict with both ratings and every assumption."""
    a = resolve(assume)
    res = dict(min_flips=m, min_flips_is_lower_bound=m_is_lower_bound, assumptions=a, disclaimer=LAB_DISCLAIMER, notes=[])
    if m is None:
        res["status"] = "no_result"
        res["headline"] = "No usable result (solver unknown or configuration problem): no margin estimate."
        return res
    if m == 0:
        res["status"] = "no_fault_needed"
        res["headline"] = ("The goal is reached with 0 flips: this is a logical or configuration flaw, not a fault attack. "
                           "No attack-potential estimate is made.")
        return res
    cyc = surface_cycle_stats(surface)
    ev, why = derive_events(m, m_is_lower_bound, a, cyc)
    res["events"], res["events_reasoning"], res["cycle_stats"] = ev, why, cyc
    if a["success_rare"]:
        ex_el, ex_src = "gt_month", F.PSA_RARE_NOTE[1] + " (assumption success_rare=true)"
    elif a["exploit_elapsed"]:
        ex_el, ex_src = a["exploit_elapsed"], "set by the user"
    elif ev in F.EVENTS_TO_ELAPSED:
        ex_el, ex_src = F.EVENTS_TO_ELAPSED[ev]
    else:
        ex_el, ex_src = F.EVENTS_TO_ELAPSED[2][0], F.NO_ANCHOR_3PLUS
        res["notes"].append(F.NO_ANCHOR_3PLUS)

    def basis(k):
        return DEFAULT_SOURCE.get(k, "") if (assume or {}).get(k) is None else "set by the user"

    psa_sel = dict(
        id={f: a["id_" + f] for f in ("elapsed", "expertise", "knowledge", "access", "equipment")},
        ex=dict(elapsed=ex_el, expertise=a["exploit_expertise"], knowledge=a["exploit_knowledge"], access=a["exploit_access"],
                equipment=a["exploit_equipment"]),
        basis={f: basis("id_" + f) for f in ("expertise", "knowledge", "access", "equipment")})
    psa_sel["basis"]["elapsed"] = f"identification: {basis('id_elapsed')}; exploitation: {ex_src}"
    rows, tid, tex = _rate("psa", psa_sel)
    total = tid + tex
    levels = {}
    for lvl, ceil in F.PSA_LEVELS.items():
        levels[lvl] = dict(ceiling=ceil, in_scope=total <= ceil, margin=total - ceil)
    tgt = a["target_psa_level"]
    psa = dict(rows=rows, id_total=tid, ex_total=tex, total=total, levels=levels, table_source=F.PSA_TABLE1["_source"],
               levels_source=F.PSA_LEVELS_SOURCE, target_level=tgt, above_target=total > F.PSA_LEVELS[tgt])
    if ev == 2 and ex_el == "week" and not a["exploit_elapsed"]:
        psa["printed_example"] = dict(total=F.PSA_EXAMPLES["two_glitches"]["printed_total"],
                                      note=F.PSA_EXAMPLES["two_glitches"]["discrepancy"], source=F.PSA_EXAMPLES["two_glitches"]["source"])
    res["psa"] = psa

    jeq, jname = (a["jil_equipment"], "set by the user") if a["jil_equipment"] else F.JIL_TOOL_CLASS[a["fault_type"]]
    jeq_basis = "set by the user" if a["jil_equipment"] else f"{F.JIL_TOOL_SOURCE}: '{jname}' is {jeq}"
    jil_sel = dict(id=dict(psa_sel["id"], equipment=jeq, open_samples=a["jil_open_samples"]),
                   ex=dict(psa_sel["ex"], equipment=jeq, open_samples=None),
                   basis=dict(psa_sel["basis"], equipment=jeq_basis, open_samples=basis("jil_open_samples")))
    jil_sel["basis"]["elapsed"] += ("; JIL bands are '< one day' / '< one week' where PSA writes '<='; the factor levels are the PSA "
                                    "example's choices re-scored on JIL Table 13, not a JIL worked example")
    jrows, jid, jex = _rate("jil", jil_sel)
    res["jil"] = dict(rows=jrows, id_total=jid, ex_total=jex, total=jid + jex, band=F.jil_band(jid + jex),
                      table_source=F.JIL_TABLE13["_source"], band_source=F.JIL_BANDS_SOURCE)

    mtxt = f"{m}{' or more' if m_is_lower_bound else ''} modelled flip(s)"
    lv = levels[tgt]
    rel = (f"> L{tgt} ceiling {lv['ceiling']}, out of scope at L{tgt}" if not lv["in_scope"]
           else f"<= L{tgt} ceiling {lv['ceiling']}, in scope at L{tgt}: the device must resist it")
    head = f"minimum {mtxt} -> {ev} injection event(s) assumed -> PSA rating {total} ({rel})"
    if "printed_example" in psa:
        head += f"; PSA 5.1.3 prints {psa['printed_example']['total']} for its two-glitch example (Table 1 gives {total})"
    head += f"; JIL re-scored {jid + jex} ('{res['jil']['band']}')"
    res["headline"] = head
    res["status"] = "rated"
    res["sensitivity"] = sensitivity(m, m_is_lower_bound, assume, surface) if with_sensitivity and (assume or {}).get("events") is None else []
    return res


def sensitivity(m, lb, assume, surface):
    """The same estimate under the two extreme event assumptions, so the reader sees how much the assumption decides."""
    out = []
    for label, fpe in (("one glitch can cause every flip of a cycle (flips_per_event=any)", "any"),
                       ("every flip needs its own injection (flips_per_event=1)", 1)):
        a2 = dict(assume or {}, flips_per_event=fpe)
        a2.pop("events", None)
        r = rate(m, lb, a2, surface, with_sensitivity=False)
        out.append(dict(assumption=label, events=r["events"], psa=r["psa"]["total"], jil=r["jil"]["total"], jil_band=r["jil"]["band"]))
    return out


def timing_summary(group, surface=None):
    """Timing precision the minimum attacks need, as far as the model shows it: how many distinct clock cycles the flips of
    one attack occupy. Reported, never scored (no cited factor gives points for it)."""
    cyc = surface_cycle_stats(surface)
    if cyc:
        src = f"source: attack-surface listing of {cyc['count']} minimum attack(s), complete = {cyc['complete']}"
        lo, hi, single = cyc["min_cycles"], cyc["max_cycles"], cyc["single_cycle_attacks"]
        n = cyc["listed"]
    elif group.get("witnesses"):
        per = [len({f["cycle"] for f in w}) for w in group["witnesses"]]
        src = f"source: {len(per)} witness(es) of the bounded runs, not a complete listing"
        lo, hi, single, n = min(per), max(per), sum(1 for x in per if x == 1), len(per)
    else:
        return None
    if hi <= 1:
        txt = (f"every listed minimum attack puts all its flips in ONE clock cycle ({src}): a single, well-timed injection event "
               f"could in principle cause it, if one event can flip all of those nets")
    elif single:
        txt = (f"{single} of {n} listed minimum attack(s) fit in one clock cycle, others span up to {hi} cycles ({src})")
    else:
        txt = (f"every listed minimum attack spans at least {lo} distinct clock cycles ({src}): the attacker must place injections "
               f"in {lo} or more separate cycles, each with cycle-exact timing")
    return dict(min_cycles=lo, max_cycles=hi, single_cycle_attacks=single, listed=n, source=src, text=txt,
                notes=[F.JIL_TIMING_NOTE, F.JIL_SYNC_NOTE])


def rate_group(group, assume=None, surface=None, unbounded=None):
    """Rate a variant group from loaders.group_variants(); `unbounded` = loaders.summarize_unbounded() for the same netlist and
    goal, or None. An unbounded result can lower the minimum (an attack that needs more cycles than the bounded runs covered)
    or raise the lower bound (no attack with k flips at any time)."""
    m, lb, src = group["min_faults"], group["no_attack_up_to"], "bounded runs"
    ub_notes = []
    if unbounded:
        us, up = unbounded.get("smallest_attack"), unbounded.get("proved_up_to")
        if us is not None and (m is None or us < m):
            ub_notes.append(f"the unbounded check finds an attack with {us} flip(s) at some later cycle, fewer than the bounded runs "
                            f"({'none found' if m is None else m}); the estimate uses {us}")
            m, src = us, "unbounded check"
        if m is None and up is not None and (lb is None or up > lb):
            ub_notes.append(f"the unbounded check proves no attack with up to {up} flip(s) at any cycle; the lower bound uses {up}")
            lb, src = up, "unbounded check"
    if m is not None:
        r = rate(m, False, assume, surface)
    elif lb is not None:
        r = rate(lb + 1, True, assume, surface)
    else:
        r = rate(None, False, assume, surface)
    r["minimum_source"] = src
    if ub_notes and r.get("status") == "rated":
        r["notes"] = ub_notes + r["notes"]
    r["timing"] = timing_summary(group, surface)
    return r
