# Which model does what

Audited 2026-08-20 by reading the code. Every path below is a real call site.

## The short answer

**Everything except the support chatbot runs on OpenRouter's free tier today.**
That is a deliberate cost decision, not an architectural one — the primary
model and the whole fallback chain are environment variables, so upgrading is
a restart rather than a deploy.

Nothing in the interface names any of this. See `tests/test_no_provider_leaks.py`.

---

## By feature

| What | Model | File |
|---|---|---|
| Captions, brand analysis, marketing copy | `nvidia/nemotron-3-ultra-550b-a55b:free` | `services/ai_service.py` |
| Video prompt — text | `google/gemma-4-31b-it:free` | `services/video_pipeline_service.py` |
| Video prompt — image understanding | `nvidia/nemotron-nano-12b-v2-vl:free` | `services/video_pipeline_service.py` |
| Bulk media captioning (vision) | `nvidia/nemotron-nano-12b-v2-vl:free` + gemma fallbacks | `services/bulk_ingest.py` |
| Keyframe prompts (first/last frame) | inherits the marketing chain | `services/keyframes.py` |
| Support chatbot | `google/gemini-2.5-flash` — **paid** | `services/chat_agent.py` |
| Image generation | Pollinations.ai — free, no key | `services/creative_service.py` |

## The fallback chain

`services/ai_service.py` does not call one model. A request walks a chain,
falling through on rate limits and 404s:

1. `nvidia/nemotron-3-ultra-550b-a55b:free` — 550B MoE, 1M context
2. `nvidia/nemotron-3-super-120b-a12b:free` — 120B MoE
3. `inclusionai/ling-3.0-flash:free` — 124B MoE
4. `google/gemma-4-31b-it:free`
5. `google/gemma-4-26b-a4b-it:free`
6. `openai/gpt-oss-20b:free`
7. `nvidia/nemotron-3-nano-30b-a3b:free`
8. **Gemini 2.0 Flash direct** — only if `GEMINI_API_KEY` is set

The chain is refreshed hourly from OpenRouter's live catalogue rather than
trusted as written. An earlier hardcoded chain listed four models that had all
been retired, so every fallback returned 404 and only the rate-limited primary
was ever tried — the fallback existed and did nothing.

Models are excluded by slug when they are unsuited to marketing copy: safety
classifiers, code-only, vision-only.

---

## Upgrading

Two environment variables. Neither needs a code change.

```
AI_PRIMARY_MODEL=anthropic/claude-sonnet-4
AI_MODEL_CHAIN=anthropic/claude-sonnet-4,openai/gpt-4o-mini
```

Setting `AI_MODEL_CHAIN` **wins outright and skips the free-catalogue refresh**.
An operator who has paid for specific models does not want a discovery step
quietly appending free ones behind them.

### What upgrading actually buys

The free tier's cost is not correctness, it is **queueing and variance**. Under
load a request falls through several models, so two captions for the same
business can come from a 550B model and a 20B one within a minute of each
other. That inconsistency is visible in the output and it is the single
highest-leverage quality change available to this product.

Order to upgrade in, by how much each is worth per rupee:

1. **Captions and brand analysis** (`AI_PRIMARY_MODEL`) — this is what
   customers read, and what decides whether a post sounds like their business.
2. **Video prompt text** — the brief is long and structured; weaker models drop
   the beat sheet.
3. **Vision** — describing an image is the least demanding job here and the
   free models do it acceptably.

The chatbot already runs on a paid model, because a support answer that is
wrong is worse than no chatbot.
