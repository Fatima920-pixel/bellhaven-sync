import crm

for a in crm.pull_accounts():
    if "Tiffin" in a["name"]:
        print(a["account_id"], "|", a["name"], "|", a["parent_name"], "|", a["status"],
              "| rev", a["lifetime_revenue"], "ar", a["outstanding_ar"],
              "| chow ->", a["chow_current_account"] or "-")