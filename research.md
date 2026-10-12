# Research: Running Jev locally for free

Research date: 2026-10-07. Prepared for the Trinity ticket-hygiene notifier (this repository), to decide what model should judge rule 1 (does an engineer's reply ask the customer an open question?).

**Question researched.** Can TypeSafe's Jev (https://typesafe.ai/, https://typesafe.ai/blog/introducing-system-one-models-and-jev) be run for free or self-hosted locally instead of paying for the API? If not, what are all the ways to run Jev or a Jev-equivalent, and which suits this project?

**Short answer.** Jev cannot be self-hosted. It is API-only, has no published weights, and TypeSafe's Master Customer Agreement bans distilling or imitating it. The paid API is cheap (about $0.50-$4/month at this volume), but every route sends customer email to a third party. Free local substitutes exist:

- Jev-API-compatible open runtimes and models (Ollaya + Laya on CPU, Cloudflare Clef on GPU).
- Small open LLMs reading Yes/No token probabilities.
- A small encoder fine-tuned on a few hundred hand-labelled replies.

Part 2 has the full comparison and recommendation.

**How it was done.** Five web research tracks ran in parallel and were then synthesized into one report:

- Jev's nature and license
- access routes and pricing
- Jev-compatible open models
- local LLM logprob classification
- encoder classifiers

Caveats:

- Many pages were read through a summarizing fetch tool, so exact numbers should be spot-checked against the linked sources before acting.
- Items marked UNVERIFIED or SECONDARY in the notes come from secondary sources only.
- Nothing was benchmarked on our own data or hardware.

## Contents
- [Part 1: Internal Emergent context on Jev (from Notion)](#part-1-internal-emergent-context-on-jev-from-notion)
- [Part 2: Final report: Replace Cloud-Only Jev With a Local Classifier](#part-2-final-report-replace-cloud-only-jev-with-a-local-classifier)
- [Part 3: Research notes](#part-3-research-notes)
  - [3.1 What Jev is, weights, license and self-hosting](#31-what-jev-is-weights-license-and-self-hosting)
  - [3.2 Every access route to Jev and what it costs](#32-every-access-route-to-jev-and-what-it-costs)
  - [3.3 Jev-API-compatible open models and local runtimes](#33-jev-api-compatible-open-models-and-local-runtimes)
  - [3.4 Local open LLMs with Yes-No logprob classification](#34-local-open-llms-with-yes-no-logprob-classification)
  - [3.5 Small encoder classifiers (zero-shot, SetFit, fine-tuned)](#35-small-encoder-classifiers-zero-shot-setfit-fine-tuned)
- [Part 4: Hands-on test of Ollaya (2026-10-07)](#part-4-hands-on-test-of-ollaya-2026-10-07)

---

## Part 1: Internal Emergent context on Jev (from Notion)

These pages were found in the Emergent Notion workspace before the web research started. They explain why Jev was being considered and what Emergent had already measured. They describe Jev through Emergent's own integrations (Vercel AI Gateway and the Universal Key / LiteLLM route), not running it locally.

### Proposal: Use TypeSafe Jev for Intent Classification (cortex)
Source: https://app.notion.com/p/3df3b3a7b061813ab7c7dc6ceca1d818 (owner Rishabh, dated 2026-09-18, status: proposal; draft PR emergentbase/cortex#3425)

- Proposal: replace the Gemini 3 Flash intent classifier in cortex (about 175k user turns a day) with Jev, starting with a shadow phase.
- Measured on 160 real production turns:

| Metric | Jev | Gemini (production) |
|---|---|---|
| Latency p50 / p95 | 0.86 s / 1.13 s | 2.49 s / 3.40 s |
| Input tokens per call | ~2.8k | ~6k plus 6k cached |
| Cost per call | ~$0.00012 | ~$0.004 |
| Cost per day at 175k calls | ~$22 | ~$700 |
| Errors | 0 of 320 calls | ~15 timeouts per day |

- Agreement with production labels was strong for sentiment and new-bug intent and weak for same-bug. Both classifiers erred there, so a human-labelled gold set was required before any cutover.
- Wording mattered. Jev over-flagged with loose question wording (69 extra flags), and tighter literal criteria cut that to 38 with no loss of true positives. Jev reads instructions literally.
- Risks recorded:
  - **Data.** Customer and agent messages would go to a new vendor through Vercel AI Gateway with per-request zero data retention, and legal had to confirm the Vercel DPA covers this before any traffic, including shadow traffic.
  - **Rate limits.** The published limit was 1,200 requests/min, which can change.
  - **Versioning.** The gateway resolves `typesafe-ai/jev` to the current release, and pinning (e.g. `jev-1.13.0`) works only on TypeSafe's own API.
  - **Keys.** The key was `VERCEL_AI_GATEWAY_KEY`, and a TypeSafe key shared in chat had to be rotated.

### Jev via Universal Key
Source: https://app.notion.com/p/3e33b3a7b061808fbeb3ef4eaf453aaf (edited 2026-09-23)

- Jev covers 3 use-cases: binary categorisation (Noul), multi-label classification (Choice) and numeric scores (Score, a weighted sum of how relevant each option is).
- Planned billing: through the Universal Key, per call, with a maximum spend of $0.40 per free user.
- The main agent should suggest Jev via Universal Key when a user wants AI classification or evaluation of text.

### LiteLLM bump review: v1.96.2 to v1.102.1 (Jev release)
Source: https://app.notion.com/p/3e43b3a7b06181aaa59cd223622ed9fa (dated 2026-09-23)

- LiteLLM was being upgraded because the new version adds the TypeSafe `/typesafe/{path}` pass-through route, which is how Emergent's integration-proxy (Universal Key) reaches Jev.
- Note: the web research (Part 3, access and pricing) found LiteLLM's blog dating this route to v1.103.0-rc (2026-09-20). Check the release notes if it matters.

### Testing-Agent Training Set: Build Runbook (Jev section)
Source: https://app.notion.com/p/3e03b3a7b061810ca3c8e63010a1b257 (dated 2026-09-19)

Jev was validated there against independent Claude Opus extractions:

- `same_defect` (Noul) matched Opus 88% of the time, against 82% for a lexical matcher.
- Self-consistency was 100% (same input twice gave an identical Choice); Score drift was 0.03.
- Sending one request per run instead of one per question cut requests from 810 to 231 and latency from 146 ms to 22 ms per comparison.
- About 300 input tokens per judgement, negligible cost.
- Low confidence did not mean wrong: a 0.48-confidence axis validated perfectly because several levels were plausible.

### Why this matters for the notifier
Rule 1 (moved to PENDING with no open question) is a single yes/no judgement, which is exactly Jev's `noul` question type. The open issue was not fit but cost and data residency, which led to the question this research answers: can Jev, or something equivalent, run locally for free?

---

## Part 2: Final report: Replace Cloud-Only Jev With a Local Classifier

Jev cannot be run for free or self-hosted. TypeSafe ships it only as a hosted API: it has published no weights, offers no on-prem or VPC deployment, and its Master Customer Agreement explicitly forbids reverse engineering it, distilling it, or training a model to imitate its outputs. Paying for it is cheap, though. At $0.042 per million input tokens with free output, even 1,000 calls a day at 3k tokens costs roughly $4 a month on every route (TypeSafe direct, Vercel, OpenRouter, DigitalOcean). So cost is not the real obstacle. Data residency is: every Jev route sends customer email text to a third party, and zero data retention is sold only to enterprise customers. Three families of substitutes keep email in-house. The first is open-weight models that speak the Jev API, such as Cloudflare's Clef and the local runtime Ollaya serving the CPU-friendly Laya model. The second is a small open LLM (Qwen3.5-4B or Gemma 4 E4B, both Apache 2.0) that reads Yes/No token logprobs. The third is a small encoder (ModernBERT or DeBERTa) fine-tuned on a few hundred labelled replies. For a binary "does this reply ask the customer an open question?" check, the recommended path has two steps. Start this week with a zero-shot local Qwen3.5-4B logprob classifier on CPU. Then replace it with a fine-tuned ModernBERT-base classifier that uses a calibrated confidence band and sends uncertain cases back to the local LLM. Label that encoder with human labels, not Jev outputs: training on Jev outputs is precisely what TypeSafe's terms forbid.

### Jev is a closed decision API, and its contract bans cloning it

Jev is the first "System One" model from TypeSafe AI, a San Francisco company. It was announced on 15 September 2026. It does not generate text. A caller sends a `state` and a map of typed questions, and Jev returns calibrated probabilities over the allowed answers in a single parallel pass. There are three question types: **Noul** (a 0–1 yes/no probability), **Choice** and **Score**. TypeSafe claims latency of 70–500 ms ([TypeSafe blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev); [TypeSafe docs](https://docs.typesafe.ai/)). The current model is **`jev-1.13.0`**, served at `POST /v1/systemone`. Context is 64k tokens per request, of which 32k can go to state plus the longest question ([docs: Models](https://docs.typesafe.ai/models.md)). TypeSafe says it is trained with an unpublished technique, "Reinforcement Learning for Calibrated Decisions" (RLCD), on all-synthetic data. It has disclosed no parameter count, no base model and no architecture beyond "a parallel sampler" ([Latent Space](https://www.latent.space/p/jev)). TypeSafe's own documentation of Jev 1.13's weak spots is relevant to this task. It lists literal reading, prompt injection, large irrelevant context and first-option bias in Choice as known weaknesses ([Jev 1.13 jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13.md)).

Every route to "run Jev itself" is closed. The Latent Space interview summary states plainly: **"Open Weights: Not offered. Model access is API-only."** ([Latent Space](https://www.latent.space/p/jev)). TypeSafe's Hugging Face org holds zero models ([HF API](https://huggingface.co/api/models?author=typesafe)). Its GitHub org contains only MIT-licensed HTTP SDKs, integrations and agent skills, with no local inference engine ([github.com/typesafe-ai](https://github.com/typesafe-ai)). The docs index has no deployment, VPC or compliance pages. The only enterprise extras mentioned are higher rate limits and zero data retention (ZDR) through sales ([docs: Legal](https://docs.typesafe.ai/legal.md)). A private deployment might be negotiable, but nothing public suggests it.

The contract matters as much as the technology. The **Master Customer Agreement** grants only "a limited, non-exclusive, non-transferable, non-sublicensable license… to access and use the Services". It prohibits using "the Services or any Output to perform model distillation, train a model to imitate the output of the Services, or develop… a similar or competing product or service" ([TypeSafe MCA](https://typesafe.ai/legal/mca)). For a commercial company this has a concrete consequence. **Any Jev outputs already logged must not become training labels or calibration targets for a local replacement.** On the positive side, TypeSafe commits not to train on customer data without consent ([TypeSafe MCA](https://typesafe.ai/legal/mca)). Note also that the MCA leaves TypeSafe free to delete data at its discretion, but promises no retention period.

### Every paid route costs under $5 a month, but none keeps email in-house

The price is the same everywhere it is published: **$0.042 per million input tokens, with output free** ([docs: Models](https://docs.typesafe.ai/models.md)). Vercel AI Gateway lists `typesafe-ai/jev` at that price and adds no markup ([Vercel model page](https://vercel.com/ai-gateway/models/jev); [Vercel pricing](https://vercel.com/docs/ai-gateway/pricing)). OpenRouter serves `typesafe/jev-1.13` through a TypeSafe-compatible `/api/v1/systemone` endpoint, with "no waitlist or separate TypeSafe account" ([OpenRouter Jev guide](https://openrouter.ai/docs/guides/community/jev)). DigitalOcean Serverless Inference also charges $42 per billion input tokens ([DigitalOcean changelog](https://ideas.digitalocean.com/changelog/now-available-jev-from-typesafe-ai)). Netlify's AI Gateway bills Jev against Netlify credits inside Netlify Functions ([Netlify changelog](https://www.netlify.com/changelog/typesafe-jev-ai-gateway/)). LiteLLM, Portkey and the Pydantic AI Gateway are bring-your-own-key proxies. They add logging and cost tracking but **still require a TypeSafe API key** ([LiteLLM docs](https://docs.litellm.ai/docs/pass_through/typesafe); [Portkey docs](https://portkey.ai/docs/integrations/llms/typesafe); [Pydantic](https://pydantic.dev/articles/jev-pydantic-ai-gateway)). That matters, because new TypeSafe signups were reported paused from 24 September 2026 ([flaviocopes.com](https://flaviocopes.com/jev-api-key/)). The research found no listing on Together, Fireworks, Groq, Bedrock, Vertex or Azure.

Billed input includes fixed overhead. TypeSafe's own example bills a roughly 10-word state as **296 input tokens** ([API reference](https://docs.typesafe.ai/api.md)). Adding about 300 tokens of overhead per call gives the monthly cost of this workload:

| Workload | Calls/month | Monthly Jev cost |
|---|---|---|
| 300/day × 1k tokens | 9,000 | ~$0.49 |
| 300/day × 3k tokens | 9,000 | ~$1.25 |
| 1,000/day × 1k tokens | 30,000 | ~$1.64 |
| 1,000/day × 3k tokens | 30,000 | ~$4.16 |

The free routes are thin and shaky. One report says new accounts received a one-time **$5 credit, about 120M tokens**. That would cover 1.3 to 13 months of this workload, but the claim comes only from secondary reporting of a TypeSafe social post, and signups may still be closed ([explainx.ai](https://explainx.ai/blog/jev-general-availability-no-waitlist-2026)). Vercel's monthly free credits **do not apply**, because Jev is not in Vercel's free-tier model set ([Vercel free-tier list](https://vercel.com/ai-gateway/models?freeTier=true)). Netlify's free plan grants 300 credits a month ([Netlify pricing](https://www.netlify.com/pricing/)). At a secondary-sourced rate of 180 credits per $1 of model spend, that is about $1.67 a month, enough for the 300/day cases only, and only if the code runs inside Netlify Functions ([usagepricing.com](https://usagepricing.com/blueprint/netlify)). The research found no startup or academic program.

The binding constraint is privacy, not money. Every route above ships customer email text to TypeSafe or to a reseller, and several of them (Vercel, DigitalOcean) add a second processor. TypeSafe offers ZDR only to enterprise customers ([docs: Models](https://docs.typesafe.ai/models.md)). Vercel's per-request ZDR flag is free, but only on Pro and Enterprise plans ([Vercel pricing](https://vercel.com/docs/ai-gateway/pricing)). ZDR limits retention. It does not keep the data inside the company's environment.

### Jev-compatible open models exist, but their provenance decides which are safe to use

A cluster of open-weight models and runtimes now copies Jev's request and response shape. Their legal standing depends entirely on how they were trained.

**Cloudflare Clef and Clef-flash** are the strongest clean option. Clef is 27B (from Qwen3.8-27B) and Clef-flash is 9B (from Qwen3.5-9B). Both are **Apache 2.0** and "fully Jev-API compatible". Cloudflare says it trained them on "internal synthetic datasets", and it makes no mention of Jev outputs ([Cloudflare blog](https://blog.cloudflare.com/clef-decision-models/)). Cloudflare's own benchmarks put Clef ahead of Jev on classification (BANKING77 macro-F1 **94.2 vs 79.7**) and behind it on reasoning (MMLU-Pro 65.9 vs 82.7). Median latency is 38.8 ms for Clef-flash against 524.1 ms for Jev ([developersdigest.tech](https://www.developersdigest.tech/blog/cloudflare-clef-decision-models-2026)). These are vendor benchmarks. The model cards were tested on a single H200 and load a separate `joint_head.safetensors` with custom code ([HF Cloudflare/clef](https://huggingface.co/Cloudflare/clef); [HF Cloudflare/clef-flash](https://huggingface.co/Cloudflare/clef-flash)). That makes Clef a GPU-only self-host. The community GGUF quantizations most likely drop the calibrated decision head, though nobody has tested this. Hosted Clef-flash on Workers AI costs $0.090 per million input tokens. Its 10,000 free neurons a day cover roughly 1.2M tokens a day ([Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)), which is most of this workload at no cost. But hosted Clef is still Cloudflare-hosted, so it has the same residency problem as Jev.

**Ollaya** is the closest thing to "Jev on a laptop". It is an Apache-2.0 Rust daemon that serves `/v1/systemone`, `/v1/decisions` and `/v1/models` on `127.0.0.1:11435`, wire-compatible with TypeSafe. Existing Jev clients switch to it by changing `TYPESAFE_BASE_URL` ([GitHub ollaya-dev/ollaya](https://github.com/ollaya-dev/ollaya); [scriptbyai.com](https://www.scriptbyai.com/ollaya-jev-model-local/)). It runs ONNX and GGUF models on CPU, including Windows x64. Its CPU-friendly default is **Laya**, a 421M ModernBERT-large model under Apache 2.0, trained with proper scoring rules. Laya reports **193–464 ms per prediction on CPU**, and typed-decision accuracy of 0.766 against Jev's 0.727 ([HF convaiinnovations/laya](https://huggingface.co/convaiinnovations/laya)). Those are company-published numbers, not controlled tests ([runtimewire.com](https://runtimewire.com/article/ollaya-local-decision-model-runtime)). The Ollaya README does not say whether any library model was trained on Jev outputs, so provenance has to be checked model by model.

Several independent reimplementations are also legally clean. **Open-Jev** (Zefan Cai) has MIT code and Apache-2.0 weights. Its data is CC0 and template-generated, except for the WANLI-derived rows, which are CC BY 4.0. It ships LoRA adapters for Qwen 2B, 9B and 27B, plus its own `/v1/systemone` server. It states explicitly that it "does not reproduce proprietary RLCD, private weights or training data" ([GitHub Open-Jev](https://github.com/Zefan-Cai/Open-Jev); [HF Open-Jev-v1.1](https://huggingface.co/datasets/ZefanCai/Open-Jev-v1.1)). **open-jev-deberta-v3-large** (Apache 2.0, 0.4B, with an ONNX build) was trained only on banking77, SST-5 and BoolQ. It takes 1.8 s on CPU for four questions ([HF card](https://huggingface.co/com-kotobalabs/open-jev-deberta-v3-large)). **Jev-Style-Qwen3.5-2B-Decision-v2** is Apache 2.0, ships as GGUF, and runs on CPU, but its prompt budget is **1,024 tokens**, which would truncate longer emails ([HF v2 card](https://huggingface.co/chaoliangUNSW/Jev-Style-Qwen3.5-2B-Decision-v2)). The tiny **bekko-system-one** encoders currently carry **no license** ("This card does not assign a license"). They also trail Jev on its own benchmark: a noul score of 51.24 against 64.63 ([HF bekko 400m](https://huggingface.co/hotchpotch/bekko-system-one-v0-400m)).

Two groups should be excluded outright. The popular **autotrust JEV-9B / JEV-27B / JEV-27B-VL** family describes itself as a "student of TypeSafe Jev 1.13". It was trained on `SargeDev/jev-distill-corpus-v3`, whose largest stream holds 498,010 rows of Jev output distributions collected via OpenRouter ([HF autotrust/JEV-9B](https://huggingface.co/autotrust/JEV-9B); [HF dataset](https://huggingface.co/datasets/SargeDev/jev-distill-corpus-v3)). These models carry an Apache-2.0 label, and some have downloads in the hundreds of thousands to about 1.5M. Neither fact cures the provenance problem created by the MCA's distillation ban. Separately, the similarly named `openjev/openjev` is **CC-BY-NC-4.0, which bars commercial use**, and should not be confused with Zefan Cai's Open-Jev ([HF search](https://huggingface.co/api/models?search=Open-Jev)).

The last option is TypeSafe's own **`system-one-adapter`** (MIT). It is a drop-in replacement for the SDK's `system_one` call, backed by ordinary LLM APIs, and custom `base_url` endpoints default to Chat Completions ([GitHub](https://github.com/typesafe-ai/system-one-adapter-python)). In principle it could point at a local Ollama server and keep the Noul interface. However, its options (`normalize_probabilities`, `n_retry_malformed_structure`) suggest it asks the LLM to *state* probabilities as JSON. Stated probabilities are the least reliable signal, as the next section explains. TypeSafe also frames the adapter as a comparison tool, not a production path.

### A 4B local LLM reading Yes/No logprobs works from day one

The zero-training way to recreate a Noul locally is to read the model's next-token probabilities. Ask a question whose only possible answers are "Yes" or "No", force a one-token answer, and compute P(Yes) / (P(Yes) + P(No)). The research supports this over asking a model for a confidence number. Verbalized confidence is **sparse**: "Qwen3-32B verbalizes only eight unique confidence values on SST-2, with over half being exactly 95%" ([arXiv 2608.04899](https://arxiv.org/abs/2608.04899)). Raw logprobs carry biases of their own toward majority labels, recent labels and common tokens. **Contextual calibration**, which runs the prompt once with a content-free input such as "N/A" and corrects so that output becomes uniform, yielded up to 30 points of accuracy gain in the original study ([arXiv 2102.09690](https://arxiv.org/abs/2102.09690)). IBM's Granite Guardian 3.3 8B (Apache 2.0) is a production precedent. It accepts custom yes/no criteria and derives its risk probability from yes/no token logprobs ([HF model card](https://huggingface.co/ibm-granite/granite-guardian-3.3-8b)).

The tooling is ready on CPU. **Ollama added logprobs in v0.12.11** (12 November 2025) and named classification as a use case ([Ollama release](https://github.com/ollama/ollama/releases/tag/v0.12.11)). llama.cpp's `llama-server` exposes `n_probs`, GBNF grammars and prompt caching ([llama.cpp server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)). vLLM is the GPU option. It adds `logprob_token_ids` specifically for scoring a small label set, plus `/classify` endpoints for fine-tuned classifiers ([vLLM SamplingParams](https://docs.vllm.ai/en/latest/api/vllm/sampling_params/)). For a commercial stack, the clean model choices are **Qwen3.5 Small** (0.8B–9B, Apache 2.0, March 2026) and **Gemma 4** (E2B/E4B and larger), which moved to **Apache 2.0** in April 2026 ([Gigazine](https://gigazine.net/gsc_news/en/20260303-qwen-3-5-small); [TechWyse](https://www.techwyse.com/news/ai-search/google-deepmind-gemma-4-open-models-apache-2-0-release)). Two practical details matter. First, disable Qwen's "thinking" mode, or the first token will be `<think>` instead of the answer. Second, put the fixed instructions first and the email last, so that prompt caching reuses the shared prefix.

Hardware is the real trade-off, and the work here is dominated by prefill, not generation. 300 calls a day at about 2k tokens is roughly 600k prompt tokens a day, with one output token per call. One unverified report puts a 3B Q4 model at **about 43 tokens/s of prompt processing on an old 4-core i7** ([mgroeber.de](https://www.mgroeber.de/benchmarking-llamacpp-on-legacy-hardware-2.html)). At that rate a 2k-token email takes 45–50 s, which is acceptable for an asynchronous queue that validates a status change. A modern 8–16-core CPU should cut that to seconds, but no verified 2026 benchmark exists, so run `llama-bench` on the target machine. A dedicated GPU server such as Hetzner's GEX44 (RTX 4000 SFF Ada, **€184 a month**) brings per-call latency under a second ([effloow](https://effloow.com/articles/hetzner-cloud-ai-gpu-server-guide-2026)). That is around 40 times the cost of simply paying for Jev, so it is not justified at this volume. The evidence on accuracy is mixed but useful. Small models handle simple zero-shot classification well ([arXiv 2404.11122](https://arxiv.org/html/2404.11122v1)). Open 7–8B models "struggled across non-sentiment tasks", and "training classifiers using high-quality labeled data still gives the best performance" ([arXiv 2502.11830](https://arxiv.org/html/2502.11830v1)). No published study covers small-model calibration on support email, so it has to be measured locally.

### A fine-tuned encoder suits this pragmatic yes/no task best

"Does this reply ask the customer something?" is a speech-act judgement, not a topic, and surface rules handle it poorly. "Is there anything else I can help with?" contains a question but needs no reply. "Please share your job ID." is a request with no question mark. "If it happens again, send us the logs" is a conditional ask, and the team must decide as a policy matter whether it justifies PENDING. Indirect requests are literally questions but work as requests, and how they should be read depends on context ([Trott & Bergen](https://pages.ucsd.edu/%7Ebkbergen/papers/trott_5_8.pdf)). The single biggest cheap gain is preprocessing. In older work, segmenting emails into zones and classifying only the relevant ones raised request-detection accuracy to **83.76%, a 15.9% relative increase** ([Lampert et al., NAACL 2010](https://aclanthology.org/N10-1142/)). Mailgun's `talon` strips quoted replies and signatures ([PyPI talon](https://pypi.org/project/talon/)), so the quoted customer text left in a reply cannot trigger false positives.

Zero-shot NLI classifiers are permissively licensed and run on CPU, but they are a weak fit here. MoritzLaurer's DeBERTa-v3 zeroshot-v2.0 averages 0.676 macro-F1 across tasks. It scores 0.92–0.99 on sentiment but only 0.258 on a complex task, and it truncates input at 512 tokens ([HF card](https://huggingface.co/MoritzLaurer/deberta-v3-large-zeroshot-v2.0)). Fine-tuning changes the picture. Bucher and Martini found that DeBERTa-v3 trained on roughly 200–500 examples beat zero-shot GPT-4 and Claude Opus by wide margins on specialised tasks: stance **0.94 vs 0.51 and 0.57** weighted F1 ([arXiv 2406.08660](https://arxiv.org/html/2406.08660v2)). SetFit is competitive with full fine-tuning using as few as 8 examples per class, and trains in about 30 seconds on a V100 ([HF blog: SetFit](https://huggingface.co/blog/setfit)). **ModernBERT-base** (Apache 2.0, 149M parameters) has an **8,192-token context**, which avoids DeBERTa's truncation problem. It is also the first base-size model to beat DeBERTaV3 on GLUE ([HF blog: ModernBERT](https://huggingface.co/blog/modernbert)). Serving it is trivial at this volume. ONNX Runtime with INT8 quantisation cut a DistilBERT classifier's p95 latency from 75.69 ms to **26.75 ms** on CPU while keeping 99.72% of its accuracy ([philschmid.de](https://www.philschmid.de/static-quantization-optimum)).

Labels are the bottleneck, and their source is where the MCA bites. Using Jev's historical verdicts as training labels would be "train[ing] a model to imitate the output of the Services". Ground truth must therefore come from people, optionally pre-labelled by a self-hosted LLM, which keeps both the data and the legal provenance clean. LLM-labelled data followed by training on clean data is an established pattern. In one study a BERT student reached 0.869 F1 against 0.73 for its GPT-4 teacher, but the authors warn that LLM labels are unstable ([arXiv 2402.09282](https://arxiv.org/html/2402.09282v4)). Once trained, the encoder fits a **cascade**: accept confident predictions, and send the uncertain middle band to a stronger model. Conformal prediction can set that deferral rule with an explicit error-rate guarantee, rather than a hand-tuned threshold ([Conformal Cascade, arXiv 2607.25018](https://www.alphaxiv.org/abs/2607.25018)).

### Compare all options end to end, then run the local cascade

| Option | Monthly cost | Email stays in-house? | Hardware | Jev API drop-in | License / provenance | Expected fit for this task |
|---|---|---|---|---|---|---|
| Jev via TypeSafe / Vercel / OpenRouter / DO | ~$0.50–$4.20 | No (ZDR is enterprise-only or Vercel Pro) | None | Native | Clean, but bound by the MCA | Strong general judge; no local option |
| Jev "free" ($5 credit; Netlify free credits) | $0 for 1–13 months | No | None | Native | Same | Credit unconfirmed; signups possibly paused |
| Clef-flash on Workers AI | ~$0 (free neurons) to ~$5 | No | None | Yes | Apache 2.0, synthetic data | Strong on classification benchmarks |
| Clef / Clef-flash self-hosted | GPU server (~€184) | Yes | H200-class tested; ≥24 GB GPU realistic | Yes | Apache 2.0 | Strong, but overkill and GPU-bound |
| Ollaya + Laya | $0 | Yes | CPU, 193–464 ms | Yes (swap base URL) | Apache 2.0; check each model | Untested on this task; easiest migration |
| Open-Jev 2B/9B, Jev-Style-2B, open-jev-deberta | $0 | Yes | CPU (slow) to small GPU | Partial or wrapper | Apache / CC0 | General-purpose; needs local evaluation |
| autotrust JEV-*, `openjev/openjev` | $0 | Yes | GPU | Yes | **Jev-distilled or non-commercial: avoid** | Not an option |
| Local Qwen3.5-4B / Gemma 4 E4B logprobs | $0 (existing box) | Yes | CPU: seconds to ~50 s per email | Wrapper needed | Apache 2.0 | Good zero-shot baseline after calibration |
| `system-one-adapter` → local LLM | $0 | Yes | As above | Same SDK | MIT | Stated probabilities, so weaker calibration |
| Rules (`?`, imperatives, courtesy lexicon) | $0 | Yes | Any | No | N/A | Low; useful only as features or guardrails |
| Fine-tuned ModernBERT-base / SetFit + LLM fallback | $0 | Yes | CPU, tens of ms | Wrapper needed | Apache / MIT, own labels | Best accuracy and calibration at this volume |

Given the constraints (free, self-hosted, customer email, commercial, MCA), the recommendation is a local cascade built in three steps.

The first step can ship within days. Strip quoted text and signatures with talon. Then score the engineer's own reply with Qwen3.5-4B (Q4_K_M) on Ollama ≥0.12.11 or llama-server, reading Yes/No logprobs with thinking disabled. Apply contextual calibration and a conservative threshold, so that a ticket moves to PENDING only when the evidence is clear. If the pipeline already calls Jev through the TypeSafe SDK, run Ollaya + Laya alongside it as a candidate. It gives a one-variable migration, and both can be scored against the same test set.

The second step is labelling. Collect 300–1,000 historical replies, label them by hand with a written rubric that settles the conditional-ask and "we'll get back to you" cases, and hold out 150–300 as a test set that is never used for training. Use the local LLM's pre-labels to speed this up, but never Jev's.

The third step replaces the LLM as the primary model. Fine-tune ModernBERT-base on those labels, export it to ONNX INT8, and serve it on CPU. Calibrate it with temperature scaling or conformal prediction, and send only the uncertain band to the local LLM. At a few hundred calls a day, even a 20% deferral rate is a few dozen LLM calls.

Paid Jev remains a sensible fallback only if the local stack misses the accuracy bar *and* legal approves sending email to a processor. In that case the right setup is Vercel Pro with per-request ZDR, or a TypeSafe enterprise ZDR agreement. Either costs less than a team lunch per year.

### Conclusion

Asking "can we run Jev for free?" frames the problem wrongly. Jev is already almost free, and it is not available locally at any price. The real choice is between an accurate, nearly free external judge and keeping customer email inside the company's walls. For a single, narrow yes/no decision, the second option gives up little, because fine-tuned small encoders routinely match or beat frontier zero-shot models on specialised labels once a few hundred examples exist. The most expensive input in this project is therefore careful human labelling against a clear PENDING policy, not compute or API fees. That labelled set also becomes the asset that lets the team swap models freely later.

The legal risk sits where engineers are least likely to look. Ecosystem buzz and download counts point toward "Jev-compatible" weights, some of them pulled hundreds of thousands of times, that are explicitly distilled from Jev. A commercial team should treat provenance as a release gate. Clean bases are Apache-licensed models trained on synthetic or public data, such as Qwen3.5, Gemma 4, ModernBERT, Clef, Laya and Open-Jev. Logged Jev outputs must stay out of the training set, while human labels can go in freely. Several key numbers remain unverified and should be measured before committing: CPU prefill speed on the actual hardware, Laya's and Qwen's accuracy on real engineer replies, and whether TypeSafe signups and the $5 credit are currently available.

---

## Part 3: Research notes

The raw notes behind the report, one per research track. They keep every source link, the unknowns per question, and the details the report summarizes.

### 3.1 What Jev is, weights, license and self-hosting

*Source file: `research_notes/Running Jev locally for free/jev_model_and_license.md`*

#### TypeSafe "Jev" (System One model): what it is, weights, license, and whether it can be self-hosted

Research date: 2026-10-07. All pages below were fetched on 2026-10-07 unless noted. The product is new: TypeSafe left stealth and announced Jev on 2026-09-15.

##### 1. What exactly is Jev / a "System One" model?

###### Takeaway
Jev is a proprietary, API-only "decision model" from TypeSafe AI, Inc. (San Francisco). It does not generate text. You send it a `state` and a map of typed questions (Noul, Choice, Score), and it returns calibrated probability distributions over the allowed answers in one parallel pass. TypeSafe describes the training method (RLCD) and a "new architecture with a parallel sampler" only at a high level. It does not disclose the parameter count, the base model (if any), or the internal architecture. The current version is `jev-1.13.0`.

###### Cited Findings
**Identity and positioning**
- TypeSafe calls System One Models "a new class of frontier models built to make fast, structured decisions that software can use directly". Jev is its first public System One model. Blog post by founder Diogo Almeida; the page shows "Sep 15, 2026" as the announcement date and a "Sep 28, 2026" publish/update timestamp. — [TypeSafe blog: Introducing System One Models and Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- Docs: "Jev is TypeSafe's flagship model and the first System One model." It evaluates typed questions against state and returns structured answers "without text generation or parsing." — [TypeSafe docs intro](https://docs.typesafe.ai/) / [llms.txt index](https://docs.typesafe.ai/llms.txt)
- The name "System One" comes from Kahneman's *Thinking, Fast and Slow* (fast, intuitive judgment versus slow System 2 reasoning). — [blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev); [Alura news](https://www.alura.com.br/noticias/empresa-typesafe-ai-sai-do-stealth-e-faz-barulho-com-modelo-jev)
- Company background: founded in 2024 by Diogo Almeida (former OpenAI researcher who worked on InstructGPT, ChatGPT and RLHF), Erik Gafni and Sasha Sheng. It spent about two years in stealth and came out with a **$40M seed round led by DCVC**. — secondary sources: [Alura](https://www.alura.com.br/noticias/empresa-typesafe-ai-sai-do-stealth-e-faz-barulho-com-modelo-jev), [ecosistemastartup](https://ecosistemastartup.com/?p=109311), [Netlify changelog](https://www.netlify.com/changelog/typesafe-jev-ai-gateway/). I did not verify these against a primary press release.
- Legal entity: "TypeSafe AI, Inc., 255 California St, Suite 1300, San Francisco, CA 94117". — [Terms of Use](https://typesafe.ai/legal/terms)

**Technique (only what has been disclosed)**
- Blog: it uses a "new model architecture with a parallel sampler". It is trained with "Reinforcement Learning for Calibrated Decisions (RLCD)". It generates "all outputs in a single query" rather than sequentially. — [blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- On the Latent Space podcast (2026-09-21), the CEO called RLCD a "novel, unpublished technique that optimizes for answers with epistemically honest probabilities". He said training data is "all synthetic", that TypeSafe sees itself as "a data lab rather than a model lab", and that it uses "programs in the loop" rather than human feedback. — [Latent Space: Jev](https://www.latent.space/p/jev)
- Jev "does not decode text autoregressively", so it produces no output tokens and none are billed. — [Netlify changelog](https://www.netlify.com/changelog/typesafe-jev-ai-gateway/)
- Vercel AI Gateway model card lists "Maximum Output Tokens: 0" and "Type: Evaluation model". — [Vercel AI Gateway: typesafe-ai/jev](https://vercel.com/ai-gateway/models/jev)

**Typed outputs**
- There are three primitives. **Choice** ("choose an option from a list") returns `choice`, `probabilities` and `confidence`. **Score** ("score the state on a rubric") returns `score`, `probabilities` and `confidence`. **Noul** ("is this statement true?") returns `noul` in the range 0–1. All three can be mixed in one call and are "evaluated in parallel and in isolation". "Adding questions barely changes the response time." — [docs](https://docs.typesafe.ai/)
- Score is computed as the expected value over levels: "Multiply each level number by its probability, then add the results". Example: 1×0.57 + 2×0.43 = 1.43. Probabilities sum to 1. Confidence (0–1) is "computed from how `probabilities` is spread": a single peak means high confidence. — [docs: Score](https://docs.typesafe.ai/primitives/score.md)
- The CEO describes Noul as a continuous Bernoulli ("noulli") and maps the primitives to programming constructs (if-statements, switch statements). — [Latent Space](https://www.latent.space/p/jev)
- TypeSafe claims type errors are "mathematically impossible" and the hallucination rate on schema matching is 0%, because answers are restricted to the declared options. — [blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev)

**Specifications**
- Current model: `jev-1.13.0`. The aliases `jev-latest` and `jev-preview` both point to it. Endpoint: `POST /v1/systemone`. — [docs: Models](https://docs.typesafe.ai/models.md)
- Context: "64k tokens per request; 32k tokens for `state` plus the longest question". Text input only (string, JSON object or array of text), with no image, audio or video. English is the primary language; other languages, including CJK, work but "not equally well". — [docs: Models](https://docs.typesafe.ai/models.md). Vercel's card says the context window is 32,000 tokens, which probably reflects the state limit. — [Vercel](https://vercel.com/ai-gateway/models/jev)
- Rate limits: "100K tokens per second / 80 requests per second". Limits are "adjusting dynamically", and enterprise plans get higher ones. — [docs: Models](https://docs.typesafe.ai/models.md)
- Pricing: $0.042 per million input tokens ($42 per billion). Output tokens are free. — [docs: Models](https://docs.typesafe.ai/models.md); [homepage](https://typesafe.ai/)
- Latency claims: "70ms–500ms end-to-end", "40x–200x faster than frontier LLMs on System One tasks". The homepage claims "193.6x faster and 444.6x cheaper", with a workflow taking 0.114 s versus 8.566 s. — [blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev); [homepage](https://typesafe.ai/)
- Known weaknesses of jev-1.13 (page last reviewed 2026-10-02): literal reading, math and numbers, date comparison, multi-hop indirection, large irrelevant context, prompt injection, contradictory instructions, first-option bias in Choice, and no text generation. — [docs: Jev 1.13 jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13.md)
- Versioning: the CEO says "We will not change our models when we deploy them" and mentions possible LTS versions. — [Latent Space](https://www.latent.space/p/jev)
- Distribution channels besides TypeSafe's own API: Vercel AI Gateway (providers listed are TypeSafe AI and DigitalOcean) — [Vercel](https://vercel.com/ai-gateway/models/jev); Netlify AI Gateway — [Netlify](https://www.netlify.com/changelog/typesafe-jev-ai-gateway/); OpenRouter, which lists a `typesafe/jev-router` product that "runs on Jev" and links to `~typesafe/jev-latest` — [OpenRouter models API](https://openrouter.ai/api/v1/models); and AIML API — [aimlapi](https://aimlapi.com/models/typesafe-jev-latest).

###### Inferences
- "No autoregressive decoding", "parallel sampler", "0 output tokens" and per-option probabilities all suggest that Jev scores each allowed answer in one forward pass, for example with classification heads or logit readout over a transformer. TypeSafe has not confirmed this, and it is my inference.
- TypeSafe's own claims ("calibrated", "zero hallucinations", the speed multiples) are vendor benchmarks. I found no independent verification.

###### Gaps
- **Parameter count: not disclosed.** It is absent from the blog, the docs, the podcast and the Vercel card.
- **Base model: not disclosed.** I found no statement on whether Jev is a fine-tune of an open model or trained from scratch. The CEO calls RLCD "unpublished".
- **Internal architecture** beyond "new architecture with a parallel sampler": not disclosed. There is no paper or technical report.
- The blog page carries two dates (Sep 15 and Sep 28, 2026). Sep 15 is consistent with the launch reported by third parties.

##### 2. Are Jev's weights published anywhere? Are there SDKs with local inference?

###### Takeaway
No. TypeSafe has not published Jev's weights anywhere. The `typesafe` Hugging Face org exists but holds zero models, and every "Jev" model on Hugging Face is a third-party imitation. TypeSafe's GitHub org contains only MIT-licensed API clients, agent skills, integrations and an LLM-backed adapter. None of them performs local Jev inference.

###### Cited Findings
- The Latent Space summary states: "Open Weights: Not offered. Model access is API-only." — [Latent Space](https://www.latent.space/p/jev)
- Hugging Face API: `author=typesafe` and `author=typesafe-ai` both return `[]` (zero models). `huggingface.co/typesafe` returns HTTP 200 (the org page exists), and `huggingface.co/typesafe-ai` redirects to `/Typesafe-ai`, whose org overview API returns "not found". — Hugging Face API queries, 2026-10-07: [models?author=typesafe](https://huggingface.co/api/models?author=typesafe)
- GitHub org `typesafe-ai` (about 12 public repos) includes:
  - `skills`: agent skills, MIT
  - `system-one-adapter-python`
  - `typesafe-sdk-python`: MIT, updated 2026-09-26
  - `typesafe-sdk-js`: TypeScript, MIT
  - `typesafe-public-examples`
  - `n8n-nodes-typesafe-ai`
  - `WorkflowEvals`: Apache-2.0
  - `daggerverse`, `pulumi-clickhouse`, `typesafe-ai.github.io`

  None of them contains model weights or a local inference engine. — [github.com/typesafe-ai](https://github.com/typesafe-ai)
- PyPI packages `typesafe-sdk` (MIT, author "TypeSafe AI <support@typesafe.ai>") and `system-one-adapter` exist. — [PyPI typesafe-sdk](https://pypi.org/pypi/typesafe-sdk/json), [PyPI system-one-adapter](https://pypi.org/pypi/system-one-adapter/json)
- **`system-one-adapter-python` (official, MIT)** is "a drop-in replacement for `typesafe_sdk`'s `system_one` evaluation API, backed by LLM APIs instead of TypeSafe":
  - Its stated purpose is cost and quality comparison.
  - Install extras: `[openai]`, `[anthropic]`, `[gemini]`.
  - "Custom endpoints (including `OPENAI_BASE_URL`) default to Chat Completions."
  - Answer modes are `"probabilities"` or `"discrete"`.
  - A `normalize_probabilities` option rescales "invalid LLM probability distributions to sum to 1".
  - Caveat: "OpenAI-compatible endpoints may omit token usage."

  — [GitHub: system-one-adapter-python](https://github.com/typesafe-ai/system-one-adapter-python)
- The SDK docs (Python and JS) describe only HTTP clients (`TypeSafeClient`, `AsyncTypeSafeClient`, retries, errors). There is no offline mode. — [docs llms.txt index](https://docs.typesafe.ai/llms.txt)

###### Inferences
- The adapter accepts `base_url`, so it could point at a local OpenAI-compatible server such as Ollama, vLLM or llama.cpp. That would let you keep the TypeSafe SDK interface (Noul, Choice, Score) on a free, local open-weight LLM. The result would be an LLM imitating Jev's interface, not Jev. Its probabilities come from the LLM's stated distributions, with normalization, rather than from calibrated RLCD outputs. The README does not explicitly document local servers; this is my inference from the `base_url` support.

###### Gaps
- I did not read the SDK source code line by line. The conclusion that there is no local inference rests on the README and docs descriptions.

##### 3. License and terms of service (self-hosting, data, distillation)

###### Takeaway
Access is a revocable, limited license to use a hosted service. Nothing in the documents grants rights to weights or self-hosting. The Master Customer Agreement explicitly bans reverse engineering, model distillation, training a model to imitate Jev's outputs, and building competing products. TypeSafe commits not to train on customer inputs. Zero data retention is available to enterprise customers only.

###### Cited Findings
- **Master Customer Agreement** (last updated Sep 23, 2026) — [MCA](https://typesafe.ai/legal/mca):
  - License: "a limited, non-exclusive, non-transferable, non-sublicensable license during the Term to: (a) access and use the Services in accordance with the applicable documentation"
  - Prohibited: "reverse engineer, decompile, disassemble, or attempt to access or derive the source code or underlying data with respect to the Services, including the underlying ideas, algorithms, structure, or organization"
  - Prohibited: "use the Services or any Output to perform model distillation, train a model to imitate the output of the Services, or develop (or to facilitate the development of) a similar or competing product or service"
  - Training: "TypeSafe will not, include Customer Data in a dataset used to train (i.e., to modify the model weights of) any artificial intelligence or machine learning models without Customer's prior consent."
  - Retention: TypeSafe "will be under no obligation to store or retain Customer Data and may delete Customer Data at any time in its sole discretion."
  - Free credits: "Promotional Credits are subject to any additional terms… including… expiration, revocation". I found no permanent free tier.
- **Website Terms of Use** (last updated Sep 19, 2026) grant a personal, revocable license to the Site. They ban reverse engineering "the proprietary software powering any portion of the Site" and ban scraping. — [Terms](https://typesafe.ai/legal/terms)
- **Privacy Policy** (last updated Nov 19, 2025, which predates the launch): "We will not train or fine tune any artificial intelligence or machine learning models on your prompts or other Input." Personal data is retained "as long as reasonably necessary". — [Privacy Policy](https://typesafe.ai/legal/privacy-policy)
- Docs: "Jev is not trained on customer requests or responses". Zero data retention (ZDR) is available for enterprise customers through sales. — [docs: Models](https://docs.typesafe.ai/models.md); [docs: Legal](https://docs.typesafe.ai/legal.md)
- Other legal documents: a [Data Processing Agreement](https://typesafe.ai/legal/data-processing) and an [Acceptable Use Policy](https://typesafe.ai/legal/acceptable-use-policy). I did not read either in full.

###### Inferences
- An MCA customer may not train a local model on Jev outputs. This covers anyone whose purpose is "running Jev locally for free" by distilling it. Third parties that distilled Jev (see section 5) appear to have done what the MCA forbids, if they were bound by it as customers, including through OpenRouter or other gateways, whose own terms may also pass through provider restrictions. Downloading and using their Apache-2.0-labeled weights carries **unclear legal provenance** risk: the uploader's license label may not override TypeSafe's contractual claims against the uploader. Whether TypeSafe has any claim against downstream users is a legal question I cannot settle; it is not legal advice.

###### Gaps
- I did not find the full DPA text or the specific retention periods for API inputs.
- I did not check whether the gateway resellers (Vercel, Netlify, OpenRouter, DigitalOcean) impose TypeSafe's distillation ban through their own terms.

##### 4. On-prem, VPC, bring-your-own-cloud, or air-gapped deployment?

###### Takeaway
I found no evidence of any on-prem, VPC, BYOC or air-gapped offering for Jev. The only enterprise extras documented are higher rate limits, custom plans and ZDR through sales.

###### Cited Findings
- The docs index has no pages on deployment, infrastructure, security or compliance, or enterprise tiers. — [llms.txt](https://docs.typesafe.ai/llms.txt)
- Enterprise mentions are limited to higher rate limits and ZDR ("contact sales"). — [docs: Models](https://docs.typesafe.ai/models.md); [docs: Legal](https://docs.typesafe.ai/legal.md)
- The homepage gives no information on on-prem, VPC or self-hosting. — [typesafe.ai](https://typesafe.ai/)
- The Latent Space interview has "No mention of self-hosting, on-premises, or VPC deployment options". — [Latent Space](https://www.latent.space/p/jev)
- A web search for "TypeSafe Jev enterprise VPC on-prem deployment self-hosted" (2026-10-07) returned nothing relevant.
- The closest thing to third-party hosting: Vercel lists DigitalOcean as a provider. That is still a hosted API, not customer-controlled. — [Vercel](https://vercel.com/ai-gateway/models/jev)

###### Inferences
- A private deployment might be negotiable through enterprise sales, but nothing public says so. Treat Jev as SaaS-only.

###### Gaps
- I did not look for a pricing page, which may not exist, or for direct sales or "contact us" terms on private deployment.

##### 5. Community reproductions, open clones, and papers

###### Takeaway
Within three weeks of launch, Hugging Face filled with unofficial "Jev" models and datasets. Many are LoRA or fine-tunes of open models such as Qwen 3.5 and 3.8, Gemma 4, DeBERTa-v3 and ModernBERT. Some are explicitly **distilled from Jev 1.13's API outputs**, which is legally risky given the MCA. Others are independent reimplementations trained on synthetic or public data, a cleaner basis for a free local "Jev-like" system. No TypeSafe paper exists.

###### Cited Findings
**Distilled from the real Jev (the provenance concern)**
- `autotrust/JEV-9B` (Apache-2.0 label; base Qwen/Qwen3.5-9B; LoRA plus a "dual-head" design; created 2026-09-23; about 313k downloads):
  - Its card calls it the "student of TypeSafe Jev 1.13" and claims System 1 decisions "indistinguishable from the closed TypeSafe Jev 1.13 by KL".
  - Reported metrics: mean KL 0.021; Noul AUROC 0.996; Choice top-1 agreement 0.898 overall and 0.954 on rows where the teacher's top two options differ by at least 0.1.
  - It runs on vLLM, takes about 0.2 s per decision on one GPU, and keeps base-Qwen text generation as a "System 2" path.

  — [HF: autotrust/JEV-9B](https://huggingface.co/autotrust/JEV-9B)
- Siblings: `autotrust/JEV-27B` (base Qwen3.8-27B, same distill dataset), `autotrust/JEV-27B-VL` (about 1.5M downloads), and `autotrust/JEV-Gemma4-26B-A4B`. Third-party quantizations include `Atlas3D/JEV-27B-VL-GGUF`, `-NVFP4` and `prithivMLmods/JEV-27B-VL-GGUF`. — [HF API search "jev"](https://huggingface.co/api/models?search=jev&limit=30)
- Dataset `SargeDev/jev-distill-corpus-v3` (740,957 rows, Apache-2.0 label): its `yuri_v3` stream (498,010 rows) has "Labels distilled from **Jev 1.13** (TypeSafe) via OpenRouter". It was built "for training small local 'System One' judges". — [HF dataset card](https://huggingface.co/datasets/SargeDev/jev-distill-corpus-v3)

**Independent reimplementations (not distilled from Jev outputs)**
- `ZefanCai/Open-Jev` dataset (CC0) and models (`Open-Jev-2B`, `-9B` and `-27B-v1.1`, all Qwen adapters). Code is at [github.com/Zefan-Cai/Open-Jev-Dev](https://github.com/Zefan-Cai/Open-Jev-Dev). The card says: "These are controlled, mostly synthetic tasks and reference labels. They are not official TypeSafe/Jev training data, model predictions… Open-Jev is independently implemented and is not affiliated with TypeSafe." — [HF: ZefanCai/Open-Jev](https://huggingface.co/datasets/ZefanCai/Open-Jev)
- Small and CPU-friendly options:
  - `hotchpotch/bekko-system-one-v0-17m` and `-400m` (ModernBERT cross-encoders with ONNX, "typed-decisions")
  - `com-kotobalabs/open-jev-deberta-v3-large` (trained on banking77, SST-5 and BoolQ; ONNX build at `onnx-community/open-jev-deberta-v3-large-ONNX`)
  - `chaoliangUNSW/Jev-Style-Qwen3.5-2B-Decision` (GGUF and MLX; trained on GLUE, AG News, BoolQ and SST-5)
  - `iapp/OpenThai-SystemOne` (Qwen3.5-0.8B; Ollama tag)
  - `Meanblock/JEV-CPU` (Qwen3-0.6B)

  — [HF API searches "jev", "system-one"](https://huggingface.co/api/models?search=system-one&limit=20)
- Several community benchmarks also exist, for example `JevBench/jevbench`, `SabaPivot/jev-safety-bench` and `autotrust/jev-decision-index-results`. — [HF dataset search "jev"](https://huggingface.co/api/datasets?search=jev&limit=20)

**Papers**
- None from TypeSafe. RLCD is "novel, unpublished". — [Latent Space](https://www.latent.space/p/jev)
- `autotrust/JEV-27B-VL` cites `arxiv:2512.16899` in its tags. I did not check what that paper covers. — [HF API search](https://huggingface.co/api/models?search=jev&limit=30)

###### Inferences
- The general technique can be reproduced with open tools: score each allowed answer in one forward pass using classification heads or constrained logit readout over an open LLM or encoder, then calibrate with temperature scaling on a held-out calibration split. Several clones use exactly this pattern, with "dual-head" designs, calibration splits and ECE/Brier metrics. Jev's specific quality, which comes from RLCD and proprietary synthetic data, is not reproducible from public material.
- For a legally cleaner free local setup, there are two routes: (a) the official MIT `system-one-adapter` pointed at a local open-weight LLM, or (b) independently trained clones such as Open-Jev (CC0 data), the bekko encoders, or the DeBERTa or Jev-Style models trained on public datasets. Avoid models and datasets that are labeled as distilled from Jev 1.13.
- Download counts and the "indistinguishable by KL" claims are self-reported on the model cards and have not been verified independently.

###### Gaps
- I did not verify how good the community clones are beyond their own cards, or the licensing terms of their base models (Qwen 3.5/3.8 and Gemma 4 licenses would govern).
- I found no Hacker News thread or independent evaluation comparing the clones with Jev.
- I did not read the GitHub `Open-Jev-Dev` repository in depth.

### 3.2 Every access route to Jev and what it costs

*Source file: `research_notes/Running Jev locally for free/jev_access_and_pricing.md`*

#### Jev (TypeSafe AI "System One" model): every access route, what each costs, and free routes

Research date: 2026-10-07. All prices are as read on that date unless another date is given. "VERIFIED" means the price was read on a primary source (TypeSafe, or the gateway's own page or docs). "SECONDARY" means it comes only from a third-party article. "UNVERIFIED" means no source confirmed it.

##### 1. TypeSafe's own API (direct)

###### Takeaway
VERIFIED: Jev costs **$0.042 per 1M input tokens ($42 per 1B), and output tokens are free.** The endpoint is `POST https://api.typesafe.ai/v1/systemone` with a Bearer key from console.typesafe.ai. New accounts were reported to get a one-time **$5 free credit** (about 120M tokens). That is SECONDARY: it rests on a TypeSafe X post as reported by explainx.ai. Signup availability has changed back and forth since launch. Published rate limits conflict: 80 req/s in TypeSafe's docs versus 1,200 req/min in a third-party guide.

###### Cited Findings
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

###### Inferences
- The ~$0.042/M input price with free output is confirmed on three TypeSafe-owned pages.
- Billed input tokens include fixed overhead beyond the visible text. The docs example uses a ~10-word state and one short question, yet reports `input_tokens: 296`. Budget about 250–300 extra tokens per call.
- The $5 credit (≈119M tokens at $0.042/M) is a one-time credit, not a monthly one. Whether a new account can be created today is unclear given the reported pause.

###### Gaps
- I found no TypeSafe-hosted pricing page or rate-limit page; docs/llms.txt lists none.
- The $5 credit and the waitlist status are not confirmed on a TypeSafe-owned web page.
- I could not determine whether `output_tokens` (for example, 20 in the example) is truly never billed. All primary sources say output is free.

##### 2. Vercel AI Gateway

###### Takeaway
VERIFIED: `typesafe-ai/jev` is listed at **$0.042/1M input**, and Vercel adds no markup. Jev is **not** in Vercel's free-tier model set, so Vercel's monthly free credits cannot be used for it. You need purchased AI Gateway Credits. Per-request ZDR is free but only on Pro and Enterprise.

###### Cited Findings
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

###### Inferences
- Vercel costs the same as TypeSafe direct ($0.042/M) and needs no TypeSafe account, so it works while TypeSafe signups are paused.
- Because Jev is not in the free-tier model set, Hobby free credits cannot legitimately cover Jev calls. A credit top-up is required.
- Team-wide ZDR would add $0.90/month at 300/day and $3.00/month at 1,000/day, which is more than the token cost itself. Per-request ZDR is free on Pro.

###### Gaps
- The exact paid-tier rate limits for Jev on Vercel were not retrieved.
- The current $5/month free credit figure was not confirmed on a page fetched today.

##### 3. LiteLLM `/typesafe/{path}` pass-through

###### Takeaway
LiteLLM is a self-hosted proxy, not a provider. It **still requires your own TypeSafe API key**, set once on the proxy. Clients then use LiteLLM virtual keys. It adds logging and cost tracking at no extra token cost.

###### Cited Findings
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

###### Inferences
- LiteLLM, Portkey and Pydantic Gateway do not get around the need for a TypeSafe account. If TypeSafe signups are still paused, these routes only help people who already hold a key.

###### Gaps
- I did not confirm the v1.103.0-rc claim against the GitHub release notes.

##### 4. OpenRouter, Netlify, DigitalOcean, Cloudflare, Together, Fireworks, Groq, Hugging Face, AWS/GCP/Azure

###### Takeaway
Jev is confirmed on **OpenRouter** (`typesafe/jev-1.13`), **Netlify AI Gateway**, **DigitalOcean Serverless Inference**, and as a backend provider behind Vercel. Each is priced at $0.042/M input where a price is stated. I found no evidence that Jev is on Together, Fireworks, Groq, Hugging Face Inference Providers, AWS Bedrock, GCP Vertex or Azure Foundry. Jev's weights are closed, so those hosts would need a partnership. Cloudflare hosts its own open-weight, Jev-API-compatible "Clef" models, not Jev itself.

###### Cited Findings
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

###### Inferences
- OpenRouter and Vercel are the routes with no waitlist and no TypeSafe account. Netlify is too, but only inside Netlify Functions.
- "Running Jev locally" is not possible. Only Jev-API-compatible substitutes (Clef, community clones) can run locally, and they are different models with different accuracy.

###### Gaps
- I did not check whether OpenRouter adds a fee on credit purchases for Jev, or whether OpenRouter grants free credits for paid models.
- I did not verify Netlify's 180-credits-per-$1 rate on a Netlify-owned page (docs.netlify.com was blocked for fetching).
- For Together, Fireworks, Groq, HF Inference Providers and the AWS/GCP/Azure marketplaces, I only ran a broad search and found no listing. That is absence of evidence, not confirmed absence.

##### 5. Free programs, credits, and whether Jev can be used without paying

###### Takeaway
I found no startup, academic, open-source or hackathon credit program for Jev. The free routes are:
- **TypeSafe's reported one-time $5 signup credit.** It would cover this workload for months, but signups may be paused.
- **Netlify's Free plan monthly credits.** These may cover the 300/day scenario if the 180-credits/$ rate is right and no other credits are used. Not verified.

Vercel's free credits do **not** apply to Jev.

###### Cited Findings
- **TypeSafe:** $5 credit for new accounts, worth about 120M tokens (SECONDARY). — [explainx.ai](https://explainx.ai/blog/jev-general-availability-no-waitlist-2026). Signups were later reported paused. — [flaviocopes.com](https://flaviocopes.com/jev-api-key/)
- **Vercel:** Jev is not in the free-tier model list. — [Vercel free-tier list](https://vercel.com/ai-gateway/models?freeTier=true); [Vercel pricing docs](https://vercel.com/docs/ai-gateway/pricing)
- **Netlify:** the Free plan gets 300 credits/month. — [Netlify pricing](https://www.netlify.com/pricing/). AI Gateway is metered at 180 credits per $1 (SECONDARY). — [usagepricing.com](https://usagepricing.com/blueprint/netlify)
- **Opentweet's claim (aggregator):** "TypeSafe offers no trial credits or hobby plan across any provider". — [opentweet.io](https://opentweet.io/jev/api-access)

###### Monthly cost for the workload (computed; 30-day month; $0.042/M input; output free)

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

###### Inferences
- In practice, even at the maximum scenario, paid Jev costs under about $5/month. The practical cost floor is the minimum top-up on whichever gateway is used; minimum top-up amounts were not found.
- The only legitimate $0 routes are the one-time TypeSafe credit, if signup is open, and possibly the Netlify Free plan for the 300/day case. The Netlify route has unverified metering and would require running the code in Netlify Functions.

###### Gaps
- No TypeSafe startup or academic program was found.
- Minimum credit top-up amounts on Vercel and OpenRouter were not retrieved.
- Whether Netlify's Free plan allows AI Gateway use, and at what rate limits, was not confirmed.
- The current open or paused state of TypeSafe signups as of 2026-10-07 is unconfirmed.

### 3.3 Jev-API-compatible open models and local runtimes

*Source file: `research_notes/Running Jev locally for free/jev_compatible_open_models.md`*

#### Open-weight, locally runnable Jev "System One"-compatible models and runtimes (as of 2026-10-07)

Context for the report writer: the use case is a binary `noul` classifier ("does the support engineer's reply ask the customer an open question?"), a few hundred calls/day, customer email text must stay in our environment, and free, CPU-friendly options are preferred. Fetches were done on 2026-10-07. Most HF and GitHub facts come from WebFetch summaries of the live pages, so exact numbers should be spot-checked before anyone acts on them. Items marked **UNVERIFIED** could not be confirmed from a primary source.

##### Q0. Reference: Jev System One API shape and the MCA restriction

###### Takeaway
TypeSafe's API is `POST /v1/systemone` with `state`, `model`, and `questions` (a map of typed `noul`/`choice`/`score` questions). It returns `answers` keyed by question id, plus probabilities and confidence. The Master Customer Agreement clause banning use of Jev outputs to train competing models could not be retrieved, so it rests on the brief's statement.

###### Cited Findings
- Request top-level fields are `state` (string/object/array), `model` (e.g. `"jev-latest"`) and `questions` (a map). Question types: `noul` (`instructions`, optional `criteria` true/false), `choice` (`criteria` map of options, up to 255), `score` (ordered `criteria`, 2–10 levels) — [TypeSafe API reference](https://docs.typesafe.ai/api.md)
- The response has `model`, `answers` (keyed by question id) and `usage` (`input_tokens`, `output_tokens`). A noul answer returns `noul` (0–1). A choice answer returns `choice`, `probabilities` and `confidence`. A score answer returns `score` (probability-weighted), `legend`, `probabilities` and `confidence` — [TypeSafe API reference](https://docs.typesafe.ai/api.md)
- The endpoint is `https://api.typesafe.ai/v1/systemone` with Bearer auth. Jev is priced at $0.042/M input tokens and output is free (secondary source) — [digitalstrategy-ai.com, 2026-09-18](https://digitalstrategy-ai.com/2026/09/18/jev-system-one-model)
- TypeSafe says it trains Jev on 100% synthetic data (secondary source) — [llmreference.com](https://www.llmreference.com/provider/typesafe-ai/jev)
- TypeSafe's legal page links a Master Customer Agreement, a DPA and a Privacy Policy. The privacy policy description states "our commitment not to train models on user data" — [docs.typesafe.ai/legal.md](https://docs.typesafe.ai/legal.md)

###### Inferences
- Any local replacement only has to emulate the `noul` answer (one probability) for this use case. Full `choice` and `score` fidelity is not needed.

###### Gaps
- **UNVERIFIED:** the exact MCA clause prohibiting use of Jev outputs to train imitating or competing models. The legal index only links the documents, and `typesafe.ai/legal/master-customer-agreement` returned 404. The clause text, section number and effective date need to come from Legal or the signed contract.

##### Q1. Cloudflare Clef and Clef-flash

###### Takeaway
**Verified.** Cloudflare announced Clef (27B, post-trained from Qwen3.8-27B) and Clef-flash (9B, from Qwen3.5-9B) on 2026-10-01. Both are Apache 2.0 open weights on Hugging Face and are served on Workers AI using the Jev `/v1/systemone` request and response body. Cloudflare says they were trained on its own internal synthetic data, and no source mentions Jev distillation. However, self-hosting is documented on GPU (tested on a single H200), not CPU. Workers AI is hosted, so customer email would leave our environment.

###### Cited Findings
- **Release and authorship:** the Cloudflare blog post "Clef decision models" by Michelle Chen was published on 2026-10-01 — [Cloudflare blog](https://blog.cloudflare.com/clef-decision-models/)
- **Sizes and base models:** Clef is 27B, based on Qwen 3.8-27B. Clef-flash is 9B, based on Qwen 3.5-9B. Both are Apache 2.0 — [Cloudflare blog](https://blog.cloudflare.com/clef-decision-models/); [HF Cloudflare/clef](https://huggingface.co/Cloudflare/clef); [HF Cloudflare/clef-flash](https://huggingface.co/Cloudflare/clef-flash); also [datanorth.ai](https://datanorth.ai/news/cloudflare-releases-clef-and-clef-flash)
- **Training provenance:** the blog says Cloudflare post-trained Qwen with label-smoothed cross-entropy plus a Brier loss and an RL stage ("Reinforcement Learning for Calibrated Decisions", RLCD). It trained on "internal synthetic datasets permutating field orders, prompts, and schema structures". The summary of the blog found no mention of using Jev outputs — [Cloudflare blog](https://blog.cloudflare.com/clef-decision-models/)
- The training data and pipeline are not published, "so it is open weights rather than a fully reproducible open-source release" — [developersdigest.tech](https://www.developersdigest.tech/blog/cloudflare-clef-decision-models-2026)
- **Jev-API compatibility:** the blog calls the models "fully Jev-API compatible", serving the same `POST /v1/systemone` path and body — [Cloudflare blog](https://blog.cloudflare.com/clef-decision-models/); [orcarouter.ai summary](https://www.orcarouter.ai/blog/clef-decision-models-release)
- **HF model card (Clef):**
  - Weights are BF16 safetensors plus a separate `joint_head.safetensors` and a custom `joint_schema_model.py`. Loading uses `load_release_model(path, device="cuda")`, and the card provides a `systemone()` helper that matches the `/v1/systemone` format.
  - It was tested on a single H200 with torch 2.11 and transformers 5.10.2.
  - The card lists vLLM/SGLang/Docker snippets, 20 quantized variants and 5 fine-tunes, and about 7,255 downloads last month — [HF Cloudflare/clef](https://huggingface.co/Cloudflare/clef)
- **HF model card (Clef-flash):**
  - Base is Qwen3.5-9B plus a vision encoder, in BF16 sharded safetensors, tested on a single H200.
  - The page lists vLLM/SGLang (OpenAI-compatible) snippets and about 35 quantizations usable with llama.cpp, Ollama and LM Studio.
  - CPU is not mentioned as supported — [HF Cloudflare/clef-flash](https://huggingface.co/Cloudflare/clef-flash)
- **Workers AI model ids:** `@cf/cloudflare/clef` and `@cf/cloudflare/clef-flash`. Context is 65,536 tokens, with 1–64 questions per request, up to 4 images and a 13 MiB request cap. Clef-flash is described as "a fast 9B multimodal decision model" — [Workers AI: clef-flash](https://developers.cloudflare.com/workers-ai/models/clef-flash/); [developersdigest.tech](https://www.developersdigest.tech/blog/cloudflare-clef-decision-models-2026)
- **Pricing:**
  - Clef is $0.240/M input tokens (21,818 neurons/M). Clef-flash is $0.090/M input tokens (8,182 neurons/M).
  - The free allocation is 10,000 neurons/day on both Free and Paid plans. Overage is $0.011 per 1,000 neurons.
  - Source: [Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)
- **Benchmarks** (Cloudflare-published, vendor-run):

  | Benchmark | Clef | Jev |
  |---|---|---|
  | BANKING77 macro-F1 | 94.2 | 79.7 |
  | CLINC150+OOS macro-F1 | 97.4 | 89.3 |
  | BFCL | 98.5 | 95.8 |
  | GPQA Diamond | 48.0 | 78.3 |
  | MMLU-Pro | 65.9 | 82.7 |

  Median latency: Clef-flash 38.8 ms, Clef 209.3 ms, Jev 524.1 ms. Clef wins on classification, Jev wins on reasoning-heavy evals — [developersdigest.tech](https://www.developersdigest.tech/blog/cloudflare-clef-decision-models-2026); [cryptobriefing.com](https://cryptobriefing.com/cloudflare-clef-decision-models-workers-ai/); [Cloudflare blog](https://blog.cloudflare.com/clef-decision-models/)
- **Context window:** 64k for Clef vs 32k for Jev — [Cloudflare blog](https://blog.cloudflare.com/clef-decision-models/)

###### Inferences
- **Free-allocation math** (from the pricing page figures):
  - 10,000 neurons/day covers about 1.22M input tokens/day on Clef-flash, or about 0.46M/day on Clef.
  - Our workload is about 0.3M tokens/day at the low end (300 calls × 1k), about 1M mid-range (500 × 2k), and 3M at the high end (1,000 × 3k).
  - Clef-flash fits inside the free tier for roughly 300–600 calls/day at 2k tokens, or up to about 1,000 calls/day at about 1.2k tokens.
  - At the worst case of 3M tokens/day, Clef-flash overage is about 14,546 neurons, roughly $0.16/day (about $5/month). Clef at the same volume is about $0.61/day.
  - Whether overage needs the Workers Paid plan was not checked.
- Workers AI is hosted by Cloudflare. Sending customer email there conflicts with the requirement that the text stays in our environment, unless a DPA or approval covers it. The local option is self-hosting the HF weights.
- The 9B Clef-flash in BF16 is about 18 GB of weights (9B × 2 bytes), so it is not realistically CPU-friendly at full precision.
- The listed GGUF quants on HF are community quants of the backbone. Clef uses a separate `joint_head.safetensors` and custom model code, so a plain GGUF in Ollama or llama.cpp probably does **not** reproduce the calibrated decision head or the `/v1/systemone` interface. Treat this as **UNVERIFIED** until it is tested.
- Clef is the cleanest legal option among the strong models: Apache 2.0, a vendor statement of internal synthetic training data, and no Jev distillation claimed. The weakness is GPU-only hosting.

###### Gaps
- Not found in any fetched page: an official statement that Jev outputs were **not** used. Only the absence of any mention and the "internal synthetic datasets" wording were found.
- No official CPU or GGUF guidance and no RAM figures from Cloudflare. It is unknown whether any community GGUF keeps the joint head.
- The blog summary also mentioned "adapted the DiffusionGemma model to output deterministic probabilities", which is inconsistent with the Qwen base. This may be a summarizer artifact; reread the blog to confirm.
- One secondary source (developersdigest) implied Clef-flash has no vision encoder. This is contradicted by the HF card and the Workers AI page, which both say multimodal.
- HF org listing via `huggingface.co/api/models?author=cloudflare` returned `[]` (the org name is "Cloudflare", and the API is case-sensitive). The repo pages themselves resolved.
- No Hacker News thread was checked.

##### Q2. Ollaya (local runner exposing the Jev API shape)

###### Takeaway
**Verified.** Ollaya is an Ollama-style Rust daemon and CLI by Mert Cobanov, licensed Apache-2.0, with about 1.2k GitHub stars. It serves `/v1/systemone`, `/v1/decisions` and `/v1/models` wire-compatible with TypeSafe on `127.0.0.1:11435`. It runs ONNX and GGUF decision models, several of which are small encoders that run on CPU. It is the best fit for "local, free, CPU, same API". The provenance of each model has to be checked separately.

###### Cited Findings
- **Repo and maintainer:** [github.com/ollaya-dev/ollaya](https://github.com/ollaya-dev/ollaya), Apache-2.0, maintained by Mert Cobanov. It is written in Rust and has about 1.2k stars and 71 forks — [GitHub ollaya-dev/ollaya](https://github.com/ollaya-dev/ollaya); [runtimewire.com](https://runtimewire.com/article/ollaya-local-decision-model-runtime)
- **Backends and platforms:** ONNX Runtime (CPU/CUDA) and GGUF via llama.cpp (CPU, Vulkan, CUDA, Metal). It runs on Linux x86_64/arm64 (glibc ≥2.38), macOS on Apple silicon and Windows x64. An NVIDIA GPU (driver R525+) is optional — [GitHub](https://github.com/ollaya-dev/ollaya)
- **API:**
  - Endpoints are `POST /v1/systemone`, `POST /v1/decisions`, `GET /v1/models`, plus native `/api/decide` and `/api/pull`.
  - Its own environment variables are `OLLAYA_HOST`, `OLLAYA_DEVICE`, `OLLAYA_API_KEY` and others.
  - Existing Jev clients work by changing one environment variable (`TYPESAFE_BASE_URL`).
  - Sources: [GitHub](https://github.com/ollaya-dev/ollaya); [scriptbyai.com](https://www.scriptbyai.com/ollaya-jev-model-local/); [alternativeto.net](https://alternativeto.net/software/ollaya/about/)
- **Install:** `curl -fsSL https://ollaya.dev/install.sh | sh`, or on Windows `irm https://ollaya.dev/install.ps1 | iex` — [scriptbyai.com](https://www.scriptbyai.com/ollaya-jev-model-local/)
- **Model library:** the README claims 30+ models. Highlights:

  | Model | Size | Base | License | Notes |
  |---|---|---|---|---|
  | `winnow:e4b` | 4B | Gemma 4 | Apache-2.0 | Recommended start; not CPU-friendly |
  | `laya` | 421M | ModernBERT | Apache-2.0 | CPU |
  | `laya:multilingual` | 322M | mmBERT | Apache-2.0 | CPU |
  | `decider` | 2B | Qwen3.5 | Apache-2.0 | Marginal on CPU |
  | `nli` | large | DeBERTa-v3 | MIT | CPU |
  | `gliclass` | large | DeBERTa-v3 | Apache-2.0 | CPU |

  Kev, Von and Qwen3Guard are also mentioned. Source: [GitHub](https://github.com/ollaya-dev/ollaya); [scriptbyai.com](https://www.scriptbyai.com/ollaya-jev-model-local/)
- The README says the weights come from their authors' Hugging Face repos. It does not explicitly say whether any of them were trained on Jev outputs — [GitHub](https://github.com/ollaya-dev/ollaya)
- **Laya** (ConvAI Innovations):
  - Apache 2.0. ModernBERT-large, 421M (multilingual: mmBERT-base, 322M). Trained with RLCD-style proper scoring rules; the card does not mention Jev outputs.
  - Latency is 193–464 ms per prediction on CPU and 32.8 ms on GPU.
  - Accuracy on typed-decisions is 0.766 (fine-tuned) vs Jev 0.727.
  - Calibration error (ECE) is 0.081 after temperature fitting vs Jev 0.144 raw. This was reported as 0.246 for Jev in the runtimewire article.
  - Source: [HF convaiinnovations/laya](https://huggingface.co/convaiinnovations/laya); [runtimewire.com](https://runtimewire.com/article/ollaya-local-decision-model-runtime)
- **Benchmark claim:** `winnow:e4b` scores 0.722 on typed-decisions vs Jev 0.738 — [GitHub](https://github.com/ollaya-dev/ollaya)
- **Caveats:**
  - "API compatibility does not make an Ollaya model equivalent to Jev."
  - Context varies by checkpoint, and the daemon returns `422 STATE_TRUNCATED` when input is too long — [scriptbyai.com](https://www.scriptbyai.com/ollaya-jev-model-local/)
  - The quality figures are "company-published" and not controlled tests — [runtimewire.com](https://runtimewire.com/article/ollaya-local-decision-model-runtime)

###### Inferences
- For our use case, `ollaya run laya` on CPU behind `/v1/systemone` is the most direct free, local, Jev-shaped path.
- Laya's 193–464 ms per call on CPU is fine for a few hundred calls/day.
- Laya's context limit (ModernBERT is about 8k tokens) should cover 1–3k-token emails. This is not confirmed from the card.

###### Gaps
- Not found: Ollaya release date or version history.
- Not found: a per-model provenance audit of the whole library (for example Kev, Von, `decider` by Mapika, `winnow`). Each model needs checking for Jev-distilled training before production use.
- It is unknown whether Ollaya packages Clef, Open-Jev or bekko.

##### Q3. ZefanCai Open-Jev (CC0 data, Qwen adapters 2B/9B/27B)

###### Takeaway
**Mostly verified.** Open-Jev is an independent reimplementation by Zefan Cai. The code is MIT, the weights are Apache-2.0, and the data is CC0 except for WANLI-derived rows, which stay CC BY 4.0. The data is mainly template- and procedurally-generated, and the project states it does not reproduce TypeSafe's weights or data. It ships rank-8 LoRA adapters plus a scalar head on Qwen bases (Apache-2.0). It includes its own `/v1/systemone` server, but the setup is Python/GPU-oriented.

###### Cited Findings
- **Independence:** "Open-Jev is an independent implementation inspired by TypeSafe's Jev. It does not reproduce proprietary RLCD, private weights or training data." The GitHub summary found no statement that Jev API outputs were used — [GitHub Zefan-Cai/Open-Jev](https://github.com/Zefan-Cai/Open-Jev)
- **Data (v1.1):** 51,200 original controlled decision records across eight authored domains (support, IR, contracts, RAG, browser tools, shell history, games, rubric judging). It also has 101,207 WANLI-derived NLI records, mapped to a typed Choice. Totals: 326,619 records and 147,139 training rows, 89.8 MB. "Original generated Open-Jev content is dedicated under CC0 1.0"; WANLI rows stay CC BY 4.0 — [HF dataset ZefanCai/Open-Jev-v1.1](https://huggingface.co/datasets/ZefanCai/Open-Jev-v1.1)
- **Generation method:** templates and procedural generation dominate rather than LLM synthesis (customer case generators, game episodes, workflow forms, and so on) — [GitHub](https://github.com/Zefan-Cai/Open-Jev)
- **Licenses:** code MIT, data CC0-1.0 (WANLI CC BY 4.0), weights Apache-2.0. The Qwen base revisions are pinned — [GitHub](https://github.com/Zefan-Cai/Open-Jev)
- **Models:**
  - Open-Jev-2B (Qwen/Qwen3.5-2B), Open-Jev-9B (Qwen/Qwen3.5-9B) and Open-Jev-27B-v1.1. All are LoRA rank 8 plus a scalar head plus calibration, and the loader fetches the Qwen base separately.
  - HF repos are `ZefanCai/Open-Jev-2B` and `ZefanCai/Open-Jev-9B` (created 2026-09-20) and `ZefanCai/Open-Jev-27B-v1.1` (created 2026-09-22). All are Apache-2.0 and showed 0 downloads in the API listing.
  - Sources: [GitHub](https://github.com/Zefan-Cai/Open-Jev); [HF API search](https://huggingface.co/api/models?search=Open-Jev)
- **Running it:**
  - Server command is `python -m jev.server --checkpoint ...` and exposes `/v1/systemone` with partial TypeSafe compatibility.
  - Needs Python 3.10+. NVIDIA CUDA is primary; CPU and MPS variants are documented. Docker images are available.
  - Examples cite H100, H200, RTX 4060 Ti and RTX 5060 Ti.
  - Source: [GitHub](https://github.com/Zefan-Cai/Open-Jev)
- **Benchmarks** (self-reported):
  - On the 231-task JevBench Public, Open-Jev-27B v1.1 scores 197/231 (85.28%) vs Jev 194/231.
  - Median latency for Open-Jev-2B over HTTP is 85 ms vs Jev 295 ms (customer-service case). At 1,024 tokens with 32 candidates it is 1,016 ms vs Jev 301 ms. The project notes that hardware and network paths differ.
  - Source: [GitHub](https://github.com/Zefan-Cai/Open-Jev)

###### Inferences
- Legally, Open-Jev looks clean: independently generated CC0 data and Apache-2.0 Qwen bases.
- The WANLI subset carries CC BY 4.0 attribution obligations.
- Open-Jev-2B on CPU is possible but slow for long states. Expect a second or more per 2k-token email (inferred from the GPU latency figures).
- The distilled clone corpus `SargeDev/jev-distill-corpus-v3` includes 94,801 Open-Jev rows (see Q6). The flow is Open-Jev data into the clone, not the reverse.

###### Gaps
- **Conflicting base for the 27B:** the GitHub summary says Qwen/Qwen3.5-27B, while the HF API tags show Qwen/Qwen3.8-27B. Needs checking on the model card.
- No GGUF or ONNX export from the author was found. Open-Jev cannot run in Ollama out of the box, because the LoRA plus scalar head needs the project's own loader.
- **Data-provenance mismatch:** one tool summary of the dataset card claimed "data appears synthetically generated via TypeSafe/Jev systems". That was the summarizer's inference, not a quote, and the GitHub README contradicts it. A human should read the dataset card's provenance section directly.
- **Name clash:** a different repo, `openjev/openjev` (and its GGUF/MLX/FP8 variants, plus `ggml-org/OpenJev-GGUF`), is **CC-BY-NC-4.0, so not for commercial use**. It must not be confused with ZefanCai Open-Jev — [HF API search](https://huggingface.co/api/models?search=Open-Jev)

##### Q4. Small and CPU-oriented models: bekko-system-one, open-jev-deberta-v3-large, Jev-Style-Qwen3.5-2B

###### Takeaway
All three appear to be trained on public NLP datasets with no Jev distillation documented, and all are CPU-capable.
- **bekko-system-one** (17M/68M/400M, ONNX) has **no license yet**, so it cannot be used commercially today. It also scores well below Jev.
- **open-jev-deberta-v3-large** (Kotoba Labs/Mithril) is Apache-2.0, 0.4B, CPU-runnable, with an ONNX build.
- **Jev-Style-Qwen3.5-2B** (chaoliangUNSW) is Apache-2.0 with GGUF builds and CPU support.

None of the three exposes `/v1/systemone` natively, so each needs a thin wrapper or Ollaya.

###### Cited Findings

**hotchpotch/bekko-system-one (v0)**
- Repos `-v0-17m`, `-v0-68m` and `-v0-400m` were created on 2026-09-29, with 0 downloads at the time of the fetch — [HF API search](https://huggingface.co/api/models?search=bekko)
- **License:** "The released-weight and bundled inference-code license declaration remains to be finalized. This card does not assign a license." — [HF bekko-system-one-v0-17m](https://huggingface.co/hotchpotch/bekko-system-one-v0-17m); [HF 400m](https://huggingface.co/hotchpotch/bekko-system-one-v0-400m)
- **Bases:** the cross-encoder/ettin-reranker-17m-v1 and -400m-v1 rerankers, ModernBERT-compatible, with task heads for noul, choice and score.
  - The 17M model has about 4M active parameters and a ~29 MB ONNX file.
  - The 68M model has a ~196 MB ONNX file.
  - The 400M model has 395M parameters (343M active) and a 1.43 GB ONNX file with INT8 embeddings only.
  - Sources: [HF 17m](https://huggingface.co/hotchpotch/bekko-system-one-v0-17m); [HF 400m](https://huggingface.co/hotchpotch/bekko-system-one-v0-400m)
- **Training data:** bekko-system-one-dataset-v0, with 153 subsets and about 6.59M cases converted from NLP and retrieval datasets. No Jev or TypeSafe outputs are documented. The evaluation benchmark (S1MB) used synthetic labels authored with a third-party LLM ("GPT-6-Astra") — [HF 400m](https://huggingface.co/hotchpotch/bekko-system-one-v0-400m)
- **S1MB scores vs Jev 1.13** (task average): 400M 50.60 vs 59.59 (noul 51.24 vs 64.63); 17M 27.57. On the synthetic generalization set, 400M scores 54.48 vs Jev 96.27. English only — [HF 400m](https://huggingface.co/hotchpotch/bekko-system-one-v0-400m); [HF 17m](https://huggingface.co/hotchpotch/bekko-system-one-v0-17m)
- **Latency:** 17M at 1.38 ms single-request (compiled SDPA); 400M at 5.03 ms on an RTX 5090 — [HF cards as above]
- **API:** `BekkoSentenceTransformer.predict()`. It is not `/v1/systemone`-compatible — [HF 400m](https://huggingface.co/hotchpotch/bekko-system-one-v0-400m)

**com-kotobalabs/open-jev-deberta-v3-large**
- Published by Mithril (formerly Kotoba Cloud) / Kotoba Labs Inc. It is Apache 2.0, based on microsoft/deberta-v3-large (MIT), about 0.4B parameters, and was created on 2026-09-18 — [HF card](https://huggingface.co/com-kotobalabs/open-jev-deberta-v3-large); [HF API](https://huggingface.co/api/models?search=Open-Jev)
- **Training data:** mteb/banking77, SetFit/sst5 and google/boolq, totalling 18,000 states and 42,000 questions over 1 epoch, in about 229 s on one H100. It describes itself as an independent reproduction of the Jev shape, "not affiliated with TypeSafe", and says "its numbers are not comparable to theirs". No Jev comparison is given — [HF card](https://huggingface.co/com-kotobalabs/open-jev-deberta-v3-large)
- **Output types:** choice (≤255 options), score (2–10 levels) and noul. CPU fp32 on an M1 Max takes 1.8 s for 4 questions — [HF card](https://huggingface.co/com-kotobalabs/open-jev-deberta-v3-large)
- **ONNX build:** `onnx-community/open-jev-deberta-v3-large-ONNX`, Apache-2.0, created 2026-09-20 — [HF API](https://huggingface.co/api/models?search=Open-Jev)

**chaoliangUNSW/Jev-Style-Qwen3.5-2B-Decision (v1, v2)**
- By Yan Chao Liang (chaoliangUNSW). Apache-2.0, based on Qwen/Qwen3.5-2B-Base.
  - v1 tags list nyu-mll/glue, ag_news, google/boolq and SetFit/sst5. v1 GGUF and MLX were created on 2026-09-21. The v1 GGUF had about 10,364 downloads.
  - v2 and its GGUF/MLX were created on 2026-09-23.
  - Sources: [HF API search](https://huggingface.co/api/models?search=Jev-Style-Qwen3.5-2B); [HF v2 card](https://huggingface.co/chaoliangUNSW/Jev-Style-Qwen3.5-2B-Decision-v2)
- **v2 training data:** a 60k-record pool (replay of the original tasks plus emotion, email filtering, typed workflow decisions and programmatic threshold rules). "Training data retain their original source licenses." No proprietary-LLM labels or distillation are mentioned — [HF v2 card](https://huggingface.co/chaoliangUNSW/Jev-Style-Qwen3.5-2B-Decision-v2)
- **Mechanism:** one prefill produces one logit per option (2–26 options), then calibration is applied and the scores are normalized into probabilities — [HF v2 card](https://huggingface.co/chaoliangUNSW/Jev-Style-Qwen3.5-2B-Decision-v2)
- **Running it:**
  - CPU via `jev_h100.decide --model . --device cpu`.
  - GGUF in Q4_K_M, Q8_0 and BF16, from 1.27 to 3.78 GB.
  - The prompt budget is 1,024 tokens.
  - No `/v1/systemone` endpoint.
  - Source: [HF v2 card](https://huggingface.co/chaoliangUNSW/Jev-Style-Qwen3.5-2B-Decision-v2)
- **Quality:** 81.20% macro accuracy on its English reference panel, vs 76.68% for v1 and 75.09% for English Laya. No direct comparison with Jev is given — [HF v2 card](https://huggingface.co/chaoliangUNSW/Jev-Style-Qwen3.5-2B-Decision-v2)

###### Inferences
- **bekko:** not usable commercially until a license is assigned. Good to watch because the 17M/68M models are tiny on CPU.
- **open-jev-deberta-v3-large:** the most "boring and safe" CPU option. It is fine-tuned only on public datasets, and an ONNX build exists. Its training domain (banking intents, sentiment, BoolQ) is far from "does this reply ask an open question", so expect to fine-tune or calibrate on our own labeled emails.
- **Jev-Style-2B:** its 1,024-token prompt budget may truncate 1–3k-token emails, so input would need trimming (for example, only the engineer's reply, without quoted history).

###### Gaps
- bekko CPU-specific latency: whether the 1.38 ms figure is CPU or GPU is unclear on the card.
- The licenses of the upstream training datasets for deberta and Jev-Style (for example, BoolQ's license) were not checked.
- It is unknown whether Ollaya packages any of these three models.

##### Q5. TypeSafe's system-one-adapter-python

###### Takeaway
**Partly verified.** It is an official TypeSafe Python package (`pip install 'system-one-adapter[openai]'`) that answers System One-style questions using ordinary LLM providers. It accepts a custom `base_url`, and custom endpoints default to Chat Completions, so Ollama, vLLM or llama.cpp servers should work. Its stated purpose is comparing TypeSafe against LLMs on cost, speed and intelligence, not production use. How it derives probabilities is not documented in the README.

###### Cited Findings
- **Repo:** [github.com/typesafe-ai/system-one-adapter-python](https://github.com/typesafe-ai/system-one-adapter-python). The repo summary reports an MIT license, but the README fetch found no license text — [GitHub](https://github.com/typesafe-ai/system-one-adapter-python); [README raw](https://raw.githubusercontent.com/typesafe-ai/system-one-adapter-python/main/README.md)
- **Custom endpoints:** "Custom endpoints (including `OPENAI_BASE_URL`) default to Chat Completions. Pass `api="responses"` or `api="chat_completions"` to `OpenAIProvider`." The example given is `client.system_one(state, questions, model=OpenAIProvider("grok-4", base_url="https://api.x.ai/v1"))` — [GitHub](https://github.com/typesafe-ai/system-one-adapter-python); [README](https://raw.githubusercontent.com/typesafe-ai/system-one-adapter-python/main/README.md)
- **Options:**
  - `llm_answer_mode`: `"probabilities"` (a per-label distribution) or `"discrete"` (one value per question).
  - `structured_outputs=True` uses the provider's native structured-output mode.
  - Also `normalize_probabilities` and `n_retry_malformed_structure`.
  - It supports Noul, Choice and Score.
  - Sources: [GitHub](https://github.com/typesafe-ai/system-one-adapter-python); [README](https://raw.githubusercontent.com/typesafe-ai/system-one-adapter-python/main/README.md)
- **Purpose:** "Useful for comparing TypeSafe against an LLM on cost/speed/intelligence" — [README](https://raw.githubusercontent.com/typesafe-ai/system-one-adapter-python/main/README.md)

###### Inferences
- The options `normalize_probabilities`, `n_retry_malformed_structure` and `structured_outputs` strongly suggest the LLM writes its probabilities as structured JSON (verbalized probabilities) rather than the adapter reading token logprobs. **UNVERIFIED**: the source code was not readable through the fetch tool.
  - If true, the probabilities are less calibrated than those from Jev, Clef or Laya.
  - It also means the model must reliably emit schema-valid JSON. Small local models on CPU may need retries.
- Ollama exposes an OpenAI-compatible `/v1` Chat Completions endpoint (default `http://localhost:11434/v1`) with JSON-schema structured outputs. That should make `OpenAIProvider("<ollama-model>", base_url="http://localhost:11434/v1")` work. This is general knowledge and was not verified against the adapter's tests.
- This path keeps data local and is free. However, it uses a generic chat LLM rather than a trained decision model, and it is officially framed as an evaluation tool.

###### Gaps
- Not documented: the exact probability mechanism (verbalized JSON vs logprobs). Needs a read of the source (for example with `gh api` or a local clone).
- Not found: version or date and the PyPI release history.
- Not documented: whether a dummy API key is needed for local endpoints.

##### Q6. Distilled clones (flag only — do not recommend)

###### Takeaway
**Verified for autotrust/JEV-9B.** It is explicitly a student distilled from Jev 1.13 output distributions collected via OpenRouter. Its corpus `SargeDev/jev-distill-corpus-v3` has about 498k Jev-labeled rows. Using it could breach the MCA clause cited in the brief (clause text unverified), so this family is a legal risk.

###### Cited Findings
- **autotrust/JEV-9B:**
  - Apache-2.0, based on Qwen3.5-9B.
  - Trained on `SargeDev/jev-distill-corpus-v3` (740,957 rows) with three streams: `yuri_v3` (498,010 rows of "TypeSafe Jev 1.13 full output distributions via OpenRouter"), `openjev_v2` (94,801 Open-Jev rows with programmatic CC0 labels) and `yuri_v1` (148,154 placeholder-labeled rows).
  - The card explicitly calls it a student distilled from Jev 1.13 outputs and says it is "not affiliated with, endorsed by, or a product of TypeSafe AI".
  - Source: [HF autotrust/JEV-9B](https://huggingface.co/autotrust/JEV-9B)
- **Related autotrust repos:** JEV-27B (created 2026-09-25, about 168k downloads), JEV-27B-VL (2026-09-30, about 1.5M downloads), JEV-9B (2026-09-23, about 313k downloads) and JEV-Gemma4-26B-A4B — [HF API search "jev"](https://huggingface.co/api/models?search=jev)

###### Inferences
- The other autotrust variants probably share the same distillation provenance. This is **UNVERIFIED**; each card was not opened.
- Other community "Jev"/"OpenJev" models have **unknown provenance** and should be treated as risky until checked:
  - Meanblock/JEV-CPU
  - TokenRhythm/NeoHorse-Jev-4B
  - akhilaaa3/Jev-Omni
  - the apus-ailab/APUS-OpenJev-v1 series
  - alanhuangya/OpenJev-*, including the 4B built on jaredpalmer/kev-4b
- A high download count is not evidence of legal safety.

###### Gaps
- The `SargeDev/jev-distill-corpus-v3` dataset card was not opened directly; the details come from the JEV-9B card.
- The provenance of the other autotrust and community models was not checked.
- The MCA clause text is unverified (see Q0).

### 3.4 Local open LLMs with Yes-No logprob classification

*Source file: `research_notes/Running Jev locally for free/local_llm_logprob_classification.md`*

#### Replicating Jev-style typed classification outputs (Noul / Choice / Score) with small open-weight LLMs run locally

Research date: 2026-10-07. Research was done on the open web (vendor docs, GitHub, arXiv, Hugging Face, practitioner blogs). The request snippets below are my own examples built from the parameters each project documents; I did not run them. Check them against the server version you install.

Mapping used throughout:
- **Noul (yes/no probability)**: ask a question that can only be answered "Yes" or "No", force a one-token answer, and read P("Yes") / (P("Yes") + P("No")) from next-token logprobs.
- **Choice (probability per option)**: label the options with single-token letters (A/B/C...) or single-token words, force one token, and softmax over the label tokens' logprobs.
- **Score (numeric)**: either (a) take the probability-weighted expected value over the digit tokens "1".."5" or "0".."9" (the "verbalization logprobs" idea below), or (b) constrain the output to a number with a regex or grammar and read it directly. Option (a) gives much better resolution than a bare verbalized number.

---

##### Q1. Logprob/logit-based classification: reliability, calibration, best practices

###### Takeaway
Reading next-token probabilities over a fixed label set is the standard, cheap way to get a probability-like score from an LLM, and it is generally better than asking the model to state a confidence number. The raw probabilities are biased by prompt format, label order and label frequency, so plan on a calibration step: contextual calibration with a content-free input, or temperature/Platt scaling on a few hundred labelled emails. The best 2026 result combines both signals: weight the verbalized confidence digits by their token probabilities.

###### Cited Findings
- "Calibrate Before Use" (Zhao, Wallace, Feng, Klein, Singh; ICML 2021; arXiv Feb 19 2021, revised Jun 10 2021) found that few-shot LLM predictions are systematically biased toward labels that are frequent in the prompt (majority label), labels near the end of the prompt (recency), and tokens common in pre-training. They propose **contextual calibration**: run the prompt with a content-free input such as "N/A", record the label probabilities, and fit an affine correction that makes that output uniform. They report up to 30.0% absolute average-accuracy gains and lower variance across prompt formats. — [arXiv 2102.09690](https://arxiv.org/abs/2102.09690)
- Merdjanovska, Zaidan, Rücklé, "Evaluation Pitfalls and Sparsity Limitations in LLM-based Confidence Estimates for Classification" (arXiv Aug 5 2026; ACL 2026 Findings) compared verbalized confidence with token likelihood for classification. Verbalized confidence is **sparse**: "Qwen3-32B verbalizes only eight unique confidence values on SST-2, with over half being exactly 95%." — [arXiv 2608.04899](https://arxiv.org/abs/2608.04899)
- The same paper proposes **"verbalization logprobs"**, which weights the verbalized confidence digits by their token probabilities. Reported gains: +2.3 pts AUARC and +0.9 AUROC over vanilla verbalization, and +1.3 AUARC and +4.7 AUROC over plain token logprobs, at no extra inference cost. — [arXiv 2608.04899 (search abstract)](https://arxiv.org/pdf/2608.04899); [ACL Anthology 2026.findings-acl.1671](https://aclanthology.org/2026.findings-acl.1671/)
  - Note: the +1.3/+4.7 figures over token logprobs come from the search-engine summary of the abstract. The abstract page I fetched confirmed the +2.3 AUARC figure only.
- "Same Answer, Different Confidence: Protocol Sensitivity in LLM Confidence Calibration" (2026) warns that "token likelihood" is not a single baseline. Results depend on which answer is scored, how tokens are aggregated, the conditioning prompt, and the answer position. Different choices can change the comparison for the same model and dataset. — [arXiv 2605.27752](https://arxiv.org/pdf/2605.27752)
- Other 2025–2026 work on calibrating or training verbalized confidence: "Calibrating Verbalized Probabilities for LLMs" ([arXiv 2410.06707](https://arxiv.org/html/2410.06707v1)), ConfTuner ([arXiv 2508.18847](https://arxiv.org/html/2508.18847v1)), and "How do LLMs Compute Verbal Confidence?" (2026), which finds that verbal confidence carries information beyond token log-probabilities ([arXiv 2603.17839](https://arxiv.org/pdf/2603.17839v2)).
- Production precedent: IBM Granite Guardian models emit a yes/no verdict, and a risk probability is derived from the yes/no token logprobs (the docs show code requesting the top-20 logprobs, `nlogprobs=20`). An NVIDIA NIM example shows "risk detected? Yes" with "probability of risk: 0.995". — [HF model card granite-guardian-3.3-8b](https://huggingface.co/ibm-granite/granite-guardian-3.3-8b); [NVIDIA NIM Granite Guardian 3.0 8B](https://docs.api.nvidia.com/nim/reference/ibm-granite-guardian-3_0-8b)
- Practitioner write-up on using LLMs (including through Ollama) as classifiers via logprobs: [Gerard Simons, "LLMs as Classifiers (Part 2)", Medium](https://medium.com/@GerardSimons/llms-as-classifiers-part-2-d874d20cd3c9). There is also a small library, `ollama_classifier`, that wraps the Ollama backend for this ([readthedocs source](https://ollama-classifier.readthedocs.io/en/latest/_modules/ollama_classifier/backends/ollama.html)). I did not review either in detail.

###### Inferences (best-practice checklist synthesized from the sources above plus standard practice; these are not each separately cited)
- **Use single-token labels.** "Yes"/"No" and capital letters "A".."E" are single tokens in essentially every modern tokenizer. Check the leading-space variant too (" Yes" vs "Yes"): chat templates usually put the assistant answer at the start of a turn, so the no-space form is typical, but verify with the tokenizer. Sum the probability mass of the case and space variants ("Yes", " Yes", "yes") before normalizing.
- **Normalize over the label set only:** p_i = exp(lp_i) / Σ_j exp(lp_j). If the total label mass before normalizing is low (for example under 0.5), the model wanted to say something else. Treat that as low reliability and log it.
- **Force the answer token.** End the prompt with an instruction like "Answer with exactly one letter." Disable "thinking"/reasoning modes, because Qwen3/3.5 hybrid-thinking models otherwise emit `<think>` first. With vLLM you can pass `chat_template_kwargs={"enable_thinking": false}` for Qwen. Then read logprobs at the first generated position. `max_tokens=1` is enough.
- **Prefer reading logprobs over constrained decoding to read the score.** A constrained or grammar-restricted generation guarantees a valid label, but the logprob it returns may reflect post-mask renormalized or sampled values. The cleanest signal is unconstrained logits at the first answer position, restricted afterwards to the label tokens (vLLM `logprob_token_ids`, or top-k logprobs with k=20).
- **Calibration:**
  - With zero labelled data, use contextual calibration: one extra call per prompt template with "N/A" as the email, cached.
  - With 200–500 labelled emails, fit temperature scaling (one parameter) or Platt/isotonic regression per label on the normalized probabilities, and report ECE and Brier score before and after.
  - Few-shot examples help accuracy, but they introduce majority-label and recency bias (Zhao et al.), so balance the examples and shuffle their order.
- **Score:** ask for a 1–5 (or 0–9) rating, read the logprobs of the digit tokens, and compute E[score] = Σ d·p(d). This avoids the sparsity problem Merdjanovska et al. describe.
- Do not ask the model to "output a probability between 0 and 1". Verbalized numbers are sparse and cluster at 90–95%.

###### Gaps
- I found no 2025–2026 paper with ECE numbers specifically for **small (≤9B) open models on support-ticket or email classification** using next-token label probabilities. We need to measure this ourselves on a labelled sample.
- I could not get the full results tables of Merdjanovska et al. (the second model name, the datasets beyond SST-2, ECE values).

---

##### Q2. Serving stacks that expose token logprobs / constrained decoding locally

###### Takeaway
All the major local stacks now expose top-k token logprobs:
- **vLLM** is the most complete. It has `logprobs`, `prompt_logprobs`, a `logprob_token_ids` parameter made for classification, `allowed_token_ids`, `logit_bias`, structured outputs with `choice`/regex/JSON, and dedicated `/classify` and `/score` endpoints. It is effectively GPU-oriented.
- **llama.cpp server** is the best CPU option. It has `n_probs`, GBNF `grammar` and `json_schema`, and OpenAI-compatible endpoints.
- **Ollama** added logprobs in **v0.12.11 (Nov 12, 2025)**. Older blog posts saying "Ollama has no logprobs" are outdated.

###### Cited Findings
**vLLM**
- Structured outputs use xgrammar or guidance backends (default `"auto"`; select with `--structured-outputs-config.backend`). `guided_choice` was **deprecated in v0.12.0** in favour of `extra_body={"structured_outputs": {"choice": [...]}}` or `StructuredOutputsParams(choice=...)`. Regex and JSON-schema (`response_format={"type":"json_schema",...}`) are also supported. — [vLLM docs: Structured Outputs](https://docs.vllm.ai/en/latest/features/structured_outputs/)
- Documented choice example: `client.chat.completions.create(model=model, messages=[...], extra_body={"structured_outputs": {"choice": ["positive", "negative"]}})`. — [vLLM docs: Structured Outputs](https://docs.vllm.ai/en/latest/features/structured_outputs/)
- SamplingParams:
  - `logprobs` is the "Number of log probabilities to return per output token". It follows the OpenAI convention: the sampled token is always included, so up to logprobs+1 entries; -1 returns the whole vocabulary.
  - `prompt_logprobs` returns logprobs per prompt token.
  - **`logprob_token_ids`**: "Specific token IDs to return logprobs for. More efficient than logprobs=-1 when you only need logprobs for a small set of tokens" (max 128 ids). This is effectively a classification feature.
  - `allowed_token_ids` keeps only the given token ids.
  - `logit_bias` adjusts raw scores.
  - `structured_outputs` handles JSON/grammar/regex.
  — [vLLM API: SamplingParams](https://docs.vllm.ai/en/latest/api/vllm/sampling_params/)
- vLLM online serving lists a Classification API (`/classify`), a Score API (`/score`, `/v1/score`) and a Pooling API (`/pooling`) for sequence-classification and reward/cross-encoder models. — [vLLM docs: Online Serving](https://docs.vllm.ai/en/latest/serving/online_serving/)

**llama.cpp server (`llama-server`)**
- `/completion` parameters:
  - `n_probs`: "If greater than 0, the response also contains the probabilities of top N tokens for each generated token" (default 0).
  - `post_sampling_probs`: returns `prob` (0–1) and `top_probs` after the sampler chain, instead of `logprob`/`top_logprobs`.
  - `grammar` (GBNF) and `json_schema` for constrained generation.
  - Each `probs` entry has `id`, `logprob`, `token`, `bytes`, `top_logprobs`.
  — [llama.cpp tools/server/README.md](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- With temperature < 0, tokens are sampled greedily, but the probabilities are still computed as a plain softmax of the logits, ignoring other sampler settings. — [llama.cpp server README (older tag)](https://git.peisongxiao.com/CS348Project/llama.cpp/raw/tag/b1818/examples/server/README.md)
- `/v1/chat/completions` and `/v1/completions` support the same sampling features as `/completion`, plus `response_format` for schema-constrained JSON. The server also has `/reranking`, `/embedding` and `/v1/embeddings`. — [llama.cpp server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)

**Ollama**
- **v0.12.11, released Nov 12, 2025**, added logprobs to Ollama's API (`/api/generate`) and to the OpenAI-compatible API. The parameters are `"logprobs": true` and `"top_logprobs": N`. The release notes name "classification tasks" as a use case. — [Ollama release v0.12.11](https://github.com/ollama/ollama/releases/tag/v0.12.11)
- `/api/generate` documents `logprobs` ("Whether to return log probabilities of the output tokens") and `top_logprobs` ("Number of most likely tokens to return at each token position"). The response carries a `logprobs` array of `{token, logprob, bytes, top_logprobs}`. The `format` parameter accepts `"json"` or a JSON schema for constrained output. — [Ollama docs: Generate](https://docs.ollama.com/api/generate)
- Related client-library issue: [ollama-python #517](https://github.com/ollama/ollama-python/issues/517).

**Other**
- Amazon Bedrock Custom Model Import added logprob support for imported open models (Sep 2025). Not local, but evidence that logprob classification is a mainstream pattern. — [AWS ML blog](https://aws.amazon.com/blogs/machine-learning/unlock-model-insights-with-log-probability-support-for-amazon-bedrock-custom-model-import/)

###### Example request snippets (built from the documented parameters above; not run)

vLLM, OpenAI-compatible chat, Yes/No (Noul):
```python
from openai import OpenAI
import math
c = OpenAI(base_url="http://localhost:8000/v1", api_key="-")
r = c.chat.completions.create(
    model="Qwen/Qwen3.5-4B",
    messages=[{"role":"system","content":"Answer with exactly one word: Yes or No."},
              {"role":"user","content":f"Email:\n{email}\n\nIs the customer asking for a refund?"}],
    max_tokens=1, temperature=0, logprobs=True, top_logprobs=20,
    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
)
top = r.choices[0].logprobs.content[0].top_logprobs
py = sum(math.exp(t.logprob) for t in top if t.token.strip().lower()=="yes")
pn = sum(math.exp(t.logprob) for t in top if t.token.strip().lower()=="no")
p_yes = py/(py+pn) if py+pn>0 else None
```

vLLM, Choice. Use letters, or pass the label token ids through `logprob_token_ids` (a SamplingParams field; check that your version's OpenAI server accepts it in `extra_body`) or through `allowed_token_ids`:
```python
extra_body={"allowed_token_ids": [id_A, id_B, id_C, id_D], "chat_template_kwargs":{"enable_thinking": False}}
# with logprobs=True, top_logprobs=4, max_tokens=1 -> softmax over the 4 returned logprobs
```
Caveat: with `allowed_token_ids` the returned logprobs may be computed after masking. Compare against an unmasked call.

llama.cpp server, native endpoint:
```bash
curl http://localhost:8080/completion -d '{
  "prompt": "<chat-templated prompt ending at assistant turn>",
  "n_predict": 1, "temperature": 0, "n_probs": 10,
  "grammar": "root ::= \"Yes\" | \"No\""
}'
# read completion_probabilities[0].top_logprobs (or top_probs if post_sampling_probs=true)
```

Ollama (>= 0.12.11):
```bash
curl http://localhost:11434/api/generate -d '{
  "model": "qwen3.5:4b", "prompt": "...Answer Yes or No.", "stream": false,
  "raw": false, "think": false,
  "options": {"temperature": 0, "num_predict": 1},
  "logprobs": true, "top_logprobs": 10
}'
```

###### Inferences
- **On CPU:** use llama.cpp's `llama-server` directly, or Ollama, which is built on llama.cpp. llama-server gives more control (grammar, `n_probs`, and slot/prompt caching so a shared system prompt is reused).
- **On a GPU:** use vLLM. `logprob_token_ids` and the `/classify` endpoint for fine-tuned sequence classifiers are a clean upgrade path.
- **SGLang** and **HF TGI** also implement OpenAI-style logprobs and grammar/JSON constraints according to their docs (see Gaps). **transformers** directly is the simplest route for a batch job: one forward pass, take `logits[0, -1, label_ids]`, softmax. No server is needed, and it works on CPU for models of 2B or less.

###### Gaps
- I did not fetch SGLang or TGI docs in this pass, so their exact parameter names (e.g. SGLang `return_logprob`, `top_logprobs_num`, `regex`, `choices`; TGI `details`/`top_n_tokens`, `grammar`) are unverified here. Check them before relying on them. Also note that TGI went into maintenance mode in 2025 according to community reports; that is also unverified here.
- It is not confirmed from the docs whether Ollama's `/api/chat` (as opposed to `/api/generate`) returns logprobs. The release notes name `/api/generate` and the OpenAI-compatible API.
- It is not confirmed whether vLLM's OpenAI server accepts `logprob_token_ids` via `extra_body` in every version. The field is documented on SamplingParams.

---

##### Q3. Best small open-weight models (2026) and licenses

###### Takeaway
As of October 2026 the strongest commercially usable small families are **Qwen3.5 Small** (0.8B/2B/4B/9B, Apache 2.0, released Mar 2 2026) and **Gemma 4** (E2B/E4B, plus 26B-A4B MoE and 31B, **now Apache 2.0**, released Apr 2 2026). For short support-email classification, a 4B-class instruct model (Qwen3.5-4B or Gemma 4 E4B) is the natural default, with 9B as the accuracy step-up. Gemma 4's switch to Apache 2.0 makes older "Gemma license restrictions" notes outdated.

###### Cited Findings
- **Qwen3.5 Small**:
  - Four models (0.8B, 2B, 4B, 9B), released **March 2, 2026** on Hugging Face and ModelScope.
  - **Apache 2.0**, 201 languages, natively multimodal.
  - 262K context for all four (9B extendable to 1M).
  — [Gigazine, 2026-03-03](https://gigazine.net/gsc_news/en/20260303-qwen-3-5-small); [tokencost.app](https://tokencost.app/blog/qwen-3-5-small-benchmarks-pricing)
- Qwen3.5-9B is reported at 82.5% MMLU-Pro and 81.7% GPQA Diamond. This is an aggregator figure, not verified against the model card. The Qwen3.5 family runs from 0.8B to a 397B MoE flagship. — [Hugging Face community blog (daya-shankar)](https://huggingface.co/blog/daya-shankar/open-source-llms); [computingforgeeks comparison table](https://computingforgeeks.com/open-source-llm-comparison/)
- **Gemma 4**:
  - Released **April 2, 2026** under **Apache 2.0**, replacing Google's earlier custom Gemma license.
  - Variants: E2B (2.3B effective), E4B (4.5B effective), 26B MoE (4B active), 31B dense.
  - E2B/E4B have a 128K context; 26B/31B have 256K.
  - The 31B ranks third on the Arena text leaderboard (1452 Elo).
  — [TechWyse news](https://www.techwyse.com/news/ai-search/google-deepmind-gemma-4-open-models-apache-2-0-release); [Gigazine 2026-04-03](https://gigazine.net/gsc_news/en/20260403-google-released-gemma-4); [DataNorth](https://datanorth.ai/news/google-releases-gemma-4-open-models)
  - Date conflict: one aggregator says Gemma 4 "launched March 31, 2026" ([codersera](https://codersera.com/blog/gemma-4-vs-qwen-3-5-comparison-2026/)). Most sources say April 2, 2026.
- Lushbinary (Apr 2026) gives the Gemma 4 E2B as 2.3B and E4B as 4B, calls Qwen 3.5 the "safe, battle-tested choice", and lists the DeepSeek-R1 distills (1.5B–70B, **MIT**). — [Lushbinary, Apr 2026](https://lushbinary.com/blog/best-open-source-llms-april-2026-comparison-guide/)
- "Qwen3 and Gemma 4 are safer commercial choices because of Apache 2.0 licensing." — [contextstudios.ai self-hosting guide](https://www.contextstudios.ai/guides/best-open-weight-llms-2026)
- A list of the best small models under 10B for 2026 (aggregator): [Labellerr](https://www.labellerr.com/blog/best-small-language-models-under-10b-parameters/)
- Granite Guardian 3.3 8B is **Apache 2.0** (released Aug 1, 2025). — [HF model card](https://huggingface.co/ibm-granite/granite-guardian-3.3-8b)

###### Inferences
- For local yes/no or choice classification on CPU:
  - **Qwen3.5-2B or 4B** at Q4_K_M/Q8_0 GGUF is the speed/quality sweet spot.
  - On a GPU, **Qwen3.5-9B** or **Gemma 4 E4B** in BF16 is better.
  - Gemma 4 26B-A4B (MoE, 4B active) is a GPU option. It has 26B weights to hold in memory, so it is not a CPU-friendly default.
- Both Qwen3.5 and Gemma 4 are multimodal. For text-only classification that is fine, but check that the GGUF/vLLM build you use loads the text path efficiently.
- Qwen3.x/3.5 are hybrid "thinking" models. **Disable thinking** for logprob classification, otherwise the first token is `<think>`.
- Licenses to double-check from memory (not verified in this pass):
  - Llama 3.x: Llama Community License. Commercial use is allowed, but it has a 700M-MAU clause and naming/attribution terms.
  - Phi-4-mini: MIT.
  - SmolLM3: Apache 2.0.
  - Mistral's small models: mixed (some Apache 2.0, some Mistral Research License).
  For a strictly permissive stack, Qwen3.5 and Gemma 4 (Apache 2.0) are confirmed above.

###### Gaps
- I did not fetch the Qwen3.5 or Gemma 4 model cards on Hugging Face directly, so the license and sizes are from news and aggregator sources (consistent across several).
- No source compared Qwen3.5 vs Gemma 4 vs Llama/Phi/SmolLM3 specifically on **zero-shot classification calibration**.
- I did not verify the license status of Phi-4-mini, SmolLM3, Llama 3.x/4, Ministral or Granite 4 in this pass.

---

##### Q4. Hardware for a few hundred calls/day with 1–3k token inputs

###### Takeaway
Volume is tiny: 300 calls × ~2k tokens ≈ 600k input tokens/day, and each call generates only 1 token. Cost is dominated by **prompt processing (prefill)**, not generation.
- **CPU-only is feasible for an asynchronous or batch workflow** with a 1–4B model. Expect tens of seconds per 2k-token email on an older 4-core CPU, and much less on a modern 8–16-core CPU.
- **A single small GPU** (e.g. 20 GB RTX 4000 SFF Ada; Hetzner GEX44 at €184/mo) brings per-call latency to roughly a second or less.
- An existing developer laptop or a ~$40/mo VPS can handle this volume if latency is not critical.

###### Cited Findings
- CPU benchmark (Jul 13 2026), 4 cores of a Xeon E5-2696 v4, 7.8 GB RAM, DDR4-2400, llama.cpp, *generation* speed:

  | Model | Quant | Speed | RAM |
  |---|---|---|---|
  | Mistral 7B | Q4_K_M | 4.5 tok/s | ~4.3 GB |
  | Qwen2.5-7B | Q4_K_M | 3.8 tok/s | ~4.5 GB |
  | Llama 3.1 8B | Q4_K_M | 3.2 tok/s | ~5.2 GB |
  | Llama 3.1 8B | Q8_0 | 2.1 tok/s | ~8.1 GB |

  The author ran a hybrid local/API setup on a **$40/month VPS** that handled 70% of requests locally and cut the API bill from ~$120 to ~$35/month. They state llama.cpp CPU efficiency improved "roughly 10x over two years". — [dev.to, "Running LLMs on CPU in 2026"](https://dev.to/manoir_yantai_f22f01340f0/-running-llms-on-cpu-in-2026-real-benchmarks-from-a-4-core-xeon-server-a-4-1438)
- CPU-only on a 16-core Ryzen 9 7950X reaches ~26 tok/s generation for an 8B Q4_K_M model. Other reported figures: 7950X 35 tok/s and i9-13900K 30 tok/s (Llama-2-7B class). Reported cold time-to-first-token: ~1,250 ms on CPU vs ~350 ms on GPU (prompt length unspecified). — [markaicode llama.cpp CPU vs GPU benchmark](https://markaicode.com/benchmarks/llamacpp-tokens-per-second-benchmark/)
- Prompt processing (prefill) is compute-bound and parallel, while generation is memory-bandwidth-bound. `llama-bench` reports `pp512` (prefill) and `tg128` (generation). — [llama-bench README](https://github.com/ggerganov/llama.cpp/blob/b8c1476e44cc1f3a1811613f65251cf779067636/examples/llama-bench)
- One reported prefill figure: Qwen2.5-3B Q4_K_M on an old Intel i7-6700 (4 threads) at **~43 tok/s prompt processing**. This comes from a search-result summary of legacy-hardware benchmark posts and I did not verify it on the page. — [mgroeber.de legacy hardware benchmarks](https://www.mgroeber.de/benchmarking-llamacpp-on-legacy-hardware-2.html); [computingforgeeks llama.cpp guide](https://computingforgeeks.com/run-local-llm-llama-cpp/)
- **Hetzner GEX44** dedicated GPU server: NVIDIA RTX 4000 SFF Ada (20 GB), i5-13500 14-core, 64 GB RAM, 2×1.92 TB NVMe, **€184/month + €79 setup**. Price unchanged in the June 2026 price adjustment. — [effloow Hetzner GPU guide 2026](https://effloow.com/articles/hetzner-cloud-ai-gpu-server-guide-2026); [LowEndBox](https://lowendbox.com/blog/need-a-cheap-gpu-server-hetzner-brings-them-back-with-some-controversy/)
- RTX 4000 Ada hourly cloud pricing across providers: [getdeploying.com](https://getdeploying.com/gpus/nvidia-rtx-4000-ada-vs-nvidia-rtx-pro-4000)

###### Inferences (back-of-envelope; validate with `llama-bench -p 2048 -n 1` on the target box)
- At ~43 tok/s prefill (3B Q4 on an old 4-core CPU), a 2k-token email takes **~45–50 s**. 300/day is ~4 CPU-hours/day: fine for a background queue, not for interactive use.
- A modern 8–16-core desktop or server CPU (AVX2/AVX-512) typically prefills several hundred tok/s for a 1–4B Q4 model, giving **a few seconds per email**. I have no verified source for this; benchmark it.
- **Reuse the shared prefix.** Put the fixed instructions and few-shot examples first and the email last, then use llama-server prompt caching or vLLM automatic prefix caching. Only the email tokens are new per call, and each extra question about the same email (Noul + Choice + Score) reuses the email prefix too, if the email comes before the question.
- **GPU:** a 4B–9B model in BF16 or FP8 fits easily in 16–24 GB. Prefill for 2k tokens on an RTX 4000-class card should be well under a second (inference; not measured in a cited source). €184/month is likely overkill for 300 calls/day unless latency matters.
- **Memory:** a 4B Q4_K_M GGUF is ~2.5–3 GB and an 8B Q4_K_M is ~5 GB (consistent with the 5.2 GB figure above), so 8–16 GB of RAM is enough for CPU serving.

###### Gaps
- I found no verified 2026 CPU **prefill** benchmarks for Qwen3.5-2B/4B or Gemma 4 E2B/E4B GGUF at 2k-token prompts.
- No verified per-call latency numbers for small-GPU vLLM at a 2k-token prompt / 1 output token.

---

##### Q5. Purpose-built open classifiers / judge / guard models that output label probabilities

###### Takeaway
The most directly reusable pattern is **IBM Granite Guardian 3.3 8B** (Apache 2.0). It is a yes/no judge that accepts **custom criteria** and derives its probability from yes/no token logprobs, which is almost exactly a "Noul" primitive. vLLM's `/classify` and `/score` endpoints serve fine-tuned sequence-classifier and reward models, which is the upgrade path once we have labelled tickets.

###### Cited Findings
- **Granite Guardian 3.3 8B** (Apache 2.0, released Aug 1 2025):
  - Outputs `<score>yes</score>` or `<score>no</score>`, with an optional `<think>` reasoning mode. Probability comes from token logprobs (examples use `nlogprobs=20`).
  - Supports "bring your own criteria" through `custom_criteria` in `guardian_config` passed to `apply_chat_template()`.
  - Benchmarks: harm detection F1 0.81 (no-think); RAG hallucination balanced accuracy 0.761 on LM-AggreFact; function-calling 0.74 balanced accuracy on fc-reward-bench.
  - Smaller relative: Granite-Guardian-HAP-38M (a hate/abuse/profanity classifier).
  — [HF model card](https://huggingface.co/ibm-granite/granite-guardian-3.3-8b)
- Granite Guardian 3.0 8B (Oct 2024): aggregate harm F1 0.67, average AUC 0.81 on RAG hallucination benchmarks. Example output "probability of risk: 0.995". Earlier 2B and 3.2-5B variants exist. — [NVIDIA NIM model card](https://docs.api.nvidia.com/nim/reference/ibm-granite-guardian-3_0-8b); [featherless granite-guardian-3.2-5b](https://featherless.ai/models/ibm-granite/granite-guardian-3.2-5b)
- Mozilla.ai's `any-guardrail` wraps Granite Guardian as a guardrail backend. — [any-guardrail docs](https://docs.mozilla.ai/any-guardrail/api-reference/index/granite-guardian)
- vLLM serves classification models via `/classify` and cross-encoder/reward scoring via `/score`. — [vLLM docs: Online Serving](https://docs.vllm.ai/en/latest/serving/online_serving/)

###### Inferences
- For yes/no checks on support emails ("is this a refund request?", "is the customer angry?"), Granite Guardian 3.3 with custom criteria is a credible zero-training baseline. At 8B, though, it is heavier than a 4B general instruct model.
- Once a few hundred labelled emails exist, fine-tune a small encoder (e.g. ModernBERT/DeBERTa) or a 0.5–2B LLM with a classification head. It gives calibrated softmax outputs, millisecond CPU latency, and is servable via vLLM `/classify`. This matches the literature in Q6, where fine-tuned small models beat zero-shot.
- Other judge models (Prometheus 2, Llama Guard, Qwen3Guard, ShieldGemma) exist, but I did not verify their 2026 status or licenses in this pass. Llama Guard carries the Llama license.

###### Gaps
- I did not verify the Prometheus-2, Qwen3Guard or ShieldGemma model cards, licenses or calibration results.
- I found no published calibration (ECE) results for Granite Guardian's probability on custom criteria.

---

##### Q6. Published comparisons: small-LLM zero-shot classification vs API models

###### Takeaway
The consistent finding (2024–2025) is that zero-shot small open LLMs trail API models on harder, many-label tasks. Small **fine-tuned** models, including BERT-class models, match or beat zero-shot GPT-4/Claude-class models when labelled data exists. For a few binary or low-cardinality questions, small zero-shot models are often adequate.

###### Cited Findings
- Bucher & Martini, "Fine-Tuned 'Small' LLMs (Still) Significantly Outperform Zero-Shot Generative AI Models in Text Classification" (arXiv 2406.08660, Jun 2024): fine-tuned smaller models "consistently and significantly outperform" zero-shot GPT-3.5, GPT-4 and Claude Opus on sentiment, approval/disapproval, emotions and party positions. — [arXiv 2406.08660](https://arxiv.org/html/2406.08660v2)
- Lepagnol et al., "Small Language Models are Good Too: An Empirical Study of Zero-Shot Classification" (LREC-COLING 2024; arXiv 2404.11122) benchmarked 77M–40B parameter models on 15 datasets. Small models "can effectively classify texts, getting on par with or surpassing their larger counterparts." — [arXiv 2404.11122](https://arxiv.org/html/2404.11122v1); [ACL Anthology](https://preview.aclanthology.org/watermark/2024.lrec-main.1299)
- Vajjala & Shimangaud, "Text Classification in the LLM Era – Where do we stand?" (arXiv 2502.11830, Feb 2025):
  - Setup: 32 datasets in 8 languages; Qwen2.5-7B, Aya23-8B and Aya-Expanse-8B vs GPT-4 vs BERT/logistic regression.
  - Zero-shot GPT-4 was strong on sentiment but weak on many-label topic classification. Open 7–8B models "struggled across non-sentiment tasks".
  - Few-shot fine-tuning (FastFit) gave up to ~10% gains over zero-shot.
  - "Training classifiers using high-quality labeled data still gives the best performance."
  — [arXiv 2502.11830](https://arxiv.org/html/2502.11830v1)

###### Inferences
- These comparisons mostly used Qwen2.5 and Llama 3-era models. The 2026 Qwen3.5/Gemma 4 small models are considerably stronger on general benchmarks, so the gap is likely narrower, but no cited 2026 study confirms it. Treat the findings as directional.
- Practical plan:
  1. Start zero-shot (or few-shot) with logprob reading on Qwen3.5-4B.
  2. Label 300–500 historical support emails, measure accuracy, ECE and Brier score against our current Jev outputs, and fit temperature/Platt calibration.
  3. If a question underperforms, fine-tune a small classifier on the accumulated labels.

###### Gaps
- I found no 2026 head-to-head study of Qwen3.5/Gemma 4 small models vs frontier APIs on zero-shot classification calibration.
- I found no study using customer-support email data specifically.

### 3.5 Small encoder classifiers (zero-shot, SetFit, fine-tuned)

*Source file: `research_notes/Running Jev locally for free/encoder_classifier_alternatives.md`*

#### Encoder-Based (Non-Generative) Classifier Alternatives to Jev for "Genuine PENDING Request vs. Courtesy Close" Classification

Task framing used throughout: binary label on a support engineer's outbound reply. POSITIVE = reply asks the customer an open question or requests something the customer must supply (valid PENDING). NEGATIVE = reply resolves / informs and ends with only a courtesy close ("let me know if you have any other questions") or "we will get back to you". Volume: a few hundred per day; 100–1,500 words; data must stay on-prem. Research date: 2026-10-07.

##### 1. Zero-shot NLI / universal classifiers: how well do they handle this pragmatic distinction?

###### Takeaway
Off-the-shelf zero-shot NLI classifiers (MoritzLaurer zeroshot-v2.0, ModernBERT-zeroshot, GLiClass, bart-large-mnli) are commercially licensable and run on CPU. On benchmarks they do well on easy, topic-like tasks such as sentiment but noticeably worse on complex ones, and no source tests them on "genuine request vs. courtesy closing". Treat them as a weak baseline or a label-bootstrapping aid, not the production classifier. They also truncate at 512 tokens (DeBERTa), so the request may be cut off unless the input is pre-trimmed.

###### Cited Findings
- **MoritzLaurer/deberta-v3-large-zeroshot-v2.0**: base model under the MIT license. Variants with a "-c" suffix were trained only on commercially friendly data (Mixtral-8x7B synthetic data plus MNLI and FEVER-NLI). Variants without "-c" also include ANLI, WANLI and LingNLI, which have more restrictive licensing. — [HF model card](https://huggingface.co/MoritzLaurer/deberta-v3-large-zeroshot-v2.0)
- Across 28 classification tasks it averages 0.676 macro-F1, against 0.497 for facebook/bart-large-mnli. Sentiment tasks score 0.923–0.988; complex tasks score much lower (manifesto: 0.258). — [HF model card](https://huggingface.co/MoritzLaurer/deberta-v3-large-zeroshot-v2.0)
- The v2.0 family comes in RoBERTa-base/large and DeBERTa-v3-base/large, each with and without "-c", plus BGE-m3 multilingual versions. Token limit is 512 for DeBERTa and 8,192 for BGE-m3. The card recommends RoBERTa variants with TEI containers for production speed. The hypothesis template is customizable, e.g. "This text is about {}". — [HF model card](https://huggingface.co/MoritzLaurer/deberta-v3-large-zeroshot-v2.0)
- **ModernBERT-large-zeroshot-v2.0**: Apache 2.0, 8k context, mean macro-F1 of 0.834 across 37 datasets. The author says it "performs slightly worse then DeBERTav3 on average" but is "multiple times faster and consumes multiple times less memory", reaching about 1,100+ samples/sec on an A100 at batch size 32. The author also says a newer version with better synthetic data, to make full use of the 8k window, is being prepared. Its training mix includes ANLI and WANLI, so it is not the "-c" commercially-clean data mix. — [HF model card](https://huggingface.co/MoritzLaurer/ModernBERT-large-zeroshot-v2.0)
- Paper "Building Efficient Universal Classifiers with Natural Language Inference" (Laurer et al.; arXiv 2312.17543; v1 2023-12-29, v2 2024-03-22): trained on 33 datasets with 389 classes, it improves zero-shot performance by 9.4%. The authors argue BERT-like models are the efficient alternative to LLMs when classification is the only goal, for both zero-shot and few-shot use. — [arXiv](https://arxiv.org/abs/2312.17543)
- **GLiClass v3.0** (Knowledgator): Apache 2.0, trained on synthetic and licensed data that permits commercial use. Sizes: edge (32.7M params), modern-base (151M), modern-large (399M), base (187M), large (439M). — [HF model card](https://huggingface.co/knowledgator/gliclass-modern-large-v3.0); [license README](https://huggingface.co/knowledgator/gliclass-base-v3.0/blob/main/README.md)
- GLiClass modern-large averages 0.6082 F1 in zero-shot, against 0.6821 for DeBERTa-v3-large zero-shot. The best v3.0 model reaches 0.7193. Throughput is about 43.8 examples/sec against about 6.03/sec for cross-encoders (A6000 GPU, batch size 1). Paper arXiv 2508.07662, dated 2025-08-11. — [HF model card](https://huggingface.co/knowledgator/gliclass-modern-large-v3.0)
- SetFit docs, dair-ai/emotion test set: bart-large-mnli zero-shot scored 37.65% accuracy, against 59.1% for "zero-shot" SetFit (bge-small trained on templated synthetic sentences). On GPU, bart-large-mnli took 31.2 ms per sentence against 0.46 ms for SetFit bge-small, about 67x slower. — [SetFit docs: zero-shot](https://huggingface.co/docs/setfit/main/en/how_to/zero_shot)
- Background on why this task is hard. Indirect requests such as "Can you open that window?" are literally questions but function as requests. Whether such a form counts as a request depends on context, and canonical forms can lead listeners to mistake intended questions for requests. — [Trott & Bergen, UCSD](https://pages.ucsd.edu/%7Ebkbergen/papers/trott_5_8.pdf)

###### Inferences
- The target distinction is a speech-act / pragmatics judgement, not a topic. On "complex" tasks NLI zero-shot models fall to well below 0.7 F1 (manifesto: 0.258), so expect mediocre and unstable results without fine-tuning. Rough guess, not sourced: perhaps 65–80% accuracy, depending heavily on hypothesis wording.
- Hypothesis wording matters a lot. Candidate templates: "The writer is asking the customer to provide information or take an action." vs. "The writer is only offering further help and does not need a reply." Run several and compare on a labelled set.
- Zero-shot NLI probabilities come from entailment softmax and were not shown to be calibrated in any source found. If scores will be thresholded, recalibrate them (Platt / isotonic) on a labelled set.
- Use a "-c" (commercial-data) variant if training-data licensing provenance matters to legal review.
- 512-token truncation of 100–1,500-word emails is a real risk: the operative request is often near the end. Pre-trim to the last N sentences/paragraphs, or chunk.

###### Gaps
- No published evaluation was found of NLI zero-shot models on email request detection, courtesy-closing detection, or support-ticket status classification.
- No source documents calibration (ECE / reliability) of MoritzLaurer or GLiClass probabilities.
- bart-large-mnli's exact license was not verified in this session (commonly listed as MIT; check the model card).

##### 2. Few-shot and standard fine-tuning (SetFit, ModernBERT, DeBERTa-v3): labelled data, accuracy, training cost

###### Takeaway
Fine-tuning is the strongest option. SetFit can be competitive with roughly 8–64 examples per class and trains in seconds to minutes. Full fine-tuning of DeBERTa-v3 / RoBERTa / ModernBERT on about 200–500 labelled examples consistently beat GPT-4 and Claude Opus zero-shot in a 2024 study, especially on specialised tasks. For this task, plan on about 300–1,000 labelled replies, roughly balanced, plus a held-out test set.

###### Cited Findings
- **How SetFit works**: contrastive fine-tuning of a Sentence Transformer on pairs built from a few labelled examples, then a classification head on the embeddings. — [HF blog: SetFit, 2022-09-26](https://huggingface.co/blog/setfit)
- With 8 examples per class on Customer Reviews, SetFit was "competitive with fine-tuning RoBERTa Large on the full training set of 3k examples". RAFT scores: SetFit (RoBERTa-L, 355M params) 71.3, T-Few (11B) 75.8, GPT-3 (175B) 62.7, human baseline 73.5. — [HF blog: SetFit](https://huggingface.co/blog/setfit)
- Training SetFit with 8 labelled examples took about 30 s on a V100 (about $0.025), against 11 min (about $0.70) for T-Few 3B. The blog says SetFit can also run on CPU. The MPNet variant has 110M params. — [HF blog: SetFit](https://huggingface.co/blog/setfit)
- SetFit docs example: bge-small-en-v1.5 trained 1 epoch on 60 pairs in about 15 s. — [SetFit docs](https://huggingface.co/docs/setfit/main/en/how_to/zero_shot)
- **Fine-tuned small encoders vs. zero-shot LLMs** (Bucher & Martini, arXiv 2406.08660 v2, 2024-08-16), weighted F1:
  - Sentiment: DeBERTa-v3 0.92 / RoBERTa-L 0.92 vs. GPT-4 0.87 / Claude Opus 0.87.
  - Stance: DeBERTa-v3 0.94 vs. GPT-4 0.51 / Opus 0.57.
  - Multi-class EU positions: DeBERTa-v3 0.91 vs. GPT-4 0.45 / Opus 0.29.
  - Performance "picks up quickly" and saturates; about 200–500 training examples was the range where fine-tuned models consistently beat zero-shot LLMs.
  - Source: [arXiv 2406.08660v2](https://arxiv.org/html/2406.08660v2). Note: some GPT-4/Opus figures, e.g. 0.13 on German emotion, are unusually low and may reflect prompt or label-format issues in that study.
- **ModernBERT** (released 2024-12-19): base has 149M params and large 395M, with 8,192-token context. It is "the first base-size model to beat DeBERTaV3 on GLUE", about 2x faster than DeBERTa and up to 4x faster on variable-length inputs. — [HF blog: ModernBERT](https://huggingface.co/blog/modernbert)
- ModernBERT-base is Apache 2.0. Fine-tune it with standard BERT recipes. Flash Attention 2 is recommended on GPU, there is no CPU-specific guidance, and it does not use token type IDs. — [HF model card](https://huggingface.co/answerdotai/ModernBERT-base)
- Older domain result: segmenting emails into functional zones and classifying only specific zones raised message-level request-detection accuracy to 83.76%, a 15.9% relative increase. — [Lampert, Dale & Paris, NAACL 2010, "Detecting Emails Containing Requests for Action"](https://aclanthology.org/N10-1142/)
- Action-item detection in email "requires inferring the sender's intent". Enriched n-gram features (up to 4-grams) with chi-squared selection improved results by up to 10% over unigrams. — [Microsoft Research: Detecting Action-Items in E-mail](https://www.microsoft.com/en-us/research/publication/detecting-action-items-e-mail/)

###### Inferences
- **Recipe A (fastest to try): SetFit.**
  - Backbone: `sentence-transformers/all-mpnet-base-v2` or `BAAI/bge-small/base-en-v1.5`.
  - Data: 32–64 labelled replies per class; input is the last 1–3 paragraphs of the reply (see section 6).
  - Training: 1–2 epochs, probably minutes on a laptop CPU or seconds to minutes on free Colab T4 (extrapolated from the V100 timing above).
- **Recipe B (likely best accuracy): full fine-tune of `answerdotai/ModernBERT-base` or `microsoft/deberta-v3-base`.**
  - Data: 300–1,000 labelled replies.
  - Settings: max_length 512 (DeBERTa) or 1,024–2,048 (ModernBERT); lr about 2e-5 to 5e-5; 3–5 epochs.
  - Compute: free Colab T4; expect minutes to tens of minutes for a few hundred long examples. This is an estimate, not sourced.
- Pragmatic tasks are "specialised, non-standard" in Bucher & Martini's sense, which is exactly where fine-tuning beat zero-shot LLMs by the largest margins.
- Multilingual option, if needed: `BAAI/bge-m3`, or the multilingual zeroshot-v2.0 BGE-m3 variants. Expect lower performance than English-only models.

###### Gaps
- No published learning curve was found specifically for email request vs. courtesy-close detection. The 200–500 figure comes from social-science text tasks.
- No verified CPU-only SetFit training times for 512-token inputs were found.
- No head-to-head SetFit vs. ModernBERT-base fine-tune result on email/support data was found.

##### 3. Bootstrapping labels with an LLM (one-off) or weak rules, then distilling; active learning

###### Takeaway
"LLM labels a few hundred to few thousand historical examples, then train a small encoder on them" is an established, documented pattern. Mixing LLM labels with even a small human-verified set beats either alone. The main risks are systematic LLM label errors, which the student learns faithfully, and having no clean test set.

###### Cited Findings
- Huang, Tang & Chen (arXiv 2402.09282v4, 2024-03-24): GPT-4 annotated CoNLL data. GPT-4 itself scored F1 0.65 (standard prompting) and 0.73 (chain-of-thought). BERT trained on human labels scored 0.850, and BERT trained sequentially on GPT-4-distilled data then original data scored 0.869. The authors warn LLM output "can still be unstable" and hallucinates, and recommend tiered selection, prompt refinement, embedding-similarity few-shot example selection and active learning. Note this is an NER task, not text classification. — [arXiv 2402.09282v4](https://arxiv.org/html/2402.09282v4)
- A related study, "Knowledge Distillation in Automated Annotation: Supervised Text Classification with LLM-Generated Training Labels", trained BERT/RoBERTa/DistilBERT on 1,000 LLM-labelled samples and compared them with 250 and 1,000 human-labelled samples. Only a secondary summary was accessed, and its numerical results were not retrieved. — [secondary review](https://www.themoonlight.io/en/review/knowledge-distillation-in-automated-annotation-supervised-text-classification-with-llm-generated-training-labels)
- Bucher & Martini found fine-tuned encoders trained on 200–500 examples beat zero-shot Claude Opus and GPT-4 on specialised tasks. This implies a well-trained student can match or exceed a zero-shot teacher, provided the training labels are accurate. — [arXiv 2406.08660v2](https://arxiv.org/html/2406.08660v2)

###### Inferences
- Recommended bootstrap pipeline:
  1. Pull about 1,000–2,000 historical replies, keeping only the engineer-authored text.
  2. Have Claude label each with a strict rubric that includes edge cases: courtesy closes, "we will get back to you", rhetorical questions, embedded imperatives like "please share your job ID", conditional asks like "if the issue persists, send logs". Ask for a label plus a short rationale.
  3. Have a human audit a stratified sample of about 200, including all low-confidence or disagreement cases, and fix the rubric.
  4. Keep a human-verified test set of about 150–300 that is never used for training.
  5. Train SetFit or ModernBERT on the LLM-labelled set.
  6. Use active learning: route the student's uncertain predictions (0.35–0.65) and LLM/student disagreements to human review, add the corrections, and retrain weekly or monthly.
- Historical ticket outcomes can serve as weak labels. Did the customer reply next? Was the ticket later reopened? These are noisy and need checking against the rubric.
- Risk: sending historical emails to Claude once is still a data transfer outside the environment. That must be acceptable under the data-residency constraint; otherwise use a self-hosted LLM for the one-off labelling.

###### Gaps
- No text-classification-specific numbers were found on LLM-label noise rates for email intent tasks.
- No source quantified the effect of active learning on this kind of task.

##### 4. Rule-based and linguistic baselines (question marks, imperatives, dialogue-act models) and their failure modes

###### Takeaway
Rules (a "?" in the final paragraphs, imperatives like "please share/send/confirm", courtesy-close regex blacklists) make a cheap, interpretable first pass and a useful feature or guardrail. They fail on exactly the hard cases: courtesy questions, rhetorical questions, imperatives with no question mark, and conditional asks. Off-the-shelf dialogue-act models are trained on spoken conversation (Switchboard/MIDAS/SILICONE) and transfer poorly to support emails.

###### Cited Findings
- Hugging Face hosts dialogue-act classifiers fine-tuned on SILICONE (DeBERTa) and MIDAS (RoBERTa, XLM-RoBERTa) data. — [PyPI cltl.dialogueclassification](https://pypi.org/project/cltl-dialogueclassification)
- One dialogue system team found a dialogue-act classifier conditioned on user and bot utterances "didn't work well for question recognition". They instead fine-tuned RoBERTa on simplified dialogue-act data as a binary question/not-question task. — [arXiv 2008.12348](https://arxiv.org/pdf/2008.12348)
- The Switchboard Dialog Act Corpus tags turns/utterances with dialogue acts that summarise syntactic, semantic and pragmatic information. — [HF dataset cgpotts/swda](https://huggingface.co/datasets/cgpotts/swda/blob/main/swda.py)
- Email request detection is more accurate when quoted text, signatures and other zones are separated out (83.76% after zoning, up 15.9% relative). — [Lampert et al., NAACL 2010](https://aclanthology.org/N10-1142/)
- Indirect requests ("Can you…?") are literally questions but function as requests. Classifying their intent is context-dependent; one acoustic-feature classifier reached 74%. — [Trott & Bergen](https://pages.ucsd.edu/%7Ebkbergen/papers/trott_5_8.pdf)
- Rhetorical questions are indirect speech acts: rhetorical assertion, command, stance or emotion. — [search summary of rhetorical-question literature](https://meikai.repo.nii.ac.jp/records/2000304) (secondary; not fetched in full)
- Lexical and syntactic politeness features (indirection, deference, modality, e.g. "could you please") reach near-human politeness classification. These are candidate features for spotting softened requests. — [Danescu-Niculescu-Mizil et al. 2013, arXiv 1306.6078](https://arxiv.org/abs/1306.6078?context=cs); [conversational-featurizer docs](https://conversational-featurizer.readthedocs.io/en/latest/features_conceptual/politeness_strategies.html)
- `talon` (Mailgun) extracts quoted replies (`quotations.extract_from_plain/html`) and signatures (brute-force `extract_signature`, which works "90% of the time"; ML mode via `talon.init()`). A maintained fork, `great-talon`, exists. — [PyPI talon](https://pypi.org/project/talon/); [GitHub mailgun/talon](https://www.github.com/mailgun/talon)

###### Inferences
Failure modes for this task:

| Pattern | Example | Rule output | Correct label |
|---|---|---|---|
| Courtesy question | "Is there anything else I can help with?" | Question detected | NEGATIVE |
| Rhetorical or quoted question | "You asked: why did the deploy fail? The cause was…" | Question detected | NEGATIVE |
| Imperative request with no "?" | "Please share your job ID." | Missed | POSITIVE |
| Conditional ask | "If it happens again, send us the logs" | Ambiguous; likely NEGATIVE under the stated PENDING policy | Needs a policy decision |
| Promise of follow-up | "We will get back to you" | — | NEGATIVE |
| Question embedded mid-email, then a courtesy close | — | Last-paragraph rules miss it | POSITIVE |
| Quoted customer text left in the reply | — | False positives | Strip quoted text first |

- Rules are still worth having:
  - Preprocess with talon, i.e. strip quotes and signatures.
  - Use regex features: "?" count outside the courtesy-close list, imperative verbs (share, send, confirm, provide, try, let us know whether), and a courtesy-close lexicon.
  - Possibly use spaCy for imperative mood (root verb with no subject).
  - Feed these as auxiliary features or a sanity check alongside the learned classifier.

###### Gaps
- No published dialogue-act model trained on support or business email with a "request for information" vs. "conventional closing" distinction was found.
- No quantitative failure-rate figures for question-mark baselines on email were found.
- talon's license was not verified in this session.

##### 5. Hybrid design: local classifier plus confidence threshold, escalating uncertain cases to an LLM

###### Takeaway
Cascades (small model first, defer to a bigger model when confidence is low) are a standard, well-studied pattern. Their weak point is calibration: the threshold must be tuned per domain, and naive softmax confidence is miscalibrated. Conformal prediction gives a principled deferral rule with an error-rate guarantee.

###### Cited Findings
- Cascades cut cost by routing easy queries to a small model and deferring hard ones. Production cascades use a confidence threshold, but scores are miscalibrated, the threshold needs per-domain tuning, and naive thresholds give no accuracy bound. "Conformal Cascade" defers whenever the calibrated prediction set has more than one label, with a distribution-free error guarantee. — [Conformal Cascade, arXiv 2607.25018 (submitted 2026-07-31)](https://www.alphaxiv.org/abs/2607.25018)
- "Early abstention" in cascades trades a higher abstention rate for significant cost and error reductions. — [Cost-Saving LLM Cascades with Early Abstention, arXiv 2502.09054](https://arxiv.org/html/2502.09054v2)

###### Inferences
- Concrete design:
  1. Preprocess: talon strip, then take the last about 512 tokens of the engineer's own text.
  2. Run the fine-tuned ModernBERT/DeBERTa/SetFit model on CPU.
  3. Calibrate probabilities on a held-out human-labelled set (temperature scaling or isotonic).
  4. Auto-accept if p ≥ τ_hi or p ≤ τ_lo, and escalate the middle band to the existing Jev or LLM path, or to a self-hosted LLM if data must stay local.
  5. Pick τ so the auto-accepted error rate is at or below the target (e.g. 2%), or use split-conformal prediction with α = 0.02 and defer whenever the set is {0,1}.
  6. Log escalated cases with the LLM's verdict as new training labels (active-learning loop).
- At a few hundred per day, even a 10–20% escalation rate means only tens of LLM calls per day.
- The escalation rate itself should be monitored as a drift signal.

###### Gaps
- No source gave escalation rates for an email-intent cascade. The rate has to be measured on your own data.

##### 6. Inference stack: ONNX Runtime / Optimum, CPU latency, long-text handling

###### Takeaway
At a few hundred emails per day, CPU inference for a base-size encoder is trivially cheap: tens to a few hundred ms per email, even unoptimised. ONNX plus INT8 quantisation gives about 2–3x more speed with negligible accuracy loss. Long-text handling matters more for accuracy than speed. Trimming to the last paragraphs after stripping quotes and signatures is probably better than feeding the full 8k context.

###### Cited Findings
- Static INT8 quantisation with Hugging Face Optimum and ONNX Runtime, DistilBERT on Banking77, 128-token payload, AWS c6i.xlarge CPU:
  - p95 latency fell from 75.69 ms to 26.75 ms (2.83x).
  - Accuracy went from 92.5% to 92.24% (99.72% retained).
  - Model size fell from 255.68 MB to 134.32 MB.
  - Recipe: `ORTModelForSequenceClassification` → `AutoQuantizationConfig` (AVX512-VNNI) → percentile calibration on 256 samples → `ORTQuantizer`.
  - Source: [philschmid.de, 2022-06-07](https://www.philschmid.de/static-quantization-optimum)
- Secondary/aggregator claims: ONNX Runtime typically gives about 1.5–2x CPU speedup over PyTorch, and Optimum with ORT gives about 3–10x. A Twitter/X engineering post reports 18.5 ms average latency for an ONNX dynamic-quantised model with 8 threads on GCP n2-standard-16, for sequence lengths up to 512. — [reintech.io guide](https://reintech.io/blog/hugging-face-transformers-performance-optimization-guide); [X engineering blog 2021](https://blog.x.com/engineering/en_us/topics/insights/2021/speeding-up-transformer-cpu-inference-in-google-cloud). The X page returned 403, so this is a search-snippet figure only and it is unclear which sequence length the 18.5 ms applies to.
- A Hugging Face forum thread reports ONNX being faster only at lower sequence lengths. — [HF forum](https://discuss.huggingface.co/t/onnx-only-faster-at-lower-sequence-lengths/85654) (not fetched; title only)
- ModernBERT: 8,192 context, about 3x faster than competing long-context models, and designed with CPU deployment in mind. Its efficiency features (unpadding, Flash Attention 2) are GPU-oriented. — [HF blog](https://huggingface.co/blog/modernbert); [model card](https://huggingface.co/answerdotai/ModernBERT-base)
- On GPU, SetFit bge-small inference took 0.46 ms per sentence against 31 ms for bart-large-mnli zero-shot. — [SetFit docs](https://huggingface.co/docs/setfit/main/en/how_to/zero_shot)
- Zoning emails (dropping quoted text and signatures) improves request detection. — [Lampert et al. 2010](https://aclanthology.org/N10-1142/)

###### Inferences
- **Latency at 512 tokens** (estimate, not sourced): a base encoder (110–150M params) on a modern 4–8-core CPU probably takes about 50–300 ms per email in FP32 PyTorch, and less with ONNX INT8. Attention cost grows quadratically, so 1,024–2,048 tokens with ModernBERT costs several times more but stays well under a second or two. At a few hundred per day, throughput is not a constraint.
- **Zero-shot NLI cost**: NLI runs one forward pass per candidate label. With 2 labels on long text, the cost is about 2x a fine-tuned classifier. GLiClass avoids this with a single pass.
- **Long text — recommendation**:
  1. Strip quoted history and signatures (talon).
  2. Feed the last about 400–512 tokens of the engineer's own text, where questions, requests and closings usually sit.
  3. Optionally add a second pass that max-pools the positive probability over 512-token chunks, to catch mid-email questions.
  4. Use ModernBERT at 1–2k tokens if most cleaned replies fit, since it avoids chunking. Benchmark on your own CPU.
- **Deployment**: export with `optimum-cli export onnx --model <dir> --task text-classification`, then run dynamic INT8 quantisation (`ORTQuantizer` with `AutoQuantizationConfig.avx2/avx512_vnni(is_static=False)`). Serve from a small FastAPI process; GPU is not needed. SetFit models can likewise export their Sentence Transformer body to ONNX.

###### Gaps
- No verified, recent CPU benchmark was found for ModernBERT-base or DeBERTa-v3-base at 512 or 1,024 tokens. Benchmark locally.
- ONNX export support for ModernBERT in Optimum was not verified in this session.

##### 7. Licenses for commercial use

###### Takeaway
All mainstream candidates are permissively licensed (MIT or Apache 2.0). The nuance is training-data provenance for some zero-shot models; use the MoritzLaurer "-c" variants or GLiClass, which states commercial-OK data, if that matters.

###### Cited Findings
- MoritzLaurer deberta-v3-*-zeroshot-v2.0: MIT on the base model. "-c" variants use only commercially friendly data; non-"-c" variants include ANLI, WANLI and LingNLI. — [HF card](https://huggingface.co/MoritzLaurer/deberta-v3-large-zeroshot-v2.0)
- MoritzLaurer ModernBERT-large-zeroshot-v2.0: Apache 2.0, though the training mix includes the non-"-c" datasets. — [HF card](https://huggingface.co/MoritzLaurer/ModernBERT-large-zeroshot-v2.0)
- answerdotai/ModernBERT-base and -large: Apache 2.0. — [HF card](https://huggingface.co/answerdotai/ModernBERT-base)
- Knowledgator GLiClass v3.0: Apache 2.0, trained on synthetic and licensed data that allows commercial use. — [HF card](https://huggingface.co/knowledgator/gliclass-modern-large-v3.0); [README](https://huggingface.co/knowledgator/gliclass-base-v3.0/blob/main/README.md)

###### Inferences
- A fine-tuned model trained on your own (or Claude-labelled) data, built on an MIT or Apache base, is cleanly usable commercially. Check the Anthropic usage terms on using outputs to train models; classification-label distillation for internal use is typically the low-risk case.

###### Gaps
- These licenses were not verified in this session: facebook/bart-large-mnli (commonly MIT), microsoft/deberta-v3-base (commonly MIT), sentence-transformers/all-mpnet-base-v2 and BAAI/bge models (commonly Apache 2.0 / MIT), the SetFit library (commonly Apache 2.0), and talon. Confirm each on its model card or repo before adoption.

###### Summary comparison

All rows except the rules row are estimates for this task; "est." marks unsourced guesses.

| Approach | Labels needed | Expected quality on this task | Train cost | CPU inference | License |
|---|---|---|---|---|---|
| Rules (?, imperatives, courtesy lexicon) | 0 (plus a test set) | Low to moderate; fails on courtesy and imperative cases | None | Microseconds | N/A |
| NLI zero-shot (DeBERTa-v3 zeroshot-v2.0 "-c", ModernBERT-zeroshot) | 0 (plus a test set to tune hypotheses) | Moderate and unstable on pragmatic tasks (est.) | None | 2 passes per email; about 0.1–1 s at 512 tokens (est.) | MIT / Apache |
| GLiClass v3.0 | 0, LoRA-tunable | Moderate (est.); about 0.61–0.72 avg zero-shot F1 on benchmarks | None | Single pass | Apache 2.0 |
| SetFit (mpnet / bge) | 16–64 per class | Good; competitive with full fine-tuning at small n | Seconds to minutes | Fast | Apache / MIT (verify) |
| Fine-tuned ModernBERT-base / DeBERTa-v3-base | About 200–1,000 | Best local option; beat zero-shot GPT-4/Opus at 200–500 examples on specialised tasks | Minutes on Colab T4 (est.) | Tens to hundreds of ms; 2–3x faster with ONNX INT8 | Apache / MIT |
| Hybrid: fine-tuned encoder + calibrated threshold + LLM fallback | Same as above plus a calibration set | Highest, with an error budget | Same | Mostly local; small % escalated | — |


---

## Part 4: Hands-on test of Ollaya (2026-10-07)

After the research, Ollaya was installed and tested on this project's actual task.

### Setup
- **Ollaya v0.12.0** (released 2026-10-06). Repo `ollaya-dev/ollaya` verified: Apache-2.0, about 1.2k stars.
- Used the CPU zip `ollaya-windows-amd64.zip` instead of the `irm | iex` installer. The installer only unzips and edits PATH.
  - The zip's sha256 matched the release's `sha256sum.txt`.
  - It was unpacked to `.tools/ollaya`, which is git-ignored, and PATH was not changed.
- The server ran on `127.0.0.1:11435`, with models in `.tools/models`.
- Hardware: Intel i7-13620H (10 cores, 16 threads), 16 GB RAM, integrated graphics only, so CPU inference.
- Models pulled: `laya:en` (853 MB), `von` (1.6 GB), `nli:modernbert-large` (799 MB) and `gliclass` (1.8 GB).
  - Each took about 1.5–5 minutes to download.
  - The weights come from each author's Hugging Face repo, pinned and checked against sha256.
- **Laya's real context length is 512 tokens** (`ollaya show laya:en`), not the roughly 8k assumed in Part 3. Replies longer than that are rejected with `422`. `von` has an 8k context.

### Eval set
- 24 labelled engineer replies in `scripts/eval_classifier.py`:
  - 9 adapted from real Trinity replies.
  - 15 hand-written hard cases: courtesy questions ending in "?", asks without a question mark, rhetorical questions, a quoted customer question, "we will update you", an ask buried in the middle, and replies longer than 512 tokens.
- One `noul` question per call. A score of 0.5 or above counts as "awaiting customer".

### Whole-reply scoring (best wording per model)

| Model | Correct / 24 | Avg latency per call |
|---|---|---|
| `von` (criteria wording) | 21 | ~0.4 s |
| `nli:modernbert-large` (criteria wording) | 20 | ~0.6 s |
| `gliclass` (criteria wording) | 17 | ~0.4 s |
| `laya:en` (needs_info wording) | 15 | ~0.3 s |

Observations:
- **Laya itself performed worst on this task.** With a long, detailed instruction it scored 3/9 on the original cases, and its scores bunched around 0.5.
- **Wording mattered more than the model.** The same model swung from 4/9 to 9/9 depending on the question text, and shorter, literal wordings won. This matches TypeSafe's own note that Jev "reads instructions literally".
- **On the 9 original cases**, `nli:modernbert-large` and `von` each reached 9/9 with the right wording. Both dropped to about 20/24 once the hard cases were added, which shows how easily a small eval flatters a model.

### Improvements that worked
1. **Scoring each sentence separately and taking the highest score.** This catches asks that are buried mid-reply, and with `von` every genuine ask scored 0.67 or higher. On its own, though, it is fooled by courtesy questions ("Is there anything else I can help you with today?") and rhetorical questions.
2. **Removing stock courtesy sentences before scoring.** A small regex covers phrases like "any other questions", "anything else I can help with", "feel free to reach out" and sign-offs.
3. **Combining both scores:** P = mean(whole-reply score, best sentence score).

| `von` setup | Correct / 24 | Lowest score on an ask | Highest score on a non-ask |
|---|---|---|---|
| whole reply, courtesy stripped | 23 | 0.45 | 0.42 |
| best sentence, courtesy stripped | 22 | 0.67 | 0.87 |
| **mean of both (shipped)** | **23** | **0.61** | **0.55** |

- Run through the notifier's own code path (`notifier/systemone.py`), the shipped setup scores **23/24**, taking about **1 s per reply** on CPU.
- The two scores inside the uncertain 0.4–0.6 band were the rhetorical question (0.49) and the quoted customer question (0.55). These are what `SYSTEMONE_FALLBACK=claude` would send to Claude.
- The one wrong answer was the quoted customer question ("You asked whether you can get a refund… Yes: we've refunded…").

### Caveats and next steps
- The wording, the courtesy list and the thresholds were all tuned on the same 24 cases, so these numbers are optimistic. Next step: label 100–300 real engineer replies from Trinity and re-run the eval.
  - Keep that data out of git, because it contains customer email.
- With real labels, the stronger long-term option from Part 2 becomes possible: fine-tune ModernBERT-base on our own replies. Under TypeSafe's terms, those labels must never be Jev outputs.
- `decision` (Qwen3.5-0.8B) and larger decoders such as `winnow:e4b` were not evaluated; on this CPU they would take seconds per call.
