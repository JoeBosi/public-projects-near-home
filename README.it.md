# public-projects-near-home

Sito statico che mostra, in parole semplici, i progetti finanziati con i fondi di coesione nel Comune di Arezzo, costruito con la API ufficiale di [OpenCoesione](https://opencoesione.gov.it/it/api/).

Demo: https://opendata.giuseppebosi.com (italiano, con interfaccia inglese sotto `/en/`).
Concept a titolo didattico, con dati ufficiali. Non è un sito istituzionale.

## Fonte e licenza

- Fonte: API pubblica di OpenCoesione, dati aggiornati al 30/06/2026.
- Licenza dei dati: **CC BY 4.0**, citare «OpenCoesione». I dati **non** sono coperti dalla licenza MIT del codice.
- I titoli riscritti in italiano semplice (`dati/titoli_*.json`) sono fatti con un assistente di IA solo da titolo e sintesi ufficiali; il titolo originale è sempre accanto. I nomi di persone fisiche nei titoli «a favore di» sono omessi.
- I dati grezzi non sono nel repository: li ricreano gli script.

## Uso

Solo libreria standard di Python 3. Passi: `scripts/01_lista.py`, `02_dettagli.py`, `03_costruisci.py`, `04_verifica.py` (vedi README.md in inglese). `scripts/aggiorna.sh` aggiorna e pubblica solo se i controlli passano; ogni tre mesi con il timer systemd.

## Autore

A cura del Prof. Giuseppe Bosi, Scienze e Tecnologie Informatiche. <https://www.giuseppebosi.com> · <https://www.linkedin.com/in/giuseppebosi>

## Licenza

Codice: MIT. Dati: CC BY 4.0, fonte OpenCoesione.
