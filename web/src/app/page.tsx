import Link from "next/link";

import { IconArrow, IconBolt, IconBook, IconCheck, IconExternal, IconShield, IconSun } from "@/components/icons";
import { OpenChatButton } from "@/components/OpenChat";
import { DOCUMENTS, TOTAL_CLAUSES } from "@/lib/content";

// Real output for the PESCO Sep-2026 sample bill (rehnuma-summary, template, verified by the engine).
const SEP_SUMMARY_UR = [
  "آپ کو کچھ ادا نہیں کرنا۔ آپ کے اکاؤنٹ میں 134,041 روپے کا کریڈٹ ہے (یہ رقم آپ کے حق میں ہے)۔",
  "سولر: اس مہینے آپ نے گرڈ سے 629 یونٹ لیے اور 942 یونٹ واپس بھیجے۔",
  "یہ 3 مہینوں کے حساب کا آخری مہینہ ہے، اس لیے جمع شدہ یونٹس کا حساب اس بل میں ہو گیا۔",
  "اس بل سے آپ کو 19,285 روپے کا کریڈٹ ملا۔",
  "جانچ: رہنما نے اس بل کے 17 حسابات چیک کیے، سب درست ہیں۔",
];

// Real audit rows from the PESCO Mar-2026 bill - including the Rs 2 inconsistency printed on it.
const CHECKS: [string, "PASS" | "FAIL"][] = [
  ["units from meter: 195", "PASS"],
  ["net off-peak: −304", "PASS"],
  ["FPA + taxes: 1,164", "PASS"],
  ["arrears vs history", "PASS"],
  ["FPA total: 1,166 ≠ 1,164", "FAIL"],
];

function Hero() {
  return (
    <section className="hero">
      <div className="wrap">
        <div className="hero-copy">
          <span className="eyebrow">Bill checks · Plain Urdu · NEPRA rules, cited · Solar &amp; 12-month outlook</span>
          <h1>
            Understand your electricity bill.
            <br />
            Plan what comes next.
          </h1>
          <p className="hero-urdu urdu" dir="rtl">
            بجلی کے بل سے سولر تک — نیپرا کے قواعد کے مطابق، آسان اردو میں
          </p>
          <p className="hero-sub">
            Rehnuma checks every calculation on your bill and explains it in plain Urdu or English,
            answers NEPRA rule questions with the clause and page they come from, and looks ahead:
            your next 12 months and, for solar homes, what the 2026 rules mean for you.
          </p>
          <div className="hero-cta">
            <OpenChatButton className="btn btn-dark" sampleId="pesco-2026-09">
              Try a real sample bill <IconArrow size={16} />
            </OpenChatButton>
            <Link href="/accuracy" className="btn btn-light">
              How we measure accuracy
            </Link>
          </div>
        </div>

        <div className="cards">
          <div className="card card-blue">
            <h3>
              <IconBook size={18} /> Explains in Urdu
            </h3>
            <p>A plain-language summary of what you owe, what solar earned, and why.</p>
            <div className="mini urdu" dir="rtl">
              {SEP_SUMMARY_UR.slice(0, 2).map((l) => (
                <div key={l}>{l}</div>
              ))}
            </div>
          </div>

          <div className="card card-white">
            <h3>
              <IconCheck size={18} /> Checks every number
            </h3>
            <p>Meter readings, units, taxes, fuel adjustment and arrears, recomputed.</p>
            <div className="mini">
              {CHECKS.map(([c, s]) => (
                <div key={c} className="check-row">
                  <span>{c}</span>
                  <span className={s === "PASS" ? "tag-pass" : "tag-fail"}>{s}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="card card-amber">
            <h3>
              <IconSun size={18} /> Solar and net metering
            </h3>
            <p>Units taken vs sent back, the 3-month bank, and what you were credited.</p>
            <div className="mini">
              <div style={{ display: "flex", justifyContent: "space-between", fontWeight: 600 }}>
                <span>Took 629</span>
                <span style={{ color: "#b86e00" }}>Sent 942</span>
              </div>
              <div className="flow-bar">
                <span style={{ width: "40%", background: "var(--brand)" }} />
                <span style={{ width: "60%", background: "var(--amber)" }} />
              </div>
              <div style={{ color: "var(--muted)" }}>PESCO · Sep 2026 · settlement month</div>
              <div style={{ fontFamily: "var(--font-serif)", fontSize: 26, fontWeight: 600, color: "var(--navy)", marginTop: 6 }}>
                Rs 19,285 credit
              </div>
            </div>
          </div>

          <div className="card card-sky">
            <h3>
              <IconShield size={18} /> Rules, with sources
            </h3>
            <p>Answers only from NEPRA text, and says so when the documents don&apos;t cover it.</p>
            <div className="mini">
              <div style={{ fontWeight: 600, color: "var(--navy)", marginBottom: 4 }}>
                My net-metering agreement is from before 2026. What rate do I get?
              </div>
              <div>
                You are billed at the national average power purchase price until your agreement
                expires, and the energy purchase price on renewal <span className="cite-chip">S1</span>
              </div>
              <div style={{ marginTop: 6 }}>
                <span className="cite-chip">Prosumer Regs 2026 · reg. 21(2) · p. 7</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function HowItWorks() {
  const steps = [
    {
      h: "Pick a bill or upload a photo",
      p: "Start with one of seven real (anonymised) PESCO and IESCO bills, or photograph your own. The photo is read in memory and never stored.",
    },
    {
      h: "Rehnuma audits it",
      p: "A deterministic engine, not an LLM, re-does the arithmetic: units from meter readings, net-metering bank, taxes, fuel adjustment and arrears.",
    },
    {
      h: "Ask anything, in Urdu or English",
      p: "Bill questions are answered from verified numbers only. Rule questions are answered from NEPRA clauses, each claim tagged with its source.",
    },
  ];
  return (
    <section className="section">
      <div className="wrap">
        <div className="section-head">
          <span className="eyebrow">What it does</span>
          <h2>Three steps from a confusing bill to a clear answer</h2>
          <p>
            Most households in Pakistan can&apos;t tell if their bill is right, and solar households
            face rules that changed in 2026. Rehnuma is built for both.
          </p>
        </div>
        <div className="steps">
          {steps.map((s, i) => (
            <div key={s.h} className="step">
              <div className="step-num">{i + 1}</div>
              <h3>{s.h}</h3>
              <p>{s.p}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Example() {
  return (
    <section className="section section-soft">
      <div className="wrap split">
        <div>
          <span className="eyebrow">A real bill</span>
          <h2 style={{ fontSize: "clamp(30px,4vw,42px)" }}>
            A solar family&apos;s September bill, in their own language
          </h2>
          <p style={{ marginTop: 14, color: "var(--muted)", fontSize: 17 }}>
            The bill that started the project: a PESCO net-metering household with a credit that
            nobody at home could explain. This is Rehnuma&apos;s summary, word for word.
          </p>
          <ul className="ticks">
            <li>
              <IconCheck size={18} />
              <span>
                <b>Every number comes from the engine.</b> A faithfulness check rejects any summary
                with a number the audit did not produce.
              </span>
            </li>
            <li>
              <IconCheck size={18} />
              <span>
                <b>Reviewed by native Urdu readers</b> - the bill owner and about five neighbours.
              </span>
            </li>
            <li>
              <IconCheck size={18} />
              <span>
                <b>Works without an LLM.</b> If the model is down, a template summary with the same
                verified facts takes over.
              </span>
            </li>
          </ul>
          <div style={{ marginTop: 26 }}>
            <OpenChatButton className="btn btn-primary" sampleId="pesco-2026-09">
              Open this bill in the chat <IconArrow size={16} />
            </OpenChatButton>
          </div>
        </div>
        <div className="bill-demo">
          <div className="bill-demo-head">
            <span>PESCO · September 2026 · net metering</span>
            <span className="badge badge-live">17 checks passed</span>
          </div>
          <div className="bill-demo-body urdu" dir="rtl">
            <div style={{ fontSize: 20 }}>ستمبر 2026 کا بل</div>
            {SEP_SUMMARY_UR.map((l) => (
              <p key={l}>{l}</p>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function Sources() {
  return (
    <section className="section" id="sources">
      <div className="wrap">
        <div className="section-head">
          <span className="eyebrow">Grounded in the source</span>
          <h2>Built on the actual NEPRA documents, clause by clause</h2>
          <p>
            Rehnuma reads the official PDFs from nepra.org.pk, splits them into {TOTAL_CLAUSES}{" "}
            clauses (regulations, definitions, schedules and annexures), and every answer links to the
            exact clause and page. A fingerprint of each PDF flags the day NEPRA changes one.
          </p>
        </div>
        <div className="docs-grid">
          {DOCUMENTS.map((d) => (
            <a key={d.short} className="doc" href={d.url} target="_blank" rel="noreferrer">
              <div className="doc-top">
                <h3>{d.short}</h3>
                <span className={`badge ${d.status === "in_force" ? "badge-live" : "badge-old"}`}>
                  {d.status === "in_force" ? "In force" : "Repealed · savings clause"}
                </span>
              </div>
              <p>{d.what}</p>
              <div className="doc-meta">
                <span>
                  {d.clauses} {d.clauses === 1 ? "clause" : "clauses"} indexed
                </span>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                  Official PDF <IconExternal size={12} />
                </span>
              </div>
            </a>
          ))}
          <div className="doc" style={{ background: "var(--bg-soft)" }}>
            <div className="doc-top">
              <h3>Why repealed rules are still here</h3>
            </div>
            <p>
              The 2026 Prosumer Regulations replaced net metering, but reg. 21(2) keeps existing
              agreements on their old terms until they expire. So whenever an answer uses a repealed
              document, Rehnuma adds 21(2) to the sources and must cite it - otherwise the answer is
              rejected.
            </p>
          </div>
        </div>
        <div className="callout">
          <b>Honest about gaps.</b> Asked &quot;is the fuel adjustment on my bill legal?&quot;, Rehnuma
          answers that these documents don&apos;t cover it (the legal basis is in the NEPRA Act, which
          isn&apos;t indexed yet) instead of guessing.
        </div>
      </div>
    </section>
  );
}

function Closing() {
  return (
    <section className="section section-soft">
      <div className="wrap" style={{ textAlign: "center" }}>
        <div className="section-head center">
          <span className="eyebrow">
            <IconBolt size={14} style={{ verticalAlign: -2 }} /> Measured, not claimed
          </span>
          <h2>See how accuracy was achieved</h2>
          <p>
            Held-out questions written before tuning, a critic that rejects unsupported numbers, and
            every bug we found in real bills and real PDFs.
          </p>
        </div>
        <div className="hero-cta" style={{ marginTop: 0 }}>
          <Link href="/accuracy" className="btn btn-primary">
            Read the accuracy report <IconArrow size={16} />
          </Link>
          <OpenChatButton className="btn btn-light">Ask a question</OpenChatButton>
        </div>
      </div>
    </section>
  );
}

export default function Home() {
  return (
    <>
      <div className="announce">
        <div className="wrap">
          <span>Urdu first · every rule cited to its NEPRA clause · photos never stored</span>
          <OpenChatButton className="pill" sampleId="pesco-2026-09">
            Try a sample bill
          </OpenChatButton>
        </div>
      </div>
      <Hero />
      <HowItWorks />
      <Example />
      <Sources />
      <Closing />
    </>
  );
}
