"""Design description for the guarded-boot toy family (the shape of rtl/v0.v, v1.v, v2.v, v2e.v), its direct mapping
to gates, and the Verilog + Yosys scripts written for a hardened candidate.

A design is: an attacker input `sig` compared with a constant key by `copies` identical compare blocks; a state
register that goes idle -> armed -> (accept | reject) and then holds; and a rule (`voter`) that says how the compare
results choose between the accept and the reject word.

  voter = 'single_and'   one net ok = m0 & m1 & ... picks the whole word (rtl/v1.v). The voter sits BEFORE the register.
          'per_bit_and'  one separately kept AND voter per state bit (W voters in front of the register).
          'owner'        no voter gate: state bit i is driven by copy owner[i] alone (rtl/v2.v). The vote is the
                         consumer's comparison of the whole word, i.e. the voter sits AFTER the register.
  alarm = 'none' | 'infect' | 'sticky'   disagreement between ANY two compare blocks (the owning copies plus
          `check_copies` extra blocks that own no bit) forces the reject word ('infect'); 'sticky' also latches the
          alarm in a flop that keeps forcing reject (a one-bit saturating alarm counter).
  trap_invalid   a state that is none of the four code words moves to reject instead of holding.
  output = 'state' (boot_word = state register, as v1/v2) | 'decoded' (boot_word = boot_ok ? 0x96 : 0x69, as v0).
"""
import dataclasses
from .netlist import Builder

OUT_ACCEPT, OUT_REJECT = 0x96, 0x69


@dataclasses.dataclass(frozen=True)
class Spec:
    name: str = 'v2'
    key: int = 0xC3
    width: int = 8
    idle: int = 0xF0
    armed: int = 0xCC
    accept: int = 0x96
    reject: int = 0x69
    copies: int = 3
    check_copies: int = 0
    voter: str = 'owner'
    owner: tuple = (0, 1, 2, 0, 1, 2, 0, 1)
    alarm: str = 'none'
    trap_invalid: bool = False
    output: str = 'state'

    def problems(self):
        p = []
        codes = [self.idle, self.armed, self.accept, self.reject]
        if len(set(codes)) != 4:
            p.append('idle, armed, accept and reject must be four different words')
        if any(not 0 <= c < (1 << self.width) for c in codes):
            p.append('a code word does not fit the state width')
        if self.voter not in ('single_and', 'per_bit_and', 'owner'):
            p.append('unknown voter')
        if self.voter == 'owner':
            if len(self.owner) != self.width or set(self.owner) != set(range(self.copies)):
                p.append('owner must name a copy for each state bit and use every copy')
        if self.alarm not in ('none', 'infect', 'sticky'):
            p.append('unknown alarm')
        if self.alarm != 'none' and self.copies + self.check_copies < 2:
            p.append('an alarm needs at least two compare blocks')
        if self.alarm == 'none' and self.check_copies:
            p.append('check copies are only used by an alarm')
        if self.output == 'state' and (self.width != 8 or self.accept != OUT_ACCEPT):
            pass   # allowed: then the consumer must compare with spec.accept; goal_value() reports it
        if self.output not in ('state', 'decoded'):
            p.append('unknown output')
        if self.copies < 1:
            p.append('copies < 1')
        return p

    def goal_value(self):
        return self.accept if self.output == 'state' else OUT_ACCEPT

    def out_width(self):
        return self.width if self.output == 'state' else 8

    def replace(self, **kw):
        return dataclasses.replace(self, **kw)

    def as_dict(self):
        d = dataclasses.asdict(self)
        d['owner'] = list(self.owner)
        for k in ('key', 'idle', 'armed', 'accept', 'reject'):
            d[k + '_hex'] = f'0x{getattr(self, k):0{(self.width + 3) // 4 if k != "key" else 2}X}'
        return d

    def short(self):
        s = f'{self.copies} cop{"y" if self.copies == 1 else "ies"}'
        if self.check_copies:
            s += f' + {self.check_copies} check'
        s += f', voter {self.voter}'
        if self.voter == 'owner':
            s += ' ' + ''.join(str(o) for o in reversed(self.owner))
        h = (self.width + 3) // 4
        s += f', idle/armed/accept/reject {self.idle:0{h}X}/{self.armed:0{h}X}/{self.accept:0{h}X}/{self.reject:0{h}X}'
        if self.alarm != 'none':
            s += f', alarm {self.alarm}'
        if self.trap_invalid:
            s += ', invalid state -> reject'
        return s


PRESETS = {
    'v0': Spec(name='v0', width=2, idle=0, armed=1, accept=2, reject=3, copies=1, voter='single_and', owner=(), output='decoded'),
    'v1': Spec(name='v1', copies=2, voter='single_and', owner=()),
    'v2': Spec(name='v2'),
    'v2e': Spec(name='v2e', armed=0xA5),
}
PRESET_RTL = {'v0': 'rtl/v0.v', 'v1': 'rtl/v1.v', 'v2': 'rtl/v2.v', 'v2e': 'rtl/v2e.v'}


MAPPINGS = {   # name -> (style, share, what it models)
    'select-shared': ('select', 'scope', 'priority-select next state, every identical gate shared outside the kept copies (most sharing)'),
    'mux-shared': ('mux', 'scope', 'per-bit word mux, every identical gate shared outside the kept copies'),
    'unshared': ('mux', 'none', 'per-bit logic, nothing shared (like the stored 68-gate netlist: one mux per bit)'),
    'merged': ('mux', 'all', 'identical gates shared ACROSS the copies too: what opt_merge after flatten does'),
}
UNMERGED = ('select-shared', 'mux-shared', 'unshared')


def build_mapping(spec, mapping):
    style, share, _ = MAPPINGS[mapping]
    return build(spec, share, style)


def build(spec, share='scope', style='select'):
    """Map the description to gates. share: see netlist.Builder ('scope', 'none', 'all' = merged copies).
    style: two equivalent ways to write the next-state logic; they differ only in which nets end up shared."""
    pr = spec.problems()
    if pr:
        raise ValueError('; '.join(pr))
    B = Builder(spec.name, share)
    B.input('clk')
    sig = B.input('sig', 8)
    W = spec.width
    st = [B.flop(f'st[{i}]', (spec.idle >> i) & 1) for i in range(W)]
    m = []
    for j in range(spec.copies + spec.check_copies):
        with B.scope(f'c{j}'):
            x = B.eq_const(sig, spec.key)
        if share != 'all':
            B.rename(x, f'c{j}.m')
        m.append(x)
    bit = lambda v, i: '1' if (v >> i) & 1 else '0'
    is_idle, is_armed = B.eq_const(st, spec.idle), B.eq_const(st, spec.armed)
    B.rename(is_idle, 'is_idle'); B.rename(is_armed, 'is_armed')
    bad, aq = '0', None
    if spec.alarm != 'none':
        bad = B.tree('or', [B.XOR(m[j], m[j + 1]) for j in range(len(m) - 1)])
        B.rename(bad, 'disagree')
        if spec.alarm == 'sticky':
            aq = B.flop('alarm', 0)
            bad = B.OR(bad, aq)
            B.rename(bad, 'bad')
            B.set_d(aq, bad)
    own = m[:spec.copies]
    if spec.voter == 'single_and':
        ok = B.tree('and', own)
        B.rename(ok, 'ok')
        sel = [ok] * W
    elif spec.voter == 'per_bit_and':
        sel = []
        for i in range(W):
            with B.scope(f'v{i}'):
                sel.append(B.tree('and', own) if len(own) > 1 else own[0])
    else:
        sel = [m[spec.owner[i]] for i in range(W)]
    hold = B.AND(B.NOT(is_idle), B.NOT(is_armed))
    valid = '1'
    if spec.trap_invalid:
        valid = B.OR(B.OR(is_idle, is_armed), B.OR(B.eq_const(st, spec.accept), B.eq_const(st, spec.reject)))
        B.rename(valid, 'valid')
    # style 'select':  load ? accept_i : base_i  with  load = is_armed & sel & ~bad.  With hashing there is ONE load net
    #   per selecting signal and one base term per (armed bit, reject bit) class: a single flip can rewrite several
    #   state bits. On the nine armed constants of research/c6/p01 this is never above the apt Yosys 0.33 result.
    # style 'mux':  is_idle ? armed_i : is_armed ? word_i : hold, with word_i = sel ? accept_i : reject_i per bit.
    nbad = B.NOT(bad)
    for i in range(W):
        a_i, r_i = bit(spec.accept, i), bit(spec.reject, i)
        held = B.AND(hold, B.MUX(valid, r_i, st[i]))
        if style == 'select':
            base = B.OR(B.OR(B.AND(is_idle, bit(spec.armed, i)), B.AND(is_armed, r_i)), held)
            nxt = B.MUX(B.AND(B.AND(is_armed, sel[i]), nbad), base, a_i) if a_i != r_i else base
        else:
            word = B.MUX(bad, B.MUX(sel[i], r_i, a_i), r_i)
            B.rename(word, f'word[{i}]')
            nxt = B.OR(B.OR(B.AND(is_idle, bit(spec.armed, i)), B.AND(is_armed, word)), held)
        if aq is not None:
            nxt = B.MUX(aq, nxt, r_i)
        B.set_d(st[i], nxt)
    boot_ok = B.eq_const(st, spec.accept)
    B.rename(boot_ok, 'boot_ok')
    B.output('boot_ok', [boot_ok])
    if spec.output == 'state':
        B.output('boot_word', st)
    else:
        B.output('boot_word', [B.MUX(boot_ok, bit(OUT_REJECT, i), bit(OUT_ACCEPT, i)) for i in range(8)])
    nl = B.finish()
    nl.scope_of = dict(B.scope_of)
    return nl


def reference_trace(spec, cycles):
    """Fault-free behaviour from the description alone (no netlist): per input value the boot_word per cycle."""
    out = []
    for sig in range(256):
        st, alarm, row = spec.idle, 0, []
        for _ in range(cycles):
            ok = st == spec.accept
            row.append(st if spec.output == 'state' else (OUT_ACCEPT if ok else OUT_REJECT))
            match = sig == spec.key          # all blocks agree when nothing is flipped, so the alarm never fires
            if st == spec.idle:
                st = spec.armed
            elif st == spec.armed:
                st = spec.accept if match else spec.reject
            elif spec.trap_invalid and st not in (spec.accept, spec.reject):
                st = spec.reject
        out.append(row)
    return out


# ------------------------------------------------------------------------------------------------ Verilog
def verilog(spec, module=None, note=''):
    module = module or spec.name
    W, h = spec.width, (spec.width + 3) // 4
    c = lambda v: f"{W}'h{v:0{h}X}"
    nb = spec.copies + spec.check_copies
    L = ['// Written by `glitchsat harden`. Toy design, modelled bit flips only, not a security proof.',
         f"// KEY = 8'h{spec.key:02X}. Attack goal in the analysis: boot accepted while sig != KEY.",
         f'// {spec.short()}']
    L += ['// ' + x for x in note.splitlines() if x]
    L += ['(* keep_hierarchy *) module cmp8(input [7:0] a, output m);', f"  assign m = (a == 8'h{spec.key:02X});", 'endmodule', '']
    if spec.voter == 'per_bit_and':
        L += [f'(* keep_hierarchy *) module vote{spec.copies}(input [{spec.copies - 1}:0] m, output v);', '  assign v = &m;', 'endmodule', '']
    L.append(f'module {module}(input clk, input [7:0] sig, output boot_ok, output [7:0] boot_word);')
    L.append(f'  (* keep *) reg [{W - 1}:0] st; initial st = {c(spec.idle)};   // idle {c(spec.idle)}, armed {c(spec.armed)}, accept {c(spec.accept)}, reject {c(spec.reject)}')
    L.append('  wire ' + ', '.join(f'm{j}' for j in range(nb)) + '; ' + ' '.join(f'cmp8 c{j}(.a(sig), .m(m{j}));' for j in range(nb)))
    if spec.voter == 'single_and':
        L.append('  (* keep *) wire ok = ' + ' & '.join(f'm{j}' for j in range(spec.copies)) + ';   // single voter in front of the register')
        L.append(f'  (* keep *) wire [{W - 1}:0] sel = {{{W}{{ok}}}};')
    elif spec.voter == 'per_bit_and':
        L.append(f'  (* keep *) wire [{W - 1}:0] sel;')
        mv = '{' + ', '.join(f'm{j}' for j in reversed(range(spec.copies))) + '}'
        for i in range(W):
            L.append(f'  vote{spec.copies} v{i}(.m({mv}), .v(sel[{i}]));')
    else:
        L.append(f'  (* keep *) wire [{W - 1}:0] sel = {{{", ".join(f"m{spec.owner[i]}" for i in reversed(range(W)))}}};   // bit i is owned by one compare copy')
    if spec.alarm != 'none':
        L.append('  (* keep *) wire disagree = ' + ' | '.join(f'(m{j} ^ m{j + 1})' for j in range(nb - 1)) + ';   // any two compare blocks differ')
        if spec.alarm == 'sticky':
            L.append("  (* keep *) reg alarm; initial alarm = 1'b0;")
            L.append('  (* keep *) wire bad = disagree | alarm;')
        else:
            L.append('  wire bad = disagree;')
        L.append(f'  (* keep *) wire [{W - 1}:0] word = bad ? {c(spec.reject)} : ((sel & {c(spec.accept)}) | (~sel & {c(spec.reject)}));')
    else:
        L.append(f'  (* keep *) wire [{W - 1}:0] word = (sel & {c(spec.accept)}) | (~sel & {c(spec.reject)});')
    dflt = 'st'
    if spec.trap_invalid:
        L.append(f'  wire valid = (st == {c(spec.idle)}) | (st == {c(spec.armed)}) | (st == {c(spec.accept)}) | (st == {c(spec.reject)});')
        dflt = f'valid ? st : {c(spec.reject)}'
    L.append('  always @(posedge clk) begin')
    ind = '    '
    if spec.alarm == 'sticky':
        L.append('    alarm <= bad;')
        L.append(f'    if (alarm) st <= {c(spec.reject)};')
        L.append('    else case (st)')
    else:
        L.append('    case (st)')
    L += [f'{ind}  {c(spec.idle)}: st <= {c(spec.armed)};', f'{ind}  {c(spec.armed)}: st <= word;', f'{ind}  default: st <= {dflt};', f'{ind}endcase', '  end']
    L.append(f'  assign boot_ok = (st == {c(spec.accept)});')
    if spec.output == 'state':
        L.append('  assign boot_word = st;' if W == 8 else f"  assign boot_word = {{{8 - W}'b0, st}};")
    else:
        L.append("  assign boot_word = boot_ok ? 8'h96 : 8'h69;")
    L.append('endmodule')
    return '\n'.join(L) + '\n'


KEPT_MODULES = lambda spec: ['cmp8'] + ([f'vote{spec.copies}'] if spec.voter == 'per_bit_and' else [])


def yosys_script(spec, src, out, top=None, guard=True, flow='plain', abc='abc -g AND,OR,XOR,MUX', order='abc_then_flatten', merge=False):
    """One Yosys script. With guard=False it is command for command the script of
    research/c2/e2_variance/scripts/matrix.py for the same (flow, order, abc, merge); flow='plain', order='abc_then_flatten',
    default abc, merge=False is scripts/synth.sh (plain).

    guard=True adds the copy-separation step: after each kept module (cmp8, and vote<n> when used) has been mapped on its
    own, every cell inside it gets keep=1 BEFORE flatten, so that an opt_merge after flatten is expected not to fold the
    identical copies into one (opt_merge skips cells that carry keep; read from the Yosys source, UNTESTED-HERE).
    In flatten_then_abc the guard is set right after proc; abc then sees all copies at once and may restructure them
    whatever the attribute says, so the guard is not expected to help there (measured by cloud/run_cloud.sh)."""
    top = top or spec.name
    unset = 'setattr -mod -unset keep_hierarchy *'
    keepcmd = [f'setattr -set keep 1 {m}/c:*' for m in KEPT_MODULES(spec)] if guard else []
    pre = [f'synth -top {top}', 'dffunmap'] if flow == 'opt' else ['proc', 'opt_clean', 'techmap', 'opt_clean']
    L = [f'read_verilog {src}', f'hierarchy -top {top}']
    if order == 'abc_then_flatten':
        L += pre + ([abc] if abc else []) + ['opt_clean'] + keepcmd + [unset, 'flatten', 'opt_clean', 'techmap', 'opt_clean']
        if merge:
            L += ['opt_merge', 'opt_clean']
    else:
        L += ['proc'] + keepcmd + [unset, 'flatten']
        L += ([f'synth -top {top}', 'dffunmap'] if flow == 'opt' else ['opt_clean', 'techmap', 'opt_clean'])
        if merge:
            L += ['opt_merge', 'opt_clean']
        L += ([abc] if abc else []) + ['opt_clean']
    L.append(f'write_json {out}')
    return '\n'.join(L) + '\n'
