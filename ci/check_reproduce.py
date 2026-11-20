#!/usr/bin/env python3
"""Check results/reproduce_summary.json (from a fresh `make reproduce`) against ci/expected_reproduce.json.  

What it does (default mode, no engine run, ~1 s):
  * compares verdict + min_faults + cycles of every expected row; REJECTS duplicate, missing and unexpected rows (exact row count);
  * cross-checks each summary row against its per-run file results/reproduce/<design>_<src>_<flow>_k<k>.json (verdict, min_faults,
    k, cycles) and against the input file it names (design_sha256_16 must equal the first 16 hex of the SHA-256 of that file);
  * (-v) prints the full SHA-256 of every input netlist/RTL, of glitchsat.py, of the expected file, the summary and every per-run file.
  * --rerun    : ALSO re-runs the engine (scripts/glitchsat.py) on every expected row in a temp dir (~30-40 s) and compares.
  * --write-manifest FILE / --manifest FILE : write / verify a SHA-256 manifest of those files.
What it does NOT prove: a summary and an expected file that live in the same tree can both be edited, so without --rerun this is a
consistency/integrity check against accidents, not tamper evidence; a manifest in the same tree is not authentic either (publish its hash
out of band, e.g. in a signed tag). Even --rerun only shows that THIS engine on THIS tool versions reproduces the table; it says nothing
about the model (bit flips of gate outputs/flop Q, constant attacker input, known init) being right, nor about other netlists.
Only verdict and min_faults are compared (runtimes and fault-site names depend on tool versions; the witness is not unique).
Exit codes: 0 all good; 1 mismatch (any problem, RERUN MISMATCH included); 3 missing/malformed input file; 4 the --rerun engine crashed on a row.

H2 (RT2 N2/N13): a RERUN MISMATCH, RERUN ERROR, MISMATCH or MISSING ROW row is a FAILED row: it is never counted in "N/36 rows match".
Every run prints the TAMPER-EVIDENCE statement (TAMPER_NOTE below). Short form: coordinated edits of several files in one tree, or an edited engine whose
SHA-256 matches nothing outside the tree, are NOT detected; compare against an external copy (signed tag / release notes / a fresh checkout of a pinned
commit) to catch them. --rerun also compares the SHA-256 of the engine files it executes with ENGINE_MANIFEST below and WARNS if they differ; that
manifest is inside this same file/tree, so it is evidence only against someone who edits the engine but not this file."""
import argparse, hashlib, json, os, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__)); root = os.path.dirname(here)
EXIT_OK, EXIT_MISMATCH, EXIT_INPUT, EXIT_ENGINE_ERROR = 0, 1, 3, 4
# SHA-256 of the engine files that --rerun executes (H2). Regenerate deliberately with --print-engine-manifest after a reviewed engine change.
ENGINE_MANIFEST = {
    'scripts/glitchsat.py': '1ad037ef07e23c2aabcea75b87a99616591957bd61ed8e0b80abae6b737a9f3c',
    'scripts/synth.sh': '99686d4e22780650bbeb8829ea9d2dd6b8bb30422af27d82a6ae2aa4f14af6fc',
}
ROW_TAGS = ('MISMATCH', 'MISSING ROW', 'RERUN MISMATCH', 'RERUN ERROR')   # tags whose second field is a row key: that row FAILED
TAMPER_NOTE = """What this run can and cannot tell you (TAMPER-EVIDENCE):
  DETECTED   : accidental or one-sided edits: summary vs per-run file vs input hash (first 16 hex only) vs expected file; duplicate / missing / extra rows;
               (with --rerun) results or expected values that the engine in this tree does not reproduce.
  NOT DETECTED: a coordinated edit of several files in the same tree (summary + per-run files + recorded hashes); an edited engine
               (scripts/glitchsat.py) or scripts/synth.sh, unless its SHA-256 is compared with a copy you trust (the built-in ENGINE_MANIFEST lives in this tree too);
               an edited RTL/netlist that keeps the same verdicts; a changed model; tool-version differences.
  Coordinated edits are only caught by comparing against an EXTERNAL copy (a signed tag, release notes, a fresh checkout of a pinned commit, a manifest hash kept elsewhere).
  --rerun means: 'this engine, on this tree, with these tool versions, reproduces the table'. Nothing more."""


def sha(p):
    with open(p, 'rb') as f: return hashlib.sha256(f.read()).hexdigest()


def load_unique(p):
    def hook(pairs):
        d = {}
        for k, v in pairs:
            if k in d: raise ValueError(f'duplicate JSON key {k!r}')
            d[k] = v
        return d
    with open(p) as f: return json.load(f, object_pairs_hook=hook)


def input_path(design, netlist):
    src = netlist.split('/')[0]
    return os.path.join(root, 'rtl', f'{design}.v') if src == 'rtl' else os.path.join(root, 'reference', 'spike_netlists', f'{design}.json')


def run_file(r):
    return os.path.join(root, 'results', 'reproduce', f"{r['design']}_{r['netlist'].replace('/', '_')}_k{r['k']}.json")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--rerun', action='store_true', help='re-run the engine on every expected row and compare (slow)')
    ap.add_argument('--manifest', help='verify SHA-256 manifest FILE'); ap.add_argument('--write-manifest', help='write SHA-256 manifest to FILE')
    ap.add_argument('-v', '--verbose', action='store_true', help='print the SHA-256 of every file covered')
    ap.add_argument('--print-engine-manifest', action='store_true', help='print the SHA-256 of the engine files (paste into ENGINE_MANIFEST after a reviewed engine change) and exit')
    ap.add_argument('--strict-engine', action='store_true', help='with --rerun: an engine file that differs from ENGINE_MANIFEST is a failure (exit 1), not only a warning')
    a = ap.parse_args(argv)
    if a.print_engine_manifest:
        for p in sorted(ENGINE_MANIFEST): print(f"    '{p}': '{sha(os.path.join(root, p))}',")
        return EXIT_OK
    try:
        exp = load_unique(os.path.join(here, 'expected_reproduce.json'))
        got = load_unique(os.path.join(root, 'results', 'reproduce_summary.json'))
        rows = got['rows']
    except (OSError, ValueError, KeyError) as e:
        print('INPUT ERROR:', e, file=sys.stderr); return EXIT_INPUT
    bad = []; seen = {}; files = {}
    for r in rows:
        key = f"{r['design']}|{r['netlist']}|k{r['k']}"
        if key in seen: bad.append(('DUPLICATE ROW', key, None)); continue
        seen[key] = r
    for k in seen:
        if k not in exp['expected']: bad.append(('UNEXPECTED ROW', k, None))
    for k, v in exp['expected'].items():
        r = seen.get(k)
        if r is None: bad.append(('MISSING ROW', k, v)); continue
        if [r['verdict'], r['min_faults']] != v: bad.append(('MISMATCH', k, v, [r['verdict'], r['min_faults']]))
        # cross-check against the per-run file and the input it names
        rf = run_file(r)
        try:
            j = load_unique(rf)
        except (OSError, ValueError) as e:
            bad.append(('RUN FILE', k, f'{os.path.relpath(rf, root)}: {e}')); continue
        if (j.get('verdict'), j.get('min_faults'), j.get('bound', {}).get('max_faults'), j.get('bound', {}).get('cycles')) != (r['verdict'], r['min_faults'], r['k'], r['cycles']):
            bad.append(('RUN FILE DISAGREES WITH SUMMARY', k, os.path.relpath(rf, root)))
        ip = input_path(r['design'], r['netlist'])
        if not os.path.isfile(ip): bad.append(('INPUT MISSING', k, ip)); continue
        if j.get('design_sha256_16') != sha(ip)[:16]: bad.append(('INPUT HASH != hash recorded in run file', k, os.path.relpath(ip, root)))
        files[os.path.relpath(ip, root)] = sha(ip); files[os.path.relpath(rf, root)] = sha(rf)
    if got.get('cycles') != exp['cycles']: bad.append(('cycles', exp['cycles'], got.get('cycles')))
    if len(rows) != len(exp['expected']): bad.append(('ROW COUNT', len(exp['expected']), len(rows)))
    for p in ('scripts/glitchsat.py', 'ci/expected_reproduce.json', 'results/reproduce_summary.json'):
        files[p] = sha(os.path.join(root, p))
    engine_errors = 0
    if a.rerun:
        for p, h in sorted(ENGINE_MANIFEST.items()):   # H2: warn when the engine that is about to be trusted is not the one in the manifest
            try: cur = sha(os.path.join(root, p))
            except OSError as e: cur = f'unreadable ({e})'
            if cur != h:
                msg = f'ENGINE FILE DIFFERS FROM MANIFEST {p}: sha256 {cur} != {h} (an edited engine can make --rerun say anything; review the change, then --print-engine-manifest)'
                print('WARNING:', msg, file=sys.stderr); print('WARNING:', msg)
                if a.strict_engine: bad.append(('ENGINE MANIFEST', p, h, cur))
        sys.path.insert(0, os.path.join(root, 'scripts')); import glitchsat as g
        with tempfile.TemporaryDirectory() as td:
            for k, v in exp['expected'].items():
                d, nl, kk = k.split('|'); kk = int(kk[1:]); src, flow = nl.split('/')
                try:
                    res = g.run_check(input_path(d, nl), d, kk, exp['cycles'], None, flow=flow if src == 'rtl' else 'plain', workdir=td)
                except Exception as e:   # N13: a crashing engine is a FAILED row (exit 4), not a Python traceback with exit 1
                    bad.append(('RERUN ERROR', k, f'{type(e).__name__}: {str(e)[:200]}')); engine_errors += 1; continue
                if [res['verdict'], res.get('min_faults')] != v: bad.append(('RERUN MISMATCH', k, v, [res['verdict'], res.get('min_faults')]))
    if a.write_manifest:
        with open(a.write_manifest, 'w') as f:
            for p in sorted(files): f.write(f'{files[p]}  {p}\n')
    if a.manifest:
        try:
            lines = [l.split('  ', 1) for l in open(a.manifest).read().splitlines() if l.strip()]
            for h, p in lines:
                if files.get(p) != h: bad.append(('MANIFEST', p, h, files.get(p)))
            for p in files:
                if p not in {p for _, p in lines}: bad.append(('NOT IN MANIFEST', p, None))
        except OSError as e:
            print('INPUT ERROR:', e, file=sys.stderr); return EXIT_INPUT
    for b in bad: print(*b)
    failed = {b[1] for b in bad if b[0] in ROW_TAGS}   # every row that has at least one row-level failure (RERUN MISMATCH included)
    n = len(exp['expected'])
    print(f"{n - len(failed)}/{n} rows match"
          f" ({'engine re-run' if a.rerun else 'summary + per-run files + input hashes; engine NOT re-run'}); {len(failed)} row(s) FAILED; {len(bad)} problem(s) in total")
    print(TAMPER_NOTE)
    if a.verbose:
        for p in sorted(files): print(f'  sha256 {files[p]}  {p}')
    if engine_errors: return EXIT_ENGINE_ERROR
    return EXIT_MISMATCH if bad else EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
