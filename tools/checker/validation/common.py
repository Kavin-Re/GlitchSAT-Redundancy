"""Shared helpers of the validation scripts."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from survival import paths  # noqa: E402

paths.setup()
ROOT = paths.repo_root()
RESULTS = os.path.join(os.path.dirname(HERE), "results")
os.makedirs(RESULTS, exist_ok=True)


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    return dict(tp=tp, fp=fp, fn=fn, precision=None if p is None else round(p, 3), recall=None if r is None else round(r, 3))


def prf_text(d):
    f = lambda x: "n/a" if x is None else f"{x:.2f}"   # noqa: E731
    return f"precision {f(d['precision'])} ({d['tp']}/{d['tp'] + d['fp']}), recall {f(d['recall'])} ({d['tp']}/{d['tp'] + d['fn']})"
