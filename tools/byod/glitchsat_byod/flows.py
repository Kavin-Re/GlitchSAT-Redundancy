"""Yosys runs: elaboration (what is in the design), synthesis flows, the generated monitor and the RTL reference.

Every Yosys run is a script file (`yosys -q -s`), never a shell command with user text in it. A project file is data:
every string from it that reaches a script (paths, top, defines, parameters, probe names, custom commands) is checked
against a strict pattern first, and every script line is checked again just before Yosys starts (`guard_line`): no
line breaks, no `;` or `#` outside quotes, no leading `!` (Yosys runs such a line in a shell), and the command must be
on an allow-list. Logs go to <workdir>/<step>/yosys.log.
"""
import gzip
import json
import os
import re
import shutil
import subprocess

from .errors import GSError

_BAD_PATH = re.compile(r'[\x00-\x1f\x7f"\'`;#]')
_IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_$]*$')


def check_path(p, what='file'):
    if not isinstance(p, str) or not p or p.startswith('-') or _BAD_PATH.search(p):
        raise GSError('GS003', '%s path %r cannot be used' % (what, p),
                      help='use a plain path without quotes, ";", "#", control characters, and not starting with "-"')
    return p


def check_ident(n, what='name'):
    if not isinstance(n, str) or not _IDENT.match(n):
        raise GSError('GS002', '%s %r is not a plain Verilog identifier' % (what, n),
                      help='use letters, digits, `_` and `$` only, starting with a letter or `_`')
    return n


_HIER = re.compile(r'^[A-Za-z_][A-Za-z0-9_$]*(\.[A-Za-z_][A-Za-z0-9_$]*)*$')
_DEF_NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_DEF_VAL = re.compile(r"^[A-Za-z0-9_.'+-]*$")


def check_hier(n, what='signal'):
    """A dotted hierarchical name (u_core.u_ctrl.state_q), each part a plain identifier."""
    if not isinstance(n, str) or not _HIER.match(n):
        raise GSError('GS002', '%s %r is not a plain (dotted) Verilog name' % (what, n),
                      help='write it as instance.instance.signal with plain identifiers (letters, digits, `_`, `$`)')
    return n


def check_define(k, v):
    if not isinstance(k, str) or not _DEF_NAME.match(k):
        raise GSError('GS002', 'define name %r is not a plain identifier' % (k,), help='use letters, digits and `_` only')
    if v is not None and (isinstance(v, (dict, list)) or not _DEF_VAL.match(str(v))):
        raise GSError('GS002', 'value of define `%s` (%r) is not a plain value' % (k, v),
                      help="use a number or a word (letters, digits, `_ . ' + -`); no spaces, quotes, `;` or line breaks")
    return k, v


# Commands GlitchSAT itself writes into scripts, and the extra ones a custom flow (`design.yosys_script`) may use.
# Anything else is refused: in particular `!` (shell), `shell`, `exec`, `script`, `tee`, `plugin`, `tcl`, `python`,
# every `write_*`, and options that write files or start programs (`-o`, `-write`, `-exe`, `-script`).
OWN_CMDS = {'read_verilog', 'read_liberty', 'read_json', 'read_slang', 'hierarchy', 'proc', 'opt_dff', 'opt_clean', 'memory',
            'techmap', 'abc', 'setattr', 'flatten', 'synth', 'dfflibmap', 'write_json', 'connect', 'dffunmap', 'delete'}
USER_CMDS = {'synth', 'proc', 'opt', 'opt_clean', 'opt_expr', 'opt_merge', 'opt_dff', 'opt_reduce', 'opt_muxtree', 'opt_share',
             'flatten', 'hierarchy', 'techmap', 'simplemap', 'abc', 'fsm', 'fsm_detect', 'fsm_extract', 'fsm_opt', 'fsm_recode',
             'fsm_map', 'memory', 'memory_map', 'memory_collect', 'memory_dff', 'memory_share', 'memory_memx', 'wreduce',
             'alumacc', 'share', 'peepopt', 'pmuxtree', 'muxcover', 'muxpack', 'dfflegalize', 'dffunmap', 'dfflibmap', 'dffinit',
             'setattr', 'setparam', 'chparam', 'rename', 'select', 'splitnets', 'clean', 'check', 'stat', 'async2sync', 'delete',
             'hilomap', 'insbuf', 'deminout', 'tribuf', 'connect', 'expose', 'extract_fa', 'bmuxmap', 'demuxmap', 'chtype',
             'attrmap', 'attrmvcp', 'read_verilog', 'read_liberty', 'read_json', 'read_rtlil', 'read', 'design', 'log'}
FORBIDDEN_OPTS = {'-o', '-write', '-exe', '-script', '-save', '-push', '-pop', '-stash', '-copy-from', '-copy-to', '-import'}
FILE_CMDS = {'read_verilog', 'read_liberty', 'read_json', 'read_rtlil', 'read'}
FILE_OPTS = {'-map', '-liberty', '-constr', '-libdir', '-read', '-lut'}


def _scan_line(line):
    """Problems of one script line outside double quotes: (has_semicolon_or_hash, first_word)."""
    inq = False
    for ch in line:
        if ch == '"':
            inq = not inq
        elif not inq and ch in ';#':
            return True
    return False


def guard_line(line):
    """Last check before a line goes into script.ys (defence in depth; user strings were checked when read)."""
    if not isinstance(line, str) or re.search(r'[\x00-\x1f\x7f]', line):
        raise GSError('GS002', 'a Yosys command contains a line break or control character: %r' % (line,),
                      help='project values must not contain line breaks')
    t = line.strip()
    if t.startswith('!'):
        raise GSError('GS002', 'a Yosys command starts with `!` (that would run a shell command): %r' % line)
    if _scan_line(t):
        raise GSError('GS002', 'a Yosys command contains `;` or `#` outside quotes: %r' % line,
                      help='one command per line; no `;` and no comments inside values')
    w = t.split()[0] if t.split() else ''
    if w not in OWN_CMDS | USER_CMDS:
        raise GSError('GS002', 'Yosys command `%s` is not allowed' % w)
    return line


def check_user_script(lines, base, extra_roots=()):
    """`design.yosys_script` (flow `custom`): only allow-listed commands; files read must be inside the project folder
    (or a Liberty folder). Returns the lines with file arguments made absolute and quoted."""
    if isinstance(lines, str):
        lines = lines.splitlines()
    out = []
    roots = [os.path.realpath(base)] + [os.path.realpath(r) for r in extra_roots if r]
    for raw in lines or []:
        if not isinstance(raw, str):
            raise GSError('GS002', '`design.yosys_script` entries must be strings, not %r' % (raw,))
        if re.search(r'[\x00-\x1f\x7f]', raw):
            raise GSError('GS002', '`design.yosys_script` line contains a line break or control character: %r' % raw)
        for cmd in raw.split(';'):
            t = cmd.strip()
            if not t or t.startswith('#'):
                continue
            if t.startswith('!'):
                raise GSError('GS002', '`design.yosys_script` line %r would run a shell command' % t,
                              help='a project file cannot run programs; only Yosys synthesis commands are allowed (see docs/SCHEMA.md)')
            if any(c in t for c in '"#`\'\\'):
                raise GSError('GS002', '`design.yosys_script` line %r contains a quote, backslash or `#`' % t,
                              help='write file names without quotes; paths with spaces cannot be used here')
            toks = t.split()
            w = toks[0]
            if w not in USER_CMDS:
                raise GSError('GS002', 'Yosys command `%s` is not allowed in `design.yosys_script`' % w,
                              help='allowed: synthesis and transformation commands (%s, ...). Never allowed: `!`, shell, exec, '
                                   'script, tee, plugin, tcl, python, write_*' % ', '.join(sorted(USER_CMDS)[:12]))
            res = [w]
            i = 1
            while i < len(toks):
                tk = toks[i]
                if tk in FORBIDDEN_OPTS or tk.startswith('-exe') or tk.startswith('-script'):
                    raise GSError('GS002', 'option `%s` of `%s` is not allowed in `design.yosys_script`' % (tk, w),
                                  help='options that write files or start programs are refused')
                if tk in FILE_OPTS and i + 1 < len(toks):
                    res.append(tk)
                    res.append(_user_path(toks[i + 1], base, roots, w))
                    i += 2
                    continue
                if w in FILE_CMDS and not tk.startswith('-'):
                    res.append(_user_path(tk, base, roots, w))
                else:
                    res.append(tk)
                i += 1
            out.append(' '.join(res))
    return out


def _user_path(tk, base, roots, w):
    if tk.startswith('+/'):                               # Yosys's own share folder (techmap -map +/techmap.v)
        if '..' in tk.split('/'):
            raise GSError('GS002', 'path %r in `design.yosys_script` (%s) leaves the Yosys share folder' % (tk, w))
        return tk
    if re.fullmatch(r'\d+', tk):
        return tk
    check_path(tk, 'yosys_script')
    p = os.path.realpath(os.path.join(base, os.path.expanduser(tk)))
    if not any(p == r or p.startswith(r + os.sep) for r in roots):
        raise GSError('GS002', 'path %r in `design.yosys_script` (%s) is outside the project folder' % (tk, w),
                      help='files a custom flow reads must be inside the folder of glitchsat.yaml')
    return '"%s"' % p


# ------------------------------------------------------------------ tools

class Yosys:
    def __init__(self, path):
        self.path = path
        try:
            r = subprocess.run([path, '-V'], capture_output=True, text=True, timeout=30)
            self.version = (r.stdout or r.stderr).strip().splitlines()[0]
        except Exception as e:                                   # noqa: BLE001
            raise GSError('GS021', 'Yosys at %s could not be started: %s' % (path, e))
        m = re.search(r'Yosys (\d+)\.(\d+)', self.version)
        self.vnum = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
        self._slang = None

    @property
    def has_slang(self):
        if self._slang is None:
            r = subprocess.run([self.path, '-p', 'help read_slang'], capture_output=True, text=True, timeout=60)
            self._slang = r.returncode == 0 and 'read_slang' in r.stdout and 'No such command' not in r.stdout
        return self._slang

    def short(self):
        m = re.search(r'Yosys [0-9.+a-z]+', self.version)
        return m.group(0) if m else self.version


_CACHE = {}


def find_yosys(need_slang=False, newest=False):
    """newest: pick the newest Yosys among the candidates (used for gate-level netlists: Yosys 0.33 reads the Liberty
    clear_preset_var rule wrongly, GS046)."""
    key = ('slang' if need_slang else 'plain') + ('+new' if newest else '')
    if key in _CACHE:
        return _CACHE[key]
    if newest and not need_slang:
        found = []
        for c in [os.environ.get('GLITCHSAT_YOSYS'), shutil.which('yosys'), os.environ.get('GLITCHSAT_YOSYS_SLANG')]:
            if c and os.path.isfile(c) and os.access(c, os.X_OK):
                try:
                    found.append(Yosys(c))
                except GSError:
                    pass
        if found:
            y = max(found, key=lambda y: y.vnum)
            _CACHE[key] = y
            return y
    cands = []
    if need_slang:
        cands += [os.environ.get('GLITCHSAT_YOSYS_SLANG'), os.environ.get('GLITCHSAT_YOSYS'), shutil.which('yosys'),
                  os.path.expanduser('~/oss-cad-suite/bin/yosys')]
    else:
        cands += [os.environ.get('GLITCHSAT_YOSYS'), shutil.which('yosys'), os.environ.get('GLITCHSAT_YOSYS_SLANG')]
    for c in cands:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            y = Yosys(c)
            if need_slang and not y.has_slang:
                continue
            _CACHE[key] = y
            return y
    if need_slang:
        raise GSError('GS021', 'no Yosys with the SystemVerilog frontend read_slang was found',
                      help='install Yosys 0.67 or newer (it includes read_slang), set GLITCHSAT_YOSYS_SLANG=/path/to/yosys, '
                           'or set `design.frontend: verilog` for simple SystemVerilog')
    raise GSError('GS021', 'Yosys was not found',
                  help='install Yosys 0.33 or newer (Debian/Ubuntu: sudo apt-get install -y yosys) or set GLITCHSAT_YOSYS=/path/to/yosys. '
                       'Every input path needs it, gate-level netlists and Yosys JSON included')


def run(ys, cmds, workdir, step, timeout=600):
    """Run a Yosys script. Returns the log text. Errors become GS022/GS023 with the relevant log lines."""
    d = os.path.join(workdir, step)
    os.makedirs(d, exist_ok=True)
    scr = os.path.join(d, 'script.ys')
    for c in cmds:
        guard_line(c)
    with open(scr, 'w') as f:
        f.write('\n'.join(cmds) + '\n')
    log = os.path.join(d, 'yosys.log')
    try:
        r = subprocess.run([ys.path, '-q', '-l', log, '-s', scr], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise GSError('GS022', 'Yosys (%s) did not finish within %d s' % (step, timeout))
    text = open(log).read() if os.path.isfile(log) else ''
    if r.returncode != 0:
        err = (r.stderr or '') + '\n' + text
        m = re.search(r"Module [`\\']*\\?([^\s'`]+)'? referenced in module [`\\']*\\?([^\s'`]+)'? in cell [`\\']*\\?([^\s'`]+)'? is not part of the design", err)
        if m:
            raise GSError('GS023', 'module `%s` is used by instance `%s` in `%s` but is not defined in the sources' % (m.group(1), m.group(3), m.group(2)),
                          help='add the file that defines `%s` to `design.sources`, or declare it as a black box: '
                               '`design.blackboxes: [{module: %s, stub: path/to/%s_stub.v}]`' % (m.group(1), m.group(1), m.group(1)))
        m2 = re.search(r'unknown module type[^\n]*?([A-Za-z_][\w$]*)', err, re.I)
        if m2 and 'slang' in ' '.join(cmds):
            raise GSError('GS023', 'module `%s` is used but not defined in the sources' % m2.group(1),
                          help='add its source to `design.sources`, or declare it under `design.blackboxes` with a stub')
        lines = []
        for ln in err.splitlines():
            if ln.strip() and ln.strip() not in lines:
                lines.append(ln.strip())
        errl = [ln for ln in lines if 'ERROR' in ln or 'error' in ln][:6] or lines[-6:]
        raise GSError('GS022', 'Yosys failed in step `%s`' % step, note='\n'.join(errl[-6:]),
                      help='the full log is %s' % os.path.relpath(log))
    return text


# ------------------------------------------------------------------ reading the sources

def frontend_of(spec):
    fe = spec['frontend']
    if fe != 'auto':
        return fe
    srcs = spec['sources']
    if srcs and all(s.endswith('.json') for s in srcs):
        return 'json'
    if spec.get('liberty') and spec.get('netlist_input'):
        return 'netlist'
    if any(s.endswith(('.sv', '.svh')) for s in srcs):
        try:
            find_yosys(need_slang=True)
            return 'slang'
        except GSError:
            return 'verilog'
    return 'verilog'


def read_cmds(spec, ys, top=None, for_ref=False, preview=False):
    """Commands that read the design sources (and black-box stubs). For a gate-level netlist, the Liberty cells are
    read as functional modules (Yosys's own reading of the Liberty functions): used to elaborate and as the reference."""
    fe = frontend_of(spec)
    out = []
    if fe == 'netlist':
        libs = spec.get('liberty') or []
        if not libs:
            raise GSError('GS026', 'a gate-level netlist needs the Liberty file of its cells', help='add `design.liberty: [path/to/cells.lib]`')
        tmpd = os.path.join(spec.get('out') or '/tmp', 'tmp_lib')
        for p in libs:
            if p.endswith('.gz') and not preview:
                os.makedirs(tmpd, exist_ok=True)
                p = _lib_arg(p, tmpd)
            out.append('read_liberty -ignore_miss_func -ignore_miss_dir -ignore_miss_data_latch "%s"' % check_path(p, 'liberty'))
    for bb in spec.get('blackboxes') or []:
        if bb.get('stub'):
            out.append('read_verilog -sv -lib "%s"' % check_path(bb['stub'], 'black-box stub'))
    dl = [check_define(k, v) for k, v in (spec.get('defines') or {}).items()]
    defs = ' '.join('-D%s=%s' % (k, v) if v is not None else '-D%s' % k for k, v in dl)
    incs = ' '.join('-I"%s"' % check_path(i, 'include dir') for i in spec.get('include_dirs') or [])
    if fe == 'slang':
        files = ' '.join(_nospace(check_path(s)) for s in spec['sources'])
        gp = ' '.join('-G %s=%s' % (check_ident(k, 'parameter'), _pval(v)) for k, v in (spec.get('params') or {}).items())
        incs2 = ' '.join('-I %s' % _nospace(check_path(i, 'include dir')) for i in spec.get('include_dirs') or [])
        defs2 = ' '.join('-D %s=%s' % (k, v) if v is not None else '-D %s' % k for k, v in dl)
        t = '--top %s' % check_ident(top, 'top module') if top else ''
        out.append('read_slang %s %s %s %s %s' % (incs2, defs2, gp, t, files))
    elif fe == 'json':
        for s in spec['sources']:
            out.append('read_json "%s"' % check_path(s))
    elif fe in ('verilog', 'netlist'):
        for s in spec['sources']:
            sv = '-sv ' if s.endswith(('.sv', '.svh')) or fe == 'verilog' else ''
            out.append('read_verilog %s%s %s "%s"' % (sv, defs, incs, check_path(s)))
        if fe == 'netlist':
            for pat in physical_found(spec):
                out.append('delete t:%s' % pat)
    else:
        raise GSError('GS025', 'frontend %r cannot be read by Yosys here' % fe)
    return out


def physical_found(spec):
    """Patterns of `design.physical_cells` that match an instance in the netlist sources (taps, fillers, decaps,
    diodes: no logic function). Counts are kept in spec['physical_dropped'] {cell type: n}."""
    import fnmatch
    pats = spec.get('physical_cells') or []
    if not pats:
        return []
    cnt = {}
    rx = re.compile(r'^\s*\\?([A-Za-z_][\w$]*)\s+(?:#\s*\(.*?\)\s*)?\\?[^\s(]+\s*\(', re.M)
    for src in spec['sources']:
        try:
            text = open(src, errors='replace').read()
        except OSError:
            continue
        for m in rx.finditer(text):
            t = m.group(1)
            if t in ('module', 'input', 'output', 'inout', 'wire', 'reg', 'assign', 'endmodule'):
                continue
            if any(fnmatch.fnmatchcase(t, p) for p in pats):
                cnt[t] = cnt.get(t, 0) + 1
    spec['physical_dropped'] = cnt
    return [p for p in pats if any(fnmatch.fnmatchcase(t, p) for t in cnt)]


def _nospace(p):
    if ' ' in p:
        raise GSError('GS003', 'path %r contains a space; read_slang cannot take it' % p, help='move or rename the file so its path has no spaces')
    return p


def _pval(v):
    if isinstance(v, bool):
        return '1' if v else '0'
    if isinstance(v, int):
        return str(v)
    s = str(v)
    if not re.match(r"^[0-9A-Za-z_'.]+$", s):
        raise GSError('GS002', 'parameter value %r is not a plain number' % s, help="use a number such as 8, 'h3F or 8'b1010_0101")
    return s


def hier_cmds(spec, top):
    fe = frontend_of(spec)
    check_ident(top, 'top module')
    ps = ' '.join('-chparam %s %s' % (check_ident(k, 'parameter'), _pval(v)) for k, v in (spec.get('params') or {}).items())
    if fe == 'slang':
        return ['hierarchy -check -top %s' % top]
    return ['hierarchy -check -top %s %s' % (top, ps)]


# ------------------------------------------------------------------ elaboration (step 0)

def yosys_for(spec):
    fe = frontend_of(spec)
    if fe == 'slang':
        return find_yosys(need_slang=True)
    return find_yosys(newest=(fe == 'netlist'))


def _run_elab(spec, fe, ys, cmds, workdir, step):
    try:
        return run(ys, cmds, workdir, step)
    except GSError as e:
        if e.code == 'GS022' and spec.get('frontend', 'auto') == 'auto' and fe == 'verilog' and \
                any(x.endswith(('.sv', '.svh')) for x in spec['sources']):
            e.help = ('these .sv files were read with `read_verilog -sv` because no Yosys with the SystemVerilog frontend '
                      'read_slang was found, and that reader stopped. Install Yosys 0.67 or newer (it includes read_slang) or '
                      'set GLITCHSAT_YOSYS_SLANG=/path/to/yosys (more: glitchsat explain GS021). ' + (e.help or ''))
        raise


def elaborate(spec, workdir):
    """Read, pick the top, elaborate without optimisation. Returns dict(top, hier, flat, ys, log, commands)."""
    fe = frontend_of(spec)
    ys = yosys_for(spec)
    top = spec.get('top')
    if fe == 'slang':
        cmds = read_cmds(spec, ys, top=top)
    else:
        cmds = read_cmds(spec, ys)
    if not top:
        # candidates: modules never instantiated
        cmds_l = cmds + ['hierarchy', 'proc', 'write_json "%s"' % os.path.join(workdir, 'elab', 'modules.json')]
        os.makedirs(os.path.join(workdir, 'elab'), exist_ok=True)
        _run_elab(spec, fe, ys, cmds_l, workdir, 'elab_list')
        doc = json.load(open(os.path.join(workdir, 'elab', 'modules.json')))
        mods = {k: v for k, v in doc['modules'].items() if not (v.get('attributes') or {}).get('blackbox')}
        used = {c['type'] for m in mods.values() for c in (m.get('cells') or {}).values()}
        cands = sorted(m for m in mods if m not in used and not m.startswith('$'))
        tops = [m for m in cands if (mods[m].get('attributes') or {}).get('top')]
        if len(cands) == 1:
            top = cands[0]
        elif len(tops) == 1 and fe == 'slang':
            top = tops[0]
        else:
            err = GSError('GS010', 'cannot tell which module is the top: %s' % (', '.join('`%s`' % c for c in cands) or 'no module found'),
                          help='add `top: <name>` under `design:` in glitchsat.yaml',
                          note='candidates are the modules that no other module instantiates')
            err.candidates = cands
            raise err
        if fe == 'slang':
            cmds = read_cmds(spec, ys, top=top)
    check_ident(top, 'top module')
    d = os.path.join(workdir, 'elab')
    os.makedirs(d, exist_ok=True)
    hj, fj, dj = os.path.join(d, 'hier.json'), os.path.join(d, 'flat.json'), os.path.join(d, 'detect.json')
    cmds = cmds + hier_cmds(spec, top) + ['proc', 'write_json "%s"' % hj, KEEPH, 'flatten', 'opt_clean', 'write_json "%s"' % fj,
                                          'opt_dff', 'opt_clean', 'write_json "%s"' % dj]
    log = _run_elab(spec, fe, ys, cmds, workdir, 'elab')
    hier = json.load(open(hj))
    flat = json.load(open(fj))
    det = json.load(open(dj))
    if top not in flat['modules']:
        # slang may give the module a derived name when parameters are set
        cand = [m for m in flat['modules'] if m.split('$')[0] == top or m.startswith(top)]
        if len(cand) == 1:
            flat['modules'][top] = flat['modules'][cand[0]]
    if top not in flat['modules']:
        raise GSError('GS010', 'top module `%s` was not found after elaboration' % top,
                      note='modules: %s' % ', '.join(list(flat['modules'])[:12]))
    for m in list(det['modules']):
        if top not in det['modules'] and (m.split('$')[0] == top or m.startswith(top)):
            det['modules'][top] = det['modules'][m]
    return dict(top=top, hier=hier, flat=flat, detect=det, ys=ys, log=log, commands=cmds, frontend=fe)


def instance_modules(hier, top):
    """{instance path: module name} from the unflattened JSON."""
    mods = hier['modules']
    out = {'': top}

    def walk(m, path):
        for cn, cv in (mods.get(m, {}).get('cells') or {}).items():
            t = cv['type']
            if t in mods and not t.startswith('$_'):
                p = (path + '.' if path else '') + cn.lstrip('\\')
                out[p] = t
                walk(t, p)
    walk(top, '')
    return out


# ------------------------------------------------------------------ synthesis flows

def _lib_arg(p, workdir):
    """Yosys 0.33 does not read .lib.gz: decompress into the run folder (deleted after the run)."""
    if p.endswith('.gz'):
        tmp = os.path.join(workdir, 'tmp_liberty_%s' % os.path.basename(p)[:-3])
        with gzip.open(p, 'rb') as fi, open(tmp, 'wb') as fo:
            shutil.copyfileobj(fi, fo)
        return tmp
    return p


FLOWS = {
    'plain': dict(desc='structure-preserving: each module is mapped to AND/OR/XOR/NOT/MUX before flattening (the GlitchSAT '
                       'repository flow); copies in separate modules stay separate', lib=None),
    'synth': dict(desc='Yosys `synth -flatten`: full optimisation across modules (FSM re-encoding, sharing), Yosys gates', lib=None),
    'synth-nofsm': dict(desc='as synth, but FSM encodings are kept (`-nofsm`)', lib=None),
    'synth-keep': dict(desc='Yosys `synth` per module (no flattening during optimisation), then flatten', lib=None),
    'nangate45': dict(desc='synth + map to Nangate45 standard cells (abc -liberty, dfflibmap)', lib='nangate45'),
    'sky130hd': dict(desc='synth + map to SkyWater sky130_fd_sc_hd standard cells', lib='sky130hd'),
    'ihp-sg13g2': dict(desc='synth + map to IHP SG13G2 standard cells', lib='ihp-sg13g2'),
    'gf180mcu': dict(desc='synth + map to GF180MCU 7-track standard cells', lib='gf180mcu'),
    'liberty': dict(desc='synth + map to the cells of `design.liberty`', lib='user'),
    'netlist': dict(desc='no synthesis: the sources are a gate-level netlist (Verilog or Yosys JSON)', lib='optional'),
    'custom': dict(desc='your own Yosys commands (`design.yosys_script`), then GlitchSAT reads the result', lib='optional'),
}

KNOWN_LIBS = {   # name -> path relative to $GLITCHSAT_LIBS (see scripts/fetch_libs.sh)
    'nangate45': 'nangate45/NangateOpenCellLibrary_typical.lib',
    'sky130hd': 'sky130hd/sky130_fd_sc_hd__tt_025C_1v80.lib',
    'ihp-sg13g2': 'ihp-sg13g2/sg13g2_stdcell_typ_1p20V_25C.lib',
    'gf180mcu': 'gf180mcu/gf180mcu_fd_sc_mcu7t5v0__tt_025C_5v00.lib.gz',
}


def libs_dir():
    return os.environ.get('GLITCHSAT_LIBS') or os.path.expanduser('~/.cache/glitchsat/libs')


def lib_path(name, spec=None):
    if name == 'user' or name == 'optional':
        libs = (spec or {}).get('liberty') or []
        if not libs and name == 'user':
            raise GSError('GS026', 'flow `liberty` needs `design.liberty: [path/to/cells.lib]`')
        return libs
    p = os.path.join(libs_dir(), KNOWN_LIBS[name])
    if not os.path.isfile(p):
        raise GSError('GS026', 'the %s Liberty file is not on this computer (looked for %s)' % (name, p),
                      help='run `sh scripts/fetch_libs.sh` once (downloads pinned, open-licensed libraries with git), '
                           'or set GLITCHSAT_LIBS to the folder that holds them')
    return [p]


KEEPH = 'setattr -mod -unset keep_hierarchy *'
# read_slang writes an async reset to a parameter value as $aldff; opt_dff turns one with a constant load value into
# a plain async-reset flop ($adff). -nodffe -nosdff: no enable or sync-reset extraction (structure stays as written).
ALDFF = 'opt_dff -nodffe -nosdff'


# Fault semantics must not depend on whether a flow used enable or synchronous-reset flip-flops. Every flow therefore
# ends with `dffunmap`: $_DFFE_*/$_SDFF*_ cells become a plain D flip-flop plus explicit $_MUX_/gate logic, which is
# what the `plain` flow writes anyway. The flip-flop's fault site is its stored value (see netlist.py), so a flip
# persists through the hold multiplexer exactly as it would in a DFF+MUX netlist.
NORMALISE = ['dffunmap', 'techmap', 'opt_clean']


def flow_cmds(flow, top, libs, workdir, spec):
    if flow == 'plain':
        return ['proc', ALDFF, 'memory', 'opt_clean', 'techmap', 'opt_clean', 'abc -g AND,OR,XOR,MUX', 'opt_clean',
                'setattr -mod -unset keep_hierarchy *', 'flatten', 'opt_clean', 'techmap', 'opt_clean'] + NORMALISE
    if flow == 'synth':
        return ['synth -top %s -flatten' % top, KEEPH, 'flatten', 'opt_clean'] + NORMALISE
    if flow == 'synth-nofsm':
        return ['synth -top %s -flatten -nofsm' % top, KEEPH, 'flatten', 'opt_clean'] + NORMALISE
    if flow == 'synth-keep':
        return ['synth -top %s' % top, KEEPH, 'flatten', 'opt_clean', 'techmap', 'opt_clean'] + NORMALISE
    if flow in ('nangate45', 'sky130hd', 'ihp-sg13g2', 'gf180mcu', 'liberty'):
        la = [_lib_arg(p, workdir) if workdir else p for p in libs]
        lib_opts = ' '.join('-liberty "%s"' % check_path(p, 'liberty') for p in la)
        return ['synth -top %s -flatten' % top, 'dfflibmap %s' % lib_opts, 'opt_clean',
                'abc %s' % lib_opts, 'opt_clean', KEEPH, 'flatten', 'opt_clean'] + NORMALISE
    if flow == 'custom':
        sc = user_script(spec)
        if not sc:
            raise GSError('GS025', 'flow `custom` needs `design.yosys_script`')
        return sc + [KEEPH, 'flatten', 'opt_clean'] + NORMALISE
    raise GSError('GS025', 'unknown flow `%s`' % flow, help='flows: ' + ', '.join(FLOWS))


def user_script(spec):
    """The checked custom Yosys commands of a project (empty list if none)."""
    sc = spec.get('yosys_script')
    if not sc:
        return []
    roots = [libs_dir()] + [os.path.dirname(p) for p in spec.get('liberty') or []]
    return check_user_script(sc, spec.get('base') or os.getcwd(), roots)


def synthesize(spec, flow, top, workdir, keep_sel=()):
    """Run one flow. Returns dict(json, module, libs, log, commands, yosys)."""
    fe = frontend_of(spec)
    step = 'flow_' + flow
    d = os.path.join(workdir, step)
    os.makedirs(d, exist_ok=True)
    out = os.path.join(d, 'netlist.json')
    libs = []
    if FLOWS[flow]['lib']:
        libs = lib_path(FLOWS[flow]['lib'], spec)
    if fe == 'json' and len(spec['sources']) != 1:
        raise GSError('GS004', 'a Yosys JSON netlist must be exactly one file')
    ys = yosys_for(spec)
    cmds = []
    if fe == 'netlist' or flow == 'netlist':
        for p in libs:
            cmds.append('read_liberty -lib "%s"' % check_path(_lib_arg(p, d), 'liberty'))
        cmds += [c for c in read_cmds(dict(spec, frontend=fe if fe in ('slang', 'json') else 'netlist'), ys, top=top)
                 if not c.startswith('read_liberty')]
        cmds += ['hierarchy -check -top %s' % check_ident(top, 'top module'), KEEPH, 'flatten', 'opt_clean'] + NORMALISE
    else:
        cmds += read_cmds(spec, ys, top=top) + hier_cmds(spec, top)
        cmds += ['setattr -set keep 1 %s' % _keep_sel(s) for s in keep_sel]
        cmds += flow_cmds(flow, top, libs, d, spec)
    cmds.append('write_json "%s"' % out)
    log = run(ys, cmds, workdir, step)
    for f in os.listdir(d):
        if f.startswith('tmp_liberty_'):
            os.remove(os.path.join(d, f))
    doc = json.load(open(out))
    mods = doc['modules']
    m = mods.get(top)
    if m is None:
        cand = [k for k in mods if not (mods[k].get('attributes') or {}).get('blackbox')]
        if len(cand) == 1:
            m = mods[cand[0]]
        else:
            raise GSError('GS022', 'flow %s produced no module `%s`' % (flow, top), note='modules: ' + ', '.join(mods))
    return dict(json=out, module=m, libs=libs, log=log, commands=cmds, yosys=ys.short(), all_modules=mods)


def _keep_sel(s):
    mod, _, w = s.partition('/w:')
    check_ident(mod, 'module'); check_ident(w, 'probe wire')
    return s


def synth_small(verilog_path, top, workdir, step, formal=False):
    """Elaborate a small generated module (the monitor) to Yosys gates, nothing optimised away but constants."""
    ys = find_yosys()
    out = os.path.join(workdir, step, 'netlist.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cmds = ['read_verilog -sv %s"%s"' % ('-formal ' if formal else '', check_path(verilog_path)),
            'hierarchy -check -top %s' % top, 'proc', ALDFF, 'flatten', 'opt_clean', 'techmap', 'opt_clean',
            'write_json "%s"' % out]
    log = run(ys, cmds, workdir, step)
    doc = json.load(open(out))
    return dict(json=out, module=doc['modules'][top], log=log, commands=cmds, yosys=ys.short())


def reference(spec, wrapper_path, top_wrap, design_top, workdir, connects=()):
    """The RTL as written, wrapped: user sources + generated wrapper and monitor, elaborated without optimisation."""
    fe = frontend_of(spec)
    ys = yosys_for(spec)
    out = os.path.join(workdir, 'reference', 'netlist.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cmds = read_cmds(spec, ys, top=design_top)
    if fe != 'slang':
        cmds += hier_cmds(spec, design_top)
    else:
        cmds += ['hierarchy -top %s' % design_top]
    cmds += ['read_verilog -sv "%s"' % check_path(wrapper_path), 'hierarchy -check -top %s' % top_wrap, 'proc', ALDFF,
             'memory', KEEPH, 'flatten', 'opt_clean']
    cmds += ['connect -set %s %s' % (a, b) for a, b in connects]
    cmds += ['opt_clean', 'techmap', 'opt_clean', 'write_json "%s"' % out]
    log = run(ys, cmds, workdir, 'reference')
    doc = json.load(open(out))
    return dict(json=out, module=doc['modules'][top_wrap], log=log, commands=cmds, yosys=ys.short())
