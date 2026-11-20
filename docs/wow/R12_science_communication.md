# R12 Science communication: explaining redundancy and common-cause failure
Research lens R12 for the "wow for any audience" pages.

## How this was researched (honest scope)
- One public WebSearch (query: common-cause failure redundancy explained simple analogy). It returned a result list plus a summary; I did NOT open any of the result pages.
- One WebFetch of https://ncase.me/trust/ (Nicky Case, "The Evolution of Trust"): the page opened but returned only a title and a loading placeholder, no usable text. So nothing below is a verified reading of that page.
- Everything else is my own knowledge of the genre, marked UNVERIFIED. Treat this file as design rationale, not a literature review.

## What the search result said (secondary, from a search summary; pages not opened)
- Core idea: redundancy helps only when the backups fail independently; a common-mode failure is one fault that takes out every backup at once. Listed sources (titles only, UNVERIFIED): fs.blog "mental model: redundancy"; accendoreliability.com "common mode failures"; NASA NTRS records 20240013667 and 20240013164; a City University paper on diversity; a dev.to post "Four instances, two data centers, one bug: when redundancy isn't independence".
- The summary's own analogy (it said "my own, not from the sources"): several smoke detectors on one circuit breaker.
- The summary claimed NASA material says that with significant common-cause failures, a third or fourth identical unit adds little. UNVERIFIED (page not opened).
- Mitigations named: diversity (different technology or maker), separation, avoiding shared power or control.

## Patterns that teach this well (UNVERIFIED, from general knowledge of the genre)
1. Explorable explanations (Nicky Case, Bret Victor's "Explorable Explanations" essay, Amit Patel): the reader changes one thing and sees the consequence immediately. Lesson used: the game lets you flip a wire and watch the lock.
2. One idea per screen, concrete picture before the abstract term. Lesson used: door and guard first; the words "common-mode" and "netlist" never appear in the story.
3. Let the reader predict first ("surely one lie is no longer enough?"), then show the surprise. Lesson used: story sections 3 and 4.
4. Everyday single-point-of-failure images that already work for lay audiences: three locks on one hinge; several smoke alarms on one battery or breaker; two nurses copying one wrong chart; two backups on the same shelf; all eggs in one basket. Lesson used: analogies.md, each with where it breaks.
5. Honesty devices: say what the picture simplifies, label illustrative parts. Lesson used: banner on every page.

## Common pitfalls to avoid
- Overclaiming ("proved secure", "real attack"). Both pages say toy example, modelled bit flips.
- Jargon without in-place explanation. "Yosys" is explained as "a free program that turns a design into wires".
- Colour as the only signal. Pages also use text (YES/no, LOCK OPEN/SHUT).
- Motion that cannot be turned off. Animation is skipped under prefers-reduced-motion; buttons still work.
- Analogy creep: an analogy carried too far misleads. Hence the "breaks" line per analogy.

## Design decisions that follow
- 60-second path: banner, headline, door and guard, one lie, three guards, one wire, "oh".
- The "tool twist" (same plan, different builder) is the hardest idea; it is placed last and tied to a measured fact (2 flips versus 3).
- Explainer scenes use one reusable diagram so the change between scenes is easy to see.

## Open items
- The cited pages should be opened and checked before anyone quotes them.
