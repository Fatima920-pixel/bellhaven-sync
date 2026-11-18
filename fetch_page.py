import urllib.request

base = "https://analyst-assessment-production.up.railway.app"


def fetch(path):
    return urllib.request.urlopen(base + path).read().decode("utf-8")


listing = fetch("/communities?page=1")
detail = fetch("/communities/bellhaven-of-maplewood")

with open("communities_p1.html", "w", encoding="utf-8") as f:
    f.write(listing)
with open("detail_maplewood.html", "w", encoding="utf-8") as f:
    f.write(detail)

i = listing.find("Maplewood")
print("===== LISTING SNIPPET =====")
print(listing[max(0, i - 600): i + 900])

j = detail.find("<main")
print("\n===== DETAIL PAGE =====")
print(detail[j if j > 0 else 0: (j if j > 0 else 0) + 2500])