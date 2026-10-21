"""Repair the defects 1.0.7's Brazil rows carry, before they go back into the dataset.

build_ecd.py calls repair() on the merged rows. Run on its own for a dry run:

    python scraper/repair_kept.py

The repairs, and what each one is held to. The first two apply to the
rescrape's PDF text too, which has the same layout.

* Words broken across a line in PDF text -- "Argen- tina", "Div ulgação". Joined
  where the joined form is a word in the clean (web) text of the same file. A
  line break inside a real hyphenation keeps its hyphen: where the hyphenated
  pair appears in the clean text ("mão-de- obra", "boas- vindas"), or the second
  piece is a pronoun after a verb ("Assegurou- se"); otherwise it is joined. A
  split ("orgul ho", "presente s") is joined only when the joined form is a word
  of three letters or more, at least one piece is not a word on its own -- a
  single letter other than a, e, o, é, à, ó, or a string under a hundredth as
  common as the joined word -- and the clean text never has the two pieces side
  by side, so "encaram os" is never read as "encaramos".
* The press office's header on Lula's 2003-10 PDFs -- "Discurso do Presidente
  da República / Presidência da República / Secretaria de Imprensa e
  Divulgação / 01/01/2003" -- is removed, at the top and at every page break,
  where it fell in mid-sentence. On 1.0.7's rows the speech's own title, which
  follows it, replaces the title made from the file name.
* The editors' notes set into Sarney's speeches in the published volumes --
  "— A inflação do mês de janeiro alcança o recorde histórico de 16,2%." -- are
  removed. A note runs from its dash to the end of its first sentence, or to the
  "/" the scan left where a note ran into the speech; a dash with neither within
  400 characters is left alone.
* Sarney's rows take their title and type from the heading each speech opens
  with ("PRONUNCIAMENTO DO PRESIDENTE JOSÉ SARNEY, ... AO EMPOSSAR O MINISTÉRIO").
* Dates: a Lula PDF whose file name and header agree on a date the date column
  does not have takes that date; a web row whose own dateline, within its
  speaker's term, is more than a week from the date column takes the dateline.
* HTML tags left in the text are removed; rows with less than 200 characters of
  text (a placeholder pointing to a PDF) are dropped; an exact duplicate of
  another row's text is dropped, keeping the copy whose date its dateline backs.
"""
import pathlib, re, sys
from collections import Counter
from datetime import datetime, timezone

import polars as pl

BASE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scraper"))
from parse import LONG, MONTHS, NUM, mk, in_term  # noqa: E402

WORD = r"A-Za-zÀ-ÿ"
SINGLE_WORDS = {"a", "e", "o", "é", "à", "ó"}
ENCLITIC = {"se", "lo", "la", "los", "las", "lhe", "lhes", "me", "te", "nos", "vos", "no", "na", "nas"}
def spaced(s):
    """A pattern for s with any whitespace between its characters, as PDF text breaks it."""
    return r"\s*".join(r"\s+" if c == " " else re.escape(c) for c in s)


# The press office's block, at the top of every page of Lula's PDFs (and a few of
# Dilma's): "Discurso do Presidente da República / Presidência da República /
# Secretaria de Imprensa e Divulgação / 01/01/2003", led by the page number
# after the first page. The office's name changed over the years (de Imprensa; e
# Divulgação; e Porta-Voz; de Comunicação Social), files from 2006 add a link to
# its site -- often broken across lines -- and a few have the date printed over
# the start of the title.
SITE_LINK = (spaced("Visite o site da") + r"\s*(?:" + spaced("Secretaria") + "|" + spaced("SIP") + r")\s*:\s*"
             + spaced("http://www.") + r"\s*(?:" + spaced("imprensa") + "|" + spaced("info") + r")\s*[.,]\s*"
             + spaced("planalto.gov.br"))
PRESS_BLOCK = (r"(?:[A-ZÀ-Ý][a-zà-ÿ]+(?:\s+[a-zà-ÿ]+){0,3}?\s+d\s*[oa]\s+" + spaced("President") + r"\s*[ae]\s+"
               + spaced("da República") + r"(?:\s+em\s+exercício)?\s+)?" + spaced("Presidência da República") + r"\s+"
               + spaced("Secretaria") + r"\s+de\s[^\d]{0,80}?\s+(?:(\d{2}) ?/ ?)?(\d{2}) ?/ ?(\d{1,4})"
               + r"\s*(?:" + SITE_LINK + ")?")
PRESS_HEADER = re.compile(r"^\s*(?:\d{1,3}\s*)?" + PRESS_BLOCK)
PRESS_RUNNING = re.compile(r"\s+(?:\d{1,3}\s*)?" + PRESS_BLOCK)
# the speech's own title, after the header in 1.0.7's text, which ends lines with spaces
HEADER_TITLE = re.compile(r"\s*(.+?)\s{3,}", re.S)
SARNEY_HEAD = re.compile(r"^\s*((?:[A-ZÀ-Ý0-9ºª.,;:()/'’\-–]+\s+){3,}?)(?=[A-ZÀ-Ý][a-zà-ÿ])")
NOTE_START = re.compile(r"\s{2}— ")


class Lexicon:
    """Word counts from text with no PDF layout in it: the rows that came from web pages."""
    def __init__(self, texts):
        self.n = Counter(w.lower() for t in texts for w in re.findall(f"[{WORD}]+", t))
        # adjacent pairs inside hyphenated words: bem-estar, mão-de-obra -> (mão, de), (de, obra)
        self.pairs = Counter()
        # adjacent words: (encaram, os)
        self.bigrams = Counter()
        for t in texts:
            for h in re.findall(f"[{WORD}]+(?:-[{WORD}]+)+", t):
                parts = h.lower().split("-")
                self.pairs.update(zip(parts, parts[1:]))
            words = [w.lower() for w in re.findall(f"[{WORD}]+", t)]
            self.bigrams.update(zip(words, words[1:]))

    def hyphenated(self, a, b):
        return self.pairs.get((a.lower(), b.lower()), 0) >= 1

    def side_by_side(self, a, b):
        return self.bigrams.get((a.lower(), b.lower()), 0) >= 1

    def word(self, w, at_least=3):
        return self.n.get(w.lower(), 0) >= at_least

    def piece(self, w, joined):
        """Whether w, beside the rest of `joined`, is a broken piece of it rather than a word:
        a single letter that is not a word, or under a hundredth as common as `joined`."""
        w = w.lower()
        if len(w) == 1:
            return w not in SINGLE_WORDS
        return self.n.get(w, 0) * 100 < self.n.get(joined.lower(), 0)


def fix_breaks(text, lex, counts):
    def hyphen(m):
        a, b = m.group(1), m.group(2)
        if lex.word(a + b):
            counts["line-break hyphen joined"] += 1
            return a + b
        verb_like = re.search(r"[aeiouáéíóúâêôãõrsm]$", a.lower())
        if lex.hyphenated(a, b) or (b.lower() in ENCLITIC and verb_like and lex.word(a, 1)):
            counts["line-break hyphen kept as a hyphen"] += 1
            return f"{a}-{b}"
        counts["line-break hyphen joined (rare word)"] += 1
        return a + b
    # 1.0.7's text has a space where the line ended, the rescrape's a newline
    text = re.sub(f"\\b([{WORD}]+)-(?: |[ \\t]*\\n[ \\t]*)([a-zà-ÿ]+)\\b", hyphen, text)

    # The second piece is looked ahead at, not consumed, so it can be the first
    # piece of the next pair ("esta primei ra"); once joined, it is not paired again.
    out, pos, taken = [], 0, -1
    for m in re.finditer(f"\\b([{WORD}]+)( {{1,2}})(?=([a-zà-ÿ]+)\\b)", text):
        a, b = m.group(1), m.group(3)
        if m.start() < taken:
            continue
        ab = a + b
        if (len(ab) >= 3 and lex.word(ab) and (lex.piece(a, ab) or lex.piece(b, ab))
                and not lex.side_by_side(a, b)):
            out.append(text[pos:m.end(1)])
            pos, taken = m.end(2), m.end(2) + len(b)
            counts["split word joined"] += 1
    out.append(text[pos:])
    return "".join(out)


def strip_notes(text, counts, removed):
    out, pos = [], 0
    for m in NOTE_START.finditer(text):
        if m.start() < pos:
            continue
        rest = text[m.end():m.end() + 400]
        end = re.search(r"[.!?](?=\s)|\s?/(?=[A-ZÀ-Ý])", rest)
        if not end:
            counts["note left: no end found"] += 1
            continue
        note = rest[:end.end()].rstrip("/ ")
        removed.append(note)
        counts["editors' note removed"] += 1
        out.append(text[pos:m.start()])
        out.append("  ")
        pos = m.end() + end.end()
    out.append(text[pos:])
    return re.sub(r" {3,}", "  ", "".join(out))


def sarney_head(text):
    m = SARNEY_HEAD.match(text)
    if not m:
        return None, None
    head = re.sub(r"\s+", " ", re.sub(r"(\w)- (\w)", r"\1\2", m.group(1))).strip()
    up = head.upper()
    kind = ("Interview" if "ENTREVISTA" in up else
            "Pronouncement" if "NAÇÃO" in up or "CADEIA NACIONAL" in up else
            "Message to Congress" if "MENSAGEM" in up and "CONGRESSO" in up else "Speech")
    return head, kind


def dateline(text):
    m = LONG.search(text[:300])
    return mk(m.group(3), MONTHS[m.group(2).lower()], m.group(1)) if m else None


def repair(df, clean_texts, pdf_mask_col="pdf", kept_col="kept"):
    """df: the merged rows, with boolean columns `pdf` (text came from a PDF) and
    `kept` (row came from 1.0.7). Returns the repaired frame and a report."""
    lex = Lexicon(clean_texts)
    counts, notes, changes = Counter(), [], []
    rows, shrunk = [], []
    letters = lambda x: len(re.sub(f"[^{WORD}]", "", x))
    for r in df.iter_rows(named=True):
        t = r["text"] or ""
        before = letters(t)
        m = PRESS_HEADER.match(t)
        garbled, head_date = False, None
        if m:
            day, month, year = m.group(1), m.group(2), m.group(3)
            garbled = len(year) in (2, 3)          # the date printed over the title
            year = f"200{year}" if len(year) == 1 else year   # "21/10/4": these files are all 2003-10
            head_date = None if garbled or not day else mk(year, month, day)
            t = t[m.end():]
            counts["press-office header removed"] += 1
        # 1.0.7's titles for these files are made from the file name; the speech's
        # own opens the text, after the header where there is one
        if r[kept_col] and r["executive"] == "Luiz Inácio Lula da Silva" and r["file"]:
            file_m = re.match(r"(\d{2})-(\d{2})-(\d{4})", r["file"])
            file_date = mk(file_m.group(3), file_m.group(2), file_m.group(1)) if file_m else None
            d = r["date"].date() if r["date"] else None
            if head_date and head_date == file_date and head_date != d:
                changes.append(("Lula PDF date", d, head_date, r["file"]))
                r["date"] = datetime(head_date.year, head_date.month, head_date.day, tzinfo=timezone.utc)
                counts["Lula PDF re-dated from file name and header"] += 1
            title = HEADER_TITLE.match(t)
            if (title and not garbled and re.match(r"[A-ZÀ-Ý]", title.group(1))
                    and re.search(r"President[ae]\s+da\s+República", title.group(1)[:150])):
                r["title"] = re.sub(r"\s+", " ", fix_breaks(title.group(1), lex, Counter())).strip()
                t = t[title.end():]
                counts["title taken from the speech's own heading"] += 1
        t, n = PRESS_RUNNING.subn(lambda m: "\n" if "\n" in m.group(0) else "  ", t)
        if n:
            counts["press-office header removed at page breaks"] += n
            counts["rows with the header at page breaks"] += 1
        if r[pdf_mask_col]:
            t = fix_breaks(t, lex, counts)
        if r["executive"] == "José Sarney":
            t = strip_notes(t, counts, notes)
            if r[kept_col]:
                head, kind = sarney_head(t)
                if head:
                    r["title"] = r["title"] or head
                    r["type"] = r["type"] or kind
                    counts["Sarney title and type from heading"] += 1
                elif not r["type"]:
                    r["type"] = "Speech"            # from the volumes of his speeches
                    counts["Sarney type set to Speech (no heading)"] += 1
        if r[kept_col] and r["url"] and r["date"] is not None:
            dl = dateline(t)
            d = r["date"].date()
            month_typo = dl and dl.year == d.year and dl.day == d.day and abs(dl.month - d.month) == 1
            if dl and in_term(r["executive"], dl) and abs((dl - d).days) > 7 and not month_typo:
                changes.append(("web date", d, dl, r["url"]))
                r["date"] = datetime(dl.year, dl.month, dl.day, tzinfo=timezone.utc)
                counts["web row re-dated from its dateline"] += 1
        if re.search(r"<[a-zA-Z/][^>]{0,30}>", t):
            t = re.sub(r"<[a-zA-Z/][^>]{0,30}>", " ", t)
            counts["HTML tags removed"] += 1
        r["text"] = t.strip()
        if before and letters(r["text"]) < 0.9 * before:
            shrunk.append((r["executive"], r["title"], before, letters(r["text"])))
        if r["date"] is not None:
            r["year_of_statement"] = float(r["date"].year)
        rows.append(r)

    out = pl.DataFrame(rows, schema=df.schema)
    short = out.filter(pl.col("text").str.len_chars() < 200)
    counts["placeholder rows dropped"] = short.height
    out = out.filter(pl.col("text").str.len_chars() >= 200)
    # exact duplicates: keep the copy whose own dateline backs its date
    out = out.with_columns(_backed=pl.struct("text", "date").map_elements(
        lambda s: bool(s["date"] and dateline(s["text"]) == s["date"].date()), return_dtype=pl.Boolean))
    before = out.height
    out = out.sort("_backed", descending=True).unique(subset=["text"], keep="first", maintain_order=True).drop("_backed")
    counts["exact duplicates dropped"] = before - out.height
    counts["rows that lost over 10% of their letters"] = len(shrunk)
    return out, counts, notes, changes, shrunk


def main():
    out = pl.read_parquet(BASE / "build" / "brazil.parquet")
    new_urls = set(pl.read_parquet(BASE / "data" / "documents.parquet")["original_url"].drop_nulls())
    df = out.with_columns(kept=~pl.col("url").is_in(list(new_urls)).fill_null(False),
                          pdf=pl.col("url").is_null() | pl.col("url").str.to_lowercase().str.contains(r"\.pdf"))
    clean = df.filter(~pl.col("pdf"))["text"].to_list()
    fixed, counts, notes, changes, shrunk = repair(df, clean)
    for k, v in sorted(counts.items()):
        print(f"  {k:<48}{v:>8,}")
    print(f"\n{len(changes)} dates changed:")
    for c in changes:
        print("   ", c[0], c[1], "->", c[2], "|", str(c[3])[-70:])
    print("\nsample of removed notes:")
    import random
    random.seed(5)
    for n in random.sample(notes, min(12, len(notes))):
        print("   —", n[:150])


if __name__ == "__main__":
    main()
