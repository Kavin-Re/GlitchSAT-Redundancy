"""Minimal SDF reader for the file written by eda/regen_sdf.sh (OpenSTA `write_sdf`).

Collapses each cell's IOPATH arcs to ONE number per instance: the largest rise/fall delay over all arcs
(worst value of each (min:typ:max) triple).  That matches the one-delay-per-cell engine in vlab.timing;
it is pessimistic for fast pins.  INTERCONNECT delays are added to the driving cell (largest per driver).
Returns {instance_name: delay_ps}.
"""
import re

_NUM = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"


def _worst(triple_text):
    vals = [float(x) for x in re.findall(_NUM, triple_text)]
    return max(vals) if vals else 0.0


def load_sdf(path):
    txt = open(path).read()
    m = re.search(r"\(TIMESCALE\s+(%s)\s*(\w+)\)" % _NUM, txt)
    scale = 1000.0                                   # default 1 ns -> ps
    if m:
        scale = float(m.group(1)) * {"ps": 1.0, "ns": 1000.0, "us": 1e6}[m.group(2)]
    out = {}
    for cm in re.finditer(r"\(CELL\s*\(CELLTYPE\s+\"([^\"]+)\"\)\s*\(INSTANCE\s*([^)]*)\)(.*?)(?=\(CELL\s|\Z)",
                          txt, re.S):
        inst = cm.group(2).strip().replace("\\", "")
        body = cm.group(3)
        if inst:
            worst = 0.0
            for im in re.finditer(r"\(IOPATH\s+\S+\s+\S+\s+((?:\([^)]*\)\s*)+)\)", body):
                for tri in re.findall(r"\(([^)]*)\)", im.group(1)):
                    worst = max(worst, _worst(tri))
            out[inst] = worst * scale
        else:                                        # top cell: interconnect
            wire = {}
            for im in re.finditer(r"\(INTERCONNECT\s+(\S+)\s+\S+\s+((?:\([^)]*\)\s*)+)\)", body):
                drv = im.group(1).replace("\\", "").rsplit("/", 1)[0]
                w = max((_worst(t) for t in re.findall(r"\(([^)]*)\)", im.group(2))), default=0.0)
                wire[drv] = max(wire.get(drv, 0.0), w * scale)
            for d, w in wire.items():
                out["__wire__" + d] = w
    for k in [k for k in out if k.startswith("__wire__")]:
        d = k[len("__wire__"):]
        if d in out:
            out[d] += out[k]
        del out[k]
    return out
