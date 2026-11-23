"""Firmware stage: did the compiler keep the repeated checks that are in the C source?

Reads the compiled ELF (RV32IMC, via the decoder of ext/firmware/rv32sim) and its line table
(<name>.lines.json written by ext/firmware/scripts/build.py, or produced here with llvm-dwarfdump) and, for every
repeated check found in the source, counts

  guards       source guards (`if (...) handler();`) that still own a conditional branch or a call to their handler
               in the binary (instructions whose line-table entry is one of the guard's lines)
  evaluations  how many times the checked computation is still done: call sites of the compared function plus its
               inlined copies inside the checking function (one per loop of the inlined code; when the loops were
               unrolled, one per stretch of its instructions that is not interrupted by a jump of another line)

Verdict for N guards in the source:
  independent checks left = max(guards, evaluations): a check counts as lost only when both counts say so
  SURVIVED  N left          WEAKENED  fewer, but at least two          REMOVED  one: the repetition is gone
Not detected: a comparison computed once whose result is tested N times with N surviving branches.

The line table is the compiler's own statement of which instruction belongs to which source line. Code the compiler
shared between two source lines carries one of them (or line 0), so the count is of what is still separate.
"""
import json
import os
import re
import subprocess

from . import paths
from .model import StageResult, SURVIVED, WEAKENED, REMOVED, UNTRACKED


class Binary:
    def __init__(self, elf):
        paths.setup()
        rv = paths.optional("rv32sim")
        if rv is None:
            raise RuntimeError("the firmware stage needs ext/firmware (rv32sim decoder); set GLITCHSAT_EXT")
        self.isa = paths.optional("rv32sim.isa")
        self.elf = str(elf)
        lp = os.path.splitext(self.elf)[0] + ".lines.json"
        self.prog = rv.load_elf(self.elf)
        self.lines_from = lp if os.path.exists(lp) else None
        if not self.prog.lines:
            self.prog.lines.update(_dwarf_lines(self.elf))
            self.lines_from = "llvm-dwarfdump --debug-line" if self.prog.lines else None

    def func(self, name):
        if name not in self.prog.symbols:
            return None
        a, size = self.prog.symbols[name]
        out, pc = [], a
        while pc < a + size:
            ins = self.prog.code[pc]
            f, ln = self.prog.lines.get(pc, ("?", 0))
            out.append((pc, ins, os.path.basename(str(f)), ln))
            pc += ins.size
        return out

    def calls(self, name):
        """[(pc, target symbol)] for calls/jumps to named functions inside function `name`."""
        isa = self.isa
        a, size = self.prog.symbols[name]
        by_addr = {v[0]: k for k, v in self.prog.symbols.items() if v[1] or k.startswith("rom_")}
        out, last, pc = [], {}, a
        while pc < a + size:
            ins = self.prog.code[pc]
            t = None
            if ins.op == isa.AUIPC:
                last[ins.rd] = (pc + ins.imm) & 0xFFFFFFFF
            if ins.op == isa.JALR and ins.rs1 in last:
                t = (last[ins.rs1] + ins.imm) & 0xFFFFFFFE
            elif ins.op == isa.JAL:
                t = (pc + ins.imm) & 0xFFFFFFFF
            if t in by_addr and not (a <= t < a + size):
                out.append((pc, by_addr[t]))
            pc += ins.size
        return out


def _dwarf_lines(elf):
    tool = paths.tool("llvm-dwarfdump")
    if not tool:
        return {}
    try:
        txt = subprocess.run([tool, "--debug-line", elf], capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return {}
    files, out = {}, {}
    for m in re.finditer(r"file_names\[\s*(\d+)\]:\s*\n\s*name:\s*\"([^\"]+)\"", txt):
        files[int(m.group(1))] = m.group(2)
    rows = []
    for m in re.finditer(r"^0x([0-9a-f]+)\s+(\d+)\s+\d+\s+(\d+)\s", txt, re.M):
        rows.append((int(m.group(1), 16), files.get(int(m.group(3)), "?"), int(m.group(2))))
    rows.sort()
    for i, (a, f, ln) in enumerate(rows):
        end = rows[i + 1][0] if i + 1 < len(rows) else a + 2
        for pc in range(a, min(end, a + 4096), 2):
            out.setdefault(pc, (f, ln))
    return out


def check(cm, binary, stage, source_text=None):
    if cm.kind == "fw_repeated_check":
        return _repeat(cm, binary, stage, source_text)
    if cm.kind == "fw_flow_counter":
        return _flow(cm, binary, stage)
    return None


def _body_lines(source_text, fname):
    from . import intent_fw
    text, _ = intent_fw._strip(source_text)
    for n, s, e in intent_fw.functions(text):
        if n == fname:
            return text.count("\n", 0, s) + 1, text.count("\n", 0, e) + 1
    return None


def _repeat(cm, b, stage, source_text):
    i = cm.intent
    fn = b.func(i["function"])
    if fn is None:
        return StageResult(cm.id, stage, UNTRACKED, evidence=[f"function {i['function']} is not a symbol of {b.elf} (inlined or renamed)"])
    if not b.prog.lines:
        return StageResult(cm.id, stage, UNTRACKED, evidence=["the binary has no line table (build with -g, or keep the .lines.json next to it)"])
    src = os.path.basename(i["file"])
    isa = b.isa
    calls = dict(b.calls(i["function"]))
    present, ev, detail = 0, [], []
    for g in i["guards"]:
        mine = [(pc, ins) for pc, ins, f, ln in fn if f == src and g["line"] <= ln <= g["end"]]
        br = [pc for pc, ins in mine if ins.op in isa.BRANCHES]
        hc = [pc for pc, ins in mine if calls.get(pc) == g.get("handler")] if g.get("handler") else []
        ok = bool(br or hc)
        present += ok
        detail.append(dict(line=g["line"], instructions=len(mine), branches=len(br), handler_calls=len(hc), present=ok))
        if not ok:
            ev.append(f"{src}:{g['line']} `if ({g['text']})`" + (f" -> {g['handler']}()" if g.get("handler") else "") +
                      (": no instruction of the binary belongs to this line" if not mine else
                       f": {len(mine)} instruction(s) left, but no conditional branch and no call to its handler"))
    n = i["copies"]
    evals, how = None, None
    for callee in i.get("callees", []):
        direct = sum(1 for pc, t in calls.items() if t == callee)
        rng = None
        if source_text:
            rng = _body_lines(source_text, callee)
        runs = loops = 0
        if rng:
            inside, flow_gap = False, True
            for pc, ins, f, ln in fn:
                if f == src and rng[0] <= ln <= rng[1]:
                    if not inside and flow_gap:
                        runs += 1
                    inside, flow_gap = True, False
                    if ins.op in isa.BRANCHES and ins.imm < 0:
                        loops += 1                # a backward branch of the inlined function: one loop per copy
                else:
                    inside = False
                    if ins.op in isa.BRANCHES or ins.op in (isa.JAL, isa.JALR):
                        flow_gap = True       # a jump, call or branch of another line ends the inlined copy
        inl = loops if loops else runs
        c = direct + inl
        if c and (evals is None or c < evals):
            evals, how = c, f"{callee}: {direct} call site(s) + {inl} inlined copy(ies)" + (" (one loop each)" if loops else "")
    meas = dict(intended=n, guards_present=present, evaluations=evals, guards=detail, lines_from=b.lines_from)
    if evals is not None:
        ev.append(f"the checked computation is still done {evals} time(s) in {i['function']} ({how})")
    eff = present if evals is None else max(present, evals)     # both counts must agree before a check is called lost
    meas["independent"] = eff
    if eff >= n:
        v = SURVIVED
        if present >= n:
            ev.insert(0, f"all {n} guards own a conditional branch or handler call in the binary")
        else:
            ev.insert(0, f"only {present} of {n} guards can be told apart by source line, but the checked computation "
                         f"is still done {evals} times, each with its own branches")
    elif eff >= 2:
        v = WEAKENED
        ev.insert(0, f"{eff} of {n} independent checks left in the binary ({present} guard line(s) with a branch)")
    else:
        v = REMOVED
        ev.insert(0, f"{eff} of {n} independent checks left in the binary ({present} guard line(s) with a branch): "
                     "the repetition is gone")
    return StageResult(cm.id, stage, v, measured=meas, evidence=ev)


def _flow(cm, b, stage):
    i = cm.intent
    fn = b.func(i["function"])
    if fn is None or not b.prog.lines:
        return StageResult(cm.id, stage, UNTRACKED, evidence=[f"function {i['function']} or its line table not available in the binary"])
    src = os.path.basename(i["file"])
    isa = b.isa
    steps = {ln: sum(1 for pc, ins, f, l in fn if f == src and l == ln) for ln in i["steps"]}
    kept = sum(1 for v in steps.values() if v)
    chk = 0
    for g in i["checks"]:
        chk += any(ins.op in isa.BRANCHES for pc, ins, f, ln in fn if f == src and g["line"] <= ln <= g["end"])
    meas = dict(steps=len(steps), steps_with_code=kept, checks=len(i["checks"]), checks_with_branch=chk)
    ev = [f"{kept} of {len(steps)} counter updates have code in the binary; {chk} of {len(i['checks'])} counter checks have a conditional branch"]
    if chk == 0:
        v = REMOVED
        ev.append("the comparison of the counter was folded away: the compiler proved its value at compile time")
    elif kept < len(steps):
        v = WEAKENED
        ev.append("some updates were folded into constants: skipping the code between them no longer changes the counter")
    else:
        v = SURVIVED
    return StageResult(cm.id, stage, v, measured=meas, evidence=ev)


def recorded_margin(elf):
    """Minimum number of instruction faults recorded by ext/firmware for this build (matched by file name)."""
    p = os.path.join(paths.ext_root(), "firmware", "results", "summary.json")
    if not os.path.isfile(p):
        return None
    stem = os.path.splitext(os.path.basename(elf))[0]
    with open(p) as f:
        s = json.load(f)
    for row in s.get("table", []):
        if row.get("build") == stem:
            t = row["tampered_payload"]
            return dict(min_faults=t["four_models"].get("exact"), text=t["four_models"]["text"],
                        per_model={k: v["text"] for k, v in t["per_model"].items()},
                        label="SIMULATED (recorded by ext/firmware: rv32sim, one fault model per search)",
                        source="ext/firmware/results/summary.json")
    return None
