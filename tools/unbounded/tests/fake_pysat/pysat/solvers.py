"""Stand-in for python-sat, used ONLY by the tests to exercise the PySAT adapter and the unsat-core code paths on a
machine without python-sat. It wraps the pure Python solver; get_core() returns a minimal core found by deletion.
It is not python-sat and says nothing about how the real package behaves."""
import sat as _sat


class Solver:
    def __init__(self, name='cadical153'):
        if name not in ('cadical153', 'glucose4'):
            raise ValueError(name)
        self._s = _sat.load_minicdcl().Solver()
        self._core = None
        self._model = None

    def add_clause(self, c):
        self._s.add_clause(c)

    def solve(self, assumptions=()):
        r = self._s.solve(assumptions)
        if r:
            m = self._s.model()
            self._model = [v if m[v] else -v for v in range(1, len(m))]
            self._core = None
        else:
            core = list(assumptions)
            for a in list(core):
                trial = [x for x in core if x != a]
                if self._s.solve(trial) is False:
                    core = trial
            self._core, self._model = core, None
        return r

    def get_model(self):
        return self._model

    def get_core(self):
        return self._core
