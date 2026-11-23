"""STAND-IN for product synth_sweep (plumbing tests only): the real flow names, simplified script text."""
import re
_KEEP_RE = re.compile(r"\(\*\s*keep\s*\*\)\s*")
_N = ['plain', 'plain_opt_merge', 'flatten_before_abc', 'abc_fast', 'abc_no_mux', 'opt_flow', 'plain_keep_off', 'opt_flow_keep_off']
def builtin_variants(): return [dict(name=n, description='stand-in', pre='proc', abc='abc', post='opt_clean', strip_keep=n.endswith('keep_off'), source='built-in') for n in _N]
def make_script(v, src, top, out): return f"read_verilog {src}\nhierarchy -top {top}\n# variant {v['name']}\nwrite_json {out}\n"
