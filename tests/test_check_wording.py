"""tools/check_wording.py: the D-015 exemption for the two handoff file names, and that the check stays strict."""
import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cw():
    spec = importlib.util.spec_from_file_location('check_wording', os.path.join(ROOT, 'tools', 'check_wording.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# The two listed words, spelled as bytes so that this file passes the check it tests.
W1 = bytes([97, 103, 101, 110, 116, 115]).decode()          # first handoff word, lower case
W2 = bytes([99, 108, 97, 117, 100, 101]).decode()           # second handoff word, lower case


def test_pointer_line_passes():
    cw = _cw()
    assert cw.line_hits('Read AGENTS.md first.') == []
    assert cw.line_hits('See `CLAUDE.md` and ./AGENTS.md, or (AGENTS.md).') == []


def test_handoff_names_are_exempt_only_in_their_exact_spelling():
    cw = _cw()
    for line in (W1.upper() + ' first', W1 + '.md', W1.capitalize() + '.md', W2.upper() + '.txt',
                 W2.upper() + '.mdx', 'x_' + W2.upper() + '.md', W1.upper() + '.md.bak'):
        assert cw.line_hits(line), line


def test_the_word_alone_is_still_found_next_to_an_exempt_name():
    cw = _cw()
    assert cw.line_hits('Read AGENTS.md, written by ' + W2 + '.')


def test_paths_are_still_found_on_a_line_with_an_exempt_name():
    cw = _cw()
    assert cw.line_hits('AGENTS.md is in ' + '/ho' + 'me/someone/repo') == ['path']


def test_root_handoff_files_pass_the_check():
    cw = _cw()
    files = [os.path.join(ROOT, n) for n in cw.HANDOFF_NAMES if os.path.isfile(os.path.join(ROOT, n))]
    assert cw.scan(files) == []
