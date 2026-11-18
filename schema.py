import json
import urllib.request

url = "https://analyst-assessment-production.up.railway.app/api/openapi.json"
spec = json.load(urllib.request.urlopen(url))

for path, methods in spec["paths"].items():
    if path.startswith("/api/v1/accounts"):
        for method, info in methods.items():
            print("=====", method.upper(), path)
            print("summary:", info.get("summary"))
            print("description:", info.get("description"))
            print("parameters:", json.dumps(info.get("parameters"), indent=1))
            print("requestBody:", json.dumps(info.get("requestBody"), indent=1))
            print()