"""Тимчасова діагностика параметрів пошуку AUTO.RIA."""
import json, os, time, urllib.parse, urllib.request
K = os.environ["RIA_API_KEY"]
def get(path, params):
    time.sleep(3)
    url = "https://developers.ria.com/auto" + path + "?" + urllib.parse.urlencode([("api_key", K)] + params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode()), dict(r.headers)
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()[:300]}, dict(e.headers)
variants = {
 "A plain": [("category_id",1),("marka_id",29),("model_id",293),("s_yers",2015)],
 "B indexed": [("category_id",1),("marka_id[0]",29),("model_id[0]",293),("s_yers[0]",2015)],
 "C both": [("category_id",1),("marka_id[0]",29),("model_id[0]",293),("s_yers[0]",2015),("po_yers[0]",2026)],
}
first = None
for name, p in variants.items():
    d, h = get("/search", p)
    sr = d.get("result", {}).get("search_result", {}) if "result" in d else d
    ids = sr.get("ids", [])
    print(name, "count=", sr.get("count"), "ids=", ids[:3], "limits:", {k: v for k, v in h.items() if "limit" in k.lower() or "retry" in k.lower()})
    if ids and first is None and name.startswith("A"):
        first = ids[0]
for name in ("A plain",):
    pass
if first:
    d, _ = get("/info", [("auto_id", first)])
    print("first title:", d.get("title"), d.get("autoData", {}).get("year"))
    print("technicalCondition:", json.dumps(d.get("technicalCondition"), ensure_ascii=False)[:500])
# пошук з фільтром стану: різні варіанти назв параметра
for pname in ("technical_condition_id", "technicalCondition", "damage", "spareParts"):
    for val in ("1","3","4"):
        d, _ = get("/search", [("category_id",1),("marka_id",29),("model_id",293),(pname,val)])
        sr = d.get("result", {}).get("search_result", {}) if "result" in d else d
        print("filter", pname, val, "count=", sr.get("count"), d.get("error",""))
