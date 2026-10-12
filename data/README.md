# data/: input files

Files the notifier reads, as exported from the team's sheets. They contain staff names, emails and shifts, so everything in this folder except this README is git-ignored.

| File | Used for | How to update |
|---|---|---|
| `table.tsv` | Who is monitored, and each engineer's associate (`config/teams.yaml` is generated from it) | Export the team sheet as TSV to this path, then run `python scripts/import_teams.py data/table.tsv --associate "Name=email" ...` (the command is at the top of `scripts/import_teams.py`) |
| `Roster_L1_L2_2026_Schedule - L2 FS Team (Mid Oct - Dec).csv` | Shift schedule for themes 4–5 (status vs shift, tickets held off shift); covers 9 Oct to 15 Dec 2026 | Export the new roster as CSV into this folder and set `SHIFTS["file"]` in `config.py` to its path. The notifier warns a week before the current roster runs out. |
