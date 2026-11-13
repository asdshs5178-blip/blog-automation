import os
import html
from datetime import datetime, timezone, timedelta

import requests
import anthropic

KST = timezone(timedelta(hours=9))
now = datetime.now(KST)
today = now.strftime("%Y-%m-%d")
weekday = ["월", "화", "수", "목", "금", "토", "일"][now.weekday()]
post2 = "생활 꿀팁" if now.weekday() in (0, 2, 4) else "생활상식"


def get_trends():
    try:
        r = requests.get(
            "https://trends.google.com/trending/rss?geo=KR",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        return r.text[:6000]
    except Exception as e:
        return "트렌드 수집 실패: " + str(e)


SPECS = [
    "실시간 이슈 글 (카테고리: 실시간 뉴스). 아래 트렌드에서 정보 글로 풀 수 있는 가장 높은 순위의 주제를 고릅니다. 연예인, 스포츠 경기, 정치 공방, 사건·사고, 특정 개인 이야기는 건너뜁니다. 뉴스 내용을 옮기지 말고 그 뉴스를 본 사람이 다음에 검색할 말(대상 조회, 신청 방법, 기간 등)을 씁니다. 마땅한 이슈가 없으면 꾸준히 검색되는 정보 주제로 대신합니다.",
    post2 + " 글 (카테고리: " + post2 + "). 모르는 사람이 많지만 알면 도움이 되는 내용을 고릅니다.",
    "조회수 기대 글 (카테고리: 생활정보). 지금 시기와 검색 수요를 따져 조회수가 가장 잘 나올 주제를 고릅니다. 날짜가 정해진 주제는 1~2주 전에 다룹니다.",
]

PROMPT = """오늘은 __TODAY__ (__WEEKDAY__요일)입니다.
네이버 블로그 "알아두면 쓸모있는 생활노트"(정보·꿀팁형 생활정보 블로그)에 올릴 글 1편을 만듭니다.

[이번에 쓸 글]
__SPEC__

[오늘 이미 쓴 글 - 주제가 겹치지 않게 합니다]
__DONE__

[오늘의 Google Trends 대한민국 RSS]
__TRENDS__

[사실 확인 - 가장 중요]
- 웹 검색으로 공식 출처(기관 공지, 보도자료, 공식 안내)를 확인한 숫자, 날짜, 금액, 자격 조건만 씁니다.
- 확인하지 못한 값은 쓰지 않습니다. 추정으로 채우지 않습니다. 확정되지 않은 내용은 확정 전이라고 적습니다.
- 하지 않은 경험을 한 것처럼 쓰지 않습니다. "무조건", "100%", "누구나" 같은 단정 표현을 쓰지 않습니다.
- 특정 상품·업체 홍보, 특정 개인 비방, 정치적 주장, 건강 효능이나 투자 수익 단정은 쓰지 않습니다.
- 다른 글이나 기사의 문장을 복사하지 않고 직접 쓴 문장으로 정리합니다.

[글 작성 규칙]
- 순서: 도입(공감할 상황 한두 문장) → 첫 문단 안에서 핵심 답 → 소제목 5~7개 → 자주 묻는 질문 3~4개 → 마무리 요약 4~5줄 → 확인 기준일과 출처 기관명 한 줄.
- 제목: 핵심 키워드를 맨 앞에, 40자 안팎. 제목이 약속한 답은 본문에 반드시 있어야 합니다.
- 분량: 본문은 공백 제외 1,800~2,300자.
- 말투: AI가 쓴 티가 나지 않는 자연스러운 블로그 말투. 문단은 2~4문장. "오늘", "어제" 대신 날짜를 씁니다.
- 그림 이모지는 쓰지 않습니다. 소제목 앞에는 ✔ 나 ▶ 같은 단순 기호를 쓰고, 본문에는 ㅎㅎ ㅠㅠ ^^ 를 가끔, 규칙적이지 않게 씁니다.
- 마크다운 기호는 쓰지 않습니다. 대괄호 빈칸 없이 바로 올릴 수 있는 완성본으로 씁니다.
- 핵심 문장 6~10곳은 [[ 와 ]] 로 감쌉니다(첫 문단의 핵심 답 포함).

[출력 형식]
조사를 마친 뒤 아래 형식으로만 출력합니다. 모든 줄은 @@로 시작하는 표식으로 시작하고, 표식 뒤에 한 칸 띄우고 내용을 한 줄로 씁니다. 다른 설명은 쓰지 않습니다.
@@TITLE 글 제목
@@CATEGORY 카테고리
@@P 본문 문단 (문단마다 한 줄)
@@H 소제목
@@Q 자주 묻는 질문의 질문 줄 (답은 다음 줄에 @@P로)
@@SMALL 확인 기준일과 출처 기관명 한 줄
@@TAGS 태그 15개, 모든 단어 앞에 #
@@KEYWORDS 핵심 키워드, 보조 키워드 2~3개
@@REASON 이 주제를 고른 이유 한 줄
@@NOTE 주의할 점 (확인하지 못해 뺀 내용, 이 글의 정보가 낡는 날짜)
@@SOURCE 출처 주소 (출처마다 한 줄)
"""

client = anthropic.Anthropic()


def ask(prompt):
    messages = [{"role": "user", "content": prompt}]
    text = ""
    for _ in range(6):
        with client.messages.stream(
            model="claude-sonnet-5-5",
            max_tokens=32000,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}],
            messages=messages,
        ) as stream:
            msg = stream.get_final_message()
        print("stop_reason:", msg.stop_reason, flush=True)
        text += "".join(b.text for b in msg.content if b.type == "text")
        if msg.stop_reason != "pause_turn":
            break
        messages.append({"role": "assistant", "content": msg.content})
    return text


def parse(text):
    post = {"blocks": [], "sources": []}
    in_block = False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if not line.startswith("@@"):
            if in_block:
                kind, old = post["blocks"][-1]
                post["blocks"][-1] = (kind, old + " " + line)
            continue
        key, _, val = line[2:].partition(" ")
        key = key.strip().upper()
        val = val.strip()
        in_block = key in ("P", "H", "Q", "SMALL")
        if in_block:
            post["blocks"].append((key.lower(), val))
        elif key == "SOURCE":
            post["sources"].append(val)
        else:
            post[key.lower()] = val
    return post


trends = get_trends()
posts = []
raws = []
for i, spec in enumerate(SPECS, start=1):
    done = ", ".join(p.get("title", "") for p in posts) or "없음"
    prompt = (
        PROMPT.replace("__TODAY__", today)
        .replace("__WEEKDAY__", weekday)
        .replace("__SPEC__", spec)
        .replace("__DONE__", done)
        .replace("__TRENDS__", trends)
    )
    print("글", i, "작성 시작", flush=True)
    try:
        raw = ask(prompt)
    except Exception as e:
        print("글", i, "API 오류:", e, flush=True)
        raw = ""
    post = parse(raw)
    post["number"] = i
    if post.get("title") and len(post["blocks"]) >= 8:
        posts.append(post)
        print("글", i, "완료:", post["title"], flush=True)
    else:
        raws.append(raw)
        print("글", i, "실패: 형식에 맞는 글이 나오지 않았습니다.", flush=True)

STYLES = {
    "h": "font-size:24px;font-weight:bold;color:#1f5ad6;margin:28px 0 10px",
    "p": "font-size:16px;color:#222222;line-height:1.8;margin:0 0 16px",
    "q": "font-size:16px;font-weight:bold;color:#1f5ad6;margin:18px 0 6px",
    "small": "font-size:13px;color:#777777;margin:20px 0 0",
}
MARK = "<b style='background:#fff2a8'>"


def render(post):
    out = []
    for kind, t in post["blocks"]:
        t = html.escape(t, quote=False).replace("[[", MARK).replace("]]", "</b>")
        out.append("<p style='" + STYLES[kind] + "'>" + t + "</p>")
    out.append("<p style='" + STYLES["p"] + "'>" + html.escape(post.get("tags", "")) + "</p>")
    return "".join(out)


page = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TODAY__ 블로그 원고</title>
<style>
body{font-family:sans-serif;max-width:820px;margin:0 auto;padding:20px;background:#f0f2f5}
.post{background:#fff;border-radius:12px;padding:24px;margin-bottom:24px}
.badge{font-size:13px;color:#1f5ad6;font-weight:bold}
.title{font-size:20px;font-weight:bold;margin:8px 0 12px}
.btn{padding:10px 18px;border:0;border-radius:8px;background:#1f5ad6;color:#fff;font-size:14px;font-weight:bold;cursor:pointer;margin-right:8px}
.body{border:1px solid #e3e3e3;border-radius:8px;padding:20px;margin-top:16px;background:#fff}
.info{font-size:13px;color:#666;margin-top:12px;white-space:pre-wrap;word-break:break-all}
</style></head><body>
<h1>__TODAY__ (__WEEKDAY__) 블로그 원고</h1>
__POSTS__
<script>
function done(id){var b=document.getElementById(id);var o=b.textContent;b.textContent="복사됨";setTimeout(function(){b.textContent=o;},1500);}
function ct(n){navigator.clipboard.writeText(document.getElementById("t"+n).textContent).then(function(){done("bt"+n);});}
function cc(n){var el=document.getElementById("c"+n);var r=document.createRange();r.selectNodeContents(el);var s=window.getSelection();s.removeAllRanges();s.addRange(r);document.execCommand("copy");s.removeAllRanges();done("bc"+n);}
</script></body></html>"""

NL = chr(10)
posts_html = ""
for p in posts:
    n = str(p["number"])
    info = "키워드: " + p.get("keywords", "")
    info += NL + "고른 이유: " + p.get("reason", "")
    info += NL + "주의할 점: " + p.get("note", "")
    info += NL + "출처: " + NL + NL.join(p["sources"])
    posts_html += (
        "<div class=post><div class=badge>" + n + "번 · " + html.escape(p.get("category", "")) + "</div>"
        + "<div class=title id=t" + n + ">" + html.escape(p["title"], quote=False) + "</div>"
        + "<button class=btn id=bt" + n + " onclick=ct(" + n + ")>제목 복사</button>"
        + "<button class=btn id=bc" + n + " onclick=cc(" + n + ")>본문+태그 복사</button>"
        + "<div class=body id=c" + n + ">" + render(p) + "</div>"
        + "<div class=info>" + html.escape(info) + "</div></div>"
    )
for raw in raws:
    posts_html += "<div class=post><div class=badge>만들지 못한 글의 원문</div><div class=info>" + html.escape(raw) + "</div></div>"

page = page.replace("__TODAY__", today).replace("__WEEKDAY__", weekday).replace("__POSTS__", posts_html)
os.makedirs("posts", exist_ok=True)
path = "posts/" + today + ".html"
with open(path, "w", encoding="utf-8") as f:
    f.write(page)

print("저장:", path, "/ 완성된 글:", len(posts), "편")
if len(posts) < len(SPECS):
    raise SystemExit("일부 글이 만들어지지 않았습니다.")
