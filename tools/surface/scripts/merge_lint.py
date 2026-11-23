#!/usr/bin/env python3
"""Redundancy-merge lint for GlitchSAT netlists (instant, no solver).

Question it answers: did the intended redundant copies of a check (c0/c1/c2 ...) survive synthesis as
separate logic, or do two or more copies now share nets, so that one fault site can act on several copies at once?

Method (purely structural, on the Yosys JSON netlist read by scripts/glitchsat.py `Netlist`):
  * decision bits: the bits of the goal output port (default boot_word). A goal bit that is a flop Q is replaced by
    that flop's D net (the logic that decides the next value); a gate-driven goal bit is used as is.
  * combinational cone: backward closure through gates, stopping at flop Q nets, input-port bits and constants.
  * input-dependent net: a gate net whose combinational support contains a primary input bit (any input port except
    clk). Only input-dependent nets can carry a copy's check result.
  * copy groups, two sources:
      names      - nets whose Yosys name carries a hierarchy prefix (c0., \\c0., c0/ ..., regex configurable).
                   Copy cone = combinational cone of the copy's named gate nets.
      structural - when no names survive: decision bits whose input-dependent cones overlap are put in one group
                   (union-find). The number of groups is the number of independent copies that are still visible.
                   Optionally the intended bit ownership can be given (--groups "0,3,6;1,4,7;2,5"); then shared nets
                   between the intended groups are reported like in names mode.
  * findings:
      shared nets   - nets inside the cones of two or more copies (copy logic that synthesis merged).
      merge points  - input-dependent nets outside every copy cone whose cone contains nets of two or more copies
                      (logic that combines copies before the decision bits, e.g. V1's `ok = m1 & m2`).
      single points - shared nets and merge points that reach at least one decision bit; each one is a place where
                      one modelled fault can act on more than one copy. The lint does NOT claim a single fault there
                      is sufficient to reach the goal; that needs the bounded search (scripts/glitchsat.py).
  * structural hashing: every net gets a canonical hash of its gate DAG (commutative inputs sorted; MUX ordered S,A,B;
    leaves = input-bit position, flop name, constant). Copies with equal hashes are structurally identical; a later
    structural-hashing / opt_merge pass would fold them into one unless the flow keeps them apart (the repo's E2
    synthesis sweep measured this effect; the lint itself only reports the identity).

verdict:
  merged            a single point covers every copy (structural mode with --copies N: one group only)
  partially_shared  a single point covers two or more copies but not all of them (structural, --copies N: 1 < groups < N)
  separate          no single point (structural mode: two or more independent groups, and not fewer than --copies)
  single_group      structural mode without --copies: all decision bits hang off one block of input-dependent logic
                    (a one-copy design, or copies that were merged; the lint cannot tell which)
  no_copies         no input-dependent logic reaches the decision bits

JSON output (schema "glitchsat-merge-lint/1"):
  {schema, netlist, netlist_sha256, top, goal_out, mode: "names"|"structural", verdict,
   copies: {label: {named_nets, cone_size, hash, decision_bits:[i,...]}},
   decision_bits: [{bit, net, owners:[label,...]}],
   shared_nets: [{net, net_id, copies:[...] }], merge_points: [{net, net_id, copies:[...], first: bool}],
   single_points: [{net, net_id, kind: "shared"|"merge", copies:[...], decision_bits_reached:[i,...]}],
   identical_copies: [[label, label, ...]], duplicate_hash_groups: int,
   structural_groups: [[bit, ...], ...], findings: [text, ...], runtime_s}
"""
import argparse, collections, hashlib, json, os, re, sys, time

DEFAULT_COPY_RE = r'(?:^|[\\/.$])(c\d+)[./]'


def _repo_root():
    env = os.environ.get('GLITCHSAT_ROOT')
    here = os.path.dirname(os.path.abspath(__file__))
    for c in ([env] if env else []) + [os.path.abspath(os.path.join(here, '..', '..', '..'))]:
        if c and os.path.isfile(os.path.join(c, 'scripts', 'glitchsat.py')):
            return c
    raise ImportError('cannot find scripts/glitchsat.py: set GLITCHSAT_ROOT to the repository root')


def engine():
    """Import scripts/glitchsat.py (its z3 import is optional, so this works without z3)."""
    root = _repo_root()
    p = os.path.join(root, 'scripts')
    if p not in sys.path:
        sys.path.insert(0, p)
    import glitchsat
    return glitchsat


def load(path, top):
    return engine().Netlist(path, top)


def _sha256(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


class Structure:
    """Cones, input dependence, fanout and canonical hashes of one Netlist (no solver)."""

    def __init__(self, nl, goal_out='boot_word'):
        self.nl = nl
        ports = nl.ports
        if goal_out not in ports or ports[goal_out].get('direction') != 'output':
            raise ValueError(f'goal output {goal_out!r} is not an output port')
        self.goal_out = goal_out
        self.in_bits = {}
        for p, v in ports.items():
            if v.get('direction') == 'input' and p != 'clk':
                for i, b in enumerate(v['bits']):
                    if isinstance(b, int):
                        self.in_bits[b] = (p, i)
        self.fanout = collections.defaultdict(set)
        for o in nl.drivers:
            for f in nl.fanins(o):
                if isinstance(f, int):
                    self.fanout[f].add(o)
        self.goal_bits = ports[goal_out]['bits']
        self._cone = {}
        self._dep = {}
        self._hash = {}
        self.decision = []   # (bit index, [decision nets])
        for i, b in enumerate(self.goal_bits):
            if not isinstance(b, int):
                continue
            if b in nl.dq:
                nets = [nl.dq[b]]
            elif self.dep_cone(b):
                nets = [b]
            else:   # gate goal bit that decodes flops only (e.g. boot_ok = st == 0x96): use the D nets of those flops
                sup = engine().support(nl, b)
                nets = sorted(nl.dq[q] for kind, q in (x for x in sup if isinstance(x, tuple)) if kind == 'flop') or [b]
            self.decision.append((i, nets))
        self.all_names = collections.defaultdict(list)  # filled below
        for n, x in nl.m['netnames'].items():
            for b in x['bits']:
                if isinstance(b, int):
                    self.all_names[b].append(n)

    def name(self, b):
        return self.nl.names.get(b, str(b))

    def cone(self, b):
        """Gate nets in the combinational backward cone of b (b included when it is a gate net)."""
        if b in self._cone:
            return self._cone[b]
        seen = set()
        st = [b]
        while st:
            x = st.pop()
            if not isinstance(x, int) or x in seen or x not in self.nl.drivers:
                continue
            seen.add(x)
            st.extend(self.nl.fanins(x))
        self._cone[b] = frozenset(seen)
        return self._cone[b]

    def input_dependent(self, b):
        if b in self._dep:
            return self._dep[b]
        order = []
        st = [b]
        while st:
            x = st[-1]
            if x in self._dep or not isinstance(x, int):
                st.pop(); continue
            if x in self.in_bits:
                self._dep[x] = True; st.pop(); continue
            if x not in self.nl.drivers:
                self._dep[x] = False; st.pop(); continue
            pend = [f for f in self.nl.fanins(x) if isinstance(f, int) and f not in self._dep]
            if pend:
                st.extend(pend); continue
            self._dep[x] = any(self._dep.get(f, False) for f in self.nl.fanins(x) if isinstance(f, int))
            st.pop()
        return self._dep.get(b, False)

    def dep_cone(self, b):
        if isinstance(b, (list, tuple)):
            return frozenset().union(*[self.dep_cone(x) for x in b]) if b else frozenset()
        return frozenset(x for x in self.cone(b) if self.input_dependent(x))

    def cone_many(self, bs):
        return frozenset().union(*[self.cone(x) for x in bs]) if bs else frozenset()

    def forward(self, b):
        """Gate nets in the combinational forward cone of b (b included)."""
        seen = set()
        st = [b]
        while st:
            x = st.pop()
            if x in seen:
                continue
            seen.add(x)
            st.extend(self.fanout.get(x, ()))
        return seen

    def chash(self, b):
        """Canonical structural hash of net b (16 hex chars)."""
        if b in self._hash:
            return self._hash[b]
        st = [b]
        while st:
            x = st[-1]
            if x in self._hash:
                st.pop(); continue
            if not isinstance(x, int):
                self._hash[x] = 'k' + str(x); st.pop(); continue
            if x in self.in_bits:
                p, i = self.in_bits[x]
                self._hash[x] = f'in:{p}[{i}]'; st.pop(); continue
            if x not in self.nl.drivers:
                self._hash[x] = 'ff:' + self.name(x); st.pop(); continue
            _, ty, con = self.nl.drivers[x]
            pins = [con[p][0] for p in ('S', 'A', 'B') if p in con] if ty == '$_MUX_' else [v[0] for p, v in con.items() if p != 'Y']
            pend = [f for f in pins if f not in self._hash]
            if pend:
                st.extend(pend); continue
            ch = [self._hash[f] for f in pins]
            if ty in ('$_AND_', '$_OR_', '$_XOR_'):
                ch = sorted(ch)
            self._hash[x] = hashlib.sha1(repr((ty, ch)).encode()).hexdigest()[:16]
            st.pop()
        return self._hash[b]


def named_copies(S, copy_re=DEFAULT_COPY_RE):
    """{label: set of gate nets whose name carries the copy prefix}."""
    rx = re.compile(copy_re)
    groups = collections.defaultdict(set)
    for b, names in S.all_names.items():
        if b in S.in_bits or b not in S.nl.drivers:
            continue
        for n in names:
            mm = rx.search(n)
            if mm:
                groups[mm.group(1)].add(b)
    return dict(sorted(groups.items()))


def structural_groups(S):
    """Union-find of decision bits whose input-dependent cones overlap. Returns list of lists of bit indices
    (bits with no input-dependent logic are left out)."""
    bits = [(i, S.dep_cone(d)) for i, d in S.decision]
    bits = [(i, c) for i, c in bits if c]
    parent = {i: i for i, _ in bits}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    owner = {}
    for i, c in bits:
        for n in c:
            if n in owner:
                parent[find(i)] = find(owner[n])
            else:
                owner[n] = i
    g = collections.defaultdict(list)
    for i, _ in bits:
        g[find(i)].append(i)
    return sorted((sorted(v) for v in g.values()), key=lambda v: v[0])


def copy_membership(nl, goal_out='boot_word', copy_re=DEFAULT_COPY_RE, groups=None):
    """net id -> label: 'c0' ... (inside that copy's cone), 'c0:path' ... (input-dependent net downstream of that copy
    only), 'shared' (inside two or more copy cones), 'merge' (combines copies); other nets are absent. Used by
    attack_surface for the per-copy share. Returns (mapping, source) with source 'names', 'structural' or 'none'."""
    r = lint(nl, goal_out=goal_out, copy_re=copy_re, groups=groups, _want_membership=True)
    return r['_membership'], r['mode'] if r['copies'] else 'none'


def lint(nl, goal_out='boot_word', copy_re=DEFAULT_COPY_RE, groups=None, mode='auto', netlist_path=None,
         expected_copies=None, _want_membership=False):
    t0 = time.time()
    S = Structure(nl, goal_out)
    named = named_copies(S, copy_re) if mode in ('auto', 'names') else {}
    findings = []
    if mode == 'names' and not named:
        findings.append('no hierarchy names matched the copy pattern; falling back to structural mode')
    sgroups = structural_groups(S)
    copies = {}   # label -> cone (set of gate nets)
    named_nets = {}
    if named and mode != 'structural' and groups is None:
        used = 'names'
        for lab, nets in named.items():
            cone = set()
            for b in nets:
                cone |= S.cone(b)
            copies[lab] = {x for x in cone if S.input_dependent(x)}
            named_nets[lab] = sorted(S.name(b) for b in nets)
    else:
        used = 'structural'
        if groups is not None:
            for gi, g in enumerate(groups):
                cone = set()
                dec = dict(S.decision)
                for i in g:
                    if i in dec:
                        cone |= S.dep_cone(dec[i])
                copies[f'g{gi}'] = cone
        else:
            dec = dict(S.decision)
            for gi, g in enumerate(sgroups):
                cone = set()
                for i in g:
                    cone |= S.dep_cone(dec[i])
                copies[f'g{gi}'] = cone
    labels = list(copies)
    net_copies = collections.defaultdict(set)
    for lab, cone in copies.items():
        for n in cone:
            net_copies[n].add(lab)
    shared = sorted((n for n, cs in net_copies.items() if len(cs) > 1), key=lambda n: S.name(n))
    # decision bits and their owners
    dec_rows = []
    reach_bits = collections.defaultdict(set)   # net -> decision bits whose cone contains it
    for i, d in S.decision:
        cone = S.cone_many(d)
        for n in cone:
            reach_bits[n].add(i)
        owners = sorted({c for n in cone for c in net_copies.get(n, ())})
        dec_rows.append(dict(bit=i, net=', '.join(S.name(x) for x in d), owners=owners))
    # merge points: input-dependent nets outside all copy cones whose cone holds nets of >= 2 copies
    merge = {}
    for n in nl.drivers:
        if n in net_copies or not S.input_dependent(n):
            continue
        cs = {c for x in S.cone(n) for c in net_copies.get(x, ())}
        if len(cs) > 1:
            merge[n] = cs
    first = {n for n in merge if not any(f in merge for f in nl.fanins(n) if isinstance(f, int))}
    singles = []
    for n in shared:
        if reach_bits.get(n):
            singles.append(dict(net=S.name(n), net_id=n, kind='shared', copies=sorted(net_copies[n]),
                                decision_bits_reached=sorted(reach_bits[n])))
    for n in sorted(merge, key=lambda n: (n not in first, S.name(n))):
        if reach_bits.get(n):
            singles.append(dict(net=S.name(n), net_id=n, kind='merge', first=n in first, copies=sorted(merge[n]),
                                decision_bits_reached=sorted(reach_bits[n])))
    # hashing
    copy_info = {}
    for lab, cone in copies.items():
        outs = sorted(n for n in cone if not (S.fanout.get(n, set()) & cone) or n in S.goal_bits)
        h = hashlib.sha1(repr(sorted(S.chash(n) for n in outs)).encode()).hexdigest()[:16] if outs else None
        bits = sorted(r['bit'] for r in dec_rows if lab in r['owners'])
        copy_info[lab] = dict(named_nets=named_nets.get(lab, []), cone_size=len(cone), hash=h, decision_bits=bits)
    byhash = collections.defaultdict(list)
    for lab, ci in copy_info.items():
        if ci['hash']:
            byhash[ci['hash']].append(lab)
    identical = [v for v in byhash.values() if len(v) > 1]
    hgroups = collections.defaultdict(set)
    for n in nl.drivers:
        hgroups[S.chash(n)].add(n)
    dup = sum(1 for v in hgroups.values() if len(v) > 1)
    # verdict
    if not copies:
        verdict = 'no_copies'
    elif used == 'structural' and groups is None:
        if expected_copies and len(copies) < expected_copies:
            verdict = 'merged' if len(copies) == 1 else 'partially_shared'
        else:
            verdict = 'single_group' if len(copies) == 1 else 'separate'
    else:
        cover = max((len(s['copies']) for s in singles), default=0)
        verdict = 'merged' if cover == len(labels) and cover > 1 else 'partially_shared' if cover > 1 else 'separate'
    # human-readable findings
    if used == 'names':
        findings.append('copy groups from hierarchy names: ' + ', '.join('%s (%d input-dependent nets)' % (l, copy_info[l]['cone_size']) for l in labels))
    elif groups is not None:
        findings.append(f'copy groups from the given decision-bit ownership: {groups}')
    else:
        findings.append(f'no copy names: decision bits grouped by overlapping input-dependent logic -> {len(sgroups)} independent group(s): {sgroups}')
    if shared:
        findings.append(f'{len(shared)} net(s) lie inside two or more copy cones (merged copy logic), e.g. ' +
                        ', '.join(f'`{S.name(n)}` ({"+".join(sorted(net_copies[n]))})' for n in shared[:5]))
    fm = [n for n in merge if n in first and reach_bits.get(n)]
    if fm:
        findings.append(f'{len(fm)} first merge point(s) combine copies before the decision bits: ' +
                        ', '.join(f'`{S.name(n)}` ({"+".join(sorted(merge[n]))})' for n in sorted(fm, key=S.name)[:5]) +
                        f' ({len([n for n in merge if reach_bits.get(n)])} merge nets in total)')
    if used == 'structural' and groups is None and len(sgroups) == 1 and len(S.decision) > 1:
        allbits = {i for i, d in S.decision if S.dep_cone(d)}
        common = [n for n in nl.drivers if S.input_dependent(n) and allbits and allbits <= reach_bits.get(n, set())]
        findings.append(f'every decision bit depends on shared input-dependent logic; {len(common)} net(s) reach all of them, e.g. ' +
                        ', '.join(f'`{S.name(n)}`' for n in sorted(common, key=S.name)[:5]) +
                        ('' if expected_copies else ' (either the design has one copy, or its copies were merged; '
                         'pass --copies N to say how many were intended)'))
    if not shared and not fm and verdict == 'separate':
        findings.append('no net is shared by two copies and no net combines copies before the decision bits')
    for grp in identical:
        findings.append(f"copies {', '.join(grp)} are structurally identical (same canonical hash): a structural-hashing pass "
                        "(e.g. opt_merge) can fold them unless the flow keeps them apart")
    if len([b for b in S.goal_bits if isinstance(b, int)]) == 1:
        findings.append(f'goal output `{goal_out}` is one bit wide: a fault on that bit or on its decoding logic does not need '
                        'any copy, and this lint does not look at it (the bounded search does)')
    own = [r for r in dec_rows if len(r['owners']) > 1]
    if own and used == 'names':
        findings.append(f"{len(own)} decision bit(s) depend on more than one copy: bits {[r['bit'] for r in own]}")
    res = dict(schema='glitchsat-merge-lint/1', netlist=netlist_path, netlist_sha256=_sha256(netlist_path) if netlist_path else None,
               top=nl.top, goal_out=goal_out, mode=used, verdict=verdict, copies=copy_info, decision_bits=dec_rows,
               shared_nets=[dict(net=S.name(n), net_id=n, copies=sorted(net_copies[n])) for n in shared],
               merge_points=[dict(net=S.name(n), net_id=n, copies=sorted(merge[n]), first=n in first) for n in sorted(merge, key=S.name)],
               single_points=singles, identical_copies=identical, duplicate_hash_groups=dup,
               structural_groups=sgroups, findings=findings, runtime_s=round(time.time() - t0, 4),
               note='Structural lint only (no solver, no simulation). A single point is a place where one modelled fault can '
                    'act on several copies; whether it is enough to reach the goal is decided by the bounded search.')
    if _want_membership:
        mem = {}
        for n, cs in net_copies.items():
            mem[n] = next(iter(cs)) if len(cs) == 1 else 'shared'
        for n in merge:
            mem.setdefault(n, 'merge')
        for n in nl.drivers:   # private path of one copy towards the decision bits (downstream of that copy only)
            if n not in mem and S.input_dependent(n):
                cs = {c for x in S.cone(n) for c in net_copies.get(x, ())}
                if len(cs) == 1:
                    mem[n] = next(iter(cs)) + ':path'
        res['_membership'] = mem
    return res


def format_text(r):
    out = [f"{r['top']}: verdict {r['verdict'].upper()}  (mode {r['mode']}, goal {r['goal_out']}, {r['runtime_s']} s)"]
    out += ['  - ' + f for f in r['findings']]
    if r['single_points']:
        out.append('  single points (one fault site acting on several copies):')
        for s in r['single_points'][:12]:
            out.append(f"    {s['kind']:6s} `{s['net']}` copies {'+'.join(s['copies'])} reaches decision bits {s['decision_bits_reached']}")
        if len(r['single_points']) > 12:
            out.append(f"    ... {len(r['single_points']) - 12} more")
    out.append('  ' + r['note'])
    return '\n'.join(out)


def parse_groups(s):
    if not s:
        return None
    return [[int(x) for x in g.split(',') if x.strip()] for g in s.split(';') if g.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description='Redundancy-merge lint: do the redundant copies of a check still use separate logic? '
                                             'Structural only, no solver.')
    ap.add_argument('netlist', help='Yosys JSON netlist')
    ap.add_argument('--top', required=True)
    ap.add_argument('--goal-out', default='boot_word')
    ap.add_argument('--mode', choices=['auto', 'names', 'structural'], default='auto')
    ap.add_argument('--groups', help='intended decision-bit ownership, e.g. "0,3,6;1,4,7;2,5" (structural mode)')
    ap.add_argument('--copies', type=int, help='number of copies the design intends (structural mode verdict)')
    ap.add_argument('--copy-regex', default=DEFAULT_COPY_RE, help='regex with one group capturing the copy label')
    ap.add_argument('--json', metavar='FILE', help='write the JSON result to FILE ("-" for stdout)')
    a = ap.parse_args(argv)
    nl = load(a.netlist, a.top)
    r = lint(nl, a.goal_out, a.copy_regex, parse_groups(a.groups), a.mode, netlist_path=a.netlist, expected_copies=a.copies)
    if a.json == '-':
        print(json.dumps(r, indent=2))
    else:
        print(format_text(r))
        if a.json:
            with open(a.json, 'w') as f:
                json.dump(r, f, indent=2)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except BrokenPipeError:   # output piped into head etc.
        sys.exit(0)
