"""Hybrid retrieval over NEPRA clauses: BM25 on words + TF-IDF on character n-grams.

Why both: BM25 is precise on exact terms ("sanctioned load", "detection bill"), but the
regulations' text layer is OCR output ("prosurner", "Meteiing", "iegulations") and a
misspelt word scores zero. Character 3-5-grams still overlap ("pros", "rosu"...), so the
typo'd clause is found. The two rankings are fused with reciprocal rank fusion (RRF),
which needs no score calibration between them. Pure Python: the corpus is a few hundred
clauses, so an index builds in milliseconds and needs no vector database.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from rehnuma.policy.parse import Chunk

STOP = set("""a an and are as at be by can do does for from has have how i if in is it its
me my of on or shall should that the their them then there these this to was what when
which who will with would you your under any may such not all per""".split())

METHODS = ("bm25", "char", "hybrid")                # lexical: no model, no download
DENSE_METHODS = ("dense", "hybrid+dense")          # need a DenseIndex (HF embedding model)
ALL_METHODS = METHODS + DENSE_METHODS


def _stem(w: str) -> str:
    for suf, rep in (("ies", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)] + rep
    return w


def words(text: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]


def char_grams(text: str, n_min: int = 3, n_max: int = 5) -> Counter:
    grams: Counter = Counter()
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w in STOP:
            continue
        w = f"#{w}#"
        for n in range(n_min, n_max + 1):
            grams.update(w[i:i + n] for i in range(len(w) - n + 1))
    return grams


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tfs = [Counter(d) for d in docs]
        self.lens = [len(d) for d in docs]
        self.avg = sum(self.lens) / (len(docs) or 1)
        df = Counter(t for d in docs for t in set(d))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: list[str]) -> list[float]:
        out = []
        for tf, ln in zip(self.tfs, self.lens, strict=True):
            s = 0.0
            for t in query:
                f = tf.get(t)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (
                        f + self.k1 * (1 - self.b + self.b * ln / self.avg))
            out.append(s)
        return out


class CharTfidf:
    def __init__(self, texts: list[str]):
        grams = [char_grams(t) for t in texts]
        n = len(texts)
        df = Counter(g for c in grams for g in c)
        self.idf = {g: math.log((1 + n) / (1 + f)) + 1 for g, f in df.items()}
        self.vecs = [self._vec(c) for c in grams]

    def _vec(self, c: Counter) -> dict[str, float]:
        v = {g: (1 + math.log(f)) * self.idf.get(g, 0.0) for g, f in c.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {g: x / norm for g, x in v.items()}

    def scores(self, query: str) -> list[float]:
        q = self._vec(char_grams(query))
        return [sum(w * v.get(g, 0.0) for g, w in q.items()) for v in self.vecs]


def _ranking(scores: list[float]) -> list[int]:
    return [i for i in sorted(range(len(scores)), key=lambda i: -scores[i]) if scores[i] > 0]


@dataclass
class Hit:
    chunk: Chunk
    score: float
    rank: int


class PolicyIndex:
    def __init__(self, chunks: list[Chunk], dense=None):
        self.chunks = chunks
        texts = [c.search_text for c in chunks]
        self.bm25 = BM25([words(t) for t in texts])
        self.char = CharTfidf(texts)
        self.dense = dense                          # rehnuma.policy.dense.DenseIndex | None

    @property
    def methods(self) -> tuple[str, ...]:
        return ALL_METHODS if self.dense else METHODS

    def _scores(self, query: str, method: str) -> list[float]:
        if method == "bm25":
            return self.bm25.scores(words(query))
        if method == "char":
            return self.char.scores(query)
        if method == "dense":
            return self.dense.scores(query)
        return []

    def search(self, query: str, k: int = 5, method: str = "hybrid",
               rrf_k: int = 60) -> list[Hit]:
        if method not in self.methods:
            raise ValueError(f"method must be one of {self.methods}"
                             + ("" if self.dense else " (dense methods need a DenseIndex)"))
        if method in ("bm25", "char", "dense"):
            scores = self._scores(query, method)
        else:                                       # reciprocal rank fusion
            parts = ("bm25", "char") + (("dense",) if method == "hybrid+dense" else ())
            fused: dict[int, float] = {}
            for part in parts:
                for r, i in enumerate(_ranking(self._scores(query, part))):
                    fused[i] = fused.get(i, 0.0) + 1 / (rrf_k + r + 1)
            scores = [fused.get(i, 0.0) for i in range(len(self.chunks))]
        ranked = _ranking(scores)[:k]
        return [Hit(self.chunks[i], scores[i], r + 1) for r, i in enumerate(ranked)]
