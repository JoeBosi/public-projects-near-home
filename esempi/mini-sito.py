"""Mini sito dei progetti pubblici di un Comune, dai dati OpenCoesione. Solo libreria standard di Python."""
import html, json, os, time, urllib.error, urllib.request
from datetime import date

COMUNE = "arezzo-comune"          # cambia questo valore per un altro Comune
URL = "https://opencoesione.gov.it/it/api/progetti/?format=json&territorio=" + COMUNE + "&page_size=500&page="
os.makedirs("cache", exist_ok=True)

def scarica(pagina):
    """Scarica una pagina di risultati; se l'hai già scaricata la rilegge dal disco."""
    nome = f"cache/pagina-{pagina}.json"
    if os.path.exists(nome):
        return json.load(open(nome, encoding="utf-8"))
    time.sleep(1)                  # pausa di cortesia: oltre circa una richiesta al secondo il servizio risponde 429
    richiesta = urllib.request.Request(URL + str(pagina), headers={"User-Agent": "mini-sito-didattico/1.0"})
    for tentativo in range(1, 6):
        try:
            with urllib.request.urlopen(richiesta, timeout=90) as risposta:
                dati = json.load(risposta)
            break
        except urllib.error.HTTPError as errore:
            if errore.code != 429 or tentativo == 5:
                raise
            time.sleep(20 * tentativo)     # troppe richieste: aspetta di più e riprova
    json.dump(dati, open(nome, "w", encoding="utf-8"), ensure_ascii=False)
    return dati

progetti, pagina = [], 1
while True:
    dati = scarica(pagina)
    progetti += dati["results"]
    if pagina >= dati["last_page"]:
        break
    pagina += 1
print(f"Scaricate {pagina} pagine, {len(progetti)} progetti")

euro = lambda testo: float((testo or "0").replace(",", "."))      # "51817680,65" -> 51817680.65
fmt = lambda x: f"{round(x):,}".replace(",", ".") + " €"
finanziato = sum(euro(p["oc_finanz_tot_pub_netto"]) for p in progetti)
pagato = sum(euro(p["tot_pagamenti"]) for p in progetti)
in_corso = sorted((p for p in progetti if p["oc_stato_progetto"] == "In corso"), key=lambda p: -euro(p["oc_finanz_tot_pub_netto"]))
print("Finanziato:", fmt(finanziato), "- Già pagato:", fmt(pagato), "- In corso:", len(in_corso))

righe = "".join(
    f"<tr><td>{html.escape(p['oc_titolo_progetto'])}</td><td>{fmt(euro(p['oc_finanz_tot_pub_netto']))}</td><td>{fmt(euro(p['tot_pagamenti']))}</td></tr>"
    for p in in_corso[:15])
pagina_html = f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Progetti pubblici ad Arezzo</title>
<style>body{{font:18px/1.5 system-ui,sans-serif;max-width:900px;margin:0 auto;padding:16px;color:#1b2330}}
table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #d9e0ea;padding:6px;text-align:left}}.n{{font-size:1.6rem;font-weight:700}}</style></head><body>
<p>Fonte: <a href="https://opencoesione.gov.it/">OpenCoesione</a> (licenza CC BY 4.0). Dati scaricati il {date.today().strftime('%d/%m/%Y')}.</p>
<h1>Progetti pubblici ad Arezzo</h1>
<p><span class="n">{fmt(finanziato)}</span> finanziati e <span class="n">{fmt(pagato)}</span> già pagati, su {len(progetti)} progetti.</p>
<h2>I 15 progetti in corso più grandi</h2>
<div style="overflow-x:auto"><table><tr><th>Titolo</th><th>Finanziato</th><th>Già pagato</th></tr>{righe}</table></div>
</body></html>"""
os.makedirs("sito", exist_ok=True)
open("sito/index.html", "w", encoding="utf-8").write(pagina_html)
print("Creato sito/index.html")
