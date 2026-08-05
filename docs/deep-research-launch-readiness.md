# Deep Research Brief — Launch and Commercial Readiness

Companion to `deep-research-prompt.md`, which covers prompt engineering for
video briefs and captions. That subject is largely settled. This brief covers
what now stands between a working platform and a paying stranger: Meta App
Review, unit economics, and the infrastructure ceilings we have measured.

Paste the block below into a deep-research tool (Gemini Deep Research, ChatGPT
Deep Research, Perplexity, Claude with web search).

Every figure in the context was measured against the running system on
5 August 2026, not estimated. Telling the researcher what is already true and
already solved is what stops the output being a list of things we shipped last
week.

---

```
# ROLE

You are advising the solo founder of a live, pre-launch micro-SaaS on what to
do next. Your output is a decision document, not a survey. Assume technical
competence: skip explanations of what an API is, skip generic startup advice,
skip anything that reads like a listicle. Where you cite a policy, quote the
clause and link it. Where you cite a cost, give the 2026 figure and its source.

# THE PRODUCT

Organic Marketing AI — multi-tenant software that runs a small business's
organic social media unattended. The customer connects Facebook and Instagram,
uploads a media library once, and the platform writes captions, chooses what to
post next, brands each clip with a watermark and end card, and publishes on
their chosen interval. Entry tier $17/month.

# THE STACK, EXACTLY

- Backend: FastAPI on Render, ONE gunicorn/uvicorn worker, 512 MB RAM,
  fractional CPU. Python 3.11, SQLAlchemy 2.0 async, asyncpg.
- Database: Neon serverless Postgres, row-level security per workspace.
- Frontend: React/Vite on Vercel.
- Media: Cloudinary. Video processed with ffmpeg IN-PROCESS on the web dyno.
  A single 1080x1920 encode peaks at 308 MB of the 512 MB budget (measured).
- LLM: OpenRouter, FREE-tier models only (Nemotron, Gemma), with a fallback
  chain. They return 429 and 504 frequently.
- Publishing: Meta Graph API — Instagram Content Publishing + Facebook Pages.
- Billing: PayPal subscriptions. Plans $0 / $17 / $49 / $149.
- Scheduling: APScheduler in-process, 15-minute tick, per-workspace interval.

# CURRENT SCALE

7 workspaces, ~6,000 media assets (largest single workspace: 4,400 assets),
5 workspaces publishing automatically, ~40 posts/day in total. One paying
customer: the founder. Not yet publicly launched.

# ALREADY SOLVED — DO NOT RECOMMEND THESE BACK

Multi-tenant authorisation (router-level workspace ownership checks), plan and
quota enforcement on the autonomous publishing path, prompt-injection fencing
of scraped website text, per-workspace media rotation without repeats, the
video branding pipeline, password-reset hardening, scheduler reliability and
per-cycle auditing. All shipped and tested.

# QUESTIONS, IN ORDER OF HOW ACTIONABLE THEY ARE

## 1. Meta App Review — the launch blocker

The Meta app is in Development mode, so only accounts with an explicit app role
can complete Facebook Login. No customer can onboard until it is Live.

- Current 2026 App Review process and realistic calendar timeline for:
  pages_show_list, pages_read_engagement, pages_manage_posts, instagram_basic,
  instagram_content_publish.
- Is Business Verification required before or after review, and what exactly
  does it demand from a SOLE PROPRIETOR IN INDIA with no registered company?
  Name the acceptable documents. This is the largest single unknown.
- Most common rejection reasons for a scheduling/publishing tool specifically.
  What does an approved screencast actually demonstrate, step by step?
- Tech Provider vs. non-Tech-Provider classification: which applies to
  self-serve SaaS whose customers connect their own pages, and what changes?
- If pages publishing through the app host adult-adjacent or AI-generated human
  imagery, what is the risk to THE APP ITSELF during and after review? Does
  Meta assess content published via an app when deciding its standing?

## 2. Escaping the free LLM tier without destroying margin

- Cost per 1,000 captions on realistic 2026 options: Gemini Flash, the GPT-5
  mini/nano tier, Claude Haiku, DeepSeek, Llama via Groq or Together. Give
  current per-token pricing.
- At ~60 posts/customer/month, what is inference cost per customer per month,
  and what gross margin remains on $17?
- Best caption quality per dollar. Cite evaluations of SHORT-FORM MARKETING
  COPY, not general reasoning leaderboards.
- Is prompt caching or request batching materially useful for this workload?

## 3. Video processing at 512 MB

One encode uses 308 MB, in the same process that serves requests. Two
concurrent customers cannot both encode.

- Cheapest 2026 architecture that removes the ceiling: separate Render worker,
  Cloud Run, Fly.io, Modal, or a managed video API (Cloudinary
  transformations, Mux, Shotstack)?
- Total monthly cost at 10, 100 and 500 customers for each option, assuming
  ~60 short vertical videos per customer per month.
- Where is the crossover at which a managed API beats self-hosted ffmpeg?
- Can Cloudinary's own transformation pipeline apply a watermark overlay AND
  append an end card? At what cost per video?

## 4. Instagram publishing limits and account safety

- Current 2026 limits: posts per 24h per account, API call quotas, how they
  scale per app.
- What posting frequency actually triggers reach suppression on a business
  account? Some of our accounts run at 24 posts/day. Is that demonstrably
  harmful? Cite evidence, not folklore.
- Does publishing via API rather than the app affect reach? Real evidence only.
- What happens to an app's standing when accounts under it get restricted?

## 5. Pricing and competitive position

- Feature and 2026 pricing comparison: Buffer, Later, Hootsuite, Metricool,
  Publer, Ocoya, Predis.ai, Postiz, Vista Social. Which are AI-first? Which
  auto-generate captions from an uploaded library?
- Is $17/month positioned correctly for this automation depth?
- Is "upload once, never touch it again" a real wedge, or does the market
  distrust full autonomy? Evidence either way.
- Which segments demonstrably pay: local services, e-commerce, agencies,
  faceless content pages?

## 6. Compliance for a solo operator selling internationally

- Minimum viable setup for an Indian sole proprietor selling SaaS worldwide:
  entity, GST on exported digital services, and PayPal versus a merchant of
  record.
- Does a merchant of record (Paddle, Lemon Squeezy) fully remove EU/UK VAT and
  US sales-tax burden? Total cost versus PayPal?
- GDPR obligations for storing EU customers' social tokens and media. Is a DPA
  required, and with whom?
- What must a privacy policy and terms of service contain to pass Meta App
  Review specifically?

## 7. AI-generated content disclosure

- Meta's 2026 labelling requirements for AI-generated content. Does the
  obligation fall on the publishing app or the account owner?
- Do EU AI Act transparency duties apply to a tool that generates or publishes
  synthetic media, and on what timeline?
- Legal exposure for AI imagery resembling real people under Indian IT Rules,
  the US TAKE IT DOWN Act, and EU rules.

# OUTPUT REQUIRED

1. A RANKED ACTION LIST. For each: what to do, why now, effort, cost, and what
   it unblocks. Rank by revenue impact per unit of FOUNDER TIME — that is the
   scarce resource here, not money.
2. A LAUNCH-BLOCKER SECTION: everything that must be true before a stranger can
   sign up and pay, with realistic calendar time for each.
3. A COST MODEL at 10 / 100 / 500 customers covering infrastructure, inference,
   video processing and payment fees. State gross margin per customer at $17
   and name the first component that breaks.
4. WHAT THIS BRIEF HAS WRONG. Where these assumptions are mistaken or out of
   date, say so directly and show the evidence.

Prefer primary sources: official documentation, current pricing pages, policy
text. Flag anything you could not verify rather than presenting it as settled.
For each recommendation, state what evidence would change your mind.
```
