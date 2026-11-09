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
lit = "category_id=1&marka_id[0]=29&model_id[0]=293"
for extra in ("technical_condition=3", "technical_condition[0]=3", "technical_condition[0]=4",
              "technicalCondition[0]=3", "technical_condition_id[0]=3", "crashed=1", "damage=0"):
    i = search(f"literal+{extra}", f"{lit}&{extra}")
