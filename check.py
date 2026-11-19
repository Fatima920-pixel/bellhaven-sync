import crm

for name in ("Portsmouth", "Batavia"):
    for a in crm.pull_accounts():
        if name in a["name"]:
            print(a["account_id"], "|", a["name"], "|", a["billing_street"],
                  a["billing_city"], a["billing_zip"], "|", a["parent_name"], "|", a["status"])