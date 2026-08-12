# Cowork Brief â€” Conversion & Enterprise-Readiness Audit

Paste everything below the line into Cowork as a single prompt. It is written to
stand alone: the agent starts cold and has no memory of this project.

---

## Context

**Product:** OrganicAI â€” a SaaS that runs organic social marketing on autopilot for
small businesses. A user adds their business (website + description), the AI reads
the site to build a brand profile, generates creatives and video prompts, and
publishes to Facebook, Instagram, LinkedIn and X on a schedule (default every 2
hours). Single plan, $17/month, PayPal only.

**Live:** https://organic-marketing-ai.vercel.app
**Backend:** https://organic-marketing-ai-0abh.onrender.com (FastAPI)
**Repo:** the working directory you are in.

**Stack:** React 18 + Vite (`frontend/`), FastAPI + SQLAlchemy async + PostgreSQL,
Alembic migrations, APScheduler for the posting loop, ARQ/Redis for background
jobs with an inline asyncio fallback.

**Business goal:** convert cold visitors into paying subscribers, and make sure a
paying subscriber's marketing actually runs without them touching it. Revenue
depends on both halves. A beautiful landing page that leads to a product which
silently posts nothing produces refunds, not income.

## Your job

Audit the product end to end from the point of view of (a) a cold visitor deciding
whether to pay, and (b) a new paying customer trying to get value in their first
15 minutes. Then produce a prioritised, implementable plan.

Work in this order.

### 1. Map the real user journey

Walk the actual flow in the code and, where possible, the live site:
landing â†’ signup â†’ checkout â†’ onboarding â†’ add business â†’ connect socials â†’
creatives generated â†’ posts queued â†’ review/approve â†’ published.

For each step record: what the user sees, what could confuse them, what could
fail silently, and how many clicks/fields it takes. Flag any step where a
reasonable person would give up.

### 2. Conversion audit of the landing page

`frontend/src/pages/Landing.jsx`. Assess:

- Does the hero make the value proposition obvious in under 5 seconds?
- Is there a credible reason to trust this? (Note: fake customer logos were
  deliberately removed â€” do **not** propose adding social proof the business
  cannot substantiate. Propose ways to earn trust honestly instead.)
- Is the pricing objection handled? Is the risk reversal clear?
- Is there a single dominant call to action, or are there competing ones?
- Where does the page ask for effort before delivering value?
- Mobile: does the whole flow work on a phone?

### 3. Find the "too many ways to do the same thing" problem

The owner's words: *"there many options for the same thing, aline everything up."*
There is real duplication across the dashboard â€” e.g. content generation is
reachable from the Overview campaign generator, the AI Video Studio, and the
Media & Catalog uploader; posting cadence is configurable in both the Workspaces
automation tab and the Social Scheduler. Inventory every place a user can perform
the same underlying action, then propose one canonical home for each, with the
others either removed or made into clearly-labelled shortcuts to it.

### 4. Enterprise-readiness gaps

Assess and report on: multi-tenant isolation (does workspace A's data ever leak
into workspace B?), authorization on every workspace-scoped endpoint, audit
logging, error visibility for the operator, onboarding for a team rather than an
individual, data export and deletion, and what happens when a third-party API
(Meta, OpenRouter, Cloudinary) is down or rate-limited.

### 5. Reliability of the core promise

This is the highest-stakes area. Trace what happens after a user clicks
"Initialize Workspace" all the way to a live post. Specifically verify:

- Does creative generation actually complete, and what happens if it fails?
- Does the scheduler pick up the workspace and post on the configured interval?
- If a social token is missing or expired, does the user find out, or does it
  fail silently?
- Is there anywhere a failure is swallowed without reaching a log or the UI?

## Known issues â€” already fixed, do not re-report

- Fake customer logo marquee on the landing page (removed)
- Team page rendered unstyled because it used Tailwind classes that are not
  installed, and showed hardcoded mock members (rewritten against the real API)
- PayPal order amount was not verified server-side, and one order could activate
  unlimited accounts (both closed)
- `asyncio.create_task()` results were discarded in four places, so detached work
  could be garbage collected mid-flight (fixed via `services/task_utils.py`)
- A JSX nesting bug left `social-proof-section` unclosed on the landing page
- New users were being auto-assigned a "Default Workspace"

## Known issue â€” still open, needs your plan

The live backend on Render is serving a stale build: every endpoint added
recently (`/api/v1/team`, `/api/v1/meta/connect`, `/api/v1/admin/system-status`)
returns 404 even though the code is on `origin/main`. Auto-deploy appears to have
stopped after the git history was rewritten by `git filter-repo`. Diagnose and
propose a fix, including how to prevent silent deploy drift in future (e.g. a
`/health` field exposing the running commit SHA, checked by CI after deploy).

Also open: `/api/v1/marketing/emails`, `/api/v1/marketing/audiences` and
`/api/v1/social/scheduler-status` return 500 on the live (stale) build. Determine
whether the current `main` already fixes these, and if not, fix them.

## Deliverable

A single markdown document, `docs/ENTERPRISE_AUDIT.md`, containing:

1. **Executive summary** â€” the three changes most likely to increase paid
   conversion, and the three most likely to reduce churn. One paragraph each.
2. **Journey map** â€” the table from step 1, with a friction score per step.
3. **Findings** â€” each with: severity (critical / high / medium / low), the
   evidence (`file:line`), the user-visible consequence, and the proposed fix.
   Order by severity. Separate revenue-affecting findings into their own section.
4. **Consolidation plan** â€” the duplicate-surface inventory and the single
   canonical home proposed for each.
5. **Implementation plan** â€” sequenced, with each item small enough to ship
   independently. Mark which are safe to do without design input.

## Ground rules

- Do not invent customers, testimonials, metrics, or case studies, and do not
  propose adding any. Every trust signal you recommend must be something the
  business can truthfully substantiate today.
- Cite `file:line` for every claim about the code. If you did not verify it,
  say so explicitly rather than asserting it.
- Distinguish clearly between what you verified running and what you only read.
- Prefer removing a surface over adding one. The owner's complaint is that there
  is already too much, not too little.
- Do not make changes to payment logic, authentication, or the Meta integration
  as part of the audit â€” report on them and propose fixes, but leave the code
  alone so the changes can be reviewed deliberately.
