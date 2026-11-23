"""STAND-IN for scripts/glitchsat.py (plumbing tests only): answers run_check from the project's recorded files. No solver."""
import json, os, shutil, time, hashlib
__version__ = '0.9.0'
REAL = os.environ.get('GS_STANDIN_REAL') or open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '_standin_real')).read().strip()   # set by make_overlay
STANDIN_NL = {('v2', 'plain'): 'research/c6/p01/netlists/nl_apt_v2.json', ('v2e', 'plain'): 'research/c6/p01/netlists/nl_apt_v2e.json',
              ('v1', 'plain'): 'research/c2/e2_variance/baseline_netlists/apt0.33_v1.json', ('v0', 'plain'): 'research/c2/e2_variance/baseline_netlists/apt0.33_v0.json',
              ('v2', 'opt'): 'research/c2/e2_variance/baseline_netlists/conda-eda0.38_v2.json'}
class NetlistError(Exception): pass
def run_check(verilog, top, k, N, out=None, reduce='full', goal_out='boot_word', goal_value=0x96, attack_in='sig', key=0xC3, timeout_ms=0,
              workdir=None, label='MEASURED', flow='plain', amk=None):
    time.sleep(float(os.environ.get('STANDIN_SLEEP', '0')))
    if os.environ.get('STANDIN_FAIL') == 'synth' and not verilog.endswith('.json'):
        raise NetlistError("synthesis failed:\nERROR: Module `v2' referenced in module `top' is not part of the design.")
    stored = verilog.endswith('.json')
    if stored: jpath = verilog; fl = 'given-netlist'
    else:
        jpath = os.path.join(workdir, f'{top}.json' if flow == 'plain' else f'{top}_{flow}.json'); fl = flow
        src = STANDIN_NL.get((top, flow))
        if not src: raise NetlistError('stand-in has no netlist for this build')
        shutil.copy(os.path.join(REAL, src), jpath)
    m = json.load(open(jpath))['modules'][top]
    gates = sum(1 for c in m['cells'].values() if c['type'] != '$_DFF_P_' and c['type'] != '$scopeinfo'); flops = sum(1 for c in m['cells'].values() if c['type'] == '$_DFF_P_')
    names = {}
    for n, x in sorted(m['netnames'].items(), key=lambda kv: (kv[0].startswith('$'), kv[0])):
        for i, b in enumerate(x['bits']):
            if isinstance(b, int): names.setdefault(f'{n}[{i}]' if len(x['bits']) > 1 else n, b)
    # recorded minimum + witness for this setting
    rec = None
    if goal_out == 'boot_ok':
        rec = dict(min=1, faults=[('boot_ok', 3)], sig=0x43)
    elif stored:
        r = json.load(open(f'{REAL}/results/reproduce/{top}_spike_given-netlist_k3.json')); rec = dict(min=r['min_faults'], faults=[(f['net'], f['cycle']) for f in r['faults']], sig=r['attacker_input_raw']['sig'])
    elif (top, flow) == ('v2', 'opt'):
        rec = dict(min=3, faults=[('boot_word[6]', 1), ('$abc$275$new_n59', 4), ('boot_word[3]', 5)], sig=None)   # research/c6/p01/sweep_rows.csv, Yosys 0.38+92 plain row
    elif top == 'v2e':
        rec = dict(min=3, faults=[('$abc$275$new_n65_', 1), ('$abc$275$new_n72_', 2), ('$procmux$10.Y[2]', 2)], sig=3)
    else:
        r = json.load(open(f'{REAL}/results/reproduce/{top}_rtl_plain_k3.json')); rec = dict(min=r['min_faults'], faults=[(f['net'], f['cycle']) for f in r['faults']], sig=r['attacker_input_raw']['sig'])
    unknown = os.environ.get('STANDIN_UNKNOWN') == '1'
    atk = rec and k >= rec['min'] and not unknown and all(n in names for n, _ in rec['faults'])
    d = dict(label='STAND-IN (plumbing test)', tool='glitchsat.py', design=os.path.relpath(verilog, REAL) if verilog.startswith(REAL) else verilog,
             design_sha256_16=hashlib.sha256(open(verilog, 'rb').read()).hexdigest()[:16], top=top, synth_flow=fl,
             verdict='UNKNOWN_TIMEOUT' if unknown else 'ATTACK_FOUND' if atk else 'NO_ATTACK_UP_TO_BOUND',
             bound=dict(max_faults=k, cycles=N, fault_model='single-cycle bit flip of any gate output or flop Q', attacker_input='`sig` free, held constant, != key 0xC3',
                        goal=f'{goal_out} == 0x{goal_value:X} at some cycle < {N}'), note='stand-in', netlist=dict(gates=gates, flops=flops),
             honest_key_boots_fault_free=True, model=dict(sites_total=(gates + flops) * N, sites_modelled=(gates + flops) * N - 100, reduce='full', build_s=0.01, solve_s=0.02, minimize_s=0.01),
             runtime_s=dict(synth=0.0 if stored else 0.12, solve_and_minimize=0.03), netlist_json=jpath)
    if atk:
        d['min_faults'] = rec['min']
        d['faults'] = [dict(net=n, net_id=names[n], cycle=t, kind='gate_output') for n, t in rec['faults']]
        sig = rec['sig'] if rec['sig'] is not None else 0x03
        d['attacker_input'] = {'sig': f'0x{sig:02X}'}; d['attacker_input_raw'] = {'sig': sig}
        d['explanation'] = dict(summary='STAND-IN TEXT THAT MUST NEVER BE SHOWN', fix_pattern='x', fault_details=[])
    return d
