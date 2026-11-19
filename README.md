# Bellhaven CRM sync

Keeps the CRM's ownership picture for Bellhaven Senior Living in line with what the Bellhaven website says, without ever writing to the CRM unless a human approves.

```
website scrape ─┐
                ├─> matching ─> proposals ─> review queue (SQLite) ─> reviewer approves/rejects ─> CRM API
CRM API (read) ─┘
```

## Run it

Requires Python 3.10+. No third-party packages.

```
# .env  (never committed)
BH_TOKEN=your-token
BH_API=https://analyst-assessment-production.up.railway.app/api/v1

python pipeline.py     # pull CRM + scrape site + queue NEW proposals (writes nothing to the CRM)
python app.py          # review app at http://127.0.0.1:8000
```

## Files

| File | Purpose |
|---|---|
| `scraper.py` | Walks the community directory plus the homepage (one location is only linked there) and parses each detail page: name, street, city, state, zip, care offerings, phone |
| `matching.py` | Pure logic: website locations + CRM accounts in, proposals out. No network, no writes |
| `store.py` | SQLite review queue. Remembers every decision, which is what makes re-runs safe |
| `pipeline.py` | One full run: pull, scrape, match, queue only new proposals |
| `app.py` | Local review app: evidence and exact field diffs, Approve / Reject. Approve writes via the API |
| `crm.py` | Small API client (token from environment or `.env`) |
| `.github/workflows/daily-sync.yml` | Daily schedule |
| `verify_final.py`, `check_state.py` | Audit helpers: re-read the CRM / the review queue and report the end state |
| `exploration/` | Throwaway scripts and raw data from the initial investigation (kept for transparency) |

## How matching works

1. **Address first.** Street is normalized (`Northwest`/`NW`, `Pike`/`Pk`, `Avenue`/`Ave`, ...) and compared with zip, or with city and state. Names are not trusted because rebrands and sales are the whole problem.
2. **Fallback: same city and same phone.** This catches records whose address was entered badly (for example a PO Box).
3. **A similar name alone never matches.** A look-alike in the same town with a different street and phone is treated as a different facility. It is shown as evidence on a CREATE proposal and the existing account is left untouched.
4. **Survivor selection** when several accounts share an address: prefer one already under the Bellhaven parent, then name match, then phone match, then billing history, then Active.

Each location lands in one of these buckets:

| Outcome | Proposal |
|---|---|
| Correct already | none |
| Outdated name / address field / wrong parent | `UPDATE` |
| Wrong parent **and** billing history | `CHOW` |
| Extra copies at the same address | `DUPLICATE` |
| No CRM account | `CREATE` |
| Under Bellhaven in the CRM but not on the website | `STALE` (status Needs Review plus a note; parent is left alone) |

## The billing SOP

When an account must move to a different parent:

- **revenue > 0 AND outstanding AR > 0**: the old account is not changed. A new account is created under the correct parent and `chow_current_account` is set on the old one.
- **otherwise**: direct re-parent.

This is enforced twice. `matching.py` chooses the right flow, and `app.py` re-reads the live account right before every write and refuses any re-parent of an account that has both revenue and AR, even if a proposal asks for it. Accounts already superseded by a CHOW are never modified again.

## Safe re-runs

Every proposal has a deterministic key (hash of what it would change). `store.py` only inserts keys it has never seen, so approved, rejected, applied and failed items are never re-proposed. Pending items that stop being true are marked `superseded` and come back if the problem returns. A scrape that looks broken (nothing found, a big drop, or incomplete records) aborts the run before anything is queued, so a website outage can never turn into "every account is stale".

Writes are checkpointed per step. A CHOW that creates the new account but fails before setting the pointer resumes from the pointer on retry and does not create a second account. Creates are refused if the same name already exists at that address under the same parent.

## Schedule

`.github/workflows/daily-sync.yml` runs the pipeline daily (11:17 UTC), restoring and re-saving `review.db` between runs through the Actions cache. A plain cron equivalent:

```
17 11 * * *  cd /path/to/bellhaven-sync && /usr/bin/python3 pipeline.py >> sync.log 2>&1
```

The scheduled job only queues proposals. Nothing reaches the CRM without a human in the app.
