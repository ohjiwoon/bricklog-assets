"""노션 원고(Notion-flavored Markdown)를 네이버 입력용 블록으로 바꾼다.

사용법:
    python3 scripts/naver/format_post.py posts/<slug>.md  # → posts/<slug>.naver.json

토글(제목 안, 발행 메모)과 콜아웃(복사 페이지 안내)은 빼고, 해시태그는 본문이 아니라 tags로 분리한다.
블록은 html / image 두 종류이고, 매크로가 차례대로 붙여넣고 이미지를 올린다.
"""
import html
import json
import os
import re
import sys

ORANGE = "#ff7a45"
HEAD_BG = "#f5f5f5"
LINE = "#d3d3d3"
MAX_LEN = 80  # 한 문단 글자 수. 넘으면 문장 단위로 나눈다
BLANK = "<p><br></p>"


def inline(text):
    """굵게와 오렌지 강조만 남긴다. 나머지 태그는 글자로 처리한다."""
    text = text.replace("\\~", "~").replace("\\[", "[").replace("\\]", "]").replace("\\_", "_").replace("\\|", "|")
    text = html.escape(text, quote=False)
    text = re.sub(r"&lt;b&gt;(.*?)&lt;/b&gt;", r"<b>\1</b>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"&lt;i&gt;(.*?)&lt;/i&gt;", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', text)
    return re.sub(r'&lt;span color="orange"&gt;(.*?)&lt;/span&gt;',
                  rf'<span style="color:{ORANGE}">\1</span>', text)


def split_sentences(text):
    """긴 문단을 문장 단위로 묶어 MAX_LEN 안쪽 문단들로 나눈다. 소수점에서는 끊지 않는다."""
    if len(text) <= MAX_LEN:
        return [text]
    parts = re.split(r"(?<=[.?!])\s+", text)
    out, cur = [], ""
    for part in parts:
        if cur and len(cur) + len(part) + 1 > MAX_LEN:
            out.append(cur)
            cur = part
        else:
            cur = f"{cur} {part}".strip()
    if cur:
        out.append(cur)
    return out


def orange_marker(line):
    """🟧로 시작하는 줄은 표시를 떼고 문장 전체를 오렌지로."""
    if not line.startswith("🟧"):
        return line
    body = line[len("🟧"):].strip()
    return f'<span color="orange">{body}</span>'


def table_html(rows):
    cells = []
    for r, row in enumerate(rows):
        tds = []
        for col in row:
            # 지운이 고른 표: 회색 머리글 가운데 정렬, 본문 왼쪽 정렬, 굵게는 머리글만
            body = re.sub(r"</?b>", "", inline(col))
            if r == 0:
                style = f"background-color:{HEAD_BG};text-align:center;"
                body = f"<b>{body}</b>"
            else:
                style = "text-align:left;"
            tds.append(f'<td style="border:1px solid {LINE};padding:10px;{style}">{body}</td>')
        cells.append("<tr>" + "".join(tds) + "</tr>")
    return '<table style="border-collapse:collapse;width:100%">' + "".join(cells) + "</table>"


def parse(markdown):
    markdown = re.sub(r"<(toggle|callout).*?</\1>", "", markdown, flags=re.S)
    markdown = re.sub(r"^\s*(-{3,}\s*)+|(\s*-{3,})+\s*$", "", markdown)  # 메모를 뺀 자리에 남는 앞뒤 구분선
    title, tags, blocks, buf = None, [], [], []

    def flush():
        if buf:
            blocks.append({"type": "html", "html": "".join(buf)})
            buf.clear()

    lines = markdown.splitlines()
    i = 0
    num, prev_list, list_kind = 0, None, None
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            continue
        line = re.sub(r"^>\s*", "", line)  # 인용(결론 줄)은 일반 문단으로
        image = re.fullmatch(r"!\[[^\]]*\]\((\S+)\)", line)
        if image:
            flush()
            blocks.append({"type": "image", "url": image.group(1)})
        elif re.fullmatch(r"-{3,}", line):
            if buf or blocks:  # 글 맨 앞의 구분선은 뺀다
                buf.append("<hr>")
        elif line.startswith("#") and re.match(r"#{1,4}\s", line):
            buf.append(f'<p><span style="font-size:19px"><b>{inline(line.lstrip("# "))}</b></span></p>')
        elif re.fullmatch(r"(#\S+\s*)+", line):
            tags = [t[1:] for t in line.split()]
        elif re.match(r"태그\s*(\([^)]*\))?\s*[:：]", line):
            body = re.split(r"[:：]", line, 1)[1]
            tags = [t.strip().lstrip("#") for t in re.split(r"[,\s]+", body) if t.strip().lstrip("#")]
        elif line.startswith("|"):
            rows = [line]
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            parsed = [[c.strip() for c in re.split(r"(?<!\\)\|", r.strip("|"))] for r in rows]
            parsed = [r for r in parsed if not all(re.fullmatch(r":?-{3,}:?", c) for c in r)]
            buf.append(table_html(parsed))
        elif re.match(r"\d+\.\s", line):
            num = num + 1 if prev_list == "ol" else 1  # 노션 API는 번호를 다 1로 준다
            item = re.sub(r"^\d+\.\s+", "", line)
            buf.append(f"<p>{num}. {inline(item)}</p>")
            list_kind = "ol"
        elif line.startswith("- "):
            buf.append(f"<p>· {inline(line[2:])}</p>")
            list_kind = "ul"
        else:
            orange = line.startswith("🟧")
            if orange:  # 표시를 떼고, 나눈 조각마다 오렌지·굵게를 따로 씌운다
                line = re.sub(r"</?b>|\*\*", "", line[len("🟧"):].strip())
            parts = split_sentences(line)
            if orange:
                parts = [f'<span color="orange"><b>{part}</b></span>' for part in parts]
            # 한 문단을 문장으로 나눈 조각은 빈 줄 없이 이어 붙이고, 문단 끝에만 빈 줄 하나
            buf.append("".join(f"<p>{inline(part)}</p>" for part in parts) + BLANK)
        heading = '<p><span style="font-size'
        if prev_list and not list_kind and buf and not buf[-1].startswith(heading):
            # 목록이 끝난 직후 문단 앞에 빈 줄
            last = buf.pop(); buf.append(BLANK); buf.append(last)
        prev_list, list_kind = list_kind, None
    while buf and buf[-1] == "<hr>":  # 글 맨 끝의 구분선도 뺀다
        buf.pop()
    flush()
    return {"title": title, "tags": tags, "blocks": blocks}


def main(path):
    with open(path, encoding="utf-8") as f:
        post = parse(f.read())
    out = os.path.splitext(path)[0] + ".naver.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(post, f, ensure_ascii=False, indent=1)
    print("saved to", out, f"(blocks {len(post['blocks'])}, tags {len(post['tags'])})")


if __name__ == "__main__":
    main(sys.argv[1])
