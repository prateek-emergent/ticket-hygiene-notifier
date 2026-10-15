"""Switchboard for the notifier: which checks run, and their main settings.

Edit this file and restart the notifier. Secrets and connection details (Trinity key, Slack token,
URLs) stay in .env. Open questions behind the "off" switches are tracked in pending_decisions.md.
"""

# --- Which themes run ---------------------------------------------------------------------
# The notifier watches 6 themes of ticket hygiene. Theme 6 (L3 escalations) has two checks with
# separate switches: 6a (did it need L3?) and 6b (is the escalation note a proper RCA?).
THEMES = {
    # Theme 1. An engineer sets a ticket to PENDING but their reply asks the customer nothing.
    "pending_without_open_question": True,
    # Theme 2. An engineer assigns themselves a ticket that a colleague was holding.
    "reassigned_from_colleague": True,
    # Theme 3. An engineer grabs a ticket while Overwatch is running on it, then System closes it.
    "picked_up_during_overwatch_run": True,
    # Theme 4. An engineer's Trinity status (Online/Offline) doesn't match their shift 45 min after it starts/ends.
    "status_not_matching_shift": True,
    # Theme 5. A customer has waited 3+ hours on an OPEN ticket whose assignee is off shift.
    #    Definition to confirm (pending decision D7).
    "ticket_held_off_shift": True,
    # Theme 6a. An L2->L3 escalation that the escalation knowledge base says L2 could have handled.
    #    Built and tested; off until pending decision D13.
    "l3_escalation_check": False,
    # Theme 6b. An L2->L3 escalation whose internal note (the RCA) is missing, too short, or vague: no root
    #    cause and no exact ask, or a cause with no evidence. MISSING is flagged by code; the rest by Jev.
    #    Standard: kb/escalation/reference/rca-standard.md.
    "escalation_note_quality": True,
    # Theme 7 (from shift-guardian). An engineer held a ticket 30+ min, then un-assigned it themselves without
    #    escalating (no move to L1/L3 or l3_needs_review up to 5 min after). Says whether they left a note.
    "held_then_unassigned": True,
    # Theme 8 (from shift-guardian). A customer has waited 60+ min, since the ticket was assigned to an
    #    engineer who is on shift, with no reply from a person. Off-shift cases are theme 5.
    "assigned_without_reply": True,
}

# --- Themes 7 and 8: holding and replying ----------------------------------------------------
HOLDS = {
    "held_minutes": 30,  # theme 7: held longer than this, then dropped
    "no_reply_minutes": 60,  # theme 8: customer waiting this long with no reply
}

# Jev (TypeSafe's decision model) through Emergent's LiteLLM. The main model everywhere: theme 1 (option B)
# and theme 6 (6a and 6b). Claude is only theme 6's fallback (L3_ESCALATION below).
# The key goes in .env as JEV_API_KEY, never here.
JEV_URL = "https://litellm.central-infra-apps.emergentagent.com/typesafe"

# --- Theme 1: which model reads the engineer's reply -----------------------------------------
# Themes 2-5 use no model: they are plain logic on Trinity events and the roster. Theme 6 has its own
# setting (L3_ESCALATION below). Comparison on 100 hand-written cases: pending_decisions.md, D9.
#
#   "A"  von (English) + decider:4b (other languages), running locally in Ollaya.
#        Customer text stays on this machine. Needs Ollaya started first (README, terminal 1).
#        ~1 s per English reply, ~7-30 s per non-English reply on a laptop CPU; ~10 GB RAM.
#   "B"  Jev (jev-latest) through Emergent's LiteLLM, for every language.
#        No Ollaya needed. Customer text is sent to that service. Needs JEV_API_KEY in .env.
#        ~1 s per reply.
PENDING_MODEL = {
    "option": "B",  # Jev, chosen 2026-10-12 (was A: local von + decider:4b)
    "options": {
        "A": {
            "url": "http://127.0.0.1:11435",
            "english_model": "von",
            "other_languages_model": "decider:4b",
            "score_sentences": True,  # von also scores each ask-like sentence; it misses buried asks otherwise
            "api_key_env": None,
        },
        "B": {
            "url": JEV_URL,
            "english_model": "jev-latest",
            "other_languages_model": "jev-latest",
            "score_sentences": False,  # one call per reply is enough for Jev
            "api_key_env": "JEV_API_KEY",  # the key itself lives in .env, never here
        },
    },
}

# --- Shifts (themes 4 and 5) ----------------------------------------------------------------
SHIFTS = {
    # The team roster (.csv or .xlsx), as exported from the roster sheet. Replace it when a new roster
    # is published: the current one ends mid-December and the notifier warns a week before.
    "file": "data/Roster_L1_L2_2026_Schedule - L2 FS Team (Mid Oct - Dec).csv",
    # Timezone the shift times in the file are written in.
    "timezone": "Asia/Kolkata",
}

# --- Theme 4: status vs shift ---------------------------------------------------------------
STATUS_CHECK = {
    # Check the engineer's Trinity status this long after their shift starts (should be Online)
    # and after it ends (should be Offline).
    "minutes_after_shift_boundary": 45,
    "post_to_channel": True,  # alert in the channel, tagging the associate
    "dm_engineer": True,  # also remind the engineer directly
}

# --- Theme 5: tickets held off shift --------------------------------------------------------
OFF_SHIFT_HOLDING = {
    # Alert when a customer has been waiting this long, counted from the later of the customer's
    # unanswered message and the end of the assignee's shift.
    "customer_waiting_hours": 3,
    "sweep_minutes": 15,  # how often open tickets of off-shift engineers are checked
    "dm_engineer": False,  # they are off shift; the channel alert lets the associate reassign
}

# --- Theme 6: L3 escalations (6a KB check, 6b escalation note) ------------------------------
L3_ESCALATION = {
    "kb_dir": "kb/escalation",  # every .md file here is part of the knowledge base
    "grace_minutes": 15,  # wait for the escalation note: 93% of notes written after the move land within 15 min
    # Jev (at JEV_URL, needs JEV_API_KEY) judges every escalation (6a) and every escalation note (6b) first.
    "judge_model": "jev-latest",
    # Claude decides the cases Jev can't settle: Jev unsure, Jev failed, or the ticket too long for Jev.
    # It needs ANTHROPIC_API_KEY in .env. Without the key the fallback is simply off (one warning at start,
    # no error): those cases are logged as not judged and never alerted. None = never use Claude.
    "fallback_model": "claude-opus-5-5",
    "min_confidence": "medium",  # only alert when the judge is at least this confident
}

# --- Down alert (python -m notifier watchdog) -----------------------------------------------
# A Slack DM to one person, never the channel, when the notifier stops (no heartbeat) or keeps failing every
# cycle (e.g. VPN down, Trinity key revoked), and another DM when it's back. The watchdog is its own process,
# so it still works when the notifier has crashed.
DOWN_ALERT = {
    "dm": "prateek.m@emergent.sh",  # the only person who gets these messages
    "after_minutes": 10,  # stopped or failing this long before the first DM
    "remind_every_minutes": 60,  # repeat while still down; 0 = one DM only
    "send_during_dry_run": True,  # DRY_RUN=true holds back the alerts to associates, not this DM
}

# --- Dashboard (python -m dashboard) --------------------------------------------------------
DASHBOARD = {
    # 127.0.0.1 = this machine only. Google sign-in needs https for any other address, so sharing it
    # with associates happens once it's deployed (pending decision D10).
    "host": "127.0.0.1",
    "port": 8090,
    # Who may sign in (Google accounts). Git-ignored; see config/dashboard_users.example.yaml.
    "users_file": "config/dashboard_users.yaml",
    "session_hours": 12,
}
