"""Download every document in raw/targets.tsv from the Internet Archive.

For each document, its captures are tried in the order targets.py chose until
one is real: PDF bytes, or a page with content. A capture of the library's
anti-bot challenge or its maintenance page is never saved; the next capture is
tried instead. Captures are fetched as originally archived -- the `id_` form of
a Wayback URL returns the archived bytes without the archive's banner or link
rewriting -- and saved under raw/pages/<source>/<folder>/, HTML gzipped and
PDFs as they are.

raw/manifest.tsv records the outcome for every document, so the run can be
stopped and resumed: a document already in the manifest is skipped.

The archive is shared infrastructure that throttles and goes offline from time
to time, so this runs a few requests at a time, backs off on 429/5xx and
connection resets, and waits out outages.
"""
import csv, gzip, hashlib, pathlib, sys, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from classify import classify  # noqa: E402

BASE = pathlib.Path(__file__).resolve().parents[1]
RAW = BASE / "raw"
PAGES = RAW / "pages"
MANIFEST = RAW / "manifest.tsv"
LOG = BASE / "logs" / "fetch.log"
UA = {"User-Agent": "ecdata research scraper (Executive Communications Dataset; "
                    "github.com/Executive-Communications-Dataset)"}
WORKERS = 1
# The archive refuses connections from an address that sends requests in
# bursts or much past ten a minute, and each refusal costs minutes of cooldown,
# so requests go one at a time, paced well under that.
PER_MINUTE = 9
FIELDS = ["source", "folder", "section", "doc", "status", "kind", "used_url", "used_ts",
          "path", "bytes", "tries", "fetched_at"]

lock = threading.Lock()
cooldown_until = [0.0]
next_slot = [0.0]


def wait_turn():
    with lock:
        now = time.time()
        slot = max(now, next_slot[0], cooldown_until[0])
        next_slot[0] = slot + 60.0 / PER_MINUTE
    time.sleep(max(0.0, slot - now))


def log(msg):
    with lock:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")


def get(url):
    """The archived bytes at url, or None if the archive says it has none."""
    for attempt in range(10):
        wait_turn()
        try:
            r = requests.get(url, headers=UA, timeout=120)
            if r.status_code == 200 and b"temporarily offline" not in r.content[:400].lower():
                return r.content
            if r.status_code in (404, 403, 410):
                return None
            why = f"http-{r.status_code}"
        except requests.RequestException as e:
            why = type(e).__name__
        backoff = min(60 * 2 ** attempt, 900)
        with lock:
            cooldown_until[0] = max(cooldown_until[0], time.time() + backoff)
        log(f"{why} on {url} (attempt {attempt + 1}); everyone waits {backoff}s")
    raise RuntimeError(f"gave up on {url}")


def fetch(t):
    if t.get("fetch") == "false":
        return t, "pdf-not-archived", "", "", "", "", 0, 0
    tss, urls = t["cand_ts"].split("|"), t["cand_url"].split("|")
    seen = []
    for k, (ts, url) in enumerate(zip(tss, urls), start=1):
        try:
            body = get(f"https://web.archive.org/web/{ts}id_/{url}")
        except RuntimeError:
            return t, "gave-up", "", url, ts, "", 0, k
        if body is None:
            seen.append("404")
            continue
        kind = classify(body)
        seen.append(kind)
        if kind not in ("pdf", "page"):
            continue
        h = hashlib.sha1(f"{t['source']}/{t['doc']}".encode()).hexdigest()[:16]
        path = PAGES / t["source"] / t["folder"] / (f"{h}.pdf" if kind == "pdf" else f"{h}.html.gz")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".part")
        if kind == "pdf":
            tmp.write_bytes(body)
        else:
            with gzip.open(tmp, "wb") as g:
                g.write(body)
        tmp.rename(path)
        return t, "ok", kind, url, ts, str(path), len(body), k
    status = "only-" + "+".join(sorted(set(seen))) if seen else "no-captures"
    return t, status, "", "", "", "", 0, len(seen)


def main():
    PAGES.mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(RAW / "targets.tsv", encoding="utf-8") as f:
        targets = list(csv.DictReader(f, delimiter="\t"))
    only = set(sys.argv[1:])
    if only:
        targets = [t for t in targets if t["folder"] in only or t["source"] in only]
    done_docs = set()
    if MANIFEST.exists():
        with open(MANIFEST, encoding="utf-8") as f:
            done_docs = {(r["source"], r["doc"]) for r in csv.DictReader(f, delimiter="\t")
                         if r["status"] != "gave-up"}
    todo = [t for t in targets if (t["source"], t["doc"]) not in done_docs]
    print(f"{len(targets):,} documents, {len(targets) - len(todo):,} already done, {len(todo):,} to fetch", flush=True)

    new = not MANIFEST.exists()
    counts, start = {}, time.time()
    with open(MANIFEST, "a", encoding="utf-8", newline="") as mf:
        w = csv.writer(mf, delimiter="\t")
        if new:
            w.writerow(FIELDS)
        with ThreadPoolExecutor(WORKERS) as pool:
            futures = [pool.submit(fetch, t) for t in todo]
            for n, fut in enumerate(as_completed(futures), start=1):
                t, status, kind, url, ts, path, size, tries = fut.result()
                key = status if status != "ok" else f"ok-{kind}"
                counts[key] = counts.get(key, 0) + 1
                with lock:
                    w.writerow([t["source"], t["folder"], t["section"], t["doc"], status, kind, url, ts,
                                path, size, tries, time.strftime("%Y-%m-%dT%H:%M:%S")])
                    mf.flush()
                if n % 100 == 0 or n == len(todo):
                    rate = n / max(1, time.time() - start)
                    eta = (len(todo) - n) / max(rate, 1e-9) / 60
                    print(f"{n:>6,}/{len(todo):,}  {dict(sorted(counts.items()))}  {rate:.2f} docs/s  ~{eta:.0f} min left", flush=True)
    print("finished", dict(sorted(counts.items())), flush=True)


if __name__ == "__main__":
    main()
