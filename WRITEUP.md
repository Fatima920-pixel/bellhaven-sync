# Writeup

## Result

Starting point: 121 CRM accounts and 35 website locations (34 in the directory, plus Bellhaven Meadows of Findlay, which is only linked from the homepage). 16 locations were already correct. The pipeline proposed 29 changes. I approved 28 and rejected 1.

| Applied | Count |
|---|---|
| Field fixes: renames, address and zip fixes, re-parents (13) | 13 |
| Duplicates marked Inactive with `duplicate_of_account` | 7 |
| CHOW (Tiffin, Marietta: revenue and AR both above zero) | 2 |
| New accounts for locations missing from the CRM | 4 |
| Needs Review (Coldwater, Sandusky) | 2 |
| Rejected (Alliance) | 1 |

The CRM ends at 127 accounts. A final audit script confirmed no account with revenue and AR had its parent changed.

## Matching approach

Ownership changes constantly, so names are the least reliable signal. Matching works on normalized address (street plus zip, or city and state), with a same-city-same-phone fallback for bad addresses. Several of the traps in this data only show up that way: "Riverbend Manor Care Center" and "Sunny Acres Retirement Home" are the website's Chagrin Falls and Willow Creek locations, and a fuzzy name match would have missed both.

The most important design rule is that a similar name alone never counts as a match. "Union Square Senior Living" (Juniper Point) and "Bellhaven at Union Square" are in the same town with different streets and phones. Moving another operator's account to Bellhaven on that evidence would create exactly the ownership error this system exists to prevent, while a wrongly created extra account is cheap to fix. So it proposes a CREATE, shows the look-alike as evidence, and leaves the other account alone. The same reasoning applies to the four CRM accounts named "Amberly ..." in other cities, none of which is the Hudson, OH location.

The SOP is a hard rule in two places: the matcher picks CHOW versus direct re-parent, and the app re-reads the live account before every write and refuses to re-parent one with revenue and AR.

## How I used AI tools

I used Claude as a pair programmer for the whole build: it wrote the code and I directed it, supplied the real data, and decided what to trust. I did not accept its output on faith:

- **Read-only first.** I explored the API and the website, and exported both datasets, before any matching code existed.
- **Tested before touching the CRM.** The matcher and store were run against fixtures built from the real edge cases, and the first CRM write was a no-op PATCH to confirm the request format.
- **Single approvals before bulk.** I approved one update, one create, and one CHOW by itself and verified each in the CRM before using bulk approve.
- **Testing caught real bugs.**
  1. My create-guard blocked the legitimate CHOW create because the old account has the same name and address by design. It now only blocks a match under the same parent.
  2. After the first CHOW, the matcher saw the preserved Tiffin account as a duplicate and proposed deactivating it, which would have broken the SOP. It now ignores CHOW'd accounts, and the app refuses to modify them.
- **I overruled an AI default.** The first matcher would have re-parented Union Square on a name match. I changed it to a create plus evidence (see above).
- **Independent audit.** `verify_final.py` re-reads the CRM and checks the end state rather than trusting the app's own record of what it did.

## Judgment calls

- **Missing from the website is not proof of closure.** Coldwater and Sandusky are marked Needs Review with a note, and their parent is untouched. Sandusky has revenue and AR, so its parent must not change in any case.
- **I rejected the Alliance proposal** during the demo because I would confirm with the account owner before flagging a facility, so it is still Active. This is a deliberate gap, and it will not be re-proposed unless the decision is cleared.
- **Phone and care type are not synced.** They disagree between the CRM and the website too often to trust blindly. They are used as matching evidence only.

## What I'd build next

1. A hosted review app and database (Postgres) with logins and an audit trail, instead of a local SQLite file passed through the Actions cache.
2. Slack notifications for new proposals and failed runs, plus a daily digest, so review happens where reps already work.
3. Detect ownership changes from the website over time (a location disappearing or its parent changing between runs), not just a snapshot comparison.
4. Reconcile contacts and phone numbers, and use an LLM only for explanations or tie-breaks on ambiguous matches, never for the write decision.
5. A scrape contract test (expected location count and fields) and unit tests for `matching.py`, so a site redesign fails loudly.
6. An "undo" that restores the pre-change values already recorded in each proposal's diff.
