import json,re,sys,time,urllib.request
sys.path.insert(0,"taxi"); sys.argv.append("--test")
import taxi_bot as tb
cfg=tb.load_json(tb.CONFIG_PATH,{}); st=tb.load_json(tb.STATE_PATH,{}); seen=st.get("seen",{})
m=[x for x in cfg["models"] if "Megane" in x["name"]][0]
ads=tb.fetch_site(m,cfg)
print("cards",len(ads))
for a in ads:
    if 2011<=a["year"]<=2013 and 3500<=a["usd"]<=5500:
        print("AD",a["id"],a["year"],a["usd"],a["sub"],a["d"],"match=",tb.matches(a,m,[]),"seen=",a["id"] in seen,a["link"])
for a in ads[:5]: print("NEWEST",a["id"],a["year"],a["usd"],a["title"],a["sub"])
time.sleep(3)
h=tb.http("https://auto.ria.com/api/categories/1/marks")
vw=[x for x in json.loads(h) if x["name"] in("Volkswagen","VW")]; print("VW",vw)
time.sleep(3)
ms=json.loads(tb.http(f"https://auto.ria.com/api/categories/1/marks/{vw[0]['value']}/models"))
print("POLO",[x for x in ms if "polo" in x["name"].lower()])
