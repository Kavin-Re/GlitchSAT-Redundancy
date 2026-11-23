"""Clock-glitch fault model: inject one shortened clock period at a chosen capture edge (offset) and
run the design to the horizon, classifying the outcome with the labels a ChipWhisperer-style campaign uses.

Outcome of one (offset t, period P, sig) shot, compared to the fault-free run of the same sig:
  * SUCCESS   : boot accepted (boot_word==GOOD at some cycle) while sig != KEY, and the fault-free run
                of that sig did NOT accept  -> the glitch created a wrong-key accept.
  * CRASH     : the state sequence differs from fault-free but boot is not (wrongly) accepted
                (a wrong/hung boot) -- the usual "glitch did something but not the attacker's goal".
  * NO_EFFECT : the observable state sequence is identical to fault-free.
Also reported: the set of flops the glitch actually corrupted at the glitched edge (the "realized flip
set"), which is what ties this model to the abstract GlitchSAT bit-flip attacks, and `nonmix_mask`: the
bits whose captured value is NEITHER the old value S[offset] NOR the new value S[offset+1] (a hazard
captured mid-settling). Such captures exist on V1 under the ASSUMED delays, so the capture is not limited
to per-bit old/new mixes.
"""
from . import sim
from .netlist import KEY, GOOD, INIT
from . import timing


def fault_free_states(design, T, sig):
    states, accepted = sim.run_scalar(design, T, sig)
    return states, accepted


def glitch_shot(design, dm, T, offset, period_ps, sig, xband_ps=0.0, _waveform=None, _base=None):
    """One glitch at capture edge `offset` (loads state[offset+1]) with shortened period `period_ps`.
    _waveform/_base: optional precomputed settle() waveform and (states, accepted) for reuse across a
    period sweep (same offset and sig class). Returns a dict describing the outcome."""
    base_states, base_acc = _base if _base is not None else fault_free_states(design, T, sig)
    if offset >= T:
        raise ValueError("offset beyond horizon")
    from_state = base_states[offset - 1] if offset >= 1 else INIT
    to_state = base_states[offset]
    if _waveform is None:
        _waveform = timing.settle(design, dm, from_state, to_state, sig)
    captured, x_mask, info = timing.sample(design, dm, _waveform, period_ps, xband_ps)
    # realized flip set at the glitched edge: flops whose captured value differs from fault-free next
    good_next = base_states[offset + 1] if offset + 1 < len(base_states) else base_states[-1]
    flip_mask = (captured ^ good_next) & 0xFF
    nonmix_mask = (captured ^ to_state) & (captured ^ good_next) & 0xFF   # neither old nor new
    realized = [i for i in range(8) if (flip_mask >> i) & 1]
    # continue fault-free from the glitched capture
    glitched_states = base_states[:offset + 1] + [captured]
    st = captured
    accepted = any(s == GOOD for s in glitched_states)
    for t in range(offset + 1, T):
        v = sim.step_scalar(design, st, sig)
        st = v["#next"]
        glitched_states.append(st)
        if v["#word"] == GOOD:
            accepted = True
    # acceptance also includes the pre-glitch cycles (states[0..offset])
    accepted = accepted or any(s == GOOD for s in base_states[:offset + 1])
    wrong_key = (sig != KEY)
    changed = glitched_states[:T + 1] != base_states[:T + 1]
    if accepted and wrong_key and not base_acc:
        outcome = "SUCCESS"
    elif changed:
        outcome = "CRASH"
    else:
        outcome = "NO_EFFECT"
    return dict(offset=offset, period_ps=round(period_ps, 2), sig=sig, outcome=outcome,
                realized_flips=realized, captured=captured, good_next=good_next, old_next=to_state,
                nonmix_mask=nonmix_mask,
                x_mask=x_mask, arrival=info["arrival"], accepted=bool(accepted),
                base_accepted=bool(base_acc))
