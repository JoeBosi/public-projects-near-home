"""Controlli: somme ricalcolate in modo indipendente e confronto di 5 progetti con le pagine ufficiali."""
import json, re, html, time, urllib.request
num = lambda s: float((s or "0").replace(".", "").replace(",", "."))
D = json.load(open("dati/dettagli_arezzo.json"))
per = [d for d in D if d["oc_stato_progetto"] in ("In corso", "Non avviato") or (d["oc_data_fine_progetto_effettiva"] or "0") >= "20160101"]
print("perimetro", len(per), "finanziato", round(sum(num(d["oc_finanz_tot_pub_netto"]) for d in per)), "pagato", round(sum(num(d["tot_pagamenti"]) for d in per)))
vis = sorted([d for d in per if d["oc_stato_progetto"] == "In corso"], key=lambda d: -num(d["oc_finanz_tot_pub_netto"]))[:3]
vis += [d for d in per if d["oc_stato_progetto"] == "Concluso"][:1] + [d for d in per if d["oc_stato_progetto"] == "Non avviato"][:1]
for d in vis:
    time.sleep(2)
    req = urllib.request.Request(d["oc_link"], headers={"User-Agent": "progetti-pubblici-sotto-casa/1.0 (info@giuseppebosi.com)"})
    t = html.unescape(re.sub(r"<[^>]+>", " ", urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")))
    t = re.sub(r"\s+", " ", t)
    def trova(v):
        n = num(v); it = f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return it in t or it.replace(",00", "") in t or f"{round(n):,}".replace(",", ".") in t
    print(d["cod_locale_progetto"], d["oc_stato_progetto"], "finanz", d["oc_finanz_tot_pub_netto"], trova(d["oc_finanz_tot_pub_netto"]), "pagato", d["tot_pagamenti"], trova(d["tot_pagamenti"]), "CUP", (d["cup"] or "") in t, d["oc_link"])
