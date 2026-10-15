from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

from .detectors import Rule

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_rules_config(path: str | Path | None = None):
    """The root config.py switchboard, loaded by path so it never clashes with the config/ folder."""
    import importlib.util

    path = Path(path or os.getenv("RULES_CONFIG") or PROJECT_ROOT / "config.py")
    spec = importlib.util.spec_from_file_location("notifier_rules_config", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "THEMES") and hasattr(module, "RULES"):  # the switchboard's name before 2026-10-12
        module.THEMES = module.RULES
    unknown = set(module.THEMES) - {r.value for r in Rule}
    if unknown:
        raise SystemExit(f"{path}: unknown theme names in THEMES: {sorted(unknown)}")
    return module


PENDING_MODEL_KEYS = {"url", "english_model", "other_languages_model", "score_sentences", "api_key_env"}


def pending_model(rc, option: str | None = None) -> tuple[str, dict, str | None]:
    """Theme 1's model choice from config.py PENDING_MODEL: (option, its settings, API key or None).

    PENDING_MODEL_OPTION in the environment overrides the option for one run (used by the eval scripts)."""
    pm = rc.PENDING_MODEL
    option = (option or os.getenv("PENDING_MODEL_OPTION") or pm["option"]).strip().upper()
    if option not in pm["options"]:
        raise SystemExit(f"config.py PENDING_MODEL: option must be one of {sorted(pm['options'])}, not {option!r}")
    settings = pm["options"][option]
    missing = PENDING_MODEL_KEYS - set(settings)
    if missing:
        raise SystemExit(f"config.py PENDING_MODEL option {option}: missing {sorted(missing)}")
    key = None
    if settings["api_key_env"]:
        key = os.getenv(settings["api_key_env"]) or None
        if not key and Rule.PENDING_NO_QUESTION.value in {n for n, on in rc.THEMES.items() if on}:
            raise SystemExit(
                f"config.py PENDING_MODEL option {option} needs {settings['api_key_env']} in .env "
                "(or switch to another option)"
            )
    return option, settings, key


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    v = os.getenv(name)
    return default if not v else int(v)


@dataclass
class Config:
    trinity_url: str
    trinity_headers: dict[str, str]
    ticket_url_template: str
    slack_token: str | None
    slack_channel: str
    dry_run: bool
    classifier_model: str
    classifier_effort: str
    classifier_fallbacks: bool
    teams_file: Path
    state_db: Path
    poll_seconds: int
    initial_lookback: timedelta
    grace: dict[Rule, timedelta]
    human_domains: tuple[str, ...]
    enabled_rules: set[Rule] = field(default_factory=lambda: set(Rule))
    slack_api_url: str | None = None
    reassign_min_hold: timedelta = timedelta(minutes=2)
    pending_reply_window: timedelta = timedelta(minutes=30)
    alert_uncertain: bool = False
    classifier_backend: str = "systemone"
    pending_model_option: str = "A"
    systemone_url: str = "http://127.0.0.1:11435"
    systemone_model: str = "von"
    systemone_multilingual_model: str | None = "decider:4b"
    systemone_per_sentence: bool = True
    systemone_multilingual_per_sentence: bool = False
    systemone_timeout: float = 300
    systemone_api_key: str | None = None
    systemone_low: float = 0.4
    systemone_high: float = 0.6
    systemone_fallback: str = "none"
    shifts_file: Path = Path("config/shifts.xlsx")
    shifts_tz: str = "Asia/Kolkata"
    status_after: timedelta = timedelta(minutes=45)
    status_post_channel: bool = True
    status_dm: bool = True
    offshift_wait: timedelta = timedelta(hours=3)
    offshift_sweep: timedelta = timedelta(minutes=15)
    offshift_dm: bool = False
    l3_kb_dir: Path = Path("kb/escalation")
    l3_model: str = "jev-latest"
    l3_url: str = "https://litellm.central-infra-apps.emergentagent.com/typesafe"
    l3_api_key: str | None = None
    l3_fallback_model: str | None = "claude-opus-5-5"
    l3_min_confidence: str = "medium"
    held_min: timedelta = timedelta(minutes=30)  # theme 7: held longer than this before dropping it
    no_reply_after: timedelta = timedelta(minutes=60)  # theme 8: customer waiting this long with no reply
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8080
    webhook_token: str | None = None
    reconcile_minutes: int = 15
    due_tick_seconds: int = 15

    @classmethod
    def from_env(cls, env_file: str | None = ".env") -> "Config":
        if env_file and Path(env_file).exists():
            load_dotenv(env_file)
        url = os.getenv("TRINITY_MCP_URL")
        if not url:
            raise SystemExit("TRINITY_MCP_URL is not set (see .env.example)")
        token = os.getenv("TRINITY_MCP_TOKEN", "")
        header = os.getenv("TRINITY_AUTH_HEADER", "Authorization")
        scheme = os.getenv("TRINITY_AUTH_SCHEME", "Bearer")
        headers = {header: f"{scheme} {token}".strip()} if token else {}

        rc = load_rules_config()
        enabled = {Rule(name) for name, on in rc.THEMES.items() if on}
        holds = {"held_minutes": 30, "no_reply_minutes": 60} | dict(getattr(rc, "HOLDS", {}) or {})
        option, model, model_key = pending_model(rc)
        l3_key = os.getenv("JEV_API_KEY") or None
        for r in (Rule.L3_ESCALATION, Rule.ESCALATION_NOTE):
            if r in enabled and not l3_key:
                raise SystemExit(f"theme {r.value} is on: it judges with Jev, which needs JEV_API_KEY in .env")

        return cls(
            trinity_url=url,
            trinity_headers=headers,
            ticket_url_template=os.getenv(
                "TICKET_URL_TEMPLATE", "https://trinity-base.internal.emergent.host/tickets/{id}"
            ),
            slack_token=os.getenv("SLACK_BOT_TOKEN") or None,
            slack_channel=os.getenv("SLACK_CHANNEL", "#ticket-hygiene"),
            dry_run=_bool("DRY_RUN", True),
            classifier_model=os.getenv("CLASSIFIER_MODEL", "claude-opus-5-5"),
            classifier_effort=os.getenv("CLASSIFIER_EFFORT", "low"),
            classifier_fallbacks=_bool("CLASSIFIER_FALLBACKS", True),
            teams_file=Path(os.getenv("TEAMS_FILE", "config/teams.yaml")),
            state_db=Path(os.getenv("STATE_DB", "state.db")),
            poll_seconds=_int("POLL_SECONDS", 60),
            initial_lookback=timedelta(minutes=_int("INITIAL_LOOKBACK_MINUTES", 0)),
            grace={
                Rule.PENDING_NO_QUESTION: timedelta(minutes=_int("PENDING_GRACE_MINUTES", 5)),
                Rule.SELF_REASSIGN: timedelta(minutes=_int("REASSIGN_GRACE_MINUTES", 5)),
                Rule.OVERWATCH_CLOSE: timedelta(minutes=_int("CLOSE_GRACE_MINUTES", 1)),
                Rule.L3_ESCALATION: timedelta(minutes=rc.L3_ESCALATION["grace_minutes"]),
                Rule.ESCALATION_NOTE: timedelta(minutes=rc.L3_ESCALATION["grace_minutes"]),
                # theme 7: 5 min after the un-assign an escalation still counts, so look 6 min later
                Rule.HELD_THEN_DROPPED: timedelta(minutes=6),
                Rule.NO_REPLY: timedelta(minutes=holds["no_reply_minutes"]),
            },
            human_domains=tuple(
                "@" + d.strip().lstrip("@").lower()
                for d in os.getenv("HUMAN_EMAIL_DOMAINS", "emergent.sh").split(",")
                if d.strip()
            ),
            enabled_rules=enabled,
            slack_api_url=os.getenv("SLACK_API_URL") or None,
            alert_uncertain=_bool("ALERT_UNCERTAIN", False),
            pending_reply_window=timedelta(minutes=float(os.getenv("PENDING_REPLY_WINDOW_MINUTES", "30"))),
            reassign_min_hold=timedelta(minutes=float(os.getenv("REASSIGN_MIN_HOLD_MINUTES", "2"))),
            classifier_backend=os.getenv("CLASSIFIER_BACKEND", "systemone").strip().lower(),
            pending_model_option=option,
            systemone_url=model["url"],
            systemone_model=model["english_model"],
            systemone_multilingual_model=model["other_languages_model"] or None,
            systemone_per_sentence=model["score_sentences"],
            systemone_multilingual_per_sentence=False,  # both options read non-English replies whole
            systemone_timeout=float(os.getenv("SYSTEMONE_TIMEOUT_SECONDS", "300")),
            systemone_api_key=model_key,
            systemone_low=float(os.getenv("SYSTEMONE_LOW", "0.4")),
            systemone_high=float(os.getenv("SYSTEMONE_HIGH", "0.6")),
            systemone_fallback=os.getenv("SYSTEMONE_FALLBACK", "none").strip().lower(),
            shifts_file=Path(rc.SHIFTS["file"]),
            shifts_tz=rc.SHIFTS["timezone"],
            status_after=timedelta(minutes=rc.STATUS_CHECK["minutes_after_shift_boundary"]),
            status_post_channel=rc.STATUS_CHECK["post_to_channel"],
            status_dm=rc.STATUS_CHECK["dm_engineer"],
            offshift_wait=timedelta(hours=rc.OFF_SHIFT_HOLDING["customer_waiting_hours"]),
            offshift_sweep=timedelta(minutes=rc.OFF_SHIFT_HOLDING["sweep_minutes"]),
            offshift_dm=rc.OFF_SHIFT_HOLDING["dm_engineer"],
            l3_kb_dir=Path(rc.L3_ESCALATION["kb_dir"]),
            l3_model=rc.L3_ESCALATION["judge_model"],
            l3_url=rc.JEV_URL,
            l3_api_key=l3_key,
            l3_fallback_model=rc.L3_ESCALATION.get("fallback_model") or None,
            l3_min_confidence=rc.L3_ESCALATION["min_confidence"],
            held_min=timedelta(minutes=holds["held_minutes"]),
            no_reply_after=timedelta(minutes=holds["no_reply_minutes"]),
            webhook_host=os.getenv("WEBHOOK_HOST", "0.0.0.0"),
            webhook_port=_int("WEBHOOK_PORT", 8080),
            webhook_token=os.getenv("WEBHOOK_TOKEN") or None,
            reconcile_minutes=_int("RECONCILE_MINUTES", 15),
            due_tick_seconds=_int("DUE_TICK_SECONDS", 15),
        )

    def is_human(self, email: str | None) -> bool:
        return bool(email) and email.strip().lower().endswith(self.human_domains)

    def ticket_url(self, ticket_id: str, num: int | None) -> str:
        return self.ticket_url_template.format(id=ticket_id, num=num or "")
