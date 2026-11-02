"""Costruisce il sito statico in site/ dai dati OpenCoesione (cache locale). Ripetibile."""
import csv, glob, html, json, os, re, sys, collections, datetime
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import api
SITE = os.environ.get("OC_SITE") or os.path.join(ROOT, "site")
SITO = "https://opendata.giuseppebosi.com"
DATA_DATI = None  # calcolata dai dati in carica()
SOGLIA = "20160101"

num = lambda s: float((s or "0").replace(".", "").replace(",", ".")) if isinstance(s, str) else float(s or 0)
esc = lambda s: html.escape(str(s if s is not None else ""), quote=True)

LANG = "it"
T = lambda it, en: en if LANG == "en" else it

def eur(x):
    if LANG == "en":
        return "€" + f"{round(x):,}"
    return f"{round(x):,}".replace(",", ".") + " €"

def data(s):
    if not (s and len(s) == 8):
        return T("dato non disponibile", "not available")
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if LANG == "en" else f"{s[6:8]}/{s[4:6]}/{s[:4]}"

# etichette nostre (non dati della fonte) tradotte in inglese; i valori ufficiali della fonte restano in italiano
TEMI_EN = {"Strade e trasporti": "Roads and transport", "Ambiente": "Environment", "Cultura e turismo": "Culture and tourism",
           "Aiuti alle imprese": "Support to businesses", "Lavoro": "Employment", "Istruzione e formazione": "Education and training",
           "Salute e inclusione sociale": "Health and social inclusion", "Servizi digitali": "Digital services", "Energia": "Energy",
           "Ricerca e innovazione": "Research and innovation", "Pubblica amministrazione": "Public administration"}
NATURA_EN = {"Lavori pubblici": "Public works", "Acquisto di beni": "Purchase of goods", "Servizi": "Services",
             "Incentivi alle imprese": "Incentives to businesses", "Contributi a enti e persone": "Grants to organisations and people"}
def lab(it, dic):
    """In inglese: etichetta inglese e, tra parentesi, l'italiano; se manca la traduzione resta l'italiano."""
    return f"{dic[it]} (<span lang=\"it\">{esc(it)}</span>)" if LANG == "en" and it in dic else esc(it)

VOC = set()
MAIUSC = {"arezzo", "toscana", "italia", "valdarno", "casentino", "buriano", "europa", "fse", "fesr", "fsc", "pon", "por", "pnrr", "snai",
          "cnr", "asl", "s.r.l.", "s.p.a.", "srl", "spa", "ar", "covid", "co.mi.te.l.", "ice"}

def _tok(w):
    if re.search(r"[0-9_]", w):
        return w.upper()
    b = re.sub(r"^\W+|\W+$", "", w).lower()
    if b in MAIUSC or b in VOC:
        return w[:1].upper() + w[1:] if b not in ("fse", "fesr", "fsc", "pon", "por", "cnr", "asl", "srl", "spa", "ar", "ice", "snai") else w.upper()
    return w

def frase(t):
    t = re.sub(r"\s+", " ", (t or "").strip())
    if not t:
        return "dato non disponibile"
    lett = [c for c in t if c.isalpha()]
    if lett and sum(c.isupper() for c in lett) / len(lett) > 0.6:
        t = t.lower()
        t = " ".join(_tok(w) for w in t.split(" "))
        t = re.sub(r"(^|[.:;/] ?)([a-zà-ù])", lambda m: m.group(1) + m.group(2).upper(), t)
    return t[0].upper() + t[1:]

def impara_vocabolario(testi):
    for t in testi:
        if not t or t.isupper():
            continue
        for w in t.split():
            b = re.sub(r"^\W+|\W+$", "", w)
            if len(b) > 3 and b[0].isupper() and b[1:].islower():
                VOC.add(b.lower())

TEMI_S = {
    "Trasporti e mobilità": "Strade e trasporti",
    "Ambiente": "Ambiente",
    "Ambiente e prevenzione dei rischi": "Ambiente",
    "Cultura e turismo": "Cultura e turismo",
    "Competitività delle imprese": "Aiuti alle imprese",
    "Competitività imprese": "Aiuti alle imprese",
    "Occupazione e lavoro": "Lavoro",
    "Istruzione e formazione": "Istruzione e formazione",
    "Inclusione sociale e salute": "Salute e inclusione sociale",
    "Reti e servizi digitali": "Servizi digitali",
    "Energia": "Energia",
    "Ricerca e innovazione": "Ricerca e innovazione",
    "Capacità amministrativa": "Pubblica amministrazione",
}
tema = lambda d: d["oc_tema_sintetico"] or "Altro"            # termine ufficiale (schede, dati completi)
tema_s = lambda d: TEMI_S.get(d["oc_tema_sintetico"], d["oc_tema_sintetico"] or "Altro")  # parole semplici (prima pagina, elenchi)
def pl(n, sing, plur):
    return f"{n} {sing if n == 1 else plur}"
OPERE = ("REALIZZAZIONE DI LAVORI", "ACQUISTO DI BENI")
is_opera = lambda d: (d["cup_descr_natura"] or "").startswith(OPERE)

NATURA_SEMPLICE = {
    "REALIZZAZIONE DI LAVORI PUBBLICI (OPERE ED IMPIANTISTICA)": "Lavori pubblici",
    "ACQUISTO DI BENI": "Acquisto di beni",
    "ACQUISTO O REALIZZAZIONE DI SERVIZI": "Servizi",
    "CONCESSIONE DI INCENTIVI AD UNITA' PRODUTTIVE": "Incentivi alle imprese",
    "CONCESSIONE DI CONTRIBUTI AD ALTRI SOGGETTI (DIVERSI DA UNITA' PRODUTTIVE)": "Contributi a enti e persone",
}
natura = lambda d: NATURA_SEMPLICE.get(d["cup_descr_natura"], frase(d["cup_descr_natura"]))

RX_PERSONA = re.compile(r"(A FAVORE DI|-)\s+[^()]+?\s*\(\*CODICE FISCALE\*\)", re.I)

def pulisci(t):
    """Omette il nome delle persone fisiche nei titoli degli interventi individuali."""
    return RX_PERSONA.sub(lambda m: m.group(1) + " [nome omesso] (codice fiscale omesso)", t or "")

def carica():
    ds = []
    for p in glob.glob(os.path.join(api.CACHE, "*.json")):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d, dict) and "fasi_procedurali" in d and "oc_stato_progetto" in d:
            ds.append(d)
    uniq = {}
    for d in ds:
        uniq[d["cod_locale_progetto"]] = d
    for d in uniq.values():
        d["oc_titolo_progetto"] = pulisci(d["oc_titolo_progetto"])
        d["oc_sintesi_progetto"] = pulisci(d.get("oc_sintesi_progetto"))
    return list(uniq.values())

def enti(d):
    r = [s["denominazione"] for s in d["soggetti"] if set(s["ruoli"]) & {"Beneficiario", "Attuatore", "Realizzatore"}]
    return r or [s["denominazione"] for s in d["soggetti"]]

def ente_str(d):
    e = enti(d)
    return "; ".join(frase(x) if x.isupper() else x for x in e) if e else T("dato non disponibile", "not available")

# ------------------------------------------------------------------ layout
CSS = """
:root{--bg:#fff;--tx:#1b2330;--mu:#566074;--ac:#0b5cab;--l:#d9e0ea;--sf:#f4f7fb;--ok:#2f7d4f}
*{box-sizing:border-box}body{margin:0;font:18px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--tx);background:var(--bg)}
main p,main li,main dd,main h1,main h2,main h3{overflow-wrap:anywhere}
a{color:var(--ac)}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #f2a900;outline-offset:2px}
.w{max-width:960px;margin:0 auto;padding:0 16px}
header.top{border-bottom:1px solid var(--l);background:var(--sf)}
html{scroll-padding-top:110px}header.top{position:sticky;top:0;z-index:50}header.top .w.nav{display:flex;flex-wrap:wrap;gap:2px 24px;align-items:center;padding:6px 16px}header.top .fonte{background:#0b3d6e;color:#fff;font-size:.88rem;padding:5px 0}header.top .fonte a{color:#fff}header.top .conc{font-size:.8rem;opacity:.9;padding-top:1px}header.top .fl{display:flex;justify-content:space-between;align-items:center;gap:12px}a.lingua{display:inline-flex;align-items:center;gap:6px;font-weight:600;text-decoration:none;border:1px solid #ffffff80;border-radius:6px;padding:1px 8px}
header.top b{font-size:1.05rem}nav{display:flex;flex:1 1 auto;flex-wrap:wrap;gap:4px 18px}nav a{text-decoration:none;padding:4px 0}nav a.tut{margin-left:auto;color:#000;font-weight:600}nav a.cod{color:#6D28D9;font-weight:700}nav a.cod::before{content:'</> ';font-family:ui-monospace,Menlo,Consolas,monospace;font-weight:700}nav a.cod.on{border-bottom-color:#6D28D9}nav a.on{border-bottom:3px solid var(--ac);font-weight:600}
h1{font-size:2rem;line-height:1.2;margin:1.2rem 0 .6rem}h2{font-size:1.4rem;margin:2.2rem 0 .6rem}h3{font-size:1.1rem;margin:1.4rem 0 .4rem}
.lead{font-size:1.2rem;color:var(--tx)}.mu{color:var(--mu)}.small{font-size:.9rem}
.data{display:inline-block;background:var(--sf);border:1px solid var(--l);border-radius:8px;padding:6px 12px;margin:.3rem 0}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin:1rem 0}
.card{border:1px solid var(--l);border-radius:10px;padding:14px 16px;background:#fff}.card .n{font-size:1.9rem;font-weight:700;line-height:1.2}
.card.fin{border-top:5px solid var(--ac)}.card.pag{border-top:5px solid var(--ok)}
.avv{border:1px solid #e7c76b;background:#fff8e1;border-radius:10px;padding:10px 14px;margin:1.4rem 0}
.riga{margin:.7rem 0}.bar{height:12px;background:var(--sf);border:1px solid var(--l);border-radius:6px;overflow:hidden}.bar i{display:block;height:100%;background:var(--ac)}.bar i.p{background:var(--ok)}
.lista{list-style:none;padding:0;margin:0}.lista li{border-bottom:1px solid var(--l);padding:12px 0}.lista a{font-weight:600}
table{border-collapse:collapse;width:100%;font-size:.92rem}th,td{border-bottom:1px solid var(--l);padding:6px 8px;text-align:left;vertical-align:top}th{background:var(--sf);position:sticky;top:0}
.sc{overflow-x:auto;max-height:70vh;border:1px solid var(--l);border-radius:8px}
dl.sch{display:grid;grid-template-columns:minmax(120px,200px) 1fr;gap:6px 16px}dl.sch dt{color:var(--mu)}dl.sch dd{margin:0}
.btn{display:inline-block;border:1px solid var(--ac);color:var(--ac);padding:8px 14px;border-radius:8px;text-decoration:none;margin:.3rem .4rem .3rem 0;background:#fff}
pre{background:var(--sf);border:1px solid var(--l);border-radius:8px;padding:12px;overflow-x:auto;font-size:.85rem;line-height:1.45}code{font-family:ui-monospace,Menlo,Consolas,monospace}
.tag{display:inline-block;border:1px solid var(--l);border-radius:6px;padding:0 8px;font-size:.85rem;background:var(--sf)}
.filtri{display:flex;flex-wrap:wrap;gap:10px;margin:.8rem 0}.filtri input,.filtri select{font:inherit;padding:8px;border:1px solid var(--l);border-radius:8px;max-width:100%}

.sch-o{display:block;width:100%;height:auto;margin:.6rem 0}.sch-v{display:none;width:100%;max-width:360px;height:auto;margin:.6rem auto}@media(max-width:700px){.sch-o{display:none}.sch-v{display:block}}.build{border:2px solid var(--ac);border-radius:12px;background:#fff;padding:14px 16px;margin:1.2rem 0}.build h2{margin:0 0 .4rem;font-size:1.25rem}.build p{margin:.3rem 0 .6rem}
.puoi{margin:.4rem 0 .8rem;padding-left:1.2rem}.puoi li{margin:.2rem 0}
.hero{background:var(--sf);border:1px solid var(--l);border-radius:14px;padding:18px 18px 14px;margin:1rem 0 1.4rem}
.hero h1{margin-top:0}.cerca{display:flex;flex-wrap:wrap;gap:8px;margin:.8rem 0}.cerca input{flex:1 1 240px;font:inherit;padding:12px;border:2px solid var(--ac);border-radius:10px}
.cerca button,.btn.pri{font:inherit;background:var(--ac);color:#fff;border:2px solid var(--ac);border-radius:10px;padding:12px 18px;cursor:pointer;font-weight:600}
.passi{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin:.6rem 0 0}
.passi a{display:block;border:1px solid var(--l);background:#fff;border-radius:10px;padding:10px 14px;text-decoration:none;color:var(--tx)}.passi a strong{display:block;color:var(--ac)}
.vuoto{border:1px dashed var(--mu);border-radius:10px;padding:14px;margin:.8rem 0;background:var(--sf)}
.stati{display:flex;flex-wrap:wrap;gap:8px;margin:.4rem 0 1rem}.stati .tag{font-size:.95rem;padding:2px 10px}
.tag.st{background:#e6f0fb;border-color:#9bbfe6;font-weight:600}
footer{border-top:1px solid var(--l);background:var(--sf);margin-top:3rem;padding:18px 0;font-size:.92rem}
@media(max-width:600px){html{scroll-padding-top:96px}header.top .fonte{font-size:.74rem;line-height:1.3;padding:3px 0}header.top .conc{font-size:.7rem}a.lingua{padding:0 6px}a.lingua svg{width:18px;height:12px}header.top .w.nav{padding:4px 16px;gap:0}header.top .w.nav>b{display:none}header.top.sc .conc{display:none}nav{gap:0 11px;font-size:.86rem}nav a{white-space:nowrap;padding:3px 0}body{font-size:17px}h1{font-size:1.65rem}dl.sch{grid-template-columns:1fr}dl.sch dt{margin-top:6px}}
"""

FLAG_IT = '<svg width="22" height="15" viewBox="0 0 3 2" aria-hidden="true"><rect width="1" height="2" fill="#009246"/><rect x="1" width="1" height="2" fill="#fff"/><rect x="2" width="1" height="2" fill="#ce2b37"/></svg>'
FLAG_UK = ('<svg width="22" height="15" viewBox="0 0 60 40" aria-hidden="true"><rect width="60" height="40" fill="#012169"/><path d="M0 0L60 40M60 0L0 40" stroke="#fff" stroke-width="8"/>'
           '<path d="M0 0L60 40M60 0L0 40" stroke="#c8102e" stroke-width="3"/><path d="M30 0V40M0 20H60" stroke="#fff" stroke-width="13"/><path d="M30 0V40M0 20H60" stroke="#c8102e" stroke-width="7"/></svg>')

FOOT_IT = '<p>I dati provengono da <a href="https://opencoesione.gov.it/">OpenCoesione</a> (licenza <a href="https://creativecommons.org/licenses/by/4.0/deed.it">CC BY 4.0</a>) e sono quelli comunicati dagli enti: per lo stato attuale di un\'opera consulta la scheda ufficiale e le fonti. Per segnalare una correzione scrivi a <a href="mailto:info@giuseppebosi.com">info@giuseppebosi.com</a>. Dati aggiornati al ' + "{DATA_DATI}" + '.</p>'
FOOT_EN = '<p>The data come from <a href="https://opencoesione.gov.it/">OpenCoesione</a> (licence <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>) and are those reported by public bodies: for the current state of a work, see the official page and the sources. Official project texts appear in Italian, as published in the source. To suggest a correction write to <a href="mailto:info@giuseppebosi.com">info@giuseppebosi.com</a>. Data updated to ' + "{DATA_ISO}" + '.</p>'

def pagina(percorso, titolo, corpo, attiva="", descr="", profondita=0):
    en = LANG == "en"
    rel = "../" * (profondita + (1 if en else 0))   # radice del sito (CSS)
    lrel = "../" * profondita                         # radice della lingua corrente (link di navigazione)
    dir_p = percorso[:-len("index.html")] if percorso.endswith("index.html") else percorso
    altra = ("../" * (profondita + 1) + dir_p) if en else (rel + "en/" + dir_p)
    flag = (f'<a class="lingua" href="{altra}" hreflang="it" lang="it" title="Italiano">{FLAG_IT}<span>IT</span></a>' if en
            else f'<a class="lingua" href="{altra}" hreflang="en" lang="en" title="English">{FLAG_UK}<span>EN</span></a>')
    alt_it = f'<link rel="alternate" hreflang="it" href="{SITO}/{dir_p}"><link rel="alternate" hreflang="en" href="{SITO}/en/{dir_p}">'
    nav = ([("", "Start here", "home"), ("opere/", "Projects", "opere"), ("dati/", "Full data", "dati"),
            ("metodo/", "Method and sources", "metodo"), ("guida/", "Tutorial", "guida"), ("guida/costruisci/", "Coding", "coding")] if en else
           [("", "Per cominciare", "home"), ("opere/", "Opere e progetti", "opere"), ("dati/", "Dati completi", "dati"),
            ("metodo/", "Metodo e fonti", "metodo"), ("guida/", "Tutorial", "guida"), ("guida/costruisci/", "Coding", "coding")])
    n = "".join(f'<a href="{lrel}{h}" class="{"on " if k == attiva else ""}{"tut" if k == "guida" else ("cod" if k == "coding" else "")}"{" aria-current=page" if k == attiva else ""}>{t}</a>' for h, t, k in nav)
    doc = f"""<!doctype html>
<html lang="{LANG}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(titolo)} | {T("Progetti pubblici sotto casa", "Public projects near home")}</title>{alt_it}
<meta name="description" content="{esc(descr or T('I progetti finanziati con fondi pubblici di coesione nel Comune di Arezzo, spiegati in modo semplice, con i dati ufficiali di OpenCoesione.', 'Projects funded with public cohesion funds in the Municipality of Arezzo, explained simply, with the official OpenCoesione data.'))}">
<link rel="stylesheet" href="{rel}stile.css"></head><body>
<header class="top"><div class="fonte"><div class="w fl"><span>{T("Fonte", "Source")}: <a href="https://opencoesione.gov.it/">OpenCoesione</a> · {T("ultimo aggiornamento dei dati", "latest data update")}: <strong>{DATA_ISO if en else DATA_DATI}</strong></span>{flag}</div><div class="w conc">{T("Progetto indipendente, a titolo didattico, con dati ufficiali.", "Independent project, for educational purposes, using official data.")}</div></div><div class="w nav"><b><a href="{lrel or './'}" style="text-decoration:none;color:inherit">{T("Progetti pubblici sotto casa", "Public projects near home")}</a></b><nav aria-label="Principale">{n}</nav></div></header>
<script>(function(){{var h=document.querySelector("header.top");function f(){{document.documentElement.style.scrollPaddingTop=(h.offsetHeight+8)+"px"}}function g(){{h.classList.toggle("sc",scrollY>40);f()}}f();addEventListener("resize",f);addEventListener("scroll",g,{{passive:true}})}})()</script>
<main class="w">{corpo}</main>
<footer><div class="w">{FOOT_EN.replace('{DATA_ISO}', DATA_ISO) if en else FOOT_IT.replace('{DATA_DATI}', DATA_DATI)}
<p>{T("A cura del Prof. Giuseppe Bosi, Scienze e Tecnologie Informatiche", "By Prof. Giuseppe Bosi, Computer Science and Technology")} — <a href="https://www.giuseppebosi.com">www.giuseppebosi.com</a></p></div></footer>
</body></html>"""
    p = os.path.join(SITE, ("en/" if en else "") + percorso)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(doc)

def avviso():
    return (T('<p class="avv"><strong>Cosa dicono i dati.</strong> I dati mostrano quanti soldi sono assegnati e pagati; per lo stato del cantiere guarda la scheda del progetto e le fonti.</p>',
              '<p class="avv"><strong>What the data show.</strong> The data show how much money is assigned and paid; for the state of a site, see the project page and the sources.</p>'))

URLMAP = {}

def apiurl(d):
    return URLMAP.get(d["cod_locale_progetto"]) or f"{api.BASE}/progetti/{d['cod_locale_progetto'].lower()}/?format=json"

def slug(d):
    return re.sub(r"[^a-z0-9_-]+", "-", d["cod_locale_progetto"].lower()).strip("-")

# ------------------------------------------------------------------ dati
tutti = carica()
_m = max(d.get('data_aggiornamento') or '' for d in tutti)
DATA_DATI = f'{_m[6:8]}/{_m[4:6]}/{_m[0:4]}'  # dalla API, non scritta a mano
DATA_ISO = f'{_m[0:4]}-{_m[4:6]}-{_m[6:8]}'
lista = json.load(open(os.environ.get("OC_LISTA") or os.path.join(ROOT, "dati", "lista_arezzo.json"), encoding="utf-8"))
URLMAP.update({r["cod_locale_progetto"]: r["url"] for r in lista})
semplici = {}
for i in (1, 2, 3):
    pi = os.path.join(ROOT, "dati", f"titoli_{i}.json")
    if os.path.exists(pi):
        semplici.update({k: {"titolo": v} for k, v in json.load(open(pi, encoding="utf-8")).items() if v})
sp = os.path.join(ROOT, "dati", "titoli_semplici.json")   # riscritture fatte a mano, hanno la precedenza
if os.path.exists(sp):
    semplici.update(json.load(open(sp, encoding="utf-8")))

def nel_perimetro(d):
    s = d["oc_stato_progetto"]
    if s in ("In corso", "Non avviato"):
        return True
    return bool(d["oc_data_fine_progetto_effettiva"]) and d["oc_data_fine_progetto_effettiva"] >= SOGLIA

impara_vocabolario([d["oc_titolo_progetto"] for d in tutti] + [x["denominazione"] for d in tutti for x in d["soggetti"]])
VOC.difference_update({"lotto", "lavori", "piazza", "palazzo", "centro", "comune", "regione", "provincia", "progetto", "azienda", "sistema", "servizi", "recupero", "restauro", "teatro", "ponte"})
perim = [d for d in tutti if nel_perimetro(d)]
senza_data = [d for d in tutti if d["oc_stato_progetto"] not in ("In corso", "Non avviato") and not d["oc_data_fine_progetto_effettiva"]]
prima_2016 = [d for d in tutti if d["oc_stato_progetto"] not in ("In corso", "Non avviato") and d["oc_data_fine_progetto_effettiva"] and d["oc_data_fine_progetto_effettiva"] < SOGLIA]
fin = lambda d: num(d["oc_finanz_tot_pub_netto"])
pag = lambda d: num(d["tot_pagamenti"])
tot_fin = sum(fin(d) for d in perim)
tot_pag = sum(pag(d) for d in perim)
corso = sorted([d for d in perim if d["oc_stato_progetto"] == "In corso"], key=fin, reverse=True)
nonav = sorted([d for d in perim if d["oc_stato_progetto"] == "Non avviato"], key=fin, reverse=True)
n_perim = len(perim)
n_lista = len(lista)
tot_lista = sum(num(r["oc_finanz_tot_pub_netto"]) for r in lista)
non_esaminati = n_lista - len(tutti)
pc = {d["cod_locale_progetto"] for d in perim}
fp = lambda rs: (sum(num(r["oc_finanz_tot_pub_netto"]) for r in rs), sum(num(r["tot_pagamenti"]) for r in rs))
fuori = [r for r in lista if r["cod_locale_progetto"] not in pc]
n_fuori = len(fuori)
fuori_fin, fuori_pag = fp(fuori)
tot_lista_pag = fp(lista)[1]
chk = fp([r for r in lista if r["cod_locale_progetto"] in pc])
assert round(chk[0]) == round(tot_fin) and round(chk[1]) == round(tot_pag), "lista e dettagli non coincidono"

def titolo_vis(d):
    s = semplici.get(d["cod_locale_progetto"])
    return (s["titolo"] if s else frase(d["oc_titolo_progetto"]))

def prevista(d):
    p = d["oc_data_fine_progetto_prevista"]
    return data(p) if p else None

def superata(d):
    p = d["oc_data_fine_progetto_prevista"]
    return d["oc_stato_progetto"] in ("In corso", "Non avviato") and bool(p) and p < "20260630" and not d["oc_data_fine_progetto_effettiva"]

def riga_progetto(d):
    extra = []
    extra.append(f'<span class="tag">{lab(tema_s(d), TEMI_EN)}</span> <span class="tag">{lab(natura(d), NATURA_EN)}</span> <span class="tag"><span lang="it">{esc(d["oc_stato_progetto"])}</span></span>')
    pv = prevista(d)
    if pv:
        extra.append(T("Fine prevista: ", "Planned end: ") + pv + (T(" (scadenza superata secondo i dati)", " (deadline passed according to the data)") if superata(d) else ""))
    return (f'<li><a lang="it" href="{{R}}progetti/{slug(d)}.html">{esc(titolo_vis(d))}</a><br>'
            f'<span class="mu" lang="it">{esc(ente_str(d))}</span><br>{T("Finanziato", "Funded")}: <strong>{eur(fin(d))}</strong> · {T("Già pagato", "Already paid")}: <strong>{eur(pag(d))}</strong><br>'
            f'<span class="small">{" · ".join(extra)}</span></li>')

# ------------------------------------------------------------------ home
def schema_svg(passi):
    """Schemino 'come funziona': 4 riquadri con frecce. Due versioni (orizzontale e verticale), scelte dal CSS."""
    def box(x, y, w, h, n, t, sub, tw):
        return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#fff" stroke="#0b5cab" stroke-width="2"/>'
                f'<circle cx="{x+22}" cy="{y+24}" r="13" fill="#0b5cab"/><text x="{x+22}" y="{y+29}" text-anchor="middle" font-size="14" font-weight="700" fill="#fff">{n}</text>'
                f'<text x="{x+42}" y="{y+29}" font-size="14" font-weight="700" fill="#1b2330">{esc(t)}</text>'
                f'<text x="{x+14}" y="{y+54}" font-size="13" fill="#566074">{esc(sub)}</text>')
    ar = lambda x1, y1, x2, y2: f'<path d="M{x1} {y1}L{x2} {y2}" stroke="#0b5cab" stroke-width="3" marker-end="url(#fr)"/>'
    defs = '<defs><marker id="fr" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0 0L8 4L0 8z" fill="#0b5cab"/></marker></defs>'
    desc = " → ".join(t for t, _ in passi)
    # verticale (telefono): viewBox 320 x 4*74+3*26
    v = defs + "".join(box(0, i*100, 320, 74, i+1, t, sub, 0) for i, (t, sub) in enumerate(passi)) + "".join(ar(160, i*100+76, 160, i*100+98) for i in range(3))
    # orizzontale (schermi larghi): 4 riquadri da 210, spazio 30
    h = defs + "".join(box(i*255, 0, 225, 74, i+1, t, sub, 0) for i, (t, sub) in enumerate(passi)) + "".join(ar(i*255+227, 37, i*255+252, 37) for i in range(3))
    return (f'<svg class="sch-o" viewBox="0 0 990 76" role="img" aria-label="{esc(desc)}" xmlns="http://www.w3.org/2000/svg">{h}</svg>'
            f'<svg class="sch-v" viewBox="0 0 320 374" role="img" aria-label="{esc(desc)}" xmlns="http://www.w3.org/2000/svg">{v}</svg>')

def home():
    en = LANG == "en"
    per_tema = collections.defaultdict(lambda: [0, 0, 0])
    per_tema_op = collections.defaultdict(lambda: [0, 0, 0])
    for d in perim:
        t = per_tema_op if is_opera(d) else per_tema
        t[tema_s(d)][0] += fin(d); t[tema_s(d)][1] += pag(d); t[tema_s(d)][2] += 1
    npj = lambda n: f"{n} project{'' if n == 1 else 's'}" if en else pl(n, "progetto", "progetti")
    def blocco(dic, titolo, nota):
        if not dic: return ""
        mx = max(v[0] for v in dic.values()) or 1
        righe = "".join(
            f'<div class="riga"><strong>{lab(k, TEMI_EN)}</strong> <span class="mu small">({npj(v[2])})</span><br>'
            f'<div class="bar" role="img" aria-label="{T("Finanziato", "Funded")} {eur(v[0])}"><i style="width:{max(1,v[0]/mx*100):.1f}%"></i></div>'
            f'<div class="bar" style="margin-top:3px" role="img" aria-label="{T("Pagato", "Paid")} {eur(v[1])}"><i class="p" style="width:{max(0.5,v[1]/mx*100) if v[1] else 0:.1f}%"></i></div>'
            f'<span class="small">{T("Finanziato", "Funded")} {eur(v[0])} · {T("Già pagato", "Already paid")} {eur(v[1])}</span></div>'
            for k, v in sorted(dic.items(), key=lambda kv: -kv[1][0]))
        return f"<h3>{titolo}</h3><p class='mu small'>{nota}</p>{righe}"
    op_n = sum(v[2] for v in per_tema_op.values())
    ent = collections.defaultdict(lambda: [0, 0, 0])
    for d in perim:
        for e in set(enti(d)):
            ent[e][0] += fin(d); ent[e][1] += pag(d); ent[e][2] += 1
    top_ent = sorted(ent.items(), key=lambda kv: -kv[1][0])[:8]
    ent_html = "".join(f'<li><strong lang="it">{esc(frase(k) if k.isupper() else k)}</strong><br>{npj(v[2])} · {T("finanziato", "funded")} {eur(v[0])} · {T("già pagato", "already paid")} {eur(v[1])}</li>' for k, v in top_ent)
    corso_html = "".join(riga_progetto(d).replace("{R}", "") for d in corso[:10])
    mig = lambda n: format(n, ",") if en else format(n, ",").replace(",", ".")
    ph = T("Cerca: scuola, ponte, museo", "Search (Italian words): scuola, ponte, museo")
    if en:
        c1 = f"""<h2>1. How much money do the main projects of Arezzo involve?</h2>
<p>We count <strong>{npj(n_perim)}</strong>: all those ongoing or not yet started, and those concluded since 2016 that are public works or purchases or are worth at least €100,000. The two figures are different: the first is the sum <em>assigned</em>, the second the sum <em>already paid</em>.</p>
<div class="cards">
<div class="card fin"><div class="n">{eur(tot_fin)}</div><div><strong>Funded</strong>: public money assigned.</div></div>
<div class="card pag"><div class="n">{eur(tot_pag)}</div><div><strong>Already paid</strong>: money actually paid out, according to the data.</div></div>
</div>
<p><strong>The rest of the projects.</strong> The data for Arezzo include another {mig(n_fuori)} projects, with {eur(fuori_fin)} funded and {eur(fuori_pag)} already paid: mostly small projects already concluded (training courses, grants to individuals), or concluded before 2016 or with the end date missing. With all projects together the total is {eur(tot_lista)} funded and {eur(tot_lista_pag)} already paid. Details in <a href="metodo/">Method and sources</a>.</p>

<h2>2. What for?</h2>
<p>Projects are grouped by topic. <strong>Works and purchases</strong> ({npj(op_n)}) are kept apart from grants, incentives and services, which are far more numerous but smaller individually. The blue bar is the funded amount, the green one the amount already paid. Topic names are our own plain labels, with the Italian one in brackets.</p>
{blocco(per_tema_op, "Works and purchases of goods", "Public works and purchases, for example roads, buildings, equipment.")}
{blocco(per_tema, "Grants, incentives and services", "Support to businesses, bodies and people, training, services.")}

<h2>3. What is being done now?</h2>
<p>These are the ten projects with status «<span lang="it">In corso</span>» (ongoing) with the largest amounts. The end date is the one planned by the body, if it exists. The full list, with {npj(len(corso))} ongoing and {len(nonav)} not yet started, is on the <a href="opere/">Projects</a> page.</p>
<ul class="lista">{corso_html}</ul>
<p><a class="btn" href="opere/">See all projects</a></p>

<h2>4. Who is in charge?</h2>
<p>Each project has a responsible body (who carries it out or receives the funding). These are the eight bodies with the most funded resources. Names are official and stay in Italian.</p>
<ul class="lista">{ent_html}</ul>

<h2>Want to see the original data?</h2>
<p>All the numbers above come from the public database OpenCoesione. In the <a href="guida/">Tutorial</a> you learn to read and download them yourself, and to <a href="guida/costruisci/">build a basic version of this website</a>. On the <a href="dati/">Full data</a> page you find all the columns and the file to open in a spreadsheet.</p>
"""
        top = f"""<div class="hero"><h1>What is being built with public money near your home?</h1>
<p class="lead">Find out which works and projects are funded in Arezzo with cohesion funds (European and national resources meant to reduce differences between territories): how much they cost, who is in charge and how far along they are, with official data.</p>
<p><strong>Here you can:</strong></p>
<ul class="puoi"><li>discover the works and projects of the Municipality of Arezzo;</li><li>see the amounts: how much money is assigned and how much already paid;</li><li>check how far along they are: declared status and planned dates.</li></ul>
<p class="small mu"><strong>Language.</strong> Project titles, descriptions and names of public bodies come from the official source and are shown in Italian, as published. The data are real; the interface is available in English.</p>
<form class="cerca" action="dati/" method="get" role="search"><input name="q" type="search" aria-label="Search for a project" placeholder="{ph}"><button type="submit">Search</button></form>
<div class="passi"><a href="opere/#corso"><strong>What is happening now</strong>Ongoing projects, largest first</a><a href="opere/"><strong>Projects</strong>The whole list</a><a href="dati/"><strong>Table and CSV file</strong>To filter and download the data</a></div></div>
<h2 class="pic">How it works</h2>
{schema_svg([("Official source", "OpenCoesione, public database"), ("Updated every 3 months", "download and automatic checks"), ("Titles in plain Italian", "original title shown beside it"), ("You search and check", "search, pages, source links")])}
<div class="build"><h2>Build it yourself: basic version, step by step</h2><p>Build a basic version of this site with Python in about fifteen minutes, from the same official data.</p><a class="btn pri" style="text-decoration:none" href="guida/costruisci/">Go to the coding guide</a><a class="btn" href="https://github.com/JoeBosi/public-projects-near-home">Code on GitHub</a></div>
<p class="avv"><strong>What the data show.</strong> The data show how much money is assigned and paid; for the state of a site, see the project page and the sources.</p>
"""
    else:
        c1 = f"""<h2>1. Quanti soldi riguardano i progetti principali di Arezzo?</h2>
<p>Contiamo <strong>{pl(n_perim, 'progetto', 'progetti')}</strong>: tutti quelli in corso o non ancora avviati e quelli conclusi dal 2016 che sono opere o valgono almeno 100.000 €. Le due cifre sono diverse: la prima è la somma <em>assegnata</em>, la seconda quella <em>già pagata</em>.</p>
<div class="cards">
<div class="card fin"><div class="n">{eur(tot_fin)}</div><div><strong>Finanziato</strong>: soldi pubblici assegnati.</div></div>
<div class="card pag"><div class="n">{eur(tot_pag)}</div><div><strong>Già pagato</strong>: soldi usciti davvero, secondo i dati.</div></div>
</div>
<p><strong>Il resto dei progetti.</strong> Nei dati di Arezzo ci sono altri {mig(n_fuori)} progetti, per {eur(fuori_fin)} finanziati e {eur(fuori_pag)} già pagati: per lo più piccoli progetti già conclusi (corsi, contributi alle persone), oppure conclusi prima del 2016 o con la data di fine mancante. Con tutti i progetti insieme il totale è {eur(tot_lista)} finanziati e {eur(tot_lista_pag)} già pagati. Dettagli nel <a href="metodo/">Metodo e fonti</a>.</p>

<h2>2. Per fare cosa?</h2>
<p>I progetti sono raggruppati per argomento. Le <strong>opere e gli acquisti</strong> ({pl(op_n, 'progetto', 'progetti')}) sono separati dai contributi, dagli incentivi e dai servizi, che sono molto più numerosi ma di importo singolo più piccolo. La barra blu è il finanziato, quella verde il già pagato.</p>
{blocco(per_tema_op, "Opere e acquisti di beni", "Lavori pubblici e acquisti, per esempio strade, edifici, impianti.")}
{blocco(per_tema, "Contributi, incentivi e servizi", "Aiuti a imprese, enti e persone, corsi, servizi.")}

<h2>3. Cosa si sta facendo adesso?</h2>
<p>Ecco i dieci progetti con stato «In corso» di importo maggiore. La data di fine è quella prevista dall'ente, se esiste. L'elenco completo, con {pl(len(corso), 'progetto', 'progetti')} in corso e {len(nonav)} non ancora avviati, è nella pagina <a href="opere/">Opere e progetti</a>.</p>
<ul class="lista">{corso_html}</ul>
<p><a class="btn" href="opere/">Vedi tutti i progetti</a></p>

<h2>4. Chi se ne occupa?</h2>
<p>Ogni progetto ha un ente responsabile (chi realizza o riceve il finanziamento). Questi sono gli otto enti con più risorse finanziate.</p>
<ul class="lista">{ent_html}</ul>

<h2>Vuoi vedere i dati originali?</h2>
<p>Tutti i numeri qui sopra vengono dalla banca dati pubblica OpenCoesione. Nel <a href="guida/">Tutorial</a> impari a leggerli e a scaricarli da solo, e a <a href="guida/costruisci/">costruire una versione base di questo sito</a>. Nella pagina <a href="dati/">Dati completi</a> trovi tutte le colonne e il file da aprire in un foglio di calcolo.</p>
"""
        top = f"""<div class="hero"><h1>Cosa si sta costruendo con i soldi pubblici vicino a casa tua?</h1>
<p class="lead">Scopri quali lavori e progetti sono finanziati ad Arezzo con i fondi di coesione (risorse europee e nazionali per ridurre le differenze tra territori): quanto costano, chi se ne occupa e a che punto sono, con i dati ufficiali.</p>
<p><strong>Qui puoi:</strong></p>
<ul class="puoi"><li>scoprire i lavori e i progetti del Comune di Arezzo;</li><li>vedere gli importi: quanti soldi sono assegnati e quanti già pagati;</li><li>controllare a che punto sono: stato dichiarato e date previste.</li></ul>
<form class="cerca" action="dati/" method="get" role="search"><input name="q" type="search" aria-label="Cerca un progetto" placeholder="{ph}"><button type="submit">Cerca</button></form>
<div class="passi"><a href="opere/#corso"><strong>Cosa si sta facendo adesso</strong>Progetti in corso, dal più grande</a><a href="opere/"><strong>Opere e progetti</strong>Tutto l'elenco, in parole semplici</a><a href="dati/"><strong>Tabella e file CSV</strong>Per filtrare e scaricare i dati</a></div></div>
<h2 class="pic">Come funziona</h2>
{schema_svg([("Fonte ufficiale", "OpenCoesione, banca dati pubblica"), ("Aggiornamento ogni 3 mesi", "scarico e controlli automatici"), ("Titoli in parole semplici", "con il titolo originale accanto"), ("Tu cerchi e controlli", "ricerca, schede, link alla fonte")])}
<div class="build"><h2>Costruiscilo tu: versione base, passo passo</h2><p>Crea in un quarto d'ora una versione base di questo sito con Python, partendo dagli stessi dati ufficiali.</p><a class="btn pri" style="text-decoration:none" href="guida/costruisci/">Vai al coding</a><a class="btn" href="https://github.com/JoeBosi/public-projects-near-home">Codice su GitHub</a></div>
<p class="avv"><strong>Cosa dicono i dati.</strong> I dati mostrano quanti soldi sono assegnati e pagati; per lo stato del cantiere guarda la scheda del progetto e le fonti.</p>
"""
    pagina("index.html", T("Cosa si sta costruendo con i soldi pubblici vicino a casa tua?", "What is being built with public money near your home?"), top + c1, "home")

# ------------------------------------------------------------------ elenco opere
def elenco():
    out = os.path.join(SITE, "en" if LANG == "en" else "", "opere"); os.makedirs(out, exist_ok=True)
    def sez(titolo, lst, ident):
        return f'<h2 id="{ident}">{titolo} ({len(lst)})</h2><ul class="lista">' + "".join(riga_progetto(d).replace("{R}", "../") for d in lst) + "</ul>"
    ope = sorted([d for d in perim if is_opera(d)], key=fin, reverse=True)
    altri_c = [d for d in corso if not is_opera(d)]
    c = f"""<h1>{T("Opere e progetti", "Projects")}</h1>
<p class="lead">{T("Le opere e gli acquisti sono elencati per primi; poi gli altri progetti in corso o non ancora avviati. I progetti conclusi dal 2016 che non sono opere si trovano in <a href='../dati/'>Dati completi</a>.", "Public works and purchases come first; then the other projects that are ongoing or not yet started. Projects concluded since 2016 that are not works are in <a href='../dati/'>Full data</a>.")}</p>
{T("", '<p class="small mu">Project titles, descriptions and the names of public bodies come from the official source and are shown in Italian, as published. Status values (<span lang="it">In corso</span> = ongoing, <span lang="it">Non avviato</span> = not started) are explained in <a href="../metodo/#glossario">Method and sources</a>.</p>')}
<p class="data">{T("Dati aggiornati al", "Data updated to")} {DATA_ISO if LANG == "en" else DATA_DATI}</p>{avviso()}
<p>{T("Vai a", "Jump to")}: <a href="#opere">{T("Opere e acquisti", "Works and purchases")}</a> · <a href="#corso">{T("In corso", "Ongoing")}</a> · <a href="#nonav">{T("Non ancora avviati", "Not yet started")}</a></p>
<div class="filtri"><label>{T("Cerca in questa pagina", "Search this page")} <input id="qo" type="search" placeholder="{T("per esempio scuola, ponte, museo", "Italian words, e.g. scuola, ponte, museo")}"></label><span id="conto" class="mu" aria-live="polite"></span></div>
<div id="vuotoo" class="vuoto" hidden>{T("Nessun progetto contiene questa parola. Prova con una parola più corta o cancella la ricerca. Per cercare tra tutti i progetti usa <a href='../dati/'>Dati completi</a>.", "No project contains this word. Try a shorter word or clear the search. The titles are in Italian. To search all projects use <a href='../dati/'>Full data</a>.")}</div>
{sez(T("Opere e acquisti di beni", "Works and purchases of goods"), ope, "opere")}
{sez(T("Altri progetti in corso", "Other ongoing projects"), altri_c, "corso")}
{sez(T("Progetti non ancora avviati", "Projects not yet started"), nonav, "nonav")}
<script src="filtro.js"></script>"""
    js = """(function(){var q=document.getElementById('qo'),c=document.getElementById('conto'),v=document.getElementById('vuotoo');
var li=[].slice.call(document.querySelectorAll('ul.lista li'));
function f(){var x=q.value.toLowerCase().trim(),n=0;li.forEach(function(e){var ok=!x||e.textContent.toLowerCase().indexOf(x)>-1;e.hidden=!ok;if(ok)n++});
document.querySelectorAll('h2[id]').forEach(function(h){var u=h.nextElementSibling;h.hidden=!!x&&!u.querySelector('li:not([hidden])')});
v.hidden=n>0;c.textContent=x?(n+(n==1?' @1':' @2')):''}
q.oninput=f;f()})();""".replace("@1", T("progetto trovato", "project found")).replace("@2", T("progetti trovati", "projects found"))
    open(os.path.join(out, "filtro.js"), "w").write(js)
    pagina("opere/index.html", T("Opere e progetti", "Projects"), c, "opere", profondita=1)

# ------------------------------------------------------------------ scheda
def scheda(d):
    en = LANG == "en"
    rip = [(T("Unione europea", "European Union"), d["oc_finanz_ue_netto"]), (T("Stato", "Italian State"), num(d["oc_finanz_stato_fsc_netto"]) + num(d["oc_finanz_stato_fondo_rot_netto"]) + num(d["oc_finanz_stato_altri_prov_netto"]) + num(d["oc_finanz_stato_compl_netto"]) + num(d["oc_finanz_stato_pac_netto"])),
           (T("Regione", "Region"), d["oc_finanz_regione_netto"]), (T("Provincia", "Province"), d["oc_finanz_provincia_netto"]), (T("Comune", "Municipality"), d["oc_finanz_comune_netto"]),
           (T("Altri soggetti pubblici", "Other public bodies"), d["oc_finanz_altro_pubblico_netto"]), (T("Privati", "Private"), d["oc_finanz_privato_netto"])]
    rip = [(k, num(v)) for k, v in rip if num(v) > 0]
    ripd = "".join(f"<li>{k}: {eur(v)}</li>" for k, v in rip) or "<li>" + T("dato non disponibile", "not available") + "</li>"
    fasi = "".join(
        f"<tr><td lang=\"it\">{esc(f['oc_descr_fase'])}</td><td>{data(f.get('data_inizio_prevista'))}</td><td>{data(f.get('data_inizio_effettiva'))}</td><td>{data(f.get('data_fine_prevista'))}</td><td>{data(f.get('data_fine_effettiva'))}</td></tr>"
        for f in d.get("fasi_procedurali", []))
    th = T("<th>Fase</th><th>Inizio previsto</th><th>Inizio effettivo</th><th>Fine prevista</th><th>Fine effettiva</th>", "<th>Phase (Italian)</th><th>Planned start</th><th>Actual start</th><th>Planned end</th><th>Actual end</th>")
    fasi_t = f'<h2>{T("Fasi dichiarate", "Declared phases")}</h2><div class="sc"><table><tr>{th}</tr>{fasi}</table></div>' if fasi else ""
    s = semplici.get(d["cod_locale_progetto"])
    if s and s["titolo"].strip() == (d["oc_titolo_progetto"] or "").strip():
        s = None
    orig = ((f'<p class="small mu">Titolo riscritto in italiano semplice a partire dal titolo e dalla sintesi ufficiali. Titolo originale: «{esc(d["oc_titolo_progetto"])}»</p>' if not en else
             f'<p class="small mu">The title is shown in Italian, rewritten in plain Italian from the official title and summary. Original official title: <span lang="it">«{esc(d["oc_titolo_progetto"])}»</span></p>') if s
            else ("" if not en else '<p class="small mu">The title is the official one, in Italian, as published in the source.</p>'))
    sint = d.get("oc_sintesi_progetto") or ""
    sint_h = f'<h2>{T("Descrizione ufficiale", "Official description (Italian)")}</h2><p lang="it">{esc(sint)}</p>' if sint and sint != d["oc_titolo_progetto"] else ""
    perc = f"{pag(d)/fin(d)*100:.0f}%" if fin(d) > 0 else T("dato non disponibile", "not available")
    note = ""
    if superata(d):
        note = (f'<p class="avv">La data di fine prevista ({prevista(d)}) è precedente alla data dei dati: scadenza superata secondo i dati.</p>' if not en else
                f'<p class="avv">The planned end date ({prevista(d)}) is earlier than the date of the data: deadline passed according to the data.</p>')
    cup = esc(d['cup'] or T('dato non disponibile', 'not available'))
    fase_c = (' · ' + T('fase', 'phase') + ': <span lang="it">' + esc(d['oc_descr_fase_corrente']) + '</span>') if d.get('oc_descr_fase_corrente') else ''
    c = f"""<p><a href="../opere/">← {T("Opere e progetti", "Projects")}</a></p>
<h1 lang="it">{esc(titolo_vis(d))}</h1>{orig}
<div class="stati"><span class="tag st" lang="it">{esc(d['oc_stato_progetto'])}</span><span class="tag">{lab(tema_s(d), TEMI_EN)}</span><span class="tag">{lab(natura(d), NATURA_EN)}</span></div>
<p class="lead" lang="it">{esc(ente_str(d))}</p><p class="lead">{eur(fin(d))} {T("finanziati", "funded")}, {eur(pag(d))} {T("già pagati", "already paid")}.</p>
<p class="data">{T("Dati di questo progetto aggiornati al", "Data for this project updated to")} {data(d.get('data_aggiornamento'))}</p>{note}
<div class="cards"><div class="card fin"><div class="n">{eur(fin(d))}</div>{T("Finanziato", "Funded")}</div><div class="card pag"><div class="n">{eur(pag(d))}</div>{T("Già pagato", "Already paid")} ({perc} {T("del finanziato", "of the funded amount")})</div></div>
<h2>{T("Che cos'è", "What it is")}</h2>
<dl class="sch"><dt>{T("Argomento", "Topic")}</dt><dd>{lab(tema_s(d), TEMI_EN)} <span class="small mu">({T("termine ufficiale", "official term")}: <span lang="it">{esc(tema(d))}</span>)</span></dd><dt>{T("Tipo", "Type")}</dt><dd><span lang="it">{esc(natura(d))}; {esc(frase(d['cup_descr_categoria']))}</span></dd>
<dt>{T("Chi se ne occupa", "Responsible body")}</dt><dd lang="it">{esc(ente_str(d))}</dd><dt>{T("Stato dichiarato", "Declared status")}</dt><dd><span lang="it">{esc(d['oc_stato_progetto'])}</span>{fase_c}</dd>
<dt>{T("Inizio del progetto", "Project start")}</dt><dd>{data(d['oc_data_inizio_progetto'])}</dd><dt>{T("Fine prevista del progetto", "Planned project end")}</dt><dd>{data(d['oc_data_fine_progetto_prevista'])}</dd><dt>{T("Fine effettiva del progetto", "Actual project end")}</dt><dd>{data(d['oc_data_fine_progetto_effettiva'])}</dd>
<dt>CUP</dt><dd>{cup} <span class="small mu">({T("Codice Unico di Progetto", "Unique Project Code")})</span></dd><dt>{T("Ciclo", "Cycle")}</dt><dd lang="it">{esc(d['oc_descr_ciclo'])}</dd></dl>
<p class="small mu">{T("«Dato non disponibile» significa che l'ente non ha comunicato quel dato alla fonte. Le date sopra sono quelle riferite all'intero progetto, comunicate dall'ente. La scheda ufficiale di OpenCoesione può mostrare invece le date di una singola fase, per esempio l'esecuzione dei lavori, che possono essere diverse: le fasi sono elencate più sotto.", "«Not available» means the body did not report that item to the source. The dates above refer to the whole project, as reported by the body. The official OpenCoesione page may instead show the dates of a single phase, for example the execution of works, which can differ: the phases are listed below.")}</p>
<h2>{T("Da dove vengono i soldi", "Where the money comes from")}</h2><ul>{ripd}</ul>
{sint_h}{fasi_t}
<h2>{T("Fonte", "Source")}</h2>
<p><a class="btn" href="{esc(d['oc_link'])}">{T("Scheda ufficiale su OpenCoesione", "Official page on OpenCoesione")}</a> <a class="btn" href="{esc(apiurl(d))}">{T("Vedi da dove vengono questi dati (JSON)", "See where this data comes from (JSON)")}</a></p>
<p class="small mu">{T("Il link «dati» è la risposta esatta della API usata per questa pagina. Per capire come leggerla: <a href='../guida/'>Guida agli open data</a>.", "The «data» link is the exact API response used for this page. To learn how to read it: <a href='../guida/'>Tutorial</a>.")}</p>"""
    pagina(f"progetti/{slug(d)}.html", titolo_vis(d), c, "opere", profondita=1)

# ------------------------------------------------------------------ dati completi + CSV
def dati_completi():
    campi = ["cod_locale_progetto", "cup", "titolo_originale", "ciclo", "tema", "natura", "stato", "fase_corrente", "ente", "finanziato_euro", "pagato_euro",
             "data_inizio", "fine_prevista", "fine_effettiva", "link_scheda_ufficiale", "link_api"]
    righe = []
    for d in sorted(perim, key=fin, reverse=True):
        righe.append([d["cod_locale_progetto"], d["cup"], d["oc_titolo_progetto"], d["oc_descr_ciclo"], d["oc_tema_sintetico"], d["cup_descr_natura"], d["oc_stato_progetto"],
                      d.get("oc_descr_fase_corrente", ""), "; ".join(enti(d)), f"{fin(d):.2f}", f"{pag(d):.2f}", d["oc_data_inizio_progetto"], d["oc_data_fine_progetto_prevista"],
                      d["oc_data_fine_progetto_effettiva"], d["oc_link"], apiurl(d)])
    os.makedirs(os.path.join(SITE, "dati"), exist_ok=True)
    os.makedirs(os.path.join(SITE, "en", "dati"), exist_ok=True)
    if LANG == "it":
      with open(os.path.join(SITE, "dati", "progetti-arezzo.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(campi); w.writerows(righe)
    if LANG == "it": json.dump([dict(zip(campi, r)) for r in righe], open(os.path.join(SITE, "dati", "progetti-arezzo.json"), "w", encoding="utf-8"), ensure_ascii=False)
    en = LANG == "en"
    stati = sorted({d["oc_stato_progetto"] for d in perim})
    temi = sorted({tema(d) for d in perim})
    tr = "".join(
        f'<tr data-s="{esc(d["oc_stato_progetto"])}" data-t="{esc(tema(d))}"><td lang="it"><a href="../progetti/{slug(d)}.html">{esc(titolo_vis(d))}</a></td><td>{esc(d["cup"])}</td><td lang="it">{esc(tema(d))}</td><td lang="it">{esc(d["oc_stato_progetto"])}</td>'
        f'<td data-v="{fin(d):.0f}">{eur(fin(d))}</td><td data-v="{pag(d):.0f}">{eur(pag(d))}</td><td>{data(d["oc_data_fine_progetto_prevista"])}</td><td>{data(d["oc_data_fine_progetto_effettiva"])}</td><td lang="it">{esc(ente_str(d))}</td></tr>'
        for d in sorted(perim, key=fin, reverse=True))
    CSV = "../../dati/progetti-arezzo.csv" if en else "progetti-arezzo.csv"
    JSN = "../../dati/progetti-arezzo.json" if en else "progetti-arezzo.json"
    heads = T("<th>Titolo</th><th>CUP</th><th>Argomento</th><th>Stato</th><th>Finanziato</th><th>Già pagato</th><th>Fine prevista</th><th>Fine effettiva</th><th>Ente</th>",
              "<th>Title (Italian)</th><th>CUP</th><th>Topic (Italian)</th><th>Status (Italian)</th><th>Funded</th><th>Already paid</th><th>Planned end</th><th>Actual end</th><th>Body (Italian)</th>")
    c = f"""<h1>{T("Dati completi", "Full data")}</h1>
<p class="lead">{T(f"Tutti i {pl(n_perim, 'progetto', 'progetti')} considerati, con le colonne principali. Puoi filtrare e scaricare il file da aprire in un foglio di calcolo.", f"All {n_perim} projects considered, with the main columns. You can filter them and download the file to open in a spreadsheet.")}</p>
{T("", '<p class="small mu">Titles, topics, statuses and body names are the official Italian texts from the source, shown as published. The CSV and JSON files are the same as on the Italian site: column names and values are in Italian. Meaning of the status values: <a href="../metodo/#glossario">Method and sources</a>.</p>')}
<p class="data">{T("Dati aggiornati al", "Data updated to")} {DATA_ISO if en else DATA_DATI}</p>{avviso()}
<p><a class="btn" href="{CSV}" download>{T("Scarica CSV (foglio di calcolo)", "Download CSV (spreadsheet)")}</a> <a class="btn" href="{JSN}" download>{T("Scarica JSON", "Download JSON")}</a></p>
<p class="small mu">{T("Il CSV usa il punto come separatore decimale e contiene i valori in euro senza simboli. Come aprirlo: <a href='../guida/#csv'>Guida agli open data</a>.", "The CSV uses a dot as decimal separator and holds euro values without symbols. How to open it: <a href='../guida/#csv'>Tutorial</a>.")}</p>
<div class="filtri"><label>{T("Cerca", "Search")} <input id="q" type="search" placeholder="{T("parola nel titolo o ente", "word in the title or body (Italian)")}"></label>
<label>{T("Stato", "Status")} <select id="fs"><option value="">{T("Tutti", "All")}</option>{''.join(f'<option>{esc(x)}</option>' for x in stati)}</select></label>
<label>{T("Argomento", "Topic")} <select id="ft"><option value="">{T("Tutti", "All")}</option>{''.join(f'<option>{esc(x)}</option>' for x in temi)}</select></label>
<span id="cont" class="mu" aria-live="polite"></span></div>
<div class="sc"><table id="tab"><thead><tr>{heads}</tr></thead><tbody>{tr}</tbody></table></div>
<div id="vuoto" class="vuoto" hidden>{T("Nessun progetto corrisponde ai filtri.", "No project matches the filters.")} <button type="button" id="azzera" class="btn">{T("Azzera i filtri", "Clear filters")}</button></div>
<noscript><p>{T("Per filtrare serve JavaScript; l'elenco è comunque completo e il CSV è scaricabile.", "Filtering needs JavaScript; the list is complete anyway and the CSV can be downloaded.")}</p></noscript>
<script src="filtri.js"></script>"""
    pagina("dati/index.html", T("Dati completi", "Full data"), c, "dati", profondita=1)
    js = """(function(){var q=document.getElementById('q'),s=document.getElementById('fs'),t=document.getElementById('ft'),c=document.getElementById('cont'),v=document.getElementById('vuoto'),z=document.getElementById('azzera');
var rows=[].slice.call(document.querySelectorAll('#tab tbody tr'));
function f(){var x=q.value.toLowerCase().trim(),n=0;rows.forEach(function(r){
var ok=(!s.value||r.dataset.s===s.value)&&(!t.value||r.dataset.t===t.value)&&(!x||r.textContent.toLowerCase().indexOf(x)>-1);r.hidden=!ok;if(ok)n++});
c.textContent=n+(n==1?' @1':' @2');v.hidden=n>0}
q.oninput=s.onchange=t.onchange=f;
z.onclick=function(){q.value='';s.value='';t.value='';f();q.focus()};
try{var p=new URLSearchParams(location.search);if(p.get('q'))q.value=p.get('q')}catch(e){}
f()})();""".replace("@1", T("progetto mostrato", "project shown")).replace("@2", T("progetti mostrati", "projects shown"))
    open(os.path.join(SITE, "en" if en else "", "dati", "filtri.js"), "w").write(js)

# ------------------------------------------------------------------ metodo
def metodo():
    fuori_c = len([r for r in lista if r["oc_stato_progetto"] == "Concluso"]) - len([d for d in tutti if d["oc_stato_progetto"] == "Concluso"])
    c = f"""<h1>Metodo e fonti</h1>
<p class="data">Dati aggiornati al {DATA_DATI}</p>
<h2>Fonte</h2>
<p>Tutti i progetti vengono dalla API pubblica di <a href="https://opencoesione.gov.it/it/api/">OpenCoesione</a>, il portale ufficiale sui progetti finanziati dalle politiche di coesione, curato con la Ragioneria Generale dello Stato. Licenza: <a href="https://creativecommons.org/licenses/by/4.0/deed.it">Creative Commons Attribuzione 4.0</a> (si può riusare citando la fonte). Data di aggiornamento dichiarata dalla API: 30/06/2026. Per i progetti usiamo solo questa fonte.</p>
<h2>Che cosa abbiamo preso</h2>
<p>I progetti localizzati nel Comune di Arezzo (parametro <code>territorio=arezzo-comune</code>): {n_lista} in totale, dal ciclo di programmazione 2000-2006 in poi. Di questi mostriamo quelli del perimetro seguente.</p>
<h2>Perimetro: cosa è contato e dove trovi il resto</h2>
<p><strong>Contati ({pl(n_perim, 'progetto', 'progetti')}, {eur(tot_fin)} finanziati, {eur(tot_pag)} già pagati):</strong></p>
<ul><li>tutti i progetti con stato «In corso» o «Non avviato»;</li>
<li>i progetti «Concluso», «Liquidato» o «Non determinabile» con data di fine effettiva dal 1° gennaio 2016, ma solo se sono opere (lavori pubblici o acquisto di beni) oppure hanno un finanziamento di almeno 100.000 €. Poiché la data di fine di progetto può differire da quella della scheda ufficiale (che spesso indica la fine dei lavori), il confine del 2016 va inteso «secondo il campo di progetto».</li></ul>
<p><strong>Il resto dei progetti, indicato a parte ({format(n_fuori, ",").replace(",", ".")} progetti, {eur(fuori_fin)} finanziati, {eur(fuori_pag)} già pagati):</strong></p>
<ul><li><strong>{format(non_esaminati, ",").replace(",", ".")}</strong> progetti conclusi, di importo inferiore a 100.000 € e diversi dalle opere (per lo più corsi, voucher e contributi individuali). Per rispettare i limiti di frequenza della API, di questi progetti usiamo la lista di OpenCoesione, importi compresi; la data di fine di ciascuno si trova nella sua scheda ufficiale.</li>
<li><strong>{len(senza_data)}</strong> progetti, tra quelli scaricati, conclusi con la data di fine effettiva mancante.</li>
<li><strong>{len(prima_2016)}</strong> progetti, tra quelli scaricati, con fine effettiva prima del 2016.</li></ul>
<p>Totale di tutti i progetti di Arezzo nella banca dati: {pl(n_lista, 'progetto', 'progetti')}, {eur(tot_lista)} finanziati, {eur(tot_lista_pag)} già pagati. Progetti contati e resto dei progetti sommano a questo totale. Per i progetti contati, i totali calcolati dalle schede di dettaglio coincidono con quelli ricavati dalla lista (controllo automatico a ogni costruzione del sito). Finanziato e pagato sono due misure distinte: in alcuni casi il pagato supera il finanziato netto.</p>
<h2>Significato dei campi</h2>
<ul><li><strong>Finanziato</strong>: campo <code>oc_finanz_tot_pub_netto</code>, finanziamento pubblico totale al netto delle economie, cioè dei risparmi già tolti.</li>
<li><strong>Già pagato</strong>: campo <code>tot_pagamenti</code>, pagamenti totali registrati. Finanziato e pagato sono sempre mostrati separati, come due misure distinte: un progetto può avere pagato più o meno del finanziato.</li>
<li id="glossario"><strong>Stato</strong>: campo <code>oc_stato_progetto</code>, riportato esattamente come dichiarato dalla fonte (In corso, Non avviato, Concluso, Liquidato, Non determinabile).</li>
<li><strong>Date</strong>: inizio, fine prevista e fine effettiva del progetto (campi <code>oc_data_inizio_progetto</code>, <code>oc_data_fine_progetto_prevista</code>, <code>oc_data_fine_progetto_effettiva</code>) sono quelle riferite all'intero progetto, comunicate dagli enti. La scheda ufficiale su OpenCoesione mostra invece, in alto, le date dell'esecuzione dei lavori, che possono differire (controllo fatto a mano su tre progetti: pagamenti identici, date di fine diverse per questo motivo). Le date di ogni fase sono riportate nelle schede. Se una data manca, il sito scrive «dato non disponibile».</li>
<li><strong>Argomento</strong>: tema sintetico di OpenCoesione, con nomi più brevi (per esempio «Trasporti e mobilità» diventa «Strade e trasporti»).</li>
<li><strong>Opere e acquisti</strong>: progetti con natura CUP «Realizzazione di lavori pubblici» o «Acquisto di beni». Tutto il resto è «contributi, incentivi e servizi».</li></ul>
<h2>Etichette</h2>
<p>Per i progetti con stato «In corso» o «Non avviato», con data di fine prevista precedente al 30/06/2026 e data di fine effettiva assente, il sito scrive «scadenza superata secondo i dati». È un confronto tra due date della fonte, a titolo informativo.</p>
<h2>Titoli riscritti</h2>
<p>Alcuni titoli, in origine tecnici o in maiuscolo, sono riscritti in italiano semplice con un assistente di intelligenza artificiale (IA), solo a partire dal titolo e dalla sintesi ufficiali usando solo le informazioni già presenti. Accanto c'è sempre il titolo originale e la scritta «titolo riscritto in italiano semplice». I titoli in maiuscolo mantenuti come sono vengono mostrati con la sola iniziale maiuscola.</p>
<h2>Arrotondamenti</h2>
<p>Gli importi sono mostrati in euro interi, arrotondati; le somme sono calcolate sui valori originali e poi arrotondate, quindi la somma di cifre mostrate può differire di qualche euro. Le percentuali sono arrotondate all'intero.</p>
<h2>Limiti</h2>
<ul><li>Il sito mostra i progetti per Comune: la fonte indica il Comune in cui ciascun progetto è localizzato.</li>
<li>I progetti localizzati in più territori compaiono anche in quelli: gli importi sono quelli complessivi del progetto, riferiti a tutti i suoi territori.</li>
<li>Il sito è dedicato ad Arezzo; un confronto con altri Comuni richiederebbe lo stesso perimetro e dati demografici verificati.</li>
<li>Nei titoli degli interventi individuali a favore di persone fisiche il nome è omesso dal sito («[nome omesso]»), anche se presente nella fonte.</li>
<li>Alcuni testi della fonte contengono caratteri sostituiti da «?» (per esempio apostrofi e accenti): sono nei dati originali.</li></ul>
<h2>Come verificare</h2>
<p>Ogni scheda ha il link alla pagina ufficiale e il link alla risposta esatta della API. Vedi la <a href="../guida/">Guida agli open data</a>.</p>"""
    pagina("metodo/index.html", "Metodo e fonti", c, "metodo", profondita=1)

# ------------------------------------------------------------------ guida
def guida():
    es_idx = api.get(api.BASE + "/")
    es_due = api.get(api.BASE + "/progetti/?format=json&territorio=arezzo-comune&page_size=2")
    es_corso = api.get(api.BASE + "/progetti/?format=json&territorio=arezzo-comune&stato=in_corso&page_size=1")
    es_p2 = api.get(api.BASE + "/progetti/?format=json&territorio=arezzo-comune&page_size=2&page=2")
    es_det = api.get(es_due["results"][0]["url"])
    tronca = lambda o: json.dumps(o, ensure_ascii=False, indent=2)
    r0 = es_due["results"][0]
    esempio_corto = {k: r0[k] for k in ("cod_locale_progetto", "cup", "oc_titolo_progetto", "oc_finanz_tot_pub_netto", "tot_pagamenti", "oc_stato_progetto")}
    det_corto = {k: es_det[k] for k in ("cod_locale_progetto", "cup", "oc_titolo_progetto", "oc_finanz_tot_pub_netto", "tot_pagamenti", "oc_stato_progetto", "oc_data_inizio_progetto", "oc_data_fine_progetto_effettiva")}
    B = "https://opencoesione.gov.it/it/api"
    u2 = B + "/progetti/?format=json&territorio=arezzo-comune&page_size=2"
    c = f"""<h1>Tutorial: guida agli open data</h1>
<p><a class="btn pri" href="costruisci/" style="text-decoration:none">Costruisci una versione base del sito, passo passo</a></p>
<p class="lead">Una guida per chi parte da zero. Ogni esempio è stato eseguito davvero sui dati di Arezzo il giorno in cui è stato scritto questo sito; i numeri che vedi sono quelli reali.</p>
<p class="data">Esempi eseguiti sui dati al {DATA_DATI}</p>
<nav aria-label="Indice" class="small"><a href="#cosa">1. Cosa sono</a> · <a href="#dove">2. Dove si trovano</a> · <a href="#licenze">3. Licenze</a> · <a href="#api">4. Cos'è una API</a> · <a href="#json">5. Leggere il JSON</a> · <a href="#param">6. Parametri</a> · <a href="#pagine">7. Paginazione</a> · <a href="#csv">8. CSV nel foglio di calcolo</a> · <a href="#soldi">9. Finanziato e pagato</a> · <a href="#verifica">10. Verificare un dato</a> · <a href="#python">11. Python (facoltativo)</a></nav>

<h2 id="cosa">1. Cosa sono gli open data</h2>
<p>Gli <strong>open data</strong> (dati aperti) sono informazioni pubbliche che chiunque può scaricare, controllare e riusare, in un formato che un computer sa leggere. Un esempio: l'elenco dei progetti finanziati con soldi pubblici, con importi e date. Aperto significa che non serve chiedere il permesso e non si paga.</p>
<h2 id="dove">2. Dove si trovano</h2>
<p>Ogni amministrazione pubblica può pubblicarli. Alcuni punti di partenza: <a href="https://www.dati.gov.it/">dati.gov.it</a> (catalogo nazionale) e <a href="https://opencoesione.gov.it/it/opendata/">OpenCoesione</a>, la fonte di questo sito. OpenCoesione offre due strade: file interi da scaricare (per esempio l'elenco di tutti i progetti, in un archivio compresso) e una <strong>API</strong>, cioè un servizio per chiedere solo i dati che servono.</p>
<h2 id="licenze">3. Licenze</h2>
<p>Un dato aperto ha una licenza che dice cosa puoi farne. I dati di OpenCoesione usano la licenza <a href="https://creativecommons.org/licenses/by/4.0/deed.it">CC BY 4.0</a> (Creative Commons Attribuzione): puoi copiarli, modificarli e anche usarli commercialmente, a patto di <strong>citare la fonte</strong>. Per esempio: «Fonte: OpenCoesione, dati al 30/06/2026».</p>
<h2 id="api">4. Cos'è una API, con un esempio vero</h2>
<p>Una <strong>API</strong> (interfaccia di programmazione) è un indirizzo web che invece di una pagina da leggere restituisce dati. Non serve installare nulla: basta il browser. Apri questo indirizzo:</p>
<pre><code>{B}/</code></pre>
<p><a class="btn" href="{B}/">Apri nel browser</a></p>
<p>Vedrai un elenco di «sezioni» della banca dati. Questa è la risposta che abbiamo ottenuto:</p>
<pre><code>{esc(tronca(es_idx))}</code></pre>
<p>Ogni voce è un altro indirizzo. Noi useremo <code>progetti</code>.</p>
<h2 id="json">5. Leggere il JSON</h2>
<p>I dati arrivano in formato <strong>JSON</strong>: testo con coppie «nome: valore» tra parentesi graffe. Apri l'indirizzo seguente (chiede i progetti del Comune di Arezzo, due soltanto):</p>
<pre><code>{u2}</code></pre>
<p><a class="btn" href="{u2}">Apri nel browser</a></p>
<p>Il numero <code>count</code> è il totale dei progetti trovati: <strong>{es_due['count']}</strong>. Il primo risultato, ridotto ai campi principali, è questo:</p>
<pre><code>{esc(tronca(esempio_corto))}</code></pre>
<p>Si legge così: <code>oc_finanz_tot_pub_netto</code> è il <em>finanziato</em>, <code>tot_pagamenti</code> è il <em>pagato</em>, <code>oc_stato_progetto</code> è lo stato. Gli importi hanno la virgola come separatore decimale e sono scritti come testo.</p>
<h2 id="param">6. I parametri: chiedere solo quello che serve</h2>
<p>Dopo il punto interrogativo ci sono i <strong>parametri</strong>, separati da <code>&amp;</code>:</p>
<ul><li><code>format=json</code>: il formato della risposta;</li><li><code>territorio=arezzo-comune</code>: il Comune;</li><li><code>page_size=2</code>: quanti risultati per volta;</li><li><code>stato=in_corso</code>: solo i progetti in corso.</li></ul>
<p>Aggiungendo <code>stato=in_corso</code> il totale diventa <strong>{es_corso['count']}</strong>:</p>
<pre><code>{B}/progetti/?format=json&amp;territorio=arezzo-comune&amp;stato=in_corso&amp;page_size=1</code></pre>
<p><a class="btn" href="{B}/progetti/?format=json&amp;territorio=arezzo-comune&amp;stato=in_corso&amp;page_size=1">Apri nel browser</a></p>
<h2 id="pagine">7. La paginazione</h2>
<p>Con migliaia di risultati la API li consegna a gruppi, le <strong>pagine</strong>. Nella risposta trovi <code>current_page</code> (pagina attuale: {es_due['current_page']}), <code>last_page</code> (ultima: {es_due['last_page']}) e <code>next</code>, l'indirizzo della pagina successiva. Per passare alla pagina 2 si aggiunge <code>page=2</code>:</p>
<pre><code>{u2}&amp;page=2</code></pre>
<p><a class="btn" href="{u2}&amp;page=2">Apri nel browser</a></p>
<p>Il primo progetto della pagina 2 è «{esc(frase(es_p2['results'][0]['oc_titolo_progetto']))}». Per scaricare tutto si continua finché <code>next</code> è vuoto, aspettando un secondo tra una richiesta e l'altra per non appesantire il servizio.</p>
<h2 id="csv">8. Il CSV nel foglio di calcolo</h2>
<p>Un <strong>CSV</strong> è una tabella in un file di testo, con le colonne separate da virgole. Si apre con Excel, LibreOffice o Fogli Google. La API di OpenCoesione risponde solo in JSON, quindi abbiamo convertito noi i progetti di questo sito in un CSV: <a href="../dati/progetti-arezzo.csv" download>scarica progetti-arezzo.csv</a> ({pl(n_perim, 'riga', 'righe')}). Per i file interi, già in CSV, c'è la pagina <a href="https://opencoesione.gov.it/it/opendata/">dati scaricabili di OpenCoesione</a>.</p>
<ol><li>Scarica il file.</li><li>In LibreOffice: «File → Apri», scegli il file, nella finestra di importazione lascia «Unicode (UTF-8)» e separatore «Virgola». In Excel: «Dati → Da testo/CSV». In Fogli Google: «File → Importa → Carica».</li><li>Per filtrare: seleziona la riga delle intestazioni e attiva il filtro automatico (menu «Dati»). Scegli per esempio <code>stato</code> uguale a «In corso».</li><li>Per sommare: seleziona la colonna <code>finanziato_euro</code> e leggi la somma in basso. Fai la stessa cosa con <code>pagato_euro</code>: sono due totali diversi.</li></ol>
<h2 id="soldi">9. Importo finanziato e pagamenti</h2>
<p>Il <strong>finanziato</strong> è la somma assegnata al progetto; il <strong>pagato</strong> è quanto è stato effettivamente versato. Nel progetto «{esc(frase(es_det['oc_titolo_progetto']))}» (CUP {esc(es_det['cup'])}) il finanziato è {eur(num(es_det['oc_finanz_tot_pub_netto']))} e il pagato è {eur(num(es_det['tot_pagamenti']))}. In altri progetti le due cifre differiscono: per questo sul sito non vengono mai sommate né confuse.</p>
<h2>Cercare un CUP</h2>
<p>Il <strong>CUP</strong> (Codice Unico di Progetto) è il «codice fiscale» di un progetto pubblico: identifica lo stesso progetto in banche dati diverse. Ogni scheda di questo sito lo riporta, e nella tabella di <a href="../dati/">Dati completi</a> puoi scrivere un CUP nel campo «Cerca».</p>
<h2 id="verifica">10. Come verificare un dato</h2>
<ol><li>Apri la scheda del progetto su questo sito.</li><li>Premi «Scheda ufficiale su OpenCoesione» e confronta importi e stato.</li><li>Premi «Vedi da dove vengono questi dati»: è il JSON della API. Cerca <code>oc_finanz_tot_pub_netto</code> e <code>tot_pagamenti</code>.</li></ol>
<p>Dettaglio di un progetto, ridotto ai campi principali ({esc(es_due['results'][0]['url'])}):</p>
<pre><code>{esc(tronca(det_corto))}</code></pre>
<p>Le date sono scritte come anno, mese, giorno senza separatori: <code>20220629</code> significa 29/06/2022.</p>
<h2 id="python">11. Primi passi con Python (facoltativo)</h2>
<p>Se vuoi automatizzare, ecco un programma di poche righe che usa solo la libreria standard di Python (si installa da <a href="https://www.python.org/">python.org</a>). Salvalo come <code>progetti.py</code> ed eseguilo con <code>python progetti.py</code>:</p>
<pre><code>import json, urllib.request

url = "{u2}"
with urllib.request.urlopen(url) as risposta:
    dati = json.load(risposta)

print("Progetti trovati:", dati["count"])
for p in dati["results"]:
    print(p["cup"], p["oc_stato_progetto"], p["oc_finanz_tot_pub_netto"], p["tot_pagamenti"])</code></pre>
<p>Risultato ottenuto eseguendolo:</p>
<pre><code>Progetti trovati: {es_due['count']}
{chr(10).join(f"{p['cup']} {p['oc_stato_progetto']} {p['oc_finanz_tot_pub_netto']} {p['tot_pagamenti']}" for p in es_due['results'])}</code></pre>
<p class="small mu">Quando scarichi molte pagine, aspetta almeno un secondo tra una richiesta e l'altra e salva le risposte sul tuo computer per non ripeterle.</p>"""
    pagina("guida/index.html", "Guida agli open data", c, "guida", profondita=1)

# ------------------------------------------------------------------ inglese: metodo e guida
def metodo_en():
    c = f"""<h1>Method and sources</h1>
<p class="data">Data updated to {DATA_ISO}</p>
<p class="small mu"><strong>Language note.</strong> This page is the English version. Project titles, descriptions, topics, statuses and body names come from the official source and stay in Italian; they are shown in Italian, as published.</p>
<h2>Source</h2>
<p>All projects come from the public API of <a href="https://opencoesione.gov.it/it/api/">OpenCoesione</a>, the official Italian portal on projects funded by cohesion policy, run with the State General Accounting Department. Licence: <a href="https://creativecommons.org/licenses/by/4.0/">Creative Commons Attribution 4.0</a> (reuse is allowed if you credit the source). Update date declared by the API: {DATA_ISO}. For projects we use only this source.</p>
<h2>What we took</h2>
<p>The projects located in the Municipality of Arezzo (parameter <code>territorio=arezzo-comune</code>): {n_lista} in total, from the 2000-2006 programming cycle onwards. We show those that fall in the perimeter below.</p>
<h2>Perimeter: what is counted and where to find the rest</h2>
<p><strong>Counted ({n_perim} projects, {eur(tot_fin)} funded, {eur(tot_pag)} already paid):</strong></p>
<ul><li>all projects with status «In corso» (ongoing) or «Non avviato» (not started);</li>
<li>projects «Concluso», «Liquidato» or «Non determinabile» with an actual end date from 1 January 2016, but only if they are works (public works or purchase of goods) or have funding of at least €100,000. The project end date may differ from the one on the official page (which often shows the end of works), so the 2016 boundary is meant «according to the project field».</li></ul>
<p><strong>The rest of the projects, listed separately ({format(n_fuori, ",")} projects, {eur(fuori_fin)} funded, {eur(fuori_pag)} already paid):</strong></p>
<ul><li><strong>{format(non_esaminati, ",")}</strong> concluded projects of less than €100,000 other than works (mostly training courses, vouchers and individual grants). To respect the API's rate limits, for these projects we use the OpenCoesione list, amounts included; the end date of each one is on its official page.</li>
<li><strong>{len(senza_data)}</strong> projects, among those downloaded, concluded with the actual end date missing.</li>
<li><strong>{len(prima_2016)}</strong> projects, among those downloaded, with an actual end before 2016.</li></ul>
<p>Total of all projects of Arezzo in the database: {n_lista} projects, {eur(tot_lista)} funded, {eur(tot_lista_pag)} already paid. Counted projects and the rest of the projects add up to this total. For the counted projects, the totals computed from the detail records match those taken from the list (automatic check at every build). Funded and paid are two distinct measures: in some cases the paid amount exceeds the net funded amount.</p>
<h2>Meaning of the fields</h2>
<ul><li><strong>Funded</strong>: field <code>oc_finanz_tot_pub_netto</code>, total public funding net of savings (amounts already deducted).</li>
<li><strong>Already paid</strong>: field <code>tot_pagamenti</code>, total payments recorded. Funded and paid are always shown separately, as two distinct measures.</li>
<li><strong>Status</strong>: field <code>oc_stato_progetto</code>, reported exactly as declared by the source.</li>
<li><strong>Dates</strong>: start, planned end and actual end of the project (fields <code>oc_data_inizio_progetto</code>, <code>oc_data_fine_progetto_prevista</code>, <code>oc_data_fine_progetto_effettiva</code>) refer to the whole project, as reported by the bodies. The official OpenCoesione page shows, at the top, the dates of the execution of works, which can differ (hand check on three projects: identical payments, different end dates for this reason). If a date is missing the site writes «not available».</li>
<li><strong>Topic</strong>: OpenCoesione's synthetic theme, with shorter plain names on the home page.</li>
<li><strong>Works and purchases</strong>: projects whose CUP nature is «Realizzazione di lavori pubblici» (public works) or «Acquisto di beni» (purchase of goods). Everything else is «grants, incentives and services».</li></ul>
<h2 id="glossario">Glossary of status values (Italian to English)</h2>
<p>These are the only status values that appear in the data. We keep the Italian word on the site because it is the value declared by the source; the English meaning is given here as a help.</p>
<ul><li><span lang="it">In corso</span>: ongoing</li><li><span lang="it">Non avviato</span>: not started</li><li><span lang="it">Concluso</span>: concluded</li><li><span lang="it">Liquidato</span>: settled (payments completed)</li><li><span lang="it">Non determinabile</span>: not determinable (the source could not determine the status)</li></ul>
<h2>Labels</h2>
<p>For projects with status «In corso» or «Non avviato», with a planned end date earlier than the data date and the actual end date missing, the site writes «deadline passed according to the data». It is a comparison between two dates of the source, for information only.</p>
<h2>Rewritten titles</h2>
<p>Some titles, originally technical or in capitals, are rewritten in plain Italian with an artificial intelligence (AI) assistant, only from the official title and summary using only the information already there. The original title is always shown beside it. Capitalised titles kept as they are are shown with only the first letter in capitals. New projects keep the official title until they are simplified.</p>
<h2>Rounding</h2>
<p>Amounts are shown in whole euros, rounded; sums are computed on the original values and then rounded, so the sum of the figures shown may differ by a few euros.</p>
<h2>Limits</h2>
<ul><li>The site shows projects by municipality: the source gives the municipality where each project is located.</li>
<li>Projects located in several territories also appear in those: amounts are the project's overall figures, covering all its territories.</li>
<li>The site is dedicated to Arezzo; a comparison with other municipalities would need the same perimeter and verified demographic data.</li>
<li>In titles of individual interventions in favour of natural persons the name is omitted from the site («[nome omesso]»), even if present in the source.</li>
<li>Some texts of the source contain characters replaced by «?» (for example apostrophes and accents): they are in the original data.</li></ul>
<h2>How to check</h2>
<p>Every project page has a link to the official page and a link to the exact API response. See the <a href="../guida/">Tutorial</a>.</p>"""
    pagina("metodo/index.html", "Method and sources", c, "metodo", profondita=1)

def guida_en():
    es_idx = api.get(api.BASE + "/")
    es_due = api.get(api.BASE + "/progetti/?format=json&territorio=arezzo-comune&page_size=2")
    es_corso = api.get(api.BASE + "/progetti/?format=json&territorio=arezzo-comune&stato=in_corso&page_size=1")
    es_p2 = api.get(api.BASE + "/progetti/?format=json&territorio=arezzo-comune&page_size=2&page=2")
    es_det = api.get(es_due["results"][0]["url"])
    tronca = lambda o: json.dumps(o, ensure_ascii=False, indent=2)
    r0 = es_due["results"][0]
    esempio_corto = {k: r0[k] for k in ("cod_locale_progetto", "cup", "oc_titolo_progetto", "oc_finanz_tot_pub_netto", "tot_pagamenti", "oc_stato_progetto")}
    det_corto = {k: es_det[k] for k in ("cod_locale_progetto", "cup", "oc_titolo_progetto", "oc_finanz_tot_pub_netto", "tot_pagamenti", "oc_stato_progetto", "oc_data_inizio_progetto", "oc_data_fine_progetto_effettiva")}
    B = "https://opencoesione.gov.it/it/api"
    u2 = B + "/progetti/?format=json&territorio=arezzo-comune&page_size=2"
    c = f"""<h1>Tutorial: open data</h1>
<p class="lead">A guide for those starting from zero. Every example was really run on the data of Arezzo; the numbers you see are the real ones. The data fields and project titles are in Italian, as in the source.</p>
<p><a class="btn pri" href="costruisci/" style="text-decoration:none">Build a basic version of this website, step by step</a></p>
<p class="data">Examples run on data updated to {DATA_ISO}</p>
<nav aria-label="Index" class="small"><a href="#cosa">1. What they are</a> · <a href="#dove">2. Where to find them</a> · <a href="#licenze">3. Licences</a> · <a href="#api">4. What an API is</a> · <a href="#json">5. Reading JSON</a> · <a href="#param">6. Parameters</a> · <a href="#pagine">7. Pagination</a> · <a href="#csv">8. CSV in a spreadsheet</a> · <a href="#soldi">9. Funded and paid</a> · <a href="#verifica">10. Checking a figure</a> · <a href="#python">11. Python (optional)</a></nav>

<h2 id="cosa">1. What open data are</h2>
<p><strong>Open data</strong> are public information that anyone can download, check and reuse, in a format a computer can read. An example: the list of projects funded with public money, with amounts and dates. Open means you do not need to ask permission and you do not pay.</p>
<h2 id="dove">2. Where to find them</h2>
<p>Every public administration can publish them. Some starting points: <a href="https://www.dati.gov.it/">dati.gov.it</a> (the Italian national catalogue) and <a href="https://opencoesione.gov.it/it/opendata/">OpenCoesione</a>, the source of this site. OpenCoesione offers two ways: whole files to download (for example the list of all projects, in a compressed archive) and an <strong>API</strong>, a service to ask only for the data you need.</p>
<h2 id="licenze">3. Licences</h2>
<p>Open data come with a licence that says what you may do with them. OpenCoesione data use the <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a> licence (Creative Commons Attribution): you can copy and modify them, even for commercial use, as long as you <strong>credit the source</strong>. For example: «Source: OpenCoesione, data updated to {DATA_ISO}».</p>
<h2 id="api">4. What an API is, with a real example</h2>
<p>An <strong>API</strong> (application programming interface) is a web address that, instead of a page to read, returns data. You need to install nothing: the browser is enough. Open this address:</p>
<pre><code>{B}/</code></pre>
<p><a class="btn" href="{B}/">Open in the browser</a></p>
<p>You will see a list of «sections» of the database. This is the answer we got:</p>
<pre><code>{esc(tronca(es_idx))}</code></pre>
<p>Each entry is another address. We will use <code>progetti</code> (projects).</p>
<h2 id="json">5. Reading JSON</h2>
<p>Data arrive in <strong>JSON</strong> format: text with «name: value» pairs between curly brackets. Open the address below (it asks for the projects of the Municipality of Arezzo, only two of them):</p>
<pre><code>{u2}</code></pre>
<p><a class="btn" href="{u2}">Open in the browser</a></p>
<p>The number <code>count</code> is the total of projects found: <strong>{es_due['count']}</strong>. The first result, reduced to the main fields, is:</p>
<pre><code>{esc(tronca(esempio_corto))}</code></pre>
<p>Read it like this: <code>oc_finanz_tot_pub_netto</code> is the <em>funded</em> amount, <code>tot_pagamenti</code> is the <em>paid</em> amount, <code>oc_stato_progetto</code> is the status. Amounts use a comma as decimal separator and are written as text.</p>
<h2 id="param">6. Parameters: ask only for what you need</h2>
<p>After the question mark come the <strong>parameters</strong>, separated by <code>&amp;</code>:</p>
<ul><li><code>format=json</code>: the format of the answer;</li><li><code>territorio=arezzo-comune</code>: the municipality;</li><li><code>page_size=2</code>: how many results at a time;</li><li><code>stato=in_corso</code>: only ongoing projects.</li></ul>
<p>Adding <code>stato=in_corso</code> the total becomes <strong>{es_corso['count']}</strong>:</p>
<pre><code>{B}/progetti/?format=json&amp;territorio=arezzo-comune&amp;stato=in_corso&amp;page_size=1</code></pre>
<p><a class="btn" href="{B}/progetti/?format=json&amp;territorio=arezzo-comune&amp;stato=in_corso&amp;page_size=1">Open in the browser</a></p>
<h2 id="pagine">7. Pagination</h2>
<p>With thousands of results the API delivers them in groups, the <strong>pages</strong>. In the answer you find <code>current_page</code> (current page: {es_due['current_page']}), <code>last_page</code> (last: {es_due['last_page']}) and <code>next</code>, the address of the next page. To go to page 2 add <code>page=2</code>:</p>
<pre><code>{u2}&amp;page=2</code></pre>
<p><a class="btn" href="{u2}&amp;page=2">Open in the browser</a></p>
<p>The first project on page 2 is «<span lang="it">{esc(frase(es_p2['results'][0]['oc_titolo_progetto']))}</span>». To download everything you keep going until <code>next</code> is empty, waiting a second between requests so as not to overload the service.</p>
<h2 id="csv">8. CSV in a spreadsheet</h2>
<p>A <strong>CSV</strong> is a table in a text file, with columns separated by commas. It opens with Excel, LibreOffice or Google Sheets. The OpenCoesione API answers only in JSON, so we converted this site's projects to CSV ourselves: <a href="../../dati/progetti-arezzo.csv" download>download progetti-arezzo.csv</a> ({n_perim} rows; column names and values are in Italian). For the whole files, already in CSV, see the <a href="https://opencoesione.gov.it/it/opendata/">OpenCoesione downloads page</a>.</p>
<ol><li>Download the file.</li><li>In LibreOffice: «File → Open», choose the file, in the import window keep «Unicode (UTF-8)» and separator «Comma». In Excel: «Data → From Text/CSV». In Google Sheets: «File → Import → Upload».</li><li>To filter: select the header row and turn on the autofilter (the «Data» menu). Choose for example <code>stato</code> equal to «In corso».</li><li>To sum: select the <code>finanziato_euro</code> column and read the sum at the bottom. Do the same with <code>pagato_euro</code>: they are two different totals.</li></ol>
<h2 id="soldi">9. Funded amount and payments</h2>
<p>The <strong>funded</strong> amount is the sum assigned to the project; the <strong>paid</strong> amount is what was actually paid out. In the project «<span lang="it">{esc(frase(es_det['oc_titolo_progetto']))}</span>» (CUP {esc(es_det['cup'])}) the funded amount is {eur(num(es_det['oc_finanz_tot_pub_netto']))} and the paid amount is {eur(num(es_det['tot_pagamenti']))}. In other projects the two figures differ: that is why the site never adds them together or mixes them up.</p>
<h2>Looking up a CUP</h2>
<p>The <strong>CUP</strong> (Codice Unico di Progetto, Unique Project Code) is the «tax code» of a public project: it identifies the same project in different databases. Every project page of this site shows it, and in the <a href="../dati/">Full data</a> table you can type a CUP in the «Search» field.</p>
<h2 id="verifica">10. How to check a figure</h2>
<ol><li>Open the project page on this site.</li><li>Press «Official page on OpenCoesione» and compare amounts and status.</li><li>Press «See where this data comes from»: it is the API's JSON. Look for <code>oc_finanz_tot_pub_netto</code> and <code>tot_pagamenti</code>.</li></ol>
<p>Detail of one project, reduced to the main fields ({esc(es_due['results'][0]['url'])}):</p>
<pre><code>{esc(tronca(det_corto))}</code></pre>
<p>Dates are written as year, month, day without separators: <code>20220629</code> means 2022-06-29.</p>
<h2 id="python">11. First steps with Python (optional)</h2>
<p>If you want to automate, here is a program of a few lines that uses only Python's standard library (install it from <a href="https://www.python.org/">python.org</a>). Save it as <code>projects.py</code> and run it with <code>python projects.py</code>:</p>
<pre><code>import json, urllib.request

url = "{u2}"
with urllib.request.urlopen(url) as response:
    data = json.load(response)

print("Projects found:", data["count"])
for p in data["results"]:
    print(p["cup"], p["oc_stato_progetto"], p["oc_finanz_tot_pub_netto"], p["tot_pagamenti"])</code></pre>
<p>Result obtained by running it:</p>
<pre><code>Projects found: {es_due['count']}
{chr(10).join(f"{p['cup']} {p['oc_stato_progetto']} {p['oc_finanz_tot_pub_netto']} {p['tot_pagamenti']}" for p in es_due['results'])}</code></pre>
<p class="small mu">When you download many pages, wait at least a second between requests and save the answers on your computer so as not to repeat them.</p>"""
    pagina("guida/index.html", "Tutorial: open data", c, "guida", profondita=1)

# ------------------------------------------------------------------ parte didattica: costruisci una versione base
def costruisci():
    en = LANG == "en"
    src = open(os.path.join(ROOT, "esempi", "mini-site.py" if en else "mini-sito.py"), encoding="utf-8").read()
    esito = open(os.path.join(ROOT, "dati", "esito_mini_sito_en.txt" if en else "esito_mini_sito_it.txt"), encoding="utf-8").read().strip()
    nome = "mini-site.py" if en else "mini-sito.py"
    out = os.path.join(SITE, "en" if en else "", "guida", "costruisci"); os.makedirs(out, exist_ok=True)
    open(os.path.join(out, nome), "w", encoding="utf-8").write(src)
    if en:
        c = f"""<p><a href="../">← Tutorial</a></p>
<h1>Build a basic version of this website, step by step</h1>
<p class="lead">In about fifteen minutes you build a small web page that downloads the projects of a municipality from OpenCoesione, adds up funded and paid amounts and lists the largest ongoing projects. It is a rough, working version of this site, not a copy of it.</p>
<p class="small mu">Project titles are in Italian, as in the source. We really ran every step below from an empty folder; the result is declared at the end.</p>
<h2>What you will get</h2>
<p>One page, <code>site/index.html</code>, with: total funded and total paid for all projects of the municipality (shown separately), the 15 largest ongoing projects, the source with its licence and the download date.</p>
<h2>What you need</h2>
<ul><li>Python 3 (version 3.8 or newer; we used 3.12). Check with <code>python3 --version</code> (on Windows: <code>python --version</code>). If it is missing, install it from <a href="https://www.python.org/">python.org</a>.</li><li>A terminal (Terminal on Mac and Linux, PowerShell on Windows) and a web browser.</li><li>An internet connection. Nothing else to install: the program uses only Python's standard library.</li></ul>
<h2>Step 1. Create an empty folder</h2>
<pre><code>mkdir mini-site
cd mini-site</code></pre>
<h2>Step 2. Save the program</h2>
<p>Create a file called <code>build.py</code> in that folder and paste the code below, or <a href="{nome}" download>download it</a> and rename it. Read it first: the comments explain each part.</p>
<pre><code>{esc(src)}</code></pre>
<h2>Step 3. Run it</h2>
<pre><code>python3 build.py</code></pre>
<p>The program downloads 26 pages of 500 projects, waiting a second between requests, and it keeps every page in the <code>cache</code> folder: if it stops, run it again and it resumes. It takes about three minutes. This is what we obtained:</p>
<pre><code>{esc(esito.splitlines()[0])}
{esc(esito.splitlines()[1])}
{esc(esito.splitlines()[2])}</code></pre>
<h2>Step 4. Look at the result</h2>
<pre><code>python3 -m http.server 8000 --directory site</code></pre>
<p>Open <code>http://localhost:8000</code> in the browser. To stop the server press Ctrl+C. The two big figures are the same ones you can read on the <a href="../../">home page</a> for all 12,590 projects of Arezzo (the home page counts a narrower perimeter, explained in <a href="../../metodo/">Method and sources</a>).</p>
<h2>How it works, in four parts</h2>
<ol><li><strong>Download with a pause and a memory</strong>: <code>download()</code> asks one page at a time, waits a second, waits longer and retries if the service answers 429 («too many requests»), and saves each answer in <code>cache</code>.</li><li><strong>Pagination</strong>: the loop continues until <code>last_page</code>, as explained in the <a href="../#pagine">tutorial</a>.</li><li><strong>Sums</strong>: amounts are text with a comma, so <code>euro()</code> turns <code>"51817680,65"</code> into a number. Funded and paid are summed separately.</li><li><strong>The page</strong>: a text template with the figures and a table; <code>html.escape</code> protects the page from special characters in titles.</li></ol>
<h2>Next steps</h2>
<ul><li>Change <code>COMUNE</code> to another municipality: the codes are listed in the API's <a href="https://opencoesione.gov.it/it/api/territori/">territories section</a>.</li><li>Add a column with the status, or a link to each project's official page (<code>oc_link</code> field).</li><li>Publish: the <code>site</code> folder is a normal static website; copy it to any static hosting.</li><li>Look at how this full site is built: the code is in the project repository and the pages are generated by a script.</li></ul>
<h2>Outcome of our test</h2>
<p>Run on 2 November 2026 from an empty folder, with Python 3.12.3 on Linux, following exactly the steps above. The <strong>first attempt failed</strong>: the service answered 429 partway through the download, because the one-second pause was not enough. We added the wait-and-retry you see in the code, repeated the test from an empty folder and it completed in 3 minutes 32 seconds (English version: 2 minutes 32 seconds). The totals match the full list of the Arezzo projects used by this site. After the test we wrapped the table in a scrolling container because on a phone (390 px) it ran off the screen; we rechecked it by re-running the program with the already downloaded cache. Not tested: Windows and macOS, other Python versions, other municipalities.</p>"""
        titolo = "Build a basic version of this website"
    else:
        c = f"""<p><a href="../">← Tutorial</a></p>
<h1>Costruisci una versione base di questo sito, passo passo</h1>
<p class="lead">In un quarto d'ora crei una piccola pagina web che scarica da OpenCoesione i progetti di un Comune, somma finanziato e pagato e elenca i progetti in corso più grandi. È una versione di massima ma funzionante di questo sito, non una copia.</p>
<p class="small mu">Ogni passo qui sotto è stato eseguito davvero partendo da una cartella vuota; l'esito è dichiarato in fondo.</p>
<h2>Cosa ottieni</h2>
<p>Una pagina, <code>sito/index.html</code>, con: totale finanziato e totale pagato di tutti i progetti del Comune (separati), i 15 progetti in corso più grandi, la fonte con la licenza e la data di scarico.</p>
<h2>Cosa ti serve</h2>
<ul><li>Python 3 (versione 3.8 o successiva; noi abbiamo usato la 3.12). Controlla con <code>python3 --version</code> (su Windows: <code>python --version</code>). Se manca, installalo da <a href="https://www.python.org/">python.org</a>.</li><li>Un terminale (Terminale su Mac e Linux, PowerShell su Windows) e un browser.</li><li>Una connessione a internet. Non devi installare altro: il programma usa solo la libreria standard di Python.</li></ul>
<h2>Passo 1. Crea una cartella vuota</h2>
<pre><code>mkdir mini-sito
cd mini-sito</code></pre>
<h2>Passo 2. Salva il programma</h2>
<p>Crea in quella cartella un file chiamato <code>costruisci.py</code> e incolla il codice qui sotto, oppure <a href="{nome}" download>scaricalo</a> e rinominalo. Leggilo prima: i commenti spiegano ogni parte.</p>
<pre><code>{esc(src)}</code></pre>
<h2>Passo 3. Eseguilo</h2>
<pre><code>python3 costruisci.py</code></pre>
<p>Il programma scarica 26 pagine da 500 progetti, aspettando un secondo tra una richiesta e l'altra, e conserva ogni pagina nella cartella <code>cache</code>: se si ferma, rilancialo e riparte da dove era arrivato. Richiede circa tre minuti. Ecco cosa abbiamo ottenuto:</p>
<pre><code>{esc(esito.splitlines()[0])}
{esc(esito.splitlines()[1])}
{esc(esito.splitlines()[2])}</code></pre>
<h2>Passo 4. Guarda il risultato</h2>
<pre><code>python3 -m http.server 8000 --directory sito</code></pre>
<p>Apri <code>http://localhost:8000</code> nel browser. Per fermare il server premi Ctrl+C. Le due cifre grandi sono quelle della <a href="../../">prima pagina</a> riferite a tutti i 12.590 progetti di Arezzo (la prima pagina conta un perimetro più ristretto, spiegato nel <a href="../../metodo/">Metodo e fonti</a>).</p>
<h2>Come funziona, in quattro parti</h2>
<ol><li><strong>Scarico con pausa e memoria</strong>: <code>scarica()</code> chiede una pagina per volta, aspetta un secondo, aspetta di più e riprova se il servizio risponde 429 («troppe richieste»), e salva ogni risposta in <code>cache</code>.</li><li><strong>Paginazione</strong>: il ciclo continua fino a <code>last_page</code>, come spiegato nel <a href="../#pagine">tutorial</a>.</li><li><strong>Somme</strong>: gli importi sono testo con la virgola, quindi <code>euro()</code> trasforma <code>"51817680,65"</code> in un numero. Finanziato e pagato sono sommati separatamente.</li><li><strong>La pagina</strong>: un modello di testo con le cifre e una tabella; <code>html.escape</code> protegge la pagina dai caratteri speciali nei titoli.</li></ol>
<h2>E poi</h2>
<ul><li>Cambia <code>COMUNE</code> con un altro Comune: i codici sono nella <a href="https://opencoesione.gov.it/it/api/territori/">sezione territori</a> della API.</li><li>Aggiungi una colonna con lo stato o un link alla scheda ufficiale di ogni progetto (campo <code>oc_link</code>).</li><li>Pubblica: la cartella <code>sito</code> è un normale sito statico; copiala su un qualsiasi servizio di hosting statico.</li><li>Guarda come è fatto questo sito completo: il codice è nel repository del progetto e le pagine sono generate da uno script.</li></ul>
<h2>Esito della nostra prova</h2>
<p>Eseguito il 2 novembre 2026 da una cartella vuota, con Python 3.12.3 su Linux, seguendo esattamente i passi qui sopra. Il <strong>primo tentativo è fallito</strong>: il servizio ha risposto 429 a metà scarico, perché la pausa di un secondo non bastava. Abbiamo aggiunto l'attesa con nuovi tentativi che vedi nel codice, ripetuto la prova da una cartella vuota ed è arrivata in fondo in 3 minuti e 32 secondi. I totali coincidono con quelli della lista completa dei progetti di Arezzo usata da questo sito. Dopo la prova abbiamo avvolto la tabella in un contenitore scorrevole perché sul telefono (390 px) usciva dallo schermo; l'abbiamo ricontrollato rilanciando il programma con la cache già scaricata. Non provato: Windows e macOS, altre versioni di Python, altri Comuni.</p>"""
        titolo = "Costruisci una versione base del sito"
    pagina("guida/costruisci/index.html", titolo, c, "coding", profondita=2)

# ------------------------------------------------------------------ robots, sitemap, main
def varie():
    base = ["", "opere/", "dati/", "guida/", "guida/costruisci/", "metodo/"] + [f"progetti/{slug(d)}.html" for d in perim]
    urls = base + ["en/" + u for u in base]
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"<url><loc>{SITO}/{u}</loc></url>\n" for u in urls) + "</urlset>\n"
    open(os.path.join(SITE, "sitemap.xml"), "w").write(sm)
    open(os.path.join(SITE, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {SITO}/sitemap.xml\n")

if __name__ == "__main__":
    import shutil
    shutil.rmtree(SITE, ignore_errors=True)
    os.makedirs(SITE)
    open(os.path.join(SITE, "stile.css"), "w").write(CSS)
    for LANG in ("it", "en"):
        home(); elenco(); dati_completi()
        (metodo_en if LANG == "en" else metodo)()
        (guida_en if LANG == "en" else guida)()
        costruisci()
        for d in perim:
            scheda(d)
    LANG = "it"
    varie()
    # report per l'aggiornamento: titoli ancora ufficiali tra i progetti che dovrebbero averlo semplice
    prior = [d for d in perim if d["oc_stato_progetto"] in ("In corso", "Non avviato") or is_opera(d)]
    senza = [d["cod_locale_progetto"] for d in prior if d["cod_locale_progetto"] not in semplici]
    json.dump({"data_dati": DATA_DATI, "n_lista": n_lista, "n_perimetro": n_perim, "finanziato": round(tot_fin), "pagato": round(tot_pag),
               "titoli_semplici": len(prior) - len(senza), "titoli_ufficiali_da_semplificare": len(senza), "codici_da_semplificare": senza},
              open(os.path.join(SITE, "..", "report.json") if os.environ.get("OC_SITE") else os.path.join(ROOT, "dati", "report.json"), "w"), ensure_ascii=False, indent=1)
    print("progetti dettagliati:", len(tutti), "perimetro:", n_perim, "finanziato", eur(tot_fin), "pagato", eur(tot_pag))
