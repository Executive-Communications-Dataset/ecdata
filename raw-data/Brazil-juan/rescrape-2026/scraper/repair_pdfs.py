"""Replace truncated PDFs with a complete copy, from either archive.

The archives sometimes store only the start of a large file. fetch.py took the
first capture that began with %PDF-, so some saved PDFs end early and cannot be
opened. For each one, every other PDF capture of the same document is tried --
the Internet Archive's, then Common Crawl's -- until one opens and has pages.
The complete copy replaces the truncated file; raw/pdf_repairs.tsv records what
was done, and the truncated original is kept alongside as <name>.truncated.

    python scraper/repair_pdfs.py <president folder> ...
"""
import csv, json, pathlib, sys, time
import pypdfium2 as pdfium

BASE = pathlib.Path(__file__).resolve().parents[1]
RAW = BASE / "raw"
sys.path.insert(0, str(BASE / "scraper"))
import fetch  # noqa: E402  (its paced, retrying get() against the Internet Archive)
from commoncrawl_fetch import doc_of, warc_body  # noqa: E402
from targets import read  # noqa: E402


def complete(body: bytes) -> bool:
    if body[:5] != b"%PDF-":
        return False
    try:
        return len(pdfium.PdfDocument(body)) > 0
    except Exception:
        return False


def main():
    only = set(sys.argv[1:])
    man = list(csv.DictReader(open(RAW / "manifest.tsv", encoding="utf-8"), delimiter="\t"))
    man += [{**r, "used_url": r["url"]} for r in csv.DictReader(open(RAW / "manifest_cc.tsv", encoding="utf-8"), delimiter="\t")]
    broken = {}
    for r in man:
        if r["status"] == "ok" and r["kind"] == "pdf" and (not only or r["folder"] in only):
            p = pathlib.Path(r["path"])
            if p.exists() and not complete(p.read_bytes()):
                broken[(r["source"], r["doc"])] = r
    print(f"{len(broken)} truncated PDFs", flush=True)

    # every PDF capture per document, from both archives
    ia = read("captures_biblioteca.tsv")
    ia = ia.filter(ia["mime"] == "application/pdf")
    ia_by = {}
    for ts, url, length in ia.select("ts", "url", "length").iter_rows():
        d = doc_of(url)
        if d:
            ia_by.setdefault((d[0], d[3]), []).append((int(length), ts, url))
    cc_by = {}
    for f in (RAW / "index" / "commoncrawl").glob("*.jsonl"):
        for line in f.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("status") == "200" and (rec.get("mime-detected") == "application/pdf"):
                d = doc_of(rec["url"])
                if d:
                    cc_by.setdefault((d[0], d[3]), []).append(rec)

    new = not (RAW / "pdf_repairs.tsv").exists()
    counts = {}
    with open(RAW / "pdf_repairs.tsv", "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        if new:
            w.writerow(["source", "doc", "result", "archive", "url", "ref", "bytes"])
        for n, ((source, doc), r) in enumerate(broken.items(), start=1):
            target = pathlib.Path(r["path"])
            got = None
            for length, ts, url in sorted(ia_by.get((source, doc), []), reverse=True):
                if url == r.get("used_url") and ts == r.get("used_ts"):
                    continue
                try:
                    body = fetch.get(f"https://web.archive.org/web/{ts}id_/{url}")
                except RuntimeError:
                    continue
                if body and complete(body):
                    got = ("Internet Archive", url, ts, body)
                    break
            if not got:
                for rec in sorted(cc_by.get((source, doc), []), key=lambda x: -int(x.get("length", 0))):
                    try:
                        body = warc_body(rec)
                    except RuntimeError:
                        continue
                    time.sleep(0.5)
                    if complete(body):
                        got = ("Common Crawl", rec["url"], f"{rec['filename']}@{rec['offset']}", body)
                        break
            if got:
                archive, url, ref, body = got
                target.rename(target.with_name(target.name + ".truncated"))
                target.write_bytes(body)
                w.writerow([source, doc, "replaced", archive, url, ref, len(body)])
                counts["replaced"] = counts.get("replaced", 0) + 1
            else:
                w.writerow([source, doc, "no complete copy", "", "", "", 0])
                counts["no complete copy"] = counts.get("no complete copy", 0) + 1
            f.flush()
            print(f"{n}/{len(broken)} {counts}", flush=True)
    print("finished", counts, flush=True)


if __name__ == "__main__":
    main()
