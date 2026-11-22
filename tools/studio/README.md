# GlitchSAT Studio

A local app (one Python file, standard library only) that runs the GlitchSAT engine on the three toy designs
(V0, V1, V2), replays attacks step by step and shows the project's recorded results. Without z3 or Yosys it shows
recorded results and says so on screen. It listens on 127.0.0.1 only.

Start it from the repository root:

```
bash tools/studio/glitchsat-studio.sh
```

Options: `--port N` (default 8765), `--no-browser`, `--no-autostop`.

Some views belong to add-on modules that are not part of this repository yet. Each such view says where it looked
for its data and that the module is missing; the rest of the app works without them.

Test: `python3 -m pytest tools/studio/tests` starts Studio on a free port and checks the page and the JSON endpoints.
