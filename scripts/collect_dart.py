"""OpenDART 공모주 자료 수집기. 증권신고서가 원본이라 38보다 먼저 쓴다.

사용법:
    python3 scripts/collect_dart.py 옵토닉스      # 종목명으로 찾아 일정·공모가·수요예측 결과 출력

키는 ~/.bricklog/dart.env (권한 600) 또는 환경 변수 DART_API_KEY. 저장소에는 넣지 않는다.
- 청약일·납입일·주관사·공모 주식 수: 지분증권 주요정보 API(estkRs)
- 희망 공모가·확정 공모가·수요예측 기간·기관 경쟁률·확약 비율: 가장 최근 증권신고서 원문
상장일·시장·업종은 신고서에 확정값이 없어 38에서 채운다. 원문은 접수번호별로 한 번만 받는다.
"""
import datetime as dt
import html
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile

API = "https://opendart.fss.or.kr/api"
HOME = os.path.expanduser("~/.bricklog")
KEY_FILE = os.path.join(HOME, "dart.env")
CACHE = os.path.join(HOME, "raw", "dart")
DELAY = 0.5  # 요청 간격(초)
LOOKBACK = 89  # 공시 목록은 회사 지정 없이 3개월까지만 조회된다
LOCKUPS = ("6개월 확약", "3개월 확약", "1개월 확약", "15일 확약")
_filings = None


def key():
    value = os.environ.get("DART_API_KEY")
    if not value:
        with open(KEY_FILE, encoding="utf-8") as f:
            value = f.read().strip()
    return value


def fetch(path, **params):
    time.sleep(DELAY)
    url = f"{API}/{path}?" + urllib.parse.urlencode(dict(params, crtfc_key=key()))
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def call(path, **params):
    data = json.loads(fetch(path, **params))
    if data["status"] == "013":  # 조회된 데이터 없음
        return {}
    if data["status"] != "000":
        raise SystemExit(f"DART 오류 {data['status']}: {data['message']}")
    return data


def filings():
    """최근 증권신고서(지분증권) 계열 공시. 한 번 실행에 한 번만 받는다."""
    global _filings
    if _filings is None:
        end = dt.date.today()
        params = {"bgn_de": f"{end - dt.timedelta(LOOKBACK):%Y%m%d}", "end_de": f"{end:%Y%m%d}",
                  "pblntf_detail_ty": "C001", "page_count": 100}
        _filings, page = [], 1
        while True:
            data = call("list.json", page_no=page, **params)
            _filings += data.get("list", [])
            if page >= int(data.get("total_page", 1)):
                break
            page += 1
    return _filings


def norm(name):
    return re.sub(r"\s|\(주\)|㈜|주식회사", "", name or "")


def find(name):
    """38 종목명과 같은 회사의 신고서 목록(최근 순). 스팩·이름이 다른 회사는 뺀다."""
    target = norm(name)
    rows = [f for f in filings() if "기업인수목적" not in f["corp_name"]
            and (norm(f["corp_name"]) == target or norm(f["corp_name"]).startswith(target)
                 or target.startswith(norm(f["corp_name"])))]
    if not rows:
        return []
    exact = [f for f in rows if norm(f["corp_name"]) == target]
    rows = exact or rows
    corp = max(rows, key=lambda f: f["rcept_no"])["corp_code"]
    return sorted((f for f in rows if f["corp_code"] == corp), key=lambda f: f["rcept_no"], reverse=True)


def text(rcept_no):
    """신고서 원문을 글자만 남겨 한 줄로. 접수번호별로 저장해 두고 다시 받지 않는다."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{rcept_no}.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    try:
        with zipfile.ZipFile(io.BytesIO(fetch("document.xml", rcept_no=rcept_no))) as z:
            raw = "".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist())
    except zipfile.BadZipFile:  # 첨부정정처럼 본문 파일이 없는 공시는 빈 글로 저장해 다시 묻지 않는다
        raw = ""
    out = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))
    with open(path, "w", encoding="utf-8") as f:
        f.write(out)
    return out


def won(value):
    return int(value.replace(",", ""))


def korean_dates(value):
    return [dt.date(int(y), int(m), int(d)) for y, m, d in re.findall(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", value or "")]


def demand_result(body):
    """발행조건확정 신고서의 수요예측 결과. 확정 전이면 전부 None."""
    out = {"offer": None, "demand": [], "competition": None, "lockup": None}
    m = re.search(r"확정공모가액을\s*([\d,]+)원으로\s*(?:최종\s*)?결정", body)
    if not m:
        return out
    out["offer"] = won(m.group(1))
    # 신고서마다 문장이 달라 두 가지만 읽고, 못 읽으면 38 값을 쓴다
    m = (re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일부터\s*(?:(\d{4})년\s*)?(\d{1,2})월\s*(\d{1,2})일까지\s*실시한\s*수요예측", body)
         or re.search(r"수요예측\s*(?:예정)?일은\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일(?:\(.\))?\s*~\s*(?:(\d{4})년\s*)?(\d{1,2})월\s*(\d{1,2})일", body))
    if m:
        y, m1, d1, y2, m2, d2 = m.groups()
        out["demand"] = [dt.date(int(y), int(m1), int(d1)), dt.date(int(y2 or y), int(m2), int(d2))]
    # (가) 참여내역 표의 '경쟁률' 행: 마지막 칸이 합계
    m = re.search(r"경쟁률(?:\s*\(주\d\))?((?:\s+(?:[\d,]+\.\d+|[\d,]+|-)(?=\s|$))+)", body)
    if m:
        values = [v for v in m.group(1).split() if v != "-"]
        out["competition"] = float(values[-1].replace(",", "")) if values else None
    # (다) 확약기간별 참여내역: 표가 국내·외국 둘로 나뉘고, 뒤쪽 표의 마지막 세 칸(건수·수량·가격)이 전체 합계.
    # 주관사마다 표 모양이 달라 두 표 모두 행 이름이 있을 때만 읽고, 아니면 38 값을 쓴다
    m = re.search(r"의무보유\s*확약기간별", body)
    if m:
        sec = body[m.start():body.find("주1)", m.start())]
        seen = {}
        # 숫자 뒤에 '개월'·'일'이 붙은 건 다음 행 이름이라 칸으로 읽지 않는다
        for label, cells in re.findall(r"(6개월 확약|3개월 확약|1개월 확약|15일 확약|미확약|(?<!\S)(?:합 ?)?계)((?:\s+(?:[\d,]+|-)(?=\s|$))+)", sec):
            label = "합계" if label.endswith("계") else label
            seen.setdefault(label, []).append(cells.split())
        names = LOCKUPS + ("미확약", "합계")
        if all(len(seen.get(k, [])) == 2 and len(seen[k][1]) >= 3 for k in names):
            qty = {k: 0 if seen[k][1][-2] == "-" else won(seen[k][1][-2]) for k in names}
            if qty["합계"] and sum(qty[k] for k in LOCKUPS) + qty["미확약"] == qty["합계"]:  # 합이 맞을 때만 믿는다
                out["lockup"] = round(sum(qty[k] for k in LOCKUPS) / qty["합계"] * 100, 2)
    return out


def detail(name):
    """대시보드 칸 이름에 맞춘 값. 찾지 못한 칸은 None 또는 빈 목록."""
    rows = find(name)
    if not rows:
        return None
    corp = rows[0]["corp_code"]
    info = call("estkRs.json", corp_code=corp, bgn_de=f"{dt.date.today() - dt.timedelta(LOOKBACK):%Y%m%d}",
                end_de=f"{dt.date.today():%Y%m%d}")
    groups = {g["title"]: g["list"] for g in info.get("group", [])}
    general = (groups.get("일반사항") or [{}])[-1]
    leads = [r["actnmn"] for r in groups.get("인수인정보", []) if r.get("actsen") == "대표"]
    kind = (groups.get("증권의종류") or [{}])[-1]
    shares, low = kind.get("stkcnt"), kind.get("slprc")
    out = {"source": f"DART {rows[0]['corp_name']}", "corp_code": corp, "name": rows[0]["corp_name"],
           "subscription": korean_dates(general.get("sbd")), "refund": korean_dates(general.get("pymd")),
           "underwriter": ", ".join(dict.fromkeys(leads)), "shares": won(shares) if shares and shares != "-" else None,
           "band": "", "offer": None, "demand": [], "competition": None, "lockup": None, "rcept_no": None,
           "withdrawn": any("철회" in r["report_nm"] for r in rows)}
    # 정정 신고서에는 정정 전 밴드도 같이 적혀 있어, 주요정보 API의 모집가액(밴드 하단)과 맞는 것만 쓴다.
    # 투자설명서·발행실적보고서는 건너뛰고 본문이 있는 가장 최근 증권신고서를 읽는다
    for r in (r for r in rows if "증권신고서" in r["report_nm"]):
        body = text(r["rcept_no"])
        if not body:
            continue
        bands = re.findall(r"희망공모가액[^~]{0,40}?([\d,]+)원\s*~\s*([\d,]+)원", body)
        match = [b for b in bands if low and b[0] == low] or (bands[:1] if len(set(bands)) == 1 else [])
        if match:
            out["band"] = f"{match[0][0]} ~ {match[0][1]}원"  # 38 표기와 같게
        out["rcept_no"] = r["rcept_no"]
        break
    confirmed = next((r for r in rows if "발행조건확정" in r["report_nm"]), None)
    if confirmed:
        out.update(demand_result(text(confirmed["rcept_no"])))
        out["rcept_no"] = confirmed["rcept_no"]
    return out


def main(argv):
    if len(argv) != 1:
        raise SystemExit(__doc__)
    d = detail(argv[0])
    if d is None:
        raise SystemExit(f"DART에서 {argv[0]} 증권신고서를 못 찾음")
    print(json.dumps(d, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main(sys.argv[1:])
