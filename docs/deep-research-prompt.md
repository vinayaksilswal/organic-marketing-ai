# Deep Research Brief — Prompt Engineering for AI Video Creatives and Social Captions

Paste the block below into a deep-research tool (Gemini Deep Research, ChatGPT
Deep Research, Perplexity, Claude with web search, etc.).

It is written to produce **decision-grade, sourced findings we can encode as
rules**, not a survey of opinions. The specific failures listed under "What we
already know" are real ones observed in this product — telling the researcher
what we have already ruled out is what stops the output being a list of things
we tried in week one.

---

```
# ROLE

You are a research analyst producing an implementation reference for an
engineering team. Your output will be turned directly into system prompts and
automated validation rules in a production SaaS product. Assume the reader is
technical, already fluent in prompt engineering basics, and impatient with
generic advice.

# CONTEXT

We operate a platform that runs organic marketing automatically for small and
mid-size businesses. For each customer it:

1. Reads their website and builds a brand profile (what they sell, audience,
   tone, content themes, primary offer).
2. Writes a **creative brief** used as the prompt for a text-to-video model,
   producing a 10-second vertical (9:16) clip for Instagram Reels, Facebook
   Reels and paid social.
3. Writes the **caption** for the post, informed by the brand profile and by a
   description of the specific asset attached.
4. Publishes to Facebook Pages and Instagram on a schedule.

Volume is high and unattended. Output quality has to hold without a human
editing each piece.

# WHAT WE ALREADY KNOW — DO NOT REPEAT THIS BACK TO US

These are failures we have already diagnosed and fixed. Treat them as the
floor, and research what lies beyond them.

Video briefs:
- Text-to-video models cannot render legible interfaces. Asking for "a
  dashboard showing a compliance score" or "a terminal with a passing build"
  produces smeared pseudo-text every time.
- On-screen text degrades glyph by glyph. Anything beyond roughly four words
  becomes unreadable, so a call-to-action sentence cannot be burned into the
  video.
- Camera moves that change direction mid-shot (a 180° rotation, "then it flips
  to reveal") produce morphing and melted geometry.
- Stacking subjects (a face AND a screen AND hands AND steam AND a keyboard)
  splits fidelity and everything comes out mushy.
- Prompt length past roughly 85-120 words causes the model to silently drop
  elements. Density is the problem, not just word count.

Captions:
- Instructing a model to "use a proven framework (AIDA or PAS)" reliably
  produces abstract LinkedIn thought-leadership that could describe any company
  in the category.
- Handing the model the video's cinematic brief unlabelled makes it paraphrase
  the shot list ("watch the terminal light up, then pan to the export").
- Models drift into reviewer voice ("our team tested…", "solid pick for…") when
  writing about the brand's own product.
- Passing a targetAudience field verbatim leaks it into copy as a label
  ("perfect for entrepreneur parents") instead of addressing the reader.
- Banned-word lists only work if something programmatically checks the output
  and triggers a corrective retry.

# RESEARCH QUESTIONS

## A. Video creative briefs for 8-12 second vertical ads

A1. **Model-specific prompt grammar.** For Veo 3/3.1, Sora, Runway Gen-3/Gen-4,
    Luma Dream Machine, Kling and Pika: what prompt structure does each vendor's
    own documentation specify? Where do they materially disagree? Produce a
    comparison table with the citation for each claim. Flag anything that is
    community folklore rather than documented.

A2. **What renders reliably vs. what fails.** Beyond the failure classes listed
    above, what other categories of instruction are known to fail in current
    text-to-video models? Cover at minimum: hands and fingers, crowds, reflections,
    liquids, brand logos, product labels, text on packaging, rapid motion, animals,
    and continuity of a named subject across a cut. Cite systematic evaluations,
    model cards or vendor guidance where they exist; say plainly where only
    anecdotal evidence exists.

A3. **Negative prompts.** Which models actually support a negative prompt, and
    with what syntax? Where negative prompts are unsupported, what phrasing in the
    positive prompt achieves the same suppression? Is the widely copied
    "-v oversaturated, plastic, artificial" suffix doing anything on the models
    that do not parse it?

A4. **Audio direction.** For models that generate audio (Veo 3 and successors),
    what audio instruction format works, how much of the prompt budget should go
    to it, and does audio direction measurably degrade visual fidelity by
    consuming attention?

A5. **The 10-second ad structure.** What does the evidence say about beat
    structure for very short vertical ads — hook timing, when a brand should
    appear, whether a cut helps or hurts in under 12 seconds? Prioritise Meta's
    own published creative guidance and any peer-reviewed or large-sample
    advertising research over agency blog posts, and label which is which.

A6. **Variation without drift.** How do production systems generate visually
    distinct creatives for the same brand repeatedly without losing brand
    consistency? Cover named techniques (seed control, style anchoring, reference
    images, explicit avoid-lists of previous outputs) with the trade-offs of each.

## B. Captions for Instagram and Facebook

B1. **What the platforms actually reward.** Current, sourced guidance on caption
    length, hook placement, hashtag count and placement, emoji use, line breaks,
    and whether URLs in captions suppress reach. Distinguish Meta's official
    statements from third-party correlational studies, and give the sample size
    and date of any study you cite. Note explicitly where 2023-era advice is now
    outdated.

B2. **Prompting for concreteness.** What prompt techniques reliably stop an LLM
    producing category-generic marketing copy? We want named, testable techniques
    — negative exemplars, self-critique passes, constrained vocabulary, forced
    specificity slots, retrieval of the brand's own language — with evidence about
    which actually work rather than which sound plausible.

B3. **Brand voice at scale.** How do systems keep hundreds of businesses sounding
    like themselves rather than like each other? Compare few-shot exemplars from
    the customer's own writing, structured brand profiles, fine-tuning, and
    retrieval over the customer's site. What are the cost, latency and quality
    trade-offs of each?

B4. **Automated quality gates.** What measurable, computable checks correlate
    with caption quality? We already reject on banned phrases, exhausted openers,
    camera narration, reviewer voice and length. What else can be checked in code
    — readability scores, specificity or entity density, brand-term presence,
    claim detection, near-duplicate detection against previous posts? For each,
    say whether there is evidence it correlates with engagement or whether it is
    merely intuitive.

B5. **Claim safety.** How should an automated system avoid generating unverifiable
    or regulated claims (health, financial, income, efficacy) on behalf of a
    customer whose industry it does not know in advance? What is the regulatory
    exposure of the platform versus the customer for AI-generated claims, in the
    US, EU and UK?

## C. Making this an enterprise-grade capability

C1. **Evaluation.** How do teams actually measure creative-generation quality in
    production? Cover offline evaluation (LLM-as-judge and its known biases, human
    rubrics, inter-rater reliability) and online evaluation (holdout tests, what
    sample size is needed to detect a realistic effect on engagement). Be concrete
    about the statistics — an account posting 60 times a month cannot detect a 5%
    lift, and we need to know what it *can* detect.

C2. **Prompt lifecycle.** What are the established practices for versioning
    prompts, running regression suites against them, and rolling out a change
    safely when the output is subjective? Cite real tooling and real published
    engineering practice, not vendor marketing.

C3. **Model routing and cost.** For a platform running on mixed free and paid
    model tiers, what routing strategies balance quality against cost and rate
    limits? What quality loss is documented when falling back from a frontier
    model to a small open one for copywriting specifically?

C4. **Competitive teardown.** How do Jasper, Copy.ai, AdCreative.ai, Predis.ai,
    Ocoya and Creatify structure their creative generation? What is publicly
    documented about their prompt architecture, their guardrails, and where users
    report they fall short? Identify the gap a competitor could not easily close.

# OUTPUT FORMAT

1. **Executive summary** — the ten findings that would most change how we build
   this, ranked by expected impact.

2. **Video brief specification** — a concrete, copy-ready system prompt structure
   for 10-second vertical ads, with the reasoning and citation behind each rule.
   Include the word budget and where it should be spent.

3. **Caption specification** — the same, for captions.

4. **Automated checks** — a table of programmatic validations we could implement,
   each with: what it detects, how to compute it, and the strength of evidence
   that it matters.

5. **Evaluation plan** — how we would know any of this worked, with realistic
   sample sizes for an account posting 30-300 times a month.

6. **Contradictions and open questions** — where sources disagree, and what we
   would have to test ourselves because no reliable public answer exists.

# STANDARDS

- Cite a source for every factual claim, with its date. Prefer vendor
  documentation, model cards, platform policy pages and peer-reviewed work over
  agency blogs and LinkedIn posts.
- Where the honest answer is "no reliable public evidence exists", say so and
  say what experiment would settle it. Do not fill gaps with plausible-sounding
  advice.
- Mark anything published before 2025 as potentially stale; this field moves
  fast and much of the top-ranking advice describes retired model behaviour.
- Prefer specifics we can encode — word counts, orderings, exact phrasings,
  thresholds — over principles we would have to interpret.
```

---

## Why the brief is shaped this way

**It states what we already fixed.** Without that, a research tool returns the
basics — "be specific", "use negative prompts" — which is where this product was
a week ago. Naming the floor forces the output above it.

**It asks for evidence strength, not just answers.** Most published prompt advice
is untested folklore, and a lot of it describes model behaviour that no longer
exists. Asking the researcher to separate vendor documentation from blog
consensus is what makes the result safe to encode.

**It demands computable checks.** Anything that cannot be checked in code will
drift the moment a model updates. The rules in this codebase that have held are
the ones with a validator behind them.

**It asks what cannot be known.** The honest gaps are worth more than confident
filler, because they tell us what to A/B test rather than what to assume.
