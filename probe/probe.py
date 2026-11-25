import json,re,urllib.request,time
from collections import Counter
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
def get(u):
    time.sleep(4)
    return urllib.request.urlopen(urllib.request.Request("https://auto.ria.com"+u,headers={"User-Agent":UA,"Accept-Language":"uk"}),timeout=40).read().decode("utf-8","replace")
base="/uk/search/?indexName=auto&categories.main.id=1&brand.id[0]=62&price.USD.lte=3000&size=100"
def info(extra):
    h=get(base+extra); m=re.search(r'"count":(\d+)',h)
    labs=Counter()
    for l in re.findall(r'"labels":\[(.*?)\],"publishTime"',h,re.S): labs.update(set(re.findall(r'"content":"([^"]+)"',l)))
    lt=Counter()
    for l in re.findall(r'"leftTopBadges":\[(.*?)\]',h,re.S): lt.update(re.findall(r'"content":"([^"]+)"',l))
    return (m.group(1) if m else "?"), dict(labs.most_common(12)), dict(lt.most_common(6)), h
for e in ["","&search_type=2","&search_type=3","&search_type=1","&damage.not=0","&damage.not=1"]:
    c,l,lt,h=info(e); print("COUNT",e,c,l,lt)
# technical condition options
m=re.search(r'"technical_condition".{0,6000}',h,re.S)
txt=h
for kw in ['"crashed"','technical_condition","value','"name":"Не на ходу"','Після ДТП','Пошкоджен']:
    for mm in list(re.finditer(re.escape(kw),txt))[:2]:
        print(kw,"::",txt[max(0,mm.start()-300):mm.start()+300].replace("\n"," "))
