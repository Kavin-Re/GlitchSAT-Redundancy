"""auto-harden: search countermeasure changes for a design description until the fault budget goal is met, and verify
every accepted candidate by exhaustive simulation (harden.sim) on reference gate mappings of the candidate.

Goal "at least G flips needed" is accepted only when, on EVERY unmerged reference mapping, no set of at most G-1 modelled
flips reaches the goal for any wrong input and any number of cycles, the right key still boots, and no wrong key does.
"""
import itertools, time
from . import sim, spec as S

FLOP_GE = 6      # area unit used for ranking only: one flop counted as 6 two-input gates (assumption, not measured)

MOVES = {
    'encoding': ('State encoding',
                 'Choose the armed / idle code words so that turning any state the wrong-key run passes through into the accept word needs '
                 'changes in bits driven by as many different compare copies as possible. Generalises the manual 0xCC -> 0xA5 change (rtl/v2e.v).',
                 'Sound because only constants change: the fault-free behaviour is re-checked for all 256 inputs, and the flip count is re-measured.'),
    'ownership': ('Bit-to-copy ownership',
                  'Re-assign which compare copy drives which state bit, so that every shortcut into the accept word crosses every copy.',
                  'Sound for the same reason as an encoding change: wiring of existing signals only, behaviour re-checked for all inputs.'),
    'voter': ('Voter placement',
              'Remove the single voter net in front of the state register. Either each state bit gets its own kept voter (per_bit_and) or each '
              'bit is driven by one copy and the consumer comparing the whole word is the voter (owner).',
              'A voter in front of the register is one net that decides every bit; behind the register no single net does. Behaviour re-checked for all inputs.'),
    'copies': ('More compare copies',
               'Add compare copies that own state bits. Each copy is one more net the attacker has to flip on the compare path.',
               'Adds logic only; the new copies compute the same comparison. Needs the copies to stay separate through synthesis.'),
    'alarm': ('Check copy with infection / alarm latch',
              'Add a compare copy that owns no bit and an alarm: if any two compare blocks disagree the reject word is forced (infect); '
              'the sticky variant latches the alarm in a flop that keeps forcing reject.',
              'The alarm can only force reject, so it cannot create an accept. It is itself one net, so it adds one flip, not more.'),
    'trap': ('Invalid state goes to reject',
             'A state that is none of the four code words moves to reject instead of being held.',
             'Only changes behaviour in states the fault-free design never reaches.'),
    'sparse': ('Sparse state word as output',
               'Replace the 2-bit state and the decoded output by an 8-bit state word that is the output (as rtl/v1.v, v2.v do).',
               'Changes the interface meaning of boot_word bits only in the sense that they now come from 8 flops instead of one decoded flag; values are the same 0x96 / 0x69.'),
    'separation': ('Keep the copies separate through synthesis',
                   'Map each compare copy on its own (keep_hierarchy until after abc), mark its cells keep before flatten, and do not run abc on the flattened design.',
                   'Does not change the logic function. Needed by every other fix: when identical copies are merged one flip decides all of them.'),
    'consumer': ('Consumer checks every owned bit',
                 'The block that uses boot_word must compare all bits, at least one from every copy; a partial mask lets an attacker ignore copies.',
                 'Outside the netlist: it changes what counts as accepted. Measured by changing the goal mask.'),
}


def hd(a, b, mask=-1):
    return bin((a ^ b) & mask).count('1')


def predictor(sp, mask=None):
    """Cheap estimate of the minimum flips on the most-shared reference mapping, from attacks that are expected to exist there
    (flip the state flops directly; flip the compare nets that own the bits where accept and reject differ; rewrite the
    armed word as it is loaded). Used only to skip candidates before simulation: a candidate is never accepted on the
    predictor, so an optimistic or pessimistic estimate can only make the search slower or make it miss a fix.
    tests/test_search.py checks that it is not below the simulated worst case on sample designs."""
    if sp.output != 'state':
        return 1                                           # boot_ok is one net
    m = (1 << sp.width) - 1 if mask is None else mask
    p = min(hd(c, sp.accept, m) for c in (sp.idle, sp.armed, sp.reject))          # flip the state flop outputs directly
    d = (sp.accept ^ sp.reject) & m
    if sp.voter == 'single_and':
        p2 = 1
    elif sp.voter == 'per_bit_and':
        p2 = min(sp.copies, bin(d).count('1'))
    else:
        p2 = len({sp.owner[i] for i in range(sp.width) if (d >> i) & 1})
    if sp.alarm != 'none' and sp.voter != 'single_and':
        p2 += 1 if sp.check_copies else 0
    p = min(p, p2)
    x = (sp.armed ^ sp.accept) & m                         # rewrite the load of the armed word at cycle 0
    same = ~(sp.accept ^ sp.reject)
    if not (x & same & ((1 << sp.width) - 1)):
        if sp.voter == 'owner':
            p = min(p, len({sp.owner[i] for i in range(sp.width) if (x >> i) & 1}))
        elif sp.voter == 'single_and':
            p = min(p, 1)
    return p


def owners(width, copies):
    """Every assignment of state bits to copies that uses all copies, one per relabelling class."""
    def rec(i, cur, used):
        if i == width:
            if used == copies:
                yield tuple(cur)
            return
        if copies - used > width - i:
            return
        for c in range(min(used + 1, copies)):
            cur.append(c)
            yield from rec(i + 1, cur, max(used, c + 1))
            cur.pop()
    yield from rec(0, [], 0)


def round_robin(width, copies):
    return tuple(i % copies for i in range(width))


def structures(base, allow):
    """Structural variants of `base`, each with the list of moves applied."""
    out, seen = [], set()

    def add(sp, moves):
        if sp.problems():
            return
        key = sp.replace(name='x')
        if key not in seen:
            seen.add(key)
            out.append((sp, tuple(moves)))
    b0 = [(base, [])]
    if base.output == 'decoded' and 'sparse' in allow:
        b0.append((base.replace(width=8, idle=0xF0, armed=0xCC, accept=0x96, reject=0x69, output='state'), ['sparse']))
    for sp0, mv0 in b0:
        voters = [(sp0.voter, [])]
        if 'voter' in allow and sp0.voter == 'single_and' and sp0.width >= 2:
            voters += [('owner', ['voter']), ('per_bit_and', ['voter'])]
        for (v, mv1), dn, al, trap in itertools.product(voters, (0, 1, 2) if 'copies' in allow else (0,),
                                                       ('none', 'infect', 'sticky') if 'alarm' in allow else (sp0.alarm,),
                                                       (sp0.trap_invalid, True) if 'trap' in allow else (sp0.trap_invalid,)):
            n = sp0.copies + dn
            if v == 'owner' and n > sp0.width:
                continue
            mv = list(mv0) + mv1 + (['copies'] if dn else []) + (['alarm'] if al != sp0.alarm else []) + (['trap'] if trap != sp0.trap_invalid else [])
            ow = sp0.owner if (v == 'owner' and sp0.voter == 'owner' and dn == 0) else (round_robin(sp0.width, n) if v == 'owner' else ())
            add(sp0.replace(voter=v, copies=n, owner=ow, alarm=al, check_copies=(1 if al != 'none' else 0) if al != sp0.alarm else sp0.check_copies,
                            trap_invalid=trap), mv)
    return out


def area(nl):
    st = nl.stats()
    return st['gates'] + FLOP_GE * st['flops']


def measure(sp, kmax, mappings=S.UNMERGED, cycles=None, goal_mask=None, time_limit=None):
    """min flips of `sp` on each mapping (None = none with <= kmax). Also the functional check against the description."""
    import numpy as np
    res = {}
    for mp in mappings:
        nl = S.build_mapping(sp, mp)
        g = sim.Goal('boot_word', sp.goal_value(), goal_mask)
        r = sim.min_flips(nl, g, kmax=kmax, cycles=cycles, key=sp.key, time_limit=time_limit)
        ff = sim.fault_free(nl, 6, g)
        func_ok = bool((ff['boot_word'] == np.array(S.reference_trace(sp, 6)).T).all())
        res[mp] = dict(min_flips=r.min_flips, exhaustive_up_to=r.exhaustive_up_to, witness=r.witness, honest_ok=r.honest_ok,
                       wrong_accept=r.fault_free_wrong_accept, matches_description=func_ok, sets_simulated=r.sets_simulated,
                       sites=r.sites_total, runtime_s=r.runtime_s, gates=nl.stats()['gates'], flops=nl.stats()['flops'], depth=nl.stats()['depth'])
    return res


def passes(meas, goal):
    return all(v['min_flips'] is None and v['exhaustive_up_to'] is not None and v['exhaustive_up_to'] >= goal - 1 and v['honest_ok']
               and not v['wrong_accept'] and v['matches_description'] for v in meas.values())


def worst(meas):
    """Smallest minimum over the mappings; None when no mapping has an attack within the searched budget."""
    xs = [v['min_flips'] for v in meas.values() if v['min_flips'] is not None]
    return min(xs) if xs else None


def encodings(sp, base, goal, tiers):
    """Candidate (spec, moves) in tiers of increasing change, pruned by the predictor."""
    W = sp.width
    full = range(1 << W)
    fixed = {sp.accept, sp.reject}
    rank = lambda c: (-min(hd(x, c.accept) for x in (c.idle, c.armed, c.reject)), hd(c.armed, base.armed if base.width == W else sp.armed)
                      + hd(c.idle, base.idle if base.width == W else sp.idle), c.armed, c.idle, c.owner)
    yield 0, [(sp, ())]
    if sp.output != 'state':
        return
    if 'encoding' in tiers:
        t1 = [sp.replace(armed=a) for a in full if a not in fixed and a != sp.idle and a != sp.armed]
        yield 1, [(c, ('encoding',)) for c in sorted((c for c in t1 if predictor(c) >= goal), key=rank)]
    if 'ownership' in tiers and sp.voter == 'owner' and sp.copies <= 5:
        t2 = []
        for ow in owners(W, sp.copies):
            c0 = sp.replace(owner=ow)
            if ow != sp.owner and predictor(c0) >= goal:
                t2.append((c0, ('ownership',)))
        yield 2, sorted(t2, key=lambda x: rank(x[0]))
        t3 = []
        for ow in owners(W, sp.copies):
            if ow == sp.owner:
                continue
            for a in full:
                if a in fixed or a == sp.idle or a == sp.armed:
                    continue
                c = sp.replace(owner=ow, armed=a)
                if predictor(c) >= goal:
                    t3.append((c, ('encoding', 'ownership')))
        yield 3, sorted(t3, key=lambda x: rank(x[0]))
    if 'encoding' in tiers:
        t4 = []
        for i in full:
            if i in fixed or i == sp.idle:
                continue
            for a in full:
                if a in fixed or a == i:
                    continue
                c = sp.replace(idle=i, armed=a)
                if predictor(c) >= goal:
                    t4.append((c, ('encoding',)))
        yield 4, sorted(t4, key=lambda x: rank(x[0]))


ALL_MOVES = ('encoding', 'ownership', 'voter', 'copies', 'alarm', 'trap', 'sparse')


def harden(base, goal, allow=ALL_MOVES, cycles=None, max_verify=8, alternatives=3, log=None, exact=True, time_budget=600):
    """Search. Returns a dict: before, goal, best (or None), alternatives, tried, not_reached_best."""
    t0 = time.time()
    say = log or (lambda *a: None)
    before = measure(base, max(goal, 1), cycles=cycles)
    before_merged = measure(base, 1, mappings=('merged',), cycles=cycles)
    base_nl = S.build_mapping(base, 'select-shared')
    base_area, base_stats = area(base_nl), base_nl.stats()
    bw = worst(before)
    say(f'before: {base.short()}  min flips (worst unmerged mapping) = {bw if bw is not None else ">" + str(goal)}')
    structs = structures(base, allow)
    structs.sort(key=lambda x: (area(S.build_mapping(x[0], 'select-shared')), len(x[1])))
    found, tried, best_fail = [], [], None
    stats = dict(structures=len(structs), candidates_after_predictor=0, candidates_simulated=0, sets_simulated=0, stopped_by_time_budget=False)
    for sp0, mv0 in structs:
        if len(found) >= alternatives:
            break
        if time.time() - t0 > time_budget:
            stats['stopped_by_time_budget'] = True
            break
        if found and area(S.build_mapping(sp0, 'select-shared')) > 1.5 * found[0]['cost']['area_ge_after']:
            break
        ok_here = False
        for tier, cands in encodings(sp0, base, goal, [m for m in ('encoding', 'ownership') if m in allow]):
            stats['candidates_after_predictor'] += len(cands)
            for c, mv in cands[:max_verify]:
                if time.time() - t0 > time_budget:
                    stats['stopped_by_time_budget'] = True
                    break
                if predictor(c) < goal:
                    tried.append(dict(spec=c.short(), moves=list(mv0 + mv), verdict='discarded by predictor', predictor=predictor(c)))
                    continue
                meas = measure(c, goal - 1, cycles=cycles)
                stats['candidates_simulated'] += 1
                stats['sets_simulated'] += sum(v['sets_simulated'] for v in meas.values())
                w = worst(meas)
                okc = passes(meas, goal)
                tried.append(dict(spec=c.short(), moves=list(mv0 + mv), verdict='pass' if okc else 'fail',
                                  min_flips={k: v['min_flips'] for k, v in meas.items()}))
                if okc:
                    nl = S.build_mapping(c, 'select-shared')
                    found.append(dict(spec=c, moves=list(dict.fromkeys(mv0 + mv)), tier=tier, measured=meas,
                                      cost=cost(base_stats, nl.stats())))
                    say(f'  pass: {c.short()}  [{", ".join(mv0 + mv) or "no change"}]  +{found[-1]["cost"]["gates_added"]} gates, +{found[-1]["cost"]["flops_added"]} flops')
                    ok_here = True
                    break
                if w is not None and (best_fail is None or w > best_fail[0]):
                    best_fail = (w, c, list(mv0 + mv))
            if ok_here:
                break
    found.sort(key=lambda f: (f['cost']['area_ge_after'], len(f['moves'])))
    for f in found:
        f['merged'] = measure(f['spec'], 1, mappings=('merged',), cycles=cycles)['merged']
        if exact:
            ex = measure(f['spec'], goal, cycles=cycles, time_limit=120)
            f['exact'] = {k: (v['min_flips'], v['exhaustive_up_to']) for k, v in ex.items()}
            f['exact_witness'] = next((v['witness'] for v in ex.values() if v['witness']), None)
            xs = [v['min_flips'] for v in ex.values()]
            f['after_min'] = min(x for x in xs if x is not None) if any(x is not None for x in xs) else None
        f['bounded6'] = {k: v['min_flips'] for k, v in measure(f['spec'], goal - 1, cycles=6).items()}
    return dict(design=base, goal=goal, before=before, before_min=bw, before_merged=before_merged['merged'], base_stats=base_stats,
                found=found, best=found[0] if found else None, tried=tried, best_fail=best_fail, stats=stats,
                runtime_s=round(time.time() - t0, 2), cycles='all' if not cycles else cycles, allow=list(allow))


def cost(before, after):
    return dict(gates_before=before['gates'], gates_after=after['gates'], gates_added=after['gates'] - before['gates'],
                flops_before=before['flops'], flops_after=after['flops'], flops_added=after['flops'] - before['flops'],
                depth_before=before['depth'], depth_after=after['depth'], depth_added=after['depth'] - before['depth'],
                area_ge_before=before['gates'] + FLOP_GE * before['flops'], area_ge_after=after['gates'] + FLOP_GE * after['flops'],
                decision_latency_cycles_before=2, decision_latency_cycles_after=2,
                note=f'gate and flop counts of the select-shared reference mapping (MEASURED here); area unit = gates + {FLOP_GE} x flops (assumed weight); '
                     'latency = clock cycles from reset to the decision (2 in every variant) and logic depth in gate levels')
