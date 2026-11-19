"""Thin CRM API client. Reads BH_TOKEN / BH_API from environment, falling back to .env."""
import json
import os
import time
import urllib.error
import urllib.request


class CrmError(Exception):
    pass


def _load_env(path=".env"):
    env = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


_FILE_ENV = _load_env()


def _cfg(name):
    val = os.environ.get(name) or _FILE_ENV.get(name)
    if not val:
        raise CrmError(f"Missing {name}: set it in .env or as an environment variable")
    return val


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        _cfg("BH_API") + path, data=data, method=method,
        headers={"Authorization": f"Bearer {_cfg('BH_TOKEN')}",
                 "Content-Type": "application/json"},
    )
    # Only GETs are retried: retrying a POST could create a duplicate account.
    attempts = 3 if method == "GET" else 1
    for i in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            if method == "GET" and e.code >= 500 and i < attempts - 1:
                time.sleep(2 * (i + 1))
                continue
            raise CrmError(f"{method} {path} -> HTTP {e.code}: {detail}")
        except urllib.error.URLError as e:
            if method == "GET" and i < attempts - 1:
                time.sleep(2 * (i + 1))
                continue
            raise CrmError(f"{method} {path} failed: {e}")


def pull_accounts():
    out, page = [], 1
    while True:
        d = call("GET", f"/accounts?page={page}&page_size=50")
        out.extend(d["data"])
        if not d["data"] or len(out) >= d["total"]:
            return out
        page += 1


def get_account(account_id):
    return call("GET", f"/accounts/{account_id}")


def update_account(account_id, body):
    return call("PATCH", f"/accounts/{account_id}", body)


def create_account(body):
    resp = call("POST", "/accounts", body)
    new_id = resp.get("account_id") or resp.get("id") if isinstance(resp, dict) else None
    if not new_id:
        raise CrmError(f"Create succeeded but no account id found in response: {resp}")
    return new_id, resp
