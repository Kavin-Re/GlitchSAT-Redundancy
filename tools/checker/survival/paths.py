"""Locate the GlitchSAT repository and the sibling modules this checker reuses (nothing is copied).

Environment overrides (same names the other modules use):
  GLITCHSAT_ROOT      repository root (holds scripts/glitchsat.py)
  GLITCHSAT_EXT       folder holding surface/, fastsat/, unbounded/, shots/, firmware/, harden/, product/
  GLITCHSAT_REAL      folder holding glitchsat_real/ (Nangate45 adapter), optional
  GLITCHSAT_TOOLS_ENV shell file exporting PATH for Yosys / solvers, optional
"""
import importlib
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKER = os.path.dirname(HERE)


def ext_root():
    c = os.environ.get("GLITCHSAT_EXT") or os.path.dirname(CHECKER)
    return os.path.abspath(c)


def repo_root():
    cands = [os.environ.get("GLITCHSAT_ROOT"), os.path.dirname(ext_root()),
             os.path.join(os.path.dirname(ext_root()), "work", "glitchsat")]
    for c in cands:
        if c and os.path.isfile(os.path.join(c, "scripts", "glitchsat.py")):
            return os.path.abspath(c)
    raise FileNotFoundError("GlitchSAT repository not found: set GLITCHSAT_ROOT to its root")


def real_root():
    for c in (os.environ.get("GLITCHSAT_REAL"), os.path.join(os.path.dirname(ext_root()), "real"),
              os.path.join(ext_root(), "real")):
        if c and os.path.isdir(os.path.join(c, "glitchsat_real")):
            return os.path.abspath(c)
    return None


def _add(p):
    if p and os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)


def setup():
    """Put the reused modules on sys.path. Safe to call many times."""
    sys.dont_write_bytecode = True      # the repository and the sibling modules are read, never written (no .pyc there)
    try:
        root = repo_root()
        os.environ.setdefault("GLITCHSAT_ROOT", root)
        _add(os.path.join(root, "scripts"))
    except FileNotFoundError:
        pass
    e = ext_root()
    for sub in ("surface/scripts", "fastsat/scripts", "unbounded/src", "shots", "firmware", "harden",
                "product/product/src"):
        _add(os.path.join(e, sub))
    r = real_root()
    if r:
        _add(r)


def optional(name):
    """Import a reused module, or return None with no error when it is not available."""
    setup()
    try:
        return importlib.import_module(name)
    except Exception:       # missing module, or a module that refuses to load without its inputs
        return None


def tool(name):
    """Absolute path of an external tool (yosys, clang, llvm-objdump ...), honouring the optional tools env file."""
    p = shutil.which(name)
    if p:
        return p
    env = os.environ.get("GLITCHSAT_TOOLS_ENV") or os.path.join(os.path.dirname(ext_root()), "tools", "env.sh")
    if os.path.isfile(env):
        try:
            out = subprocess.run(["bash", "-c", f". {env!r} >/dev/null 2>&1; command -v {name}"],
                                 capture_output=True, text=True, timeout=20).stdout.strip()
            if out and os.path.isfile(out):
                return out
        except Exception:
            pass
    return None


def rel(path, root=None):
    """Path relative to the repository root when inside it, else unchanged."""
    try:
        root = root or repo_root()
        r = os.path.relpath(os.path.abspath(path), root)
        return r if not r.startswith("..") else path
    except Exception:
        return path
