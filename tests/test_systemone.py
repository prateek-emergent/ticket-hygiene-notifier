import asyncio

from aiohttp import web
from aiohttp.test_utils import TestServer

from notifier.classifier import Verdict
from notifier.systemone import SENTENCE_QUESTION, WHOLE_QUESTION, SystemOneClassifier, prepare


def test_prepare_drops_courtesy_quotes_and_signature():
    reply = (
        "We restored your data. Could you confirm the orders collection looks right? "
        "Let me know if you have any other questions. Is there anything else I can help you with today? "
        "Best regards, Emergent Support Team\n"
        "On Mon, 5 Oct 2026, 09:11 Customer <c@x.com> wrote:\n> where is my data??"
    )
    assert prepare(reply) == ["We restored your data.", "Could you confirm the orders collection looks right?"]


def test_prepare_only_courtesy_is_empty():
    assert prepare("Hope this helps! Have a great day.") == []


class FakeDecisionServer:
    """Answers /v1/systemone: whole-reply questions with `whole`, sentence questions by keyword."""

    def __init__(self, whole=0.2, asks=0.9, other=0.1, fail_status=None, max_state=None):
        self.whole, self.asks, self.other = whole, asks, other
        self.fail_status, self.max_state = fail_status, max_state
        self.requests = []

    async def handle(self, request):
        body = await request.json()
        self.requests.append(body)
        if self.fail_status:
            return web.json_response({"error": "boom"}, status=self.fail_status)
        if self.max_state and len(body["state"]) > self.max_state:
            return web.json_response({"error": {"code": "STATE_TRUNCATED"}}, status=422)
        q = body["questions"]["q"]
        if q["instructions"] == WHOLE_QUESTION["instructions"]:
            p = self.whole
        else:
            assert q["instructions"] == SENTENCE_QUESTION["instructions"]
            p = self.asks if "?" in body["state"] or "please" in body["state"].lower() else self.other
        return web.json_response({"model": body["model"], "answers": {"q": {"type": "noul", "noul": p}}})


async def _run(fake, coro_fn):
    app = web.Application()
    app.router.add_post("/v1/systemone", fake.handle)
    async with TestServer(app) as server:
        return await coro_fn(str(server.make_url("")))


class FakeFallback:
    def __init__(self):
        self.calls = 0

    async def classify(self, reply, customer, subject):
        self.calls += 1
        return Verdict(True, "q", "fallback says awaiting", "high")


def test_score_is_mean_of_whole_and_best_sentence():
    fake = FakeDecisionServer(whole=0.4, asks=0.9)
    reply = "We checked your account. Could you send the job ID? Thanks for your patience."

    async def go(url):
        return await SystemOneClassifier(url, "von").score(reply)

    assert abs(asyncio.run(_run(fake, go)) - 0.65) < 1e-9
    # whole reply + only the sentence that could be an ask ("Could you send the job ID?")
    assert len(fake.requests) == 1 + 1


def test_same_reply_is_scored_once():
    fake = FakeDecisionServer(whole=0.4, asks=0.9)

    async def go(url):
        clf = SystemOneClassifier(url, "von")
        return [await clf.score("Could you send the job ID?") for _ in range(3)]

    assert asyncio.run(_run(fake, go)) == [0.65, 0.65, 0.65]
    assert len(fake.requests) == 2


def test_confident_scores_decide_without_fallback():
    fallback = FakeFallback()

    async def go(url):
        clf = SystemOneClassifier(url, "von", fallback=fallback)
        yes = await clf.classify("Could you send the job ID?", None, "s")  # (0.9 + 0.9) / 2
        no = await clf.classify("We fixed it and redeployed.", None, "s")  # no ask-like sentence: (0.9 + 0) / 2
        return yes, no

    yes, no = asyncio.run(_run(FakeDecisionServer(whole=0.9, asks=0.9, other=0.1), go))
    # "no": whole=0.9 but nothing looks like an ask -> 0.45 -> uncertain -> fallback
    assert yes.awaiting_customer and yes.probability == 0.9
    assert fallback.calls == 1 and no.reason == "fallback says awaiting" and no.probability == 0.45


def test_uncertain_without_fallback_is_low_confidence():
    async def go(url):
        return await SystemOneClassifier(url, "von").classify("We fixed it and redeployed.", None, "s")

    v = asyncio.run(_run(FakeDecisionServer(whole=0.9, other=0.1), go))
    # benefit of the doubt: treated as awaiting the customer, flagged uncertain
    assert v.uncertain and v.confidence == "low" and v.awaiting_customer is True and v.probability == 0.45


def test_language_check():
    from notifier.systemone import looks_english

    assert looks_english("Run that, and send me the agent's plan and credit estimate when it comes back.")
    assert looks_english("okay.")
    assert not looks_english("Per controllarli mi serve la conferma di proprietà: mandami il suo codice di accesso.")
    assert not looks_english("Antes de generar la nueva build, sube el número de versión de la aplicación.")
    assert not looks_english("Si vous voulez un export plus récent, répondez à ce message en nous indiquant l'heure.")


def test_non_english_reply_is_uncertain_without_calling_model():
    fake = FakeDecisionServer()
    fallback = FakeFallback()
    italian = "Dimmi da quale punto vuoi ripartire e ti do il prompt per il tuo agente."

    async def go(url):
        alone = await SystemOneClassifier(url, "von").classify(italian, None, "s")
        with_fb = await SystemOneClassifier(url, "von", fallback=fallback).classify(italian, None, "s")
        return alone, with_fb

    alone, with_fb = asyncio.run(_run(fake, go))
    assert alone.uncertain and alone.awaiting_customer and "not in English" in alone.reason
    assert with_fb.reason == "fallback says awaiting" and fallback.calls == 1
    assert fake.requests == []


def test_only_courtesy_text_means_not_awaiting_without_calling_model():
    fake = FakeDecisionServer()

    async def go(url):
        return await SystemOneClassifier(url, "von").classify("Let me know if you have any other questions!", None, "s")

    v = asyncio.run(_run(fake, go))
    assert not v.awaiting_customer and v.probability == 0.0 and fake.requests == []


def _whole_states(fake):
    return [r["state"] for r in fake.requests if r["questions"]["q"]["instructions"] == WHOLE_QUESTION["instructions"]]


def test_long_reply_sends_only_its_end_as_the_whole_state():
    fake = FakeDecisionServer(whole=0.8, asks=0.8)
    reply = "Background detail sentence number one goes here. " * 60 + "Could you confirm the domain?"

    async def go(url):
        return await SystemOneClassifier(url, "von").score(reply)

    assert asyncio.run(_run(fake, go)) == 0.8
    [state] = _whole_states(fake)
    assert len(state) <= 1000 and state.endswith("Could you confirm the domain?")


def test_state_rejected_as_too_long_is_retried_shorter():
    fake = FakeDecisionServer(whole=0.8, asks=0.8, max_state=900)  # a model with a short context
    reply = "Background detail sentence number one goes here. " * 60 + "Could you confirm the domain?"

    async def go(url):
        return await SystemOneClassifier(url, "von").score(reply)

    assert asyncio.run(_run(fake, go)) == 0.8
    first, retry = _whole_states(fake)
    assert len(first) > 900 >= len(retry) and retry.endswith("Could you confirm the domain?")


def test_server_error_uses_fallback_or_flags_for_review():
    fallback = FakeFallback()

    async def go(url):
        with_fb = await SystemOneClassifier(url, "von", fallback=fallback).classify("Send logs?", None, "s")
        without = await SystemOneClassifier(url, "von").classify("Send logs?", None, "s")
        return with_fb, without

    with_fb, without = asyncio.run(_run(FakeDecisionServer(fail_status=500), go))
    assert with_fb.reason == "fallback says awaiting"
    # Model down and no fallback: skip (uncertain, logged) rather than alert on every PENDING change.
    assert without.error and without.uncertain and "skipped" in without.reason


# --- multilingual replies ----------------------------------------------------------------------


def test_language_detection_ignores_links_and_quoted_prompts():
    from notifier.systemone import detect_language

    assert detect_language("Hello Jean-Luc, here's your requested dump, it's a secure link only you can access "
                           "https://drive.google.com/drive/folders/13gE_j-sOEYP7lQx9aaaabbbbcccdddeeefff?usp=sharing") == "en"
    assert detect_language('Hola Francisco, copia y pega este mensaje en el chat del agente: "Add automatic '
                           'renewal to the subscription flow and do not create a second Stripe integration." '
                           "Con eso queda resuelto, un saludo.") == "es"
    assert detect_language("Grazie per averci contattato. Per favore condividi il Job ID dell'app.") == "it"


def test_multilingual_courtesy_and_ask_phrases():
    from notifier.systemone import ASK_HINT_RE, COURTESY_RE

    for courtesy in ("C'è altro con cui posso aiutarti oggi?", "¿Hay algo más en lo que pueda ayudarte hoy?",
                     "Posso ajudar em mais alguma coisa hoje?", "Puis-je vous aider pour autre chose aujourd'hui ?",
                     "Kann ich Ihnen heute sonst noch irgendwie helfen?"):
        assert COURTESY_RE.search(courtesy), courtesy
    for ask in ("Dimmi da quale punto vuoi ripartire.", "Mandami il link del progetto.", "Envíanos una captura.",
                "Merci de nous indiquer le Job ID.", "Bitte teilen Sie uns die Job-ID mit."):
        assert ASK_HINT_RE.search(ask), ask


def test_non_english_reply_goes_to_the_multilingual_model():
    fake = FakeDecisionServer(whole=0.9, asks=0.9)
    italian = "Grazie per averci contattato. Per favore condividi il Job ID dell'app interessata?"

    async def go(url):
        return await SystemOneClassifier(url, "von", multilingual_model="decider:4b").classify(italian, None, "s")

    v = asyncio.run(_run(fake, go))
    assert v.awaiting_customer and not v.uncertain and "Italian" in v.reason
    assert {r["model"] for r in fake.requests} == {"decider:4b"}


def test_english_reply_still_uses_the_english_model():
    fake = FakeDecisionServer(whole=0.9, asks=0.9)

    async def go(url):
        return await SystemOneClassifier(url, "von", multilingual_model="decider:4b").classify(
            "Could you send the job ID?", None, "s")

    asyncio.run(_run(fake, go))
    assert {r["model"] for r in fake.requests} == {"von"}
