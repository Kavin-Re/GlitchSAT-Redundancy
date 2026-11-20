cd /tmp/work_m1b
for d in v0_spike:v0 v1_spike:v1 v2_spike:v2 v1_apt033:v1 v2_apt033:v2 v2m:v2m v2s:v2s; do n=${d%%:*}; t=${d##*:}; s=$(date +%s); timeout 1500 venv/bin/python $1 main nl/$n.json $t out/main_$n.jsonl 90000; echo $n $(( $(date +%s)-s ))s; done
