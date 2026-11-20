import sys,time
from pysat.formula import CNF
from pysat.solvers import Solver
f=CNF(from_file=sys.argv[1])
t=time.time()
with Solver(name='glucose4',bootstrap_with=f.clauses) as s:
    r=s.solve()
print(sys.argv[1],'vars',f.nv,'clauses',len(f.clauses),'SAT' if r else 'UNSAT','%.3fs'%(time.time()-t))
