"""Dense multilingual retrieval: a Hugging Face feature-extraction model as a third ranker.

Why: the real eval showed a vocabulary gap BM25 cannot cross - people say "export" and
"solar", the regulations say "kWh supplied by prosumer to the licensee" and "distributed
generation facility". An embedding model matches meaning, not spelling. A multilingual
one also embeds Urdu questions straight into the same space as the English clauses, so
Urdu retrieval needs no LLM translation call.

Default: intfloat/multilingual-e5-small (118M params, runs on CPU, ~100 languages incl.
Urdu). E5 models expect "query: " / "passage: " prefixes. Passage vectors are cached per
chunk in data/policy/embeddings/ (git-ignored) keyed by a hash of the text, so re-ingesting
only re-encodes clauses that changed.

    uv sync --extra dense          # installs sentence-transformers (+ torch, CPU)
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Protocol

from rehnuma.policy.parse import Chunk
from rehnuma.policy.sources import POLICY_DIR

DEFAULT_MODEL = "intfloat/multilingual-e5-small"
CACHE_DIR = POLICY_DIR / "embeddings"


class Encoder(Protocol):
    name: str

    def encode_queries(self, texts: list[str]) -> list[list[float]]: ...

    def encode_passages(self, texts: list[str]) -> list[list[float]]: ...


class HFEncoder:
    """sentence-transformers wrapper; downloads the model from the Hugging Face Hub once."""

    def __init__(self, model: str = DEFAULT_MODEL):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise RuntimeError("dense retrieval needs: uv sync --extra dense") from e
        self.name = model
        self.model = SentenceTransformer(model)
        e5 = "e5" in model.lower()
        self._q, self._p = ("query: ", "passage: ") if e5 else ("", "")

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vecs = self.model.encode(texts, batch_size=32, normalize_embeddings=True,
                                 show_progress_bar=len(texts) > 64)
        return [list(map(float, v)) for v in vecs]

    def encode_queries(self, texts: list[str]) -> list[list[float]]:
        return self._encode([self._q + t for t in texts])

    def encode_passages(self, texts: list[str]) -> list[list[float]]:
        return self._encode([self._p + t for t in texts])


def _digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class DenseIndex:
    def __init__(self, chunks: list[Chunk], encoder: Encoder, cache_dir: Path | None = CACHE_DIR):
        self.encoder = encoder
        cache_file = (cache_dir / f"{encoder.name.replace('/', '__')}.json") if cache_dir else None
        cache = (json.loads(cache_file.read_text(encoding="utf-8"))
                 if cache_file and cache_file.exists() else {})
        texts = [c.search_text for c in chunks]
        todo = [i for i, (c, t) in enumerate(zip(chunks, texts, strict=True))
                if cache.get(c.id, {}).get("h") != _digest(t)]
        if todo:
            for i, v in zip(todo, encoder.encode_passages([texts[i] for i in todo]), strict=True):
                cache[chunks[i].id] = {"h": _digest(texts[i]), "v": [round(x, 5) for x in v]}
            if cache_file:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps(cache), encoding="utf-8")
        self.encoded = len(todo)
        self.vecs = [_normalize(cache[c.id]["v"]) for c in chunks]

    def scores(self, query: str) -> list[float]:
        q = _normalize(self.encoder.encode_queries([query])[0])
        return [sum(a * b for a, b in zip(q, v, strict=True)) for v in self.vecs]
