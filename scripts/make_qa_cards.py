"""공모주 Q&A 썸네일 생성기. 답은 넣지 않고 질문만 보여준다.

사용법:
    python3 scripts/make_qa_cards.py data/qa/<slug>.json   # → qa/<slug>/thumbnail.png
"""
import json
import os
import sys

from PIL import Image, ImageDraw

from make_cards import BEIGE, BROWN, MUTED, ORANGE, ROOT, WHITE, YELLOW, F, ensure_font, fit, paste_char, rr


def thumbnail(c, out):
    W = H = 1080
    img = Image.new("RGBA", (W, H), BEIGE); d = ImageDraw.Draw(img)
    rr(d, (70, 70, 270, 135), 32, fill=ORANGE)
    d.text((112, 80), "Q&A", font=F("ExtraBold", 36), fill=WHITE)
    d.text((W - 230, 85), c["date"], font=F("SemiBold", 30), fill=MUTED)
    d.text((70, 160), "공모주 Q&A", font=F("Black", 150), fill=BROWN)
    y = 420
    for line in c["question"]:
        fs = fit(d, line, "ExtraBold", 88, W - 140)
        d.text((76, y), line, font=F("ExtraBold", fs), fill=ORANGE)
        y += fs + 30
    paste_char(img, 290, (W - 560, H - 320))
    d.rectangle((0, H - 30, W, H), fill=YELLOW)
    img.convert("RGB").save(f"{out}/thumbnail.png")


def main(path):
    ensure_font()
    with open(path, encoding="utf-8") as f:
        c = json.load(f)
    out = os.path.join(ROOT, "qa", c["slug"])
    os.makedirs(out, exist_ok=True)
    thumbnail(c, out)
    print("saved to", out)


if __name__ == "__main__":
    main(sys.argv[1])
