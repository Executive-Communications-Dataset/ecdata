"""Every capture (not just one per URL) the archive holds under the library's
former-presidents section and Planalto's speeches, with size and type, so the
best copy of each document can be chosen. The library served the archive's
crawler an anti-bot JavaScript challenge some of the time, and those captures
are small HTML pages even where the URL is a PDF.

Writes raw/index/captures_<source>.tsv: urlkey timestamp original mimetype length digest
"""
import pathlib, sys, time
import requests

BASE = pathlib.Path(__file__).resolve().parents[1]
OUT = BASE / "raw" / "index"
CDX = "http://web.archive.org/cdx/search/cdx"
UA = {"User-Agent": "ecdata research scraper (Executive Communications Dataset)"}
PREFIXES = {
    "biblioteca": "biblioteca.presidencia.gov.br/presidencia/ex-presidentes/*",
    "planalto": "gov.br/planalto/pt-br/acompanhe-o-planalto/discursos-e-pronunciamentos/*",
}


def get(params, tries=12):
    for k in range(tries):
        try:
            r = requests.get(CDX, params=params, headers=UA, timeout=300)
            if r.status_code == 200 and "<html" not in r.text[:200].lower():
                return r.text
            why = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            why = type(e).__name__
        wait = min(30 * (k + 1), 300)
        print(f"  {why}; retrying in {wait}s", flush=True)
        time.sleep(wait)
    sys.exit("CDX unavailable")


def main():
    for name, prefix in PREFIXES.items():
        base = {"url": prefix, "filter": "statuscode:200", "fl": "urlkey,timestamp,original,mimetype,length,digest"}
        count = {k: v for k, v in base.items() if k != "fl"}
        pages = int(get({**count, "showNumPages": "true"}).strip())
        parts = []
        for p in range(pages):
            f = OUT / f"captures_{name}_page_{p}.txt"
            if not (f.exists() and f.stat().st_size):
                f.write_text(get({**base, "page": p}))
                time.sleep(3)
            parts.append(f.read_text())
            print(f"  {name} page {p + 1}/{pages}", flush=True)
        text = "".join(parts)
        (OUT / f"captures_{name}.tsv").write_text(text)
        print(f"{name}: {len(text.splitlines()):,} captures", flush=True)


if __name__ == "__main__":
    main()
