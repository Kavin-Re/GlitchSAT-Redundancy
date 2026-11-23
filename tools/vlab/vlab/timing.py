"""Event-driven, two-value-with-delays simulator of ONE clock cycle's settling, used to decide what each
flip-flop captures when the capture edge comes early (a shortened period = clock glitch / supply droop).

Physical picture for the capture edge that ends cycle `t`:
  * at the launch edge the flop Q nets step from their cycle `t-1` settled values to their cycle `t`
    values (S[t-1] -> S[t]); the primary inputs `sig` are held constant.
  * each combinational cell recomputes when an input changes and drives its output after its own delay
    (transport delay, so reconvergent paths can produce a short-lived hazard = an intermediate value).
  * flop i samples its D net at time  P_glitch + clock_latency(i).  It captures:
        - the SETTLED (new) value if D has finished transitioning by then,
        - the OLD value (or a hazard-intermediate value) if it has not  -> a timing-violation fault.

This is value-dependent: only a flop whose D actually changes this cycle and is on a path slower than the
glitched period can be corrupted.  With P_glitch large enough every D settles and the result equals the
zero-delay oracle (vlab.sim) exactly -- the property the test-suite checks over all 256 keys.
"""
import heapq
from . import cells
from .netlist import INIT


def _settled(design, state8, sig):
    from .sim import step_scalar
    return step_scalar(design, state8, sig)


def settle(design, dm, from_state, to_state, sig):
    """Event-driven settling after one launch edge. Returns {net: [(time_ps, value), ...]} (the full
    two-value waveform of every net, first entry = value before the edge)."""
    v_from = _settled(design, from_state, sig)
    # current value of every net = previous-cycle settled value
    value = {}
    # set sig (held constant across the cycle)
    for i, n in enumerate(design.sig_nets):
        value[n] = (sig >> i) & 1
    for c in design.comb:
        value[c.out] = v_from[c.out]
    for i, fl in enumerate(design.flops):
        value[fl.out] = (from_state >> i) & 1
    waveform = {n: [(0.0, value[n])] for n in value}

    # readers of each net (comb cells only; flop D sampling handled at the end)
    readers = {}
    for c in design.comb:
        for p in cells.input_pins(c.master):
            readers.setdefault(c.pins[p], []).append(c)

    heap = []            # (time, seq, net, newval)
    seq = 0
    sched = dict(value)  # last value SCHEDULED for each net (not yet processed) -> correct hazard dedup
    # launch: flop Q nets step to their cycle-t value at launch time = clock latency + clk->Q
    for i, fl in enumerate(design.flops):
        nv = (to_state >> i) & 1
        lt = dm.clk_latency.get(fl.out, 0.0) + dm.tcq(fl)
        if nv != sched[fl.out]:
            heapq.heappush(heap, (lt, seq, fl.out, nv))
            sched[fl.out] = nv
            seq += 1

    def recompute(cell, now):
        # `now` is non-decreasing and the per-cell delay is constant, so events scheduled for a net
        # keep non-decreasing times; comparing against the last SCHEDULED value makes the final event
        # (driven by the last input to settle) the one that wins.
        nonlocal seq
        o = cells.evaluate(cell.master,
                           {p: value[cell.pins[p]] for p in cells.input_pins(cell.master)},
                           lambda a: a ^ 1) & 1
        if o != sched[cell.out]:
            heapq.heappush(heap, (now + dm.cell_delay[cell.name], seq, cell.out, o))
            sched[cell.out] = o
            seq += 1

    guard = 0
    while heap:
        guard += 1
        if guard > 200000:
            raise RuntimeError("event storm (comb loop?) in %s" % design.id)
        now, _s, net, nv = heapq.heappop(heap)
        if nv == value[net]:
            continue
        value[net] = nv
        waveform[net].append((now, nv))
        for c in readers.get(net, ()):
            recompute(c, now)

    return waveform


def sample(design, dm, waveform, period_ps, xband_ps=0.0):
    """What each flop captures if the capture edge arrives period_ps after the launch edge."""
    f = cells.FLOP["dfxtp"]
    # sample each flop D at its (glitched) capture instant
    captured = 0
    x_mask = 0
    arrival, sample_t, changed = {}, {}, {}
    for i, fl in enumerate(design.flops):
        d_net = fl.pins[f["d"]]
        s_i = period_ps + dm.clk_latency.get(fl.out, 0.0)
        wf = waveform[d_net]
        val = wf[0][1]
        last_t = 0.0
        for (tt, vv) in wf:
            if tt <= s_i:
                val = vv
                last_t = tt
            else:
                break
        final_t = wf[-1][1]
        arrival[i] = wf[-1][0]
        sample_t[i] = s_i
        changed[i] = (wf[0][1] != final_t)
        if xband_ps > 0.0 and any(s_i - xband_ps < tt <= s_i for (tt, _vv) in wf):
            x_mask |= (1 << i)
        captured |= (val & 1) << i
    return captured, x_mask, dict(arrival=arrival, sample=sample_t, changed=changed)


def capture_edge(design, dm, from_state, to_state, sig, period_ps, xband_ps=0.0):
    """Simulate the settling that precedes one (glitched) capture edge and return the captured next state.

    from_state, to_state : int 0..255  (S[t-1] and S[t]); Q nets step from_state->to_state at launch.
    sig                  : int 0..255  (held).
    period_ps            : the (shortened) time from launch edge to this capture edge.
    xband_ps             : optional setup uncertainty; if D's last transition lands within this band
                           below the sample instant the bit is marked X (returned separately).

    Returns (captured_state:int, x_mask:int, info:dict).  x_mask bit i set => flop i sampled in the X band.
    info has 'arrival' {bit:last_D_transition_ps}, 'sample' {bit:sample_ps}, 'changed' {bit:bool}.
    """
    return sample(design, dm, settle(design, dm, from_state, to_state, sig), period_ps, xband_ps)
