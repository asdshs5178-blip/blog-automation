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
    "조회수 기대 글 (카테고리: 생활정보). 목표는 조회수 하나입니다. 주제 범위 제한은 없습니다. 생활, 돈, 세금, 건강보험, 연금, 지원금, 쇼핑, 요금, 교통, 날씨, 계절 준비, 요즘 많이 검색되는 생활 이슈 등 어디든, 지금 많은 사람이 네이버에서 실제로 검색하는 주제를 고릅니다. 시기 주제는 참고일 뿐 거기에 묶이지 않습니다. 트렌드에 정보 글로 풀 수 있는 큰 이슈가 있으면 우선합니다. 단, 아래 '사실 확인'과 금지 사항(연예인 사생활, 사건·사고, 정치, 성인·도박·대부업·불법, 상품 홍보, 건강 효능·투자 수익 단정)은 어떤 경우에도 지킵니다. 제목은 검색형으로 씁니다.",
    "조회수 기대 글 (카테고리: 생활정보). 1번과 다른 소재로, 역시 조회수가 가장 잘 나올 주제를 고릅니다. 주제 범위 제한은 없고 금지 사항만 지킵니다. 많은 사람이 겪는 상황(요금이 갑자기 올랐을 때, 신청했는데 안 됐을 때, 헷갈리는 두 제도의 차이, 자주 하는 실수)이 잘 맞습니다. 이 글만 제목을 홈판형으로 씁니다: 핵심 키워드는 넣되 궁금증, 공감, 자주 하는 실수, 손해를 피하는 법 중 하나를 살립니다(예: \"에어컨 전기요금, 하루 종일 켰다가 놀란 이유\"). 사실 안에서만 궁금증을 만들고, 제목이 약속한 답은 본문에 반드시 있어야 합니다.",
]

PROMPT = """오늘은 __TODAY__ (__WEEKDAY__요일)입니다.
네이버 블로그 "알아두면 쓸모있는 생활노트"(정보·꿀팁형 생활정보 블로그)에 올릴 글 1편을 만듭니다.

[이번에 쓸 글]
__SPEC__

[오늘 이미 쓴 글 - 이 글들과 소재 자체가 달라야 합니다. 같은 행사, 같은 제도, 같은 시험(예: 수능)을 오늘 두 번 다루지 않습니다]
__DONE__

[이전에 이미 쓴 글 - 같은 소재는 다시 쓰지 않습니다. 이전 글 이후에 새 발표나 변경이 나온 경우에만, 이전 글에 없는 내용으로 씁니다. 아래 목록에 같은 소재가 두 번 이상 있으면 그 소재는 고르지 않습니다]
__HISTORY__

[오늘의 Google Trends 대한민국 RSS]
__TRENDS__

[최근 글 제목 - 제목의 꼴이 이것들과 비슷하면 안 됩니다. 특히 "정리", "총정리", "한 번에 정리"로 끝나는 제목은 이미 너무 많으니 쓰지 않습니다]
__RECENT__

[주제 고르는 순서 - 쓰기 전에 반드시 거칩니다]
1. 소재를 찾습니다(트렌드, 정책브리핑 korea.kr, 복지로, 보조금24, 부처·지자체 보도자료, 뉴스).
2. 웹 검색으로 사람들이 실제로 검색하는 표현을 확인합니다. 검색 결과 상위 글들의 제목에서 반복되는 말이 실제 검색어입니다. 그 말을 제목과 첫 문단에 그대로 씁니다.
3. "핵심 키워드 + 상황 + 행동"으로 좁힙니다(예: "자동차세"가 아니라 "자동차세 12월 납부 기간"). 글 하나에는 검색 의도 하나만 담습니다.
4. 행동 키워드를 우선합니다: 신청 방법, 자격 조건, 대상 조회, 신청 기간, 지급일, 필요 서류, 신청이 안 될 때, 비용, 계산 방법, 차이·비교, 변경, 해지, 환불. 검색한 뒤 바로 무언가를 하려는 사람이 찾는 말입니다.
5. 그 키워드로 검색해 상위 글 몇 개를 보고, 오래된 조건, 빠진 예외, 헷갈리는 계산, 따라 하기 어려운 단계를 찾아 내 글에서 채웁니다. 문장과 이미지는 가져오지 않습니다.
6. 통과 기준: 많은 사람이 실제로 검색하는 주제이고, 공식 출처가 있고, 기존 글보다 분명한 답을 줄 수 있어야 합니다. 검색하는 사람이 거의 없는 주제(아주 먼 미래의 개통 계획, 일부 지역·일부 직군만 해당하는 제도, 전문가만 찾는 계산법)는 고르지 않습니다.

[월별 시기 주제 - 참고용. 날짜와 내용은 해마다 다르니 공식 출처에서 확인합니다]
1월: 연말정산 간소화, 새해 달라지는 제도, 자동차세 연납, 설 준비 / 2월: 설, 졸업·입학, 국가장학금, 이사철 / 3월: 새 학기, 근로·자녀장려금 반기 신청, 미세먼지, 청년 정책 신청 / 4월: 건강보험료 연말정산, 부가세 예정신고 / 5월: 종합소득세, 근로·자녀장려금 정기 신청 / 6월: 장마, 휴가 준비, 자동차세 1기분 / 7월: 폭염·전기요금, 재산세, 부가세 확정신고 / 8월: 태풍, 추석 열차 예매, 2학기 국가장학금 / 9월: 추석, 재산세, 독감 접종, 근로장려금 반기 / 10월: 환절기, 연말정산 미리보기 / 11월: 수능, 난방비·에너지바우처, 김장, 연말 할인, 연말정산 준비 / 12월: 연말정산 절세, 자동차세 2기분, 새해 달라지는 제도, 한파·동파, 연말 마감 신청

[AI 브리핑에 인용되는 글 - 네이버 검색 상단 AI 요약이 근거로 가져다 쓰는 글이 되어야 합니다]
- 첫 문단에서 검색한 질문에 바로 답합니다. 결론(금액, 날짜, 되는지 안 되는지)을 숨기지 않습니다.
- 숫자·날짜·대상·조건이 들어간 사실 문장은 "무엇이, 어떤 조건에서, 얼마(언제)"가 한 문장에 들어가게 써서, 그 문장만 떼어 읽어도 뜻이 통하게 합니다. 앞 문장을 봐야 뜻이 통하는 "이건 그렇게 돼요" 같은 문장은 피합니다.
- 소제목 중 2~3개는 사람들이 실제로 검색하는 질문 문장으로 씁니다(예: "연납했는데 12월 고지서가 오면 어떻게 하나요").
- 숫자가 여러 개 나오면 본문 중간에 한 줄에 항목 하나씩 조건과 값을 모은 정리 문단을 한 번 넣습니다.

[사실 확인 - 가장 중요]
- 웹 검색으로 공식 출처(기관 공지, 보도자료, 공식 안내)를 확인한 숫자, 날짜, 금액, 자격 조건만 씁니다.
- 사실 확인 대상은 숫자, 날짜, 금액, 자격 조건, 기관명, 제도명, 절차입니다. 누구나 아는 일반적인 생활 요령(예: 눈길에는 체인을 챙긴다, 마감 직전에는 접속이 몰린다)은 출처 없이도 쓸 수 있습니다. 확인이 안 됐다고 글의 알맹이를 모두 "확인하세요"로 바꾸면 안 됩니다. 확인된 사실로 답을 주고, 확인 못 한 세부만 어디서 보는지 안내합니다.
- 확인하지 못한 값은 쓰지 않습니다. 추정으로 채우지 않습니다. 확정되지 않은 내용은 확정 전이라고 적습니다.
- 예전 연도 기준의 금액이나 조건은 쓰지 않습니다. 올해 기준을 공식 출처에서 확인하지 못하면 숫자를 빼고 어디서 확인하는지만 안내합니다.
- 지역이나 기관마다 다른 내용은 어느 지역, 어느 기관 기준인지 적습니다.
- 블로그, 카페, 홍보성 기사에서만 본 내용은 쓰지 않습니다.
- 하지 않은 경험을 한 것처럼 쓰지 않습니다. "무조건", "100%", "누구나" 같은 단정 표현을 쓰지 않습니다.
- 특정 상품·업체 홍보, 특정 개인 비방, 정치적 주장, 건강 효능이나 투자 수익 단정은 쓰지 않습니다.
- 다른 글이나 기사의 문장을 복사하지 않고 직접 쓴 문장으로 정리합니다.

[글 작성 규칙]
- 순서: 도입(공감할 상황 한두 문장) → 첫 문단 안에서 핵심 답 → 소제목 5~7개 → 자주 묻는 질문 3~4개 → 마무리 요약 4~5줄 → 확인 기준일과 출처 기관명 한 줄.
- 제목(검색형): 실제 검색어를 맨 앞에 두고, 그 뒤에 글이 주는 답 하나를 붙입니다. 25~35자. 키워드를 두세 개 이어 붙이지 않습니다. "정리", "총정리", "한 번에 정리"로 끝내지 않습니다. 막연한 겁주기("모르면 손해"), 확인되지 않은 마감("오늘 끝"), 본문에 없는 혜택 약속은 쓰지 않습니다. 제목이 약속한 답은 본문에 반드시 있어야 합니다.
- 제목 예: "자동차세 12월 납부기간, 고지서 안 와도 내는 법" (좋음) / "자동차세 12월 납부기간 16~31일, 고지서 안 와도 조회하는 법 정리" (나쁨: 너무 길고 끝이 '정리')
- 분량: 본문은 공백 제외 1,800~2,300자.
- 말투(가장 중요한 요구): 사람이 직접 쓴 네이버 블로그 글처럼 씁니다. 기본은 편한 해요체이고 문장 끝을 섞습니다(~해요, ~거든요, ~더라고요, ~잖아요, ~죠, 가끔 ~습니다). 같은 끝맺음이 서너 문장 이어지면 안 됩니다. "~입니다"만 이어지는 보고서 문체는 안 됩니다.
- 쓰지 않는 틀 문장: "결론부터 말씀드리면", "정리하면 이렇습니다", "마무리로 핵심만 정리합니다", "먼저 알아둘 점이 있습니다", "첫째, 둘째, 셋째", "하나, 둘, 셋", "~할 수 있습니다"의 반복, 문단마다 똑같은 길이와 구조.
- 문단마다 길이와 리듬을 다르게 합니다. 짧게 끊는 문장, 괄호 속 혼잣말, 독자에게 건네는 말("여기까진 쉽죠?")을 섞습니다. 조사도 입말로 씁니다(와/과 대신 랑·이랑, ~에는 대신 ~엔). 문단은 2~4문장. "오늘", "어제" 대신 날짜를 씁니다.
- 겪지 않은 일을 겪은 것처럼 꾸미지 않습니다. "찾아봤어요", "헷갈리더라고요" 정도까지만 씁니다. 숫자, 날짜, 조건, 기관명은 말투와 상관없이 정확하게 씁니다.
- 마무리 요약은 "✔"로 시작하는 짧은 메모 4~5줄로 씁니다(예: "✔ 납부는 12월 16일 ~ 31일").
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
- 검수 대상은 숫자, 날짜, 금액, 자격 조건, 기관명, 제도명, 절차입니다. 누구나 아는 일반적인 생활 요령이나 글쓴이의 조언은 출처가 없어도 지우지 않습니다. 글의 알맹이를 "확인하세요"로 바꿔 버리면 안 됩니다. 확인된 사실로 답을 주는 문장은 그대로 두고, 확인 못 한 세부만 안내 문장으로 바꿉니다.
- 고친 뒤에도 글의 순서, 말투(해요체 섞인 블로그 말투, 보고서 문체로 바꾸지 않음), 분량(공백 제외 1,800~2,300자), [[ ]] 표시 7~9곳, @@IMG 1·2·3 자리를 유지합니다. 제목의 꼴(길이, 끝맺음)도 바꾸지 않습니다.

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
- html과 body는 margin 0, 가로 정확히 700px. 세로는 위에 적힌 높이를 min-height 로만 두고, height 고정이나 overflow hidden 은 쓰지 않습니다(내용이 잘립니다). 3번은 내용이 많으면 세로로 더 길어져도 됩니다(최대 1300px). 1번과 2번은 반드시 700px 안에 들어가게 내용을 줄입니다.
- 하단 문구 "알아두면 쓸모있는 생활노트"는 position:absolute 로 띄우지 말고, 내용 맨 아래에 흐름대로 넣고 위쪽 여백을 둡니다. 다른 요소도 position:absolute 로 겹치게 배치하지 않습니다.
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


def ask(prompt, search=True, model="claude-sonnet-5-5"):
    kwargs = {}
    if search:
        kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}]
    messages = [{"role": "user", "content": prompt}]
    text = ""
    for _ in range(6):
        with client.messages.stream(
            model=model,
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


HIST = "history.txt"
history = []
if os.path.exists(HIST):
    with open(HIST, encoding="utf-8") as f:
        history = [line.strip() for line in f if line.strip()]
history = [line for line in history if not line.startswith(today)]
old_topics = NL.join("- " + line for line in history[-200:]) or "없음"
recent_titles = NL.join("- " + line.split("|", 1)[-1].strip() for line in history[-24:]) or "없음"

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
        .replace("__HISTORY__", old_topics)
        .replace("__TRENDS__", trends)
        .replace("__RECENT__", recent_titles)
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
        docs = parse_images(ask(IMG_PROMPT.replace("__STYLE__", styles).replace("__POST__", body), search=False, model="claude-haiku-5-5"))[:3]
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
                pg.add_style_tag(content="html,body{overflow:visible !important;height:auto !important;max-height:none !important}")
                pg.evaluate("document.body.style.minHeight='" + str(h) + "px'")
                real = pg.evaluate("Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
                limit = h if h == 700 else 1300
                if real > limit:
                    z = round(limit / real, 4)
                    pg.evaluate("(function(z,h){var b=document.body;b.style.zoom=z;b.style.width=(700/z)+'px';b.style.minHeight=(h/z)+'px';document.documentElement.style.width=(700/z)+'px';})(" + str(z) + "," + str(limit) + ")")
                    print(name, "내용이 넘쳐 축소:", real, "->", limit, flush=True)
                    real = limit
                final_h = h if h == 700 else max(h, min(real, limit))
                pg.set_viewport_size({"width": 700, "height": final_h})
                pg.screenshot(path=img_dir + "/" + name, clip={"x": 0, "y": 0, "width": 700, "height": final_h})
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

with open(HIST, "w", encoding="utf-8") as f:
    f.write(NL.join(history + [today + " | " + p["title"] for p in posts]) + NL)

print("저장:", path, "/ 완성된 글:", len(posts), "편 / 사진:", image_count, "장")
if len(posts) < len(SPECS):
    raise SystemExit("일부 글이 만들어지지 않았습니다.")
if image_count < 3 * len(posts):
    raise SystemExit("일부 사진이 만들어지지 않았습니다.")
