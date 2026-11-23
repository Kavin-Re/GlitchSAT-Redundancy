"""Builds the overlay root used by the plumbing tests. Everything except the engine entry points is a symlink to the real repo."""
import os, sys, shutil, stat
HERE = os.path.dirname(os.path.abspath(__file__))
# the real repository: $GLITCHSAT_ROOT, else the repository around tools/studio/harness/ (never a fixed machine path)
REAL = os.environ.get('GS_STANDIN_REAL') or os.environ.get('GLITCHSAT_ROOT') or os.path.normpath(os.path.join(HERE, '..', '..', '..'))
os.environ['GS_STANDIN_REAL'] = REAL       # read by the stand-ins, which run as copies inside the overlay
def make(dst):
    shutil.rmtree(dst, ignore_errors=True); os.makedirs(dst)
    for n in os.listdir(REAL):
        if n in ('scripts', 'product'): continue
        os.symlink(os.path.join(REAL, n), os.path.join(dst, n))
    os.makedirs(dst + '/scripts')
    for n in os.listdir(REAL + '/scripts'):
        if n != 'glitchsat.py' and n != '__pycache__': os.symlink(os.path.join(REAL, 'scripts', n), os.path.join(dst, 'scripts', n))
    open(dst + '/_standin_real', 'w').write(REAL + '\n')
    shutil.copy(HERE + '/standin_glitchsat.py', dst + '/scripts/glitchsat.py')
    pk = dst + '/product/src/faultbound_wt'; os.makedirs(pk)
    open(pk + '/__init__.py', 'w').write('__version__ = "0.9.0"\n')
    shutil.copy(HERE + '/standin_cli.py', pk + '/cli.py'); shutil.copy(HERE + '/standin_synth_sweep.py', pk + '/synth_sweep.py')
    os.symlink(REAL + '/product/src/faultbound_wt/examples', pk + '/examples')
    shutil.copy(REAL + '/product/pyproject.toml', dst + '/product/pyproject.toml')
    fp = dst + '/_standin_py'; os.makedirs(fp)
    open(fp + '/z3.py', 'w').write('"""STAND-IN z3 module (plumbing tests only)."""\ndef get_version_string(): return "0.0-STAND-IN"\n')
    fb = dst + '/_standin_bin'; os.makedirs(fb)
    y = fb + '/yosys'; shutil.copy(HERE + '/standin_yosys.py', y); os.chmod(y, os.stat(y).st_mode | stat.S_IEXEC)
    return dst
if __name__ == '__main__': print(make(sys.argv[1]))
