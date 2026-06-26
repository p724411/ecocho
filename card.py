import re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from google import genai

_TEMPLATE = open(Path(__file__).parent / "rebalancing_story.html", encoding="utf-8").read()

_KST = timezone(timedelta(hours=9))
_CARDS_DIR = Path(__file__).parent / "static" / "cards"
_BASE_URL = "https://lunavis.pythonanywhere.com/static/cards"

_PROMPT = """당신은 30년이상 베테랑 경제, 재테크 전문가. 경제지식이 초보인 사람들을 위한 카드뉴스를 만드는데,

오늘({today}) 경제 뉴스를 바탕으로,
아래 HTML 템플릿과 완전히 동일한 구조·디자인으로 카드뉴스 HTML을 만들어줘.

오늘의 주제: {topic}

참고 기사:
{news}

[작성 조건]
1. 날짜: {today} 로 업데이트
2. 주식/경제 초보도 이해할 수 있게 — 어려운 용어는 괄호()로 바로 설명
3. STEP 3단계 흐름:
   - STEP 1 발단: 이 이슈/용어가 정확히 무슨 뜻인지?, 왜 이런일이 일어났는지(원인)
   - STEP 2 핵심: 현재상황 or 왜 중요한지? 
   - STEP 3 전망: 앞으로 어떻게 될까?, 내 돈·일상에 어떤 영향?
4. 결론 박스: 핵심 한 줄 정리 + 수혜·주의 종목 명시
5. 인사이트 칩 3개: 📉주의 종목 / 📈수혜 종목 / 👀다음 변수
6. 헤드라인: 독자가 궁금해할 문장(3초안에 시선을 머물도록.) (예: "~가 내 ~을 바꾼다?", ~한 이유?)
7. 390×844px 한 화면에 딱 맞게 — 폰트 크기·여백 조정해서 스크롤 없이
8. step-desc 안 <b> 태그로 핵심 수치·단어 강조

[HTML 템플릿]
{template}

HTML 코드만 출력. 마크다운·설명 없이."""


def generate_card_html(topic: str, news_items: list, today: str, api_key: str) -> str:
    news_text = "\n".join(
        f"- {item.get('title', '')} | {item.get('description', '')}"
        for item in news_items[:6]
    )
    prompt = _PROMPT.format(today=today, topic=topic, news=news_text, template=_TEMPLATE)

    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)

    html = resp.text.strip()
    html = re.sub(r"^```html\s*", "", html)
    html = re.sub(r"\s*```$", "", html)
    return html


def save_card_html(html: str, filename: str = None) -> str:
    _CARDS_DIR.mkdir(parents=True, exist_ok=True)
    if filename is None:
        filename = f"card_{datetime.now(_KST).strftime('%Y%m%d_%H%M')}.html"
    (_CARDS_DIR / filename).write_text(html, encoding="utf-8")
    return f"{_BASE_URL}/{filename}"
