"""Scarica la scheda dettaglio dei progetti nel perimetro di lavoro (vedi docs/FONTI.md).
Riparte dalla cache; gli errori su un singolo progetto vanno in dati/falliti.txt e si ritentano alla fine."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
import api
D = os.path.join(os.path.dirname(__file__), "..", "dati")
num = lambda s: float((s or "0").replace(".", "").replace(",", "."))
L = json.load(open(os.path.join(D, "lista_arezzo.json")))
def serve(r):
    if r["oc_stato_progetto"] != "Concluso":
        return True
    if num(r["oc_finanz_tot_pub_netto"]) >= 100000:
        return True
    return r["cup_descr_natura"].startswith(("REALIZZAZIONE DI LAVORI", "ACQUISTO DI BENI"))
sel = [r for r in L if serve(r)]
print(len(sel), flush=True)
out, falliti = {}, []
for giro in range(3):
    falliti = []
    for i, r in enumerate(sel):
        if r["cod_locale_progetto"] in out: continue
        try:
            out[r["cod_locale_progetto"]] = api.get(r["url"])
        except Exception as e:
            falliti.append(r["url"])
        if i % 50 == 0: print(giro, i, len(out), flush=True)
    open(os.path.join(D, "falliti.txt"), "w").write("\n".join(falliti))
    if not falliti: break
    time.sleep(60)
json.dump(list(out.values()), open(os.path.join(D, "dettagli_arezzo.json"), "w"), ensure_ascii=False)
print("FINITO", len(out), "falliti", len(falliti), flush=True)
