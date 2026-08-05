#!/usr/bin/env python3
"""ecd_repair.py -- rebuild a release from the published 1.0.0 assets.

Every fix here is derivable from the published parquet files alone: no re-scrape,
no access to the source sites. That is the whole design constraint. Defects that
need the raw HTML back (Colombia's provenance, Russia's translations, the
paragraph-vs-document grain, thin country coverage) are out of scope and stay open
against the pipeline.

    python ecd_repair.py --data-dir ./data --out-dir ./candidate --full-ecd
    python ecd_validate.py --data-dir ./candidate \\
           --full-ecd ./candidate/full_ecd.parquet --fail-on ERROR

What it fixes, and the issue each one closes:

  schema   #14  one set of 17 columns, documented dtypes, `date` as Datetime(us, UTC).
                Recovers portugal's `urls` and dominican_republic's `subject`, which
                hold real data under a non-canonical name.
  pooled   #10  dominican_republic and ecuador ship the same pooled corpus under
                swapped labels. Partitions it by source host and re-derives
                `executive` from the date, per country.
  dedupe   #12  exact duplicates on (country, url, text, date), ~82% of all rows.
  labels   --   country-level columns (country, isonumber, gwc, cowcodes, polity,
                vdem, language) that a partial join left null on some rows. Only
                brazil is affected in 1.0.0: 611 of its rows carry no country at
                all, which is why full_ecd cannot account for them.
  text     #16  UTF-8 decoded as latin-1, repaired where the round-trip is clean.
  url      #17  jamaica's doubled host prefix.
  names    #13  misspelled executives, the part of that issue that is a rename,
                plus brazil's `language` value ("Portugese"). The wrong handover
                dates and overlapping terms are NOT fixed here: they need a reviewed
                term table for every country, which belongs in the pipeline, not in
                a repair pass.
  full     #11  rebuilds full_ecd.parquet from the repaired country assets, so
                Portugal stops being one empty row and Ecuador appears once.

Not attempted: the all-null `file`/`office`/`language` columns (#19) and `type`
(#20). Both need a decision about what the column is for, not a transformation.
"""

import argparse
import pathlib
import sys
from datetime import datetime, timezone

import polars as pl

# --------------------------------------------------------------------------
# the published schema
# --------------------------------------------------------------------------

CANONICAL: dict[str, pl.DataType] = {
    "country": pl.String,
    "url": pl.String,
    "text": pl.String,
    "date": pl.Datetime("us", "UTC"),
    "title": pl.String,
    "executive": pl.String,
    "type": pl.String,
    "language": pl.String,
    "file": pl.String,
    "isonumber": pl.Float64,
    "gwc": pl.String,
    "cowcodes": pl.String,
    "polity_v": pl.String,
    "polity_iv": pl.String,
    "vdem": pl.Float64,
    "year_of_statement": pl.Float64,
    "office": pl.String,
}

# Columns holding canonical data under another name. Verified against 1.0.0:
# portugal has no `url` but a fully populated `urls`; dominican_republic has no
# `title` but `subject` holds the headline.
ALIASES = {"urls": "url", "subject": "title"}

DEDUPE_KEY = ["country", "url", "text", "date"]

# --------------------------------------------------------------------------
# repair tables -- REVIEW THESE. They encode judgements, not derivations.
# --------------------------------------------------------------------------

# Misspellings from the 1.0.0 audit. Left-hand side is what 1.0.0 ships.
EXECUTIVE_RENAMES = {
    "Jooseph R. Biden, Jr.": "Joseph R. Biden, Jr.",
    "Dmitry Medvedec": "Dmitry Medvedev",
    "Kyriakos Misotakis": "Kyriakos Mitsotakis",
    "Ioannis Samaras": "Ioannis Sarmas",
    "Poul Nyrup Rasumussen": "Poul Nyrup Rasmussen",
    "Christina Fernandez de Kirchner": "Cristina Fernández de Kirchner",
    "Iralki Garibashvili": "Irakli Garibashvili",
    "Jose Luis Rodriquez Zapatero": "José Luis Rodríguez Zapatero",
    "Andrew Manuel Lopez Obrador": "Andrés Manuel López Obrador",
}

# `language` as spelled in the data. The country dictionary shipped with both
# packages says "Portuguese"; brazil.parquet says "Portugese", so a filter written
# against the column rather than the dictionary returns nothing.
LANGUAGE_RENAMES = {"Portugese": "Portuguese"}

# Terms used to re-derive `executive` after the pooled corpus is split. Only the
# two countries involved in that split are listed: assigning executives anywhere
# else is the pipeline's job. Dates are inauguration dates; the interval is
# [start, next start).
TERMS = {
    "Dominican Republic": [
        ("2004-08-16", "Leonel Fernández"),
        ("2012-08-16", "Danilo Medina"),
        ("2020-08-16", "Luis Abinader"),
    ],
    "Ecuador": [
        ("2007-01-15", "Rafael Correa"),
        ("2017-05-24", "Lenín Moreno"),
        ("2021-05-24", "Guillermo Lasso"),
        ("2023-11-23", "Daniel Noboa"),
    ],
}

# Which source domain belongs to which country, for the pooled DR/Ecuador corpus.
# Matched as a suffix of the host, so `www.` and any other subdomain are covered --
# the corpus uses both `presidencia.gob.ec` and `www.presidencia.gob.ec`.
POOLED_DOMAINS = {
    "gobiernodanilomedina.do": "Dominican Republic",
    "comunicacion.gob.ec": "Ecuador",
    "presidencia.gob.ec": "Ecuador",
}
POOLED_FILES = {"dominican_republic": "Dominican Republic", "ecuador": "Ecuador"}

MOJIBAKE = "Ã|Â|â€"

# Columns that describe the country, not the document, so they must hold one value
# throughout a country asset. Where a join dropped some of them, the file's own
# surviving value fills the gap. Columns that are null for the *whole* file are a
# different problem (#19) and are left alone.
COUNTRY_LEVEL = ["country", "isonumber", "gwc", "cowcodes", "polity_v",
                 "polity_iv", "vdem", "language"]


class Report:
    def __init__(self):
        self.lines: list[str] = []
        self.changed = 0

    def note(self, scope, message, changed=0):
        self.lines.append(f"  {scope:<28} {message}")
        self.changed += changed

    def head(self, title):
        self.lines.append("")
        self.lines.append(title)

    def render(self):
        return "\n".join(self.lines) + "\n"


# --------------------------------------------------------------------------
# steps
# --------------------------------------------------------------------------

def canonicalise(lf: pl.LazyFrame) -> pl.LazyFrame:
    """Project onto CANONICAL: recover aliases, add what is missing, fix dtypes."""
    names = lf.collect_schema().names()
    renames = {src: dst for src, dst in ALIASES.items()
               if src in names and dst not in names}
    if renames:
        lf = lf.rename(renames)
        names = [renames.get(n, n) for n in names]

    missing = [c for c in CANONICAL if c not in names]
    if missing:
        lf = lf.with_columns([pl.lit(None, dtype=CANONICAL[c]).alias(c)
                              for c in missing])
    return lf.select([pl.col(c).cast(dtype) for c, dtype in CANONICAL.items()])


def split_pooled(frames: dict[str, pl.LazyFrame], rep: Report) -> None:
    """Undo the pooled DR/Ecuador corpus: assign country by host, executive by date."""
    present = [f for f in POOLED_FILES if f in frames]
    if len(present) < 2:
        rep.note("pooled", "dominican_republic/ecuador not both present, skipped")
        return

    # The two files hold the same rows; take one, drop the labels that were
    # assigned by sort order, and re-derive them from the source.
    pooled = frames["dominican_republic"].with_columns(
        host=pl.col("url").str.extract(r"https?://([^/]+)")
    )

    country = pl.lit(None, dtype=pl.String)
    for domain, name in POOLED_DOMAINS.items():
        country = (pl.when(pl.col("host").str.ends_with(domain))
                   .then(pl.lit(name)).otherwise(country))
    pooled = pooled.with_columns(country.alias("country"))

    # Anything unrecognised would be dropped by the filter below, so stop instead:
    # silently losing documents is exactly the class of defect this repairs.
    unmatched = pooled.filter(pl.col("country").is_null()).select(
        pl.col("host").unique()).collect()["host"].to_list()
    if unmatched:
        sys.exit(f"pooled split: {len(unmatched)} unrecognised host(s) in the "
                 f"DR/Ecuador corpus: {unmatched}\nAdd them to POOLED_DOMAINS.")

    executive = pl.lit(None, dtype=pl.String)
    for name, terms in TERMS.items():
        for start, who in terms:
            executive = (
                pl.when((pl.col("country") == name)
                        & (pl.col("date") >= pl.lit(datetime.fromisoformat(start)
                                                    .replace(tzinfo=timezone.utc))))
                .then(pl.lit(who))
                .otherwise(executive)
            )
    pooled = pooled.with_columns(executive.alias("executive")).drop("host")

    for file_name, country_name in POOLED_FILES.items():
        frames[file_name] = pooled.filter(pl.col("country") == country_name)

    counts = (pooled.group_by("country").agg(pl.len().alias("n"),
                                             pl.col("url").n_unique().alias("docs"))
              .sort("country").collect())
    for row in counts.iter_rows(named=True):
        rep.note("pooled", f"{row['country']}: {row['n']:,} rows, "
                           f"{row['docs']:,} documents", changed=row["n"])


def repair_text(df: pl.DataFrame, rep: Report, scope: str) -> pl.DataFrame:
    """Re-decode text that was read as latin-1, where the round-trip is clean."""
    affected = df.filter(pl.col("text").str.contains(MOJIBAKE)).height
    if not affected:
        return df

    def fix(value: str) -> str:
        try:
            return value.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return value

    df = df.with_row_index("__i")
    bad = df.filter(pl.col("text").str.contains(MOJIBAKE))
    repaired = bad.with_columns(
        pl.col("text").map_elements(fix, return_dtype=pl.String))
    unchanged = (repaired["text"] == bad["text"]).sum()

    df = (pl.concat([df.filter(~pl.col("text").str.contains(MOJIBAKE)), repaired])
          .sort("__i").drop("__i"))
    fixed = affected - unchanged
    if not fixed:
        # The pattern also matches legitimate text -- uppercase Portuguese "SÃO",
        # for one -- so a match that does not round-trip is not evidence of damage.
        rep.note(scope, f"{affected:,} rows matched the mojibake pattern but none "
                        f"round-tripped; left unchanged")
    else:
        note = f"re-decoded {fixed:,} mis-decoded rows"
        if unchanged:
            note += (f" ({unchanged:,} more matched the pattern but did not "
                     f"round-trip, left as-is)")
        rep.note(scope, note, changed=fixed)
    return df


def repair_urls(df: pl.DataFrame, rep: Report, scope: str) -> pl.DataFrame:
    """Strip a host that was prefixed onto an already-absolute link."""
    pattern = r"^https?://[^/]+/(https?://.*)$"
    affected = df.filter(pl.col("url").str.contains(pattern)).height
    if not affected:
        return df
    df = df.with_columns(pl.col("url").str.replace(pattern, "$1"))
    rep.note(scope, f"unwrapped {affected:,} doubled-host urls", changed=affected)
    return df


def repair_labels(df: pl.DataFrame, rep: Report, scope: str) -> pl.DataFrame:
    """Fill country-level columns that a partial join left null on some rows."""
    filled = []
    for column in COUNTRY_LEVEL:
        nulls = df[column].null_count()
        if not nulls or nulls == df.height:
            continue
        values = df[column].drop_nulls().unique().to_list()
        if len(values) != 1:
            rep.note(scope, f"WARNING {column} is null on {nulls:,} rows but holds "
                            f"{len(values)} distinct values; left alone")
            continue
        df = df.with_columns(pl.col(column).fill_null(pl.lit(values[0])))
        filled.append(f"{column}={values[0]!r}")
    if filled:
        rep.note(scope, f"backfilled {', '.join(filled)} on rows a join had left "
                        f"unlabelled", changed=1)
    return df


def repair_names(df: pl.DataFrame, rep: Report, scope: str) -> pl.DataFrame:
    hit = df.filter(pl.col("executive").is_in(list(EXECUTIVE_RENAMES)))
    if hit.is_empty():
        return df
    names = sorted(hit["executive"].unique().to_list())
    df = df.with_columns(pl.col("executive").replace(EXECUTIVE_RENAMES))
    rep.note(scope, f"respelled {', '.join(names)} on {hit.height:,} rows",
             changed=hit.height)
    return df


def repair_languages(df: pl.DataFrame, rep: Report, scope: str) -> pl.DataFrame:
    hit = df.filter(pl.col("language").is_in(list(LANGUAGE_RENAMES))).height
    if not hit:
        return df
    df = df.with_columns(pl.col("language").replace(LANGUAGE_RENAMES))
    rep.note(scope, f"respelled language on {hit:,} rows", changed=hit)
    return df


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------

def repair(data_dir: pathlib.Path, out_dir: pathlib.Path, write_full: bool,
           skip: set[str]) -> Report:
    rep = Report()
    paths = sorted(p for p in data_dir.glob("*.parquet") if p.stem != "full_ecd")
    if not paths:
        sys.exit(f"no country parquet files in {data_dir}")

    frames = {p.stem: canonicalise(pl.scan_parquet(p)) for p in paths}
    rep.head(f"canonicalised {len(frames)} assets onto the {len(CANONICAL)} "
             f"documented columns")

    if "pooled" not in skip:
        rep.head("pooled corpus")
        split_pooled(frames, rep)

    rep.head("per-asset repairs")
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name in sorted(frames):
        lf = frames[name]
        before = lf.select(pl.len()).collect().item()

        if "dedupe" not in skip:
            lf = lf.unique(subset=DEDUPE_KEY, keep="first", maintain_order=True)
        df = lf.collect()
        after_dedupe = df.height

        if "labels" not in skip:
            df = repair_labels(df, rep, name)
        if "text" not in skip:
            df = repair_text(df, rep, name)
        if "url" not in skip:
            df = repair_urls(df, rep, name)
        if "names" not in skip:
            df = repair_names(df, rep, name)
            df = repair_languages(df, rep, name)
        if "dedupe" not in skip:
            df = df.unique(subset=DEDUPE_KEY, keep="first", maintain_order=True)

        if before != df.height:
            pct = 100 * (before - df.height) / before
            rep.note(name, f"{before:,} -> {df.height:,} rows "
                           f"({pct:.1f}% removed as duplicates)",
                     changed=before - df.height)
        elif after_dedupe == before:
            rep.note(name, f"{before:,} rows, no duplicates")

        target = out_dir / f"{name}.parquet"
        df.write_parquet(target)
        written.append(target)

    if write_full:
        rep.head("full_ecd.parquet")
        full = pl.concat([pl.scan_parquet(p) for p in written], how="vertical")
        n = full.select(pl.len()).collect().item()
        full.sink_parquet(out_dir / "full_ecd.parquet")
        countries = (pl.scan_parquet(out_dir / "full_ecd.parquet")
                     .select(pl.col("country").n_unique()).collect().item())
        rep.note("full_ecd", f"rebuilt from {len(written)} assets: "
                             f"{n:,} rows, {countries} countries", changed=n)

    return rep


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", required=True, type=pathlib.Path,
                    help="directory holding the published 1.0.0 assets")
    ap.add_argument("--out-dir", required=True, type=pathlib.Path,
                    help="where the repaired assets are written")
    ap.add_argument("--full-ecd", action="store_true",
                    help="also rebuild full_ecd.parquet from the repaired assets")
    ap.add_argument("--skip", default="",
                    help="comma-separated steps to skip: "
                         "pooled,dedupe,labels,text,url,names")
    ap.add_argument("--report", type=pathlib.Path,
                    help="write the change log here as well as to stdout")
    args = ap.parse_args()

    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    rep = repair(args.data_dir, args.out_dir, args.full_ecd, skip)

    out = rep.render()
    print(out)
    if args.report:
        args.report.write_text(out, encoding="utf-8")
    print(f"repaired assets in {args.out_dir}. Validate before publishing:\n"
          f"  python ecd_validate.py --data-dir {args.out_dir} --fail-on ERROR")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
