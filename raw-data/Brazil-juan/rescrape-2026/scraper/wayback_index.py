"""Enumerate every page the Internet Archive holds under the Presidency Library's
former-presidents section, one CDX page at a time, retrying through outages.

Writes raw/index/cdx_page_<n>.txt (one line per archived URL: urlkey timestamp
original mimetype statuscode digest length) and raw/index/cdx_all.tsv.
"""
import pathlib, sys, time
import requests

BASE = pathlib.Path(__file__).resolve().parents[1]
OUT = BASE / "raw" / "index"
CDX = "http://web.archive.org/cdx/search/cdx"
PREFIX = "biblioteca.presidencia.gov.br/presidencia/ex-presidentes/*"
UA = {"User-Agent": "ecdata research scraper (Executive Communications Dataset; contact via github.com/Executive-Communications-Dataset)"}


def get(params, tries=12):
    for k in range(tries):
        try:
            r = requests.get(CDX, params=params, headers=UA, timeout=180)
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
    OUT.mkdir(parents=True, exist_ok=True)
    base = {"url": PREFIX, "filter": "statuscode:200", "collapse": "urlkey"}
    pages = int(get({**base, "showNumPages": "true"}).strip())
    print(f"{pages} CDX pages", flush=True)
    for p in range(pages):
        f = OUT / f"cdx_page_{p}.txt"
        if f.exists() and f.stat().st_size:
            continue
        f.write_text(get({**base, "page": p}))
        print(f"  page {p}: {len(f.read_text().splitlines())} urls", flush=True)
        time.sleep(3)
    lines = [l for p in range(pages) for l in (OUT / f"cdx_page_{p}.txt").read_text().splitlines() if l.strip()]
    (OUT / "cdx_all.tsv").write_text("\n".join(lines) + "\n")
    print(f"{len(lines)} archived URLs in total", flush=True)


if __name__ == "__main__":
    main()
