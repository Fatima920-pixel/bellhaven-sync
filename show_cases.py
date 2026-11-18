import json

accounts = json.load(open("accounts.json", encoding="utf-8"))
site = json.load(open("site_locations.json", encoding="utf-8"))

names = ["Port Clinton", "Erie", "Kettering", "Monroe", "Owosso", "Zanesville",
         "Chagrin Falls", "Willow Creek", "Ashtabula", "Portsmouth", "Union Square",
         "Chesterton", "Batavia", "Carlisle", "Amberly", "Findlay", "Toledo",
         "Lima", "Tiffin", "Marietta"]
extra_ids = ["00116ETS45BL7DTQP7", "0016PVXH4B25HWR7QE", "001SXSF4ELF0Z2LGDM"]

out = []
for n in names:
    for loc in site:
        if n.lower() in loc["name"].lower():
            out.append(f"\n##### SITE: {loc['name']} | {loc['street']}, {loc['city']}, {loc['state']} {loc['zip']} | {loc['phone']} | {loc['care_offerings']}")
            for a in accounts:
                if (a["billing_city"].lower() == loc["city"].lower()
                        or a["billing_zip"][:5] == loc["zip"]
                        or n.lower() in a["name"].lower()):
                    out.append(
                        f"   CRM {a['account_id']} | {a['name']} | {a['billing_street']}, {a['billing_city']} {a['billing_state']} {a['billing_zip']}"
                        f" | {a['phone']} | parent={a['parent_name'] or 'NONE'} | {a['status']}"
                        f" | rev={a['lifetime_revenue']} ar={a['outstanding_ar']} | care={a['care_type']}"
                        f" | note='{a['note']}' | chow='{a['chow_current_account']}' | dup='{a['duplicate_of_account']}'")

out.append("\n##### CRM-only accounts under Bellhaven")
for a in accounts:
    if a["account_id"] in extra_ids:
        out.append(f"   CRM {a['account_id']} | {a['name']} | {a['billing_street']}, {a['billing_city']} {a['billing_zip']} | {a['phone']} | rev={a['lifetime_revenue']} ar={a['outstanding_ar']} | note='{a['note']}'")

open("cases.txt", "w", encoding="utf-8").write("\n".join(out))
print("Saved cases.txt with", len(out), "lines")