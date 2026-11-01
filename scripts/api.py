"""Accesso alla API OpenCoesione con cache su disco e pausa tra le chiamate."""
import json, os, time, urllib.request, hashlib
BASE = "https://opencoesione.gov.it/it/api"
CACHE = os.path.join(os.path.dirname(__file__), "..", "dati", "cache")
PAUSA = 1.0
_ultimo = [0.0]

def get(url):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest() + ".json")
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    attesa = PAUSA - (time.time() - _ultimo[0])
    if attesa > 0:
        time.sleep(attesa)
    req = urllib.request.Request(url, headers={"User-Agent": "progetti-pubblici-sotto-casa/1.0 (info@giuseppebosi.com)"})
    for tentativo in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.load(r)
            break
        except Exception as e:
            time.sleep(15 * (tentativo + 1))
    else:
        raise RuntimeError("fallito: " + url)
    _ultimo[0] = time.time()
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    return d

def lista(territorio="arezzo-comune"):
    out, page = [], 1
    while True:
        d = get(f"{BASE}/progetti/?format=json&territorio={territorio}&page_size=500&page={page}")
        out += d["results"]
        if page >= d["last_page"]:
            return out, d
        page += 1
