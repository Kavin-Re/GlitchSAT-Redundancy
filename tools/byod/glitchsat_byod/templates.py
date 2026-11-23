"""Templates for common "what must never happen" properties. Each turns a few named parameters into the `bad` and
`must_hold` conditions of a check, plus a plain-language sentence. The YAML snippets are in templates/*.yaml."""
from .errors import GSError


def _req(p, keys, tid):
    miss = [k for k in keys if k not in p]
    if miss:
        raise GSError('GS002', 'template `%s` needs the parameter(s) %s' % (tid, ', '.join('`%s`' % k for k in miss)),
                      help='see `glitchsat templates %s` for an example' % tid)


def _alarm(p, out):
    if p.get('alarm'):
        out['must_hold'].append('!(%s)' % p['alarm'])
        out['explain'] += ' The alarm `%s` must stay silent.' % p['alarm']
        if p.get('alarm_latency'):
            out['detect_latency'] = int(p['alarm_latency'])


def expand(tid, p):
    p = dict(p or {})
    out = dict(bad=None, must_hold=[], explain='', fixed={}, detect_latency=0)
    if tid == 'secure_boot_wrong_key':
        _req(p, ['accept', 'key_input', 'good_key'], tid)
        out['bad'] = '(%s) && (%s != %s)' % (p['accept'], p['key_input'], p['good_key'])
        out['explain'] = ('The chip says ACCEPT (%s) while the key or signature at `%s` is not the genuine one (%s).'
                          % (p['accept'], p['key_input'], p['good_key']))
        _alarm(p, out)
    elif tid == 'debug_unlock_locked':
        _req(p, ['unlocked', 'locked'], tid)
        out['bad'] = '(%s) && (%s)' % (p['unlocked'], p['locked'])
        out['explain'] = ('Debug access opens (%s) although the life-cycle state says locked (%s).' % (p['unlocked'], p['locked']))
        _alarm(p, out)
    elif tid == 'fsm_forbidden_state':
        _req(p, ['state'], tid)
        if 'forbidden' in p:
            vals = p['forbidden'] if isinstance(p['forbidden'], list) else [p['forbidden']]
            out['bad'] = ' || '.join('(%s == %s)' % (p['state'], v) for v in vals)
            out['explain'] = 'The state machine `%s` reaches a forbidden state (%s).' % (p['state'], ', '.join(str(v) for v in vals))
        elif 'allowed' in p:
            vals = p['allowed']
            out['bad'] = '!(%s)' % ' || '.join('(%s == %s)' % (p['state'], v) for v in vals)
            out['explain'] = 'The state machine `%s` holds a value that is none of its legal states (%s).' % (p['state'], ', '.join(str(v) for v in vals))
        else:
            raise GSError('GS002', 'template `fsm_forbidden_state` needs `forbidden: [...]` or `allowed: [...]`')
        if p.get('when'):
            out['bad'] = '(%s) && (%s)' % (out['bad'], p['when'])
        _alarm(p, out)
    elif tid == 'key_to_output':
        _req(p, ['key', 'output', 'test_key'], tid)
        out['fixed'][p['key']] = p['test_key']
        mask = p.get('mask')
        if mask:
            out['bad'] = '((%s) & (%s)) == ((%s) & (%s))' % (p['output'], mask, p['test_key'], mask)
        else:
            out['bad'] = '(%s) == (%s)' % (p['output'], p['test_key'])
        if p.get('valid'):
            out['bad'] = '(%s) && (%s)' % (out['bad'], p['valid'])
        out['explain'] = ('With the test key %s at `%s`, the output `%s` shows the key. The fault-free design never shows it '
                          '(checked first), so a hit means faults made key bits reach the output.' % (p['test_key'], p['key'], p['output']))
        _alarm(p, out)
    elif tid == 'counter_skip':
        _req(p, ['counter'], tid)
        step = p.get('step', 1)
        c = p['counter']
        jump = '(%s != $past(%s)) && (%s != (($past(%s) + %s) & {W}))' % (c, c, c, c, step)
        if p.get('must_step_when'):
            # a stuck counter: the event that must be counted happened, and the counter did not move
            out['bad'] = '!$initial && ((%s) || ($past(%s) && (%s == $past(%s))))' % (jump, p['must_step_when'], c, c)
        else:
            out['bad'] = '!$initial && %s' % jump
        out['width_of'] = c
        if p.get('when'):
            out['bad'] = '(%s) && (%s)' % (out['bad'], p['when'])
        out['explain'] = ('The counter `%s` changes by something other than +%s (skips or jumps)%s.'
                          % (c, step, ', or does not count an event that must be counted (`%s`)' % p['must_step_when']
                             if p.get('must_step_when') else ''))
        _alarm(p, out)
    elif tid == 'alarm_suppressed':
        _req(p, ['trigger', 'alarm'], tid)
        lat = int(p.get('latency', 1))
        out['bad'] = '$past(%s, %d)' % (p['trigger'], lat) if lat else '(%s)' % p['trigger']
        out['must_hold'].append('!(%s)' % p['alarm'])
        out['explain'] = ('The tamper condition `%s` happened, yet the alarm `%s` did not fire within %d cycle(s).'
                          % (p['trigger'], p['alarm'], lat))
    elif tid == 'custom':
        _req(p, ['bad'], tid)
        out['bad'] = p['bad']
    else:
        raise GSError('GS002', 'unknown template `%s`' % tid, help='templates: ' + ', '.join(NAMES))
    return out


# What the attacker gets when a check fails ("goal"): stated per check as `goal:` in glitchsat.yaml; each template
# has a default. The plain-words findings take "what the attacker gets" from this, never from the check's wording.
GOALS = {
    'boot_accept': 'the chip starts software it should refuse (a wrong key, tag or signature is accepted)',
    'key_leak': 'secret key bits become readable',
    'debug_unlock': 'the debug port opens while the chip is locked',
    'lock_bypass': 'a lock or access check opens without the right code',
    'alarm_suppress': 'an attack that should raise the alarm goes unnoticed',
    'state_change': 'the design does a different next step (a counter, a state machine, a setting)',
    'crash_only': 'the design stops or misbehaves, and the attacker gains nothing else',
}
GOAL = {'secure_boot_wrong_key': 'boot_accept', 'debug_unlock_locked': 'debug_unlock', 'fsm_forbidden_state': 'state_change',
        'key_to_output': 'key_leak', 'counter_skip': 'state_change', 'alarm_suppressed': 'alarm_suppress'}

NAMES = ['secure_boot_wrong_key', 'debug_unlock_locked', 'fsm_forbidden_state', 'key_to_output', 'counter_skip',
         'alarm_suppressed', 'custom']

PLAIN = {
    'secure_boot_wrong_key': 'The boot check accepts a program whose key or signature is wrong.',
    'debug_unlock_locked': 'The debug port (JTAG) opens while the chip is in a locked life-cycle state.',
    'fsm_forbidden_state': 'A state machine reaches a state it must never reach (or an illegal code).',
    'key_to_output': 'Bits of a secret key appear on an output.',
    'counter_skip': 'A counter jumps over a value, or does not count what it must (a retry counter, a step counter).',
    'alarm_suppressed': 'Something that must raise the alarm happens, and the alarm stays silent.',
    'custom': 'Your own condition, written as a Verilog expression.',
}
