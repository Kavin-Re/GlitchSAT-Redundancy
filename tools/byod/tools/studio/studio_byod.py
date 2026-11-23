#!/usr/bin/env python3
"""Start GlitchSAT Studio with the "Open my design" module, without changing studio.py.

    python3 tools/studio/studio_byod.py [--port 8765] [--no-browser]

It loads studio.py (next to this file, or $GLITCHSAT_STUDIO), adds the module's page part (byod_view.install),
answers the module's /api/byod/ requests (byod_view.handle) and adds a Content-Security-Policy to every response.
Everything else is the Studio unchanged: 127.0.0.1 only, its Host/Origin checks, offline.
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _studio_path():
    for p in (os.environ.get('GLITCHSAT_STUDIO'), os.path.join(HERE, 'studio.py')):
        if p and os.path.isfile(p):
            return p
    sys.exit('studio.py not found: set GLITCHSAT_STUDIO=/path/to/studio.py')


def load():
    sp = importlib.util.spec_from_file_location('byod_view', os.path.join(HERE, 'byod_view.py'))
    bv = importlib.util.module_from_spec(sp); sp.loader.exec_module(bv)
    path = _studio_path()
    sys.argv[0] = path                      # the Studio starts its worker processes with sys.argv[0]
    spec = importlib.util.spec_from_file_location('studio', path)
    st = importlib.util.module_from_spec(spec)
    sys.modules['studio'] = st
    spec.loader.exec_module(st)
    st.PAGE = bv.install(st.PAGE)
    Base = st.H

    class H(Base):
        def _send(self, code, body, ctype='application/json'):
            self._csp = True
            return Base._send(self, code, body, ctype)

        def end_headers(self):
            if getattr(self, '_csp', False):
                self.send_header('Content-Security-Policy', bv.CSP)
                self.send_header('Referrer-Policy', 'no-referrer')
            return Base.end_headers(self)

        def do_GET(self):
            if self.path.startswith('/api/byod/'):
                if not self._local():
                    return self._send(403, '{"error":"forbidden"}')
                return bv.handle(self, 'GET', self.path.split('?')[0], self._query())
            return Base.do_GET(self)

        def do_POST(self):
            if self.path.startswith('/api/byod/'):
                if not self._local() or self.headers.get('X-GlitchSAT') != '1':
                    return self._send(403, '{"error":"forbidden"}')
                import json
                try:
                    n = int(self.headers.get('Content-Length', 0) or 0)
                    q = json.loads(self.rfile.read(n) or b'{}') if n < 1_000_000 else {}
                except Exception:          # noqa: BLE001
                    return self._send(400, '{"error":"bad request"}')
                return bv.handle(self, 'POST', self.path.split('?')[0], q if isinstance(q, dict) else {})
            return Base.do_POST(self)
    st.H = H
    return st, bv


if __name__ == '__main__':
    st, bv = load()
    if '--worker' in sys.argv:
        i = sys.argv.index('--worker')
        st.worker_main(sys.argv[i + 1], sys.argv[i + 2])
    else:
        st.main()
