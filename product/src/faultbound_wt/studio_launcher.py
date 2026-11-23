"""`glitchsat-studio`: start GlitchSAT Studio (the local desktop app) from an installed package.

Studio is shipped as package data at faultbound_wt/tools/studio/studio.py. This launcher finds that file and runs it
with the same Python interpreter. Search order:
  1. $GLITCHSAT_STUDIO (path to a studio.py), if set;
  2. the copy installed with this package (faultbound_wt/tools/studio/studio.py, or the project data package
     glitchsat_data/tools/studio/studio.py that `pip install .` at the repository root installs);
  3. $GLITCHSAT_ROOT/tools/studio/studio.py, then tools/studio/studio.py in the current directory and each parent
     (a clone of the repository, for example an editable install without the packaged copy).
Studio's project root is $GLITCHSAT_ROOT; when it is not set, the launcher sets it to the directory that holds
tools/studio/ for a repository copy (or $GLITCHSAT_STUDIO), or, for the packaged copy, to the first directory at or above the current one that contains
scripts/glitchsat.py (none found: Studio uses the current directory and shows recorded results only).
All arguments are passed through (e.g. --port 8765 --no-browser). Exit 3 when Studio cannot be found."""
import contextlib, os, subprocess, sys

REL = os.path.join("tools", "studio", "studio.py")
PKG_DIR = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join("scripts", "glitchsat.py")
DATA_PKG = "glitchsat_data"


def packaged_studio():
    """Path of the Studio copy installed with the package, or None: faultbound_wt/tools/studio/studio.py, else the
    project data package installed beside it (glitchsat_data/tools/studio/studio.py, from `pip install .` at the
    repository root)."""
    for p in (os.path.join(PKG_DIR, REL), os.path.join(os.path.dirname(PKG_DIR), DATA_PKG, REL)):
        if os.path.isfile(p):
            return p
    try:   # installs where the package is not a plain directory (zip import): ask importlib.resources
        from importlib import resources
        ref = resources.files(__package__ or "faultbound_wt").joinpath("tools", "studio", "studio.py")
        return ref if ref.is_file() else None
    except Exception:   # noqa: BLE001  (no package context, or a loader without resource support)
        return None


def _walk_up(start, rel):
    d = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(d, rel)):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def find_studio(start=None, env=None):
    """Return (studio path or importlib resource, where), where = 'env', 'package' or 'repository'; (None, None)."""
    env = os.environ if env is None else env
    p = env.get("GLITCHSAT_STUDIO")
    if p:
        return (os.path.abspath(p), "env") if os.path.isfile(p) else (None, None)
    pk = packaged_studio()
    if pk is not None:
        return pk, "package"
    root = env.get("GLITCHSAT_ROOT")
    if root and os.path.isfile(os.path.join(root, REL)):
        return os.path.abspath(os.path.join(root, REL)), "repository"
    d = _walk_up(start or os.getcwd(), REL)
    return (os.path.join(d, REL), "repository") if d else (None, None)


def _missing_message(env):
    lines = ["glitchsat-studio: GlitchSAT Studio was not found.",
             f"  - not installed with this package (expected {os.path.join(PKG_DIR, REL)});"]
    if env.get("GLITCHSAT_STUDIO"):
        lines.append(f"  - GLITCHSAT_STUDIO={env['GLITCHSAT_STUDIO']} is not a file;")
    lines.append("  - no tools/studio/studio.py in $GLITCHSAT_ROOT or in the current directory or its parents.")
    lines.append("Install a GlitchSAT release that includes Studio, run this command inside a clone of the GlitchSAT "
                 "repository, or set GLITCHSAT_STUDIO to the studio.py file.")
    return "\n".join(lines)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    studio, where = find_studio()
    if studio is None:
        print(_missing_message(os.environ), file=sys.stderr)
        return 3
    env = dict(os.environ)
    if "GLITCHSAT_ROOT" not in env:
        if where == "package":
            root = _walk_up(os.getcwd(), ENGINE)
        else:   # <root>/tools/studio/studio.py
            root = os.path.dirname(os.path.dirname(os.path.dirname(str(studio))))
        if root:
            env["GLITCHSAT_ROOT"] = root
    try:
        from importlib import resources
        ctx = resources.as_file(studio) if not isinstance(studio, str) else contextlib.nullcontext(studio)
        with ctx as path:
            return subprocess.call([sys.executable, str(path)] + argv, env=env)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
