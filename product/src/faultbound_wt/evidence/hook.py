"""pre-commit entry point: run `glitchsat check` on the project's targets file when a netlist, threat model, recorded
result or the targets file itself changes. pre-commit passes the changed file names; they only decide WHETHER to run.
Usage: glitchsat-evidence-hook [--targets glitchsat.toml] [--sarif F] [--report-dir D] [changed files ...]
Exit code = the check's (0 margin met, 1 below target, 2 no verdict, 3 input error)."""
import argparse, os, sys

from . import cli


def main(argv=None):
    ap = argparse.ArgumentParser(prog="glitchsat-evidence-hook")
    ap.add_argument("--targets", default="glitchsat.toml")
    ap.add_argument("--sarif", default=os.path.join(".glitchsat", "glitchsat.sarif"))
    ap.add_argument("--report-dir", default=".glitchsat")
    ap.add_argument("files", nargs="*")
    a = ap.parse_args(sys.argv[1:] if argv is None else argv)
    if not os.path.isfile(a.targets):
        print(f"glitchsat-evidence-hook: {a.targets} not found (create one from templates/glitchsat-project/glitchsat.toml)", file=sys.stderr)
        return cli.EXIT_ERROR
    os.makedirs(a.report_dir, exist_ok=True)
    return cli.main(["check", f"--targets={a.targets}", f"--sarif={a.sarif}", f"--report-dir={a.report_dir}"])


if __name__ == "__main__":
    sys.exit(main())
