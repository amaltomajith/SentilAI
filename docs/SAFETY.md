# Safety, abuse and privacy model

Sentinel lets a person have an AI answer a suspected scammer from the person's own WhatsApp. That is useful and also easy to misuse, so the limits below are enforced in code, not just stated.

## Who it is for
People who are being targeted by a scammer. The terms the user must accept before anything runs say: use it only against someone who **contacted you first** and appears to be a scammer; never against a person you know or for harassment.

## Abuse rails (enforced)
- **Consent first.** Linking WhatsApp or adding a number returns 403 until the user has accepted the terms (stored with a timestamp).
- **Never initiates.** A reply exists only as the answer to an inbound message from a target number. There is no "send" endpoint for arbitrary text.
- **Only the target number.** Three independent checks: the bridge drops all other chats before they leave the device; the backend accepts inbound only for `(user, number)` pairs that user added; the bridge refuses to send to any number that is not that user's target.
- **Limits.** At most `MAX_TARGETS_PER_USER` numbers per user, `MAX_LINKED_ACCOUNTS` linked accounts per server, a per-session exchange cap (`MAX_EXCHANGES`), and a user cannot target their own number.
- **Stop is instant.** Removing a number or unlinking takes effect on the next message.
- **Auditable.** Every turn, tool call and decision is in a hash-chained ledger.
- **No real payments, no real bank details.** The agent can offer only a generated decoy UPI id. Takedown dispatch is dry-run only (files are written, nothing is sent).

## Privacy of the user's own details
- The profile has two kinds of fields. **Mentionable** fields (alias, age, occupation, city, languages, style, situation) are included in the model prompt only if the user left "the agent may mention this" on. **Protected** fields (full legal name, employer, home address, own phone) and any mentionable field the user switched off are **never sent to the model**.
- The outbound gate blocks any draft containing a protected value (full name, surname, employer, address, the last 8 digits of a phone number) and replaces it with a safe reply. The user's chosen alias is excluded from the block list so the agent can use it.
- The profile form refuses values that look like bank/card/UPI/OTP/password/ID numbers, because the profile is read by an AI model.
- Everything is scoped by the Clerk user id. User B gets 404 (not 403) for any of user A's resources and never receives A's events, QR code or targets.

## What "learning" means here
There is **no model training**. Two mechanisms:
1. **Per-conversation adaptation.** Rules read each scammer message (scam type, stage, pressure, language). The agent mirrors the scammer's language only if the user speaks it.
2. **Outcome learning.** A Thompson-sampling chooser picks the next tactic from a hand-written playbook, rewarded when the scammer reveals a new detail after it. Counters are stored per user. If the user opts in, the same counters (scam type, tactic, successes, trials) are added to a shared table. No message text, numbers, profile data or user ids are shared. This is federated *analytics* in spirit; it is not federated learning in the strict sense.

## Known risks you should tell users
- **WhatsApp** forbids unofficial clients; the linked account can be restricted or banned. Recommend a secondary number.
- **Legal.** Whether and how you may engage a suspected scammer varies by country. The tool does not give legal advice.
- **The agent speaks in the user's name.** Review practice chats first. Do not rely on it for anything safety-critical, and stop if a conversation turns to real threats: report to the police/cybercrime portal (India: 1930 / cybercrime.gov.in).
- **Hash chain** shows internal consistency, not who created the records.

## Reporting a problem
Open an issue with the ledger proof (`/api/sessions/<id>/proof.json`) and the gate trace; do not include real personal data.