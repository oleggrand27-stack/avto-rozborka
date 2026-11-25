import json,os,time,urllib.request,urllib.parse
K=os.environ["RIA_API_KEY"]
def s(extra):
    time.sleep(2)
    p=[("api_key",K),("category_id",1),("marka_id[0]",55),("model_id[0]",36565),("countpage",100)]+extra
    d=json.loads(urllib.request.urlopen("https://developers.ria.com/auto/search?"+urllib.parse.urlencode(p),timeout=30).read())
    sr=d["result"]["search_result"]; return sr["count"], sr["ids"][:100]
base=s([])
print("BASE",base[0])
for e in [[("abroad",0)],[("abroad",1)],[("abroad",2)],[("custom",0)],[("custom",1)],[("custom",2)],[("damage",2)],[("damage",2),("abroad",2),("custom",1)]]:
    c,ids=s(e); print("COUNT",e,c)
c,ids=s([("abroad",1)])
for i in ids[:3]:
    time.sleep(2)
    d=json.loads(urllib.request.urlopen(f"https://developers.ria.com/auto/info?api_key={K}&auto_id={i}",timeout=30).read())
    print("INFO abroad=1", i, d.get("locationCityName"), d.get("stateData",{}).get("name"), d.get("autoData",{}).get("custom"), str(d)[:300])
