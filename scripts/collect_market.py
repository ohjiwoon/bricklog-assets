"""데일리 시황 자료 수집기 (네이버 증권).

사용법:
    python3 scripts/collect_market.py 011200 035900 ...   # 종목별 KRX 정규장 종가·등락률
    python3 scripts/collect_market.py today               # 지수·수급·거래대금 확정치 저장 + 전일 대비

네이버 종목 시세의 closePrice는 넥스트레이드 애프터마켓·KRX 시간외 단일가까지 반영된 마지막 가격이라
정규장 종가와 다르다. 정규장 종가는 15:30 이후 첫 분봉(종가 단일가)에서, 전일 종가는 closePrice - 전일비로 구한다.
Yahoo Finance 일봉 종가와 맞춰 두 곳 대조로 쓴다(2026-11-12 19종목 일치).
"""
import datetime as dt
import json
import os
import sys
import urllib.request

HISTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "market", "history")

UA = {"User-Agent": "Mozilla/5.0 (Macintosh) bricklog-research"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return json.load(r)


def num(text):
    return float(str(text).replace(",", ""))


def krx_close(code, day=None):
    """(종목명, 정규장 종가, 전일 종가, 등락률%). 15:30 분봉이 없으면 종가는 None."""
    day = day or dt.date.today()
    b = get(f"https://m.stock.naver.com/api/stock/{code}/basic")
    prev = num(b["closePrice"]) - num(b["compareToPreviousClosePrice"])
    stamp = f"{day:%Y%m%d}"
    bars = get(f"https://api.stock.naver.com/chart/domestic/item/{code}/minute"
               f"?startDateTime={stamp}1520&endDateTime={stamp}1535")
    # 종가 단일가는 15:30에 체결되지만 변동성 완화장치가 걸리면 몇 분 늦게 찍힌다
    close = next((x["currentPrice"] for x in sorted(bars, key=lambda x: x["localDateTime"])
                  if x["localDateTime"] >= f"{stamp}153000"), None)
    return b["stockName"], close, prev, round((close / prev - 1) * 100, 2) if close else None


def index_today(name):
    """코스피·코스닥 확정치(장 마감 후). 수급·거래대금 단위는 억 원."""
    d = get(f"https://m.stock.naver.com/api/index/{name}/integration")
    b = get(f"https://m.stock.naver.com/api/index/{name}/basic")
    info = {x["code"]: x["value"] for x in d["totalInfos"]}
    flow = d["dealTrendInfo"]
    return {"date": flow["bizdate"], "close": b["closePrice"], "points": num(b["compareToPreviousClosePrice"]),
            "day": num(b["fluctuationsRatio"]),
            "flows": [int(num(flow[k])) for k in ("personalValue", "foreignValue", "institutionalValue")],
            "value": round(num(info["accumulatedTradingValue"].replace("백만", "")) / 100)}


def save_today():
    """오늘 값을 저장하고, 저장해 둔 직전 거래일 값과 거래대금을 비교한다.
    네이버는 지난 날 거래대금을 주지 않아 매일 쌓아 두는 수밖에 없다."""
    today = {m: index_today(m) for m in ("KOSPI", "KOSDAQ")}
    day = today["KOSPI"]["date"]
    os.makedirs(HISTORY, exist_ok=True)
    with open(os.path.join(HISTORY, f"{day}.json"), "w", encoding="utf-8") as f:
        json.dump(today, f, ensure_ascii=False, indent=1)
    older = sorted(n for n in os.listdir(HISTORY) if n < f"{day}.json")
    prev = None
    if older:
        with open(os.path.join(HISTORY, older[-1]), encoding="utf-8") as f:
            prev = json.load(f)
    return today, prev


def main(args):
    if args == ["today"]:
        today, prev = save_today()
        print(json.dumps({"today": today, "prev": prev}, ensure_ascii=False, indent=1))
        return
    for code in args:
        print(code, *krx_close(code))


if __name__ == "__main__":
    main(sys.argv[1:])
