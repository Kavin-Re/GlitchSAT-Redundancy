"""Smoke test of GlitchSAT Studio: start tools/studio/studio.py on a free local port against this repository and
read the page and the JSON endpoints. Needs nothing beyond the standard library (without z3 Studio shows recorded
results)."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
STUDIO = os.path.join(os.path.dirname(HERE), "studio.py")
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@pytest.fixture(scope="module")
def studio():
    port = _free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith("GLITCHSAT_")}
    env["XDG_CACHE_HOME"] = tempfile.mkdtemp(prefix="gs-studio-test-")
    p = subprocess.Popen([sys.executable, STUDIO, "--no-browser", "--port", str(port), "--no-autostop"], cwd=ROOT, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/api/status", timeout=1).read()
            break
        except Exception:   # noqa: BLE001
            if p.poll() is not None:
                pytest.fail("Studio exited: " + p.stdout.read()[-2000:])
            time.sleep(0.2)
    yield base
    p.terminate()
    try:
        p.wait(timeout=10)
    except subprocess.TimeoutExpired:
        p.kill()


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=60) as r:
        body = r.read().decode("utf-8")
    return json.loads(body) if path.startswith("/api/") else body


def test_page_and_status(studio):
    assert "<html" in get(studio, "/").lower()
    st = get(studio, "/api/status")
    assert "studio" in st
    assert isinstance(get(studio, "/api/findings"), (dict, list))


def test_missing_module_is_reported_not_broken(studio):
    d = get(studio, "/api/mod?name=surface")
    assert isinstance(d, dict)
    assert not d.get("broken"), d.get("detail")


def test_no_request_reaches_outside_the_repository(studio):
    with pytest.raises(urllib.error.HTTPError):
        get(studio, "/mod/surface/..%2F..%2F..%2Fetc%2Fpasswd")
