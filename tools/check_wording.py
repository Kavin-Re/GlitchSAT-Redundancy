#!/usr/bin/env python3
"""Wording and path check for every file that may ship (code, UI text, results, docs).

  python3 check_wording.py [FOLDER ...]      exit 1 and a list of file:line hits when something is found

Three kinds of finding:
  * an absolute developer path (/home/<user>/..., except the placeholder /home/you used in examples);
  * a word or phrase from the project's list of words that must not appear in shipped files;
  * an identifier withheld pending responsible disclosure (function, file, build and commit names of the bootloader
    study), matched as a whole identifier or as one part of an identifier split at '_' and '-'.
One exemption (decision D-015): the conventional names of the two handoff files at the repository root, written
exactly as HANDOFF_NAMES lists them (capitals, '.md'), are removed from a line before the word scan, so a file may
point to them. The same word anywhere else, in any other spelling, is still reported.
The word list is stored only as SHA-256 hashes, so neither this file nor the tests that call it contain the
words themselves. A token is checked as a whole word (case-insensitive), as a word stem, or as a two-word phrase.
Used by the test suites of the Studio and of the modules; it needs nothing outside the Python standard library.
"""
import hashlib
import os
import re
import sys

# sha256(term)[:16] -> kind. kinds: word (whole token), stem (token starts with it), pair (two tokens), upper (token
# in capitals only), except_of (whole token unless the phrase is "of <token>").
TERMS = {
    'c857d09db23e6822': 'word', 'c70eca6b0f88f44d': 'word', '60965168ce762e94': 'word', '7d3194f79e645c42': 'word',
    '487b91042c7cf27a': 'word', '3ea125d0bff386e6': 'word', 'd4f0bc5a29de06b5': 'word', '8c70b25cbbbe8e79': 'word',
    '32e83e92d45d71f6': 'upper', '350f355f9c0579eb': 'stem', 'a908043ed469f361': 'except_of', '936e5cc5021d8a07': 'except_of',
    '5cdb778cb86d9a0a': 'word', '051f7a6a7c815c1d': 'pair', '5eff592cc497fccb': 'pair', 'f1726c61cbcfbaf7': 'word',
    'bdb012c3163a27d5': 'word', '508c9187ad1f5baa': 'word', 'e24cc7b0c49f50f0': 'word', '86e0db401e2c9f6c': 'word',
    '7b647ad335158318': 'word', '49672f0ef3b3a542': 'word',
}
STEMS = sorted({9})                         # lengths of the stems in TERMS
# sha256(identifier, lower case)[:16] of names withheld pending responsible disclosure (kept in the private notes).
DISCLOSE = {
    'e5529b7e31143aaf', 'ff89ecf8fa0ec643', 'f3dcea6d457e27e7', 'b180c84c1b01f40a', '290ecbecd47bb5e1', '59f2bb169f29efce',
    '2cfbf877f40eaa74', 'abea1a485e65442f', 'abdb59762a00eae0', '422eb6960cb03d79', '43f7f39992f13cdf', '86ff545bae916f63',
    '242b971611a69517', '21ddb770e29b3b41', '2c5b41081632e17c',
}
# A published third-party article in the research log may keep its own link (its address contains a withheld name).
DISCLOSE_OK = {('research/c1/R1_users_needs.md', '2c5b41081632e17c')}
# D-015: the two handoff file names, exact spelling only, not part of a longer name (a sentence-ending full stop is allowed).
HANDOFF_NAMES = ('AGENTS.md', 'CLAUDE.md')
HANDOFF_RX = re.compile(r'(?<![A-Za-z0-9_.-])(?:' + '|'.join(re.escape(n) for n in HANDOFF_NAMES) + r')(?![A-Za-z0-9_]|\.[A-Za-z0-9_])')
ID_RX = re.compile(r'[A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)*')
PATH_RX = re.compile(r'(?<![\w.~])/home/(?!you\b)[A-Za-z0-9_.-]+')
TOKEN_RX = re.compile(r"[A-Za-z][A-Za-z0-9]*")
TEXT_EXT = ('.py', '.md', '.json', '.yaml', '.yml', '.txt', '.html', '.js', '.css', '.sh', '.v', '.sv', '.c', '.h', '.toml',
            '.cfg', '.ini', '.tcl', '.lock', '')
SKIP_DIRS = {'.git', '__pycache__', '.pytest_cache', 'work', '.glitchsat', 'third_party', 'src_clone', 'node_modules',
             'to_report', 'backup', 'patch31', 'patch_ut2'}


def _h(s):
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def line_hits(line):
    """Kinds of finding in one line of text (no words are returned, only 'path' or 'word:<hash>')."""
    out = []
    if PATH_RX.search(line):
        out.append('path')
    line = HANDOFF_RX.sub(' ', line)
    for ident in ID_RX.findall(line):
        il = ident.lower()
        for part in {il} | set(re.split(r'[-_]', il)) | set(il.split('-')):
            if part and _h(part) in DISCLOSE:
                out.append('disclose:' + _h(part))
                break
    toks = TOKEN_RX.findall(line)
    low = [t.lower() for t in toks]
    for i, t in enumerate(low):
        k = TERMS.get(_h(t))
        if k == 'word':
            out.append('word:' + _h(t))
        elif k == 'upper' and toks[i].isupper():
            out.append('word:' + _h(t))
        elif k == 'except_of' and not (i and low[i - 1] == 'of'):
            out.append('word:' + _h(t))
        for n in STEMS:
            if len(t) > n and TERMS.get(_h(t[:n])) == 'stem':
                out.append('word:' + _h(t[:n]))
        if i + 1 < len(low) and TERMS.get(_h(t + ' ' + low[i + 1])) == 'pair':
            out.append('word:' + _h(t + ' ' + low[i + 1]))
    return out


def scan_text(text):
    return [(n, k) for n, line in enumerate(text.splitlines(), 1) for k in line_hits(line)]


def iter_files(root, skip_dirs=SKIP_DIRS, skip_names=()):
    if os.path.isfile(root):
        yield root
        return
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('shots') and not d.endswith('_pre_audit')]
        for f in files:
            if '_pre_audit' in f or f in skip_names or not f.endswith(TEXT_EXT) or f.endswith(('.tar.gz', '.tgz')):
                continue
            yield os.path.join(base, f)


def scan(roots, skip_dirs=SKIP_DIRS, skip_names=()):
    """[(file, line, kind)] over every text file under the roots."""
    hits = []
    for r in roots:
        for p in iter_files(r, skip_dirs, skip_names):
            try:
                with open(p, 'rb') as fh:
                    raw = fh.read(4_000_000)
            except OSError:
                continue
            if b'\0' in raw[:8192]:            # a binary file (an image, a build output): not text, not scanned
                continue
            text = raw.decode('utf-8', errors='replace')
            rel = p.replace(os.sep, '/')
            hits += [(p, n, k) for n, k in scan_text(text)
                     if not any(rel.endswith('/' + f) and k == 'disclose:' + h for f, h in DISCLOSE_OK)]
    return hits


def main(argv):
    roots = argv or [os.path.dirname(os.path.abspath(__file__))]
    hits = scan(roots)
    for p, n, k in hits:
        print('%s:%d: %s' % (p, n, 'absolute developer path' if k == 'path' else
                             'withheld identifier (%s)' % k if k.startswith('disclose:') else 'listed word (%s)' % k))
    print('%d finding(s) in %s' % (len(hits), ', '.join(roots)))
    return 1 if hits else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
