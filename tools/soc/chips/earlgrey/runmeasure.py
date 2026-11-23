#!/usr/bin/env python3
"""Run a command with a time limit; print wall time and peak memory of the child. Usage: runmeasure.py SECONDS cmd..."""
import resource, subprocess, sys, time
t0 = time.time()
try:
    rc = subprocess.run(sys.argv[2:], timeout=float(sys.argv[1])).returncode
except subprocess.TimeoutExpired:
    rc = 'TIMEOUT'
ru = resource.getrusage(resource.RUSAGE_CHILDREN)
print('exit=%s wall_s=%.1f peak_rss_mb=%d' % (rc, time.time() - t0, ru.ru_maxrss // 1024))
