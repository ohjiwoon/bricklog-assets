"""노션 원고를 네이버에 붙여넣을 복사 페이지로 만든다. 네이버에는 접속하지 않는다.

사용법:
    python3 scripts/naver/copy_page.py posts/<slug>.md "최종 제목" ["경고 문구"]  # → posts/<slug>.copy.html
    open posts/<slug>.copy.html

제목, 본문 전체(이미지 포함), 태그를 버튼 세 개로 복사해 평소 Chrome의 글쓰기 화면에 붙여넣는다.
전체 복사에서 이미지가 빠지면 '따로 복사' 칸에서 이미지만 복사한다.
"""
import base64
import html
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from format_post import parse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

STYLE = """
:root{--o:#FF7A45;--b:#3B230F;--bg:#FFF6E8;--line:#EADBC4;--ok:#22A566;--muted:#8A7560}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--b);font:15px/1.6 -apple-system,'Apple SD Gothic Neo',sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:24px 16px 80px}
h1{font-size:20px;margin:0 0 4px}
.help{color:var(--muted);margin:0 0 20px}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px;margin:0 0 12px}
.card.done{border-color:var(--ok);opacity:.65}
.row{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:8px}
.label{font-weight:700;font-size:13px;color:var(--muted)}
button{border:0;border-radius:8px;background:var(--o);color:#fff;font:700 14px sans-serif;padding:8px 14px;cursor:pointer;white-space:nowrap}
.done button{background:var(--ok)}
.all{width:100%;padding:12px;background:var(--b);margin-bottom:16px}
img{max-width:100%;max-height:260px;display:block;border-radius:8px}
.body{overflow:auto}
.plain{font-weight:600;word-break:break-all}
.main{border:2px solid var(--o)}
.warn{background:#FDE8E8;border:2px solid #E5484D;border-radius:12px;padding:12px 14px;margin:0 0 16px;font-weight:700}
.main .body{max-height:360px}
details{margin-top:24px}
summary{cursor:pointer;font-weight:700;margin-bottom:12px}
"""

SCRIPT = """
function mark(btn){btn.closest('.card')?.classList.add('done');const t=btn.textContent;btn.textContent='복사됨 ✓';setTimeout(()=>btn.textContent=t,1500)}
function legacy(setup){const h=e=>{setup(e);e.preventDefault()};document.addEventListener('copy',h,{once:true});const ok=document.execCommand('copy');document.removeEventListener('copy',h);return ok}
function fail(btn){btn.textContent='복사 실패: 직접 선택';}
async function copyHtml(btn,el){const body=el.innerHTML,text=el.innerText;
  try{await navigator.clipboard.write([new ClipboardItem({'text/html':new Blob([body],{type:'text/html'}),'text/plain':new Blob([text],{type:'text/plain'})})]);mark(btn)}
  catch(_){legacy(e=>{e.clipboardData.setData('text/html',body);e.clipboardData.setData('text/plain',text)})?mark(btn):fail(btn)}}
async function copyText(btn,text){
  try{await navigator.clipboard.writeText(text);mark(btn)}
  catch(_){legacy(e=>e.clipboardData.setData('text/plain',text))?mark(btn):fail(btn)}}
async function copyImage(btn,img){
  try{const bin=atob(img.src.split(',')[1]);const bytes=Uint8Array.from(bin,c=>c.charCodeAt(0));
    await navigator.clipboard.write([new ClipboardItem({'image/png':new Blob([bytes],{type:'image/png'})})]);mark(btn)}
  catch(_){fail(btn)}}
document.addEventListener('click',e=>{const btn=e.target.closest('button');if(!btn)return;
  const card=btn.closest('.card');
  if(btn.dataset.kind==='html')copyHtml(btn,card.querySelector('.body'));
  if(btn.dataset.kind==='all')copyHtml(btn,card.querySelector('.body'));
  if(btn.dataset.kind==='text')copyText(btn,card.querySelector('.plain').innerText);
  if(btn.dataset.kind==='image')copyImage(btn,card.querySelector('img'));
});
"""


def local_image(url):
    """저장소에 있는 이미지 주소를 로컬 파일로 바꿔 읽는다. 없으면 받는다."""
    match = re.search(r"/((?:ipo|market)/.+\.png)$", url)
    path = os.path.join(ROOT, match.group(1)) if match else ""
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:  # 파일이 없거나 백그라운드에서 Desktop 접근이 막힌 경우
        pass
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read()


def text_card(label, value):
    return (f'<div class="card"><div class="row"><span class="label">{label}</span>'
            f'<button data-kind="text">복사</button></div><div class="plain">{html.escape(value)}</div></div>')


def block_card(i, block):
    if block["type"] == "image":
        data = base64.b64encode(local_image(block["url"])).decode()
        return (f'<div class="card"><div class="row"><span class="label">{i}. 이미지</span>'
                f'<button data-kind="image">이미지 복사</button></div>'
                f'<img src="data:image/png;base64,{data}" alt=""></div>')
    return (f'<div class="card"><div class="row"><span class="label">{i}. 본문</span>'
            f'<button data-kind="html">본문 복사</button></div><div class="body">{block["html"]}</div></div>')


def full_body(blocks):
    """이미지를 공개 주소로 넣은 본문 전체."""
    return "".join(f'<p><img src="{b["url"]}" alt=""></p>' if b["type"] == "image" else b["html"] for b in blocks)


def build(post, title, warning=""):
    tags = " ".join(f"#{t}" for t in post["tags"])
    main_card = ('<div class="card main"><div class="row"><span class="label">본문 전체 (이미지 포함)</span>'
                 f'<button data-kind="all">본문 전체 복사</button></div><div class="body">{full_body(post["blocks"])}</div></div>')
    pieces = "".join(block_card(i, b) for i, b in enumerate(post["blocks"], 1))
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>복사 페이지</title><style>{STYLE}</style></head><body><div class="wrap">'
            f'<h1>{html.escape(title)}</h1>'
            f'<p class="help">버튼 세 개면 됩니다. 카테고리, 임시저장, 발행은 직접 합니다.</p>'
            + (f'<div class="warn">{html.escape(warning)}</div>' if warning else "")
            + text_card("1. 제목", title) + main_card.replace("본문 전체 (이미지 포함)", "2. 본문 전체 (이미지 포함)")
            + text_card("3. 태그", tags)
            + f'<details><summary>이미지가 빠지면: 따로 복사</summary>{pieces}</details>'
            + f'</div><script>{SCRIPT}</script></body></html>')


def main(path, title, warning=""):
    with open(path, encoding="utf-8") as f:
        post = parse(f.read())
    out = os.path.splitext(path)[0] + ".copy.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(build(post, title, warning))
    print("saved to", out, f"(blocks {len(post['blocks'])}, tags {len(post['tags'])})")


if __name__ == "__main__":
    main(*sys.argv[1:4])
