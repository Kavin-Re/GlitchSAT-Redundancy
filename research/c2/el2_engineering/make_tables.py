#!/usr/bin/env python3
# Collect OpenROAD/yosys numbers for the six mapped netlists into data_part1_electrical.json + markdown.
import re, json
O = '/tmp/work_el2/lay/out/'
rows = {}
for d in ('v0', 'v1', 'v2'):
    for fl in ('033', '038'):
        t = f'{d}_{fl}'
        st = open(O + f'{t}_stat.txt' if fl == '038' else f'/tmp/work_el2/mapped/{t}_stat.txt').read() if True else ''
        top = re.findall(r"Number of cells:\s+(\d+)", st)[-1]
        area = re.findall(r"Chip area for top module '\\\w+': ([0-9.]+)", st)[-1]
        seq = (re.findall(r"of which used for sequential elements: ([0-9.]+)", st) or ["nan"])[-1]
        lg = open(O + f'{t}_openroad.log').read()
        da = re.search(r'Design area ([0-9.]+) u\^2 (\d+)% utilization', lg)
        ws = re.search(r'worst slack ([0-9.\-]+)', lg).group(1)
        ep = lg.split('EL2_ENDPOINTS_BEGIN')[1]
        first = re.search(r'^(\S+) .*?\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.\-]+) \(', ep.split('-----\n', 1)[1], flags=re.M)
        wh = re.findall(r'worst slack ([0-9.\-]+)', lg)[1]
        pw = re.search(r'^Total\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', lg.split('EL2_POWER_BEGIN')[1], flags=re.M)
        tm = open(O + f'{t}_time.txt').read().split()[1]
        rows[t] = dict(yosys_cells=int(top), yosys_area_um2=float(area), seq_area=float(seq), placed_area_um2=float(da.group(1)), util_pct=int(da.group(2)),
                       setup_slack_ns=float(ws), worst_endpoint=first.group(1), req=float(first.group(2)), arr=float(first.group(3)), hold_slack_ns=float(wh),
                       power_total_uW=float(pw.group(4)) * 1e6, power_internal_uW=float(pw.group(1)) * 1e6, power_switch_uW=float(pw.group(2)) * 1e6, pnr_s=float(tm))
json.dump(rows, open('/home/user/project/research/c2/el2_engineering/data_part1_electrical.json', 'w'), indent=1)
for k, r in rows.items(): print(k, r)
