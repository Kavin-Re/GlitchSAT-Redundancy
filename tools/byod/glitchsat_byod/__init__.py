"""GlitchSAT for your own chip design: project file, automatic wrapper, standard-cell import, analyses.

Python use:
    from glitchsat_byod import Project
    rep = Project('glitchsat.yaml').run()
"""
__version__ = '0.1.0'


class Project:
    def __init__(self, path, task=None):
        self.path, self.task = path, task

    def run(self, progress=None, only=None):
        from .run import run_project
        rep, spec = run_project(self.path, self.task, progress, only)
        return rep

    def explain(self, rep):
        from .report import plain
        return plain(rep)
