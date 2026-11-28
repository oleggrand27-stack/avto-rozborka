import json,sys,time,statistics
sys.path.insert(0,"taxi"); sys.argv.append("--test")
import taxi_bot as tb
ms=json.loads(tb.http("https://auto.ria.com/api/categories/1/marks/70/models"))
rap=[x["value"] for x in ms if "rapid" in x["name"].lower()]; print("RAPID",[x for x in ms if "rapid" in x["name"].lower()])
cfg={"pages_per_model":5,"pause_between_requests_sec":4}
for name,ids,yf in [("Rapid",rap,2013),("Octavia",[652],2010)]:
    time.sleep(4)
    ads=tb.fetch_site({"brand_id":70,"model_ids":ids,"year_from":yf,"price_max":9000},cfg)
    print(name,"cards",len(ads))
    by={}
    for a in ads:
        f=a["d"]["fuel"]
        if f.startswith("Дизель"): continue
        by.setdefault((a["year"],f,a["d"]["vol"]),[]).append(a["usd"])
    rows={}
    for (y,f,v),p in by.items():
        rows.setdefault(y,[]).extend(p)
    for y in sorted(rows): 
        p=sorted(rows[y]); print(" ",name,y,"n=",len(p),"min",p[0],"med",int(statistics.median(p)))
    vols={}
    for (y,f,v),p in by.items(): vols[(f,v)]=vols.get((f,v),0)+len(p)
    print(" ",name,"fuel/vol",sorted(vols.items(),key=lambda x:-x[1])[:10])
