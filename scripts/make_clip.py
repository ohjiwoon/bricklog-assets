"""브릭로그 공모주 세로 숏폼(네이버 클립) 샘플 생성기.

사용법:
    python3 scripts/make_clip.py

macOS say로 내레이션을 만들고 PIL로 프레임을 그려 ffmpeg로 합친다.
결과: clips/2026-11-alrobot_sample.mp4 (1080x1920, 30fps)
"""
import os
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FD = os.path.join(ROOT, ".cache/package/dist/public/static")
OUT = os.path.join(ROOT, "clips/2026-11-alrobot_sample.mp4")
W, H, FPS = 1080, 1920, 30
VOICE, RATE = "Yuna", "205"
PAD = 0.35

ORANGE = "#FF7A45"; BROWN = "#3B230F"; YELLOW = "#FFC400"; GREEN = "#22A566"
BEIGE = "#FFF6E8"; WHITE = "#FFFFFF"; RED = "#E5484D"; MUTED = "#8A7560"; LINE = "#EADBC4"

_fonts = {}
_text = {}


def F(weight, size):
    key = (weight, size)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(f"{FD}/Pretendard-{weight}.otf", size)
    return _fonts[key]


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def text_img(s, weight, size, color):
    key = (s, weight, size, color)
    if key not in _text:
        f = F(weight, size)
        box = f.getbbox(s)
        img = Image.new("RGBA", (box[2] + 8, box[3] + 16), (0, 0, 0, 0))
        ImageDraw.Draw(img).text((0, 0), s, font=f, fill=color)
        _text[key] = img
    return _text[key]


def put(frame, s, weight, size, color, y, t, t0, x=None, rise=46):
    """t0초에 아래에서 올라오며 나타나는 글자. x가 없으면 가운데 정렬."""
    p = ease((t - t0) / 0.35)
    if p <= 0:
        return
    img = text_img(s, weight, size, color)
    if p < 1:
        img = img.copy()
        img.putalpha(img.getchannel("A").point(lambda a: int(a * p)))
    px = (W - img.width) // 2 if x is None else x
    frame.alpha_composite(img, (px, int(y + rise * (1 - p))))


def pill(frame, s, y, fill, color, t, t0):
    p = ease((t - t0) / 0.3)
    if p <= 0:
        return
    f = F("ExtraBold", 44)
    w = int(f.getlength(s)) + 80
    d = ImageDraw.Draw(frame)
    x = (W - w) // 2
    d.rounded_rectangle((x, y, x + w, y + 92), 46, fill=fill)
    d.text((x + 40, y + 18), s, font=f, fill=color)


def bar(frame, x, y, w, h, ratio, color, back=LINE):
    d = ImageDraw.Draw(frame)
    d.rounded_rectangle((x, y, x + w, y + h), h // 2, fill=back)
    fw = int(w * ratio)
    if fw > h:
        d.rounded_rectangle((x, y, x + fw, y + h), h // 2, fill=color)


_char = Image.open(os.path.join(ROOT, "brand/character.png")).convert("RGBA")


def character(frame, h, cy, t, t0):
    p = ease((t - t0) / 0.45)
    if p <= 0:
        return
    hh = max(1, int(h * (0.7 + 0.3 * p)))
    c = _char.resize((int(_char.width * hh / _char.height), hh), Image.LANCZOS)
    frame.alpha_composite(c, ((W - c.width) // 2, cy - hh // 2))


def s_hook(f, t, dur):
    pill(f, "에이엘로봇 공모주", 300, ORANGE, WHITE, t, 0)
    put(f, "장외에서 부르는 값", "Bold", 70, BROWN, 500, t, 0.15)
    p = ease((t - 0.4) / 0.4)
    if p > 0:
        put(f, "30,000원", "Black", 190, ORANGE, 610, t, 0.4)
    put(f, "믿어도 될까?", "Black", 110, BROWN, 850, t, 1.1)
    put(f, "공모가 17,600원", "ExtraBold", 66, MUTED, 1050, t, 1.7)
    put(f, "게시 호가 기준, 실제 체결가 아님", "Medium", 36, MUTED, 1150, t, 1.7)


def s_mix(f, t, dur):
    put(f, "로봇 센서 회사로 알려졌지만", "Bold", 62, BROWN, 340, t, 0)
    p = ease((t - 0.5) / 1.0)
    put(f, f"{int(94 * p)}%", "Black", 260, ORANGE, 460, t, 0.3)
    put(f, "작년 매출 중 제어장치", "ExtraBold", 66, BROWN, 790, t, 0.8)
    if t > 0.5:
        bar(f, 110, 930, 860, 80, 0.94 * p, ORANGE)
    put(f, "센서는 약 9억 원", "ExtraBold", 66, MUTED, 1070, t, 1.5)


def s_future(f, t, dur):
    put(f, "작년 영업이익", "Bold", 62, BROWN, 340, t, 0)
    put(f, "-13억", "Black", 170, RED, 430, t, 0.2)
    put(f, "2028년 회사 전망", "Bold", 62, BROWN, 700, t, 1.1)
    put(f, "+142억", "Black", 170, GREEN, 790, t, 1.3)
    pill(f, "공모가는 2028년 이익 기준", 1090, BROWN, WHITE, t, 2.2)


def s_lock(f, t, dur):
    p = ease((t - 0.1) / 0.9)
    put(f, "기관 경쟁률", "Bold", 62, BROWN, 340, t, 0)
    put(f, f"{int(872 * p)} : 1", "Black", 170, BROWN, 430, t, 0.1)
    put(f, "오래 들고 가겠다는 확약은", "Bold", 62, BROWN, 720, t, 1.3)
    put(f, "1.13%", "Black", 220, RED, 810, t, 1.6)
    if t > 1.6:
        bar(f, 110, 1100, 860, 56, 0.0113 * ease((t - 1.6) / 0.5) + 0.012, RED)


def s_float(f, t, dur):
    p = ease((t - 0.2) / 1.0)
    put(f, "상장 첫날 거래 가능 물량", "Bold", 62, BROWN, 340, t, 0)
    put(f, f"약 {int(742 * p)}억", "Black", 210, ORANGE, 450, t, 0.2)
    put(f, "공모가 기준 평가액", "ExtraBold", 56, MUTED, 740, t, 0.8)
    if t > 0.8:
        bar(f, 110, 860, 860, 80, 0.3494 * ease((t - 0.8) / 0.6), ORANGE)
    put(f, "전체 주식의 34.94%", "ExtraBold", 66, BROWN, 980, t, 1.3)


def s_end(f, t, dur):
    character(f, 430, 560, t, 0)
    put(f, "제가 끝까지 고민한", "ExtraBold", 80, BROWN, 820, t, 0.3)
    put(f, "3가지", "Black", 170, ORANGE, 920, t, 0.5)
    put(f, "전체 분석은 블로그에서", "ExtraBold", 62, BROWN, 1140, t, 1.0)
    put(f, "청약 11/6~11/9 · 대신증권", "SemiBold", 48, MUTED, 1230, t, 1.2)
    put(f, "투자 권유가 아닌 개인 기록입니다", "Medium", 36, MUTED, 1310, t, 1.2)


SCENES = [
    ("장외에서 3만 원 부른다는 공모주, 믿어도 될까요?", s_hook, BEIGE),
    ("에이엘로봇은 로봇 센서 회사로 알려졌지만, 작년 매출의 94%는 제어장치였습니다.", s_mix, WHITE),
    ("작년엔 영업손실 13억 원. 공모가는 2028년 회사 전망 이익을 기준으로 계산했습니다.", s_future, BEIGE),
    ("기관 경쟁률은 872대 1인데, 오래 들고 가겠다는 확약은 1.13%뿐입니다.", s_lock, WHITE),
    ("상장 첫날 거래할 수 있는 물량은 공모가 기준 약 742억 원어치입니다.", s_float, BEIGE),
    ("제가 끝까지 고민한 3가지, 전체 내용은 브릭로그 블로그에 정리했습니다.", s_end, BEIGE),
]


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def narrate(tmp):
    durs, parts = [], []
    for i, (line, _, _) in enumerate(SCENES):
        aiff = os.path.join(tmp, f"{i}.aiff")
        subprocess.run(["say", "-v", VOICE, "-r", RATE, "-o", aiff, line], check=True)
        wav = os.path.join(tmp, f"{i}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", aiff, "-af", f"apad=pad_dur={PAD}",
                        "-ar", "44100", "-ac", "2", wav], check=True)
        durs.append(duration(wav))
        parts.append(wav)
    listing = os.path.join(tmp, "list.txt")
    with open(listing, "w") as f:
        f.writelines(f"file '{p}'\n" for p in parts)
    audio = os.path.join(tmp, "voice.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", listing,
                    "-c", "copy", audio], check=True)
    return durs, audio


def caption(frame, line, ratio):
    """문장을 쉼표·마침표 기준으로 나눠 진행률에 맞게 자막을 보여준다."""
    parts, cur = [], ""
    for i, ch in enumerate(line):
        cur += ch
        ends = i + 1 == len(line) or line[i + 1] == " "  # 1.13% 같은 소수점에서 끊지 않는다
        if ch in ",.?" and ends and len(cur) > 8:
            parts.append(cur.strip())
            cur = ""
    if cur.strip():
        parts.append(cur.strip())
    total = sum(map(len, parts))
    acc = 0
    shown = parts[-1]
    for p in parts:
        acc += len(p)
        if ratio <= acc / total:
            shown = p
            break
    f = F("Bold", 46)
    lines, row = [], ""
    for word in shown.split(" "):
        test = (row + " " + word).strip()
        if f.getlength(test) > W - 220:
            lines.append(row)
            row = word
        else:
            row = test
    lines.append(row)
    d = ImageDraw.Draw(frame)
    top = 1420
    d.rounded_rectangle((70, top, W - 70, top + 40 + 66 * len(lines)), 28, fill=BROWN)
    for i, ln in enumerate(lines):
        x = (W - f.getlength(ln)) / 2
        d.text((x, top + 18 + 66 * i), ln, font=f, fill=WHITE)


def render(durs, audio):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", audio,
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                            "-c:a", "aac", "-b:a", "160k", "-shortest", OUT], stdin=subprocess.PIPE)
    total = sum(durs)
    elapsed = 0.0
    for (line, draw, bg), dur in zip(SCENES, durs):
        for n in range(int(dur * FPS)):
            t = n / FPS
            frame = Image.new("RGBA", (W, H), bg)
            draw(frame, t, dur)
            caption(frame, line, t / max(dur - PAD, 0.1))
            ImageDraw.Draw(frame).rectangle((0, 0, int(W * (elapsed + t) / total), 14), fill=ORANGE)
            enc.stdin.write(frame.convert("RGB").tobytes())
        elapsed += dur
    enc.stdin.close()
    enc.wait()
    print("saved to", OUT, f"({total:.1f}s)")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        durs, audio = narrate(tmp)
        render(durs, audio)


if __name__ == "__main__":
    main()
