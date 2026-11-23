# GlitchSAT Studio

The local app of GlitchSAT. Python standard library only, one start command, listens on 127.0.0.1 only and needs
no internet. It runs the GlitchSAT engine live when z3 (and, for rebuilt designs, Yosys) is installed; otherwise it
shows the project's recorded results and says so on screen.

## Start

After `pip install .` at the repository root:

```
glitchsat-studio            # or: glitchsat studio
```

From a clone without installing: `bash tools/studio/glitchsat-studio.sh` (or `python3 tools/studio/studio.py`).
Options: `--port N` (default 8765), `--no-browser`, `--no-autostop`, `--no-plugins`, `--allow-root DIR`.

## What is in this folder

| File | What it is |
|---|---|
| `studio.py` | the app: server, page, guided path, findings, Explore views, studies |
| `first_run_view.py` | the welcome story shown on the first start, and Presenter mode |
| `learn_view.py` | the lesson "Why protect chips?" |
| `labs_view.py` | the Labs page (in the "More" menu) |
| `glitchsat-studio.sh` | start script for a clone |
| `tests/` | pytest smoke tests (start the app on a free port, check the page and the JSON endpoints) |
| `verify*.py` | browser suites (Playwright with Chromium): screenshots, JavaScript errors, wording, behaviour |
| `harness/` | stand-ins for z3, Yosys and the engine, to test the plumbing of live mode without those tools |

The "Open my design" view is loaded from `tools/byod/tools/studio/` (see [`../byod/README.md`](../byod/README.md)).
The other views read their data from `tools/<module>/` at run time.

## Tests

```
python3 -m pytest -q tools/studio/tests
python3 tools/studio/verify_audit.py           # needs: pip install playwright && python3 -m playwright install chromium
```

The `verify*.py` suites write screenshots into `tools/studio/shots_*/` (ignored by git).
