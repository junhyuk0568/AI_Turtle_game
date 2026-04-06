import re

from django.conf import settings


LABELS = {"맞습니다", "아닙니다", "질문이 모호합니다", "관계없습니다"}
ABSTRACT_PATTERNS = (
    "중요한가요",
    "중요합니까",
    "어떤 일인가요",
    "무슨 일인가요",
    "어떻게 된 일인가요",
    "큰 충격",
    "심각한가요",
)
IRRELEVANT_KEYWORDS = {
    "직업",
    "날씨",
    "이름",
    "나이",
    "키",
    "외모",
    "혈액형",
    "출신",
    "취미",
    "옷",
    "색깔",
}
STOPWORDS = {
    "남자",
    "여자",
    "사람",
    "누군가",
    "누구",
    "어떤",
    "무언가",
    "무엇",
    "왜",
    "정말",
    "혹시",
    "에서",
    "으로",
    "에게",
    "했다",
    "했나요",
    "인가요",
    "입니까",
    "가요",
    "나요",
    "했습니까",
    "있었나요",
    "있나요",
    "인가",
    "중요",
    "들어",
    "있었",
    "있어",
    "있습",
}
KEYWORD_SYNONYMS = {
    "죽": ("죽", "사망", "자살", "살해"),
    "자살": ("자살", "죽", "사망"),
    "살해": ("살해", "죽", "사망", "자살"),
    "스프": ("스프", "수프"),
    "먹": ("먹", "마시", "섭취"),
    "식당": ("식당",),
    "독": ("독",),
}


def _normalize_label(raw_text):
    if not raw_text:
        return "질문이 모호합니다"

    cleaned = raw_text.strip()
    if cleaned in LABELS:
        return cleaned

    # 변경: YES/NO를 최우선으로 고정하고, 관계없습니다를 그 다음으로 판정
    if "맞습니다" in cleaned:
        return "맞습니다"
    if "아닙니다" in cleaned:
        return "아닙니다"
    if "관계없습니다" in cleaned:
        return "관계없습니다"
    if "질문이 모호합니다" in cleaned:
        return "질문이 모호합니다"

    return "질문이 모호합니다"


def _extract_keywords(text):
    tokens = re.findall(r"[가-힣A-Za-z0-9]+", text.lower())
    normalized_tokens = []
    for token in tokens:
        if len(token) < 2 or token in STOPWORDS:
            continue

        for suffix in ("인가요", "입니까", "했나요", "습니까", "있나요", "있었나요", "가요", "나요"):
            if token.endswith(suffix) and len(token) > len(suffix):
                token = token[: -len(suffix)]
                break

        for prefix_keyword in KEYWORD_SYNONYMS:
            if token.startswith(prefix_keyword):
                token = prefix_keyword
                break

        normalized_tokens.append(token)

    return normalized_tokens


def _classify_question_locally(scenario, answer_text, question_text):
    source_text = f"{scenario} {answer_text}".lower()
    normalized_question = question_text.strip().lower()

    # 변경: API를 쓰지 못할 때도 "질문이 모호합니다" 남발을 막기 위한 로컬 fallback
    if any(keyword in normalized_question for keyword in IRRELEVANT_KEYWORDS):
        return "관계없습니다"

    if any(pattern in normalized_question for pattern in ABSTRACT_PATTERNS):
        return "질문이 모호합니다"

    keywords = _extract_keywords(normalized_question)
    if not keywords:
        return "질문이 모호합니다"

    matched_keywords = []
    for keyword in keywords:
        synonym_candidates = KEYWORD_SYNONYMS.get(keyword, (keyword,))
        if any(candidate in source_text for candidate in synonym_candidates):
            matched_keywords.append(keyword)

    concrete_question = normalized_question.endswith(("나요?", "가요?", "습니까?", "인가요?", "입니까?"))

    match_ratio = len(matched_keywords) / len(keywords)

    if matched_keywords and match_ratio >= 0.6:
        return "맞습니다"

    if concrete_question:
        return "아닙니다"

    return "질문이 모호합니다"


def classify_question(scenario, answer_text, question_text):
    print("QUESTION:", question_text)

    if not settings.OPENAI_API_KEY:
        # 변경: API 키가 없어도 로컬 규칙으로 YES/NO/관계없습니다를 우선 판정
        return _classify_question_locally(scenario, answer_text, question_text)

    try:
        from openai import OpenAI
    except ImportError:
        # 변경: 패키지 import 실패 시에도 로컬 규칙 판정으로 fallback
        return _classify_question_locally(scenario, answer_text, question_text)

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # 변경: 모호 판정을 최소화하고 YES/NO를 우선 반환하도록 프롬프트 전면 수정
    prompt = f"""
너는 바다거북스프 게임의 질문 판정기다.
사용자의 질문을 보고 이야기의 진실과 비교하여 아래 4개 중 하나만 반환한다.
설명 없이 결과만 출력한다.

반드시 아래 4개 중 정확히 하나만 출력하라:
맞습니다
아닙니다
질문이 모호합니다
관계없습니다

출력 규칙:
- 다른 설명, 이유, 부가 문장, 문장부호, 줄바꿈을 붙이지 말 것
- "맞습니다."처럼 마침표를 붙이지 말 것
- 영어로 출력하지 말 것

판정 우선순위:
1. 가장 먼저 "맞습니다" 또는 "아닙니다"로 판단할 수 있는지 검토하라.
2. YES/NO 판단이 어렵더라도 질문이 명확하고 사건 해결과 무관하면 "관계없습니다"를 반환하라.
3. "질문이 모호합니다"는 정말로 예/아니오 판단이 불가능한 경우에만 마지막 수단으로 사용하라.

판정 기준:
- "맞습니다": 질문의 내용이 이야기의 사실과 직접적으로 일치할 때
- "아닙니다": 질문의 내용이 이야기의 사실과 직접적으로 일치하지 않을 때
- "관계없습니다": 질문 자체는 명확하지만 사건 해결과 무관한 주변 정보일 때
- "질문이 모호합니다": 질문이 너무 추상적이거나, 기준 없는 감정/정도 평가이거나, YES/NO 자체가 성립하지 않을 때만 사용한다

매우 중요한 지침:
- 질문의 의미가 이해 가능하면 절대 "질문이 모호합니다"로 보내지 말 것
- 단어가 조금 애매해도 문맥상 의미가 이해되면 반드시 "맞습니다" 또는 "아닙니다"를 우선 판단할 것
- "누군가", "어떤", "무언가" 같은 표현은 모호한 것으로 간주하지 말 것
- 가능하면 무조건 YES/NO를 먼저 판단할 것
- "질문이 모호합니다"는 최소한으로 사용할 것

"질문이 모호합니다"를 사용할 수 있는 경우:
- 질문이 너무 추상적일 때
- 기준이 없는 감정/정도 질문일 때
- YES/NO로 판단 자체가 불가능할 때

"관계없습니다"를 사용할 수 있는 경우:
- 질문은 명확하지만 사건 해결과 무관할 때

예시:
- 누군가 죽었나요? -> 맞습니다
- 남자는 식당에서 무언가를 먹었나요? -> 맞습니다
- 남자는 식당에서 스프를 먹었나요? -> 맞습니다
- 스프에 독이 들어 있었나요? -> 아닙니다
- 남자는 살해당했나요? -> 아닙니다
- 남자는 큰 충격을 받았나요? -> 질문이 모호합니다
- 중요한가요? -> 질문이 모호합니다
- 남자의 직업이 중요합니까? -> 관계없습니다
- 날씨가 중요합니까? -> 관계없습니다

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
                            "text": "너는 바다거북스프 질문 판정기다. 반드시 '맞습니다', '아닙니다', '질문이 모호합니다', '관계없습니다' 중 하나만 출력하고 설명은 절대 덧붙이지 마라. 가능하면 반드시 YES/NO를 먼저 판단하고, '질문이 모호합니다'는 마지막 수단으로만 사용하라.",
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
        # 변경: API 오류 시에도 로컬 규칙 판정으로 fallback
        return _classify_question_locally(scenario, answer_text, question_text)
