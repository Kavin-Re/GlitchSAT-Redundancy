"""Incremental solver handle over the fastsat backends: clauses can be added between calls, budgets and horizons are
passed as assumptions, learned clauses are kept (bundled Python CDCL and PySAT). An external DIMACS binary is not
incremental: the whole clause list is written again for every call."""
import os, shutil, subprocess, tempfile, time
from . import fastsat


class Dimacs:
    """External solver binary (CaDiCaL, Kissat, ...): reads a DIMACS file, prints 's SATISFIABLE' and 'v' lines.
    One process per call; assumptions are written as unit clauses. Extra arguments: $GLITCHSAT_DIMACS_ARGS.
    A model must name every variable: CaDiCaL 3 leaves "unused" variables out of the 'v' lines unless
    --modelalllits=true is given, so that option is added when the binary offers it, and a model with missing
    variables is refused (never completed by guessing)."""

    def __init__(self, e, binary):
        path = shutil.which(binary)
        if not path:
            raise fastsat().BackendError('solver binary %r not found on PATH' % binary)
        self.bin = path; self.name = os.path.basename(path); self.e = e; self._m = None
        self.args = os.environ.get('GLITCHSAT_DIMACS_ARGS', '').split()
        try:
            h = subprocess.run([path, '--help'], capture_output=True, text=True, timeout=20).stdout
            if 'modelalllits' in h: self.args.append('--modelalllits=true')
        except (OSError, subprocess.SubprocessError):
            pass

    def solve(self, assumptions, deadline=None):
        self._m = None
        e = self.e
        fd, path = tempfile.mkstemp(suffix='.cnf', prefix='gscale_')
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(e.to_dimacs(list(assumptions)))
            to = None if deadline is None else max(0.05, deadline - time.time())
            try:
                r = subprocess.run([self.bin] + self.args + [path], capture_output=True, text=True, timeout=to)
            except subprocess.TimeoutExpired:
                return None
        finally:
            os.unlink(path)
        status = None; lits = []
        for line in r.stdout.splitlines():
            if line.startswith('s '): status = line[2:].strip()
            elif line.startswith('v '): lits += [int(x) for x in line[2:].split()]
        if status == 'UNSATISFIABLE': return False
        if status == 'SATISFIABLE':
            m = [None] * (e.nvars + 1)
            for l in lits:
                if 0 < abs(l) <= e.nvars: m[abs(l)] = l > 0
            missing = sum(1 for v in range(1, e.nvars + 1) if m[v] is None)
            if missing:
                raise RuntimeError('solver %s printed a model without %d of %d variables; refusing to guess them '
                                   '(pass an option that prints the full model in GLITCHSAT_DIMACS_ARGS)' % (self.name, missing, e.nvars))
            self._m = m
            return True
        if r.returncode not in (0, 10, 20) and status is None:
            raise RuntimeError('solver %s failed (exit %d): %s' % (self.name, r.returncode, r.stderr[-300:]))
        return None

    def model(self): return self._m
    def close(self): pass


class Inc:
    def __init__(self, e, backend='auto'):
        self.fs = fastsat()
        self.e = e; self.backend = backend; self.be = None; self.fed = 0
        self.calls = 0; self.time = 0.0

    def _sync(self):
        if self.be is None:
            if str(self.backend).startswith('dimacs:'): self.be = Dimacs(self.e, self.backend[7:])
            else: self.be = self.fs.make_backend(self.e, self.backend)
            self.fed = len(self.e.clauses)
            return
        s = getattr(self.be, 's', None)
        if s is not None:
            cl = self.e.clauses
            for i in range(self.fed, len(cl)):
                s.add_clause(cl[i])
        self.fed = len(self.e.clauses)

    @property
    def name(self):
        self._sync()
        return self.be.name

    def solve(self, assumptions=(), deadline=None, conflict_limit=None):
        """True / False / None (limit reached)."""
        self._sync()
        t0 = time.time(); self.calls += 1
        a = [x for x in assumptions if x != self.fs.T_]
        if self.fs.F_ in a:
            return False
        try:
            if conflict_limit is not None and hasattr(getattr(self.be, 's', None), 'stats') and self.be.name == 'minicdcl':
                return self.be.s.solve(a, deadline=deadline, conflict_limit=conflict_limit)
            return self.be.solve(a, deadline=deadline)
        finally:
            self.time += time.time() - t0

    def model(self):
        m = self.be.model()
        if m is not None and len(m) <= self.e.nvars:
            m = list(m) + [False] * (self.e.nvars + 1 - len(m))
        return m

    def close(self):
        if self.be is not None: self.be.close()
