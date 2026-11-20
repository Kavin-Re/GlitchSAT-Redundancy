# Evidence labels
| Label | Meaning | Allowed wording |
|---|---|---|
| MEASURED | A command in this repo produced it; command and log are stored in results/ | "measured", "observed" |
| SIMULATED | Produced by RTL or model simulation | "in simulation" |
| ESTIMATED | Derived from a model or a tool's estimate (e.g. placer timing) | "estimated" |
| ILLUSTRATIVE | Drawn to explain; not a result | must say "illustrative" |
| UNVERIFIED | Claimed by a source I did not open or run | must say "unverified" |
Never: "proved" unless a solver proved it and the bounds are stated; "first"/"novel" without a checked literature search; any silicon, power or board claim without a measurement.
