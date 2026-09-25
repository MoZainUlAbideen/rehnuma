"""The outlook in plain Urdu or English. Every number comes from the Outlook object."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from rehnuma.explain.render import month_name, n
from rehnuma.forecast.outlook import Outlook

TOP_CHANCES = 3


def rs(x: Decimal | int) -> int:
    """Estimates are rounded to Rs 10 - a forecast has no business showing single rupees."""
    return int((Decimal(x) / 10).quantize(Decimal(1), ROUND_HALF_UP) * 10)


def summarize_outlook(o: Outlook, lang: str = "ur") -> list[str]:
    ur = lang == "ur"
    first, last = o.months[0].month, o.months[-1].month
    lines = [
        f"اگلے 12 مہینے ({month_name(first, 'ur')} تا {month_name(last, 'ur')})" if ur
        else f"The next 12 months ({month_name(first, 'en')} to {month_name(last, 'en')})",
        f"آج کے ریٹ پر اندازاً کل بل: {n(rs(o.total))} روپے (فیول ایڈجسٹمنٹ کے بغیر)۔" if ur
        else f"Estimated total at today's rates: Rs {n(rs(o.total))} (before fuel adjustment).",
    ]
    if len(o.cross_months) == len(o.months):
        lines.append("پچھلے سال ہر مہینہ 200 یونٹ سے اوپر تھا، اس لیے پروٹیکٹڈ ریٹ اس استعمال پر "
                     "ممکن نہیں۔" if ur
                     else "Every month last year was above 200 units, so protected rates are "
                     "out of reach at this usage.")
    elif o.cross_months:
        names = "، ".join(month_name(m, lang) for m in o.cross_months) if ur \
            else ", ".join(month_name(m, lang) for m in o.cross_months)
        lines.append(f"پچھلے سال کے حساب سے ان مہینوں میں 200 یونٹ سے زیادہ ہو سکتے ہیں: {names}۔"
                     if ur else f"Based on last year, these months may go over 200 units: {names}.")
    else:
        lines.append("پچھلے سال کے حساب سے کسی مہینے میں 200 یونٹ سے زیادہ نہیں ہوں گے۔" if ur
                     else "Based on last year, no month should go over 200 units.")
    for c in o.chances[:TOP_CHANCES]:
        m = month_name(c.month, lang)
        if c.keeps_protection:
            lines.append(
                f"{m}: اندازاً {n(c.units)} یونٹ۔ اگر {n(c.edge)} یا کم رکھیں تو تقریباً "
                f"{n(rs(c.saving))} روپے بچیں گے - ہر نہ استعمال کیے گئے یونٹ پر تقریباً "
                f"{n(rs(c.per_unit))} روپے، کیونکہ مزید {n(c.protected_gained)} "
                f"{'مہینہ' if c.protected_gained == 1 else 'مہینے'} پروٹیکٹڈ ریٹ ملے گا۔" if ur
                else f"{m}: about {n(c.units)} units. Keeping it at {n(c.edge)} or below saves "
                f"about Rs {n(rs(c.saving))} - about Rs {n(rs(c.per_unit))} for every unit not "
                f"used, because it keeps protected rates for {n(c.protected_gained)} more "
                f"month{'s' if c.protected_gained > 1 else ''}.")
        else:
            lines.append(
                f"{m}: اندازاً {n(c.units)} یونٹ، سلیب کی حد {n(c.edge)} سے {n(c.over)} زیادہ۔ "
                f"{n(c.edge)} پر رکھیں تو تقریباً {n(rs(c.saving))} روپے بچیں گے۔" if ur
                else f"{m}: about {n(c.units)} units, {n(c.over)} over the {n(c.edge)}-unit slab "
                f"edge. Keeping it at {n(c.edge)} saves about Rs {n(rs(c.saving))} - the whole "
                f"month is priced at the higher slab's rate.")
    if len(o.chances) > 1:
        lines.append(f"یہ سب مہینے حد پر رکھیں تو کل بچت تقریباً {n(rs(o.saving_if_capped))} روپے۔"
                     if ur else f"All of these together: about Rs {n(rs(o.saving_if_capped))} "
                     f"saved over the year.")
    lines.append("شامل نہیں: فیول ایڈجسٹمنٹ (نیپرا ہر مہینے بعد میں طے کرتا ہے)، "
                 "سہ ماہی ایڈجسٹمنٹ، ٹی وی فیس۔ ریٹ ثانوی ذرائع سے ہیں۔" if ur
                 else "Not included: fuel adjustment (NEPRA sets it after each month), quarterly "
                 "adjustments, TV fee. Rates are from secondary sources.")
    return lines


def table(o: Outlook, lang: str = "en") -> str:
    ur = lang == "ur"
    head = ("| مہینہ | یونٹ (حد) | پروٹیکٹڈ | اندازاً بل |" if ur
            else "| Month | Units (range) | Protected | Estimated bill |")
    rows = [head, "|---|---|---|---|"]
    for u, m in zip(o.units, o.months, strict=True):
        prot = ("ہاں" if m.protected else "نہیں") if ur else ("yes" if m.protected else "no")
        rows.append(f"| {month_name(u.month, lang)} | {n(u.units)} ({n(u.low)}-{n(u.high)}) | "
                    f"{prot} | {'' if ur else 'Rs '}{n(rs(m.total))}{' روپے' if ur else ''} |")
    return "\n".join(rows)
