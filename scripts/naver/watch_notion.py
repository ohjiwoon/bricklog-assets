"""노션 '최종 체크'를 1분마다 확인해 복사 페이지를 만들고 주소를 노션에 적는다. 네이버에는 접속하지 않는다.

사용법:
    python3 scripts/naver/watch_notion.py setup      # 토큰 저장, 연결 확인, 복사 페이지(1분)·대시보드(1시간) 등록
    python3 scripts/naver/watch_notion.py once       # 지금 한 번 확인
    python3 scripts/naver/watch_notion.py uninstall  # 자동 실행 해제

토큰은 ~/.bricklog/notion.env 에 권한 600으로 둔다. 저장소에는 넣지 않는다.
macOS가 백그라운드에서 Desktop 접근을 막으므로, 실행 파일은 ~/.bricklog/bin 에 복사해서 돌린다.
코드를 고치면 setup을 다시 실행한다. 원고에 없는 내용은 만들지 않는다.
"""
import getpass
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from copy_page import build
from format_post import parse

HOME = os.path.expanduser("~/.bricklog")
TOKEN_FILE = os.path.join(HOME, "notion.env")
BIN = os.path.join(HOME, "bin")
PAGES = os.path.join(HOME, "pages")
LOG = os.path.join(HOME, "copy_page.log")
LABEL = "com.bricklog.copypage"
AGENT = os.path.expanduser(f"~/Library/LaunchAgents/{LABEL}.plist")
DASH_LABEL = "com.bricklog.dashboard"
DASH_AGENT = os.path.expanduser(f"~/Library/LaunchAgents/{DASH_LABEL}.plist")
DASH_LOG = os.path.join(HOME, "dashboard.log")
DATABASE_ID = "eea41e597f6c4627b3425b693446650e"
API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
WARNING = "수치 확인 필요 상태입니다. 노션 확인 메모를 본 뒤 발행하세요."
FAIL_PREFIX = "복사 페이지 실패: "


def token():
    with open(TOKEN_FILE, encoding="utf-8") as f:
        return f.read().strip()


def call(method, path, body=None):
    req = urllib.request.Request(f"{API}{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {token()}", "Notion-Version": VERSION,
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def children(block_id):
    out, cursor = [], None
    while True:
        query = f"?page_size=100&start_cursor={cursor}" if cursor else "?page_size=100"
        data = call("GET", f"/blocks/{block_id}/children{query}")
        out += data["results"]
        if not data.get("has_more"):
            return out
        cursor = data["next_cursor"]


def rich_to_md(items, in_table=False):
    """노션 글자 조각을 format_post가 읽는 표기로 바꾼다."""
    out = []
    for item in items:
        text = item["plain_text"]
        if in_table:
            text = text.replace("|", "\\|")
        notes = item.get("annotations", {})
        if item.get("href"):
            text = f"[{text}]({item['href']})"
        if notes.get("color", "").startswith("orange"):
            text = f'<span color="orange">{text}</span>'
        if notes.get("bold"):
            text = f"<b>{text}</b>"
        out.append(text)
    return "".join(out)


def table_to_md(block):
    rows = [rich_row["table_row"]["cells"] for rich_row in children(block["id"])]
    lines = ["| " + " | ".join(rich_to_md(cell, True) for cell in row) + " |" for row in rows]
    if lines:
        lines.insert(1, "| " + " | ".join("---" for _ in rows[0]) + " |")
    return "\n".join(lines)


def block_to_md(block):
    """토글과 콜아웃은 메모라 뺀다."""
    kind = block["type"]
    data = block.get(kind, {})
    if kind == "image":
        return f"![]({data[data['type']]['url']})"
    if kind == "divider":
        return "---"
    if kind == "table":
        return table_to_md(block)
    if kind in ("heading_1", "heading_2", "heading_3"):
        if data.get("is_toggleable"):
            return ""
        return f"### {rich_to_md(data['rich_text'])}"
    if kind == "bulleted_list_item":
        return f"- {rich_to_md(data['rich_text'])}"
    if kind == "numbered_list_item":
        return f"1. {rich_to_md(data['rich_text'])}"
    if kind in ("paragraph", "quote"):
        return rich_to_md(data["rich_text"])
    return ""


def page_to_md(page_id):
    return "\n\n".join(md for md in (block_to_md(b) for b in children(page_id)) if md)


def plain(prop):
    return "".join(t["plain_text"] for t in prop.get(prop["type"], []))


def make_page(page):
    props = page["properties"]
    title = plain(props["제목"])
    status = (props["상태"].get("select") or props["상태"].get("status") or {}).get("name", "")
    md = page_to_md(page["id"])
    # 노션에 직접 올린 이미지 주소는 1시간 뒤 만료돼 네이버 글에서 깨진다. 깃허브 주소만 받는다
    expiring = [u for u in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", md) if "raw.githubusercontent.com" not in u]
    if expiring:
        raise ValueError(f"깃허브가 아닌 이미지 {len(expiring)}장: 노션 이미지를 raw.githubusercontent 주소로 바꾸세요")
    post = parse(md)
    os.makedirs(PAGES, exist_ok=True)
    # 같은 날 만든 노션 페이지는 ID 앞 8자리가 같아서, 전체 ID로 파일 이름을 짓는다
    path = os.path.join(PAGES, page["id"].replace("-", "") + ".copy.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(build(post, title, WARNING if status == "수치 확인 필요" else ""))
    return title, path


def notify(message):
    script = f'display notification {json.dumps(message, ensure_ascii=False)} with title "브릭로그"'
    subprocess.run(["osascript", "-e", script], check=False)


def handle(page):
    title, path = make_page(page)
    url = "file://" + path
    # 주소 기록과 체크 해제를 한 번에 해서 같은 글을 두 번 처리하지 않는다
    memo = plain(page["properties"]["메모"])
    fields = {"복사 페이지": {"url": url}, "최종 체크": {"checkbox": False}}
    if memo.startswith(FAIL_PREFIX):
        fields["메모"] = {"rich_text": [{"text": {"content": memo.split(" / ", 1)[-1]}}]}
    call("PATCH", f"/pages/{page['id']}", {"properties": fields})
    subprocess.run(["open", "-a", "Google Chrome", path], check=False)
    notify(f"복사 페이지 완성: {title}")
    print("done", title, url)


def fail(page, error):
    memo = plain(page["properties"]["메모"])
    print("fail", page["id"], error)
    if memo.startswith(FAIL_PREFIX):
        return  # 1분마다 같은 실패를 쌓지 않는다
    text = f"{FAIL_PREFIX}{error} / {memo}"[:1900]
    call("PATCH", f"/pages/{page['id']}", {"properties": {"메모": {"rich_text": [{"text": {"content": text}}]}}})
    notify("복사 페이지 실패. 노션 메모를 확인하세요")


def once():
    query = {"filter": {"property": "최종 체크", "checkbox": {"equals": True}}}
    for page in call("POST", f"/databases/{DATABASE_ID}/query", query)["results"]:
        try:
            handle(page)
        except (OSError, KeyError, ValueError, urllib.error.URLError) as e:
            fail(page, f"{type(e).__name__} {e}")


def install():
    os.makedirs(BIN, exist_ok=True)
    here = os.path.dirname(os.path.abspath(__file__))
    for name in ("watch_notion.py", "copy_page.py", "format_post.py", "sync_dashboard.py", "../collect_38.py", "../collect_dart.py"):
        shutil.copy(os.path.join(here, name), BIN)
    os.makedirs(os.path.dirname(AGENT), exist_ok=True)
    # 복사 페이지는 1분 간격. 대시보드는 38 부담을 줄이려 매시 5분에 돌리고,
    # 잠자기로 놓친 회차는 깨어날 때 한 번 몰아서 돈다(StartInterval은 잠자는 동안 멈춘다)
    for label, path, script, timing, log in ((LABEL, AGENT, "watch_notion.py", {"StartInterval": 60}, LOG),
                                             (DASH_LABEL, DASH_AGENT, "sync_dashboard.py",
                                              {"StartCalendarInterval": {"Minute": 5}}, DASH_LOG)):
        subprocess.run(["launchctl", "unload", path], capture_output=True)
        with open(path, "wb") as f:
            plistlib.dump({"Label": label, "ProgramArguments": [sys.executable, os.path.join(BIN, script), "once"],
                           **timing, "RunAtLoad": True, "StandardOutPath": log, "StandardErrorPath": log}, f)
        subprocess.run(["launchctl", "load", path], check=True)


def setup():
    os.makedirs(HOME, exist_ok=True)
    if not os.path.exists(TOKEN_FILE):
        value = getpass.getpass("노션 토큰을 붙여넣고 Enter (화면에 안 보입니다): ").strip()
        fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(value)
    try:
        call("POST", f"/databases/{DATABASE_ID}/query", {"page_size": 1})
    except urllib.error.HTTPError as e:
        if e.code == 401:
            os.remove(TOKEN_FILE)
            raise SystemExit("토큰이 맞지 않습니다. setup을 다시 실행하세요.")
        raise SystemExit("토큰은 저장했습니다. 브릭로그 콘텐츠 DB에 연동을 연결한 뒤 setup을 다시 실행하세요.")
    install()
    print("연결 완료. 1분마다 최종 체크를, 매시 5분에 대시보드를 확인합니다.")


def uninstall():
    for path in (AGENT, DASH_AGENT):
        subprocess.run(["launchctl", "unload", path], capture_output=True)
        if os.path.exists(path):
            os.remove(path)
    print("자동 실행을 해제했습니다.")


def main(argv):
    actions = {"setup": setup, "once": once, "uninstall": uninstall}
    if len(argv) != 1 or argv[0] not in actions:
        raise SystemExit(__doc__)
    actions[argv[0]]()


if __name__ == "__main__":
    main(sys.argv[1:])
