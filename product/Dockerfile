# BUILT AND RUN LOCALLY ONLY (2026-11-20): the build succeeded only after the sandbox proxy's CA was added to a COPY of this file (the container did not trust the proxy's TLS CA; TLS checking not disabled; this file is unchanged). Not built on a normal network or on GitHub. Image runs as uid 1000; Debian's Yosys here is 0.52 (v2 at <=2 flips: NO_ATTACK, 83 gates; see docs/NUMBERS.md YOSYS.version).
# Build from the repository root:  docker build -f product/Dockerfile -t faultbound-wt:dev .
# Run:  docker run --rm -v "$PWD":/work faultbound-wt:dev analyze /work/netlist.json --config /work/threat.toml
# Yosys comes from Debian's apt (version depends on the base image; the report records it). Pin the base by digest for reproducibility.
FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends yosys \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/faultbound
COPY product/ /opt/faultbound/product/
RUN pip install --no-cache-dir /opt/faultbound/product
RUN useradd --create-home app
USER app
WORKDIR /work
ENTRYPOINT ["faultbound-wt"]
CMD ["--help"]
