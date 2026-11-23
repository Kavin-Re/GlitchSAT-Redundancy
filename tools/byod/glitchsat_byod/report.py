"""Reports: plain-language text, JSON, and the `--redact` mode (consistent aliases for every design name)."""
import json
import re

FAULT_WORDS = {'flip': 'flipped (0 and 1 swapped)', 'set': 'forced to 1', 'reset': 'forced to 0'}


def _n(k, one, many):
    return '%d %s' % (k, one if k == 1 else many)


def _bound_txt(c):
    return 'within %s, with up to %s' % (_n(c['horizon'], 'cycle', 'cycles'), _n(c['max_faults'], 'fault', 'faults'))


def headline(c):
    """One line that names the weakest build when builds differ (main flow first)."""
    mf = (c.get('analyses') or {}).get('min_faults') or {}
    sv = (c.get('analyses') or {}).get('survival') or {}
    rows = sv.get('rows') or []
    if len(rows) < 2:
        return None
    vals = [(r['flow'], r.get('min_faults'), r.get('verdict')) for r in rows]
    if len({(m, v) for _, m, v in vals}) < 2:
        return None
    found = [(m, f) for f, m, v in vals if m is not None]
    if not found:
        return None
    m, f = min(found)
    main = rows[0]
    mtxt = ('held (no attack with up to %d)' % c['max_faults'] if main.get('verdict') == 'NO_ATTACK_UP_TO_BOUND' else
            _n(main['min_faults'], 'fault', 'faults') if main.get('min_faults') is not None else main.get('verdict'))
    return 'Main build (%s): %s. Weakest build (%s): %s.' % (main['flow'], mtxt, f, _n(m, 'fault', 'faults'))


# ------------------------------------------------------------------ "What to do": named remedies, in plain words

def must_hold_line(w):
    """`must_hold: [...]` built from the input values of a no-glitch run: "the attack may not simply do this"."""
    terms = []
    hit = (w or {}).get('hit_cycle') or 0
    for p, iv in ((w or {}).get('inputs') or {}).items():
        vals = iv.get('values') or []
        if not vals:
            continue
        v = vals[0] if len(vals) == 1 else vals[max(0, min(len(vals) - 1, hit - 1))]
        v = str(v)
        if v.startswith('0x'):
            if int(v, 16) == 0:
                continue
            v = "'h" + v[2:]
        terms.append('%s == %s' % (p, v))
    cond = '!(%s)' % ' && '.join(terms) if terms else '!(<what a legitimate user does>)'
    return 'must_hold: ["%s"]' % cond


def _cm_name(cm):
    """A countermeasure title as words: "3 copies of x" -> "the copies of x", "alarm alarm" -> "the alarm"."""
    t = re.sub(r'\b(\w+) \1\b', r'\1', (cm.get('title') or 'the protection').strip())
    t = re.sub(r'^\d+ copies of ', 'the copies of ', t)
    if t.lower().startswith('alarm') or (cm.get('kind') == 'alarm' and not t.lower().startswith('the ')):
        t = 'the ' + (t if t.lower().startswith('alarm') else 'alarm ' + t)
    return t


def remedies(c, rep_flows=None):
    """Concrete next steps chosen by what the analyses found. Returns a list of dict(id, text)."""
    A = c.get('analyses') or {}
    out = []
    seen = set()

    def add(i, t):
        if i not in seen:
            seen.add(i); out.append(dict(id=i, text=t))
    mf = A.get('min_faults') or {}
    if mf.get('verdict') == 'FAILS_WITHOUT_FAULTS':
        # No glitch was needed: the question is wrong or the design has a bug. Advice about copies or placement would
        # only distract, so the one next step is about the condition itself.
        line = must_hold_line(mf.get('witness'))
        if not c.get('must_hold') and not c.get('assertions'):
            add('must_hold', 'The must_hold condition is missing from check `%s`. Without one, ordinary use already makes '
                '`bad` true: the inputs shown above did it with no glitch at all. Write down what a legitimate user may do, '
                'so that the search has to break the design instead of simply using it. Line to add under the check in '
                'glitchsat.yaml (edit it to what your design really allows): %s' % (c.get('id'), line))
        else:
            add('must_hold', 'No glitch was needed, so either the design has a functional bug or the must_hold condition '
                'is too wide. Replay the inputs shown above in your own simulation; if that use is allowed, add it to '
                'must_hold, for example: %s' % line)
        if any(fl.get('blackbox_outputs') for fl in (rep_flows or {}).values()):
            add('blackbox', 'Part of the design is a black box: its outputs are free here, so the answer covers the logic '
                'around it only. Add its source (or a functional model) to analyse it too.')
        return out
    sv = (A.get('survival') or {}).get('rows') or []
    weaker = [r['flow'] for r in sv if 'WEAKER' in (r.get('change') or '')]
    cms = (A.get('merge_lint') or {}).get('countermeasures') or []
    for cm in cms:
        kind = cm.get('kind') or ''
        for st in cm.get('stages') or []:
            v = (st.get('verdict') or '').strip()
            fl = st.get('stage')
            if v in ('REMOVED', 'WEAKENED') and kind in ('redundant_copies', 'redundant_register', 'alarm'):
                add('keep', 'Build `%s` %s %s. Stop the tool from merging them: keep each copy in its own '
                    'module and do not flatten before optimising (Yosys: put (* keep_hierarchy *) on the copy modules and '
                    '(* keep *) on their registers, or use the per-module flow `synth-keep`; commercial tools: set '
                    'dont_touch / preserve on those instances). Then run GlitchSAT again on the final netlist.'
                    % (fl, 'removed' if v == 'REMOVED' else 'merged some of', _cm_name(cm)))
            if v in ('REMOVED', 'WEAKENED') and kind in ('sparse_encoding', 'mubi'):
                add('encoding', 'Build `%s` re-encoded `%s`, so its codes are closer together than written. Keep the '
                    'encoding: Yosys flow `synth-nofsm` (or (* fsm_encoding = "none" *) on the state register); '
                    'commercial tools: switch off FSM extraction/re-encoding for that register.' % (fl, cm.get('title')))
            if v == 'UNTRACKED':
                add('untracked', 'UNTRACKED means the copies of %s could not be followed through build `%s` (no flip-flop '
                    'or net with their names was left), so nothing is said about whether they survived; the glitch '
                    'counts above still hold. To make them traceable, keep their names: (* keep *) on the registers.'
                    % (cm.get('title'), fl))
            if kind.startswith('fw_') and v in ('REMOVED', 'WEAKENED'):
                add('barrier', 'The compiler merged the repeated check %s. Read the value again each time (volatile) and '
                    'put a compiler barrier between the checks (GCC/Clang: asm volatile("" ::: "memory")).' % cm.get('title'))
    if weaker and 'keep' not in seen:
        add('keep', 'Build %s needs fewer glitches than `%s`: synthesis merged or simplified the protection. Keep '
            'the copies in separate modules and stop merging (Yosys: (* keep_hierarchy *) and (* keep *), or flow '
            '`synth-keep`; commercial tools: dont_touch / preserve), then run GlitchSAT again on the final netlist.'
            % (', '.join('`%s`' % f for f in weaker), sv[0]['flow']))
    mf = A.get('min_faults') or {}
    s = A.get('attack_surface') or {}
    if mf.get('verdict') == 'ATTACK_FOUND':
        if s.get('count') and s.get('sites'):
            site, n = s['sites'][0]
            if n == s['count'] and s['count'] > 1:
                add('single', 'Every one of the %d cheapest attacks uses `%s`: it is a single point of failure. Give each '
                    'copy its own path to the decision (for example require all copies to agree, or vote) instead of '
                    'one shared signal, and add an alarm when the copies disagree.' % (s['count'], site))
        if mf.get('min_faults') == 1:
            w = mf.get('witness') or {}
            fl = [f for f in w.get('faults') or [] if f.get('kind') == 'flop']
            if fl:
                add('encode', 'One flipped flip-flop (`%s`) is enough. Store this decision redundantly: several copies, '
                    'or a sparse code (valid values that differ in at least one more bit than the number of faults to resist, '
                    'e.g. 4\'b1010 / 4\'b0101 instead of 1/0), '
                    'so one flip cannot turn one valid value into another.' % fl[0]['site'])
            elif w.get('faults'):
                add('encode', 'One glitch on `%s` is enough. Check the decision more than once, on separate logic, and '
                    'raise an alarm when the results disagree.' % w['faults'][0]['site'])
    has_copies = any((cm.get('kind') in ('redundant_copies', 'redundant_register')) for cm in cms)
    if has_copies:
        add('place', 'This analysis does not see placement: one laser or EM shot can hit copies that sit next to each '
            'other. Spread the copies apart with a placement constraint (regions/fences or a minimum distance in the '
            'place-and-route flow) and check the placed design again.')
    if any(fl.get('blackbox_outputs') for fl in (rep_flows or {}).values()):
        add('blackbox', 'Part of the design is a black box: its outputs are free here, so the answer covers the logic '
            'around it only. Add its source (or a functional model) to analyse it too.')
    return out


def plain_findings_module():
    """The shared plain-words explainer (tools/findings in the repository; ext/findings in a work tree), or None."""
    import importlib.util
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    for d in (os.environ.get('GLITCHSAT_FINDINGS'), os.path.join(here, '..', '..', 'findings'),
              os.path.join(os.environ.get('GLITCHSAT_ROOT') or '', 'tools', 'findings')):
        p = os.path.join(d or '', 'plain_findings.py')
        if d and os.path.isfile(p):
            sp = importlib.util.spec_from_file_location('plain_findings', p)
            m = importlib.util.module_from_spec(sp)
            sp.loader.exec_module(m)
            return m
    return None


def plain_findings(rep):
    """Plain-words findings of a report (stored in the report as `plain_findings`), [] when the explainer is missing."""
    if rep.get('plain_findings') is not None:
        return rep['plain_findings']
    pf = plain_findings_module()
    return pf.from_byod_report(rep) if pf else []


def plain(rep):
    L = []
    L.append('GlitchSAT result: %s (top module `%s`)%s' % (rep['name'], rep['top'], (' task ' + rep['task']) if rep.get('task') else ''))
    L.append('=' * len(L[0]))
    fs = plain_findings(rep)
    pf = plain_findings_module() if fs else None
    if pf:                       # learners first: what it means, how bad, what to do; the technical report follows
        L += pf.to_text(fs).splitlines() + ['', 'Technical details', '-----------------']
    d = rep['design']
    att = [p for p, r in d['roles'].items() if r == 'attacker']
    sec = [p for p, r in d['roles'].items() if r == 'secret']
    L.append('The attacker controls: %s (%s).' % (', '.join(att) or 'no input', 'a new value every cycle' if d['attacker_changes'] == 'every_cycle' else 'one value for the whole run'))
    if sec:
        L.append('Secret inputs (held constant, any value): %s.' % ', '.join(sec))
    if d['fixed']:
        L.append('Tied inputs: %s.' % ', '.join('%s = %s' % kv for kv in d['fixed'].items()))
    if d['reset']:
        r = d['reset']
        L.append('Before the attack: reset `%s` (active %s) for %s; %s.' % (
            r['port'], r['active'], _n(r['cycles'], 'cycle', 'cycles'),
            'faults may also hit the reset sequence' if r.get('glitch_during_reset') else 'faults start in the first cycle after reset'))
    L.append('Power-up values of the flip-flops: %s.' % {'any': 'unknown (the search may choose any)', 'zero': 'all 0',
                                                          'init': 'as given in the design', 'init-or-zero': 'as given in the design, else 0'}[d['powerup']])
    L.append('Fault sites: every gate output and the stored value of every flip-flop (a flipped stored value stays until '
             'the flip-flop loads a new one). Every build is normalised the same way first (enable and synchronous-reset '
             'flip-flops become plain flip-flops plus gates), so builds are compared on the same fault model.')
    fls = rep.get('flows') or {}
    bbo = sorted({'%s.%s' % (b['cell'], b['pin']) for f in fls.values() for b in f.get('blackbox_outputs') or []})
    bbi = sorted({'%s.%s' % (b['cell'], b['pin']) for f in fls.values() for b in f.get('blackbox_inputs') or []})
    if bbo or bbi:
        L.append('Coverage boundary (black boxes): these outputs are free (any value, every cycle): %s; these inputs leave '
                 'the analysis: %s. Nothing inside the black boxes is analysed.' % (', '.join(bbo) or 'none', ', '.join(bbi) or 'none'))
    for fl, f in fls.items():
        if f.get('error'):
            continue
        sp = f.get('scan_enable_attacker') or []
        if sp:
            L.append('Risk (%s): the scan enable of %s is driven by attacker input %s, so the attacker can switch '
                     'those flip-flops to their scan input. Tie it with `inputs.fixed` if it is a test pin.'
                     % (fl, _n(f.get('scan_flops') or 0, 'flip-flop', 'flip-flops'), ', '.join('`%s`' % x for x in sp)))
        rk = {k: v for k, v in (f.get('risks') or {}).items() if v}
        if rk:
            L.append('Cells with extra risk (%s): %s.' % (fl, ', '.join('%s %d' % kv for kv in sorted(rk.items()))))
        if f.get('physical_dropped'):
            L.append('Physical-only cells dropped before reading (%s): %s.' % (fl, ', '.join('%s %d' % kv for kv in sorted(f['physical_dropped'].items()))))
    for c in rep['checks']:
        L.append('')
        if c.get('status') == 'NOT_RUN':
            L.append('Check `%s` (%s): NOT RUN. %s' % (c['id'], c.get('kind'), c.get('why')))
            continue
        L.append('Check `%s`' % c['id'])
        L.append('-' * (8 + len(c['id'])))
        if c.get('explain'):
            L.append('What must never happen: %s' % c['explain'])
        if c.get('assertions'):
            ac = c.get('assertion_count') or {}
            L.append('Condition: the assert/assume statements in %s (%s, %s read; an assert that fails is the success of '
                     'the attack)' % (c['assertions'], _n(ac.get('assert', 0), 'assert', 'asserts'), _n(ac.get('assume', 0), 'assume', 'assumes')))
        else:
            L.append('Condition (Verilog): bad = %s%s' % (c['bad'], ('; must hold: ' + ' && '.join(c['must_hold'])) if c['must_hold'] else ''))
        A = c['analyses']
        mf = A.get('min_faults') or {}
        v = mf.get('verdict')
        scope = _bound_txt(c)
        bbnote = ' The attack also uses free black-box outputs (%s): it holds only if the box can produce those values.' % \
            ', '.join(sorted((mf.get('witness') or {}).get('free') or {})) if (mf.get('witness') or {}).get('free') else ''
        if v == 'ATTACK_FOUND':
            m = mf['min_faults']
            L.append('ANSWER: %s %s enough %s. [MEASURED%s]%s' % (_n(m, 'fault', 'faults'), 'is' if m == 1 else 'are', scope,
                                                                  ', smallest number proved' if mf.get('proved_minimum') else ', ' + mf.get('note_interval', ''), bbnote))
        elif v == 'NO_ATTACK_UP_TO_BOUND':
            L.append('ANSWER: no attack %s. [MEASURED, bounded: says nothing about more faults or more cycles]' % scope)
        elif v == 'FAILS_WITHOUT_FAULTS':
            L.append('ANSWER: the design does this WITHOUT any fault (a functional bug, or the condition is too wide). [MEASURED]%s%s' % (
                bbnote, '' if (c.get('must_hold') or c.get('assertions')) else ' This check has no must_hold condition: see "What to do".'))
        elif v == 'VACUOUS':
            L.append('ANSWER: none. The must-hold conditions can never all be true, so the question is empty (%s).' % mf.get('why'))
        else:
            L.append('ANSWER: not decided (%s).' % (mf.get('why') or v))
        h = headline(c)
        if h:
            L.append(h)
        w = mf.get('witness')
        if w:
            L.append('How the attack works (replayed on a gate-level simulator: %s):' % ('yes' if w['replayed'] else 'NO'))
            for f in w['faults']:
                L.append('  - cycle %d: %s is %s%s' % (f['cycle'], f['site'], FAULT_WORDS.get(f['type'], f['type']),
                                                       ' (%s)' % f['src'] if f.get('src') else ''))
            for p, iv in w['inputs'].items():
                vals = iv['values']
                L.append('  - input %s: %s' % (p, vals[0] if len(vals) == 1 else ', '.join(vals) + ' (cycle 0, 1, ...)'))
            for p, vals in (w.get('free') or {}).items():
                L.append('  - black-box output %s (free): %s' % (p, ', '.join(vals)))
            if w['powerup_ones']:
                L.append('  - power-up value 1 chosen for: %s' % ', '.join(list(w['powerup_ones'])[:8]))
            L.append('  - the condition is met in cycle %s (cycle 0 = first cycle %s)%s' % (
                w['hit_cycle'], 'after reset' if d['reset'] and not d['reset'].get('glitch_during_reset') else 'after power-up',
                '; this is the earliest cycle in which it can happen with this number of faults' if w.get('shortest') else ''))
        s = A.get('attack_surface') or {}
        if s.get('count'):
            top = ', '.join('%s (%d)' % (k, n) for k, n in s['sites'][:5])
            L.append('Weak spots: %d smallest attack(s)%s; most used: %s.' % (s['count'], '' if s['complete'] else ' (list stopped: %s)' % s['stop_reason'], top))
        u = A.get('unbounded') or {}
        if u.get('verdict') == 'PROVED_UNBOUNDED':
            L.append('For any waiting time: PROVED that %s cannot do it, however many cycles pass. [MEASURED, proof]' % _n(u['k'], 'fault', 'faults'))
        elif u.get('verdict') == 'ATTACK_FOUND':
            L.append('For any waiting time: an attack with %s exists if the attacker waits longer: %s' % (_n(u['k'], 'fault', 'faults'), u.get('meaning')))
        elif u.get('verdict'):
            L.append('For any waiting time: not decided (%s).' % (u.get('why') or u['verdict']))
        sv = A.get('survival')
        if sv:
            parts = []
            for r in sv['rows']:
                mm = r.get('min_faults')
                parts.append('%s: %s%s' % (r['flow'], (_n(mm, 'fault', 'faults') if mm is not None else
                                                     ('no attack up to %d' % c['max_faults'] if r['verdict'] == 'NO_ATTACK_UP_TO_BOUND' else r['verdict'])),
                                          (' (' + r['change'] + ')') if r.get('change') and r['change'] != 'same' else ''))
            L.append('Other synthesis flows: ' + '; '.join(parts) + '.')
        ml = A.get('merge_lint') or {}
        for cm in ml.get('countermeasures', []):
            L.append('Redundancy `%s`: %s' % (cm['title'], ', '.join('%s %s' % (st['stage'], st['verdict']) for st in cm['stages'])))
        if any((st.get('verdict') or '').strip() == 'UNTRACKED' for cm in ml.get('countermeasures', []) for st in cm['stages']):
            L.append('  (UNTRACKED: the copies could not be followed through that build, so nothing is said about them.)')
        if c.get('assertions'):
            L.append('Not checked by simulation: the wrapper validation is not run for checks written as assertion files.')
        vals = [(fl, fr['validation']) for fl, fr in c['flows'].items() if (fr.get('validation') or {}).get('runs')]
        if vals:
            ref = 'Yosys\'s own reading of the same cells' if rep.get('frontend') == 'netlist' else 'the RTL'
            va = vals[0][1]
            L.append('Checked (%s): the analysed netlist matched %s in fault-free operation (%d random runs x %d cycles, '
                     '%s of values known on both sides). Logic that only acts after a fault (alarms, redundant copies) is '
                     'not covered by this check.' % (', '.join(f for f, _ in vals), ref, va['runs'], va['cycles'],
                                                     '/'.join('%.0f%%' % (100 * v['share_compared']) for _, v in vals)))
        for fl, fr in c['flows'].items():
            if (fr.get('validation') or {}).get('error'):
                L.append('NOT checked (%s): %s' % (fl, fr['validation']['error'].get('message')))
        todo = c.get('what_to_do') or remedies(c, fls)
        if todo:
            L.append('What to do:')
            for t in todo:
                L.append('  - ' + t['text'])
    L.append('')
    if rep.get('warnings'):
        L.append('Warnings:')
        for w in rep['warnings']:
            L.append('  [%s] %s' % (w['code'], w['message']))
    L.append('Limits: faults are modelled (a value inverted or forced for one clock cycle at a gate output or in a '
             'flip-flop), not measured on a chip. "No attack" is bounded by the fault budget and the number of cycles '
             'unless an unbounded proof is shown. Results hold for the analysed netlist of each flow.')
    return '\n'.join(L) + '\n'


# ------------------------------------------------------------------ redaction
#
# Redaction works on the structure of the report first, then on the remaining text:
#   * files: every design file, generated file and netlist path becomes file_N.<ext> (sha256 kept where present);
#     absolute paths of the project, the repository and the solvers are removed; Liberty files keep only their base
#     name (public library names) and sha256;
#   * values: the values of secret inputs (in the attack and in the signal table), tied-input values and every
#     constant written in a condition become <secret> / <value> / <const>;
#   * Yosys command lists become a count and a sha256;
#   * names: every design name (ports, nets, instances, modules, check ids, task, project name, file stems) becomes
#     an alias (sig_N, check_N), matched as whole tokens so the same name always gets the same alias.
# glitchsat.lock and the .glitchsat/ folder are NOT redacted (they stay on this computer, next to the design).

_LIT = re.compile(r"(?<![A-Za-z0-9_$])(\d*\s*'[sS]?[bBoOdDhH]\s*[0-9a-fA-FxXzZ?_]+|0[xX][0-9a-fA-F_]+|\d{2,})(?![A-Za-z0-9_])")


def _sha(text):
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()


def _cmds(cmds):
    cmds = list(cmds or [])
    return '<%d Yosys commands, sha256 %s>' % (len(cmds), _sha('\n'.join(map(str, cmds)))[:16])


def redact(obj, names, extra=None):
    """Returns (redacted report, alias mapping). `names`: design names; `extra`: dict(files=[paths], checks=[ids],
    secret_ports=[...], roots=[absolute folders to remove], words=[other identifying strings])."""
    import copy
    import os
    extra = extra or {}
    rep = copy.deepcopy(obj)
    files = {}

    def falias(p):
        if not isinstance(p, str) or not p:
            return p
        key = os.path.normpath(p)
        if key not in files:
            ext = os.path.splitext(p)[1] or ''
            files[key] = 'file_%02d%s' % (len(files) + 1, ext)
        return files[key]
    checks = {}
    for i, cid in enumerate(extra.get('checks') or [c.get('id') for c in rep.get('checks', [])], 1):
        if cid is not None:
            checks[str(cid)] = 'check_%02d' % i
    secret_ports = set(extra.get('secret_ports') or []) | {p for p, r in ((rep.get('design') or {}).get('roles') or {}).items() if r == 'secret'}
    # --- structure
    rep['name'] = 'design'
    rep['project'] = 'project.yaml'
    if rep.get('task'):
        rep['task'] = 'task'
    d = rep.get('design') or {}
    if d.get('fixed'):
        d['fixed'] = {k: '<value>' for k in d['fixed']}
    for c in rep.get('checks', []):
        for k in ('bad', 'explain', 'why'):
            if isinstance(c.get(k), str):
                c[k] = _LIT.sub('<const>', c[k])
        if isinstance(c.get('must_hold'), list):
            c['must_hold'] = [_LIT.sub('<const>', x) for x in c['must_hold']]
        if c.get('assertions'):
            c['assertions'] = falias(c['assertions'])
        g = c.get('generated') or {}
        for k in list(g):
            g[k] = '%s/%s' % (checks.get(str(c.get('id')), 'check'), os.path.basename(g[k])) if g[k] else g[k]
        for fl in (c.get('flows') or {}).values():
            va = fl.get('validation') or {}
            if isinstance(va.get('mismatch'), dict):
                va['mismatch'] = {k: (v if k in ('cycle', 'run') else '<redacted>') for k, v in va['mismatch'].items()}
        A = c.get('analyses') or {}
        for an in ('min_faults',):
            w = (A.get(an) or {}).get('witness')
            if w:
                for p in list(w.get('inputs') or {}):
                    if p in secret_ports:
                        w['inputs'][p]['values'] = ['<secret>']
                for row in w.get('trace') or []:
                    for p in secret_ports:
                        if 'in:' + p in row:
                            row['in:' + p] = '<secret>'
                for f in w.get('faults') or []:
                    if f.get('src'):
                        f['src'] = _src_alias(f['src'], falias)
        for cm in ((A.get('merge_lint') or {}).get('countermeasures') or []):
            if cm.get('source'):
                cm['source'] = _src_alias(str(cm['source']), falias)
            for st in cm.get('stages') or []:
                st['evidence'] = ['<redacted>' for _ in st.get('evidence') or []]
        ml = A.get('merge_lint') or {}
        if ml.get('notes'):
            ml['notes'] = ['<redacted>' for _ in ml['notes']]
        if (A.get('unbounded') or {}).get('invariant'):
            A['unbounded']['invariant'] = '<redacted>'
    for fl in (rep.get('flows') or {}).values():
        if 'commands' in fl:
            fl['commands'] = _cmds(fl['commands'])
        if fl.get('netlist'):
            fl['netlist'] = falias(fl['netlist'])
        fl['liberty'] = [dict(name=os.path.basename(x.get('path', '')), sha256=x.get('sha256')) for x in fl.get('liberty') or []]
    pv = rep.get('provenance') or {}
    if pv:
        pv['sources'] = [dict(path=falias(x.get('path')), sha256=x.get('sha256')) for x in pv.get('sources') or []]
        pv['elab_commands'] = _cmds(pv.get('elab_commands'))
        sv = pv.get('solvers') or {}
        pv['solvers'] = {k: (os.path.basename(v.split(':', 1)[-1]) if isinstance(v, str) and v else v) for k, v in sv.items()}
        eng = pv.get('engines') or {}
        if eng.get('repository'):
            eng['repository'] = 'found'
        for k, v in (pv.get('flows') or {}).items():
            v['commands'] = _cmds(v.get('commands'))
            v['liberty'] = [dict(name=os.path.basename(x.get('path', '')), sha256=x.get('sha256')) for x in v.get('liberty') or []]
        if 'files_read' in pv:
            pv['files_read'] = [dict(path=falias(x.get('path')), sha256=x.get('sha256')) for x in pv['files_read']]
    if rep.get('lock'):
        rep['lock']['path'] = 'project.lock'
    # --- text: absolute folders, then whole-token names
    roots = sorted({os.path.realpath(r) for r in (extra.get('roots') or []) if r} | {r for r in (extra.get('roots') or []) if r},
                   key=len, reverse=True)
    for f in extra.get('files') or []:
        falias(f)
    comps = set()
    for n in list(names) + list(extra.get('words') or []):
        for part in re.split(r'[.\[\]/\\$ :]+', str(n)):
            if part and not part.isdigit() and len(part) > 1 and not part.startswith('gs_') and part not in _KEEP:
                comps.add(part)
    for f in list(files):
        stem = os.path.splitext(os.path.basename(f))[0]
        if len(stem) > 1 and stem not in _KEEP:
            comps.add(stem)
    comps -= set(checks)
    mapping = {}
    for i, n in enumerate(sorted(comps, key=lambda s: (-len(s), s)), 1):
        mapping[n] = 'sig_%03d' % i
    mapping.update(checks)
    fmap = {}
    for f, al in files.items():
        fmap[f] = al
        fmap[os.path.basename(f)] = al
    frx = re.compile('|'.join(re.escape(k) for k in sorted(fmap, key=len, reverse=True))) if fmap else None
    rrx = re.compile('(%s)[^\\s,;:()\'"`]*' % '|'.join(re.escape(r) for r in roots)) if roots else None
    nrx = re.compile(r'(?<![A-Za-z0-9_])(%s)(?![A-Za-z0-9_])' % '|'.join(re.escape(k) for k in sorted(mapping, key=len, reverse=True))) if mapping else None

    def sub(x):
        if rrx:
            x = rrx.sub('<path>', x)
        if frx:
            x = frx.sub(lambda m: fmap[m.group(0)], x)
        if nrx:
            x = nrx.sub(lambda m: mapping[m.group(1)], x)
        return x

    def walk(x):
        if isinstance(x, str):
            return sub(x)
        if isinstance(x, list):
            return [walk(v) for v in x]
        if isinstance(x, dict):
            return {walk(k) if isinstance(k, str) else k: walk(v) for k, v in x.items()}
        return x
    return walk(rep), dict(mapping, **{('file:' + k): v for k, v in files.items()})


def _src_alias(src, falias):
    """'path/to/file.v:12.3-12.9' -> 'file_03.v:12'."""
    import os
    out = []
    for part in str(src).split('|'):
        m = re.match(r'^(.*?):(\d+)', part)
        out.append('%s:%s' % (falias(os.path.basename(m.group(1))), m.group(2)) if m else falias(os.path.basename(part)))
    return '|'.join(out)


_KEEP = {'bad', 'ok', 'flip', 'set', 'reset', 'gate', 'flop', 'flip-flop', 'output', 'input', 'AND', 'OR', 'XOR', 'NOT', 'MUX',
         'DFF', 'clk', 'MEASURED', 'cycle', 'the', 'of', 'and', 'or', 'not', 'stored', 'value', 'plain', 'synth', 'custom',
         'netlist', 'design', 'project', 'task', 'check', 'yaml', 'file', 'sig', 'past', 'initial', 'rtl', 'synth-keep', 'synth-nofsm', 'liberty'}


def to_json(rep):
    return json.dumps(rep, indent=1, sort_keys=False, default=str)
