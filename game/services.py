import re

from django.conf import settings


LABELS = {"맞습니다", "아닙니다", "질문이 모호합니다", "관계없습니다"}


def _normalize_label(raw_text):
    if not raw_text:
        return "질문이 모호합니다"

    cleaned = raw_text.strip()
    if cleaned in LABELS:
        return cleaned

    if "맞습니다" in cleaned:
        return "맞습니다"
    if "아닙니다" in cleaned:
        return "아닙니다"
    if "질문이 모호합니다" in cleaned:
        return "질문이 모호합니다"
    if "관계없습니다" in cleaned:
        return "관계없습니다"

    return "질문이 모호합니다"


def classify_question(scenario, answer_text, question_text):
    print("QUESTION:", question_text)

    if not settings.OPENAI_API_KEY:
        return "질문이 모호합니다"

    try:
        from openai import OpenAI
    except ImportError:
        return "질문이 모호합니다"

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # 변경: 판정 프롬프트를 한국어 4개 라벨 전용으로 강화
    # 예시 기대값:
    # - 남자는 식당에서 무언가를 먹었나요? -> 맞습니다
    # - 남자는 살해당했나요? -> 아닙니다
    # - 남자는 큰 충격을 받았나요? -> 질문이 모호합니다
    # - 남자의 직업이 중요합니까? -> 관계없습니다
    prompt = f"""
너는 바다거북스프 게임의 질문 판정기다.
사용자의 질문을 보고 이야기의 진실과 비교하여 4개 중 하나만 반환한다.
설명하지 말고 결과만 출력한다.

반드시 아래 4개 중 정확히 하나만 출력하라:
맞습니다
아닙니다
질문이 모호합니다
관계없습니다

출력 규칙:
- 다른 설명, 이유, 부가 문장, 문장부호, 줄바꿈을 붙이지 말 것
- "맞습니다."처럼 마침표를 붙이지 말 것
- 영어로 출력하지 말 것

판정 기준:
- "맞습니다": 질문의 내용이 이야기의 사실과 직접적으로 일치할 때
- "아닙니다": 질문의 내용이 이야기의 사실과 직접적으로 일치하지 않을 때
- "질문이 모호합니다": 질문이 너무 넓거나 애매하거나, 예/아니오로 단정하기 어렵거나, 기준이 불명확할 때
- "관계없습니다": 질문 자체는 명확하지만 사건 해결과 거의 관련이 없는 주변 정보일 때

추가 지침:
- 질문이 예/아니오로 답하기 어려운 경우에는 "질문이 모호합니다"
- 질문이 명확하지만 사건 해결과 무관하면 "관계없습니다"
- 사건의 핵심과 직접 관련된 사실이면 "맞습니다" 또는 "아닙니다"

예시:
- 남자는 식당에서 무언가를 먹었나요? -> 맞습니다
- 남자는 살해당했나요? -> 아닙니다
- 남자는 큰 충격을 받았나요? -> 질문이 모호합니다
- 남자의 직업이 중요합니까? -> 관계없습니다

이야기 시나리오:
{scenario}

이야기의 진실:
{answer_text}

사용자 질문:
{question_text}
""".strip()

    try:
        response = client.responses.create(
            model=settings.OPENAI_CLASSIFIER_MODEL,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "너는 바다거북스프 질문 판정기다. 반드시 '맞습니다', '아닙니다', '질문이 모호합니다', '관계없습니다' 중 하나만 출력하고 설명은 절대 덧붙이지 마라.",
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt,
                        }
                    ],
                },
            ],
            max_output_tokens=300,
        )
        print("RAW RESPONSE:", response)

        label = "질문이 모호합니다"

        try:
            # 변경: None 안전 처리 유지, 예상 밖 응답도 문자열로 안전 변환
            answer = getattr(response, "output_text", None)
            if not answer:
                answer = "응답 생성 실패 (토큰 부족 또는 오류)"

            text = str(answer).strip()

            print("PARSED TEXT:", text)

            # 변경: 서버 측 후처리를 한국어 4개 라벨 기준으로 고정
            label = _normalize_label(text)
        except Exception as e:
            print("PARSING ERROR:", e)

        return label
    except Exception as e:
        print("OPENAI ERROR:", e)
        return "질문이 모호합니다"
