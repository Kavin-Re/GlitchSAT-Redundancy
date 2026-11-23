import time
import minicdcl


class SolverNames:
    cadical195 = ('cd19', 'cd195', 'cdl19', 'cdl195', 'cadical19', 'cadical195')
    glucose4 = ('g4', 'g41', 'glucose4', 'glucose41')


class Solver:
    delay_s = 0.0          # tests set this to make solve() slow

    def __init__(self, name='cadical195', bootstrap_with=None, **kw):
        if name not in ('cadical195', 'glucose4'):
            raise NotImplementedError(name)
        cls = list(bootstrap_with or [])
        self.s = minicdcl.Solver(max((abs(l) for c in cls for l in c), default=0))
        for c in cls:
            self.s.add_clause(c)

    def add_clause(self, c):
        self.s.add_clause(c)

    def solve(self, assumptions=()):
        if Solver.delay_s:
            time.sleep(Solver.delay_s)
        return self.s.solve(list(assumptions))

    def get_model(self):
        m = self.s.model()
        return None if m is None else [v if m[v] else -v for v in range(1, len(m))]

    def delete(self):
        self.s = None
