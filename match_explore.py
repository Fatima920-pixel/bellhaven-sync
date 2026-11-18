import json
import re
from difflib import SequenceMatcher

BELLHAVEN_PARENT = "0015QAPLGS3FVYEEEM"

accounts = json.load(open("accounts.json", encoding="utf-8"))
site = json.load(open("site_locations.json", encoding="utf-8"))

ABBR = {"street": "st", "road": "rd", "avenue": "ave", "boulevard": "blvd",
        "drive": "dr", "lane": "ln", "court": "ct", "highway": "hwy",
        "north": "n", "south": "s", "east": "e", "west": "w"}


def norm_street(s):
    words = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split()
    return " ".join(ABBR.get(w, w) for w in words)


def addr_key(street, zip_):
    return (norm_street(street), (zip_ or "").strip()[:5])


def sim(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


by_addr = {}
for a in accounts:
    by_addr.setdefault(addr_key(a["billing_street"], a["billing_zip"]), []).append(a)

matched_ids = set()
print("=== SITE LOCATIONS ===")
for loc in site:
    hits = by_addr.get(addr_key(loc["street"], loc["zip"]), [])
    if not hits:
        cands = [a for a in accounts
                 if a["billing_city"].lower() == loc["city"].lower()
                 and a["billing_state"].upper() == loc["state"].upper()]
        best = max(cands, key=lambda a: sim(a["name"], loc["name"]), default=None)
        if best:
            print(f"NO ADDR MATCH  {loc['name']} ({loc['city']}, {loc['state']}) -> "
                  f"closest in city: {best['name']} [{best['account_id']}] "
                  f"{best['billing_street']} {best['billing_zip']}")
        else:
            print(f"NO CRM ACCOUNT {loc['name']} ({loc['city']}, {loc['state']}) {loc['street']} {loc['zip']}")
        continue
    for a in hits:
        matched_ids.add(a["account_id"])
    flags = []
    if len(hits) > 1:
        flags.append(f"DUPLICATES x{len(hits)}")
    for a in hits:
        if a["parent_id"] != BELLHAVEN_PARENT:
            flags.append(f"parent={a['parent_name'] or 'NONE'}")
        if a["name"] != loc["name"]:
            flags.append(f"name differs: '{a['name']}'")
        if a["status"] != "Active":
            flags.append(f"status={a['status']}")
    tag = "OK            " if not flags else "CHECK         "
    print(f"{tag} {loc['name']} -> {[a['account_id'] for a in hits]} {'; '.join(flags)}")

print("\n=== BELLHAVEN-PARENT ACCOUNTS NOT MATCHED TO ANY WEBSITE ADDRESS ===")
for a in accounts:
    if a["parent_id"] == BELLHAVEN_PARENT and a["account_id"] not in matched_ids:
        print(f"{a['account_id']} {a['name']} | {a['billing_street']}, {a['billing_city']} {a['billing_zip']} "
              f"| {a['status']} | rev={a['lifetime_revenue']} ar={a['outstanding_ar']}")