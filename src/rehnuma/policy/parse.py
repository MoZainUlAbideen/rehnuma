"""NEPRA PDF -> clause-level chunks with citations.

A chunk is one legal unit - "reg. 14(2)" of the Prosumer Regulations, "4.3.1" of the
Consumer Service Manual - so an answer can cite exactly what it relies on, and a human can
check it on the printed page.

What the real documents look like (and why the parser is shaped this way):
  * Regulations: headings run inline - "14. Billing.— (1) At the end ... (2) In case ...".
    The text layer is OCR output with typos ("prosurner", "Meteiing"), so headings are
    matched loosely and then filtered by NUMBERING ORDER: regulation n+1 must follow n.
    Cross-references ("regulation 3. The") are rejected by that order and by context.
  * Manual: dotted clauses at the start of a line ("4.3.1 ..."), chapter headings, a table
    of contents that repeats every number (skipped - it would break the order filter),
    annexures at the end.
  * Amendments (1-2 page S.R.O.s): no stable structure -> page windows.
"""

from __future__ import annotations

import json
import re
from bisect import bisect_right
from dataclasses import asdict, dataclass
from pathlib import Path

from rehnuma.policy.sources import POLICY_DIR, Document

CHUNKS = POLICY_DIR / "chunks.jsonl"
MAX_CHARS = 1600          # longer clauses are split into parts (#1, #2...) at sentence ends
TARGET_CHARS = 1100


@dataclass
class Chunk:
    id: str               # "prosumer-2026:14(2)", "csm-2025:4.3.1#2"
    doc_id: str
    clause: str           # "14(2)", "2(1)(viii)", "4.3.1", "Schedule-I", "preamble", "p1"
    path: list[str]       # ["14", "2"] - gold labels match on a prefix of this
    heading: str          # "Billing" / "CHAPTER 4 METERING > DEFECTIVE METERS"
    page: int             # 1-based page where the clause starts
    text: str

    @property
    def search_text(self) -> str:
        return f"{self.heading} {self.text}"


# --- text cleanup -----------------------------------------------------------
_DASHES = re.compile(r"[‒–—―−]")
_PAGE_NO = re.compile(r"(?im)^\s*(?:page\s*)?\d{1,3}(?:\s*(?:of|/)\s*\d{1,3})?\s*$")


def clean(text: str) -> str:
    text = text.replace(" ", " ").replace("“", '"').replace("”", '"')
    text = _DASHES.sub("—", text)
    text = re.sub(r"\.\s*-{1,4}\s+", ".— ", text)         # OCR'd ".-" / ". ---" heading dash
    text = re.sub(r"(?m)^[ \t]*[Il]\.(?=\s+[A-Z])", "1.", text)  # OCR'd "1." as "I." / "l."
    text = _PAGE_NO.sub("", text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def extract_pages(pdf: Path) -> list[str]:
    from pypdf import PdfReader  # only needed for ingest
    return [clean(p.extract_text() or "") for p in PdfReader(str(pdf)).pages]


class _Pages:
    """Pages joined into one string, remembering where each page starts."""

    def __init__(self, pages: list[str]):
        self.starts, parts, pos = [], [], 0
        for p in pages:
            self.starts.append(pos)
            parts.append(p)
            pos += len(p) + 1
        self.text = "\n".join(parts)

    def page_of(self, offset: int) -> int:
        return bisect_right(self.starts, offset)


def _split_long(text: str) -> list[str]:
    if len(text) <= MAX_CHARS:
        return [text]
    sentences = re.split(r"(?<=[.;:])\s+(?=[A-Z(\"])", text)
    parts, cur = [], ""
    for s in sentences:
        if cur and len(cur) + len(s) > TARGET_CHARS:
            parts.append(cur)
            cur = ""
        cur = f"{cur} {s}".strip()
    if cur:
        parts.append(cur)
    out = []                         # a single sentence can still be huge: hard-wrap it
    for p in parts:
        out += [p[i:i + MAX_CHARS] for i in range(0, len(p), MAX_CHARS)]
    return out


def _emit(doc_id, clause, path, heading, page, text) -> list[Chunk]:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < 15:
        return []
    parts = _split_long(text)
    if len(parts) == 1:
        return [Chunk(f"{doc_id}:{clause}", doc_id, clause, path, heading, page, text)]
    return [Chunk(f"{doc_id}:{clause}#{i}", doc_id, clause, path, heading, page, p)
            for i, p in enumerate(parts, 1)]


# --- regulations ------------------------------------------------------------
# "14. Billing.— (1)"; also "6. Rights and obligations of the prosumer. (1)" (no dash at all
# in the real PDF) - a title then straight into sub-regulation (1)
# OCR also gives "— 10 Prevention of interfei en e — (1)" and "11-. Voltage andfrequency rânge. —"
_REG_HEAD = re.compile(r"(?<![\w(/.])(\d{1,2})\s?([.,\-]{0,2})\s+"          # number, separator
                       r"([A-Z][^—\n]{1,120}?(?:\n[^—\n]{1,80}?)?)"          # title (may wrap)
                       r"(?:\s*—|\.(?=\s+[({]\s*1\s*\)))")                  # dash, or ". (1)"
_XREF = re.compile(r"(?i)(regulation|clause|section|rule|para(?:graph)?|schedule|no|s\.r\.o)\s*$")
_SUBREG = re.compile(r"[({]\s*(\d{1,2}|I|l)\s*\)\s+(?=[A-Z\"'])")   # OCR reads (1) as (I)
_ROMAN_ITEM = re.compile(r"\(([ivxl]{1,6})\)\s+(?=[\"'])")
_SCHEDULE = re.compile(r"(?m)^\s*SCHEDULE[\s\-—]*([IVX]{1,4})\b")
_ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50}


def _roman(s: str) -> int:
    total = 0
    for a, b in zip(s, s[1:] + " ", strict=True):
        v = _ROMAN[a]
        total += -v if b != " " and _ROMAN[b] > v else v
    return total


def _in_order(matches, number, prefix_ok=lambda m: True):
    """Keep matches whose number continues the sequence 1, 2, 3... (one gap allowed)."""
    out, expected = [], 1
    for m in matches:
        n = number(m)
        if n in (expected, expected + 1) and prefix_ok(m):
            out.append(m)
            expected = n + 1
    return out


def _with_next(items: list) -> list[tuple]:
    """[(a, b), (b, c), (c, None)] - each boundary with the one after it."""
    return list(zip(items, [*items[1:], None], strict=False)) if items else []


def _longest_increasing(matches, number):
    """Longest strictly increasing run of numbers (gaps allowed). A page with no text layer
    can hide regulations 4-13; "next number only" would then drop everything after it."""
    nums = [number(m) for m in matches]
    best = [1] * len(nums)
    prev = [-1] * len(nums)
    for i in range(len(nums)):
        for j in range(i):
            if nums[j] < nums[i] and best[j] + 1 > best[i]:
                best[i], prev[i] = best[j] + 1, j
    if not nums:
        return []
    i = max(range(len(nums)), key=lambda x: (best[x], -x))
    out = []
    while i != -1:
        out.append(matches[i])
        i = prev[i]
    return out[::-1]


def _preceded_ok(text: str, start: int) -> bool:
    before = text[max(0, start - 20):start]
    if _XREF.search(before):
        return False
    stripped = before.rstrip()
    return (not stripped or stripped[-1] in ".:;—)-" or before.endswith("\n")
            or bool(re.search(r"\n\s*-?\s*$", before)))


def _reg_heads(text: str) -> list[re.Match]:
    """Heading candidates, tried at EVERY number (overlapping). A plain finditer let
    "up to 1 MW set up by ...;\n3. Application process ...—" match as a heading for
    "regulation 1" and swallow the real "3." inside it."""
    out = []
    for n in re.finditer(r"(?<![\w(/.])\d{1,2}(?!\d)", text):
        m = _REG_HEAD.match(text, n.start())
        if not m or not _preceded_ok(text, m.start()):
            continue
        if not m.group(2):              # "10 Prevention" (no full stop): only after a dash/newline
            before = text[max(0, m.start() - 4):m.start()]
            if not re.search(r"(—|\n)\s*$", before):
                continue
        out.append(m)
    return out


def _split_subregs(body: str) -> list[tuple[str, str]]:
    """'(1) At the end ... (2) In case ...' -> [('1', text), ('2', text)]; a clause
    marker counts only after a sentence end, so 'sub-regulation (2), the' does not."""
    marks = [m for m in _SUBREG.finditer(body) if _preceded_ok(body, m.start())]
    marks = _in_order(marks, _subreg_no)
    if not marks:
        return [("", body)]
    out = [("", body[:marks[0].start()])] if body[:marks[0].start()].strip() else []
    for m, nxt in _with_next(marks):
        out.append((str(_subreg_no(m)), body[m.end():nxt.start() if nxt else len(body)]))
    return out


def _subreg_no(m: re.Match) -> int:
    return 1 if m.group(1) in ("I", "l") else int(m.group(1))


def _split_definitions(text: str) -> list[tuple[str, str]]:
    marks = _in_order(list(_ROMAN_ITEM.finditer(text)), lambda m: _roman(m.group(1)))
    if len(marks) < 3:
        return [("", text)]
    out = [("", text[:marks[0].start()])]
    for m, nxt in _with_next(marks):
        out.append((m.group(1), text[m.end():nxt.start() if nxt else len(text)]))
    return out


def parse_regulations(doc_id: str, pages: list[str]) -> list[Chunk]:
    P = _Pages(pages)
    text = P.text
    heads = _longest_increasing(_reg_heads(text), lambda m: int(m.group(1)))
    first_sched = next((m for m in _SCHEDULE.finditer(text)
                        if not heads or m.start() > heads[-1].start()), None)
    end_regs = first_sched.start() if first_sched else len(text)
    chunks: list[Chunk] = []
    if heads and heads[0].start() > 0:
        chunks += _emit(doc_id, "preamble", ["preamble"], "Preamble", 1,
                        text[:heads[0].start()])
    for h, nxt in _with_next(heads):
        num, title = h.group(1), " ".join(h.group(3).split()).rstrip(" .,")
        body = text[h.end():nxt.start() if nxt else end_regs]
        page = P.page_of(h.start())
        for sub, sub_text in _split_subregs(body):
            clause = f"{num}({sub})" if sub else num
            path = [num, sub] if sub else [num]
            for item, item_text in _split_definitions(sub_text):
                c = f"{clause}({item})" if item else clause
                chunks += _emit(doc_id, c, path + ([item] if item else []), title, page,
                                item_text)
    scheds = [m for m in _SCHEDULE.finditer(text) if m.start() >= end_regs]
    for s, nxt in _with_next(scheds):
        name = f"Schedule-{s.group(1)}"
        chunks += _emit(doc_id, name, [name], name, P.page_of(s.start()),
                        text[s.end():nxt.start() if nxt else len(text)])
    return chunks


# --- manual -----------------------------------------------------------------
_CHAPTER = re.compile(r"(?m)^\s*CHAPTER\s*[-—:]?\s*(\d{1,2}|[IVX]{1,5})\b[ \t.:—-]*([^\n]*)")
_CLAUSE = re.compile(r"(?m)^[ \t]*(\d{1,2}(?:\.\d{1,2}){1,3})\.?[ \t]+(?=\S)")
_ANNEX = re.compile(r"(?m)^\s*ANNEX(?:URE)?[\s\-—]*([A-Z0-9]{1,4})\b")


def is_toc_page(page: str) -> bool:
    lines = [ln for ln in page.splitlines() if ln.strip()]
    if re.search(r"(?i)table\s+of\s+contents|^\s*contents\s*$", page, re.M):
        return True
    if len(lines) < 8:
        return False
    tail_num = sum(bool(re.search(r"(\.{3,}|\s)\d{1,3}\s*$", ln)) for ln in lines)
    return tail_num / len(lines) > 0.5


def _title_of(body: str) -> str | None:
    """A clause is a heading if its whole body is one short line ("4.3 METER REPLACEMENT")
    or its first line is short and in capitals. NOT "the first line lacks a full stop":
    PDF text wraps mid-sentence, and that rule once stamped "Meter reading of all the
    consumers of DISCO is carried out on a routine basis each" onto every clause under
    6.1.1, flooding CHAPTER 6 with billing words that outranked the real answers."""
    t = body.strip()
    if 0 < len(t) <= 100 and "\n" not in t:
        return t.rstrip(" .:")
    first = t.split("\n", 1)[0].strip()
    letters = [c for c in first if c.isalpha()]
    if 0 < len(first) <= 90 and len(letters) >= 4 and \
            sum(c.isupper() for c in letters) / len(letters) > 0.7:
        return first.rstrip(" .:")
    return None


def parse_manual(doc_id: str, pages: list[str]) -> list[Chunk]:
    pages = ["" if is_toc_page(p) else p for p in pages]
    P = _Pages(pages)
    text = P.text
    annex = next(iter(_ANNEX.finditer(text)), None)
    body_end = annex.start() if annex else len(text)

    chapters = []                                 # (offset, "CHAPTER 4 METERING")
    for m in _CHAPTER.finditer(text[:body_end]):
        title = m.group(2).strip()
        if sum(c.isalpha() for c in title) < 4:   # title on a later line, after logo junk ("y*")
            following = text[m.end():m.end() + 300].split("\n")
            title = next((ln.strip() for ln in following if sum(c.isalpha() for c in ln) >= 4),
                         "")
        chapters.append((m.start(), f"CHAPTER {m.group(1)} {title}".strip()))

    def chapter_no(offset: int) -> int | None:
        nums = [n for off, n in chapter_nums if off <= offset]
        return nums[-1] if nums else None

    chapter_nums = [(m.start(), int(m.group(1))) for m in _CHAPTER.finditer(text[:body_end])
                    if m.group(1).isdigit()]
    candidates = []
    for m in _CLAUSE.finditer(text[:body_end]):
        key = tuple(int(x) for x in m.group(1).split("."))
        ch = chapter_no(m.start())
        if ch is None or key[0] == ch:            # "4.3.1" must sit inside CHAPTER 4
            candidates.append((key, m))
    accepted = [m for _, m in _longest_increasing(candidates, lambda c: c[0])]

    chunks: list[Chunk] = []
    titles: dict[tuple, str] = {}
    for m, nxt in _with_next(accepted):
        num = m.group(1)
        key = tuple(num.split("."))
        body = text[m.end():nxt.start() if nxt else body_end]
        if title := _title_of(body):
            titles[key] = title
        chapter = next((t for off, t in reversed(chapters) if off <= m.start()), "")
        ancestors = [titles[key[:i]] for i in range(1, len(key)) if key[:i] in titles]
        heading = " > ".join([chapter, *ancestors]).strip(" >")
        chunks += _emit(doc_id, num, list(key), heading, P.page_of(m.start()), body)

    annexes = list(_ANNEX.finditer(text))
    for a, nxt in _with_next(annexes):
        name = f"Annex-{a.group(1)}"
        chunks += _emit(doc_id, name, [name], name, P.page_of(a.start()),
                        text[a.end():nxt.start() if nxt else len(text)])
    return chunks


# --- fallback: page windows ------------------------------------------------
def parse_pages(doc_id: str, pages: list[str], heading: str = "") -> list[Chunk]:
    out: list[Chunk] = []
    for i, p in enumerate(pages, 1):
        out += _emit(doc_id, f"p{i}", [f"p{i}"], heading, i, p)
    return out


def parse_document(doc: Document, pages: list[str]) -> list[Chunk]:
    if doc.style == "regulations":
        chunks = parse_regulations(doc.id, pages)
    elif doc.style == "manual":
        chunks = parse_manual(doc.id, pages)
    else:
        chunks = []
    if len(chunks) < 3:            # structure not recognised: never silently drop a document
        heading = f"Amends {doc.amends}" if doc.amends else doc.short
        chunks = parse_pages(doc.id, pages, heading)
    return chunks


# --- chunk store ------------------------------------------------------------
def save_chunks(chunks: list[Chunk], path: Path = CHUNKS) -> None:
    path.write_text("".join(json.dumps(asdict(c), ensure_ascii=False) + "\n" for c in chunks),
                    encoding="utf-8")


def load_chunks(path: Path = CHUNKS) -> list[Chunk]:
    return [Chunk(**json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]
