"""Download every active Luxembourg fund in the GLEIF register whose name contains an ESG-type keyword.

GLEIF (Global Legal Entity Identifier Foundation) data is public, licence CC0.
Luxembourg has ~29,500 active funds and sub-funds with an LEI; the API caps a query at
10,000 results, so we query one keyword at a time and merge the results.
"""
from pathlib import Path
import time

import pandas as pd
import requests

API = "https://api.gleif.org/api/v1/lei-records"
OUT = Path(__file__).resolve().parents[1] / "data" / "gleif_lu_funds_esg_keywords.csv"

# broad on purpose: the classifier decides later what is really an ESG term
KEYWORDS = [
    "ESG", "SRI", "ISR", "green", "climate", "clean", "environmental", "sustainable", "sustainability",
    "durable", "nachhaltig", "nachhaltigkeit", "sostenibile", "impact", "transition", "net zero", "paris",
    "low carbon", "carbon", "decarbonisation", "decarbonization", "social", "governance", "responsible",
    "responsable", "ethical", "ethique", "solar", "renewable", "biodiversity", "water", "circular", "gender",
    "inclusion", "planet", "ocean", "nature", "positive", "improvers", "transformation", "future", "SDG",
    "eco", "ecology", "energy", "PAB", "CTB", "article 9", "solidarity", "solidaire",
]


def fetch(keyword: str) -> list[dict]:
    rows, page = [], 1
    while True:
        params = {"filter[entity.legalAddress.country]": "LU", "filter[entity.category]": "FUND",
                  "filter[entity.status]": "ACTIVE", "filter[fulltext]": keyword,
                  "page[size]": 200, "page[number]": page}
        r = requests.get(API, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        for rec in data["data"]:
            e = rec["attributes"]["entity"]
            rows.append({"lei": rec["attributes"]["lei"], "legal_name": e["legalName"]["name"],
                         "legal_form_code": e["legalForm"]["id"], "legal_form_other": e["legalForm"].get("other"),
                         "umbrella": (e.get("associatedEntity") or {}).get("name"), "keyword": keyword})
        last = data["meta"]["pagination"]["lastPage"]
        if page >= min(last, 50):
            return rows
        page += 1
        time.sleep(0.2)


def main():
    frames = []
    for kw in KEYWORDS:
        rows = fetch(kw)
        print(f"{kw:20s} {len(rows):5d}")
        frames.append(pd.DataFrame(rows))
    df = pd.concat(frames)
    df = (df.groupby(["lei", "legal_name", "legal_form_code", "legal_form_other", "umbrella"], dropna=False)
          ["keyword"].agg(lambda s: "|".join(sorted(set(s)))).reset_index())
    OUT.parent.mkdir(exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"{len(df)} unique funds saved to {OUT}")


if __name__ == "__main__":
    main()
