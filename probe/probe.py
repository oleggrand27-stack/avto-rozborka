import json,re,urllib.request
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
def get(u):
    return urllib.request.urlopen(urllib.request.Request("https://auto.ria.com"+u,headers={"User-Agent":UA,"Accept-Language":"uk"}),timeout=40).read().decode("utf-8","replace")
for b in ("Renault","Dacia","Nissan","Hyundai","Kia","Chevrolet"):
    marks=json.loads(get("/api/categories/1/marks")); mid=[m for m in marks if m["name"]==b][0]["value"]
    ms=json.loads(get(f"/api/categories/1/marks/{mid}/models"))
    print(b,mid,[f'{m["name"]}:{m["value"]}' for m in ms if re.search(r"Logan|Sandero|Duster|Dokker|Lodgy|Zoe|Leaf|Accent|Elantra|Niro|Forte|Bolt|Kona|Megane|Scenic|Santa|Sorento|Sportage|Ioniq",m["name"])])
base="/uk/search/?indexName=auto&categories.main.id=1&brand.id[0]=62&price.USD.lte=3000&size=20"
h=get(base)
for kw in ["abroad","custom","damage","Під пригон","pidgon","country.import","spareParts","technicalCondition"]:
    for m in list(re.finditer(re.escape(kw),h))[:4]:
        print(kw,"::",h[max(0,m.start()-150):m.start()+200].replace("\n"," "))
def count(extra):
    h=get(base+extra); m=re.search(r'"count":(\d+)',h) or re.search(r'Знайдено\D{0,40}([\d ]+)',h)
    ids=len(set(re.findall(r'"id":"Auto(\d+)"',h)))
    return (m.group(1) if m else "?"), ids
for e in ["","&abroad.not=0","&abroad.not=1","&customs.not=1","&custom.not=1","&custom.not=-1","&damage.not=0","&damage.not=1","&spareParts=1"]:
    print("COUNT",e,count(e))
