"""z3-free brute force for ONE selective dip event (B3 dip_subset): the event forces to 0 an arbitrary set S of
gate outputs and flop D pins in one cycle (cost 1). Enumerates ALL S with |S| <= M, every cycle t < T, all 256 sig lanes.
usage: dip_subset_bf.py NETLIST TOP T M"""
import sys, json, itertools, time
from anchor_sim import Net, ALL
path, top, T, M = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
N = Net(path, top); gl = list(N.gates); fl = [q for _, q in N.flops]
sites = [('g', y) for y in gl] + [('d', q) for q in fl]
st = N.init; states = []
for t in range(T):
    states.append(st); _, _, st = N.cycle(st)
res = {m: 0 for m in range(M + 1)}; wit = {}; t0 = time.time(); tot = 0
for t in range(T):
    for m in range(1, M + 1):
        for S in itertools.combinations(sites, m):
            gz = {x for k, x in S if k == 'g'}; fz = {x for k, x in S if k == 'd'}
            h, ok, _ = N.cycle(states[t], (), gz, fz); tot += 1
            # goal may also be hit in later cycles: run the remaining cycles fault free
            if not h:
                _, _, nx = N.cycle(states[t], (), gz, fz); s2 = nx
                for u in range(t + 1, T):
                    h2, ok2, s2 = N.cycle(s2); h |= h2
            if h:
                res[m] += 1
                wit.setdefault(m, []).append((t, [N.names.get(x, x) for k, x in S]))
print(json.dumps(dict(netlist=path, T=T, max_sites=M, events_tried=tot, attacking_sets_by_size=res, secs=round(time.time() - t0, 1),
      first_witnesses={m: w[:2] for m, w in wit.items()})))
