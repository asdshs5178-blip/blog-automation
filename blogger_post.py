import os
import json
import html
import base64
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser

import requests
import anthropic

NL = chr(10)
KST = timezone(timedelta(hours=9))
now = datetime.now(KST)
today = now.strftime("%Y-%m-%d")
BLOG_ID = "6291295349653158917"
BLOG_URL = "https://everydaykoreanote.blogspot.com"
HIST = "blogger_history.txt"
UA = {"User-Agent": "EverydayKoreaNotesBot/1.0 (personal blog automation)"}

PROMPT = """오늘은 __TODAY__ (한국 시간)입니다. 블로그스팟 블로그 "Everyday Korea Notes"(https://everydaykoreanote.blogspot.com/)에 올릴 영어 글 1편을 씁니다.

[블로그]
- 독자: 한국에 오는 외국인 여행자가 중심이고, 한국에 사는 외국인도 포함합니다. 글은 전부 영어입니다.
- 운영자는 한국에 사는 한국인입니다. 외국인인 척하거나 겪지 않은 일을 겪은 것처럼 쓰지 않습니다. 가 보지 않은 식당이나 장소의 추천·후기를 쓰지 않습니다.
- 목적은 구글 검색 유입입니다. 몇 달 동안 계속 검색되는 주제를 고르고 당일 뉴스는 다루지 않습니다. 계절 주제는 해당 시기 4~8주 전에 다룹니다.

[주제군과 비율 - 여러 주에 걸쳐 맞추고, 같은 주제군이 3일 연속 나오지 않게 합니다]
A 여행자 실용 안내 약 50%: 교통, 결제, 통신, 공항, 예매, 앱, 환전, 짐 보관, 병원·약국, 긴급 전화, 쇼핑과 세금 환급, 숙소 유형(찜질방·한옥·게스트하우스 이용 방법), 계절별 준비물과 날씨, 공휴일·명절 휴무, 미세먼지·태풍·지진 알림 대처.
B 한국 문화·예절·음식 안내 약 30%: 식사 예절, 술자리 예절(음주를 권하지 않고 거절하는 법도 함께), 호칭과 존댓말, 신발 벗는 곳, 대중교통 예절, 사찰·궁 방문 예절, 찜질방 이용법, 한국 음식 설명, 메뉴판 읽기, 채식·할랄·알레르기 대응, 편의점 음식, 배달 앱, 명절과 기념일, 기본 한국어 표현, 쓰레기 분리배출.
C 지역별 여행 계획 약 15%: 가는 방법, 소요 시간, 요금, 운영 시간처럼 공식 출처로 확인되는 정보 중심. 식당 이름을 지어내지 않습니다.
E 거주자 주제 약 5%: 비자, 외국인등록, 세금, 건강보험, 은행.
B 글은 "모든 한국인은"처럼 일반화하지 않고, 세대·지역·상황에 따라 다르다고 적습니다. 다른 나라와 우열을 비교하지 않고, 역사·정치·종교 논쟁은 다루지 않습니다.

[지금까지의 주제군 기록]
__GROUPS__

[이미 발행된 글 - 같은 주제를 다시 쓰지 않습니다. 내부 링크는 이 목록의 주소만 씁니다]
__POSTS__

[사실 확인 - 가장 중요]
- 웹 검색으로 공식 출처(한국관광공사, Visit Seoul, 하이코리아, 국세청, 관세청, 코레일, 서울교통공사, 인천국제공항, 티머니, 환경부, 국가유산청, 기상청 등 운영 기관의 공식 안내)를 확인합니다. 영문 페이지가 낡았을 수 있으니 한국어 원문 공지도 확인합니다.
- 숫자, 날짜, 요금, 자격 조건은 공식 출처에서 확인한 것만 씁니다. 확인하지 못한 값은 쓰지 않습니다. 다른 블로그와 기사는 단서로만 씁니다.
- 출처끼리 엇갈리면 더 최근의 공식 발표를 따르고, 풀리지 않으면 그 내용은 뺍니다. 예정인 것은 예정이라고 씁니다. 계산한 값은 직접 계산한 것이라고 밝힙니다.
- 의료·법률·세무·이민 결과를 단정하지 않습니다. 특정 업체나 금융 상품을 권하지 않습니다. 제휴 링크와 광고 언급을 넣지 않습니다.
- "guaranteed", "always", "everyone qualifies" 같은 단정을 쓰지 않습니다. 다른 글의 문장을 복사하지 않습니다.

[글 작성 규칙]
- 영어 900~1,500단어. 1,500단어를 넘기지 않습니다. 사람이 쓴 담백한 영어. 1인칭은 사실일 때만. 이모지와 과한 느낌표를 쓰지 않습니다.
- 쓰지 않는 표현: "In today's fast-paced world", "Whether you're... or...", "Let's dive in", "game-changer", "seamless", "navigate the complexities".
- 구조: 첫 문단에 핵심 답 → h2 소제목 5~8개(필요하면 h3) → 비교는 표, 절차는 번호 목록 → 상황별 추천이나 흔한 실수 → 마지막 문단에 확인 기준일과 출처 기관명.
- 첫 문단은 굵은 말(Short answer:, In short:, The quick version: 등)로 시작합니다. 즉 본문은 <p><b> 로 시작합니다.
- 마지막 문단은 전체를 i 태그 하나로 감쌉니다: <p><i>Last checked: __TODAY__. Sources: 기관명들. Fares and rules change, so please confirm on the official pages before you travel.</i></p> (문화 글이면 마지막 문장을 "Customs vary by place and generation, so treat this as a starting point."로)
- 본문 HTML 태그는 p, h2, h3, ul, ol, li, b, i, a, table, tbody, tr, th, td 만 씁니다. 속성은 a 의 href 만 씁니다.
- 내부 링크는 관련 글이 있을 때만 1~3곳. 외부 링크는 공식 안내 페이지만 몇 곳.
- 사진 자리 2~3곳: 관련 소제목의 첫 문단 뒤에 한 줄로 [[PHOTO: 위키미디어 공용에서 찾을 구체적인 영어 검색어 | 사진 아래에 넣을 영어 설명 한 문장]] 을 씁니다.

[출력 형식 - 이 형식만 출력합니다]
@@TITLE 전체 제목 (핵심 키워드가 앞에, 답이 드러나게, 60~80자)
@@SLUG 주소용 짧은 제목 (영어 소문자 단어 3~5개, 예: korea tax refund guide)
@@LABELS 라벨 1~3개를 쉼표로 (Transport, Travel Basics, Culture & Etiquette, Money, Connectivity, Itineraries, Food & Places, Living in Korea 중에서)
@@DESC 검색 설명 영어 120~150자
@@GROUP 주제군 글자 하나 (A, B, C, E)
@@SUMMARY_KO 무엇을 안내했는지와 핵심 숫자를 담은 한국어 요약 한 문장
@@NOTE_KO 주의할 점 한국어 한 문장 (확인하지 못해 뺀 내용, 출처가 엇갈린 부분, 이 글의 정보가 낡는 날짜. 없으면 특이사항 없음)
@@BODY
(본문 HTML)
@@END
"""

VERIFY = """오늘은 __TODAY__ 입니다. 아래는 영어 블로그 글의 초안입니다. 발행 전에 사실 검수를 합니다.
- 초안을 그대로 믿지 않고, 웹 검색으로 운영 기관의 공식 안내를 직접 다시 확인합니다. 한국어 원문 공지도 확인합니다.
- 숫자, 날짜, 요금, 시간, 자격 조건, 기관명, 서비스 이름을 하나씩 대조합니다. 공식 출처에서 현재 기준으로 확인된 내용만 남깁니다.
- 확인되지 않은 내용, 출처끼리 다른 내용, 낡은 내용은 맞게 고치거나 문장째 지웁니다. 추정으로 채우지 않습니다.
- 글의 구조, 말투, 분량(900~1,500단어), <p><b> 로 시작하는 첫 문단, <p><i>...</i></p> 인 마지막 문단, [[PHOTO: ...]] 줄을 유지합니다.
- 검수를 마친 글 전체를 초안과 같은 @@ 형식으로 다시 출력합니다. 다른 설명은 쓰지 않습니다. @@NOTE_KO 에는 검수에서 고치거나 뺀 내용을 한국어 한 문장으로 적습니다.

[초안]
__DRAFT__
"""

client = anthropic.Anthropic()
MODELS = ["claude-fable-5-1", "claude-sonnet-5-5"]


def ask(prompt):
    last = None
    for model in MODELS:
        try:
            messages = [{"role": "user", "content": prompt}]
            text = ""
            for _ in range(6):
                with client.messages.stream(
                    model=model,
                    max_tokens=32000,
                    tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}],
                    messages=messages,
                ) as stream:
                    msg = stream.get_final_message()
                print("model:", model, "stop_reason:", msg.stop_reason, flush=True)
                text += "".join(b.text for b in msg.content if b.type == "text")
                if msg.stop_reason != "pause_turn":
                    break
                messages.append({"role": "assistant", "content": msg.content})
            return text
        except Exception as e:
            last = e
            print("model", model, "오류:", e, flush=True)
    raise last


def parse(text):
    post = {}
    body = []
    in_body = False
    for line in text.splitlines():
        s = line.strip()
        if s == "@@BODY":
            in_body = True
            continue
        if s == "@@END":
            in_body = False
            continue
        if in_body:
            if not s.startswith("```"):
                body.append(line)
            continue
        if s.startswith("@@"):
            key, _, val = s[2:].partition(" ")
            post[key.strip().lower()] = val.strip()
    post["body"] = NL.join(body).strip()
    return post


def ok(post):
    return bool(post.get("title") and post.get("slug") and len(post.get("body", "")) > 2000)


ALLOWED = {"p", "h2", "h3", "ul", "ol", "li", "b", "i", "a", "table", "tbody", "tr", "th", "td"}
RENAME = {"strong": "b", "em": "i"}
CELL = {
    "table": "border-collapse:collapse;width:100%;margin:12px 0;",
    "th": "border:1px solid #cfcfcf;padding:8px;background:#f3f6fa;text-align:left;",
    "td": "border:1px solid #cfcfcf;padding:8px;vertical-align:top;",
}


class Clean(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.words = []

    def handle_starttag(self, tag, attrs):
        tag = RENAME.get(tag, tag)
        if tag not in ALLOWED:
            return
        extra = ""
        if tag == "a":
            href = dict(attrs).get("href") or ""
            if href.startswith("https://") or href.startswith("http://"):
                extra = " href='" + html.escape(href, quote=True) + "'"
        if tag in CELL:
            extra = " style='" + CELL[tag] + "'"
        self.out.append("<" + tag + extra + ">")

    def handle_endtag(self, tag):
        tag = RENAME.get(tag, tag)
        if tag in ALLOWED:
            self.out.append("</" + tag + ">")

    def handle_data(self, data):
        self.out.append(html.escape(data, quote=False))
        self.words += data.split()


class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain(value):
    t = Text()
    t.feed(str(value or ""))
    return " ".join("".join(t.parts).split())


def find_photo(query, caption):
    try:
        r = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 15,
                "gsrsearch": query + " filetype:bitmap", "prop": "imageinfo",
                "iiprop": "url|extmetadata|size|mime", "iiurlwidth": 960,
            },
            headers=UA, timeout=30,
        )
        pages = (r.json().get("query") or {}).get("pages") or {}
    except Exception as e:
        print("사진 검색 오류:", e, flush=True)
        return None
    cands = []
    for page in sorted(pages.values(), key=lambda p: p.get("index", 99)):
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        lic = plain((meta.get("LicenseShortName") or {}).get("value"))
        up = lic.upper()
        allowed = (up.startswith("CC BY") or up.startswith("CC0") or up.startswith("PUBLIC DOMAIN")) and "NC" not in up and "ND" not in up
        if not allowed or info.get("mime") not in ("image/jpeg", "image/png"):
            continue
        if int(info.get("width") or 0) < 1200 or not info.get("thumburl"):
            continue
        cands.append({
            "thumb": info["thumburl"].split("?")[0], "page": info.get("descriptionurl", ""), "mime": info["mime"], "license": lic,
            "license_url": plain((meta.get("LicenseUrl") or {}).get("value")),
            "artist": plain((meta.get("Artist") or {}).get("value"))[:60] or "Unknown author",
        })
        if len(cands) == 6:
            break
    if not cands:
        return None
    content = []
    kept = []
    for c in cands:
        try:
            img = requests.get(c["thumb"], headers=UA, timeout=30)
            if img.status_code != 200:
                continue
            content.append({"type": "image", "source": {"type": "base64", "media_type": c["mime"], "data": base64.b64encode(img.content).decode()}})
            kept.append(c)
        except Exception:
            continue
    if not kept:
        return None
    content.append({"type": "text", "text": "These are candidate photos, numbered 1 to " + str(len(kept)) + " in order, for a travel blog post about Korea. Wanted: " + query + ". Caption: " + caption + ". Pick the one that clearly shows this and looks good. Reject photos where a person's face is the main subject, photos dominated by ads or logos, scanned documents, maps, and photos that do not match. Answer with only the number, or 0 if none fits."})
    try:
        msg = client.messages.create(model="claude-sonnet-5-5", max_tokens=2000, messages=[{"role": "user", "content": content}])
        answer = "".join(b.text for b in msg.content if b.type == "text")
        digits = [ch for ch in answer if ch.isdigit()]
        pick = int(digits[-1]) if digits else 0
    except Exception as e:
        print("사진 고르기 오류:", e, flush=True)
        return None
    if pick < 1 or pick > len(kept):
        return None
    return kept[pick - 1]


def photo_html(c, caption):
    lic = html.escape(c["license"])
    if c["license_url"].startswith("http"):
        lic = "<a href='" + html.escape(c["license_url"], quote=True) + "'>" + lic + "</a>"
    return (
        "<div class='separator' style='clear:both;text-align:center;'><a href='" + html.escape(c["page"], quote=True) + "' style='margin-left:0;margin-right:0;'>"
        + "<img src='" + html.escape(c["thumb"], quote=True) + "' alt='" + html.escape(caption, quote=True) + "' width='960' style='max-width:100%;height:auto;' /></a></div>"
        + "<p style='text-align:center;font-size:0.85em;color:#666;'>" + html.escape(caption) + " Photo: " + html.escape(c["artist"]) + ", " + lic + ", via Wikimedia Commons.</p>"
    )


# 1. 이미 발행된 글과 주제군 기록
published = []
total = 0
try:
    feed = requests.get(BLOG_URL + "/feeds/posts/default?alt=json&max-results=150", headers=UA, timeout=30).json()["feed"]
    total = int(feed.get("openSearch$totalResults", {}).get("$t", 0))
    for e in feed.get("entry", []):
        link = [x["href"] for x in e.get("link", []) if x.get("rel") == "alternate"]
        published.append(e["title"]["$t"] + " | " + (link[0] if link else ""))
except Exception as e:
    print("피드 읽기 오류:", e, flush=True)
history = []
if os.path.exists(HIST):
    with open(HIST, encoding="utf-8") as f:
        history = [line.strip() for line in f if line.strip()]

# 2. 글 쓰기와 검수
prompt = PROMPT.replace("__TODAY__", today).replace("__GROUPS__", NL.join(history[-40:]) or "없음").replace("__POSTS__", NL.join(published) or "없음")
print("글 작성 시작", flush=True)
raw = ask(prompt)
post = parse(raw)
problems = []
if not ok(post):
    raise SystemExit("형식에 맞는 글이 나오지 않았습니다.")
print("검수 시작:", post["title"], flush=True)
try:
    checked = parse(ask(VERIFY.replace("__TODAY__", today).replace("__DRAFT__", raw)))
except Exception as e:
    print("검수 오류:", e, flush=True)
    checked = {}
if ok(checked):
    post = checked
else:
    problems.append("사실 검수를 마치지 못함")

# 3. 본문 정리와 사진
slots = []
lines = []
for line in post["body"].splitlines():
    s = line.strip()
    if s.startswith("[[PHOTO:"):
        query, _, caption = s[8:].rstrip("]").partition("|")
        slots.append((query.strip(), caption.strip()))
        lines.append("PHOTOSLOT" + str(len(slots)) + "X")
    else:
        lines.append(line)
cleaner = Clean()
cleaner.feed(NL.join(lines))
body = "".join(cleaner.out).strip()
words = len([w for w in cleaner.words if not w.startswith("PHOTOSLOT")])
photos = 0
for n, (query, caption) in enumerate(slots[:3], start=1):
    print("사진 찾기:", query, flush=True)
    c = find_photo(query, caption) if query else None
    body = body.replace("PHOTOSLOT" + str(n) + "X", photo_html(c, caption) if c else "")
    photos += 1 if c else 0
for n in range(1, len(slots) + 1):
    body = body.replace("PHOTOSLOT" + str(n) + "X", "")
body = body.strip()

# 4. 발행 전 자체 검수
if words < 800:
    problems.append("단어 수 " + str(words) + "개로 800 미만")
if not body.startswith("<p><b>"):
    problems.append("첫 문단이 굵은 글씨로 시작하지 않음")
if not body.endswith("</i></p>"):
    problems.append("마지막 문단이 기울임 출처 문단이 아님")
if body.count("<h2>") < 5:
    problems.append("소제목이 5개 미만")
labels = [x.strip() for x in post.get("labels", "").split(",") if x.strip()][:3]

# 5. 발행 (구글 연결 정보가 있을 때만)
cid = os.environ.get("BLOGGER_CLIENT_ID", "")
secret = os.environ.get("BLOGGER_CLIENT_SECRET", "")
refresh = os.environ.get("BLOGGER_REFRESH_TOKEN", "")
result = "시험 실행 — 발행하지 않음 (구글 연결 전)"
post_url = ""
if cid and secret and refresh:
    try:
        tok = requests.post("https://oauth2.googleapis.com/token", data={"client_id": cid, "client_secret": secret, "refresh_token": refresh, "grant_type": "refresh_token"}, timeout=30).json()
        auth = {"Authorization": "Bearer " + tok["access_token"]}
        api = "https://www.googleapis.com/blogger/v3/blogs/" + BLOG_ID + "/posts"
        draft = bool(problems) or os.environ.get("BLOGGER_FORCE_DRAFT") == "true"
        made = requests.post(api, params={"isDraft": "true" if draft else "false"}, headers=auth, json={"kind": "blogger#post", "title": post["slug"], "content": body, "labels": labels}, timeout=60)
        made.raise_for_status()
        made = made.json()
        fixed = requests.patch(api + "/" + made["id"], headers=auth, json={"title": post["title"]}, timeout=60)
        post_url = made.get("url", "")
        result = ("임시저장만 함 (" + ", ".join(problems or ["시험 실행"]) + ")") if draft else "발행됨"
        if fixed.status_code >= 300:
            problems.append("제목을 전체 제목으로 바꾸지 못함")
        if not draft:
            history.append(today + " | " + post.get("group", "?") + " | " + post["title"])
            with open(HIST, "w", encoding="utf-8") as f:
                f.write(NL.join(history) + NL)
            total += 1
    except Exception as e:
        result = "발행 못 함 (" + str(e)[:200] + ")"

# 6. 필수 페이지 점검과 보고
bad = []
for path in ("/p/about.html", "/p/privacy-policy.html", "/p/disclaimer.html", "/p/contact.html"):
    try:
        if requests.get(BLOG_URL + path, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}, timeout=30).status_code != 200:
            bad.append(path)
    except Exception:
        bad.append(path)
report = [
    result + (" " + post_url if post_url else ""),
    post["title"] + " (주제군 " + post.get("group", "?") + ", 라벨: " + ", ".join(labels) + ")",
    post.get("summary_ko", ""),
    "발행 글 " + str(total) + "편, 20편까지 " + str(max(0, 20 - total)) + "편 남음. 필수 페이지: " + ("모두 열림" if not bad else "안 열림 " + ", ".join(bad)) + ". 영어 " + str(words) + "단어, 사진 " + str(photos) + "장.",
    post.get("note_ko", "특이사항 없음") + (" / 자체 검수: " + ", ".join(problems) if problems else ""),
]
print(NL.join(report), flush=True)

HEAD = "<meta charset='UTF-8'><meta name='viewport' content='width=device-width, initial-scale=1'><meta name='robots' content='noindex, nofollow'>"
os.makedirs("blogger", exist_ok=True)
page = (
    "<!DOCTYPE html><html lang='ko'><head>" + HEAD + "<title>" + today + " Everyday Korea Notes</title></head>"
    + "<body style='font-family:sans-serif;max-width:820px;margin:0 auto;padding:20px;line-height:1.7'>"
    + "<h1>" + today + " Everyday Korea Notes 보고</h1><ol style='background:#f3f6fa;padding:16px 16px 16px 36px;border-radius:8px'>"
    + "".join("<li>" + html.escape(x) + "</li>" for x in report) + "</ol>"
    + "<p style='color:#666;font-size:13px'>주소용 짧은 제목: " + html.escape(post["slug"]) + " / 검색 설명: " + html.escape(post.get("desc", "")) + "</p>"
    + "<hr><h1>" + html.escape(post["title"]) + "</h1>" + body + "</body></html>"
)
with open("blogger/" + today + ".html", "w", encoding="utf-8") as f:
    f.write(page)
files = sorted((f for f in os.listdir("blogger") if f.endswith(".html") and f != "index.html"), reverse=True)
index = (
    "<!DOCTYPE html><html lang='ko'><head>" + HEAD + "<title>Everyday Korea Notes 보고</title></head>"
    + "<body style='font-family:sans-serif;max-width:600px;margin:40px auto;padding:0 20px;font-size:18px;line-height:2'>"
    + "<h1>Everyday Korea Notes 보고</h1><ul>" + "".join("<li><a href='" + f + "'>" + f[:-5] + "</a></li>" for f in files) + "</ul></body></html>"
)
with open("blogger/index.html", "w", encoding="utf-8") as f:
    f.write(index)
if result.startswith("발행 못 함"):
    raise SystemExit(result)
