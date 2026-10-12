# TypeSafe "Jev" (System One model): what it is, weights, license, and whether it can be self-hosted

Research date: 2026-10-07. All pages below were fetched on 2026-10-07 unless noted. The product is new: TypeSafe left stealth and announced Jev on 2026-09-15.

## 1. What exactly is Jev / a "System One" model?

### Takeaway
Jev is a proprietary, API-only "decision model" from TypeSafe AI, Inc. (San Francisco). It does not generate text. You send it a `state` and a map of typed questions (Noul, Choice, Score), and it returns calibrated probability distributions over the allowed answers in one parallel pass. TypeSafe describes the training method (RLCD) and a "new architecture with a parallel sampler" only at a high level. It does not disclose the parameter count, the base model (if any), or the internal architecture. The current version is `jev-1.13.0`.

### Cited Findings
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

### Inferences
- "No autoregressive decoding", "parallel sampler", "0 output tokens" and per-option probabilities all suggest that Jev scores each allowed answer in one forward pass, for example with classification heads or logit readout over a transformer. TypeSafe has not confirmed this, and it is my inference.
- TypeSafe's own claims ("calibrated", "zero hallucinations", the speed multiples) are vendor benchmarks. I found no independent verification.

### Gaps
- **Parameter count: not disclosed.** It is absent from the blog, the docs, the podcast and the Vercel card.
- **Base model: not disclosed.** I found no statement on whether Jev is a fine-tune of an open model or trained from scratch. The CEO calls RLCD "unpublished".
- **Internal architecture** beyond "new architecture with a parallel sampler": not disclosed. There is no paper or technical report.
- The blog page carries two dates (Sep 15 and Sep 28, 2026). Sep 15 is consistent with the launch reported by third parties.

## 2. Are Jev's weights published anywhere? Are there SDKs with local inference?

### Takeaway
No. TypeSafe has not published Jev's weights anywhere. The `typesafe` Hugging Face org exists but holds zero models, and every "Jev" model on Hugging Face is a third-party imitation. TypeSafe's GitHub org contains only MIT-licensed API clients, agent skills, integrations and an LLM-backed adapter. None of them performs local Jev inference.

### Cited Findings
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

### Inferences
- The adapter accepts `base_url`, so it could point at a local OpenAI-compatible server such as Ollama, vLLM or llama.cpp. That would let you keep the TypeSafe SDK interface (Noul, Choice, Score) on a free, local open-weight LLM. The result would be an LLM imitating Jev's interface, not Jev. Its probabilities come from the LLM's stated distributions, with normalization, rather than from calibrated RLCD outputs. The README does not explicitly document local servers; this is my inference from the `base_url` support.

### Gaps
- I did not read the SDK source code line by line. The conclusion that there is no local inference rests on the README and docs descriptions.

## 3. License and terms of service (self-hosting, data, distillation)

### Takeaway
Access is a revocable, limited license to use a hosted service. Nothing in the documents grants rights to weights or self-hosting. The Master Customer Agreement explicitly bans reverse engineering, model distillation, training a model to imitate Jev's outputs, and building competing products. TypeSafe commits not to train on customer inputs. Zero data retention is available to enterprise customers only.

### Cited Findings
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

### Inferences
- An MCA customer may not train a local model on Jev outputs. This covers anyone whose purpose is "running Jev locally for free" by distilling it. Third parties that distilled Jev (see section 5) appear to have done what the MCA forbids, if they were bound by it as customers, including through OpenRouter or other gateways, whose own terms may also pass through provider restrictions. Downloading and using their Apache-2.0-labeled weights carries **unclear legal provenance** risk: the uploader's license label may not override TypeSafe's contractual claims against the uploader. Whether TypeSafe has any claim against downstream users is a legal question I cannot settle; it is not legal advice.

### Gaps
- I did not find the full DPA text or the specific retention periods for API inputs.
- I did not check whether the gateway resellers (Vercel, Netlify, OpenRouter, DigitalOcean) impose TypeSafe's distillation ban through their own terms.

## 4. On-prem, VPC, bring-your-own-cloud, or air-gapped deployment?

### Takeaway
I found no evidence of any on-prem, VPC, BYOC or air-gapped offering for Jev. The only enterprise extras documented are higher rate limits, custom plans and ZDR through sales.

### Cited Findings
- The docs index has no pages on deployment, infrastructure, security or compliance, or enterprise tiers. — [llms.txt](https://docs.typesafe.ai/llms.txt)
- Enterprise mentions are limited to higher rate limits and ZDR ("contact sales"). — [docs: Models](https://docs.typesafe.ai/models.md); [docs: Legal](https://docs.typesafe.ai/legal.md)
- The homepage gives no information on on-prem, VPC or self-hosting. — [typesafe.ai](https://typesafe.ai/)
- The Latent Space interview has "No mention of self-hosting, on-premises, or VPC deployment options". — [Latent Space](https://www.latent.space/p/jev)
- A web search for "TypeSafe Jev enterprise VPC on-prem deployment self-hosted" (2026-10-07) returned nothing relevant.
- The closest thing to third-party hosting: Vercel lists DigitalOcean as a provider. That is still a hosted API, not customer-controlled. — [Vercel](https://vercel.com/ai-gateway/models/jev)

### Inferences
- A private deployment might be negotiable through enterprise sales, but nothing public says so. Treat Jev as SaaS-only.

### Gaps
- I did not look for a pricing page, which may not exist, or for direct sales or "contact us" terms on private deployment.

## 5. Community reproductions, open clones, and papers

### Takeaway
Within three weeks of launch, Hugging Face filled with unofficial "Jev" models and datasets. Many are LoRA or fine-tunes of open models such as Qwen 3.5 and 3.8, Gemma 4, DeBERTa-v3 and ModernBERT. Some are explicitly **distilled from Jev 1.13's API outputs**, which is legally risky given the MCA. Others are independent reimplementations trained on synthetic or public data, a cleaner basis for a free local "Jev-like" system. No TypeSafe paper exists.

### Cited Findings
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

### Inferences
- The general technique can be reproduced with open tools: score each allowed answer in one forward pass using classification heads or constrained logit readout over an open LLM or encoder, then calibrate with temperature scaling on a held-out calibration split. Several clones use exactly this pattern, with "dual-head" designs, calibration splits and ECE/Brier metrics. Jev's specific quality, which comes from RLCD and proprietary synthetic data, is not reproducible from public material.
- For a legally cleaner free local setup, there are two routes: (a) the official MIT `system-one-adapter` pointed at a local open-weight LLM, or (b) independently trained clones such as Open-Jev (CC0 data), the bekko encoders, or the DeBERTa or Jev-Style models trained on public datasets. Avoid models and datasets that are labeled as distilled from Jev 1.13.
- Download counts and the "indistinguishable by KL" claims are self-reported on the model cards and have not been verified independently.

### Gaps
- I did not verify how good the community clones are beyond their own cards, or the licensing terms of their base models (Qwen 3.5/3.8 and Gemma 4 licenses would govern).
- I found no Hacker News thread or independent evaluation comparing the clones with Jev.
- I did not read the GitHub `Open-Jev-Dev` repository in depth.
