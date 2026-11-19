import store

c = store.connect()
print("Proposals by status:")
for r in c.execute("SELECT status, COUNT(*) n FROM proposals GROUP BY status"):
    print(f"  {r['status']}: {r['n']}")

print("\nNot yet applied:")
for r in c.execute("SELECT type, site_name, target_name, status, error FROM proposals "
                   "WHERE status NOT IN ('applied','superseded')"):
    print(f"  [{r['status']}] {r['type']} - {r['site_name'] or r['target_name']} {r['error'] or ''}")