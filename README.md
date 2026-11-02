# public-projects-near-home

![Laptop showing a dashboard of Arezzo projects, a city map and a small bridge model on a wooden table](assets/opendata-arezzo.jpg)

A static website that shows, in plain language, the projects funded with Italian and European cohesion funds in the Municipality of Arezzo, built from the official [OpenCoesione](https://opencoesione.gov.it/it/api/) API.

Demo: https://opendata.giuseppebosi.com (Italian, with an English interface under `/en/`).
Educational concept using official data. Not an institutional website.

## Data source and licence

- Source: OpenCoesione public API (<https://opencoesione.gov.it/it/api/>), data updated to 2026-06-30.
- Data licence: **Creative Commons Attribution 4.0 (CC BY 4.0)**. Credit "OpenCoesione" when reusing the data. The data are **not** covered by this repository's MIT licence.
- Project titles, descriptions and body names are official Italian texts and are never translated. Many titles are also rewritten in plain Italian with an AI assistant, only from the official title and summary (`dati/titoli_*.json`); the original title is always shown beside it.
- Names of private individuals appearing in "in favour of ..." titles are omitted from the site.
- Raw downloads are not stored in this repository (they are re-created by the scripts).

## How it works

Python 3 standard library only, no dependencies.

```bash
python3 scripts/01_lista.py        # list of all Arezzo projects (26 pages, ~1 request per second, cached)
python3 scripts/02_dettagli.py     # detail records for the projects in the working perimeter (~1,300, about 25 minutes)
python3 scripts/03_costruisci.py   # builds the static site in site/ (Italian + /en/)
python3 scripts/04_verifica.py     # independent checks; exits with 1 if anything does not add up
```

`scripts/aggiorna.sh` runs the four steps in a fresh folder and publishes only if the checks pass; otherwise the published site is left untouched and a ntfy notification is sent (configure with `NTFY_CONF`, `PUBLISH_DIR`). `scripts/opendata-aggiorna.service` and `.timer` run it every three months with systemd.

`esempi/` holds the basic version of the site used in the tutorial page (`guida/costruisci/`), in Italian and English.

The scripts expect the API rate limit to be respected (HTTP 429 above about one request per second) and keep every answer in a local cache.

## Author

By Prof. Giuseppe Bosi, Computer Science and Technology. <https://www.giuseppebosi.com> · <https://www.linkedin.com/in/giuseppebosi>

## Licence

Code: MIT (see `LICENSE`). Data: CC BY 4.0, source OpenCoesione.
