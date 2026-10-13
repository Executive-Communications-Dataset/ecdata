#!/usr/bin/env python3
"""ecd_punctuate.py -- restore punctuation and capitalisation to Colombia.

Colombia's rows are auto-generated YouTube captions: a whole speech as one run
of words with no punctuation, and either no capitalisation (most of Duque's
term) or YouTube's own, which capitalises some sentence starts and proper nouns
and many words that are neither (most of Petro's). Nothing downstream that
needs a sentence can use them, which is why the sentence view passes Colombia
through whole.

    python ecd_punctuate.py --data-dir ./data --out-dir ./candidate

This puts punctuation back with token classifiers, and nothing else. A token
classifier labels the words it is given -- a mark before, a mark after, which
letters are capitals -- so it can add punctuation and change case, but it has no
way to add, drop, reorder or respell a word. That is the reason for using them
rather than a generative model: every output row is checked against its input,
and nothing is written if any row differs from its source in anything other
than added marks and letter case.

Two models, both pinned to one revision:

* kredor/punctuate-all (XLM-RoBERTa, trained on Europarl in 12 languages)
  decides the mark after each word: `.` `,` or `?`.
* 1-800-BAD-CODE/punctuation_fullstop_truecase_romance re-cases every word and
  places `¿`. Its capitalisation is conditioned on punctuation -- it embeds the
  mark after each token -- and that embedding is fed kredor's marks rather than
  its own, so the capitals follow the punctuation that is actually written.

The split is by what each does best on human punctuation from this release
(`--evaluate`, below): kredor is ahead by 0.10 F1 on commas and 0.15 on full
stops, and the romance model is the only one of the two that cases or opens a
question at all.

Questions are left to kredor, which marks few but is right about three times
in four. Taking the romance model's `?` as well finds more than twice as many and gets
more than half of them wrong, turning statements into questions. Where kredor
writes a colon, the human text has a comma more often than a colon, so a comma
is written. kredor also marks a parenthetical by putting a comma after every
word of it -- "por, lo, tanto," -- so no mark is written inside the fixed
connectives listed in CONNECTIVES.

Words are lower-cased before either model sees them, so Petro's rows are
re-cased by the same model as Duque's rather than keeping YouTube's capitals.
Caption annotations -- `[Aplausos]`, `[Risas]` -- and the whitespace between
words are kept exactly as they are. A `¿` is kept only in a sentence that ends
in `?`, and a question with no `¿` gets one at the start of its sentence, so
every question is opened and closed.

    python ecd_punctuate.py --evaluate --data-dir ./data

scores the result against human punctuation from the same release: Mexico's
stenographic press-conference transcripts and Argentina's speeches, with their
punctuation and capitals stripped and then restored. Those are clean
transcripts, so the scores are an upper bound for captions, which also carry
recognition errors.
"""

import argparse
import pathlib
import random
import re
import sys
import time

import numpy as np
import polars as pl

try:
    import onnx
    import onnxruntime as ort
    import sentencepiece as spm
    import torch
    from huggingface_hub import hf_hub_download
    from transformers import AutoModelForTokenClassification, AutoTokenizer
except ImportError:
    sys.exit("these are required:\n  pip install polars torch transformers "
             "onnx onnxruntime sentencepiece huggingface_hub")

PUNCT_MODEL = dict(
    repo="kredor/punctuate-all",
    revision="0fe37019de3f5e4fbd83289fd94e07fa588e47df",
    # its labels -> the mark written. "-" is a dash, which there is no way to
    # tell from a hyphen in a caption, so it is not written; where it predicts
    # ":" the human text has a comma more often than a colon.
    marks={"0": "", ".": ".", ",": ",", "?": "?", ":": ",", "-": ""},
    max_length=512,
)

CASE_MODEL = dict(
    repo="1-800-BAD-CODE/punctuation_fullstop_truecase_romance",
    revision="1e8d395731a9e19471cee4b636f034e0cff7b405",
    spe="sp.model",
    onnx="model.onnx",
    # the graph has 512 positions but was trained on sequences up to 256
    max_length=256,
    pre_labels=[None, "¿"],
    post_labels=[None, "<ACRONYM>", ".", ",", "?"],
    # where the graph embeds its own choice of mark to condition capitals on
    punct_emb="/_decoder/_punct_emb/Gather",
)

# a mark as written -> the post label the casing model is conditioned on
CONDITION = {"": None, ".": ".", ",": ",", "?": "?"}

# Fixed connectives that no mark is written inside. kredor marks a
# parenthetical by putting a comma after every word of it and the word before
# -- "y, por, supuesto," -- and in Mexico's and Argentina's transcripts it puts
# a mark at 1,320 of the 2,564 positions inside one of these, where the
# transcribers put one at 4. This is a judgement rather than a derivation, so it
# is here to be reviewed.
CONNECTIVES = [p.split() for p in """
    a la vez | a propósito | a su vez | ahora bien | al contrario | al mismo tiempo |
    ante todo | de alguna manera | de esta forma | de esta manera | de hecho |
    de todas formas | de todas maneras | de verdad | desde luego | en cambio |
    en consecuencia | en definitiva | en efecto | en ese sentido | en especial |
    en este sentido | en fin | en general | en particular | en primer lugar |
    en realidad | en resumen | en segundo lugar | en tercer lugar | en todo caso |
    eso sí | es decir | más aún | no obstante | o sea | por cierto |
    por consiguiente | por ejemplo | por el contrario | por eso | por fin |
    por lo demás | por lo general | por lo menos | por lo tanto | por otra parte |
    por otro lado | por supuesto | por tanto | por último | por un lado |
    por una parte | sin embargo | sobre todo
    """.split("|")]

COUNTRIES = ("colombia",)
BATCH = 16

TAG = re.compile(r"^\[[^\]]*\]$")       # caption annotations: [Aplausos], [Risas]
WORDLIKE = re.compile(r"\w")
SPACE = re.compile(r"(\s+)")
TERMINAL = (".", "?")


def _windows(lengths, budget):
    """Overlapping windows over items of these lengths, and the one to read each item from.

    Each window holds at most `budget` in total length and overlaps the next by
    about a quarter of that. An item is read from the window where it sits
    furthest from a cut edge, so every prediction has context on both sides
    unless it is at the start or end of the document itself.
    """
    n = len(lengths)
    if n == 0:
        return [], np.zeros(0, dtype=np.int64)
    cum = np.concatenate([[0], np.cumsum(lengths)])
    bounds, s = [], 0
    while True:
        e = max(int(np.searchsorted(cum, cum[s] + budget, side="right")) - 1, s + 1)
        bounds.append((s, e))
        if e >= n:
            break
        s = max(int(np.searchsorted(cum, cum[e] - budget // 4, side="left")), s + 1)
    pos = np.arange(n)[:, None]
    lo = np.array([s for s, _ in bounds])[None, :]
    hi = np.array([e for _, e in bounds])[None, :]
    inside = (pos >= lo) & (pos < hi)
    left = np.where(lo == 0, n, pos - lo)
    right = np.where(hi == n, n, hi - 1 - pos)
    margin = np.where(inside, np.minimum(left, right), -1)
    return bounds, margin.argmax(axis=1)


def _conditioned_on_given_marks(path):
    """The casing model's graph, taking the marks to condition capitals on as an input."""
    m = onnx.load(path)
    g = m.graph
    node = next(n for n in g.node if n.name == CASE_MODEL["punct_emb"])
    node.input[1] = "post_given"
    g.input.append(onnx.helper.make_tensor_value_info(
        "post_given", onnx.TensorProto.INT64, ["batch", "tokens"]))
    return m.SerializeToString()


class Punctuator:
    def __init__(self, device="cpu", threads=0, cache_dir=None):
        if threads:
            torch.set_num_threads(threads)
        self.device = device
        rev = dict(revision=PUNCT_MODEL["revision"], cache_dir=cache_dir)
        self.tok = AutoTokenizer.from_pretrained(PUNCT_MODEL["repo"], **rev)
        self.punct = AutoModelForTokenClassification.from_pretrained(
            PUNCT_MODEL["repo"], **rev).eval().to(device)
        self.punct_marks = [PUNCT_MODEL["marks"][self.punct.config.id2label[i]]
                            for i in range(self.punct.config.num_labels)]

        get = lambda f: hf_hub_download(CASE_MODEL["repo"], f, revision=CASE_MODEL["revision"],
                                        cache_dir=cache_dir)
        self.sp = spm.SentencePieceProcessor(model_file=get(CASE_MODEL["spe"]))
        opts = ort.SessionOptions()
        if threads:
            opts.intra_op_num_threads = threads
        self.case = ort.InferenceSession(_conditioned_on_given_marks(get(CASE_MODEL["onnx"])),
                                         sess_options=opts, providers=["CPUExecutionProvider"])
        self.condition = {m: CASE_MODEL["post_labels"].index(l) for m, l in CONDITION.items()}

    # -- the mark after each word --------------------------------------------

    @torch.inference_mode()
    def marks(self, docs):
        """For each list of lower-cased words, the mark after each word."""
        budget = PUNCT_MODEL["max_length"] - 2
        jobs, plans = [], []
        for d, words in enumerate(docs):
            lengths = [max(len(x), 1) for x in
                       self.tok(words, add_special_tokens=False)["input_ids"]] if words else []
            bounds, owner = _windows(lengths, budget)
            plans.append((bounds, owner))
            jobs.extend((d, k, s, e) for k, (s, e) in enumerate(bounds))
        jobs.sort(key=lambda j: j[3] - j[2], reverse=True)

        got = {}
        for b in range(0, len(jobs), BATCH):
            batch = jobs[b:b + BATCH]
            enc = self.tok([docs[d][s:e] for d, _, s, e in batch], is_split_into_words=True,
                           padding=True, truncation=True,
                           max_length=PUNCT_MODEL["max_length"], return_tensors="pt")
            pred = self.punct(**{k: v.to(self.device) for k, v in enc.items()}
                              ).logits.argmax(-1).cpu().numpy()
            for r, (d, k, s, e) in enumerate(batch):
                last = {}
                for t, w in enumerate(enc.word_ids(r)):
                    if w is not None:
                        last[w] = t          # a word's mark is read from its last piece
                got[d, k] = [self.punct_marks[pred[r, last[w]]] if w in last else ""
                             for w in range(e - s)]

        out = []
        for d, words in enumerate(docs):
            bounds, owner = plans[d]
            out.append([got[d, owner[i]][i - bounds[owner[i]][0]] for i in range(len(words))])
        return out

    # -- capitals and ¿ -------------------------------------------------------

    def _encode(self, words):
        """Casing-model token ids for `words`, and the token span [start, end) of each."""
        ids = self.sp.encode(" ".join(words))
        pieces = [self.sp.id_to_piece(i) for i in ids]
        starts = [k for k, p in enumerate(pieces) if p.startswith("▁")]
        if len(starts) != len(words):
            # normalisation swallowed or split a word; encode word by word instead
            ids, starts = [], []
            for w in words:
                starts.append(len(ids))
                ids.extend(self.sp.encode(w))
            pieces = [self.sp.id_to_piece(i) for i in ids]
        spans = list(zip(starts, starts[1:] + [len(ids)]))
        return ids, pieces, spans

    def _case_predict(self, docs, given):
        """Run the casing model over token sequences, conditioned on given post labels.

        Returns, per sequence, (pre, cap) with one entry per token.
        """
        budget = CASE_MODEL["max_length"] - 2      # room for BOS and EOS
        jobs, plans = [], []
        for d, ids in enumerate(docs):
            bounds, owner = _windows(np.ones(len(ids), dtype=np.int64), budget)
            plans.append((bounds, owner))
            jobs.extend((d, k, s, e) for k, (s, e) in enumerate(bounds))
        jobs.sort(key=lambda j: j[3] - j[2], reverse=True)

        got = {}
        bos, eos, pad = self.sp.bos_id(), self.sp.eos_id(), self.sp.pad_id()
        for b in range(0, len(jobs), BATCH * 2):
            batch = jobs[b:b + BATCH * 2]
            width = max(e - s for _, _, s, e in batch) + 2
            x = np.full((len(batch), width), pad, dtype=np.int64)
            cond = np.zeros((len(batch), width), dtype=np.int64)
            for r, (d, _, s, e) in enumerate(batch):
                x[r, :e - s + 2] = [bos] + docs[d][s:e] + [eos]
                cond[r, 1:e - s + 1] = given[d][s:e]
            pre, _, cap, _ = self.case.run(None, {"input_ids": x, "post_given": cond})
            for r, (d, k, s, e) in enumerate(batch):
                got[d, k] = (pre[r, 1:e - s + 1], cap[r, 1:e - s + 1])

        out = []
        for d, ids in enumerate(docs):
            n = len(ids)
            pre = np.zeros(n, dtype=np.int64)
            cap = np.zeros((n, 16), dtype=bool)
            bounds, owner = plans[d]
            for k, (s, e) in enumerate(bounds):
                mine = np.nonzero(owner[s:e] == k)[0]
                p, c = got[d, k]
                pre[s + mine], cap[s + mine] = p[mine], c[mine]
            out.append((pre, cap))
        return out

    @staticmethod
    def _case(lower, pieces, cap):
        """Apply per-character capital predictions to one word."""
        chars = list(lower)
        pos = 0
        for piece, flags in zip(pieces, cap):
            first = 1 if piece.startswith("▁") else 0
            for j in range(first, len(piece)):
                if pos < len(chars) and j < len(flags) and flags[j]:
                    up = chars[pos].upper()
                    if len(up) == 1:
                        chars[pos] = up
                pos += 1
        if pos != len(chars):
            # the tokenizer normalised this word, so its characters do not line
            # up with the input: trust only the prediction for the first letter
            chars = list(lower)
            first = 1 if pieces[0].startswith("▁") else 0
            if len(pieces[0]) > first and cap[0][first] and len(chars[0].upper()) == 1:
                chars[0] = chars[0].upper()
        return "".join(chars)

    def label_words(self, docs):
        """For each list of words, the (pre, word, post) given to each one.

        `word` is the input word re-cased; pre is "" or "¿", post "" or one of
        . , ?
        """
        lowered = [[w.lower() for w in words] for words in docs]
        marks = [_keep_connectives_whole(words, m)
                 for words, m in zip(lowered, self.marks(lowered))]
        encoded = [self._encode(words) for words in lowered]
        given = []
        for (ids, _, spans), m in zip(encoded, marks):
            g = np.zeros(len(ids), dtype=np.int64)
            for (a, b), mark in zip(spans, m):
                if b > a:
                    g[b - 1] = self.condition[mark]
            given.append(g)
        cased = self._case_predict([ids for ids, _, _ in encoded], given)

        out = []
        for words, lower, (_, pieces, spans), m, (pre, cap) in zip(
                docs, lowered, encoded, marks, cased):
            labelled = []
            for w, lw, (a, b), mark in zip(words, lower, spans, m):
                if b == a or len(lw) != len(w):
                    labelled.append(("", w, mark))
                    continue
                p = CASE_MODEL["pre_labels"][pre[a]] or ""
                labelled.append((p, self._case(lw, pieces[a:b], cap[a:b]), mark))
            out.append(_pair_questions(labelled))
        return out

    def punctuate(self, texts):
        """Punctuate whole texts, leaving tags, symbols and whitespace in place."""
        splits = [SPACE.split(t) for t in texts]
        # even positions are words (possibly an empty first/last), odd are whitespace
        model_idx = [[i for i in range(0, len(parts), 2)
                      if parts[i] and WORDLIKE.search(parts[i]) and not TAG.match(parts[i])]
                     for parts in splits]
        labelled = self.label_words([[parts[i] for i in idx]
                                     for parts, idx in zip(splits, model_idx)])
        out = []
        for parts, idx, labels in zip(splits, model_idx, labelled):
            parts = list(parts)
            for n, (i, (p, w, q)) in enumerate(zip(idx, labels)):
                # a sentence starts with a capital, and a text ends with a full stop
                if n == 0 or labels[n - 1][2] in TERMINAL:
                    w = _capitalise(w)
                if n == len(labels) - 1 and q not in TERMINAL:
                    q = "."
                if q and w.endswith(q):
                    q = ""
                parts[i] = p + w + q
            out.append("".join(parts))
        return out


_CONNECTIVES_BY_FIRST = {}
for _phrase in CONNECTIVES:
    _CONNECTIVES_BY_FIRST.setdefault(_phrase[0], []).append(_phrase)


def _keep_connectives_whole(words, marks):
    """Drop any mark that would split one of CONNECTIVES."""
    marks = list(marks)
    for i, w in enumerate(words):
        for phrase in _CONNECTIVES_BY_FIRST.get(w, ()):
            if words[i:i + len(phrase)] == phrase:
                for k in range(i, i + len(phrase) - 1):
                    marks[k] = ""
    return marks


def _pair_questions(labelled):
    """Keep `¿` only where a `?` closes it, and open every `?` that has none.

    The two marks come from different models. Within a sentence that ends in
    `?`, the last predicted `¿` is kept, or one is put on its first word; in any
    other sentence a `¿` is dropped.
    """
    out = [list(x) for x in labelled]
    start = 0
    for i, (_, _, q) in enumerate(labelled):
        if q in TERMINAL or i == len(labelled) - 1:
            opened = [k for k in range(start, i + 1) if out[k][0]]
            for k in opened:
                out[k][0] = ""
            if q == "?":
                out[opened[-1] if opened else start][0] = "¿"
            start = i + 1
    return [tuple(x) for x in out]


def _capitalise(word):
    for k, ch in enumerate(word):
        if ch.isalpha():
            up = ch.upper()
            return word[:k] + up + word[k + 1:] if len(up) == 1 else word
    return word


def unchanged_but_for_marks(before, after):
    """True if `after` is `before` with only marks added and letter case changed.

    Checked independently of the code that produced `after`: same whitespace,
    same number of words, and each word equal to its source up to case, with at
    most a ¿ before it and one of . , ? after it.
    """
    a, b = SPACE.split(before), SPACE.split(after)
    if len(a) != len(b):
        return False
    for i, (x, y) in enumerate(zip(a, b)):
        if i % 2:
            if x != y:
                return False
        elif x != y and not re.fullmatch("¿?" + re.escape(x.lower()) + "[.,?]?", y.lower()):
            return False
    return True


# -- applying it to a release -------------------------------------------------

def punctuate_country(path, out_dir, model, chunk):
    df = pl.read_parquet(path)
    texts = df["text"].to_list()
    todo = [i for i, t in enumerate(texts) if t]
    done = list(texts)
    t0 = time.time()
    for c in range(0, len(todo), chunk):
        part = todo[c:c + chunk]
        for i, t in zip(part, model.punctuate([texts[i] for i in part])):
            done[i] = t
        n = min(c + chunk, len(todo))
        print(f"    {n:>6,}/{len(todo):,} rows  {time.time() - t0:>6.0f}s", flush=True)

    bad = [i for i in todo if not unchanged_but_for_marks(texts[i], done[i])]
    if bad:
        raise SystemExit(f"{path.stem}: {len(bad)} rows changed beyond punctuation "
                         f"and case, first at row {bad[0]}; nothing written")

    out = df.with_columns(text=pl.Series("text", done, dtype=pl.String))
    out.write_parquet(out_dir / path.name)
    words = sum(len(t.split()) for t in done if t)
    added = {m: sum(t.count(m) for t in done if t) - sum(t.count(m) for t in texts if t)
             for m in ".,?¿"}
    return dict(country=path.stem, rows=len(todo), words=words, added=added)


# -- evaluation against human punctuation ----------------------------------

LEAD = re.compile(r"^[¿¡\"“«'‘(\[—–-]+")
TRAIL = re.compile(r"[)\]\"”»'’…:;,.!?—–-]+$")
SPEAKER = re.compile(r"^[A-ZÁÉÍÓÚÑÜ][A-ZÁÉÍÓÚÑÜ .,\-–]+:\s*")


def reference(text):
    """Words of a punctuated text, stripped, with the marks a model could restore."""
    words, pre, post, cap = [], [], [], []
    for tok in text.split():
        lead, trail = LEAD.match(tok), TRAIL.search(tok)
        core = tok[lead.end() if lead else 0: trail.start() if trail else len(tok)]
        if not WORDLIKE.search(core):
            continue
        marks = trail.group() if trail else ""
        words.append(core.lower())
        pre.append("¿" if lead and "¿" in lead.group() else "")
        post.append("?" if "?" in marks else
                    "." if any(m in marks for m in ".!…") else
                    "," if any(m in marks for m in ",;:") else "")
        cap.append(core[0].isupper())
    return words, pre, post, cap


def eval_corpus(data_dir, n_docs, max_words, seed):
    """Human-punctuated Spanish from the release, as `reference` tuples."""
    rng = random.Random(seed)
    docs = {}

    mx = pl.read_parquet(data_dir / "mexico.parquet", columns=["url", "text"])
    mx = mx.filter(pl.col("url").str.contains("version-estenografica"))
    urls = rng.sample(sorted(mx["url"].unique().to_list()), n_docs)
    mx = mx.filter(pl.col("url").is_in(urls))
    for url in urls:
        rows = [SPEAKER.sub("", t) for t in mx.filter(pl.col("url") == url)["text"].to_list() if t]
        rows = [t for t in rows if re.search(r"[a-záéíóúñ]", t)]
        docs.setdefault("Mexico (press conferences)", []).append(" ".join(rows))

    ar = pl.read_parquet(data_dir / "argentina.parquet", columns=["text"])["text"].to_list()
    for t in rng.sample([t for t in ar if t], n_docs):
        lines = [l for l in t.splitlines() if re.search(r"[a-záéíóúñ]", l)]   # drop the all-caps heading
        docs.setdefault("Argentina (speeches)", []).append(" ".join(lines))

    return {k: [reference(" ".join(d.split()[:max_words])) for d in v] for k, v in docs.items()}


def _prf(gold, pred, cls):
    tp = sum(g == cls and p == cls for g, p in zip(gold, pred))
    fp = sum(g != cls and p == cls for g, p in zip(gold, pred))
    fn = sum(g == cls and p != cls for g, p in zip(gold, pred))
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0), tp + fn


def evaluate(data_dir, model, n_docs, max_words, seed):
    corpora = eval_corpus(data_dir, n_docs, max_words, seed)
    print(f"{'corpus':<28}{'mark':<12}{'precision':>10}{'recall':>8}{'F1':>7}{'support':>10}")
    for name, docs in corpora.items():
        restored = model.punctuate([" ".join(words) for words, *_ in docs])
        gold_pre, gold_post, gold_cap, got_pre, got_post, got_cap = [], [], [], [], [], []
        for (words, pre, post, cap), text in zip(docs, restored):
            _, p, q, c = reference(text)
            assert len(q) == len(words), "restored text does not align with its input"
            gold_pre += pre
            gold_post += post
            gold_cap += cap
            got_pre += p
            got_post += q
            got_cap += c
        bound = lambda xs: ["|" if x in TERMINAL else "" for x in xs]
        rows = [(", comma", gold_post, got_post, ","),
                (". full stop", gold_post, got_post, "."),
                ("? question", gold_post, got_post, "?"),
                ("¿ opening", gold_pre, got_pre, "¿"),
                ("boundary", bound(gold_post), bound(got_post), "|"),
                ("capital", gold_cap, got_cap, True)]
        for label, g, p, cls in rows:
            pr, rc, f1, sup = _prf(g, p, cls)
            print(f"{name:<28}{label:<12}{pr:>10.3f}{rc:>8.3f}{f1:>7.3f}{sup:>10,}")
        print(f"{name:<28}{len(docs)} documents, {len(gold_post):,} words\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", required=True, type=pathlib.Path)
    ap.add_argument("--out-dir", type=pathlib.Path)
    ap.add_argument("--device", default="cpu",
                    help="torch device for the punctuation model: cpu, mps or cuda")
    ap.add_argument("--threads", type=int, default=0, help="CPU threads; 0 = the default")
    ap.add_argument("--chunk", type=int, default=50, help="rows per progress line")
    ap.add_argument("--evaluate", action="store_true",
                    help="score against Mexico's and Argentina's human punctuation instead")
    ap.add_argument("--eval-docs", type=int, default=60)
    ap.add_argument("--eval-words", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    model = Punctuator(device=args.device, threads=args.threads)
    if args.evaluate:
        evaluate(args.data_dir, model, args.eval_docs, args.eval_words, args.seed)
        return 0
    if not args.out_dir:
        ap.error("--out-dir is required unless --evaluate")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name in COUNTRIES:
        path = args.data_dir / f"{name}.parquet"
        print(f"  {name}", flush=True)
        r = punctuate_country(path, args.out_dir, model, args.chunk)
        added = ", ".join(f"{n:,} '{m}'" for m, n in r["added"].items())
        print(f"  {r['country']}: {r['rows']:,} rows, {r['words']:,} words; added {added}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
