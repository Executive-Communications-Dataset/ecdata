"""Turn the downloaded pages and PDFs into tables.

    data/documents.{parquet,csv}  one row per recovered document, with its text
    data/catalogue.{parquet,csv}  every document the library's listings and file
                                  pages say exists, with its date and title,
                                  and whether its text was recovered
    data/missing.csv              catalogue entries with no recovered text
    data/no_text.csv              downloads with no text in them: empty section
                                  pages, and PDFs that are page images

`executive` is the president whose section of the library a document is in --
who spoke -- not something inferred from the date. `date` is taken, in order of
preference, from the library's own catalogue entry for the document, the
document's title, its dateline, its URL, the page's publication date, and
finally the year folder it sits in; `date_source` says which.
"""
import csv, gzip, pathlib, re, sys, urllib.parse
from datetime import date

import polars as pl
from bs4 import BeautifulSoup

BASE = pathlib.Path(__file__).resolve().parents[1]
RAW, DATA = BASE / "raw", BASE / "data"
sys.path.insert(0, str(BASE / "scraper"))
from targets import canonical_path  # noqa: E402

EXECUTIVES = {
    "jose-sarney": "José Sarney", "fernando-collor": "Fernando Collor",
    "itamar-franco": "Itamar Franco", "fernando-henrique-cardoso": "Fernando Henrique Cardoso",
    "luiz-inacio-lula-da-silva": "Luiz Inácio Lula da Silva",
    "luiz-inacio-lula-da-silva-ii": "Luiz Inácio Lula da Silva",
    "lula-planalto": "Luiz Inácio Lula da Silva", "dilma-rousseff": "Dilma Rousseff",
    "michel-temer": "Michel Temer", "bolsonaro": "Jair Bolsonaro",
    "getulio-vargas": "Getúlio Vargas", "jk": "Juscelino Kubitschek", "joao-goulart": "João Goulart",
    "castello-branco": "Humberto de Alencar Castello Branco", "costa-silva": "Artur da Costa e Silva",
    "emilio-medici": "Emílio Garrastazu Médici", "ernesto-geisel": "Ernesto Geisel",
    "jb-figueiredo": "João Baptista Figueiredo", "cafe-filho": "João Café Filho",
    "gaspar-dutra": "Eurico Gaspar Dutra", "washigton-luis": "Washington Luís",
    "rodrigues-alves": "Rodrigues Alves", "hermes-fonseca": "Hermes da Fonseca",
    "campos-salles": "Campos Sales", "affonso-penna": "Afonso Pena", "arthur-bernardes": "Artur Bernardes",
    "epitacio-pessoa": "Epitácio Pessoa", "delfim-moreira": "Delfim Moreira", "nilo-pecanha": "Nilo Peçanha",
    "venceslau-braz": "Venceslau Brás", "prudente-morais": "Prudente de Morais",
    "floriano-peixoto": "Floriano Peixoto", "deodoro-da-fonseca": "Deodoro da Fonseca",
    "jose-linhares": "José Linhares", "nereu-ramos": "Nereu Ramos", "carlos-luz": "Carlos Luz",
    "janio-quadros": "Jânio Quadros", "ranieri-mazzilli": "Ranieri Mazzilli",
}
# Terms in office; a document may come from up to PRE_TERM days before a term,
# as president-elect. A candidate date outside the speaker's terms is passed over.
from datetime import timedelta
TERMS = {
    "José Sarney": [("1985-03-15", "1990-03-15")],
    "Fernando Collor": [("1990-03-15", "1992-12-29")],
    "Itamar Franco": [("1992-10-02", "1995-01-01")],
    "Fernando Henrique Cardoso": [("1995-01-01", "2003-01-01")],
    "Luiz Inácio Lula da Silva": [("2003-01-01", "2011-01-01"), ("2023-01-01", "2030-01-01")],
    "Dilma Rousseff": [("2011-01-01", "2016-08-31")],
    "Michel Temer": [("2016-05-12", "2019-01-01")],
    "Jair Bolsonaro": [("2019-01-01", "2023-01-01")],
}
PRE_TERM = 92

# Dates no rule can recover, set by hand with the reason. Reviewed, not derived.
DATE_OVERRIDES = {
    # dateline reads "05 de setembro de 2015"; Temer was in Xiamen for the BRICS
    # summit of 3-5 September 2017, and was not president in 2015
    "michel-temer/entrevistas-concedidas-pelo-presidente-michel-temer/entrevista-coletiva-concedida-pelo-presidente-da-republica-michel-temer-na-saida-do-hotel-xiamen-china":
        (date(2017, 9, 5), "BRICS summit in Xiamen, 3-5 September 2017"),
}


def in_term(executive, d):
    spans = TERMS.get(executive)
    if not spans or d is None:
        return True
    return any(date.fromisoformat(a) - timedelta(days=PRE_TERM) <= d <= date.fromisoformat(b) for a, b in spans)


def any_date(s):
    """A date written out in words or as digits, whichever comes first."""
    d = long_date(s)
    m = NUM.search(s or "")
    n = mk(m.group(3), m.group(2), m.group(1)) if m else None
    return d or n


TYPES = [(r"entrevist", "Interview"), (r"mensage", "Message to Congress"),
         (r"notas-oficiais", "Official note"), (r"artigos", "Article"),
         (r"programas?-de-radio|cafe-com|cafe-presidenta|conversa", "Radio programme or column"),
         (r"pronunciament", "Pronouncement"), (r"discurs|dis-cursos|^\d{4}$|ultimos", "Speech")]

MONTHS = {m: i + 1 for i, m in enumerate("janeiro fevereiro março abril maio junho julho agosto "
                                         "setembro outubro novembro dezembro".split())}
MONTHS.update({"marco": 3, "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6, "jul": 7,
               "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12})
LONG = re.compile(r"\b(\d{1,2})\s*[º°o]?\s*(?:de\s+)?(" + "|".join(sorted(MONTHS, key=len, reverse=True))
                  + r")\.?\s+(?:de\s+)?(\d{4})\b", re.I)
SLUG_LONG = re.compile(r"\b(\d{1,2})-de-(" + "|".join(MONTHS) + r")-de-(\d{4})\b", re.I)
NUM = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b")
YEAR_DIR = re.compile(r"/((?:18|19|20)\d{2})(?:-\d)?(?:/|$)")
COVER = re.compile(r"^\s*Presidência da República\s+Casa Civil\s+Secretaria de Administração\s+Diretoria de "
                   r"Gestão de Pessoas\s+Coordenação\s*[–-]\s*Geral de Documentação e Informação\s+"
                   r"Coordenação de Biblioteca\s*", re.S)


def mk(y, m, d):
    try:
        return date(int(y), int(m), int(d)) if 1800 < int(y) < 2100 else None
    except (ValueError, TypeError):
        return None


def long_date(s, last=False):
    ms = list(LONG.finditer(s or ""))
    for m in (reversed(ms) if last else ms):
        d = mk(m.group(3), MONTHS[m.group(2).lower()], m.group(1))
        if d:
            return d
    return None


def slug_date(path):
    tail = urllib.parse.unquote(path).rsplit("/", 2)[-2:]
    for part in reversed(tail):
        m = SLUG_LONG.search(part)
        if m:
            return mk(m.group(3), MONTHS[m.group(2).lower()], m.group(1))
        m = NUM.search(part)
        if m:
            return mk(m.group(3), m.group(2), m.group(1))
    return None


def year_dir(path):
    m = YEAR_DIR.findall(path)
    return int(m[-1]) if m else None


def doc_type(section, path):
    s = f"{section} {path}".lower()
    for pat, name in TYPES:
        if re.search(pat, section or "") or (name == "Pronouncement" and "pronunciamento" in path.lower()):
            return name
    return "Other"


def text_of(node):
    for bad in node.select("script, style, nav, .documentActions, #viewlet-social-like, .visualClear"):
        bad.decompose()
    t = node.get_text("\n", strip=True)
    return re.sub(r"[ \t ]+", " ", re.sub(r"\n{3,}", "\n\n", t)).strip()


def parse_html(raw, source):
    soup = BeautifulSoup(raw, "lxml")
    h1 = soup.select_one("h1.documentFirstHeading") or soup.select_one("h1")
    title = h1.get_text(" ", strip=True) if h1 else (soup.title.get_text(strip=True) if soup.title else "")
    desc = soup.select_one(".documentDescription")
    body = soup.select_one("#parent-fieldname-text") or soup.select_one("[property='rnews:articleBody']")
    core = soup.select_one("#content-core") or soup.select_one("#content")
    published = None
    pub = soup.select_one(".documentPublished") or soup.select_one(".documentModified")
    if pub:
        m = NUM.search(pub.get_text(" ", strip=True))
        published = mk(m.group(3), m.group(2), m.group(1)) if m else None
    items = []
    for tile in (core.select(".tileItem") if core else []):
        a = tile.select_one(".tileHeadline a[href]") or tile.select_one("a[href]")
        if a:
            items.append((a.get_text(" ", strip=True), a["href"]))
    if core and not items:
        for a in core.select("table.listing a[href], dl.entries dt a[href], .entries a[href]"):
            items.append((a.get_text(" ", strip=True), a["href"]))
    files = [a["href"] for a in (core.select("a[href]") if core else []) if ".pdf" in a["href"].lower()]
    text = text_of(body) if body else ""
    return dict(title=title, description=desc.get_text(" ", strip=True) if desc else "",
                text=text, published=published, items=items, files=files)


def ocr_pdf(path):
    """Text of a PDF made of page images, by the OCR built into macOS. Cached."""
    import hashlib
    cache = RAW / "ocr" / (hashlib.sha1(str(path).encode()).hexdigest()[:16] + ".txt")
    if cache.exists():
        return cache.read_text()
    import pypdfium2 as pdfium
    from ocrmac import ocrmac
    pdf = pdfium.PdfDocument(str(path))
    pages = []
    for page in pdf:
        img = page.render(scale=3).to_pil()
        lines = ocrmac.OCR(img, language_preference=["pt-BR"], recognition_level="accurate").recognize()
        pages.append("\n".join(l[0] for l in lines))
    text = "\n".join(pages)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(text)
    return text


def letter_spaced(text):
    """pypdf reads some fonts with a space after every letter: "C o p y r i g h t"."""
    toks = text.split()
    return len(toks) > 100 and sum(len(t) == 1 and t.isalpha() for t in toks) / len(toks) > 0.5


def parse_pdf(path):
    """(text, pages, error, how): the PDF's own text layer, or OCR where it has none."""
    from pypdf import PdfReader
    try:
        r = PdfReader(str(path))
        pages = [p.extract_text() or "" for p in r.pages]
        text = "\n".join(pages)
        if letter_spaced(text):                  # pdfium reads the same text layer without the spaces
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(str(path))
            text = "\n".join(pdf[i].get_textpage().get_text_range() for i in range(len(pdf)))
        if len(text.strip()) < 100 and len(pages):
            try:
                return ocr_pdf(path), len(pages), "", "ocr"
            except Exception as e:
                return text, len(pages), f"ocr: {type(e).__name__}", "pdf text layer"
        return text, len(pages), "", "pdf text layer"
    except Exception as e:                       # truncated or broken capture
        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                pages = [p.extract_text() or "" for p in pdf.pages]
            return "\n".join(pages), len(pages), "", "pdf text layer"
        except Exception as e2:
            return "", 0, f"{type(e).__name__}; {type(e2).__name__}", ""


def lib_doc_path(href):
    m = re.search(r"/presidencia/ex-presidentes/(.+)$", href)
    return canonical_path(m.group(1)) if m else None


def main():
    DATA.mkdir(exist_ok=True)
    # every real download, from both archives: per document, a PDF over a page,
    # and the Internet Archive's copy over Common Crawl's
    man = []
    with open(RAW / "manifest.tsv", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["status"] == "ok":
                man.append({**r, "archive": "Internet Archive",
                            "archive_url": f"https://web.archive.org/web/{r['used_ts']}/{r['used_url']}"})
    if (RAW / "manifest_cc.tsv").exists():
        with open(RAW / "manifest_cc.tsv", encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                if r["status"] == "ok":
                    man.append({**r, "archive": "Common Crawl", "used_url": r["url"], "used_ts": r["crawl"],
                                "archive_url": f"commoncrawl:{r['crawl']}:{r['warc']}"})
    rank = lambda r: (r["kind"] != "pdf", r["archive"] != "Internet Archive")
    best = {}
    for r in sorted(man, key=rank):
        best.setdefault((r["source"], r["doc"]), r)
    man = list(best.values())

    docs, catalogue, failures = [], [], []
    for r in man:
        path = pathlib.Path(r["path"])
        folder, section, doc = r["folder"], r["section"], r["doc"]
        base = dict(source=r["source"], folder=folder, section=section, doc=doc,
                    executive=EXECUTIVES.get(folder, folder.replace("-", " ").title()),
                    type=doc_type(section, doc), original_url=r["used_url"], archive=r["archive"],
                    archive_url=r["archive_url"], archive_timestamp=r["used_ts"],
                    raw_path=str(path.relative_to(BASE)))
        if r["kind"] == "pdf":
            text, n_pages, err, how = parse_pdf(path)
            if err:
                failures.append(dict(doc=doc, error=err))
            text = COVER.sub("", text).strip()
            docs.append({**base, "kind": "pdf", "title": "", "page_title": "", "n_pages": n_pages,
                         "text": text, "published": None, "pdf_error": err, "text_source": how})
            continue
        raw = gzip.decompress(path.read_bytes()).decode("utf-8", "replace")
        p = parse_html(raw, r["source"])
        for title, href in p["items"]:             # a listing: the library's catalogue of a folder
            target = lib_doc_path(href) if r["source"] == "biblioteca" else None
            catalogue.append(dict(executive=base["executive"], folder=folder, section=section,
                                  listed_in=doc, doc=target, title=title,
                                  date=long_date(title) or slug_date(target or ""), via="listing"))
        is_file_page = doc.lower().endswith(".pdf") or (p["files"] and len(p["text"]) < 200 and not p["items"])
        if is_file_page and not p["items"]:        # Plone's page around a PDF: metadata, no text
            catalogue.append(dict(executive=base["executive"], folder=folder, section=section,
                                  listed_in=doc, doc=doc, title=p["title"],
                                  date=long_date(p["title"]) or slug_date(doc), via="file page"))
            continue
        if p["items"] and len(p["text"]) < 500:
            continue                                # a listing, not a document
        docs.append({**base, "kind": "html", "title": p["title"], "page_title": p["title"],
                     "n_pages": None, "text": (p["description"] + "\n\n" + p["text"]).strip()
                     if p["description"] and p["description"] not in p["text"] else p["text"],
                     "published": p["published"], "pdf_error": "", "text_source": "html"})

    cat = pl.DataFrame(catalogue, infer_schema_length=None) if catalogue else pl.DataFrame()
    cat_dates = {}
    if cat.height:
        cat = cat.unique(subset=["doc", "title"], keep="first", maintain_order=True)
        for d, t, dt in cat.filter(pl.col("doc").is_not_null()).select("doc", "title", "date").iter_rows():
            if d not in cat_dates or (cat_dates[d][1] is None and dt is not None):
                cat_dates[d] = (t, dt)

    out = []
    for d in docs:
        title_cat, date_cat = cat_dates.get(d["doc"], ("", None))
        title = d["title"] or title_cat
        head = d["text"][:600]
        candidates = [("catalogue", date_cat), ("title", any_date(title)), ("dateline", long_date(head)),
                      ("url", slug_date(d["doc"])), ("published", d["published"]),
                      ("dateline at end", long_date(d["text"][-400:], last=True))]
        found = [(v, k) for k, v in candidates if v]
        when, source = next(((v, k) for v, k in found if in_term(d["executive"], v)), (None, ""))
        flag = ""
        yd = year_dir(d["doc"])
        override = next((v for k, v in DATE_OVERRIDES.items() if d["doc"].endswith(k)), None)
        if override:
            when, source = override[0], f"set by hand: {override[1]}"
        elif when is None and found:
            v, k = found[0]
            shifted = [mk(y, v.month, v.day) for y in ([yd] if yd else []) + [v.year + 1]]
            fix = next((x for x in shifted if x and in_term(d["executive"], x)), None)
            if fix:
                # the year folder, or a dateline written with the year before -- common in January
                when, source = fix, f"{k}, year from {'folder' if yd and fix.year == yd else 'the next year'}"
            else:
                when, source, flag = v, k, "outside term"
        if when is None and d["type"] == "Message to Congress":
            m = re.search(r"\b(19[89]\d|20[0-3]\d)\b", f"{title} {d['doc']}")
            opening = date(int(m.group(1)), 2, 2) if m else None
            if opening and in_term(d["executive"], opening):   # delivered when Congress opens its year
                when, source = opening, "opening of Congress (2 February)"
        if when is None and yd:
            when, source = date(yd, 1, 1), "year folder"
        out.append({**d, "title": title, "date": when, "date_source": source, "date_flag": flag,
                    "year_folder": yd, "n_chars": len(d["text"]), "n_words": len(d["text"].split())})

    df = pl.DataFrame(out, infer_schema_length=None)
    df = df.sort(["executive", "date"], nulls_last=True)
    cols = ["executive", "date", "date_source", "date_flag", "type", "title", "text", "n_words", "n_chars", "kind", "text_source",
            "n_pages", "section", "doc", "source", "original_url", "archive", "archive_url", "archive_timestamp",
            "raw_path", "year_folder", "published", "pdf_error"]
    df = df.select(cols)
    empty = df.filter(pl.col("n_chars") < 200)
    empty.drop("text").write_csv(DATA / "no_text.csv")
    df = df.filter(pl.col("n_chars") >= 200)
    df.write_parquet(DATA / "documents.parquet")
    df.drop("text").write_csv(DATA / "documents_index.csv")
    df.write_csv(DATA / "documents.csv")

    if cat.height:
        have = set(df["doc"].to_list())
        cat = cat.with_columns(recovered=pl.col("doc").is_in(list(have)))
        cat.write_parquet(DATA / "catalogue.parquet")
        cat.write_csv(DATA / "catalogue.csv")
        cat.filter(~pl.col("recovered")).write_csv(DATA / "missing.csv")

    print(f"{df.height:,} documents with text, {empty.height:,} downloads without, "
          f"{cat.height:,} catalogue entries, {len(failures)} unreadable PDFs")
    with pl.Config(tbl_rows=40):
        print(df.group_by("executive").agg(pl.len().alias("docs"),
                                           pl.col("n_words").sum().alias("words"), pl.col("date").min().alias("first"),
                                           pl.col("date").max().alias("last")).sort("first", nulls_last=True))


if __name__ == "__main__":
    main()
