#!/usr/bin/env python3
"""Hamming-distance analysis behind the FSM state codes in model/spec.py (SPEC.md section 3).

Rules checked (all by exhaustive enumeration, nothing sampled):
  R1  every code is a word of the [8,4,4] extended Hamming code spanned by FF, F0, CC, AA, with weight 4
      (so neither all-zero nor all-one, and any two codes differ in at least 4 bits);
  R2  ACCEPT and REJECT are bitwise complements (distance 8): every state bit takes part in the decision;
  R3  no other pair of codes is a complement pair;
  R4  for every compare mode, no partial decision (some compare copies say 'match', the others do not) lands
      on a valid code: a half-fooled decision is always an invalid state.
Reported, not a rule: with mubi flags a single flag-register bit moves 1 or 2 state bits, so flag-bit flips can
build any word; the number printed is the fewest state bits such flips must move to leave REJECT for another
valid code (it equals the code distance).
Also prints, for comparison, the minimum distance of a 3-bit binary and a 7-bit one-hot encoding.
Run: python3 tools/encoding_analysis.py   (exit 0 = all rules hold)"""
import itertools, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from model import spec as S


def hd(a, b):
    return bin(a ^ b).count('1')


def codewords():
    gens = (0xFF, 0xF0, 0xCC, 0xAA)
    out = set()
    for m in range(16):
        w = 0
        for i, g in enumerate(gens):
            if m >> i & 1:
                w ^= g
        out.add(w)
    return out


def analyse(states=None):
    st = dict(states or S.STATES)
    code = codewords()
    errs = []
    for n, v in st.items():
        if v not in code or bin(v).count('1') != 4:
            errs.append(f'R1: {n}=0x{v:02X} is not a weight-4 word of the [8,4,4] code')
    pairs = {(a, b): hd(st[a], st[b]) for a, b in itertools.combinations(st, 2)}
    dmin = min(pairs.values())
    if dmin < 4:
        errs.append(f'R1: minimum distance {dmin} < 4')
    if st['ACCEPT'] ^ st['REJECT'] != 0xFF:
        errs.append('R2: ACCEPT and REJECT are not complements')
    for (a, b), d in pairs.items():
        if d == 8 and {a, b} != {'ACCEPT', 'REJECT'}:
            errs.append(f'R3: {a} and {b} are complements')
    partial = []
    for mode in range(4):
        for mubi in (0,):
            cfg = S.Cfg(CMP_MODE=mode, FLAG_MUBI=mubi)
            groups = S.decision_groups(cfg)
            for m in range(1, (1 << len(groups)) - 1):
                w = st['REJECT']
                for gi, g in enumerate(groups):
                    if m >> gi & 1:
                        for i in g:
                            w = (w & ~(1 << i)) | (st['ACCEPT'] & (1 << i))
                partial.append((mode, mubi, w))
                if w in st.values():
                    errs.append(f'R4: CMP_MODE={mode} FLAG_MUBI={mubi}: partial decision gives valid code 0x{w:02X}')
    return dict(pairs=pairs, dmin=dmin, errors=errs, partial_words=sorted({w for _, _, w in partial}),
                min_bits_from_reject=min(hd(v, st['REJECT']) for n, v in st.items() if n != 'REJECT'))


def main():
    r = analyse()
    names = list(S.STATES)
    print('state codes:', ', '.join(f'{n}=0x{S.STATES[n]:02X}' for n in names))
    print('pairwise Hamming distance:')
    print('         ' + ' '.join(f'{n[:7]:>7}' for n in names))
    for a in names:
        print(f'{a:>8} ' + ' '.join(f'{hd(S.STATES[a], S.STATES[b]):>7}' for b in names))
    print(f'minimum distance {r["dmin"]}; partial decision words (all invalid codes): '
          + ' '.join(f'0x{w:02X}' for w in r['partial_words']))
    print(f'fewest state bits between REJECT and any other valid code: {r["min_bits_from_reject"]}')
    print('for comparison: 3-bit binary encoding of 7 states has minimum distance 1; 7-bit one-hot has 2')
    for e in r['errors']:
        print('FAIL', e)
    print('all rules hold' if not r['errors'] else f'{len(r["errors"])} rule violation(s)')
    return 1 if r['errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
