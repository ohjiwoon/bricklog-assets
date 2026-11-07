"""공모 일정을 노션 '공모주 캘린더'에 맞추고, 대시보드 숫자 칸을 고쳐 쓴다.

사용법:
    python3 scripts/naver/sync_dashboard.py once   # 지금 한 번 갱신

자료 순서: DART 증권신고서(원본)를 먼저 쓰고, DART에 없는 칸(상장일·시장·업종, 못 읽은 확약)만 38로 채운다.
종목 목록은 38에서 받는다. 38이 막히면 캘린더에 있던 종목만 DART로 갱신하고 나머지 칸은 그대로 둔다.
자동 실행은 watch_notion.py setup 이 매시 5분에 등록한다. 토큰은 watch_notion과 같은 파일을 쓴다.
38 요청은 정직한 UA로 2초 간격, 진행 중인 종목만 상세를 읽는다. 차단되면 우회하지 않고 멈춘다.
"""
import datetime as dt
import fcntl
import json
import os
import re
import subprocess
import sys
import urllib.error
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collect_38
import collect_dart
from watch_notion import HOME, call, plain

collect_38.RAW = os.path.join(HOME, "raw")  # 백그라운드에서는 Desktop에 쓰지 않는다
DASH_PAGE = "410488d6e9fa8119acb0caa033939e68"
CAL_DB = "d818233493d348879a2699af04f5f386"
CONTENT_DB = "eea41e597f6c4627b3425b693446650e"
EVENTS_DB = "314a15996e8148bfb51eba6a7a9516c9"
KST = dt.timezone(dt.timedelta(hours=9))
MARKETS = {"코스닥": "코스닥", "유가증권": "코스피", "코스피": "코스피", "코넥스": "코넥스"}
DONE = "발행 완료"
PLANNED = ("초안", "수치 확인 필요", "발행 준비")


def today():
    return dt.datetime.now(KST).date()


def dates(text):
    return [dt.date(int(y), int(m), int(d)) for y, m, d in re.findall(r"(\d{4})\.(\d{2})\.(\d{2})", text or "")]


def number(text):
    match = re.search(r"[\d,]+(?:\.\d+)?", text or "")
    return float(match.group(0).replace(",", "")) if match else None


def stage(ipo, day):
    sub, demand, listing = ipo["subscription"], ipo["demand"], ipo["listing"]
    if listing and listing[0] <= day:
        return "상장 완료"
    if sub and sub[-1] < day:
        return "청약 끝"
    if sub and sub[0] <= day:
        return "청약 중"
    if ipo["competition"] is not None:
        return "결과 나옴"
    if demand and demand[0] <= day:
        return "수요예측 중"
    return "수요예측 전"


def from_38(raw):
    """collect_38.detail 결과를 대시보드 값으로 바꾼다. 결과 전에는 경쟁률·확약을 비운다."""
    competition = re.fullmatch(r"\s*([\d,.]+)\s*:\s*1\s*", raw.get("competition") or "")
    competition = float(competition.group(1).replace(",", "")) if competition else None
    return {"name": raw["name"], "subscription": dates(raw["subscription"]), "demand": dates(raw["demand_period"]),
            "refund": dates(raw["refund"]), "listing": dates(raw["listing"]), "underwriter": raw["underwriter"] or "",
            "band": (raw["band"] or "").replace(" 원", "원").strip(), "offer": number(raw["offer_price"]),
            "competition": competition,
            "lockup": number(raw["lockup_rate"]) if competition is not None else None,
            "market": MARKETS.get(raw["market"] or ""), "industry": raw["industry"] or ""}


def from_row(row):
    """38을 못 읽을 때 캘린더에 이미 있는 값을 바탕으로 쓴다."""
    p = row["properties"]

    def days(key):
        d = p[key]["date"] or {}
        return [dt.date.fromisoformat(v[:10]) for v in (d.get("start"), d.get("end")) if v]

    return {"name": plain(p["종목"]), "subscription": days("청약일"), "demand": days("수요예측"),
            "refund": days("환불일"), "listing": days("상장일"), "underwriter": plain(p["증권사"]),
            "band": plain(p["희망 공모가"]), "offer": p["확정 공모가"]["number"],
            "competition": p["기관 경쟁률"]["number"], "lockup": p["확약(%)"]["number"],
            "market": (p["시장"]["select"] or {}).get("name"), "industry": plain(p["업종"])}


DART_KEYS = ("subscription", "refund", "demand", "underwriter", "band", "offer", "competition", "lockup")


def from_dart(name):
    try:
        return collect_dart.detail(name)
    except (SystemExit, OSError, ValueError, KeyError, zipfile.BadZipFile) as e:
        print("DART 실패:", name, e)
        return None


def merge(ipo, dart):
    """DART가 원본이라 먼저 쓰고, DART가 비운 칸만 38 값을 둔다. 둘이 다르면 로그에 남긴다."""
    if not dart:
        return ipo
    out = dict(ipo)
    for key in DART_KEYS:
        value = dart.get(key)
        if value in (None, "", []):
            continue
        if key != "underwriter" and ipo.get(key) not in (None, "", []) and ipo[key] != value:
            print("DART≠38", ipo["name"], key, ipo[key], "→", value)
        out[key] = value
    return out


def date_prop(values):
    if not values:
        return {"date": None}
    end = values[-1].isoformat() if len(values) > 1 and values[-1] != values[0] else None
    return {"date": {"start": values[0].isoformat(), "end": end}}


def text_prop(value):
    return {"rich_text": [{"text": {"content": value[:1900]}}] if value else []}


def properties(no, ipo, day):
    props = {"종목": {"title": [{"text": {"content": ipo["name"]}}]}, "38 번호": {"number": int(no)},
             "단계": {"select": {"name": stage(ipo, day)}}, "청약일": date_prop(ipo["subscription"]),
             "수요예측": date_prop(ipo["demand"]), "환불일": date_prop(ipo["refund"]),
             "상장일": date_prop(ipo["listing"]), "증권사": text_prop(ipo["underwriter"]),
             "희망 공모가": text_prop(ipo["band"]), "확정 공모가": {"number": ipo["offer"]},
             "기관 경쟁률": {"number": ipo["competition"]}, "확약(%)": {"number": ipo["lockup"]},
             "업종": text_prop(ipo["industry"]), "갱신": {"date": {"start": dt.datetime.now(KST).isoformat()}}}
    if ipo["market"]:
        props["시장"] = {"select": {"name": ipo["market"]}}
    return props


def query_all(db, body=None):
    out, cursor = [], None
    while True:
        payload = dict(body or {}, page_size=100, **({"start_cursor": cursor} if cursor else {}))
        data = call("POST", f"/databases/{db}/query", payload)
        out += data["results"]
        if not data.get("has_more"):
            return out
        cursor = data["next_cursor"]


def unique(rows, pairs):
    """같은 키가 두 줄이면 첫 줄만 남기고 나머지는 보관함으로 보낸다."""
    for key, row in pairs:
        if key in rows:
            call("PATCH", f"/pages/{row['id']}", {"archived": True})
        else:
            rows[key] = row
    return rows


def my_posts(name, posts):
    """콘텐츠 DB에서 제목에 종목명이 들어간 글을 찾는다."""
    return [{"id": p["id"]} for p in posts if name in plain(p["properties"]["제목"])]


def sync_calendar(day, posts):
    rows = unique({},
                  [(int(r["properties"]["38 번호"]["number"]), r) for r in query_all(CAL_DB)
                   if r["properties"]["38 번호"]["number"] is not None])
    try:
        targets = [int(no) for no, labels in collect_38.listing().items() if "스팩" not in labels[0]]
        blocked = False
    except SystemExit as e:  # 38이 막히면 있던 종목만 DART로 갱신한다
        print("38 목록 실패:", e)
        targets, blocked = [], True
    # 목록에서 빠졌어도 상장 전이거나 상장 1주일 이내인 종목은 계속 갱신한다
    for no, row in rows.items():
        listing = (row["properties"]["상장일"]["date"] or {}).get("start")
        recent = listing is None or dt.date.fromisoformat(listing) >= day - dt.timedelta(days=7)
        if no not in targets and recent and row["properties"]["단계"]["select"]["name"] != "상장 완료":
            targets.append(no)
    ipos = []
    for no in targets:
        ipo = None
        if not blocked:
            try:
                ipo = from_38(collect_38.detail(str(no))[1])
            except SystemExit as e:  # 한 번 막히면 남은 종목은 38에 다시 묻지 않는다
                print("38 상세 실패:", no, e)
                blocked = True
        if ipo is None:
            if no not in rows:
                continue
            ipo = from_row(rows[no])
        ipo = merge(ipo, from_dart(ipo["name"]))
        props = properties(no, ipo, day)
        linked = my_posts(ipo["name"], posts)
        if linked:
            props["내 글"] = {"relation": linked}
        if no in rows:
            call("PATCH", f"/pages/{rows[no]['id']}", {"properties": props})
        else:
            call("POST", "/pages", {"parent": {"database_id": CAL_DB}, "properties": props})
        ipos.append(dict(ipo, no=no, stage=stage(ipo, day), linked=bool(linked)))
    return ipos


def events(ipos, posts):
    """통합 달력에 넣을 일정. 색은 '종류' 선택값과 제목 앞 네모로 구분한다."""
    out = {}
    for i in ipos:
        if i["subscription"]:
            out[f"청약:{i['no']}"] = ("청약", f"🟥 청약 {i['name']}", i["subscription"], i["name"])
        if i["demand"]:
            # 38은 결과 발표일을 따로 주지 않아 수요예측 마지막 날에 표시한다
            label = f"🟨 결과 {i['name']} {i['competition']:,.0f}:1" if i["competition"] is not None else f"🟨 결과 발표 예정 {i['name']}"
            out[f"결과:{i['no']}"] = ("수요예측 결과", label, i["demand"][-1:], i["name"])
        if i["listing"]:
            out[f"상장:{i['no']}"] = ("상장", f"🟩 상장 {i['name']}", i["listing"][:1], i["name"])
    for p in posts:
        start = (p["properties"]["발행일"]["date"] or {}).get("start")
        status = (p["properties"]["상태"]["status"] or {}).get("name")
        if not start:
            continue
        title = plain(p["properties"]["제목"])
        kind, mark = ("발행 완료", "⬜ 발행") if status == DONE else ("발행 예정", "🟪 발행 예정")
        out[f"발행:{p['id']}"] = (kind, f"{mark} {title}", [dt.date.fromisoformat(start[:10])], "")
    return out


def sync_events(ipos, posts):
    current = unique({}, [(plain(r["properties"]["키"]), r) for r in query_all(EVENTS_DB)])
    wanted = events(ipos, posts)
    for key, (kind, title, days, name) in wanted.items():
        props = {"일정": {"title": [{"text": {"content": title[:1900]}}]}, "날짜": date_prop(days),
                 "종류": {"select": {"name": kind}}, "종목": text_prop(name), "키": text_prop(key)}
        if key in current:
            call("PATCH", f"/pages/{current[key]['id']}", {"properties": props})
        else:
            call("POST", "/pages", {"parent": {"database_id": EVENTS_DB}, "properties": props})
    # 발행일이 지워진 글만 정리한다. 갱신 대상에서 빠진 지난 공모주 일정은 기록으로 남긴다
    for key, row in current.items():
        if key.startswith("발행:") and key not in wanted:
            call("PATCH", f"/pages/{row['id']}", {"archived": True})


def index_moves():
    """코스피·코스닥 5·20거래일 등락. 실패하면 빈 문자열."""
    out = []
    for sym, label in (("^KS11", "코스피"), ("^KQ11", "코스닥")):
        r = subprocess.run(["curl", "-sS", "-m", "20", "-A", collect_38.UA,
                            f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=3mo&interval=1d"],
                           capture_output=True, text=True)
        try:
            chart = json.loads(r.stdout)["chart"]["result"][0]
            now = dt.datetime.now(KST)
            # 장중 값은 빼고 끝난 날의 종가만 쓴다 (15시 40분 이후면 오늘 종가 포함)
            closes = [c for t, c in zip(chart["timestamp"], chart["indicators"]["quote"][0]["close"])
                      if c and (dt.datetime.fromtimestamp(t, KST).date() < now.date() or now.hour * 60 + now.minute >= 940)]
            out.append(f"{label} 5일 {closes[-1] / closes[-6] * 100 - 100:+.1f}% · 20일 {closes[-1] / closes[-21] * 100 - 100:+.1f}%")
        except (ValueError, KeyError, IndexError, TypeError):
            return ""
    return " / ".join(out) + " (종가 기준, 참고용)"


def dday(items, key, day, label):
    upcoming = sorted((d, i["name"]) for i in items for d in i[key][-1:] if d >= day)
    if not upcoming:
        return None
    d, name = upcoming[0]
    return f"{label} {name} D-{(d - day).days}" if d > day else f"{label} {name} 오늘"


def brick_record(posts):
    """상장 결과가 쌓이면 수요·확약 등급별 첫날 평균 수익률을 보여준다."""
    done = []
    for p in posts:
        result = (p["properties"].get("첫날 수익률(%)", {}).get("formula") or {}).get("number")
        if result is not None:
            done.append((p["properties"], result))
    if len(done) < 3:
        return f"🧱 BRICK CHECK 기록 {len(done)}건 (3건부터 등급별 첫날 수익률 표시)"
    parts = []
    for key in ("수요", "확약"):
        for grade in "ABC":
            values = [r for props, r in done if (props[key]["select"] or {}).get("name") == grade]
            if values:
                parts.append(f"{key} {grade} {sum(values) / len(values):+.0f}% ({len(values)})")
    return "🧱 BRICK CHECK 첫날 평균: " + " · ".join(parts)


def summary(ipos, posts, day):
    status = [(p, (p["properties"]["상태"]["status"] or {}).get("name")) for p in posts]
    published = [p for p, s in status if s == DONE]
    month = [p for p in published if ((p["properties"]["발행일"]["date"] or {}).get("start") or "")[:7] == day.isoformat()[:7]]
    planned = [p for p, s in status if s in PLANNED]
    monday = day - dt.timedelta(days=day.weekday())
    week = [i for i in ipos if i["subscription"] and i["subscription"][0] <= monday + dt.timedelta(6)
            and i["subscription"][-1] >= monday]
    todo = [f"{i['name']} 글 쓰기" for i in ipos if i["stage"] == "결과 나옴" and not i["linked"]]
    todo += [f"{plain(p['properties']['제목'])} 발행" for p, s in status
             if s in PLANNED and (p["properties"]["발행일"]["date"] or {}).get("start") == day.isoformat()]
    ddays = [x for x in (dday(ipos, "subscription", day, "마감"), dday(ipos, "refund", day, "환불"),
                         dday(ipos, "listing", day, "상장")) if x]
    lines = [f"📊 발행 {len(published)}편 (이번 달 {len(month)}) · 발행 예정 {len(planned)}편 · 이번 주 청약 {len(week)}곳",
             "✍️ 오늘 할 일: " + (", ".join(todo) if todo else "없음"),
             "⏰ " + (" · ".join(ddays) if ddays else "다가오는 일정 없음")]
    market = index_moves()
    if market:
        lines.append("🌧️ " + market)
    lines.append(brick_record(posts))
    lines.append(f"갱신 {dt.datetime.now(KST):%m/%d %H:%M}")
    return "\n".join(lines)


def write_summary(text):
    from watch_notion import children
    for block in children(DASH_PAGE):
        if block["type"] == "callout" and "".join(t["plain_text"] for t in block["callout"]["rich_text"]).startswith("📊"):
            call("PATCH", f"/blocks/{block['id']}", {"callout": {"rich_text": [{"text": {"content": text}}]}})
            return
    raise KeyError("대시보드 숫자 칸(📊 콜아웃)을 찾지 못함")


def once():
    # 자동 실행과 수동 실행이 겹치면 같은 일정이 두 번 생기므로 한 번에 하나만 돈다
    lock = open(os.path.join(HOME, "dashboard.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("이미 갱신 중")
        return
    day = today()
    posts = query_all(CONTENT_DB)
    try:
        ipos = sync_calendar(day, posts)
    except SystemExit as e:  # 일정 수집 실패는 숫자 칸 갱신을 막지 않는다
        print("일정 수집 실패:", e)
        ipos = []
    sync_events(ipos, posts)
    write_summary(summary(ipos, posts, day))
    print("dashboard", dt.datetime.now(KST).isoformat(timespec="minutes"), len(ipos))


if __name__ == "__main__":
    if sys.argv[1:] != ["once"]:
        raise SystemExit(__doc__)
    try:
        once()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"노션 오류 {e.code}: 대시보드 페이지에 연동이 연결됐는지 확인하세요")
