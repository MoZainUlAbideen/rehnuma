"use client";

import Image from "next/image";
import { Fragment, useCallback, useEffect, useRef, useState } from "react";

import {
  api,
  API_URL,
  ApiError,
  type AskReply,
  type BillView,
  type Citation,
  type Lang,
  type SampleCard,
} from "@/lib/api";

import { IconCheck, IconChat, IconExternal, IconSend, IconUpload, IconX } from "./icons";
import { OPEN_CHAT_EVENT, type OpenChatDetail } from "./OpenChat";
import { OutlookCard } from "./OutlookCard";
import { SolarCard } from "./SolarCard";

// ---------------------------------------------------------------- strings

const T = {
  ur: {
    title: "رہنما",
    subtitle: "بجلی کے بل کا مددگار",
    upload: "بل کی تصویر",
    change: "بل بدلیں",
    placeholder: "اپنا سوال لکھیں…",
    thinking: "سوچ رہا ہوں…",
    reading: "بل پڑھ رہا ہوں… (30 سے 60 سیکنڈ)",
    waking: "سرور جاگ رہا ہے — مفت سرور خالی وقت میں سو جاتا ہے، ایک منٹ تک لگ سکتا ہے۔",
    checks: (p: number, f: number) =>
      f ? `${p} حسابات درست، ${f} میں فرق` : `${p} حسابات چیک کیے، سب درست`,
    showChecks: "تمام جانچ دیکھیں",
    sources: "حوالے",
    old: "منسوخ شدہ",
    suggestions: "مثال کے سوال",
    noStore: "تصویر محفوظ نہیں کی گئی۔",
    disclaimer: "جوابات نیپرا کی دستاویزات سے جانچے جاتے ہیں۔ یہ قانونی مشورہ نہیں۔",
    solar: "سولر",
    plain: "عام",
    credit: "کریڈٹ",
    greeting:
      "السلام علیکم! میں آپ کا بل جانچ کر آسان اردو میں سمجھاتا ہوں، اور نیپرا کے قواعد حوالوں کے ساتھ بتاتا ہوں۔",
    uploadTitle: "اپنے بل کی تصویر اپ لوڈ کریں",
    uploadSub: "JPG، PNG یا WebP · تصویر محفوظ نہیں کی جاتی",
    orSample: "یا کوئی اصل نمونہ بل آزمائیں",
    attach: "بل کی تصویر اپ لوڈ کریں",
  },
  en: {
    title: "Rehnuma",
    subtitle: "Electricity bill copilot",
    upload: "Upload photo",
    change: "Change bill",
    placeholder: "Ask a question…",
    thinking: "Thinking…",
    reading: "Reading your bill… (30–60 s)",
    waking: "Waking the server up - the free server sleeps when idle, this can take a minute.",
    checks: (p: number, f: number) =>
      f ? `${p} checks passed, ${f} mismatch${f > 1 ? "es" : ""}` : `${p} checks passed, all correct`,
    showChecks: "See every check",
    sources: "Sources",
    old: "repealed",
    suggestions: "Try asking",
    noStore: "Your photo was not stored.",
    disclaimer: "Answers are checked against NEPRA documents. Not legal advice.",
    solar: "solar",
    plain: "regular",
    credit: "credit",
    greeting:
      "Hi! I check your electricity bill, explain it in plain words, and answer NEPRA rule questions with citations.",
    uploadTitle: "Upload a photo of your bill",
    uploadSub: "JPG, PNG or WebP · read in memory, never stored",
    orSample: "Or try a real sample bill",
    attach: "Upload a bill photo",
  },
} as const;

const SUGGEST: Record<Lang, { bill: string[]; rules: string[] }> = {
  ur: {
    bill: ["میرا بل منفی کیوں ہے؟", "مجھے کتنی رقم ادا کرنی ہے؟"],
    rules: [
      "میرا نیٹ میٹرنگ معاہدہ 2026 سے پہلے کا ہے، مجھے کس ریٹ پر پیسے ملیں گے؟",
      "ڈیٹیکشن بل کیا ہوتا ہے؟",
    ],
  },
  en: {
    bill: ["Why is my bill negative this month?", "How much do I have to pay?"],
    rules: [
      "Can my solar system be bigger than my sanctioned load?",
      "What is a detection bill and can I challenge it?",
    ],
  },
};

const MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTHS_UR = ["جنوری", "فروری", "مارچ", "اپریل", "مئی", "جون", "جولائی", "اگست", "ستمبر", "اکتوبر", "نومبر", "دسمبر"];

function monthLabel(ym: string, lang: Lang) {
  const [y, m] = ym.split("-").map(Number);
  return `${(lang === "ur" ? MONTHS_UR : MONTHS_EN)[m - 1]} ${y}`;
}

// ---------------------------------------------------------------- types

type Bill =
  | { kind: "sample"; id: string; card: SampleCard; view: BillView }
  | { kind: "upload"; token: string; view: BillView };

type Msg =
  | { id: number; role: "user"; text: string; lang: Lang }
  | { id: number; role: "bot"; lang: Lang; text?: string; reply?: AskReply; bill?: BillView; note?: string }
  | { id: number; role: "error"; text: string };

type DistOmit<T, K extends PropertyKey> = T extends unknown ? Omit<T, K> : never;
type NewMsg = DistOmit<Msg, "id">;

let nextId = 1;

// ---------------------------------------------------------------- answer rendering

function renderInline(text: string, cites: Map<string, Citation>) {
  // [S1] -> citation chip linking to the PDF page; **bold** -> <strong>
  const parts = text.split(/(\[S\d+\]|\*\*[^*]+\*\*)/g);
  return parts.map((p, i) => {
    const tag = p.match(/^\[(S\d+)\]$/)?.[1];
    if (tag) {
      const c = cites.get(tag);
      return c ? (
        <a key={i} className={`cite-chip${c.repealed ? " old" : ""}`} href={c.url} target="_blank" rel="noreferrer" title={c.label}>
          {tag}
        </a>
      ) : (
        <span key={i} className="cite-chip">
          {tag}
        </span>
      );
    }
    if (p.startsWith("**") && p.endsWith("**")) return <strong key={i}>{p.slice(2, -2)}</strong>;
    return <Fragment key={i}>{p}</Fragment>;
  });
}

function AnswerText({ text, cites }: { text: string; cites: Map<string, Citation> }) {
  const blocks: React.ReactNode[] = [];
  let list: string[] = [];
  const flush = () => {
    if (list.length) {
      blocks.push(
        <ul key={`l${blocks.length}`}>
          {list.map((li, i) => (
            <li key={i}>{renderInline(li, cites)}</li>
          ))}
        </ul>,
      );
      list = [];
    }
  };
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line) {
      flush();
      continue;
    }
    if (/^[-*•]\s+/.test(line)) {
      list.push(line.replace(/^[-*•]\s+/, ""));
      continue;
    }
    flush();
    if (line.startsWith("#")) {
      blocks.push(
        <h4 key={`h${blocks.length}`} className="chat-h">
          {line.replace(/^#+\s*/, "")}
        </h4>,
      );
    } else {
      blocks.push(<p key={`p${blocks.length}`}>{renderInline(line, cites)}</p>);
    }
  }
  flush();
  return <>{blocks}</>;
}

function Sources({ cites, lang }: { cites: Citation[]; lang: Lang }) {
  if (!cites.length) return null;
  return (
    <div className="chat-sources" dir="ltr">
      <div className="chat-sources-title">{T[lang].sources}</div>
      {cites.map((c) => (
        <a key={c.tag} href={c.url} target="_blank" rel="noreferrer" className="chat-source">
          <span className={`cite-chip${c.repealed ? " old" : ""}`}>{c.tag}</span>
          <span className="chat-source-label">
            {c.label}
            {c.repealed && <span className="badge badge-old">{T.en.old}</span>}
          </span>
          <IconExternal size={13} />
        </a>
      ))}
    </div>
  );
}

function BillCard({ view, lang, note }: { view: BillView; lang: Lang; note?: string }) {
  const [showAll, setShowAll] = useState(false);
  const t = T[lang];
  const [title, ...lines] = view.summary[lang];
  const { passed, failed } = view.audit;
  return (
    <div className="chat-bill">
      <div className={`chat-bill-title ${lang === "ur" ? "urdu" : ""}`}>{title}</div>
      <div className={lang === "ur" ? "urdu chat-bill-lines" : "chat-bill-lines"}>
        {lines.map((l, i) => (
          <p key={i}>{l}</p>
        ))}
      </div>
      <button className={`chat-audit ${failed ? "has-fail" : ""}`} onClick={() => setShowAll(!showAll)}>
        <IconCheck size={14} /> <span className={lang === "ur" ? "urdu-inline" : ""}>{t.checks(passed, failed)}</span>
        <span className="chat-audit-more">{showAll ? "−" : t.showChecks}</span>
      </button>
      {showAll && (
        <div className="chat-findings" dir="ltr">
          {view.audit.findings
            .filter((f) => f.status !== "SKIP")
            .map((f, i) => (
              <div key={i} className="check-row" title={f.message}>
                <span>{f.check}</span>
                <span className={f.status === "PASS" ? "tag-pass" : "tag-fail"}>{f.status}</span>
              </div>
            ))}
        </div>
      )}
      <OutlookCard outlook={view.outlook} lang={lang} />
      <SolarCard solar={view.solar} lang={lang} />
      {note && <div className="chat-note">{note}</div>}
    </div>
  );
}

// ---------------------------------------------------------------- widget

export function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [lang, setLang] = useState<Lang>("ur");
  const [samples, setSamples] = useState<SampleCard[] | null>(null);
  const [bill, setBill] = useState<Bill | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [busy, setBusy] = useState<null | "ask" | "read" | "load">(null);
  const [slow, setSlow] = useState(false);
  const [input, setInput] = useState("");
  const [dragging, setDragging] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const pending = useRef<OpenChatDetail | null>(null);
  const t = T[lang];

  // Wake the free Render server as soon as someone lands on the site.
  useEffect(() => {
    fetch(`${API_URL}/api/health`).catch(() => {});
  }, []);

  useEffect(() => {
    const box = scroller.current;
    if (!box) return;
    const last = box.querySelector<HTMLElement>(".chat-msg.latest");
    const top = last && !busy ? last.offsetTop - 12 : box.scrollHeight;
    box.scrollTo({ top, behavior: "smooth" });
  }, [msgs, busy]);

  // "Waking up" hint when a request takes long (cold start).
  useEffect(() => {
    if (!busy) return;
    const h = setTimeout(() => setSlow(true), 6000);
    return () => {
      clearTimeout(h);
      setSlow(false);
    };
  }, [busy]);

  const push = (m: NewMsg) => setMsgs((prev) => [...prev, { ...m, id: nextId++ } as Msg]);

  const fail = (e: unknown) => {
    const text = e instanceof ApiError ? e.message : "Something went wrong. Please try again.";
    if (e instanceof ApiError && e.status === 410) setBill(null);
    push({ role: "error", text });
  };

  const loadSamples = useCallback(async () => {
    if (samples) return samples;
    try {
      const s = (await api.samples()).sort(
        (a, b) =>
          Number(b.connection_type === "net_metering") - Number(a.connection_type === "net_metering") ||
          b.month.localeCompare(a.month),
      );
      setSamples(s);
      return s;
    } catch (e) {
      fail(e);
      return null;
    }
  }, [samples]); // eslint-disable-line react-hooks/exhaustive-deps

  const chooseSample = useCallback(
    async (id: string, list?: SampleCard[] | null) => {
      const card = (list ?? samples)?.find((s) => s.id === id);
      if (!card) return;
      setBusy("load");
      try {
        const view = await api.sample(id);
        setBill({ kind: "sample", id, card, view });
        push({ role: "bot", lang, bill: view });
      } catch (e) {
        fail(e);
      } finally {
        setBusy(null);
      }
    },
    [samples, lang], // eslint-disable-line react-hooks/exhaustive-deps
  );

  const ask = useCallback(
    async (question: string) => {
      const q = question.trim();
      if (!q || busy) return;
      setInput("");
      push({ role: "user", text: q, lang });
      setBusy("ask");
      try {
        const reply = await api.ask({
          question: q,
          lang,
          sample_id: bill?.kind === "sample" ? bill.id : undefined,
          bill_token: bill?.kind === "upload" ? bill.token : undefined,
        });
        push({ role: "bot", lang: reply.lang, reply });
      } catch (e) {
        fail(e);
      } finally {
        setBusy(null);
      }
    },
    [busy, lang, bill], // eslint-disable-line react-hooks/exhaustive-deps
  );

  // Open from anywhere on the site (hero buttons, nav), optionally with a sample preselected.
  useEffect(() => {
    const onOpen = (ev: Event) => {
      pending.current = (ev as CustomEvent<OpenChatDetail>).detail ?? {};
      setOpen(true);
    };
    window.addEventListener(OPEN_CHAT_EVENT, onOpen);
    return () => window.removeEventListener(OPEN_CHAT_EVENT, onOpen);
  }, []);

  useEffect(() => {
    if (!open) return;
    (async () => {
      const list = await loadSamples();
      const want = pending.current;
      pending.current = null;
      if (want?.sampleId && list && !(bill?.kind === "sample" && bill.id === want.sampleId)) {
        await chooseSample(want.sampleId, list);
      }
      if (want?.question) setInput(want.question);
    })();
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const onUpload = async (file: File | undefined) => {
    if (!file) return;
    if (fileRef.current) fileRef.current.value = "";
    setBusy("read");
    try {
      const up = await api.extract(file);
      setBill({ kind: "upload", token: up.bill_token, view: up });
      push({ role: "bot", lang, bill: up, note: t.noStore });
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  };

  const billLabel = (c: SampleCard) =>
    `${c.disco} · ${monthLabel(c.month, lang)} · ${c.connection_type === "net_metering" ? t.solar : t.plain}`;

  const suggestions = bill ? [...SUGGEST[lang].bill, SUGGEST[lang].rules[0]] : SUGGEST[lang].rules;

  return (
    <>
      <button
        className={`chat-launcher${open ? " is-open" : ""}`}
        aria-label={open ? "Close chat" : "Open Rehnuma chat"}
        onClick={() => setOpen(!open)}
      >
        {open ? <IconX size={24} /> : <IconChat size={26} />}
      </button>

      {open && (
        <section
          className={`chat-panel lang-${lang}`}
          dir={lang === "ur" ? "rtl" : "ltr"}
          aria-label="Rehnuma chat"
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            onUpload(e.dataTransfer.files?.[0]);
          }}
        >
          <header className="chat-head">
            <Image src="/logo-mark.png" alt="" width={46} height={24} />
            <div className="chat-head-text">
              <div className="chat-head-title">{t.title}</div>
              <div className="chat-head-sub">{t.subtitle}</div>
            </div>
            <div className="chat-lang" role="group" aria-label="Language">
              <button className={lang === "ur" ? "on" : ""} onClick={() => setLang("ur")}>
                اردو
              </button>
              <button className={lang === "en" ? "on" : ""} onClick={() => setLang("en")}>
                EN
              </button>
            </div>
            <button className="chat-close" aria-label="Close chat" onClick={() => setOpen(false)}>
              <IconX size={18} />
            </button>
          </header>

          <input
            ref={fileRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            hidden
            onChange={(e) => onUpload(e.target.files?.[0])}
          />
          {bill && (
            <div className="chat-billbar">
              <div className="chat-current">
                <span className="chat-current-dot" />
                <span>{bill.kind === "sample" ? billLabel(bill.card) : t.upload}</span>
                <button onClick={() => setBill(null)}>{t.change}</button>
              </div>
            </div>
          )}

          <div className="chat-body" ref={scroller}>
            <div className={`chat-msg bot ${lang === "ur" ? "urdu" : ""}`}>{t.greeting}</div>

            {!bill && (
              <div className="chat-start">
                <button
                  className={`chat-upload-card${dragging ? " dragging" : ""}`}
                  onClick={() => fileRef.current?.click()}
                  disabled={!!busy}
                >
                  <span className="chat-upload-icon">
                    <IconUpload size={20} />
                  </span>
                  <span className="chat-upload-text">
                    <span className={`chat-upload-title ${lang === "ur" ? "urdu-inline" : ""}`}>{t.uploadTitle}</span>
                    <span className={`chat-upload-sub ${lang === "ur" ? "urdu-inline" : ""}`}>{t.uploadSub}</span>
                  </span>
                </button>
                <div className={`chat-pick ${lang === "ur" ? "urdu-inline" : ""}`}>{t.orSample}</div>
                <div className="chat-chips">
                  {samples === null && <span className="chat-chip ghost">…</span>}
                  {samples?.map((s) => (
                    <button key={s.id} className="chat-chip" onClick={() => chooseSample(s.id)} disabled={!!busy}>
                      {billLabel(s)}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {msgs.map((m, idx) => {
              const latest = idx === msgs.length - 1 ? " latest" : "";
              if (m.role === "user")
                return (
                  <div key={m.id} className={`chat-msg user${latest} ${m.lang === "ur" ? "urdu" : ""}`} dir={m.lang === "ur" ? "rtl" : "ltr"}>
                    {m.text}
                  </div>
                );
              if (m.role === "error")
                return (
                  <div key={m.id} className={`chat-msg error${latest}`} dir="ltr">
                    {m.text}
                  </div>
                );
              if (m.bill)
                return (
                  <div key={m.id} className={`chat-msg bot wide${latest}`} dir={lang === "ur" ? "rtl" : "ltr"}>
                    <BillCard view={m.bill} lang={lang} note={m.note ? T[lang].noStore : undefined} />
                  </div>
                );
              const r = m.reply!;
              const cites = new Map((r.policy?.citations ?? []).map((c) => [c.tag, c]));
              return (
                <div key={m.id} className={`chat-msg bot wide${latest} ${r.lang === "ur" ? "urdu" : ""}`} dir={r.lang === "ur" ? "rtl" : "ltr"}>
                  <AnswerText text={r.text} cites={cites} />
                  <Sources cites={r.policy?.citations ?? []} lang={r.lang} />
                  {r.route === "needs_bill" && !bill && (
                    <button className="chat-chip upload inline" onClick={() => fileRef.current?.click()}>
                      <IconUpload size={14} /> {T[r.lang].upload}
                    </button>
                  )}
                  {r.cached && <div className="chat-meta" dir="ltr">cached answer</div>}
                </div>
              );
            })}

            {busy && busy !== "load" && (
              <div className="chat-msg bot typing">
                <span className="dots">
                  <i />
                  <i />
                  <i />
                </span>
                <span className={lang === "ur" ? "urdu-inline" : ""}>{busy === "read" ? t.reading : t.thinking}</span>
              </div>
            )}
            {busy && slow && <div className={`chat-msg notice ${lang === "ur" ? "urdu" : ""}`}>{t.waking}</div>}

            {!busy && !msgs.some((m) => m.role === "user") && (
              <div className="chat-suggest">
                <div className="chat-suggest-title">{t.suggestions}</div>
                {suggestions.map((s) => (
                  <button key={s} className={lang === "ur" ? "urdu" : ""} onClick={() => ask(s)}>
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>

          <form
            className="chat-input"
            onSubmit={(e) => {
              e.preventDefault();
              ask(input);
            }}
          >
            <button
              type="button"
              className="chat-attach"
              onClick={() => fileRef.current?.click()}
              disabled={!!busy}
              aria-label={t.attach}
              title={t.attach}
            >
              <IconUpload size={18} />
            </button>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  ask(input);
                }
              }}
              placeholder={t.placeholder}
              rows={1}
              maxLength={500}
              dir="auto"
              className={lang === "ur" ? "urdu" : ""}
            />
            <button type="submit" disabled={!input.trim() || !!busy} aria-label="Send">
              <IconSend size={18} />
            </button>
          </form>
          <div className={`chat-foot ${lang === "ur" ? "urdu" : ""}`}>{t.disclaimer}</div>
        </section>
      )}
    </>
  );
}
