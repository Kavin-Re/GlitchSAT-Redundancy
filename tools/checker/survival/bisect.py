"""Which synthesis command broke it: re-run the Yosys script one command at a time (needs Yosys).

For i = 1..n the first i commands of the script are run, followed by a neutral tail (`proc; flatten; techmap`, hierarchy guards lifted) that
only makes the intermediate design readable as gates and merges nothing. Each intermediate netlist gets the normal
netlist check; the first prefix whose verdict differs from the previous one names the command.
"""
import os
import re

from . import gnet, pipeline
from . import stage_netlist as SN
from .model import ORDER, NOT_CHECKED

TAIL = pipeline.RTL_REFERENCE_FLOW


def commands(script):
    return [c.strip() for c in re.split(r"[;\n]", re.sub(r"#[^\n]*", "", script))
            if c.strip() and c.split()[0] not in ("read_verilog", "write_json", "hierarchy", "read", "write_verilog", "stat")]


def bisect(verilog, top, script, cms, workdir, stage):
    import copy
    cmds = commands(script)
    out = dict(commands=cmds, steps=[], first_break={}, label="MEASURED (Yosys run per command prefix)")
    last = {}
    for i in range(len(cmds) + 1):
        flow = "; ".join(cmds[:i] + [TAIL])
        path = os.path.join(workdir, f"{stage}.bisect{i}.json")
        ok, msg = pipeline.run_yosys(verilog, top, flow, path)
        if not ok:
            out["steps"].append(dict(index=i - 1, command=cmds[i - 1] if i else "(as written)", error=msg))
            continue
        try:
            g = gnet.load(path, top)
        except Exception as e:
            out["steps"].append(dict(index=i - 1, command=cmds[i - 1] if i else "(as written)", error=str(e)[:200]))
            continue
        row = dict(index=i - 1, command=cmds[i - 1] if i else "(as written)", gates=len(g.gates), verdicts={})
        for cm in cms:
            c2 = copy.deepcopy(cm)
            r = SN.check(c2, g, f"{stage}#{i}", False)
            if r is None:
                continue
            row["verdicts"][cm.id] = r.verdict
            if i and cm.id not in out["first_break"] and ORDER.get(r.verdict, 0) > ORDER.get(last.get(cm.id, NOT_CHECKED), 0) \
                    and ORDER.get(r.verdict, 0) >= 2:
                out["first_break"][cm.id] = dict(index=i - 1, command=cmds[i - 1], verdict=r.verdict)
            last[cm.id] = r.verdict
        out["steps"].append(row)
    return out
