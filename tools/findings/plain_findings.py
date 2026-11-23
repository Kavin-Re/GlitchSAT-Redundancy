"""Plain-words findings: one shared explainer for every GlitchSAT result path.

Every finding has seven parts, built only from data of the run (nothing is invented; a missing piece is said):
  severity   level (Critical / High / Medium / Low / Info) with an icon and a word (never colour alone), the reasons,
             what it means in real life, a real-world comparison from the lesson (only where honest), how urgent the
             fix is, and the note that this is an estimate for a modelled fault, not a measured attack
  statement  one plain sentence ("One well-timed glitch can make the check pass without comparing anything")
  why        the weakness pattern behind it, and whether the data showed it (yes / likely / cannot tell from this data)
  where      signal / instruction, file:line and clock step when known, or what is missing
  sure       how sure we are: PROVED / BOUNDED / SAMPLED / RECORDED in plain words
  next       what to do (concrete fixes) and how to check the fix (the exact re-run command)
  how        "How we found it": six numbered steps, a before/after trace of key values (only real run data), a way to
             try it yourself, a predict-first question, the lesson screen, and "spot it next time"

Patterns detected where the data allows (see PATTERNS):
  (a) removed_redundancy  the build tool or compiler removed a check or a copy the source intended
  (b) aliasing            one skipped instruction made two values the same, so a compare always passes
  (c) delay_only          a random delay did nothing against a precisely timed glitch
  (d) single_point        one wire, gate, flip-flop or branch decides the outcome
The severity rules live in SEVERITY_RULES and in SEVERITY.md (same text, one source: this file writes that page).
Standard library only. Used by the Studio (path, whole chip, boot program), the own-design tool (text report, JSON,
SARIF, "Open my design") and the tests.
"""
import json
import os
import re

LEVELS = ['Info', 'Low', 'Medium', 'High', 'Critical']
# A run that gave no answer (empty question, out of time, not run, solver gave up, tool error) is not a level of the
# scale above: it is never Info or Low, and it never says "nothing to fix".
UNKNOWN = 'Unknown'
UNKNOWN_WORDS = 'Unknown \u2014 not checked'
UNKNOWN_RANK = 1.5                     # sorted above Low and below Medium; counted on its own in the summary line
ICON = {'Critical': '!!!', 'High': '!!', 'Medium': '!', 'Low': '~', 'Info': 'i', UNKNOWN: '?'}  # text icons: never colour alone
COLOUR = {'Critical': 'crit', 'High': 'high', 'Medium': 'med', 'Low': 'low', 'Info': 'info', UNKNOWN: 'unknown'}

# What the attacker gets comes from explicit data: the check's `goal:` (project file), the template's goal, or the
# goal of a built-in study. Only when none is given is it guessed from whole words of the check's names, and then the
# card says so.
GOALS = {'boot_accept': 'boot', 'key_leak': 'key', 'debug_unlock': 'debug', 'lock_bypass': 'unlock',
         'alarm_suppress': 'alarm', 'state_change': 'control', 'crash_only': 'crash'}
GUESS_NOTE = 'guessed from the signal name \u2014 please confirm (add `goal:` to the check)'

# What an attacker gains, in plain words, and how much it matters (3 = takes control or a secret, 1 = nuisance).
GAINS = {
    'boot': (3, 'could make the chip start their own software'),
    'key': (3, 'could read a secret key'),
    'debug': (3, 'could take over the chip through its debug mode'),
    'unlock': (3, 'could open the lock without the right code'),
    'alarm': (2, 'could silence an alarm, so a second attack goes unnoticed'),
    'control': (2, 'could change what the chip does next (a counter, a setting or its next step)'),
    'crash': (1, 'could make the chip stop or misbehave, but gains nothing else'),
}

# Severity rules (the one place they are defined; SEVERITY.md is written from this table).
SEVERITY_RULES = [
    ('Fewest glitches needed', '1 glitch: easiest. 2 glitches: harder (two precise hits). 3 or more: much harder. '
     'None found within the limits: Info.'),
    ('What the attacker gets', 'Starting their own software, reading a key, taking over debug, opening a lock: high. '
     'Silencing an alarm or changing a step: medium. Only a crash: low. Taken from the goal of the check (`goal:` in '
     'the project file, the template, or the built-in study). Without a goal it is guessed from whole words of the '
     'signal names and the card says "please confirm"; with no match nothing is claimed and no comparison is given.'),
    ('Base level', '1 glitch: Critical (high gain), High (medium gain), Medium (low gain). 2 glitches: High, Medium, '
     'Low. 3 or more: Medium, Low, Low.'),
    ('Protection silently missing', 'If the source had a protection that the build tool or compiler removed, the level '
     'goes up by one (the designer believes it is there).'),
    ('How sure we are', 'BOUNDED and SAMPLED results do not change the level, but the card says the real answer might be '
     'worse or better than shown.'),
    ('Published attack-potential examples', 'PSA Certified Attack Methods v1.3, section 5.1.3, rates "a glitch required '
     'on each target device" at 20 points and "two successful glitches required" at about 21 to 23; no published '
     'example rates three or more glitches, so none is claimed here. No CVSS score is ever given.'),
    ('No answer', 'A run that did not decide the question (an empty question, out of time, not run, the solver gave up, '
     'a tool error) is rated "Unknown \u2014 not checked", never Info or Low, and is counted on its own in the summary '
     'line. It is not a pass.'),
    ('Always an estimate', 'Severity is our estimate for a modelled fault on a simulated chip or program, not a measured '
     'attack on real hardware.'),
]

URGENCY = {
    'Critical': 'Fix this before the design is made into a chip (or before the firmware ships).',
    'High': 'Fix before release; plan the change now.',
    'Medium': 'Worth fixing, but not a blocker on its own.',
    'Low': 'Fix when convenient, and keep an eye on it after each build change.',
    'Info': 'Nothing to fix for this question within the limits that were checked.',
    UNKNOWN: 'Not checked: this is not a pass. Fix the cause below and run again before relying on this result.',
}

WHO = {
    1: 'Someone with the device on their desk and standard glitching tools could do this, after some practice.',
    2: 'It takes two precise glitches at the right moments: harder, but published ratings still treat it as doable '
       'with standard equipment and expertise.',
    3: 'It takes several precise glitches at once: much harder, and likely needs a well-equipped lab.',
}

# Real-world comparisons: only cases told, with sources, in the lesson "Why protect chips?" (screen numbers from 1).
COMPARE = {
    'boot': ('Like the Nintendo Switch modchips, which glitch the start-up checks so that they accept unofficial '
             'software (lesson, true stories 1).', 5),
    'unlock': ('Like the start-up checks of the Nintendo Switch, which modchips glitched to accept unofficial software '
               '(lesson, true stories 1).', 5),
    'key': ('Like the Trezor wallets, where two voltage glitches let researchers copy out the stored secret (lesson, '
            'true stories 2).', 6),
    'debug': ('Like the Apple AirTag, whose locked debug connector gave way to one well-timed power cut (lesson, '
              'true stories 1).', 5),
}

SURE = {
    'PROVED': 'Proved: checked for every possibility, for any waiting time, in this model.',
    'BOUNDED': 'Bounded: the exact smallest number within the stated number of steps; longer runs were not checked, so '
               'the real answer might be worse or better.',
    'SAMPLED': 'Sampled: seen in a simulation of chosen cases; cases that were not tried might be worse or better.',
    'MEASURED': 'Computed exactly by the solver within the stated limits (number of glitches and steps).',
    'RECORDED': 'A saved result, computed earlier with the solver within the stated limits.',
    'LIVE': 'Computed just now with the solver within the stated limits.',
    'SIMULATED': 'Found by trying every single glitch position on a simulated processor; not measured on a real chip.',
    'NO_ANSWER': 'Not checked: the run gave no answer, so nothing was proved or found.',
}

PATTERNS = {
    'removed_redundancy': dict(
        tag='(a)', title='The build tool removed a protection',
        text='The design as written has a second check or extra copies. The tool that built the chip (or the compiler '
             'that made the machine code) merged or removed them. So fewer glitches are enough.',
        spot='After every change of build tool or compiler setting, check that each copy or second check is still '
             'there in the result (the gate list or the assembly), not only in your source.',
        fix_hw=['Keep each copy in its own module and stop the tool from merging them: Yosys (* keep_hierarchy *) on the '
                'copy modules and (* keep *) on their registers, or the flow synth-keep; commercial tools: dont_touch.',
                'Run GlitchSAT again on the final netlist, not only on the source.'],
        fix_fw=['Make the values of the check volatile (or use a compiler barrier) so the compiler cannot fold the '
                'second check away, and read the assembly to confirm both checks are there.',
                'Check every optimisation level you ship (-O0, -O2, -Os), not only one.']),
    'aliasing': dict(
        tag='(b)', title='One skipped instruction made two values the same',
        text='Two values that should be compared are loaded through the same register. Skipping one load leaves the '
             'first value in place, so the code compares something with itself and the check always passes.',
        spot='Look for code that copies two pointers or values through the same register right before a compare.',
        fix_hw=[],
        fix_fw=['Load the two values with independent loads and check that the two pointers differ before comparing.',
                'Compare a second time against a complemented (bit-inverted) copy of the expected value, so that a '
                'value compared with itself fails.']),
    'delay_only': dict(
        tag='(c)', title='A random delay did not stop a precisely timed glitch',
        text='The protection only adds a random wait. That makes timing harder on average, but a glitch at the right '
             'moment still works, and the attacker can simply try again.',
        spot='A random delay is a speed bump, not a lock: check that a single well-timed fault still fails, with the '
             'delay switched off.',
        fix_hw=['Add real redundancy (independent copies with an alarm) in addition to any random delay.'],
        fix_fw=['Keep the random delay, but also duplicate the decision with independent data (a second check, a '
                'complemented copy) so that one fault is not enough.']),
    'single_point': dict(
        tag='(d)', title='One wire or branch decides the outcome',
        text='The whole decision passes through a single point: one wire, one memory cell or one branch. Disturbing '
             'that one point is enough.',
        spot='Follow the decision from the check to where it is used: if it passes through one signal or one branch '
             'anywhere, that point is the weak spot.',
        fix_hw=['Make the decision a multi-bit answer (sparse code) and let the rest of the chip read all of it.',
                'Keep separate copies all the way to where the decision is used, and raise an alarm when they disagree.'],
        fix_fw=['Check the decision twice with independent code and compare against a complemented value '
                '(fault-injection hardening style), and never let a single branch grant access.']),
    'unprotected_alarm': dict(
        tag='', title='The alarm itself is not protected',
        text='The protection raises an alarm when copies disagree, but the alarm signal itself can be silenced with '
             'a glitch.',
        spot='Ask "what if the alarm wire itself is glitched?" for every alarm in your design.',
        fix_hw=['Duplicate the alarm path (or make it a multi-bit signal) and check it is still there after the build.'],
        fix_fw=['Report the alarm through two independent paths, or make the alarm the default and require an active '
                '"all clear".']),
    'no_fault_needed': dict(
        tag='', title='No glitch was needed',
        text='The bad outcome happens in ordinary use, without any glitch: either the design has a bug, or the question '
             'is missing what a legitimate user may do (a must-hold condition).',
        spot='Before counting glitches, check that the question excludes ordinary, allowed use.',
        fix_hw=['Add a must_hold condition that describes allowed use, then run again.'],
        fix_fw=['Check the decision logic without faults first.']),
    'copies_held': dict(
        tag='', title='The protection held: every copy had to be hit',
        text='No single point decides the outcome here: the attacker has to glitch every copy of the check, each at the '
             'right moment. That is what the protection is for.',
        spot='Count how many separate copies an attacker must hit; check that the number stays the same after the build.',
        fix_hw=['Keep it this way: run the check again after every change of build tool or setting, on the final netlist.',
                'Consider spreading the copies apart on the chip, so that one laser or electromagnetic shot cannot hit two.'],
        fix_fw=['Keep it this way: run the check again for every compiler setting you ship.']),
    'no_answer': dict(
        tag='', title='We could not get an answer',
        text='The run ended without deciding the question, so nothing is known about this check: it is neither safe '
             'nor unsafe.',
        spot='Read the reason first. A run without an answer is not a pass.',
        fix_hw=[], fix_fw=[]),
    'none_found': dict(
        tag='', title='No way in found within the limits',
        text='Within the number of glitches and steps that were tried, nothing worked.',
        spot='A "none found" only covers the limits shown; raise them to learn more.',
        fix_hw=[], fix_fw=[]),
}
NOT_APPLICABLE = {'hardware': ('aliasing', 'delay_only'), 'chip': ('aliasing', 'delay_only'), 'firmware': ()}


def severity(min_faults, gain, protection='present', label=None, gain_guessed=False):
    """-> dict(level, icon, rank, rationale[...], ...). min_faults: int, 0 for 'without any fault', None for none found."""
    if gain in GAINS:
        g, gtext = GAINS[gain]
    else:                              # no goal given and none could be guessed: say what happens, claim no gain
        g, gtext = 2, 'could make the checked condition happen (what that gives an attacker was not stated)'
    why = []
    if min_faults is None:
        lv = 0
        why.append('No way in was found within the limits that were checked.')
    elif min_faults == 0:
        lv = 3
        why.append('No glitch was needed at all: ordinary use already does it (a bug, or a missing must-hold condition).')
    else:
        table = {1: {3: 4, 2: 3, 1: 2}, 2: {3: 3, 2: 2, 1: 1}}
        lv = table.get(min_faults, {3: 2, 2: 1, 1: 1})[g]
        why.append('%d glitch%s needed%s.' % (min_faults, '' if min_faults == 1 else 'es',
                                             ' (the easiest kind)' if min_faults == 1 else ''))
        why.append('An attacker %s%s.' % (gtext, (' (%s)' % GUESS_NOTE) if gain_guessed else ''))
        why.append('Equipment: a voltage or clock glitch setup counts as "standard" equipment in the JIL smartcard rating '
                   'tables (Table 10); published PSA examples rate one required glitch at 20 points and two at about 21 '
                   'to 23.' if min_faults <= 2 else 'No published rating example covers three or more required glitches, '
                   'so none is claimed.')
        if protection == 'removed':
            lv = min(4, lv + 1)
            why.append('A protection written in the source was removed by the build tool or compiler, so the designer '
                       'may believe it is there (one level up).')
        elif protection == 'weaker':
            why.append('A protection is there but weaker than intended.')
    level = LEVELS[lv]
    if label in ('BOUNDED', 'SAMPLED'):
        why.append('Result %s: the real answer might be worse or better than shown.' % label.lower())
    real = None
    if min_faults:
        real = '%s It %s.' % (WHO.get(min(min_faults, 3)), gtext.replace('could ', 'would let them '))
        real = real.replace('It would let them', 'If it works, they')
        real = real.replace('If it works, they ', 'If it works, they ')
    elif min_faults == 0:
        real = 'Anyone using the device normally could trigger it; no equipment is needed.'
    cmp_ = COMPARE.get(gain) if min_faults and min_faults <= 2 and not gain_guessed else None
    return dict(level=level, rank=LEVELS.index(level), icon=ICON[level], css=COLOUR[level], rationale=why,
                real_life=real, comparison=dict(text=cmp_[0], lesson=cmp_[1]) if cmp_ else None, urgency=URGENCY[level],
                estimate_note='This is our estimate for a modelled fault on a simulated design, not a measured attack on '
                              'real hardware.', gain=gain)


# Why a run gave no answer, in plain words, and what to try. Keys: the verdicts and statuses of every engine.
NO_ANSWER = {
    'VACUOUS': ('The must-hold conditions can never all be true at once, so the question is empty: no run, with or '
                'without glitches, is allowed by them.',
                'Check each must-hold condition on its own (one of them is probably always false or contradicts '
                'another), correct it, then run again.'),
    'UNDECIDED': ('The search stopped before it could decide: it ran out of time, or the solver gave up.',
                  'Give the search more time, lower the number of glitches or clock steps, or check a smaller part of '
                  'the design, then run again.'),
    'TIMEOUT': ('The search ran out of time before it could decide.',
                'Give the search more time, lower the number of glitches or clock steps, or check a smaller part of '
                'the design, then run again.'),
    'UNKNOWN': ('The solver could not decide this question.',
                'Lower the number of glitches or clock steps, or check a smaller part of the design, then run again.'),
    'NOT_RUN': ('This check was not run.',
                'Fix the reason given (often the design could not be built into gates), then run again.'),
    'ERROR': ('The tool stopped with an error before it could answer.',
              'Read the error message in the technical details, fix its cause, then run again.'),
    'STOPPED': ('The run was stopped before it finished.', 'Start the run again and let it finish.'),
}
DECIDED = ('ATTACK_FOUND', 'FAILS_WITHOUT_FAULTS', 'NO_ATTACK_UP_TO_BOUND')


def no_answer_reason(verdict, detail=None):
    """(why, what to try) in plain words for a verdict that is not an answer."""
    if verdict in NO_ANSWER:
        why, todo = NO_ANSWER[verdict]
    elif not verdict:
        why, todo = NO_ANSWER['ERROR']
    else:
        why, todo = 'The run ended with "%s", which is not an answer.' % verdict, NO_ANSWER['ERROR'][1]
    if detail:
        why = '%s Reason given by the tool: %s.' % (why, str(detail).strip().rstrip('.')[:300])
    return why, todo


def unknown_severity(verdict, detail=None):
    """Severity block of a run that gave no answer: 'Unknown - not checked', never Info or Low."""
    why, todo = no_answer_reason(verdict, detail)
    return dict(level=UNKNOWN, words=UNKNOWN_WORDS, rank=UNKNOWN_RANK, icon=ICON[UNKNOWN], css=COLOUR[UNKNOWN],
                rationale=['We could not get an answer, so this check says nothing about whether the design is safe.', why],
                real_life=None, comparison=None, urgency=URGENCY[UNKNOWN],
                estimate_note='No answer was computed, so there is no estimate for this check.', gain=None,
                no_answer=dict(verdict=verdict, why=why, try_next=todo))


def no_answer_finding(domain, subject, verdict, detail, check_cmd, question, tech=None, fid=None, lesson=8):
    """The finding of an inconclusive run: 'We could not get an answer', why in plain words, what to try."""
    sev = unknown_severity(verdict, detail)
    why, todo = sev['no_answer']['why'], sev['no_answer']['try_next']
    statement = 'We could not get an answer for "%s". %s' % (str(subject).rstrip('. '), why)
    steps = [
        'The question: %s' % question,
        'What was tried: the search was started, but it did not finish with an answer.',
        'What was found: no answer (%s).' % (verdict or 'error'),
        'Before and after: there is no glitched run to compare.',
        'Why there is no answer: %s' % why,
        'How the tool knows: it does not. Nothing was proved or found for this check. What to try: %s' % todo,
    ]
    where = dict(text='No place: the run gave no answer', signal=None, file=None, line=None, cycle=None,
                 available=False, missing_note=None)
    return make(domain, statement, sev, _pattern('no_answer', domain, 'yes', why), where, 'NO_ANSWER', [todo], check_cmd,
                steps, [], 'No answer, so no trace.', replay=dict(cmd=check_cmd, replayed=False), predict=None,
                lesson=lesson, patterns=[], tech=dict(tech or {}, verdict=verdict), fid=fid)


_EVID = {'copies_held': 'the fewest glitches found is more than one, and no build removed a copy',
         'none_found': 'nothing worked within the limits', 'no_fault_needed': 'ordinary use already reaches the bad outcome',
         'unprotected_alarm': 'the goal is "the copies disagree and the alarm stays silent", and one glitch reaches it'}


def _pattern(pid, domain, detected, evidence):
    p = PATTERNS[pid]
    return dict(id=pid, tag=p['tag'], title=p['title'], text=p['text'], detected=detected, evidence=evidence,
                spot=p['spot'])


def checked_patterns(domain, found):
    """The (a)-(d) list for a finding: which were seen, which cannot be told from this data, which do not apply."""
    out = []
    for pid in ('removed_redundancy', 'aliasing', 'delay_only', 'single_point'):
        if pid in found:
            out.append(dict(id=pid, tag=PATTERNS[pid]['tag'], title=PATTERNS[pid]['title'], status=found[pid]))
        elif pid in NOT_APPLICABLE.get(domain, ()):
            out.append(dict(id=pid, tag=PATTERNS[pid]['tag'], title=PATTERNS[pid]['title'],
                            status='does not apply (this pattern is about compiled code)'))
        else:
            out.append(dict(id=pid, tag=PATTERNS[pid]['tag'], title=PATTERNS[pid]['title'], status='not seen in this data'))
    return out


def make(domain, statement, sev, why, where, sure_label, fixes, check_cmd, steps, trace=None, trace_note=None,
         replay=None, predict=None, lesson=None, patterns=None, tech=None, fid=None):
    pid = why['id']
    return dict(
        id=fid or pid, domain=domain, severity=sev, statement=statement, why=why, where=where,
        sure=dict(label=sure_label, plain=SURE.get(sure_label, sure_label)),
        next=dict(fixes=fixes, check_cmd=check_cmd),
        how=dict(steps=steps, trace=trace or [], trace_note=trace_note if not trace else None, replay=replay,
                 predict=predict, lesson=lesson, spot_next=PATTERNS[pid]['spot']),
        patterns=patterns or [], tech=tech or {})


def summary_line(findings):
    """'2 critical, 1 medium - start with the critical one: ...'"""
    if not findings:
        return 'No findings.'
    counts = {}
    for f in findings:
        counts[f['severity']['level']] = counts.get(f['severity']['level'], 0) + 1
    parts = ['%d %s' % (counts[lv], lv.lower()) for lv in reversed(LEVELS) if counts.get(lv)]
    nu = counts.get(UNKNOWN, 0)          # runs without an answer: counted on their own, never "nothing to fix"
    if nu:
        parts.append('%d with no answer' % nu)
    ranked = sorted((f for f in findings if f['severity']['level'] != UNKNOWN), key=lambda f: -f['severity']['rank'])
    top = ranked[0] if ranked else None
    unk = next((f for f in findings if f['severity']['level'] == UNKNOWN), None)
    if unk and (top is None or top['severity']['level'] in ('Info', 'Low')):
        return '%s. We could not get an answer for %s; that is not a pass. Start there: %s' % (
            ', '.join(parts), 'one check' if nu == 1 else '%d checks' % nu, unk['statement'])
    if top['severity']['level'] == 'Info':
        return ', '.join(parts) + ': nothing to fix within the limits that were checked.'
    return '%s. Start with the %s one: %s%s' % (', '.join(parts), top['severity']['level'].lower(), top['statement'],
                                              (' (%d check%s gave no answer; that is not a pass.)' % (nu, '' if nu == 1 else 's'))
                                              if nu else '')


_NUM = {1: 'One', 2: 'Two', 3: 'Three', 4: 'Four', 5: 'Five'}


def _plural(n, w):
    return '%d %s%s' % (n, w, '' if n == 1 else ('es' if w.endswith('ch') else 's'))


# ======================================================================== own-design tool (glitchsat run report)

# The goal each template stands for (the same table as glitchsat_byod.templates.GOAL; repeated here so that older
# reports without a `goal` field are read the same way).
TEMPLATE_GOAL = {'secure_boot_wrong_key': 'boot_accept', 'debug_unlock_locked': 'debug_unlock', 'key_to_output': 'key_leak',
                 'alarm_suppressed': 'alarm_suppress', 'counter_skip': 'state_change', 'fsm_forbidden_state': 'state_change'}

# Last resort only: whole words of the check's id and condition (never parts of words: "clock" is not "lock",
# "stage" is not "tag", "decode" is not "code").
_GUESS_WORDS = ((('key', 'keys', 'secret', 'secrets', 'leak', 'leaks'), 'key'), (('boot',), 'boot'),
                (('debug', 'jtag'), 'debug'), (('unlock', 'unlocked', 'lock', 'locked', 'open', 'opens'), 'unlock'),
                (('alarm', 'alert'), 'alarm'))


def guess_gain(*names):
    """Gain guessed from whole words of names (split at anything that is not a letter or digit), or None."""
    words = set()
    for n in names:
        words.update(w for w in re.split(r'[^a-z0-9]+', str(n or '').lower()) if w)
    for ws, g in _GUESS_WORDS:
        if words.intersection(ws):
            return g
    return None


def gain_for_check(c):
    """-> (gain or None, source): source 'stated' (the check's goal), 'template' (the template's goal), 'guessed' (from
    whole words of the names; the card asks to confirm) or None (nothing is claimed)."""
    goal = (c.get('goal') or '').strip()
    if goal in GOALS:
        return GOALS[goal], ('template' if c.get('goal_source') == 'template' else 'stated')
    t = (c.get('template') or '').strip()
    if t in TEMPLATE_GOAL:
        return GOALS[TEMPLATE_GOAL[t]], 'template'
    g = guess_gain(c.get('id'), c.get('bad'))
    return (g, 'guessed') if g else (None, None)


def lint_evidence(merge_lint):
    """Pattern (a) from the merge lint. 'yes' only for a protection named in the source that the as-written build has
    (first stage SURVIVED) and a later build lacks (REMOVED / WEAKENED). A protection already missing in the
    as-written build was never built in this configuration: not evidence of removal. -> (yes[], not_built[], removed?)"""
    yes, not_built, removed = [], [], False
    for cm in (merge_lint or {}).get('countermeasures') or []:
        st = cm.get('stages') or []
        if not st:
            continue
        first = (st[0].get('verdict') or '').strip()
        later = [x for x in st[1:] if (x.get('verdict') or '').strip() in ('REMOVED', 'WEAKENED')]
        if first == 'SURVIVED' and later:
            yes.append('%s: in the as-written build "%s", %s in build %s' % (
                cm.get('title'), st[0].get('stage'), later[0]['verdict'], later[0].get('stage')))
            removed = removed or any(x['verdict'].strip() == 'REMOVED' for x in later)
        elif first in ('REMOVED', 'WEAKENED'):
            not_built.append('%s: already %s in the as-written build "%s" (not built in this configuration)' % (
                cm.get('title'), first, st[0].get('stage')))
    return yes, not_built, removed


def from_byod_check(c, rep, project_file='glitchsat.yaml', task=None):
    """One finding per check of a `glitchsat run` report (report.json structure)."""
    A = c.get('analyses') or {}
    mf = A.get('min_faults') or {}
    v = mf.get('verdict') if c.get('status') != 'NOT_RUN' else 'NOT_RUN'
    cmd = 'glitchsat run %s%s' % (project_file, (' --task ' + task) if task else '')
    if v not in DECIDED:                 # empty question, out of time, not run, solver gave up, tool error: no answer
        detail = mf.get('why') or c.get('why') or mf.get('error') or (mf.get('status') if mf.get('status') not in (None, v) else None)
        return no_answer_finding('hardware', c.get('explain') or c.get('bad') or c.get('id'), v, detail, cmd,
                                 'can up to %s make "%s" happen within %s clock steps after reset?' % (
                                     _plural(c.get('max_faults') or 0, 'glitch'), c.get('bad'), c.get('horizon')),
                                 tech=dict(check=c.get('id'), min_faults=None), fid='%s:no_answer' % c.get('id'))
    gain, gsrc = gain_for_check(c)
    w = mf.get('witness') or {}
    found, prot = {}, 'present'
    sv = (A.get('survival') or {}).get('rows') or []
    nums = {r['flow']: r.get('min_faults') for r in sv if isinstance(r.get('min_faults'), int)}
    yes, not_built, rem = lint_evidence(A.get('merge_lint'))
    counts = ['%s build: %s' % (k, _plural(n, 'glitch')) for k, n in nums.items()]
    if yes:                              # direct evidence: a protection named in the source is missing after the build
        found['removed_redundancy'] = 'yes: ' + '; '.join((yes + counts)[:4])
        prot = 'removed' if rem else 'weaker'
    elif nums and len(set(nums.values())) > 1:
        found['removed_redundancy'] = ('maybe: %s (fewer glitches after a build step, but no protection from the source '
                                       'was found missing)' % '; '.join(counts[:4]))
    elif not_built:
        found['removed_redundancy'] = 'cannot tell: ' + '; '.join(not_built[:3])
    m = mf.get('min_faults') if v == 'ATTACK_FOUND' else (0 if v == 'FAILS_WITHOUT_FAULTS' else None)
    weak = min(nums.items(), key=lambda kv: kv[1]) if nums else None      # the weakest build decides how bad it is
    msev = min(m, weak[1]) if (m and weak) else m
    faults = w.get('faults') or []
    if m == 1 and faults:
        found['single_point'] = 'yes: one glitch on %s is enough' % faults[0]['site']
    if v == 'FAILS_WITHOUT_FAULTS':
        pid = 'no_fault_needed'
    elif v != 'ATTACK_FOUND':
        pid = 'none_found'
    elif str(found.get('removed_redundancy', '')).startswith('yes') and prot == 'removed':
        pid = 'removed_redundancy'
    elif 'single_point' in found:
        pid = 'single_point'
    elif str(found.get('removed_redundancy', '')).startswith('yes'):
        pid = 'removed_redundancy'
    else:
        pid = 'single_point' if m == 1 else 'copies_held'
    sev = severity(msev, gain, prot, 'BOUNDED' if v == 'ATTACK_FOUND' and not mf.get('proved_minimum') else None,
                   gain_guessed=(gsrc == 'guessed'))
    sev['gain_source'] = gsrc
    horizon, kmax = c.get('horizon'), c.get('max_faults')
    if v == 'ATTACK_FOUND':
        what = (c.get('explain') or c.get('bad') or '').rstrip('. ')
        statement = ('One well-timed glitch can make this happen: %s.' % what if m == 1 else
                     '%s well-timed glitches, all landing right, can make this happen: %s.' % (_NUM.get(m, str(m)), what))
        if weak and weak[1] < m:
            statement += ' After the build "%s", %s enough.' % (weak[0], 'one glitch is' if weak[1] == 1 else '%d glitches are' % weak[1])
    elif v == 'FAILS_WITHOUT_FAULTS':
        statement = 'The design does "%s" without any glitch at all.' % (c.get('explain') or c.get('bad'))
    else:
        statement = 'No way was found to make "%s" happen with up to %s within %s cycles.' % (
            c.get('explain') or c.get('bad'), _plural(kmax or 0, 'glitch'), horizon)
    where_bits, f0 = [], (faults[0] if faults else None)
    if f0:
        where_bits = ['%s at clock step %d%s' % (f['site'], f['cycle'], (' (%s)' % f['src']) if f.get('src') else '') for f in faults]
    src = next((f.get('src') for f in faults if f.get('src')), None)
    fl, ln = None, None
    if src:
        mm = re.match(r'(.+?):(\d+)', src)
        if mm:
            fl, ln = mm.group(1), int(mm.group(2))
    where = dict(text='; '.join(where_bits) if where_bits else 'No single place: %s' % ('ordinary use triggers it' if m == 0 else 'nothing was found'),
                 signal=f0['site'] if f0 else None, file=fl, line=ln, cycle=f0['cycle'] if f0 else None,
                 hit_cycle=w.get('hit_cycle'), available=bool(f0),
                 missing_note=None if src or not f0 else 'No source line is known for this spot (it is a gate the build '
                                                         'tool made); its name in the gate list is shown instead.')
    fixes = list(PATTERNS[pid]['fix_hw']) or ['Nothing to fix for this question; raise the limits to learn more.']
    for t in (c.get('what_to_do') or [])[:3]:
        if t.get('text') and t['text'] not in fixes:
            fixes.append(t['text'])
    steps = [
        'The question: can %s make "%s" happen within %s clock steps after reset%s?' % (
            'up to ' + _plural(kmax or 0, 'glitch'), c.get('bad'), horizon,
            (' while "%s" stays true' % ' and '.join(c['must_hold'])) if c.get('must_hold') else ''),
        'What was tried: every way of flipping one wire or one memory cell for one clock step, then two, and so on '
        '(the fault model), on the chip plan of each build.',
        ('What was found: %s.' % '; '.join(where_bits)) if where_bits else (
            'What was found: the bad outcome happens with no glitch at all.' if m == 0 else 'What was found: nothing within the limits.'),
        'Before and after: %s' % ('the run with the glitch reaches the bad outcome at clock step %s; the same inputs '
                                  'without the glitch do not (replayed on a gate-level simulator: %s).' % (
                                      w.get('hit_cycle'), 'yes' if w.get('replayed') else 'NO') if f0 else 'no glitched run to compare.'),
        'Why that breaks the protection: %s' % PATTERNS[pid]['text'],
        'How the tool knows: %s Not checked: more glitches or longer runs than the limits, other fault kinds, the '
        'placed layout.' % (('The solver searched every combination up to this size and proved none smaller works.'
                              if mf.get('proved_minimum') else SURE['MEASURED']) if v == 'ATTACK_FOUND' else SURE['MEASURED']),
    ]
    trace = []
    for p, iv in (w.get('inputs') or {}).items():
        trace.append(dict(name='input %s' % p, normal=', '.join(map(str, iv.get('values') or [])), glitched='same'))
    for f in faults:
        trace.append(dict(name=f['site'], normal='its normal value', glitched='%s at clock step %d' % (f.get('type', 'flipped'), f['cycle'])))
    return make('hardware', statement, sev, _pattern(pid, 'hardware', 'yes', found.get(pid) or _EVID.get(pid)),
                where, 'MEASURED' if v != 'ATTACK_FOUND' or mf.get('proved_minimum') else 'BOUNDED', fixes, cmd, steps, trace,
                'The run keeps the inputs and the glitch positions, not every internal value; the trace shows those.',
                replay=dict(cmd=cmd, replayed=bool(w.get('replayed'))),
                predict='Before you look: how many glitches do you think this needs?', lesson=8,
                patterns=checked_patterns('hardware', found), tech=dict(check=c.get('id'), verdict=v, min_faults=m),
                fid='%s:%s' % (c.get('id'), pid))


def from_byod_report(rep, project_file=None):
    pf = project_file or (rep.get('project') or 'glitchsat.yaml')
    return [from_byod_check(c, rep, os.path.basename(pf), rep.get('task')) for c in rep.get('checks') or []]


# ======================================================================== Studio path (built-in locks)

# The goals of the built-in study (the Studio's path): what the attacker gets is part of the study definition.
STUDY_GOALS = {
    'word': dict(goal='lock_bypass', did='make the lock accept a wrong key', one='makes the lock accept a wrong key',
                 question='make the lock say "open" (its whole 8-signal answer) for a wrong key'),
    'flag': dict(goal='lock_bypass', did='make the one "open" signal say yes for a wrong key, while the lock itself '
                 'stays shut (the rest of the chip reads only that signal)',
                 one='makes the one "open" signal say yes for a wrong key, while the lock itself stays shut (the rest of '
                 'the chip reads only that signal)',
                 question='make the one "open" signal say yes for a wrong key'),
}


def from_studio_result(r, q=None):
    """r: an /api/analyze result. q: the query (design, goal). Uses the replay for the before/after trace.
    r['_ref'] (optional, from the Studio): the stored chip plan of the same design for the same goal and limits."""
    q = q or {}
    v = r.get('verdict')
    k, N = r.get('_k'), r.get('_cycles')
    gk = 'flag' if (q.get('goal') or r.get('_goal')) == 'flag' else 'word'
    SG = STUDY_GOALS[gk]
    cmd = (r.get('_prov') or {}).get('cli') or 'python3 scripts/glitchsat.py check (see Technical view for the exact command)'
    if v not in DECIDED:
        stop = (r.get('_stop') or {}).get('why')
        vv = 'STOPPED' if stop == 'stopped' else 'TIMEOUT' if (stop == 'timeout' or 'TIMEOUT' in str(v)) else (v or 'ERROR')
        return [no_answer_finding('hardware', 'can glitches %s' % SG['did'], vv, None, cmd,
                                  'can up to %s %s, within %s steps?' % (_plural(k or 0, 'glitch'), SG['question'], N),
                                  tech=dict(design=q.get('design'), goal=q.get('goal')))]
    atk = v == 'ATTACK_FOUND'
    m = r.get('min_faults') if atk else None
    design = (q.get('design') or '').replace('_rtl', '')
    rebuilt = (q.get('design') or '').endswith('_rtl')
    found, prot = {}, 'present'
    ref = r.get('_ref') or {}
    if rebuilt and m is not None:
        if ref.get('goal') == r.get('_goal', ref.get('goal')) and ref.get('verdict') in DECIDED:
            rm = ref.get('min')
            if rm is None or rm > m:
                found['removed_redundancy'] = ('maybe: the stored chip plan of this design needs %s for the same goal; this '
                                               'rebuilt one needs %d. The build changed the result, but which copy went '
                                               'missing is not shown by this data' % (
                                                   'more than %d' % (k or 0) if rm is None else rm, m))
            else:
                found['removed_redundancy'] = ('not seen: the stored chip plan needs %d for the same goal, the same as '
                                               'this rebuilt one' % rm)
        else:
            found['removed_redundancy'] = 'cannot tell: no stored result of this design for the same goal and limits'
    faults = r.get('faults') or []
    if m == 1 and faults:
        found['single_point'] = 'yes: one glitch on %s decides the outcome' % (faults[0].get('plain') or faults[0].get('net'))
    pid = ('single_point' if 'single_point' in found else 'none_found' if not atk else 'copies_held')
    label = 'RECORDED' if r.get('_src') == 'recorded' else 'LIVE'
    sev = severity(m, GOALS[SG['goal']], prot, None)
    sev['gain_source'] = 'study'
    if atk:
        statement = ('One well-timed glitch %s.' % SG['one'] if m == 1 else
                     '%s well-timed glitches, all landing right, %s.' % (['', 'One', 'Two', 'Three', 'Four'][min(m, 4)], SG['did']))
    else:
        statement = 'No way in was found with up to %s within %s steps.' % (_plural(k or 0, 'glitch'), N)
    rp = r.get('_replay') or {}
    trace = []
    t = rp.get('opens_at')
    if t is not None:
        for row in rp.get('rows') or []:
            if row.get('id') == 'sig':
                continue
            a, c = row.get('attack') or [], row.get('clean') or []
            if t < len(a) and t < len(c) and a[t] != c[t]:
                nm = row.get('names') or {}
                trace.append(dict(name=row.get('plain') or row.get('tech'), tech=row.get('tech'),
                                  normal=nm.get(str(c[t]), str(c[t])), glitched=nm.get(str(a[t]), str(a[t]))))
    where = dict(text='; '.join('%s at step %s' % (f.get('plain') or f.get('net'), f.get('cycle')) for f in faults) or 'nothing found',
                 signal=faults[0].get('net') if faults else None, file=None, line=None,
                 cycle=faults[0].get('cycle') if faults else None, hit_cycle=t, available=bool(faults),
                 missing_note='The built-in locks are drawn from their chip plan; the circuit map under "See how" shows the spot.' if faults else None)
    steps = [
        'The question: can up to %s %s, within %s steps?' % (_plural(k or 0, 'glitch'), SG['question'], N),
        'What was tried: every way of flipping wires or memory cells, one step each, for every wrong key.',
        'What was found: %s.' % (where['text'] if atk else 'nothing within the limits'),
        'Before and after: %s' % ('same wrong key, with and without the glitch, at step %s: %s.' % (
            t, '; '.join('%s %s instead of %s' % (x['name'], x['glitched'], x['normal']) for x in trace[:3])) if trace else
            'the replay of this result is not available here.'),
        'Why that breaks the protection: %s' % PATTERNS[pid]['text'],
        'How the tool knows: %s Not checked: more glitches or steps than the limits, other chip plans, the layout.' % SURE[label],
    ]
    return [make('hardware', statement, sev, _pattern(pid, 'hardware', 'yes', found.get(pid) or _EVID.get(pid)),
                 where, label, list(PATTERNS[pid]['fix_hw']) or ['Nothing to fix within these limits.'],
                 cmd, steps, trace,
                 'No replay is available for this result.', replay=dict(studio='replay this step', replayed=t is not None),
                 predict='Before you look: how many glitches will this lock need?', lesson=8,
                 patterns=checked_patterns('hardware', found), tech=dict(design=q.get('design'), goal=q.get('goal')))]


# ======================================================================== whole chip (soc)

_SOC_GAIN = {'boot_release': 'boot', 'first_fetch': 'boot', 'debug_entry': 'debug', 'debug_entry_silent': 'debug',
             'alarm_suppressed': 'alarm', 'flash_takeover': 'control'}


def _soc_removed(chip, variant, goal):
    """Pattern (a) from the whole-chip inventory: a deliberate protection (reviewed by hand) that SURVIVED in the
    as-written build and is REMOVED / WEAKENED in a later build, with the merge lint for this goal."""
    out = []
    for inv in chip.get('inventory') or []:
        if inv.get('variant') != variant:
            continue
        lint = ((inv.get('merge_lint') or {}).get(goal) or {})
        for r in inv.get('reviewed') or []:
            if not (r.get('note') or '').startswith('Deliberate'):
                continue
            pf = r.get('per_flow') or {}
            if (pf.get('written') or '').strip() != 'SURVIVED':
                continue
            for fl in ('keep', 'flat'):
                v = (pf.get(fl) or '').strip()
                if v in ('REMOVED', 'WEAKENED'):
                    out.append('%s: SURVIVED as written, %s in build %s%s' % (
                        r.get('title'), v, fl, ' (merge lint: copies %s)' % lint[fl] if lint.get(fl) else ''))
    return out


def from_soc_chip(chip):
    """One finding per goal and version of a chip of explore_chip.json (the weakest build first)."""
    out = []
    by = {}
    for v in chip.get('variants') or []:
        for g in v.get('goals') or []:
            by.setdefault((v['variant'], g['id']), []).append((v, g))
    for (vn, gid), rows in by.items():
        nums = []
        for v, g in rows:
            try:
                nums.append((int(g['faults_needed']), v, g))
            except (TypeError, ValueError):
                pass
        if not nums:
            continue
        nums.sort(key=lambda x: x[0])
        m, v, g = nums[0]
        found, prot = {}, 'present'
        if len({n for n, _, _ in nums}) > 1:     # counts differ per build
            counts = ', '.join('%s build %d' % (vv['flow'], n) for n, vv, _ in nums)
            gone = _soc_removed(chip, vn, gid)
            if gone:                             # the inventory names a protection that the as-written build has and a later build lacks
                found['removed_redundancy'] = 'yes: %s; %s' % ('; '.join(gone), counts)
                prot = 'removed' if any(' REMOVED ' in x for x in gone) else 'weaker'
            else:
                found['removed_redundancy'] = ('maybe: %s (the build changes how many glitches are needed; the whole-chip '
                                               'inventory does not name a protection that went missing)' % counts)
        if m == 1:
            found['single_point'] = 'yes: one glitch on %s' % ((g.get('example') or [{}])[0].get('net') or 'one spot')
        gain = _SOC_GAIN.get(gid, 'control')
        pid = ('unprotected_alarm' if gid == 'alarm_suppressed' and m == 1
               else 'single_point' if m == 1 else 'copies_held')
        sev = severity(m, gain, prot, g.get('label'))
        if v.get('note'):                       # e.g. the lockstep chip: a configuration made for this study
            sev['rationale'].append(v['note'])
        ex = g.get('example') or []
        where = dict(text='; '.join('%s at clock step %s' % (e['net'], e['cycle']) for e in ex) or 'not recorded',
                     signal=ex[0]['net'] if ex else None, file=None, line=None, cycle=ex[0]['cycle'] if ex else None,
                     available=bool(ex), missing_note='Whole-chip results keep the gate-list names of the glitched spots, '
                                                      'not source lines.')
        steps = [
            'The question: can up to a few glitches make "%s" happen within %s clock steps after reset?' % (g['title'], g['cycles']),
            'What was tried: the part of the chip that can reach that decision (%s cells of %s) was cut out, and every way '
            'of flipping one or more of its parts for one clock step was searched.' % (g.get('slice_cells'), v.get('cells')),
            'What was found: %s, in the build "%s".' % (where['text'], v.get('flow_plain') or v.get('flow')),
            'Before and after: the attack was replayed on the whole chip and reached the goal; the record keeps the '
            'glitched spots, not every value, so no value trace is shown.',
            'Why that breaks the protection: %s' % PATTERNS[pid]['text'],
            'How the tool knows: %s Not checked: longer runs, other builds, a real cell library.' % SURE.get(g.get('label'), ''),
        ]
        out.append(make('chip', '%s: %s with %s.' % ((v.get('variant_plain') or vn), g['title'], _plural(m, 'glitch')), sev,
                        _pattern(pid, 'chip', 'yes', found.get(pid) or _EVID.get(pid)),
                        where, g.get('label') or 'BOUNDED', list(PATTERNS[pid]['fix_hw']),
                        'python3 tools/soc/glitchsat_soc.py analyse %s --variant %s --goal %s' % (chip.get('id'), vn, gid),
                        steps, [], 'The whole-chip record keeps the glitched spots only.',
                        replay=dict(cmd='python3 tools/soc/glitchsat_soc.py analyse %s --variant %s --goal %s' % (chip.get('id'), vn, gid), replayed=True),
                        predict='Before you look: one glitch, or more?', lesson=8,
                        patterns=checked_patterns('chip', found), tech=dict(variant=vn, goal=gid, flow=v.get('flow')),
                        fid='%s:%s:%s' % (chip.get('id'), vn, gid)))
    out.sort(key=lambda f: -f['severity']['rank'])
    return out


# ======================================================================== boot program (firmware)

_LOAD = re.compile(r'^(c\.)?l[wdhb]u?\b|^c\.lwsp\b|^ldr', re.I)


def from_firmware(data, variants=None, opt='O2', mode='plain'):
    """One finding per boot-program version (one compiler setting) from the firmware module's Studio file."""
    cells = data.get('cells') or []
    red = {(r['variant'], r['opt'], r['mode']): r for r in data.get('redundancy') or []}
    delay = {r['build']: r for r in (data.get('random_delay') or {}).get('rows') or []}
    out = []
    for c in cells:
        if c.get('mode') != mode or c.get('opt') != opt or (variants and c['variant'] not in variants):
            continue
        try:
            m = int(c.get('tampered'))
        except (TypeError, ValueError):
            m = None
        w = c.get('witness') or []
        found, prot = {}, 'present'
        r0, rx = red.get((c['variant'], 'O0', mode)), red.get((c['variant'], opt, mode))
        m0 = next((x.get('tampered') for x in cells if (x['variant'], x.get('opt'), x.get('mode')) == (c['variant'], 'O0', mode)), None)
        try:
            m0 = int(m0)
        except (TypeError, ValueError):
            m0 = None
        if opt != 'O0' and r0 and rx and rx.get('mac_compares', 0) < r0.get('mac_compares', 0):
            a0, ax = float(r0['mac_compares']), float(rx['mac_compares'])
            if a0 != int(a0) or ax != int(ax):
                # the count is word loads of the compare / 8: a fraction is a merged load, not a missing compare
                found['removed_redundancy'] = ('cannot tell: %g compare-loads at -O0, %g at -%s; a fraction means a '
                                               'merged load, not a missing compare' % (a0, ax, opt))
            elif m is not None and m0 is not None and m < m0:
                found['removed_redundancy'] = ('yes: the check is compiled %d times at -O0 (as written) but only %d '
                                               'time%s at -%s; this build needs %d fault%s, -O0 needs %d'
                                               % (a0, ax, '' if ax == 1 else 's', opt, m, '' if m == 1 else 's', m0))
                prot = 'removed'
            else:
                found['removed_redundancy'] = ('maybe: %d compares at -O0, %d at -%s, but this build does not need fewer '
                                               'faults than -O0' % (a0, ax, opt))
        if m == 1 and w and w[0].get('model') == 'skip' and _LOAD.match(w[0].get('asm') or ''):
            found['aliasing'] = ('likely: the skipped instruction is a load (%s); the stored result does not keep register '
                                 'values, so it cannot be confirmed that two values became the same' % w[0]['asm'].replace('\t', ' '))
        dk = sorted((b for b in delay if b.startswith(c['variant'] + '-')), key=lambda b: (not b.startswith('%s-%s-%s' % (c['variant'], opt, mode)), b))
        nseeds = (data.get('random_delay') or {}).get('seeds')
        if 'delay' in c['variant'] and dk:
            d = delay[dk[0]]
            if nseeds and d.get('seeds_with_any_single_skip') == nseeds:
                found['delay_only'] = 'yes: in all %s random-delay runs one skipped instruction still worked' % d.get('seeds_with_any_single_skip')
            else:
                found['delay_only'] = 'not seen: some random-delay runs resisted one skip'
        elif 'delay' in c['variant']:
            found['delay_only'] = 'cannot tell from this data (no random-delay runs stored)'
        if m == 1 and w and w[0].get('model') == 'brinv':
            found['single_point'] = 'yes: inverting one branch (%s) is enough' % w[0]['asm'].replace('\t', ' ')
        elif m == 1 and w:
            found['single_point'] = 'yes: one fault at one instruction is enough'
        order = ['removed_redundancy', 'delay_only', 'aliasing', 'single_point']
        pid = next((p for p in order if p in found and not str(found[p]).startswith(('not seen', 'cannot', 'maybe'))), None)
        if m is None:
            pid = 'none_found'
        elif pid is None:
            pid = 'single_point' if m == 1 else 'copies_held'
        sev = severity(m, 'boot', prot, 'SAMPLED' if pid == 'delay_only' else None)
        h = w[0] if w else {}
        where = dict(text=('%s line %s, instruction %s (%s), %s' % (h.get('file'), h.get('line'), h.get('pc'),
                                                                   (h.get('asm') or '').replace('\t', ' '), h.get('effect'))) if h else 'not recorded',
                     file=h.get('file'), line=h.get('line'), instruction=(h.get('asm') or '').replace('\t', ' ') or None,
                     pc=h.get('pc'), cycle=None, available=bool(h),
                     missing_note=None if h else 'This result keeps no instruction position.')
        mt = (data.get('model_text') or {}).get(h.get('model'), h.get('model'))
        steps = [
            'The question: can one or more faults make the boot program start a tampered program (one byte changed)?',
            'What was tried: every single fault of each kind (%s) at every instruction the program runs, then two.' % ', '.join(
                (data.get('model_text') or {}).values()),
            'What was found: %s.' % (('%s at %s' % (mt, where['text'])) if h else 'nothing within the limits'),
            'Before and after: without the fault the tampered program is refused; with it, it runs (replayed on a fresh '
            'simulator). Register values are not stored, so no value trace is shown.',
            'Why that breaks the protection: %s' % PATTERNS[pid]['text'],
            'How the tool knows: %s Not checked: real silicon, faults of two kinds at once.' % SURE['SIMULATED'],
        ]
        stmt = ('One well-timed fault makes the boot program start a tampered program (version %s).' % c['variant'] if m == 1 else
                '%s well-timed faults make the boot program start a tampered program (version %s).' % (_NUM.get(m, m), c['variant'])
                if m else 'No way was found to make the boot program start a tampered program (version %s).' % c['variant'])
        out.append(make('firmware', stmt,
                        sev, _pattern(pid, 'firmware', 'likely' if pid == 'aliasing' else 'yes', found.get(pid) or _EVID.get(pid)), where,
                        'SAMPLED' if pid == 'delay_only' else 'SIMULATED', list(PATTERNS[pid]['fix_fw']) or ['Nothing to fix within these limits.'],
                        'python3 tools/firmware/scripts/run_faults.py --set main', steps, [], 'Register values are not stored.',
                        replay=dict(cmd='python3 -m pytest -q tools/firmware/tests/test_results.py', replayed=True),
                        predict='Before you look: how many faults does this version need?', lesson=6,
                        patterns=checked_patterns('firmware', found), tech=dict(variant=c['variant'], opt=opt, mode=mode),
                        fid='%s-%s-%s' % (c['variant'], opt, mode)))
    out.sort(key=lambda f: -f['severity']['rank'])
    return out


# ======================================================================== text and SARIF

def to_text(findings, width=110):
    import textwrap
    L = ['What we found and what it means', '-' * 31, summary_line(findings)]
    for i, f in enumerate(findings, 1):
        s = f['severity']
        L.append('')
        L.append('%d. [%s %s] %s' % (i, s['icon'], (s.get('words') or s['level']).upper(), f['statement']))
        for lab, txt in (('Why it matters', ' '.join(s['rationale'])), ('In real life', s.get('real_life')),
                         ('Real-world comparison', (s.get('comparison') or {}).get('text')), ('How urgent', s['urgency']),
                         ('Why it happened', '%s %s: %s' % (f['why']['tag'], f['why']['title'], f['why']['text'])),
                         ('Where', f['where']['text'] + ((' (' + f['where']['missing_note'] + ')') if f['where'].get('missing_note') else '')),
                         ('How sure', f['sure']['plain']), ('What to do', ' | '.join(f['next']['fixes'])),
                         ('How to check the fix', f['next']['check_cmd'])):
            if txt:
                L += textwrap.wrap('%s: %s' % (lab, txt), width, initial_indent='   ', subsequent_indent='     ')
        for cl in (f['where'].get('context') or []):
            L.append('     %4d %s %s' % (cl['line'], '>' if cl['hit'] else ' ', cl['text']))
        L.append('   How we found it:')
        for j, st in enumerate(f['how']['steps'], 1):
            L += textwrap.wrap('%d) %s' % (j, st), width, initial_indent='     ', subsequent_indent='        ')
        L += textwrap.wrap('Spot it next time: ' + f['how']['spot_next'], width, initial_indent='   ', subsequent_indent='     ')
        L.append('   (%s)' % s['estimate_note'])
    return '\n'.join(L)


SARIF_LEVEL = {'Critical': 'error', 'High': 'error', 'Medium': 'warning', 'Low': 'note', 'Info': 'none', UNKNOWN: 'warning'}


def to_sarif(findings, tool='glitchsat', version='', uri_base=None):
    """SARIF 2.1.0 log: one result per finding, the plain text as message, the how-steps as a threadFlow."""
    results = []
    for f in findings:
        loc = None
        if f['where'].get('file'):
            loc = dict(physicalLocation=dict(artifactLocation=dict(uri=f['where']['file']),
                                             region=dict(startLine=int(f['where'].get('line') or 1))))
        tf = [dict(location=dict(message=dict(text=st), **({'physicalLocation': loc['physicalLocation']} if loc and j == 2 else {})))
              for j, st in enumerate(f['how']['steps'])]
        res = dict(ruleId=f['why']['id'], level=SARIF_LEVEL[f['severity']['level']],
                   message=dict(text='[%s] %s %s What to do: %s How to check the fix: %s' % (
                       f['severity']['level'], f['statement'], f['severity'].get('real_life') or '',
                       ' '.join(f['next']['fixes'][:2]), f['next']['check_cmd'])),
                   codeFlows=[dict(threadFlows=[dict(locations=tf)])],
                   properties=dict(severity=f['severity']['level'], sure=f['sure']['label'], estimate=f['severity']['estimate_note']))
        if loc:
            res['locations'] = [loc]
        results.append(res)
    rules = [dict(id=pid, name=p['title'], shortDescription=dict(text=p['title']), fullDescription=dict(text=p['text']),
                  help=dict(text=p['spot'])) for pid, p in PATTERNS.items()]
    return dict(version='2.1.0', **{'$schema': 'https://json.schemastore.org/sarif-2.1.0.json'},
                runs=[dict(tool=dict(driver=dict(name=tool, version=version, rules=rules)), results=results)])


def severity_doc():
    L = ['# How we decide severity', '', 'Written from `SEVERITY_RULES` in `plain_findings.py` (one source for the app, '
         'the reports and this page).', '', '| rule | how it works |', '|---|---|']
    L += ['| %s | %s |' % (a, b) for a, b in SEVERITY_RULES]
    L += ['', '| level | icon | how urgent |', '|---|---|---|'] + ['| %s | `%s` | %s |' % (lv, ICON[lv], URGENCY[lv]) for lv in reversed(LEVELS)]
    L += ['| %s | `%s` | %s |' % (UNKNOWN_WORDS, ICON[UNKNOWN], URGENCY[UNKNOWN])]
    L += ['', 'Patterns:', ''] + ['- %s **%s**: %s Spot it next time: %s' % (p['tag'], p['title'], p['text'], p['spot']) for p in PATTERNS.values()]
    return '\n'.join(L) + '\n'


if __name__ == '__main__':
    import sys
    if sys.argv[1:2] == ['doc']:
        open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'SEVERITY.md'), 'w').write(severity_doc())
        print('wrote SEVERITY.md')
    elif sys.argv[1:2] == ['report'] and len(sys.argv) > 2:
        rep = json.load(open(sys.argv[2]))
        print(to_text(from_byod_report(rep)))
