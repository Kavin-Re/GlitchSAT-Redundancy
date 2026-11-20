#!/usr/bin/env python3
"""Line-based one-at-a-time mutation harness. Works ONLY on copies under /tmp/work_mt.
usage: mutate.py run [--only ID,..] ; results -> /tmp/work_mt/results.json
Each mutant: (id, scope, old, new[, nth]) ; scope E = shared engine text (applied to scripts/glitchsat.py -> suite 'root' AND
product/src/faultbound_wt/_engine.py -> suite 'product'); G = glitchsat.py only; Pk = product file named k (engine/runner/cli/config)."""
import os, sys, json, shutil, subprocess, time, concurrent.futures as cf
LITE = '/tmp/work_mt/lite'; WORK = '/tmp/work_mt/m'; PY = '/tmp/work_mt/venv/bin/python'
GS = 'scripts/glitchsat.py'; PE = 'product/src/faultbound_wt/_engine.py'
PF = {'runner': 'product/src/faultbound_wt/runner.py', 'cli': 'product/src/faultbound_wt/cli.py', 'config': 'product/src/faultbound_wt/config.py', 'engine': PE}
M = [
# id, scope, old, new
('flip_or',      'E', "v = Xor(v, F[(t, b)])", "v = Or(v, F[(t, b)])"),
('flip_and',     'E', "v = Xor(v, F[(t, b)])", "v = And(v, F[(t, b)])"),
('no_flop_sites','E', "allsites = list(nl.qs) + list(nl.drivers.keys())", "allsites = list(nl.drivers.keys())"),
('no_gate_sites','E', "allsites = list(nl.qs) + list(nl.drivers.keys())", "allsites = list(nl.qs)"),
('k_plus1',      'E', "s.add(PbLe([(f, 1) for f in allf], k))", "s.add(PbLe([(f, 1) for f in allf], k + 1))"),
('k_minus1',     'E', "s.add(PbLe([(f, 1) for f in allf], k))", "s.add(PbLe([(f, 1) for f in allf], k - 1))"),
('drop_atmost',  'E', "if allf: s.add(PbLe([(f, 1) for f in allf], k))", "if False: s.add(PbLe([(f, 1) for f in allf], k))"),
('min_off',      'E', "while minimize and best:", "while False and best:"),
('min_bound2',   'E', "s.add(PbLe([(f, 1) for f in allf], len(best) - 1))", "s.add(PbLe([(f, 1) for f in allf], len(best) - 2))"),
('min_nopop_brk','E', "s.pop(); break", "break"),
('temporal_off1','E', "t + dist[b] <= N - 1", "t + dist[b] <= N"),
('temporal_off2','E', "t + dist[b] <= N - 1", "t + dist[b] <= N - 2"),
('coi_nolast',   'E', "usable = lambda t, b: b in dist\n", "usable = lambda t, b: b in dist and t > 0\n"),
('hits_or',      'E', "hits.append(And(*[w[i] == BoolVal", "hits.append(Or(*[w[i] == BoolVal"),
('goal_shift',   'E', "bool((goal_value >> i) & 1)", "bool((goal_value >> (i + 1)) & 1)"),
('goal_invert',  'E', "w[i] == BoolVal(", "w[i] != BoolVal("),
('last_cycle_only','E', "s.add(Or(*hits))", "s.add(hits[-1])"),
('first_cycle_only','E', "s.add(Or(*hits))", "s.add(hits[0])"),
('key_eq',       'E', "if bad_only: s.add(ain != key)", "if bad_only: s.add(ain == key)"),
('skip_badonly', 'E', "if bad_only: s.add(ain != key)", "if False: s.add(ain != key)"),
('fixed_in_neg', 'E', "s.add(ain == fixed_in)", "s.add(ain != fixed_in)"),
('honest_invert','E', "return v == 'ATTACK_FOUND'", "return v != 'ATTACK_FOUND'"),
('honest_nofix', 'E', "v, info, res = solve(nl, N, 0, minimize=False, bad_only=False, fixed_in=key, **kw)", "v, info, res = solve(nl, N, 0, minimize=False, bad_only=False, **kw)"),
('honest_badonly','E', "v, info, res = solve(nl, N, 0, minimize=False, bad_only=False, fixed_in=key, **kw)", "v, info, res = solve(nl, N, 0, minimize=False, bad_only=True, fixed_in=key, **kw)"),
('and_to_or',    'E', "if ty == '$_AND_': v = And(g('A'), g('B'))", "if ty == '$_AND_': v = Or(g('A'), g('B'))"),
('or_to_and',    'E', "elif ty == '$_OR_': v = Or(g('A'), g('B'))", "elif ty == '$_OR_': v = And(g('A'), g('B'))"),
('xor_to_and',   'E', "elif ty == '$_XOR_': v = Xor(g('A'), g('B'))", "elif ty == '$_XOR_': v = And(g('A'), g('B'))"),
('xor_to_or',    'E', "elif ty == '$_XOR_': v = Xor(g('A'), g('B'))", "elif ty == '$_XOR_': v = Or(g('A'), g('B'))"),
('not_dropped',  'E', "elif ty == '$_NOT_': v = Not(g('A'))", "elif ty == '$_NOT_': v = g('A')"),
('mux_swap',     'E', "else: v = If(g('S'), g('B'), g('A'))", "else: v = If(g('S'), g('A'), g('B'))"),
('mux_sel_inv',  'E', "else: v = If(g('S'), g('B'), g('A'))", "else: v = If(Not(g('S')), g('B'), g('A'))"),
('init_all_zero','E', "state = {q: BoolVal(nl.init[q]) for q in nl.qs}", "state = {q: BoolVal(False) for q in nl.qs}"),
('init_default1','E', "self.init.setdefault(q, False)", "self.init.setdefault(q, True)"),
('init_bit_inv', 'E', "self.init[x['bits'][i]] = (b == '1')", "self.init[x['bits'][i]] = (b == '0')"),
('state_hold',   'E', "state = nxt", "state = state"),
('cycles_minus1','E', "for t in range(N):\n        val = {}", "for t in range(N - 1):\n        val = {}"),
('simp_off',     'E', "if simp: v = simplify(v)", "if False: v = simplify(v)"),
('simp_always',  'E', "simp = reduce != 'none'", "simp = True"),
('dist_noinc',   'E', "nxt = [(self.dq[b], dist[b] + 1)]", "nxt = [(self.dq[b], dist[b])]"),
('dist_goal_none','E', "dist[b] = 0; dq.append(b)", "dist[b] = 1; dq.append(b)"),
('fanin_incl_y', 'E', "return [v[0] for p, v in con.items() if p != 'Y']", "return [v[0] for p, v in con.items()]"),
('multidrv_off', 'E', "if net in self.driver_cell:", "if False:"),
('inport_drv_off','E', "if net in in_bits:", "if False:"),
('loop_off',     'E', "if color.get(f) == 1:", "if color.get(f) == 99:"),
('xinit_off',    'E', "if b not in '01':", "if b not in '01x':"),
('dupkey_off',   'E', "if k in d:", "if False:"),
('undriven_off', 'E', "if b not in nl.drivers:", "if False:"),
('xconst_off',   'E', "if b == 'x' or b == 'z':", "if b == 'q':"),
('unk_is_true',  'E', "return 'UNKNOWN_TIMEOUT', info, None", "return 'NO_ATTACK_UP_TO_BOUND', info, None"),
('timeout_off',  'E', "if timeout_ms: s.set('timeout', timeout_ms)", "if False: s.set('timeout', timeout_ms)"),
('extract_inv',  'E', "return [kk for kk, f in F.items() if is_true(mod.eval(f, model_completion=True))]", "return [kk for kk, f in F.items() if not is_true(mod.eval(f, model_completion=True))]"),
('goal_widthchk','E', "if goal_out not in ports or ports[goal_out].get('direction') != 'output':", "if goal_out not in ports:"),
('attin_dirchk', 'E', "if attack_in not in ports or ports[attack_in].get('direction') != 'input':", "if attack_in not in ports:"),
('clk_free',     'E', "if v['direction'] == 'input' and p != 'clk'}", "if v['direction'] == 'input'}"),
('expl_k1',      'E', "ncyc = len({t for t, _ in faults})", "ncyc = len(faults)"),
('expl_nin',     'E', "n_in = len(sup & in_bits)", "n_in = len(sup)"),
('reach_lt',     'E', "if c2 <= maxcyc and (y, c2) not in seen", "if c2 < maxcyc and (y, c2) not in seen"),
('sup_flop',     'E', "memo[x] = frozenset([('flop', x)])", "memo[x] = frozenset([x])"),
('kind_label',   'E', "kind = 'flip-flop Q' if b in nl.dq else 'gate output'", "kind = 'flip-flop Q' if b not in nl.dq else 'gate output'"),
('dffs_sub',     'E', "if t == '$_DFF_P_':", "if t == '$_DFF_P_' and False:"),
# glitchsat CLI / run_check only
('cli_k_neg',    'G', "if k < 0: raise", "if k < -5: raise"),
('cli_k_le0',    'G', "if k < 0: raise", "if k <= 0: raise"),
('cli_N_zero',   'G', "if N < 1: raise", "if N < 0: raise"),
('cli_gv_width', 'G', "if goal_value >> len(nl.ports[goal_out]['bits']):", "if goal_value >> (len(nl.ports[goal_out]['bits']) + 1):"),
('cli_key_width','G', "if key >> len(nl.ports[attack_in]['bits']):", "if False:"),
('cli_exit_unk', 'G', "sys.exit(0 if r['verdict'] in ('NO_ATTACK_UP_TO_BOUND', 'ATTACK_FOUND') else 2)", "sys.exit(0)"),
('cli_nofaults_min','G', "out_d['min_faults'] = len(faults)", "out_d['min_faults'] = len(faults) + 1"),
('cli_honest_flag','G', "honest_key_boots_fault_free=honest_boots(nl, N, **kw)", "honest_key_boots_fault_free=True"),
('cli_safe_off', 'G', "def _safe(s):\n", "def _safe(s):\n    return s\n"),
# product only: site filter, runner, cli, config
('pf_filter_none','P:engine', "(site_filter is None or site_filter(b, 'flop' if b in nl.dq else 'gate'))", "True"),
('pf_filter_kind','P:engine', "site_filter(b, 'flop' if b in nl.dq else 'gate')", "site_filter(b, 'gate' if b in nl.dq else 'flop')"),
('pf_unsup_gate','P:engine', "if t not in SUPPORTED:", "if False:"),
('pr_kind_inv',  'P:runner', "if kind not in kinds:", "if kind in kinds:"),
('pr_incl_any',  'P:runner', "if th.include and not any(", "if th.include and not all("),
('pr_excl_off',  'P:runner', "if any(fnmatch.fnmatchcase(n, g) for n in names for g in th.exclude):", "if False:"),
('pr_honest_chk','P:runner', "if not honest and th.honest_check:", "if not honest and False:"),
('pr_honest_inv','P:runner', "if not honest and th.honest_check:", "if honest and th.honest_check:"),
('pr_lv_width',  'P:runner', "if th.legitimate_value >= 1 << len(a[\"bits\"]):", "if th.legitimate_value > 1 << len(a[\"bits\"]):"),
('pr_bv_width',  'P:runner', "if th.bad_value >= 1 << len(o[\"bits\"]):", "if False:"),
('pr_kindlabel', 'P:runner', "kind=\"flop_Q\" if b in nl.dq else \"gate_output\"", "kind=\"gate_output\" if b in nl.dq else \"flop_Q\""),
('pr_minfaults', 'P:runner', "rep[\"min_faults\"] = len(res[\"faults\"])", "rep[\"min_faults\"] = th.max_flips"),
('pr_reduce_none','P:runner', 'reduce="full", site_filter', 'reduce="none", site_filter'),
('pr_outwrongkey','P:runner', "goal_value=th.bad_value, attack_in", "goal_value=th.bad_value ^ 1, attack_in"),
('pr_dir_in',    'P:runner', "if not a or a[\"direction\"] != \"input\":", "if not a:"),
('pc_exit_attack','P:cli', "\"ATTACK_FOUND\": EXIT_ATTACK}", "\"ATTACK_FOUND\": EXIT_OK}"),
('pc_exit_unknown','P:cli', ".get(rep[\"verdict\"], EXIT_UNKNOWN)", ".get(rep[\"verdict\"], EXIT_OK)"),
('pc_internal',  'P:cli', "return EXIT_INTERNAL", "return EXIT_ATTACK"),
('pc_exitzero',  'P:cli', "if args.exit_zero:\n        return EXIT_OK", "if args.exit_zero:\n        return EXIT_ATTACK"),
('pc_cfgprob_exit','P:cli', "            print(line)\n        return EXIT_ERROR", "            print(line)\n        return EXIT_OK"),
('pc_override_k','P:cli', "th.max_flips = args.max_flips", "th.max_flips = args.max_flips + 1"),
('pc_nohonest',  'P:cli', "th.honest_check = False", "th.honest_check = True"),
('pcfg_neg',     'P:config', "or v < 0:", "or v < -1:"),
('pcfg_cycles',  'P:config', "if t.cycles < 1:", "if t.cycles < 0:"),
('pcfg_bool',    'P:config', "isinstance(v, bool) or ", ""),
('pcfg_kinds',   'P:config', "if bad or not t.kinds:", "if bad:"),
('pcfg_model',   'P:config', "if t.attacker_model != \"constant\":", "if False:"),
('pcfg_defaulted','P:config', "t.defaulted = [f\"{a}.{b}\" for a, b in _KEYS if b not in raw.get(a, {})]", "t.defaulted = []"),
('pcfg_unkkey',  'P:config', "if k not in _ALLOWED[sec]:", "if False:"),
]

def targets(scope):
    if scope == 'E': return [('root', GS), ('product', PE)]
    if scope == 'G': return [('root', GS)]
    return [('product', PF[scope.split(':')[1]])]

def apply(path, old, new):
    s = open(path).read()
    n = s.count(old)
    if n != 1: return None, n
    i = s.index(old); line = s.count('\n', 0, i) + 1
    open(path, 'w').write(s.replace(old, new)); return line, 1

def run_one(mid, scope, old, new, suite):
    tgt = dict(targets(scope))[suite] if suite in dict(targets(scope)) else None
    d = f'{WORK}/{mid}__{suite}'
    shutil.rmtree(d, ignore_errors=True); shutil.copytree(LITE, d)
    line, n = apply(os.path.join(d, tgt), old, new)
    if line is None: return dict(id=mid, suite=suite, file=tgt, status='NOT_APPLIED', matches=n)
    if suite == 'root':
        cmd = ['timeout', '120', PY, '-m', 'pytest', '-q', '-x', '-p', 'no:cacheprovider', 'tests']; cwd = d; env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    else:
        cmd = ['timeout', '120', PY, '-m', 'pytest', '-q', '-x', '-p', 'no:cacheprovider', 'tests']; cwd = d + '/product'
        env = dict(os.environ, PYTHONPATH=d + '/product/src', PYTHONDONTWRITEBYTECODE='1')
    t0 = time.time()
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    out = p.stdout[-1500:]
    st = {0: 'SURVIVED', 1: 'KILLED', 124: 'TIMEOUT'}.get(p.returncode, f'ERROR_rc{p.returncode}')
    failed = [l for l in p.stdout.splitlines() if l.startswith('FAILED')]
    shutil.rmtree(d, ignore_errors=True)
    return dict(id=mid, suite=suite, file=tgt, line=line, status=st, secs=round(time.time() - t0, 1), failed=failed[:2], tail=out[-300:] if st.startswith('ERROR') else '')

def main():
    only = None
    if '--only' in sys.argv: only = set(sys.argv[sys.argv.index('--only') + 1].split(','))
    jobs = [(m[0], m[1], m[2], m[3], s) for m in M if not only or m[0] in only for s, _ in targets(m[1])]
    os.makedirs(WORK, exist_ok=True)
    res = []
    with cf.ThreadPoolExecutor(4) as ex:
        futs = [ex.submit(run_one, *j) for j in jobs]
        for f in cf.as_completed(futs):
            r = f.result(); res.append(r); print(r['id'], r['suite'], r['status'], r.get('secs'), flush=True)
    json.dump(res, open('/tmp/work_mt/results%s.json' % ('_' + '_'.join(sorted(only))[:20] if only else ''), 'w'), indent=1)
if __name__ == '__main__': main()
