# Organiflo — handoff brief

You are taking over an in-flight production SaaS. Read this whole file before
touching anything. It is written to save you the specific mistakes that have
already been made and fixed here, most of which look correct until they reach
production.

---

## 1. What the system is

**Organiflo** — a multi-tenant organic marketing SaaS. A business connects its
social accounts, and the platform writes captions, generates video-prompt
briefs, schedules posts and publishes them automatically.

| Piece | Detail |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.0 async, asyncpg, APScheduler, Alembic |
| Frontend | React + Vite (no Tailwind — inline styles and `index.css` tokens) |
| Hosting | Backend on Render (single gunicorn worker), frontend on Vercel |
| Database | Neon Postgres |
| Repo | `github.com/vinayaksilswal/organic-marketing-ai`, branch `main`, CI on push |
| State at handoff | commit `e2cc348`, **978 tests passing, 2 skipped**, 61 test files |
| Live | https://organiflo.com · API https://organic-marketing-ai-0abh.onrender.com |

Run the suite with the project venv:
```
./.venv/Scripts/python.exe -m pytest -q
```
It takes 5–9 minutes. Run it in full before every commit.

---

## 2. Read this before you write a line of code

These are not style preferences. Each one is a bug that reached production or
came close, and most have a test guarding them now.

### 2.1 "Works locally" is meaningless here

The local venv has drifted from `requirements.txt` in **19 of 27 pinned
packages**. Most dangerously:

| Package | Pinned (production) | Local |
|---|---|---|
| pydantic | 2.11.5 | 2.13.4 |
| fastapi | 0.115.12 | 0.139.0 |

A real production outage was invisible locally because of exactly this: newer
pydantic resolved an annotation that 2.11.5 could not, so password reset was
broken for every user while every local test passed. **CI is the only
trustworthy signal.** Push and read the CI result before believing anything.

Related: never add `from __future__ import annotations` to `routers/auth.py`.
Combined with the `@limiter.limit` decorator it makes FastAPI resolve the body
model against slowapi's module globals, fail, and silently reclassify the
request body as a **query parameter**. There is a test.

### 2.2 Error messages: never read `body.detail`

`main.py` has a global exception handler that reshapes every `HTTPException`
into `{"success": false, "message": ...}`. So `body.detail` is populated in a
unit test and **undefined in production**. Fifteen call sites had this bug and
showed generic fallbacks instead of the real reason to every real user.

Use the helper: `import { apiError } from '../config'` →
`apiError(body, 'fallback text')`. A test sweeps every `.jsx`/`.js` for
regressions.

### 2.3 Never invent a number

The product's entire pitch is that it does not fabricate figures, and there
are FTC-style claim gates in `prompt_engine`. Do not add:

- engagement counts on previews of unpublished posts
- "Brand score 72 / Social consistency 38" style scores computed from nothing
- estimated reach, predicted followers, or any metric you cannot derive

If you need a number, derive it from data you actually have and **return the
evidence alongside it** so the customer can check. `services/account_insights.py`
`observations()` is the pattern to copy: every reading carries the figure it
came from, and an account without enough data correctly produces nothing.

Tests enforce this in `test_dashboard_is_one_product.py` and
`test_growth_audit`-style checks.

### 2.4 Design tokens

- Colours live in `frontend/src/index.css` (`--primary-color: #6d28d9`,
  `--secondary-color`, `--accent-color`, `--success`, `--error`) and
  `Landing.jsx` defines its own `--violet`.
- **Orange does not exist.** It was never a token — only loose hexes in five
  files, which is why it drifted and made four tools look like four products.
  A test fails if `#f97316`/`#ea580c`/`#fb923c` or their rgba tints appear in
  any `.jsx`.
- **Never put `className="card"` on a dashboard panel.** `.card` is the auth
  screen's login box at `max-width: 480px`. Three dashboard panels wore it and
  sat in a 480px column inside a 1040px page.
- The dashboard is a **light** product. Watch for dark-theme leftovers: white
  text on white cards and near-black text on near-black panels have both
  shipped here. Media thumbnails keep `background: '#000'` on purpose — video
  letterboxes against black.

### 2.5 Platform limits that are design constraints, not footnotes

| Platform | Limit | Consequence |
|---|---|---|
| Meta | 200 API calls/hour per IG account; 100 posts/24h | Batch reads; never one call per post |
| X | **500 posts/month on the free tier, for the whole app** | ~2 active workspaces before you must pay $200/mo |
| YouTube | 1,600 quota units/upload against 10,000/day **for the whole app** | 6 uploads/day total; there is a ceiling in `youtube_service.py` |
| Reddit | — | **Do not build automated posting.** It gets accounts banned permanently. PostShip writes the post, a human submits it. |
| TikTok | — | **Banned in this product.** A test fails if the word appears in shipped code or copy. |

### 2.6 Things that must not regress

- `services/post_protection.py` — never delete a post at or above the view
  floor. A reel with 4k views was destroyed by a caption-text purge before
  this existed. Meta deletes are irreversible.
- Publishing must treat an unconnected platform as **skipped**, not failed.
  Two permanently-red log lines is how a delivery log stops being read.
- Scraped web pages and user text are untrusted: fence them with
  `services/untrusted_text.py` `guarded_block()` before any model sees them.
- Reveal-on-scroll: the class goes on `section > .wrap`, never on `<section>`
  itself. Six landing sections were invisible for a while because of this.

### 2.7 Tests must actually bite

Several tests here passed while the code was broken because they read source
strings rather than running anything. Two habits are expected:

1. **Mutation-test every guard you add.** Reintroduce the bug, watch the test
   fail, restore. A guard that has never failed has never been shown to work.
2. Beware skip conditions that are too broad. One test here skipped the exact
   line it existed to catch because it matched the *word* `message` from an
   unrelated object key.

### 2.8 Environment quirk

Heredocs in this shell collapse `\n` escapes — writing `\\n` inside a Python
heredoc has repeatedly produced real newlines or stray control bytes in the
output file. Prefer the file-writing tools, or `chr(10)`, over heredocs
containing escapes.

---

## 3. What is already built and working

Do not rebuild these.

- **Publishing**: Facebook, Instagram, X, LinkedIn, YouTube via
  `services/multi_publisher.py`. One caption, shaped per platform (X truncates
  on a word boundary at 280; LinkedIn moves hashtags out of the paragraph;
  YouTube gets a 100-char single-line title). Unconnected platforms are
  skipped, not failed.
- **OAuth**: Meta, X (OAuth 1.0a), LinkedIn (OpenID + `w_member_social`),
  YouTube (offline + forced consent for a refresh token). All four have
  connect/callback/disconnect and UI buttons in Workspaces.
- **Scheduler**: one-time posts, recurring rules (weekdays or day-of-month),
  calendar, delivery log — four separate tabs in `SocialScheduler.jsx`.
- **Brand Brain**: `services/brand_intelligence.py` scrapes the customer's
  website and everything generated flows from it.
- **Creative**: Brand Video Studio (first frame + 3-second beat timeline +
  closing CTA card), Faceless Shorts, Viral Validator, PostShip (X/LinkedIn/
  Reddit).
- **Leads**: `services/lead_finder.py` reads comments across connected
  accounts and surfaces buying intent — unanswered price questions first, each
  with the phrase that flagged it. Pattern matching, not a model, on purpose.
- **Insights**: `account_insights.py` reads live from Meta including views,
  and `observations()` turns the numbers into readings with actions.
- **Billing**: plan quotas enforced at the publish path, PayPal one-time
  checkout working.

---

## 4. What is left

### 4.1 Blocked on the owner — you cannot do these

Tell him, do not attempt:

1. **Add API credentials in Render** (X, LinkedIn and YouTube all return 503
   until these exist), and whitelist the callback URLs in each provider's app:
   - `TWITTER_API_KEY`, `TWITTER_API_SECRET` → callback
     `.../api/v1/x/callback`; app permissions must be **Read and Write**
   - `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET` → `.../api/v1/linkedin/callback`;
     add both "Sign In with LinkedIn using OpenID Connect" and "Share on LinkedIn"
   - `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET` → `.../api/v1/youtube/callback`
2. **Enable PayPal Subscriptions** — recurring checkout 502s on missing
   scopes. One-time `/checkout` works.
3. **Run one live $17 payment** end to end. Never done.
4. **Decide pricing.** He charges $17; his own market research says $19–49.
   This is his call and has not been made.
5. **Facebook Page URL** for the landing footer — Page URLs are numeric IDs
   and cannot be derived from the page name.
6. `python scripts/media_sweep.py --apply` — retires dead Cloudinary assets.

### 4.2 Verification nobody has done

**The dashboard has never been visually verified.** Everything in it is
verified by build, tests and code reading only, because those pages are behind
a login. If you can have the owner log in and drive the session, check:
Faceless Shorts end to end, the leads panel, the four scheduler tabs, and the
Viral Validator results panel.

### 4.3 Engineering work outstanding

**a) 17 customer-facing routes still have no interface caller.** This is the
recurring failure mode of this codebase — capability that exists, is tested,
is billed for, and cannot be reached. Audit each and either wire it up or
delete it:

```
GET  /api/public/recent-activity          GET  /api/public/self-promotion
GET  /api/v1/creatives/brand-intelligence GET  /api/v1/creatives/brand-status
GET  /api/v1/creatives/prompt-history     POST /api/v1/chat
POST /api/v1/creatives/auto-generate-now  POST /api/v1/creatives/faceless-autopilot
POST /api/v1/creatives/generate-image     POST /api/v1/creatives/generate-video-campaign
POST /api/v1/creatives/re-analyze         POST /api/v1/ecommerce/sync-catalog
POST /api/v1/marketing/media/dedupe       POST /api/v1/marketing/posts/generate-caption
POST /api/v1/prompt/caption/validate      POST /api/v1/video/add-outro
POST /api/v1/video/generate-prompt
```

Some are called by the worker rather than the browser — check before deleting.
`tests/test_features_are_reachable.py` is the guard; extend its `SOLD_FEATURES`
list as you wire things up.

**`faceless-autopilot` is the most valuable of these**: Faceless Shorts has a
UI now, but the autopilot that runs it on a schedule does not.

**b) Cross-platform content rotation.** The owner asked for this early and it
was never finished: posts should rotate text-only → media → alternating image
and video across platforms. `services/media_rotation.py` already alternates
image and video; text-only posts across platforms is the missing piece.

**c) The repositioning roadmap.** The owner has repeatedly shared a strategy
document proposing Growth Score, Trend Radar, competitor intelligence, Google
Business Profile, an agency dashboard, and UPI AutoPay via Razorpay for Indian
recurring billing.

**Be honest with him about scope.** That document's own roadmap puts these in
Phases 2–4 and it is months of work. He has roughly two weeks of runway. Do
not start a rebuild that leaves nothing shippable. If he wants one thing from
it, the highest-value items that fit the timeline are the pricing change and
an acquisition funnel.

**Note:** a "Free Growth Audit" funnel from that document was built and then
**removed at his request** (commits `77e9fe7`, `593b104`, reverted in
`3adc3d0`). Do not rebuild it unless he asks. `git revert` restores it.

---

## 5. How to work here

- Verify against the live system rather than your own records. Curl production,
  read the deployed bundle, measure contrast in a browser. Several bugs here
  were found that way and would not have been found any other way.
- Run the **full** suite before committing. A targeted green run let a
  `NameError` reach production once.
- When you fix something, add the test that would have caught it, then prove
  it fails without the fix.
- Say plainly what you did not verify. The owner is spending his last runway
  on this; a confident claim that turns out to be untested costs him more than
  an honest gap.
- Commit messages here explain *why*, in prose, including what was wrong
  before. Match that.

---

## 6. First thing to do

Do not start coding. Run this and confirm it matches what this document says:

```
./.venv/Scripts/python.exe -m pytest -q
```

Expect **978 passed, 2 skipped**. If it differs, something changed after this
handoff was written, and you should find out what before trusting anything
above.
