"""Static facts about a built boot ROM, read from the ELF with rv32sim's decoder.

call_sites(prog) lists the calls in rom_main to the exits (rom_fail,
rom_alarm, rom_jump) and to mac_image. Calls are `auipc ra; jalr ra` pairs
(the build links with --no-relax) or `jal`. The compiler may share one call
instruction between several source-level calls (its line is then 0), so the
count is of call instructions, not of source calls.
"""
from rv32sim import isa

TARGETS = ("rom_alarm", "rom_fail", "rom_jump", "mac_image")


def call_sites(prog, func="rom_main"):
    a, size = prog.symbols[func]
    names = {prog.sym(n): n for n in TARGETS if n in prog.symbols}
    out = []
    last = {}
    pc = a
    while pc < a + size:
        ins = prog.code[pc]
        if ins.op == isa.AUIPC:
            last[ins.rd] = (pc + ins.imm) & 0xFFFFFFFF
        t = None
        if ins.op == isa.JALR and ins.rs1 in last:
            t = (last[ins.rs1] + ins.imm) & 0xFFFFFFFE
        elif ins.op == isa.JAL:
            t = (pc + ins.imm) & 0xFFFFFFFF
        if t in names:
            out.append({"pc": pc, "target": names[t], "line": prog.lines.get(pc, ("?", 0))[1]})
        pc += ins.size
    return out


def count_calls(prog, target, func="rom_main"):
    return sum(1 for c in call_sites(prog, func) if c["target"] == target)


def count_op(prog, op, func="rom_main"):
    """Number of instructions with operation `op` (an isa.* code) in `func`."""
    a, size = prog.symbols[func]
    n = 0
    pc = a
    while pc < a + size:
        ins = prog.code[pc]
        n += ins.op == op
        pc += ins.size
    return n
