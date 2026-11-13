import os
import html
import random
import shutil
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

import requests
import anthropic
from playwright.sync_api import sync_playwright

NL = chr(10)
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
- 예전 연도 기준의 금액이나 조건은 쓰지 않습니다. 올해 기준을 공식 출처에서 확인하지 못하면 숫자를 빼고 어디서 확인하는지만 안내합니다.
- 지역이나 기관마다 다른 내용은 어느 지역, 어느 기관 기준인지 적습니다.
- 블로그, 카페, 홍보성 기사에서만 본 내용은 쓰지 않습니다.
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
- 핵심 문장 7~9곳은 [[ 와 ]] 로 감쌉니다(첫 문단의 핵심 답 포함). 6곳보다 적으면 안 됩니다.
- 사진 3장이 들어갈 자리를 @@IMG 줄로 표시합니다. @@IMG 1 은 맨 위(첫 문단 앞)에, @@IMG 2 와 @@IMG 3 은 그 사진이 정리할 소제목의 내용이 끝나는 자리에 둡니다.

[출력 형식]
조사를 마친 뒤 아래 형식으로만 출력합니다. 모든 줄은 @@로 시작하는 표식으로 시작하고, 표식 뒤에 한 칸 띄우고 내용을 한 줄로 씁니다. 다른 설명은 쓰지 않습니다.
@@TITLE 글 제목
@@TOPIC 사진 파일 이름에 쓸 짧은 주제 이름 (10자 안팎, 기호 없이)
@@CATEGORY 카테고리
@@P 본문 문단 (문단마다 한 줄)
@@H 소제목
@@Q 자주 묻는 질문의 질문 줄 (답은 다음 줄에 @@P로)
@@IMG 사진 번호 (1, 2, 3 을 각각 한 번씩, 사진이 들어갈 자리에)
@@SMALL 확인 기준일과 출처 기관명 한 줄
@@TAGS 태그 15개, 모든 단어 앞에 #
@@KEYWORDS 핵심 키워드, 보조 키워드 2~3개
@@REASON 이 주제를 고른 이유 한 줄
@@NOTE 주의할 점 (확인하지 못해 뺀 내용, 이 글의 정보가 낡는 날짜)
@@SOURCE 출처 주소 (출처마다 한 줄)
"""

VERIFY = """오늘은 __TODAY__ 입니다. 아래는 네이버 블로그에 올릴 글의 초안입니다. 발행 전에 사실 검수를 합니다.

[검수 방법]
- 초안의 설명을 그대로 믿지 않습니다. 웹 검색으로 공식 출처(정부·지자체·공공기관 누리집, 보도자료, 공고문, 공식 안내)를 직접 다시 확인합니다.
- 숫자, 날짜, 요일, 금액, 자격 조건, 기간, 기관명, 제도명을 하나씩 대조합니다.
- 공식 출처에서 올해 기준으로 확인된 내용만 남깁니다.
- 확인되지 않은 내용, 출처끼리 서로 다른 내용, 예전 연도 기준인 내용은 맞게 고치거나 문장째 지웁니다. 필요하면 어디서 확인하는지 안내하는 문장으로 바꿉니다. 추정으로 채우지 않습니다.
- 제목에 들어간 숫자와 날짜도 같은 기준으로 확인하고, 제목이 약속한 답이 본문에 남아 있게 합니다.
- 고친 뒤에도 글의 순서, 말투, 분량(공백 제외 1,800~2,300자), [[ ]] 표시 7~9곳, @@IMG 1·2·3 자리를 유지합니다.

[출력 형식]
검수를 마친 글 전체를 초안과 같은 @@ 형식으로 다시 출력합니다. 다른 설명은 쓰지 않습니다.
@@NOTE 에는 검수에서 고치거나 뺀 내용과 이 글의 정보가 낡는 날짜를 적습니다.
@@SOURCE 에는 검수에서 실제로 열어 확인한 공식 출처 주소만 적습니다.

[초안]
__DRAFT__
"""

STYLE_HINTS = [
    "공책 줄무늬와 손글씨 느낌", "신문 1면 머리기사", "칠판과 분필", "영수증과 계산서", "달력과 체크 표시",
    "굵은 색 블록을 겹친 포스터", "파스텔 톤 둥근 카드", "짙은 남색 바탕에 노란 강조", "크라프트지와 스탬프", "교통 표지판",
    "서류철과 인덱스 탭", "타임라인 화살표", "큰 숫자를 주인공으로", "대각선으로 나눈 2색 배경", "모눈종이와 형광펜",
    "티켓과 절취선", "말풍선 대화", "신호등 3색", "따뜻한 베이지와 벽돌색", "민트와 진회색",
]

IMG_PROMPT = """아래 블로그 글에 넣을 이미지 3장을 HTML로 만듭니다.

[3장의 역할]
1번 대표 이미지 (700x700): 제목의 핵심 키워드와 글이 주는 답이 한눈에 읽히는 큰 제목.
2번 핵심 요약 카드 (700x700): 본문의 핵심 3~4가지를 정리.
3번 비교·정리 카드 (700x820): 조건별 비교표, 순서, 체크리스트처럼 본문 내용을 정리.
글 안의 [사진 N 자리] 표시는 그 사진이 들어갈 곳입니다. 2번과 3번 사진은 그 자리 바로 위 소제목의 내용을 정리합니다.

[규칙]
- 이미지마다 완전한 HTML 문서 하나를 씁니다. 인라인 style 태그의 CSS만 쓰고 외부 파일, 스크립트, 사진, 로고는 쓰지 않습니다. 도형은 CSS로 그립니다.
- html과 body는 margin 0, 가로 정확히 700px, 세로는 위에 적힌 높이, overflow hidden 으로 합니다.
- 글꼴은 font-family: Noto Sans CJK KR, sans-serif 또는 Noto Serif CJK KR, serif 를 씁니다.
- 이모지는 쓰지 않습니다. 본문에 없는 숫자나 내용은 넣지 않습니다.
- 글자가 넘치거나 겹치거나 잘리지 않게 합니다. 문장은 짧게 줄이고, 바깥 여백을 40px 이상 두고, 큰 빈 공간이 남지 않게 채웁니다. 한 줄이 길면 글자 크기를 줄입니다.
- 3장은 배경색, 레이아웃, 모티프가 서로 달라야 합니다. 글의 주제에서 따온 모티프를 씁니다.
- 이번 디자인 방향(장마다 하나씩 참고): __STYLE__
- 모든 이미지 하단에 작은 글씨로 "알아두면 쓸모있는 생활노트"를 넣습니다.

[출력 형식]
@@IMAGE 1
(1번 HTML 문서)
@@IMAGE 2
(2번 HTML 문서)
@@IMAGE 3
(3번 HTML 문서)
다른 설명은 쓰지 않습니다.

[블로그 글]
__POST__
"""

client = anthropic.Anthropic()


def ask(prompt, search=True):
    kwargs = {}
    if search:
        kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}]
    messages = [{"role": "user", "content": prompt}]
    text = ""
    for _ in range(6):
        with client.messages.stream(
            model="claude-sonnet-5-5",
            max_tokens=32000,
            messages=messages,
            **kwargs,
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
        elif key == "IMG":
            post["blocks"].append(("img", val))
        elif key == "SOURCE":
            post["sources"].append(val)
        else:
            post[key.lower()] = val
    return post


def place_images(post):
    blocks = post["blocks"]
    nums = [t.strip()[:1] for k, t in blocks if k == "img"]
    if sorted(nums) == ["1", "2", "3"]:
        post["blocks"] = [(k, t.strip()[:1] if k == "img" else t) for k, t in blocks]
        return
    blocks = [b for b in blocks if b[0] != "img"]
    heads = [i for i, b in enumerate(blocks) if b[0] == "h"]
    out = [("img", "1")]
    for i, b in enumerate(blocks):
        if len(heads) >= 5 and i == heads[2]:
            out.append(("img", "2"))
        if len(heads) >= 5 and i == heads[4]:
            out.append(("img", "3"))
        out.append(b)
    if len(heads) < 5:
        out += [("img", "2"), ("img", "3")]
    post["blocks"] = out


def parse_images(text):
    docs = []
    cur = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("@@IMAGE"):
            cur = []
            docs.append(cur)
            continue
        if s.startswith("```"):
            continue
        if cur is not None:
            cur.append(line)
    return [NL.join(d) for d in docs if "".join(d).strip()]


def clean(name):
    return "".join(c for c in name if c.isalnum() or c == " ").strip()


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
    if post.get("title") and len(post["blocks"]) >= 8:
        print("글", i, "검수 시작", flush=True)
        try:
            checked = parse(ask(VERIFY.replace("__TODAY__", today).replace("__DRAFT__", raw)))
        except Exception as e:
            print("글", i, "검수 API 오류:", e, flush=True)
            checked = {"blocks": []}
        if checked.get("title") and len(checked["blocks"]) >= 8:
            post = checked
        else:
            post["note"] = "검수를 마치지 못한 초안입니다. 숫자와 날짜를 직접 확인하세요. " + post.get("note", "")
            print("글", i, "검수 실패: 초안을 그대로 둡니다.", flush=True)
        post["number"] = i
        post["images"] = []
        place_images(post)
        posts.append(post)
        print("글", i, "완료:", post["title"], flush=True)
    else:
        raws.append(raw)
        print("글", i, "실패: 형식에 맞는 글이 나오지 않았습니다.", flush=True)

img_dir = "posts/" + today
shutil.rmtree(img_dir, ignore_errors=True)
os.makedirs(img_dir, exist_ok=True)
jobs = []
for p in posts:
    body = p["title"] + NL + NL.join("[사진 " + t + " 자리]" if k == "img" else t for k, t in p["blocks"])
    styles = " / ".join(random.sample(STYLE_HINTS, 3))
    print("글", p["number"], "이미지 작성 시작:", styles, flush=True)
    try:
        docs = parse_images(ask(IMG_PROMPT.replace("__STYLE__", styles).replace("__POST__", body), search=False))[:3]
    except Exception as e:
        print("글", p["number"], "이미지 API 오류:", e, flush=True)
        docs = []
    topic = clean(p.get("topic") or p["title"])[:20].strip() or ("글" + str(p["number"]))
    for k, doc in enumerate(docs, start=1):
        name = topic + " " + str(k) + "번사진.png"
        jobs.append((p, name, doc, 700 if k < 3 else 820))

if jobs:
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch()
            pg = br.new_page(viewport={"width": 700, "height": 820})
            for p, name, doc, h in jobs:
                pg.set_content(doc, wait_until="load")
                pg.screenshot(path=img_dir + "/" + name, clip={"x": 0, "y": 0, "width": 700, "height": h})
                p["images"].append(name)
            br.close()
    except Exception as e:
        print("이미지 캡처 오류:", e, flush=True)
image_count = sum(len(p["images"]) for p in posts)

STYLES = {
    "h": "font-size:24px;font-weight:bold;color:#1f5ad6;margin:0",
    "p": "font-size:16px;color:#222222;line-height:1.8;margin:0",
    "q": "font-size:16px;font-weight:bold;color:#1f5ad6;margin:0",
    "small": "font-size:13px;color:#777777;margin:0",
}
MARK = "<b style='background:#fff2a8'>"


BLANK = "<p style='font-size:16px;line-height:1.8;margin:0'>&nbsp;</p>"


def render(post):
    out = []
    for kind, t in post["blocks"]:
        if kind == "img":
            out.append("<div class=slot data-n='사진 " + t + " 자리'>" + BLANK * 4 + "</div>")
            continue
        t = html.escape(t, quote=False).replace("[[", MARK).replace("]]", "</b>")
        if kind == "h":
            out.append(BLANK)
        out.append("<p style='" + STYLES[kind] + "'>" + t + "</p>")
        if kind == "p":
            out.append(BLANK)
    out.append(BLANK)
    out.append("<p style='" + STYLES["p"] + "'>" + html.escape(post.get("tags", "")) + "</p>")
    return "".join(out)


HEAD = "<meta charset='UTF-8'><meta name='viewport' content='width=device-width, initial-scale=1'><meta name='robots' content='noindex, nofollow'>"

page = """<!DOCTYPE html>
<html lang="ko"><head>__HEAD__
<title>__TODAY__ 블로그 원고</title>
<style>
body{font-family:sans-serif;max-width:820px;margin:0 auto;padding:20px;background:#f0f2f5}
.post{background:#fff;border-radius:12px;padding:24px;margin-bottom:24px}
.badge{font-size:13px;color:#1f5ad6;font-weight:bold}
.title{font-size:20px;font-weight:bold;margin:8px 0 12px}
.btn{padding:10px 18px;border:0;border-radius:8px;background:#1f5ad6;color:#fff;font-size:14px;font-weight:bold;cursor:pointer;margin:0 8px 8px 0}
.gallery{display:flex;gap:10px;margin:14px 0 6px;align-items:flex-start}
.gallery img{width:100%;border:1px solid #ddd;border-radius:6px;display:block}
.gallery a{flex:1}
.body{border:1px solid #e3e3e3;border-radius:8px;padding:20px;margin-top:16px;background:#fff}
.slot{position:relative;background:#f4f7ff;outline:1px dashed #9db4e8}
.slot:before{content:attr(data-n);position:absolute;top:10px;left:12px;font-size:13px;color:#6b84c4}
.info{font-size:13px;color:#666;margin-top:12px;white-space:pre-wrap;word-break:break-all}
</style></head><body>
<h1>__TODAY__ (__WEEKDAY__) 블로그 원고</h1>
__POSTS__
<script>
function done(id){var b=document.getElementById(id);var o=b.textContent;b.textContent="복사됨";setTimeout(function(){b.textContent=o;},1500);}
function ct(n){navigator.clipboard.writeText(document.getElementById("t"+n).textContent).then(function(){done("bt"+n);});}
function cc(n){var el=document.getElementById("c"+n);var r=document.createRange();r.selectNodeContents(el);var s=window.getSelection();s.removeAllRanges();s.addRange(r);document.execCommand("copy");s.removeAllRanges();done("bc"+n);}
function dl(n){var a=document.querySelectorAll("#g"+n+" a");for(var i=0;i<a.length;i++){(function(x,k){setTimeout(function(){x.click();},k*600);})(a[i],i);}}
</script></body></html>"""

posts_html = ""
for p in posts:
    n = str(p["number"])
    info = "키워드: " + p.get("keywords", "")
    info += NL + "고른 이유: " + p.get("reason", "")
    info += NL + "주의할 점: " + p.get("note", "")
    info += NL + "사진 위치: 본문의 빈 칸(사진 자리)에 번호 순서대로 넣기"
    info += NL + "출처: " + NL + NL.join(p["sources"])
    gallery = ""
    if p["images"]:
        gallery = "<button class=btn onclick=dl(" + n + ")>사진 3장 저장</button><div class=gallery id=g" + n + ">"
        for name in p["images"]:
            src = today + "/" + quote(name)
            gallery += "<a href='" + src + "' download='" + html.escape(name) + "'><img src='" + src + "' alt=''></a>"
        gallery += "</div>"
    posts_html += (
        "<div class=post><div class=badge>" + n + "번 · " + html.escape(p.get("category", "")) + "</div>"
        + "<div class=title id=t" + n + ">" + html.escape(p["title"], quote=False) + "</div>"
        + "<button class=btn id=bt" + n + " onclick=ct(" + n + ")>제목 복사</button>"
        + "<button class=btn id=bc" + n + " onclick=cc(" + n + ")>본문+태그 복사</button>"
        + gallery
        + "<div class=body id=c" + n + ">" + render(p) + "</div>"
        + "<div class=info>" + html.escape(info) + "</div></div>"
    )
for raw in raws:
    posts_html += "<div class=post><div class=badge>만들지 못한 글의 원문</div><div class=info>" + html.escape(raw) + "</div></div>"

page = page.replace("__HEAD__", HEAD).replace("__TODAY__", today).replace("__WEEKDAY__", weekday).replace("__POSTS__", posts_html)
path = "posts/" + today + ".html"
with open(path, "w", encoding="utf-8") as f:
    f.write(page)

files = sorted((f for f in os.listdir("posts") if f.endswith(".html")), reverse=True)
links = "".join("<li><a href='posts/" + f + "'>" + f[:-5] + " 원고</a></li>" for f in files)
index = (
    "<!DOCTYPE html><html lang='ko'><head>" + HEAD + "<title>블로그 원고</title></head>"
    + "<body style='font-family:sans-serif;max-width:600px;margin:40px auto;padding:0 20px;font-size:18px;line-height:2'>"
    + "<h1>블로그 원고</h1><ul>" + links + "</ul></body></html>"
)
with open("index.html", "w", encoding="utf-8") as f:
    f.write(index)

print("저장:", path, "/ 완성된 글:", len(posts), "편 / 사진:", image_count, "장")
if len(posts) < len(SPECS):
    raise SystemExit("일부 글이 만들어지지 않았습니다.")
if image_count < 3 * len(posts):
    raise SystemExit("일부 사진이 만들어지지 않았습니다.")
