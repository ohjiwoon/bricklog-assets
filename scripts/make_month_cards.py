"""브릭로그 월간 공모주 일정 카드 생성기.

사용법:
    python3 scripts/make_month_cards.py data/ipo/2026-11-month.json

입력 JSON 하나로 썸네일 + 일정 카드 + 증거금 달력 카드를 ipo/<slug>/ 에 만든다.
"""
import json
import os
import sys
from datetime import date, timedelta

from PIL import Image, ImageDraw

from make_cards import BEIGE, BROWN, LINE, MUTED, ORANGE, ROOT, SOFT_ORANGE, WHITE, F, ensure_font, fit, header, rr, thumbnail

W = 1080
ROW = 96


def schedule(c, out):
    rows = c["schedule"]
    H = 250 + ROW * len(rows) + 50
    img = Image.new("RGBA", (W, H), BEIGE); d = ImageDraw.Draw(img)
    header(d, img, c["schedule_title"], c["name"], W)
    for x, label in ((70, "청약"), (250, "종목"), (620, "증권사"), (900, "환불")):
        d.text((x, 186), label, font=F("SemiBold", 26), fill=MUTED)
    y = 240
    for date, name, broker, refund in rows:
        rr(d, (40, y, W - 40, y + ROW - 10), 18, fill=WHITE, outline=LINE, width=2)
        d.text((70, y + 28), date, font=F("ExtraBold", 28), fill=ORANGE)
        fs = fit(d, name, "ExtraBold", 32, 350)
        d.text((250, y + 26), name, font=F("ExtraBold", fs), fill=BROWN)
        fs = fit(d, broker, "SemiBold", 26, 260)
        d.text((620, y + 30), broker, font=F("SemiBold", fs), fill=MUTED)
        d.text((900, y + 28), refund, font=F("ExtraBold", 28), fill=BROWN)
        y += ROW
    img.convert("RGB").save(f"{out}/card_schedule.png")


def margins(c):
    """종목별 증거금(50%)과 날짜별 묶이는 돈. 마감일에 넣고 환불일 아침에 돌아온다고 본다."""
    bricks = [(n, date.fromisoformat(a), date.fromisoformat(b), p * q // 2) for n, a, b, p, q in c["bricks"]]
    days = [bricks[0][1] + timedelta(i) for i in range((bricks[-1][2] - bricks[0][1]).days + 1)]
    tied = {d: sum(m for _, a, b, m in bricks if a <= d < b) for d in days}
    return bricks, days, tied


def bricks_card(c, out):
    bricks, days, tied = margins(c)
    row, top, left, right = 62, 250, 280, W - 60
    day_w = (right - left) / len(days)
    peak = max(tied.values())
    H = top + row * len(bricks) + 190
    img = Image.new("RGBA", (W, H), BEIGE); d = ImageDraw.Draw(img)
    header(d, img, c["bricks_title"], c["name"], W)
    x_of = lambda day: left + (day - days[0]).days * day_w
    bottom = top + row * len(bricks)
    for day in days:
        if tied[day] == peak:  # 가장 많이 묶이는 날 표시
            d.rectangle((x_of(day), top - 10, x_of(day) + day_w, bottom), fill=SOFT_ORANGE)
    for day in days:
        if day.weekday() == 0 or day == days[0]:
            d.line((x_of(day), top - 10, x_of(day), bottom), fill=LINE, width=2)
            d.text((x_of(day) + 2, top - 50), f"{day.month}/{day.day}", font=F("SemiBold", 24), fill=MUTED)
    for i, (name, a, b, m) in enumerate(bricks):
        y = top + i * row
        fs = fit(d, name, "SemiBold", 26, 205)
        d.text((60, y + 14), name, font=F("SemiBold", fs), fill=BROWN)
        rr(d, (x_of(a), y + 8, x_of(b), y + row - 8), 8, fill=ORANGE, outline=BROWN, width=2)
    total = sum(m for *_, m in bricks)
    rr(d, (40, bottom + 30, W - 40, bottom + 140), 22, fill=ORANGE)
    msg = f"12곳 합계 {total:,}원 → 가장 많이 묶이는 날 {peak:,}원"
    fs = fit(d, msg, "ExtraBold", 36, W - 140)
    tw = d.textlength(msg, font=F("ExtraBold", fs))
    d.text(((W - tw) / 2, bottom + 62), msg, font=F("ExtraBold", fs), fill=WHITE)
    img.convert("RGB").save(f"{out}/card_bricks.png")
    return total, peak, tied


def main(path):
    ensure_font()
    with open(path, encoding="utf-8") as f:
        c = json.load(f)
    out = os.path.join(ROOT, "ipo", c["slug"])
    os.makedirs(out, exist_ok=True)
    thumbnail(c, out); schedule(c, out)
    total, peak, tied = bricks_card(c, out)
    print("saved to", out, f"(합계 {total:,}, 최대 {peak:,})")
    for day, amount in tied.items():
        print(day, f"{amount:,}")


if __name__ == "__main__":
    main(sys.argv[1])
