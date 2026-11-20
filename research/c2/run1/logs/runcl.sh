#!/bin/bash
# usage: runcl.sh design ne nc [opt]
d=$1; ne=$2; nc=$3; opt=${4:-nopt}
P=/tmp/work_run1/nl/${d}_spike_N6; [ -n "$APT" ] && P=/tmp/work_run1/nl/${d}apt_spike_N6
O=/tmp/work_run1/out/${d}${APT}_ne${ne}_nc${nc}_$opt
s=$(date +%s.%N)
timeout 300 /tmp/work_run1/cbuild/CLEAVE 3 $P.nl ${P}_blacklist.txt $O $ne 1 $nc detection bit-flip $opt 1 true SAT noncomposition > $O.enc.log 2>&1
e=$(date +%s.%N)
/tmp/work_run1/venv/bin/python /tmp/work_run1/solvecnf.py $O.cnf | tr '\n' ' '
echo "encode=$(echo "$e - $s" | bc)s design=$d ne=$ne nc=$nc $opt"
