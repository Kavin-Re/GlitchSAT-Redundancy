"""Starting points from other tools: Tiny Tapeout info.yaml, SymbiYosys .sby, SYNFI fault_model.json.
Each writes a glitchsat.yaml that `glitchsat check` accepts; the bad condition usually needs one edit (marked TODO)."""
import json
import os
import re
import sys

from .errors import GSError
from . import init as INIT


def tinytapeout(folder):
    """info.yaml of a Tiny Tapeout project: project.top_module and project.source_files (in src/)."""
    p = os.path.join(folder, 'info.yaml')
    if not os.path.isfile(p):
        raise GSError('GS003', 'no info.yaml in %s' % folder, help='give the folder of a Tiny Tapeout project (it has info.yaml and src/)')
    import yaml
    doc = yaml.safe_load(open(p)) or {}
    pr = doc.get('project') or {}
    top = pr.get('top_module')
    srcs = [os.path.join('src', s) for s in pr.get('source_files') or []]
    if not top or not srcs:
        raise GSError('GS002', 'info.yaml has no project.top_module or project.source_files')
    return dict(top=top, sources=srcs, title=pr.get('title'))


def from_sby(path):
    """[files] -> sources, `prep -top X` / `hierarchy -top X` -> top, [options] depth -> horizon."""
    txt = open(path).read()
    sec, cur = {}, None
    for ln in txt.splitlines():
        m = re.match(r'^\[(\w+)\]', ln.strip())
        if m:
            cur = m.group(1); sec.setdefault(cur, []); continue
        if cur and ln.strip() and not ln.strip().startswith('#'):
            sec[cur].append(ln.strip())
    files = [l.split()[-1] for l in sec.get('files', [])]
    top = None
    for l in sec.get('script', []):
        m = re.search(r'-top\s+(\S+)', l)
        if m:
            top = m.group(1)
    depth = 20
    for l in sec.get('options', []):
        m = re.match(r'depth\s+(\d+)', l)
        if m:
            depth = int(m.group(1))
    return dict(sources=files, top=top, horizon=depth)


def _synfi_values(vals):
    """SYNFI {signal: {pin: {bit: value}}} (or flat {signal: value}) -> Verilog terms `signal[bit] == value`."""
    terms = []
    for sig, v in (vals or {}).items():
        if isinstance(v, dict):
            for pin, bits in v.items():
                if isinstance(bits, dict):
                    for bit, val in bits.items():
                        terms.append('(%s[%s] == %s)' % (sig, int(bit), int(val)))
                else:
                    terms.append('(%s == %s)' % (sig, int(bits)))
        else:
            terms.append('(%s == %s)' % (sig, v))
    return terms


def from_synfi(path):
    """SYNFI fault_model.json: {"fimodels": {name: {simultaneous_faults, fault_locations, output_values, alert_values,
    node_fault_mapping, stages}}}. One check per model: output_values -> bad, alert_values -> must_hold (the alert keeps
    its stated value), fault_locations -> include, simultaneous_faults -> max_faults. Keys not used are listed."""
    d = json.load(open(path))
    models = d.get('fimodels')
    if not isinstance(models, dict):
        models = {'model': d}              # an old flat file
    out = []
    unused = set()
    for name, m in models.items():
        locs = m.get('fault_locations') or {}
        inc = sorted({re.sub(r'\$abc\$.*', '*', str(k)) for k in (locs if isinstance(locs, (dict, list)) else [])})[:40]
        bad = _synfi_values(m.get('output_values'))
        hold = _synfi_values(m.get('alert_values'))
        out.append(dict(id=re.sub(r'[^A-Za-z0-9_]', '_', str(name)) or 'model', max_faults=int(m.get('simultaneous_faults', 1)),
                        include=inc, bad=' && '.join(bad) or 'TODO_write_the_bad_condition', must_hold=hold))
        unused |= {k for k in m if k not in ('fault_locations', 'output_values', 'alert_values', 'simultaneous_faults')}
    return dict(models=out, unused=sorted(unused))


def _detect(sources, top):
    """Clock, reset and top from the design, as `glitchsat init` finds them (None when Yosys or the files are missing)."""
    srcs = [x for x in sources or [] if os.path.isfile(x)]
    if not srcs or len(srcs) != len(sources or []):
        return None
    try:
        return INIT.suggest(os.getcwd(), srcs, top)
    except GSError:
        return None


def main(a):
    if os.path.exists(a.out):
        print('error[GS003]: %s already exists\n  = help: use --out other.yaml' % a.out, file=sys.stderr)
        return 3
    if a.cmd == 'import-sby':
        s = from_sby(a.file)
        det = _detect(s['sources'], s['top'])
        ans = dict(name=s['top'] or 'design', sources=s['sources'], top=(det or {}).get('top') or s['top'] or 'TODO_top',
                   clock=(det or {}).get('clock') or 'clk', reset=(det or {}).get('reset'),
                   attacker='all', template='custom', bad='TODO_write_the_bad_condition', horizon=s['horizon'], max_faults=3,
                   evidence=(det or {}).get('evidence') or ['imported from %s: files, top and depth; clock/reset are guesses '
                                                            '(Yosys or the files were not available)' % os.path.basename(a.file)])
        text = INIT.make_yaml(ans)
        warn = []
    else:
        s = from_synfi(a.file)
        m0 = s['models'][0]
        det = _detect(a.sources, None)
        ans = dict(name='synfi_import', sources=a.sources or ['TODO_netlist.v'], top=(det or {}).get('top') or 'TODO_top',
                   clock=(det or {}).get('clock') or 'clk_i', reset=(det or {}).get('reset'),
                   attacker='all', template='custom', bad=m0['bad'], must_hold=m0['must_hold'], horizon=4,
                   max_faults=max(x['max_faults'] for x in s['models']), check_id=m0['id'],
                   evidence=(det or {}).get('evidence') or ['imported from SYNFI %s' % os.path.basename(a.file)])
        text = INIT.make_yaml(ans)
        extra = []
        for m in s['models'][1:]:
            extra.append('  - id: %s' % m['id'])
            extra.append('    bad: %s' % INIT._q(m['bad']))
            if m['must_hold']:
                extra.append('    must_hold: [%s]' % ', '.join(INIT._q(x) for x in m['must_hold']))
            extra.append('    max_faults: %d' % m['max_faults'])
        if extra:
            text = text.replace('\n# 5. How hard', '\n' + '\n'.join(extra) + '\n\n# 5. How hard', 1)
        incs = sorted({x for m in s['models'] for x in m['include']})
        if incs:
            text = text.replace('  max_faults:', '  include: [%s]   # from fault_locations\n  max_faults:' % ', '.join(INIT._q(x) for x in incs), 1)
        warn = ['SYNFI key(s) not used: %s (GlitchSAT does not need them)' % ', '.join(s['unused'])] if s['unused'] else []
        if 'TODO' in text:
            warn.append('values marked TODO must be filled in; `glitchsat check` refuses the file until then')
    open(a.out, 'w').write(text)
    for w in warn:
        print('warning: ' + w, file=sys.stderr)
    print('Wrote %s; edit the lines marked TODO (if any), then `glitchsat check %s`.' % (a.out, a.out))
    return 0
