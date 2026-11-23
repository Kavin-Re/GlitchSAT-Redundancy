import json, os, sys
REAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REAL)
import pytest

NETS = {
    'aes_fsm': ('synfi/examples/aes_cipher_control_fsm/netlist_aes_cipher_control_fsm.json', 'aes_cipher_control_fsm'),
    'aes_ctrl': ('synfi/examples/aes_cipher_control_rnd_ctr/netlist_aes_cipher_control_flattened_ctr_reg.json', 'aes_cipher_control'),
    'ibex': ('synfi/examples/ibex/netlist_ibex_if_stage.json', 'ibex_if_stage'),
}
SPECS = {
    'E1': ('aes_fsm', 'synfi/examples/aes_cipher_control_fsm/fault_model_aes_cipher_control_fsm_rnd_cntr.json'),
    'E2': ('aes_fsm', 'synfi/examples/aes_cipher_control_fsm/fault_model_aes_cipher_control_fsm_rnd_cntr_target_value.json'),
    'E3': ('aes_ctrl', 'synfi/examples/aes_cipher_control_rnd_ctr/fault_model_aes_cipher_control_rnd_cntr.json'),
    'E4': ('ibex', 'synfi/examples/ibex/fault_model_ibex_if_stage_pc.json'),
    'E5': ('ibex', 'synfi/examples/ibex/fault_model_ibex_if_stage_pc_target.json'),
}


@pytest.fixture(scope='session')
def lib():
    from glitchsat_real import nangate as ng
    return ng.load_cell_lib()


def load(name):
    p, top = NETS[name]
    return json.load(open(os.path.join(REAL, p))), top


def spec(eid):
    net, sp = SPECS[eid]
    return net, next(iter(json.load(open(os.path.join(REAL, sp)))['fimodels'].values()))
