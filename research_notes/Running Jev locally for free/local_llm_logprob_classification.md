# Replicating Jev-style typed classification outputs (Noul / Choice / Score) with small open-weight LLMs run locally

Research date: 2026-10-07. Research was done on the open web (vendor docs, GitHub, arXiv, Hugging Face, practitioner blogs). The request snippets below are my own examples built from the parameters each project documents; I did not run them. Check them against the server version you install.

Mapping used throughout:
- **Noul (yes/no probability)**: ask a question that can only be answered "Yes" or "No", force a one-token answer, and read P("Yes") / (P("Yes") + P("No")) from next-token logprobs.
- **Choice (probability per option)**: label the options with single-token letters (A/B/C...) or single-token words, force one token, and softmax over the label tokens' logprobs.
- **Score (numeric)**: either (a) take the probability-weighted expected value over the digit tokens "1".."5" or "0".."9" (the "verbalization logprobs" idea below), or (b) constrain the output to a number with a regex or grammar and read it directly. Option (a) gives much better resolution than a bare verbalized number.

---

## Q1. Logprob/logit-based classification: reliability, calibration, best practices

### Takeaway
Reading next-token probabilities over a fixed label set is the standard, cheap way to get a probability-like score from an LLM, and it is generally better than asking the model to state a confidence number. The raw probabilities are biased by prompt format, label order and label frequency, so plan on a calibration step: contextual calibration with a content-free input, or temperature/Platt scaling on a few hundred labelled emails. The best 2026 result combines both signals: weight the verbalized confidence digits by their token probabilities.

### Cited Findings
- "Calibrate Before Use" (Zhao, Wallace, Feng, Klein, Singh; ICML 2021; arXiv Feb 19 2021, revised Jun 10 2021) found that few-shot LLM predictions are systematically biased toward labels that are frequent in the prompt (majority label), labels near the end of the prompt (recency), and tokens common in pre-training. They propose **contextual calibration**: run the prompt with a content-free input such as "N/A", record the label probabilities, and fit an affine correction that makes that output uniform. They report up to 30.0% absolute average-accuracy gains and lower variance across prompt formats. — [arXiv 2102.09690](https://arxiv.org/abs/2102.09690)
- Merdjanovska, Zaidan, Rücklé, "Evaluation Pitfalls and Sparsity Limitations in LLM-based Confidence Estimates for Classification" (arXiv Aug 5 2026; ACL 2026 Findings) compared verbalized confidence with token likelihood for classification. Verbalized confidence is **sparse**: "Qwen3-32B verbalizes only eight unique confidence values on SST-2, with over half being exactly 95%." — [arXiv 2608.04899](https://arxiv.org/abs/2608.04899)
- The same paper proposes **"verbalization logprobs"**, which weights the verbalized confidence digits by their token probabilities. Reported gains: +2.3 pts AUARC and +0.9 AUROC over vanilla verbalization, and +1.3 AUARC and +4.7 AUROC over plain token logprobs, at no extra inference cost. — [arXiv 2608.04899 (search abstract)](https://arxiv.org/pdf/2608.04899); [ACL Anthology 2026.findings-acl.1671](https://aclanthology.org/2026.findings-acl.1671/)
  - Note: the +1.3/+4.7 figures over token logprobs come from the search-engine summary of the abstract. The abstract page I fetched confirmed the +2.3 AUARC figure only.
- "Same Answer, Different Confidence: Protocol Sensitivity in LLM Confidence Calibration" (2026) warns that "token likelihood" is not a single baseline. Results depend on which answer is scored, how tokens are aggregated, the conditioning prompt, and the answer position. Different choices can change the comparison for the same model and dataset. — [arXiv 2605.27752](https://arxiv.org/pdf/2605.27752)
- Other 2025–2026 work on calibrating or training verbalized confidence: "Calibrating Verbalized Probabilities for LLMs" ([arXiv 2410.06707](https://arxiv.org/html/2410.06707v1)), ConfTuner ([arXiv 2508.18847](https://arxiv.org/html/2508.18847v1)), and "How do LLMs Compute Verbal Confidence?" (2026), which finds that verbal confidence carries information beyond token log-probabilities ([arXiv 2603.17839](https://arxiv.org/pdf/2603.17839v2)).
- Production precedent: IBM Granite Guardian models emit a yes/no verdict, and a risk probability is derived from the yes/no token logprobs (the docs show code requesting the top-20 logprobs, `nlogprobs=20`). An NVIDIA NIM example shows "risk detected? Yes" with "probability of risk: 0.995". — [HF model card granite-guardian-3.3-8b](https://huggingface.co/ibm-granite/granite-guardian-3.3-8b); [NVIDIA NIM Granite Guardian 3.0 8B](https://docs.api.nvidia.com/nim/reference/ibm-granite-guardian-3_0-8b)
- Practitioner write-up on using LLMs (including through Ollama) as classifiers via logprobs: [Gerard Simons, "LLMs as Classifiers (Part 2)", Medium](https://medium.com/@GerardSimons/llms-as-classifiers-part-2-d874d20cd3c9). There is also a small library, `ollama_classifier`, that wraps the Ollama backend for this ([readthedocs source](https://ollama-classifier.readthedocs.io/en/latest/_modules/ollama_classifier/backends/ollama.html)). I did not review either in detail.

### Inferences (best-practice checklist synthesized from the sources above plus standard practice; these are not each separately cited)
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

### Gaps
- I found no 2025–2026 paper with ECE numbers specifically for **small (≤9B) open models on support-ticket or email classification** using next-token label probabilities. We need to measure this ourselves on a labelled sample.
- I could not get the full results tables of Merdjanovska et al. (the second model name, the datasets beyond SST-2, ECE values).

---

## Q2. Serving stacks that expose token logprobs / constrained decoding locally

### Takeaway
All the major local stacks now expose top-k token logprobs:
- **vLLM** is the most complete. It has `logprobs`, `prompt_logprobs`, a `logprob_token_ids` parameter made for classification, `allowed_token_ids`, `logit_bias`, structured outputs with `choice`/regex/JSON, and dedicated `/classify` and `/score` endpoints. It is effectively GPU-oriented.
- **llama.cpp server** is the best CPU option. It has `n_probs`, GBNF `grammar` and `json_schema`, and OpenAI-compatible endpoints.
- **Ollama** added logprobs in **v0.12.11 (Nov 12, 2025)**. Older blog posts saying "Ollama has no logprobs" are outdated.

### Cited Findings
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

### Example request snippets (built from the documented parameters above; not run)

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

### Inferences
- **On CPU:** use llama.cpp's `llama-server` directly, or Ollama, which is built on llama.cpp. llama-server gives more control (grammar, `n_probs`, and slot/prompt caching so a shared system prompt is reused).
- **On a GPU:** use vLLM. `logprob_token_ids` and the `/classify` endpoint for fine-tuned sequence classifiers are a clean upgrade path.
- **SGLang** and **HF TGI** also implement OpenAI-style logprobs and grammar/JSON constraints according to their docs (see Gaps). **transformers** directly is the simplest route for a batch job: one forward pass, take `logits[0, -1, label_ids]`, softmax. No server is needed, and it works on CPU for models of 2B or less.

### Gaps
- I did not fetch SGLang or TGI docs in this pass, so their exact parameter names (e.g. SGLang `return_logprob`, `top_logprobs_num`, `regex`, `choices`; TGI `details`/`top_n_tokens`, `grammar`) are unverified here. Check them before relying on them. Also note that TGI went into maintenance mode in 2025 according to community reports; that is also unverified here.
- It is not confirmed from the docs whether Ollama's `/api/chat` (as opposed to `/api/generate`) returns logprobs. The release notes name `/api/generate` and the OpenAI-compatible API.
- It is not confirmed whether vLLM's OpenAI server accepts `logprob_token_ids` via `extra_body` in every version. The field is documented on SamplingParams.

---

## Q3. Best small open-weight models (2026) and licenses

### Takeaway
As of October 2026 the strongest commercially usable small families are **Qwen3.5 Small** (0.8B/2B/4B/9B, Apache 2.0, released Mar 2 2026) and **Gemma 4** (E2B/E4B, plus 26B-A4B MoE and 31B, **now Apache 2.0**, released Apr 2 2026). For short support-email classification, a 4B-class instruct model (Qwen3.5-4B or Gemma 4 E4B) is the natural default, with 9B as the accuracy step-up. Gemma 4's switch to Apache 2.0 makes older "Gemma license restrictions" notes outdated.

### Cited Findings
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

### Inferences
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

### Gaps
- I did not fetch the Qwen3.5 or Gemma 4 model cards on Hugging Face directly, so the license and sizes are from news and aggregator sources (consistent across several).
- No source compared Qwen3.5 vs Gemma 4 vs Llama/Phi/SmolLM3 specifically on **zero-shot classification calibration**.
- I did not verify the license status of Phi-4-mini, SmolLM3, Llama 3.x/4, Ministral or Granite 4 in this pass.

---

## Q4. Hardware for a few hundred calls/day with 1–3k token inputs

### Takeaway
Volume is tiny: 300 calls × ~2k tokens ≈ 600k input tokens/day, and each call generates only 1 token. Cost is dominated by **prompt processing (prefill)**, not generation.
- **CPU-only is feasible for an asynchronous or batch workflow** with a 1–4B model. Expect tens of seconds per 2k-token email on an older 4-core CPU, and much less on a modern 8–16-core CPU.
- **A single small GPU** (e.g. 20 GB RTX 4000 SFF Ada; Hetzner GEX44 at €184/mo) brings per-call latency to roughly a second or less.
- An existing developer laptop or a ~$40/mo VPS can handle this volume if latency is not critical.

### Cited Findings
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

### Inferences (back-of-envelope; validate with `llama-bench -p 2048 -n 1` on the target box)
- At ~43 tok/s prefill (3B Q4 on an old 4-core CPU), a 2k-token email takes **~45–50 s**. 300/day is ~4 CPU-hours/day: fine for a background queue, not for interactive use.
- A modern 8–16-core desktop or server CPU (AVX2/AVX-512) typically prefills several hundred tok/s for a 1–4B Q4 model, giving **a few seconds per email**. I have no verified source for this; benchmark it.
- **Reuse the shared prefix.** Put the fixed instructions and few-shot examples first and the email last, then use llama-server prompt caching or vLLM automatic prefix caching. Only the email tokens are new per call, and each extra question about the same email (Noul + Choice + Score) reuses the email prefix too, if the email comes before the question.
- **GPU:** a 4B–9B model in BF16 or FP8 fits easily in 16–24 GB. Prefill for 2k tokens on an RTX 4000-class card should be well under a second (inference; not measured in a cited source). €184/month is likely overkill for 300 calls/day unless latency matters.
- **Memory:** a 4B Q4_K_M GGUF is ~2.5–3 GB and an 8B Q4_K_M is ~5 GB (consistent with the 5.2 GB figure above), so 8–16 GB of RAM is enough for CPU serving.

### Gaps
- I found no verified 2026 CPU **prefill** benchmarks for Qwen3.5-2B/4B or Gemma 4 E2B/E4B GGUF at 2k-token prompts.
- No verified per-call latency numbers for small-GPU vLLM at a 2k-token prompt / 1 output token.

---

## Q5. Purpose-built open classifiers / judge / guard models that output label probabilities

### Takeaway
The most directly reusable pattern is **IBM Granite Guardian 3.3 8B** (Apache 2.0). It is a yes/no judge that accepts **custom criteria** and derives its probability from yes/no token logprobs, which is almost exactly a "Noul" primitive. vLLM's `/classify` and `/score` endpoints serve fine-tuned sequence-classifier and reward models, which is the upgrade path once we have labelled tickets.

### Cited Findings
- **Granite Guardian 3.3 8B** (Apache 2.0, released Aug 1 2025):
  - Outputs `<score>yes</score>` or `<score>no</score>`, with an optional `<think>` reasoning mode. Probability comes from token logprobs (examples use `nlogprobs=20`).
  - Supports "bring your own criteria" through `custom_criteria` in `guardian_config` passed to `apply_chat_template()`.
  - Benchmarks: harm detection F1 0.81 (no-think); RAG hallucination balanced accuracy 0.761 on LM-AggreFact; function-calling 0.74 balanced accuracy on fc-reward-bench.
  - Smaller relative: Granite-Guardian-HAP-38M (a hate/abuse/profanity classifier).
  — [HF model card](https://huggingface.co/ibm-granite/granite-guardian-3.3-8b)
- Granite Guardian 3.0 8B (Oct 2024): aggregate harm F1 0.67, average AUC 0.81 on RAG hallucination benchmarks. Example output "probability of risk: 0.995". Earlier 2B and 3.2-5B variants exist. — [NVIDIA NIM model card](https://docs.api.nvidia.com/nim/reference/ibm-granite-guardian-3_0-8b); [featherless granite-guardian-3.2-5b](https://featherless.ai/models/ibm-granite/granite-guardian-3.2-5b)
- Mozilla.ai's `any-guardrail` wraps Granite Guardian as a guardrail backend. — [any-guardrail docs](https://docs.mozilla.ai/any-guardrail/api-reference/index/granite-guardian)
- vLLM serves classification models via `/classify` and cross-encoder/reward scoring via `/score`. — [vLLM docs: Online Serving](https://docs.vllm.ai/en/latest/serving/online_serving/)

### Inferences
- For yes/no checks on support emails ("is this a refund request?", "is the customer angry?"), Granite Guardian 3.3 with custom criteria is a credible zero-training baseline. At 8B, though, it is heavier than a 4B general instruct model.
- Once a few hundred labelled emails exist, fine-tune a small encoder (e.g. ModernBERT/DeBERTa) or a 0.5–2B LLM with a classification head. It gives calibrated softmax outputs, millisecond CPU latency, and is servable via vLLM `/classify`. This matches the literature in Q6, where fine-tuned small models beat zero-shot.
- Other judge models (Prometheus 2, Llama Guard, Qwen3Guard, ShieldGemma) exist, but I did not verify their 2026 status or licenses in this pass. Llama Guard carries the Llama license.

### Gaps
- I did not verify the Prometheus-2, Qwen3Guard or ShieldGemma model cards, licenses or calibration results.
- I found no published calibration (ECE) results for Granite Guardian's probability on custom criteria.

---

## Q6. Published comparisons: small-LLM zero-shot classification vs API models

### Takeaway
The consistent finding (2024–2025) is that zero-shot small open LLMs trail API models on harder, many-label tasks. Small **fine-tuned** models, including BERT-class models, match or beat zero-shot GPT-4/Claude-class models when labelled data exists. For a few binary or low-cardinality questions, small zero-shot models are often adequate.

### Cited Findings
- Bucher & Martini, "Fine-Tuned 'Small' LLMs (Still) Significantly Outperform Zero-Shot Generative AI Models in Text Classification" (arXiv 2406.08660, Jun 2024): fine-tuned smaller models "consistently and significantly outperform" zero-shot GPT-3.5, GPT-4 and Claude Opus on sentiment, approval/disapproval, emotions and party positions. — [arXiv 2406.08660](https://arxiv.org/html/2406.08660v2)
- Lepagnol et al., "Small Language Models are Good Too: An Empirical Study of Zero-Shot Classification" (LREC-COLING 2024; arXiv 2404.11122) benchmarked 77M–40B parameter models on 15 datasets. Small models "can effectively classify texts, getting on par with or surpassing their larger counterparts." — [arXiv 2404.11122](https://arxiv.org/html/2404.11122v1); [ACL Anthology](https://preview.aclanthology.org/watermark/2024.lrec-main.1299)
- Vajjala & Shimangaud, "Text Classification in the LLM Era – Where do we stand?" (arXiv 2502.11830, Feb 2025):
  - Setup: 32 datasets in 8 languages; Qwen2.5-7B, Aya23-8B and Aya-Expanse-8B vs GPT-4 vs BERT/logistic regression.
  - Zero-shot GPT-4 was strong on sentiment but weak on many-label topic classification. Open 7–8B models "struggled across non-sentiment tasks".
  - Few-shot fine-tuning (FastFit) gave up to ~10% gains over zero-shot.
  - "Training classifiers using high-quality labeled data still gives the best performance."
  — [arXiv 2502.11830](https://arxiv.org/html/2502.11830v1)

### Inferences
- These comparisons mostly used Qwen2.5 and Llama 3-era models. The 2026 Qwen3.5/Gemma 4 small models are considerably stronger on general benchmarks, so the gap is likely narrower, but no cited 2026 study confirms it. Treat the findings as directional.
- Practical plan:
  1. Start zero-shot (or few-shot) with logprob reading on Qwen3.5-4B.
  2. Label 300–500 historical support emails, measure accuracy, ECE and Brier score against our current Jev outputs, and fit temperature/Platt calibration.
  3. If a question underperforms, fine-tune a small classifier on the accumulated labels.

### Gaps
- I found no 2026 head-to-head study of Qwen3.5/Gemma 4 small models vs frontier APIs on zero-shot classification calibration.
- I found no study using customer-support email data specifically.
