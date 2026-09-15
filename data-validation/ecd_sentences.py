#!/usr/bin/env python3
"""ecd_sentences.py -- derive a sentence-level view of an ECD release.

One row per sentence, keeping every documented column, plus the identifiers a
sentence-level table needs to be joinable back to its source:

    document_id     stable id for the source document (the url, hashed)
    block_index     which original row within that document this came from
    sentence_index  position of the sentence within the document
    segmenter       which rules split it, so a reader can judge the result

The source release is left untouched; this writes a parallel set of files.

    python ecd_sentences.py --data-dir ./data --out-dir ./sentences

Segmentation uses pysbd, which has rules for 11 of the 22 languages in the
release. The other 11 fall back to the English rules, which handle a Latin or
Cyrillic script with `.` `!` `?` terminators well enough -- tested against real
rows in Czech, Portuguese, Turkish, Korean, Hungarian, Hebrew, Indonesian,
Icelandic, Norwegian and Georgian, where fewer than 4% of long rows collapse to
a single sentence. What the fallback loses is language-specific abbreviation
handling, so an abbreviation followed by a capital may split early.

Colombia cannot be segmented at all and is passed through whole, marked
`segmenter = "none (unpunctuated source)"`. Its rows are auto-generated YouTube
captions with no punctuation and no capitalisation, so there are no sentence
boundaries to find.
"""

import argparse
import hashlib
import pathlib
import sys
from concurrent.futures import ProcessPoolExecutor

import polars as pl

try:
    import pysbd
except ImportError:
    sys.exit("pysbd is required:  pip install pysbd")

PYSBD_LANGS = set("am ar bg da de el en es fa fr hi hy it ja kk mr my nl pl ru sk ur zh".split())

# `language` as it appears in the data -> ISO 639-1
ISO = {
    "Chinese": "zh", "Czech": "cs", "Danish": "da", "English": "en",
    "Filipino": "fil", "French": "fr", "Georgian": "ka", "German": "de",
    "Greek": "el", "Hebrew": "he", "Hindi": "hi", "Hungarian": "hu",
    "Icelandic": "is", "Indonesian": "id", "Italian": "it", "Japanese": "ja",
    "Korean": "ko", "Norwegian": "no", "Polish": "pl", "Portuguese": "pt",
    "Spanish": "es", "Turkish": "tr",
}

# Sources with no sentence boundaries to find.
UNSEGMENTABLE = {"colombia"}

CHUNK = 20_000


def _label(iso):
    if iso in PYSBD_LANGS:
        return f"pysbd/{iso}"
    return f"pysbd/en (fallback from {iso})"


def _split_chunk(args):
    """Return, for each input row, the list of sentences it contains."""
    texts, iso = args
    seg = pysbd.Segmenter(language=iso if iso in PYSBD_LANGS else "en", clean=False)
    out = []
    for t in texts:
        if not t:
            out.append([])
            continue
        try:
            parts = [s.strip() for s in seg.segment(t)]
        except Exception:
            parts = [t.strip()]
        out.append([s for s in parts if s])
    return out


def segment_country(path, out_dir, jobs):
    name = path.stem
    df = pl.read_parquet(path)
    if df.is_empty():
        return None

    df = df.with_columns(
        document_id=pl.col("url").fill_null("").map_elements(
            lambda u: hashlib.sha1(u.encode()).hexdigest()[:16] if u else None,
            return_dtype=pl.String),
    )
    # position of each original row inside its document, before anything is split
    df = df.with_row_index("_row").with_columns(
        block_index=pl.col("_row").rank("ordinal").over("document_id").cast(pl.Int32) - 1
    ).drop("_row")

    if name in UNSEGMENTABLE:
        out = df.with_columns(
            sentence_index=pl.col("block_index"),
            segmenter=pl.lit("none (unpunctuated source)"),
        )
        rows_in, sents = df.height, df.height
    else:
        pieces = []
        for (lang,), part in df.group_by(["language"], maintain_order=True):
            iso = ISO.get(lang, "en")
            texts = part["text"].to_list()
            chunks = [(texts[i:i + CHUNK], iso) for i in range(0, len(texts), CHUNK)]
            if jobs > 1 and len(chunks) > 1:
                with ProcessPoolExecutor(max_workers=jobs) as pool:
                    results = list(pool.map(_split_chunk, chunks))
            else:
                results = [_split_chunk(c) for c in chunks]
            flat = [s for r in results for s in r]
            pieces.append(
                part.with_columns(
                    _sents=pl.Series("_sents", flat, dtype=pl.List(pl.String)),
                    segmenter=pl.lit(_label(iso)),
                )
            )
        merged = pl.concat(pieces, how="vertical")
        rows_in = merged.height
        out = (merged.filter(pl.col("_sents").list.len() > 0)
                     .explode("_sents")
                     .with_columns(text=pl.col("_sents"))
                     .drop("_sents"))
        out = out.with_row_index("_i").with_columns(
            sentence_index=pl.col("_i").rank("ordinal").over("document_id").cast(pl.Int32) - 1
        ).drop("_i")
        sents = out.height

    cols = [c for c in df.columns if c not in ("document_id", "block_index")]
    out = out.select(cols + ["document_id", "block_index", "sentence_index", "segmenter"])
    out.write_parquet(out_dir / f"{name}.parquet")
    return dict(country=name, rows_in=rows_in, sentences=sents,
                per_row=sents / rows_in if rows_in else 0,
                segmenter=out["segmenter"][0] if out.height else "-")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", required=True, type=pathlib.Path)
    ap.add_argument("--out-dir", required=True, type=pathlib.Path)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--only", help="comma-separated country file stems")
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    paths = sorted(p for p in args.data_dir.glob("*.parquet") if p.stem != "full_ecd")
    if args.only:
        keep = {s.strip() for s in args.only.split(",")}
        paths = [p for p in paths if p.stem in keep]

    results = []
    for p in paths:
        r = segment_country(p, args.out_dir, args.jobs)
        if r:
            results.append(r)
            print(f"  {r['country']:<26}{r['rows_in']:>10,} rows -> "
                  f"{r['sentences']:>10,} sentences  ({r['per_row']:>5.1f}/row)  "
                  f"{r['segmenter']}", flush=True)

    tot_in = sum(r["rows_in"] for r in results)
    tot_out = sum(r["sentences"] for r in results)
    print(f"\n{len(results)} countries: {tot_in:,} rows -> {tot_out:,} sentences "
          f"({tot_out/tot_in:.1f} per row)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
