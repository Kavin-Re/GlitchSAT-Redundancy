#!/bin/bash
# run from layout/v_designs. needs micromamba env 'eda' at /tmp/mm_root/envs/eda and `pip install klayout pillow`
export PATH=/tmp/mm_root/envs/eda/bin:$PATH
for d in v1 v2; do
  flow/run.sh $d
  DESIGN=$d magic -dnull -noconsole -rcfile /tmp/mm_root/envs/eda/share/pdk/sky130A/libs.tech/magic/sky130A.magicrc flow/gds.tcl > out/${d}_magic.log 2>&1
  bash flow/lvs.sh $d > out/${d}_lvs.log 2>&1
  python3 flow/render.py $d
done
