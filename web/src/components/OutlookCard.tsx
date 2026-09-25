"use client";

import type { Lang, Outlook, OutlookMonth } from "@/lib/api";

const LIMIT = 200;
const MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const nf = new Intl.NumberFormat("en-US");

const T = {
  ur: { title: "اگلے 12 مہینے", total: "اندازاً کل", legend: "نارنجی: 200 یونٹ سے زیادہ", rs: "روپے" },
  en: { title: "Next 12 months", total: "estimated total", legend: "Amber: over 200 units", rs: "Rs" },
};

/** Units per month; months over the 200-unit protected limit in amber with their value.
 *  One series, so no legend box - the note under the chart names the one colour rule. */
function UnitsChart({ months }: { months: OutlookMonth[] }) {
  const W = 340, H = 120, top = 16, bottom = 18, gap = 4;
  const max = Math.max(LIMIT * 1.15, ...months.map((m) => m.units));
  const y = (v: number) => top + (H - top - bottom) * (1 - v / max);
  const bw = (W - gap * (months.length - 1)) / months.length;
  const barPath = (x: number, v: number) => {
    const y0 = H - bottom, y1 = Math.min(y(v), y0 - 1), r = Math.min(4, bw / 2, y0 - y1);
    return `M${x},${y0}V${y1 + r}Q${x},${y1} ${x + r},${y1}H${x + bw - r}Q${x + bw},${y1} ${x + bw},${y1 + r}V${y0}Z`;
  };
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="outlook-chart" role="img"
         aria-label="Forecast units per month for the next 12 months">
      <line x1={0} x2={W} y1={H - bottom} y2={H - bottom} className="axis" />
      <line x1={0} x2={W} y1={y(LIMIT)} y2={y(LIMIT)} className="limit" />
      <text x={W} y={y(LIMIT) - 3} textAnchor="end" className="limit-label">200</text>
      {months.map((m, i) => {
        const x = i * (bw + gap);
        const over = m.units > LIMIT;
        const label = `${MONTHS_EN[Number(m.month.slice(5)) - 1]} ${m.month.slice(0, 4)}: ${m.units} units ` +
          `(range ${m.low}-${m.high}) · ${m.protected ? "protected" : "not protected"} · ≈ Rs ${nf.format(m.bill)}`;
        return (
          <g key={m.month}>
            <title>{label}</title>
            <rect x={x - gap / 2} y={0} width={bw + gap} height={H} fill="transparent" />
            <path d={barPath(x, m.units)} className={over ? "bar over" : "bar"} />
            {over && (
              <text x={x + bw / 2} y={y(m.units) - 3} textAnchor="middle" className="bar-label">
                {m.units}
              </text>
            )}
            <text x={x + bw / 2} y={H - 5} textAnchor="middle" className="tick">
              {MONTHS_EN[Number(m.month.slice(5)) - 1][0]}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function OutlookCard({ outlook, lang }: { outlook?: Outlook; lang: Lang }) {
  if (!outlook?.available) return null;
  const t = T[lang];
  const lines = outlook.summary[lang].slice(2);   // title and total are shown above the chart
  return (
    <div className="outlook">
      <div className="outlook-head">
        <span className={lang === "ur" ? "urdu-inline" : ""}>{t.title}</span>
        <span className="outlook-total">
          <span className={lang === "ur" ? "urdu-inline" : ""}>{t.total}</span>{" "}
          <b dir="ltr">{lang === "ur" ? `${nf.format(outlook.total)} ${t.rs}` : `${t.rs} ${nf.format(outlook.total)}`}</b>
        </span>
      </div>
      <div dir="ltr">
        <UnitsChart months={outlook.months} />
      </div>
      <div className={`outlook-legend ${lang === "ur" ? "urdu-inline" : ""}`}>{t.legend}</div>
      <div className={lang === "ur" ? "urdu outlook-lines" : "outlook-lines"}>
        {lines.map((l) => (
          <p key={l}>{l}</p>
        ))}
      </div>
    </div>
  );
}
