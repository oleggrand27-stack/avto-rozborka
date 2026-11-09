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
REQUEST_PAUSE = 2  # секунди між запитами, щоб не перевищити ліміт API


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


def search_all(pairs, extra):
    """Один запит на всі моделі: нові оголошення першими (order_by=7)."""
    params = [("category_id", 1), ("countpage", 100), ("order_by", 7)]
    for i, (marka_id, model_id, year_from, _label) in enumerate(pairs):
        params += [(f"marka_id[{i}]", marka_id), (f"model_id[{i}]", model_id)]
        if year_from:
            params.append((f"s_yers[{i}]", year_from))
    params += list(extra.items())
    data = ria("/search", params)
    sr = data.get("result", {}).get("search_result", {})
    print(f"Всього знайдено на AUTO.RIA: {sr.get('count')}")
    return [str(i) for i in sr.get("ids", [])]


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
    me = tg("getMe").get("result", {})
    updates = tg("getUpdates").get("result", [])
    print(f"Telegram бот: @{me.get('username')}, оновлень: {len(updates)}")
    for upd in reversed(updates):
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
    ids = search_all(pairs, extra)
    new = [i for i in ids if i not in seen]
    seen.update(new)
    print(f"Нових: {len(new)}")
    sent = 0
    if not first_run:
        for ad_id in reversed(new):  # від старіших до новіших
            link = f"https://auto.ria.com/uk/auto___{ad_id}.html"
            tg("sendMessage", chat_id=chat_id, text=f"🚗 Нове авто з пошкодженнями на AUTO.RIA\n{link}")
            sent += 1

    state["seen"] = sorted(seen)
    save_state(state)
    if first_run:
        tg("sendMessage", chat_id=chat_id,
           text=f"✅ Бот запущено. Запам'ятав {len(seen)} наявних оголошень, далі надсилатиму лише нові авто з пошкодженнями (після ДТП, не на ходу).")
    print(f"Моделей у пошуку: {len(pairs)}, надіслано: {sent}, всього бачених: {len(seen)}")


if __name__ == "__main__":
    main()
