import type { Metadata } from "next";

import { IconArrow, IconGithub } from "@/components/icons";
import { GITHUB_URL } from "@/lib/content";

export const metadata: Metadata = {
  title: "How accuracy was achieved",
  description:
    "Held-out evals, a deterministic critic, and every real bug found in NEPRA PDFs and real bills.",
};

const doc = (name: string) => `${GITHUB_URL}/blob/main/docs/${name}`;

const STATS = [
  {
    value: "100%",
    label: "held-out rule questions answered",
    note: "English and Urdu, 13 questions written before any tuning. 91–100% cite the right clause.",
  },
  {
    value: "91%",
    label: "right clause in the top 5",
    note: `Held-out English retrieval out of 566 clauses. Urdu (dev) reaches 83% after query rewriting.`,
  },
  {
    value: "6 / 6",
    label: "out-of-scope questions refused",
    note: "Questions the documents don't answer get \"not covered\", not a guess.",
  },
  {
    value: "0",
    label: "invented numbers reached a user",
    note: "Summary eval on 7 real bills × 2 languages. Any number the engine didn't produce is rejected.",
  },
  {
    value: "96.2%",
    label: "fields read correctly from photos",
    note: "Gemini on real bill photos, checked by the audit engine: 100% of key fields, 6 of 7 photos read.",
  },
  {
    value: "100%",
    label: "planted errors caught",
    note: "2,000 synthetic bills, 11 error types, 0% false alarms. Tests the wiring - not a real-world figure.",
  },
];

const LAYERS = [
  {
    kicker: "Layer 1",
    h: "A deterministic audit engine",
    items: [
      "Plain arithmetic with exact decimals - no LLM ever computes a bill.",
      "Units from meter readings, the net-metering bank, electricity duty, GST, fuel adjustment tax cascade, arrears vs history.",
      "Real bills must fail exactly their documented anomalies: PESCO's March 2026 bill really does print a Rs 2 inconsistency, and Rehnuma shows it.",
    ],
  },
  {
    kicker: "Layer 2",
    h: "Photo reading that checks itself",
    items: [
      "The vision model's reading is audited by the engine; failed checks trigger a re-read.",
      "The re-read names the failing fields only - never the expected value, so the model can't copy an answer.",
      "No field exists for names, addresses or reference numbers; the photo is never written to disk.",
    ],
  },
  {
    kicker: "Layer 3",
    h: "Retrieval that survives OCR and Urdu",
    items: [
      "BM25 plus character n-grams (robust to OCR typos like 'Meteiing'), fused by reciprocal rank.",
      "Urdu questions are rewritten into NEPRA's English wording and searched alongside the original.",
      "One hit per clause, ties broken deterministically - results don't depend on file order.",
    ],
  },
  {
    kicker: "Layer 4",
    h: "A critic on every answer",
    items: [
      "Every claim carries a source tag that must exist; every number must appear in the cited clause.",
      "Answer in the question's language; repealed documents flagged; the savings clause cited whenever one is used.",
      "One retry that fixes its own draft, then an honest fallback that lists the relevant clauses.",
    ],
  },
  {
    kicker: "Layer 5",
    h: "A router that keeps jobs separate",
    items: [
      "Bill questions → verified engine numbers. Rule questions → cited clauses. Both → two labelled sections.",
      "\"Why is my bill so high?\" with no bill asks for a photo instead of guessing.",
      "Rules, not an LLM: 100% on dev questions, with held-out misses reported as they are.",
    ],
  },
];

const RETRIEVAL: { setting: string; dev: string; held: string; ur: string; best?: boolean }[] = [
  { setting: "Lexical hybrid, no rewrite", dev: "88%", held: "91%", ur: "0%" },
  { setting: "+ rewrite Urdu questions", dev: "88%", held: "91%", ur: "67%" },
  { setting: "+ rewrite all, concatenated with the question", dev: "75%", held: "91%", ur: "67%" },
  { setting: "+ rewrite all, fused as a second query", dev: "81%", held: "91%", ur: "67%" },
  { setting: "+ document names stripped from rewrites", dev: "88%", held: "91%", ur: "67%" },
  { setting: "+ new rewrite prompt (production)", dev: "94%", held: "91%", ur: "83%", best: true },
];

const ANSWERS = [
  { split: "Held-out, English", n: 11, answered: "100%", gold: "91%", refusal: "0%" },
  { split: "Held-out, Urdu", n: 2, answered: "100%", gold: "100%", refusal: "0%" },
  { split: "Dev, English", n: 16, answered: "88%", gold: "93%", refusal: "6%" },
  { split: "Dev, Urdu", n: 6, answered: "67% → 100%*", gold: "100%", refusal: "0%" },
];

const BUGS = [
  {
    area: "Answers",
    h: "The family's own question got a cited - but wrong - answer",
    found:
      "Retrieval missed the savings clause, and the model repeated a paraphrase from our own document notes.",
    fix: "Notes no longer state rules. Whenever a repealed document is used, reg. 21(2) is added to the sources and must be cited.",
  },
  {
    area: "Urdu",
    h: "Urdu turned the 'power' price into the 'energy' price",
    found:
      "Both rates translate to the same Urdu phrase - and they are different rates. The eval's Urdu fact was loose enough to pass it.",
    fix: "A critic rule: rate names stay verbatim in English whenever a cited clause names them.",
  },
  {
    area: "PDF parsing",
    h: "Every schedule was glued onto one regulation",
    found:
      "Schedules were matched in upper case only, so Net Metering reg. 18 swallowed 16,000 characters of annexes.",
    fix: "Case-insensitive schedule headings with OCR numeral fixes (H → II, Ill → III).",
  },
  {
    area: "PDF parsing",
    h: "OCR read '1.' as 'I.' - five regulations vanished",
    found: "Regulations 1, 4, 6, 10 and 11 were missing from the index because of heading variants.",
    fix: "The parser now accepts 'I.', '.---', missing dashes and full stops, and '(I)' for (1).",
  },
  {
    area: "Evaluation",
    h: "Our hit@1 was partly luck",
    found: "4 of 27 questions tied at rank 1 and were broken by file order.",
    fix: "Deterministic tie-break, and the earlier hit@1 figures were corrected downward in the report.",
  },
  {
    area: "Photo reading",
    h: "Gemini copied one tax line into another",
    found: "It wrote GST on FPA (46) into the ED on FPA line (really 4) - and no check looked at that line, so the bill still passed as verified.",
    fix: "A new ed_on_fpa check. The next misread of that line triggers a re-read.",
  },
  {
    area: "Summaries",
    h: "'Credited Rs 872' - it actually added Rs 292",
    found: "The fuel adjustment is billed separately, so the electricity credit wasn't the month's outcome.",
    fix: "The summary now reports the month's net effect and explains the fuel adjustment's month.",
  },
  {
    area: "Critic",
    h: "A correct answer was rewritten into a wrong one",
    found: "The retry started from scratch after a tagging complaint and lost the right answer.",
    fix: "The retry now sees its own draft and fixes only the listed problems.",
  },
];

const LIMITS = [
  "The answer on grandfathered net metering gives both rates but often omits that billing moves to net billing (reg. 14). The eval measures this; the critic can't enforce completeness.",
  "The critic checks that a number appears in the cited clause, not in the exact sentence it supports. The eval's 'cites the right clause' column is what catches a wrong sub-clause.",
  "Meaning isn't machine-checked for summaries. Native Urdu readers (the bill owner and about five neighbours) are the safeguard today.",
  "Router misses on held-out phrasings like 'legally' and 'import' are left in the numbers, not patched to the test.",
  "Eval sets are small: 35 retrieval questions, 7 real bills. One question moves a percentage by several points.",
  "The legal basis for the fuel adjustment (NEPRA Act s. 31(7)) isn't indexed yet, so that question is answered 'not covered'.",
];

export default function Accuracy() {
  return (
    <>
      <section className="page-hero">
        <div className="wrap">
          <span className="eyebrow">Accuracy</span>
          <h1>How Rehnuma earns the right to answer</h1>
          <p>
            Every number on this page comes from an eval in the repository - including the ones that
            aren&apos;t flattering. Questions were split into a dev set for tuning and a held-out set
            written before any tuning and never tuned on.
          </p>
        </div>
      </section>

      <section className="section">
        <div className="wrap">
          <div className="stats">
            {STATS.map((s) => (
              <div key={s.label} className="stat">
                <div className="stat-value">{s.value}</div>
                <div className="stat-label">{s.label}</div>
                <div className="stat-note">{s.note}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section section-soft">
        <div className="wrap">
          <div className="section-head">
            <span className="eyebrow">Design</span>
            <h2>Five layers, each checking the one before</h2>
            <p>
              The LLM writes words. It never does arithmetic and never has the last word on a fact.
            </p>
          </div>
          <div className="layers">
            {LAYERS.map((l) => (
              <div key={l.h} className="layer">
                <div>
                  <div className="layer-kicker">{l.kicker}</div>
                  <h3>{l.h}</h3>
                </div>
                <ul>
                  {l.items.map((i) => (
                    <li key={i}>{i}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="wrap">
          <div className="section-head">
            <span className="eyebrow">Retrieval</span>
            <h2>What moved the numbers - and what didn&apos;t</h2>
            <p>
              Share of questions whose correct clause is in the top 5 of 566. Every row after the first
              replays the same cached rewrites, so rows differ only in retrieval.
            </p>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Setting</th>
                  <th>Dev · English</th>
                  <th>Held-out · English</th>
                  <th>Dev · Urdu</th>
                </tr>
              </thead>
              <tbody>
                {RETRIEVAL.map((r) => (
                  <tr key={r.setting} className={r.best ? "best" : undefined}>
                    <td>{r.setting}</td>
                    <td className="num">{r.dev}</td>
                    <td className="num">{r.held}</td>
                    <td className="num">{r.ur}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="table-note">
            Tried and rejected: multilingual embeddings (e5-small) - no gain in English, 17% on raw Urdu.
            Concatenating the rewrite with the question diluted the user&apos;s own words (88% → 75%).
          </p>

          <div className="section-head" style={{ marginTop: 64 }}>
            <span className="eyebrow">Answers</span>
            <h2>Answered, cited, and willing to refuse</h2>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Split</th>
                  <th>Questions</th>
                  <th>Answered</th>
                  <th>Cites the right clause</th>
                  <th>False refusals</th>
                </tr>
              </thead>
              <tbody>
                {ANSWERS.map((a) => (
                  <tr key={a.split}>
                    <td>{a.split}</td>
                    <td className="num">{a.n}</td>
                    <td className="num">{a.answered}</td>
                    <td className="num">{a.gold}</td>
                    <td className="num">{a.refusal}</td>
                  </tr>
                ))}
                <tr>
                  <td>Out of scope</td>
                  <td className="num">6</td>
                  <td className="num" colSpan={3}>
                    Refused 6 / 6
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="table-note">
            * Dev Urdu had 33% fallbacks from a too-strict tagging rule; after the neighbour-sentence fix
            the re-run had 0 fallbacks (two questions hit the free API rate limit and are reported as
            errors, not scored). Model: gpt-oss-120b on Groq.
          </p>
        </div>
      </section>

      <section className="section section-soft">
        <div className="wrap">
          <div className="section-head">
            <span className="eyebrow">Real bugs, diagnosed</span>
            <h2>What the real PDFs and real bills broke</h2>
            <p>
              Each one was found by reading the failing output, not by guessing from a score - and each
              fix has a test.
            </p>
          </div>
          <div className="bugs">
            {BUGS.map((b) => (
              <div key={b.h} className="bug">
                <div className="bug-area">{b.area}</div>
                <h3>{b.h}</h3>
                <p>
                  <b>Found:</b> {b.found}
                </p>
                <p>
                  <b>Fix:</b> {b.fix}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="wrap">
          <div className="section-head">
            <span className="eyebrow">Known limits</span>
            <h2>What Rehnuma doesn&apos;t do well yet</h2>
          </div>
          <ul className="limits">
            {LIMITS.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
          <div className="hero-cta" style={{ justifyContent: "flex-start", marginTop: 36 }}>
            <a className="btn btn-dark" href={GITHUB_URL} target="_blank" rel="noreferrer">
              <IconGithub size={16} /> Code and tests on GitHub
            </a>
            <a className="btn btn-light" href={doc("POLICY_EVAL.md")} target="_blank" rel="noreferrer">
              Full policy eval report <IconArrow size={16} />
            </a>
          </div>
        </div>
      </section>
    </>
  );
}
