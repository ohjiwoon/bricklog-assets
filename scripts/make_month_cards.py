"""브릭로그 월간 공모주 일정 카드 생성기.

사용법:
    python3 scripts/make_month_cards.py data/ipo/2026-11-month.json

입력 JSON 하나로 썸네일 + 일정 카드 + 증권사 카드를 ipo/<slug>/ 에 만든다.
"""
import json
import os
import sys

from PIL import Image, ImageDraw

from make_cards import BEIGE, BROWN, LINE, MUTED, ORANGE, ROOT, WHITE, F, ensure_font, fit, header, rr, thumbnail

W = 1080
ROW = 96


def schedule(c, out):
    rows = c["schedule"]
    H = 190 + ROW * len(rows) + 50
    img = Image.new("RGBA", (W, H), BEIGE); d = ImageDraw.Draw(img)
    header(d, img, c["schedule_title"], c["name"], W)
    y = 190
    for date, name, broker in rows:
        rr(d, (40, y, W - 40, y + ROW - 10), 18, fill=WHITE, outline=LINE, width=2)
        d.text((70, y + 26), date, font=F("ExtraBold", 32), fill=ORANGE)
        fs = fit(d, name, "ExtraBold", 34, 400)
        d.text((270, y + 26), name, font=F("ExtraBold", fs), fill=BROWN)
        fs = fit(d, broker, "SemiBold", 28, 330)
        tw = d.textlength(broker, font=F("SemiBold", fs))
        d.text((W - 70 - tw, y + 30), broker, font=F("SemiBold", fs), fill=MUTED)
        y += ROW
    img.convert("RGB").save(f"{out}/card_schedule.png")


def brokers(c, out):
    rows = c["brokers"]
    H = 190 + 118 * len(rows) + 50
    img = Image.new("RGBA", (W, H), BEIGE); d = ImageDraw.Draw(img)
    header(d, img, c["brokers_title"], c["name"], W)
    y = 190
    for broker, names in rows:
        rr(d, (40, y, W - 40, y + 104), 20, fill=WHITE, outline=LINE, width=2)
        d.text((70, y + 32), broker, font=F("ExtraBold", 36), fill=BROWN)
        fs = fit(d, names, "SemiBold", 30, 590)
        d.text((400, y + 36), names, font=F("SemiBold", fs), fill=MUTED)
        y += 118
    img.convert("RGB").save(f"{out}/card_brokers.png")


def main(path):
    ensure_font()
    with open(path, encoding="utf-8") as f:
        c = json.load(f)
    out = os.path.join(ROOT, "ipo", c["slug"])
    os.makedirs(out, exist_ok=True)
    thumbnail(c, out); schedule(c, out); brokers(c, out)
    print("saved to", out)


if __name__ == "__main__":
    main(sys.argv[1])
