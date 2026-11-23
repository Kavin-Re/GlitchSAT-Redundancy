# "Open my design" in GlitchSAT Studio

Three ways to load the module; none needs an edit of `studio.py` today.

0. **One start command**: `python3 studio.py`. The Studio looks for `tools/studio/studio_byod.py` (in the project,
   next to `studio.py`, or in `tools/byod/`) and loads `byod_view.py` from the same folder by itself.

1. **The launcher**:

   ```
   python3 tools/studio/studio_byod.py [--port 8765] [--no-browser]
   ```

   It loads `studio.py` (next to it, or `$GLITCHSAT_STUDIO`), installs the module's page part, answers the module's
   `/api/byod/` requests and adds a Content-Security-Policy header to every response. Everything else is the
   Studio unchanged.

2. **Two marked lines in studio.py** (only for a Studio version without the plug-in loader), the same pattern as the learn_view hook (after `PAGE = ...` and inside the two
   request methods). Re-read studio.py before editing, and do not overwrite other modules' marked lines:

   ```python
   # ---- BYOD hook: "Open my design" lives in byod_view.py
   try:
       import importlib.util as _ilu2
       _sp2 = _ilu2.spec_from_file_location('byod_view', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'byod_view.py'))
       byod_view = _ilu2.module_from_spec(_sp2); _sp2.loader.exec_module(byod_view); PAGE = byod_view.install(PAGE)
   except Exception as _e:                # noqa: BLE001 - the Studio must start without it
       byod_view = None; print(f'byod_view not loaded: {_e}', file=sys.stderr)
   ```

   and, as the first line after the `_local()` check of `do_GET` and of `do_POST` (after the body is parsed):

   ```python
   if byod_view and byod_view.handle(self, 'GET', path, q): return      # BYOD hook   (do_POST: 'POST')
   ```

What the module does: a tab "Open my design" with the gallery (each example with what it is, why the protection
matters, what it teaches, and a weak/protected pair to run), a folder picker limited to the home folder, a five-step
wizard in plain words (your design; clock and reset with the evidence found; who controls which input; what must
never happen, as a template; how hard to search), progress while `glitchsat run` works in a separate process that
can be stopped, and the result: the answer, the cheapest attack step by step with a signal table, whether it holds
for any waiting time, whether the protection survived each build, the weak spots, and the simulation check. The
expert path stays the YAML file; the wizard writes the same commented `glitchsat.yaml` as `glitchsat init`.

Security: 127.0.0.1 only and the Studio's Host/Origin checks; every `/api/byod/` request also needs the per-session
token that is embedded in the page; no network access; the folder picker refuses folders outside the home folder
and hidden folders. A project file that is not a gallery example (box 3, "I already have a glitchsat.yaml") is never
run on one click: the tab shows the Yosys commands of every build and the files read, and runs only after "I checked
these commands: run it"; the confirmation code is bound to the file's content, so a file changed afterwards needs a
new confirmation. Files the wizard writes are confirmed by the wizard. The wizard writes only `*.yaml` files with a
plain name inside the chosen folder, and every answer goes through the YAML writer, so an answer cannot add a key.
Gallery examples run on a copy in a scratch folder (nothing is written into the install folder).

Without Yosys: the tab says so in one banner, the example buttons read "(saved result)" and show the saved full
report of the same run (`examples/<name>/saved/`), labelled RECORDED; "My own design" is greyed out with the reason.
Error codes and variable names appear only under "Details" in the Plain view. Pages may be framed by the Studio's
own pages (`frame-ancestors 'self'`), so the Evidence report frame works with the launcher too.
Screenshots: `docs/shots/`.
