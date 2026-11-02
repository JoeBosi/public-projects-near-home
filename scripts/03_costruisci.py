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

def eur(x):
    return f"{round(x):,}".replace(",", ".") + " €"

def data(s):
    return f"{s[6:8]}/{s[4:6]}/{s[:4]}" if s and len(s) == 8 else "dato non disponibile"

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
    return "; ".join(frase(x) if x.isupper() else x for x in e) if e else "dato non disponibile"

# ------------------------------------------------------------------ layout
CSS = """
:root{--bg:#fff;--tx:#1b2330;--mu:#566074;--ac:#0b5cab;--l:#d9e0ea;--sf:#f4f7fb;--ok:#2f7d4f}
*{box-sizing:border-box}body{margin:0;font:18px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--tx);background:var(--bg)}
main p,main li,main dd,main h1,main h2,main h3{overflow-wrap:anywhere}
a{color:var(--ac)}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #f2a900;outline-offset:2px}
.w{max-width:960px;margin:0 auto;padding:0 16px}
header.top{border-bottom:1px solid var(--l);background:var(--sf)}
header.top .w.nav{display:flex;flex-wrap:wrap;gap:8px 24px;align-items:center;padding:10px 16px}header.top .fonte{background:#0b3d6e;color:#fff;font-size:.88rem;padding:5px 0}header.top .fonte a{color:#fff}
header.top b{font-size:1.05rem}nav{display:flex;flex:1 1 auto;flex-wrap:wrap;gap:4px 18px}nav a{text-decoration:none;padding:4px 0}nav a.tut{margin-left:auto;color:#000;font-weight:600}nav a.on{border-bottom:3px solid var(--ac);font-weight:600}
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

.hero{background:var(--sf);border:1px solid var(--l);border-radius:14px;padding:18px 18px 14px;margin:1rem 0 1.4rem}
.hero h1{margin-top:0}.cerca{display:flex;flex-wrap:wrap;gap:8px;margin:.8rem 0}.cerca input{flex:1 1 240px;font:inherit;padding:12px;border:2px solid var(--ac);border-radius:10px}
.cerca button,.btn.pri{font:inherit;background:var(--ac);color:#fff;border:2px solid var(--ac);border-radius:10px;padding:12px 18px;cursor:pointer;font-weight:600}
.passi{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin:.6rem 0 0}
.passi a{display:block;border:1px solid var(--l);background:#fff;border-radius:10px;padding:10px 14px;text-decoration:none;color:var(--tx)}.passi a strong{display:block;color:var(--ac)}
.vuoto{border:1px dashed var(--mu);border-radius:10px;padding:14px;margin:.8rem 0;background:var(--sf)}
.stati{display:flex;flex-wrap:wrap;gap:8px;margin:.4rem 0 1rem}.stati .tag{font-size:.95rem;padding:2px 10px}
.tag.st{background:#e6f0fb;border-color:#9bbfe6;font-weight:600}
footer{border-top:1px solid var(--l);background:var(--sf);margin-top:3rem;padding:18px 0;font-size:.92rem}
@media(max-width:600px){body{font-size:17px}h1{font-size:1.65rem}dl.sch{grid-template-columns:1fr}dl.sch dt{margin-top:6px}}
"""

def pagina(percorso, titolo, corpo, attiva="", descr="", profondita=0):
    rel = "../" * profondita
    nav = [("", "Per cominciare", "home"), ("opere/", "Opere e progetti", "opere"), ("dati/", "Dati completi", "dati"),
           ("metodo/", "Metodo e fonti", "metodo"), ("guida/", "Tutorial", "guida")]
    n = "".join(f'<a href="{rel}{h}" class="{"on " if k == attiva else ""}{"tut" if k == "guida" else ""}"{" aria-current=page" if k == attiva else ""}>{t}</a>' for h, t, k in nav)
    doc = f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(titolo)} | Progetti pubblici sotto casa</title>
<meta name="description" content="{esc(descr or 'I progetti finanziati con fondi pubblici di coesione nel Comune di Arezzo, spiegati in modo semplice, con i dati ufficiali di OpenCoesione.')}">
<link rel="stylesheet" href="{rel}stile.css"></head><body>
<header class="top"><div class="fonte"><div class="w">Fonte: <a href="https://opencoesione.gov.it/">OpenCoesione</a> · ultimo aggiornamento dei dati: <strong>{DATA_DATI}</strong></div></div><div class="w nav"><b><a href="{rel}" style="text-decoration:none;color:inherit">Progetti pubblici sotto casa</a></b><nav aria-label="Principale">{n}</nav></div></header>
<main class="w">{corpo}</main>
<footer><div class="w"><p>I dati provengono da <a href="https://opencoesione.gov.it/">OpenCoesione</a> (licenza <a href="https://creativecommons.org/licenses/by/4.0/deed.it">CC BY 4.0</a>) e possono non riflettere lo stato reale: sono quelli comunicati dagli enti. Per segnalare un errore scrivi a <a href="mailto:info@giuseppebosi.com">info@giuseppebosi.com</a>. Dati aggiornati al {DATA_DATI}.</p>
<p>A cura del Prof. Giuseppe Bosi, Scienze e Tecnologie Informatiche — <a href="https://www.giuseppebosi.com">www.giuseppebosi.com</a></p></div></footer>
</body></html>"""
    p = os.path.join(SITE, percorso)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(doc)

def avviso():
    return ('<p class="avv"><strong>Limite.</strong> I dati dicono quanti soldi sono assegnati e pagati, non come è stata fatta l\'opera. Possono non riflettere lo stato reale.</p>')

URLMAP = {}

def apiurl(d):
    return URLMAP.get(d["cod_locale_progetto"]) or f"{api.BASE}/progetti/{d['cod_locale_progetto'].lower()}/?format=json"

def slug(d):
    return re.sub(r"[^a-z0-9_-]+", "-", d["cod_locale_progetto"].lower()).strip("-")

# ------------------------------------------------------------------ dati
tutti = carica()
_m = max(d.get('data_aggiornamento') or '' for d in tutti)
DATA_DATI = f'{_m[6:8]}/{_m[4:6]}/{_m[0:4]}'  # dalla API, non scritta a mano
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
    extra.append(f'<span class="tag">{esc(tema_s(d))}</span> <span class="tag">{esc(natura(d))}</span> <span class="tag">{esc(d["oc_stato_progetto"])}</span>')
    pv = prevista(d)
    if pv:
        extra.append(f"Fine prevista: {pv}" + (" (scadenza superata secondo i dati)" if superata(d) else ""))
    return (f'<li><a href="{{R}}progetti/{slug(d)}.html">{esc(titolo_vis(d))}</a><br>'
            f'<span class="mu">{esc(ente_str(d))}</span><br>Finanziato: <strong>{eur(fin(d))}</strong> · Già pagato: <strong>{eur(pag(d))}</strong><br>'
            f'<span class="small">{" · ".join(extra)}</span></li>')

# ------------------------------------------------------------------ home
def home():
    per_tema = collections.defaultdict(lambda: [0, 0, 0])
    per_tema_op = collections.defaultdict(lambda: [0, 0, 0])
    for d in perim:
        t = per_tema_op if is_opera(d) else per_tema
        t[tema_s(d)][0] += fin(d); t[tema_s(d)][1] += pag(d); t[tema_s(d)][2] += 1
    def blocco(dic, titolo, nota):
        if not dic: return ""
        mx = max(v[0] for v in dic.values()) or 1
        righe = "".join(
            f'<div class="riga"><strong>{esc(k)}</strong> <span class="mu small">({pl(v[2], "progetto", "progetti")})</span><br>'
            f'<div class="bar" role="img" aria-label="Finanziato {eur(v[0])}"><i style="width:{max(1,v[0]/mx*100):.1f}%"></i></div>'
            f'<div class="bar" style="margin-top:3px" role="img" aria-label="Pagato {eur(v[1])}"><i class="p" style="width:{max(0.5,v[1]/mx*100) if v[1] else 0:.1f}%"></i></div>'
            f'<span class="small">Finanziato {eur(v[0])} · Già pagato {eur(v[1])}</span></div>'
            for k, v in sorted(dic.items(), key=lambda kv: -kv[1][0]))
        return f"<h3>{titolo}</h3><p class='mu small'>{nota}</p>{righe}"
    op_n = sum(v[2] for v in per_tema_op.values())
    ent = collections.defaultdict(lambda: [0, 0, 0])
    for d in perim:
        for e in set(enti(d)):
            ent[e][0] += fin(d); ent[e][1] += pag(d); ent[e][2] += 1
    top_ent = sorted(ent.items(), key=lambda kv: -kv[1][0])[:8]
    ent_html = "".join(f'<li><strong>{esc(frase(k) if k.isupper() else k)}</strong><br>{pl(v[2], 'progetto', 'progetti')} · finanziato {eur(v[0])} · già pagato {eur(v[1])}</li>' for k, v in top_ent)
    corso_html = "".join(riga_progetto(d).replace("{R}", "") for d in corso[:10])
    ope = [d for d in perim if is_opera(d)]
    c = f"""
<div class="hero"><h1>Quali progetti pubblici riguardano Arezzo?</h1>
<p class="lead">Qui trovi i progetti del Comune di Arezzo finanziati con i fondi di coesione (risorse europee e nazionali per ridurre le differenze tra territori), con importi e stato presi dai dati ufficiali.</p>
<form class="cerca" action="dati/" method="get" role="search"><input name="q" type="search" aria-label="Cerca un progetto" placeholder="Cerca: scuola, ponte, museo"><button type="submit">Cerca</button></form>
<div class="passi"><a href="opere/#corso"><strong>Cosa si sta facendo adesso</strong>Progetti in corso, dal più grande</a><a href="opere/"><strong>Opere e progetti</strong>Tutto l'elenco, in parole semplici</a><a href="dati/"><strong>Tabella e file CSV</strong>Per filtrare e scaricare i dati</a></div></div>
<p class="avv"><strong>Limite.</strong> I dati dicono quanti soldi sono assegnati e pagati, non come è stata fatta l'opera. Possono non riflettere lo stato reale.</p>

<h2>1. Quanti soldi riguardano i progetti principali di Arezzo?</h2>
<p>Contiamo <strong>{pl(n_perim, 'progetto', 'progetti')}</strong>: tutti quelli in corso o non ancora avviati e quelli conclusi dal 2016 che sono opere o valgono almeno 100.000 €. Le due cifre sono diverse: la prima è la somma <em>assegnata</em>, la seconda quella <em>già pagata</em>.</p>
<div class="cards">
<div class="card fin"><div class="n">{eur(tot_fin)}</div><div><strong>Finanziato</strong>: soldi pubblici assegnati.</div></div>
<div class="card pag"><div class="n">{eur(tot_pag)}</div><div><strong>Già pagato</strong>: soldi usciti davvero, secondo i dati.</div></div>
</div>
<p><strong>Cosa non è contato.</strong> Nei dati di Arezzo ci sono altri {format(n_fuori, ",").replace(",", ".")} progetti, per {eur(fuori_fin)} finanziati e {eur(fuori_pag)} già pagati: per lo più piccoli progetti già conclusi (corsi, contributi alle persone), oppure conclusi prima del 2016 o senza data di fine. Con tutti i progetti insieme il totale sarebbe {eur(tot_lista)} finanziati e {eur(tot_lista_pag)} già pagati. Dettagli nel <a href="metodo/">Metodo e fonti</a>.</p>

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
<p>Tutti i numeri qui sopra vengono dalla banca dati pubblica OpenCoesione. Nella <a href="guida/">Guida agli open data</a> impari a leggerli e a scaricarli da solo. Nella pagina <a href="dati/">Dati completi</a> trovi tutte le colonne e il file da aprire in un foglio di calcolo.</p>
"""
    pagina("index.html", "Quali progetti pubblici riguardano Arezzo?", c, "home")

# ------------------------------------------------------------------ elenco opere
def elenco():
    os.makedirs(os.path.join(SITE, "opere"), exist_ok=True)
    def sez(titolo, lst, ident):
        return f'<h2 id="{ident}">{titolo} ({len(lst)})</h2><ul class="lista">' + "".join(riga_progetto(d).replace("{R}", "../") for d in lst) + "</ul>"
    ope = sorted([d for d in perim if is_opera(d)], key=fin, reverse=True)
    altri_c = [d for d in corso if not is_opera(d)]
    c = f"""<h1>Opere e progetti</h1>
<p class="lead">Le opere e gli acquisti sono elencati per primi; poi gli altri progetti in corso o non ancora avviati. I progetti conclusi dal 2016 che non sono opere si trovano in <a href="../dati/">Dati completi</a>.</p>
<p class="data">Dati aggiornati al {DATA_DATI}</p>{avviso()}
<p>Vai a: <a href="#opere">Opere e acquisti</a> · <a href="#corso">In corso</a> · <a href="#nonav">Non ancora avviati</a></p>
<div class="filtri"><label>Cerca in questa pagina <input id="qo" type="search" placeholder="per esempio scuola, ponte, museo"></label><span id="conto" class="mu" aria-live="polite"></span></div>
<div id="vuotoo" class="vuoto" hidden>Nessun progetto contiene questa parola. Prova con una parola più corta o cancella la ricerca. Per cercare tra tutti i progetti usa <a href="../dati/">Dati completi</a>.</div>
{sez("Opere e acquisti di beni", ope, "opere")}
{sez("Altri progetti in corso", altri_c, "corso")}
{sez("Progetti non ancora avviati", nonav, "nonav")}
<script src="filtro.js"></script>"""
    open(os.path.join(SITE, "opere", "filtro.js"), "w").write("""(function(){var q=document.getElementById('qo'),c=document.getElementById('conto'),v=document.getElementById('vuotoo');
var li=[].slice.call(document.querySelectorAll('ul.lista li'));
function f(){var x=q.value.toLowerCase().trim(),n=0;li.forEach(function(e){var ok=!x||e.textContent.toLowerCase().indexOf(x)>-1;e.hidden=!ok;if(ok)n++});
document.querySelectorAll('h2[id]').forEach(function(h){var u=h.nextElementSibling;h.hidden=!!x&&!u.querySelector('li:not([hidden])')});
v.hidden=n>0;c.textContent=x?(n+(n==1?' progetto trovato':' progetti trovati')):''}
q.oninput=f;f()})();""")
    pagina("opere/index.html", "Opere e progetti", c, "opere", profondita=1)

# ------------------------------------------------------------------ scheda
def scheda(d):
    rip = [("Unione europea", d["oc_finanz_ue_netto"]), ("Stato", num(d["oc_finanz_stato_fsc_netto"]) + num(d["oc_finanz_stato_fondo_rot_netto"]) + num(d["oc_finanz_stato_altri_prov_netto"]) + num(d["oc_finanz_stato_compl_netto"]) + num(d["oc_finanz_stato_pac_netto"])),
           ("Regione", d["oc_finanz_regione_netto"]), ("Provincia", d["oc_finanz_provincia_netto"]), ("Comune", d["oc_finanz_comune_netto"]),
           ("Altri soggetti pubblici", d["oc_finanz_altro_pubblico_netto"]), ("Privati", d["oc_finanz_privato_netto"])]
    rip = [(k, num(v)) for k, v in rip if num(v) > 0]
    ripd = "".join(f"<li>{k}: {eur(v)}</li>" for k, v in rip) or "<li>dato non disponibile</li>"
    fasi = "".join(
        f"<tr><td>{esc(f['oc_descr_fase'])}</td><td>{data(f.get('data_inizio_prevista'))}</td><td>{data(f.get('data_inizio_effettiva'))}</td><td>{data(f.get('data_fine_prevista'))}</td><td>{data(f.get('data_fine_effettiva'))}</td></tr>"
        for f in d.get("fasi_procedurali", []))
    fasi_t = f'<h2>Fasi dichiarate</h2><div class="sc"><table><tr><th>Fase</th><th>Inizio previsto</th><th>Inizio effettivo</th><th>Fine prevista</th><th>Fine effettiva</th></tr>{fasi}</table></div>' if fasi else ""
    s = semplici.get(d["cod_locale_progetto"])
    if s and s["titolo"].strip() == (d["oc_titolo_progetto"] or "").strip():
        s = None
    orig = (f'<p class="small mu">Titolo riscritto in italiano semplice a partire dal titolo e dalla sintesi ufficiali. Titolo originale: «{esc(d["oc_titolo_progetto"])}»</p>' if s
            else "")
    sint = d.get("oc_sintesi_progetto") or ""
    sint_h = f"<h2>Descrizione ufficiale</h2><p>{esc(sint)}</p>" if sint and sint != d["oc_titolo_progetto"] else ""
    perc = f"{pag(d)/fin(d)*100:.0f}%" if fin(d) > 0 else "dato non disponibile"
    note = ""
    if superata(d):
        note = f'<p class="avv">La data di fine prevista ({prevista(d)}) è precedente alla data dei dati: scadenza superata secondo i dati.</p>'
    c = f"""<p><a href="../opere/">← Opere e progetti</a></p>
<h1>{esc(titolo_vis(d))}</h1>{orig}
<div class="stati"><span class="tag st">{esc(d['oc_stato_progetto'])}</span><span class="tag">{esc(tema_s(d))}</span><span class="tag">{esc(natura(d))}</span></div>
<p class="lead">{esc(ente_str(d))}: {eur(fin(d))} finanziati, {eur(pag(d))} già pagati.</p>
<p class="data">Dati di questo progetto aggiornati al {data(d.get('data_aggiornamento'))}</p>{note}
<div class="cards"><div class="card fin"><div class="n">{eur(fin(d))}</div>Finanziato</div><div class="card pag"><div class="n">{eur(pag(d))}</div>Già pagato ({perc} del finanziato)</div></div>
<h2>Che cos'è</h2>
<dl class="sch"><dt>Argomento</dt><dd>{esc(tema_s(d))} <span class="small mu">(termine ufficiale: {esc(tema(d))})</span></dd><dt>Tipo</dt><dd>{esc(natura(d))}; {esc(frase(d['cup_descr_categoria']))}</dd>
<dt>Chi se ne occupa</dt><dd>{esc(ente_str(d))}</dd><dt>Stato dichiarato</dt><dd>{esc(d['oc_stato_progetto'])}{' · fase: ' + esc(d['oc_descr_fase_corrente']) if d.get('oc_descr_fase_corrente') else ''}</dd>
<dt>Inizio del progetto</dt><dd>{data(d['oc_data_inizio_progetto'])}</dd><dt>Fine prevista del progetto</dt><dd>{data(d['oc_data_fine_progetto_prevista'])}</dd><dt>Fine effettiva del progetto</dt><dd>{data(d['oc_data_fine_progetto_effettiva'])}</dd>
<dt>CUP</dt><dd>{esc(d['cup'] or 'dato non disponibile')} <span class="small mu">(Codice Unico di Progetto)</span></dd><dt>Ciclo</dt><dd>{esc(d['oc_descr_ciclo'])}</dd></dl>
<p class="small mu">«Dato non disponibile» significa che l'ente non ha comunicato quel dato alla fonte. Le date sopra sono quelle riferite all'intero progetto, comunicate dall'ente. La scheda ufficiale di OpenCoesione può mostrare invece le date di una singola fase, per esempio l'esecuzione dei lavori, che possono essere diverse: le fasi sono elencate più sotto.</p>
<h2>Da dove vengono i soldi</h2><ul>{ripd}</ul>
{sint_h}{fasi_t}
<h2>Fonte</h2>
<p><a class="btn" href="{esc(d['oc_link'])}">Scheda ufficiale su OpenCoesione</a> <a class="btn" href="{esc(apiurl(d))}">Vedi da dove vengono questi dati (JSON)</a></p>
<p class="small mu">Il link «dati» è la risposta esatta della API usata per questa pagina. Per capire come leggerla: <a href="../guida/">Guida agli open data</a>.</p>"""
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
    with open(os.path.join(SITE, "dati", "progetti-arezzo.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(campi); w.writerows(righe)
    json.dump([dict(zip(campi, r)) for r in righe], open(os.path.join(SITE, "dati", "progetti-arezzo.json"), "w", encoding="utf-8"), ensure_ascii=False)
    stati = sorted({d["oc_stato_progetto"] for d in perim})
    temi = sorted({tema(d) for d in perim})
    tr = "".join(
        f'<tr data-s="{esc(d["oc_stato_progetto"])}" data-t="{esc(tema(d))}"><td><a href="../progetti/{slug(d)}.html">{esc(titolo_vis(d))}</a></td><td>{esc(d["cup"])}</td><td>{esc(tema(d))}</td><td>{esc(d["oc_stato_progetto"])}</td>'
        f'<td data-v="{fin(d):.0f}">{eur(fin(d))}</td><td data-v="{pag(d):.0f}">{eur(pag(d))}</td><td>{data(d["oc_data_fine_progetto_prevista"])}</td><td>{data(d["oc_data_fine_progetto_effettiva"])}</td><td>{esc(ente_str(d))}</td></tr>'
        for d in sorted(perim, key=fin, reverse=True))
    c = f"""<h1>Dati completi</h1>
<p class="lead">Tutti i {pl(n_perim, 'progetto', 'progetti')} considerati, con le colonne principali. Puoi filtrare e scaricare il file da aprire in un foglio di calcolo.</p>
<p class="data">Dati aggiornati al {DATA_DATI}</p>{avviso()}
<p><a class="btn" href="progetti-arezzo.csv" download>Scarica CSV (foglio di calcolo)</a> <a class="btn" href="progetti-arezzo.json" download>Scarica JSON</a></p>
<p class="small mu">Il CSV usa il punto come separatore decimale e contiene i valori in euro senza simboli. Come aprirlo: <a href="../guida/#csv">Guida agli open data</a>.</p>
<div class="filtri"><label>Cerca <input id="q" type="search" placeholder="parola nel titolo o ente"></label>
<label>Stato <select id="fs"><option value="">Tutti</option>{''.join(f'<option>{esc(s)}</option>' for s in stati)}</select></label>
<label>Argomento <select id="ft"><option value="">Tutti</option>{''.join(f'<option>{esc(s)}</option>' for s in temi)}</select></label>
<span id="cont" class="mu" aria-live="polite"></span></div>
<div class="sc"><table id="tab"><thead><tr><th>Titolo</th><th>CUP</th><th>Argomento</th><th>Stato</th><th>Finanziato</th><th>Già pagato</th><th>Fine prevista</th><th>Fine effettiva</th><th>Ente</th></tr></thead><tbody>{tr}</tbody></table></div>
<div id="vuoto" class="vuoto" hidden>Nessun progetto corrisponde ai filtri. <button type="button" id="azzera" class="btn">Azzera i filtri</button></div>
<noscript><p>Per filtrare serve JavaScript; l'elenco è comunque completo e il CSV è scaricabile.</p></noscript>
<script src="filtri.js"></script>"""
    pagina("dati/index.html", "Dati completi", c, "dati", profondita=1)
    open(os.path.join(SITE, "dati", "filtri.js"), "w").write("""(function(){var q=document.getElementById('q'),s=document.getElementById('fs'),t=document.getElementById('ft'),c=document.getElementById('cont'),v=document.getElementById('vuoto'),z=document.getElementById('azzera');
var rows=[].slice.call(document.querySelectorAll('#tab tbody tr'));
function f(){var x=q.value.toLowerCase().trim(),n=0;rows.forEach(function(r){
var ok=(!s.value||r.dataset.s===s.value)&&(!t.value||r.dataset.t===t.value)&&(!x||r.textContent.toLowerCase().indexOf(x)>-1);r.hidden=!ok;if(ok)n++});
c.textContent=n+(n==1?' progetto mostrato':' progetti mostrati');v.hidden=n>0}
q.oninput=s.onchange=t.onchange=f;
z.onclick=function(){q.value='';s.value='';t.value='';f();q.focus()};
try{var p=new URLSearchParams(location.search);if(p.get('q'))q.value=p.get('q')}catch(e){}
f()})();""")

# ------------------------------------------------------------------ metodo
def metodo():
    fuori_c = len([r for r in lista if r["oc_stato_progetto"] == "Concluso"]) - len([d for d in tutti if d["oc_stato_progetto"] == "Concluso"])
    c = f"""<h1>Metodo e fonti</h1>
<p class="data">Dati aggiornati al {DATA_DATI}</p>
<h2>Fonte</h2>
<p>Tutti i progetti vengono dalla API pubblica di <a href="https://opencoesione.gov.it/it/api/">OpenCoesione</a>, il portale ufficiale sui progetti finanziati dalle politiche di coesione, curato con la Ragioneria Generale dello Stato. Licenza: <a href="https://creativecommons.org/licenses/by/4.0/deed.it">Creative Commons Attribuzione 4.0</a> (si può riusare citando la fonte). Data di aggiornamento dichiarata dalla API: 30/06/2026. Non usiamo altre fonti per i progetti.</p>
<h2>Che cosa abbiamo preso</h2>
<p>I progetti localizzati nel Comune di Arezzo (parametro <code>territorio=arezzo-comune</code>): {n_lista} in totale, dal ciclo di programmazione 2000-2006 in poi. Di questi mostriamo quelli del perimetro seguente.</p>
<h2>Perimetro: cosa è contato e cosa no</h2>
<p><strong>Contati ({pl(n_perim, 'progetto', 'progetti')}, {eur(tot_fin)} finanziati, {eur(tot_pag)} già pagati):</strong></p>
<ul><li>tutti i progetti con stato «In corso» o «Non avviato»;</li>
<li>i progetti «Concluso», «Liquidato» o «Non determinabile» con data di fine effettiva dal 1° gennaio 2016, ma solo se sono opere (lavori pubblici o acquisto di beni) oppure hanno un finanziamento di almeno 100.000 €. Poiché la data di fine di progetto può non coincidere con quella della scheda ufficiale (che spesso indica la fine dei lavori), il confine del 2016 va inteso «secondo il campo di progetto».</li></ul>
<p><strong>Non contati ({format(n_fuori, ",").replace(",", ".")} progetti, {eur(fuori_fin)} finanziati, {eur(fuori_pag)} già pagati):</strong></p>
<ul><li><strong>{format(non_esaminati, ",").replace(",", ".")}</strong> progetti conclusi, sotto 100.000 € e non opere (per lo più corsi, voucher e contributi individuali). Per rispettare i limiti di frequenza della API non ne abbiamo scaricato il dettaglio, quindi per loro non conosciamo la data di fine: la loro somma viene dalla lista di OpenCoesione.</li>
<li><strong>{len(senza_data)}</strong> progetti, tra quelli scaricati, conclusi senza data di fine effettiva.</li>
<li><strong>{len(prima_2016)}</strong> progetti, tra quelli scaricati, con fine effettiva prima del 2016.</li></ul>
<p>Totale di tutti i progetti di Arezzo nella banca dati: {pl(n_lista, 'progetto', 'progetti')}, {eur(tot_lista)} finanziati, {eur(tot_lista_pag)} già pagati. Contati e non contati sommano a questo totale. Per i progetti contati, i totali calcolati dalle schede di dettaglio coincidono con quelli ricavati dalla lista (controllo automatico a ogni costruzione del sito). Finanziato e pagato non sono confrontabili progetto per progetto: in alcuni casi il pagato supera il finanziato netto.</p>
<h2>Significato dei campi</h2>
<ul><li><strong>Finanziato</strong>: campo <code>oc_finanz_tot_pub_netto</code>, finanziamento pubblico totale al netto delle economie, cioè dei risparmi già tolti.</li>
<li><strong>Già pagato</strong>: campo <code>tot_pagamenti</code>, pagamenti totali registrati. Finanziato e pagato sono sempre mostrati separati e non vanno confusi: un progetto può avere pagato più o meno del finanziato.</li>
<li><strong>Stato</strong>: campo <code>oc_stato_progetto</code>, riportato esattamente come dichiarato dalla fonte (In corso, Non avviato, Concluso, Liquidato, Non determinabile).</li>
<li><strong>Date</strong>: inizio, fine prevista e fine effettiva del progetto (campi <code>oc_data_inizio_progetto</code>, <code>oc_data_fine_progetto_prevista</code>, <code>oc_data_fine_progetto_effettiva</code>) sono quelle riferite all'intero progetto, comunicate dagli enti. La scheda ufficiale su OpenCoesione mostra invece, in alto, le date dell'esecuzione dei lavori, che possono differire (controllo fatto a mano su tre progetti: pagamenti identici, date di fine diverse per questo motivo). Le date di ogni fase sono riportate nelle schede. Se una data manca, il sito scrive «dato non disponibile».</li>
<li><strong>Argomento</strong>: tema sintetico di OpenCoesione, con nomi più brevi (per esempio «Trasporti e mobilità» diventa «Strade e trasporti»).</li>
<li><strong>Opere e acquisti</strong>: progetti con natura CUP «Realizzazione di lavori pubblici» o «Acquisto di beni». Tutto il resto è «contributi, incentivi e servizi».</li></ul>
<h2>Etichette</h2>
<p>Per i progetti con stato «In corso» o «Non avviato», con data di fine prevista precedente al 30/06/2026 e senza data di fine effettiva, il sito scrive «scadenza superata secondo i dati». È un confronto tra due date della fonte, non un giudizio.</p>
<h2>Titoli riscritti</h2>
<p>Alcuni titoli, in origine tecnici o in maiuscolo, sono riscritti in italiano semplice con un assistente di intelligenza artificiale (IA), solo a partire dal titolo e dalla sintesi ufficiali e senza aggiungere informazioni. Accanto c'è sempre il titolo originale e la scritta «titolo riscritto in italiano semplice». I titoli in maiuscolo non riscritti sono mostrati con la sola iniziale maiuscola.</p>
<h2>Arrotondamenti</h2>
<p>Gli importi sono mostrati in euro interi, arrotondati; le somme sono calcolate sui valori originali e poi arrotondate, quindi la somma di cifre mostrate può differire di qualche euro. Le percentuali sono arrotondate all'intero.</p>
<h2>Limiti</h2>
<ul><li>Il sito mostra i progetti per Comune, non per indirizzo: la fonte non fornisce coordinate.</li>
<li>I progetti localizzati in più territori compaiono anche in quelli: gli importi non sono ripartiti tra i Comuni.</li>
<li>Non abbiamo un confronto con altri Comuni: richiederebbe lo stesso perimetro e dati demografici verificati.</li>
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
    c = f"""<h1>Guida agli open data</h1>
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

# ------------------------------------------------------------------ robots, sitemap, main
def varie():
    urls = ["", "opere/", "dati/", "guida/", "metodo/"] + [f"progetti/{slug(d)}.html" for d in perim]
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"<url><loc>{SITO}/{u}</loc></url>\n" for u in urls) + "</urlset>\n"
    open(os.path.join(SITE, "sitemap.xml"), "w").write(sm)
    open(os.path.join(SITE, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {SITO}/sitemap.xml\n")

if __name__ == "__main__":
    import shutil
    shutil.rmtree(SITE, ignore_errors=True)
    os.makedirs(SITE)
    open(os.path.join(SITE, "stile.css"), "w").write(CSS)
    home(); elenco(); dati_completi(); metodo(); guida(); varie()
    for d in perim:
        scheda(d)
    # report per l'aggiornamento: titoli ancora ufficiali tra i progetti che dovrebbero averlo semplice
    prior = [d for d in perim if d["oc_stato_progetto"] in ("In corso", "Non avviato") or is_opera(d)]
    senza = [d["cod_locale_progetto"] for d in prior if d["cod_locale_progetto"] not in semplici]
    json.dump({"data_dati": DATA_DATI, "n_lista": n_lista, "n_perimetro": n_perim, "finanziato": round(tot_fin), "pagato": round(tot_pag),
               "titoli_semplici": len(prior) - len(senza), "titoli_ufficiali_da_semplificare": len(senza), "codici_da_semplificare": senza},
              open(os.path.join(SITE, "..", "report.json") if os.environ.get("OC_SITE") else os.path.join(ROOT, "dati", "report.json"), "w"), ensure_ascii=False, indent=1)
    print("progetti dettagliati:", len(tutti), "perimetro:", n_perim, "finanziato", eur(tot_fin), "pagato", eur(tot_pag))
