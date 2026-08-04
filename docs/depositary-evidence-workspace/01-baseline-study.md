# Baseline study — three weeks, no code

The purpose is not to justify the project. It is to find out whether there is
one. A negative result here is a successful study and costs three weeks instead
of a quarter.

## Gate before you start

One named person accountable for review quality agrees to let their team's
hours be measured. If nobody will spend eight analyst-hours on this, the pain
is not what the proposal assumes, and no amount of design work changes that.

Ask exactly this, in 45 minutes, without pitching anything:

> Can I stopwatch your team on eight closed cases and show you where the
> minutes actually go?

## What to measure

Eight to ten closed cases of the **same recurring process**, worked by two
analysts. Do not mix process types — variance across processes will swamp the
signal you are looking for.

### Time categories

Record these separately. The whole study fails if prep and judgement are
recorded as one number.

| Category | Definition | In scope for automation? |
|---|---|---|
| **Locating** | Finding documents: folder navigation, search, asking colleagues, chasing by email | Yes |
| **Version checking** | Confirming a document is current, signed, correct entity/fund | Yes |
| **Assembly** | Copying references, populating the workpaper, formatting | Yes |
| **Reading** | Reading a document to understand it | Partly |
| **Judgement** | Deciding whether a control is satisfied | No |
| **Waiting** | Blocked on a third party: manager, AIFM, valuer, signature | No — but record it |
| **Rework** | Redoing work after a reviewer or a late document | Yes |

### Per-case record sheet

```
Case ref:                        Process type:
Analyst:                         Date worked:

Documents in pack:        ___    of which scanned:        ___
                                 of which spreadsheets:   ___
                                 of which email-derived:  ___

TOUCH TIME (minutes)
  Locating                ___
  Version checking        ___
  Assembly                ___
  Reading                 ___
  Judgement               ___
  Rework                  ___
  ----------------------------
  Total touch time        ___

ELAPSED TIME
  Case opened             ____________
  Case signed off         ____________
  Elapsed calendar days   ___
  Days blocked waiting    ___

FRICTION EVENTS (count)
  Document not found first time        ___
  Wrong version initially used         ___
  Wrong fund / entity document         ___
  Missing document chased              ___
  Conflicting values found             ___
  Reviewer sent it back                ___

Analyst's own answer: what wasted the most time on this case?
  ________________________________________________
```

### Volume figures to obtain

Touch time is meaningless without these. Get them from whoever owns the
process, not by estimating:

- Cases of this type per year: **[TBC]**
- Analysts who work them: **[TBC]**
- Reviewers who sign them off, and their time per case: **[TBC]**
- Seasonal concentration — is this smooth, or 60% in one month? **[TBC]**

## The two numbers that decide the project

**Addressable minutes per case** = Locating + Version checking + Assembly + Rework.
This is the ceiling on what any tool can save, before the cost of verifying
the tool's output is subtracted. If it is under ~15 minutes, stop.

**Addressable hours per year** = addressable minutes × annual case volume ÷ 60.
This is the only number a sponsor will act on. If it is under ~200 hours, this
is a personal-productivity improvement, not a project, and should be pitched as
filing discipline rather than as a system.

## Elapsed time is the trap

If cases sit blocked for days waiting on a valuer or a signature, saving 40
minutes of touch time changes nothing anyone senior cares about. Record days
blocked. If waiting dominates, the honest conclusion is that the valuable
intervention is chasing and visibility — a different, cheaper project — and the
study should say so.

## Output

A two-page memo. Structure:

1. What was measured, and the method's limits (n=8, one process, two analysts,
   observer effect, self-reported categories).
2. The two numbers above, with the range across cases, not just the mean.
3. Friction event frequencies — these justify the deterministic checks far
   better than time savings do.
4. Three verbatim analyst quotes about what actually wasted their time.
5. A recommendation that is allowed to be "don't build this."

This memo is the credibility artifact. It survives a negative result; a demo
does not.
