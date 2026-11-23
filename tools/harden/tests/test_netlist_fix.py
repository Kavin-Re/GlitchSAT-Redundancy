"""Fixes applied directly to stored netlists: single-point removal (merge lint) and the consumer mask."""
import os
import pytest
from harden import cli, sim, unmerge as U
from harden.netlist import Netlist

G = [[0, 3, 6], [1, 4, 7], [2, 5]]


def test_unmerge_removes_single_points_and_keeps_function(repo):
    p = repo('validation/nl/v2.json')
    nl = Netlist.load(p, 'v2')
    assert U.shared_nets(nl, G)
    n2, info = U.unmerge(nl, G)
    assert info['shared_after'] == 0 and info['clones_added'] > 0
    a, b = sim.fault_free(nl, 6), sim.fault_free(n2, 6)
    assert (a['boot_word'] == b['boot_word']).all()
    assert sim.min_flips(nl, kmax=2, cycles=None).min_flips == 1
    assert sim.min_flips(n2, kmax=2, cycles=None).min_flips is None or sim.min_flips(n2, kmax=2, cycles=None).min_flips >= 2


def test_netlist_fix_with_consumer_mask(repo, tmp_path):
    ev = cli.netlist_fix(repo('reference/spike_netlists/v2.json'), 'v2', 3, G, mask=0x0F, outdir=str(tmp_path))
    assert ev['before']['min_flips'] is not None and ev['before']['min_flips'] < 3
    assert ev['steps'][0]['move'] == 'consumer'
    assert ev['steps'][0]['min_flips'] is None or ev['steps'][0]['min_flips'] > ev['before']['min_flips']


def test_merge_lint_from_ext_surface_is_used(repo, surface):
    r = U.run_lint(repo('validation/nl/v2.json'), 'v2', G)
    assert r is not None and 'error' not in r, r
    assert r['single_points'] > 0
