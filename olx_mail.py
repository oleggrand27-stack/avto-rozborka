"""Пересилає в Telegram нові оголошення OLX з листів-сповіщень у Gmail.

OLX надсилає листи про нові оголошення за збереженими пошуками. Скрипт лише читає
листи від OLX (нічого не видаляє і не позначає прочитаним), бере з них посилання на
оголошення і надсилає в Telegram ті, що схожі на авто під розбірку.

Секрети: GMAIL_ADDRESS, GMAIL_APP_PASSWORD, TELEGRAM_BOT_TOKEN.
"""
import email
import email.header
import html
import imaplib
import json
import os
import re
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone

import checker  # tg(), get_chat_id(), norm(), load_json()

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(ROOT, "olx_state.json")
LOOKBACK_DAYS = 3


def decode(s):
    parts = email.header.decode_header(s or "")
    return "".join(p.decode(c or "utf-8", "replace") if isinstance(p, bytes) else p for p, c in parts)


def html_part(msg):
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            return html.escape(part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace"))
    return ""


AD_RE = re.compile(r"https?://(?:www\.|m\.)?olx\.ua/[^\s\"'<>]*?(?:/d/|/obyavlenie/)[^\s\"'<>]*?-ID([A-Za-z0-9]+)\.html")


def unwrap(url):
    """Розгортає посилання-трекери: шукає справжню адресу olx.ua всередині параметрів."""
    url = html.unescape(url)
    for _ in range(3):
        if AD_RE.search(url):
            return url
        q = urllib.parse.urlparse(url).query
        inner = [v for vals in urllib.parse.parse_qs(q).values() for v in vals if "olx.ua" in v]
        if not inner:
            break
        url = inner[0]
    return url


def extract_ads(body):
    """Повертає {id: (title, url)} з HTML листа."""
    ads = {}
    for m in re.finditer(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", body, flags=re.S | re.I):
        url = unwrap(m.group(1))
        found = AD_RE.search(url)
        if not found:
            continue
        ad_id = found.group(1)
        text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", m.group(2))).split())
        clean_url = url.split("?")[0].split("#")[0]
        old_title = ads.get(ad_id, ("", ""))[0]
        ads[ad_id] = (text if len(text) > len(old_title) else old_title, clean_url)
    return ads


def main():
    user, password = os.environ.get("GMAIL_ADDRESS"), os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
    if not user or not password:
        print("GMAIL_ADDRESS / GMAIL_APP_PASSWORD не задано, OLX пропускаю.")
        return
    config = checker.load_json(checker.CONFIG_PATH, {})
    keywords = config.get("keywords", [])
    only_keywords = config.get("olx_only_keywords", True)
    state = checker.load_json(STATE_PATH, {})
    seen_msgs, seen_ads = set(state.get("messages", [])), set(state.get("ads", []))
    first_run = not seen_msgs

    chat_id = checker.get_chat_id(checker.load_json(checker.STATE_PATH, {}))
    if not chat_id:
        sys.exit("Бот ще не знає ваш чат.")

    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(user, password)
    imap.select("INBOX", readonly=True)
    since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime("%d-%b-%Y")
    _, data = imap.search(None, "SINCE", since, "FROM", "olx")
    nums = data[0].split()
    print(f"Листів від OLX за {LOOKBACK_DAYS} дні: {len(nums)}")

    sent = 0
    for num in nums:
        _, raw = imap.fetch(num, "(BODY.PEEK[])")
        msg = email.message_from_bytes(raw[0][1])
        mid = msg.get("Message-ID") or f"{msg.get('Date')}|{msg.get('Subject')}"
        if mid in seen_msgs:
            continue
        seen_msgs.add(mid)
        subject = decode(msg.get("Subject"))
        ads = extract_ads(html_part(msg))
        print(f"Лист: {subject[:80]!r}, оголошень: {len(ads)}")
        for ad_id, (title, url) in ads.items():
            if ad_id in seen_ads:
                continue
            seen_ads.add(ad_id)
            if first_run:
                continue
            hits = [k for k in keywords if checker.norm(k) in checker.norm(title)]
            if only_keywords and not hits:
                continue
            text = f"🟢 OLX: {title or 'оголошення'}\n🔎 {', '.join(hits) or subject}\n{url}"
            checker.tg("sendMessage", chat_id=chat_id, text=text)
            sent += 1
    imap.logout()

    state["messages"] = sorted(seen_msgs)[-500:]
    state["ads"] = sorted(seen_ads)[-5000:]
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    if first_run:
        checker.tg("sendMessage", chat_id=chat_id,
                   text=f"✅ OLX підключено. Листів від OLX за {LOOKBACK_DAYS} дні: {len(nums)}. Далі надсилатиму нові оголошення під розбірку.")
    print(f"OLX: надіслано {sent}")


if __name__ == "__main__":
    main()
