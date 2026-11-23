"""A small JSON Schema validator (the subset used by schema/glitchsat.schema.json), standard library only.
Errors name the key path and say what was expected, so they can be turned into GS002 messages."""
import difflib
import json
import os
import re

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'schema', 'glitchsat.schema.json')
_SCHEMA = None


def schema():
    global _SCHEMA
    if _SCHEMA is None:
        with open(SCHEMA_PATH) as f:
            _SCHEMA = json.load(f)
    return _SCHEMA


_TYPES = {'string': str, 'integer': int, 'number': (int, float), 'boolean': bool, 'array': list, 'object': dict,
          'null': type(None)}


def _is(v, t):
    if t == 'integer':
        return isinstance(v, int) and not isinstance(v, bool)
    if t == 'number':
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return isinstance(v, _TYPES[t])


def _path(p):
    return '.'.join(str(x) for x in p) or '(top level)'


def validate(doc, sch=None, root=None, path=()):
    """Returns a list of (path, message). Empty list = valid."""
    root = root or schema()
    sch = sch if sch is not None else root
    if '$ref' in sch:
        ref = sch['$ref']
        node = root
        for part in ref.lstrip('#/').split('/'):
            node = node[part]
        return validate(doc, node, root, path)
    errs = []
    if 'const' in sch and doc != sch['const']:
        return [(path, 'must be %s' % json.dumps(sch['const']))]
    if 'enum' in sch and doc not in sch['enum']:
        close = difflib.get_close_matches(str(doc), [str(x) for x in sch['enum']], 1)
        return [(path, 'is %r; allowed: %s%s' % (doc, ', '.join(str(x) for x in sch['enum']),
                                                  ' (did you mean %s?)' % close[0] if close else ''))]
    for key in ('oneOf', 'anyOf'):
        if key in sch:
            subs = [validate(doc, s, root, path) for s in sch[key]]
            if not any(not e for e in subs):
                best = min(subs, key=len)
                return best if len(best) == 1 and best[0][0] != path else [(path, 'has an unexpected form: %s' % '; or '.join(e[0][1] for e in subs if e))]
            return []
    t = sch.get('type')
    if t:
        ts = t if isinstance(t, list) else [t]
        if not any(_is(doc, x) for x in ts):
            return [(path, 'must be %s, not %s' % (' or '.join(ts), type(doc).__name__ if doc is not None else 'empty'))]
    if isinstance(doc, dict):
        props = sch.get('properties', {})
        for r in sch.get('required', []):
            if r not in doc:
                errs.append((path, 'needs the key `%s`' % r))
        for k, v in doc.items():
            if k in props:
                errs += validate(v, props[k], root, path + (k,))
            else:
                ap = sch.get('additionalProperties', True)
                if ap is False:
                    close = difflib.get_close_matches(str(k), list(props), 1)
                    errs.append((path + (k,), 'is not a known key%s' % (' (did you mean `%s`?)' % close[0] if close else
                                                                        '; known keys here: ' + ', '.join(props))))
                elif isinstance(ap, dict):
                    errs += validate(v, ap, root, path + (k,))
    if isinstance(doc, list):
        if 'minItems' in sch and len(doc) < sch['minItems']:
            errs.append((path, 'needs at least %d entr%s' % (sch['minItems'], 'y' if sch['minItems'] == 1 else 'ies')))
        if 'items' in sch:
            for i, v in enumerate(doc):
                errs += validate(v, sch['items'], root, path + (i,))
    if isinstance(doc, (int, float)) and not isinstance(doc, bool):
        if 'minimum' in sch and doc < sch['minimum']:
            errs.append((path, 'must be at least %s' % sch['minimum']))
        if 'maximum' in sch and doc > sch['maximum']:
            errs.append((path, 'must be at most %s' % sch['maximum']))
    if isinstance(doc, str) and 'pattern' in sch and not re.search(sch['pattern'], doc):
        errs.append((path, 'does not match %s' % sch['pattern']))
    return errs


def format_errors(errs):
    return ['`%s` %s' % (_path(p), m) for p, m in errs]
