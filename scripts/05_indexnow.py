"""Invia a IndexNow (Bing e altri) gli URL della sitemap pubblicata. Uso: python3 scripts/05_indexnow.py [sitemap_url]"""
import json, os, re, sys, urllib.request
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SITO = "https://opendata.giuseppebosi.com"
chiave = open(os.path.join(R, "assets", "indexnow-key.txt")).read().strip()
xml = urllib.request.urlopen(sys.argv[1] if len(sys.argv) > 1 else SITO + "/sitemap.xml", timeout=60).read().decode()
urls = re.findall(r"<loc>(.*?)</loc>", xml)
corpo = json.dumps({"host": "opendata.giuseppebosi.com", "key": chiave, "keyLocation": f"{SITO}/{chiave}.txt", "urlList": urls}).encode()
req = urllib.request.Request("https://api.indexnow.org/indexnow", data=corpo, headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "progetti-pubblici-sotto-casa/1.0 (info@giuseppebosi.com)"})
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        print("IndexNow:", len(urls), "URL inviati, risposta HTTP", r.status, r.reason)
except urllib.error.HTTPError as e:
    print("IndexNow: HTTP", e.code, e.reason, e.read().decode()[:300]); sys.exit(1)
