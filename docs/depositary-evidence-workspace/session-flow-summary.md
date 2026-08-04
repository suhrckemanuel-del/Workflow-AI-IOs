# Depositary Evidence Workspace — full session flow

A walkthrough of everything covered in this session, in order, so the whole
arc is visible in one place. Written for brainstorming, not as a polished
deliverable — it shows how each stage changed the shape of the idea.

---

## Stage 0 — The starting idea

You brought a fully-formed proposal: a **Depositary Evidence Workspace** for
Aztec — a controlled, read-only system that helps depositary analysts
assemble evidence for recurring controls and checklists.

Core principle: a checklist item can only be marked **"Supported"** if it
carries a precise citation (document, version, page/table, excerpt) to
accepted source material. Permitted outcomes were deliberately narrow —
Supported / Missing / Conflicting evidence / Calculation mismatch / Needs
analyst judgement — with mandatory human sign-off and no autonomous actions
(no approvals, no exception closure, no record changes, no client emails, no
payments).

The proposal already included: an MVP scope (one process, 15–25 checklist
items, 10–20 historical cases), a security model (least-privilege read-only
SharePoint access, deterministic rules, audit logging, prompt-injection
awareness), an 8-workflow roadmap, a "small builder team, not everyone gets
Codex" operating model, and an evaluation plan with pass/fail metrics. You
asked 11 specific critique questions — is the pain real, which use case
first, what's buildable on existing tools, what should stay manual, etc.

---

## Stage 1 — LLM Council pressure-test

You asked me to run the idea through the `llm-council` skill (from
`aiwithremy/claude-skills-llm-council` on GitHub). I cloned the skill, then
ran the full process:

1. **5 independent advisors** (Contrarian, First Principles Thinker,
   Expansionist, Outsider, Executor) each analyzed the proposal from a fixed
   lens, in parallel, with no visibility into each other's answers.
2. **Anonymized peer review** — each advisor's response was relabeled A–E and
   reviewed by 5 fresh reviewers answering: strongest response, biggest blind
   spot, and what all five missed.
3. **Chairman synthesis** — one final pass combining everything into a
   verdict.

### What came out of it

**Where the council agreed (high confidence):**
- The 20–45 min/case saving is invented — there's no baseline yet.
- No named sponsor, no named user, no case-volume number — the whole
  business case is currently a theory of someone else's pain.
- **Ship the deterministic pack-readiness gate first**, not the citation
  collector — no LLM, no hallucination surface, no model-risk committee.
- The real critical path is IT/DPIA/vendor approval (months), not code.

**Where it clashed:**
- Build nothing yet (Contrarian) vs. build the boring, risk-free half now
  (Executor) — resolved as: the *AI* pilot can't ship in 8 weeks, but
  deterministic tooling can, in parallel with measurement.
- Is the citation layer even the product, or is the real asset a
  machine-readable **control library** (checklist items as testable
  predicates) that has value with zero AI?
- Scope up (promote the audit/DDQ pack builder, reframe as capacity not
  minutes) vs. scope down — reviewers flagged the "scope up" advisor's
  response as the biggest blind spot in the whole council (governance
  overreach with no mandate).

**Blind spots the peer review caught that no advisor addressed directly:**
- Nobody answered the actual core question: is page-level citation reliable
  on real depositary PDFs? (Answer given in the chairman synthesis: yes for
  born-digital PDFs, no for scans/Excel/email — route those to "needs
  analyst" instead of promising citation everywhere.)
- **Automation bias** — a pre-populated, confidently-cited checklist can turn
  analyst sign-off into rubber-stamping, degrading the control while every
  metric looks fine. Mandatory sign-off is not automatically a safety net.
- The dangerous failure isn't "unsupported = supported," it's
  **wrongly-supported** — a real, correctly-located citation attached to a
  claim it doesn't actually satisfy. No metric in the original plan caught
  this.
- No ground truth exists for the historical cases — shadow-mode evaluation
  needs hand-labelled gold answers, which is itself a real cost nobody had
  budgeted.
- Retrospective evaluation against today's checklist is invalid if the
  checklist itself is versioned and policy has changed since the case closed.
- Possible regulatory framing (AIFMD/CSSF-adjacent delegated-function
  tooling) that the original proposal hadn't addressed.

**Final recommendation:** run a 3-week, no-code baseline time-and-motion
study (in parallel, start the IT/DPIA conversation) plus a 2-day citation
feasibility spike, then build the deterministic pack-readiness gate as the
actual first shippable thing — the citation collector becomes phase 2, gated
on the spike results and a labelled gold set.

**The one thing to do first:** a 45-minute conversation with whoever is
accountable for review quality — "can I stopwatch your team on 8 closed
cases and show you where the minutes go?" That single ask tests both whether
the pain is real and whether a sponsor exists, for the cost of one meeting.

---

## Stage 2 — Started building the pre-code pack (interrupted)

You said "continue," so I began turning the council's verdict into an actual
working pack in `docs/depositary-evidence-workspace/`:

- **`README.md`** — index of the pack, the three claims it's designed to
  test (prep time is material / citation is feasible / someone wants it),
  and an explicit "what's deliberately not here" section (no architecture,
  no data model, no prompt design — all premature).
- **`01-baseline-study.md`** — the full instrument for the 3-week
  time-and-motion study: per-case record sheet, time categories (locating /
  version-checking / assembly / judgement / waiting / rework), the two
  numbers that decide the project (addressable minutes per case,
  addressable hours per year), and why elapsed time (queue-blocked days) is
  the trap that makes a fast tool look good while changing nothing.

This was cut off before the remaining referenced files
(`02-citation-spike.md`, `03-proposal-v2.md`, `04-evaluation-plan.md`) were
written — they still only exist as placeholders in the README's table.

---

## Stage 3 — Pivot: "what's the fastest, highest-ROI thing to actually build"

You reset the frame: instead of continuing the governance-heavy pack, you
wanted concrete build options — 3–5 ideas, evaluated, ranked, cross-checked
by a second independent pass.

**Five candidates**, deliberately scoped from the council's own constraints
(deterministic where possible, zero new vendor approval, prototypable on
sample data before touching production):

1. **Case Friction Tracker** — Power App/Excel self-logging form; produces
   the baseline data itself; no document access needed.
2. **Pack Completeness Checker** — lists files in a case folder, checks
   filenames against a required-category list, flags missing categories.
   Metadata only, never opens file content.
3. **Version & Duplicate Detector** — hash/filename-pattern check for
   duplicates and stale versions; shares a backbone with #2.
4. **Evidence Index / Pack Assembler** — auto-generates a cover index for an
   already-organized case folder; metadata only.
5. **Keyword-Search Evidence Locator** — deterministic full-text search
   across PDFs to suggest candidate citation pages; closest to the original
   vision, but gated on PDF text quality.

**Two independent evaluator agents** scored all five against the same rubric
(build time, ROI, regulatory/model risk, IT dependency, adoption
likelihood) — run in parallel, neither seeing the other's output, one of
them additionally forced to name the single most likely failure mode for
each candidate.

**Both converged independently on the same ranking:**

| Rank | Tool | Why |
|---|---|---|
| 1 | **Pack Completeness Checker** | 2–4 days, filename-only, zero content-access risk, zero approval needed to prototype, attacks the most-cited pain directly |
| 2 | Version & Duplicate Detector | Near-free bolt-on once #1's folder-listing code exists |
| 3 | Case Friction Tracker | Cheap and strategically necessary, but weak alone — logging discipline decays without a mandate |
| 4 | Evidence Index / Pack Assembler | Real but narrower win; fragile across differing fund/case templates |
| 5 | Keyword-Search Evidence Locator | Highest ceiling, but 3–5× the build effort and fails silently on scanned/signed documents — build last |

**Recommendation:** build #1 alone first, fully prototyped on synthetic
sample files with no SharePoint or IT ticket needed to start; run #2 as a
cheap parallel instrument. That's a working, demonstrable, zero-risk tool in
under a week — and it happens to be the same conclusion the council reached
from a completely different angle (risk/governance vs. speed/ROI). That
convergence is a signal, not a coincidence.

---

## Stage 4 — Technical follow-ups (from "what to build" to "how, safely")

**"What is OCR and what role does it play?"** — explained OCR as the
image-to-text step, and tied it directly to why the #5 candidate is ranked
last: depositary evidence is disproportionately scanned/signed documents —
exactly the ones a keyword-search tool would fail on silently (reporting
"not found" when the text simply isn't machine-readable), which is worse
than no tool at all. This is also why #1 was ranked first — it never needs
OCR because it only reads filenames.

**"Cheapest way to have an agent harness that checks folders, like Claude
Code or Codex?"** — the answer split into two tiers:
- For deterministic checks (like #1): skip the agent entirely — a plain
  script/cron/Power Automate flow costs ~$0 per run.
- For checks that genuinely need LLM judgment: self-host the **Claude Agent
  SDK** (the same harness Claude Code uses, but a free library you run
  yourself) restricted to a couple of read-only tools, paying only
  per-token API costs — cents to a few dollars per run on Haiku-tier
  pricing. Explicitly **not** buying Claude Code or Codex seats per
  analyst — that's the higher-privilege, higher-cost, wrong-shaped option
  your own original proposal had already ruled out.

**"Can you break down the Agent SDK, I feel like I need security access?"**
— broke the SDK down into two independent security questions:
1. The **API credential** (just auth/billing — one centrally-held key, not
   distributed to analysts).
2. What the harness can actually **do on the machine it runs on** — since
   the SDK provides no sandbox of its own, this is entirely your
   responsibility. Concrete recommendation for your use case:
   `allowedTools: ["Read", "Glob", "Grep"]` only (structurally excludes
   Bash/Write/Edit/WebFetch, not just told not to use them), run under a
   read-only-mounted service account scoped to only the case folder, block
   all outbound network except Anthropic's API, and log every tool call via
   hooks for the audit trail. Also flagged **Managed Agents** as the
   alternative where Anthropic owns the sandbox instead of you, if you'd
   rather not run the container yourself.

---

## Where things actually stand right now

- `docs/depositary-evidence-workspace/README.md` and `01-baseline-study.md`
  exist in the repo but are **untracked in git** — not committed, and the
  pack is incomplete (3 of 5 referenced docs were never written).
- The council's "measure first, ship the deterministic gate in parallel"
  path and the tool-evaluation's "build the Pack Completeness Checker first"
  conclusion are **the same recommendation reached twice, independently** —
  once from a risk/governance lens, once from a speed/ROI lens.
- No code has been written yet for the checker itself.
- Security posture for the checker (self-hosted Agent SDK, read-only tool
  allowlist, no network) has been designed but not implemented or tested.

## Open threads to brainstorm from

- Finish the docs pack as originally scoped, or treat it as superseded by
  the simpler build-first path and abandon/trim it?
- Who is the actual named sponsor/ops-manager contact — the council's "one
  thing to do first" — and has that conversation happened?
- Should the Pack Completeness Checker be scaffolded now as real code
  against synthetic sample data, independent of any Aztec access?
- How does the checker's output (missing-doc flags) eventually feed into
  the audit-log and sign-off requirements from the original proposal, once
  it's more than a standalone script?
- Where will this actually run day-to-day — your laptop, a shared service
  account, eventually Aztec infra — and does the security config above
  change per environment?
