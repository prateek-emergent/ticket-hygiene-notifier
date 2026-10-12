"""Rule-1 classifier backed by a "System One" decision model.

Speaks TypeSafe's `POST /v1/systemone` wire format, so the same code runs against:
  * Ollaya on localhost (free, local, data stays on the machine): http://127.0.0.1:11435
  * Jev through Emergent's LiteLLM (/typesafe), or any other service with the same API.
Which one is chosen in config.py PENDING_MODEL (option A: Ollaya, option B: Jev).

How a reply is scored (chosen on scripts/eval_classifier.py; see research.md for the background):
  1. Drop stock courtesy sentences ("let me know if you have any other questions", "is there anything
     else I can help with?"). Decision models read them as asks.
  2. Ask the model about the whole remaining reply, and separately about each sentence that could be an
     ask ("?", please, could you, confirm, send, ...). An ask is almost always one sentence, which a
     whole-email score dilutes when it is buried.
  3. P(awaiting customer) = mean(whole-reply score, highest sentence score; 0 if no sentence could be an ask).
Scores in the uncertain band [low, high) go to the fallback classifier (Claude) when configured.
"""

from __future__ import annotations

import asyncio
import logging
import re

import aiohttp

from .classifier import Verdict

log = logging.getLogger(__name__)

# Decision models read instructions literally; these wordings scored best for `von` (a ModernBERT-large
# decision model). A longer, "more complete" single instruction scored worse on every model tried.
WHOLE_QUESTION = {
    "instructions": "Is the support agent waiting on the customer?",
    "criteria": {
        "true": "The reply asks the customer a question or asks them to send, confirm, choose or try something.",
        "false": "The reply answers or resolves the issue, or says the support team will follow up; "
                 "at most it ends with a polite 'let me know if you need anything else'.",
    },
}
SENTENCE_QUESTION = {
    "instructions": "Does this sentence ask the customer for something the agent needs in order to continue?",
    "criteria": {
        "true": "It asks the customer a question, or asks them to send, confirm, choose or try something.",
        "false": "It informs, explains, apologises, says the team will act, or is a polite closing such as "
                 "'let me know if you have any other questions' or 'is there anything else I can help with?'.",
    },
}

# Stock courtesy sentences, which models read as asks. English plus the languages seen in Trinity replies
# (Italian, Spanish, Portuguese, French, German).
COURTESY_RE = re.compile(
    r"(anything else (i|we) can (help|do)|any (other|further|more) questions"
    r"|feel free to (reach out|reply|contact|get in touch)"
    r"|let (me|us) know if (you|there)('s| is| are| have)? ?(anything|any other|need)"
    r"|hope this helps|have a (great|nice|good) day|best regards|kind regards|thanks for building|just reply here"
    # it
    r"|(c'è|c'e) (qualcos'altro|altro|qualcosa) (con cui|in cui|per cui) (posso|possiamo)"
    r"|(non esitare|sentiti libero|sentitevi liberi) (a|di) (contattarci|scriverci|rispondere|ricontattarci)"
    r"|se (hai|avete) (bisogno|altre domande|altri dubbi)|rispondi pure qui|resto a disposizione|restiamo a disposizione"
    r"|cordiali saluti|un saluto|buona giornata"
    # es
    r"|algo más (en lo )?que (pueda|podamos) ayudar|no dudes en (escribirnos|contactarnos|responder|consultarnos)"
    r"|si (tienes|tiene|necesitas|necesita) (alguna|cualquier|otra|algo más)|responde aquí|quedo a (tu|su) disposición"
    r"|quedamos a (tu|su) disposición|un saludo|saludos cordiales|atentamente"
    # pt
    r"|(posso|podemos) ajudar em mais alguma coisa|fique à vontade para|se (tiver|precisar de) (alguma|outra|mais)"
    r"|é só responder aqui|atenciosamente|um abraço"
    # fr
    r"|(puis-je|pouvons-nous) vous aider (pour|à|sur) (autre chose|quoi que ce soit)|n'hésitez pas à"
    r"|si vous avez (d'autres|des|la moindre) (questions?|besoin)|répondez simplement ici|cordialement|bonne journée"
    # de
    r"|kann ich ihnen (heute )?(sonst|noch) (noch )?(irgendwie|etwas|weiter)|(melden|wenden) sie sich gerne"
    r"|bei (weiteren )?fragen|antworten sie (gerne|einfach) hier|viele grüße|mit freundlichen grüßen|freundliche grüße)",
    re.I,
)
SENTENCE_RE = re.compile(r"(?<=[.?!])\s+(?=[A-Z\"'(¿¡ÀÁÂÉÈÊÍÓÔÚÜÇÑ])")
QUOTE_HEADER_RE = re.compile(r"^(On .{5,200} wrote:|Il giorno .{5,200} ha scritto:|El .{5,200} escribió:"
                             r"|Em .{5,200} escreveu:|Le .{5,200} a écrit :|Am .{5,200} schrieb .{0,100}:)\s*$", re.M)

# Only sentences that could be an ask get their own model call. A decision model runs one forward pass
# at a time, so scoring every explanatory sentence of a long email made real replies take 10-60 s each.
ASK_HINT_RE = re.compile(
    r"[?¿]|\b(please|kindly|could you|can you|would you|will you|let (me|us) know|confirm|share|send|"
    r"provide|reply|respond|attach|upload|try|test|check|verify|clarify|forward|tell us|which|whether"
    # it / es / pt / fr / de
    r"|per favore|puoi|potresti|potete|conferma|confermare|invia|inviaci|mandami|mandaci|condividi|dimmi|dicci"
    r"|fammi sapere|fateci sapere|rispondi"
    r"|por favor|puedes|podrías|podría|confirma|confirme|envía|envíanos|comparte|dime|dinos|avísanos|indícanos|responde"
    r"|você pode|poderia|envie|compartilhe|nos diga|me diga|nos avise|responda"
    r"|merci de|pouvez-vous|pourriez-vous|confirmez|envoyez|indiquez|dites-nous|veuillez|répondez"
    r"|bitte|können sie|könnten sie|bestätigen sie|schicken sie|senden sie|teilen sie|sagen sie|antworten sie)\b",
    re.I,
)
MAX_CANDIDATES = 8
# The whole-reply call's cost grows with length (on a laptop CPU: ~0.5 s at 400 chars, ~6 s at 2,200).
# Its job is the overall gist near the end, where an ask or closing sits; buried asks are caught by
# the per-sentence calls. So only the last WHOLE_MAX_CHARS characters are sent.
WHOLE_MAX_CHARS = 1000

# Short-context models reject long states (422); we retry with the end of the text, halving each time.
MIN_RETRY_CHARS = 200
MAX_SENTENCES = 40
CONCURRENCY = 2
CACHE_SIZE = 512


# Language check: count each language's common function words, after removing what isn't prose. The
# languages are the ones seen in Trinity replies (2026-10-07 backtest: Italian, Spanish, Portuguese, French,
# German); anything that isn't clearly English goes to the multilingual model.
LANGUAGE_MARKERS = {
    "en": "the and to you your is are we our for of this that it with be have has will can please if not was "
          "from as at by or an so what when would could should there they them us".split(),
    "it": "il lo gli che non per con sono questo questa grazie ciao cordiali saluti puoi dimmi della nel ti "
          "abbiamo è sei".split(),
    "es": "el los las que por con para una gracias hola saludos puedes usted del al tu hemos está también".split(),
    "pt": "os as que para com você obrigado olá atenciosamente uma não do da no na seu sua está também".split(),
    "fr": "le les des que pour avec vous nous merci bonjour cordialement est une sur dans votre pas".split(),
    "de": "der die das und nicht mit ist sie wir danke hallo bitte ihr ihre ein eine den dem auf".split(),
    "tr": "ve bir bu için ile merhaba teşekkürler lütfen değil olarak çok".split(),
}
LANGUAGE_NAMES = {"en": "English", "it": "Italian", "es": "Spanish", "pt": "Portuguese", "fr": "French",
                  "de": "German", "tr": "Turkish"}
WORD_RE = re.compile(r"[a-zà-öø-ÿğışç']+")
NOT_PROSE_RE = re.compile(
    r"https?://\S+|www\.\S+|\S+@\S+\.\S+|`[^`]*`|```.*?```|\"[^\"]{40,}\"|“[^”]{40,}”|«[^»]{40,}»", re.S
)


def detect_language(text: str) -> str:
    """Best-guess language code ("en", "it", "es", ...); "en" when there's too little prose to tell."""
    words = WORD_RE.findall(NOT_PROSE_RE.sub(" ", text).lower())
    if len(words) < 6:
        return "en"  # "okay.", "Thanks!": too short to tell, and harmless to score as English
    counts = {lang: sum(w in markers for w in words) for lang, markers in LANGUAGE_MARKERS.items()}
    best = max(counts, key=counts.get)
    # Prefer English unless another language clearly wins: English replies quote Spanish/Italian words.
    return best if counts[best] > counts["en"] * 1.2 else "en"


def looks_english(text: str) -> bool:
    return detect_language(text) == "en"


def prepare(reply: str) -> list[str]:
    """Reply text -> the sentences worth scoring (quoted history and courtesy sentences removed)."""
    m = QUOTE_HEADER_RE.search(reply)
    if m:
        reply = reply[: m.start()]
    lines = [ln for ln in reply.splitlines() if not ln.lstrip().startswith(">")]
    text = " ".join(" ".join(lines).split())
    sentences = [s.strip() for s in SENTENCE_RE.split(text) if len(s.strip()) > 3]
    # Keep the end of very long replies: that is where the ask usually is.
    return [s for s in sentences if not COURTESY_RE.search(s)][-MAX_SENTENCES:]


class SystemOneClassifier:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        low: float = 0.4,
        high: float = 0.6,
        fallback=None,
        timeout_seconds: float = 120,
        multilingual_model: str | None = None,
        multilingual_per_sentence: bool = False,
        per_sentence: bool = True,
    ):
        self.url = base_url.rstrip("/") + "/v1/systemone"
        self.model = model
        # Non-English replies are scored by this model (None: they are skipped as uncertain).
        self.multilingual_model = multilingual_model
        # Sentence-by-sentence scoring compensates for an English encoder's weak spots; a multilingual LLM
        # (e.g. decider:4b) reads the whole reply well, and each extra call costs it ~5 s on a CPU.
        self.multilingual_per_sentence = multilingual_per_sentence
        self.per_sentence = per_sentence  # for the English model (`von` needs it)
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.low, self.high = low, high
        self.fallback = fallback
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._cache: dict[tuple[str, str], float] = {}

    async def health(self) -> str | None:
        """None if the decision model answers; otherwise what's wrong."""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5), headers=self.headers) as s:
                async with s.get(self.url.rsplit("/v1/", 1)[0] + "/v1/models") as resp:
                    if resp.status != 200:
                        return f"{self.url} answered HTTP {resp.status}"
                    data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            return f"cannot reach {self.url} ({type(e).__name__})"
        names = [m.get("name", "") or m.get("id", "") for m in data.get("models", data.get("data", []))]
        if names or "11435" in self.url:  # the models must be listed (Ollaya: installed locally)
            for model in filter(None, {self.model, self.multilingual_model}):
                if not any(n == model or n == f"{model}:latest" for n in names):
                    return f"model {model!r} is not installed (have: {', '.join(names) or 'none'})"
        return None

    async def _noul(self, session: aiohttp.ClientSession, state: str, question: dict, model: str | None = None) -> float:
        model = model or self.model
        body = {"model": model, "state": state, "questions": {"q": {"type": "noul", **question}}}
        async with session.post(self.url, json=body) as resp:
            if resp.status == 422 and len(state) > MIN_RETRY_CHARS:
                # Too long for this model's context: keep the end (where the ask is) and halve until it fits.
                shorter = state[-(len(state) // 2):].split(" ", 1)[-1]
                log.info("state too long for %s, retrying with the last %d chars", model, len(shorter))
                return await self._noul(session, shorter, question, model)
            if resp.status != 200:
                raise RuntimeError(f"{resp.status}: {(await resp.text())[:300]}")
            data = await resp.json()
        return float(data["answers"]["q"]["noul"])

    async def score(self, reply: str, model: str | None = None, per_sentence: bool = True) -> float:
        model = model or self.model
        if (model, reply) in self._cache:  # the same reply is often judged for several PENDING changes
            return self._cache[(model, reply)]
        sentences = prepare(reply)
        if not sentences:
            return 0.0  # nothing but courtesy text
        candidates = [s for s in sentences if ASK_HINT_RE.search(s)][-MAX_CANDIDATES:] if per_sentence else []
        sem = asyncio.Semaphore(CONCURRENCY)
        async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:

            async def one(state: str, question: dict) -> float:
                async with sem:
                    return await self._noul(session, state, question, model)

            body = " ".join(sentences)
            if len(body) > WHOLE_MAX_CHARS:
                body = body[-WHOLE_MAX_CHARS:].split(" ", 1)[-1]
            whole, *sentence_scores = await asyncio.gather(
                one(body, WHOLE_QUESTION), *(one(s, SENTENCE_QUESTION) for s in candidates)
            )
        if not per_sentence:
            p = whole  # whole-reply only (multilingual LLM)
        else:
            # No sentence even looks like an ask: the sentence-level evidence is "none".
            p = (whole + (max(sentence_scores) if sentence_scores else 0.0)) / 2
        if len(self._cache) >= CACHE_SIZE:
            self._cache.pop(next(iter(self._cache)))
        self._cache[(model, reply)] = p
        return p

    async def classify(self, reply_text: str, customer_text: str | None, subject: str) -> Verdict:
        lang = detect_language(reply_text)
        v = await self._classify(reply_text, customer_text, subject, lang)
        v.language = lang
        if v.model is None:
            v.model = self.multilingual_model if lang != "en" and self.multilingual_model else self.model
        elif self.fallback is not None and v.model == getattr(self.fallback, "model", None):
            v.model = f"{v.model} (fallback)"
        return v

    async def _ask_fallback(self, reply_text: str, customer_text: str | None, subject: str,
                            why: str | None = None) -> Verdict | None:
        """The fallback's verdict, or None when there is no usable fallback (none set, or its key was rejected).
        A failed fallback call is marked uncertain, so it is skipped like an unsure reply instead of alerted."""
        if self.fallback is None or getattr(self.fallback, "disabled", None):
            return None
        if why:
            log.warning("%s; using the fallback", why)
        try:
            v = await self.fallback.classify(reply_text, customer_text, subject)
        except Exception as e:
            log.warning("fallback failed: %s: %s", type(e).__name__, e)
            return Verdict(True, "", f"Check skipped: fallback failed ({e}).", "low", error=str(e), uncertain=True)
        if v.error:
            v.uncertain = True
        return v

    async def _classify(self, reply_text: str, customer_text: str | None, subject: str, lang: str) -> Verdict:
        model = self.model
        if lang != "en":
            # Non-English replies (mostly Italian and Spanish in Trinity) go to the multilingual model.
            if self.multilingual_model:
                model = self.multilingual_model
            elif (v := await self._ask_fallback(reply_text, customer_text, subject)) is not None:
                return v
            else:
                return Verdict(True, "", f"Reply is not in English ({lang}) and no multilingual model is set.",
                               "low", uncertain=True)
        try:
            per_sentence = self.per_sentence if lang == "en" else self.multilingual_per_sentence
            p = await self.score(reply_text, model, per_sentence)
        except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError, KeyError, ValueError) as e:
            if (v := await self._ask_fallback(reply_text, customer_text, subject, f"decision model failed ({e})")) is not None:
                return v
            # Usually Ollaya isn't running. Alerting here would send associates one "please review" per PENDING
            # change until it's back, so skip (logged as an error) instead. Start it: scripts\ollaya.ps1 start
            log.error(
                "decision model unreachable at %s (%s): PENDING check skipped. %s", self.url, e,
                "Check the network and API key." if self.headers else "Is Ollaya running?",
            )
            return Verdict(True, "", f"Check skipped: decision model unreachable ({e}).", "low",
                           error=str(e), uncertain=True)

        tag = model if lang == "en" else f"{model}, reply in {LANGUAGE_NAMES.get(lang, lang)}"
        if self.low <= p < self.high:
            if (verdict := await self._ask_fallback(reply_text, customer_text, subject)) is not None:
                verdict.probability = p
                return verdict
            # In the backtest the English false alarms all sat in this band, so: benefit of the doubt.
            return Verdict(True, "", f"Unclear whether the reply asks the customer anything ({tag}: {p:.0%}).",
                           "low", probability=p, uncertain=True)

        awaiting = p >= self.high
        confidence = "high" if (p >= (1 + self.high) / 2 or p < self.low / 2) else "medium"
        reason = (
            f"Reply appears to ask the customer something ({tag}: {p:.0%})."
            if awaiting
            else f"No question or request for the customer found in the reply ({tag}: {p:.0%} "
            "that it asks the customer anything)."
        )
        return Verdict(awaiting, "", reason, confidence, probability=p)
