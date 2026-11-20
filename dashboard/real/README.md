# Real netlist renders (MEASURED-FROM-TOOL)
Netlists: `netlists/v{0,1,2}.json` are copies of the Yosys 0.33 `write_json` output the solver used
(`.../spike_F2/work/v*.json`; source `src/boot.v`). My own re-run of Yosys with a guessed flow gave different
gate counts/net names, so the spike's JSONs are used as-is to keep fault net names exact.
Faulted nets come from `work/v*_results.json` (first SAT, cycle 1; V2 = 3 flips).

    apt-get install -y graphviz
    cd dashboard/real
    python3 render.py        # writes v*.dot, v*.svg, v*.png via `dot -Tsvg` / `dot -Tpng -Gdpi=160`
    # view: index.html (self-contained, uses the SVGs)
