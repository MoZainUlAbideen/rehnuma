# Policy retrieval eval — NEPRA documents

Does the clause that answers a household's question come back in the top 5? That is the
ceiling for everything the policy guide will say: an answer can only cite what retrieval
found.

## Setup

- **Corpus:** 5 official NEPRA PDFs — Prosumer Regulations 2026, Net Metering Regulations
  2015 + its 2017 and 2018 amendments, Consumer Service Manual 2025. 566 clause-level chunks.
- **Questions:** 35, each with a gold clause checked against the PDF text.
  - `dev` (22): seen while fixing the parser and retrieval.
  - `heldout` (13): written from the clause text *before* any tuning, never tuned on.
  - 8 are in Urdu, the product's default language.
- **Metrics:** hit@1, hit@5, MRR. Questions whose gold clause the *parser* never produced are
  listed separately, so a parsing bug cannot pass as a retrieval score.
- **Caveat:** Urdu has n=6 (dev) and n=2 (held-out). One question moves those rows by 17–50
  points; read them as direction, not precision.

## What the real PDFs broke

The parser was first written against text pulled from the PDFs, then run on the real files.
Each bug below was found by the eval or the ingest report, not guessed:

| Symptom | Cause | Fix |
|---|---|---|
| Regs 1, 4, 6, 10, 11 of the 2026 rules missing | OCR: "I." for 1, ". ---", no dash, no full stop ("— 10 Prevention"), "(I)" for (1) | Tolerant heading pattern + numbering-order filter (longest increasing run) |
| Fixture reg. 3 vanished after loosening the pattern | "up to 1 MW set up by…;↵3. Application…—" matched as a heading and swallowed the real "3." | Candidates tried at every number (overlapping) |
| Billing words flooded all of CSM Chapter 6 | A wrapped mid-sentence line was taken as a clause *title* and stamped on every sub-clause | A title is a short line or a line in capitals, not "no full stop" |
| Chapter titles "y*", "£3" | A logo sits between "CHAPTER 3" and its title | Take the first line with real words |
| nm-2015 reg. 18 = 16,000 chars; 2026 reg. 21(3) = 14,000; CSM 16.8 = 22,000 | "Schedule-I", "Schedule - H" (II), "Annexure -1" matched only in uppercase — all end matter glued to the last clause | Case-insensitive, OCR-tolerant numerals, heading alone on its line, annexures only after the last chapter |
| One regulation filled 3 of the top-3 slots | Long clause split into parts, each ranked separately | One hit per clause |

Known limit: 2015 reg. 8 is printed as "S. Termination of Agrei"; its text stays under reg. 7.

## Correction: ties

Reciprocal rank fusion produces exact ties (1st + 2nd = 2nd + 1st). 4 of 27 English
questions tied at rank 1, and the search broke ties by the order of chunks in the file.
Earlier hit@1 figures (38% dev, 55–64% held-out for lexical hybrid) were partly that luck.
Ties are now broken by BM25 rank on the user's own words, then by chunk id; a test shuffles
the corpus and requires identical results. All numbers below use the new tie-break.

## Results

Lexical hybrid (BM25 + char n-grams, one hit per clause):

| Setting | dev/en hit@1 · hit@5 · MRR | heldout/en | dev/ur | heldout/ur |
|---|---|---|---|---|
| No rewrite | 25% · 88% · 0.49 | 45% · 91% · 0.67 | 0% · 0% · 0.00 | 0% · 0% · 0.00 |
| Rewrite Urdu only | 25% · 88% · 0.49 | 45% · 91% · 0.67 | 33% · 67% · 0.47 | 50% · 100% · 0.60 |
| Rewrite all, question + rewrite **concatenated** | 31% · 75% · 0.48 | 55% · 91% · 0.73 | 33% · 67% | 50% · 100% |
| Rewrite all, **fused** (two queries, RRF) | 31% · 81% · 0.51 | 64% · 91% · 0.77 | 33% · 67% | 50% · 100% |
| Rewrite all, fused, **source names stripped** | **38% · 88% · 0.57** | **64% · 91% · 0.76** | **50% · 67% · 0.58** | 50% · 100% · 0.67 |
| Same + **new rewrite prompt** (fresh Groq run) | 38% · **94%** · 0.59 | 55% · 91% · 0.73 | 50% · **83%** · 0.64 | 50% · 100% · 0.75 |

Rewrites were generated once by Groq gpt-oss-120b and **replayed** for every row after the
first (`--replay`), so the rows differ only in retrieval, not in LLM sampling.

Earlier runs (file-order tie-break, before the schedule fix) with the multilingual
**e5-small** embeddings: no gain in English (held-out hit@5 91% → 82% when fused in), and
17% hit@5 on raw Urdu questions (dev). Kept optional (`--dense`), not the default.

## What the rewrite experiments showed

- **Concatenating** question + rewrite into one query diluted the user's own precise words:
  it fixed p1 (4 → 1) but broke p3 (1 → 5), p4 and c2. Dev hit@5 88% → 75%.
- **Fusing** them as two queries lets the rewrite add candidates without removing any.
- The rewriter appended **source names** ("NEPRA Consumer Service Manual", "NEPRA
  regulations") to 6 of 27 English rewrites. Those words occur all over the corpus and
  pulled p4 into CSM billing clauses. They are now stripped before searching, and the
  prompt asks for no document names, no new topics, and every stated condition kept.
- **The new prompt fixed p4** (grandfathered export price, Prosumer Regs 21(2)): not in the
  top 5 → rank 2. Held-out hit@1 moved by one question (h3, rank 1 → 2) - run-to-run LLM
  variation, and the prompt change targeted a dev question, so no held-out gain is claimed.
  p4-ur (the Urdu twin) still misses: its rewrite still drops "existing agreement".
- *Previously* failing: p4 ("I got net metering before 2026, how are my exports priced now?" →
  Prosumer Regs 21(2)). The rewrite dropped "existing agreement". This is the question that
  decides a grandfathered household's export price; it needs a fresh run with the new
  prompt, and the answer layer should always pull 21(2) for grandfathering questions.

## Decisions

1. **Production retrieval: lexical hybrid, with an LLM rewrite fused as a second query**
   (English and Urdu), source names stripped. It matches or beats no-rewrite on every row.
2. **Urdu depends on the rewrite** (0% without it). If Groq is down, English still works and
   Urdu falls back to keyword search — the answer layer must say so rather than guess.
3. **Dense embeddings stay optional**; a stronger multilingual model (bge-m3) is backlog.
4. Small-n caveat stands: held-out English is 11 questions (one question = 9 points), Urdu 8.

## Answer layer

`rehnuma-policy ask "..."` answers from the top-5 clauses as [S1]..[S5] and a
deterministic critic checks every draft: tags exist, every sentence is tagged, every number
appears in a cited source ("thirty days" supports "30 days"; Urdu digits normalised), the
language matches, and a repealed source is called old. One retry with the problem list
(never the answer); then an honest fallback listing the clauses. NOT_FOUND → refusal in the
user's language. `rehnuma-eval-answer` measures answered / first-draft / fallback / false
refusal, whether the gold clause is cited, a checkable fact per question, and refusal on 6
out-of-scope questions.

### First answer run (held-out + out-of-scope, gpt-oss-120b)

| Split | n | answered | first draft | fallback | false refusal | cites gold | fact correct |
|---|---|---|---|---|---|---|---|
| held-out, English | 11 | 91% | 45% | 9% | 0% | 90% | 100% (n=3) |
| held-out, Urdu | 2 | 100% | 100% | 0% | 0% | 100% | 100% (n=2) |
| out of scope | 6 | refused 100% | | | | | |

Most retries were the "every sentence tagged" rule (the model tagged only the last
sentence); each retry fixed it. h5 fell back only because "2026" was in the source header the
model saw but not in the clause text - the critic now checks numbers against exactly what
the model was shown.

**The important failure was not in these numbers.** The family's own question, in Urdu -
"my net metering was installed before 2026, at what rate are my units counted now?" - got a
confident, cited, *wrong* answer: "the price stays under the old 2015 rules until the
agreement ends", citing 2015 reg. 14(2). The real rule is Prosumer Regs 21(2): billing moves
to net billing (reg. 14 of 2026) from the next cycle, with exports priced at the national
average *power* purchase price until the agreement expires. Two causes:

1. Retrieval returned five clauses of the repealed 2015 rules and missed 21(2) (p4-ur).
2. Each repealed source was shown with a `note` from our own metadata - a paraphrase
   ("keep their export price until the term ends") - and the model repeated it as if it
   were NEPRA's text. h3 invented "a repealed rule that still applies to existing
   agreements" from the same note.

Fix (structural, not a prompt tweak): the note no longer states any rule; every repealed
document names its **savings clause** (`savings_clause` in sources.json), which is always
added to the sources next to any retrieved clause of that document; and the critic rejects
an answer that relies on a repealed source without citing the savings clause.

### Second answer run (after the savings-clause fix)

| Split | n | answered | first draft | false refusal | cites gold | fact correct* |
|---|---|---|---|---|---|---|
| held-out, English | 11 | 100% | 73% | 0% | 91% | 100% (n=3) |
| held-out, Urdu | 2 | 100% | 100% | 0% | 100% | 100% (n=2) |
| dev, English | 16 | 88% | 81% | 12% | 93% | 89% (n=9) |
| dev, Urdu | 6 | 100% | 100% | 0% | 100% | 75% (n=4) |

\*The Urdu fact check for p4 was **too loose** and scored a wrong answer as correct - see below.

p4 in English is now exactly right: power purchase price until the term ends, energy
purchase price for renewals, citing 21(2) and 14(1). The family's question now cites 21(2),
**but its Urdu says "qaumi ausat tawanai khareedari qeemat" - the national average ENERGY
purchase price.** 21(2) says POWER. p4-ur dropped the word altogether ("qaumi ausat
khareedari qeemat"). The model translates rate names, and in Urdu the two legally different
rates collapse into near-identical phrases. The critic could not see it (numbers and
citations were right), and the eval's Urdu alternative "qaumi ausat" (national average)
matched both rates.

Fixes: rate names must be written verbatim in English inside any answer that discusses a
price, when a cited source names them (critic rule, checked against exactly what the model
was shown); the eval's rate facts are English-only.

Two refusals: **n3** (2018 amendment, 1.5x sanctioned load) - the clause was never
retrieved, so refusing was the right behaviour for the sources given. **c5** (security
deposit) - clause 5.1.1 was retrieved and says the rates "are as per Annexure - IV", but
the annexure was not; the model had the pointer without the rates. Annexures and schedules
that a retrieved clause references are now added to the sources (at most 2), and the prompt
allows a partial answer instead of all-or-nothing NOT_FOUND.

### Two process findings from the third run

- **A correct draft was thrown away by the retry.** For the family's question the first
  draft was right - power purchase price until the agreement ends, energy purchase price for
  renewals, both names in English - and was rejected only for two untagged sentences. The
  retry prompt listed the problems but did not show the draft, so the model rewrote from
  scratch and said "energy" for both periods. The retry now receives its own previous draft
  and is told to fix only the listed problems.
- **That run tested stale code.** The files were copied to the outbox and written to the
  developer's machine in parallel; the write shipped the previous versions and reported
  success. Found by reading the machine's files back and diffing. Deliveries are now
  sequential and verified by read-back.

### Fourth run (verified code) - the family's question answered correctly

The family's question now gets: exports billed at the national average **power** purchase
price until the agreement ends, then the national average **energy** purchase price on
renewal - both names in English, citing Prosumer Regs 21(2). The first draft was already
right; the retry (which now sees its own draft) only merged two sentences so both carried a
tag. p4-ur: the rate-name rule rejected a draft without the English names; the retry added
them.

Still incomplete: the answer says the agreement "still runs under the repealed 2015 rules"
but not that 21(2) moves the **billing** to net billing (reg. 14 of 2026). The critic cannot
enforce completeness, so p4/p4-ur now carry a third fact (net billing / regulation 14) that
the eval measures.

c5 fell back although both drafts were good partial answers (Annexure IV's real rates, and
"the sources do not provide connection-charge amounts"). Three critic bugs: the sentence
splitter broke on "Rs." and "etc."; a sentence stating what the sources do NOT cover was
required to carry a tag; and a partial answer ending in "NOT_FOUND." was not cleaned. All
three fixed. Trade-off: a sentence phrased as an absence ("... not given ...") is exempt
from the tag rule - its numbers are still checked.

### Fifth run - full answer eval on verified code

| Split | n | answered | first draft | fallback | false refusal | cites gold | fact correct |
|---|---|---|---|---|---|---|---|
| held-out, English | 11 | 100% | 64% | 0% | 0% | 91% | 100% (n=3) |
| held-out, Urdu | 2 | 100% | 100% | 0% | 0% | 100% | 100% (n=2) |
| dev, English | 16 | 88% | 75% | 6% | 6% | 93% | 78% (n=9) |
| dev, Urdu | 6 | 67% | 67% | 33% | 0% | 100% | 100% (n=3) |
| out of scope | 6 | refused 6/6 | | | | | |

Reading the drafts behind the failures:

- **c5, c3-ur, p4-ur fell back with correct content.** Each was rejected for one sentence
  without its own tag, next to a tagged sentence in the same paragraph ("claim. claim
  [S5][S6]", or a one-line conclusion). The retry did not restructure, and the user got no
  answer. **Change:** a sentence is covered if it or an adjacent sentence in the same
  paragraph carries a tag. Replayed on every draft the old rule rejected for tags in this
  run, 7 of 8 now pass; the one still rejected (h9) opens with two untagged sentences in a
  row. Trade-off: one untagged sentence can ride on a neighbour's citation; a paragraph
  with no tag still fails and every number is still checked against the cited sources.
- **p4-ur's first draft was right** - it transliterated the rates as "power" / "energy"
  (paawar / enarji), keeping the distinction - and was rejected by the English-name rule as
  designed; the retry added the English names, then hit the tag rule above.
- **p4 (English) is correct but incomplete**: it gives both rates but not that billing moves
  to net billing (reg. 14). The completeness fact scores it "no", as intended.
- **p8, n3** are retrieval misses (the 1 MW definition; the 2018 amendment): p8 honestly
  says the sources give no number, n3 refuses. Both correct behaviour for the sources given.

Known critic limit (seen in a dry run): the number check asks whether a number appears
*anywhere* in the cited clause, not in the sentence it supports - an answer citing the wrong
sub-clause can pass the critic. The eval's "cites gold" column is what catches it.

### Sixth run - dev after the neighbour rule

Zero fallbacks (Urdu dev was 33% fallback the run before). Two questions (c3-ur, c5) hit
Groq's free-tier limit (HTTP 429) and are reported as **errors**, not scored as wrong.
p4/p4-ur still omit the switch to net billing (completeness fact "no") - a measured limit.

## Router - one assistant, three destinations

`rehnuma-ask` routes each question: **bill** (about the user's own bill -> the engine's
verified facts, numbers checked, template fallback), **policy** (rules -> cited clauses),
**both** (a rule applied to the user's bill -> two labelled sections), or **needs bill**
(asks for a photo instead of guessing). Rules, not an LLM: instant, free, works when Groq
is down. Ownership signals ("my bill", "this month", "did I use", Urdu agentive "my solar
DID send") vs rule signals ("allowed", "NEPRA", "can the DISCO", "is it right to apply").

| Router eval (`rehnuma-eval-route`, no API) | English | Urdu |
|---|---|---|
| dev (rules written from these) | 12/12 | 8/8 |
| held-out batch 1 (run once, before fixes) | 9/10 | 4/6 |
| held-out batch 2 (written before round-2 fixes) | 3/5 | 5/5 |

Batch-1 failures (Urdu agentive "my solar did send", "was I charged", "is it right to apply
average units") were fixed and moved to dev; batch 2 was written before re-running. Batch-2
misses are left unfixed so it stays a measurement: "legally" (only "legal" matches) and "did
I import". The costly direction is bill -> policy (the user gets the rule but not their own
numbers). Caveat: questions, labels and rules share an author; real user questions are the
real test.

## Reproduce

```powershell
uv run rehnuma-policy fetch
uv run rehnuma-policy ingest
uv run rehnuma-eval-policy                    # lexical
uv run rehnuma-eval-policy --rewrite all      # + Groq rewrite, English and Urdu
uv run rehnuma-eval-policy --rewrite all --replay reports/policy_eval/retrieval_rewrite-all/report.json
uv sync --extra dense
uv run rehnuma-eval-policy --dense            # + multilingual HF embeddings
```
Reports land in `reports/policy_eval/<setting>/report.md`.
