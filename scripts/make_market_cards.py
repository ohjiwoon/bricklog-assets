"""시황 카드 생성기. 썸네일 + 하루 숫자 카드 1장.

사용법:
    python3 scripts/make_market_cards.py data/market/<slug>.json   # → market/<slug>/
"""
import json
import os
import sys

from PIL import Image, ImageDraw

from make_cards import BEIGE, BROWN, LINE, MUTED, RED, ROOT, WHITE, F, ensure_font, header, rr, thumbnail

W = 1080
DOWN = "#2F6FDB"  # 국내 시세 관례: 하락 파랑, 상승 빨강


def pct(v):
    return f"{v:+.2f}%" if abs(v) < 10 else f"{v:+.1f}%"


def color(v):
    return RED if v > 0 else DOWN


def day_card(c, out):
    H = 1110
    img = Image.new("RGBA", (W, H), BEIGE); d = ImageDraw.Draw(img)
    header(d, img, "오늘 숫자로 보면", c["name"], W)

    # 지수 두 칸
    bw, y = (W - 120) // 2, 190
    for i, ix in enumerate(c["indices"]):
        x = 40 + i * (bw + 40)
        rr(d, (x, y, x + bw, y + 330), 24, fill=WHITE, outline=LINE, width=3)
        d.text((x + 36, y + 30), ix["name"], font=F("ExtraBold", 36), fill=BROWN)
        d.text((x + 36, y + 86), ix["close"], font=F("Black", 72), fill=BROWN)
        d.text((x + 36, y + 180), pct(ix["day"]), font=F("Black", 60), fill=color(ix["day"]))
        d.text((x + 36, y + 268), f"5거래일 {pct(ix['d5'])} · 20거래일 {pct(ix['d20'])}",
               font=F("SemiBold", 24), fill=MUTED)

    # 수급 막대 (가운데 0 기준)
    y = 570
    d.text((40, y), c["flow_title"], font=F("ExtraBold", 34), fill=BROWN)
    mid, half = W // 2 + 60, 300
    top = max(abs(v) for _, v in c["flows"])
    for j, (who, v) in enumerate(c["flows"]):
        ry = y + 70 + j * 84
        d.text((40, ry + 8), who, font=F("SemiBold", 32), fill=BROWN)
        L = int(half * abs(v) / top)
        box = (mid - L, ry, mid, ry + 52) if v < 0 else (mid, ry, mid + L, ry + 52)
        rr(d, box, 10, fill=color(v))
        label = f"{v:+,}"
        lf = F("ExtraBold", 28)
        lw = d.textlength(label, font=lf)
        lx = max(mid - L - 16 - lw, 170) if v < 0 else min(mid + L + 16, W - 40 - lw)
        d.text((lx, ry + 10), label, font=lf, fill=color(v))
    d.line((mid, y + 60, mid, y + 70 + len(c["flows"]) * 84), fill=MUTED, width=2)

    # 장중 사건
    y = 940
    x = 40
    for e in c["events"]:
        tw = d.textlength(e, font=F("SemiBold", 28))
        if x + tw + 48 > W - 40:
            x, y = 40, y + 76
        rr(d, (x, y, x + tw + 48, y + 60), 30, fill=BROWN)
        d.text((x + 24, y + 12), e, font=F("SemiBold", 28), fill=WHITE)
        x += tw + 64
    d.text((40, H - 70), c["source"], font=F("Medium", 22), fill=MUTED)
    img.convert("RGB").save(f"{out}/card_day.png")


def main(path):
    ensure_font()
    with open(path, encoding="utf-8") as f:
        c = json.load(f)
    out = os.path.join(ROOT, "market", c["slug"])
    os.makedirs(out, exist_ok=True)
    thumbnail(c, out); day_card(c, out)
    print("saved to", out)


if __name__ == "__main__":
    main(sys.argv[1])
