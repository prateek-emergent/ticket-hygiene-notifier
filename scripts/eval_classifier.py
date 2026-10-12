"""Sanity-check the Pending classifier on labeled replies before going live.

    python scripts/eval_classifier.py                       # the option chosen in config.py PENDING_MODEL
    python scripts/eval_classifier.py --option A --set all  # von + decider:4b (Ollaya), English + other languages
    python scripts/eval_classifier.py --option B --set all  # Jev (needs JEV_API_KEY in .env)
    python scripts/eval_classifier.py --backend claude      # needs ANTHROPIC_API_KEY

Cases are adapted from real Trinity replies (customer details removed). Add every false alert or
missed alert you see in Slack here, so prompt changes can be checked against them.
"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv  # noqa: E402

from notifier.classifier import PendingClassifier  # noqa: E402

# (label: awaiting_customer, subject, customer message, our reply)
CASES = [
    (False, "Referral link not showing", "I can't find the referral link, please enable it.",
     "To be eligible for the referral program, you need an active subscription along with at least one top-up "
     "purchase. Once you make a top-up purchase, the referral feature will be available for you. If you have any "
     "other questions, feel free to reach out."),
    (True, "Database backup", "I want a full backup of my app's MongoDB under my own account.",
     "Here are two ways to get a full copy: Option 1 JSON dump via the MongoDB Viewer, Option 2 a backup endpoint "
     "in your app. To help us check the right app, please also reply with the Job ID of your production app."),
    (False, "MongoDB export from deleted deployment", "Any update on my export?",
     "Thank you for your message. The export file is being prepared, and we will send it to you here on this "
     "ticket. If anything else comes up in the meantime, just reply here."),
    (True, "Deployment error", "My deployment is blocked with a phishing flag.",
     "Our trust and safety team has completed the review and the phishing flag on your job has been removed. "
     "Could you please fork the job and redeploy, and confirm here whether the deployment goes through?"),
    (False, "Refund request", "I want a refund for the credits the agent wasted.",
     "We reviewed your account. Credits consumed by completed agent runs are non-refundable under our terms, so "
     "we're unable to issue a refund for this usage. We've shared feedback on the run with our product team."),
    (True, "Custom domain", "My domain isn't connecting.",
     "There are two ways to fix this: (A) point your apex A record to our IP, or (B) use a www CNAME and redirect "
     "the apex. Which of these would you prefer? Once you tell us, we'll send exact DNS values."),
    (False, "App down", "My app has been down since this morning.",
     "Thanks for flagging this. We've escalated it to our engineering team and will update you on this ticket "
     "within 24 hours."),
    (False, "Credits not added", "Paid but no credits.",
     "We've added the 100 credits to your account. They should now be visible on your dashboard. Hope this "
     "helps, and let us know if there's anything else."),
    (True, "Login issue", "Can't log in.",
     "Could you send a screenshot of the error you see on the login page, and confirm whether you signed up "
     "with Google or email? That will tell us which fix applies."),
    # --- harder cases: courtesy questions, asks without "?", rhetorical questions, buried asks ----------
    (False, "Credits added", "Where are my credits?",
     "We've added the missing 50 credits to your account and they are visible on your dashboard now. "
     "Is there anything else I can help you with today?"),
    (False, "Build failing", "Why does my build keep failing?",
     "Why was the build failing? Your backend requirements listed a package that doesn't exist, lintiq==0.1.3, "
     "so every install step stopped there. We removed that line from your project and re-ran the publish, which "
     "is now live on your domain."),
    (True, "Job not found", "My app disappeared.",
     "Thanks for reaching out. Please share the Job ID of the affected app so we can look into it. You can find "
     "it in the URL of your project page or under Settings."),
    (True, "Restore target", "Please restore yesterday's backup.",
     "We have yesterday's backup ready. Before we restore it, please confirm whether it should go to your "
     "production app or your preview environment, since restoring overwrites the current data."),
    (False, "Redeploy fixed", "Deployment fails at the build step.",
     "We fixed the Dockerfile path that was breaking your build and redeployed. The app is live again. If the "
     "issue persists after your next deploy, feel free to reply here."),
    (False, "Escalated outage", "Nothing loads.",
     "We've escalated this to our engineering team, who are actively working on it. We'll update you on this "
     "ticket within 48 hours. No action is needed from your side in the meantime."),
    (True, "Cache issue", "Seeing an old version of the app.",
     "This looks like a cached version of your site. Could you try clearing your browser cache and opening the "
     "app in a private window, then let us know whether you still see the old version?"),
    (False, "Refund question quoted", "Can I get a refund for the failed run?",
     "You asked whether you can get a refund for the failed run. Yes: we've refunded the 20 credits from that "
     "run to your balance, and you can see the adjustment in your billing history."),
    (True, "Unknown account", "My subscription isn't showing.",
     "We couldn't find an active subscription under this email address. Which email address did you use when "
     "you subscribed? It may be a different one from the address you're writing from."),
    (True, "Transfer ownership", "Move the app to my teammate.",
     "We can transfer ownership of the app to your teammate's account. Would you like us to go ahead with the "
     "transfer to jordan@acme.io? Just reply yes and we'll do it right away."),
    (False, "Feature request", "Please add dark mode to the editor.",
     "Thank you for the suggestion. Dark mode for the editor isn't available yet, and I've passed your request "
     "to our product team so they can consider it for the roadmap. Have a great day!"),
    (True, "Buried ask", "Emails from my app aren't being delivered.",
     "Thanks for the details. We checked your app's email setup and the sending domain is configured correctly. "
     "To narrow this down, could you send us one recipient address that didn't receive an email and the "
     "approximate time it was sent? Meanwhile, here is some background on how delivery works: messages go out "
     "through our provider, which retries soft bounces for up to 24 hours, and hard bounces are suppressed "
     "automatically for 30 days. Spam filters at the recipient's provider can also hold messages, so checking "
     "the spam folder is worthwhile. Best regards, Emergent Support Team"),
    (False, "Long resolved explanation", "My database looks empty.",
     "Thanks for your patience while we looked into this. Your production database is not empty: the viewer was "
     "connected to the preview database, which is separate and starts empty for every app. Production and "
     "preview each have their own MONGO_URL, and the database viewer defaults to whichever environment you "
     "opened last. We switched your viewer back to production, and all 14 collections and their documents are "
     "there, including the orders collection you mentioned, with 2,381 documents as of this morning. Going "
     "forward, the environment switch is at the top of the viewer, next to the collection list, and the label "
     "turns orange when you are looking at preview data. Nothing was lost or deleted at any point, and no "
     "action is required on your side. " * 2 + "Best regards, Emergent Support Team"),
    (True, "Long reply, ask at the end", "The payment page shows an error.",
     "Thanks for the screenshots. Here is what we found. The payment page loads the Stripe script from your "
     "frontend and creates a checkout session on your backend. In the logs, the session call fails with an "
     "authentication error, which usually means the secret key in your production secrets is a test key or has "
     "been rotated. Test keys start with sk_test and only work with test cards, while live keys start with "
     "sk_live. Your preview environment uses its own secrets, which is why checkout works there. " * 2
     + "To fix it we need to know which key you intended to use: could you confirm whether you want live "
     "payments enabled now, or whether you are still testing?"),
    (False, "Thanks follow-up", "Thank you, it works now!",
     "Glad to hear everything is working! We'll close this ticket now. Thanks for building with Emergent."),
    # Added 2026-10-08 and never used for tuning (the 100-case comparison in pending_decisions.md D9).
    (True, "Invoice email", "Billing issue.",
     "We've located two payments on your card but only one is linked to your account. To match the second one, "
     "could you forward us the receipt email you got from Stripe for it?"),
    (True, "Pick a time", "Need a call.",
     "Happy to get on a call with you. Our team is free Tuesday 3-5 pm IST or Wednesday 11 am-1 pm IST. "
     "Which slot works best for you?"),
    (True, "Run and report", "Login loop.",
     "We pushed a fix for the login redirect. Please log out, clear cookies for your domain, log back in, and "
     "let us know whether the loop still happens."),
    (True, "Permission to access", "Data looks wrong.",
     "To check this properly we need to open your production database in read-only mode. Do we have your "
     "permission to do that? We won't change anything."),
    (True, "Missing screenshot", "Error on checkout.",
     "Thanks for the report. The screenshot didn't come through on our side. Please attach it again, or paste "
     "the exact error text, so we can match it to our logs."),
    (True, "Approve plan", "Migrate my app.",
     "Here is the migration plan: export the data, create the new collections, and switch the app over during a "
     "quiet hour. Reply with an approval and a preferred date, and we'll schedule it."),
    (False, "Fixed, thanks", "Images not loading.",
     "The images were blocked by a missing CORS rule on your storage bucket. We added the rule and every image "
     "now loads on the live site. Thanks for your patience, and have a lovely weekend!"),
    (False, "Policy refusal", "Transfer my credits.",
     "Credits can't be moved between accounts: they are tied to the account that bought them. Your remaining "
     "1,240 credits stay available on this account and don't expire while your plan is active."),
    (False, "We will check", "Slow app.",
     "Thanks for flagging the slowdown. Our infrastructure team is looking at the database cluster your app "
     "runs on, and we'll post an update here as soon as we know more."),
    (False, "How-to answer", "Custom domain?",
     "Yes, custom domains are supported on every paid plan. Go to Settings, then Domains, add your domain, and "
     "copy the two DNS records shown into your registrar. It usually goes live within an hour."),
    (False, "Rhetorical what happened", "Deploy failed.",
     "What happened? The deploy ran out of memory while building your frontend. We raised the build memory "
     "limit for your app and redeployed, and the new version is live now."),
    (False, "Echoed question", "Can I downgrade?",
     "You asked if you can downgrade without losing your apps. You can: downgrading only changes your monthly "
     "credits, and all your apps and code stay as they are."),
]


def build_classifier(backend: str, option: str | None, model: str | None, ml_model: str | None):
    if backend == "claude":
        return PendingClassifier(
            model or os.getenv("CLASSIFIER_MODEL", "claude-opus-5-5"),
            os.getenv("CLASSIFIER_EFFORT", "low"),
            os.getenv("CLASSIFIER_FALLBACKS", "true").lower() == "true",
        )
    from notifier.config import load_rules_config, pending_model
    from notifier.systemone import SystemOneClassifier

    option, settings, key = pending_model(load_rules_config(), option)
    clf = SystemOneClassifier(
        settings["url"],
        model or settings["english_model"],
        api_key=key,
        low=float(os.getenv("SYSTEMONE_LOW", "0.4")),
        high=float(os.getenv("SYSTEMONE_HIGH", "0.6")),
        multilingual_model=ml_model or settings["other_languages_model"],
        per_sentence=settings["score_sentences"] if not model else model == "von",
        timeout_seconds=600,
    )
    print(f"option {option}: {clf.model} (English) + {clf.multilingual_model} (other languages) at {settings['url']}\n")
    return clf


async def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["claude", "systemone"], default=os.getenv("CLASSIFIER_BACKEND", "systemone"))
    ap.add_argument("--option", help="config.py PENDING_MODEL option to test (default: the one chosen there)")
    ap.add_argument("--model", help="try another English model with the option's service")
    ap.add_argument("--ml-model", help="try another model for non-English replies")
    ap.add_argument("--set", choices=["english", "multilingual", "all"], default="english",
                    help="which labelled replies to use (multilingual: scripts/eval_multilingual.py)")
    args = ap.parse_args()
    clf = build_classifier(args.backend, args.option, args.model, args.ml_model)
    global CASES
    if args.set != "english":
        from eval_multilingual import CASES as ML_CASES

        CASES = ML_CASES if args.set == "multilingual" else CASES + ML_CASES

    verdicts = []
    for _, s, c, r in CASES:  # sequential: a local CPU model gains nothing from concurrency
        verdicts.append(await clf.classify(r, c, s))

    # label True = the reply asks the customer something (no alert wanted); False = it doesn't (alert wanted).
    correct, decided, wrong_alerts, missed, skipped = 0, 0, 0, 0, 0
    pos = [v.probability for (lab, *_), v in zip(CASES, verdicts) if lab and v.probability is not None]
    neg = [v.probability for (lab, *_), v in zip(CASES, verdicts) if not lab and v.probability is not None]
    for (label, subject, _, _), v in zip(CASES, verdicts):
        p = f" p={v.probability:.2f}" if v.probability is not None else ""
        if v.uncertain:
            skipped += 1
            status = "SKIP"  # no alert (benefit of the doubt)
            missed += not label
        else:
            decided += 1
            ok = v.error is None and v.awaiting_customer == label
            correct += ok
            wrong_alerts += label and not v.awaiting_customer
            missed += (not label) and v.awaiting_customer
            status = "PASS" if ok else "FAIL"
        print(f"{status}  expected={label!s:5} got={v.awaiting_customer!s:5}{p} "
              f"[{v.confidence}] {subject}: {v.reason}{'  ERROR: ' + v.error if v.error else ''}")
    print(f"\n{correct}/{decided} decided cases correct; {skipped} uncertain (no alert)")
    print(f"wrong alerts (reply did ask): {wrong_alerts}; missed alerts (reply asked nothing): {missed}")
    if pos and neg:
        print(f"separation: lowest positive {min(pos):.2f} vs highest negative {max(neg):.2f} "
              f"({'separable' if min(pos) > max(neg) else 'overlapping'})")


if __name__ == "__main__":
    asyncio.run(main())
