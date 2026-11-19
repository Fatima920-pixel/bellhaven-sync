"""One full run: pull CRM + scrape website -> match -> queue NEW proposals for review.

Safe to run as often as you like. Writes nothing to the CRM.
"""
import json
import sys

import crm
import matching
import scraper
import store


def scrape_all():
    listing = scraper.get_listing_links()
    home = scraper.get_homepage_links()
    slugs = list(listing) + [s for s in home if s not in listing]
    records = []
    for slug in slugs:
        rec = scraper.parse_detail(slug)
        rec["listed_in_directory"] = slug in listing
        records.append(rec)
    return records


def run():
    c = store.connect()
    accounts = crm.pull_accounts()
    site = scrape_all()

    # Safety net: a broken scrape must never turn into "everything is stale".
    prev = store.last_site_count(c)
    bad = [r["slug"] for r in site if not (r["street"] and r["city"] and r["state"] and r["zip"])]
    if not site or (prev and len(site) < 0.8 * prev) or bad:
        print(f"ABORT: scrape looks wrong (found {len(site)}, previous run {prev}, incomplete: {bad}).")
        print("Nothing was queued.")
        return 1

    json.dump(accounts, open("accounts.json", "w", encoding="utf-8"), indent=2)
    json.dump(site, open("site_locations.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    proposals, clean = matching.build_proposals(accounts, site)
    new, skipped, superseded = store.sync_proposals(c, proposals)
    store.log_run(c, len(accounts), len(site), new, skipped, superseded)

    print(f"CRM accounts: {len(accounts)} | website locations: {len(site)} | already correct: {len(clean)}")
    print(f"Proposals found this run: {len(proposals)}")
    print(f"  NEW queued for review : {new}")
    print(f"  already known/decided : {skipped}")
    print(f"  no longer needed      : {superseded}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
