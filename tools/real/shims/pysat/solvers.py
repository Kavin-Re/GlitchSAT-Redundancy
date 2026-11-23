"""Minisat22 stand-in backed by the pure-Python CDCL of ext/fastsat (same method names as PySAT)."""
import os, sys
_D = os.environ.get('GLITCHSAT_FASTSAT_SCRIPTS') or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'ext', 'fastsat', 'scripts')
if _D not in sys.path: sys.path.insert(0, _D)
import minicdcl

class Minisat22:
    def __init__(self, bootstrap_with=None, **kw):
        self._cls = [list(c) for c in (bootstrap_with or [])]
        self._m = None
    def add_clause(self, c): self._cls.append([int(l) for l in c])
    def solve(self, assumptions=()):
        n = max([abs(l) for c in self._cls for l in c] + [abs(l) for l in assumptions] + [1])
        s = minicdcl.Solver(n)
        for c in self._cls:
            s.add_clause(c)
        r = s.solve(list(assumptions))
        self._m = s.model() if r else None
        return bool(r)
    def get_model(self):
        m = self._m
        return None if m is None else [v if m[v] else -v for v in range(1, len(m))]
    def delete(self): self._cls = None
