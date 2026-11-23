"""Known-answer test values: the published constants used by tb/gen/tb_kat.v are checked against hashlib and the
model, and the testbench file contains them."""
import hashlib, os
from model import keccak as K
from model.secboot_model import mac
from model.variants import BY_NAME
from engine import benches

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_published_values_agree_with_hashlib():
    assert hashlib.sha3_256(b'').hexdigest() == benches.SHA3_256_EMPTY
    assert hashlib.sha3_256(b'abc').hexdigest() == benches.SHA3_256_ABC


def test_model_reproduces_the_known_answers():
    assert K.keccak_p(0, 64) & ((1 << 64) - 1) == benches.KECCAK_F1600_ZERO_LANE0
    s = K.keccak_p(K.pad_block(1088), 64)
    assert (s & ((1 << 256) - 1)) == benches.digest_int(benches.SHA3_256_EMPTY)
    s = K.keccak_p(benches.sha3_block(b'abc'), 64)
    assert (s & ((1 << 256) - 1)) == benches.digest_int(benches.SHA3_256_ABC)


def test_testbench_carries_the_values():
    t = open(os.path.join(HERE, 'tb', 'gen', 'tb_kat.v')).read()
    assert f"64'h{benches.KECCAK_F1600_ZERO_LANE0:016X}" in t
    assert f"256'h{benches.digest_int(benches.SHA3_256_EMPTY):064X}" in t
    assert f"256'h{benches.digest_int(benches.SHA3_256_ABC):064X}" in t
    v = BY_NAME['h_single']
    assert f"{v.cfg.TAG}'h{mac(v.cfg, [v.key]):X}" in t
