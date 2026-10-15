"""Engineer -> associate/team-lead mapping, loaded from teams.yaml.

Only engineers listed here are monitored. Everyone else (other teams, associates, System) is ignored.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Team:
    name: str
    associates: list[str]
    engineers: list[str]


class Directory:
    def __init__(self, teams: list[Team], exempt_from_reassign: list[str] | None = None):
        self.teams = teams
        self._by_engineer: dict[str, Team] = {}
        for t in teams:
            for e in t.engineers:
                self._by_engineer[e.lower()] = t
        # Leads and associates reassign tickets as part of their job; never flag them for rule 2.
        self.reassign_exempt = {a.lower() for t in teams for a in t.associates}
        self.reassign_exempt |= {a.lower() for a in exempt_from_reassign or []}

    @classmethod
    def load(cls, path: str | Path) -> "Directory":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        teams = [
            Team(
                name=t["name"],
                associates=[a.lower() for a in t.get("associates", [])],
                engineers=[e.lower() for e in t.get("engineers", [])],
            )
            for t in data.get("teams", [])
        ]
        return cls(teams, data.get("exempt_from_reassign_rule", []))

    @property
    def engineers(self) -> list[str]:
        """Every monitored engineer (lower-case), sorted."""
        return sorted(self._by_engineer)

    def is_monitored(self, engineer_email: str | None) -> bool:
        return bool(engineer_email) and engineer_email.lower() in self._by_engineer

    def team_of(self, engineer_email: str) -> Team | None:
        return self._by_engineer.get(engineer_email.lower())

    def associates_for(self, engineer_email: str) -> list[str]:
        team = self.team_of(engineer_email)
        return team.associates if team else []
