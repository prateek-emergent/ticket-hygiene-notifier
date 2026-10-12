"""Build config/teams.yaml from the team sheet exported as TSV.

    python scripts/import_teams.py data/table.tsv \
        --associate "Hridaya Madaan=hridaya@emergent.sh" \
        --associate "Sutikshan Mahajan=sutikshan@emergent.sh" ...

Sheet layout: name, email, associate. A blank associate cell means "same associate as the row above",
so each named associate starts a new team. Only engineers in this sheet are monitored.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import yaml


def parse(tsv: Path) -> list[dict]:
    teams: list[dict] = []
    with tsv.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f, delimiter="\t"))
    for i, row in enumerate(rows[1:], start=2):  # row 1 is the header
        row = [c.strip() for c in row] + [""] * 3
        name, email, associate = row[:3]
        if not email:
            continue
        if associate:
            teams.append({"associate_name": associate, "engineers": []})
        if not teams:
            raise SystemExit(f"row {i}: {name} has no associate and no associate above it")
        teams[-1]["engineers"].append({"name": name, "email": email.lower()})
    return teams


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("tsv", type=Path)
    ap.add_argument("--associate", action="append", default=[], metavar="NAME=EMAIL",
                    help="email of an associate named in the sheet (repeat per associate)")
    ap.add_argument("--out", type=Path, default=Path("config/teams.yaml"))
    args = ap.parse_args()

    emails = {}
    for item in args.associate:
        name, _, email = item.partition("=")
        emails[name.strip().lower()] = email.strip().lower()

    teams = parse(args.tsv)
    missing = sorted({t["associate_name"] for t in teams if t["associate_name"].lower() not in emails})
    if missing:
        sys.exit("no email given for associate(s): " + ", ".join(missing) + " (use --associate 'Name=email')")

    doc = {
        "teams": [
            {
                "name": f"{t['associate_name']}'s team",
                "associates": [emails[t["associate_name"].lower()]],
                "engineers": [e["email"] for e in t["engineers"]],
            }
            for t in teams
        ],
        "exempt_from_reassign_rule": [],
        "slack_ids": {},
        # Display names for the dashboard.
        "names": {e["email"]: e["name"] for t in teams for e in t["engineers"]}
        | {emails[t["associate_name"].lower()]: t["associate_name"] for t in teams},
    }
    header = (
        f"# Generated from {args.tsv.as_posix()} by scripts/import_teams.py. Re-run it when the sheet changes.\n"
        "# Only the engineers below are monitored; everyone else is ignored.\n"
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(header + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    n = sum(len(t["engineers"]) for t in teams)
    print(f"wrote {args.out}: {len(teams)} teams, {n} engineers")
    for t in teams:
        print(f"  {t['associate_name']:20} {len(t['engineers']):2} engineers")


if __name__ == "__main__":
    main()
