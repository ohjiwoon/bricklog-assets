"""브릭로그 월간 공모주 일정 카드 생성기.

사용법:
    python3 scripts/make_month_cards.py data/ipo/2026-11-month.json

입력 JSON 하나로 썸네일 + 달력 카드를 ipo/<slug>/ 에 만든다.
"""
import json
import os
import sys
from datetime import date, timedelta

from PIL import Image, ImageDraw

from make_cards import BEIGE, BROWN, GREEN, LINE, MUTED, ORANGE, ROOT, WHITE, F, ensure_font, fit, header, rr, thumbnail

W = 1080


def split_name(name):
    """칸에 안 들어가는 긴 종목명은 두 줄로 나눈다."""
    return [name] if len(name) <= 6 else [name[:len(name) // 2], name[len(name) // 2:]]


def parse_day(text):
    month, day = text.split("/")
    return date(2026, int(month), int(day))


def calendar_entries(c):
    """날짜별 청약(증권사 포함)·마감·환불 항목을 모은다."""
    subs, refunds = {}, {}
    for span, name, broker, refund in c["schedule"]:
        first, last = span.split("~")
        start = parse_day(first)
        end = start.replace(day=int(last)) if "/" not in last else parse_day(last)
        day = start
        while day <= end:
            if day.weekday() < 5:
                subs.setdefault(day, []).append((name, broker, day == end))
            day += timedelta(1)
        refunds.setdefault(parse_day(refund), []).append(name)
    return subs, refunds


def calendar_card(c, out):
    subs, refunds = calendar_entries(c)
    x0, cell_w, top = 40, 200, 250
    line, chip_gap, chip_pad = 28, 8, 12

    def chip_h(name):
        return len(split_name(name)) * line + 26 + chip_pad

    weeks = []
    first = date(2026, 11, 2)
    last = max(list(subs) + list(refunds))
    while first <= last:
        days = [first + timedelta(i) for i in range(5)]
        h = 60
        for day in days:
            used = sum(chip_h(n) + chip_gap for n, _, _ in subs.get(day, []))
            names = refunds.get(day, [])
            if names:
                used += 34 + sum(len(split_name(n)) * 26 for n in names) + 14
            h = max(h, 60 + used)
        weeks.append((days, max(h, 150)))
        first += timedelta(7)

    H = top + sum(h for _, h in weeks) + 110
    img = Image.new("RGBA", (W, H), BEIGE); d = ImageDraw.Draw(img)
    header(d, img, c["calendar_title"], c["name"], W)
    for i, label in enumerate("월화수목금"):
        tw = d.textlength(label, font=F("SemiBold", 28))
        d.text((x0 + i * cell_w + (cell_w - tw) / 2, 190), label, font=F("SemiBold", 28), fill=MUTED)
    y = top
    for days, h in weeks:
        for i, day in enumerate(days):
            cx = x0 + i * cell_w
            d.rectangle((cx, y, cx + cell_w, y + h), fill=WHITE, outline=LINE, width=2)
            label = f"{day.month}/{day.day}"
            d.text((cx + 12, y + 10), label, font=F("ExtraBold", 28), fill=BROWN)
            cy = y + 52
            for name, broker, is_last in subs.get(day, []):
                ch = chip_h(name)
                rr(d, (cx + 8, cy, cx + cell_w - 8, cy + ch), 12, fill=BROWN if is_last else ORANGE)
                ty = cy + 6
                for part in split_name(name):
                    d.text((cx + 18, ty), part, font=F("ExtraBold", 24), fill=WHITE)
                    ty += line
                fs = fit(d, broker, "Medium", 20, cell_w - 36) if d.textlength(broker, font=F("Medium", 20)) > cell_w - 36 else 20
                d.text((cx + 18, ty), broker, font=F("Medium", fs), fill="#FFE9D9")
                cy += ch + chip_gap
            names = refunds.get(day, [])
            if names:
                d.text((cx + 12, cy + 4), "환불", font=F("ExtraBold", 24), fill=GREEN)
                ty = cy + 34
                for name in names:
                    for part in split_name(name):
                        d.text((cx + 12, ty), part, font=F("SemiBold", 22), fill=GREEN)
                        ty += 26
        y += h
    lx = x0
    for color, label in ((ORANGE, "청약"), (BROWN, "청약 마감일"), (GREEN, "환불")):
        rr(d, (lx, y + 34, lx + 34, y + 68), 8, fill=color)
        d.text((lx + 44, y + 34), label, font=F("SemiBold", 26), fill=BROWN)
        lx += 44 + d.textlength(label, font=F("SemiBold", 26)) + 44
    img.convert("RGB").save(f"{out}/card_calendar.png")


def main(path):
    ensure_font()
    with open(path, encoding="utf-8") as f:
        c = json.load(f)
    out = os.path.join(ROOT, "ipo", c["slug"])
    os.makedirs(out, exist_ok=True)
    thumbnail(c, out); calendar_card(c, out)
    print("saved to", out)


if __name__ == "__main__":
    main(sys.argv[1])
