"""Template summary of a BillStory - Urdu by default, English on request.

This is the deterministic baseline: no LLM, works offline, and is 100% faithful to
the engine by construction. A later LLM summary will be measured against it.

Order follows what people told us they care about (docs/USER_RESEARCH.md):
what to pay -> solar sent/used OR units and tariff -> protected limit ->
where the money went -> did the check find anything.

Numbers use Western digits, as printed on the bills themselves.
"""

from __future__ import annotations

from datetime import date

from rehnuma.explain.story import BillStory, Slots

MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August",
             "September", "October", "November", "December"]
MONTHS_UR = ["جنوری", "فروری", "مارچ", "اپریل", "مئی", "جون", "جولائی", "اگست",
             "ستمبر", "اکتوبر", "نومبر", "دسمبر"]
LANGS = ("ur", "en")


def n(x: int) -> str:
    return f"{abs(x):,}"


def month_name(ym: str, lang: str) -> str:
    y, m = (int(p) for p in ym.split("-"))
    return f"{(MONTHS_UR if lang == 'ur' else MONTHS_EN)[m - 1]} {y}"


def day(d: date, lang: str) -> str:
    return f"{d.day} {(MONTHS_UR if lang == 'ur' else MONTHS_EN)[d.month - 1]} {d.year}"


# --- sections ------------------------------------------------------------------------
def _header(s: BillStory, lang: str) -> str:
    m = month_name(s.bill_month, lang)
    return f"{m} کا بل" if lang == "ur" else f"Your bill for {m}"


def _payable(s: BillStory, lang: str) -> list[str]:
    if s.is_credit:
        if lang == "ur":
            return [f"آپ کو کچھ ادا نہیں کرنا۔ آپ کے اکاؤنٹ میں {n(s.payable)} روپے کا کریڈٹ ہے "
                    "(یہ رقم آپ کے حق میں ہے)۔"]
        return [f"You have nothing to pay. Your account is Rs {n(s.payable)} in credit "
                "(this money is in your favour)."]
    due = f" {day(s.due_date, lang)}" if s.due_date else ""
    if lang == "ur":
        out = [f"ادا کرنے کی رقم: {n(s.payable)} روپے۔"]
        if due:
            out.append(f"آخری تاریخ:{due}۔ اس کے بعد رقم {n(s.payable_after_due)} روپے ہو جائے گی۔")
        return out
    out = [f"Amount to pay: Rs {n(s.payable)}."]
    if due:
        out.append(f"Last date:{due}. After that it becomes Rs {n(s.payable_after_due)}.")
    return out


def _net_line(slot_ur: str, slot_en: str, net: int, lang: str) -> str | None:
    if net == 0:
        return None
    if lang == "ur":
        if net < 0:
            return f"{slot_ur} میں آپ نے استعمال سے {n(net)} یونٹ زیادہ بھیجے۔"
        return f"{slot_ur} میں آپ نے بھیجے گئے یونٹس سے {n(net)} یونٹ زیادہ استعمال کیے۔"
    if net < 0:
        return f"In {slot_en} you sent {n(net)} more units than you used."
    return f"In {slot_en} you used {n(net)} more units than you sent."


def _bank_phrase(b: Slots, lang: str) -> str:
    parts = []
    for value, ur, en in ((b.offpeak, "آف پیک", "off-peak"), (b.peak, "پیک", "peak")):
        if value > 0:
            parts.append(f"{n(value)} اضافی {ur} یونٹ جمع ہیں" if lang == "ur"
                         else f"{n(value)} extra {en} units saved")
        elif value < 0:
            parts.append(f"{n(value)} {ur} یونٹ ابھی حساب میں آنے ہیں" if lang == "ur"
                         else f"{n(value)} {en} units still to be charged")
    if not parts:
        return "کوئی یونٹ جمع نہیں" if lang == "ur" else "nothing banked"
    return " اور ".join(parts) if lang == "ur" else " and ".join(parts)


def _solar(s: BillStory, lang: str) -> list[str]:
    sol = s.solar
    if lang == "ur":
        out = [f"سولر: اس مہینے آپ نے گرڈ سے {n(sol.imported.total)} یونٹ لیے اور "
               f"{n(sol.exported.total)} یونٹ واپس بھیجے۔",
               f"آف پیک: لیے {n(sol.imported.offpeak)}، بھیجے {n(sol.exported.offpeak)}۔ "
               f"پیک: لیے {n(sol.imported.peak)}، بھیجے {n(sol.exported.peak)}۔"]
    else:
        out = [f"Solar: this month you took {n(sol.imported.total)} units from the grid and "
               f"sent {n(sol.exported.total)} units back.",
               f"Off-peak: took {n(sol.imported.offpeak)}, sent {n(sol.exported.offpeak)}. "
               f"Peak: took {n(sol.imported.peak)}, sent {n(sol.exported.peak)}."]
    for line in (_net_line("آف پیک اوقات", "off-peak hours", sol.net.offpeak, lang),
                 _net_line("پیک اوقات", "peak hours", sol.net.peak, lang)):
        if line:
            out.append(line)
    if sol.settling:
        if lang == "ur":
            out.append(f"یہ {sol.cycle_length} مہینوں کے حساب کا آخری مہینہ ہے، اس لیے جمع شدہ "
                       "یونٹس کا حساب اس بل میں ہو گیا۔")
        else:
            out.append(f"This is the last month of the {sol.cycle_length}-month cycle, so your "
                       "banked units were settled on this bill.")
    else:
        bank = _bank_phrase(sol.banked, lang)
        if lang == "ur":
            out.append(f"یونٹس کا حساب ہر {sol.cycle_length} مہینے بعد ہوتا ہے۔ یہ مہینہ "
                       f"{sol.month_count} ہے؛ اب تک {bank}۔ ان کا حساب مہینہ "
                       f"{sol.cycle_length} کے بل میں ہوگا۔")
        else:
            out.append(f"Units are settled every {sol.cycle_length} months. This is month "
                       f"{sol.month_count}; so far: {bank}. They will be settled on the month "
                       f"{sol.cycle_length} bill.")
    out.append(_current_bill_line(s, lang))
    return out


def _amount(x: int, lang: str) -> str:
    """Signed money for the breakdown: negative amounts are credits."""
    if x < 0:
        return f"{n(x)} روپے کا کریڈٹ" if lang == "ur" else f"a credit of Rs {n(x)}"
    return f"{n(x)} روپے" if lang == "ur" else f"Rs {n(x)}"


def _current_bill_line(s: BillStory, lang: str) -> str:
    """Uses payable - arrears, NOT the 'current bill' line: on the legacy layout the FPA is
    billed separately, so PESCO Mar-26 shows current bill -872 while the bill actually ADDED
    Rs 292 (-872 + 1,164 FPA). Saying 'credited Rs 872' would have been wrong."""
    c = s.bill_effect
    if c < 0:
        return (f"اس بل سے آپ کو {n(c)} روپے کا کریڈٹ ملا۔" if lang == "ur"
                else f"This bill credited you Rs {n(c)}.")
    return (f"اس مہینے کے {n(c)} روپے کے چارجز آپ کے بیلنس میں شامل ہوئے۔" if lang == "ur"
            else f"This month's charges of Rs {n(c)} were added to your balance.")


def _units_and_tariff(s: BillStory, lang: str) -> list[str]:
    out = []
    if lang == "ur":
        out.append(f"اس مہینے استعمال شدہ یونٹ: {n(s.units)}۔")
        if s.last_year_units is not None:
            out.append(f"پچھلے سال اسی مہینے: {n(s.last_year_units)} یونٹ۔")
    else:
        out.append(f"Units used this month: {n(s.units)}.")
        if s.last_year_units is not None:
            out.append(f"Same month last year: {n(s.last_year_units)} units.")

    if s.tariff_kind == "flat":
        out.append("آپ کا میٹر عام ٹیرف (A-1a) پر ہے: دن کے کسی بھی وقت "
                   "ہر یونٹ کا ریٹ ایک جیسا ہے، "
                   "اس لیے پیک آورز سے آپ کا ریٹ نہیں بدلتا۔" if lang == "ur" else
                   "Your meter is on a flat tariff (A-1a): every unit costs the same at any time "
                   "of day, so peak hours do not change your rate.")
    else:
        line = ("آپ کا میٹر ٹائم آف یوز (A-1b) ہے: پیک آورز کے یونٹ آف پیک سے مہنگے ہوتے ہیں۔"
                if lang == "ur" else
                "Your meter is time-of-use (A-1b): units in peak hours cost more than off-peak.")
        if s.tou_units:
            line += (f" پیک یونٹ: {n(s.tou_units.peak)}، آف پیک یونٹ: {n(s.tou_units.offpeak)}۔"
                     if lang == "ur" else
                     f" Peak units: {n(s.tou_units.peak)}, off-peak units: "
                     f"{n(s.tou_units.offpeak)}.")
        out.append(line)
    return out


def _protected(s: BillStory, lang: str) -> list[str]:
    p = s.protected
    if p is None:
        return []
    if p.is_protected:
        out = ["آپ پروٹیکٹڈ صارف ہیں (پچھلے 6 مہینوں میں ہر مہینے 200 یونٹ یا کم)، اس لیے آپ کو سب "
               "سے کم ریٹ ملتا ہے۔" if lang == "ur" else
               "You are a protected consumer (200 units or less in each of the last 6 months), "
               "so you get the lowest rates."]
        if p.near_limit:
            out.append(f"احتیاط: اس مہینے {n(s.units)} یونٹ استعمال ہوئے۔ "
                       "اگر کسی مہینے 200 سے زیادہ "
                       "یونٹ ہوئے تو اگلے 6 مہینے پروٹیکٹڈ ریٹ نہیں ملے گا۔" if lang == "ur" else
                       f"Careful: you used {n(s.units)} units this month. If any month goes above "
                       "200 units, you lose protected rates for the next 6 months.")
        return out
    months = p.months_over_limit
    if lang == "ur":
        which = "تمام 6 مہینے" if months == 6 else f"{months} مہینے"
        return [f"آپ پروٹیکٹڈ صارف نہیں ہیں: پچھلے 6 مہینوں میں سے {which} 200 یونٹ سے زیادہ "
                "تھے۔ اگر آپ لگاتار 6 مہینے 200 یا کم یونٹ استعمال کریں "
                "تو پروٹیکٹڈ ریٹ مل سکتا ہے، "
                "جو کافی سستا ہے۔"]
    which = "all 6" if months == 6 else f"{months} of the last 6"
    return [f"You are not a protected consumer: {which} months were above 200 "
            "units. Staying at 200 units or less for 6 months in a row can get you protected "
            "rates, which are much cheaper."]


def _money(s: BillStory, lang: str) -> list[str]:
    if lang == "ur":
        line = (f"رقم کی تفصیل — بجلی: {_amount(s.energy_rs, lang)}؛ "
                f"ٹیکس: {_amount(s.taxes_rs, lang)}")
        line += (f"؛ فیول ایڈجسٹمنٹ (FPA): {_amount(s.fpa_rs, lang)}۔"
                 if s.fpa_rs is not None else "۔")
    else:
        line = (f"Where the money goes - electricity: {_amount(s.energy_rs, lang)}; "
                f"taxes: {_amount(s.taxes_rs, lang)}")
        line += (f"; fuel adjustment (FPA): {_amount(s.fpa_rs, lang)}."
                 if s.fpa_rs is not None else ".")
    out = [line]
    if s.energy_rs < 0:
        out.append("بجلی کی رقم کریڈٹ ہے کیونکہ آپ نے استعمال سے زیادہ یونٹ بھیجے۔" if lang == "ur"
                   else "Electricity is a credit because you sent back more units than you used.")
    if s.fpa_months and s.fpa_rs:
        which = " اور ".join(f"{month_name(f.ref_month, lang)} کے {n(f.units)} یونٹ"
                             for f in s.fpa_months) if lang == "ur" else " and ".join(
                             f"{n(f.units)} units of {month_name(f.ref_month, lang)}"
                             for f in s.fpa_months)
        if lang == "ur":
            out.append(f"فیول ایڈجسٹمنٹ پرانے مہینے کے یونٹس پر لگتی ہے: {which}۔ "
                       "نیپرا مہینہ ختم ہونے کے "
                       "بعد فیول کی اصل لاگت طے کرتا ہے، اس لیے یہ بعد میں آتی ہے۔")
            if s.fpa_rs < 0:
                out.append("اس بار فیول ایڈجسٹمنٹ سے آپ کا بل کم ہوا۔")
        else:
            out.append(f"The fuel adjustment is charged on an earlier month: {which}. NEPRA sets "
                       "the actual fuel cost after the month ends, so it arrives later.")
            if s.fpa_rs < 0:
                out.append("This time the fuel adjustment reduced your bill.")
    return out


def _audit(s: BillStory, lang: str) -> list[str]:
    a = s.audit
    if a is None:
        return []
    if a.problems == 0:
        return [f"جانچ: رہنما نے اس بل کے {n(a.checks_passed)} حسابات چیک کیے، سب درست ہیں۔"
                if lang == "ur" else
                f"Check: Rehnuma verified {n(a.checks_passed)} calculations on this bill; "
                "all are correct."]
    if lang == "ur":
        return [f"جانچ: رہنما کو اس بل میں {n(a.problems)} فرق ملا (زیادہ سے زیادہ "
                f"{n(a.largest_gap_rs)} روپے)۔ تفصیل کے لیے مکمل جانچ دیکھیں۔"]
    word = "mismatch" if a.problems == 1 else "mismatches"
    return [f"Check: Rehnuma found {n(a.problems)} {word} on this bill (up to "
            f"Rs {n(a.largest_gap_rs)}). See the detailed check for more."]


def summarize(story: BillStory, lang: str = "ur") -> list[str]:
    """Lines of the summary, most important first."""
    if lang not in LANGS:
        raise ValueError(f"lang must be one of {LANGS}")
    lines = [_header(story, lang), *_payable(story, lang)]
    if story.solar:
        lines += _solar(story, lang)
    else:
        lines += _units_and_tariff(story, lang)
        lines += _protected(story, lang)
    lines += _money(story, lang)
    lines += _audit(story, lang)
    return lines
