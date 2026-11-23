"""SAT backends for the unbounded analysis (ext/unbounded).

One small interface, three backends:
    minicdcl  pure Python CDCL, from the sibling module ext/fastsat (ext/fastsat/scripts/minicdcl.py); no install
              needed, slow. HARD DEPENDENCY: every stored result was produced with it, and the test suite refuses to
              run without it (see MINICDCL_SHA256 and tests/conftest.py). Land ext/fastsat together with ext/unbounded.
    pysat     python-sat (pip install python-sat), any solver name it offers (cadical153, glucose4, ...)
    z3        z3-solver used as a plain SAT solver on the same clauses

pysat and z3 are imported only when asked for, so this file imports on a machine that has neither.

Interface (literals are non-zero ints, DIMACS style):
    b = make_backend('auto')
    b.add([1, -2])
    r = b.solve(assumptions=[3], deadline=None)   # True sat, False unsat under the assumptions, None limit reached
    b.val(v)                                      # value of variable v in the last model
    b.core()                                      # after False: subset of the assumptions that suffices, or None if the
                                                  # backend cannot say (callers then keep every assumption)
"""
import importlib, importlib.util, os, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))


class BackendError(Exception):
    pass


def find_repo_root():
    """Directory that holds scripts/glitchsat.py: $GLITCHSAT_ROOT, else the first parent of this file that has it."""
    env = os.environ.get('GLITCHSAT_ROOT')
    if env:
        return env if os.path.isfile(os.path.join(env, 'scripts', 'glitchsat.py')) else None
    d = HERE
    for _ in range(6):
        d = os.path.dirname(d)
        if os.path.isfile(os.path.join(d, 'scripts', 'glitchsat.py')):
            return d
    return None


# SHA-256 of ext/fastsat/scripts/minicdcl.py that produced every stored file in results/ (checked by the tests).
MINICDCL_SHA256 = '47a450c9bb291cdb77c8e6147f8e786d87616b866a25f7a6d70251549973c7c6'
MINICDCL_REQUIRED = 'ext/fastsat/scripts/minicdcl.py (sibling module ext/fastsat, or set GLITCHSAT_MINICDCL_DIR)'


def _minicdcl_dirs():
    out = []
    if os.environ.get('GLITCHSAT_MINICDCL_DIR'):
        out.append(os.environ['GLITCHSAT_MINICDCL_DIR'])
    root = find_repo_root()
    if root:
        out.append(os.path.join(root, 'scripts'))
    out.append(os.path.join(os.path.dirname(os.path.dirname(HERE)), 'fastsat', 'scripts'))   # side-by-side checkout
    out.append(os.path.join(os.path.dirname(HERE), 'fastsat', 'scripts'))
    return out


def load_minicdcl():
    if 'minicdcl' in sys.modules:
        return sys.modules['minicdcl']
    for d in _minicdcl_dirs():
        p = os.path.join(d, 'minicdcl.py')
        if os.path.isfile(p):
            spec = importlib.util.spec_from_file_location('minicdcl', p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            sys.modules['minicdcl'] = mod
            return mod
    raise BackendError('minicdcl.py not found (looked in: %s). ext/unbounded needs %s; or use --backend pysat / z3.'
                       % (', '.join(_minicdcl_dirs()), MINICDCL_REQUIRED))


def minicdcl_info():
    """(path, sha256, matches_stored_results) of the minicdcl.py that load_minicdcl() uses. Raises BackendError."""
    import hashlib
    mod = load_minicdcl()
    p = os.path.realpath(mod.__file__)
    with open(p, 'rb') as f:
        h = hashlib.sha256(f.read()).hexdigest()
    return p, h, h == MINICDCL_SHA256


class MiniBackend:
    """Pure Python CDCL. No unsat cores: core() returns None."""
    name = 'minicdcl'
    has_core = False

    def __init__(self):
        self.s = load_minicdcl().Solver()
        self.calls = 0
        self._m = None

    def reserve(self, n):
        self.s.new_vars(n)

    def add(self, clause):
        self.s.add_clause(clause)

    def solve(self, assumptions=(), deadline=None):
        self.calls += 1
        r = self.s.solve(assumptions, deadline=deadline)
        self._m = self.s.model() if r else None
        return r

    def val(self, v):
        return bool(self._m[v]) if v < len(self._m) else False

    def core(self):
        return None


class PySATBackend:
    """python-sat. Label: the adapter is tested here only against a stand-in module; see README (untested with real PySAT)."""
    has_core = True

    def __init__(self, solver='cadical153'):
        try:
            from pysat.solvers import Solver
        except ImportError as e:
            raise BackendError('python-sat is not installed: pip install python-sat') from e
        self.name = 'pysat:' + solver
        try:
            self.s = Solver(name=solver)
        except Exception as e:
            raise BackendError(f'python-sat has no solver {solver!r}: {e}')
        self.calls = 0
        self._m = None
        self._core = None

    def reserve(self, n):
        pass

    def add(self, clause):
        self.s.add_clause(list(clause))

    def solve(self, assumptions=(), deadline=None):
        self.calls += 1
        assumptions = list(assumptions)
        if deadline is None:
            r = self.s.solve(assumptions=assumptions)
        else:
            left = deadline - time.time()
            if left <= 0:
                return None
            try:
                timer = threading.Timer(left, self.s.interrupt)
                timer.start()
                try:
                    r = self.s.solve_limited(assumptions=assumptions, expect_interrupt=True)
                finally:
                    timer.cancel()
                    self.s.clear_interrupt()
            except (AttributeError, NotImplementedError):     # solver without interrupt support
                r = self.s.solve(assumptions=assumptions)
        if r is None:
            return None
        if r:
            self._m = set(self.s.get_model())
            self._core = None
        else:
            self._m = None
            c = self.s.get_core()
            self._core = list(c) if c is not None else None
        return bool(r)

    def val(self, v):
        return v in self._m

    def core(self):
        return self._core


class Z3Backend:
    """z3 as a SAT solver (Bool variables, clauses, assumption literals, unsat_core). Untested here: z3 is not installed."""
    name = 'z3'
    has_core = True

    def __init__(self):
        try:
            import z3
        except ImportError as e:
            raise BackendError('z3-solver is not installed: pip install z3-solver') from e
        self.z3 = z3
        self.s = z3.Solver()
        self.vars = {}
        self.calls = 0
        self._m = None
        self._core = None

    def reserve(self, n):
        pass

    def _lit(self, l):
        v = abs(l)
        x = self.vars.get(v)
        if x is None:
            x = self.vars[v] = self.z3.Bool('v%d' % v)
        return x if l > 0 else self.z3.Not(x)

    def add(self, clause):
        self.s.add(self.z3.Or(*[self._lit(l) for l in clause]) if len(clause) != 1 else self._lit(clause[0]))

    def solve(self, assumptions=(), deadline=None):
        self.calls += 1
        if deadline is not None:
            left = deadline - time.time()
            if left <= 0:
                return None
            self.s.set('timeout', max(1, int(left * 1000)))
        back = {}
        lits = []
        for a in assumptions:
            x = self._lit(a)
            back[x.get_id()] = a
            lits.append(x)
        r = self.s.check(*lits)
        if r == self.z3.sat:
            m = self.s.model()
            self._m = {v for v, x in self.vars.items() if self.z3.is_true(m.eval(x, model_completion=True))}
            return True
        if r == self.z3.unsat:
            self._core = [back[x.get_id()] for x in self.s.unsat_core() if x.get_id() in back]
            return False
        return None

    def val(self, v):
        return v in self._m

    def core(self):
        return self._core


def available_backends():
    out = []
    try:
        load_minicdcl(); out.append('minicdcl')
    except BackendError:
        pass
    for mod, nm in (('pysat.solvers', 'pysat'), ('z3', 'z3')):
        try:
            importlib.import_module(mod); out.append(nm)
        except ImportError:
            pass
    return out


def make_backend(name='auto'):
    """auto = pysat (cadical153) if installed, else z3 if installed, else minicdcl. 'pysat:NAME' picks a python-sat solver."""
    name = name or 'auto'
    if name == 'auto':
        for cand in ('pysat', 'z3', 'minicdcl'):
            try:
                return make_backend(cand)
            except BackendError:
                continue
        raise BackendError('no SAT backend available (python-sat, z3-solver or scripts/minicdcl.py)')
    if name == 'minicdcl':
        return MiniBackend()
    if name == 'z3':
        return Z3Backend()
    if name == 'pysat':
        return PySATBackend()
    if name.startswith('pysat:'):
        return PySATBackend(name.split(':', 1)[1])
    raise BackendError(f'unknown backend {name!r} (auto, minicdcl, pysat, pysat:NAME, z3)')
