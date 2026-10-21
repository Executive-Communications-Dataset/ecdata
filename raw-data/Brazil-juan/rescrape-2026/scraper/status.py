"""Where the rescrape has got to. Run from the project folder:

    .venv/bin/python scraper/status.py
"""
import csv, pathlib, subprocess
from collections import Counter

BASE = pathlib.Path(__file__).resolve().parents[1]


def running(name):
    r = subprocess.run(["pgrep", "-f", name], capture_output=True, text=True)
    return bool(r.stdout.strip())


def main():
    targets = list(csv.DictReader(open(BASE / "raw" / "targets.tsv", encoding="utf-8"), delimiter="\t"))
    man = list(csv.DictReader(open(BASE / "raw" / "manifest.tsv", encoding="utf-8"), delimiter="\t"))
    done = {(r["source"], r["doc"]) for r in man}
    print(f"Internet Archive download: {'RUNNING' if running('scraper/fetch.py') else 'not running'}")
    print(f"  {len(done):,} of {len(targets):,} documents processed")
    by = Counter((r["folder"], "text" if r["status"] == "ok" and r["kind"] in ("pdf", "page") else r["status"]) for r in man)
    folders = sorted({f for f, _ in by})
    left = Counter(t["folder"] for t in targets if (t["source"], t["doc"]) not in done)
    print(f"  {'folder':<32}{'saved':>7}{'challenge only':>16}{'not archived':>14}{'other':>7}{'to go':>7}")
    for f in folders:
        saved = by[(f, "text")]
        chal = sum(n for (g, s), n in by.items() if g == f and s.startswith("only-"))
        na = by[(f, "pdf-not-archived")]
        other = sum(n for (g, s), n in by.items() if g == f) - saved - chal - na
        print(f"  {f:<32}{saved:>7}{chal:>16}{na:>14}{other:>7}{left[f]:>7}")
    rest = sorted(set(left) - set(folders))
    if rest:
        print(f"  not started: {', '.join(rest)}")
    cc = BASE / "raw" / "index" / "commoncrawl"
    print(f"Common Crawl index: {'RUNNING' if running('commoncrawl_index.py') else 'not running'}, "
          f"{len(list(cc.glob('*.jsonl')))} crawl files")
    docs = BASE / "data" / "documents.parquet"
    if docs.exists():
        import polars as pl
        print(f"Parsed table: {pl.read_parquet(docs, columns=['doc']).height:,} documents with text "
              f"(data/documents.parquet; re-run scraper/parse.py to refresh)")


if __name__ == "__main__":
    main()
