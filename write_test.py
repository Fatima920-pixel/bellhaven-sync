import json
import urllib.error
import urllib.request


def load_env(path=".env"):
    env = {}
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


env = load_env()
API, TOKEN = env["BH_API"], env["BH_TOKEN"]
ACCOUNT = "001L3LGR6W69J8DYYV"  # Bellhaven of Maplewood (already correct)


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        API + path, data=data, method=method,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


status, before = call("GET", f"/accounts/{ACCOUNT}")
print("GET before:", status)
print(json.dumps(before, indent=2))

status, resp = call("PATCH", f"/accounts/{ACCOUNT}", {"name": before["name"]})
print("\nPATCH no-op status:", status)
print(json.dumps(resp, indent=2) if not isinstance(resp, str) else resp)