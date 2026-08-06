#!/usr/bin/env python3
"""
ecd_validate.py -- pre-release validation for the Executive Communications Dataset.

Runs a battery of structural and content checks against the per-country parquet
assets (and optionally full_ecd.parquet) that make up an ecdata release, and
emits a human-readable report plus machine-readable JSON.

Usage
-----
    python ecd_validate.py --data-dir ./data
    python ecd_validate.py --data-dir ./data --full-ecd ./full_ecd.parquet
    python ecd_validate.py --download 1.0.0 --data-dir ./data        # fetch first
    python ecd_validate.py --data-dir ./data --json report.json --fail-on ERROR

Exit codes: 0 = clean, 1 = findings at or above --fail-on severity.

Dependencies: polars (required), duckdb (strongly recommended -- spills to disk,
so the 8M-row files don't OOM), requests (only for --download).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict, field
from difflib import SequenceMatcher

import polars as pl

try:
    import duckdb
    HAVE_DUCKDB = True
except ImportError:
    HAVE_DUCKDB = False


# --------------------------------------------------------------------------
# configuration
# --------------------------------------------------------------------------

RELEASE_URL = ("https://github.com/Executive-Communications-Dataset/ecdata"
               "/releases/download/{version}/{name}.parquet")

# The schema every country asset is expected to conform to.
CANONICAL_SCHEMA = {
    "country": "String",
    "url": "String",
    "text": "String",
    "date": "Datetime(time_unit='us', time_zone='UTC')",
    "title": "String",
    "executive": "String",
    "type": "String",
    "language": "String",
    "file": "String",
    "isonumber": "Float64",
    "gwc": "String",
    "cowcodes": "String",
    "polity_v": "String",
    "polity_iv": "String",
    "vdem": "Float64",
    "year_of_statement": "Float64",
    "office": "String",
}

# Country -> expected ccTLD(s) in source URLs, used to catch corpora that have
# been pooled or mislabeled. Only countries with a reliable government ccTLD.
EXPECTED_TLD = {
    "argentina": [".ar"], "australia": [".au"], "austria": [".at"],
    "azerbaijan": [".az"], "bolivia": [".bo"], "brazil": [".br"],
    "canada": [".ca"], "chile": [".cl"], "colombia": [".co"],
    "costa_rica": [".cr"], "czechia": [".cz"], "denmark": [".dk"],
    "dominican_republic": [".do"], "ecuador": [".ec"], "france": [".fr"],
    "georgia": [".ge"], "germany": [".de"], "greece": [".gr"],
    "hong_kong": [".hk"], "hungary": [".hu"], "iceland": [".is"],
    "india": [".in"], "indonesia": [".id"], "israel": [".il"],
    "italy": [".it"], "jamaica": [".jm"], "japan": [".jp"],
    "mexico": [".mx"], "new_zealand": [".nz"], "nigeria": [".ng"],
    "norway": [".no"], "philippines": [".ph"], "poland": [".pl"],
    "portugal": [".pt"], "republic_of_korea": [".kr"], "russia": [".ru"],
    "spain": [".es"], "turkey": [".tr"], "united_kingdom": [".uk"],
    "united_states_of_america": [".gov", ".ucsb.edu", ".us"],
    "uruguay": [".uy"], "venezuela": [".ve"],
}

# Hosts that are not primary government sources. Not an error in itself, but
# worth surfacing: provenance is a third-party platform, links rot, and the
# text is likely a transcript rather than an official record.
NON_PRIMARY_HOSTS = ("youtube.com", "youtu.be", "twitter.com", "x.com",
                     "facebook.com", "medium.com", "wordpress.com",
                     "blogspot.com", "scribd.com", "web.archive.org")

# Mojibake signatures: UTF-8 bytes decoded as latin-1/cp1252.
MOJIBAKE_RX = (
    r"Ã©|Ã¡|Ã³|Ã­|Ãº|Ã±|Ã¼|Ã¶|Ã¤|Ã§|Ã£|Ãµ|Ã¨|Ã´|Ã®|Ã‰"
    r"|â€™|â€œ|Â¡|Â¿|Â°|Â«|Â»|Â·|ï¿½"
)

# Text shorter than this is very unlikely to be a substantive statement.
FRAGMENT_CHARS = 20
# Median text length below this suggests paragraph-level rather than
# document-level rows.
DOC_LEVEL_MEDIAN_CHARS = 400

# Name pairs that are similar but genuinely different people. The
# near-duplicate check is a heuristic and needs a human in the loop; add
# confirmed false positives here rather than lowering the threshold.
KNOWN_DISTINCT_NAMES = {
    frozenset({"george bush", "george w. bush"}),
    frozenset({"antonis samaras", "ioannis sarmas"}),
}

SEVERITIES = ["INFO", "WARN", "ERROR", "CRITICAL"]


@dataclass
class Finding:
    severity: str
    check: str
    scope: str
    message: str
    detail: dict = field(default_factory=dict)


class Report:
    def __init__(self):
        self.findings: list[Finding] = []

    def add(self, severity, check, scope, message, **detail):
        self.findings.append(Finding(severity, check, scope, message, detail))

    def max_severity(self):
        if not self.findings:
            return "INFO"
        return max(self.findings, key=lambda f: SEVERITIES.index(f.severity)).severity

    def dump(self, path):
        with open(path, "w") as fh:
            json.dump([asdict(f) for f in self.findings], fh, indent=1, default=str)

    def render(self):
        lines = []
        by_sev = defaultdict(list)
        for f in self.findings:
            by_sev[f.severity].append(f)
        counts = ", ".join(
            f"{len(by_sev[s])} {s}" for s in reversed(SEVERITIES) if by_sev[s]
        )
        lines.append("=" * 78)
        lines.append(f"ECD VALIDATION REPORT  --  {counts or 'no findings'}")
        lines.append("=" * 78)
        for sev in reversed(SEVERITIES):
            for f in by_sev[sev]:
                lines.append("")
                lines.append(f"[{f.severity}] {f.check}  ({f.scope})")
                for ln in f.message.splitlines():
                    lines.append(f"    {ln}")
                for k, v in f.detail.items():
                    lines.append(f"      - {k}: {v}")
        return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# query helpers -- duckdb where available (spills to disk), polars otherwise
# --------------------------------------------------------------------------

class Engine:
    def __init__(self, memory_limit="2GB"):
        self.con = None
        if HAVE_DUCKDB:
            self.con = duckdb.connect()
            self.con.execute(f"SET memory_limit='{memory_limit}';")
            self.con.execute("SET preserve_insertion_order=false;")
            try:
                self.con.execute("SET enable_progress_bar=false;")
            except Exception:
                pass

    def sql(self, query, path):
        """Run SQL against a parquet file; {t} is the table placeholder."""
        q = query.format(t=f"read_parquet('{path}')")
        if self.con is None:
            raise RuntimeError("duckdb required for this check; pip install duckdb")
        try:
            return self.con.execute(q).fetchall()
        except Exception as exc:
            # a check that cannot run should not take the whole report with it;
            # callers treat RuntimeError as "skip this file"
            raise RuntimeError(f"{type(exc).__name__}: {exc}") from exc

    def scan(self, path):
        return pl.scan_parquet(path)


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------

def check_schema(paths, rep):
    """Column presence, dtypes, and whether a vertical concat can succeed."""
    schemas = {}
    for name, path in paths.items():
        s = pl.scan_parquet(path).collect_schema()
        schemas[name] = {k: str(v) for k, v in s.items()}

    all_cols = []
    for s in schemas.values():
        for c in s:
            if c not in all_cols:
                all_cols.append(c)

    extra = [c for c in all_cols if c not in CANONICAL_SCHEMA]
    if extra:
        holders = {c: [n for n in schemas if c in schemas[n]] for c in extra}
        rep.add("ERROR", "schema.extra_columns", "dataset",
                f"{len(extra)} column(s) outside the canonical schema are present. "
                "These look like raw scraper output that was not dropped before release.",
                columns={c: v for c, v in holders.items()})

    for col, want in CANONICAL_SCHEMA.items():
        missing = sorted(n for n in schemas if col not in schemas[n])
        if missing:
            rep.add("ERROR", "schema.missing_column", "dataset",
                    f"Canonical column '{col}' is absent from {len(missing)} file(s).",
                    files=missing)
        types = Counter(schemas[n][col] for n in schemas if col in schemas[n])
        if len(types) > 1:
            offenders = {t: sorted(n for n in schemas
                                   if schemas[n].get(col) == t)
                         for t in types if t != want}
            rep.add("ERROR", "schema.dtype_conflict", "dataset",
                    f"Column '{col}' has conflicting dtypes across files "
                    f"(expected {want}). A vertical concat will fail.",
                    variants=offenders)

    # Concretely: does the documented multi-country load actually work?
    canonical = [n for n in schemas
                 if set(schemas[n]) == set(CANONICAL_SCHEMA)]
    broken = sorted(set(schemas) - set(canonical))
    if broken and canonical:
        ref = canonical[0]
        for n in broken:
            try:
                pl.concat([pl.scan_parquet(paths[ref]), pl.scan_parquet(paths[n])],
                          how="vertical").head(1).collect()
            except Exception as e:
                rep.add("CRITICAL", "schema.concat_fails", n,
                        f"load_ecd() will raise when '{n}' is combined with another "
                        f"country: {type(e).__name__}. Any multi-country or "
                        "language-based call that touches this file errors out.",
                        paired_with=ref)
    return schemas


def check_cross_file_duplication(paths, rep, engine):
    """Two country files sharing a URL set means pooled/mislabeled corpora."""
    urlsets = {}
    for name, path in paths.items():
        cols = pl.scan_parquet(path).collect_schema().names()
        if "url" not in cols:
            continue
        try:
            rows = engine.sql("SELECT DISTINCT url FROM {t} WHERE url IS NOT NULL", path)
            urlsets[name] = {r[0] for r in rows}
        except RuntimeError:
            urlsets[name] = set(
                pl.scan_parquet(path).select("url").drop_nulls().unique()
                .collect(engine="streaming")["url"].to_list())

    names = sorted(urlsets)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            sa, sb = urlsets[a], urlsets[b]
            if not sa or not sb:
                continue
            inter = len(sa & sb)
            if not inter:
                continue
            jac = inter / len(sa | sb)
            sev = "CRITICAL" if jac > 0.5 else ("ERROR" if jac > 0.05 else "WARN")
            rep.add(sev, "corpus.shared_urls", f"{a} / {b}",
                    f"'{a}' and '{b}' share {inter:,} source URLs "
                    f"(Jaccard {jac:.2f}). Distinct countries should not overlap; "
                    "this usually means one corpus was pooled into both files and "
                    "the country/executive labels assigned by sort order.",
                    urls_a=len(sa), urls_b=len(sb), shared=inter)


def check_source_domain(paths, rep, engine):
    """Do source URLs actually belong to the country the rows claim?"""
    for name, path in paths.items():
        tlds = EXPECTED_TLD.get(name)
        cols = pl.scan_parquet(path).collect_schema().names()
        if not tlds or "url" not in cols:
            continue
        try:
            rows = engine.sql(
                "SELECT regexp_extract(url, 'https?://([^/]+)', 1) AS host, "
                "count(*) AS n FROM {t} WHERE url IS NOT NULL "
                "GROUP BY host ORDER BY n DESC", path)
        except RuntimeError:
            continue
        total = sum(r[1] for r in rows)
        if not total:
            continue
        platform = [(h, n) for h, n in rows
                    if h and any(p in h for p in NON_PRIMARY_HOSTS)]
        if platform:
            pn = sum(n for _, n in platform)
            rep.add("WARN" if pn / total < 0.5 else "ERROR",
                    "corpus.non_primary_source", name,
                    f"{pn:,} of {total:,} rows ({100*pn/total:.1f}%) cite a "
                    "third-party platform rather than an official government "
                    "source. The `url` is not a citable primary record and these "
                    "links are prone to rot.",
                    hosts=[f"{h} ({n:,})" for h, n in platform[:5]])

        foreign = [(h, n) for h, n in rows
                   if h and not any(t in h for t in tlds)
                   and not any(p in h for p in NON_PRIMARY_HOSTS)]
        bad = sum(n for _, n in foreign)
        if bad / total > 0.01:
            rep.add("CRITICAL" if bad / total > 0.5 else "ERROR",
                    "corpus.foreign_domain", name,
                    f"{bad:,} of {total:,} rows ({100*bad/total:.1f}%) cite hosts "
                    f"that do not match this country's expected domains {tlds}. "
                    "These rows are labeled with the wrong country.",
                    top_foreign_hosts=[f"{h} ({n:,})" for h, n in foreign[:5]])


def check_duplication(paths, rep, engine):
    """Exact duplicate rows, and Cartesian blowup within a single document."""
    for name, path in paths.items():
        cols = pl.scan_parquet(path).collect_schema().names()
        key = [c for c in ("url", "text", "date") if c in cols]
        try:
            n = engine.sql("SELECT count(*) FROM {t}", path)[0][0]
            uq = engine.sql(
                f"SELECT count(*) FROM (SELECT DISTINCT {', '.join(key)} FROM {{t}})",
                path)[0][0]
        except RuntimeError:
            continue
        dup = n - uq
        if dup:
            pct = 100 * dup / n
            sev = ("CRITICAL" if pct > 50 else "ERROR" if pct > 10
                   else "WARN" if pct > 1 else "INFO")
            rep.add(sev, "rows.exact_duplicates", name,
                    f"{dup:,} of {n:,} rows ({pct:.1f}%) are exact duplicates on "
                    f"({', '.join(key)}). Only {uq:,} distinct rows remain.",
                    distinct_rows=f"{uq:,}")

        if "url" not in cols:
            continue
        # A clean integer rows-per-distinct-paragraph ratio is the signature of
        # a many-to-many join rather than genuine repetition in the source.
        try:
            rows = engine.sql(
                "SELECT url, count(*) AS nr, count(DISTINCT text) AS dt "
                "FROM {t} WHERE url IS NOT NULL GROUP BY url "
                "HAVING count(DISTINCT text) > 1 ORDER BY nr DESC LIMIT 200", path)
        except RuntimeError:
            continue
        worst = [(u, nr, dt, nr / dt) for u, nr, dt in rows if nr / dt >= 2]
        if worst:
            integer_ratio = sum(1 for *_, r in worst if abs(r - round(r)) < 0.01)
            top = worst[0]
            rep.add("CRITICAL" if top[3] > 50 else "ERROR",
                    "rows.cartesian_blowup", name,
                    f"Documents are replicated within themselves. Worst URL holds "
                    f"{top[1]:,} rows for only {top[2]:,} distinct paragraphs "
                    f"({top[3]:.0f}x). {integer_ratio} of the top {len(worst)} "
                    "offending URLs have a whole-number ratio, which points to a "
                    "many-to-many join rather than repetition in the source.",
                    worst_url=str(top[0])[:100])


def check_columns_content(paths, rep, engine):
    """Null rates, dead columns, malformed URLs, mojibake, text granularity.

    Aggregates run through duckdb where available so that the multi-million-row
    assets spill to disk instead of exhausting memory.
    """
    for name, path in paths.items():
        lf = pl.scan_parquet(path)
        cols = lf.collect_schema().names()
        use_sql = engine.con is not None

        if use_sql:
            n = engine.sql("SELECT count(*) FROM {t}", path)[0][0]
        else:
            n = lf.select(pl.len()).collect()[0, 0]
        if not n:
            continue

        # ---- null rates -------------------------------------------------
        if use_sql:
            expr = ", ".join(f'count(*) - count("{c}")' for c in cols)
            vals = engine.sql(f"SELECT {expr} FROM {{t}}", path)[0]
            nulls = dict(zip(cols, vals))
        else:
            nulls = lf.select([pl.col(c).null_count().alias(c) for c in cols]) \
                      .collect(engine="streaming").to_dicts()[0]

        dead = [c for c, v in nulls.items() if v == n]
        if dead:
            sev = "ERROR" if {"url", "text", "date", "language"} & set(dead) else "WARN"
            rep.add(sev, "column.all_null", name,
                    f"{len(dead)} column(s) are 100% null and carry no information.",
                    columns=dead)
        heavy = {c: f"{100*v/n:.1f}%" for c, v in nulls.items()
                 if 0 < v < n and v / n > 0.30 and c not in ("type", "title")}
        if heavy:
            rep.add("WARN", "column.high_null_rate", name,
                    "Column(s) are mostly null.", rates=heavy)

        # ---- malformed URLs ---------------------------------------------
        if "url" in cols and nulls.get("url", 0) < n:
            if use_sql:
                bad = engine.sql(
                    "SELECT count(*) FROM {t} WHERE url IS NOT NULL "
                    "AND length(url) - length(replace(url, 'http', '')) > 4", path)[0][0]
            else:
                bad = lf.filter(pl.col("url").str.count_matches("https?://") > 1) \
                        .select(pl.len()).collect(engine="streaming")[0, 0]
            if bad:
                pct = 100 * bad / n
                rep.add("CRITICAL" if pct > 50 else "ERROR", "url.malformed", name,
                        f"{bad:,} of {n:,} URLs ({pct:.1f}%) contain more than one "
                        "scheme -- the base URL was concatenated onto an already "
                        "absolute link. These do not resolve.")

        # ---- text quality -----------------------------------------------
        if "text" in cols:
            if use_sql:
                row = engine.sql(
                    "SELECT "
                    " sum(CASE WHEN length(trim(text)) = 0 THEN 1 ELSE 0 END), "
                    f" sum(CASE WHEN length(trim(text)) < {FRAGMENT_CHARS} THEN 1 ELSE 0 END), "
                    " median(length(text)), "
                    f" sum(CASE WHEN regexp_matches(text, '{MOJIBAKE_RX}') THEN 1 ELSE 0 END), "
                    " sum(CASE WHEN regexp_matches(text, '<[a-zA-Z/][^>]*>') THEN 1 ELSE 0 END) "
                    "FROM {t} WHERE text IS NOT NULL", path)[0]
                q = dict(zip(("empty", "frag", "med", "moji", "html"),
                             [v or 0 for v in row]))
            else:
                q = lf.select([
                    (pl.col("text").str.strip_chars().str.len_chars() == 0).sum().alias("empty"),
                    (pl.col("text").str.strip_chars().str.len_chars() < FRAGMENT_CHARS).sum().alias("frag"),
                    pl.col("text").str.len_chars().median().alias("med"),
                    pl.col("text").str.contains(MOJIBAKE_RX).sum().alias("moji"),
                    pl.col("text").str.contains(r"<[a-zA-Z/][^>]*>").sum().alias("html"),
                ]).collect(engine="streaming").to_dicts()[0]

            if q["moji"]:
                pct = 100 * q["moji"] / n
                rep.add("CRITICAL" if pct > 50 else "ERROR" if pct > 1 else "WARN",
                        "text.mojibake", name,
                        f"{q['moji']:,} rows ({pct:.1f}%) contain UTF-8 bytes that "
                        "were decoded as latin-1/cp1252 (e.g. 'RepÃºblica' for "
                        "'República'). Re-decode at ingest.")
            if q["empty"]:
                rep.add("WARN", "text.empty", name,
                        f"{q['empty']:,} rows have empty or whitespace-only text.")
            if q["frag"] / n > 0.10:
                rep.add("WARN", "text.fragments", name,
                        f"{q['frag']:,} rows ({100*q['frag']/n:.1f}%) hold fewer than "
                        f"{FRAGMENT_CHARS} characters -- salutations, stage "
                        "directions and boilerplate rather than statements.")
            if q["med"] is not None and q["med"] < DOC_LEVEL_MEDIAN_CHARS:
                rep.add("WARN", "text.granularity", name,
                        f"Median text length is {q['med']:.0f} characters, so rows "
                        "are paragraph- or line-level, not document-level. Pooling "
                        "this with document-level countries distorts any row count.",
                        median_chars=int(q["med"]))
            if q["html"]:
                rep.add("INFO", "text.html_residue", name,
                        f"{q['html']:,} rows still contain HTML tags.")

        # ---- date coherence ---------------------------------------------
        if "date" in cols and "year_of_statement" in cols:
            if use_sql:
                mm = engine.sql(
                    "SELECT count(*) FROM {t} WHERE year_of_statement IS NOT NULL "
                    "AND date IS NOT NULL AND year(date) <> year_of_statement",
                    path)[0][0]
            else:
                mm = lf.filter(
                    pl.col("date").dt.year().cast(pl.Float64) != pl.col("year_of_statement")
                ).select(pl.len()).collect(engine="streaming")[0, 0]
            if mm:
                rep.add("ERROR", "date.year_mismatch", name,
                        f"{mm:,} rows where year_of_statement disagrees with date.")


def check_executives(paths, rep, engine):
    """Term overlaps, out-of-term documents, and near-duplicate name spellings."""
    for name, path in paths.items():
        cols = pl.scan_parquet(path).collect_schema().names()
        if "executive" not in cols or "date" not in cols:
            continue
        try:
            rows = engine.sql(
                # cast away the time zone: duckdb needs pytz to hand a
                # TIMESTAMPTZ back to Python, and pytz is not a dependency here
                "SELECT executive, count(*) AS n, "
                "min(date::TIMESTAMP) AS mn, max(date::TIMESTAMP) AS mx "
                "FROM {t} WHERE executive IS NOT NULL GROUP BY executive "
                "ORDER BY mn", path)
        except RuntimeError:
            continue
        if len(rows) < 2:
            continue

        spans = [(r[0], r[1], r[2], r[3]) for r in rows]

        # Overlapping tenures: at most one person holds the office at a time, so
        # a real overlap means rows are attributed to the wrong executive.
        #
        # Comparing min/max spans alone is not enough. A leader with two
        # non-contiguous terms -- Lars Lokke Rasmussen, Netanyahu, Putin -- has a
        # span that encloses their successor's whole term while holding no
        # documents inside it. Counting the documents each of them actually has
        # in the intersection is what distinguishes a mis-attribution from a
        # gap in someone's tenure.
        for i, (na, ca, sa, ea) in enumerate(spans):
            for nb, cb, sb, eb in spans[i + 1:]:
                lo, hi = max(sa, sb), min(ea, eb)
                if lo >= hi:
                    continue
                days = (hi - lo).days
                if days <= 30:
                    continue
                try:
                    counts = engine.sql(
                        "SELECT executive, count(*) FROM {t} "
                        f"WHERE date::TIMESTAMP >= TIMESTAMP '{lo}' "
                        f"AND date::TIMESTAMP <= TIMESTAMP '{hi}' "
                        f"AND executive IN ('{na.replace(chr(39), chr(39) * 2)}', "
                        f"'{nb.replace(chr(39), chr(39) * 2)}') "
                        "GROUP BY executive", path)
                except RuntimeError:
                    continue
                inside = {r[0]: r[1] for r in counts}
                a_in, b_in = inside.get(na, 0), inside.get(nb, 0)

                # A handover day legitimately carries documents from both the
                # outgoing and incoming leader -- 33 of Ford's rows are dated
                # 1977-01-20, Carter's inauguration. If every row on the smaller
                # side falls on one date, and that date is an edge of the window,
                # it is a handover rather than a mis-attribution.
                if a_in and b_in:
                    minority = na if a_in <= b_in else nb
                    try:
                        days = engine.sql(
                            "SELECT DISTINCT date::DATE FROM {t} "
                            f"WHERE date::TIMESTAMP >= TIMESTAMP '{lo}' "
                            f"AND date::TIMESTAMP <= TIMESTAMP '{hi}' "
                            f"AND executive = "
                            f"'{minority.replace(chr(39), chr(39) * 2)}'", path)
                    except RuntimeError:
                        days = []
                    dates = {str(d[0]) for d in days}
                    if len(dates) == 1 and dates <= {str(lo)[:10], str(hi)[:10]}:
                        rep.add("INFO", "executive.handover_day", name,
                                f"'{na}' and '{nb}' share documents dated "
                                f"{dates.pop()}, and that is the only date they "
                                "share. Consistent with a handover rather than a "
                                "mis-attribution.")
                        continue

                # Both present inside the window on more than the handover day:
                # documents really are split between two people for the same dates.
                if a_in and b_in:
                    smaller = min(a_in, b_in)
                    rep.add("ERROR", "executive.term_overlap", name,
                            f"'{na}' ({a_in:,} rows) and '{nb}' ({b_in:,} rows) are "
                            f"both credited with documents dated between "
                            f"{str(lo)[:10]} and {str(hi)[:10]}. At most one of them "
                            f"held office; at least {smaller:,} rows are attributed "
                            "to the wrong executive.",
                            rows_in_window=f"{na}: {a_in:,}, {nb}: {b_in:,}")
                elif a_in or b_in:
                    # Only one of them has documents in the intersection, so the
                    # other's span merely encloses it -- two terms with a gap.
                    holder = na if a_in else nb
                    other = nb if a_in else na
                    rep.add("INFO", "executive.span_encloses", name,
                            f"'{other}' has a date span enclosing "
                            f"{str(lo)[:10]} to {str(hi)[:10]}, but no documents in "
                            f"it -- all {max(a_in, b_in):,} belong to '{holder}'. "
                            "Consistent with non-contiguous terms, not a "
                            "mis-attribution.")

        # Near-identical names almost always mean a typo splitting one person.
        for i, (na, ca, *_ ) in enumerate(spans):
            for nb, cb, *_ in spans[i + 1:]:
                if frozenset({na.lower(), nb.lower()}) in KNOWN_DISTINCT_NAMES:
                    continue
                ratio = SequenceMatcher(None, na.lower(), nb.lower()).ratio()
                if 0.85 <= ratio < 1.0:
                    rep.add("ERROR", "executive.near_duplicate_name", name,
                            f"'{na}' ({ca:,} rows) and '{nb}' ({cb:,} rows) differ by "
                            f"a few characters ({ratio:.0%} similar). Almost certainly "
                            "one person split by a misspelling -- any group-by on "
                            "executive silently splits their tenure.")

        # Composite values do not group.
        for nm, cnt, *_ in spans:
            if "/" in nm or " and " in nm.lower():
                rep.add("WARN", "executive.composite_value", name,
                        f"'{nm}' ({cnt:,} rows) packs more than one person into a "
                        "single value, so it will not group or join.")


def check_type_vocabulary(paths, rep, engine):
    """The `type` column should be a controlled vocabulary shared across files."""
    seen = defaultdict(set)
    for name, path in paths.items():
        cols = pl.scan_parquet(path).collect_schema().names()
        if "type" not in cols:
            continue
        if engine.con is not None:
            vals = [r[0] for r in engine.sql(
                "SELECT DISTINCT type FROM {t} WHERE type IS NOT NULL", path)]
        else:
            vals = pl.scan_parquet(path).select(pl.col("type").unique()) \
                     .collect(engine="streaming")["type"].to_list()
        vals = [v for v in vals if v]
        for v in vals:
            seen[v.strip().lower()].add(v)
        # `type` should not contain person names; a value equal to an executive
        # name in the same file means two fields were crossed.
        if "executive" in cols:
            if engine.con is not None:
                execs = {r[0] for r in engine.sql(
                    "SELECT DISTINCT executive FROM {t} "
                    "WHERE executive IS NOT NULL", path)}
            else:
                execs = set(pl.scan_parquet(path)
                            .select(pl.col("executive").unique())
                            .collect(engine="streaming")["executive"].to_list()) - {None}
            leaked = [v for v in vals if any(
                SequenceMatcher(None, v.lower(), e.lower()).ratio() > 0.8 for e in execs)]
            if leaked:
                rep.add("ERROR", "type.contaminated", name,
                        f"{len(leaked)} value(s) in `type` are executive names, not "
                        "document categories. Two fields have been crossed.",
                        values=leaked[:8])

    case_clashes = {k: sorted(v) for k, v in seen.items() if len(v) > 1}
    if case_clashes:
        rep.add("WARN", "type.case_variants", "dataset",
                "The same category appears under multiple casings.",
                variants=case_clashes)
    if len(seen) > 12:
        rep.add("WARN", "type.uncontrolled_vocabulary", "dataset",
                f"{len(seen)} distinct `type` values across the release, with no "
                "shared scheme between countries. `type` cannot be used as a filter.",
                values=sorted(seen)[:30])


def check_full_ecd(full_path, paths, rep, engine):
    """Reconcile the pooled file against the per-country assets."""
    lf = pl.scan_parquet(full_path)
    per_country = lf.group_by("country").agg(pl.len().alias("n")) \
                    .collect(engine="streaming")
    full_counts = dict(zip(per_country["country"], per_country["n"]))

    file_counts = {}
    for name, path in paths.items():
        c = pl.scan_parquet(path).select(pl.col("country").drop_nulls().first(),
                                         pl.len().alias("n")).collect()
        file_counts[c[0, 0]] = int(c[0, 1])

    for country, n_file in file_counts.items():
        n_full = full_counts.get(country)
        if n_full is None:
            rep.add("CRITICAL", "full_ecd.country_missing", country,
                    f"{n_file:,} rows exist in the country asset but the country is "
                    "absent from full_ecd.parquet.")
            continue
        if n_full == n_file:
            continue
        if n_full < n_file:
            rep.add("CRITICAL", "full_ecd.rows_lost", country,
                    f"full_ecd holds {n_full:,} rows but the country asset holds "
                    f"{n_file:,} -- {n_file - n_full:,} documents are missing from "
                    "the pooled dataset. A row count of 1 with null content is the "
                    "signature of a failed join.")
        else:
            factor = n_full / n_file
            rep.add("CRITICAL", "full_ecd.rows_duplicated", country,
                    f"full_ecd holds {n_full:,} rows against {n_file:,} in the "
                    f"country asset ({factor:.2f}x). The file was concatenated more "
                    "than once.")

    for country in set(full_counts) - set(file_counts):
        rep.add("WARN", "full_ecd.unexpected_country", str(country),
                f"Present in full_ecd ({full_counts[country]:,} rows) with no "
                "corresponding country asset.")

    fs = {k: str(v) for k, v in lf.collect_schema().items()}
    drift = {c: fs[c] for c in fs if c not in CANONICAL_SCHEMA}
    if drift:
        rep.add("WARN", "full_ecd.schema_drift", "full_ecd",
                "full_ecd carries columns outside the canonical schema.",
                columns=drift)


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------

def download(version, data_dir, names):
    import requests
    os.makedirs(data_dir, exist_ok=True)
    for nm in names:
        dest = os.path.join(data_dir, f"{nm}.parquet")
        if os.path.exists(dest):
            continue
        url = RELEASE_URL.format(version=version, name=nm)
        print(f"  fetching {nm} ...", flush=True)
        r = requests.get(url, stream=True, timeout=120)
        r.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", required=True,
                    help="directory of per-country .parquet assets")
    ap.add_argument("--full-ecd", help="path to full_ecd.parquet (optional)")
    ap.add_argument("--download", metavar="VERSION",
                    help="fetch the release assets into --data-dir first")
    ap.add_argument("--json", help="write findings as JSON to this path")
    ap.add_argument("--out", help="write the text report to this path")
    ap.add_argument("--memory-limit", default="2GB")
    ap.add_argument("--fail-on", default="ERROR", choices=SEVERITIES,
                    help="exit 1 if any finding reaches this severity")
    ap.add_argument("--skip", default="",
                    help="comma-separated check groups to skip: "
                         "schema,cross,domain,dup,columns,exec,type,full")
    args = ap.parse_args()

    if args.download:
        download(args.download, args.data_dir, sorted(EXPECTED_TLD))

    paths = {os.path.basename(p)[:-8]: p
             for p in sorted(glob.glob(os.path.join(args.data_dir, "*.parquet")))
             if os.path.basename(p) != "full_ecd.parquet"}
    if not paths:
        sys.exit(f"no parquet files found in {args.data_dir}")

    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    rep = Report()
    engine = Engine(args.memory_limit)
    if not HAVE_DUCKDB:
        rep.add("INFO", "runner.no_duckdb", "runner",
                "duckdb is not installed; duplicate, domain and executive checks "
                "were skipped. pip install duckdb to enable them.")

    print(f"validating {len(paths)} country assets ...", file=sys.stderr)
    stages = [
        ("schema",  lambda: check_schema(paths, rep)),
        ("columns", lambda: check_columns_content(paths, rep, engine)),
        ("dup",     lambda: check_duplication(paths, rep, engine)),
        ("cross",   lambda: check_cross_file_duplication(paths, rep, engine)),
        ("domain",  lambda: check_source_domain(paths, rep, engine)),
        ("exec",    lambda: check_executives(paths, rep, engine)),
        ("type",    lambda: check_type_vocabulary(paths, rep, engine)),
    ]
    for key, fn in stages:
        if key in skip:
            continue
        print(f"  [{key}]", file=sys.stderr, flush=True)
        fn()
    if args.full_ecd and "full" not in skip:
        print("  [full]", file=sys.stderr, flush=True)
        check_full_ecd(args.full_ecd, paths, rep, engine)

    text = rep.render()
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text)
    else:
        print(text)
    if args.json:
        rep.dump(args.json)

    worst = rep.max_severity()
    if SEVERITIES.index(worst) >= SEVERITIES.index(args.fail_on):
        print(f"FAILED: highest severity {worst}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
