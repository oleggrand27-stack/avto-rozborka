"""Таксі-бот: нові оголошення AUTO.RIA за погодженим списком моделей -> Telegram.

Джерело даних:
  1) сторінка пошуку auto.ria.com (без ключа, без лімітів);
  2) якщо сайт недоступний — офіційний API developers.ria.com (ключ RIA_API_KEY).

Змінні середовища (GitHub Secrets):
  TELEGRAM_BOT_TOKEN  — той самий бот, що й для розбірки
  TAXI_CHAT_ID        — (необов'язково) окремий чат для таксі; інакше TELEGRAM_CHAT_ID
                        або chat_id з ../state.json
  RIA_API_KEY         — (необов'язково) запасний канал

  python taxi/taxi_bot.py          — звичайний запуск (GitHub Actions)
  python taxi/taxi_bot.py --test   — перевірка без Telegram і без запису стану
"""
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONFIG_PATH = os.path.join(HERE, "config.json")
STATE_PATH = os.path.join(HERE, "state.json")
SITE = "https://auto.ria.com"
RIA_API = "https://developers.ria.com/auto"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
FUELS = ("Газ/Бензин", "Бензин", "Дизель", "Електро", "Гібрид", "Газ")
TEST = "--test" in sys.argv


# ---------- службове ----------
def http(url, data=None, headers=None, timeout=40):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    h = {"User-Agent": UA, "Accept-Language": "uk-UA,uk;q=0.9"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_state(state):
    if TEST:
        return
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=0, sort_keys=True)


# ---------- сайт auto.ria.com ----------
CARD_TITLE = re.compile(r'"title":\{"content":"([^"]+?) (\d{4})"\},"subtitle":"([^"]*)"')
CARD_PRICE = re.compile(r'"price":\{"UAH":\d+,"USD":(\d+)\},"basicInfo":(\[.*?\])\s*,"', re.S)
CONTENT = re.compile(r'"content":"([^"]+)"')


def search_url(m, page):
    q = ["indexName=auto", "categories.main.id=1", f"brand.id[0]={m['brand_id']}"]
    q += [f"model.id[{i}]={mid}" for i, mid in enumerate(m["model_ids"])]
    q.append(f"year[0].gte={m['year_from']}")
    if m.get("year_to"):
        q.append(f"year[0].lte={m['year_to']}")
    q += [f"price.USD.lte={m['price_max']}", "sort[0].order=dates.created.desc", "size=100", f"page={page}"]
    return f"{SITE}/uk/search/?" + "&".join(q)


def parse_cards(page_html):
    out = {}
    parts = re.split(r'"id":"Auto(?=\d+")', page_html)
    for p in parts[1:]:
        ad_id = p[: p.index('"')]
        if ad_id in out:
            continue
        t, pr = CARD_TITLE.search(p), CARD_PRICE.search(p)
        if not t or not pr:
            continue
        lab = re.search(r'"labels":\[(.*?)\],"publishTime"', p, re.S)
        link = re.search(r'"link":"(https://auto\.ria\.com/uk/auto_[^"]*_' + ad_id + r'\.html)"', page_html)
        out[ad_id] = {
            "id": ad_id, "title": t.group(1), "year": int(t.group(2)),
            "sub": re.sub(r"\s+", " ", t.group(3)).strip(), "usd": int(pr.group(1)),
            "info": CONTENT.findall(pr.group(2)),
            "crash": "Був в ДТП" in (CONTENT.findall(lab.group(1)) if lab else []),
            "link": link.group(1) if link else f"{SITE}/uk/auto___{ad_id}.html",
        }
    return list(out.values())


def details_site(ad):
    info = ad["info"]
    fuel_s = next((s for s in info if s.startswith(FUELS)), "")
    vol = re.search(r"([\d.]+) л", fuel_s)
    kwh = re.search(r"([\d.,]+) кВт", fuel_s)
    km = next((s for s in info if "тис" in s and "км" in s), "")
    gear = next((s for s in info if re.search(r"Автомат|Ручна|Механ|Варіатор|Робот|Типтронік", s)), "")
    rng = next((s for s in info if re.fullmatch(r"\d+ км", s)), "")
    city = ""
    for s in info[1:]:
        if s not in (fuel_s, km, gear, rng) and not re.search(r"\d", s):
            city = s
    return {"fuel": fuel_s.split(",")[0].strip(), "vol": vol.group(1) if vol else "",
            "kwh": kwh.group(1) if kwh else "", "km": km, "gear": gear.split(" /")[0],
            "range": rng, "city": city}


def fetch_site(m, cfg):
    ads = []
    for page in range(cfg.get("pages_per_model", 1)):
        cards = parse_cards(http(search_url(m, page)))
        for ad in cards:
            ad["d"] = details_site(ad)
        ads += cards
        time.sleep(cfg.get("pause_between_requests_sec", 2))
        if len(cards) < 50:
            break
    return ads


# ---------- запасний канал: офіційний API ----------
def ria(path, params):
    time.sleep(2)
    q = urllib.parse.urlencode([("api_key", os.environ.get("RIA_API_KEY", ""))] + params)
    return json.loads(http(f"{RIA_API}{path}?{q}"))


def fetch_api(m, seen, budget):
    """Пошук id через API; деталі (/info) тягнемо лише для нових id, не більше budget[0] за запуск."""
    params = [("category_id", 1), ("marka_id[0]", m["brand_id"]), ("s_yers[0]", m["year_from"]),
              ("price_do", m["price_max"]), ("currency", 1), ("order_by", 7), ("countpage", 50)]
    params += [(f"model_id[{i}]", mid) for i, mid in enumerate(m["model_ids"])]
    if m.get("year_to"):
        params.append(("po_yers[0]", m["year_to"]))
    ids = [str(i) for i in ria("/search", params).get("result", {}).get("search_result", {}).get("ids", [])]
    ads = []
    for ad_id in ids:
        if ad_id in seen or budget[0] <= 0:
            continue
        budget[0] -= 1
        info = ria("/info", [("auto_id", ad_id)])
        a = info.get("autoData", {}) or {}
        blob = json.dumps(a, ensure_ascii=False)
        fuel = re.sub(r"\s*/\s*", "/", str(a.get("fuelName", ""))).split(",")[0].strip()
        vol = re.search(r"(\d[.,]\d+)\s*л", blob)
        link = info.get("linkToView", "")
        ads.append({
            "id": ad_id, "title": f"{info.get('markName', '')} {info.get('modelName', '')}".strip(),
            "year": int(a.get("year") or 0), "sub": str(info.get("title", "")), "usd": int(info.get("USD") or 0),
            "crash": False, "link": (SITE + "/uk" + link) if link and not link.startswith("http") else link,
            "d": {"fuel": fuel, "vol": vol.group(1) if vol else "", "kwh": "", "km": str(a.get("race", "")),
                  "gear": str(a.get("gearboxName", "")), "range": "",
                  "city": str(info.get("locationCityName", ""))},
        })
    return ads, ids


# ---------- фільтр і повідомлення ----------
def matches(ad, m, only_cities, min_price=0):
    d = ad["d"]
    if ad["usd"] < min_price or ad["usd"] > m["price_max"] or ad["year"] < m["year_from"]:
        return False
    if m.get("year_to") and ad["year"] > m["year_to"]:
        return False
    if d["fuel"].startswith("Дизель") or "Дизель" in ad["sub"]:
        return False
    if d["fuel"] and not any(d["fuel"].startswith(f) for f in m["fuels"]):
        return False
    if m.get("engine"):
        text = d["vol"] or ad["sub"]
        if text and not re.search(m["engine"], text):
            return False
    if only_cities and not any(c.lower() in d["city"].lower() for c in only_cities):
        return False
    return True


def fmt(ad, m, old_price=None):
    d, e = ad["d"], html.escape
    head = "🚕 <b>ТАКСІ · ОРЕНДА</b> — 💸 знизили ціну\n" if old_price else "🚕 <b>ТАКСІ · ОРЕНДА</b>\n"
    price = f"<b>${ad['usd']:,}</b>".replace(",", " ")
    if old_price:
        price += f" (було ${old_price:,})".replace(",", " ")
    spec = " · ".join(x for x in [
        f"{d['vol']} л" if d["vol"] else "", d["fuel"],
        f"батарея {d['kwh']} кВт·год" if d.get("kwh") else "", d["gear"], d["km"],
        f"запас {d['range']}" if d["range"] else ""] if x)
    lines = [f"{head}<b>{e(ad['title'])} {ad['year']}</b> — {price}", e(ad["sub"]), e(spec)]
    if d["city"]:
        lines.append(f"📍 {e(d['city'])}" + (" ⭐" if "львів" in d["city"].lower() else ""))
    if ad.get("crash"):
        lines.append("⚠️ Був в ДТП")
    lines += [f"ℹ️ {e(m['name'])}: {e(m.get('note', ''))}", ad["link"]]
    return "\n".join(l for l in lines if l.strip())


def tg(method, **data):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        return json.loads(http(url, data=data))
    except urllib.error.HTTPError as ex:
        if ex.code == 429:
            time.sleep(int(json.loads(ex.read()).get("parameters", {}).get("retry_after", 5)) + 1)
            return json.loads(http(url, data=data))
        raise


def chat_ids():
    raw = os.environ.get("TAXI_CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID") or \
        str(load_json(os.path.join(ROOT, "state.json"), {}).get("chat_id", ""))
    return [c.strip() for c in raw.split(",") if c.strip()]


def send(text):
    for cid in chat_ids():
        tg("sendMessage", chat_id=cid, text=text, parse_mode="HTML")
        time.sleep(0.7)


# ---------- основне ----------
def main():
    cfg = load_json(CONFIG_PATH, {})
    state = load_json(STATE_PATH, {})
    seen = state.setdefault("seen", {})  # id -> остання ціна ($), 0 = не підходить
    first_run = not seen
    if not TEST and (not os.environ.get("TELEGRAM_BOT_TOKEN") or not chat_ids()):
        sys.exit("Немає TELEGRAM_BOT_TOKEN або chat id")

    only = cfg.get("only_cities") or []
    limit = cfg.get("max_messages_per_run", 30)
    budget = [40]  # запитів /info до API за запуск (лише якщо сайт недоступний)
    queue, used_api, errors = [], False, []

    for m in cfg["models"]:
        try:
            ads = fetch_site(m, cfg)
            src = "сайт"
        except Exception as ex:
            errors.append(f"{m['name']}: сайт — {ex}")
            if not os.environ.get("RIA_API_KEY"):
                continue
            try:
                ads, ids = fetch_api(m, seen, budget)
                used_api, src = True, "API"
                if first_run:  # тихо запам'ятати всі наявні id
                    for i in ids:
                        seen.setdefault(i, 0)
            except Exception as ex2:
                errors.append(f"{m['name']}: API — {ex2}")
                continue
        good = [a for a in ads if matches(a, m, only, cfg.get("min_price", 0))]
        print(f"{m['name']}: {src}, карток {len(ads)}, підходить {len(good)}")
        if TEST:
            for a in sorted(good, key=lambda x: x["usd"])[:3]:
                print("   ", a["year"], a["usd"], a["d"], a["link"])
            continue
        good_ids = {a["id"] for a in good}
        for a in ads:
            if a["id"] not in good_ids:
                seen.setdefault(a["id"], 0)
        for a in good:
            old = seen.get(a["id"])
            if old is None:
                if not first_run:
                    queue.append((a, m, None))
            elif old and cfg.get("notify_price_drops", True) and a["usd"] < old:
                queue.append((a, m, old))
            seen[a["id"]] = a["usd"]

    if errors:
        print("Помилки:\n  " + "\n  ".join(errors))
    if TEST:
        return
    if len(errors) == len(cfg["models"]):
        save_state(state)
        sys.exit("Жодна модель не перевірилась (сайт і API недоступні)")

    for a, m, old in queue[:limit]:
        send(fmt(a, m, old))
    for a, m, old in queue[limit:]:  # решту надішлемо наступного запуску
        if old is None:
            seen.pop(a["id"], None)
        else:
            seen[a["id"]] = old
    if first_run:
        send(f"🚕 Таксі-бот запущено. Відстежую {len(cfg['models'])} моделей (клас Комфорт, Львів). "
             f"Запам'ятав {len(seen)} наявних оголошень — далі надсилатиму лише нові та зі зниженою ціною.")
    state["last_source"] = "API" if used_api else "сайт"
    save_state(state)
    print(f"Надіслано: {min(len(queue), limit)}, у базі: {len(seen)}")


if __name__ == "__main__":
    main()
