"""Countermeasure intent read from C firmware source (text scan, no compiler).

Detected automatically:
  repeated check   the same `if (condition)` written two or more times in one function. Conditions are compared after
                   removing whitespace, value-barrier macros (LAUNDER(x), launder32(x), casts) and after replacing a
                   local variable by the expression it was initialised with, so
                       int r1 = cmp(a, b); if (r1 != 0) fail();
                       int r2 = cmp(a, b); if (r2 != 0) alarm();
                   is one check written twice.
  flow counter     a variable (or a macro that updates one) stepped at two or more places in a function and compared
                   in an `if`.
Optional annotation: a comment `/* cm: repeat NAME */` on an `if` line puts it into group NAME by hand;
`/* cm: ignore */` removes a line from automatic grouping.
"""
import re

from .model import Countermeasure

BARRIERS = ("LAUNDER", "LAUNDER_PTR", "launder32", "launderw", "barrier32", "HARDENED_CHECK", "volatile")
_CTRL = {"if", "while", "for", "switch", "return", "sizeof", "else", "do"}


def _strip(text):
    marks = {}
    for m in re.finditer(r"/\*\s*cm:\s*(\w+)\s*(\w*)\s*\*/|//\s*cm:\s*(\w+)\s*(\w*)", text):
        marks[text.count("\n", 0, m.start()) + 1] = ((m.group(1) or m.group(3)), (m.group(2) or m.group(4)))

    def keep_nl(m):
        return re.sub(r"[^\n]", " ", m.group(0))
    text = re.sub(r"/\*.*?\*/", keep_nl, text, flags=re.S)
    text = re.sub(r"//[^\n]*", keep_nl, text)
    text = re.sub(r'"(?:\\.|[^"\\])*"', lambda m: '"' + " " * (len(m.group(0)) - 2) + '"', text)
    return text, marks


def _match(text, i, open_="(", close=")"):
    depth = 0
    for j in range(i, len(text)):
        if text[j] == open_:
            depth += 1
        elif text[j] == close:
            depth -= 1
            if depth == 0:
                return j
    return -1


def functions(text):
    """(name, body_start, body_end) of every function definition (brace-matched, file scope)."""
    out = []
    for m in re.finditer(r"\b([A-Za-z_]\w*)\s*\(([^;{}()]|\([^()]*\))*\)\s*(?:__attribute__\s*\(\(.*?\)\)\s*)?\{", text):
        if m.group(1) in _CTRL:
            continue
        if text.count("{", 0, m.start()) != text.count("}", 0, m.start()):
            continue
        e = _match(text, m.end() - 1, "{", "}")
        if e > 0:
            out.append((m.group(1), m.end(), e))
    return out


def _unbarrier(e):
    prev = None
    while prev != e:
        prev = e
        for b in BARRIERS:
            i = e.find(b + "(")
            while i >= 0:
                j = _match(e, i + len(b))
                if j < 0:
                    break
                e = e[:i] + "(" + e[i + len(b) + 1:j] + ")" + e[j + 1:]
                i = e.find(b + "(")
        e = re.sub(r"\((?:u?int\d+_t|unsigned|int|size_t|uintptr_t)\)", "", e)
    return e


def _norm(e, alias):
    e = _unbarrier(re.sub(r"\s+", "", e))
    for _ in range(4):
        e2 = re.sub(r"\b[A-Za-z_]\w*\b", lambda m: "(" + alias[m.group(0)] + ")" if m.group(0) in alias else m.group(0), e)
        if e2 == e:
            break
        e = e2
    e = _unbarrier(e)
    prev = None
    while prev != e:                      # drop redundant parentheses: ((x)) -> (x), (name) -> name, (whole) -> whole
        prev = e
        e = re.sub(r"(?<![\w)])\((\w+)\)", r"\1", e)
        for i, ch in enumerate(e):
            if ch == "(" and e[i + 1:i + 2] == "(":
                j = _match(e, i)
                if j > 0 and _match(e, i + 1) == j - 1:
                    e = e[:i] + e[i + 1:j] + e[j + 1:]
                    break
        if e.startswith("(") and _match(e, 0) == len(e) - 1:
            e = e[1:-1]
    e = re.sub(r"(?<![\w)])\(([A-Za-z_]\w*\((?:[^()]|\([^()]*\))*\))\)", r"\1", e)   # (f(args)) -> f(args)
    return e


def scan_file(path, only=None):
    with open(path, encoding="utf-8", errors="replace") as f:
        raw = f.read()
    text, marks = _strip(raw)
    macros = {m.group(1): m.group(2) for m in re.finditer(r"^[ \t]*#\s*define\s+(\w+)\(\)\s+(.+)$", text, re.M)}
    out = []
    for fname, s, e in functions(text):
        if only and fname not in only:
            continue
        body = text[s:e]
        line0 = text.count("\n", 0, s) + 1
        alias, counts = {}, {}
        for m in re.finditer(r"(?:^|[;{}])\s*(?:[A-Za-z_]\w*[\s\*]+)+([A-Za-z_]\w*)\s*=\s*([^;]+);", body):
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
            alias[m.group(1)] = re.sub(r"\s+", "", m.group(2))
        for m in re.finditer(r"(?:^|[;{}])\s*([A-Za-z_]\w*)\s*(?:[-+*/|&^]?=)(?!=)", body):
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
        alias = {k: _unbarrier(v) for k, v in alias.items() if counts.get(k, 0) == 1 and not re.fullmatch(r"[\w.]+", v)}
        calls_in = {}
        ifs = []
        for m in re.finditer(r"\bif\s*\(", body):
            j = _match(body, m.end() - 1)
            if j < 0:
                continue
            cond = body[m.end():j]
            k = j + 1
            while k < len(body) and body[k].isspace():
                k += 1
            end = _match(body, k, "{", "}") if body[k:k + 1] == "{" else body.find(";", k)
            stmt = body[k:end + 1]
            hm = re.search(r"\b([A-Za-z_]\w*)\s*\(", stmt)
            l1 = line0 + body.count("\n", 0, m.start())
            l2 = line0 + body.count("\n", 0, max(end, j))
            mark = next((marks[l] for l in range(l1, l2 + 1) if l in marks), None)
            if mark and mark[0] == "ignore":
                continue
            raw_vars = set(re.findall(r"\b[A-Za-z_]\w*\b", cond))
            inits = {v: alias[v] for v in raw_vars if v in alias}
            callee = sorted({c for v in list(inits.values()) + [cond] for c in re.findall(r"\b([A-Za-z_]\w*)\s*\(", v)
                             if c not in BARRIERS and c not in _CTRL})
            ifs.append(dict(line=l1, end=l2, cond=re.sub(r"\s+", " ", cond.strip()), norm=_norm(cond, alias),
                            handler=hm.group(1) if hm and hm.group(1) not in _CTRL else None, callees=callee,
                            group=mark[1] if mark and mark[0] == "repeat" else None))
        groups = {}
        for g in ifs:
            groups.setdefault(g["group"] or g["norm"], []).append(g)
        for key, gs in groups.items():
            if len(gs) < 2:
                continue
            out.append(Countermeasure(
                id=f"fw-repeat:{fname}:{gs[0]['line']}", kind="fw_repeated_check", origin="c-scan",
                where=f"{path}:{gs[0]['line']}",
                intent=dict(function=fname, file=str(path), copies=len(gs), condition=gs[0]["cond"],
                            guards=[dict(line=g["line"], end=g["end"], handler=g["handler"], text=g["cond"]) for g in gs],
                            callees=sorted({c for g in gs for c in g["callees"]}))))
        # flow counters
        steps = {}
        for m in re.finditer(r"\b([A-Za-z_]\w*)\s*(\+=|-=|\+\+|--)|\b([A-Za-z_]\w*)\s*=\s*\3\s*[-+]", body):
            v = m.group(1) or m.group(3)
            steps.setdefault(v, []).append(line0 + body.count("\n", 0, m.start()))
        for mac, exp in macros.items():
            mm = re.search(r"\b([A-Za-z_]\w*)\s*=", exp)
            if mm and re.search(r"\b" + mm.group(1) + r"\b\s*[-+]", _unbarrier(re.sub(r"\s+", "", exp))):
                for m in re.finditer(r"\b" + mac + r"\s*\(\s*\)", body):
                    steps.setdefault(mm.group(1), []).append(line0 + body.count("\n", 0, m.start()))
        for v, lines in steps.items():
            chk = [g for g in ifs if re.search(r"\b" + re.escape(v) + r"\b", g["cond"])
                   and not re.search(r"\b" + re.escape(v) + r"\s*(<|<=)\s*\w+\s*$", g["cond"])]
            if len(set(lines)) >= 2 and chk and not re.search(r"\bfor\s*\([^;]*\b" + re.escape(v) + r"\b", body):
                out.append(Countermeasure(
                    id=f"fw-flow:{fname}:{v}", kind="fw_flow_counter", origin="c-scan", where=f"{path}:{sorted(lines)[0]}",
                    intent=dict(function=fname, file=str(path), variable=v, steps=sorted(set(lines)),
                                checks=[dict(line=g["line"], end=g["end"], handler=g["handler"], text=g["cond"]) for g in chk])))
    return out


def scan(paths_, only=None):
    out = []
    for p in paths_:
        out += scan_file(p, only)
    return out
