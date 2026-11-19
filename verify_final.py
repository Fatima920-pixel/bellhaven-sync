from collections import Counter

import crm

accts = crm.pull_accounts()
by = {a["account_id"]: a for a in accts}
P = next(a["account_id"] for a in accts if a["name"] == "Bellhaven Senior Living (Parent Account)")

under = [a for a in accts if a["parent_id"] == P]
print("Total accounts:", len(accts))
print("Under Bellhaven parent:", len(under), dict(Counter(a["status"] for a in under)))

print("\nCHOW pairs (old account -> new account):")
for a in accts:
    if a["chow_current_account"]:
        n = by.get(a["chow_current_account"], {})
        print(f"  OLD {a['name']} [{a['account_id']}] parent={a['parent_name']} "
              f"rev={a['lifetime_revenue']} ar={a['outstanding_ar']} status={a['status']}")
        print(f"  NEW {n.get('name')} [{n.get('account_id')}] parent={n.get('parent_name')}")

print("\nDuplicates marked:")
for a in accts:
    if a["duplicate_of_account"]:
        print(f"  {a['name']} [{a['account_id']}] -> {a['duplicate_of_account']} ({a['status']})")

print("\nNeeds Review:")
for a in accts:
    if a["status"] == "Needs Review":
        print(f"  {a['name']} [{a['account_id']}] parent={a['parent_name']} "
              f"rev={a['lifetime_revenue']} ar={a['outstanding_ar']}")

print("\nAccounts with revenue AND outstanding AR (billing history):")
for a in accts:
    if (a["lifetime_revenue"] or 0) > 0 and (a["outstanding_ar"] or 0) > 0:
        print(f"  {a['name']} [{a['account_id']}] parent={a['parent_name']} chow={a['chow_current_account'] or '-'}")