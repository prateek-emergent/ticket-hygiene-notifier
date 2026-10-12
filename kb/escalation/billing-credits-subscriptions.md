# Billing, credits, refunds, subscriptions and coupons

## Covers
- Refunds: "refund", "money back", "cancel and refund", refund of a subscription, annual plan, top-up or auto top-up; refund FAILED, "refund approved but money never arrived", credits clawed back after a refund
- Credit (ECU) grants and goodwill: "credits back", "compensation", "agent wasted my credits", "I am owed credits", grant over the cap, credit tool returns PENDING_APPROVAL
- Credits missing after payment: "paid but no credits", "top-up not credited", "payment successful but credits not added", crypto payment not received
- Annual plan monthly credits not added: "monthly 750 credits not added", month 2 or month 3 credits missing on an annual plan
- Plan paid but not provisioned: "charged but still on Free", "payment successful but plan not active", pass shows "payment failed" after a successful payment, paid add-on (dedicated database) never applied
- Subscription state wrong: plan still active after it ended, "can't buy a new plan", stale subscription row, $0 plan with 0 credits, wrong plan or price after checkout
- Double charge: "charged twice", duplicate charge, pending bank authorisation
- Cancellation: "cancel my subscription", can't cancel, Razorpay trial or mandate, UPI mandate, annual to monthly switch, 403 when switching to monthly, "end my annual plan early"
- Coupons, promos and campaign links: "$1 Standard Pass not applied", "coupon not applied", offer button greyed out, "free month" or "1 year free" email link, promo code rejected, wrong discount, price shown in local currency
- Referrals: "Refer & Earn missing", referral credits not received; campaign or hackathon credits not received
- Invoices: "can't download invoice", invoice missing, receipt request
- Payment gateway: checkout fails, card declined, Paddle error at checkout, move to Stripe, Razorpay, PagBrasil, Paddle
- Disputes: unauthorized charge, "I have no account but I am being charged", chargeback, bank dispute, fraud claim, account blocked after a dispute, legal or police threats about money
- App-store payments: Apple Pay, in-app purchase, Google Play or RevenueCat charge with no plan or credits on the account
- Universal Key or integration wallet balance: see integrations

## Needs L3 when
- A dollar refund is above the auto-approve limit and is waiting for a refund approver [USD-equivalent 201 by default, config-driven] — refund approver authority.
- A refund request shows FAILED, or the refund was approved and credits were deducted but the money never reached the customer — known gateway bug; billing engineering.
- The customer has already filed a chargeback or bank dispute and wants money back — the dispute flow (payments) owns it; a separate refund pays twice.
- The support credit tool returns PENDING_APPROVAL or refuses the grant because it is over the customer's cap, or the customer is already over the lifetime cap [caps are set per customer lifetime-value band in config; documented examples: none without approval under $25 LTV, 50 ECU per grant for $25-100 LTV, 100 ECU per grant for $100-300 LTV; the raw credit endpoint refuses more than 500 ECU per call] — approver group or leadership sign-off.
- An annual plan's monthly credits did not post this month although earlier months did — the recurring distribution job failed; billing engineering, and the make-up grant is above the support credit cap (#200309, #266431).
- A plan, pass or paid add-on payment succeeded at the gateway but no subscription or add-on was provisioned, or a mistaken add-on purchase must be reversed — subscription and entitlement writes are billing engineering only (#54792, #212142, #4842).
- An Apple, Google or RevenueCat purchase produced no plan or credits on any Emergent account — RevenueCat lookup and entitlement restore (#29999, #32430).
- A crypto or other non-Stripe payment settled on the customer's side but expired or is missing on ours — gateway-side reconciliation (#219996).
- The subscription row stays active after its end date, or shows a plan or price the customer did not buy, and blocks a new purchase — a subscription row write; billing engineering only (#21287, #34386).
- Many customers land on the same wrong plan or price after checkout — checkout mapping fleet bug; billing or conversion engineering (#28708).
- An annual plan must be ended early (for example to switch to monthly), or a subscription must be cancelled immediately — the immediate cancel is restricted to unlimited-access admins; a refund of the annual charge also needs a refund approver (#25933).
- The gateway refuses one customer before the card page and the customer must be moved to another gateway — billing engineering (#211124).
- An eligible customer (no promo block, not already redeemed, Stripe gateway, applicable plan) still sees full price, or the coupon was used up by a failed or cancelled payment, and the offer must be re-added, renewed or unblocked — offers owner only (#208989, #237290, #45894).
- A campaign or promo email links to the wrong offer or coupon — the offers or marketing owner fixes the campaign (#220287, #55205).
- A personal gift or goodwill promo code must be created — the promo-code tool is allow-listed to named staff.
- Charges keep hitting a card and no Emergent account matches any email or phone number the customer gave — needs gateway dashboard access that support lacks (#262948, #225964).
- An account was blocked automatically after a lost payment dispute and the customer wants it unblocked — billing and trust-and-safety decision; support must not clear the block (#264145).
- The customer uses legal, police, regulator or solicitor language about money — legal route with a case summary (#51173).

## L2 can resolve when
- The refund ask is not refundable by policy: top-ups, auto top-ups, agent quality or dissatisfaction, unused monthly credits, or a plan already used — decline with the refund policy (Cancellation & refund eligibility) (#20512, #30925, #7963).
- The refund is eligible (asked within about 48 hours of the charge, no credits consciously used, subscription cancelled first) and under the auto-approve limit — file it with the support refund request tool and confirm COMPLETED with a gateway refund id before telling the customer.
- The customer was charged full price because a coupon did not apply and only wants the money back — cancel and file the refund request (#33029).
- A chargeback is threatened but not filed — reconcile the payments, send an itemised reply, and refund or cancel within the limits (17 › Chargeback threat).
- The customer only wants to stop renewal — give the self-serve cancel path or set non-renew; the plan stays active to its end date (#20512).
- A goodwill or wasted-credit grant that the support credit tool issues without approval — quantify it from the job cost summary and logs, grant it, and check the SUPPORT credit row (#32785, #232735, #269009).
- A single top-up payment succeeded with no matching credit row and nothing systemic — grant the exact amount with the support credit tool after confirming no credit row exists (11 › Credits never showed up).
- Credits look missing but the ledger reconciles (spent on builds, deployments, Universal Key funding, or expired) — send the ledger breakdown and export.
- The plan's credit amount is smaller than the customer expected — show the plan record (#211014, #235448).
- The subscription is on the customer's other account or phone login, or a never-activated subscription is retrying a failed first payment — show which account and cancel it there (#58821).
- The customer is not eligible for an offer, already redeemed it, has a promo or fraud block, or paid through a non-Stripe gateway or mobile — explain the gate without revealing fraud details (#209314, #46158, #236387).
- Referral rewards are missing because the referee has not subscribed, the referral cap is reached, or programme rules hide the referral section — explain the rule (#29961).
- Campaign or hackathon credits — verify against the programme records and grant the programme amount; never on a screenshot alone.
- A plan-upgrade or pricing question — answer from the plan pages or ask sales (#35445).
- An invoice is asked for a payment made before invoices existed — send the receipt instead (#235664).
- A credit or refund request rides on a technical ticket (agent hang, preview, deploy) — handle the credit part at L2; the technical part follows its own KB file (#231015, #211462).

## L2 must try first
1. Find the right account: look up every email and phone number the customer gave, and work from the user id, not the email.
2. Find the charge: gateway, date, amount and status in payment transactions. Use the Stripe tool for Stripe only; for other gateways use the payment metadata and the customer's receipt or screenshot.
3. Read the subscription rows newest first: gateway, status, plan, price, end date. Check whether the end date has already passed.
4. Reconcile the credit ledger and look for a credit row that matches the payment. If the payment is still pending, wait until the pending sweep has run (about 150 minutes) before calling it missing.
5. For an annual plan, check whether earlier months' credit rows posted.
6. For a refund, check for an existing refund request and an open dispute, and cancel the subscription first.
7. For credits, run the support credit tool first; escalate only the amount it refuses or holds for approval.
8. For an offer, check the promo redemption and block records, the gateway and the plan, and get a checkout screenshot. Do not rely on Overwatch's eligibility verdict alone (#220287).
9. For a dispute or blocked account, check the dispute records and the account's blocked flag.
10. Record the account, gateway, charge date and amount, what the records show, and exactly what the approver or engineer must do.

## Not a fault
- One successful and one failed payment seconds apart — a declined first card, not a double charge; tell the customer only one charge was taken.
- A pending bank authorisation, not a capture — it voids itself; tell the customer to wait for their bank.
- The payment was declined or expired at the provider and nothing was received (#36063) — tell the customer to retry or use another method.
- The subscription shows cancellation in progress — the plan stays active until its end date, and no further charge follows.
- The subscription is already cancelled and the bank still shows a UPI or card mandate (#37499) — the mandate is separate; the customer can revoke it with their bank.
- Switching annual to monthly returns 403 — an intentional guard; the customer can wait for the end date or ask for an early end without a refund.
- The checkout price is the local-currency version of the normal price — explain the currency conversion.
- The offer button is disabled because the account has a fraud or promo block (#236387) — tell the customer the account is not eligible, without fraud details.
- The plan grants fewer credits than the customer expected (#211014, #235448) — explain the plan terms.
- Credits were spent on builds, deployments or key funding (#32785) — send the ledger breakdown.
- An app-store purchase refund or cancel — Apple or Google handles it; the customer cancels on the device.
- Credits bought from a third-party seller — nothing was bought through Emergent, so there is nothing to refund or credit.

## Changed over time
- 2026-01-12: invoice download exists only for payments from this date; earlier payments get a receipt instead (#235664).
- June 2026: the $1 first-month checkout bound subscriptions to a $0, 0-credit internal price (fleet bug, #28708). A $0 Standard plan with 0 credits after a $1 checkout in that period is this bug, not a single-account fault.
- Before 2026-09-30 the CS-Playbook (2026-06-11) sent eligible dollar refunds to billing engineering. Since the billing playbook of 2026-09-30, support files refunds itself and they auto-approve under the limit; only above-limit and FAILED refunds leave L2.

## Examples
- Genuine L3: #200309: annual plan month 2 credits never posted although month 1 did; the distribution job did not fire.
- Genuine L3: #54792: a Razorpay pass payment succeeded but the account showed payment failed; the pass had to be provisioned.
- Genuine L3: #212142: a paid dedicated-database add-on was charged but never applied.
- Genuine L3: #21287: the subscription row stayed active after its end date and blocked a new monthly purchase.
- Genuine L3: #28708: the $1 checkout bound subscriptions to a $0, 0-credit price; a fleet bug.
- Genuine L3: #25933: the annual plan had to be ended early with the admin-only immediate cancel.
- Genuine L3: #211124: the gateway refused one customer's checkout; billing moved them to another gateway.
- Genuine L3: #45894: the $1 pass coupon was used up by a cancelled crypto attempt and had to be re-added.
- Genuine L3: #220287: a "free month" campaign email sent users to the wrong offer.
- Genuine L3: #262948: recurring charges not linked to any given email; traced only in the gateway dashboard.
- Genuine L3: #264145: the account was auto-blocked after a lost dispute; lifting it was a billing and trust-and-safety decision.
- Not L3: #20512: annual cancel and refund; non-renew set and refund declined by policy because the plan was used.
- Not L3: #30925: refund claim for an auto top-up; refunds are a support action, closed at L2 the same day.
- Not L3: #33029: full charge because the coupon did not apply; cancel and refund were done by support.
- Not L3: #199535: top-up credits posted on their own a few hours later; escalated with no ledger check.
- Not L3: #211014: the plan grants 625 credits per month by design; the customer expected 750.
- Not L3: #235448: annual plan credits were a one-time grant; the per-month label in the UI was wrong.
- Not L3: #36063: the crypto payment was declined by the provider and never received.
- Not L3: #236387: the offer button was disabled by a fraud block; expected behaviour.
- Not L3: #209314: the customer was not eligible for the offer; explained, with goodwill.
- Not L3: #58821: "charged but Free" was a never-activated subscription found through the phone login.
- Not L3: #270768: escalated without the checkout screenshot; L3's first action was to ask for it.
