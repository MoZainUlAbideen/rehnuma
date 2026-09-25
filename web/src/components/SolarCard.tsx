"use client";

import type { Lang, SolarView } from "@/lib/api";

const MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const nf = new Intl.NumberFormat("en-US");

const T = {
  ur: { title: "پچھلے 12 مہینے", net: "کل", credit: "کریڈٹ", charge: "بل",
        legend: "اوپر: بل · نیچے (سبز): کریڈٹ", renewal: "معاہدے کی تجدید پر", rs: "روپے" },
  en: { title: "Your last 12 months", net: "net", credit: "credit", charge: "charged",
        legend: "Up: charged · down (green): credited", renewal: "At renewal", rs: "Rs" },
};

const k = (v: number) => (Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(Math.abs(v) >= 10000 ? 0 : 1)}k` : `${v}`);

/** Each month's change in the account: charges above the line, credits below. Settlement
 *  months dominate, which is the point - that's where a solar household's money moves. */
function AmountsChart({ months }: { months: SolarView["months"] }) {
  const W = 340, H = 130, top = 12, bottom = 16, gap = 4;
  const max = Math.max(...months.map((m) => Math.abs(m.amount)), 1);
  const pos = Math.max(...months.map((m) => Math.max(m.amount, 0)), 0);
  const neg = Math.max(...months.map((m) => Math.max(-m.amount, 0)), 0);
  const span = H - top - bottom;
  const zero = top + span * (pos / ((pos + neg) || 1));
  const scale = span / ((pos + neg) || max);
  const bw = (W - gap * (months.length - 1)) / months.length;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="outlook-chart" role="img"
         aria-label="Change in the account each month: charges above the line, credits below">
      <line x1={0} x2={W} y1={zero} y2={zero} className="axis" />
      {months.map((m, i) => {
        const x = i * (bw + gap);
        const h = Math.max(Math.abs(m.amount) * scale, 1.5);
        const up = m.amount >= 0;
        const y = up ? zero - h : zero;
        const big = Math.abs(m.amount) > max * 0.25;
        const name = MONTHS_EN[Number(m.month.slice(5)) - 1];
        return (
          <g key={m.month}>
            <title>{`${name} ${m.month.slice(0, 4)}: ${up ? "charged" : "credited"} Rs ${nf.format(Math.abs(m.amount))}` +
              (m.net_units ? ` · ${Math.abs(m.net_units)} units ${m.net_units < 0 ? "settled" : "billed"}` : "")}</title>
            <rect x={x - gap / 2} y={0} width={bw + gap} height={H} fill="transparent" />
            <rect x={x} y={y} width={bw} height={h} rx={Math.min(3, bw / 2, h / 2)}
                  className={up ? "bar" : "bar credit"} />
            {big && (() => {
              const below = y + h + 9;
              const inside = !up && below > H - bottom;      // no room under a tall credit bar
              return (
                <text x={x + bw / 2} y={up ? y - 3 : inside ? y + h - 4 : below} textAnchor="middle"
                      className={inside ? "bar-label inside" : "bar-label"}>
                  {up ? k(m.amount) : `−${k(-m.amount)}`}
                </text>
              );
            })()}
            <text x={x + bw / 2} y={H - 3} textAnchor="middle" className="tick">{name[0]}</text>
          </g>
        );
      })}
    </svg>
  );
}

export function SolarCard({ solar, lang }: { solar?: SolarView | null; lang: Lang }) {
  if (!solar?.available) return null;
  const t = T[lang];
  const [, , ...rest] = solar.summary[lang];                // title + total shown above
  const renewalAt = rest.findIndex((l) => l.includes("21(2)"));
  const history = renewalAt >= 0 ? rest.slice(0, renewalAt) : rest;
  const renewal = renewalAt >= 0 ? rest.slice(renewalAt) : [];
  const credit = solar.total < 0;
  const amount = nf.format(Math.round(Math.abs(solar.total) / 10) * 10);   // same as the text
  return (
    <div className="outlook">
      <div className="outlook-head">
        <span className={lang === "ur" ? "urdu-inline" : ""}>{t.title}</span>
        <span className="outlook-total">
          <span className={lang === "ur" ? "urdu-inline" : ""}>{credit ? t.credit : t.charge}</span>{" "}
          <b dir="ltr">{lang === "ur" ? `${amount} ${t.rs}` : `${t.rs} ${amount}`}</b>
        </span>
      </div>
      <div dir="ltr">
        <AmountsChart months={solar.months} />
      </div>
      <div className={`outlook-legend ${lang === "ur" ? "urdu-inline" : ""}`}>{t.legend}</div>
      <div className={lang === "ur" ? "urdu outlook-lines" : "outlook-lines"}>
        {history.map((l) => (
          <p key={l}>{l}</p>
        ))}
      </div>
      {renewal.length > 0 && (
        <div className="renewal">
          <div className={`renewal-title ${lang === "ur" ? "urdu-inline" : ""}`}>{t.renewal}</div>
          <div className={lang === "ur" ? "urdu outlook-lines" : "outlook-lines"}>
            {renewal.map((l) => (
              <p key={l}>{l}</p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
