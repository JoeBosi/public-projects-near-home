#!/bin/bash
# Aggiornamento trimestrale: scarica in una cartella nuova, ricostruisce, esegue 04_verifica e pubblica SOLO se passa.
# Se qualcosa fallisce il sito pubblicato non viene toccato e parte un avviso su ntfy.
cd "$(dirname "$0")/.." || exit 1
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
exec 9>/tmp/opendata-aggiorna.lock; flock -n 9 || { echo "già in corso"; exit 0; }
PUB="${PUBLISH_DIR:-/opt/opendata}"   # cartella servita dal web server
W="dati/aggiornamento/$(date +%F)"; mkdir -p "$W"; LOG="$W/aggiorna.log"
export OC_CACHE="$PWD/$W/cache" OC_LISTA="$PWD/$W/lista_arezzo.json" OC_DETTAGLI="$PWD/$W/dettagli_arezzo.json" OC_SITE="$PWD/$W/site" OC_PREC="$PUB"
# Avvisi su ntfy: NTFY_CONF (default /etc/ntfy-root-login.conf) deve definire NTFY_SERVER, NTFY_TOPIC e, se serve, NTFY_TOKEN. Senza, nessun avviso.
avvisa() { ( . "${NTFY_CONF:-/etc/ntfy-root-login.conf}" 2>/dev/null; [ -n "${NTFY_SERVER:-}" ] && curl -s -m 10 -H "Authorization: Bearer ${NTFY_TOKEN:-}" -H "Title: $1" \
  -d "$2" "$NTFY_SERVER/${NTFY_TOPIC:-opendata}" ) >/dev/null 2>&1 || true; }
fallito() { echo "FALLITO: $1" | tee -a "$LOG"; avvisa "Opendata: aggiornamento NON pubblicato" "$1. Il sito è rimasto com'era. Log: $PWD/$LOG"; exit 1; }
{
  echo "== $(date -Is) inizio"
  $PY scripts/01_lista.py   || fallito "scarico della lista"
  $PY scripts/02_dettagli.py || fallito "scarico dei dettagli (alcuni falliti)"
  $PY scripts/03_costruisci.py || fallito "costruzione del sito"
  $PY scripts/04_verifica.py || fallito "04_verifica non superata"
} >>"$LOG" 2>&1 || exit 1
rsync -a "$PUB"/ "$W/sito-precedente/" || fallito "copia di sicurezza del sito precedente"
rsync -a --delete "$OC_SITE"/ "$PUB"/ || fallito "pubblicazione"
R="$W/report.json"
MSG=$($PY -c "import json;r=json.load(open('$R'));print(f\"Pubblicato. Dati al {r['data_dati']}: {r['n_perimetro']} progetti, finanziato {r['finanziato']:,} €, pagato {r['pagato']:,} €. Titoli semplici: {r['titoli_semplici']}; ancora con titolo ufficiale da semplificare: {r['titoli_ufficiali_da_semplificare']}.\")")
echo "$MSG" | tee -a "$LOG"; avvisa "Opendata aggiornato" "$MSG"
