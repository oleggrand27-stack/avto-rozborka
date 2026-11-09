"""Тимчасово: показує структуру посилань у листі OLX про збережений пошук (без значень параметрів)."""
import email, imaplib, os, re, html, urllib.parse
import olx_mail as o
imap = imaplib.IMAP4_SSL("imap.gmail.com")
imap.login(os.environ["GMAIL_ADDRESS"], os.environ["GMAIL_APP_PASSWORD"].replace(" ", ""))
imap.select("INBOX", readonly=True)
_, d = imap.search(None, "FROM", "olx", "SINCE", "06-Nov-2026")
for num in reversed(d[0].split()):
    _, raw = imap.fetch(num, "(BODY.PEEK[])")
    m = email.message_from_bytes(raw[0][1])
    if "критеріям" not in o.decode(m.get("Subject")):
        continue
    body = o.html_part(m)
    print("html length", len(body))
    for a in re.finditer(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", body, flags=re.S | re.I)[:0] if False else list(re.finditer(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", body, flags=re.S | re.I))[:25]:
        u = urllib.parse.urlparse(html.unescape(a.group(1)))
        text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", a.group(2))).split())[:50]
        keys = list(urllib.parse.parse_qs(u.query).keys())
        print(u.netloc, u.path[:70], keys, "|", text)
    break
imap.logout()
