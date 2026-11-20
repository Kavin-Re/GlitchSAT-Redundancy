#!/usr/bin/env python3
"""R27 experiment driver. Imports unmodified glitchsat.build; swaps only the cardinality encoding / solver path."""
import sys, time, json, argparse
sys.path.insert(0, '/tmp/work_r27/project/scripts')
import glitchsat as g
from z3 import *

def seq_counter(F, kmax):
    """unary counter cnt[j] (>= j faults among sites), one-directional (x -> cnt). returns (clauses, outs[1..kmax+1])"""
    xs = list(F.values()); cl = []
    prev = [None]*(kmax+2)   # prev[j] for j=1..kmax+1 : BoolVal False initially
    prev = [BoolVal(False)]*(kmax+2)
    for i, x in enumerate(xs):
        cur = [BoolVal(False)]*(kmax+2)
        for j in range(1, kmax+2):
            c = Bool(f'c_{i}_{j}')
            # c_{i,j} >= prev_{j}  and  c_{i,j} >= x & prev_{j-1}   (j=1: >= x)
            cl.append(Implies(prev[j], c))
            cl.append(Implies(And(x, prev[j-1]) if j > 1 else x, c))
            cur[j] = c
        prev = cur
    return cl, prev

def run(nl, N, k, enc, eng, reduce='full', timeout_s=120, goal=None, minimize=False):
    t0 = time.time()
    s, F, inputs, info = g.build(nl, N, reduce=reduce, **goal)
    tb = time.time()-t0
    allf = list(F.values())
    if eng == 'sat':
        # bit-level path: tactic pipeline to CNF + SAT core
        s2 = Then('simplify','propagate-values','solve-eqs','bit-blast','simplify','tseitin-cnf','sat').solver() if False else None
    extra = []
    assume = []
    if enc == 'pb': extra.append(PbLe([(f,1) for f in allf], k))
    elif enc == 'atmost': extra.append(AtMost(*allf, k))
    elif enc == 'seq':
        cl, outs = seq_counter(F, k); extra += cl; extra.append(Not(outs[k+1]))
    elif enc == 'pair':
        if k != 1: return dict(verdict='N/A', build_s=tb, solve_s=0)
        # pairwise at-most-1 is quadratic; cap
        if len(allf) > 4000: return dict(verdict='N/A(size)', build_s=tb, solve_s=0)
        for i in range(len(allf)):
            for j in range(i+1, len(allf)): extra.append(Or(Not(allf[i]), Not(allf[j])))
    elif enc == 'incr':  # handled by caller
        pass
    if eng == 'smt':
        s.add(*extra); s.set('timeout', int(timeout_s*1000))
        t1 = time.time(); r = s.check(); ts = time.time()-t1
    else:
        t = Then('simplify','propagate-values','solve-eqs','bit-blast','simplify','tseitin-cnf','sat')
        S = t.solver(); S.add(s.assertions()); S.add(*extra); S.set('timeout', int(timeout_s*1000))
        t1 = time.time(); r = S.check(); ts = time.time()-t1
    v = 'UNSAT' if r == unsat else 'SAT' if r == sat else 'TIMEOUT'
    return dict(verdict=v, build_s=round(tb,2), solve_s=round(ts,2), sites=len(allf))

def incr(nl, N, kmax, goal, reduce='full', timeout_s=120):
    """one solver, one counter, assumptions for k=0..kmax; returns list of (k, verdict, seconds)"""
    t0=time.time()
    s, F, inputs, info = g.build(nl, N, reduce=reduce, **goal)
    cl, outs = seq_counter(F, kmax); s.add(*cl)
    s.set('timeout', int(timeout_s*1000)); out=[]; tb=time.time()-t0
    for k in range(kmax+1):
        t1=time.time(); r = s.check(Not(outs[k+1]))
        out.append((k, 'UNSAT' if r==unsat else 'SAT' if r==sat else 'TIMEOUT', round(time.time()-t1,2)))
        if r != unsat: break
    return dict(build_s=round(tb,2), steps=out)

DESIGNS = {
 'dmr': ('/tmp/work_r27/nl/sbox_dmr.json','sbox_dmr', dict(goal_out='gout', goal_value=0x17c, attack_in='sig', key=1)),
 'uart':('/tmp/work_r27/nl/uartw.json','uartw', dict(goal_out='gout', goal_value=7, attack_in='sig', key=0xC3)),
 's2':  ('/tmp/work_r27/nl/s2.json','v2', dict()),
 'w2':  ('/tmp/work_r27/nl/w2.json','v2', dict()),
}
if __name__ == '__main__':
    a = argparse.ArgumentParser()
    a.add_argument('design'); a.add_argument('--k', type=int); a.add_argument('--T', type=int)
    a.add_argument('--enc', default='pb'); a.add_argument('--eng', default='smt'); a.add_argument('--reduce', default='full')
    a.add_argument('--to', type=int, default=120)
    x = a.parse_args()
    p, top, goal = DESIGNS[x.design]
    nl = g.Netlist(p, top)
    if x.enc == 'incr': r = incr(nl, x.T, x.k, goal, x.reduce, x.to)
    else: r = run(nl, x.T, x.k, x.enc, x.eng, x.reduce, x.to, goal)
    print(json.dumps(dict(design=x.design, k=x.k, T=x.T, enc=x.enc, eng=x.eng, reduce=x.reduce, **r)))
