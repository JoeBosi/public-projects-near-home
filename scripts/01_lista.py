import json, collections, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import api
res, ult = api.lista()
json.dump(res, open(os.path.join(os.path.dirname(__file__), "..", "dati", "lista_arezzo.json"), "w"), ensure_ascii=False)
print(len(res), ult["count"])
print(collections.Counter(r["oc_stato_progetto"] for r in res))
print(collections.Counter((r["oc_stato_progetto"], r["cup_descr_natura"]) for r in res).most_common(30))
