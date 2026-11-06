"""네이버 글쓰기 에디터 매크로. 지운 PC에서 직접 실행한다.

사용법:
    .venv/bin/python scripts/naver/editor.py login     # 전용 프로필로 열고 직접 로그인
    .venv/bin/python scripts/naver/editor.py inspect   # 에디터 구조를 naver-export/inspect/ 에 저장

원칙:
- 로그인은 사람이 직접 한다. 비밀번호를 저장하거나 입력하지 않는다.
- 캡차나 보안 확인이 뜨면 우회하지 않고 멈춘다. 탐지 회피 기능은 넣지 않는다.
- 발행 버튼은 누르지 않는다.
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROFILE = os.path.expanduser("~/.bricklog/naver-profile")
INSPECT = os.path.join(ROOT, "naver-export/inspect")
BLOG_ID = "brick-log"
WRITE_URL = f"https://blog.naver.com/{BLOG_ID}?Redirect=Write"
STOP_WORDS = ("captcha", "자동입력 방지", "보안문자", "비정상적인")
LOGIN_WAIT = 300_000  # 직접 로그인을 기다리는 시간(ms)


def open_browser(p):
    os.makedirs(PROFILE, exist_ok=True)
    return p.chromium.launch_persistent_context(PROFILE, channel="chrome", headless=False,
                                                viewport={"width": 1280, "height": 900})


def needs_human(page):
    """로그인 또는 보안 확인 화면이면 멈출 이유를 돌려준다."""
    if "idSafety" in page.url:
        return "아이디 보호조치. 매크로를 쓰지 말고 평소 Chrome에서 확인하세요"
    if "nid.naver.com" in page.url:
        return "로그인 또는 보안 확인 화면"
    try:
        body = page.inner_text("body", timeout=3000)
    except Exception:
        return None
    return next((f"보안 확인 문구: {w}" for w in STOP_WORDS if w in body), None)


def wait_for_login(page):
    """로그인 화면이면 지운이 직접 로그인할 때까지 기다렸다가 글쓰기 화면으로 돌아간다."""
    if "nid.naver.com" not in page.url:
        return
    print("브라우저에서 직접 로그인하세요. '로그인 상태 유지'를 켜야 다음에 다시 안 합니다. 최대 5분 기다립니다.")
    page.wait_for_url(lambda url: "nid.naver.com" not in url or "idSafety" in url, timeout=LOGIN_WAIT)
    if "idSafety" in page.url:
        return  # 보호조치 화면에서는 글쓰기로 가지 않고 needs_human에서 멈춘다
    page.goto(WRITE_URL)
    page.wait_for_timeout(5000)


def login_kept(ctx):
    """브라우저를 닫아도 로그인이 남는지 본다. 세션 쿠키(expires -1)면 닫을 때 사라진다."""
    return any(c["name"] == "NID_AUT" and c["expires"] > 0 for c in ctx.cookies("https://naver.com"))


def login():
    with sync_playwright() as p:
        ctx = open_browser(p)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(WRITE_URL)
        print("브라우저에서 직접 로그인하세요. '로그인 상태 유지'를 켜세요. 글쓰기 화면이 보이면 여기서 Enter를 누르세요.")
        input()
        ctx.close()


def describe(frame):
    """클래스·id·placeholder가 있는 입력 요소와 버튼을 모은다."""
    return frame.evaluate("""() => {
        const pick = el => ({tag: el.tagName, id: el.id, cls: el.className && String(el.className).slice(0, 120),
            text: (el.innerText || '').trim().slice(0, 30), ph: el.getAttribute('placeholder'),
            editable: el.isContentEditable, type: el.getAttribute('type')});
        const sel = 'button, input, textarea, [contenteditable="true"], [role="button"], [class*="se-title"], [class*="se-text-paragraph"]';
        return [...document.querySelectorAll(sel)].map(pick);
    }""")


def inspect():
    os.makedirs(INSPECT, exist_ok=True)
    with sync_playwright() as p:
        ctx = open_browser(p)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(WRITE_URL)
        page.wait_for_timeout(5000)
        wait_for_login(page)
        reason = needs_human(page)
        if reason:
            print(f"멈춤: {reason}. 브라우저에서 확인 후 다시 실행하세요.")
            ctx.close()
            return 1
        print("글쓰기 화면을 확인한 뒤 Enter를 누르세요. 안내 팝업은 닫아두세요. 아무것도 입력하지 않습니다.")
        input()
        report = [{"url": f.url, "name": f.name, "elements": describe(f)} for f in page.frames]
        with open(os.path.join(INSPECT, "editor.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        page.screenshot(path=os.path.join(INSPECT, "editor.png"), full_page=False)
        print("saved to", INSPECT)
        print("로그인 유지: 켜짐" if login_kept(ctx) else "로그인 유지: 꺼짐. 닫으면 로그인이 풀립니다")
        ctx.close()
    return 0


def main(argv):
    if argv == ["login"]:
        login()
    elif argv == ["inspect"]:
        sys.exit(inspect())
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
