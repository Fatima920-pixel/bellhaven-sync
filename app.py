"""Local review app. Run: python app.py  ->  http://127.0.0.1:8000

Nothing is written to the CRM until a reviewer clicks Approve.
"""
import html
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import crm
import matching
import store

PORT = 8000
STATUSES = ["pending", "applied", "rejected", "failed", "superseded"]


class Blocked(Exception):
    """A safety guard refused the write."""


# ------------------------------------------------------------------ applying
def _resolve(body, refs):
    out = {}
    for k, v in body.items():
        m = re.fullmatch(r"\{(\w+)\}", v) if isinstance(v, str) else None
        if m:
            if m.group(1) not in refs:
                raise Blocked(f"Placeholder {v} has no value yet")
            v = refs[m.group(1)]
        out[k] = v
    return out


def _guard_create(body):
    """Refuse to create an account that already exists (e.g. after a half-finished run)."""
    existing = crm.call("GET", "/accounts?zip=" + body["billing_zip"] + "&page_size=50")["data"]
    for a in existing:
        # Only an account already under the SAME parent counts. In a CHOW the old
        # account (other parent) legitimately has the same name and address.
        if (a["parent_id"] == body["parent_id"]
                and a["name"].strip().lower() == body["name"].strip().lower()
                and matching.norm_street(a["billing_street"]) == matching.norm_street(body["billing_street"])):
            raise Blocked(f"An account named '{a['name']}' already exists under this parent at this "
                          f"address ({a['account_id']}); refusing to create a duplicate")


def _guard_update(account_id, body):
    cur = crm.get_account(account_id)
    # A CHOW'd account is a preserved billing record: only its CHOW pointer may be set.
    if cur.get("chow_current_account") and set(body) - {"chow_current_account"}:
        raise Blocked(f"{account_id} was preserved by a CHOW (-> {cur['chow_current_account']}); "
                      "it must stay exactly as it is")
    # SOP: never re-parent an account that has revenue history AND outstanding AR.
    if ("parent_id" in body and cur["parent_id"] and body["parent_id"] != cur["parent_id"]
            and matching.has_billing_history(cur)):
        raise Blocked(f"SOP: {account_id} has lifetime_revenue={cur['lifetime_revenue']} and "
                      f"outstanding_ar={cur['outstanding_ar']}; parent must not change "
                      "(create a new account and set chow_current_account instead)")
    if "duplicate_of_account" in body:
        target = body["duplicate_of_account"]
        if target == account_id:
            raise Blocked("An account cannot be a duplicate of itself")
        surv = crm.get_account(target)
        if surv.get("status") == "Inactive" or surv.get("duplicate_of_account"):
            raise Blocked(f"Survivor {target} is itself inactive or a duplicate; refusing to chain duplicates")
    return cur


def apply_proposal(c, key):
    row = c.execute("SELECT * FROM proposals WHERE key=?", (key,)).fetchone()
    if not row or row["status"] not in ("pending", "failed"):
        return
    ops = json.loads(row["ops"])
    state = json.loads(row["result"] or "{}")
    refs, done = state.get("refs", {}), state.get("done", 0)

    def save(status, err=None):
        c.execute("UPDATE proposals SET status=?, error=?, result=?, decided_at=COALESCE(decided_at,?), "
                  "applied_at=? WHERE key=?",
                  (status, err, json.dumps({"refs": refs, "done": done}), store.now(),
                   store.now() if status == "applied" else None, key))
        c.commit()

    try:
        for i, op in enumerate(ops):
            if i < done:
                continue
            if op["op"] == "create":
                _guard_create(op["body"])
                new_id, _ = crm.create_account(op["body"])
                refs[op["ref"]] = new_id
            else:
                body = _resolve(op["body"], refs)
                _guard_update(op["account_id"], body)
                crm.update_account(op["account_id"], body)
            done = i + 1
            save("failed", "in progress")  # checkpoint so a retry resumes, never repeats
        save("applied")
    except (Blocked, crm.CrmError) as e:
        save("failed", str(e))


def reject_proposal(c, key):
    c.execute("UPDATE proposals SET status='rejected', decided_at=? WHERE key=? AND status IN ('pending','failed')",
              (store.now(), key))
    c.commit()


# ------------------------------------------------------------------ rendering
CSS = """
body{font-family:Segoe UI,Arial,sans-serif;background:#f4f2ea;margin:0;color:#222}
header{background:#2E5D50;color:#fff;padding:14px 24px}
header h1{margin:0;font-size:20px} header p{margin:4px 0 0;font-size:13px;opacity:.85}
.wrap{max-width:1000px;margin:0 auto;padding:18px 24px 60px}
.tabs a{display:inline-block;padding:6px 14px;margin:0 6px 10px 0;border-radius:4px;background:#fff;
  color:#2E5D50;text-decoration:none;border:1px solid #d8d3c0;font-size:14px}
.tabs a.on{background:#2E5D50;color:#fff}
.card{background:#fff;border:1px solid #d8d3c0;border-radius:6px;padding:14px 18px;margin:12px 0}
.card h3{margin:0 0 6px;font-size:17px}
.tag{display:inline-block;font-size:11px;padding:2px 8px;border-radius:3px;margin-right:6px;color:#fff}
.UPDATE{background:#3b7ea1}.CREATE{background:#2e8b57}.DUPLICATE{background:#8a6d3b}
.CHOW{background:#8e44ad}.STALE{background:#b5651d}
.high{background:#e6f4ea;color:#1e6b34}.medium{background:#fff4d6;color:#7a5b00}
.tag.high,.tag.medium{border:1px solid #ccc}
ul.ev{margin:8px 0;padding-left:20px;font-size:14px}
table.d{border-collapse:collapse;font-size:13px;margin:8px 0;width:100%}
table.d td,table.d th{border:1px solid #e3dfd0;padding:4px 8px;text-align:left}
table.d th{background:#f4f2ea}.from{color:#a33}.to{color:#176b2c;font-weight:600}
form{display:inline}
button{padding:7px 18px;border:0;border-radius:4px;font-size:14px;cursor:pointer;margin-right:8px}
.ok{background:#2E5D50;color:#fff}.no{background:#fff;color:#a33;border:1px solid #a33}
.bulk{background:#C9A227;color:#222}
.err{color:#a33;font-size:13px;margin-top:6px}.muted{color:#777;font-size:13px}
"""


def e(x):
    return html.escape("" if x is None else str(x))


def fmt(v):
    return "(empty)" if v in (None, "") else e(v)


def render_card(r):
    ev = "".join(f"<li>{e(x)}</li>" for x in json.loads(r["evidence"]))
    rows = ""
    for d in json.loads(r["diff"]):
        who = "NEW account" if d["account_id"] == "(new)" else d["account_id"]
        rows += (f"<tr><td>{e(who)}</td><td>{e(d['field'])}</td>"
                 f"<td class='from'>{fmt(d['from'])}</td><td class='to'>{fmt(d['to'])}</td></tr>")
    title = r["site_name"] or r["target_name"] or r["target_account_id"]
    buttons = ""
    if r["status"] in ("pending", "failed"):
        label = "Retry" if r["status"] == "failed" else "Approve &amp; write to CRM"
        buttons = (f"<form method='post' action='/approve?key={r['key']}'><button class='ok'>{label}</button></form>"
                   f"<form method='post' action='/reject?key={r['key']}'><button class='no'>Reject</button></form>")
    err = f"<div class='err'>{e(r['error'])}</div>" if r["error"] and r["status"] == "failed" else ""
    done = f"<div class='muted'>{e(r['status'])} {e(r['applied_at'] or r['decided_at'] or '')}</div>" \
        if r["status"] not in ("pending", "failed") else ""
    return (f"<div class='card'><h3><span class='tag {r['type']}'>{r['type']}</span>"
            f"<span class='tag {r['confidence']}'>{r['confidence']} confidence</span>{e(title)}</h3>"
            f"<div class='muted'>target: {e(r['target_account_id'] or 'new account')} &middot; {e(r['category'])}</div>"
            f"<b style='font-size:13px'>Evidence</b><ul class='ev'>{ev}</ul>"
            f"<table class='d'><tr><th>Account</th><th>Field</th><th>Current</th><th>Proposed</th></tr>{rows}</table>"
            f"{buttons}{err}{done}</div>")


def render_page(c, status):
    counts = {s: 0 for s in STATUSES}
    for r in c.execute("SELECT status, COUNT(*) n FROM proposals GROUP BY status"):
        counts[r["status"]] = r["n"]
    tabs = "".join(f"<a class='{'on' if s == status else ''}' href='/?status={s}'>{s} ({counts.get(s, 0)})</a>"
                   for s in STATUSES)
    order = "CASE type WHEN 'CHOW' THEN 0 WHEN 'UPDATE' THEN 1 WHEN 'DUPLICATE' THEN 2 WHEN 'CREATE' THEN 3 ELSE 4 END"
    rows = c.execute(f"SELECT * FROM proposals WHERE status=? ORDER BY {order}, site_name", (status,)).fetchall()
    bulk = ""
    if status == "pending" and any(r["confidence"] == "high" for r in rows):
        bulk = ("<form method='post' action='/approve_high' onsubmit=\"return confirm("
                "'Approve and write ALL high-confidence pending proposals to the CRM?')\">"
                "<button class='bulk'>Approve all high-confidence</button></form>")
    cards = "".join(render_card(r) for r in rows) or "<p class='muted'>Nothing here.</p>"
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>Bellhaven review</title>"
            f"<style>{CSS}</style></head><body><header><h1>Bellhaven CRM review queue</h1>"
            f"<p>Nothing is written to the CRM until you click Approve.</p></header>"
            f"<div class='wrap'><div class='tabs'>{tabs}</div>{bulk}{cards}</div></body></html>")


# ------------------------------------------------------------------ server
class Handler(BaseHTTPRequestHandler):
    def _redirect(self, to="/"):
        self.send_response(303)
        self.send_header("Location", to)
        self.end_headers()

    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        status = q.get("status", ["pending"])[0]
        if status not in STATUSES:
            status = "pending"
        c = store.connect()
        body = render_page(c, status).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        u = urlparse(self.path)
        key = parse_qs(u.query).get("key", [""])[0]
        c = store.connect()
        back = "/"
        if u.path == "/approve":
            apply_proposal(c, key)
        elif u.path == "/reject":
            reject_proposal(c, key)
        elif u.path == "/approve_high":
            keys = [r["key"] for r in c.execute(
                "SELECT key FROM proposals WHERE status='pending' AND confidence='high'")]
            for k in keys:
                apply_proposal(c, k)
        r = c.execute("SELECT status FROM proposals WHERE key=?", (key,)).fetchone()
        if r and r["status"] == "failed":
            back = "/?status=failed"
        self._redirect(back)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    store.connect().close()
    print(f"Review app running at http://127.0.0.1:{PORT}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
