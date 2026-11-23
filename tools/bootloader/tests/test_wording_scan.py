"""No listed word and no absolute developer path in this module's shipped files (code, UI text, results, docs).
Uses the shared check next to the modules (check_wording.py), which stores its word list as hashes only."""
import importlib.util
import os

import pytest

MOD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _checker():
    for p in (os.path.join(os.path.dirname(MOD), 'check_wording.py'), os.path.join(os.path.dirname(MOD), 'ext', 'check_wording.py'),
              os.path.join(os.environ.get('GLITCHSAT_EXT', ''), 'check_wording.py')):
        if os.path.isfile(p):
            spec = importlib.util.spec_from_file_location('check_wording', p)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            return m
    pytest.skip('check_wording.py not found')


def test_no_listed_words_or_developer_paths():
    hits = _checker().scan([MOD])
    assert not hits, hits[:10]


def test_checker_finds_a_path_and_a_planted_word():
    cw = _checker()
    assert cw.line_hits('see ' + '/ho' + 'me/someone/x.txt') == ['path']
    assert cw.line_hits('/home/you/my_chip') == []
    word = bytes([117, 110, 105, 118, 101, 114, 115, 105, 116, 121]).decode()      # spelled as bytes, not as text
    assert cw.line_hits('a ' + word + ' tool') and not cw.line_hits('of course it works')
