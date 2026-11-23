"""Generated files on disk are exactly what the generators produce now (they are committed, and the cloud run
regenerates them and checks the same)."""
import json, os
import pytest
from engine import wrappers, benches, studio

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = dict(wrappers.generated_files())
FILES.update(benches.generated_files())


@pytest.mark.parametrize('rel', sorted(FILES))
def test_generated_file_is_up_to_date(rel):
    p = os.path.join(HERE, rel)
    assert os.path.isfile(p), f'{rel} missing: run python3 -m engine.wrappers && python3 -m engine.benches'
    assert open(p).read() == FILES[rel], f'{rel} is stale: regenerate'


def test_studio_skeleton_is_up_to_date_and_empty():
    on_disk = json.load(open(os.path.join(HERE, 'studio', 'secboot_hw.json')))
    assert on_disk == json.loads(json.dumps(studio.panel(None)))
    for c in on_disk['cards']:
        assert c['status'] == 'NOT_RUN'
        for f in on_disk['flows']:
            r = c['results'][f]
            assert r['gates'] is None and r['flops'] is None
            assert [x['verdict'] for x in r['by_k']] == ['NOT_RUN'] * on_disk['kmax']


def test_single_file_design_contains_every_module_once():
    from model.variants import VARIANTS
    for v in VARIANTS[:3]:
        t = wrappers.single_file_design(v)
        for mod in ('sb_keccak_round', 'sb_hash', 'sb_cmp', 'secboot_core', v.top):
            assert t.count(f'module {mod} ') + t.count(f'module {mod}\n') + t.count(f'module {mod}#') == 1 or \
                   t.count(f'\nmodule {mod}') == 1


def test_manifest_matches_variants():
    m = wrappers.manifest()
    from model.variants import VARIANTS
    assert [r['name'] for r in m['variants']] == [v.name for v in VARIANTS]
    for r, v in zip(m['variants'], VARIANTS):
        assert r['goal_value'] == v.goal_value and r['cycles'] == v.cycles and r['key'] == 0xC3
