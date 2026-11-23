"""Sequential stand-in for the parts of ray used by SYNFI (init, shutdown, remote, get)."""
import functools, inspect

def init(*a, **k): return None
def shutdown(*a, **k): return None

class _Ref:
    def __init__(self, fn, a, k): self.fn, self.a, self.k = fn, a, k
    def result(self): return self.fn(*self.a, **self.k)

def get(x):
    if isinstance(x, list): return [get(i) for i in x]
    return x.result() if isinstance(x, _Ref) else x

class _Method:
    def __init__(self, obj, name): self.obj, self.name = obj, name
    def remote(self, *a, **k): return _Ref(getattr(self.obj, self.name), a, k)

class _Actor:
    def __init__(self, obj): self._obj = obj
    def __getattr__(self, n): return _Method(self._obj, n)

def remote(*args, **kw):
    def wrap(target):
        if inspect.isclass(target):
            class Cls:
                @staticmethod
                def remote(*a, **k): return _Actor(target(*a, **k))
            return Cls
        f = target
        f.remote = lambda *a, **k: _Ref(target, a, k)
        return f
    if len(args) == 1 and callable(args[0]) and not kw:
        return wrap(args[0])
    return wrap
