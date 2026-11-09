"""Тимчасова діагностика параметрів пошуку AUTO.RIA (≈10 запитів)."""
import json, os, time, urllib.parse, urllib.request
K = os.environ["RIA_API_KEY"]
BASE = "https://developers.ria.com/auto"
def get(path, query):
    time.sleep(3)
    url = f"{BASE}{path}?api_key={K}&{query}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()[:200]}
def search(label, q):
    d = get("/search", q)
    sr = d.get("result", {}).get("search_result", {})
    print(f"{label}: count={sr.get('count')} ids={sr.get('ids', [])[:3]} {d.get('error','')}")
    return sr.get("ids", [])
def title(i):
    d = get("/info", f"auto_id={i}")
    print("   ->", d.get("markName"), d.get("modelName"), d.get("autoData", {}).get("year"), "| technicalCondition:", json.dumps(d.get("technicalCondition"), ensure_ascii=False)[:300])
enc = "category_id=1&marka_id%5B0%5D=29&model_id%5B0%5D=293"
lit = "category_id=1&marka_id[0]=29&model_id[0]=293"
plain = "category_id=1&marka_id=29&model_id=293"
search("encoded", enc)
ids = search("literal", lit)
search("plain", plain)
if ids: title(ids[0])
for extra in ("damage=1", "onRepairParts=1", "technical_condition_id=4", "spareParts=1"):
    i = search(f"literal+{extra}", f"{lit}&{extra}")
    if extra == "damage=1" and i: title(i[0])
search("two models", "category_id=1&marka_id[0]=29&model_id[0]=293&marka_id[1]=33&model_id[1]=326")
