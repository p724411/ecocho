import os
import sys
import json
import re
import requests
from google import genai
from google.genai import types
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

sys.stdout.reconfigure(encoding="utf-8")

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
KST = timezone(timedelta(hours=9))

KEYWORDS = [
    "코스피",
    "미국 증시 마감",
    "원달러 환율",
    "금 시세",
    "유가 WTI",
    "비트코인",
    "미국 금리",
    "정부 지원금",
    "재테크 ETF",
]


def load_config():
    config = {
        "NAVER_CLIENT_ID": os.environ.get("NAVER_CLIENT_ID", ""),
        "NAVER_CLIENT_SECRET": os.environ.get("NAVER_CLIENT_SECRET", ""),
        "TELEGRAM_TOKEN": os.environ.get("TELEGRAM_TOKEN", ""),
        "TELEGRAM_CHAT_ID": os.environ.get("TELEGRAM_CHAT_ID", "8552510154"),
        "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", ""),
    }
    if os.path.exists("secrets.json"):
        with open("secrets.json", encoding="utf-8") as f:
            local = json.load(f)
            for k in config:
                if not config[k] and k in local:
                    config[k] = local[k]
    return config


def strip_html(text):
    return re.sub(r"<[^>]+>", "", text)


def naver_search(query, client_id, client_secret, display=7):
    url = f"https://openapi.naver.com/v1/search/news.json?query={quote(query)}&display={display}&sort=date"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json().get("items", [])


def find_hot_topics(all_news, api_key):
    client = genai.Client(api_key=api_key)
    titles = [
        strip_html(item.get("title", ""))
        for items in all_news.values()
        for item in items
    ]
    prompt = f"""다음은 오늘 수집된 경제 뉴스 제목들입니다:

{chr(10).join(titles)}

위 기사들에서 반복 등장하거나 오늘 특히 화제가 될 만한 기업명·이슈 키워드를 정확히 3개만 골라주세요.
JSON 배열로만 답하세요. 예: ["애플 가격인상", "삼성전자 실적", "테슬라 리콜"]"""

    response = client.models.generate_content(
        model="gemini-2.5-flash", contents=prompt
    )
    match = re.search(r"\[.*?\]", response.text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())[:3]
        except Exception:
            pass
    return []


def collect_news(config):
    cid = config["NAVER_CLIENT_ID"]
    cs = config["NAVER_CLIENT_SECRET"]
    all_news = {}

    for kw in KEYWORDS:
        try:
            all_news[kw] = naver_search(kw, cid, cs)
            print(f"  OK {kw}: {len(all_news[kw])}건")
        except Exception as e:
            all_news[kw] = []
            print(f"  FAIL {kw}: {e}")

    print("핫 토픽 자동 탐지 중...")
    hot_topics = find_hot_topics(all_news, config["GEMINI_API_KEY"])
    print(f"  탐지된 핫 토픽: {hot_topics}")
    for kw in hot_topics:
        try:
            all_news[kw] = naver_search(kw, cid, cs)
            print(f"  OK {kw}: {len(all_news[kw])}건")
        except Exception as e:
            all_news[kw] = []
            print(f"  FAIL {kw}: {e}")

    return all_news, hot_topics


def format_for_gemini(all_news):
    parts = []
    for kw, items in all_news.items():
        parts.append(f"=== [{kw}] 검색 결과 ===")
        for item in items:
            parts.append(f"제목: {strip_html(item.get('title', ''))}")
            parts.append(f"내용: {strip_html(item.get('description', ''))}")
            parts.append(f"링크: {item.get('originallink') or item.get('link', '')}")
            parts.append(f"날짜: {item.get('pubDate', '')}")
            parts.append("")
    return "\n".join(parts)


SYSTEM_PROMPT = """당신은 30년 이상 경험을 쌓은 주식전문가이며 애널리스트입니다.
초보자를 위한 자기계발/재테크/지원금 주제로 인스타그램을 운영 중이며,
매일 아침 구독자들에게 보낼 모닝 브리핑을 작성합니다.

작성 규칙:
- 부드러운 말투 (~해요/~예요)
- 이모지 적극 활용 (많아도 좋음)
- 초보자도 이해할 수 있게, 어려운 단어는 괄호()로 간단히 설명
- 투자 권유가 아닌 정보 제공 목적 유지 (안전한 가이드 톤)
- 구체적 수치 포함
- 반드시 오늘 날짜의 기사만 활용
- 빅이슈 선정 기준: 시장 영향력, 반복 등장, 수치 구체성, 언론 신뢰도"""


def generate_briefing(news_text, today_str, time_str, hot_topics, api_key):
    client = genai.Client(api_key=api_key)
    hot_topics_str = ", ".join(hot_topics) if hot_topics else "없음"
    prompt = f"""오늘은 {today_str}입니다.

아래 뉴스 기사들을 바탕으로 모닝 브리핑을 작성해주세요.

{news_text}

---
아래 형식으로 작성하세요:

🐤 {today_str} {time_str} 브리핑

[오늘 전반적인 경제 동향 요약 2줄. 인사말·호칭 없이 핵심만. 예: "미국발 기술주 약세로 코스피 급락. 환율은 당국 개입으로 진정세."] ☕

📈 시장 브리핑 TOP 5

1️⃣ [이슈 제목] [관련 이모지]
[이슈 설명: 구체적 수치 포함]
👉 [초보자에게 어떤 의미인지, 행동 가이드]
🔗 [관련 기사 원문 링크]

2️⃣ ~ 5️⃣ (동일 형식 반복)

🔥 오늘의 화제 (오늘 특히 주목받는 이슈: {hot_topics_str})
※ TOP 5에서 이미 다룬 내용은 절대 포함하지 말 것. TOP 5와 겹치지 않는 별도 이슈 3개만 작성.
각 항목 형식:
[이모지] [제목 한 줄]
[한 문장 설명]
🔗 [링크]

💡 오늘의 정책/재테크 정보 (해당 기사가 있을 경우만 작성, 없으면 섹션 전체 생략)

📢 [정책/지원금 이름]
[설명 + 신청 방법/대상]
🔗 [관련 기사 링크]

✏️ 오늘의 한 줄 요약
> [오늘 시장을 한 문장으로]

👀 오늘 장중 주목할 점
- [체크포인트 1]
- [체크포인트 2]

[마무리 인사] 🍀"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )
    return response.text


def send_telegram(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    chunks = [text[i : i + 4096] for i in range(0, len(text), 4096)]
    for chunk in chunks:
        r = requests.post(url, json={"chat_id": chat_id, "text": chunk}, timeout=30)
        if not r.json().get("ok"):
            print(f"전송 실패: {r.json()}")
            return
    print("텔레그램 전송 성공")


def main():
    config = load_config()
    now = datetime.now(KST)
    today_str = f"{now.month}월 {now.day}일({WEEKDAYS[now.weekday()]})"
    time_str = now.strftime("%H:%M")

    print(f"뉴스 수집 중... ({today_str} {time_str})")
    all_news, hot_topics = collect_news(config)

    news_text = format_for_gemini(all_news)

    print("브리핑 생성 중 (Gemini 2.5 Flash)...")
    briefing = generate_briefing(news_text, today_str, time_str, hot_topics, config["GEMINI_API_KEY"])

    print("\n" + "=" * 60)
    print(briefing)
    print("=" * 60 + "\n")

    output = f"briefing_{now.strftime('%Y%m%d_%H%M')}.txt"
    with open(output, "w", encoding="utf-8") as f:
        f.write(briefing)
    print(f"파일 저장: {output}")

    print("텔레그램 전송 중...")
    send_telegram(config["TELEGRAM_TOKEN"], config["TELEGRAM_CHAT_ID"], briefing)


if __name__ == "__main__":
    main()
