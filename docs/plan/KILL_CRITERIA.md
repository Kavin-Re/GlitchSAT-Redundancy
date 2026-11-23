# Kill and pivot criteria

Read this page at the start of every phase and at every gate. When a signal below is observed, write the date
and the evidence in `DECISIONS.md` and take the action. Stopping on a signal is a planned outcome of this
project, not a failure of it.

The gates (G1, G2, G3) and the time boxes are defined in `ROADMAP.md`, section 4.

## Signals

| Id | Signal | Checked at | Action |
|---|---|---|---|
| K1 | The reading gate shows that an existing open tool already gives timing-derived fault sets usable in a formal search | G2 | Do not rebuild. Contribute to that tool, or publish a comparison only |
| K2 | The reading gate shows, from full text, that the plain timing-violation model is known to be the wrong abstraction for clock glitches | G2 | Redesign the Phase 2 model on paper first (branch sets and sampling effects become primary). No encoder work until the one-page redesign is in `DECISIONS.md` |
| K3 | A formal clock-glitch model with measurements is published by another group before note N1 is out | Any literature sweep | Drop every "first" wording. Re-run their examples in the open flow as a replication, or move weight to the benchmark |
| K4 | On the non-toy block the timing verdict equals the bit-flip verdict, and stays equal across the Monte Carlo draws | G3 | Publish the negative result as a short note. Stage C is reduced to the teaching and survival-check lines |
| K5 | The timing verdict or the cheapest witness changes in a large share of the per-cell Monte Carlo draws (threshold fixed in `DECISIONS.md` D-019: more than 20% of draws at the middle spread) | G3 | The model is too sensitive to give a verdict. The tool reports sets and sensitivity only; "minimum glitch depth" is not a headline |
| K6 | The open flow cannot produce post-route timing for the chosen block on the available machine within the Stage B time box | During Phase 2, Stage 2A | Stay with the toy designs and call the work a teaching tool. No research claim |
| K7 | The Stage B time box is spent and none of the three tables exists | End of the box | Stop Stage B. Offer the encoding idea upstream as an issue. Keep Stage A's results released |
| K8 | The upstream comparison draws a maintainer reply that invites a contribution | Any time after Phase E | Take it. An accepted upstream change outranks every later phase |
| K9 | Twelve months after the first tagged release: no issue or pull request from someone who was not contacted directly, no outside re-run, no named outside user | Each release; recorded in `DECISIONS.md` | Freeze the engine. Keep the learner app and the survival checker as finished pieces. Look for a group with a bench |
| K10 | A module still has no design note or module docstring that explains what it does and why, after a second attempt to write one | Phase C, and before any release | Remove that module from the release |
| K11 | (Retired; the number is kept so that later ids do not change.) | - | - |
| K12 | The Stage A time box is spent and v0.9.1 is not released | End of the box | Cut Stage A to: Phase 0 wording and score removal, the import-path fix, the strict test run. Release that. Everything else in Stage A becomes optional |
| K13 | The transistor-level check contradicts the model on the small block in a way the shapes and hold sets do not cover | Phase 2, P2.14 | Publish the mismatch. No "no attack" statements for clock glitches. Decide in `DECISIONS.md` whether a new effect is worth one more bounded attempt |
| K14 | The pilot shows that the corrected learner material still leaves most participants believing "three copies need three glitches" | After P0.13 | Rewrite the two screens again before any new feature; the learner mission comes before Stage B |

## Notes on the criteria

- **Uniform delay scaling cannot fire K5.** Scaling every delay by one factor keeps the order of arrivals,
  so the sets stay the same and only the depth label moves. K5 therefore uses per-cell and per-region
  variation.
- **Zero is a recordable result.** K9 asks for a count at each release. Writing "zero" is honest and is the
  trigger; it is not hidden.
- **Each criterion names what stays released and useful after it fires.**

## One in, one out

Before any new direction is added to `ROADMAP.md` or `BACKLOG.md`, the direction that is frozen to pay for it
is named in the same `DECISIONS.md` entry, with the date on which the frozen one will be looked at again.
