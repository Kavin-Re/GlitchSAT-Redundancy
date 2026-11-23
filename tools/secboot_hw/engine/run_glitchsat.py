"""Cloud-side runner: synthesise every variant with the repository flows, replay the model vectors on each netlist,
then run scripts/glitchsat.py at k = 1..KMAX. Needs Yosys on PATH and z3-solver; it is called by cloud/cloud_run.sh.

Per variant and flow it records: gate and flop counts of the netlist, the model's register bits in the goal cone
(a lower number of flops means synthesis merged or removed registers: flagged, not hidden), the gate-level replay
result, and per k the solver verdict, minimum flips, the flips themselves, and the run time. A timeout or error is
recorded as such and never as "no attack".

When an attack with m flips is found at budget k, the result for every larger budget is the same minimum m (the
solver minimises), so larger budgets are recorded as 'implied' unless --all-k is given.

Usage: python3 -m engine.run_glitchsat --root GLITCHSAT_ROOT --out OUT [--flows plain,opt] [--kmax 3]
                                       [--timeout 1800] [--workers N] [--large] [--all-k] [--only a,b]
"""
import argparse, concurrent.futures as cf, json, os, subprocess, sys, time
from engine import netsim
from engine.wrappers import reg_paths
from model.variants import VARIANTS, BY_NAME

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def synth(root, design, top, out_json, flow):
    t0 = time.time()
    r = subprocess.run(['sh', os.path.join(root, 'scripts', 'synth.sh'), design, top, out_json, flow],
                       capture_output=True, text=True)
    return r.returncode, r.stderr[-3000:], round(time.time() - t0, 2)


def solve(root, v, netlist, k, out_json, timeout_s):
    cmd = [sys.executable, os.path.join(root, 'scripts', 'glitchsat.py'), 'check', netlist, '--top', v.top,
           '--k', str(k), '--cycles', str(v.cycles), '--goal-out', v.goal_port, '--goal-value', hex(v.goal_value),
           '--attack-input', 'sig', '--key', hex(v.key), '--timeout-ms', str(int(timeout_s * 1000)), '--out', out_json]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s + 600)
        rc, err = r.returncode, r.stderr[-2000:]
    except subprocess.TimeoutExpired:
        rc, err = 'outer-timeout', ''
    wall = round(time.time() - t0, 2)
    row = dict(k=k, exit=rc, wall_s=wall, command=' '.join(cmd))
    if rc == 0 and os.path.isfile(out_json):
        d = json.load(open(out_json))
        row.update(verdict=d['verdict'], min_faults=d.get('min_faults'), faults=d.get('faults'),
                   attacker_input=d.get('attacker_input'), honest_key_boots=d.get('honest_key_boots_fault_free'),
                   solve_s=d['runtime_s']['solve_and_minimize'], netlist=d.get('netlist'),
                   summary=(d.get('explanation') or {}).get('summary'))
    else:
        row.update(verdict='UNKNOWN' if rc in (2, 'outer-timeout') else 'ERROR', stderr=err)
    return row


def one_variant(args, name):
    v = BY_NAME[name]
    out = os.path.join(args.out, name)
    os.makedirs(out, exist_ok=True)
    design = os.path.join(HERE, 'build', 'rtl', f'{name}.v')
    rec = dict(name=name, family=v.family, top=v.top, goal_out=v.goal_port, goal_value=hex(v.goal_value),
               key=hex(v.key), cycles=v.cycles, countermeasures=list(v.cms),
               model_register_bits_in_goal_cone=v.flop_bits(), flows={})
    regs = [p[len('dut.'):] for _, _, _, p in reg_paths(v.cfg)]
    for flow in args.flows:
        fr = dict()
        nl = os.path.join(out, f'{name}_{flow}.json')
        rc, err, secs = synth(args.root, design, v.top, nl, flow)
        fr['synth'] = dict(exit=rc, seconds=secs, stderr=err if rc else '')
        if rc:
            rec['flows'][flow] = fr
            continue
        try:
            rp = netsim.replay(nl, v.top, os.path.join(HERE, 'vectors', f'{name}.vec'), v.goal_port, regs)
            fr['gates'], fr['flops'] = rp['gates'], rp['flops']
            fr['replay'] = dict(scenarios=rp['scenarios'], fault_scenarios_skipped=rp['fault_scenarios_skipped'],
                                mismatches=rp['mismatches'][:5], ok=not rp['mismatches'])
        except netsim.NetsimError as e:
            fr['replay'] = dict(ok=False, error=str(e))
        fr['flops_vs_model'] = ('equal' if fr.get('flops') == v.flop_bits() else
                                f"CHECK: netlist has {fr.get('flops')} flops, model has {v.flop_bits()} register bits in the goal cone")
        fr['k'] = []
        found = None
        for k in range(1, args.kmax + 1):
            if found is not None and not args.all_k:
                fr['k'].append(dict(k=k, verdict='ATTACK_FOUND', min_faults=found, implied=True,
                                    note=f'implied by the minimal {found}-flip attack found at a smaller budget'))
                continue
            row = solve(args.root, v, nl, k, os.path.join(out, f'{name}_{flow}_k{k}.json'), args.timeout)
            fr['k'].append(row)
            if row['verdict'] == 'ATTACK_FOUND':
                found = row['min_faults']
            if row['verdict'] in ('UNKNOWN', 'ERROR'):
                for k2 in range(k + 1, args.kmax + 1):
                    fr['k'].append(dict(k=k2, verdict='NOT_RUN', note=f'budget {k} gave {row["verdict"]}'))
                break
        rec['flows'][flow] = fr
    with open(os.path.join(out, 'record.json'), 'w') as fh:
        json.dump(rec, fh, indent=1)
    return rec


def summary_md(recs, flows, kmax):
    lines = ['# Secure-boot hardware: GlitchSAT results (MEASURED by this run)', '',
             'Bounded results: "no attack" holds only for at most k modelled single-cycle bit flips within the stated '
             'number of cycles, on this netlist. Not a proof for more flips, longer runs or other fault types.', '']
    head = '| variant | flow | gates | flops (model bits) | replay | ' + ' | '.join(f'k={k}' for k in range(1, kmax + 1)) + ' |'
    lines += [head, '|' + '---|' * (5 + kmax)]
    for r in recs:
        if r.get('error'):
            lines.append(f"| {r['name']} | - | runner error: {r['error'][:60]} | | | " + ' | '.join('' for _ in range(kmax)) + ' |')
            continue
        for f in flows:
            fr = r['flows'].get(f)
            if not fr:
                continue
            if fr['synth']['exit']:
                lines.append(f"| {r['name']} | {f} | synth failed | | | " + ' | '.join('' for _ in range(kmax)) + ' |')
                continue
            cells = []
            for row in fr['k']:
                vtxt = row['verdict']
                if vtxt == 'ATTACK_FOUND':
                    cells.append(f"attack, min {row['min_faults']}" + (' (implied)' if row.get('implied') else f" ({row.get('solve_s')} s)"))
                elif vtxt == 'NO_ATTACK_UP_TO_BOUND':
                    cells.append(f"no attack ({row.get('solve_s')} s)")
                else:
                    cells.append(vtxt.lower().replace('_', ' '))
            cells += [''] * (kmax - len(cells))
            rep = fr.get('replay', {})
            rtxt = 'ok' if rep.get('ok') else 'MISMATCH' if 'mismatches' in rep else rep.get('error', '?')[:30]
            lines.append(f"| {r['name']} | {f} | {fr.get('gates')} | {fr.get('flops')} ({r['model_register_bits_in_goal_cone']}) | "
                         f"{rtxt} | " + ' | '.join(cells) + ' |')
    return '\n'.join(lines) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=os.environ.get('GLITCHSAT_ROOT'))
    ap.add_argument('--out', required=True)
    ap.add_argument('--flows', default='plain,opt')
    ap.add_argument('--kmax', type=int, default=3)
    ap.add_argument('--timeout', type=float, default=1800, help='solver seconds per run (z3 --timeout-ms)')
    ap.add_argument('--workers', type=int, default=os.cpu_count() or 1)
    ap.add_argument('--large', action='store_true', help='also the full-round hash variants (slow)')
    ap.add_argument('--all-k', action='store_true', help='solve every budget even after an attack was found')
    ap.add_argument('--only', default='', help='comma-separated variant names')
    a = ap.parse_args()
    if not a.root or not os.path.isfile(os.path.join(a.root, 'scripts', 'glitchsat.py')):
        sys.exit('run_glitchsat: set --root or GLITCHSAT_ROOT to the repository root')
    a.flows = [f for f in a.flows.split(',') if f]
    os.makedirs(a.out, exist_ok=True)
    names = [x for x in a.only.split(',') if x] or [v.name for v in VARIANTS if a.large or not v.large]
    recs = {}
    with cf.ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(one_variant, a, n): n for n in names}
        for f in cf.as_completed(futs):
            n = futs[f]
            try:
                recs[n] = f.result()
            except Exception as e:     # recorded, never silently dropped
                recs[n] = dict(name=n, error=f'{type(e).__name__}: {e}', flows={}, model_register_bits_in_goal_cone=None)
            print(f'[{len(recs)}/{len(names)}] {n} done', flush=True)
    ordered = [recs[n] for n in names]
    with open(os.path.join(a.out, 'summary.json'), 'w') as fh:
        json.dump(dict(schema='secboot-hw-results/1', label='MEASURED', kmax=a.kmax, timeout_s=a.timeout,
                       flows=a.flows, variants=ordered), fh, indent=1)
    with open(os.path.join(a.out, 'summary.md'), 'w') as fh:
        fh.write(summary_md(ordered, a.flows, a.kmax))
    from engine import studio
    with open(os.path.join(a.out, 'studio_secboot_hw.json'), 'w') as fh:
        json.dump(studio.panel(ordered), fh, indent=1)
    print(open(os.path.join(a.out, 'summary.md')).read())


if __name__ == '__main__':
    main()
