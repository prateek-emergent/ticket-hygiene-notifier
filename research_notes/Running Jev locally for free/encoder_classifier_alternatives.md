# Encoder-Based (Non-Generative) Classifier Alternatives to Jev for "Genuine PENDING Request vs. Courtesy Close" Classification

Task framing used throughout: binary label on a support engineer's outbound reply. POSITIVE = reply asks the customer an open question or requests something the customer must supply (valid PENDING). NEGATIVE = reply resolves / informs and ends with only a courtesy close ("let me know if you have any other questions") or "we will get back to you". Volume: a few hundred per day; 100–1,500 words; data must stay on-prem. Research date: 2026-10-07.

## 1. Zero-shot NLI / universal classifiers: how well do they handle this pragmatic distinction?

### Takeaway
Off-the-shelf zero-shot NLI classifiers (MoritzLaurer zeroshot-v2.0, ModernBERT-zeroshot, GLiClass, bart-large-mnli) are commercially licensable and run on CPU. On benchmarks they do well on easy, topic-like tasks such as sentiment but noticeably worse on complex ones, and no source tests them on "genuine request vs. courtesy closing". Treat them as a weak baseline or a label-bootstrapping aid, not the production classifier. They also truncate at 512 tokens (DeBERTa), so the request may be cut off unless the input is pre-trimmed.

### Cited Findings
- **MoritzLaurer/deberta-v3-large-zeroshot-v2.0**: base model under the MIT license. Variants with a "-c" suffix were trained only on commercially friendly data (Mixtral-8x7B synthetic data plus MNLI and FEVER-NLI). Variants without "-c" also include ANLI, WANLI and LingNLI, which have more restrictive licensing. — [HF model card](https://huggingface.co/MoritzLaurer/deberta-v3-large-zeroshot-v2.0)
- Across 28 classification tasks it averages 0.676 macro-F1, against 0.497 for facebook/bart-large-mnli. Sentiment tasks score 0.923–0.988; complex tasks score much lower (manifesto: 0.258). — [HF model card](https://huggingface.co/MoritzLaurer/deberta-v3-large-zeroshot-v2.0)
- The v2.0 family comes in RoBERTa-base/large and DeBERTa-v3-base/large, each with and without "-c", plus BGE-m3 multilingual versions. Token limit is 512 for DeBERTa and 8,192 for BGE-m3. The card recommends RoBERTa variants with TEI containers for production speed. The hypothesis template is customizable, e.g. "This text is about {}". — [HF model card](https://huggingface.co/MoritzLaurer/deberta-v3-large-zeroshot-v2.0)
- **ModernBERT-large-zeroshot-v2.0**: Apache 2.0, 8k context, mean macro-F1 of 0.834 across 37 datasets. The author says it "performs slightly worse then DeBERTav3 on average" but is "multiple times faster and consumes multiple times less memory", reaching about 1,100+ samples/sec on an A100 at batch size 32. The author also says a newer version with better synthetic data, to make full use of the 8k window, is being prepared. Its training mix includes ANLI and WANLI, so it is not the "-c" commercially-clean data mix. — [HF model card](https://huggingface.co/MoritzLaurer/ModernBERT-large-zeroshot-v2.0)
- Paper "Building Efficient Universal Classifiers with Natural Language Inference" (Laurer et al.; arXiv 2312.17543; v1 2023-12-29, v2 2024-03-22): trained on 33 datasets with 389 classes, it improves zero-shot performance by 9.4%. The authors argue BERT-like models are the efficient alternative to LLMs when classification is the only goal, for both zero-shot and few-shot use. — [arXiv](https://arxiv.org/abs/2312.17543)
- **GLiClass v3.0** (Knowledgator): Apache 2.0, trained on synthetic and licensed data that permits commercial use. Sizes: edge (32.7M params), modern-base (151M), modern-large (399M), base (187M), large (439M). — [HF model card](https://huggingface.co/knowledgator/gliclass-modern-large-v3.0); [license README](https://huggingface.co/knowledgator/gliclass-base-v3.0/blob/main/README.md)
- GLiClass modern-large averages 0.6082 F1 in zero-shot, against 0.6821 for DeBERTa-v3-large zero-shot. The best v3.0 model reaches 0.7193. Throughput is about 43.8 examples/sec against about 6.03/sec for cross-encoders (A6000 GPU, batch size 1). Paper arXiv 2508.07662, dated 2025-08-11. — [HF model card](https://huggingface.co/knowledgator/gliclass-modern-large-v3.0)
- SetFit docs, dair-ai/emotion test set: bart-large-mnli zero-shot scored 37.65% accuracy, against 59.1% for "zero-shot" SetFit (bge-small trained on templated synthetic sentences). On GPU, bart-large-mnli took 31.2 ms per sentence against 0.46 ms for SetFit bge-small, about 67x slower. — [SetFit docs: zero-shot](https://huggingface.co/docs/setfit/main/en/how_to/zero_shot)
- Background on why this task is hard. Indirect requests such as "Can you open that window?" are literally questions but function as requests. Whether such a form counts as a request depends on context, and canonical forms can lead listeners to mistake intended questions for requests. — [Trott & Bergen, UCSD](https://pages.ucsd.edu/%7Ebkbergen/papers/trott_5_8.pdf)

### Inferences
- The target distinction is a speech-act / pragmatics judgement, not a topic. On "complex" tasks NLI zero-shot models fall to well below 0.7 F1 (manifesto: 0.258), so expect mediocre and unstable results without fine-tuning. Rough guess, not sourced: perhaps 65–80% accuracy, depending heavily on hypothesis wording.
- Hypothesis wording matters a lot. Candidate templates: "The writer is asking the customer to provide information or take an action." vs. "The writer is only offering further help and does not need a reply." Run several and compare on a labelled set.
- Zero-shot NLI probabilities come from entailment softmax and were not shown to be calibrated in any source found. If scores will be thresholded, recalibrate them (Platt / isotonic) on a labelled set.
- Use a "-c" (commercial-data) variant if training-data licensing provenance matters to legal review.
- 512-token truncation of 100–1,500-word emails is a real risk: the operative request is often near the end. Pre-trim to the last N sentences/paragraphs, or chunk.

### Gaps
- No published evaluation was found of NLI zero-shot models on email request detection, courtesy-closing detection, or support-ticket status classification.
- No source documents calibration (ECE / reliability) of MoritzLaurer or GLiClass probabilities.
- bart-large-mnli's exact license was not verified in this session (commonly listed as MIT; check the model card).

## 2. Few-shot and standard fine-tuning (SetFit, ModernBERT, DeBERTa-v3): labelled data, accuracy, training cost

### Takeaway
Fine-tuning is the strongest option. SetFit can be competitive with roughly 8–64 examples per class and trains in seconds to minutes. Full fine-tuning of DeBERTa-v3 / RoBERTa / ModernBERT on about 200–500 labelled examples consistently beat GPT-4 and Claude Opus zero-shot in a 2024 study, especially on specialised tasks. For this task, plan on about 300–1,000 labelled replies, roughly balanced, plus a held-out test set.

### Cited Findings
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

### Inferences
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

### Gaps
- No published learning curve was found specifically for email request vs. courtesy-close detection. The 200–500 figure comes from social-science text tasks.
- No verified CPU-only SetFit training times for 512-token inputs were found.
- No head-to-head SetFit vs. ModernBERT-base fine-tune result on email/support data was found.

## 3. Bootstrapping labels with an LLM (one-off) or weak rules, then distilling; active learning

### Takeaway
"LLM labels a few hundred to few thousand historical examples, then train a small encoder on them" is an established, documented pattern. Mixing LLM labels with even a small human-verified set beats either alone. The main risks are systematic LLM label errors, which the student learns faithfully, and having no clean test set.

### Cited Findings
- Huang, Tang & Chen (arXiv 2402.09282v4, 2024-03-24): GPT-4 annotated CoNLL data. GPT-4 itself scored F1 0.65 (standard prompting) and 0.73 (chain-of-thought). BERT trained on human labels scored 0.850, and BERT trained sequentially on GPT-4-distilled data then original data scored 0.869. The authors warn LLM output "can still be unstable" and hallucinates, and recommend tiered selection, prompt refinement, embedding-similarity few-shot example selection and active learning. Note this is an NER task, not text classification. — [arXiv 2402.09282v4](https://arxiv.org/html/2402.09282v4)
- A related study, "Knowledge Distillation in Automated Annotation: Supervised Text Classification with LLM-Generated Training Labels", trained BERT/RoBERTa/DistilBERT on 1,000 LLM-labelled samples and compared them with 250 and 1,000 human-labelled samples. Only a secondary summary was accessed, and its numerical results were not retrieved. — [secondary review](https://www.themoonlight.io/en/review/knowledge-distillation-in-automated-annotation-supervised-text-classification-with-llm-generated-training-labels)
- Bucher & Martini found fine-tuned encoders trained on 200–500 examples beat zero-shot Claude Opus and GPT-4 on specialised tasks. This implies a well-trained student can match or exceed a zero-shot teacher, provided the training labels are accurate. — [arXiv 2406.08660v2](https://arxiv.org/html/2406.08660v2)

### Inferences
- Recommended bootstrap pipeline:
  1. Pull about 1,000–2,000 historical replies, keeping only the engineer-authored text.
  2. Have Claude label each with a strict rubric that includes edge cases: courtesy closes, "we will get back to you", rhetorical questions, embedded imperatives like "please share your job ID", conditional asks like "if the issue persists, send logs". Ask for a label plus a short rationale.
  3. Have a human audit a stratified sample of about 200, including all low-confidence or disagreement cases, and fix the rubric.
  4. Keep a human-verified test set of about 150–300 that is never used for training.
  5. Train SetFit or ModernBERT on the LLM-labelled set.
  6. Use active learning: route the student's uncertain predictions (0.35–0.65) and LLM/student disagreements to human review, add the corrections, and retrain weekly or monthly.
- Historical ticket outcomes can serve as weak labels. Did the customer reply next? Was the ticket later reopened? These are noisy and need checking against the rubric.
- Risk: sending historical emails to Claude once is still a data transfer outside the environment. That must be acceptable under the data-residency constraint; otherwise use a self-hosted LLM for the one-off labelling.

### Gaps
- No text-classification-specific numbers were found on LLM-label noise rates for email intent tasks.
- No source quantified the effect of active learning on this kind of task.

## 4. Rule-based and linguistic baselines (question marks, imperatives, dialogue-act models) and their failure modes

### Takeaway
Rules (a "?" in the final paragraphs, imperatives like "please share/send/confirm", courtesy-close regex blacklists) make a cheap, interpretable first pass and a useful feature or guardrail. They fail on exactly the hard cases: courtesy questions, rhetorical questions, imperatives with no question mark, and conditional asks. Off-the-shelf dialogue-act models are trained on spoken conversation (Switchboard/MIDAS/SILICONE) and transfer poorly to support emails.

### Cited Findings
- Hugging Face hosts dialogue-act classifiers fine-tuned on SILICONE (DeBERTa) and MIDAS (RoBERTa, XLM-RoBERTa) data. — [PyPI cltl.dialogueclassification](https://pypi.org/project/cltl-dialogueclassification)
- One dialogue system team found a dialogue-act classifier conditioned on user and bot utterances "didn't work well for question recognition". They instead fine-tuned RoBERTa on simplified dialogue-act data as a binary question/not-question task. — [arXiv 2008.12348](https://arxiv.org/pdf/2008.12348)
- The Switchboard Dialog Act Corpus tags turns/utterances with dialogue acts that summarise syntactic, semantic and pragmatic information. — [HF dataset cgpotts/swda](https://huggingface.co/datasets/cgpotts/swda/blob/main/swda.py)
- Email request detection is more accurate when quoted text, signatures and other zones are separated out (83.76% after zoning, up 15.9% relative). — [Lampert et al., NAACL 2010](https://aclanthology.org/N10-1142/)
- Indirect requests ("Can you…?") are literally questions but function as requests. Classifying their intent is context-dependent; one acoustic-feature classifier reached 74%. — [Trott & Bergen](https://pages.ucsd.edu/%7Ebkbergen/papers/trott_5_8.pdf)
- Rhetorical questions are indirect speech acts: rhetorical assertion, command, stance or emotion. — [search summary of rhetorical-question literature](https://meikai.repo.nii.ac.jp/records/2000304) (secondary; not fetched in full)
- Lexical and syntactic politeness features (indirection, deference, modality, e.g. "could you please") reach near-human politeness classification. These are candidate features for spotting softened requests. — [Danescu-Niculescu-Mizil et al. 2013, arXiv 1306.6078](https://arxiv.org/abs/1306.6078?context=cs); [conversational-featurizer docs](https://conversational-featurizer.readthedocs.io/en/latest/features_conceptual/politeness_strategies.html)
- `talon` (Mailgun) extracts quoted replies (`quotations.extract_from_plain/html`) and signatures (brute-force `extract_signature`, which works "90% of the time"; ML mode via `talon.init()`). A maintained fork, `great-talon`, exists. — [PyPI talon](https://pypi.org/project/talon/); [GitHub mailgun/talon](https://www.github.com/mailgun/talon)

### Inferences
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

### Gaps
- No published dialogue-act model trained on support or business email with a "request for information" vs. "conventional closing" distinction was found.
- No quantitative failure-rate figures for question-mark baselines on email were found.
- talon's license was not verified in this session.

## 5. Hybrid design: local classifier plus confidence threshold, escalating uncertain cases to an LLM

### Takeaway
Cascades (small model first, defer to a bigger model when confidence is low) are a standard, well-studied pattern. Their weak point is calibration: the threshold must be tuned per domain, and naive softmax confidence is miscalibrated. Conformal prediction gives a principled deferral rule with an error-rate guarantee.

### Cited Findings
- Cascades cut cost by routing easy queries to a small model and deferring hard ones. Production cascades use a confidence threshold, but scores are miscalibrated, the threshold needs per-domain tuning, and naive thresholds give no accuracy bound. "Conformal Cascade" defers whenever the calibrated prediction set has more than one label, with a distribution-free error guarantee. — [Conformal Cascade, arXiv 2607.25018 (submitted 2026-07-31)](https://www.alphaxiv.org/abs/2607.25018)
- "Early abstention" in cascades trades a higher abstention rate for significant cost and error reductions. — [Cost-Saving LLM Cascades with Early Abstention, arXiv 2502.09054](https://arxiv.org/html/2502.09054v2)

### Inferences
- Concrete design:
  1. Preprocess: talon strip, then take the last about 512 tokens of the engineer's own text.
  2. Run the fine-tuned ModernBERT/DeBERTa/SetFit model on CPU.
  3. Calibrate probabilities on a held-out human-labelled set (temperature scaling or isotonic).
  4. Auto-accept if p ≥ τ_hi or p ≤ τ_lo, and escalate the middle band to the existing Jev or LLM path, or to a self-hosted LLM if data must stay local.
  5. Pick τ so the auto-accepted error rate is at or below the target (e.g. 2%), or use split-conformal prediction with α = 0.02 and defer whenever the set is {0,1}.
  6. Log escalated cases with the LLM's verdict as new training labels (active-learning loop).
- At a few hundred per day, even a 10–20% escalation rate means only tens of LLM calls per day.
- The escalation rate itself should be monitored as a drift signal.

### Gaps
- No source gave escalation rates for an email-intent cascade. The rate has to be measured on your own data.

## 6. Inference stack: ONNX Runtime / Optimum, CPU latency, long-text handling

### Takeaway
At a few hundred emails per day, CPU inference for a base-size encoder is trivially cheap: tens to a few hundred ms per email, even unoptimised. ONNX plus INT8 quantisation gives about 2–3x more speed with negligible accuracy loss. Long-text handling matters more for accuracy than speed. Trimming to the last paragraphs after stripping quotes and signatures is probably better than feeding the full 8k context.

### Cited Findings
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

### Inferences
- **Latency at 512 tokens** (estimate, not sourced): a base encoder (110–150M params) on a modern 4–8-core CPU probably takes about 50–300 ms per email in FP32 PyTorch, and less with ONNX INT8. Attention cost grows quadratically, so 1,024–2,048 tokens with ModernBERT costs several times more but stays well under a second or two. At a few hundred per day, throughput is not a constraint.
- **Zero-shot NLI cost**: NLI runs one forward pass per candidate label. With 2 labels on long text, the cost is about 2x a fine-tuned classifier. GLiClass avoids this with a single pass.
- **Long text — recommendation**:
  1. Strip quoted history and signatures (talon).
  2. Feed the last about 400–512 tokens of the engineer's own text, where questions, requests and closings usually sit.
  3. Optionally add a second pass that max-pools the positive probability over 512-token chunks, to catch mid-email questions.
  4. Use ModernBERT at 1–2k tokens if most cleaned replies fit, since it avoids chunking. Benchmark on your own CPU.
- **Deployment**: export with `optimum-cli export onnx --model <dir> --task text-classification`, then run dynamic INT8 quantisation (`ORTQuantizer` with `AutoQuantizationConfig.avx2/avx512_vnni(is_static=False)`). Serve from a small FastAPI process; GPU is not needed. SetFit models can likewise export their Sentence Transformer body to ONNX.

### Gaps
- No verified, recent CPU benchmark was found for ModernBERT-base or DeBERTa-v3-base at 512 or 1,024 tokens. Benchmark locally.
- ONNX export support for ModernBERT in Optimum was not verified in this session.

## 7. Licenses for commercial use

### Takeaway
All mainstream candidates are permissively licensed (MIT or Apache 2.0). The nuance is training-data provenance for some zero-shot models; use the MoritzLaurer "-c" variants or GLiClass, which states commercial-OK data, if that matters.

### Cited Findings
- MoritzLaurer deberta-v3-*-zeroshot-v2.0: MIT on the base model. "-c" variants use only commercially friendly data; non-"-c" variants include ANLI, WANLI and LingNLI. — [HF card](https://huggingface.co/MoritzLaurer/deberta-v3-large-zeroshot-v2.0)
- MoritzLaurer ModernBERT-large-zeroshot-v2.0: Apache 2.0, though the training mix includes the non-"-c" datasets. — [HF card](https://huggingface.co/MoritzLaurer/ModernBERT-large-zeroshot-v2.0)
- answerdotai/ModernBERT-base and -large: Apache 2.0. — [HF card](https://huggingface.co/answerdotai/ModernBERT-base)
- Knowledgator GLiClass v3.0: Apache 2.0, trained on synthetic and licensed data that allows commercial use. — [HF card](https://huggingface.co/knowledgator/gliclass-modern-large-v3.0); [README](https://huggingface.co/knowledgator/gliclass-base-v3.0/blob/main/README.md)

### Inferences
- A fine-tuned model trained on your own (or Claude-labelled) data, built on an MIT or Apache base, is cleanly usable commercially. Check the Anthropic usage terms on using outputs to train models; classification-label distillation for internal use is typically the low-risk case.

### Gaps
- These licenses were not verified in this session: facebook/bart-large-mnli (commonly MIT), microsoft/deberta-v3-base (commonly MIT), sentence-transformers/all-mpnet-base-v2 and BAAI/bge models (commonly Apache 2.0 / MIT), the SetFit library (commonly Apache 2.0), and talon. Confirm each on its model card or repo before adoption.

### Summary comparison

All rows except the rules row are estimates for this task; "est." marks unsourced guesses.

| Approach | Labels needed | Expected quality on this task | Train cost | CPU inference | License |
|---|---|---|---|---|---|
| Rules (?, imperatives, courtesy lexicon) | 0 (plus a test set) | Low to moderate; fails on courtesy and imperative cases | None | Microseconds | N/A |
| NLI zero-shot (DeBERTa-v3 zeroshot-v2.0 "-c", ModernBERT-zeroshot) | 0 (plus a test set to tune hypotheses) | Moderate and unstable on pragmatic tasks (est.) | None | 2 passes per email; about 0.1–1 s at 512 tokens (est.) | MIT / Apache |
| GLiClass v3.0 | 0, LoRA-tunable | Moderate (est.); about 0.61–0.72 avg zero-shot F1 on benchmarks | None | Single pass | Apache 2.0 |
| SetFit (mpnet / bge) | 16–64 per class | Good; competitive with full fine-tuning at small n | Seconds to minutes | Fast | Apache / MIT (verify) |
| Fine-tuned ModernBERT-base / DeBERTa-v3-base | About 200–1,000 | Best local option; beat zero-shot GPT-4/Opus at 200–500 examples on specialised tasks | Minutes on Colab T4 (est.) | Tens to hundreds of ms; 2–3x faster with ONNX INT8 | Apache / MIT |
| Hybrid: fine-tuned encoder + calibrated threshold + LLM fallback | Same as above plus a calibration set | Highest, with an error budget | Same | Mostly local; small % escalated | — |
