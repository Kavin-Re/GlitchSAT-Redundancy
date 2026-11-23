# Session log

Fill one at the **end** of every session. Ten minutes, no more. Write for a reader three months from now who
remembers nothing.

**Where it is kept.** A contributor puts the log in the pull-request description. Decisions always go to
`docs/plan/DECISIONS.md` in this repository.

Sections 1, 3 and 8 are required. The others are filled only when there is something to say.

| | |
|---|---|
| Date | |
| Time spent | |
| Backlog entry | for example `#020` (P05.1) |
| Branch | |
| Last commit | output of `git log --oneline -1` |
| Working tree clean? | yes / no; if no, what is uncommitted and why |

## 1. What I did (required; three to six lines of fact)

- 

## 2. What I learned or what surprised me

- 

## 3. State of the tests (required)

| Command | Result (last line; counts, not just PASS) |
|---|---|
| `python3 -m pytest -q tests product/tests` | |
| `python3 scripts/test_all.py` (add `--strict` once it exists) | |
| `python3 tools/check_wording.py tools product scripts docs` | |
| Other: | |

A failing check is either fixed today or written here as a known open item with a date.

## 4. Numbers produced today

Every number gets a label: COMPUTED, SIMULATED, ASSUMED, SOURCED or recorded. Every verdict gets PROVED,
BOUNDED or SAMPLED.

| Number or verdict | Label | Command that produced it | File where it is stored |
|---|---|---|---|
| | | | |

## 5. Decisions made

One line each here; the full entry goes in `docs/plan/DECISIONS.md`.

- 

## 6. Blockers and open questions

| Blocker or question | What I tried | Who or what could answer it |
|---|---|---|
| | | |

## 7. Three questions (only when a new module or phase started today)

- What is the model, and what measurement supports it?
- Who has done this already? Date of the search:
- What result would show it is wrong?

## 8. Next session: start exactly here (required)

The first command to run:

```bash
cd ~/work/GlitchSAT-Redundancy && . .venv/bin/activate && git status
# then:
```

The first file to open:

The very next small step (one sentence, doable in 30 minutes):

After that:

## 9. Checks before closing

- [ ] No new sentence says "glitches" where it means "modelled bit flips" or "modelled events".
- [ ] Every new number has a label and a stored command.
- [ ] Nothing was claimed as new without a dated literature check.
- [ ] Results I did not re-run are marked "recorded".
- [ ] Every new or changed core function has a docstring.
- [ ] Nothing was pushed, tagged or published (only the maintainer does that).
- [ ] If the handoff file's "current phase" or "next step" changed, I updated it.

## 10. Before a long pause

One paragraph: what state the work is in, and what the next person needs to know that is not written down
elsewhere.
