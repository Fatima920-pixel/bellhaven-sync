import html
import json
import re
import urllib.request

BASE = "https://analyst-assessment-production.up.railway.app"


def fetch(path):
    return urllib.request.urlopen(BASE + path).read().decode("utf-8")


def clean(s):
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def get_listing_links():
    """Walk every directory page and return {slug: name}."""
    found, page, total_pages = {}, 1, 1
    while page <= total_pages:
        doc = fetch(f"/communities?page={page}")
        m = re.search(r"Page\s+\d+\s+of\s+(\d+)", doc)
        if m:
            total_pages = int(m.group(1))
        for slug, name in re.findall(
            r'<h3><a href="/communities/([^"]+)">(.*?)</a></h3>', doc
        ):
            found[slug] = clean(name)
        page += 1
    return found


def get_homepage_links():
    """Catch communities linked on the homepage but not in the directory."""
    doc = fetch("/")
    return {
        slug: clean(name)
        for slug, name in re.findall(r'<a href="/communities/([^"?]+)">(.*?)</a>', doc)
    }


def parse_detail(slug):
    doc = fetch(f"/communities/{slug}")
    rec = {"slug": slug, "url": f"{BASE}/communities/{slug}"}
    m = re.search(r"<h1>(.*?)</h1>", doc, re.S)
    rec["name"] = clean(m.group(1)) if m else ""

    fields = {
        clean(k).lower(): v
        for k, v in re.findall(r"<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", doc, re.S)
    }

    addr_lines = [l.strip() for l in clean(fields.get("address", "")).split("\n") if l.strip()]
    rec["street"], rec["city"], rec["state"], rec["zip"] = "", "", "", ""
    if addr_lines:
        last = addr_lines[-1]
        m = re.match(r"^(.*?),\s*([A-Za-z]{2})\s+(\d{5})", last)
        if m:
            rec["city"], rec["state"], rec["zip"] = m.group(1), m.group(2).upper(), m.group(3)
            rec["street"] = ", ".join(addr_lines[:-1])
        else:
            rec["street"] = ", ".join(addr_lines)

    care_html = fields.get("care offerings", "")
    rec["care_offerings"] = [
        clean(b) for b in re.findall(r'<span class="badge">(.*?)</span>', care_html, re.S)
    ]
    rec["administrator"] = clean(fields.get("administrator", ""))
    rec["phone"] = clean(fields.get("phone", ""))
    rec["raw_labels"] = sorted(fields.keys())
    return rec


def main():
    listing = get_listing_links()
    home = get_homepage_links()
    extra = {s: n for s, n in home.items() if s not in listing}
    print(f"Directory: {len(listing)} communities | extra on homepage only: {extra}")

    slugs = {**listing, **extra}
    records = []
    for slug in slugs:
        rec = parse_detail(slug)
        rec["listed_in_directory"] = slug in listing
        records.append(rec)
        problems = [k for k in ("street", "city", "state", "zip") if not rec[k]]
        if problems:
            print("WARN missing", problems, "for", slug)

    with open("site_locations.json", "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(records)} locations to site_locations.json")
    print("Field labels seen:", sorted({l for r in records for l in r["raw_labels"]}))
    for r in records[:3]:
        print(json.dumps({k: v for k, v in r.items() if k != "raw_labels"}, indent=2))


if __name__ == "__main__":
    main()