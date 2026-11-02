"""Mini website of a municipality's public projects, from OpenCoesione data. Python standard library only."""
import html, json, os, time, urllib.error, urllib.request
from datetime import date

COMUNE = "arezzo-comune"          # change this value for another municipality
URL = "https://opencoesione.gov.it/it/api/progetti/?format=json&territorio=" + COMUNE + "&page_size=500&page="
os.makedirs("cache", exist_ok=True)

def download(page):
    """Download one page of results; if you already have it, read it back from disk."""
    name = f"cache/page-{page}.json"
    if os.path.exists(name):
        return json.load(open(name, encoding="utf-8"))
    time.sleep(1)                  # courtesy pause: above about one request per second the service answers 429
    request = urllib.request.Request(URL + str(page), headers={"User-Agent": "mini-site-tutorial/1.0"})
    for attempt in range(1, 6):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                data = json.load(response)
            break
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == 5:
                raise
            time.sleep(20 * attempt)     # too many requests: wait longer and try again
    json.dump(data, open(name, "w", encoding="utf-8"), ensure_ascii=False)
    return data

projects, page = [], 1
while True:
    data = download(page)
    projects += data["results"]
    if page >= data["last_page"]:
        break
    page += 1
print(f"Downloaded {page} pages, {len(projects)} projects")

euro = lambda text: float((text or "0").replace(",", "."))      # "51817680,65" -> 51817680.65
fmt = lambda x: f"{round(x):,}" + " EUR"
funded = sum(euro(p["oc_finanz_tot_pub_netto"]) for p in projects)
paid = sum(euro(p["tot_pagamenti"]) for p in projects)
ongoing = sorted((p for p in projects if p["oc_stato_progetto"] == "In corso"), key=lambda p: -euro(p["oc_finanz_tot_pub_netto"]))
print("Funded:", fmt(funded), "- Already paid:", fmt(paid), "- Ongoing:", len(ongoing))

rows = "".join(
    f"<tr><td>{html.escape(p['oc_titolo_progetto'])}</td><td>{fmt(euro(p['oc_finanz_tot_pub_netto']))}</td><td>{fmt(euro(p['tot_pagamenti']))}</td></tr>"
    for p in ongoing[:15])
page_html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Public projects in Arezzo</title>
<style>body{{font:18px/1.5 system-ui,sans-serif;max-width:900px;margin:0 auto;padding:16px;color:#1b2330}}
table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #d9e0ea;padding:6px;text-align:left}}.n{{font-size:1.6rem;font-weight:700}}</style></head><body>
<p>Source: <a href="https://opencoesione.gov.it/">OpenCoesione</a> (licence CC BY 4.0). Data downloaded on {date.today().isoformat()}. Project titles are in Italian, as in the source.</p>
<h1>Public projects in Arezzo</h1>
<p><span class="n">{fmt(funded)}</span> funded and <span class="n">{fmt(paid)}</span> already paid, across {len(projects)} projects.</p>
<h2>The 15 largest ongoing projects</h2>
<table><tr><th>Title (Italian)</th><th>Funded</th><th>Already paid</th></tr>{rows}</table>
</body></html>"""
os.makedirs("site", exist_ok=True)
open("site/index.html", "w", encoding="utf-8").write(page_html)
print("Created site/index.html")
