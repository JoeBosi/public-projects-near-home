"""Controlli prima della pubblicazione. Esce con codice 1 se qualcosa non torna (il sito non va toccato).
Variabili: OC_LISTA, OC_DETTAGLI, OC_SITE (come negli altri script); OC_PREC = cartella del sito pubblicato, per il confronto."""
import csv, glob, json, os, re, sys
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
LISTA = os.environ.get("OC_LISTA") or os.path.join(R, "dati", "lista_arezzo.json")
DETT = os.environ.get("OC_DETTAGLI") or os.path.join(R, "dati", "dettagli_arezzo.json")
SITE = os.environ.get("OC_SITE") or os.path.join(R, "site")
PREC = os.environ.get("OC_PREC")
num = lambda s: float((s or "0").replace(".", "").replace(",", "."))
errori = []
def ok(c, msg):
    print(("OK    " if c else "ERRORE ") + msg)
    if not c: errori.append(msg)

L = json.load(open(LISTA)); D = {d["cod_locale_progetto"]: d for d in json.load(open(DETT))}
ok(len(L) > 10000, f"lista scaricata: {len(L)} progetti (soglia minima 10000)")
ok(len({r["cod_locale_progetto"] for r in L}) == len(L), "nessun codice duplicato nella lista")
falliti = os.path.join(os.path.dirname(DETT), "falliti.txt")
ok(not (os.path.exists(falliti) and open(falliti).read().strip()), "nessun download fallito")
ok(all(r["cod_locale_progetto"] in D for r in L if r["oc_stato_progetto"] in ("In corso", "Non avviato")), "dettaglio presente per tutti i progetti in corso e non avviati")
per = [d for d in D.values() if d["oc_stato_progetto"] in ("In corso", "Non avviato") or (d["oc_data_fine_progetto_effettiva"] or "0") >= "20160101"]
fin = round(sum(num(d["oc_finanz_tot_pub_netto"]) for d in per)); pag = round(sum(num(d["tot_pagamenti"]) for d in per))
print("perimetro ricalcolato:", len(per), fin, pag)
rows = list(csv.DictReader(open(os.path.join(SITE, "dati", "progetti-arezzo.csv"), encoding="utf-8-sig")))
ok(len(rows) == len(per), f"righe del CSV ({len(rows)}) = perimetro ricalcolato ({len(per)})")
ok(round(sum(float(r["finanziato_euro"]) for r in rows)) == fin, "somma finanziato del CSV = ricalcolo indipendente")
ok(round(sum(float(r["pagato_euro"]) for r in rows)) == pag, "somma pagato del CSV = ricalcolo indipendente")
pagine = glob.glob(os.path.join(SITE, "progetti", "*.html"))
ok(len(pagine) == len(per), f"schede progetto ({len(pagine)}) = perimetro")
for f in ("index.html", "opere/index.html", "dati/index.html", "guida/index.html", "metodo/index.html", "sitemap.xml", "dati/progetti-arezzo.json"):
    ok(os.path.exists(os.path.join(SITE, f)), f"esiste {f}")
brutte = 0
for f in glob.glob(os.path.join(SITE, "**", "*.html"), recursive=True):
    t = re.sub(r"<script.*?</script>|<pre.*?</pre>", "", open(f, encoding="utf-8").read(), flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    if re.search(r"\b(None|undefined|nan|NaN)\b", t): brutte += 1
ok(brutte == 0, f"nessuna pagina con None/undefined/nan ({brutte} trovate)")
ok("ultimo aggiornamento dei dati" in open(os.path.join(SITE, "index.html"), encoding="utf-8").read(), "intestazione con fonte e data")
if PREC and os.path.exists(os.path.join(PREC, "dati", "progetti-arezzo.csv")):
    prev = list(csv.DictReader(open(os.path.join(PREC, "dati", "progetti-arezzo.csv"), encoding="utf-8-sig")))
    ok(abs(len(rows) - len(prev)) <= 0.15 * len(prev), f"perimetro {len(rows)} vs pubblicato {len(prev)}: variazione entro il 15%")
    pf = sum(float(r["finanziato_euro"]) for r in prev); nf = sum(float(r["finanziato_euro"]) for r in rows)
    ok(abs(nf - pf) <= 0.25 * pf, f"finanziato {nf:,.0f} vs pubblicato {pf:,.0f}: variazione entro il 25%")
tutte = glob.glob(os.path.join(SITE, "**", "*.html"), recursive=True)
ok(len(glob.glob(os.path.join(SITE, "en", "progetti", "*.html"))) == len(per), "schede progetto in inglese = perimetro")
mancano = 0
for f in tutte:
    t = open(f, encoding="utf-8").read()
    en = os.sep + "en" + os.sep in f
    frase = "Educational concept using official data. Not an institutional website." if en else "Concept a titolo didattico, con dati ufficiali. Non è un sito istituzionale."
    firma = "By Prof. Giuseppe Bosi, Computer Science and Technology" if en else "A cura del Prof. Giuseppe Bosi, Scienze e Tecnologie Informatiche"
    if not (frase in t and firma in t and 'class="fonte"' in t and "OpenCoesione" in t and 'class="lingua"' in t):
        mancano += 1
ok(mancano == 0, f"ogni pagina (IT e EN) ha fonte, data, frase del concept, firma e cambio lingua ({mancano} mancanti)")
ok(not os.environ.get("OC_PROVA_FALLIMENTO"), "prova di fallimento richiesta (solo per collaudo)")
print("ESITO:", "FALLITO" if errori else "PASSATO")
sys.exit(1 if errori else 0)
