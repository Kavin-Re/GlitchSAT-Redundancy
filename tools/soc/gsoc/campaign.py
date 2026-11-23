"""Simulation fault campaigns over the WHOLE chip. Label: SAMPLED.

Each scenario ("lane") is one run of the chip from reset release for T cycles with
  - one fault (single mode) or two faults (pairs mode): a single-cycle flip of one cell output,
  - a random attacker value that differs from the key, random values on every other free input in every cycle,
    random values for every flop whose state after reset is unknown and for every black-box output.
In single mode EVERY cell of the chip is flipped once in EVERY cycle (cells x T scenarios), so the fault space of
one flip is covered completely; the environment (inputs, unknown start values) is sampled, one draw per scenario.
A campaign therefore can show attacks, and it can cross-check a PROVED minimum (a proved minimum of 2 must give
zero single-fault successes), but "no success" in a campaign proves nothing by itself.

The simulator is gsoc.sim.Compiled (the netlist compiled to straight-line Python, bit-parallel over lanes); it
shares no code with the solver path.
"""
import os
import random
import time

from . import run, slicer


def run_campaign(sess, goal, lanes=4096, seed=1, pairs=20000, force=False, max_seconds=420):
    cfg = sess.cfg
    path = os.path.join(run.RUNS, '%s.campaign.%s.json' % (run.tag(cfg, sess.variant, sess.flow), goal['id']))
    if os.path.exists(path) and not force:
        return run._load(path)
    ch, circ = sess.chip, sess.chip.circ
    T = int(goal['cycles'])
    hit = slicer.parse_assign(ch, goal.get('hit'))
    quiet = slicer.parse_assign(ch, goal.get('quiet'))
    hold = int(goal.get('hold', 1))
    rng = random.Random(seed)
    sites = sorted(ch.sites)
    tied = {}
    if sess.reset:
        for b in circ.ports[sess.reset['port']][1]:
            tied[b] = 0 if int(sess.reset.get('active', 0)) else 1
    for p, val in (goal.get('fix') or {}).items():
        for i, b in enumerate(circ.ports[p][1]):
            tied[b] = (int(val) >> i) & 1
    att = goal.get('attacker')
    abits = list(circ.ports[att['port']][1]) if att else []
    key = int(att['differs_from']) if att else None
    free_inputs = [b for b in circ.inputs if b not in tied and b not in abits]
    comp = sess.comp
    t0 = time.time()

    def batch(faults):
        """faults: list over lanes of [(cycle, net), ...]. Returns word of lanes that reach the goal."""
        n = len(faults)
        M = (1 << n) - 1
        fl = {}
        for lane, fs in enumerate(faults):
            for t, b in fs:
                d = fl.setdefault(t, {})
                d[b] = d.get(b, 0) | (1 << lane)
        st = {}
        for q in circ.flops:
            v = sess.state.get(q)
            st[q] = rng.getrandbits(n) if v is None else (M if v else 0)
        const = {b: (M if v else 0) for b, v in tied.items()}
        if abits:
            words = [rng.getrandbits(n) for _ in abits]
            eq = M
            for i, w in enumerate(words):
                eq &= w if (key >> i) & 1 else (w ^ M)
            words[0] ^= eq                      # lanes that drew the key get another value
            for b, w in zip(abits, words): const[b] = w

        def inputs_at(t):
            d = dict(const)
            for b in free_inputs: d[b] = rng.getrandbits(n)
            return d
        watch = [b for b, _ in hit + quiet]
        tr = comp.run(n, T, st, inputs_at, lambda t: fl.get(t), watch)
        ok = 0; quiet_ok = M; hist = []
        for row in tr:
            for b, v in quiet: quiet_ok &= row[b] if v else (row[b] ^ M)
            cond = M
            for b, v in hit: cond &= row[b] if v else (row[b] ^ M)
            hist.append(cond)
            run_ = cond
            for j in range(1, hold):
                run_ &= hist[-1 - j] if len(hist) > j else 0
            ok |= run_ & quiet_ok
        return ok

    # 0 faults: the goal must not be reachable by the environment alone
    base = batch([[] for _ in range(lanes)])
    base_hits = bin(base).count('1')
    # single faults: every cell x every cycle
    todo = [(t, b) for t in range(T) for b in sites]
    single_hits = []
    done = 0
    stopped = False
    for i in range(0, len(todo), lanes):
        if time.time() - t0 > max_seconds:
            stopped = True
            break
        part = todo[i:i + lanes]
        ok = batch([[f] for f in part])
        done += len(part)
        while ok:
            low = ok & -ok
            single_hits.append(part[low.bit_length() - 1]); ok ^= low
    # pairs: random two-fault sets
    pair_hits = []; pairs_done = 0
    while pairs_done < pairs and not stopped and time.time() - t0 < max_seconds:
        part = [[(rng.randrange(T), rng.choice(sites)), (rng.randrange(T), rng.choice(sites))] for _ in range(min(lanes, pairs - pairs_done))]
        ok = batch(part)
        pairs_done += len(part)
        while ok:
            low = ok & -ok
            pair_hits.append(part[low.bit_length() - 1]); ok ^= low
    by_net = {}
    for t, b in single_hits: by_net.setdefault(circ.name(b), []).append(t)
    rec = dict(
        schema='glitchsat-soc-campaign/1', label='SAMPLED', chip=cfg['name'], variant=sess.variant, flow=sess.flow,
        goal=goal['id'], cycles=T, lanes=lanes, seed=seed, simulator='gsoc.sim.Compiled (compiled Python, bit-parallel)',
        chip_cells=len(sites),
        no_fault=dict(scenarios=lanes, goal_reached=base_hits),
        single=dict(scenarios=done, of_all=len(todo), complete_fault_space=(done == len(todo)), goal_reached=len(single_hits),
                    distinct_cells=len(by_net), rate=round(len(single_hits) / max(1, done), 8),
                    examples=[dict(net=n, cycles=sorted(set(c))) for n, c in sorted(by_net.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:15]]),
        pairs=dict(scenarios=pairs_done, goal_reached=len(pair_hits), rate=round(len(pair_hits) / max(1, pairs_done), 8),
                   examples=[[dict(net=circ.name(b), cycle=t) for t, b in fs] for fs in pair_hits[:5]]),
        seconds=round(time.time() - t0, 1), stopped_at_time_limit=stopped,
        note='Environment sampled once per scenario (inputs, unknown start values, black-box values). Counts say what '
             'was observed in these scenarios only.')
    run._save(path, rec)
    return rec


def format_text(r):
    s, p = r['single'], r['pairs']
    return ('%s SAMPLED: no fault %d/%d; one fault %d/%d scenarios reach the goal (%d distinct cells; fault space %s); '
            'two random faults %d/%d  [%.0f s]' % (r['goal'], r['no_fault']['goal_reached'], r['no_fault']['scenarios'],
                                                  s['goal_reached'], s['scenarios'], s['distinct_cells'],
                                                  'complete' if s['complete_fault_space'] else 'partial',
                                                  p['goal_reached'], p['scenarios'], r['seconds']))
