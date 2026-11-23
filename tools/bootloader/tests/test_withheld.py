"""The public files of this module withhold the details of the bootloader study: no per-build outcomes in the result
file, and no function, file, build or commit name in any public file (checked with the hashed identifier list of the
shared check_wording.py, so this test does not contain the names either)."""
import json
import os

from test_wording_scan import MOD, _checker


def test_public_result_has_no_per_build_outcomes():
    d = json.load(open(os.path.join(MOD, 'results', 'labs_result.json')))
    assert 'rows' not in d['run'] and d['run'].get('withheld') is True
    assert [f['id'] for f in d['findings']] == ['withheld'] and d['module'] == 'bootloader'
    assert not _checker().scan_text(json.dumps(d))


def test_no_withheld_identifier_in_public_files():
    hits = [h for h in _checker().scan([MOD]) if h[2].startswith('disclose:')]
    assert not hits, hits[:10]
    assert not os.path.exists(os.path.join(MOD, 'harness'))         # kept in the private notes
    named = [f for f in os.listdir(os.path.join(MOD, 'tests')) if _checker().scan_text(f)]
    assert not named, named                                         # the smoke test of the harness stays private too


def test_checker_sees_the_private_notes():
    priv = os.path.join(MOD, 'to_report')
    if not os.path.isdir(priv):
        return                                                      # a public copy: nothing private to look at
    hits = [h for h in _checker().scan([priv]) if h[2].startswith('disclose:')]
    assert hits, 'the identifier list no longer matches the private notes'
