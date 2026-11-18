import json
import urllib.request


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
API = env["BH_API"]
TOKEN = env["BH_TOKEN"]


def get(path):
    req = urllib.request.Request(
        API + path, headers={"Authorization": f"Bearer {TOKEN}"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


data = get("/accounts")

with open("all_accounts_raw.json", "w") as f:
    json.dump(data, f, indent=2)

print("Response type:", type(data).__name__)
if isinstance(data, dict):
    print("Top-level keys:", list(data.keys()))
    for k, v in data.items():
        if isinstance(v, list):
            print(f"List '{k}' has {len(v)} items")
            if v:
                print("First record:")
                print(json.dumps(v[0], indent=2))
        else:
            print(f"{k}: {v}")
else:
    print("Count:", len(data))
    if data:
        print("First record:")
        print(json.dumps(data[0], indent=2))