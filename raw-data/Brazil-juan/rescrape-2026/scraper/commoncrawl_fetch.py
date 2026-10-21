"""Fill gaps from Common Crawl: documents the Internet Archive did not yield.

For every document in the library's text sections or Planalto's speeches that
Common Crawl captured with a 200, and that has no real copy from the Internet
Archive yet -- including documents the Internet Archive never captured at all --
fetch Common Crawl's record (one byte range of one of its public WARC files),
check it with classify.py, and save it under raw/pages/commoncrawl/<folder>/.

raw/manifest_cc.tsv records every attempt; re-running picks up new index
records (commoncrawl_index.py runs for hours) and skips what is done.
"""
import csv, gzip, hashlib, io, json, pathlib, re, sys, time
import requests

BASE = pathlib.Path(__file__).resolve().parents[1]
RAW = BASE / "raw"
sys.path.insert(0, str(BASE / "scraper"))
from classify import classify  # noqa: E402
from targets import TEXT_SECTIONS, LIB, PLA, canonical_path, squash, edit1  # noqa: E402

UA = {"User-Agent": "ecdata research scraper (Executive Communications Dataset)"}
MANIFEST = RAW / "manifest_cc.tsv"
FIELDS = ["source", "folder", "section", "doc", "status", "kind", "url", "crawl", "warc", "path", "bytes", "fetched_at"]
PAUSE = 0.5


ONLY = set(sys.argv[1:])          # president folders to fill; all if none given


def real_folder(folder):
    """A mistyped president folder -> the real one, as targets.py merges them."""
    for f in ONLY:
        if folder == f or squash(folder) == squash(f) or edit1(squash(folder), squash(f)):
            return f
    return folder


def doc_of(url):
    if re.match(LIB.pattern, url, re.I):
        path = re.sub(LIB.pattern, "", url, flags=re.I)
        folder = real_folder(path.split("/")[0])
        path = folder + path[len(path.split("/")[0]):]
        if ONLY and folder not in ONLY:
            return None
        m = re.match(r"^[^/]+/([^/?#]+)", path)
        section = m.group(1) if m else ""
        if not TEXT_SECTIONS.search(section):
            return None
        return "biblioteca", folder, section, canonical_path(path)
    if re.match(PLA.pattern, url, re.I):
        if ONLY and "lula-planalto" not in ONLY:
            return None
        path = re.sub(PLA.pattern, "", url, flags=re.I)
        m = re.match(r"^(\d{4}|ultimos-discursos)", path)
        if not m:
            return None
        return "planalto", "lula-planalto", m.group(1), canonical_path(path)
    return None


def warc_body(rec):
    """The HTTP response body inside one WARC record fetched by byte range."""
    start, length = int(rec["offset"]), int(rec["length"])
    for k in range(6):
        try:
            r = requests.get(f"https://data.commoncrawl.org/{rec['filename']}", headers={
                **UA, "Range": f"bytes={start}-{start + length - 1}"}, timeout=120)
            if r.status_code in (200, 206):
                raw = gzip.GzipFile(fileobj=io.BytesIO(r.content)).read()
                # WARC headers, blank line, HTTP headers, blank line, body
                parts = raw.split(b"\r\n\r\n", 2)
                return parts[2] if len(parts) == 3 else b""
            why = f"http-{r.status_code}"
        except (requests.RequestException, OSError) as e:
            why = type(e).__name__
        time.sleep(10 * (k + 1))
    raise RuntimeError(why)


def main():
    # Only documents the Internet Archive has finished with and not yielded, or
    # never had: anything still queued there is left to it.
    queued = {(r["source"], r["doc"]) for r in csv.DictReader(open(RAW / "targets.tsv", encoding="utf-8"), delimiter="\t")}
    have = set(queued)
    if (RAW / "manifest.tsv").exists():
        for r in csv.DictReader(open(RAW / "manifest.tsv", encoding="utf-8"), delimiter="\t"):
            real = r["status"] == "ok" and (r["kind"] == "pdf" or not r["doc"].lower().endswith(".pdf"))
            if not real:
                have.discard((r["source"], r["doc"]))
    done = set()
    if MANIFEST.exists():
        done = {(r["source"], r["doc"]) for r in csv.DictReader(open(MANIFEST, encoding="utf-8"), delimiter="\t")
                if r["status"] == "ok"}

    # candidate Common Crawl records per document: real-looking first, newest first
    cands = {}
    for f in sorted((RAW / "index" / "commoncrawl").glob("*.jsonl")):
        crawl = f.name.split("__")[0]
        for line in f.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("status") != "200":
                continue
            mime = rec.get("mime-detected") or rec.get("mime") or ""
            if mime not in ("application/pdf", "text/html", "application/xhtml+xml"):
                continue
            d = doc_of(rec["url"])
            if not d or (d[0], d[3]) in have or (d[0], d[3]) in done:
                continue
            rec["crawl"] = crawl
            cands.setdefault(d, []).append(rec)
    for d, recs in cands.items():
        recs.sort(key=lambda r: (r.get("mime-detected") != "application/pdf", -int(r.get("length", 0)), r["crawl"]), reverse=False)
    print(f"{len(cands):,} documents to try from Common Crawl", flush=True)

    new = not MANIFEST.exists()
    counts = {}
    with open(MANIFEST, "a", encoding="utf-8", newline="") as mf:
        w = csv.writer(mf, delimiter="\t")
        if new:
            w.writerow(FIELDS)
        for n, ((source, folder, section, doc), recs) in enumerate(cands.items(), start=1):
            status, kind, used, path, size = "only-", "", None, "", 0
            seen = []
            for rec in recs[:4]:
                try:
                    body = warc_body(rec)
                except RuntimeError as e:
                    seen.append(f"error-{e}")
                    continue
                finally:
                    time.sleep(PAUSE)
                k = classify(body)
                seen.append(k)
                if k in ("pdf", "page"):
                    h = hashlib.sha1(f"{source}/{doc}".encode()).hexdigest()[:16]
                    p = RAW / "pages" / "commoncrawl" / folder / (f"{h}.pdf" if k == "pdf" else f"{h}.html.gz")
                    p.parent.mkdir(parents=True, exist_ok=True)
                    if k == "pdf":
                        p.write_bytes(body)
                    else:
                        with gzip.open(p, "wb") as g:
                            g.write(body)
                    status, kind, used, path, size = "ok", k, rec, str(p), len(body)
                    break
            if status != "ok":
                status = "only-" + "+".join(sorted(set(seen)))
            used = used or recs[0]
            counts[status if status != "ok" else f"ok-{kind}"] = counts.get(status if status != "ok" else f"ok-{kind}", 0) + 1
            w.writerow([source, folder, section, doc, status, kind, used["url"], used["crawl"],
                        used["filename"], path, size, time.strftime("%Y-%m-%dT%H:%M:%S")])
            mf.flush()
            if n % 50 == 0 or n == len(cands):
                print(f"{n:>6,}/{len(cands):,}  {dict(sorted(counts.items()))}", flush=True)
    print("finished", dict(sorted(counts.items())), flush=True)


if __name__ == "__main__":
    main()
