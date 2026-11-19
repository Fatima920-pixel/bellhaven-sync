"""SQLite store for proposals. Doubles as the memory that makes re-runs safe."""
import json
import sqlite3
from datetime import datetime, timezone

DB_PATH = "review.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS proposals (
  key TEXT PRIMARY KEY,
  type TEXT, category TEXT, confidence TEXT,
  site_name TEXT, target_account_id TEXT, target_name TEXT,
  evidence TEXT, ops TEXT, diff TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  first_seen TEXT, last_seen TEXT, decided_at TEXT, applied_at TEXT,
  error TEXT, result TEXT
);
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT, accounts INTEGER, site_locations INTEGER,
  new_proposals INTEGER, skipped INTEGER, superseded INTEGER
);
"""
# status: pending | approved | rejected | applied | failed | superseded


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path=None):
    c = sqlite3.connect(path or DB_PATH)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def last_site_count(c):
    r = c.execute("SELECT site_locations FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    return r["site_locations"] if r else None


def sync_proposals(c, proposals):
    """Insert genuinely new proposals. Never touch anything already decided."""
    existing = {r["key"]: r["status"] for r in c.execute("SELECT key, status FROM proposals")}
    seen, new, skipped = set(), 0, 0
    t = now()
    for p in proposals:
        seen.add(p["key"])
        st = existing.get(p["key"])
        if st is None:
            c.execute(
                "INSERT INTO proposals (key,type,category,confidence,site_name,target_account_id,"
                "target_name,evidence,ops,diff,status,first_seen,last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (p["key"], p["type"], p["category"], p["confidence"], p["site_name"],
                 p["target_account_id"], p["target_name"], json.dumps(p["evidence"]),
                 json.dumps(p["ops"]), json.dumps(p["diff"]), "pending", t, t))
            new += 1
        elif st in ("pending", "superseded"):
            # still open (or came back): refresh evidence, keep it pending
            c.execute("UPDATE proposals SET evidence=?, diff=?, confidence=?, status='pending', last_seen=? WHERE key=?",
                      (json.dumps(p["evidence"]), json.dumps(p["diff"]), p["confidence"], t, p["key"]))
            skipped += 1
        else:
            skipped += 1  # approved / rejected / applied / failed: already decided, leave alone
    superseded = 0
    for key, st in existing.items():
        if st == "pending" and key not in seen:
            c.execute("UPDATE proposals SET status='superseded', last_seen=? WHERE key=?", (t, key))
            superseded += 1
    c.commit()
    return new, skipped, superseded


def log_run(c, accounts, site, new, skipped, superseded):
    c.execute("INSERT INTO runs (started_at,accounts,site_locations,new_proposals,skipped,superseded) VALUES (?,?,?,?,?,?)",
              (now(), accounts, site, new, skipped, superseded))
    c.commit()
