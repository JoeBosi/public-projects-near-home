"""Crea i 4 notebook Colab (IT/EN) in notebooks/ partendo dagli esempi del tutorial. Uso: python3 tools/crea_notebook.py"""
import json, os, re, nbformat
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
API = "https://opencoesione.gov.it/it/api/progetti/?format=json&territorio=arezzo-comune&page_size=2"
md = nbformat.v4.new_markdown_cell; code = nbformat.v4.new_code_cell

def salva(cells, nome):
    nb = nbformat.v4.new_notebook(cells=cells)
    nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    nb.metadata["language_info"] = {"name": "python"}
    nbformat.write(nb, os.path.join(ROOT, "notebooks", nome))

def primi_passi(en):
    if en:
        a = md("# First steps with Python: public projects of Arezzo\n\nData: [OpenCoesione](https://opencoesione.gov.it/) (licence CC BY 4.0). Press the play button on each cell, from top to bottom. Nothing to install: Google Colab runs Python in your browser.")
        b = code(f'''import json, urllib.request

url = "{API}"
# The User-Agent tells the service who is asking: a descriptive name is good practice
request = urllib.request.Request(url, headers={{"User-Agent": "projects-tutorial/1.0 (https://opendata.giuseppebosi.com)"}})
with urllib.request.urlopen(request) as response:
    data = json.load(response)''')
        c = md("The cell above asks the API for two projects of the Municipality of Arezzo. The next one prints the total and, for each project, the CUP (project code), the status, the funded amount and the paid amount.")
        d = code('''print("Projects found:", data["count"])
for p in data["results"]:
    print(p["cup"], p["oc_stato_progetto"], p["oc_finanz_tot_pub_netto"], p["tot_pagamenti"])''')
        salva([a, b, c, d], "first-steps-python.ipynb")
    else:
        a = md("# Primi passi con Python: i progetti pubblici di Arezzo\n\nDati: [OpenCoesione](https://opencoesione.gov.it/) (licenza CC BY 4.0). Premi il pulsante Play su ogni cella, dall'alto in basso. Non serve installare nulla: Google Colab esegue Python nel browser.")
        b = code(f'''import json, urllib.request

url = "{API}"
# Lo User-Agent dice al servizio chi sta chiedendo: un nome descrittivo è buona prassi
richiesta = urllib.request.Request(url, headers={{"User-Agent": "progetti-didattico/1.0 (https://opendata.giuseppebosi.com)"}})
with urllib.request.urlopen(richiesta) as risposta:
    dati = json.load(risposta)''')
        c = md("La cella qui sopra chiede alla API due progetti del Comune di Arezzo. Quella che segue stampa il totale e, per ogni progetto, il CUP (codice del progetto), lo stato, il finanziato e il pagato.")
        d = code('''print("Progetti trovati:", dati["count"])
for p in dati["results"]:
    print(p["cup"], p["oc_stato_progetto"], p["oc_finanz_tot_pub_netto"], p["tot_pagamenti"])''')
        salva([a, b, c, d], "primi-passi-python.ipynb")

def mini(en):
    src = open(os.path.join(ROOT, "esempi", "mini-site.py" if en else "mini-sito.py"), encoding="utf-8").read()
    m = ["def download" if en else "def scarica", "projects, page = [], 1" if en else "progetti, pagina = [], 1",
         "euro = lambda", "rows = " if en else "righe = ", "page_html = " if en else "pagina_html = ", "os.makedirs(\"site\"" if en else "os.makedirs(\"sito\""]
    pos = [src.index(x) for x in m]
    assert pos == sorted(pos), pos
    parti = [src[a:b].rstrip() + "\n" for a, b in zip([0] + pos, pos + [len(src)])]
    parti[0] = parti[0].split("\n", 1)[1]  # via la docstring iniziale (sta nel testo)
    var = "page_html" if en else "pagina_html"
    if en:
        t = [md("# A mini website of Arezzo's public projects\n\nData: [OpenCoesione](https://opencoesione.gov.it/) (licence CC BY 4.0). Press play on each cell, from top to bottom. Nothing to install: Google Colab runs Python in your browser. The download takes about three minutes (26 pages, one request per second).\n\n**1. Settings**"),
             md("**2. A function that downloads one page, with a pause and a memory**"), md("**3. Download all pages**"),
             md("**4. Sum funded and paid separately**"), md("**5. Build the page**"), md("**6. Save it**"),
             md("**7. Look at the result** (the page built above, shown here)")]
        nome = "mini-site.ipynb"
        mostra = f'''import html
from IPython.display import display
display({{"text/html": '<iframe srcdoc="' + html.escape({var}) + '" width="100%" height="520" style="border:1px solid #ccc;background:#fff"></iframe>'}}, raw=True)'''
    else:
        t = [md("# Un mini sito dei progetti pubblici di Arezzo\n\nDati: [OpenCoesione](https://opencoesione.gov.it/) (licenza CC BY 4.0). Premi Play su ogni cella, dall'alto in basso. Non serve installare nulla: Google Colab esegue Python nel browser. Lo scarico richiede circa tre minuti (26 pagine, una richiesta al secondo).\n\n**1. Impostazioni**"),
             md("**2. Una funzione che scarica una pagina, con pausa e memoria**"), md("**3. Scarica tutte le pagine**"),
             md("**4. Somma finanziato e pagato, separati**"), md("**5. Costruisci la pagina**"), md("**6. Salvala**"),
             md("**7. Guarda il risultato** (la pagina costruita sopra, mostrata qui)")]
        nome = "mini-sito.ipynb"
        mostra = f'''import html
from IPython.display import display
display({{"text/html": '<iframe srcdoc="' + html.escape({var}) + '" width="100%" height="520" style="border:1px solid #ccc;background:#fff"></iframe>'}}, raw=True)'''
    cells = []
    for i in range(6):
        cells += [t[i], code(parti[i].rstrip("\n"))]
    cells += [t[6], code(mostra)]
    salva(cells, nome)

for en in (False, True):
    primi_passi(en); mini(en)
print("notebook creati")
