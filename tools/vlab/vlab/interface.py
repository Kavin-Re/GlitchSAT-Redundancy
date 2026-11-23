"""Shared interface between the two physical fault models of GlitchSAT:
  * this virtual glitch lab (ext/vlab)      -- clock-glitch / supply-droop timing violations
  * the spatial shot model  (ext/shots)     -- laser / EM single-event upsets

Both reduce a physical attack to the SAME abstract object GlitchSAT reasons about: at one or more clock
cycles, a set of the 8 state flip-flops (boot_word bit i = flop i) is driven to a wrong value, and the
boot check either accepts a wrong key or not.  Emitting both models in this one schema lets the
comparison (vlab.compare / ext/shots) treat them uniformly.

A record conforms to schema "physical-fault-campaign/1".  See interface/README.md for the field contract.
Shared constants (must match ext/shots/shotmodel): KEY=0xC3, GOOD=0x96, INIT=0xF0; flops ordered by the
boot_word bit they drive.
"""
SCHEMA = "physical-fault-campaign/1"
MECHANISMS = ("clock_glitch", "laser_em")


def shared_record(mechanism, design_id, top, realizable, realized_flip_sets,
                  min_cost=None, cost_unit=None, honesty="SIMULATION, not measurement", extra=None):
    """Build a schema-conformant record.

    mechanism          : one of MECHANISMS.
    design_id, top     : the placed design.
    realizable         : bool -- did this mechanism accept a wrong key anywhere in its campaign?
    realized_flip_sets : list of dicts {cycle:int, flops:[int], sig:hexstr|null, outcome:str},
                         the flop-flip sets this mechanism's SIMULATION produced (what GlitchSAT
                         can check against its abstract attacks).
    min_cost/cost_unit : cheapest successful knob value (e.g. glitch period ps, or shot radius um);
                         None if no success.
    """
    if mechanism not in MECHANISMS:
        raise ValueError("unknown mechanism %r" % mechanism)
    rec = dict(
        schema=SCHEMA,
        mechanism=mechanism,
        design=design_id,
        top=top,
        key=0xC3, good=0x96, init=0xF0,
        realizable_wrong_key_accept=bool(realizable),
        min_cost=min_cost,
        cost_unit=cost_unit,
        realized_flip_sets=realized_flip_sets,
        honesty=honesty,
    )
    if extra:
        rec["extra"] = extra
    validate(rec)
    return rec


def validate(rec):
    req = ["schema", "mechanism", "design", "top", "realizable_wrong_key_accept", "realized_flip_sets"]
    for k in req:
        if k not in rec:
            raise ValueError("record missing %r" % k)
    if rec["schema"] != SCHEMA:
        raise ValueError("schema is %r, expected %r" % (rec["schema"], SCHEMA))
    if rec["mechanism"] not in MECHANISMS:
        raise ValueError("bad mechanism")
    for fs in rec["realized_flip_sets"]:
        if "cycle" not in fs or "flops" not in fs:
            raise ValueError("flip set needs cycle and flops")
        if not all(isinstance(b, int) and 0 <= b < 8 for b in fs["flops"]):
            raise ValueError("flop indices must be 0..7")
    return True


def from_vlab_campaign(campaign_result):
    """Adapter: turn a vlab campaign result into a shared record (mechanism = clock_glitch)."""
    cells = campaign_result["cells"]
    succ = [c for c in cells if c["counts"]["SUCCESS"] > 0]
    sets, seen = [], set()
    for c in cells:
        fl = c.get("realized_flips")
        if c["counts"]["SUCCESS"] > 0 and fl is not None:
            key = (c["offset"], tuple(fl))
            if key not in seen:
                seen.add(key)
                sets.append(dict(cycle=c["offset"], flops=list(fl),
                                 sig=(c["success_sig_examples"] or [None])[0], outcome="SUCCESS"))
    min_cost = min((c["period_ps"] for c in succ), default=None)
    return shared_record("clock_glitch", campaign_result["design"], campaign_result["top"],
                         realizable=bool(succ), realized_flip_sets=sets,
                         min_cost=min_cost, cost_unit="glitch_period_ps" if succ else None,
                         extra=dict(delay_model=campaign_result["delay_model"]["source"],
                                    n_offsets=len(campaign_result["offsets"]),
                                    n_periods=len(campaign_result["periods_ps"])))
