"""GlitchSAT Labs: the common result format "labs-result/1" (own code, Apache-2.0).

Every Labs module writes ONE JSON file, results/labs_result.json, with this shape:

{
  "schema":   "labs-result/1",
  "module":   "masking" | "bootloader" | "opentitan_prims" | ...,
  "title":    short plain-language name,
  "status":   "EXPERIMENTAL" | "PLANNED",
  "question": what the module tries to answer, in plain words,
  "example":  {"name": ..., "description": ..., "command": ...},
  "findings": [ {"id": ..., "text": plain-language finding, "label": "MEASURED" | "SIMULATED" | "UNTESTED",
                 "experimental": true, "evidence": {...free-form numbers...}} ],
  "labels":   {"MEASURED": ..., "SIMULATED": ..., "UNTESTED": ...}   (legend, same text in every file),
  "caveats":  [plain-language limits],
  "run":      {"started": ISO time, "seconds": float, "tools": {...}, "ok": bool, "errors": [...]},
  "readme":   path of the module README, relative to the module folder
}

Label meaning (also in ext/labs/README.md):
  MEASURED   counted or computed by running real tools (Yosys, clang, the simulator) on real inputs here
  SIMULATED  the outcome of a model run (fault simulator, probing model); a model, not silicon
  UNTESTED   stated or expected, but not checked by any run in this module yet
Every finding is EXPERIMENTAL: "experimental" is always true and status is never anything stronger.
"""
import datetime
import json
import os

SCHEMA = 'labs-result/1'
LABELS = {
    'MEASURED': 'counted or computed by running real tools on real inputs in this module',
    'SIMULATED': 'the outcome of a model (fault simulator or probing model); a model, not silicon',
    'UNTESTED': 'stated or expected, but not checked by any run in this module yet',
}
STATUSES = ('EXPERIMENTAL', 'PLANNED')
KEYS = ('schema', 'module', 'title', 'status', 'question', 'example', 'findings', 'labels', 'caveats', 'run', 'readme')


def now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def finding(fid, text, label, **evidence):
    assert label in LABELS, label
    return dict(id=fid, text=text, label=label, experimental=True, evidence=evidence)


def make(module, title, question, example, findings, caveats, run, status='EXPERIMENTAL', readme='README.md'):
    return dict(schema=SCHEMA, module=module, title=title, status=status, question=question, example=example,
                findings=findings, labels=dict(LABELS), caveats=list(caveats), run=run, readme=readme)


def validate(d):
    """Return a list of problems (empty = valid)."""
    p = []
    for k in KEYS:
        if k not in d:
            p.append('missing key %s' % k)
    if p:
        return p
    if d['schema'] != SCHEMA:
        p.append('schema is %r' % d['schema'])
    if d['status'] not in STATUSES:
        p.append('status %r' % d['status'])
    for k in ('name', 'description', 'command'):
        if k not in d['example']:
            p.append('example.%s missing' % k)
    if d['status'] == 'EXPERIMENTAL' and not d['findings']:
        p.append('no findings')
    for f in d['findings']:
        for k in ('id', 'text', 'label', 'experimental', 'evidence'):
            if k not in f:
                p.append('finding %s: %s missing' % (f.get('id'), k))
        if f.get('label') not in LABELS:
            p.append('finding %s: label %r' % (f.get('id'), f.get('label')))
        if f.get('experimental') is not True:
            p.append('finding %s: not marked experimental' % f.get('id'))
    if not d['caveats']:
        p.append('no caveats')
    for k in ('started', 'seconds', 'ok', 'errors'):
        if k not in d['run']:
            p.append('run.%s missing' % k)
    return p


def write(path, d):
    prob = validate(d)
    if prob:
        raise ValueError('labs-result/1 problems: ' + '; '.join(prob))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(d, f, indent=1)
        f.write('\n')
    os.replace(tmp, path)
    return path
