#!/bin/bash
# usage: inj.sh  -- runs payload matrix; prints per-case exit + canaries
FB=/tmp/work_rt3/venv/bin/faultbound-wt
W=/tmp/work_rt3/t
C=/tmp/work_rt3
P=/tmp/work_rt3/p
cp $P/product/examples/pin_lock/pin.v $W/pin.v
cp $P/product/examples/pin_lock/pin.toml $W/pin.toml
cd $W
rm -f $C/canary_*
chk() { # label rc
  n=$(ls $C/canary_* $W/canary_* 2>/dev/null | wc -l)
  echo "[$1] rc=$2 canaries=$n $(ls $C/canary_* $W/canary_* 2>/dev/null | tr '\n' ' ')"
  rm -f $C/canary_* $W/canary_*
}
run() { label=$1; shift; timeout 60 "$@" >$W/out.txt 2>&1; rc=$?; chk "$label" $rc; head -c 200 $W/out.txt | head -2 | sed 's/^/    /'; }
K=$C/canary_
PAYL=(
"m; exec -- touch ${K}1; hierarchy -top pin"
"pin
exec -- touch ${K}2"
"pin"$'\r'"exec -- touch ${K}3"
"pin\$(touch ${K}4)"
'pin`touch '${K}5'`'
"pin;touch ${K}6"
"pin "
" pin"
"pin"$'\xc2\xa0'
"р"in   # cyrillic p
"pi"$'\x00'"n"
'\pin '
'\pin; exec -- touch '${K}7' ;'
"-top"
"pin#"
"pin%s"
"$(printf 'a%.0s' {1..5000})"
"pin\${HOME}"
"pin;"
"pin'; exec -- touch ${K}8 ; '"
)
i=0
for t in "${PAYL[@]}"; do i=$((i+1))
  run "top-cli#$i" $FB analyze pin.v --config pin.toml --top "$t"
done
# TOML top
i=0
for t in "${PAYL[@]}"; do i=$((i+1))
  python3 - "$t" <<'PY'
import sys,json
t=sys.argv[1]
src=open('/tmp/work_rt3/t/pin.toml').read()
s=json.dumps(t)  # toml basic string compatible-ish
open('/tmp/work_rt3/t/inj.toml','w').write(src+'\n[netlist]\ntop = '+s+'\n')
PY
  run "top-toml#$i" $FB analyze pin.v --config inj.toml
done
# file names
FN=(
"m.v; exec -- touch ${K}f1; .v"
"m"$'\n'"exec -- touch ${K}f2.v"
"m\$(touch ${K}f3).v"
'm`touch '${K}f4'`.v'
"m\\\"x.v"
"-pin.v"
"p'in.v"
"pіn.v"
"pin.v "
"$(printf 'a%.0s' {1..300}).v"
'${HOME}.v'
'\pin.v'
"pin#x.v"
"pin\$(x).v"
"my file.v"
"pin"$'\r'".v"
)
i=0
for f in "${FN[@]}"; do i=$((i+1))
  cp pin.v "$f" 2>/dev/null || { echo "[fn#$i] cannot create file"; continue; }
  run "fn#$i" $FB analyze "./$f" --config pin.toml --top pin
  rm -f "./$f"
done
# symlink
ln -sf pin.v 'ln; exec -- touch '${K}'s1; .v' 2>/dev/null; run "symlink-name" $FB analyze './ln; exec -- touch '${K}'s1; .v' --config pin.toml --top pin
ln -sf $W/pin.v symok.v; run "symlink-ok" $FB analyze symok.v --config pin.toml --top pin
echo ---synth-variants
SV=(
"abc; exec -- touch ${K}v1"
"proc; exec touch ${K}v2"
"proc"$'\n'"exec -- touch ${K}v3"
'proc $(touch '${K}v4')'
'synth -top {top} ; exec touch '${K}v5
"proc; opt_clean # x"
"techmap -map /dev/null"
"synth -run :fine"
"abc -script ${K}x"
"abc -exe ${K}x"
"abc -fast -g AND,OR ; exec touch ${K}v6"
"setattr -mod -unset keep_hierarchy * ; exec touch ${K}v7"
"opt -fast"
"flatten -wb"
"synth -top {top} -noabc -flatten"
"dffunmap -ce-only"
"abc -fast -g \$(touch ${K}v8)"
"proc"$'\r'"exec touch ${K}v9"
)
i=0
for s in "${SV[@]}"; do i=$((i+1))
  python3 - "$s" <<'PY'
import sys,json
s=sys.argv[1]
js=json.dumps(s)
for fld in ('pre','post','abc'):
    pass
open('/tmp/work_rt3/t/var.toml','w').write('[[variant]]\nname="x"\npre=%s\n'%js)
open('/tmp/work_rt3/t/var2.toml','w').write('[[variant]]\nname="x"\nabc=%s\n'%js)
open('/tmp/work_rt3/t/var3.toml','w').write('[[variant]]\nname="x"\npost=%s\n'%js)
PY
  for v in var var2 var3; do
  run "variant#$i/$v" $FB analyze pin.v --top pin --config pin.toml --synth-sweep --synth-variants $v.toml --synth-select x
  done
done
echo ---names in variant name and select
python3 - <<'PY'
open('/tmp/work_rt3/t/var4.toml','w').write('[[variant]]\nname="x; exec -- touch /tmp/work_rt3/canary_vn"\npre="proc"\n')
PY
run "variant-name" $FB analyze pin.v --top pin --config pin.toml --synth-sweep --synth-variants var4.toml
run "variant-select" $FB analyze pin.v --top pin --config pin.toml --synth-sweep --synth-select "plain; exec -- touch ${K}vs"
python3 - <<'PY'
open('/tmp/work_rt3/t/var5.json','w').write('[{"name":"j","pre":"proc; exec -- touch /tmp/work_rt3/canary_jv"}]')
open('/tmp/work_rt3/t/var6.toml','w').write('[[variant]]\nname="y"\nextends="plain; exec -- touch /tmp/work_rt3/canary_ext"\n')
open('/tmp/work_rt3/t/var7.toml','w').write('[[variant]]\nname="y"\nstrip_keep="x"\nextends="plain"\ndescription="d\\nexec -- touch /tmp/work_rt3/canary_desc"\n')
PY
run "variant-json" $FB analyze pin.v --top pin --config pin.toml --synth-sweep --synth-variants var5.json
run "variant-extends" $FB analyze pin.v --top pin --config pin.toml --synth-sweep --synth-variants var6.toml
run "variant-desc" $FB analyze pin.v --top pin --config pin.toml --synth-sweep --synth-variants var7.toml
