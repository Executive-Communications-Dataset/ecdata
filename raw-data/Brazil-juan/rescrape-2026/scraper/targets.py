"""Choose what to fetch from the Internet Archive's capture lists in raw/index/.

Presidency Library (biblioteca.presidencia.gov.br/presidencia/ex-presidentes/):
every president, the sections that hold the president's own words -- speeches,
statements, interviews, messages to Congress, official notes, articles, radio
programmes. Planalto (gov.br/planalto/.../discursos-e-pronunciamentos/<year>/):
Lula's current term.

The library served the archive's crawler an anti-bot challenge some of the
time, so one capture per URL is not enough: each document gets every capture
the archive holds, in the order most likely to be the real thing -- a PDF for a
PDF, then the largest HTML first. fetch.py walks that list until a capture
turns out to be real.

URL variants of one document are merged first: Plone's `/view` wrapper and
`@@download` address, junk a
broken link left on the end (`%3E`, `.`), and mistyped president folders
(`luiz-inacio-lula-dasilva`).

Writes raw/targets.tsv: one row per document, with its candidate captures.
"""
import pathlib, re, urllib.parse
import polars as pl

BASE = pathlib.Path(__file__).resolve().parents[1]
IDX = BASE / "raw" / "index"
COLS = ["urlkey", "ts", "url", "mime", "length", "digest"]

TEXT_SECTIONS = re.compile(
    r"discurs|dis-cursos|pronunciament|entrevist|mensage|notas-oficiais|artigos|"
    r"programas?-de-radio|cafe-com|cafe-presidenta|conversa-(com-a-)?presidenta", re.I)
LIB = re.compile(r"^https?://(www\.)?biblioteca\.presidencia\.gov\.br(:80)?/presidencia/ex-presidentes/", re.I)
PLA = re.compile(r"^https?://(www\.)?gov\.br/planalto/pt-br/acompanhe-o-planalto/discursos-e-pronunciamentos/", re.I)
MAX_TRIES = 3

# Presidents the dataset covers, fetched first; the rest of the archive after.
PRIORITY = ["jose-sarney", "fernando-collor", "itamar-franco", "fernando-henrique-cardoso",
            "luiz-inacio-lula-da-silva", "luiz-inacio-lula-da-silva-ii", "dilma-rousseff",
            "michel-temer", "bolsonaro", "lula-planalto"]


def read(name):
    rows = [l.rstrip("\n").split(" ") for l in open(IDX / name, encoding="utf-8") if l.strip()]
    return pl.DataFrame([r[:6] for r in rows if len(r) >= 6], schema=COLS, orient="row").with_columns(
        pl.col("length").cast(pl.Int64, strict=False).fill_null(0))


def squash(s):
    return re.sub(r"[^a-z0-9]", "", urllib.parse.unquote(s).lower())


def edit1(a, b):
    """True if a and b differ by at most one inserted, deleted or changed letter."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) <= 1
    if len(a) > len(b):
        a, b = b, a
    return any(a == b[:i] + b[i + 1:] for i in range(len(b)))


def canonical_path(path):
    path = urllib.parse.unquote(path)
    path = re.sub(r"[?#].*$", "", path)
    path = re.sub(r"/(@@download|at_download|@@images|image_view_fullscreen)(/.*)?$", "", path)  # Plone's file URLs
    path = re.sub(r"(/view)[^/]*$", "", path)          # Plone's wrapper page, and junk after it
    path = re.sub(r"[\s.>)\]\"',;:]+$", "", path)        # what a broken link left behind
    return path.rstrip("/")


def main():
    lib = read("captures_biblioteca.tsv").filter(pl.col("url").str.contains(LIB.pattern))
    lib = lib.with_columns(path=pl.col("url").str.replace(LIB.pattern, ""), source=pl.lit("biblioteca"))
    lib = lib.with_columns(folder=pl.col("path").str.extract(r"^([^/]+)"),
                           section=pl.col("path").str.extract(r"^[^/]+/([^/?#]+)"))
    lib = lib.filter(pl.col("section").str.contains(TEXT_SECTIONS.pattern))

    # mistyped president folders -> the real one, when one letter apart after squashing
    counts = lib.group_by("folder").len()
    real = [f for f, n in counts.rows() if n >= 50]
    fix = {}
    for f, _ in counts.rows():
        sf = squash(f)
        for r in real:
            if f != r and (sf == squash(r) or edit1(sf, squash(r))):
                fix[f] = r
    lib = lib.with_columns(folder=pl.col("folder").replace(fix))
    lib = lib.with_columns(path=pl.concat_str([pl.col("folder"), pl.col("path").str.replace(r"^[^/]+", "")]))

    pla = read("captures_planalto.tsv").filter(pl.col("url").str.contains(PLA.pattern))
    pla = pla.with_columns(path=pl.col("url").str.replace(PLA.pattern, ""), source=pl.lit("planalto"))
    pla = pla.with_columns(folder=pl.lit("lula-planalto"), section=pl.col("path").str.extract(r"^(\d{4}|ultimos-discursos)"))
    pla = pla.filter(pl.col("section").is_not_null())

    c = pl.concat([lib, pla], how="vertical_relaxed")
    c = c.filter(pl.col("mime").is_in(["text/html", "application/pdf"]))
    c = c.with_columns(doc=pl.col("path").map_elements(canonical_path, return_dtype=pl.String))
    c = c.with_columns(is_pdf_doc=pl.col("doc").str.to_lowercase().str.ends_with(".pdf"),
                       is_view=pl.col("path").str.contains(r"/view"))
    # preference: for a PDF document, real PDF bytes first; then the largest HTML
    c = c.with_columns(rank=pl.when(pl.col("mime") == "application/pdf").then(0).otherwise(1))
    c = c.sort(["source", "doc", "rank", "length"], descending=[False, False, False, True])
    c = c.unique(subset=["source", "doc", "digest"], keep="first", maintain_order=True)

    docs = c.group_by(["source", "folder", "section", "doc"], maintain_order=True).agg(
        is_pdf_doc=pl.col("is_pdf_doc").first(),
        has_pdf_capture=(pl.col("mime") == "application/pdf").any(),
        n_captures=pl.len(),
        cand_ts=pl.col("ts").head(MAX_TRIES).str.join("|"),
        cand_url=pl.col("url").head(MAX_TRIES).str.join("|"),
        cand_mime=pl.col("mime").head(MAX_TRIES).str.join("|"),
    )
    # A speech published as a PDF has no text unless the archive holds the PDF
    # itself: its other captures are Plone's /view wrapper or the challenge.
    docs = docs.with_columns(fetch=~(pl.col("is_pdf_doc") & ~pl.col("has_pdf_capture")),
                             priority=pl.col("folder").replace_strict(
                                 {f: i for i, f in enumerate(PRIORITY)}, default=len(PRIORITY)))
    docs = docs.sort(["priority", "folder", "doc"])
    docs.write_csv(BASE / "raw" / "targets.tsv", separator="\t")
    print(f"to fetch: {docs['fetch'].sum():,} documents; recorded as not archived without fetching: "
          f"{(~docs['fetch']).sum():,}")

    print(f"{c.height:,} captures of {docs.height:,} documents ({len(fix)} mistyped folders merged)")
    with pl.Config(tbl_rows=30):
        print(docs.group_by("source", "is_pdf_doc", "has_pdf_capture").len().sort("len", descending=True))
        print(docs.group_by("folder").agg(pl.len(), pl.col("is_pdf_doc").sum().alias("pdf_docs"),
                                          pl.col("has_pdf_capture").sum().alias("pdf_captured"))
              .sort("len", descending=True).head(22))


if __name__ == "__main__":
    main()
