"""The solar outlook in plain Urdu or English. Every number comes from SolarOutlook."""

from __future__ import annotations

from rehnuma.explain.render import month_name, n
from rehnuma.forecast.render import rs
from rehnuma.forecast.solar import SolarOutlook


def _mn(m: str, lang: str) -> str:
    return month_name(m, lang)


def summarize_solar(o: SolarOutlook, lang: str = "ur") -> list[str]:
    ur = lang == "ur"
    last = o.last_12
    first_m, last_m = last[0].month, last[-1].month
    total = o.last_12_total
    lines = [
        f"پچھلے {n(len(last))} مہینے ({_mn(first_m, 'ur')} تا {_mn(last_m, 'ur')})" if ur
        else f"Your last {n(len(last))} months ({_mn(first_m, 'en')} to {_mn(last_m, 'en')})",
    ]
    if total < 0:
        lines.append(f"مجموعی طور پر آپ کو {n(rs(-total))} روپے کا کریڈٹ ملا۔" if ur
                     else f"Overall you were credited Rs {n(rs(-total))}.")
    else:
        lines.append(f"مجموعی طور پر {n(rs(total))} روپے کا بل بنا۔" if ur
                     else f"Overall you were charged Rs {n(rs(total))}.")
    for s in [s for s in o.settlements if s.month >= first_m]:
        units = -s.net_units
        if s.amount < 0:
            lines.append(f"{_mn(s.month, lang)}: {n(units)} یونٹ کا حساب، "
                         f"{n(rs(-s.amount))} روپے کا کریڈٹ۔"
                         if ur else f"{_mn(s.month, lang)}: {n(units)} banked units settled, "
                         f"Rs {n(rs(-s.amount))} credited.")
        else:
            lines.append(f"{_mn(s.month, lang)}: {n(units)} یونٹ کا حساب، لیکن فیول "
                         f"ایڈجسٹمنٹ کی وجہ سے {n(rs(s.amount))} روپے کا بل۔" if ur
                         else f"{_mn(s.month, lang)}: {n(units)} banked units settled, but "
                         f"the fuel adjustment made it a Rs {n(rs(s.amount))} charge.")
    if o.import_months:
        names = ("، " if ur else ", ").join(_mn(a.month, lang) for a in o.import_months)
        cost = sum(a.amount for a in o.import_months)
        units = sum(a.net_units for a in o.import_months)
        lines.append(f"{names}: استعمال بھیجے گئے یونٹس سے زیادہ تھا، {n(units)} یونٹ کا بل "
                     f"{n(rs(cost))} روپے۔" if ur
                     else f"{names}: you used more than you sent back and were billed for "
                     f"{n(units)} units, Rs {n(rs(cost))}.")
    early, late = o.in_cycle_level(False), o.in_cycle_level(True)
    if early and late and early[0] != late[0] and abs(late[1] - early[1]) > 0.25 * abs(early[1]):
        lines.append(
            f"جن مہینوں میں حساب نہیں ہوتا، ان کا بل {_mn(early[0][0], 'ur')} میں تقریباً "
            f"{n(rs(early[1]))} روپے تھا اور اب ({_mn(late[0][-1], 'ur')}) تقریباً "
            f"{n(rs(late[1]))} روپے ہے۔" if ur
            else f"Months with no settlement cost about Rs {n(rs(early[1]))} in "
            f"{_mn(early[0][0], 'en')} and about Rs {n(rs(late[1]))} now "
            f"({_mn(late[0][-1], 'en')}).")
    r = o.renewal
    if r is not None:
        u = r.usage
        imp = u.import_offpeak + u.import_peak
        lo, hi = r.renewal_total("high"), r.renewal_total("low")    # high EPP = cheaper
        dlo, dhi = r.difference("high"), r.difference("low")
        actual = u.actual_electricity
        now = (f"{n(rs(-actual))} روپے کے کریڈٹ" if actual < 0 else f"{n(rs(actual))} روپے")
        now_en = (f"the Rs {n(rs(-actual))} credit you got" if actual < 0
                  else f"the Rs {n(rs(actual))} you paid")
        lines.append(
            "آپ کا معاہدہ ختم ہونے تک پرانی شرائط برقرار ہیں "
            "(پروسیومر ریگولیشنز 2026، ضابطہ 21(2))۔ تجدید پر ہر لیا گیا یونٹ ٹیرف پر اور "
            "ہر بھیجا گیا یونٹ تقریباً 9 سے 11 روپے میں خریدا جائے گا۔"
            if ur else "Your agreement keeps its old terms until it ends (Prosumer "
            "Regulations 2026, reg. 21(2)). On renewal, every unit you take is billed at the "
            "tariff and every unit you send back is bought at about Rs 9-11.")
        lines.append(
            f"{_mn(u.months[0], 'ur')} تا {_mn(u.months[-1], 'ur')} کی آپ کی اصل ریڈنگ "
            f"({n(imp)} یونٹ لیے، {n(u.export_total)} بھیجے) پر تجدید کی شرائط سے بل تقریباً "
            f"{n(rs(lo))} سے {n(rs(hi))} روپے بنتا، {now} کی بجائے - یعنی اس سہ ماہی میں "
            f"{n(rs(dlo))} سے {n(rs(dhi))} روپے زیادہ۔" if ur
            else f"Your real {_mn(u.months[0], 'en')} to {_mn(u.months[-1], 'en')} readings "
            f"({n(imp)} units taken, {n(u.export_total)} sent back) would cost about "
            f"Rs {n(rs(lo))}-{n(rs(hi))} on renewal terms instead of {now_en} - about "
            f"Rs {n(rs(dlo))}-{n(rs(dhi))} more for that one quarter.")
        lines.append("ریٹ ثانوی ذرائع سے ہیں؛ فکسڈ چارجز اتنے ہی فرض کیے گئے ہیں۔" if ur
                     else "Rates are from secondary sources; fixed charges are assumed unchanged.")
    return lines
