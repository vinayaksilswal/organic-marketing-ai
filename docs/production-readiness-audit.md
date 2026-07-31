# Production-Readiness Audit — Core Modules

Every finding below was verified against the code in this repository, with the
file that proves it. Nothing here is generic SaaS advice; if it is listed, I
checked that it is actually missing or actually broken.

Ordered by what stops you taking money and keeping customers, not by how
interesting it is to build.

---

## Tier 1 — Blocks selling to a real customer

### 1. There is no way to tell whether any of this is working
**Missing entirely.** Nothing in the codebase fetches Meta Insights. `grep` for
`insights|impressions|reach` across `services/social_service.py` returns only
error strings.

A customer pays $17/month and gets: posts went out. Not how many people saw
them, not which caption did better, not whether any of it moved. Email has
open/CTR fields; social has nothing.

This is the single biggest gap. It is why people churn from tools like this in
month two — not because the output is bad, but because they cannot tell if it
is good. It also removes your only honest source of testimonials.

*Needs:* a scheduled job pulling `/{ig-media-id}/insights` and
`/{post-id}/insights` into a `PostMetrics` table, and a panel that ranks
published posts by reach and engagement.

### 2. Anyone can sign up with an email they do not own
**Missing entirely.** No `emailVerified` column, no verification send anywhere
in `routers/auth.py`.

Combined with a dead password reset (`resend:false`), an account created with a
typo'd address is unrecoverable, and you cannot prove a paying customer owns
the address you are billing.

### 3. No rate limiting on authentication
`slowapi` is not installed and nothing guards `/auth/login`. Password guessing
is unthrottled, and `/api/public/demo-caption` is the only endpoint in the
product with any limiter — one I added by hand.

### 4. No account deletion or data export
**Missing entirely.** No endpoint anywhere deletes a user's data or exports it.

GDPR Article 15 (access) and Article 17 (erasure) are not optional for EU or UK
customers, and you are storing their social tokens, subscriber lists and
business data. This is a legal exposure the moment one European customer signs
up, which is the same moment you start selling.

---

## Tier 2 — Breaks trust once customers are live

### 5. Meta tokens expire and nothing tells the user
`routers/meta_oauth.py` exchanges for a long-lived user token; Page tokens
derived from it do not expire, but they die when the user changes their
password, revokes the app, or Meta invalidates the session.

`services/social_service.py` detects error code 190 and raises — good — but
nothing marks the connection as broken or prompts a reconnect. The customer
finds out when posts have been failing for a week.

*Needs:* on error 190, flag `SocialConnection` as `needsReauth`, surface a
banner, and email the owner.

### 6. No audit log
No `AuditLog` model exists. When a team member deletes a business, changes the
offer, or turns on auto-approve, there is no record. For a product with team
seats on the Agency plan, "who published that" has no answer.

### 7. CI does not catch the failure that has actually hurt you
`.github/workflows/ci.yml` runs pytest on **Python 3.12**; production runs
**3.11.9** (`render.yaml`). More importantly it never does `python -c "import
main"` — which is precisely the check that would have caught the `SyntaxError`
that silently blocked deployment for days.

*Needs:* pin 3.11.9, add an import check and an `alembic upgrade head` against
a throwaway Postgres.

### 8. No backup or retention policy
Nothing in the repo documents Neon's backup settings or a restore procedure. If
the database is lost you lose every customer's tokens, subscribers and history.

---

## Tier 3 — Product gaps that cost conversions

### 9. Scheduling is "every N hours", nothing else
`MarketingState.postIntervalHours` is the only control. There is no
time-of-day, no timezone, no day-of-week. A business in Delhi and one in
Chicago post at the same moment, and a B2B brand cannot avoid posting at 3am.

Timezone-aware scheduling is table stakes for anything called a scheduler.

### 10. No calendar or queue view
Posts exist as a flat list. There is no view of what is coming, no way to
reorder, no way to skip one. The review log answers "what happened", never
"what is about to happen".

### 11. No support channel, and no feedback loop
Nothing in the product lets a user report a problem or request a feature. For
a self-serve SaaS this means every issue becomes a churn event you never hear
about.

*Worth building:* an in-app support widget writing to a `SupportTicket` table,
and a public feature board where requests can be upvoted — that board doubles
as your roadmap evidence and shows prospects the product is alive.

### 12. No onboarding checklist
A new account lands on an empty Command Center. Nothing walks them through
*connect Meta → upload media → set your offer → run once*. The steps exist;
the guidance does not.

---

## What I would do, in order

| # | Work | Why first |
|---|------|-----------|
| 1 | `RESEND_API_KEY` + email verification | Password reset is dead; unrecoverable accounts on day one |
| 2 | Post analytics from Meta Insights | The only proof the product works, and your testimonial source |
| 3 | Auth rate limiting + account deletion/export | Legal and security floor for selling in the EU/UK |
| 4 | Token-expiry detection with a reconnect prompt | Silent failure is the worst failure mode you have |
| 5 | CI: pin 3.11.9, import check, migration check | Stops the deploy problem that has already cost days |
| 6 | Timezone + time-of-day scheduling | First thing a real customer will ask for |
| 7 | Support widget + feature board | Turns silent churn into signal |

---

## What is genuinely solid already

Worth stating, because the list above is long:

- **Tenant isolation** — workspace scoping is consistent, and the cross-tenant
  email blast and `/stats` leak are both fixed and tested.
- **Secret handling** — social and email credentials are Fernet-encrypted at
  rest and never returned to the client.
- **Billing** — PayPal subscriptions with idempotent webhooks, replay
  protection, and entitlement that actually expires.
- **Failure visibility** — per-platform delivery errors, generation status, and
  quota messages all reach the user in words they can act on.
- **AI degradation** — an eleven-model fallback chain into Gemini, so a
  rate-limited provider does not take the product down.
- **Honest surfaces** — no fabricated testimonials, metrics, statuses or plan
  badges anywhere in the product or on the marketing site.

The foundations are sound. What is missing is mostly the layer that proves
value to a customer and the compliance floor for selling in Europe.
