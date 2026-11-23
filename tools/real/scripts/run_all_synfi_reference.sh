#!/bin/bash
# Re-run SYNFI's published example experiments (examples/*/run.sh) with SYNFI's own code, sequentially.
# Note: examples/aes_cipher_control_rnd_ctr/run.sh names fault_model_aes_cipher_control_cntr.json for its second
# run; that file is not in the repository. The README of that example describes the run as "2 simultaneous faults
# into the fault_locations specified in the fault specification file", so the existing spec is used without --auto_fl.
set -u
# run.sh uses -l 10000 for the Ibex 2-fault run; 2000 is used here for time (pure-Python solver).
cd "$(dirname "$0")/.."
R=runs/synfi_ref; S=synfi/examples; P="python3 scripts/run_synfi_reference.py"
A=$S/aes_cipher_control_fsm; B=$S/aes_cipher_control_rnd_ctr; I=$S/ibex
run() { name=$1; shift; [ -f $R/$name.json ] && { echo "skip $name"; return; }; $P "$@" --out $R/$name.json > $R/$name.log 2>&1; tail -1 $R/$name.log; }
run aes_fsm_fe_s1     --netlist $A/netlist_aes_cipher_control_fsm.json --module aes_cipher_control_fsm --spec $A/fault_model_aes_cipher_control_fsm_rnd_cntr.json -s 1 --auto_fl --work $R/aes_fsm
run aes_fsm_fs_s1     --netlist $A/netlist_aes_cipher_control_fsm.json --module aes_cipher_control_fsm --spec $A/fault_model_aes_cipher_control_fsm_rnd_cntr_target_value.json -s 1 --auto_fl --work $R/aes_fsm
run aes_fsm_fs_s2     --netlist $A/netlist_aes_cipher_control_fsm.json --module aes_cipher_control_fsm --spec $A/fault_model_aes_cipher_control_fsm_rnd_cntr_target_value.json -s 2 --auto_fl --work $R/aes_fsm
run aes_ctrl_fd_s1    --netlist $B/netlist_aes_cipher_control_flattened_ctr_reg.json --module aes_cipher_control --spec $B/fault_model_aes_cipher_control_rnd_cntr.json -s 1 --auto_fl --work $R/aes_ctrl
run aes_ctrl_fd_s2_fl --netlist $B/netlist_aes_cipher_control_flattened_ctr_reg.json --module aes_cipher_control --spec $B/fault_model_aes_cipher_control_rnd_cntr.json -s 2 --work $R/aes_ctrl
# Exhaustive 2-fault run over all gates (run.sh's third run) is about 2e5 pairs x 3 mappings: not feasible with the
# pure-Python solver here (about 0.3 s per injection). A prefix of SYNFI's own enumeration order (-l) is run instead.
run aes_ctrl_fd_s2_l2000 --netlist $B/netlist_aes_cipher_control_flattened_ctr_reg.json --module aes_cipher_control --spec $B/fault_model_aes_cipher_control_rnd_cntr.json -s 2 --auto_fl --limit 2000 --work $R/aes_ctrl
run ibex_pc_fe_s1     --netlist $I/netlist_ibex_if_stage.json --module ibex_if_stage --spec $I/fault_model_ibex_if_stage_pc.json -s 1 --auto_fl --work $R/ibex
run ibex_pc_fs_s1     --netlist $I/netlist_ibex_if_stage.json --module ibex_if_stage --spec $I/fault_model_ibex_if_stage_pc_target.json -s 1 --auto_fl --work $R/ibex
run ibex_pc_fs_s2_l2000 --netlist $I/netlist_ibex_if_stage.json --module ibex_if_stage --spec $I/fault_model_ibex_if_stage_pc_target.json -s 2 --auto_fl --limit 2000 --work $R/ibex
