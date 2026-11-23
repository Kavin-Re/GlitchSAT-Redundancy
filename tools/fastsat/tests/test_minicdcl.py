import itertools, random, time
import minicdcl


def brute(n, cls, assum):
    for bits in itertools.product([False, True], repeat=n):
        if all(bits[abs(a) - 1] == (a > 0) for a in assum) and all(any(bits[abs(l) - 1] == (l > 0) for l in c) for c in cls):
            return True
    return False


def test_random_cnf_against_truth_table():
    rng = random.Random(5)
    for it in range(1200):
        n = rng.randint(3, 11); m = rng.randint(1, n * 5)
        cls = [[rng.choice([-1, 1]) * rng.randint(1, n) for _ in range(rng.randint(1, 4))] for _ in range(m)]
        s = minicdcl.Solver(n)
        for c in cls: s.add_clause(c)
        for rep in range(3):                      # same instance, different assumptions (incremental use)
            assum = [rng.choice([-1, 1]) * v for v in rng.sample(range(1, n + 1), rng.randint(0, 3))]
            r = s.solve(assum)
            assert r == brute(n, cls, assum), (it, cls, assum)
            if r:
                mod = s.model()
                assert all(mod[abs(a)] == (a > 0) for a in assum)
                assert all(any(mod[abs(l)] == (l > 0) for l in c) for c in cls)


def php(p, h):
    v = lambda i, j: i * h + j + 1
    cls = [[v(i, j) for j in range(h)] for i in range(p)]
    for j in range(h):
        for a in range(p):
            for b in range(a + 1, p): cls.append([-v(a, j), -v(b, j)])
    return p * h, cls


def test_pigeonhole_unsat_and_sat():
    n, cls = php(6, 5); s = minicdcl.Solver(n)
    for c in cls: s.add_clause(c)
    assert s.solve() is False
    n, cls = php(5, 5); s = minicdcl.Solver(n)
    for c in cls: s.add_clause(c)
    assert s.solve() is True


def test_deadline_returns_none_not_a_verdict():
    n, cls = php(10, 9); s = minicdcl.Solver(n)
    for c in cls: s.add_clause(c)
    assert s.solve(deadline=time.time() + 0.2) is None
    assert s.solve(conflict_limit=200) is None


def test_empty_clause_and_unit_conflict():
    s = minicdcl.Solver(2); s.add_clause([1]); s.add_clause([-1])
    assert s.solve() is False
    s = minicdcl.Solver(2); s.add_clause([])
    assert s.solve() is False
    s = minicdcl.Solver(3); s.add_clause([1, 2]); s.add_clause([-1, 2])
    assert s.solve([-2]) is False and s.solve([2]) is True and s.solve() is True


def test_dimacs_roundtrip(tmp_path, capsys):
    p = tmp_path / 'a.cnf'
    p.write_text('c x\np cnf 3 3\n1 -2 0\n2 3 0\n-1 0\n')
    assert minicdcl.main([str(p)]) == 10
    out = capsys.readouterr().out
    assert 's SATISFIABLE' in out and 'v -1 -2 3 0' in out
    p.write_text('p cnf 1 2\n1 0\n-1 0\n')
    assert minicdcl.main([str(p)]) == 20
