"""시황 카드 생성기.

큰 날 시황: 썸네일 + 하루 숫자 카드(indices).
주간 시황: 썸네일 + 주간 숫자 카드(days) + 지수 흐름 차트(trend).

사용법:
    python3 scripts/make_market_cards.py data/market/<slug>.json   # → market/<slug>/
"""
import json
import os
import sys

from PIL import Image, ImageDraw

from make_cards import BEIGE, BROWN, LINE, MUTED, RED, ROOT, WHITE, F, ensure_font, fit, header, rr, thumbnail

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


def week_card(c, out):
    H = 1180
    img = Image.new("RGBA", (W, H), BEIGE); d = ImageDraw.Draw(img)
    header(d, img, "숫자로 보는 한 주", c["name"], W)

    bw, y = (W - 120) // 2, 190
    for i, ix in enumerate(c["indices"]):
        x = 40 + i * (bw + 40)
        rr(d, (x, y, x + bw, y + 300), 24, fill=WHITE, outline=LINE, width=3)
        d.text((x + 36, y + 30), f"{ix['name']} 1주", font=F("ExtraBold", 34), fill=BROWN)
        d.text((x + 36, y + 80), pct(ix["week"]), font=F("Black", 84), fill=color(ix["week"]))
        d.text((x + 36, y + 190), f"종가 {ix['close']}", font=F("SemiBold", 28), fill=BROWN)
        d.text((x + 36, y + 238), f"20거래일 {pct(ix['d20'])}", font=F("SemiBold", 24), fill=MUTED)

    # 요일별 막대: 왼쪽 코스피, 오른쪽 코스닥(옅은 색)
    y = 540
    d.text((40, y), "하루하루 (왼쪽 코스피 · 오른쪽 코스닥)", font=F("ExtraBold", 32), fill=BROWN)
    zero, scale, col = 760, 26, (W - 80) // len(c["days"])
    d.line((40, zero, W - 40, zero), fill=MUTED, width=2)
    for i, (date, wd, kospi, kosdaq, event) in enumerate(c["days"]):
        cx = 40 + i * col + col // 2
        for j, v in enumerate((kospi, kosdaq)):
            x0 = cx - 54 + j * 58
            h = int(abs(v) * scale)
            box = (x0, zero - h, x0 + 50, zero) if v > 0 else (x0, zero, x0 + 50, zero + h)
            fill = color(v) if j == 0 else ("#F2A7A9" if v > 0 else "#A9C3F0")
            rr(d, box, 6, fill=fill)
            label = f"{v:+.1f}"
            lf = F("Bold", 20)
            lw = d.textlength(label, font=lf)
            ly = box[1] - 28 if v > 0 else box[3] + 6
            d.text((x0 + 25 - lw / 2, ly), label, font=lf, fill=color(v))
        for k, (text, font, fill) in enumerate(((date, F("ExtraBold", 28), BROWN), (wd, F("Medium", 24), MUTED))):
            tw = d.textlength(text, font=font)
            d.text((cx - tw / 2, 960 + k * 36), text, font=font, fill=fill)
        if event:
            ef = F("SemiBold", 20)
            lines = event.split(" · ")
            ey = 590
            for line in lines:
                tw = d.textlength(line, font=ef)
                rr(d, (cx - tw / 2 - 14, ey, cx + tw / 2 + 14, ey + 36), 18, fill=BROWN)
                d.text((cx - tw / 2, ey + 6), line, font=ef, fill=WHITE)
                ey += 44
    d.text((40, H - 70), c["source"], font=F("Medium", 20), fill=MUTED)
    img.convert("RGB").save(f"{out}/card_week.png")


def trend_card(c, out):
    H = 1000
    img = Image.new("RGBA", (W, H), BEIGE); d = ImageDraw.Draw(img)
    header(d, img, c["trend_title"], "코스피 종가", W)
    series = c["trend"]
    vals = [v for _, v in series]
    lo, hi = min(vals) - 450, max(vals) + 200
    left, right, top, bottom = 140, W - 60, 230, 820

    def pos(i, v):
        return (left + (right - left) * i / (len(series) - 1),
                bottom - (bottom - top) * (v - lo) / (hi - lo))

    for level in range(5000, int(hi) + 1, 1000):  # 눈금
        _, gy = pos(0, level)
        d.line((left, gy, right, gy), fill=LINE, width=2)
        d.text((40, gy - 14), f"{level:,}", font=F("Medium", 22), fill=MUTED)
    # 월 눈금
    seen = set()
    for i, (day, _) in enumerate(series):
        m = int(day[5:7])
        if m not in seen:
            seen.add(m)
            gx, _ = pos(i, lo)
            d.text((gx, bottom + 16), f"{m}월", font=F("SemiBold", 24), fill=MUTED)

    marks = c["trend_marks"]
    idx = {day: i for i, (day, _) in enumerate(series)}
    low_i = idx[marks["low"]]
    low_v = series[low_i][1]
    _, ly = pos(0, low_v)
    for x in range(left, right, 24):  # 7월 저점 점선
        d.line((x, ly, x + 12, ly), fill=DOWN, width=3)
    d.line([pos(i, v) for i, (_, v) in enumerate(series)], fill=BROWN, width=5, joint="curve")

    def dot(i, fill, label, dx, dy, align_right=False):
        x, y = pos(i, series[i][1])
        if abs(dy) > 100:  # 선과 겹치지 않게 빈 곳으로 빼고 지시선을 잇는다
            d.line((x, y, x, y + dy + len(label) * 34), fill=fill, width=2)
        d.ellipse((x - 10, y - 10, x + 10, y + 10), fill=fill, outline=WHITE, width=3)
        lf = F("ExtraBold", 26)
        tw = max(d.textlength(t, font=lf) for t in label)
        tx = x + dx - (tw if align_right else 0)
        rr(d, (tx - 10, y + dy - 6, tx + tw + 10, y + dy + len(label) * 34 + 4), 10, fill=BEIGE)
        for k, t in enumerate(label):
            d.text((tx, y + dy + k * 34), t, font=lf, fill=fill)

    dot(low_i, DOWN, [f"7/30 저점", f"{low_v:,.2f}"], -20, 20, align_right=True)
    reb_i = idx[marks["rebound"]]
    gain = (series[reb_i][1] / low_v - 1) * 100
    dot(reb_i, RED, [f"7/31 하루 {gain:+.1f}%", "반등"], -12, -330)
    last_v = series[-1][1]
    dot(len(series) - 1, DOWN, ["11/6", f"{last_v:,.2f}"], -24, -20, align_right=True)
    gap = (last_v / low_v - 1) * 100
    note = f"지금 코스피는 7월 저점보다 {abs(gap):.1f}% 아래"
    rr(d, (40, 890, 80 + d.textlength(note, font=F("ExtraBold", 32)), 950), 30, fill=BROWN)
    d.text((60, 900), note, font=F("ExtraBold", 32), fill=WHITE)
    img.convert("RGB").save(f"{out}/card_trend.png")


def numbers_card(c, out):
    """데일리: 지수 두 칸 + 투자자별 순매수(억 원) + 거래대금."""
    t = c["today"]
    H = 1040
    img = Image.new("RGBA", (W, H), BEIGE); d = ImageDraw.Draw(img)
    header(d, img, "오늘 숫자", c["name"], W)

    bw, y = (W - 120) // 2, 190
    for i, ix in enumerate(t["indices"]):
        x = 40 + i * (bw + 40)
        rr(d, (x, y, x + bw, y + 230), 24, fill=WHITE, outline=LINE, width=3)
        d.text((x + 36, y + 28), ix["name"], font=F("ExtraBold", 34), fill=BROWN)
        d.text((x + 36, y + 78), pct(ix["day"]), font=F("Black", 72), fill=color(ix["day"]))
        d.text((x + 36, y + 170), f"종가 {ix['close']}", font=F("SemiBold", 28), fill=BROWN)

    # 투자자별 순매수: 행은 개인·외국인·기관, 열은 코스피·코스닥
    y = 460
    d.text((40, y), "누가 사고 팔았나 (억 원)", font=F("ExtraBold", 32), fill=BROWN)
    y += 60
    rr(d, (40, y, W - 40, y + 300), 24, fill=WHITE, outline=LINE, width=2)
    cols = [x["name"] for x in t["indices"]]
    cx = [560, 860]
    for j, name in enumerate(cols):
        tw = d.textlength(name, font=F("SemiBold", 26))
        d.text((cx[j] - tw / 2, y + 22), name, font=F("SemiBold", 26), fill=MUTED)
    for k, who in enumerate(("개인", "외국인", "기관")):
        ry = y + 80 + k * 70
        d.text((80, ry), who, font=F("ExtraBold", 34), fill=BROWN)
        for j, name in enumerate(cols):
            v = t["flows"][name][k]
            label = f"{v:+,}"
            tw = d.textlength(label, font=F("ExtraBold", 36))
            d.text((cx[j] - tw / 2, ry - 2), label, font=F("ExtraBold", 36), fill=color(v))

    # 거래대금: 시장별 칩, 전일 대비가 있으면 함께
    y = 862
    d.text((40, y), "거래대금", font=F("ExtraBold", 32), fill=BROWN)
    x, y = 40, y + 60
    for name, value, change in t["value"]:
        label = f"{name} {value}" + (f" ({change})" if change else "")
        tw = d.textlength(label, font=F("SemiBold", 30))
        if x + tw + 48 > W - 40:
            x, y = 40, y + 72
        rr(d, (x, y, x + tw + 48, y + 60), 30, fill=BROWN)
        d.text((x + 24, y + 12), label, font=F("SemiBold", 30), fill=WHITE)
        x += tw + 64
    img.convert("RGB").save(f"{out}/card_numbers.png")


def sector_card(c, out, cols=3):
    """데일리: 섹터·테마 칸을 cols열 격자로(칸마다 이름·이유 + 대장 종목 3~4개), 아래에 늘 보는 섹터 칩.

    칸은 3~6개. 오른 종목 3개 이상에 대장주가 +5% 이상인 묶음만 넣고, 모자라면 6칸을 채우지 않는다."""
    gap, top = 24, 190
    cw = (W - 80 - gap * (cols - 1)) // cols
    nrows = -(-len(c["sectors"]) // cols)
    most = max(len(s["leaders"]) for s in c["sectors"])
    ch = 150 + most * 52
    H = top + nrows * (ch + gap) + (170 if c.get("watch") else 0) + 30
    img = Image.new("RGBA", (W, H), BEIGE); d = ImageDraw.Draw(img)
    header(d, img, "오늘의 주도 섹터·테마", c["name"], W)
    small = cols >= 3
    nf, rf, wf = (F("ExtraBold", 32), F("SemiBold", 24), F("Medium", 20)) if small else \
                 (F("ExtraBold", 38), F("SemiBold", 28), F("Medium", 24))

    for i, s in enumerate(c["sectors"]):
        x = 40 + (i % cols) * (cw + gap)
        y = top + (i // cols) * (ch + gap)
        lead = i == 0
        rr(d, (x, y, x + cw, y + ch), 24, fill=WHITE, outline=RED if lead else LINE, width=4 if lead else 2)
        if lead:  # 섹터·테마는 구분하지 않고, 첫 칸에만 '오늘의 주도' 꼬리표
            tf = F("Bold", 20)
            tw = d.textlength("오늘의 주도", font=tf)
            rr(d, (x + 22, y + 20, x + 22 + tw + 24, y + 52), 16, fill=RED)
            d.text((x + 34, y + 24), "오늘의 주도", font=tf, fill=WHITE)
        name_font = F("ExtraBold", fit(d, s["name"], "ExtraBold", nf.size, cw - 44))
        d.text((x + 22, y + 62), s["name"], font=name_font, fill=BROWN)
        if s.get("why"):
            d.text((x + 24, y + 108), s["why"], font=F("Medium", fit(d, s["why"], "Medium", wf.size, cw - 44)), fill=MUTED)
        ry = y + 146
        for name, v in s["leaders"]:
            label = "상한가" if v >= 29.5 else f"{v:+.1f}%"  # 가격제한폭 30%는 호가 단위 때문에 29.9%대로 찍힌다
            lw = d.textlength(label, font=rf)
            d.text((x + cw - 22 - lw, ry), label, font=F("ExtraBold", rf.size), fill=color(v))
            d.text((x + 22, ry), name, font=F("SemiBold", fit(d, name, "SemiBold", rf.size, cw - 66 - lw)), fill=BROWN)
            ry += 52

    y = top + nrows * (ch + gap) + 10
    if c.get("watch"):  # 늘 보는 섹터가 오늘 어땠는지: 빨강 강세, 파랑 약세
        d.text((40, y), "늘 보는 섹터", font=F("ExtraBold", 30), fill=BROWN)
        x, y = 40, y + 52
        for name, v in c["watch"]:
            label = f"{name} {'▲' if v > 0 else '▼'}"
            tw = d.textlength(label, font=F("SemiBold", 26))
            if x + tw + 40 > W - 40:
                x, y = 40, y + 60
            rr(d, (x, y, x + tw + 40, y + 48), 24, fill=color(v))
            d.text((x + 20, y + 9), label, font=F("SemiBold", 26), fill=WHITE)
            x += tw + 56
    img.convert("RGB").save(f"{out}/card_sector.png")


def main(path):
    ensure_font()
    with open(path, encoding="utf-8") as f:
        c = json.load(f)
    out = os.path.join(ROOT, "market", c["slug"])
    os.makedirs(out, exist_ok=True)
    thumbnail(c, out)
    if "days" in c:  # 주간 시황
        week_card(c, out)
        trend_card(c, out)
    elif "indices" in c:  # 큰 날 시황
        day_card(c, out)
    if "today" in c:  # 데일리 시황
        numbers_card(c, out)
    if "sectors" in c:
        sector_card(c, out, c.get("grid_cols", 3))
    print("saved to", out)


if __name__ == "__main__":
    main(sys.argv[1])
