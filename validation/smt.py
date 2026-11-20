"""Independent SMT-LIB2 re-encoding (QF_BV, no z3 API) for boolector/z3-binary.
usage: smt.py netlist top T k > out.smt2 ; counts faults with a bitvector popcount."""
import sys; from netsim import Net,KEY
path,top,T,k=sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4])
n=Net(path,top); o=[]
o.append("(set-logic QF_BV)(declare-fun sig () (_ BitVec 8))")
fv={}
for t in range(T):
    for b in n.sites: fv[(t,b)]=f"f_{t}_{b}"; o.append(f"(declare-fun {fv[(t,b)]} () (_ BitVec 1))")
def nm(t,b): return f"n_{t}_{b}"
def ref(t,b):
    if b=='0' or b=='x': return "#b0"
    if b=='1': return "#b1"
    if b in n.sidx: return f"((_ extract {n.sidx[b]} {n.sidx[b]}) sig)"
    return nm(t,b)
for t in range(T):
    for q,(d) in [(q,d) for d,q in n.dffs]:
        if t==0: e="#b1" if n.init[q] else "#b0"
        else: e=ref(t-1,d)
        o.append(f"(declare-fun {nm(t,q)} () (_ BitVec 1))(assert (= {nm(t,q)} (bvxor {e} {fv[(t,q)]})))")
    for b in n.order:
        ty,p=n.gates[b]; r=lambda x:ref(t,p[x])
        if ty=='$_AND_': e=f"(bvand {r('A')} {r('B')})"
        elif ty=='$_OR_': e=f"(bvor {r('A')} {r('B')})"
        elif ty=='$_XOR_': e=f"(bvxor {r('A')} {r('B')})"
        elif ty=='$_NOT_': e=f"(bvnot {r('A')})"
        elif ty=='$_MUX_': e=f"(ite (= {r('S')} #b1) {r('B')} {r('A')})"
        o.append(f"(declare-fun {nm(t,b)} () (_ BitVec 1))(assert (= {nm(t,b)} (bvxor {e} {fv[(t,b)]})))")
# goal: boot_word == 0x96 at some cycle
goals=[]
for t in range(T):
    c=[f"(= {ref(t,b)} #b{(0x96>>i)&1})" for i,b in enumerate(n.out)]
    goals.append("(and "+" ".join(c)+")")
o.append("(assert (or "+" ".join(goals)+"))")
o.append(f"(assert (distinct sig #x{KEY:02x}))")
W=12
acc="#b000000000000"
for f in fv.values(): acc=f"(bvadd {acc} (concat #b00000000000 {f}))"
terms=None
o.append(f"(assert (bvule {acc} (_ bv{k} {W})))")
o.append("(check-sat)")
print("\n".join(o))
