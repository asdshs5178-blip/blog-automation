import os
import json
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


PROMPT = """오늘은 __TODAY__ (__WEEKDAY__요일)입니다.
네이버 블로그 "알아두면 쓸모있는 생활노트"(정보·꿀팁형 생활정보 블로그)에 올릴 글 3편을 만듭니다.

[오늘의 Google Trends 대한민국 RSS]
__TRENDS__

[3편 구성]
1번 실시간 이슈 글 (카테고리: 실시간 뉴스): 위 트렌드에서 정보 글로 풀 수 있는 가장 높은 순위의 주제. 연예인, 스포츠 경기, 정치 공방, 사건·사고, 특정 개인 이야기는 건너뜁니다. 뉴스 내용을 옮기지 말고 그 뉴스를 본 사람이 다음에 검색할 말(대상 조회, 신청 방법, 기간 등)을 씁니다. 마땅한 이슈가 없으면 꾸준히 검색되는 정보 주제로 대신합니다.
2번 __POST2__ 글 (카테고리: __POST2__): 모르는 사람이 많지만 알면 도움이 되는 내용.
3번 조회수 기대 글: 지금 시기와 검색 수요를 따져 조회수가 가장 잘 나올 주제. 날짜가 정해진 주제는 1~2주 전에 다룹니다.
3편의 주제는 서로 겹치지 않게 합니다.

[사실 확인 - 가장 중요]
- 웹 검색으로 공식 출처(기관 공지, 보도자료, 공식 안내)를 확인한 숫자, 날짜, 금액, 자격 조건만 씁니다.
- 확인하지 못한 값은 쓰지 않습니다. 추정으로 채우지 않습니다. 확정되지 않은 내용은 확정 전이라고 적습니다.
- 하지 않은 경험을 한 것처럼 쓰지 않습니다. "무조건", "100%", "누구나" 같은 단정 표현을 쓰지 않습니다.
- 특정 상품·업체 홍보, 특정 개인 비방, 정치적 주장, 건강 효능이나 투자 수익 단정은 쓰지 않습니다.
- 다른 글이나 기사의 문장을 복사하지 않고 직접 쓴 문장으로 정리합니다.

[글 작성 규칙]
- 순서: 도입(공감할 상황 한두 문장) → 첫 문단 안에서 핵심 답 → 소제목 5~7개 → 자주 묻는 질문 3~4개 → 마무리 요약 4~5줄 → 확인 기준일과 출처 기관명 한 줄.
- 제목: 핵심 키워드를 맨 앞에, 40자 안팎. 3번은 궁금증이나 자주 하는 실수를 살리되 본문에 답이 반드시 있어야 합니다.
- 분량: 본문은 공백 제외 1,800~2,300자.
- 말투: AI가 쓴 티가 나지 않는 자연스러운 블로그 말투. 문단은 2~4문장. "오늘", "어제" 대신 날짜를 씁니다.
- 그림 이모지는 쓰지 않습니다. 소제목 앞에는 ✔ 나 ▶ 같은 단순 기호를 쓰고, 본문에는 ㅎㅎ ㅠㅠ ^^ 를 가끔, 규칙적이지 않게 씁니다.
- 마크다운 기호(#, **, - 목록)는 쓰지 않습니다. 대괄호 빈칸 없이 바로 올릴 수 있는 완성본으로 씁니다.
- 핵심 문장 6~10곳은 [[ 와 ]] 로 감쌉니다(첫 문단의 핵심 답 포함).
- 태그는 15개, 모든 단어 앞에 #.

[출력 형식]
조사를 마친 뒤 마지막에 아래 JSON 하나만 출력합니다. JSON 앞뒤에 다른 글을 쓰지 않습니다.
{"posts": [{"number": 1, "category": "카테고리", "title": "제목", "blocks": [{"type": "p", "text": "문단"}], "tags": "#태그1 #태그2", "keywords": ["핵심", "보조"], "reason": "고른 이유 한 줄", "sources": ["출처 주소"], "note": "주의할 점"}]}
blocks의 type은 h(소제목), p(본문 문단), q(자주 묻는 질문의 질문 줄), small(확인 기준일·출처 줄) 중 하나입니다.
"""

prompt = (
    PROMPT.replace("__TODAY__", today)
    .replace("__WEEKDAY__", weekday)
    .replace("__POST2__", post2)
    .replace("__TRENDS__", get_trends())
)

client = anthropic.Anthropic()
print("Claude API 호출:", today, weekday)
messages = [{"role": "user", "content": prompt}]
text = ""
for _ in range(6):
    with client.messages.stream(
        model="claude-sonnet-5-5",
        max_tokens=32000,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}],
        messages=messages,
    ) as stream:
        msg = stream.get_final_message()
    print("stop_reason:", msg.stop_reason, [b.type for b in msg.content], flush=True)
    text += "".join(b.text for b in msg.content if b.type == "text")
    if msg.stop_reason != "pause_turn":
        break
    messages.append({"role": "assistant", "content": msg.content})

start = text.rfind("{" + chr(34) + "posts" + chr(34))
if start < 0:
    start = text.find("{")
try:
    data = json.loads(text[start: text.rfind("}") + 1])
except Exception as e:
    print("JSON 해석 실패:", e)
    data = {"posts": []}

STYLES = {
    "h": "font-size:24px;font-weight:bold;color:#1f5ad6;margin:28px 0 10px",
    "p": "font-size:16px;color:#222222;line-height:1.8;margin:0 0 16px",
    "q": "font-size:16px;font-weight:bold;color:#1f5ad6;margin:18px 0 6px",
    "small": "font-size:13px;color:#777777;margin:20px 0 0",
}
MARK = "<b style=\"background:#fff2a8\">"


def render(post):
    out = []
    for b in post.get("blocks", []):
        t = html.escape(str(b.get("text", "")))
        t = t.replace("[[", MARK).replace("]]", "</b>")
        style = STYLES.get(b.get("type"), STYLES["p"])
        out.append("<p style=\"" + style + "\">" + t + "</p>")
    out.append("<p style=\"" + STYLES["p"] + "\">" + html.escape(post.get("tags", "")) + "</p>")
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
.info{font-size:13px;color:#666;margin-top:12px;white-space:pre-wrap}
</style></head><body>
<h1>__TODAY__ (__WEEKDAY__) 블로그 원고</h1>
__POSTS__
<script>
function done(id){var b=document.getElementById(id);var o=b.textContent;b.textContent="복사됨";setTimeout(function(){b.textContent=o;},1500);}
function ct(n){navigator.clipboard.writeText(document.getElementById("t"+n).textContent).then(function(){done("bt"+n);});}
function cc(n){var el=document.getElementById("c"+n);var r=document.createRange();r.selectNodeContents(el);var s=window.getSelection();s.removeAllRanges();s.addRange(r);document.execCommand("copy");s.removeAllRanges();done("bc"+n);}
</script></body></html>"""

posts_html = ""
for p in data.get("posts", []):
    n = str(p.get("number", ""))
    info = "키워드: " + ", ".join(p.get("keywords", []))
    info += chr(10) + "고른 이유: " + str(p.get("reason", ""))
    info += chr(10) + "주의할 점: " + str(p.get("note", ""))
    info += chr(10) + "출처: " + " , ".join(p.get("sources", []))
    posts_html += (
        "<div class=post><div class=badge>" + n + "번 · " + html.escape(str(p.get("category", ""))) + "</div>"
        + "<div class=title id=t" + n + ">" + html.escape(str(p.get("title", ""))) + "</div>"
        + "<button class=btn id=bt" + n + " onclick=ct(" + n + ")>제목 복사</button>"
        + "<button class=btn id=bc" + n + " onclick=cc(" + n + ")>본문+태그 복사</button>"
        + "<div class=body id=c" + n + ">" + render(p) + "</div>"
        + "<div class=info>" + html.escape(info) + "</div></div>"
    )

if not data.get("posts"):
    posts_html = "<div class=post><div class=info>" + html.escape(text) + "</div></div>"

page = page.replace("__TODAY__", today).replace("__WEEKDAY__", weekday).replace("__POSTS__", posts_html)
os.makedirs("posts", exist_ok=True)
path = "posts/" + today + ".html"
with open(path, "w", encoding="utf-8") as f:
    f.write(page)

print("저장:", path)
for p in data.get("posts", []):
    print(p.get("number"), p.get("title"))
if not data.get("posts"):
    raise SystemExit("글이 만들어지지 않았습니다. 저장된 원문을 확인하세요.")
