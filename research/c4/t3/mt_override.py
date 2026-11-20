"""Imports MT's mutant list unchanged, then rewrites the 4 mutants whose text targeted the PbLe lines so
that they mutate the equivalent spot of the counter encoding (same ids, same intent). Everything else is untouched."""
import sys
sys.path.insert(0, 'research/c3/mt')
from mutate import *            # noqa
import mutate as _m
OV = {
 'k_plus1':     ("        kcap = k\n", "        kcap = k + 1\n"),
 'k_minus1':    ("        kcap = k\n", "        kcap = k - 1\n"),
 'drop_atmost': ("r = s.check(*(atmost(kcap) if outs else []))", "r = s.check()"),
 'min_bound2':  ("atmost(len(best) - 1)", "atmost(len(best) - 2)"),
}
M = [(x[0], x[1], OV[x[0]][0], OV[x[0]][1]) + tuple(x[4:]) if x[0] in OV else x for x in _m.M]
