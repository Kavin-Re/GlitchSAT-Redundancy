# Stand-in harness (PLUMBING TESTS ONLY)

z3 and Yosys are not installed on the build machine. `harness.py` starts `studio.py` against an overlay of the repository in which
`scripts/glitchsat.py`, `product/src/faultbound_wt`, the `z3` module and the `yosys` program are replaced by STAND-INS that answer
from the project's recorded files. It checks request handling, worker processes, time limits, Stop, jobs, the cache and the screens.
It does NOT check z3, Yosys, real minimisation or real timings. Screens made with it are named `standin_*.png`.
