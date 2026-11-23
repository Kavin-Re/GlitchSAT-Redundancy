"""Where the read-only inputs live inside the GlitchSAT repository."""
import hashlib
import os
from pathlib import Path


def repo_root():
    """Repository root: $GLITCHSAT_ROOT (the name used by ext/surface and ext/unbounded), else $GLITCHSAT_REPO
    (older alias), else the checkout this folder sits in (<repo>/ext/shots). No workspace-specific fallback."""
    marker = Path("layout") / "v_designs" / "out_patched" / "v2.def"
    for var in ("GLITCHSAT_ROOT", "GLITCHSAT_REPO"):
        if os.environ.get(var):
            c = Path(os.environ[var])
            if not (c / marker).is_file():
                raise FileNotFoundError(f"{var}={c} has no {marker}")
            return c
    c = Path(__file__).resolve().parents[3]
    if (c / marker).is_file():
        return c
    raise FileNotFoundError("GlitchSAT repository not found: put ext/shots inside it or set GLITCHSAT_ROOT to its root")


LEF = "research/c4/l2_inputs/lef/sky130_fd_sc_hd_sizes_only.lef"
SPICE = "layout/v_designs/out_patched/v2_ref.spice"      # holds the PDK transistor-level subckts of every cell

# design id -> (top module, DEF, placed netlist, note)
DESIGNS = {
    "v1": ("v1", "layout/v_designs/out_patched/v1.def", "layout/v_designs/out_patched/v1_pnr.v",
           "V1, patched flow (LVS-matching layout)"),
    "v2": ("v2", "layout/v_designs/out_patched/v2.def", "layout/v_designs/out_patched/v2_pnr.v",
           "V2, patched flow (LVS-matching layout)"),
    "v2_v8": ("v2", "research/c4/l2_inputs/def/v8.def", "research/c4/l2_inputs/pnr/v8_pnr.v",
              "V2, compare copies pinned apart, util 45 (LVS fails in the repo's flow)"),
    "v2_s8": ("v2", "research/c4/l2_inputs/def/s8.def", "research/c4/l2_inputs/pnr/s8_pnr.v",
              "V2, copies in three corners, util 25 (LVS fails)"),
    "v2_v15": ("v2", "research/c4/l2_inputs/def/v15.def", "research/c4/l2_inputs/pnr/v15_pnr.v",
               "V2, as v8 with util 20 (LVS fails)"),
    "v2_rr": ("v2", "research/c4/l2_inputs/def/rr.def", "research/c4/l2_inputs/pnr/rr_pnr.v",
              "V2, copies on rows 0/6/12 (LVS fails)"),
}
# Not placed anywhere in the repository (no DEF): V0, V2e, v2c, v2_secded. They cannot be analysed with this model.
UNPLACED = ["v0", "v2e", "v2c", "v2_secded"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()
