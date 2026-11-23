#!/usr/bin/env python3
"""Verilog wrappers for the scaling benchmarks: N bytes, each through 2 (dmr) or 3 (tmr2) AES S-box lookups, with
input and output registers and a full-width compare, in the style of research/c3/r20/designs/wrappers/w_sbox_dmr.v.
The S-box itself is research/c3/r20/designs/aes_sbox/aes_sbox.v (secworks, BSD-2-Clause), read from the repository at
synthesis time and not copied here. One lookup synthesises to 1,012 gates with Yosys 0.33 (R20_REPORT.md).

usage: gen_wide.py dmr|tmr2 N  > file.v        module name: sbox_<kind>_w<N>
goal port gout = {~alarm(s), y}; key bytes are 1, 2, ..., N; accept word = {1(s), S(N), ..., S(1)}."""
import sys


def verilog(kind, n):
    w = 8 * n
    copies = 'AB' if kind == 'dmr' else 'ABC'
    regs = ', '.join('x%d, y%d' % (i, i) for i in range(len(copies)))
    L = ['module sbox_%s_w%d(input clk, input [%d:0] sig, output [%d:0] gout);' % (kind, n, w - 1, w + len(copies) - 2),
         '  reg [%d:0] %s;' % (w - 1, regs),
         '  wire [%d:0] %s;' % (w - 1, ', '.join('s%d' % i for i in range(len(copies)))),
         '  genvar i;', '  generate for (i = 0; i < %d; i = i + 1) begin: g' % n]
    for i, cp in enumerate(copies):
        L += ['    wire [31:0] w%d;' % i,
              '    aes_sbox %s(.sboxw({24\'b0, x%d[8*i +: 8]}), .new_sboxw(w%d));' % (cp, i, i),
              '    assign s%d[8*i +: 8] = w%d[7:0];' % (i, i)]
    L += ['  end endgenerate', '  always @(posedge clk) begin']
    for i in range(len(copies)):
        L.append('    x%d <= sig; y%d <= s%d;' % (i, i, i))
    L.append('  end')
    alarms = ', '.join('~(y0 != y%d)' % i for i in range(len(copies) - 1, 0, -1))
    L += ['  assign gout = {%s, y0};' % alarms, 'endmodule']
    return '\n'.join(L) + '\n'


def params(kind, n, sbox):
    """goal value and key for the wrapper (sbox: the 256-entry table)."""
    key = sum((i + 1) << (8 * i) for i in range(n))
    val = sum(sbox[i + 1] << (8 * i) for i in range(n))
    ones = 1 if kind == 'dmr' else 3
    return dict(goal_out='gout', goal_value=val | (ones << (8 * n)), key=key, cycles=4)


if __name__ == '__main__':
    sys.stdout.write(verilog(sys.argv[1], int(sys.argv[2])))
