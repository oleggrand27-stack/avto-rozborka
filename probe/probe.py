import re,urllib.request,time
from collections import Counter
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
def get(u):
    time.sleep(4)
    return urllib.request.urlopen(urllib.request.Request("https://auto.ria.com"+u,headers={"User-Agent":UA,"Accept-Language":"uk"}),timeout=40).read().decode("utf-8","replace")
base="/uk/search/?indexName=auto&categories.main.id=1&brand.id[0]=36&model.id[0]=36565&size=100"
for e in ["","&abroad=1","&abroad=0","&abroad.not=1","&customs_cleared=1","&customsCleared=1","&custom.not=1","&search_type=3","&search_type[0]=3","&country.import.usa.not=0"]:
    try:
        h=get(base+e)
    except Exception as ex:
        print("ERR",e,ex); continue
    m=re.search(r'"count":(\d+)',h)
    low=h
    kws={k:low.count(k) for k in ["пригон","Пригон","замовлення","розмитн","Розмитн","США","abroad","Abroad","inUkraine","Не в Україні","customs"]}
    print("COUNT",e,m.group(1) if m else "?",kws)
    if e=="":
        for k in ["пригон","Пригон","замовлення","Розмитн","розмитн","abroad"]:
            for mm in list(re.finditer(k,h))[:3]:
                print(k,"::",h[max(0,mm.start()-250):mm.start()+200].replace("\n"," "))
