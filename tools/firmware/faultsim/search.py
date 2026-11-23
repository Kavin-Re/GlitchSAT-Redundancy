"""Exhaustive search for the minimum number of instruction-level faults that
make the boot ROM run a tampered (or rolled-back) image.

Fault models (all applied to the dynamic instruction at step t):
  skip    the instruction is not executed (PC advances by its length)
  brinv   a conditional branch goes the other way (RISC-V has no flags; this
          is the analogue of a flag/condition inversion)
  rdflip  one bit of the value written to rd is flipped (register-file or
          write-back flip; for loads this is a flipped loaded value)
  pcoff   the next PC is off by d bytes, d in {-16..-2, +2..+16} (even)
  iwflip  one bit of the fetched 32-bit instruction word is flipped before
          decode (a fetch-register / decoder-input flip); k = 1 only

Search: depth-first over fault positions with k faults at most, for
k = 1, 2, ... kmax. A position is any executed step whose PC lies in the ROM
outside the MAC computation unit (hmac_sw.c / hmac_hw.c / mac_sha3_hw.c). For k = 1 every
single fault is tried and every success is listed. For k >= 2 the search
stops at the first success; reaching the end without one shows that no
combination of k faults works (inside the model). States are de-duplicated:
(registers, PC, peripheral state, a 128-bit BLAKE2b digest of RAM, step
count, faults left) is stored once known to fail, so equal states reached by
different fault sets are explored once. Only a digest collision (probability
far below 2^-64 for the state counts here) could hide an attack. A per-(build, model) time budget can stop a k
level; it is then reported as NOT COMPLETED, never as a result.
"""
import os
import time

from rv32sim import isa
from rv32sim.cpu import (Machine, RUNNING, IMAGE, OUTCOME_NAMES, ROM_BASE,
                         F_SKIP, F_BRINV, F_PCOFF, F_RDFLIP, F_IWFLIP)

MODELS = {"skip": F_SKIP, "brinv": F_BRINV, "rdflip": F_RDFLIP, "pcoff": F_PCOFF, "iwflip": F_IWFLIP}
PCOFFS = [d for d in range(-16, 17, 2) if d]
EXCLUDED_FILES = ("hmac_sw.c", "hmac_hw.c", "mac_sha3_hw.c")
# the failed-state memo is cleared when it holds this many states (memory bound; results unaffected)
MEMO_MAX = int(os.environ.get("FW_MEMO_MAX", "4000000"))


class Budget(Exception):
    pass


def fault_options(model, ins):
    if model == "skip":
        return [(F_SKIP, 0)]
    if model == "brinv":
        return [(F_BRINV, 0)] if ins.op in isa.BRANCHES else []
    if model == "rdflip":
        return [(F_RDFLIP, b) for b in range(32)] if ins.writes_rd() else []
    if model == "pcoff":
        return [(F_PCOFF, d) for d in PCOFFS]
    if model == "iwflip":
        return [(F_IWFLIP, b) for b in range(32)]
    raise ValueError(model)


class Searcher:
    def __init__(self, prog, flash, otp, model, trng_seed=1, limit=None, budget_s=600.0, exec_lock=True,
                 sites="decision", memo=True):
        self.p = prog
        self.use_memo = memo
        self.exec_lock = exec_lock
        self.flash, self.otp, self.seed = flash, otp, trng_seed
        self.model = model
        excl = set(a for a, (f, _l) in prog.lines.items() if f in EXCLUDED_FILES)
        if sites == "all":
            self.sites = set(prog.code)
        else:
            self.sites = set(a for a in prog.code if a not in excl and a >= ROM_BASE)
        g = self.fresh()
        g.run(10 ** 6)
        self.golden = g
        self.limit = limit or (3 * g.steps + 500)
        self.budget_s = budget_s
        self.memo = set()
        self.nodes = 0
        self.t0 = None

    def fresh(self):
        return Machine(self.p, self.flash, self.otp, self.seed, self.exec_lock)

    def _check_time(self):
        if time.time() - self.t0 > self.budget_s:
            raise Budget()

    def _run(self, m, kleft):
        """Continue m with at most kleft more faults; return list of faults or None."""
        visited = []
        memo = self.memo
        sites = self.sites
        n = 0
        while True:
            if m.outcome != RUNNING or m.steps >= self.limit:
                if m.outcome == IMAGE:
                    return []
                memo.update(visited)
                return None
            pc = m.pc
            if pc in sites:
                if self.use_memo:
                    k = (m.key(), m.steps, kleft)
                    if k in memo:
                        memo.update(visited)
                        return None
                    visited.append(k)
                    if len(memo) > MEMO_MAX:
                        memo.clear()
                if kleft:
                    ins = m.code[pc]
                    for mode, arg in fault_options(self.model, ins):
                        m2 = m.copy()
                        m2.step(mode, arg)
                        self.nodes += 1
                        if self.nodes & 255 == 0:
                            self._check_time()
                        r = self._run(m2, kleft - 1)
                        if r is not None:
                            return [(m.steps, pc, mode, arg)] + r
            m.step()
            n += 1
            if n & 1023 == 0:
                self._check_time()

    def k1_all(self):
        """Every single fault that succeeds (exhaustive k = 1)."""
        hits = []
        if self.t0 is None:
            self.t0 = time.time()
        m = self.fresh()
        while m.outcome == RUNNING and m.steps < self.limit:
            pc = m.pc
            if pc in self.sites:
                for mode, arg in fault_options(self.model, m.code[pc]):
                    m2 = m.copy()
                    m2.step(mode, arg)
                    self.nodes += 1
                    if self._run(m2, 0) is not None:
                        hits.append([(m.steps, pc, mode, arg)])
                self._check_time()
            m.step()
        return hits

    def minimum(self, kmax):
        """Return dict: min_faults (int or None), completed_k, witness, k1_hits, nodes, seconds."""
        self.t0 = time.time()
        out = {"model": self.model, "kmax": kmax, "min_faults": None, "completed_k": 0,
               "witness": None, "k1_count": 0, "k1_hits": [], "status": "no_attack_up_to_kmax",
               "golden_outcome": OUTCOME_NAMES[self.golden.outcome], "golden_steps": self.golden.steps}
        if self.golden.outcome == IMAGE:
            out.update(min_faults=0, status="boots_without_fault", witness=[])
            return out
        try:
            hits = self.k1_all()
            out["completed_k"] = 1
            out["k1_count"] = len(hits)
            out["k1_hits"] = hits
            if hits:
                out.update(min_faults=1, witness=hits[0], status="attack_found")
            else:
                for k in range(2, kmax + 1):
                    w = self._run(self.fresh(), k)
                    if w is not None:
                        out.update(min_faults=len(w), witness=w, status="attack_found")
                        break
                    out["completed_k"] = k
        except Budget:
            out["status"] = "budget_exhausted"
        out["nodes"] = self.nodes
        out["seconds"] = round(time.time() - self.t0, 2)
        self.memo.clear()
        return out


def replay(prog, flash, otp, faults, seed=1, limit=10 ** 6, exec_lock=True):
    """Re-run with the given faults [(step, pc, mode, arg)]; returns the machine."""
    m = Machine(prog, flash, otp, seed, exec_lock)
    todo = {s: (pc, mode, arg) for s, pc, mode, arg in faults}
    while m.outcome == RUNNING and m.steps < limit:
        f = todo.get(m.steps)
        if f is not None:
            assert m.pc == f[0], "replay diverged"
            m.step(f[1], f[2])
        else:
            m.step()
    return m


MODE_NAMES = {F_SKIP: "skip", F_BRINV: "brinv", F_PCOFF: "pcoff", F_RDFLIP: "rdflip", F_IWFLIP: "iwflip"}


def describe(prog, fault):
    """One fault as a dict: step, pc, function, source line, assembly, effect."""
    step, pc, mode, arg = fault
    ins = prog.code[pc]
    f, line = prog.lines.get(pc, ("?", 0))
    asm = isa.disasm(ins, pc)
    eff = {F_SKIP: "instruction skipped",
           F_BRINV: "branch direction inverted",
           F_PCOFF: "next PC %+d bytes" % arg,
           F_RDFLIP: "bit %d of %s flipped after write" % (arg, isa.ABI[ins.rd]),
           F_IWFLIP: "bit %d of fetched word flipped" % arg}[mode]
    if mode == F_IWFLIP:
        w = int.from_bytes(prog.rom[pc:pc + 4].ljust(4, b"\0"), "little") ^ (1 << arg)
        eff += " -> executes `%s`" % isa.disasm(isa.decode_at(w.to_bytes(4, "little"), 0), pc)
    return {"step": step, "pc": "0x%x" % pc, "function": prog.func_at(pc), "file": f, "line": line,
            "asm": asm, "model": MODE_NAMES[mode], "arg": arg, "effect": eff}
