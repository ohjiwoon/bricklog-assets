"""38커뮤니케이션 공모주 자료 수집기.

사용법:
    python3 scripts/collect_38.py --list          # 청약 예정·진행 종목과 번호
    python3 scripts/collect_38.py 2342            # 상세 → data/ipo/raw/<번호>.json

수집 원문은 저장소에 올리지 않는다(.gitignore). 글에 쓰는 값은 다른 출처와
대조한 뒤 data/ipo/<slug>.json 으로 옮긴다. 차단되면 우회하지 말고 멈춘다.
"""
import html
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data/ipo/raw")
BASE = "https://www.38.co.kr/html/fund/"
UA = "bricklog-collector/0.1 (+https://github.com/ohjiwoon/bricklog-assets)"
DELAY = 2  # 요청 간격(초)

FIN_ITEMS = ["매출액", "영업이익", "당기순이익", "현금및현금성", "자산총계", "부채총계", "자본총계"]
BASIC_LABELS = {
    "code": "종목코드", "market": "시장구분", "industry": "업종", "ceo": "대표자",
    "homepage": "홈페이지", "public_offering": "상장공모", "band": "희망공모가액",
    "offer_price": "확정공모가", "total_shares": "총공모주식수", "underwriter": "주간사",
    "demand_period": "수요예측일", "subscription": "공모청약일", "refund": "환불일",
    "listing": "상장일", "competition": "기관경쟁률", "lockup_rate": "의무보유확약",
    "current_price": "현재가",
}


def fetch(url):
    time.sleep(DELAY)
    # 38 서버가 파이썬 ssl의 TLS 설정과 맞지 않아 curl을 쓴다
    r = subprocess.run(["curl", "-sS", "-f", "-m", "30", "-A", UA, url], capture_output=True)
    if r.returncode != 0:
        raise SystemExit(f"수집 실패: {r.stderr.decode(errors='ignore').strip()}")
    return r.stdout.decode("euc-kr", "ignore")


def to_tokens(page):
    s = re.sub(r"(?is)<(script|style).*?</\1>", "", page)
    s = re.sub(r"(?i)</(tr|p|div|table|td|th)>", "\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    out = [re.sub(r"\s+", " ", t).strip() for t in s.split("\n")]
    return [t for t in out if t]


def number(t):
    t = t.replace(",", "").replace(" ", "")
    return int(t) if re.fullmatch(r"-?\d+", t) else None


def after(tokens, label, start=0):
    for i in range(start, len(tokens) - 1):
        if tokens[i] == label:
            return tokens[i + 1]
        if tokens[i].startswith(label + " "):
            return tokens[i][len(label) + 1:]
    return None


def section(tokens, head, next_head):
    i = next((k for k, t in enumerate(tokens) if t.startswith(head)), None)
    if i is None:
        return []
    j = next((k for k in range(i + 1, len(tokens)) if tokens[k].startswith(next_head)), len(tokens))
    return tokens[i:j]


def financials(tokens):
    sec = section(tokens, "5.요약재무제표", "6.동종업체")
    out = {}
    for i, t in enumerate(sec):
        label = re.sub(r"\(.*\)", "", t.replace(" ", ""))  # 영업이익(손실) 같은 표기 통일
        label = "현금및현금성" if label.startswith("현금및현금성") else label
        if label in FIN_ITEMS and label not in out:
            vals = [number(v) for v in sec[i + 1:i + 5]]
            # 칸이 빈 행은 값이 밀릴 수 있어 네 칸이 다 숫자일 때만 믿는다
            out[label] = vals if len(vals) == 4 and None not in vals else None
    unit = next((m.group(1) for t in sec if (m := re.search(r"단위\s*:\s*([^)\s]+)", t))), None)
    return {"unit": unit, "items": out}


def lockups(tokens):
    out = {}
    for i, t in enumerate(tokens):
        m = re.fullmatch(r"(6개월|3개월|1개월|15일) 확약", t)
        if m and m.group(1) not in out:
            out[m.group(1)] = number(tokens[i + 1])
        if t == "합계" and "합계" not in out and out and i + 1 < len(tokens):
            out["합계"] = number(tokens[i + 1])
    return out


def price_bids(tokens):
    i = next((k for k, t in enumerate(tokens) if t == "가격 미제시"), None)
    if i is None:
        return []
    rows = []
    while i + 3 < len(tokens) and tokens[i] != "합계":
        rows.append({"price": tokens[i], "count": tokens[i + 1], "shares": tokens[i + 2], "rate": tokens[i + 3]})
        i += 4
    return rows


def detail(no):
    tokens = to_tokens(fetch(f"{BASE}?o=v&no={no}&l=&page=1"))
    start = next((k for k, t in enumerate(tokens) if t == "종목명"), None)
    if start is None:
        raise SystemExit(f"상세 페이지 구조를 못 찾음: no={no}")
    body = tokens[start:]
    data = {"source": f"{BASE}?o=v&no={no}", "fetched_at": time.strftime("%Y-%m-%d %H:%M"),
            "name": body[1]}
    for key, label in BASIC_LABELS.items():
        data[key] = after(body, label)
    if not re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", data["listing"] or ""):
        data["listing"] = None  # 상장일 칸이 비면 다음 제목을 값으로 읽는다
    data["lockups"] = lockups(body)
    data["price_bids"] = price_bids(body)
    data["financials"] = financials(body)
    data["sections"] = {
        "business": section(body, "1.사업현황", "2.매출현황"),
        "sales": section(body, "2.매출현황", "3.재무현황"),
        "finance": section(body, "3.재무현황", "4.공모후"),
        "float": section(body, "4.공모후", "5.요약재무제표"),
        "peers": section(body, "6.동종업체", "7."),
    }
    os.makedirs(RAW, exist_ok=True)
    path = os.path.join(RAW, f"{no}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return path, data


def listing():
    page = fetch(f"{BASE}index.htm?o=k")
    seen = {}
    for no, label in re.findall(r'o=v&amp;no=(\d+)[^>]*class=slist>([^<]+)<', page):
        seen.setdefault(no, []).append(label.strip())
    for no, name in re.findall(r'o=v&amp;no=(\d+)&amp;l=&amp;page=1"><font[^>]*>([^<]+)<', page):
        seen.setdefault(no, []).insert(0, name.strip())
    return seen


def main(argv):
    if argv == ["--list"]:
        for no, labels in listing().items():
            print(no, " / ".join(labels))
    elif len(argv) == 1 and argv[0].isdigit():
        path, d = detail(argv[0])
        print("saved to", path)
        print(d["name"], d["subscription"], d["refund"], d["listing"], d["competition"], d["lockup_rate"])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
