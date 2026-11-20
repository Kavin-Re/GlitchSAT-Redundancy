"""pre-commit entry point: run `analyze` on every file given, return the worst exit code.
Usage: faultbound-wt-hook [analyze args...] NETLIST [NETLIST ...]   (args before the files, e.g. --config threat.toml --max-flips 2)"""
import os, sys

from . import cli


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # leading options (and their values) are passed through; the first existing file starts the file list
    i = 0
    while i < len(argv) and not (not argv[i].startswith("-") and os.path.exists(argv[i]) and argv[i - 1:i] not in (["--config"], ["--top"], ["--max-flips"], ["--cycles"], ["--report"], ["--badge"])):
        i += 1
    opts, files = argv[:i], argv[i:]
    if not files:
        print("faultbound-wt-hook: no netlist files given", file=sys.stderr)
        return cli.EXIT_ERROR
    worst = 0
    for f in files:
        print(f"== faultbound-wt analyze {f}", flush=True)
        worst = max(worst, cli.main(["analyze", f] + opts))
    return worst


if __name__ == "__main__":
    sys.exit(main())
