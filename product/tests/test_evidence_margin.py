"""Margin calculator: the transcribed tables reproduce the schemes' own worked examples, and every assumption is explicit."""
import pytest

from faultbound_wt.evidence import factors as F, margin as M


def _psa_total(ex):
    sel = dict(id=ex["identification"], ex=ex["exploitation"], basis={})
    rows, i, e = M._rate("psa", sel)
    return i, e


def test_psa_one_glitch_example_reproduced():
    i, e = _psa_total(F.PSA_EXAMPLES["one_glitch_each_device"])
    assert (i, e, i + e) == (11, 9, 20)   # JSADEN004 5.1.3 prints 11 / 9 / 20


def test_psa_two_glitch_example_discrepancy_is_explicit():
    i, e = _psa_total(F.PSA_EXAMPLES["two_glitches"])
    assert (i, e) == (11, 10)            # Table 1: '<= one week' exploitation = 4 points
    assert F.PSA_EXAMPLES["two_glitches"]["printed_total"] == 23
    assert "21" in F.PSA_EXAMPLES["two_glitches"]["discrepancy"]


def test_psa_other_cited_examples():
    # 5.4.3 rollback bypass: month/week, expert/proficient, specialized -> 11 + 10 = 21
    sel = dict(id=dict(elapsed="month", expertise="expert", knowledge="public", access="lt10", equipment="specialized"),
               ex=dict(elapsed="week", expertise="proficient", knowledge="public", access="lt10", equipment="specialized"), basis={})
    _, i, e = M._rate("psa", sel)
    assert i + e == 21
    # 5.6.6 DFA RSA-CRT: week/day -> 10 + 9 = 19
    sel["id"]["elapsed"], sel["ex"]["elapsed"] = "week", "day"
    _, i, e = M._rate("psa", sel)
    assert (i, e) == (10, 9)


def test_jil_annex_a3_example1_reproduced():
    # JIL Table 15 (para. 286): LFI on CSP/bare die: 8 + 10 = 18 'Basic'
    sel = dict(id=dict(elapsed="month", expertise="proficient", knowledge="public", access="lt10", equipment="specialized",
                       open_samples="public"),
               ex=dict(elapsed="week", expertise="proficient", knowledge="public", access="lt10", equipment="specialized",
                       open_samples=None), basis={})
    _, i, e = M._rate("jil", sel)
    assert (i, e) == (8, 10)
    assert F.jil_band(18) == "Basic"
    ex = F.JIL_EXAMPLE_LFI
    _, i2, e2 = M._rate("jil", dict(id=ex["identification"], ex=dict(ex["exploitation"], open_samples=None), basis={}))
    assert i2 + e2 == ex["printed_total"] and F.jil_band(i2 + e2) == ex["printed_band"]


def test_jil_bands_and_psa_ceilings():
    assert [F.jil_band(x) for x in (15, 16, 20, 21, 24, 25, 30, 31)] == [
        "No rating", "Basic", "Basic", "Enhanced-Basic", "Enhanced-Basic", "Moderate", "Moderate", "High"]
    assert F.PSA_LEVELS == {2: 15, 3: 20, 4: 24}


def test_every_factor_has_a_citation():
    assert "Table 1" in F.PSA_TABLE1["_source"] and "Table 13" in F.JIL_TABLE13["_source"]
    for k, (lvl, src) in F.EVENTS_TO_ELAPSED.items():
        assert "5.1.3" in src
    for t, s in F.PSA_SCOPE_NOTES:
        assert "section" in s
    for ft, (cls, name) in F.JIL_TOOL_CLASS.items():
        assert cls in F.EQUIPMENT and name


def test_default_voltage_glitch_gives_one_event():
    r = M.rate(3)
    assert r["events"] == 1 and r["psa"]["total"] == 20 and r["psa"]["levels"][3]["in_scope"]
    assert "1 event" in r["events_reasoning"][0]


def test_two_events_example_from_brief():
    r = M.rate(2, assume=dict(flips_per_event=1))
    assert r["events"] == 2
    assert r["psa"]["total"] == 21 and not r["psa"]["levels"][3]["in_scope"] and r["psa"]["levels"][4]["in_scope"]
    assert r["psa"]["printed_example"]["total"] == 23
    assert "> L3 ceiling 20" in r["headline"] and "prints 23" in r["headline"]


def test_three_events_no_extrapolation():
    r = M.rate(3, assume=dict(flips_per_event=1))
    assert r["events"] == 3 and r["psa"]["total"] == 21
    assert any("does not extrapolate" in n for n in r["notes"])


def test_cited_pages_after_recheck():
    # re-checked against the PDFs on 2026-11-21: two-glitch example is on page 27, wording 'very low'
    assert "page 27" in F.PSA_EXAMPLES["two_glitches"]["source"] and "very low" in F.PSA_RARE_NOTE[0]
    assert "page 26" in F.PSA_EXAMPLES["one_glitch_each_device"]["source"]


def test_success_rare_matches_cited_25():
    r = M.rate(2, assume=dict(flips_per_event=1, success_rare=True))
    assert r["psa"]["total"] == 25 and not r["psa"]["levels"][4]["in_scope"]


def test_laser_defaults():
    r = M.rate(3, assume=dict(fault_type="laser"))
    assert r["assumptions"]["flips_per_event"] == 1 and r["events"] == 3
    eq = [x for x in r["jil"]["rows"] if x["factor"] == "Equipment"][0]
    assert eq["id_level"] == "Specialized" and "Table 10" in eq["basis"]


def test_jil_voltage_equipment_is_standard():
    r = M.rate(1)
    eq = [x for x in r["jil"]["rows"] if x["factor"] == "Equipment"][0]
    assert eq["id_level"] == "Standard" and r["jil"]["total"] == 16


def test_user_overrides_are_marked():
    r = M.rate(2, assume=M.parse_assumptions(["id_expertise=proficient", "events=2"]))
    exp = [x for x in r["psa"]["rows"] if x["factor"] == "Expertise"][0]
    assert exp["basis"] == "set by the user" and r["events"] == 2 and r["sensitivity"] == []


def test_lower_bound_and_zero_and_none():
    r = M.rate(4, m_is_lower_bound=True, assume=dict(flips_per_event=1))
    assert "or more" in r["headline"]
    assert M.rate(0)["status"] == "no_fault_needed"
    assert M.rate(None)["status"] == "no_result"


def test_events_from_cycles_needs_complete_surface():
    sf = dict(complete=True, count=2, attacks=[dict(faults=[["a", 0], ["b", 3]]), dict(faults=[["a", 1], ["c", 2]])])
    r = M.rate(2, assume=dict(events_from_cycles=True), surface=sf)
    assert r["events"] == 2
    sf["complete"] = False
    r = M.rate(2, assume=dict(events_from_cycles=True), surface=sf)
    assert r["events"] == 1 and any("ignored" in w for w in r["events_reasoning"])


@pytest.mark.parametrize("bad", ["nokey", "foo=1", "fault_type=plasma", "flips_per_event=0", "id_expertise=wizard",
                                 "target_psa_level=5", "events=x", "success_rare=maybe"])
def test_bad_assumptions_rejected(bad):
    with pytest.raises(M.AssumptionError):
        M.resolve(M.parse_assumptions([bad]))


def test_disclaimer_everywhere():
    r = M.rate(2)
    assert "never replaces" in r["disclaimer"]
