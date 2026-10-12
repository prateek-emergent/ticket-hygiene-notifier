# Jev (TypeSafe AI "System One" model): every access route, what each costs, and free routes

Research date: 2026-10-07. All prices are as read on that date unless another date is given. "VERIFIED" means the price was read on a primary source (TypeSafe, or the gateway's own page or docs). "SECONDARY" means it comes only from a third-party article. "UNVERIFIED" means no source confirmed it.

## 1. TypeSafe's own API (direct)

### Takeaway
VERIFIED: Jev costs **$0.042 per 1M input tokens ($42 per 1B), and output tokens are free.** The endpoint is `POST https://api.typesafe.ai/v1/systemone` with a Bearer key from console.typesafe.ai. New accounts were reported to get a one-time **$5 free credit** (about 120M tokens). That is SECONDARY: it rests on a TypeSafe X post as reported by explainx.ai. Signup availability has changed back and forth since launch. Published rate limits conflict: 80 req/s in TypeSafe's docs versus 1,200 req/min in a third-party guide.

### Cited Findings
- **Launch:** Jev was announced 2026-09-15 as TypeSafe's first "System One Model". It returns "type-safe structured values" with calibrated probabilities, not text, in 70–500 ms. Early access at launch came through a waitlist. — [TypeSafe blog, 2026-09-15](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- **Price (VERIFIED, read 2026-10-07):** $0.042 per million input tokens. Output tokens are free ("too cheap to meter"). — [TypeSafe blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev); the homepage says "$42 Per Billion input tokens" — [typesafe.ai](https://typesafe.ai/); the models page says "$42 / $0.042" per billion/million input tokens, with no charge for output — [docs.typesafe.ai/models.md](https://docs.typesafe.ai/models.md)
- **Models:** `jev-1.13.0` is the current flagship. `jev-latest` and `jev-preview` are aliases that currently point to the same model. — [TypeSafe Models docs](https://docs.typesafe.ai/models.md)
- **Context:** TypeSafe's docs say 64k tokens per request in total, with a 32k limit on state plus the longest single question. — [TypeSafe Models docs](https://docs.typesafe.ai/models.md)
  - Vercel and OpenRouter list a 32,000-token context instead. — [Vercel model page](https://vercel.com/ai-gateway/models/jev); [OpenRouter Jev guide](https://openrouter.ai/docs/guides/community/jev)
  - Netlify gives "roughly 32,000 tokens — about 150,000 characters" for state and questions combined. — [Netlify changelog](https://www.netlify.com/changelog/typesafe-jev-ai-gateway/)
  - For this workload (≤3k tokens per call) the difference does not matter.
- **Rate limits (conflicting):**
  - TypeSafe docs: "100K tokens per second and 80 requests per second", described as "adjusting dynamically" and subject to change without notice. 80 req/s is 4,800 req/min. — [TypeSafe Models docs](https://docs.typesafe.ai/models.md)
  - Third-party guide (updated 2026-10-01): 250,000 tokens/s and **1,200 requests/min**, which "change without notice while it adds capacity". For higher limits or a custom plan, contact sales. — [flaviocopes.com](https://flaviocopes.com/jev-api-key/)
  - The 1,200 RPM figure is repeated by [opentweet.io](https://opentweet.io/jev/api-access). I did not find it on a TypeSafe page.
- **Auth and errors:** `Authorization: Bearer <API_KEY>`. Error codes: 401 (missing or invalid key), 422 (validation), 429 (rate limit), 529 (overloaded). — [TypeSafe API reference](https://docs.typesafe.ai/api.md)
- **Question types:**
  - `choice` returns `choice`, `probabilities` and `confidence`, with up to 255 options.
  - `score` returns `score`, `legend`, `probabilities` and `confidence`, with 2–10 levels.
  - `noul` returns a 0–1 yes/no probability.
  - All three can be mixed in one call. Each question is evaluated in parallel, in isolation, against the same state.
  - Sources: [TypeSafe docs index](https://docs.typesafe.ai/); [API reference](https://docs.typesafe.ai/api.md)
- **Example request (verbatim from TypeSafe API reference):**
  ```json
  POST https://api.typesafe.ai/v1/systemone
  Authorization: Bearer $TYPESAFE_API_KEY
  {
    "state": "Help! My payouts have been failing for 3 days.",
    "model": "jev-latest",
    "questions": {
      "is_urgent": { "type": "noul", "instructions": "Does this convey urgency?" }
    }
  }
  ```
  **Example response:**
  ```json
  {
    "model": "jev-1.13.0",
    "answers": { "is_urgent": { "type": "noul", "noul": 0.95 } },
    "usage": { "input_tokens": 296, "output_tokens": 20 }
  }
  ```
  The docs also show Choice and Score responses, for example `"choice": "billing", "probabilities": {"billing":0.88,...}, "confidence": 0.81`. — [TypeSafe API reference](https://docs.typesafe.ai/api.md)
- **Python SDK:**
  - Install with `pip install typesafe-sdk` (Python ≥3.10).
  - Call `TypeSafeClient().system_one(state=..., questions={"is_urgent": Noul(instructions=...)})`.
  - The answer is in `response.answers["is_urgent"].noul`.
  - Keys come from console.typesafe.ai/keys, and there is a Playground at console.typesafe.ai/playground.
  - — [TypeSafe Quickstart](https://docs.typesafe.ai/introduction/quickstart.md)
- **Data retention:** "Jev is not trained on customer requests or responses." Zero data retention (ZDR) is available to **enterprise customers** under the DPA. — [TypeSafe Models docs](https://docs.typesafe.ai/models.md)
- **Signup and free credit (SECONDARY, conflicting timeline):**
  - On 2026-09-21 TypeSafe announced "Jev is now available to everyone. No waitlist", via its X post, after about 140k waitlist signups.
  - New accounts got **$5 free credit, which TypeSafe estimated at about 120M tokens**.
  - The article also notes that TypeSafe "has not published a standalone per-token rate card" alongside that claim.
  - — [explainx.ai, 2026-09-21](https://explainx.ai/blog/jev-general-availability-no-waitlist-2026)
  - A later guide (updated 2026-10-01) says new signups were **paused as of 2026-09-24** due to demand. The homepage showed only "Sign in" and "Contact sales", and TypeSafe "wants to reopen access as soon as it can". That guide documents no free credit and no minimum spend. — [flaviocopes.com](https://flaviocopes.com/jev-api-key/)
  - A search-result summary also mentioned a 2026-09-22 pause. — [search summary referencing rootdata.com](https://www.rootdata.com/news/764659) (the page body could not be retrieved)
- **Signup steps:**
  1. Go to console.typesafe.ai.
  2. Sign in with "Continue with Google" or an email code (no password).
  3. Open API Keys and create a key.
  4. Store it in `TYPESAFE_API_KEY`.
  - — [flaviocopes.com](https://flaviocopes.com/jev-api-key/)
- **No free tier on the homepage:** typesafe.ai mentions only "early access" and console sign-in, with no free tier. — [typesafe.ai](https://typesafe.ai/)
- **Opentweet's claims (aggregator):** it says TypeSafe offers "no trial credits or hobby plan across any provider". This contradicts the $5 credit report above. — [opentweet.io](https://opentweet.io/jev/api-access)

### Inferences
- The ~$0.042/M input price with free output is confirmed on three TypeSafe-owned pages.
- Billed input tokens include fixed overhead beyond the visible text. The docs example uses a ~10-word state and one short question, yet reports `input_tokens: 296`. Budget about 250–300 extra tokens per call.
- The $5 credit (≈119M tokens at $0.042/M) is a one-time credit, not a monthly one. Whether a new account can be created today is unclear given the reported pause.

### Gaps
- I found no TypeSafe-hosted pricing page or rate-limit page; docs/llms.txt lists none.
- The $5 credit and the waitlist status are not confirmed on a TypeSafe-owned web page.
- I could not determine whether `output_tokens` (for example, 20 in the example) is truly never billed. All primary sources say output is free.

## 2. Vercel AI Gateway

### Takeaway
VERIFIED: `typesafe-ai/jev` is listed at **$0.042/1M input**, and Vercel adds no markup. Jev is **not** in Vercel's free-tier model set, so Vercel's monthly free credits cannot be used for it. You need purchased AI Gateway Credits. Per-request ZDR is free but only on Pro and Enterprise.

### Cited Findings
- **Launch:** Jev went live on AI Gateway on 2026-09-16 as `typesafe-ai/jev`. It is called with the AI SDK `evaluate` API (AI SDK ≥7.0.105, experimental). Per-request ZDR is set with `providerOptions.gateway: { zeroDataRetention: true }`. Answer types are Choice, Score and Boolean. — [Vercel changelog 2026-09-16](https://vercel.com/changelog/typesafe-ai-jev-now-available-on-ai-gateway)
- **TypeSafe-client and HTTP support (2026-09-21):**
  - A TypeSafe client can point at base URL `https://ai-gateway.vercel.sh/typesafe` with only `baseURL` and `apiKey` changed.
  - The HTTP API is `POST https://ai-gateway.vercel.sh/v1/evaluate` with a Bearer `AI_GATEWAY_API_KEY`.
  - Vercel's schema uses `"type": "boolean"` where native TypeSafe uses `"noul"`.
  - — [Vercel changelog 2026-09-21](https://vercel.com/changelog/ai-gateway-now-supports-typesafe-clients-and-an-http-api-for-jev)
  - Example body: `{"model":"typesafe-ai/jev","state":"...","questions":{"continueWorking":{"type":"boolean","instructions":"Should the agent take another step?"}}}`
- **Not OpenAI-compatible:** Jev is not reached through chat/completions. No OpenAI-compatible route is mentioned. The routes are the AI SDK `evaluate`, `/v1/evaluate` and the native TypeSafe pass-through. — same changelogs as above
- **Model page (VERIFIED, read 2026-10-07):** `typesafe-ai/jev` costs $0.042/1M input tokens, with max output tokens 0 and a 32,000-token context. Providers are **TypeSafe AI and DigitalOcean**. — [Vercel model page](https://vercel.com/ai-gateway/models/jev)
- **No markup:** "AI Gateway charges no markup and no platform fee on tokens". BYOK is also free of markup but needs purchased credits (paid tier). You pay any payment-processing fees. — [Vercel AI Gateway pricing docs, last_updated 2026-09-08](https://vercel.com/docs/ai-gateway/pricing)
- **Free credits:**
  - "The free tier includes a subset of models, not the full catalog". Buying credits moves a team to the paid tier, and "the monthly free credit no longer applies". — [Vercel pricing docs](https://vercel.com/docs/ai-gateway/pricing)
  - The monthly amount, **$5 every 30 days**, appears in search snippets of Vercel docs. It was not shown on the pricing page as fetched today, so treat it as SECONDARY. — [search snippet, vercel.com/docs/ai-gateway/usage-and-pricing](https://vercel.com/docs/ai-gateway/usage-and-pricing)
- **Jev is not a free-tier model:** the free-tier filter lists only free models such as inclusionai/ling-3.1-flash and poolside/laguna-s-2.1-free. Jev shows "$0.04/1M" with no free designation. — [Vercel free-tier model list](https://vercel.com/ai-gateway/models?freeTier=true)
- **ZDR:**
  - Per-request ZDR has no extra cost on Pro and Enterprise.
  - Team-wide ZDR costs $0.10 per 1,000 requests on Pro and Enterprise.
  - Hobby is not listed for either.
  - — [Vercel pricing docs](https://vercel.com/docs/ai-gateway/pricing)
- **Free-tier rate limits:** free-tier requests are rate-limited per model at lower limits than paid, and return 429 when exceeded. — [Vercel pricing docs](https://vercel.com/docs/ai-gateway/pricing)

### Inferences
- Vercel costs the same as TypeSafe direct ($0.042/M) and needs no TypeSafe account, so it works while TypeSafe signups are paused.
- Because Jev is not in the free-tier model set, Hobby free credits cannot legitimately cover Jev calls. A credit top-up is required.
- Team-wide ZDR would add $0.90/month at 300/day and $3.00/month at 1,000/day, which is more than the token cost itself. Per-request ZDR is free on Pro.

### Gaps
- The exact paid-tier rate limits for Jev on Vercel were not retrieved.
- The current $5/month free credit figure was not confirmed on a page fetched today.

## 3. LiteLLM `/typesafe/{path}` pass-through

### Takeaway
LiteLLM is a self-hosted proxy, not a provider. It **still requires your own TypeSafe API key**, set once on the proxy. Clients then use LiteLLM virtual keys. It adds logging and cost tracking at no extra token cost.

### Cited Findings
- **How it works:**
  - Set `TYPESAFE_API_KEY` on the proxy and start `litellm`.
  - Clients replace `https://api.typesafe.ai` with `LITELLM_PROXY_BASE_URL/typesafe` and authenticate with a LiteLLM virtual key.
  - "Any path under /typesafe/ is forwarded", for example `POST /typesafe/v1/systemone` or `GET /typesafe/v1/models`.
  - — [LiteLLM TypeSafe pass-through docs](https://docs.litellm.ai/docs/pass_through/typesafe)
- **Cost tracking:** spend uses `usage.input_tokens` and `usage.output_tokens` and the `typesafe/<model>` registry entry. Spend is logged under the versioned id (`typesafe/jev-1.13.0`) even when the client requests `jev-latest`. — [LiteLLM docs](https://docs.litellm.ai/docs/pass_through/typesafe); [LiteLLM blog 2026-09-20](https://docs.litellm.ai/blog/typesafe_jev)
- **Version (correction to the brief):** LiteLLM's blog (2026-09-20) says the pass-through arrived in **v1.103.0-rc**, not v1.102.x. The pass-through docs page states no version. — [LiteLLM blog](https://docs.litellm.ai/blog/typesafe_jev)
- **Pricing in the LiteLLM registry:** $0.042 per 1M input tokens, with no output charge. — [LiteLLM blog](https://docs.litellm.ai/blog/typesafe_jev)
- **Portkey (similar BYOK gateway):**
  - Routes Jev through `https://api.portkey.ai/v1/decisions` and requires your TypeSafe API key.
  - No streaming; only pre-request guardrails apply to `state`.
  - — [Portkey docs](https://portkey.ai/docs/integrations/llms/typesafe)
- **Pydantic AI Gateway (BYOK, 2026-09-25):**
  - Add a TypeSafe provider in Logfire's Gateway section with your TypeSafe key, then call `https://gateway-us.pydantic.dev/proxy/typesafe/v1/systemone` with the Pydantic gateway key.
  - Price stated as $0.042/M input; no markup is mentioned.
  - Streaming is refused.
  - — [Pydantic article](https://pydantic.dev/articles/jev-pydantic-ai-gateway)

### Inferences
- LiteLLM, Portkey and Pydantic Gateway do not get around the need for a TypeSafe account. If TypeSafe signups are still paused, these routes only help people who already hold a key.

### Gaps
- I did not confirm the v1.103.0-rc claim against the GitHub release notes.

## 4. OpenRouter, Netlify, DigitalOcean, Cloudflare, Together, Fireworks, Groq, Hugging Face, AWS/GCP/Azure

### Takeaway
Jev is confirmed on **OpenRouter** (`typesafe/jev-1.13`), **Netlify AI Gateway**, **DigitalOcean Serverless Inference**, and as a backend provider behind Vercel. Each is priced at $0.042/M input where a price is stated. I found no evidence that Jev is on Together, Fireworks, Groq, Hugging Face Inference Providers, AWS Bedrock, GCP Vertex or Azure Foundry. Jev's weights are closed, so those hosts would need a partnership. Cloudflare hosts its own open-weight, Jev-API-compatible "Clef" models, not Jev itself.

### Cited Findings
- **OpenRouter:**
  - Model ids are `typesafe/jev-1.13` and the alias `~typesafe/jev-latest`.
  - Endpoints are `POST https://openrouter.ai/api/v1/systemone` (TypeSafe-compatible; switch the official SDK by changing its base URL) and `POST https://openrouter.ai/api/alpha/decisions`.
  - "There's no waitlist or separate TypeSafe account."
  - You pay per input token at the model-page price; output is free.
  - Responses include `usage.cost`, and the context is 32k.
  - — [OpenRouter Jev guide](https://openrouter.ai/docs/guides/community/jev)
- **OpenRouter price (SECONDARY):** Jev 1.13 is $0.042/M input with no output charge. — [runtimewire.com](https://runtimewire.com/article/typesafe-jev-router-openrouter-launch). The OpenRouter model page URL `openrouter.ai/typesafe/jev-1.13` returned 404 when fetched, so I could not read the price on OpenRouter directly.
- **"Jev Router" on OpenRouter (listed 2026-09-25):**
  - It is a $0-listed model-selection router built on Jev, which picks *another* model and reasoning effort per request. It is not a way to get Jev's typed yes/no answers for free.
  - The downstream model you are routed to is presumably billed; that is an inference, not stated in the source.
  - — [runtimewire.com](https://runtimewire.com/article/typesafe-jev-router-openrouter-launch); [OpenRouter jev-router](https://openrouter.ai/typesafe/jev-router)
- **Netlify AI Gateway (2026-10-07):**
  - Use `@typesafe-ai/sdk` inside Netlify Functions (Node ≥20). "No API keys to create, no provider config, no base URLs".
  - Usage is "billed to your Netlify credits like every other model in the gateway".
  - — [Netlify changelog](https://www.netlify.com/changelog/typesafe-jev-ai-gateway/)
- **Netlify credits:**
  - Free $0 = 300 credits/month, Personal $9 = 1,000, Pro $20 = 3,000. Pro credit packs cost $10 per 1,500 credits.
  - The pricing page says AI inference "varies based on AI model". — [Netlify pricing](https://www.netlify.com/pricing/)
  - SECONDARY: AI Gateway is metered at **180 Netlify credits per $1 of model spend** on all plans. — [usagepricing.com](https://usagepricing.com/blueprint/netlify)
- **DigitalOcean:** Jev is in Serverless Inference / Model Studio at "$42 per billion input tokens with output tokens free". No free credits or retention terms are stated. — [DigitalOcean changelog](https://ideas.digitalocean.com/changelog/now-available-jev-from-typesafe-ai). DigitalOcean is also listed as a Jev provider on Vercel. — [Vercel model page](https://vercel.com/ai-gateway/models/jev)
- **Runware:** lists `typesafe-jev` as "Compatible Only", with no price shown. — [Runware](https://runware.ai/creators/typesafe-ai)
- **Cloudflare:**
  - Cloudflare does **not** host Jev. Its 2026-10-01 post launched its own **Clef** and **Clef-flash** decision models.
  - They are Apache 2.0, on Hugging Face (huggingface.co/Cloudflare/clef, clef-flash), and "fully Jev-API compatible".
  - Clef has 64k context and is based on Qwen3.8-27B. Clef-flash is based on Qwen3.5-9B with 38.8 ms median latency.
  - Workers AI pricing was not stated.
  - — [Cloudflare blog](https://blog.cloudflare.com/clef-decision-models/)
  - This contradicts [opentweet.io](https://opentweet.io/jev/api-access), which lists a "Cloudflare AI Gateway" route with model `typesafe/jev`. Treat that as unverified.
- **No official weights:** "There are no official open weights". Community clones (SemIf, Kev on Qwen 3.5) and **Ollaya**, a local runner whose `/v1/systemone` endpoint is claimed to be "wire-identical" to TypeSafe's (`TYPESAFE_BASE_URL=http://localhost:11435`), are the local options. — [search summary: pasqualepillitteri.it](https://pasqualepillitteri.it/en/news/17263/typesafe-jev-open-source-clones-free-rtx-3090); [Towards AI](https://pub.towardsai.net/can-you-run-jev-locally-we-checked-520-jev-clients-only-193-switch-to-ollaya-with-one-setting-1d7e48e22e05)

### Inferences
- OpenRouter and Vercel are the routes with no waitlist and no TypeSafe account. Netlify is too, but only inside Netlify Functions.
- "Running Jev locally" is not possible. Only Jev-API-compatible substitutes (Clef, community clones) can run locally, and they are different models with different accuracy.

### Gaps
- I did not check whether OpenRouter adds a fee on credit purchases for Jev, or whether OpenRouter grants free credits for paid models.
- I did not verify Netlify's 180-credits-per-$1 rate on a Netlify-owned page (docs.netlify.com was blocked for fetching).
- For Together, Fireworks, Groq, HF Inference Providers and the AWS/GCP/Azure marketplaces, I only ran a broad search and found no listing. That is absence of evidence, not confirmed absence.

## 5. Free programs, credits, and whether Jev can be used without paying

### Takeaway
I found no startup, academic, open-source or hackathon credit program for Jev. The free routes are:
- **TypeSafe's reported one-time $5 signup credit.** It would cover this workload for months, but signups may be paused.
- **Netlify's Free plan monthly credits.** These may cover the 300/day scenario if the 180-credits/$ rate is right and no other credits are used. Not verified.

Vercel's free credits do **not** apply to Jev.

### Cited Findings
- **TypeSafe:** $5 credit for new accounts, worth about 120M tokens (SECONDARY). — [explainx.ai](https://explainx.ai/blog/jev-general-availability-no-waitlist-2026). Signups were later reported paused. — [flaviocopes.com](https://flaviocopes.com/jev-api-key/)
- **Vercel:** Jev is not in the free-tier model list. — [Vercel free-tier list](https://vercel.com/ai-gateway/models?freeTier=true); [Vercel pricing docs](https://vercel.com/docs/ai-gateway/pricing)
- **Netlify:** the Free plan gets 300 credits/month. — [Netlify pricing](https://www.netlify.com/pricing/). AI Gateway is metered at 180 credits per $1 (SECONDARY). — [usagepricing.com](https://usagepricing.com/blueprint/netlify)
- **Opentweet's claim (aggregator):** "TypeSafe offers no trial credits or hobby plan across any provider". — [opentweet.io](https://opentweet.io/jev/api-access)

### Monthly cost for the workload (computed; 30-day month; $0.042/M input; output free)

| Scenario | Calls/month | Input tokens/month | Cost (text only) | Cost incl. ~300-token overhead/call* |
|---|---|---|---|---|
| 300/day × 1,000 tok | 9,000 | 9M | **$0.38** | $0.49 |
| 300/day × 3,000 tok | 9,000 | 27M | **$1.13** | $1.25 |
| 1,000/day × 1,000 tok | 30,000 | 30M | **$1.26** | $1.64 |
| 1,000/day × 3,000 tok | 30,000 | 90M | **$3.78** | $4.16 |

\*The overhead is inferred from the docs example, where a ~10-word state with one question billed 296 input tokens ([API reference](https://docs.typesafe.ai/api.md)). The real overhead depends on the question instructions.

- **Per call:** $0.000042 at 1k tokens, $0.000126 at 3k tokens.
- **Prices behind the table:** the same $0.042/M on TypeSafe direct, Vercel (no markup), OpenRouter and DigitalOcean.
- **Extras to add:**
  - Vercel team-wide ZDR: +$0.90/month at 300/day, +$3.00/month at 1,000/day. Per-request ZDR on Pro is $0.
  - Payment-processing fees on Vercel top-ups.
  - Netlify meters at 180 credits/$ (SECONDARY), versus a purchase price of 150 credits/$, which makes it about 20% more expensive in effective terms.
- **Rate limits:** 1,000 calls/day averages about 0.7 requests/min, far below any published limit (80 req/s or 1,200 req/min).
- **Coverage from free credit:**
  - **TypeSafe $5 credit (~119M tokens at $0.042/M):** about 13 months at 300/day×1k, 4.4 months at 300/day×3k, 4 months at 1,000/day×1k, 1.3 months at 1,000/day×3k.
  - **Netlify Free (300 credits ÷ 180 ≈ $1.67/month of model spend, if no other credit use):** covers both 300/day scenarios ($0.49–$1.25). It covers 1,000/day only at the low end ($1.64 is borderline) and not at the high end ($4.16).

### Inferences
- In practice, even at the maximum scenario, paid Jev costs under about $5/month. The practical cost floor is the minimum top-up on whichever gateway is used; minimum top-up amounts were not found.
- The only legitimate $0 routes are the one-time TypeSafe credit, if signup is open, and possibly the Netlify Free plan for the 300/day case. The Netlify route has unverified metering and would require running the code in Netlify Functions.

### Gaps
- No TypeSafe startup or academic program was found.
- Minimum credit top-up amounts on Vercel and OpenRouter were not retrieved.
- Whether Netlify's Free plan allows AI Gateway use, and at what rate limits, was not confirmed.
- The current open or paused state of TypeSafe signups as of 2026-10-07 is unconfirmed.
