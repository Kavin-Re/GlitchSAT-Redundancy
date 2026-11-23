"""Stub: SYNFI's fault-injection path uses sympy.Symbol only as a type annotation."""
class Symbol:  # never instantiated on the fault-injection path
    def __init__(self, *a, **k): raise RuntimeError('sympy stub: not available here')
true, false = True, False
def sympify(*a, **k): raise RuntimeError('sympy stub')
