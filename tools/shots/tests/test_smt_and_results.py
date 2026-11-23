"""The emitted SMT-LIB text is evaluated with a small interpreter (no solver here); the results file is schema-checked."""
import json
import os
import re

import pytest

from shotmodel import design as dsg, search, shots, smt

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _parse(text):
    text = re.sub(r";[^\n]*", "", text)
    tok = re.findall(r"\|[^|]*\||[()]|[^\s()]+", text)
    pos = 0

    def rd():
        nonlocal pos
        t = tok[pos]
        pos += 1
        if t == "(":
            xs = []
            while tok[pos] != ")":
                xs.append(rd())
            pos += 1
            return xs
        return t
    out = []
    while pos < len(tok):
        out.append(rd())
    return out


def smt_holds(text, assignment):
    """True when every assert of the file holds under the Boolean assignment (undeclared-in-assignment consts = False)."""
    env = {}

    def ev(e):
        if isinstance(e, str):
            if e == "true":
                return True
            if e == "false":
                return False
            return env[e]
        op = e[0]
        if isinstance(op, list) and op[:2] == ["_", "at-most"]:
            return sum(ev(x) for x in e[1:]) <= int(op[2])
        a = [ev(x) for x in e[1:]]
        if op == "and":
            return all(a)
        if op == "or":
            return any(a)
        if op == "not":
            return not a[0]
        if op == "xor":
            return a[0] != a[1]
        raise ValueError(op)
    ok = True
    for f in _parse(text):
        if f[0] == "declare-const":
            env[f[1]] = bool(assignment.get(f[1], False))
        elif f[0] == "define-fun":
            env[f[1]] = ev(f[4])
        elif f[0] == "assert":
            ok = ok and ev(f[1])
    return ok


@pytest.mark.parametrize("d,r,goal", [("v2", 0.0, "word"), ("v2", 2.0, "word"), ("v2", 3.0, "word_clean"),
                                      ("v1", 0.0, "ok"), ("v1", 2.5, "word")])
def test_smt_file_accepts_witness_and_rejects_no_shot(d, r, goal):
    D = dsg.Design(d)
    tab = shots.shot_table(D, r, "centre", "cell")
    res = search.min_shots(D, tab["masks"], 6, 4, "flip", goal)
    k = res["min"]
    w = res["witness"]
    idx = {int(m): i for i, m in enumerate(tab["masks"])}
    asg = {"s%d" % i: bool((w["sig"] >> i) & 1) for i in range(8)}
    for t, m in w["shots"]:
        asg["x_%d_%d" % (t, idx[m])] = True
    assert smt_holds(smt.emit(D, tab, 6, k, "flip", goal), asg)
    assert not smt_holds(smt.emit(D, tab, 6, k - 1, "flip", goal), asg)          # one shot too many for k - 1
    none = {"s%d" % i: bool((w["sig"] >> i) & 1) for i in range(8)}
    assert not smt_holds(smt.emit(D, tab, 6, k, "flip", goal), none)             # wrong key, no shot: lock stays shut
    key = {"s%d" % i: bool((dsg.KEY >> i) & 1) for i in range(8)}
    assert not smt_holds(smt.emit(D, tab, 6, k, "flip", goal), key)              # the right key is excluded


RESULTS = os.path.join(HERE, "results", "shots_results.json")


@pytest.mark.skipif(not os.path.isfile(RESULTS), reason="results file not generated")
def test_results_file_schema_and_consistency():
    doc = json.load(open(RESULTS))
    assert doc["schema"] == "glitchsat-shots/1"
    assert all(c["matches_transistor_netlist"] in (True, None) for c in doc["cell_function_check"])
    for d, e in doc["equivalence"].items():
        assert e["transition"] == dict(cases=65536, mismatches=0) and e["boot"]["mismatches"] == 0
    assert all(v["ok"] for v in doc["validation"]["r0"] + doc["validation"]["cross"])
    ids = [c["id"] for c in doc["curves"]]
    assert len(ids) == len(set(ids))
    for c in doc["curves"]:
        assert c["design"] in doc["designs"] and c["steps"][0]["r_from"] == 0.0
        names = {x["name"] for x in doc["designs"][c["design"]]["cells"]}
        for s in c["steps"]:
            assert s["min"] is None or 0 <= s["min"] <= c["kmax"]
            if s["min"] is None:
                assert s["witness"] is None and s["searched_k"] <= c["kmax"]
            else:
                assert len(s["witness"]["shots"]) == s["min"]
                assert all(set(x["cells"]) <= names and 0 <= x["cycle"] < c["T"] for x in s["witness"]["shots"])
    # r = 0 reproduces the per-cell single-fault minimum in every flip curve of the main family
    for c in doc["curves"]:
        if c["effect"] == "flip" and c["targets"] == "all" and c["T"] == 6 and c["goal"] == "word":
            assert c["steps"][0]["min"] == (1 if c["design"] == "v1" else 3)
