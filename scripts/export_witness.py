#!/usr/bin/env python3
"""Export the data behind docs/explainers/theatre.html (Solver Replay Theatre).

What it does, in order (nothing is typed in by hand; every value below comes from a tool run):
  1. runs the project solver CLI  `scripts/glitchsat.py check`  on the STORED netlists reference/spike_netlists/v1.json
     and v2.json (6 ticks; V1 k=0,1; V2 k=0,1,2,3; V2 with goal boot_ok==1, k=1) and keeps the printed verdict text;
  2. replays each ATTACK_FOUND witness with the project's own replay recipe (scripts/replay.py, the code behind
     `make replay`): the gate-level netlist is re-emitted as Verilog with an XOR on each witness net at its cycle,
     simulated with iverilog/vvp twice (faults on / faults off), dumping VCD;
  3. replays the honest key (0xC3, no faults) with the same bench. replay.py only accepts ATTACK_FOUND-shaped files, so
     the honest-key STIMULUS file is built here (empty fault list, sig = key). It is a stimulus, not a solver result;
  4. parses the VCD files into per-signal change lists and per-tick samples;
  5. writes docs/explainers/witness.json and inlines the same JSON into docs/explainers/theatre.html (between the data markers).

All solver and simulator work files go to a temporary directory. Nothing under results/ or tb/ is written.
Faults are MODELLED single-tick bit flips in a gate-level simulation of a toy design. No hardware is involved.

Usage: python3 scripts/export_witness.py [--out docs/explainers/witness.json] [--page docs/explainers/theatre.html] [--no-embed]
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import glitchsat as g          # noqa: E402  (netlist reader; used for structural facts about the witness nets)
import replay as rp            # noqa: E402  (the project's replay recipe)

CYCLES = 6; KEY = 0xC3
NETLISTS = {'v1': 'reference/spike_netlists/v1.json', 'v2': 'reference/spike_netlists/v2.json'}
DATA_OPEN = '<script type="application/json" id="witness-data">'; DATA_CLOSE = '</script>'
TB_SIGNALS = ('clk', 'sig', 'boot_ok', 'boot_word')


def sha256(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def parse_vcd(path, want):
    """Minimal VCD reader. want = set of dotted names such as 'tb.clk' or 'tb.dut.n42'.
    Returns ({name: {'width': w, 'changes': [[time, int_or_None], ...]}}, end_time). None = x/z."""
    scope, ids, out = [], {}, {}
    t = 0; end = 0; in_defs = True
    with open(path) as f:
        for line in f:
            s = line.strip()
            if not s: continue
            if in_defs:
                tok = s.split()
                if tok[0] == '$scope': scope.append(tok[2])
                elif tok[0] == '$upscope': scope.pop()
                elif tok[0] == '$var':
                    name = '.'.join(scope + [tok[4]])
                    if name in want:
                        ids.setdefault(tok[3], []).append(name); out[name] = dict(width=int(tok[2]), changes=[])
                elif tok[0] == '$enddefinitions': in_defs = False
                continue
            if s[0] == '#': t = int(s[1:]); end = max(end, t); continue
            if s[0] == '$': continue
            if s[0] in 'bB':
                val, ident = s[1:].split()
            elif s[0] in '01xXzZ':
                val, ident = s[0], s[1:]
            else:
                continue
            for name in ids.get(ident, ()):
                v = None if any(c in 'xXzZ' for c in val) else int(val, 2)
                ch = out[name]['changes']
                if ch and ch[-1][0] == t: ch[-1][1] = v
                elif not ch or ch[-1][1] != v: ch.append([t, v])
    return out, end


def value_at(changes, t):
    v = None
    for ct, cv in changes:
        if ct <= t: v = cv
        else: break
    return v


def sample_times(n):
    """The generated bench samples tick 0 at t=1 and tick c>=1 at t=10*c (rising clock edges are at t=5,15,25,...)."""
    return [1] + [10 * c for c in range(1, n)]


def run_solver(tmp, design, k, goal_out='boot_word', goal_value=0x96):
    """Run the solver CLI exactly as a person would; return (command string, stdout text, result dict)."""
    out = os.path.join(tmp, f'{design}_{goal_out}_k{k}.json')
    args = ['scripts/glitchsat.py', 'check', NETLISTS[design], '--top', design, '--k', str(k), '--cycles', str(CYCLES)]
    if goal_out != 'boot_word': args += ['--goal-out', goal_out, '--goal-value', str(goal_value)]
    p = subprocess.run([sys.executable] + args + ['--out', out], cwd=ROOT, capture_output=True, text=True, timeout=600)
    if p.returncode != 0: raise SystemExit(f'solver failed ({p.returncode}): {p.stderr[-800:]}')
    return 'python3 ' + ' '.join(args), p.stdout.strip(), json.load(open(out)), out


def solver_block(cmd, text, r):
    lines = text.splitlines()
    b = dict(command=cmd, verdict=r['verdict'], verdict_text=lines[0].split('  solve=')[0].strip(), bound_note=r['note'],
             max_faults=r['bound']['max_faults'], cycles=r['bound']['cycles'], goal=r['bound']['goal'],
             fault_model=r['bound']['fault_model'], attacker_input_rule=r['bound']['attacker_input'],
             min_faults=r.get('min_faults'), honest_key_boots_fault_free=r['honest_key_boots_fault_free'],
             sites_total=r['model']['sites_total'], sites_modelled=r['model']['sites_modelled'], reduce=r['model']['reduce'],
             gates=r['netlist']['gates'], flops=r['netlist']['flops'])
    if 'faults' in r:
        b['faults'] = [dict(net=f['net'], net_id=f['net_id'], cycle=f['cycle'], kind=f['kind']) for f in r['faults']]
        b['attacker_input'] = r['attacker_input']; b['attacker_input_raw'] = r['attacker_input_raw']
        b['explanation'] = r['explanation']['summary']
    return b


def structural(nl, faults):
    """Structural facts (read from the netlist, not from the simulation) used to place each fault on the simplified diagram:
    which boot_word state bits the net can reach through logic into the next state."""
    word = nl.ports['boot_word']['bits']
    for f in faults:
        reach = g.forward_reach(nl, f['net_id'], word, 1)
        f['reaches_word_bits'] = sorted(word.index(b) for b in reach)
        f['is_output_net'] = [p for p, v in nl.ports.items() if v['direction'] == 'output' and f['net_id'] in v['bits']]
        f['gate'] = nl.drivers[f['net_id']][1].strip('$_') if f['net_id'] in nl.drivers else 'DFF'


def do_replay(tmp, result_path, tag, fault_ids, which=('faulted', 'faultfree')):
    """Run scripts/replay.py on a result file; parse both VCDs. Returns {run: {...signals...}} and the replay summary."""
    outdir = os.path.join(tmp, 'tb')
    res = rp.replay(result_path, outdir, tag)
    want = {f'tb.{s}' for s in TB_SIGNALS} | {f'tb.dut.{p}{i}' for i in fault_ids for p in 'nr'}
    runs = {}
    for run in which:
        vcd = os.path.join(outdir, f'{tag}_{run}.vcd')
        sig, end = parse_vcd(vcd, want)
        missing = want - set(sig)
        if missing: raise SystemExit(f'VCD {vcd} lacks {sorted(missing)}')
        signals = {}
        for name, d in sig.items():
            short = name.split('.')[-1]
            signals[short] = dict(width=d['width'], changes=d['changes'],
                                  per_tick=[value_at(d['changes'], t) for t in sample_times(CYCLES)])
        runs[run] = dict(vcd_basename=os.path.basename(vcd), t_end=end, run_faults=int(run == 'faulted'),
                         goal_hit_cycle=res[run]['goal_hit_cycle'],
                         bench_line=next(l for l in res[run]['raw'].splitlines() if l.startswith('REPLAY')), signals=signals)
    return runs, res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', default=os.path.join(ROOT, 'docs', 'explainers', 'witness.json'))
    ap.add_argument('--page', default=os.path.join(ROOT, 'docs', 'explainers', 'theatre.html'))
    ap.add_argument('--no-embed', action='store_true'); ap.add_argument('--keep', action='store_true', help='keep the temp dir')
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix='p21_witness_')
    nls = {d: g.Netlist(os.path.join(ROOT, p), d) for d, p in NETLISTS.items()}
    shas = {d: sha256(os.path.join(ROOT, p)) for d, p in NETLISTS.items()}
    creators = {d: json.load(open(os.path.join(ROOT, p))).get('creator', '') for d, p in NETLISTS.items()}
    frames = []

    def frame(fid, step, side, title, design, **kw):
        f = dict(id=fid, step=step, side=side, title=title, design=design, source_file=NETLISTS[design],
                 netlist_sha256=shas[design], label='MEASURED (solver output) + SIMULATED (gate-level replay)')
        f.update(kw); frames.append(f); return f

    replay_cmd = ('python3 scripts/replay.py <solver result JSON> --outdir <tmp>   '
                  '(iverilog -g2012 + vvp; called from scripts/export_witness.py)')
    sol = {}
    for design, k, goal in (('v1', 0, 'boot_word'), ('v1', 1, 'boot_word'), ('v2', 0, 'boot_word'), ('v2', 1, 'boot_word'),
                            ('v2', 2, 'boot_word'), ('v2', 3, 'boot_word'), ('v2', 1, 'boot_ok')):
        gv = 1 if goal == 'boot_ok' else 0x96
        sol[(design, k, goal)] = run_solver(tmp, design, k, goal, gv)
        print(sol[(design, k, goal)][1].splitlines()[0], flush=True)

    # ---- step 1: fault-free runs (honest key opens, wrong key stays shut)
    for design, kw in (('v1', 1), ('v2', 3)):
        cmd0, text0, r0, _ = sol[(design, 0, 'boot_word')]
        _, _, rw, pathw = sol[(design, kw, 'boot_word')]
        wrong = rw['attacker_input_raw']['sig']
        stim = dict(verdict='ATTACK_FOUND', netlist_json=NETLISTS[design], top=design, bound=rw['bound'], faults=[],
                    attacker_input_raw=dict(sig=KEY), _note='STIMULUS file built by export_witness.py: honest key, no faults; not a solver result')
        sp = os.path.join(tmp, f'{design}_honest_stimulus.json'); json.dump(stim, open(sp, 'w'))
        h_runs, _ = do_replay(tmp, sp, f'{design}_honest', [], which=('faultfree',))
        w_runs, _ = do_replay(tmp, pathw, f'{design}_wrongkey', [], which=('faultfree',))
        frame(f'{design}_faultfree', 1, 'left' if design == 'v1' else 'right',
              'Fault-free run: honest key opens, wrong key stays shut', design, kind='replay', solver=solver_block(cmd0, text0, r0),
              replay=dict(command=replay_cmd,
                          runs=dict(honest=dict(h_runs['faultfree'], sig=KEY, stimulus='honest key 0xC3, no faults (stimulus built by export_witness.py)'),
                                    wrong=dict(w_runs['faultfree'], sig=wrong, stimulus=f'wrong key 0x{wrong:02X} (the solver\'s attacker input), no faults')),
                          honest_opens=h_runs['faultfree']['goal_hit_cycle'] >= 0, wrong_stays_shut=w_runs['faultfree']['goal_hit_cycle'] < 0))

    # ---- steps 2, 3, 4: witnesses and bounded "none found" results
    def witness_frame(fid, step, side, title, key):
        cmd, text, r, path = sol[key]
        sb = solver_block(cmd, text, r); structural(nls[key[0]], sb['faults'])
        runs, res = do_replay(tmp, path, fid, [f['net_id'] for f in sb['faults']])
        for run in runs.values(): run['sig'] = r['attacker_input_raw']['sig']
        frame(fid, step, side, title, key[0], kind='replay', solver=sb,
              replay=dict(command=replay_cmd, runs=runs, agrees_with_solver=res['agrees_with_solver'],
                          goal_port=r['bound']['goal'].split()[0], goal_value=int(re.search(r'== 0x([0-9A-Fa-f]+)', r['bound']['goal']).group(1), 16)))

    def bound_frame(fid, step, side, title, key):
        cmd, text, r, _ = sol[key]
        frame(fid, step, side, title, key[0], kind='solver_only', solver=solver_block(cmd, text, r),
              label='MEASURED (solver output)')

    witness_frame('v1_k1', 2, 'left', "The solver's witness for V1: one flip", ('v1', 1, 'boot_word'))
    bound_frame('v2_k1', 3, 'right', 'V2 with at most 1 flip', ('v2', 1, 'boot_word'))
    bound_frame('v2_k2', 3, 'right', 'V2 with at most 2 flips', ('v2', 2, 'boot_word'))
    witness_frame('v2_k3', 3, 'right', "The solver's witness for V2: three flips", ('v2', 3, 'boot_word'))
    witness_frame('v2_flag_k1', 4, 'right', 'Caveat: the accept flag of V2 falls to one flip', ('v2', 1, 'boot_ok'))

    iv = subprocess.run(['iverilog', '-V'], capture_output=True, text=True).stdout.splitlines()[0]
    import z3
    doc = dict(
        meta=dict(label='MEASURED solver output and SIMULATED gate-level replays of modelled bit flips on a toy design. No hardware.',
                  what='replay of the solver\'s witness in a gate-level simulation',
                  generated_by='python3 scripts/export_witness.py', cycles=CYCLES, key=KEY, accept_word=0x96,
                  state_codes={'0xF0': 'idle', '0xCC': 'checking', '0x96': 'open', '0x69': 'shut'},
                  state_codes_source='rtl/v1.v line 8 comment (IDLE F0, CMP CC, BOOT 96, FAIL 69)',
                  sampling='tick 0 is sampled at t=1, tick c>=1 at t=10*c; rising clock edges at t=5,15,25,... (scripts/replay.py bench)',
                  fault_signals='r<id> = the net as the gate drives it; n<id> = the net after the modelled flip (XOR during the fault tick)',
                  tools=dict(solver='scripts/glitchsat.py (z3 %s)' % z3.get_version_string(), simulator=iv, netlist_creator=creators),
                  netlists={d: dict(file=NETLISTS[d], sha256=shas[d], gates=nls[d].stats()['gates'], flops=nls[d].stats()['flops']) for d in NETLISTS}),
        frames=frames)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, 'w') as f:
        json.dump(doc, f, indent=1, sort_keys=True); f.write('\n')
    print('wrote', os.path.relpath(a.out, ROOT), os.path.getsize(a.out), 'bytes')
    if not a.no_embed and os.path.isfile(a.page):
        html = open(a.page, encoding='utf-8').read()
        i = html.find(DATA_OPEN); j = html.find(DATA_CLOSE, i)
        if i < 0 or j < 0: raise SystemExit(f'{a.page}: data markers not found')
        blob = json.dumps(doc, sort_keys=True, separators=(',', ':')).replace('<', '\\u003c')
        open(a.page, 'w', encoding='utf-8').write(html[:i + len(DATA_OPEN)] + blob + html[j:])
        print('inlined the same data into', os.path.relpath(a.page, ROOT))
    if a.keep: print('temp dir kept:', tmp)
    else: shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
