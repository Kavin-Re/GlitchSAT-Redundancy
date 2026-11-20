#!/usr/bin/env python3
"""Random-flip (binary symmetric channel) TEACHING model of the toy boot designs.
NOT an attacker model and NOT a physical error rate; modelled bit flips on a toy design; no silicon claim.

Model: every fault site (gate output or flop Q) flips independently with probability p in every cycle t < T.
False accept: boot_word == 0x96 at some cycle t < T while the input `sig` is held at ONE fixed wrong key.
Flip semantics are those of research/c5/anchor/anchor_sim.py (stem flip: seen by all fanout and the output port).

  enum : exact count A_d of flip sets of size d <= K that give a false accept, per wrong key (numpy, lanes = flip sets)
  mc   : bit-parallel Monte Carlo (numpy uint64 lanes = trials), fixed trial counts, Clopper-Pearson 95% intervals
  plot : log-log figure
usage: bsc_channel.py enum|mc|plot|all [--out DIR] [--procs N] [--cap TRIALS] [--hits H]
"""
import argparse, csv, hashlib, json, math, os, re, sys, time, itertools, multiprocessing as mp
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KEY, GOAL, T = 0xC3, 0x96, 4
DESIGNS = [  # name, netlist (relative to ROOT), top, K (largest enumerated set size)
    ('V0', 'reference/spike_netlists/v0.json', 'v0', 3),
    ('V1', 'reference/spike_netlists/v1.json', 'v1', 3),
    ('V2-stored', 'reference/spike_netlists/v2.json', 'v2', 3),
    ('V2-apt', 'research/c4/b3_inputs/nl/v2_apt033.json', 'v2', 3),
    ('V2e', 'research/c6/p01/netlists/nl_apt_v2e.json', 'v2e', 3),
]
PGRID = [10 ** (-3 + i / 4) for i in range(9)]
ONE = np.uint64(0xFFFFFFFFFFFFFFFF)
CAPTION = 'random-flip teaching model; not an attacker model and not a physical error rate'


class Net:
    def __init__(self, path, top):
        m = json.load(open(path))['modules'][top]
        self.sigbits = m['ports']['sig']['bits']; self.word = m['ports']['boot_word']['bits']
        self.gates = {}; self.flops = []
        for c in m['cells'].values():
            cn = c['connections']
            if c['type'] == '$_DFF_P_': self.flops.append((cn['D'][0], cn['Q'][0]))
            else: self.gates[cn['Y'][0]] = (c['type'], {p: v[0] for p, v in cn.items() if p != 'Y'})
        init = {}
        for x in m['netnames'].values():
            iv = x['attributes'].get('init')
            if iv:
                for i, ch in enumerate(reversed(iv)): init[x['bits'][i]] = ch == '1'
        self.init = {q: bool(init.get(q)) for _, q in self.flops}
        seen = set(self.init) | set(self.sigbits); order = []
        def vis(b):
            if not isinstance(b, int) or b in seen: return
            seen.add(b)
            for s in self.gates[b][1].values(): vis(s)
            order.append(b)
        for d, _ in self.flops: vis(d)
        for b in self.word: vis(b)
        self.order = order
        self.sites = list(self.gates) + [q for _, q in self.flops]   # same site list as anchor_sim stem_flip
        self.sidx = {b: i for i, b in enumerate(self.sites)}
        self.n = len(self.sites)

    def run(self, sig, flips, W):
        """flips[t][site_index] -> uint64 array (W words) or None. Returns uint64 hit mask (accept at some t < T)."""
        zero = np.zeros(W, np.uint64); ones = np.full(W, ONE)
        const = {b: (ones if (sig >> i) & 1 else zero) for i, b in enumerate(self.sigbits)}
        st = {q: (ones if v else zero) for q, v in self.init.items()}
        hit = zero.copy()
        for t in range(T):
            f = flips[t]; v = dict(const)
            def fl(b, r):
                x = f[self.sidx[b]]
                return r if x is None else r ^ x
            for q, val in st.items(): v[q] = fl(q, val)
            def get(b):
                if b == '1': return ones
                if isinstance(b, str): return zero
                return v[b]
            for b in self.order:
                ty, d = self.gates[b]
                if ty == '$_AND_': r = get(d['A']) & get(d['B'])
                elif ty == '$_OR_': r = get(d['A']) | get(d['B'])
                elif ty == '$_XOR_': r = get(d['A']) ^ get(d['B'])
                elif ty == '$_NOT_': r = ~get(d['A'])
                elif ty == '$_MUX_': s = get(d['S']); r = (get(d['B']) & s) | (get(d['A']) & ~s)
                else: raise Exception('cell ' + ty)
                v[b] = fl(b, r)
            m = ones
            for i, b in enumerate(self.word): m = m & (get(b) if (GOAL >> i) & 1 else ~get(b))
            hit |= m
            st = {q: get(d) for d, q in self.flops}
        return hit


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()

def popcount(a):
    return int(np.unpackbits(a.view(np.uint8)).sum())

# ---------------------------------------------------------------- exact enumerator
def combos_chunks(N, d, chunk=1 << 20):
    it = itertools.combinations(range(N), d)
    while True:
        a = np.fromiter(itertools.chain.from_iterable(itertools.islice(it, chunk)), dtype=np.int32)
        if a.size == 0: return
        yield a.reshape(-1, d)

def enum_design(name, path, top, K):
    net = Net(os.path.join(ROOT, path), top); N = net.n * T
    keys = [s for s in range(256) if s != KEY]
    per_key = {s: [0] * (K + 1) for s in keys}; anykey = [0] * (K + 1); t0 = time.time()
    # d = 0: fault-free run
    for s in keys:
        per_key[s][0] = popcount(net.run(s, [[None] * net.n] * T, 1) & np.uint64(1))
    anykey[0] = int(any(per_key[s][0] for s in keys))
    for d in range(1, K + 1):
        for cb in combos_chunks(N, d):
            C = len(cb); W = (C + 63) // 64
            B = np.zeros((N, W * 64), dtype=bool)
            for c in range(d): B[cb[:, c], np.arange(C)] = True
            P = np.packbits(B, axis=1, bitorder='little').view(np.uint64); del B
            used = set(np.unique(cb).tolist())
            flips = [[(P[t * net.n + i] if (t * net.n + i) in used else None) for i in range(net.n)] for t in range(T)]
            u = np.zeros(W, np.uint64)
            for s in keys:
                h = net.run(s, flips, W); per_key[s][d] += popcount(h); u |= h
            anykey[d] += popcount(u)
    dmin = next((d for d in range(K + 1) if anykey[d]), None)
    best = max(keys, key=lambda s: (per_key[s][dmin], -s))
    return dict(design=name, netlist=path, netlist_sha256=sha(os.path.join(ROOT, path)), top=top, T=T, K=K, n_sites=net.n, N=N,
                goal='boot_word == 0x%02X at some cycle t < %d, sig fixed at one wrong key' % (GOAL, T),
                A_anykey=anykey, min_flips=dmin, key='0x%02X' % best, A_key=per_key[best],
                A_mean_over_wrong_keys=[sum(per_key[s][d] for s in keys) / 255 for d in range(K + 1)],
                keys_reaching_min=sum(1 for s in keys if per_key[s][dmin]),
                A_per_key={'0x%02X' % s: per_key[s] for s in keys}, secs=round(time.time() - t0, 1))

def series(A, N, p):
    return sum(a * p ** d * (1 - p) ** (N - d) for d, a in enumerate(A))

# ---------------------------------------------------------------- Monte Carlo
def bernoulli_words(rng, nbits, p):
    """nbits iid Bernoulli(p) bits as uint64 words (exact: geometric gaps between ones)."""
    out = np.zeros((nbits + 63) // 64, np.uint64); pos = -1; parts = []
    while True:
        g = rng.geometric(p, size=int(nbits * p * 1.05) + 1024).astype(np.int64)
        c = pos + np.cumsum(g)
        if c[-1] >= nbits:
            parts.append(c[:np.searchsorted(c, nbits)]); break
        parts.append(c); pos = int(c[-1])
    c = np.concatenate(parts)
    if c.size:
        w = c >> 6; bit = np.left_shift(np.uint64(1), (c & 63).astype(np.uint64))
        st = np.flatnonzero(np.r_[True, w[1:] != w[:-1]])
        out[w[st]] = np.bitwise_or.reduceat(bit, st)
    return out

_G = {}
def _mc_init(path, top):
    _G['net'] = Net(path, top)

def _mc_batch(a):
    seed, sig, p, B = a
    net = _G['net']; rng = np.random.default_rng(seed); W = B // 64; N = net.n * T
    F = bernoulli_words(rng, N * B, p).reshape(N, W)
    flips = [[F[t * net.n + i] for i in range(net.n)] for t in range(T)]
    return popcount(net.run(sig, flips, W))

def betacf(a, b, x):
    tiny = 1e-300; qab = a + b; qap = a + 1; qam = a - 1; c = 1.0; d = 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny); h = d
    for m in range(1, 200000):
        m2 = 2 * m; aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > tiny else tiny); c = 1 + aa / c; c = c if abs(c) > tiny else tiny; h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > tiny else tiny); c = 1 + aa / c; c = c if abs(c) > tiny else tiny
        de = d * c; h *= de
        if abs(de - 1) < 1e-13: break
    return h

def betainc(a, b, x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    lb = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    if x < (a + 1) / (a + b + 2): return math.exp(lb) * betacf(a, b, x) / a
    return 1 - math.exp(lb) * betacf(b, a, 1 - x) / b

def clopper_pearson(k, n, alpha=0.05):
    def inv(a, b, q):
        lo, hi = 0.0, 1.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if betainc(a, b, mid) < q: lo = mid
            else: hi = mid
            if hi - lo < 1e-15 * max(hi, 1e-300): break
        return (lo + hi) / 2
    lo = 0.0 if k == 0 else inv(k, n - k + 1, alpha / 2)
    hi = 1.0 if k == n else inv(k + 1, n - k, 1 - alpha / 2)
    return lo, hi

def mc_all(enums, out_csv, procs, cap, target, B=1 << 20, log=sys.stderr):
    rows = []
    for di, e in enumerate(enums):
        path = os.path.join(ROOT, e['netlist']); sig = int(e['key'], 16); dmin = e['min_flips']; A = e['A_key']
        with mp.Pool(procs, initializer=_mc_init, initargs=(path, e['top'])) as pool:
            for pi, p in enumerate(PGRID):
                lead = A[dmin] * p ** dmin
                # trial count fixed BEFORE the run from the leading term (not from observed hits)
                nb = min(max(math.ceil(target / min(1.0, lead) / B), 4), cap // B)
                ss = np.random.SeedSequence([20261120, di, pi]).spawn(nb); t0 = time.time()
                hits = sum(pool.imap_unordered(_mc_batch, [(s, sig, p, B) for s in ss], chunksize=4))
                n = nb * B; lo, hi = clopper_pearson(hits, n)
                r = dict(design=e['design'], netlist_sha256=e['netlist_sha256'], T=T, p='%.6g' % p, hits=hits, trials=n,
                         estimate='%.6g' % (hits / n), ci_lo='%.6g' % lo, ci_hi='%.6g' % hi,
                         exact_series='%.6g' % series(A, e['N'], p), min_flips=dmin, A_dmin=A[dmin],
                         key=e['key'], n_site_cycles=e['N'], K=e['K'], leading_term='%.6g' % lead,
                         A_dmin_anykey=e['A_anykey'][dmin], plotted=int(hits >= 20), label='SIMULATED')
                rows.append(r)
                print('%s p=%s hits=%d trials=%d est=%s series=%s lead=%s %.0fs' % (e['design'], r['p'], hits, n, r['estimate'],
                      r['exact_series'], r['leading_term'], time.time() - t0), file=log, flush=True)
    with open(out_csv, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n'); w.writeheader(); w.writerows(rows)
    return rows

# ---------------------------------------------------------------- slope and plot
def low_p_slope(rows, design, pmax=3.2e-3):
    pts = [(math.log10(float(r['p'])), math.log10(float(r['estimate']))) for r in rows
           if r['design'] == design and float(r['p']) <= pmax and int(r['hits']) >= 20]
    if len(pts) < 2: return None
    mx = sum(x for x, _ in pts) / len(pts); my = sum(y for _, y in pts) / len(pts)
    return sum((x - mx) * (y - my) for x, y in pts) / sum((x - mx) ** 2 for x, _ in pts)

def plot(csv_path, png):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    rows = list(csv.DictReader(open(csv_path)))
    col = {'V0': '#2a78d6', 'V1': '#eb6834', 'V2-apt': '#1baf7a', 'V2-stored': '#eda100', 'V2e': '#e87ba4'}
    mk = {'V0': 'o', 'V1': 's', 'V2-apt': '^', 'V2-stored': 'D', 'V2e': 'v'}
    ink, ink2, surf = '#0b0b0b', '#52514e', '#fcfcfb'
    fig, ax = plt.subplots(figsize=(9.2, 6.6), dpi=150); fig.patch.set_facecolor(surf); ax.set_facecolor(surf)
    ps = np.logspace(-3, -1, 50)
    for name in col:
        rs = [r for r in rows if r['design'] == name and int(r['hits']) >= 20]
        if not rs: continue
        r0 = rs[0]; d = int(r0['min_flips']); A = int(r0['A_dmin'])
        x = np.array([float(r['p']) for r in rs]); y = np.array([float(r['estimate']) for r in rs])
        lo = np.array([float(r['ci_lo']) for r in rs]); hi = np.array([float(r['ci_hi']) for r in rs])
        ax.plot(ps, np.minimum(A * ps ** d, 1), color=col[name], lw=1, ls=(0, (4, 3)), alpha=0.8)
        ax.errorbar(x, y, yerr=[y - lo, hi - y], color=col[name], marker=mk[name], ms=6, lw=2, capsize=2, mec=surf, mew=0.8,
                    label='%s  (slope guide %d, A = %d, key %s)' % (name, d, A, r0['key']))
        ax.annotate(name, (x[0], y[0]), xytext=(-8, 0), textcoords='offset points', ha='right', va='center', color=ink, fontsize=9)
    ax.set_xscale('log'); ax.set_yscale('log'); ax.set_xlim(5.5e-4, 1.3e-1)
    ax.set_xlabel('p = flip probability per fault site per cycle', color=ink2)
    ax.set_ylabel('P(false accept within T = 4 cycles)', color=ink2)
    ax.set_title('Random flips: slope = fewest flips needed, height = how many ways', color=ink, fontsize=12, loc='left')
    ax.grid(True, which='major', color='#e4e3df', lw=0.6); ax.tick_params(colors=ink2)
    for s in ax.spines.values(): s.set_color('#c9c8c2')
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.legend(frameon=False, fontsize=8.5, loc='lower right', labelcolor=ink,
              title='markers: Monte Carlo, 95% interval; dashed: A x p^d guide', title_fontsize=8.5)
    fig.text(0.01, 0.012, CAPTION + '. SIMULATED, toy design, modelled bit flips; points with fewer than 20 hits omitted.',
             fontsize=8, color=ink2)
    fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(png, facecolor=surf); plt.close(fig)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('cmd', choices=['enum', 'mc', 'plot', 'all'])
    ap.add_argument('--out', default=os.path.join(ROOT, 'research', 'c6', 'p12')); ap.add_argument('--procs', type=int, default=4)
    ap.add_argument('--cap', type=int, default=4 * 10 ** 9); ap.add_argument('--hits', type=int, default=200)
    ap.add_argument('--csv', default=os.path.join(ROOT, 'results', 'comms', 'waterfall.csv'))
    ap.add_argument('--png', default=os.path.join(ROOT, 'docs', 'comms', 'waterfall.png'))
    a = ap.parse_args(); ej = os.path.join(a.out, 'enum.json')
    if a.cmd in ('enum', 'all'):
        with mp.Pool(min(a.procs, len(DESIGNS))) as pool: enums = pool.starmap(enum_design, DESIGNS)
        json.dump(enums, open(ej, 'w'), indent=0)
        for e in enums: print(e['design'], 'n', e['n_sites'], 'N', e['N'], 'any', e['A_anykey'], 'key', e['key'], e['A_key'],
                              'keys@min', e['keys_reaching_min'], 'mean', ['%.3g' % x for x in e['A_mean_over_wrong_keys']], e['secs'])
    if a.cmd in ('mc', 'all'):
        mc_all(json.load(open(ej)), a.csv, a.procs, a.cap, a.hits)
    if a.cmd in ('plot', 'all'):
        plot(a.csv, a.png)

if __name__ == '__main__':
    main()
