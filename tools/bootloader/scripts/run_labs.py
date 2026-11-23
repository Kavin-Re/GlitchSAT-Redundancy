#!/usr/bin/env python3
"""GlitchSAT Labs: bootloader fault hardening (EXPERIMENTAL).

Experimental analysis of a real bootloader's fault hardening; details withheld pending responsible disclosure.
The harness, the runner and the full result are kept in the private notes of this module, which are not published.
With the private notes present this script runs the example and writes results/labs_result.json (details withheld);
without them it says so and changes nothing.
"""
import os
import runpy
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIVATE = os.path.join(ROOT, 'to_report', 'scripts', 'run_labs.py')


def main():
    if not os.path.isfile(PRIVATE):
        print("Experimental analysis of a real bootloader's fault hardening; details withheld pending responsible "
              'disclosure. The runner is part of the private notes, which are not in this copy; the stored public '
              'result is shown instead.')
        return 0
    sys.argv[0] = PRIVATE
    runpy.run_path(PRIVATE, run_name='__main__')
    return 0


if __name__ == '__main__':
    sys.exit(main())
