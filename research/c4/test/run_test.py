#!/usr/bin/env python3
"""Runs frozen predictor.py (imported, unmodified) on held-out cells. Writes cells.csv."""
import sys, os, csv, json, time, glob
from multiprocessing import Pool
sys.path.insert(0, '/home/user/project/research/c4/pre')
from predictor import predict
P = '/home/user/project/research/'
def job(a):
    cid, grp, path, top, kw, solver, extra = a
    t = time.time()
    try:
        r = predict(path, top, **kw); err = ''
    except Exception as e:
        r = None; err = repr(e)[:200]
    dt = time.time() - t
    return dict(group=grp, cell=cid, netlist=path, top=top, goal_out=kw.get('goal_out', 'boot_word'), mask=hex(kw.get('mask', 255)),
                T=kw.get('T', 6), solver_min=solver, lb=r and r['lb'], est=r and r['est'], pred=r and r['pred'], flag=r and r['flag'],
                ub_direct=r and r['ub_direct'], pred_s=round(dt, 3), error=err, **extra)
def build():
    jobs = []
    which = sys.argv[1]
    if which == 'e2':
        rows = list(csv.DictReader(open(P + 'c2/e2_variance/raw/matrix.csv')))
        seen = {}
        for r in rows:
            if r['status'] != 'SOLVED': continue
            tag = f"{r['build'].replace('conda-', 'conda-')}__{r['design']}__{r['flow']}__{r['order']}__{r['abc']}__{r['merge']}__{r['keep']}"
            key = (r['sha256_canon'], r['design'])
            seen.setdefault(key, []).append((tag, int(r['min_flips'])))
        for (canon, d), L in seen.items():
            mins = {m for _, m in L}
            assert len(mins) == 1, (canon, L)
            tag = L[0][0]
            path = f'/tmp/work_e2/nl/{tag}/r1.json'
            jobs.append((canon[:12] + '|' + d, 'E2', path, d, dict(mask=0xFF), L[0][1], dict(n_configs=len(L), example_cfg=tag)))
    elif which == 'r20':
        W = '/tmp/work_r20/work/'
        # (id, netlist, top, goal port, mask, accept, key, T, solver min, source out files)
        C = [('crc_plain_T4', 'crc_plain.json', 'bootcrc', 'ok', 1, 1, 0xA5, 4, 1, 'crc_plain_k1/k2'),
             ('crc_tmr_T4', 'crc_tmr.json', 'bootcrc_tmr', 'ok', 1, 1, 0xA5, 4, 1, 'crc_tmr_k1/k2,sc_crc_k0'),
             ('sbox_unprot_T4', 'sbox_unprot.json', 'sbox_unprot', 'y', 0xFF, 0x7C, 1, 4, 1, 'sbox_unprot_k1'),
             ('sbox_par_T4', 'sbox_par.json', 'sbox_par', 'gout', 0x1FF, 0x17C, 1, 4, 1, 'sbox_par_k1'),
             ('sbox_par2_T4', 'sbox_par2.json', 'sbox_par2', 'gout', 0x1FF, 0x17C, 1, 4, 1, 'sbox_par2_k1'),
             ('sbox_par2_T8', 'sbox_par2.json', 'sbox_par2', 'gout', 0x1FF, 0x17C, 1, 8, 1, 'sc_par2_k2_T8'),
             ('sbox_par2_T16', 'sbox_par2.json', 'sbox_par2', 'gout', 0x1FF, 0x17C, 1, 16, 1, 'sc_par2_k2_T16'),
             ('keymem_T8', 'keymem_a.json', 'keymemw', 'ready', 1, 1, 0, 8, 1, 'keymem_k1'),
             ('uart_T6', 'uart.json', 'uartw', 'gout', 7, 7, 0, 6, 1, 'uart_k1'),
             ('uart_T30', 'uart.json', 'uartw', 'gout', 7, 7, 0, 30, 1, 'sc_uart_k2_T30'),
             ('sbox_dmr_T4', '/tmp/work_test/sbox_dmr.json', 'sbox_dmr', 'gout', 0x1FF, 0x17C, 1, 4, 2, 'dmr_k1,dmr_k2')]
        for cid, nl, top, g, m, acc, key, T, s, src in C:
            jobs.append((cid, 'R20', nl if nl.startswith('/') else W + nl, top, dict(goal_out=g, mask=m, accept=acc, key=key, T=T), s, dict(n_configs=1, example_cfg=src)))
    elif which == 'm1':
        for d in ('v2', 'v1'):
            seenm = {}
            for l in open(P + f'c3/m1/m_{d}_apt033.jsonl'):
                j = json.loads(l)
                if j['status'] != 'MEASURED': continue
                jobs.append((f'{d}_apt033_m{j["mask"]:02x}', 'M1_' + d.upper() + '_apt033', P + f'c2/b1_faultmodels/netlists/{d}_apt033.json', d, dict(mask=j['mask']), j['min'], dict(n_configs=1, example_cfg='m_%s_apt033.jsonl' % d)))
    return jobs
if __name__ == '__main__':
    jobs = build()
    t0 = time.time()
    with Pool(int(os.environ.get('NP', 4))) as p: res = p.map(job, jobs, chunksize=1)
    out = f'/home/user/project/research/c4/test/cells_{sys.argv[1]}.csv'
    keys = list(res[0]); 
    w = csv.DictWriter(open(out, 'w', newline=''), fieldnames=keys); w.writeheader(); w.writerows(res)
    print(sys.argv[1], len(res), 'cells, wall', round(time.time() - t0, 1), 's, errors', sum(bool(r['error']) for r in res))
