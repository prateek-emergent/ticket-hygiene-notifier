import asyncio
import base64
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from aiohttp.test_utils import TestClient, TestServer

import notifier.webhook as webhook
from notifier.webhook import EventService, extract_ticket_ids

from .factory import Timeline
from .test_service import KRISHNA, RENUKA, FakeClassifier, FakeTrinity, make_monitor


def test_extracts_planned_ticket_updated_event():
    assert extract_ticket_ids({"id": "t1", "changedFields": {"status": "PENDING"}, "version": 3}) == ["t1"]


def test_ignores_changes_that_cannot_trigger_a_rule():
    assert extract_ticket_ids({"id": "t1", "changedFields": {"tags": ["billing"], "lastEventAt": "x"}}) == []


def test_prefers_ticket_id_over_event_id_for_timeline_events():
    assert extract_ticket_ids({"id": "evt9", "ticket_id": "t1", "action": "assigned"}) == ["t1"]


def test_unwraps_pusher_batches_and_pubsub():
    inner = {"events": [{"event": "ticket.updated", "data": {"id": "a", "changedFields": {"assignedTo": "x"}}},
                        {"ticket_id": "b"}, {"ticket_id": "a"}]}
    envelope = {"message": {"data": base64.b64encode(json.dumps(inner).encode()).decode(), "messageId": "m1"},
                "subscription": "projects/p/subscriptions/s"}
    assert extract_ticket_ids(envelope) == ["a", "b"]


def _service(tmp_path, token="s3cret"):
    monitor, notifier = make_monitor(tmp_path, FakeClassifier(awaiting=False))
    return EventService(monitor, token, reconcile_minutes=15, due_tick_seconds=1), notifier


async def _post(service, payload, headers=None, path="/trinity/events"):
    async with TestClient(TestServer(service.app())) as client:
        resp = await client.post(path, json=payload, headers=headers or {})
        return resp.status, await resp.json()


def test_rejects_missing_or_wrong_token(tmp_path):
    service, _ = _service(tmp_path)
    status, _ = asyncio.run(_post(service, {"ticket_id": "t1"}))
    assert status == 401
    status, _ = asyncio.run(_post(service, {"ticket_id": "t1"}, {"X-Webhook-Token": "nope"}))
    assert status == 401
    assert service.queue.empty()


def test_accepts_header_or_query_token(tmp_path):
    service, _ = _service(tmp_path)
    status, body = asyncio.run(_post(service, {"ticket_id": "t1"}, {"X-Webhook-Token": "s3cret"}))
    assert (status, body["queued"]) == (202, ["t1"])
    status, body = asyncio.run(_post(service, {"ticket_id": "t2"}, path="/trinity/events?token=s3cret"))
    assert (status, body["queued"]) == (202, ["t2"])


def test_push_event_schedules_check_and_alerts_after_grace(tmp_path, monkeypatch):
    # A reassignment that happened 10 minutes ago, i.e. its 5-minute grace has already passed.
    tl = Timeline("tk").customer(0).assign(1, KRISHNA, None, KRISHNA).assign(30, RENUKA, KRISHNA, RENUKA)
    shift = datetime.now(timezone.utc) - timedelta(minutes=10) - datetime.fromisoformat(tl.raw[-1]["created_at"])
    for r in tl.raw:
        r["created_at"] = (datetime.fromisoformat(r["created_at"]) + shift).isoformat()

    fake = FakeTrinity({"tk": tl})

    @asynccontextmanager
    async def fake_connect(url, headers):
        yield fake

    monkeypatch.setattr(webhook, "connect", fake_connect)
    monkeypatch.setattr(webhook, "BATCH_WINDOW_SECONDS", 0)
    service, notifier = _service(tmp_path)
    service.monitor.store.put("started_at", (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat())

    async def scenario():
        workers = [asyncio.create_task(service.ingest_worker()), asyncio.create_task(service.due_worker())]
        service.queue.put_nowait("tk")
        service.queue.put_nowait("tk")  # duplicate delivery
        for _ in range(50):
            if notifier.posts:
                break
            await asyncio.sleep(0.1)
        for w in workers:
            w.cancel()

    asyncio.run(scenario())
    assert len(notifier.posts) == 1
    assert "Taken from:* krishna@emergent.sh" in notifier.posts[0][1][1]["text"]["text"]
