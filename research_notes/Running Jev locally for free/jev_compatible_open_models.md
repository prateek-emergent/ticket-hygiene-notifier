# Open-weight, locally runnable Jev "System One"-compatible models and runtimes (as of 2026-10-07)

Context for the report writer: the use case is a binary `noul` classifier ("does the support engineer's reply ask the customer an open question?"), a few hundred calls/day, customer email text must stay in our environment, and free, CPU-friendly options are preferred. Fetches were done on 2026-10-07. Most HF and GitHub facts come from WebFetch summaries of the live pages, so exact numbers should be spot-checked before anyone acts on them. Items marked **UNVERIFIED** could not be confirmed from a primary source.

## Q0. Reference: Jev System One API shape and the MCA restriction

### Takeaway
TypeSafe's API is `POST /v1/systemone` with `state`, `model`, and `questions` (a map of typed `noul`/`choice`/`score` questions). It returns `answers` keyed by question id, plus probabilities and confidence. The Master Customer Agreement clause banning use of Jev outputs to train competing models could not be retrieved, so it rests on the brief's statement.

### Cited Findings
- Request top-level fields are `state` (string/object/array), `model` (e.g. `"jev-latest"`) and `questions` (a map). Question types: `noul` (`instructions`, optional `criteria` true/false), `choice` (`criteria` map of options, up to 255), `score` (ordered `criteria`, 2–10 levels) — [TypeSafe API reference](https://docs.typesafe.ai/api.md)
- The response has `model`, `answers` (keyed by question id) and `usage` (`input_tokens`, `output_tokens`). A noul answer returns `noul` (0–1). A choice answer returns `choice`, `probabilities` and `confidence`. A score answer returns `score` (probability-weighted), `legend`, `probabilities` and `confidence` — [TypeSafe API reference](https://docs.typesafe.ai/api.md)
- The endpoint is `https://api.typesafe.ai/v1/systemone` with Bearer auth. Jev is priced at $0.042/M input tokens and output is free (secondary source) — [digitalstrategy-ai.com, 2026-09-18](https://digitalstrategy-ai.com/2026/09/18/jev-system-one-model)
- TypeSafe says it trains Jev on 100% synthetic data (secondary source) — [llmreference.com](https://www.llmreference.com/provider/typesafe-ai/jev)
- TypeSafe's legal page links a Master Customer Agreement, a DPA and a Privacy Policy. The privacy policy description states "our commitment not to train models on user data" — [docs.typesafe.ai/legal.md](https://docs.typesafe.ai/legal.md)

### Inferences
- Any local replacement only has to emulate the `noul` answer (one probability) for this use case. Full `choice` and `score` fidelity is not needed.

### Gaps
- **UNVERIFIED:** the exact MCA clause prohibiting use of Jev outputs to train imitating or competing models. The legal index only links the documents, and `typesafe.ai/legal/master-customer-agreement` returned 404. The clause text, section number and effective date need to come from Legal or the signed contract.

## Q1. Cloudflare Clef and Clef-flash

### Takeaway
**Verified.** Cloudflare announced Clef (27B, post-trained from Qwen3.8-27B) and Clef-flash (9B, from Qwen3.5-9B) on 2026-10-01. Both are Apache 2.0 open weights on Hugging Face and are served on Workers AI using the Jev `/v1/systemone` request and response body. Cloudflare says they were trained on its own internal synthetic data, and no source mentions Jev distillation. However, self-hosting is documented on GPU (tested on a single H200), not CPU. Workers AI is hosted, so customer email would leave our environment.

### Cited Findings
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

### Inferences
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

### Gaps
- Not found in any fetched page: an official statement that Jev outputs were **not** used. Only the absence of any mention and the "internal synthetic datasets" wording were found.
- No official CPU or GGUF guidance and no RAM figures from Cloudflare. It is unknown whether any community GGUF keeps the joint head.
- The blog summary also mentioned "adapted the DiffusionGemma model to output deterministic probabilities", which is inconsistent with the Qwen base. This may be a summarizer artifact; reread the blog to confirm.
- One secondary source (developersdigest) implied Clef-flash has no vision encoder. This is contradicted by the HF card and the Workers AI page, which both say multimodal.
- HF org listing via `huggingface.co/api/models?author=cloudflare` returned `[]` (the org name is "Cloudflare", and the API is case-sensitive). The repo pages themselves resolved.
- No Hacker News thread was checked.

## Q2. Ollaya (local runner exposing the Jev API shape)

### Takeaway
**Verified.** Ollaya is an Ollama-style Rust daemon and CLI by Mert Cobanov, licensed Apache-2.0, with about 1.2k GitHub stars. It serves `/v1/systemone`, `/v1/decisions` and `/v1/models` wire-compatible with TypeSafe on `127.0.0.1:11435`. It runs ONNX and GGUF decision models, several of which are small encoders that run on CPU. It is the best fit for "local, free, CPU, same API". The provenance of each model has to be checked separately.

### Cited Findings
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

### Inferences
- For our use case, `ollaya run laya` on CPU behind `/v1/systemone` is the most direct free, local, Jev-shaped path.
- Laya's 193–464 ms per call on CPU is fine for a few hundred calls/day.
- Laya's context limit (ModernBERT is about 8k tokens) should cover 1–3k-token emails. This is not confirmed from the card.

### Gaps
- Not found: Ollaya release date or version history.
- Not found: a per-model provenance audit of the whole library (for example Kev, Von, `decider` by Mapika, `winnow`). Each model needs checking for Jev-distilled training before production use.
- It is unknown whether Ollaya packages Clef, Open-Jev or bekko.

## Q3. ZefanCai Open-Jev (CC0 data, Qwen adapters 2B/9B/27B)

### Takeaway
**Mostly verified.** Open-Jev is an independent reimplementation by Zefan Cai. The code is MIT, the weights are Apache-2.0, and the data is CC0 except for WANLI-derived rows, which stay CC BY 4.0. The data is mainly template- and procedurally-generated, and the project states it does not reproduce TypeSafe's weights or data. It ships rank-8 LoRA adapters plus a scalar head on Qwen bases (Apache-2.0). It includes its own `/v1/systemone` server, but the setup is Python/GPU-oriented.

### Cited Findings
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

### Inferences
- Legally, Open-Jev looks clean: independently generated CC0 data and Apache-2.0 Qwen bases.
- The WANLI subset carries CC BY 4.0 attribution obligations.
- Open-Jev-2B on CPU is possible but slow for long states. Expect a second or more per 2k-token email (inferred from the GPU latency figures).
- The distilled clone corpus `SargeDev/jev-distill-corpus-v3` includes 94,801 Open-Jev rows (see Q6). The flow is Open-Jev data into the clone, not the reverse.

### Gaps
- **Conflicting base for the 27B:** the GitHub summary says Qwen/Qwen3.5-27B, while the HF API tags show Qwen/Qwen3.8-27B. Needs checking on the model card.
- No GGUF or ONNX export from the author was found. Open-Jev cannot run in Ollama out of the box, because the LoRA plus scalar head needs the project's own loader.
- **Data-provenance mismatch:** one tool summary of the dataset card claimed "data appears synthetically generated via TypeSafe/Jev systems". That was the summarizer's inference, not a quote, and the GitHub README contradicts it. A human should read the dataset card's provenance section directly.
- **Name clash:** a different repo, `openjev/openjev` (and its GGUF/MLX/FP8 variants, plus `ggml-org/OpenJev-GGUF`), is **CC-BY-NC-4.0, so not for commercial use**. It must not be confused with ZefanCai Open-Jev — [HF API search](https://huggingface.co/api/models?search=Open-Jev)

## Q4. Small and CPU-oriented models: bekko-system-one, open-jev-deberta-v3-large, Jev-Style-Qwen3.5-2B

### Takeaway
All three appear to be trained on public NLP datasets with no Jev distillation documented, and all are CPU-capable.
- **bekko-system-one** (17M/68M/400M, ONNX) has **no license yet**, so it cannot be used commercially today. It also scores well below Jev.
- **open-jev-deberta-v3-large** (Kotoba Labs/Mithril) is Apache-2.0, 0.4B, CPU-runnable, with an ONNX build.
- **Jev-Style-Qwen3.5-2B** (chaoliangUNSW) is Apache-2.0 with GGUF builds and CPU support.

None of the three exposes `/v1/systemone` natively, so each needs a thin wrapper or Ollaya.

### Cited Findings

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

### Inferences
- **bekko:** not usable commercially until a license is assigned. Good to watch because the 17M/68M models are tiny on CPU.
- **open-jev-deberta-v3-large:** the most "boring and safe" CPU option. It is fine-tuned only on public datasets, and an ONNX build exists. Its training domain (banking intents, sentiment, BoolQ) is far from "does this reply ask an open question", so expect to fine-tune or calibrate on our own labeled emails.
- **Jev-Style-2B:** its 1,024-token prompt budget may truncate 1–3k-token emails, so input would need trimming (for example, only the engineer's reply, without quoted history).

### Gaps
- bekko CPU-specific latency: whether the 1.38 ms figure is CPU or GPU is unclear on the card.
- The licenses of the upstream training datasets for deberta and Jev-Style (for example, BoolQ's license) were not checked.
- It is unknown whether Ollaya packages any of these three models.

## Q5. TypeSafe's system-one-adapter-python

### Takeaway
**Partly verified.** It is an official TypeSafe Python package (`pip install 'system-one-adapter[openai]'`) that answers System One-style questions using ordinary LLM providers. It accepts a custom `base_url`, and custom endpoints default to Chat Completions, so Ollama, vLLM or llama.cpp servers should work. Its stated purpose is comparing TypeSafe against LLMs on cost, speed and intelligence, not production use. How it derives probabilities is not documented in the README.

### Cited Findings
- **Repo:** [github.com/typesafe-ai/system-one-adapter-python](https://github.com/typesafe-ai/system-one-adapter-python). The repo summary reports an MIT license, but the README fetch found no license text — [GitHub](https://github.com/typesafe-ai/system-one-adapter-python); [README raw](https://raw.githubusercontent.com/typesafe-ai/system-one-adapter-python/main/README.md)
- **Custom endpoints:** "Custom endpoints (including `OPENAI_BASE_URL`) default to Chat Completions. Pass `api="responses"` or `api="chat_completions"` to `OpenAIProvider`." The example given is `client.system_one(state, questions, model=OpenAIProvider("grok-4", base_url="https://api.x.ai/v1"))` — [GitHub](https://github.com/typesafe-ai/system-one-adapter-python); [README](https://raw.githubusercontent.com/typesafe-ai/system-one-adapter-python/main/README.md)
- **Options:**
  - `llm_answer_mode`: `"probabilities"` (a per-label distribution) or `"discrete"` (one value per question).
  - `structured_outputs=True` uses the provider's native structured-output mode.
  - Also `normalize_probabilities` and `n_retry_malformed_structure`.
  - It supports Noul, Choice and Score.
  - Sources: [GitHub](https://github.com/typesafe-ai/system-one-adapter-python); [README](https://raw.githubusercontent.com/typesafe-ai/system-one-adapter-python/main/README.md)
- **Purpose:** "Useful for comparing TypeSafe against an LLM on cost/speed/intelligence" — [README](https://raw.githubusercontent.com/typesafe-ai/system-one-adapter-python/main/README.md)

### Inferences
- The options `normalize_probabilities`, `n_retry_malformed_structure` and `structured_outputs` strongly suggest the LLM writes its probabilities as structured JSON (verbalized probabilities) rather than the adapter reading token logprobs. **UNVERIFIED**: the source code was not readable through the fetch tool.
  - If true, the probabilities are less calibrated than those from Jev, Clef or Laya.
  - It also means the model must reliably emit schema-valid JSON. Small local models on CPU may need retries.
- Ollama exposes an OpenAI-compatible `/v1` Chat Completions endpoint (default `http://localhost:11434/v1`) with JSON-schema structured outputs. That should make `OpenAIProvider("<ollama-model>", base_url="http://localhost:11434/v1")` work. This is general knowledge and was not verified against the adapter's tests.
- This path keeps data local and is free. However, it uses a generic chat LLM rather than a trained decision model, and it is officially framed as an evaluation tool.

### Gaps
- Not documented: the exact probability mechanism (verbalized JSON vs logprobs). Needs a read of the source (for example with `gh api` or a local clone).
- Not found: version or date and the PyPI release history.
- Not documented: whether a dummy API key is needed for local endpoints.

## Q6. Distilled clones (flag only — do not recommend)

### Takeaway
**Verified for autotrust/JEV-9B.** It is explicitly a student distilled from Jev 1.13 output distributions collected via OpenRouter. Its corpus `SargeDev/jev-distill-corpus-v3` has about 498k Jev-labeled rows. Using it could breach the MCA clause cited in the brief (clause text unverified), so this family is a legal risk.

### Cited Findings
- **autotrust/JEV-9B:**
  - Apache-2.0, based on Qwen3.5-9B.
  - Trained on `SargeDev/jev-distill-corpus-v3` (740,957 rows) with three streams: `yuri_v3` (498,010 rows of "TypeSafe Jev 1.13 full output distributions via OpenRouter"), `openjev_v2` (94,801 Open-Jev rows with programmatic CC0 labels) and `yuri_v1` (148,154 placeholder-labeled rows).
  - The card explicitly calls it a student distilled from Jev 1.13 outputs and says it is "not affiliated with, endorsed by, or a product of TypeSafe AI".
  - Source: [HF autotrust/JEV-9B](https://huggingface.co/autotrust/JEV-9B)
- **Related autotrust repos:** JEV-27B (created 2026-09-25, about 168k downloads), JEV-27B-VL (2026-09-30, about 1.5M downloads), JEV-9B (2026-09-23, about 313k downloads) and JEV-Gemma4-26B-A4B — [HF API search "jev"](https://huggingface.co/api/models?search=jev)

### Inferences
- The other autotrust variants probably share the same distillation provenance. This is **UNVERIFIED**; each card was not opened.
- Other community "Jev"/"OpenJev" models have **unknown provenance** and should be treated as risky until checked:
  - Meanblock/JEV-CPU
  - TokenRhythm/NeoHorse-Jev-4B
  - akhilaaa3/Jev-Omni
  - the apus-ailab/APUS-OpenJev-v1 series
  - alanhuangya/OpenJev-*, including the 4B built on jaredpalmer/kev-4b
- A high download count is not evidence of legal safety.

### Gaps
- The `SargeDev/jev-distill-corpus-v3` dataset card was not opened directly; the details come from the JEV-9B card.
- The provenance of the other autotrust and community models was not checked.
- The MCA clause text is unverified (see Q0).
