"""Re-run of the one any-net control that timed out (z3 'unknown' at 120 s) in the sweep:
2B_95_BEB structural netlist, single-flip events on any net, cap 3, longer timeout. usage: recheck_control.py <netlist.json>"""
import sys, time
sys.path.insert(0, 'scripts/comms')
import burst_sweep as bs
nl = bs.gs.Netlist(sys.argv[1], 'v2'); evs = bs.events(nl, 'flip_net'); t0 = time.time()
cell, wit, act = bs.z3_min(nl, 6, evs, 0x95, cap=3, timeout_ms=420000) if False else (bs.z3_min(nl, 6, evs, 0x95, cap=3, timeout_ms=420000) + (None,))[:3]
print('any-net control, cap 3:', cell, wit, 'gates', len(nl.drivers), 'wall_s', round(time.time() - t0, 1))
if cell.isdigit():
    w = [(int(x.rsplit('@', 1)[1]), [e.name for e in evs].index(x.rsplit('@', 1)[0])) for x in wit.split(';')[0].split(',')]
    print('witness replays in z3-free simulator:', bs.BF(nl, 6, evs, 0x95).run(w))
