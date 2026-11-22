# Targets are real; every number in results/ is produced by these commands.
# Needs: python3 (>=3.9), z3-solver, pytest, and system yosys + iverilog on PATH. Run `make check-tools` first.
SHELL := /bin/bash
PY ?= python3
.PHONY: help check-tools reproduce check-reproduce ci test bench mutate replay dashboard validate clean
help:
	@echo "make check-tools - verify yosys, iverilog, z3 (python) and pytest are available"
	@echo "make test        - pytest (engine tests)"
	@echo "make reproduce   - V0/V1/V2 sweeps -> results/reproduce/*.json + results/reproduce_summary.json (~25 s)"
	@echo "make check-reproduce - compare results/reproduce_summary.json with ci/expected_reproduce.json"
	@echo "make ci          - what the PR workflow runs: check-tools test reproduce check-reproduce replay"
	@echo "make replay      - generate+run iverilog replay testbenches from solver output (VCD in tb/generated/)"
	@echo "make dashboard   - rebuild dashboard/index.html from results/ (run 'make reproduce' first)"
	@echo "make validate    - re-run the independent gate-level simulator check (validation/k1.py, k=1, T=6, <1 s)"
	@echo "make bench       - reduction benchmark -> results/reduction_benchmark.json (~2 min)"
	@echo "make mutate      - mutation check on V2 -> results/mutation_summary.json"
	@echo "make clean       - remove generated work dirs (results/work, results/mutants, tb/generated)"
check-tools:
	@command -v yosys >/dev/null || { echo "MISSING: yosys"; exit 1; }
	@command -v iverilog >/dev/null || { echo "MISSING: iverilog"; exit 1; }
	@$(PY) -c "import z3, pytest" || { echo "MISSING: pip install z3-solver pytest"; exit 1; }
	@echo "tools OK: $$(yosys -V) / $$(iverilog -V 2>/dev/null | head -1) / z3 $$($(PY) -c 'import z3;print(z3.get_version_string())')"
reproduce:
	mkdir -p results/logs
	set -o pipefail; $(PY) scripts/reproduce.py 2>&1 | tee results/logs/reproduce.log
check-reproduce:
	$(PY) ci/check_reproduce.py
ci: check-tools test reproduce check-reproduce replay
replay:
	mkdir -p tb/generated
	$(PY) scripts/replay.py results/reproduce/v0_rtl_plain_k1.json
	$(PY) scripts/replay.py results/reproduce/v1_rtl_plain_k1.json
dashboard:
	$(PY) dashboard/build.py
validate:
	cd validation && for d in v0 v1 v2; do $(PY) k1.py nl/$$d.json $$d 6 || exit 1; done
bench:
	mkdir -p results/logs
	set -o pipefail; $(PY) scripts/bench_reduce.py 2>&1 | tee results/logs/bench_reduce.log
mutate:
	mkdir -p results/logs
	set -o pipefail; $(PY) scripts/mutate.py --all 2>&1 | tee results/logs/mutate.log
test:
	mkdir -p results/logs
	set -o pipefail; $(PY) -m pytest -q tests 2>&1 | tee results/logs/pytest.log
	$(PY) docs/explainers/dev/check_hub.py
	$(PY) docs/explainers/dev/check_dial.py
	$(PY) docs/explainers/dev/check_wall.py
	$(PY) docs/explainers/dev/check_theatre.py
	$(PY) docs/explainers/dev/check_game_answers.py
clean:
	rm -rf results/work results/mutants tb/generated
