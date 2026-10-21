"""Build brazil.parquet for the Executive Communications Dataset.

    python scraper/build_ecd.py

Only the eight presidents since the return to democracy are kept -- Sarney,
Collor, Itamar Franco, Fernando Henrique Cardoso, Lula, Dilma Rousseff, Temer
and Bolsonaro.

1. The rescrape (data/documents.parquet) is reduced to those eight, and a
   speech that came more than once -- as a PDF and as a page, or from both the
   library and Planalto -- is kept once, the most complete copy.
2. Every row of the release it replaces (reference/brazil.parquet) is matched
   against the rescrape by its text. A row the rescrape also has is replaced by
   the rescrape's copy; a row it lacks is kept, so nothing the dataset already
   had is lost. Kept rows with no executive get one: Lula for 2023-24, Collor
   for the 1990-91 PDF volumes, whose text names him.
3. The result is put on the dataset's 17 documented columns, and three things
   the release's validator holds every country to are applied:
   * Collor's speeches of January and February 1991 carry the year 1990 in
     1.0.7 -- a ninth cabinet meeting, his first message to Congress, the
     Antarctic visit, a speech that says "em 1991" -- and are moved to 1991.
   * A document dated only to its year folder has no date, and the year in
     year_of_statement, rather than an invented 1 January.
   * A document from before its speaker took office -- as president-elect -- is
     left out: the dataset credits each period to the executive in office.
     They are listed in build/before_taking_office.csv.
4. The defects 1.0.7's rows carry are repaired by repair_kept.py -- broken
   words, the press office's header on Lula's PDFs, the editors' notes in
   Sarney's volumes, titles, types and dates; its docstring lists each rule.

Writes build/brazil.parquet and build/report.md.
"""
import pathlib, re, sys, unicodedata
from collections import defaultdict
from datetime import date, datetime, timezone

import polars as pl

BASE = pathlib.Path(__file__).resolve().parents[1]
OUT = BASE / "build"
sys.path.insert(0, str(BASE / "scraper"))

EIGHT = ["José Sarney", "Fernando Collor", "Itamar Franco", "Fernando Henrique Cardoso",
         "Luiz Inácio Lula da Silva", "Dilma Rousseff", "Michel Temer", "Jair Bolsonaro"]
# the release's spellings -> the rescrape's
OLD_NAMES = {"Lula da Silva": "Luiz Inácio Lula da Silva"}
SAME = 0.5               # share of shingles two texts must share to be one speech
SHINGLE, HEAD = 5, 600   # word 5-grams over the first 600 words

COUNTRY = dict(country="Brazil", language="Portuguese", file=None, isonumber=76.0, gwc="BRA",
               cowcodes="BRA", polity_v="BRA", polity_iv="BRA", vdem=19.0, office=None)
COLUMNS = ["country", "url", "text", "date", "title", "executive", "type", "language", "file",
           "isonumber", "gwc", "cowcodes", "polity_v", "polity_iv", "vdem", "year_of_statement", "office"]


def words(text):
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"(\w)-\s+(\w)", r"\1\2", t)          # rejoin words broken across a line
    return re.findall(r"[a-z]+", t)


def shingles(text):
    w = words(text)[:HEAD]
    return {" ".join(w[i:i + SHINGLE]) for i in range(max(0, len(w) - SHINGLE + 1))}


def overlap(a, b):
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


class Index:
    """Find, among many texts, the ones that share most shingles with a given text."""
    def __init__(self):
        self.sets, self.post = [], defaultdict(set)

    def add(self, s):
        i = len(self.sets)
        self.sets.append(s)
        for g in s:
            self.post[g].add(i)
        return i

    def best(self, s):
        hits = defaultdict(int)
        for g in s:
            for i in self.post.get(g, ()):
                hits[i] += 1
        if not hits:
            return None, 0.0
        i = max(hits, key=lambda k: hits[k] / max(1, min(len(s), len(self.sets[k]))))
        return i, overlap(s, self.sets[i])


def main():
    OUT.mkdir(exist_ok=True)
    new = pl.read_parquet(BASE / "data" / "documents.parquet").filter(pl.col("executive").is_in(EIGHT))
    # a "message to Congress" page of a few lines is a link to the message, not the message
    stubs = new.filter((pl.col("type") == "Message to Congress") & (pl.col("n_words") < 300))
    new = new.filter(~((pl.col("type") == "Message to Congress") & (pl.col("n_words") < 300)))
    # most complete first, a page over a PDF on a tie (no page furniture to strip)
    new = new.sort(["n_words", "kind"], descending=[True, False])

    # 1. one copy per speech within the rescrape
    keep, idx_by_exec, dropped_dupes, row_of = [], defaultdict(Index), 0, {}
    for r in new.iter_rows(named=True):
        s = shingles(r["text"])
        ix = idx_by_exec[r["executive"]]
        i, score = ix.best(s)
        if i is not None and score >= SAME:
            dropped_dupes += 1
            continue
        row_of[(r["executive"], ix.add(s))] = len(keep)
        keep.append(r)
    new = pl.DataFrame(keep, infer_schema_length=None)

    # 2. the release it replaces, matched against the rescrape
    old = pl.read_parquet(BASE / "reference" / "brazil.parquet")
    old = old.with_columns(executive=pl.col("executive").replace(OLD_NAMES))
    old = old.with_columns(executive=pl.when(pl.col("executive").is_not_null()).then(pl.col("executive"))
                           .when(pl.col("date") >= datetime(2023, 1, 1, tzinfo=timezone.utc)).then(pl.lit("Luiz Inácio Lula da Silva"))
                           # the 1990-91 rows from a PDF volume are Collor's: 165 of the 170 name him
                           .when(pl.col("url").is_null() & pl.col("file").is_not_null()
                                 & pl.col("date").dt.year().is_between(1990, 1991)).then(pl.lit("Fernando Collor"))
                           .otherwise(None))
    match, borrowed = [], 0
    for r in old.iter_rows(named=True):
        ix = idx_by_exec.get(r["executive"])
        i, score = ix.best(shingles(r["text"])) if ix else (None, 0.0)
        match.append(score >= SAME)
        if score >= SAME and r["date"] is not None:
            k = keep[row_of[(r["executive"], i)]]
            # an undated speech, or one dated only to its year, takes 1.0.7's date
            if k["date"] is None or k["date_source"] == "year folder":
                k["date"], k["date_source"] = r["date"].date(), "1.0.7"
                borrowed += 1
    old = old.with_columns(in_rescrape=pl.Series(match))
    carried = old.filter(~pl.col("in_rescrape") & pl.col("executive").is_in(EIGHT))
    unplaced = old.filter(pl.col("executive").is_null())

    # 3. the dataset's columns
    to_ts = lambda d: datetime(d.year, d.month, d.day, tzinfo=timezone.utc) if d else None
    year_only = lambda r: r["date_source"] == "year folder"
    fresh = pl.DataFrame([{
        **COUNTRY, "url": r["original_url"], "text": r["text"],
        "date": None if year_only(r) else to_ts(r["date"]),
        "title": r["title"] or None, "executive": r["executive"], "type": r["type"],
        "year_of_statement": float(r["date"].year) if r["date"] else (float(r["year_folder"]) if r["year_folder"] else None),
    } for r in keep], schema_overrides={"date": pl.Datetime("us", "UTC")})       # keep holds the borrowed dates
    kept = carried.select(COLUMNS)
    out = pl.concat([fresh.select(COLUMNS).cast(kept.schema).with_columns(kept=pl.lit(False)),
                     kept.with_columns(kept=pl.lit(True))], how="vertical")

    # Collor's January-February 1991, dated 1990 in 1.0.7
    collor_jan_feb = ((pl.col("executive") == "Fernando Collor")
                      & (pl.col("date") >= datetime(1990, 1, 1, tzinfo=timezone.utc))
                      & (pl.col("date") < datetime(1990, 3, 1, tzinfo=timezone.utc)))
    moved = out.filter(collor_jan_feb).height
    out = out.with_columns(date=pl.when(collor_jan_feb).then(pl.col("date").dt.offset_by("1y")).otherwise(pl.col("date")))
    out = out.with_columns(year_of_statement=pl.when(pl.col("date").is_not_null())
                           .then(pl.col("date").dt.year().cast(pl.Float64)).otherwise(pl.col("year_of_statement")),
                           title=pl.when(pl.col("title").str.strip_chars().is_in(["()", ""])).then(None).otherwise(pl.col("title")))

    # nothing from before its speaker took office
    from parse import TERMS
    start = {e: datetime.fromisoformat(s[0][0]).replace(tzinfo=timezone.utc) for e, s in TERMS.items()}
    before = out.filter(pl.col("date") < pl.col("executive").replace_strict(start, return_dtype=pl.Datetime("us", "UTC")))
    before.write_csv(OUT / "before_taking_office.csv")
    out = out.join(before.select("url", "date", "executive", "text"), on=["url", "date", "executive", "text"],
                   how="anti", nulls_equal=True)
    # 4. repairs
    from repair_kept import repair
    # PDF text: from a PDF -- 75 of the rescrape's are served at a url without
    # ".pdf" -- or laid out like one: some of 1.0.7's library pages hold a PDF's
    # text, with a double space wherever a line ended
    pdf_urls = new.filter(pl.col("kind") == "pdf")["original_url"].to_list()
    out = out.with_columns(pdf=pl.col("url").is_null() | pl.col("url").str.to_lowercase().str.contains(r"\.pdf")
                           | pl.col("url").is_in(pdf_urls)
                           | (pl.col("text").str.count_matches("  ") > pl.col("text").str.len_chars() / 200))
    clean = out.filter(~pl.col("pdf"))["text"].to_list()
    out, repairs, _, date_changes, shrunk = repair(out, clean)
    out = out.drop("kept", "pdf").sort(["date", "executive"], nulls_last=True)
    out.write_parquet(OUT / "brazil.parquet")

    # report
    by = lambda df, name: df.group_by("executive").len().rename({"len": name})
    t = (by(old.filter(pl.col("executive").is_in(EIGHT)), "1.0.7 rows")
         .join(by(old.filter(pl.col("in_rescrape")), "replaced by rescrape"), on="executive", how="full", coalesce=True)
         .join(by(carried, "kept from 1.0.7"), on="executive", how="full", coalesce=True)
         .join(by(fresh, "from rescrape"), on="executive", how="full", coalesce=True)
         .join(by(out, "new total"), on="executive", how="full", coalesce=True)
         .fill_null(0))
    order = {e: i for i, e in enumerate(EIGHT)}
    t = t.with_columns(o=pl.col("executive").replace_strict(order, default=99)).sort("o").drop("o")
    years = (out.group_by(pl.col("year_of_statement").cast(pl.Int32).alias("year")).len().rename({"len": "new"})
             .join(old.group_by(pl.col("date").dt.year().alias("year")).len().rename({"len": "1.0.7"}),
                   on="year", how="full", coalesce=True).fill_null(0).sort("year", nulls_last=True))
    lines = ["# Brazil rebuild", "",
             f"{out.height:,} rows. Before repairs: {fresh.height:,} from the rescrape and {carried.height:,} kept from 1.0.7; "
             f"the repairs then dropped {repairs['exact duplicates dropped']} exact duplicates and "
             f"{repairs['placeholder rows dropped']} placeholder. "
             f"{dropped_dupes:,} duplicate copies within the rescrape were dropped; "
             f"{borrowed:,} rescraped speeches with no full date took 1.0.7's; "
             f"{old.filter(pl.col('in_rescrape')).height:,} rows of 1.0.7 are replaced by the rescrape's copy of the same speech; "
             f"{unplaced.height:,} rows of 1.0.7 could not be given an executive and are left out; "
             f"{moved} of Collor's rows were moved from 1990 to 1991; "
             f"{before.height} documents from before their speaker took office are left out.", "",
             "| executive | " + " | ".join(t.columns[1:]) + " |", "|---|" + "---:|" * (len(t.columns) - 1)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in t.iter_rows()]
    lines += ["", "| year | 1.0.7 | new |", "|---|---:|---:|"]
    lines += [f"| {y if y is not None else 'no date or year'} | {o:,} | {n:,} |"
              for y, n, o in years.select("year", "new", "1.0.7").iter_rows()]
    lines += ["", "## Repairs", "", "To the rows kept from 1.0.7, and to the PDF text of the rescrape (line breaks, press-office header).",
              "", "| repair | count |", "|---|---:|"]
    lines += [f"| {k} | {v:,} |" for k, v in sorted(repairs.items())]
    lines += ["", "Dates changed:", ""] + [f"* {c[0]}: {c[1]} -> {c[2]} ({str(c[3])[-80:]})" for c in date_changes]
    (OUT / "report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:4]))
    with pl.Config(tbl_rows=20, tbl_width_chars=160):
        print(t)


if __name__ == "__main__":
    main()
