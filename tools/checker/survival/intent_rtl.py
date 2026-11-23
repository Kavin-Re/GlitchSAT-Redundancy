"""Countermeasure intent read from Verilog / SystemVerilog source text (no elaboration, no synthesis tool).

Automatic detection (the designer writes nothing):
  redundant copies      two or more instances of one module with the same input connections and different outputs
  sparse encoding       a register (or enum type) whose code constants are pairwise at Hamming distance >= 2
  multi-bit boolean     OpenTitan mubi types; or an equality test against a constant whose complement is also used
  redundant register    register pairs named X / X_n, X_dup, X_shadow, X_chk ... of equal width
  alarm                 output ports named alarm / alert / fault / tamper / err

Optional annotations (Verilog attributes, kept by Yosys in its JSON, so they also work on netlists):
  (* cm_copies = "name" *)      on each instance or wire that is one copy of group "name"
  (* cm_sparse *)               on a state register          (* cm_sparse = "f0,cc,96,69" *) to list the codes
  (* cm_mubi = "96" *)          on a multi-bit boolean; the value is the TRUE code (hex)
  (* cm_dup = "name" *)         on each register of a redundant group
  (* cm_alarm *)                on an alarm signal

This is a text scan: it reads declarations, instances and sized constants. It does not evaluate parameters,
generate blocks or macros; what it cannot read it does not report (the YAML file can state it instead).
"""
import re

from .gnet import hamming, min_distance
from .model import Countermeasure

_KEYWORDS = set("module endmodule input output inout wire reg logic assign always always_ff always_comb always_latch "
                "begin end if else case casez casex endcase default initial localparam parameter typedef enum struct "
                "function endfunction generate endgenerate for genvar posedge negedge or and not unique priority "
                "import package endpackage return int integer bit signed unsigned packed".split())
_LIT = re.compile(r"(\d+)\s*'\s*([bhdoBHDO])\s*([0-9a-fA-F_xzXZ?]+)")
_ATTR = re.compile(r"\(\*\s*(.*?)\s*\*\)", re.S)
_ALARM = re.compile(r"(alarm|alert|fault|tamper|glitch_det|(^|_)err(or)?(_|$))", re.I)
_DUP_SUFFIX = r"(?:_n|_b|_inv|_dup|_shadow|_shd|_chk|_red|_copy|_q2|_2)"


def _lit_value(m):
    w, base, digits = int(m.group(1)), m.group(2).lower(), m.group(3).replace("_", "")
    if re.search(r"[xz?]", digits, re.I):
        return w, None
    return w, int(digits, {"b": 2, "h": 16, "d": 10, "o": 8}[base]) & ((1 << w) - 1)


def _strip_comments(text):
    def keep_nl(m):
        return re.sub(r"[^\n]", " ", m.group(0))
    text = re.sub(r"/\*.*?\*/", keep_nl, text, flags=re.S)
    return re.sub(r"//[^\n]*", keep_nl, text)


def _line(text, pos):
    return text.count("\n", 0, pos) + 1


def _attrs(s):
    """'cm_copies = "x", keep' -> {'cm_copies': 'x', 'keep': '1'}"""
    out = {}
    for part in re.split(r",(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", s):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip().strip('"')
        elif part.strip():
            out[part.strip()] = "1"
    return out


def _width(rng, params):
    if not rng:
        return 1
    m = re.match(r"\[\s*(.+?)\s*:\s*(.+?)\s*\]", rng)
    if not m:
        return None
    try:
        hi = int(eval(m.group(1), {"__builtins__": {}}, dict(params)))
        lo = int(eval(m.group(2), {"__builtins__": {}}, dict(params)))
        return abs(hi - lo) + 1
    except Exception:
        return None


def scan_file(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        raw = f.read()
    text = _strip_comments(raw)
    out = []
    enums = _enums(text, path)
    mods = list(re.finditer(r"\bmodule\s+(\w+)\b(.*?)\bendmodule\b", text, re.S))
    modnames = {m.group(1) for m in mods}
    for m in mods:
        out += _scan_module(path, text, m.start(2), m.group(1), m.group(2), modnames, enums)
    if not mods:                                    # a package: report its sparse enums on their own
        for e in enums.values():
            if e["sparse"]:
                out.append(_enum_cm(path, e, None, []))
    return out


def _enums(text, path):
    enums = {}
    for m in re.finditer(r"typedef\s+enum\s+(?:logic|bit|reg)?\s*(\[[^\]]+\])?\s*\{(.*?)\}\s*(\w+)\s*;", text, re.S):
        codes = {}
        for item in m.group(2).split(","):
            mm = re.match(r"\s*(\w+)\s*=\s*(.+?)\s*$", item, re.S)
            if mm:
                lm = _LIT.search(mm.group(2))
                if lm:
                    w, v = _lit_value(lm)
                    if v is not None:
                        codes[mm.group(1)] = (w, v)
        if len(codes) >= 2:
            w = max(x[0] for x in codes.values())
            vals = [v for _, v in codes.values()]
            d = min_distance(vals)
            enums[m.group(3)] = dict(name=m.group(3), width=w, codes={k: v for k, (_, v) in codes.items()}, min_distance=d,
                                     sparse=bool(d and d >= 2 and w >= 3), line=_line(text, m.start()))
    return enums


def _enum_cm(path, e, module, regs):
    reg = regs[0] if regs else e["name"]
    return Countermeasure(
        id=f"encoding:{module + '.' if module else ''}{reg}", kind="sparse_encoding", origin="rtl-scan",
        where=f"{path}:{e['line']}",
        intent=dict(register=reg, aliases=regs[1:], module=module, width=e["width"], codes=sorted(e["codes"].values()),
                    code_names={k: v for k, v in e["codes"].items()}, min_distance=e["min_distance"], enum=e["name"]))


def _scan_module(path, text, off, name, body, modnames, enums):
    out = []
    params = {}
    for m in re.finditer(r"\b(?:localparam|parameter)\b[^=;]*?\b(\w+)\s*=\s*([^;,)]+)", body):
        v = m.group(2).strip()
        lm = _LIT.fullmatch(v)
        try:
            params[m.group(1)] = _lit_value(lm)[1] if lm else int(eval(v, {"__builtins__": {}}, dict(params)))
        except Exception:
            pass
    # ---- declarations, with the attribute in front of them
    decls = {}   # name -> dict(kind, width, line, attrs)
    for m in re.finditer(r"(\(\*[^)]*?\*\)\s*)?\b(input|output|inout)?\s*\b(wire|reg|logic)\b\s*(signed\s*)?(\[[^\]]+\])?\s*(?=\w)", body):
        attrs = _attrs(_ATTR.match(m.group(1).strip()).group(1)) if m.group(1) else {}
        w = _width(m.group(5), params)
        rest = body[m.end():body.find(";", m.end()) if body.find(";", m.end()) >= 0 else len(body)]
        depth, piece, pieces = 0, "", []
        for ch in rest:
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
                if depth < 0:
                    break
            if ch == "," and depth == 0:
                pieces.append(piece)
                piece = ""
            else:
                piece += ch
        pieces.append(piece)
        pos = m.end()
        for k, pc in enumerate(pieces):
            mm = re.match(r"\s*(\w+)\s*(=|$)", pc, re.S)
            if mm and mm.group(1) not in _KEYWORDS:
                decls[mm.group(1)] = dict(kind=m.group(3), dir=m.group(2), width=w, line=_line(text, off + pos), attrs=attrs)
            elif k:
                break
            pos += len(pc) + 1
    for m in re.finditer(r"\b(input|output)\s+(?:wire\s+|logic\s+|reg\s+)?(\[[^\]]+\])?\s*(\w+)", body):
        if m.group(3) not in decls and m.group(3) not in _KEYWORDS:
            decls[m.group(3)] = dict(kind="wire", dir=m.group(1), width=_width(m.group(2), params),
                                     line=_line(text, off + m.start(3)), attrs={})
    # ---- instances
    inst = []
    for m in re.finditer(r"(\(\*[^)]*?\*\)\s*)?\b(\w+)\s*(#\s*\((?:[^()]|\([^()]*\))*\)\s*)?\b(\w+)\s*\(((?:[^();]|\([^()]*\))*)\)\s*;", body):
        typ, iname = m.group(2), m.group(4)
        if typ in _KEYWORDS or iname in _KEYWORDS or not re.search(r"\.\w+\s*\(", m.group(5)):
            continue
        con = {p: re.sub(r"\s+", "", e) for p, e in re.findall(r"\.(\w+)\s*\(((?:[^()]|\([^()]*\))*)\)", m.group(5))}
        attrs = _attrs(_ATTR.match(m.group(1).strip()).group(1)) if m.group(1) else {}
        inst.append(dict(type=typ, name=iname, params=re.sub(r"\s+", "", m.group(3) or ""), con=con,
                         line=_line(text, off + m.start(2)), attrs=attrs))
    groups = {}
    for i in inst:
        groups.setdefault(i["attrs"].get("cm_copies") or (i["type"], i["params"]), []).append(i)
    for key, g in groups.items():
        if len(g) < 2:
            continue
        pins = set.intersection(*[set(i["con"]) for i in g])
        same = sorted(p for p in pins if len({i["con"][p] for i in g}) == 1 and g[0]["con"][p] not in ("clk", "clk_i", "rst_ni", "rst_n", "rst"))
        diff = sorted(p for p in pins if len({i["con"][p] for i in g}) == len(g))
        annotated = isinstance(key, str)
        if not annotated and (not same or not diff):
            continue
        out.append(Countermeasure(
            id=f"copies:{name}.{key if annotated else g[0]['type']}", kind="redundant_copies",
            origin="annotation" if annotated else "rtl-scan", where=f"{path}:{g[0]['line']}",
            intent=dict(copies=len(g), module=name, cell=g[0]["type"], instances=[i["name"] for i in g],
                        same_inputs={p: g[0]["con"][p] for p in same},
                        outputs={i["name"]: {p: i["con"][p] for p in diff} for i in g},
                        what=f"{g[0]['type']}({', '.join(g[0]['con'][p] for p in same)})")))
    wg = {}
    for nm, d in decls.items():
        if d["attrs"].get("cm_copies"):
            wg.setdefault(d["attrs"]["cm_copies"], []).append(nm)
    for key, names in wg.items():
        if len(names) >= 2:
            out.append(Countermeasure(id=f"copies:{name}.{key}", kind="redundant_copies", origin="annotation",
                                      where=f"{path}:{decls[names[0]]['line']}",
                                      intent=dict(copies=len(names), module=name, instances=[], nets=names, what=key)))
    # ---- sparse encodings: enum-typed registers, then plain registers with sized constants
    for en, e in enums.items():
        regs = [v for mm in re.finditer(r"\b" + re.escape(en) + r"\s+([\w\s,]+?)\s*;", body)
                for v in re.split(r"\s*,\s*", mm.group(1).strip())]
        if regs and e["sparse"]:
            regs.sort(key=lambda r: (not re.search(r"(_q|_cs|_reg)$", r), r))
            out.append(_enum_cm(path, e, name, regs))
    lits = {}
    for m in _LIT.finditer(body):
        w, v = _lit_value(m)
        if v is not None and w >= 3:
            lits.setdefault(w, {}).setdefault(v, _line(text, off + m.start()))
    sized = {}
    for m in re.finditer(r"\blocalparam\s*(?:\[[^\]]+\])?\s*(\w+)\s*=\s*" + _LIT.pattern + r"\s*[;,]", body):
        w, v = _lit_value(_LIT.search(m.group(0)))
        if v is not None:
            sized[m.group(1)] = (w, v)
    regs = {n: d for n, d in decls.items() if d["kind"] in ("reg", "logic") and d["width"] and d["width"] >= 3}
    for rn, d in regs.items():
        ann = d["attrs"].get("cm_sparse")
        codes = set()
        if ann and ann != "1":
            codes = {int(x, 16) for x in re.split(r"[,\s]+", ann) if x}
        else:
            # constants assigned to / compared with / used as case labels of this register
            for m in re.finditer(r"\b" + re.escape(rn) + r"\s*(?:<=|==|!=|=)\s*" + _LIT.pattern, body):
                w, v = _lit_value(re.match(_LIT.pattern, body[m.start(1) - 0:m.end()]) or _LIT.search(m.group(0)))
                if v is not None:
                    codes.add(v)
            for m in re.finditer(r"\b" + re.escape(rn) + r"\s*(?:<=|==|!=)\s*([A-Za-z_]\w*)\b", body):
                if m.group(1) in sized and sized[m.group(1)][0] == d["width"]:
                    codes.add(sized[m.group(1)][1])
            for cm_ in re.finditer(r"\bcase[zx]?\s*\(\s*" + re.escape(rn) + r"\s*\)(.*?)\bendcase\b", body, re.S):
                for m in re.finditer(_LIT.pattern + r"\s*(?:,|:)", cm_.group(1)):
                    w, v = _lit_value(m)
                    if v is not None and w == d["width"]:
                        codes.add(v)
            # values the register can take through a same-width wire built from constants (good/bad words)
            for w2, dd in decls.items():
                if dd["width"] == d["width"] and re.search(r"\b" + re.escape(rn) + r"\s*<=\s*" + re.escape(w2) + r"\b", body):
                    codes |= _wire_consts(body, w2, d["width"], decls)
        d_min = min_distance(codes)
        if (ann or (len(codes) >= 3 and d_min and d_min >= 2)) and len(codes) >= 2:
            aliases = [m.group(1) for m in re.finditer(r"\bassign\s+(\w+)\s*=\s*" + re.escape(rn) + r"\s*;", body)]
            out.append(Countermeasure(
                id=f"encoding:{name}.{rn}", kind="sparse_encoding", origin="annotation" if ann else "rtl-scan",
                where=f"{path}:{d['line']}",
                intent=dict(register=rn, aliases=aliases, module=name, width=d["width"], codes=sorted(codes), min_distance=d_min)))
    # ---- multi-bit booleans
    for nm, d in decls.items():
        if d["attrs"].get("cm_mubi"):
            t = int(d["attrs"]["cm_mubi"], 16)
            out.append(Countermeasure(id=f"mubi:{name}.{nm}", kind="mubi", origin="annotation", where=f"{path}:{d['line']}",
                                      intent=dict(signal=nm, module=name, width=d["width"], true=t,
                                                  false=t ^ ((1 << (d["width"] or 1)) - 1))))
    for m in re.finditer(r"\b(?:prim_mubi_pkg::)?mubi(\d+)_t\s+([\w\s,]+?)\s*[;,)]", body):
        for nm in re.split(r"\s*,\s*", m.group(2).strip()):
            if re.fullmatch(r"\w+", nm):
                w = int(m.group(1))
                t = {4: 0x6, 8: 0x96, 12: 0x696, 16: 0x9696}.get(w)
                out.append(Countermeasure(id=f"mubi:{name}.{nm}", kind="mubi", origin="rtl-scan",
                                          where=f"{path}:{_line(text, off + m.start())}",
                                          intent=dict(signal=nm, module=name, width=w, true=t,
                                                      false=None if t is None else t ^ ((1 << w) - 1))))
    # ---- redundant registers
    dg = {}
    for nm, d in regs.items():
        if d["attrs"].get("cm_dup"):
            dg.setdefault(d["attrs"]["cm_dup"], []).append(nm)
    allregs = {n: d for n, d in decls.items() if d["kind"] in ("reg", "logic")}
    for nm, d in allregs.items():
        for other, d2 in allregs.items():
            if other != nm and re.fullmatch(re.escape(nm) + _DUP_SUFFIX, other) and d2["width"] == d["width"] \
                    and re.search(r"\b" + re.escape(other) + r"\s*<=", body) and re.search(r"\b" + re.escape(nm) + r"\s*<=", body):
                dg.setdefault(nm, [nm]).append(other)
    for key, names in dg.items():
        names = sorted(set(names), key=len)
        if len(names) >= 2:
            out.append(Countermeasure(id=f"dup:{name}.{key}", kind="redundant_register",
                                      origin="annotation" if any(decls[n]["attrs"].get("cm_dup") for n in names) else "rtl-scan",
                                      where=f"{path}:{decls[names[0]]['line']}",
                                      intent=dict(registers=names, module=name, width=decls[names[0]]["width"])))
    # ---- alarms
    for nm, d in decls.items():
        if d["attrs"].get("cm_alarm") or (d.get("dir") == "output" and _ALARM.search(nm)):
            out.append(Countermeasure(id=f"alarm:{name}.{nm}", kind="alarm",
                                      origin="annotation" if d["attrs"].get("cm_alarm") else "rtl-scan",
                                      where=f"{path}:{d['line']}", intent=dict(signal=nm, module=name, width=d["width"])))
    return out


def _wire_consts(body, wire, width, decls):
    """Constants a wire can carry when it is a per-bit choice between same-width constant wires (V2's `word`)."""
    m = re.search(r"\b" + re.escape(wire) + r"\s*=\s*([^;]+);", body)
    if not m:
        return set()
    vals = set()
    for lm in _LIT.finditer(m.group(1)):
        w, v = _lit_value(lm)
        if w == width and v is not None:
            vals.add(v)
    for ident in set(re.findall(r"\b[A-Za-z_]\w*\b", m.group(1))):
        mm = re.search(r"\b" + re.escape(ident) + r"\s*=\s*" + _LIT.pattern + r"\s*[,;]", body)
        if mm and ident != wire:
            w, v = _lit_value(_LIT.search(mm.group(0)))
            if w == width and v is not None:
                vals.add(v)
    return vals


def scan(paths_):
    out, seen = [], set()
    for p in paths_:
        for c in scan_file(p):
            if c.id not in seen:
                seen.add(c.id)
                out.append(c)
    return out
