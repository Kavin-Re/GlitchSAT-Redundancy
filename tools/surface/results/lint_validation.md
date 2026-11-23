| netlist | top | gates | lint (mode) | single points | measured min | recorded min (source) |
|---|---|---|---|---|---|---|
| `formal/gen/v1.json` | v1 | 70 | merged (names) | 14 | 1 | - |
| `reference/spike_netlists/v1.json` | v1 | 58 | merged (names) | 18 | 1 | 1 (results/reproduce (V1 spike, k=1)) |
| `research/c2/b1_faultmodels/netlists/v1_apt033.json` | v1 | 72 | merged (names) | 14 | 1 | - |
| `research/c2/b1_faultmodels/netlists/v1_conda038.json` | v1 | 70 | merged (names) | 14 | 1 | - |
| `research/c2/e2_variance/baseline_netlists/apt0.33_v1.json` | v1 | 72 | merged (names) | 14 | 1 | - |
| `research/c2/e2_variance/baseline_netlists/conda-eda0.38_v1.json` | v1 | 70 | merged (names) | 14 | 1 | - |
| `research/c2/e2_variance/baseline_netlists/conda-formal0.38_v1.json` | v1 | 70 | merged (names) | 14 | 1 | - |
| `research/c4/layout/nl/v1_layout.json` | v1 | 75 | merged (names) | 17 | 1 | - |
| `validation/nl/v1.json` | v1 | 55 | merged (structural) | 0 | 1 | - |
| `formal/gen/v2.json` | v2 | 83 | separate (names) | 0 | 3 | - |
| `formal/gen/v2_y038.json` | v2 | 83 | separate (names) | 0 | 3 | 3 (research/c3/rep/rep_results.csv (orig_unit)) |
| `formal/gen/w2o.json` | v2 | 81 | separate (names) | 0 | 2 | - |
| `reference/spike_netlists/v2.json` | v2 | 68 | separate (names) | 0 | 3 | 3 (results/reproduce/v2_spike_given-netlist_k3.json) |
| `research/c2/b1_faultmodels/netlists/v2_apt033.json` | v2 | 85 | separate (names) | 0 | 2 | 2 (research/c6/p12/enum.json (V2-apt, T=4)) |
| `research/c2/b1_faultmodels/netlists/v2_conda038.json` | v2 | 83 | separate (names) | 0 | 3 | - |
| `research/c2/e2_variance/baseline_netlists/apt0.33_v2.json` | v2 | 85 | separate (names) | 0 | 2 | 2 (research/c2/e2_variance/raw/matrix.csv (apt0.33 plain baseline)) |
| `research/c2/e2_variance/baseline_netlists/conda-eda0.38_v2.json` | v2 | 83 | separate (names) | 0 | 3 | 3 (research/c2/e2_variance/raw/matrix.csv (conda-eda0.38 plain baseline)) |
| `research/c2/e2_variance/baseline_netlists/conda-formal0.38_v2.json` | v2 | 83 | separate (names) | 0 | 3 | 3 (research/c2/e2_variance/raw/matrix.csv (conda-formal0.38 plain baseline)) |
| `research/c2/reviews/ct/tests/v2_inbuf.json` | v2 | 76 | merged (names) | 26 | 1 | - |
| `research/c4/layout/nl/v2_layout.json` | v2 | 87 | separate (names) | 0 | 3 | - |
| `research/c6/p01/netlists/nl_apt_v2.json` | v2 | 85 | separate (names) | 0 | 2 | 2 (research/c6/p01/glitchsat_cross.txt (apt v2)) |
| `research/c6/p01/netlists/nl_conda_v2.json` | v2 | 83 | separate (names) | 0 | 3 | 3 (research/c6/p01/glitchsat_cross.txt (conda v2)) |
| `validation/nl/v2.json` | v2 | 55 | merged (structural) | 0 | 1 | 1 (validation/VALIDATION.md (flow B: 4 of 378 single flips succeed)) |
| `research/c4/layout/nl/v2_wi_layout.json` | v2_wi | 87 | separate (names) | 0 | 3 | - |
| `research/c6/p01/netlists/nl_apt_v2c04.json` | v2c04 | 81 | separate (names) | 0 | 1 | - |
| `research/c6/p01/netlists/nl_conda_v2c04.json` | v2c04 | 82 | separate (names) | 0 | 1 | - |
| `research/c6/p01/netlists/nl_apt_v2c4d.json` | v2c4d | 89 | separate (names) | 0 | 2 | - |
| `research/c6/p01/netlists/nl_conda_v2c4d.json` | v2c4d | 88 | separate (names) | 0 | 3 | - |
| `research/c6/p01/netlists/nl_apt_v2c5a.json` | v2c5a | 88 | separate (names) | 0 | 3 | - |
| `research/c6/p01/netlists/nl_conda_v2c5a.json` | v2c5a | 88 | separate (names) | 0 | 3 | - |
| `research/c6/p01/netlists/nl_apt_v2e.json` | v2e | 89 | separate (names) | 0 | 3 | 3 (research/c6/p01/glitchsat_cross.txt (apt v2e); research/c6/p12/enum.json (T=4)) |
| `research/c6/p01/netlists/nl_conda_v2e.json` | v2e | 81 | separate (names) | 0 | 3 | 3 (research/c6/p01/glitchsat_cross.txt (conda v2e)) |

all:

| | measured min 1 | measured min > 1 |
|---|---|---|
| lint merged | 11 | 0 |
| lint not merged | 2 | 19 |

v1 (control):

| | measured min 1 | measured min > 1 |
|---|---|---|
| lint merged | 9 | 0 |
| lint not merged | 0 | 0 |

v2 family:

| | measured min 1 | measured min > 1 |
|---|---|---|
| lint merged | 2 | 0 |
| lint not merged | 2 | 19 |
