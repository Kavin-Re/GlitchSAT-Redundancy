"""Unit checks for first_run_view.py (welcome story and Presenter mode). Standard library only, no browser.

  python3 -m unittest studio/tests/test_first_run.py      (or: python3 tests/test_first_run.py from studio/)

The project folder is $GLITCHSAT_ROOT (default: the repository around tools/studio/); the module folders
(soc, firmware, masking) are found in tools/ or $GLITCHSAT_EXT, the real-designs folder in $GLITCHSAT_REAL.
"""
import importlib.util
import io
import json
import os
import re
import shutil
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
STUDIO = os.path.dirname(HERE)
UP = os.path.dirname(STUDIO)
ROOT = os.environ.get('GLITCHSAT_ROOT') or os.path.dirname(UP)
EXT = os.environ.get('GLITCHSAT_EXT') or UP
REAL = os.environ.get('GLITCHSAT_REAL') or os.path.join(UP, 'real')


def _j(*p):
    with open(os.path.join(*p), encoding='utf-8') as fh:
        return json.load(fh)


def _t(*p):
    with open(os.path.join(*p), encoding='utf-8') as fh:
        return fh.read()


def _load(name, path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


FR = _load('first_run_view', os.path.join(STUDIO, 'first_run_view.py'))


class FakeHandler:
    """Stands in for the Studio's request handler: records what _send was given."""
    def __init__(self, headers=None):
        self.headers = headers or {}
        self.sent = None

    def _send(self, code, body, ctype='application/json'):
        self.sent = (code, body, ctype)

    def json(self):
        return json.loads(self.sent[1])


PAGE = '<html><head><style>a{}</style></head><body><script>main</script></body></html>'


class InstallTests(unittest.TestCase):
    def test_adds_one_style_and_one_script(self):
        p = FR.install(PAGE)
        self.assertEqual(p.count('id="fr-css"'), 1)
        self.assertEqual(p.count('id="fr-js"'), 1)
        self.assertIn('Studio.firstRun', p)
        self.assertIn('Studio.onGo', p)
        self.assertLess(p.index('main'), p.index('id="fr-js"'))       # after the main script, so its helpers exist

    def test_install_twice_changes_nothing(self):
        p = FR.install(PAGE)
        self.assertEqual(FR.install(p), p)

    def test_env_switch_for_test_harnesses(self):
        old = os.environ.get('GLITCHSAT_FIRSTRUN')
        try:
            os.environ['GLITCHSAT_FIRSTRUN'] = '0'
            self.assertIn('window.GS_NO_WELCOME=1', FR.install(PAGE))
            os.environ.pop('GLITCHSAT_FIRSTRUN')
            self.assertNotIn('window.GS_NO_WELCOME=1', FR.install(PAGE))
        finally:
            if old is not None:
                os.environ['GLITCHSAT_FIRSTRUN'] = old
        self.assertIn("Q.get('firstrun')==='0'", FR.JS)

    def test_on_go_is_chained_not_replaced(self):
        self.assertRegex(FR.JS, r'const prev=Studio\.onGo;Studio\.onGo=')
        self.assertIn('return prev?prev(g):false', FR.JS)


class FactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.F, cls.P = FR.facts(ROOT, EXT, REAL, with_paths=True)

    def test_every_fact_has_value_label_and_an_existing_source(self):
        want = {'v0', 'v1', 'v2_stored', 'v2_rebuilt', 'reencode', 'e2', 'real_agree', 'real_ctr', 'chip_pico',
                'chip_ibex_alarm', 'chip_ibex_debug', 'fw_rom', 'mask', 'soc_build', 'code_v0', 'code_v2'}
        self.assertEqual(set(self.F), want)
        for k, f in self.F.items():
            self.assertIn('value', f, k)
            self.assertIn(f['label'], ('MEASURED', 'SIMULATED', 'BOUNDED', 'recorded', 'source'), k)
            self.assertTrue(os.path.isfile(self.P[k]), k)
            self.assertTrue(self.P[k].replace(os.sep, '/').endswith(f['src']), (k, f['src']))
            self.assertFalse(f['src'].startswith('/'), 'shown paths are relative: ' + f['src'])

    def test_toy_locks_match_table_7_1(self):
        d = _j(ROOT, 'results', 'reproduce_summary.json')
        r = {(x['design'], x['netlist'], x['k']): x['min_faults'] for x in d['rows']}
        self.assertEqual(self.F['v0']['value'], r[('v0', 'spike/given-netlist', 3)])
        self.assertEqual(self.F['v1']['value'], r[('v1', 'spike/given-netlist', 3)])
        self.assertEqual(self.F['v2_stored']['value'], r[('v2', 'spike/given-netlist', 3)])
        self.assertEqual(self.F['v2_rebuilt']['value'], r[('v2', 'rtl/plain', 3)])
        self.assertEqual([self.F[k]['value'] for k in ('v0', 'v1', 'v2_stored', 'v2_rebuilt')], [1, 1, 3, 2])
        self.assertEqual(self.F['v1']['shared'], 'ok')

    def test_e2_matches_the_report(self):
        t = _t(ROOT, 'research', 'c2', 'e2_variance', 'E2_REPORT.md')
        self.assertIn('| V2 | 180 | 60 | 24 |', t)
        self.assertEqual(self.F['e2']['value'], dict(min1=180, min2=60, min3=24, total=264))
        self.assertIn('264 solved', t)

    def test_reencode_matches_why_two_flips(self):
        self.assertEqual(self.F['reencode']['value'], dict(old='0xCC', new='0xA5', flips=3, accept='0x96', copies='two'))

    def test_opentitan_agreement_is_the_sum_of_the_experiments(self):
        d = _j(REAL, 'results', 'results.json')
        tot = 0
        for e in d['experiments']:
            a, b = (e.get('agreement') or {}).get('per_injection').split('/')
            self.assertEqual(a, b)
            tot += int(a)
        self.assertEqual(self.F['real_agree']['value'], dict(agree=tot, total=tot))
        self.assertEqual(tot, 4226)
        e3 = next(e for e in d['experiments'] if e['id'] == 'E3')
        self.assertEqual(self.F['real_ctr']['value'], e3['glitchsat']['min_faults_bit_flip'])

    def test_chips_match_explore_chip_json(self):
        d = _j(EXT, 'soc', 'studio', 'explore_chip.json')
        g = {}
        for c in d['chips']:
            for v in c['variants']:
                for x in v['goals']:
                    g[(c['id'], v['variant'], v['flow'], x['id'])] = (int(x['faults_needed']), x['cycles'])
        self.assertEqual(self.F['chip_pico']['value'], {f: g[('picosoc', 'tmr', f, 'boot_release')][0] for f in ('written', 'keep', 'flat')})
        self.assertEqual(self.F['chip_pico']['value'], dict(written=3, keep=2, flat=1))
        self.assertEqual(self.F['chip_pico']['cycles'], 8)
        self.assertEqual(self.F['chip_ibex_alarm']['value'], g[('ibex_demo', 'lockstep', 'flat', 'alarm_suppressed')][0])
        self.assertEqual(self.F['chip_ibex_debug']['value'], dict(stock=1, lockstep=1))
        self.assertEqual(self.F['soc_build']['value'], self.F['chip_pico']['value'])   # the README and the data file agree

    def test_code_excerpts_are_verbatim_lines_of_the_sources(self):
        for k in ('code_v0', 'code_v2'):
            src = _t(ROOT, 'rtl', k[5:] + '.v').split('\n')
            for l in self.F[k]['value']['lines']:
                self.assertEqual(src[l['n'] - 1].strip(), l['text'])
        self.assertEqual((self.F['code_v0']['value']['key'], self.F['code_v2']['value']['accept']), ('0xC3', '0x96'))
        self.assertEqual(sum('cmp8 c' in l['text'] for l in self.F['code_v2']['value']['lines']), 1)
        self.assertIn('cmp8 c2(', ''.join(l['text'] for l in self.F['code_v2']['value']['lines']))

    def test_boot_rom_and_masking(self):
        self.assertEqual(self.F['fw_rom']['value'], dict(fall=90, total=108, opt='-O2'))
        self.assertEqual(self.F['mask']['value'], 'leaks')
        self.assertEqual(self.F['mask']['label'], 'SIMULATED')

    def test_missing_files_are_left_out_not_invented(self):
        tmp = tempfile.mkdtemp()
        try:
            root, ext, real = (os.path.join(tmp, x) for x in ('proj', 'ext', 'real'))
            os.makedirs(os.path.join(root, 'results'))
            shutil.copy(os.path.join(ROOT, 'results', 'reproduce_summary.json'), os.path.join(root, 'results'))
            os.makedirs(ext)
            os.makedirs(real)
            f = FR.facts(root, ext, real)
            self.assertEqual(set(f), {'v0', 'v1', 'v2_stored', 'v2_rebuilt'})
            with open(os.path.join(root, 'results', 'reproduce_summary.json'), 'w') as fh:
                fh.write('{broken')
            self.assertEqual(FR.facts(root, ext, real), {})
        finally:
            shutil.rmtree(tmp)


class SeenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = os.environ.get('XDG_CACHE_HOME')
        os.environ['XDG_CACHE_HOME'] = self.tmp

    def tearDown(self):
        if self.old is None:
            os.environ.pop('XDG_CACHE_HOME', None)
        else:
            os.environ['XDG_CACHE_HOME'] = self.old
        shutil.rmtree(self.tmp)

    def test_round_trip_through_post_and_get(self):
        h = FakeHandler()
        self.assertTrue(FR.handle(h, 'GET', '/api/firstrun/seen', {}, ROOT))
        self.assertEqual(h.json()['seen'], False)
        self.assertEqual(h.json()['started'], False)
        h = FakeHandler({'X-GlitchSAT': '1'})
        self.assertTrue(FR.handle(h, 'POST', '/api/firstrun/seen', {'seen': False, 'screen': 2}, ROOT))
        h = FakeHandler()
        FR.handle(h, 'GET', '/api/firstrun/seen', {}, ROOT)
        self.assertEqual((h.json()['seen'], h.json()['screen'], h.json()['started']), (False, 2, True))
        FR.handle(FakeHandler({'X-GlitchSAT': '1'}), 'POST', '/api/firstrun/seen', {'seen': True, 'screen': 6}, ROOT)
        h = FakeHandler()
        FR.handle(h, 'GET', '/api/firstrun/seen', {}, ROOT)
        self.assertEqual((h.json()['seen'], h.json()['screen']), (True, 6))
        self.assertEqual([x for x in os.listdir(os.path.join(self.tmp, 'glitchsat-studio')) if x.endswith('.tmp')], [])

    def test_post_without_header_is_refused(self):
        h = FakeHandler({})
        self.assertTrue(FR.handle(h, 'POST', '/api/firstrun/seen', {'seen': True}, ROOT))
        self.assertEqual(h.sent[0], 403)
        self.assertFalse(FR.read_seen()['seen'])

    def test_bad_values_do_not_count(self):
        FR.write_seen('yes', 'three')
        self.assertEqual((FR.read_seen()['seen'], FR.read_seen()['screen']), (False, 0))

    def test_corrupt_file_reads_as_not_seen(self):
        d = os.path.join(self.tmp, 'glitchsat-studio')
        os.makedirs(d)
        for body in ('{nope', '[1,2]', '"x"'):
            with open(os.path.join(d, 'first_run.json'), 'w') as fh:
                fh.write(body)
            self.assertEqual(FR.read_seen()['seen'], False)

    def test_other_routes(self):
        self.assertFalse(FR.handle(FakeHandler(), 'GET', '/api/status', {}, ROOT))
        h = FakeHandler()
        self.assertTrue(FR.handle(h, 'GET', '/present-notes', {}, ROOT))
        self.assertIn('BroadcastChannel', h.sent[1])
        h = FakeHandler()
        FR.handle(h, 'GET', '/firstrun/src/e2', {}, ROOT)
        self.assertEqual(h.sent[0], 200)
        self.assertIn(b'| V2 |', h.sent[1])
        h = FakeHandler()
        FR.handle(h, 'GET', '/firstrun/src/..%2F..%2Fetc', {}, ROOT)
        self.assertEqual(h.sent[0], 404)


class WordingTests(unittest.TestCase):
    TEXT = FR.JS + FR.CSS + FR.NOTES_PAGE

    def test_project_word_list(self):
        cw = _load('check_wording', os.path.join(EXT, 'check_wording.py'))
        hits = cw.scan([os.path.join(STUDIO, 'first_run_view.py'), os.path.join(STUDIO, 'verify_first_run.py'), __file__])
        self.assertEqual(hits, [])

    def test_banned_and_required_phrases(self):
        low = self.TEXT.lower()
        for bad in ('quietly', 'silently', 'nobody notices', 'too late', 'nobody tells', 'undo'):
            self.assertNotIn(bad, low)
        for need in ('The answer belongs to the finished design, not the source', 'Only the last build merged the copies: '
                     'design tools can weaken a protection without telling you, so check the finished design', 'SYNFI, a published tool from the OpenTitan project, '
                     'showed before us that synthesis can merge copies', 'fault injection (glitches)', 'planned, not built',
                     'We found this along the way', 'three guards that share one weak point are really one guard'):
            self.assertIn(need, self.TEXT)
        for bad in ('WHY_TWO_FLIPS', 'Rebuilt by the design tool'):   # the 3 -> 2 drop came from the stored code, not from the tool
            self.assertNotIn(bad, FR.JS)
        for need in ():
            self.assertIn(need, self.TEXT)

    def test_no_result_number_typed_into_the_script(self):
        js = re.sub(r'\$\{[^}]*\}', '', FR.JS)          # template holes are filled from the facts at run time
        for n in ('4226', '4,226', '264', '180', '60', '24', '90', '108', '0xCC', '0xA5'):
            self.assertIsNone(re.search(r'(?<![\w.#-])' + re.escape(n) + r'(?![\w])', js), n)


if __name__ == '__main__':
    unittest.main(verbosity=2)
