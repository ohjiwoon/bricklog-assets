"""브릭로그 공모주 카드 이미지 생성기.

사용법:
    python3 scripts/make_cards.py data/ipo/2026-11-ykmc.json

입력 JSON 하나로 썸네일 + 브랜드 카드 3장을 만들어
ipo/<slug>/ 폴더에 저장한다. 틀은 고정, 숫자와 문구만 JSON에서 바꾼다.
폰트(Pretendard)가 없으면 npm으로 받아 .cache/ 에 둔다.
"""
import json
import os
import subprocess
import sys
import tarfile

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache")
FD = os.path.join(CACHE, "package/dist/public/static")
CHARACTER = os.path.join(ROOT, "brand/character.png")

# 브랜드 컬러 (brand guide v1)
ORANGE = "#FF7A45"; BROWN = "#3B230F"; YELLOW = "#FFC400"; GREEN = "#22A566"
BEIGE = "#FFF6E8"; WHITE = "#FFFFFF"; RED = "#E5484D"
MUTED = "#8A7560"; LINE = "#EADBC4"; SOFT_ORANGE = "#F7C9A9"
GRADE_COLOR = {"A": GREEN, "B": YELLOW, "C": RED}


def ensure_font():
    if os.path.exists(os.path.join(FD, "Pretendard-Black.otf")):
        return
    os.makedirs(CACHE, exist_ok=True)
    subprocess.run(["npm", "pack", "pretendard@1.3.9"], cwd=CACHE, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with tarfile.open(os.path.join(CACHE, "pretendard-1.3.9.tgz")) as t:
        t.extractall(CACHE, filter="data")


def F(weight, size):
    return ImageFont.truetype(f"{FD}/Pretendard-{weight}.otf", size)


def rr(d, box, r, **kw):
    d.rounded_rectangle(box, r, **kw)


_char = None


def paste_char(img, h, xy):
    global _char
    if _char is None:
        _char = Image.open(CHARACTER).convert("RGBA")
    c = _char.resize((int(_char.width * h / _char.height), h), Image.LANCZOS)
    img.alpha_composite(c, xy)


def header(d, img, title, name, W):
    rr(d, (40, 40, W - 40, 150), 24, fill=BROWN)
    d.text((80, 66), title, font=F("ExtraBold", 40), fill=WHITE)
    tx = 80 + d.textlength(title, font=F("ExtraBold", 40)) + 20
    d.text((tx, 78), name, font=F("Medium", 26), fill="#F3D9B8")
    paste_char(img, 100, (W - 230, 46))


def fit(d, text, weight, size, max_w):
    while size > 20 and d.textlength(text, font=F(weight, size)) > max_w:
        size -= 2
    return size


def brick_check(c, out):
    W, H = 1080, 1050
    img = Image.new("RGBA", (W, H), BEIGE); d = ImageDraw.Draw(img)
    header(d, img, "BRICK CHECK", c["name"], W)
    y = 190
    for row in c["brick_check"]:
        rr(d, (40, y, W - 40, y + 130), 22, fill=WHITE, outline=LINE, width=2)
        d.text((80, y + 30), row["label"], font=F("ExtraBold", 40), fill=BROWN)
        d.text((80, y + 82), row["desc"], font=F("Medium", 22), fill=MUTED)
        fs = fit(d, row["value"], "SemiBold", 32, 540)
        d.text((330, y + 44), row["value"], font=F("SemiBold", fs), fill=BROWN)
        g = row["grade"]; cx = W - 130
        d.ellipse((cx - 48, y + 17, cx + 48, y + 113), fill=GRADE_COLOR[g])
        tw = d.textlength(g, font=F("Black", 54))
        d.text((cx - tw / 2, y + 28), g, font=F("Black", 54), fill=BROWN if g == "B" else WHITE)
        y += 145
    rr(d, (40, y + 5, W - 40, y + 95), 22, fill=ORANGE)
    msg = c["one_liner"]; fs = fit(d, msg, "ExtraBold", 36, W - 140)
    tw = d.textlength(msg, font=F("ExtraBold", fs))
    d.text(((W - tw) / 2, y + 27), msg, font=F("ExtraBold", fs), fill=WHITE)
    img.convert("RGB").save(f"{out}/card1_brick_check.png")


def ipo_info(c, out):
    W, H = 1080, 840
    img = Image.new("RGBA", (W, H), BEIGE); d = ImageDraw.Draw(img)
    header(d, img, "청약 한눈에", c["name"], W)
    x0, y0, cw, ch, gap = 40, 190, 490, 190, 20
    for i, it in enumerate(c["info"]):
        hot = it.get("hot", False)
        cx = x0 + (i % 2) * (cw + gap); cy = y0 + (i // 2) * (ch + gap)
        rr(d, (cx, cy, cx + cw, cy + ch), 24, fill=ORANGE if hot else WHITE,
           outline=None if hot else LINE, width=2)
        d.text((cx + 36, cy + 36), it["label"], font=F("SemiBold", 28), fill=WHITE if hot else MUTED)
        fs = fit(d, it["value"], "ExtraBold", 40, cw - 72)
        d.text((cx + 36, cy + 92), it["value"], font=F("ExtraBold", fs), fill=WHITE if hot else BROWN)
    img.convert("RGB").save(f"{out}/card2_ipo_info.png")


def float_chart(c, out):
    W, H = 1080, 870
    img = Image.new("RGBA", (W, H), BEIGE); d = ImageDraw.Draw(img)
    header(d, img, "풀리는 물량", c["name"], W)
    data = c["float"]["steps"]
    rr(d, (40, 180, W - 40, 790), 24, fill=WHITE, outline=LINE, width=2)
    left, right, top, base = 90, W - 90, 250, 700
    n = len(data); slot = (right - left) / n; bw = slot * (0.62 if n > 4 else 0.5)
    for t in (0, 50, 100):
        yy = base - (base - top) * t / 100
        d.line((left, yy, right, yy), fill=LINE, width=2)
    for i, (lab, v) in enumerate(data):
        x = left + slot * i + (slot - bw) / 2
        yy = base - (base - top) * v / 100
        col = ORANGE if i == 0 else ("#E6D6C2" if v >= 100 else SOFT_ORANGE)
        rr(d, (x, yy, x + bw, base), 10, fill=col)
        s = "100%" if v >= 100 else f"{v:.1f}%"
        tw = d.textlength(s, font=F("Bold", 24))
        d.text((x + bw / 2 - tw / 2, yy - 36), s, font=F("Bold", 24), fill=ORANGE if i == 0 else BROWN)
        tw = d.textlength(lab, font=F("Medium", 21))
        d.text((x + bw / 2 - tw / 2, base + 14), lab, font=F("Medium", 21), fill=MUTED)
    cap = c["float"]["caption"]; fs = fit(d, cap, "SemiBold", 26, W - 140)
    d.text((70, 808), cap, font=F("SemiBold", fs), fill=BROWN)
    img.convert("RGB").save(f"{out}/card3_float.png")


def thumbnail(c, out):
    W = H = 1080
    t = c["thumbnail"]
    img = Image.new("RGBA", (W, H), BEIGE); d = ImageDraw.Draw(img)
    rr(d, (70, 70, 270, 135), 32, fill=ORANGE)
    d.text((112, 80), t.get("tag", "공모주"), font=F("ExtraBold", 36), fill=WHITE)
    d.text((W - 230, 85), c["date"], font=F("SemiBold", 30), fill=MUTED)
    fs = fit(d, c["name"], "Black", 150, W - 140)
    d.text((70, 300 - fs), c["name"], font=F("Black", fs), fill=BROWN)
    d.text((76, 400), t["headline"], font=F("ExtraBold", 72), fill=ORANGE)
    bfs = fit(d, t["badge"], "ExtraBold", 54, 900)
    bw = d.textlength(t["badge"], font=F("ExtraBold", bfs)) + 80
    rr(d, (70, 530, 70 + bw, 640), 28, fill=WHITE, outline=LINE, width=3)
    d.text((110, 553), t["badge"], font=F("ExtraBold", bfs), fill=BROWN)
    d.text((76, 680), t["stats"], font=F("SemiBold", 34), fill=MUTED)
    paste_char(img, 290, (W - 560, H - 320))
    d.rectangle((0, H - 30, W, H), fill=YELLOW)
    img.convert("RGB").save(f"{out}/thumbnail.png")


def main(path):
    ensure_font()
    with open(path, encoding="utf-8") as f:
        c = json.load(f)
    out = os.path.join(ROOT, "ipo", c["slug"])
    os.makedirs(out, exist_ok=True)
    thumbnail(c, out); brick_check(c, out); ipo_info(c, out); float_chart(c, out)
    print("saved to", out)


if __name__ == "__main__":
    main(sys.argv[1])
