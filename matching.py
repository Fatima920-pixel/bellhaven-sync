"""Matching + classification: website locations -> CRM accounts -> proposals.

Pure logic, no network and no writes. build_proposals() returns a list of
proposal dicts that the review app (Step 4) shows to a human. Nothing here
touches the CRM.
"""
import hashlib
import json
import re

PARENT_NAME = "Bellhaven Senior Living (Parent Account)"

ABBR = {
    "street": "st", "road": "rd", "avenue": "ave", "boulevard": "blvd",
    "drive": "dr", "lane": "ln", "court": "ct", "highway": "hwy",
    "pike": "pk", "parkway": "pkwy", "place": "pl", "circle": "cir",
    "terrace": "ter", "square": "sq", "trail": "trl",
    "northwest": "nw", "northeast": "ne", "southwest": "sw",
    "southeast": "se", "north": "n", "south": "s", "east": "e", "west": "w",
}
STOP = {"bellhaven", "senior", "living", "of", "at", "the", "and"}
CARE_MAP = {
    "assisted living": "Assisted Living",
    "memory support": "Memory Care",
    "short-term rehabilitation & nursing": "Skilled Nursing",
}


# ---------- normalization helpers ----------
def norm_street(s):
    s = (s or "").lower().replace("&", " and ")
    words = re.sub(r"[^a-z0-9 ]", " ", s).split()
    return " ".join(ABBR.get(w, w) for w in words)


def zip5(z):
    return (z or "").strip()[:5]


def digits(p):
    return re.sub(r"\D", "", p or "")


def core_name(n):
    words = re.sub(r"[^a-z0-9 ]", " ", (n or "").lower()).split()
    return " ".join(w for w in words if w not in STOP)


def money(a, field):
    return a.get(field) or 0


def has_billing_history(a):
    return money(a, "lifetime_revenue") > 0 and money(a, "outstanding_ar") > 0


def fingerprint(ptype, site_slug, ops):
    """Stable id: same underlying proposal -> same key on every run."""
    blob = json.dumps({"t": ptype, "s": site_slug, "ops": ops}, sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()[:16]


# ---------- matching ----------
def find_candidates(loc, free):
    """Return (candidates, method, confidence) for one website location."""
    lk, lz = norm_street(loc["street"]), zip5(loc["zip"])
    lcity, lstate = loc["city"].lower(), loc["state"].upper()

    def same_city(a):
        return (a["billing_city"].strip().lower() == lcity
                and a["billing_state"].strip().upper() == lstate)

    exact = [a for a in free
             if norm_street(a["billing_street"]) == lk
             and (zip5(a["billing_zip"]) == lz or same_city(a))]
    if exact:
        return exact, "same address", "high"

    # Fallback: same city AND same phone number. A similar name alone is NOT enough
    # to treat two accounts as the same facility (different street + phone = likely
    # a different building), so name-only look-alikes never match here.
    ph, lcore = digits(loc["phone"]), core_name(loc["name"])
    soft = [a for a in free if same_city(a) and ph and digits(a["phone"]) == ph]
    if soft:
        strong = any(core_name(a["name"]) == lcore for a in soft)
        return soft, "same city + phone", "high" if strong else "medium"
    return [], None, None


def near_misses(loc, free):
    """Same-city accounts with a look-alike name. Shown as evidence, never matched."""
    lcore = core_name(loc["name"])
    return [a for a in free
            if a["billing_city"].strip().lower() == loc["city"].lower()
            and a["billing_state"].strip().upper() == loc["state"].upper()
            and core_name(a["name"]) == lcore]


def pick_survivor(cands, loc, parent_id):
    ph = digits(loc["phone"])

    def score(a):
        return (
            a["parent_id"] == parent_id,
            a["name"].strip().lower() == loc["name"].strip().lower(),
            bool(ph) and digits(a["phone"]) == ph,
            money(a, "lifetime_revenue") > 0 or money(a, "outstanding_ar") > 0,
            a["status"] == "Active",
            not a["parent_id"],
        )

    return sorted(cands, key=lambda a: (tuple(-int(x) for x in score(a)), a["account_id"]))[0]


# ---------- proposal builders ----------
def new_account_body(loc, parent_id):
    first = (loc.get("care_offerings") or [""])[0].lower()
    return {
        "name": loc["name"],
        "parent_id": parent_id,
        "billing_street": loc["street"],
        "billing_city": loc["city"],
        "billing_state": loc["state"],
        "billing_zip": loc["zip"],
        "care_type": CARE_MAP.get(first, loc["care_offerings"][0] if loc.get("care_offerings") else ""),
        "phone": loc["phone"],
        "status": "Active",
        "note": "Created by Bellhaven website sync from " + loc["url"],
    }


def make(ptype, category, conf, loc, target, ops, evidence, accounts_by_id):
    diff = []
    for op in ops:
        if op["op"] == "update":
            cur = accounts_by_id.get(op["account_id"], {})
            for k, v in op["body"].items():
                diff.append({"account_id": op["account_id"], "field": k,
                             "from": cur.get(k), "to": v})
        else:
            for k, v in op["body"].items():
                diff.append({"account_id": "(new)", "field": k, "from": None, "to": v})
    return {
        "key": fingerprint(ptype, loc["slug"] if loc else target, ops),
        "type": ptype,
        "category": category,
        "confidence": conf,
        "site_slug": loc["slug"] if loc else None,
        "site_name": loc["name"] if loc else None,
        "target_account_id": target,
        "target_name": accounts_by_id[target]["name"] if target in accounts_by_id else None,
        "evidence": evidence,
        "ops": ops,
        "diff": diff,
    }


def survivor_proposal(a, loc, method, conf, parent_id, losers, by_id):
    ev = [f"Matched website '{loc['name']}' by {method}"]
    body = {}

    if a["name"].strip().lower() != loc["name"].strip().lower():
        body["name"] = loc["name"]
        ev.append(f"Website name '{loc['name']}' differs from CRM name '{a['name']}'")

    if norm_street(a["billing_street"]) != norm_street(loc["street"]):
        body["billing_street"] = loc["street"]
        ev.append(f"Street differs: CRM '{a['billing_street']}' vs website '{loc['street']}'")
    if zip5(a["billing_zip"]) != zip5(loc["zip"]):
        body["billing_zip"] = loc["zip"]
        ev.append(f"Zip differs: CRM '{a['billing_zip']}' vs website '{loc['zip']}'")
    if a["billing_city"].strip().lower() != loc["city"].lower():
        body["billing_city"] = loc["city"]
        ev.append(f"City differs: CRM '{a['billing_city']}' vs website '{loc['city']}'")
    if a["billing_state"].strip().upper() != loc["state"].upper():
        body["billing_state"] = loc["state"]
        ev.append(f"State differs: CRM '{a['billing_state']}' vs website '{loc['state']}'")
    if a["status"] != "Active":
        body["status"] = "Active"
        ev.append(f"Listed on website but CRM status is {a['status']}")

    if a["parent_id"] != parent_id:
        old_parent = a["parent_name"] or "no parent"
        rev, ar = money(a, "lifetime_revenue"), money(a, "outstanding_ar")
        if a["parent_id"] and has_billing_history(a):
            # SOP: revenue history AND outstanding AR -> keep old account untouched,
            # create a new account under Bellhaven, point old one at it via CHOW.
            ev.append(f"Website lists this under Bellhaven but CRM parent is {old_parent}")
            ev.append(f"SOP: lifetime_revenue={rev} and outstanding_ar={ar} (both > 0), "
                      "so the old account is preserved unchanged; new account created, "
                      "CHOW pointer set on the old one")
            ops = [
                {"op": "create", "ref": "new_account", "body": new_account_body(loc, parent_id)},
                {"op": "update", "account_id": a["account_id"],
                 "body": {"chow_current_account": "{new_account}"}},
            ]
            return make("CHOW", "wrong_parent_billing_history", conf, loc,
                        a["account_id"], ops, ev, by_id)
        body["parent_id"] = parent_id
        why = "no parent in CRM" if not a["parent_id"] else f"CRM parent is {old_parent}"
        ev.append(f"Website lists this under Bellhaven; {why}")
        if a["parent_id"]:
            ev.append(f"SOP check: lifetime_revenue={rev}, outstanding_ar={ar} "
                      "(not both > 0) so direct re-parent is allowed")

    if losers and any(has_billing_history(x) or money(x, "lifetime_revenue") > 0 for x in losers):
        ev.append("Note: a duplicate copy has revenue history; reviewer should confirm survivor")
    if not body:
        return None
    category = "wrong_parent" if "parent_id" in body else "match_needs_fix"
    ops = [{"op": "update", "account_id": a["account_id"], "body": body}]
    return make("UPDATE", category, conf, loc, a["account_id"], ops, ev, by_id)


def build_proposals(accounts, site):
    by_id = {a["account_id"]: a for a in accounts}
    parent = next(a for a in accounts if a["name"] == PARENT_NAME)
    P = parent["account_id"]
    # Accounts already superseded by a CHOW are preserved billing records: leave them alone.
    pool = [a for a in accounts
            if "(Parent Account)" not in a["name"] and not a.get("chow_current_account")]
    claimed, proposals, clean = set(), [], []

    for loc in site:
        free = [a for a in pool if a["account_id"] not in claimed]
        cands, method, conf = find_candidates(loc, free)

        if not cands:
            ops = [{"op": "create", "ref": "new_account", "body": new_account_body(loc, P)}]
            ev = [f"No CRM account found at {loc['street']}, {loc['city']}, {loc['state']} {loc['zip']}",
                  "No same-city account has the same phone number either"]
            cconf = "high"
            for nm in near_misses(loc, free):
                cconf = "medium"
                ev.append(f"Look-alike NOT matched: '{nm['name']}' ({nm['account_id']}, parent "
                          f"{nm['parent_name'] or 'none'}) at {nm['billing_street']}, {nm['billing_city']}: "
                          "different street and phone, so treated as a separate facility and left untouched. "
                          "Reviewer: reject if this is really the same building.")
            proposals.append(make("CREATE", "new_location", cconf, loc, None, ops, ev, by_id))
            continue

        survivor = pick_survivor(cands, loc, P)
        losers = [a for a in cands if a is not survivor]
        for a in cands:
            claimed.add(a["account_id"])

        sp = survivor_proposal(survivor, loc, method, conf, P, losers, by_id)
        if sp:
            proposals.append(sp)
        else:
            clean.append((loc["name"], survivor["account_id"]))

        for lo in losers:
            if lo.get("duplicate_of_account") == survivor["account_id"] and lo["status"] == "Inactive":
                continue  # already resolved
            note = f"Duplicate of {survivor['account_id']} ({survivor['name']}): same address on Bellhaven website."
            if lo.get("note"):
                note = lo["note"] + " | " + note
            ev = [f"Same address as {survivor['account_id']} ({survivor['name']}): "
                  f"{loc['street']}, {loc['city']} {loc['zip']}",
                  f"Survivor chosen: parent={survivor['parent_name'] or 'none'}, "
                  f"name/phone closest to website; this copy parent={lo['parent_name'] or 'none'}"]
            dconf = "high"
            if money(lo, "lifetime_revenue") > 0 or money(lo, "outstanding_ar") > 0:
                ev.append(f"WARNING: this copy has billing history (rev={money(lo, 'lifetime_revenue')}, "
                          f"ar={money(lo, 'outstanding_ar')})")
                dconf = "medium"
            ops = [{"op": "update", "account_id": lo["account_id"],
                    "body": {"duplicate_of_account": survivor["account_id"],
                             "status": "Inactive", "note": note}}]
            proposals.append(make("DUPLICATE", "duplicate", dconf, loc, lo["account_id"], ops, ev, by_id))

    for a in pool:
        if a["parent_id"] == P and a["account_id"] not in claimed and a["status"] == "Active":
            rev, ar = money(a, "lifetime_revenue"), money(a, "outstanding_ar")
            note = ("Not listed on Bellhaven website at last sync; verify whether sold, closed "
                    "or renamed. Parent left unchanged.")
            if a.get("note"):
                note = a["note"] + " | " + note
            ev = [f"CRM parent is Bellhaven but no website location matches "
                  f"{a['billing_street']}, {a['billing_city']} {a['billing_zip']}",
                  f"Billing: lifetime_revenue={rev}, outstanding_ar={ar}"]
            if rev > 0 and ar > 0:
                ev.append("Has billing history: parent must NOT be changed")
            ops = [{"op": "update", "account_id": a["account_id"],
                    "body": {"status": "Needs Review", "note": note}}]
            proposals.append(make("STALE", "not_on_website", "medium", None, a["account_id"], ops, ev, by_id))

    return proposals, clean


if __name__ == "__main__":
    accounts = json.load(open("accounts.json", encoding="utf-8"))
    site = json.load(open("site_locations.json", encoding="utf-8"))
    proposals, clean = build_proposals(accounts, site)

    with open("proposals_preview.json", "w", encoding="utf-8") as f:
        json.dump(proposals, f, indent=2, ensure_ascii=False)

    print(f"{len(clean)} locations already correct, {len(proposals)} proposals\n")
    counts = {}
    for p in proposals:
        counts[p["type"]] = counts.get(p["type"], 0) + 1
    print("By type:", counts, "\n")
    for p in sorted(proposals, key=lambda x: (x["type"], x["site_name"] or "")):
        label = p["site_name"] or p["target_name"]
        print(f"[{p['type']:9}] [{p['confidence']:6}] {label}")
        for d in p["diff"]:
            if d["account_id"] == "(new)" and d["field"] not in ("name", "parent_id"):
                continue
            print(f"      {d['account_id']}.{d['field']}: {d['from']!r} -> {d['to']!r}")