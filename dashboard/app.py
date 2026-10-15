"""The dashboard's HTTP server: JSON API, live stream (server-sent events), sign-in, and the built UI.

Read-only on everything the notifier does; the only writes are associates' feedback on alerts, sign-in
sessions, and a "Run check now" request for the notifier (dashboard/shiftviews.py).
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from aiohttp import web

USER = web.RequestKey("user", dict)

from .auth import COOKIE, AllowList, GoogleVerifier, is_loopback, new_token, token_hash
from .queries import Data
from .shiftviews import ShiftViews

log = logging.getLogger(__name__)

STATIC = Path(__file__).parent / "static"
STREAM_POLL_SECONDS = 1.0
STREAM_STATUS_EVERY = 10  # polls between status pushes
PUBLIC_API = {"/api/public", "/api/auth/google", "/api/auth/dev"}

CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' https://accounts.google.com/gsi/client",
    "style-src 'self' 'unsafe-inline' https://accounts.google.com/gsi/style",
    "frame-src https://accounts.google.com/gsi/",
    "connect-src 'self' https://accounts.google.com/gsi/",
    "img-src 'self' data: https://*.googleusercontent.com",
    "font-src 'self'",
    "base-uri 'none'",
    "frame-ancestors 'none'",
])


@dataclass
class Settings:
    google_client_id: str | None
    dev_login: bool
    session_hours: float
    bind_host: str


def _float(value: str | None, default: float, lo: float, hi: float) -> float:
    try:
        return min(hi, max(lo, float(value))) if value else default
    except ValueError:
        return default


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except ValueError:
        return None


def _date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


class Dashboard:
    def __init__(self, data: Data, allow: AllowList, settings: Settings, views: ShiftViews | None = None):
        self.data = data
        self.views = views
        self.allow = allow
        self.settings = settings
        self.google = GoogleVerifier(settings.google_client_id)

    # --- plumbing -----------------------------------------------------------------------------

    def app(self) -> web.Application:
        app = web.Application(middlewares=[self.headers_mw, self.auth_mw], client_max_size=64 * 1024)
        r = app.router
        r.add_get("/api/public", self.public)
        r.add_post("/api/auth/google", self.login_google)
        r.add_post("/api/auth/dev", self.login_dev)
        r.add_post("/api/auth/logout", self.logout)
        r.add_get("/api/me", self.me)
        r.add_get("/api/people", self.people)
        r.add_get("/api/status", self.status)
        r.add_get("/api/overview", self.overview)
        r.add_get("/api/alerts", self.alerts)
        r.add_get("/api/alerts/{id}", self.alert)
        r.add_post("/api/alerts/{id}/feedback", self.feedback)
        r.add_get("/api/activity", self.activity)
        r.add_get("/api/tickets/{ref}", self.ticket)
        r.add_get("/api/engineers", self.engineers)
        r.add_get("/api/shifts", self.shifts)
        r.add_get("/api/reports", self.reports)
        r.add_get("/api/checks/run", self.run_state)
        r.add_post("/api/checks/run", self.run_check)
        r.add_get("/api/stream", self.stream)
        if (STATIC / "assets").is_dir():
            r.add_static("/assets", STATIC / "assets", append_version=False)
        r.add_get("/{tail:.*}", self.index)
        return app

    @web.middleware
    async def headers_mw(self, request: web.Request, handler):
        resp = await handler(request)
        resp.headers.setdefault("Content-Security-Policy", CSP)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        # Google's sign-in button checks the Referer against the client's authorized origins: send the origin
        # (never the path) to other sites. "same-origin" sends nothing, and Google then refuses the button (400).
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        # Google's sign-in popup needs to talk back to this window.
        resp.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin-allow-popups")
        if request.path.startswith("/api/"):
            resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    @web.middleware
    async def auth_mw(self, request: web.Request, handler):
        if not request.path.startswith("/api/"):
            return await handler(request)
        if request.method == "POST" and request.headers.get("X-Requested-With") != "dashboard":
            # A custom header can't be sent cross-site without CORS approval: blocks forged form posts.
            raise web.HTTPForbidden(text="missing X-Requested-With")
        if request.path in PUBLIC_API:
            return await handler(request)
        user = self.current_user(request)
        if user is None:
            raise web.HTTPUnauthorized(text=json.dumps({"error": "sign in"}), content_type="application/json")
        request[USER] = user
        return await handler(request)

    def current_user(self, request: web.Request) -> dict | None:
        token = request.cookies.get(COOKIE)
        if not token:
            return None
        s = self.data.session(token_hash(token))
        if s is None or not self.allow.allows(s["email"]):  # removed from the list: access ends now
            return None
        return s

    def _secure(self, request: web.Request) -> bool:
        return request.secure or request.headers.get("X-Forwarded-Proto", "").lower() == "https"

    def _start_session(self, request: web.Request, email: str, name: str | None, picture: str | None) -> web.Response:
        token = new_token()
        self.data.create_session(token_hash(token), email.lower(), name, picture, self.settings.session_hours)
        resp = web.json_response(self._me(email, name, picture))
        resp.set_cookie(COOKIE, token, max_age=int(self.settings.session_hours * 3600), httponly=True,
                        samesite="Lax", secure=self._secure(request), path="/")
        log.info("signed in: %s", email)
        return resp

    def _me(self, email: str, name: str | None, picture: str | None) -> dict:
        return {"email": email.lower(), "name": name or self.data.name(email), "picture": picture,
                "teams": self.data.teams_for_associate(email)}

    def _dev_allowed(self, request: web.Request) -> bool:
        return self.settings.dev_login and is_loopback(self.settings.bind_host) and is_loopback(request.remote)

    # --- auth ---------------------------------------------------------------------------------

    async def public(self, request: web.Request) -> web.Response:
        return web.json_response({"google_client_id": self.settings.google_client_id,
                                  "dev_login": self._dev_allowed(request)})

    async def login_google(self, request: web.Request) -> web.Response:
        body = await request.json()
        try:
            claims = await self.google.verify(str(body.get("credential", "")))
        except Exception as e:
            log.warning("Google sign-in rejected: %s", e)
            return web.json_response({"error": "Google sign-in failed. Try again."}, status=401)
        email = claims["email"].lower()
        if not self.allow.allows(email):
            log.warning("sign-in refused (not on the list): %s", email)
            return web.json_response({"error": f"{email} isn't on the dashboard's access list."}, status=403)
        return self._start_session(request, email, claims.get("name"), claims.get("picture"))

    async def login_dev(self, request: web.Request) -> web.Response:
        if not self._dev_allowed(request):
            raise web.HTTPNotFound()
        email = str((await request.json()).get("email", "")).strip().lower()
        if not self.allow.allows(email):
            return web.json_response({"error": f"{email or 'That email'} isn't on the dashboard's access list."},
                                     status=403)
        return self._start_session(request, email, None, None)

    async def logout(self, request: web.Request) -> web.Response:
        token = request.cookies.get(COOKIE)
        if token:
            self.data.end_session(token_hash(token))
        resp = web.json_response({"ok": True})
        resp.del_cookie(COOKIE, path="/")
        return resp

    async def me(self, request: web.Request) -> web.Response:
        u = request[USER]
        return web.json_response(self._me(u["email"], u["name"], u["picture"]))

    # --- data ---------------------------------------------------------------------------------

    async def people(self, request: web.Request) -> web.Response:
        return web.json_response(self.data.people())

    async def status(self, request: web.Request) -> web.Response:
        return web.json_response(self.data.status())

    async def overview(self, request: web.Request) -> web.Response:
        q = request.query
        return web.json_response(self.data.overview(_float(q.get("hours"), 24, 1, 24 * 90), q.get("team") or None))

    async def alerts(self, request: web.Request) -> web.Response:
        q = request.query
        return web.json_response(self.data.alerts(
            rule=q.get("rule") or None, team=q.get("team") or None, engineer=q.get("engineer") or None,
            review=q.get("review") or None, q=q.get("q") or None,
            hours=_float(q.get("hours"), 0, 0, 24 * 365) or None,
            limit=int(_float(q.get("limit"), 60, 1, 200)), before_id=_int(q.get("before"))))

    async def alert(self, request: web.Request) -> web.Response:
        a = self.data.alert(_int(request.match_info["id"]) or -1)
        if a is None:
            raise web.HTTPNotFound()
        return web.json_response(a)

    async def feedback(self, request: web.Request) -> web.Response:
        body = await request.json()
        try:
            a = self.data.add_feedback(_int(request.match_info["id"]) or -1, str(body.get("verdict", "")),
                                       body.get("note"), request[USER]["email"])
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=400)
        if a is None:
            raise web.HTTPNotFound()
        return web.json_response(a)

    async def activity(self, request: web.Request) -> web.Response:
        q = request.query
        kinds = [k for k in (q.get("kinds") or "").split(",") if k]
        return web.json_response(self.data.activity(
            after_id=_int(q.get("after")), before_id=_int(q.get("before")), kinds=kinds or None,
            rule=q.get("rule") or None, team=q.get("team") or None, limit=int(_float(q.get("limit"), 150, 1, 500))))

    async def ticket(self, request: web.Request) -> web.Response:
        t = self.data.ticket(request.match_info["ref"])
        if t is None:
            raise web.HTTPNotFound()
        return web.json_response(t)

    async def engineers(self, request: web.Request) -> web.Response:
        q = request.query
        return web.json_response(self.data.engineers(_float(q.get("hours"), 24 * 7, 1, 24 * 365),
                                                     q.get("team") or None))

    def _views(self) -> ShiftViews:
        if self.views is None:
            raise web.HTTPNotFound(text="shift views aren't set up")
        return self.views

    async def shifts(self, request: web.Request) -> web.Response:
        q = request.query
        return web.json_response(self._views().shifts(datetime.now(timezone.utc), q.get("team") or None,
                                                      q.get("roster") or None, request[USER]["email"]))

    async def reports(self, request: web.Request) -> web.Response:
        q = request.query
        return web.json_response(self._views().reports(datetime.now(timezone.utc), _date(q.get("from")),
                                                       _date(q.get("to")), _date(q.get("day")),
                                                       q.get("team") or None))

    async def run_state(self, request: web.Request) -> web.Response:
        return web.json_response(self._views().run_state())

    async def run_check(self, request: web.Request) -> web.Response:
        state, accepted = self._views().request_run(request[USER]["email"], datetime.now(timezone.utc))
        return web.json_response(state, status=202 if accepted else 429)

    async def stream(self, request: web.Request) -> web.StreamResponse:
        """Live feed: every new activity row as it is written, plus the notifier's status."""
        resp = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-store",
                                           "X-Accel-Buffering": "no"})
        await resp.prepare(request)
        last = _int(request.headers.get("Last-Event-ID")) or _int(request.query.get("after"))
        if last is None:
            last = self.data.last_activity_id()

        async def send(event: str, payload, event_id: int | None = None) -> None:
            head = f"id: {event_id}\n" if event_id is not None else ""
            await resp.write(f"{head}event: {event}\ndata: {json.dumps(payload, default=str)}\n\n".encode())

        try:
            await send("status", self.data.status())
            tick = 0
            while True:
                if self.current_user(request) is None:  # signed out, expired, or removed from the list
                    await send("signed_out", {})
                    break
                rows = self.data.activity(after_id=last, limit=200)
                for row in rows:
                    await send("activity", row, row["id"])
                    last = row["id"]
                tick += 1
                if tick % STREAM_STATUS_EVERY == 0:
                    await send("status", self.data.status())
                elif not rows:
                    await resp.write(b": keep-alive\n\n")
                await asyncio.sleep(STREAM_POLL_SECONDS)
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        return resp

    async def index(self, request: web.Request) -> web.StreamResponse:
        if request.path.startswith("/api/"):
            raise web.HTTPNotFound()
        page = STATIC / "index.html"
        if not page.exists():
            return web.Response(text="The dashboard UI isn't built yet: run `npm install` and `npm run build` "
                                     "in dashboard/web (see README).", content_type="text/plain")
        return web.FileResponse(page, headers={"Cache-Control": "no-cache"})
