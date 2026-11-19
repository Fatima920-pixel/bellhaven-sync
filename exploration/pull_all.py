import json
import urllib.request
from collections import Counter


def load_env(path=".env"):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


env = load_env()
API, TOKEN = env["BH_API"], env["BH_TOKEN"]


def get(path):
    req = urllib.request.Request(API + path, headers={"Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


accounts, page = [], 1
while True:
    d = get(f"/accounts?page={page}&page_size=50")
    accounts.extend(d["data"])
    if len(accounts) >= d["total"] or not d["data"]:
        break
    page += 1

with open("accounts.json", "w") as f:
    json.dump(accounts, f, indent=2)

print("Total pulled:", len(accounts))
print("\nBy status:", dict(Counter(a["status"] for a in accounts)))
print("\nBy parent_name:")
for p, n in Counter(a["parent_name"] or "(none)" for a in accounts).most_common():
    print(f"  {n:3d}  {p}")
print("\nAccounts with 'bellhaven' in the name:")
for a in accounts:
    if "bellhaven" in a["name"].lower():
        print(f"  {a['account_id']}  {a['name']}  | parent: {a['parent_name']}  | {a['status']}")