# Depositary Evidence Workspace — pre-build pack

Working documents for a proposed internal automation project in depositary
operations. Nothing here is a build plan. This pack exists to answer, cheaply,
whether the project is worth building at all — and to make the case defensible
before any code touches client documents.

## Read in this order

| # | Document | Purpose | Effort |
|---|---|---|---|
| 0 | [`00-council-verdict.md`](00-council-verdict.md) | Record of the critique this pack responds to | — |
| 1 | [`01-baseline-study.md`](01-baseline-study.md) | Measure where the minutes actually go, before building | 3 weeks, no code |
| 2 | [`02-citation-spike.md`](02-citation-spike.md) | Test whether page-level citation is even possible on the real evidence base | 2 days |
| 3 | [`03-proposal-v2.md`](03-proposal-v2.md) | The proposal, rewritten to survive a sceptical reader | — |
| 4 | [`04-evaluation-plan.md`](04-evaluation-plan.md) | Metrics, gold-set labelling, pass/fail gates | — |

## The three claims this pack is designed to test

1. **Prep time is material.** Analysts lose meaningful time to locating,
   version-checking and assembling evidence — not just to judgement.
   → tested by `01-baseline-study.md`
2. **Citation is feasible.** A stated fact can be reliably anchored to a
   document, version and page in the evidence base as it actually exists.
   → tested by `02-citation-spike.md`
3. **Someone wants it.** A named person accountable for review quality will
   spend their team's hours on the measurement.
   → tested by whether step 1 happens at all

If claim 3 fails, stop. If claim 1 fails, stop. If claim 2 fails, the
deterministic scope in `03-proposal-v2.md` still stands — the citation layer
does not.

## What is deliberately not here

No architecture diagram, no data model, no prompt design, no tool selection.
All of it is premature until the three claims above are settled, and producing
it early is the main way this kind of proposal loses credibility.

## Status

| Item | State | Owner |
|---|---|---|
| Named sponsor identified | Not started | — |
| Baseline study run | Not started | — |
| Citation spike run | Not started | — |
| IT / data-classification conversation opened | Not started | — |
| Firm AI programme checked for overlap | Not started | — |
