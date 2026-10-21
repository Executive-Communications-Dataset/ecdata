"""Common Crawl's index records for the Presidency Library and Planalto's
speeches, from every crawl. A second archive alongside the Internet Archive:
where the IA holds only the library's anti-bot challenge for a document,
Common Crawl may have fetched the real thing.

Writes raw/index/commoncrawl/<crawl>__<source>.jsonl (one JSON record per
capture, as the index returns it) and skips crawls already written.
"""
import json, pathlib, sys, time
import requests

BASE = pathlib.Path(__file__).resolve().parents[1]
OUT = BASE / "raw" / "index" / "commoncrawl"
UA = {"User-Agent": "ecdata research scraper (Executive Communications Dataset)"}
PREFIXES = {
    "biblioteca": "biblioteca.presidencia.gov.br/presidencia/ex-presidentes/*",
    "planalto": "www.gov.br/planalto/pt-br/acompanhe-o-planalto/discursos-e-pronunciamentos/*",
}


def get(api, params, tries=8):
    for k in range(tries):
        try:
            r = requests.get(api, params=params, headers=UA, timeout=180)
            if r.status_code == 200:
                return r.text
            if r.status_code == 404:          # no captures in this crawl
                return ""
            why = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            why = type(e).__name__
        time.sleep(min(15 * (k + 1), 120))
    print(f"  gave up on {params['url']} in {api}: {why}", flush=True)
    return None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    crawls = requests.get("https://index.commoncrawl.org/collinfo.json", headers=UA, timeout=60).json()
    # Oldest first: the crawls before the library's anti-bot challenge (late
    # 2018) are the ones likely to hold real copies the Internet Archive lacks.
    crawls = sorted(crawls, key=lambda c: c["id"])
    total = 0
    for c in crawls:
        for name, prefix in PREFIXES.items():
            f = OUT / f"{c['id']}__{name}.jsonl"
            if f.exists():
                continue
            pages = get(c["cdx-api"], {"url": prefix, "output": "json", "showNumPages": "true"})
            if pages is None:
                continue
            n_pages = json.loads(pages)["pages"] if pages.strip() else 0
            lines = []
            for p in range(n_pages):
                t = get(c["cdx-api"], {"url": prefix, "output": "json", "page": p})
                if t is None:
                    lines = None
                    break
                lines += [l for l in t.splitlines() if l.strip()]
                time.sleep(2)
            if lines is None:
                continue
            f.write_text("\n".join(lines) + ("\n" if lines else ""))
            total += len(lines)
            print(f"{c['id']} {name}: {len(lines)} captures", flush=True)
            time.sleep(2)
    print(f"done: {total} captures", flush=True)


if __name__ == "__main__":
    main()
