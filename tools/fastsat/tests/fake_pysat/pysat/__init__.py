"""TEST DOUBLE, not PySAT. A stand-in with the small part of the pysat.solvers interface that glitchsat_sat.py uses,
backed by minicdcl, so the PySAT adapter code path can be exercised on machines without python-sat. It proves nothing
about the real PySAT; cloud_bench.sh runs the real one."""
__version__ = "0.0-test-double"
