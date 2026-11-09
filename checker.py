"""Перевіряє нові оголошення на AUTO.RIA і надсилає авто під розбірку в Telegram.

Потрібні змінні середовища (у GitHub: Settings -> Secrets and variables -> Actions):
  RIA_API_KEY         ключ з developers.ria.com
  TELEGRAM_BOT_TOKEN  токен від @BotFather
  TELEGRAM_CHAT_ID    (необов'язково) якщо не вказано, береться з чату, де натиснули Start
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(ROOT, "config.json")
STATE_PATH = os.path.join(ROOT, "state.json")

RIA = "https://developers.ria.com/auto"
TG = "https://api.telegram.org/bot{token}/{method}"

RIA_KEY = os.environ.get("RIA_API_KEY", "")
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
REQUEST_PAUSE = 0.4  # секунди між запитами, щоб не перевищити ліміт API


def http_json(url, params=None, data=None):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params, doseq=True)
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={"User-Agent": "avto-rozborka/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ria(path, params=None):
    time.sleep(REQUEST_PAUSE)
    p = [("api_key", RIA_KEY)] + list((params or {}).items() if isinstance(params, dict) else params or [])
    return http_json(RIA + path, p)


def norm(s):
    return " ".join(str(s).lower().replace("-", " ").split())


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1, sort_keys=True)


def resolve_ids(config, state):
    """Перетворює назви марок і моделей на id AUTO.RIA (кешує у state)."""
    cache = state.setdefault("ids", {})
    marks = None
    pairs = []  # (marka_id, model_id, year_from, label)
    for s in config["searches"]:
        mk = s["make"]
        if mk not in cache:
            if marks is None:
                marks = {norm(m["name"]): m["value"] for m in ria("/categories/1/marks")}
            if norm(mk) not in marks:
                print(f"! Марку не знайдено на AUTO.RIA: {mk}")
                continue
            mid = marks[norm(mk)]
            models = {norm(m["name"]): m["value"] for m in ria(f"/categories/1/marks/{mid}/models")}
            cache[mk] = {"id": mid, "models": models}
        entry = cache[mk]
        for model in s["models"]:
            model_id = entry["models"].get(norm(model))
            if model_id is None:
                print(f"! Модель не знайдено на AUTO.RIA: {mk} {model}")
                continue
            pairs.append((entry["id"], model_id, s.get("year_from"), f"{mk} {model}"))
    return pairs


def search_ids(marka_id, model_id, year_from, extra):
    params = [("category_id", 1), ("marka_id[0]", marka_id), ("model_id[0]", model_id),
              ("countpage", 100)]
    if year_from:
        params.append(("s_yers[0]", year_from))
    params += list(extra.items())
    data = ria("/search", params)
    return [str(i) for i in data.get("result", {}).get("search_result", {}).get("ids", [])]


def looks_for_parts(info, keywords):
    text = norm(" ".join(str(info.get(k, "")) for k in ("title",)) + " " +
                " ".join(str(info.get("autoData", {}).get(k, "")) for k in ("description", "title")))
    hits = [k for k in keywords if norm(k) in text]
    return hits


def tg(method, **data):
    return http_json(TG.format(token=TG_TOKEN, method=method), data=data)


def get_chat_id(state):
    cid = os.environ.get("TELEGRAM_CHAT_ID") or state.get("chat_id")
    if cid:
        return cid
    for upd in reversed(tg("getUpdates").get("result", [])):
        chat = (upd.get("message") or {}).get("chat") or {}
        if chat.get("type") == "private":
            state["chat_id"] = chat["id"]
            return chat["id"]
    return None


def notify(chat_id, info, label, hits):
    ad = info.get("autoData", {})
    link = info.get("linkToView", "")
    if link and not link.startswith("http"):
        link = "https://auto.ria.com/uk" + link
    lines = [
        f"🚗 {info.get('title') or label} {ad.get('year', '')}",
        f"💵 {info.get('USD', '?')} $",
        f"📍 {info.get('locationCityName') or info.get('stateData', {}).get('name', '')}",
        f"🛣 {ad.get('race', '')}",
        f"🔎 {', '.join(hits)}" if hits else "",
        link,
    ]
    text = "\n".join(l for l in lines if l.strip())
    photo = (info.get("photoData") or {}).get("seoLinkF") or (info.get("photoData") or {}).get("seoLinkM")
    try:
        if photo:
            tg("sendPhoto", chat_id=chat_id, photo=photo, caption=text[:1000])
            return
    except urllib.error.HTTPError:
        pass
    tg("sendMessage", chat_id=chat_id, text=text)


def main():
    if not RIA_KEY or not TG_TOKEN:
        sys.exit("Не задано RIA_API_KEY або TELEGRAM_BOT_TOKEN")
    config = load_json(CONFIG_PATH, {})
    state = load_json(STATE_PATH, {})
    keywords = config.get("keywords", [])
    extra = config.get("search_params", {})
    seen = set(state.get("seen", []))
    first_run = not seen

    chat_id = get_chat_id(state)
    if not chat_id:
        save_state(state)
        sys.exit("Бот ще не знає ваш чат: відкрийте бота в Telegram і натисніть Start.")

    pairs = resolve_ids(config, state)
    sent = 0
    for marka_id, model_id, year_from, label in pairs:
        try:
            ids = search_ids(marka_id, model_id, year_from, extra)
        except Exception as e:  # одна модель не повинна зупиняти решту
            print(f"! Помилка пошуку {label}: {e}")
            continue
        new = [i for i in ids if i not in seen]
        seen.update(new)
        print(f"{label}: знайдено {len(ids)}, нових {len(new)}")
        if first_run:
            if ids and not state.get("debug_done"):
                info = ria("/info", {"auto_id": ids[0]})
                print("DEBUG info keys:", sorted(info.keys()))
                print("DEBUG autoData keys:", sorted((info.get("autoData") or {}).keys()))
                print("DEBUG sample:", json.dumps({k: info.get(k) for k in ("title", "USD", "linkToView", "locationCityName")}, ensure_ascii=False))
                state["debug_done"] = True
            continue  # перший запуск лише запам'ятовує наявні оголошення
        for ad_id in new:
            try:
                info = ria("/info", {"auto_id": ad_id})
            except Exception as e:
                print(f"! Помилка оголошення {ad_id}: {e}")
                continue
            hits = looks_for_parts(info, keywords)
            if hits or extra:
                notify(chat_id, info, label, hits)
                sent += 1

    state["seen"] = sorted(seen)
    save_state(state)
    if first_run:
        tg("sendMessage", chat_id=chat_id,
           text=f"✅ Бот запущено. Запам'ятав {len(seen)} наявних оголошень, далі надсилатиму лише нові авто під розбірку.")
    print(f"Перевірено моделей: {len(pairs)}, надіслано: {sent}, всього бачених: {len(seen)}")


if __name__ == "__main__":
    main()
