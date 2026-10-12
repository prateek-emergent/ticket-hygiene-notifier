"""Sign-in: Google accounts on the allow-list only.

The browser gets an ID token from Google ("Sign in with Google"), the server verifies it (signature,
audience = our client id, issuer, verified email) and checks the email against config/dashboard_users.yaml.
It then issues its own session: a random token in an HttpOnly cookie, stored only as a hash.

The allow-list is re-read when the file changes, and every request re-checks it, so removing someone
from the file ends their access without a restart.

Local testing before a Google client id exists: DASHBOARD_DEV_LOGIN=true allows signing in as any
allow-listed email, only from this machine (loopback) and only while the server listens on loopback.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import logging
import secrets
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

COOKIE = "hygiene_session"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def is_loopback(host: str | None) -> bool:
    try:
        return ipaddress.ip_address((host or "").strip("[]")).is_loopback
    except ValueError:
        return host == "localhost"


class AllowList:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._mtime: float | None = None
        self._emails: set[str] = set()

    @property
    def emails(self) -> set[str]:
        try:
            mtime = self.path.stat().st_mtime
        except FileNotFoundError:
            if self._mtime is not None:
                log.warning("%s is gone: nobody can sign in", self.path)
            self._mtime, self._emails = None, set()
            return self._emails
        if mtime != self._mtime:
            doc = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
            self._emails = {str(e).strip().lower() for e in doc.get("allowed") or [] if str(e).strip()}
            self._mtime = mtime
            log.info("dashboard allow-list: %d email(s) from %s", len(self._emails), self.path)
        return self._emails

    def allows(self, email: str | None) -> bool:
        return bool(email) and email.strip().lower() in self.emails


class GoogleVerifier:
    def __init__(self, client_id: str | None):
        self.client_id = client_id

    async def verify(self, credential: str) -> dict:
        """The verified claims of a Google ID token; raises ValueError when it isn't valid for us."""
        if not self.client_id:
            raise ValueError("Google sign-in is not configured (GOOGLE_CLIENT_ID)")
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token

        def _verify() -> dict:
            # Checks the signature against Google's published keys, expiry, and audience.
            return id_token.verify_oauth2_token(credential, google_requests.Request(), self.client_id)

        claims = await asyncio.get_running_loop().run_in_executor(None, _verify)
        if claims.get("iss") not in GOOGLE_ISSUERS:
            raise ValueError("token not issued by Google")
        if not claims.get("email") or not claims.get("email_verified"):
            raise ValueError("Google account has no verified email")
        return claims
