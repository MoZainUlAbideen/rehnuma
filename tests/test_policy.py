"""NEPRA index: clause parsing on text shaped like the real PDFs (OCR typos included),
hybrid retrieval, gold matching and the fetch lock. No network, no PDFs needed."""

import json

from rehnuma.evals.policy_retrieval_eval import evaluate, matches
from rehnuma.policy import sources
from rehnuma.policy.parse import (
    clean,
    is_toc_page,
    load_chunks,
    parse_document,
    parse_manual,
    parse_regulations,
    save_chunks,
)
from rehnuma.policy.query import needs_rewrite, rewrite
from rehnuma.policy.retrieve import PolicyIndex
from rehnuma.policy.sources import Document

# Verbatim shape of the Prosumer Regulations 2026 text layer (typos are the PDF's own)
PROSUMER_P1 = clean("""S.R.O. 251(I)/2026.- In exercise of the powers conferred by section 47 of the
Act, the Authority is pleased to make the following regulations, namely:-
1. Short title and commencement.- (1) These regulations shall be called the National
Electric Power Regulatory Authority (Prosumer) Regulations, 2026. (2) They shall come into
force at once.
2. Definitions.- (1) In these regulations, unless there is anything repugnant in the
subject or context, (i) "Act" means the Regulation of Generation, Transmission and
Distribution of Electric Power Act, 1997; (ii) "applicant" means a person who applies to a
licensee; (iii) "billing cycle" means energy recorded by the meters in a period of thirty days;
(iv) "distributed generation facility" means a facility of up to 1 MW set up by a prosumer;
3. Application process forinterconnecting distributed generation facility.— (1) Subject tO
subregulation (2), any applicant who meets the requirements of these regulations shall be
eligible for submitting an application to a licensee as specified in Schedule-IT: Provided
that the licensee shall be bound to provide information free of cost within two working days.
(2) The capacity of a proposed distributed generation facility shall not exceed the
sanctioned load of the applicant's premisbs.""")

PROSUMER_P2 = clean("""14. Billing.— (1) A the end of each billing cycle, following the date of
intercOnnection of distributed generation facility to its distribution system, the licensee shall
raise its bill after taking into account the electricity generated and consumed by the prosumer
under a net billing arrangement as follows: (a) the kWh supplied by licensee to prosumer, shall
be billed in accordance with the applicable tariff. (b) the kWhsupplied by prosumer to the
licensee, shall be billed in accordance with the national average energy purchase price.
(2) In case the billed amount of the kWh supplied by prosumer exceeds the billed amount of kWh
supplied by licensee, the net billed amount shall be credited against prosumer's next billing
cycle or shall be paid by the licensee to the prosurner quarterly. (3) The Authority may revise
the rate provided in sub-regulation (1) through the notification during the subsistence.of the
agreement and the rate so revised shall be deemed incorporated in the agreement.
21. Savings and Repeal.— (1) The National Electric Power Regulatory Authority (Alternative &
Renewable Energy) Distributed Generation and Net Meteiing Regulations, 2015 shall stand repealed
upon coming into force of these regulations. (2) Notwithstanding the repeal effected by these
regulations, nothing shall affect the agreements executed undem the mepealed iegulations:
Provided that the distiibuted geneiatois having valid agreements executed under the repealed
regulations, shall be billed in accordance with the national average power purchase price till
the expiry of the term of their agreement.
SCHEDULE-I
Application form. 1. Name of applicant 2. Address""")

CSM_TOC = clean("\n".join(["TABLE OF CONTENTS"] + [f"4.{i} Some heading ........ {10 + i}"
                                                     for i in range(1, 10)]))
CSM_P1 = clean("""CHAPTER 4
METERING
4.3 DEFECTIVE METERS
4.3.1 In case a meter becomes defective, DISCO shall:
(a) Replace the metering installation immediately or within two billing cycles if meters are
not available.
(b) DISCO may charge bills on average basis i.e. 100% of the consumption recorded in the same
months of previous year or average of the last eleven months whichever is higher for a maximum
period of two months.
4.3.3 If at any time DISCO, doubts the accuracy of any metering installation, DISCO may
check it. (e) In case slowness is established, DISCO shall enhance multiplying factor. Further,
charging of a bill for the quantum of energy lost shall not be more than two previous billing
cycles.
CHAPTER 6
BILLING
6.1.1 Meter reading of all the consumers of DISCO is carried out on a routine basis.
ANNEX-I
Form of complaint 1.1 Name""")

PROSUMER = Document("prosumer-2026", "Prosumer Regulations 2026", "Prosumer Regs 2026",
                     "2026-02-09", "in_force", "regulations", "https://example.invalid/p.pdf")


def _by_clause(chunks):
    return {c.clause: c for c in chunks}


def test_regulations_split_into_subregulations_with_pages():
    ch = _by_clause(parse_regulations("prosumer-2026", [PROSUMER_P1, PROSUMER_P2]))
    for clause in ("1(1)", "1(2)", "3(1)", "3(2)", "14(1)", "14(2)", "14(3)", "21(1)", "21(2)"):
        assert clause in ch, f"missing {clause}; got {sorted(ch)}"
    assert ch["14(2)"].page == 2 and ch["3(2)"].page == 1
    assert ch["14(2)"].heading == "Billing"
    assert ch["14(2)"].path == ["14", "2"]
    assert "quarterly" in ch["14(2)"].text and "revise" not in ch["14(2)"].text


def test_cross_references_do_not_start_a_clause():
    """'subregulation (2), any applicant' and 'sub-regulation (1) through' are references."""
    ch = _by_clause(parse_regulations("prosumer-2026", [PROSUMER_P1, PROSUMER_P2]))
    assert "any applicant" in ch["3(1)"].text
    assert "sub-regulation (1) through" in ch["14(3)"].text


def test_definitions_become_one_chunk_each():
    ch = _by_clause(parse_regulations("prosumer-2026", [PROSUMER_P1, PROSUMER_P2]))
    assert "thirty days" in ch["2(1)(iii)"].text
    assert "1 MW" in ch["2(1)(iv)"].text


def test_schedules_are_not_glued_to_the_last_regulation():
    ch = _by_clause(parse_regulations("prosumer-2026", [PROSUMER_P1, PROSUMER_P2]))
    assert "Schedule-I" in ch
    assert "Name of applicant" not in ch["21(2)"].text


def test_manual_skips_table_of_contents_and_keeps_clause_order():
    assert is_toc_page(CSM_TOC)
    ch = _by_clause(parse_manual("csm-2025", [CSM_TOC, CSM_P1]))
    assert {"4.3", "4.3.1", "4.3.3", "6.1.1", "Annex-I"} <= set(ch)
    assert "two months" in ch["4.3.1"].text
    assert ch["4.3.1"].heading == "CHAPTER 4 METERING > DEFECTIVE METERS"
    assert ch["6.1.1"].heading.startswith("CHAPTER 6 BILLING")
    assert "1.1" not in ch                     # annex numbering is not a manual clause


def test_unrecognised_document_falls_back_to_page_windows():
    doc = Document("x", "X", "X", "2026-01-01", "in_force", "regulations", "u")
    chunks = parse_document(doc, ["Just some text without any numbered structure at all."])
    assert [c.clause for c in chunks] == ["p1"]


def test_long_clauses_are_split_into_parts():
    long = "3. Something.— (1) " + " ".join(f"Sentence number {i} is here." for i in range(200))
    chunks = parse_regulations("d", [long])
    assert len(chunks) > 1 and all(len(c.text) <= 1600 for c in chunks)
    assert chunks[0].id.endswith("#1") and chunks[0].clause == "3(1)"


def _index():
    return PolicyIndex(parse_regulations("prosumer-2026", [PROSUMER_P1, PROSUMER_P2])
                       + parse_manual("csm-2025", [CSM_TOC, CSM_P1]))


def test_hybrid_retrieval_finds_the_answering_clause():
    idx = _index()
    assert idx.search("can my solar be bigger than my sanctioned load")[0].chunk.clause == "3(2)"
    assert idx.search("defective meter average bill how many months")[0].chunk.clause == "4.3.1"
    top = [h.chunk.clause for h in idx.search("excess credit carried forward or paid quarterly")]
    assert "14(2)" in top[:2]


def test_char_ngrams_survive_ocr_typos():
    """BM25 cannot match 'prosumer' to the PDF's 'prosurner'; character n-grams can."""
    idx = PolicyIndex([c for c in _index().chunks if c.clause == "14(2)"]
                      + [c for c in _index().chunks if c.clause == "1(1)"])
    assert idx.search("prosumer paid quarterly", method="char")[0].chunk.clause == "14(2)"


def test_gold_matching_uses_path_prefix_and_phrase():
    ch = _by_clause(parse_regulations("prosumer-2026", [PROSUMER_P1, PROSUMER_P2]))
    assert matches(ch["14(2)"], {"doc": "prosumer-2026", "path": ["14", "2"]})
    assert matches(ch["14(2)"], {"doc": "prosumer-2026", "path": ["14"]})
    assert not matches(ch["14(2)"], {"doc": "prosumer-2026", "path": ["1"]})     # not "14"
    assert matches(ch["2(1)(iii)"], {"doc": "prosumer-2026", "path": ["2"],
                                     "contains": "thirty  days"})
    assert not matches(ch["2(1)(ii)"], {"doc": "prosumer-2026", "path": ["2"],
                                        "contains": "thirty days"})


def test_eval_separates_parser_misses_from_retrieval_misses():
    qs = [{"id": "ok", "lang": "en", "q": "sanctioned load capacity",
           "gold": [{"doc": "prosumer-2026", "path": ["3", "2"]}]},
          {"id": "gone", "lang": "en", "q": "late payment surcharge",
           "gold": [{"doc": "csm-2025", "path": ["9", "9"]}]}]
    rep = evaluate(_index(), qs)
    assert rep["not_in_index"] == ["gone"]
    assert rep["summary"]["dev/en"]["hybrid"]["n"] == 1                # scored over "ok" only
    assert rep["summary"]["dev/en"]["hybrid"]["hit@5"] == 1.0


class FakeLLM:
    name = "fake"

    def __init__(self, reply):
        self.reply, self.calls = reply, 0

    def complete(self, system, user):
        self.calls += 1
        return self.reply


def test_only_urdu_questions_are_rewritten():
    llm = FakeLLM("defective meter average bill maximum months\n")
    assert rewrite("defective meter", llm) == ("defective meter", None) and llm.calls == 0
    assert needs_rewrite("میرا میٹر خراب ہے")
    assert rewrite("میرا میٹر خراب ہے", llm)[0] == "defective meter average bill maximum months"


def test_chunks_round_trip(tmp_path):
    chunks = parse_regulations("prosumer-2026", [PROSUMER_P1, PROSUMER_P2])
    save_chunks(chunks, tmp_path / "c.jsonl")
    assert load_chunks(tmp_path / "c.jsonl") == chunks


def test_fetch_flags_a_changed_document(tmp_path, monkeypatch):
    monkeypatch.setattr(sources, "RAW", tmp_path)
    doc = Document("d", "D", "D", "2026-01-01", "in_force", "regulations", "https://x.invalid")
    lock = tmp_path / "lock.json"
    monkeypatch.setattr(sources, "_download", lambda url: b"%PDF-1.4 version one")
    monkeypatch.setattr(sources.time, "sleep", lambda s: None)
    assert sources.fetch([doc], lock_path=lock)[0].startswith("downloaded")
    monkeypatch.setattr(sources, "_download", lambda url: b"%PDF-1.4 version TWO")
    assert "CHANGED" in sources.fetch([doc], force=True, lock_path=lock)[0]
    assert json.loads(lock.read_text())["d"]["sha256"] == sources.sha256(tmp_path / "d.pdf")


def test_non_pdf_response_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(sources, "RAW", tmp_path)
    monkeypatch.setattr(sources, "_download", lambda url: b"<html>blocked</html>")
    doc = Document("d", "D", "D", "2026-01-01", "in_force", "regulations", "https://x.invalid")
    assert sources.fetch([doc], lock_path=tmp_path / "l.json")[0].startswith("FAILED")


def test_real_sources_file_is_valid():
    docs = sources.load_sources()
    ids = {d.id for d in docs}
    assert {"prosumer-2026", "csm-2025", "nm-2015"} <= ids
    for d in docs:
        assert d.url.startswith("https://nepra.org.pk/")
        assert d.repealed_by in (None, *ids) and d.amends in (None, *ids)


def test_ocr_heading_variants_from_the_real_pdfs():
    """Each line is verbatim from a real NEPRA PDF's text layer."""
    text = clean(
        "I. Short title, cornrnecement. — (1) These Regulations may be called the Regulations.\n"
        "(2) They shall come into force at once.\n"
        "2. Definitions.— (1) In these regulations the words mean what they say here.\n"
        "3. Concurrence. --- (1) Notwithstanding anything contained, a prosumer shall seek it.\n"
        "4. Rights and obligations of the prosumer. (1) A prosurner shall operate its facility.\n"
        "(2) The prosumer shall maintain it.\n"
        "5. Protection Requirements.— (I) The protection diagrams shall be approved.\n"
        "-(2) The. prosumer shall install the equipment for interconnection.\n"
        "as may be notified from time to time..— 6 Prevention of interfei en e — (1) '1 he "
        "prosurner shall not interfere.\n"
        "7-. Voltage andfrequency rânge. —A variation of 5% is permissible to the voltage.\n")
    ch = _by_clause(parse_regulations("d", [text]))
    for clause in ("1(1)", "1(2)", "3(1)", "4(1)", "4(2)", "5(1)", "5(2)", "6(1)", "7"):
        assert clause in ch, f"missing {clause}; got {sorted(ch)}"
    assert ch["4(1)"].heading == "Rights and obligations of the prosumer"


def test_manual_wrapped_sentence_is_not_a_title():
    """Regression: a wrapped first line ('...on a routine basis each') became the heading of
    every sub-clause, spreading billing words over all of Chapter 6."""
    text = clean("CHAPTER 6\nMETER READING AND BILLING\n6.1 METER READING\n"
                 "6.1.1 Meter reading of all the consumers of DISCO is carried out on a routine "
                 "basis each\nmonth by the meter reader.\n"
                 "6.1.1.1 In the event of force majeure pro-rata billing applies.\n")
    ch = _by_clause(parse_manual("csm", [text]))
    assert ch["6.1.1.1"].heading == "CHAPTER 6 METER READING AND BILLING > METER READING"


class FakeEncoder:
    """Bag-of-concepts 'embedding': maps lay words and legal words to the same axis, which is
    what a real multilingual model learns. Lets us test the dense plumbing offline."""
    name = "fake/encoder"
    AXES = [("export", "supplied by prosumer", "بھیج"), ("sanctioned", "منظور"),
            ("meter", "میٹر"), ("agreement", "معاہدہ")]

    def __init__(self):
        self.passages = 0

    def _vec(self, t):
        t = t.lower()
        return [float(sum(w in t for w in axis)) + 0.01 for axis in self.AXES]

    def encode_queries(self, texts):
        return [self._vec(t) for t in texts]

    def encode_passages(self, texts):
        self.passages += len(texts)
        return [self._vec(t) for t in texts]


def test_dense_ranker_bridges_vocabulary_and_language(tmp_path):
    from rehnuma.policy.dense import DenseIndex
    chunks = parse_regulations("prosumer-2026", [PROSUMER_P1, PROSUMER_P2])
    idx = PolicyIndex(chunks, dense=DenseIndex(chunks, FakeEncoder(), cache_dir=tmp_path))
    assert "hybrid+dense" in idx.methods
    top = idx.search("میرے بھیجے گئے یونٹ", method="dense")[0].chunk.clause   # Urdu, no rewrite
    assert top in ("14(1)", "14(2)")


def test_dense_cache_only_reencodes_changed_chunks(tmp_path):
    from rehnuma.policy.dense import DenseIndex
    chunks = parse_regulations("prosumer-2026", [PROSUMER_P1, PROSUMER_P2])
    enc = FakeEncoder()
    DenseIndex(chunks, enc, cache_dir=tmp_path)
    first = enc.passages
    chunks[0].text += " amended"
    again = DenseIndex(chunks, enc, cache_dir=tmp_path)
    assert first == len(chunks) and again.encoded == 1


def test_dense_methods_refused_without_a_model():
    idx = _index()
    assert "dense" not in idx.methods
    try:
        idx.search("x", method="dense")
    except ValueError as e:
        assert "DenseIndex" in str(e)
    else:
        raise AssertionError("dense search without a model must fail loudly")
