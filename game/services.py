import json
import re

from django.conf import settings


LABEL_YES = "맞습니다"
LABEL_NO = "아닙니다"
LABEL_AMBIGUOUS = "질문이 모호합니다"
LABEL_IRRELEVANT = "관계없습니다"
LABELS = {LABEL_YES, LABEL_NO, LABEL_AMBIGUOUS, LABEL_IRRELEVANT}

FINAL_ANSWER_CORRECT = "정답입니다"
FINAL_ANSWER_INSUFFICIENT = "아직 부족합니다"

IRRELEVANT_KEYWORDS = [
    "신발",
    "색깔",
    "옷",
    "혈액형",
    "키",
    "머리색",
    "이름",
    "나이",
]
NO_KEYWORDS = [
    "살해",
    "타살",
    "죽임",
    "죽였",
    "독",
    "사고",
    "병",
    "강도",
]
YES_KEYWORDS = [
    "식당",
    "먹",
    "바다거북스프",
    "자살",
    "조난",
    "인육",
    "과거",
    "깨달",
    "충격",
]
AMBIGUOUS_KEYWORDS = [
    "이상한",
    "기분",
    "무언가",
    "뭔가",
    "왜",
    "어떻게",
    "무엇",
]
FALSE_PHRASE_KEYWORDS = [
    ("자살", "계획"),
    ("자살", "예정"),
    ("자살", "처음부터"),
    ("자살", "전부터"),
    ("먹기전", "자살"),
    ("먹기전에", "자살"),
]

FINAL_ANSWER_KEYWORD_GROUPS = [
    ("과거", "조난", "예전"),
    ("인육", "사람고기", "사람 고기"),
    ("바다거북스프", "수프", "스프"),
    ("깨달", "알게", "알았", "떠올"),
]
TOKEN_STOPWORDS = {
    "것",
    "그",
    "그는",
    "남자",
    "남자는",
    "사실",
    "정답",
    "핵심",
    "이유",
    "때문",
    "했다",
    "있다",
    "없다",
    "먹고",
    "먹었",
}
CRITERIA_KEYS = {
    "yes": "question_yes_facts",
    "no": "question_no_facts",
    "irrelevant": "question_irrelevant_facts",
    "ambiguous": "question_ambiguous_examples",
}
EMPTY_CRITERIA = {"yes": [], "no": [], "irrelevant": [], "ambiguous": []}


def _normalize_label(raw_text):
    if not raw_text:
        return LABEL_AMBIGUOUS

    cleaned = raw_text.strip()
    if cleaned in LABELS:
        return cleaned

    if LABEL_YES in cleaned:
        return LABEL_YES
    if LABEL_NO in cleaned:
        return LABEL_NO
    if LABEL_AMBIGUOUS in cleaned:
        return LABEL_AMBIGUOUS
    if LABEL_IRRELEVANT in cleaned:
        return LABEL_IRRELEVANT

    return LABEL_AMBIGUOUS


def _normalize_final_answer_label(raw_text):
    if not raw_text:
        return FINAL_ANSWER_INSUFFICIENT

    cleaned = raw_text.strip()
    if FINAL_ANSWER_CORRECT in cleaned:
        return FINAL_ANSWER_CORRECT
    if FINAL_ANSWER_INSUFFICIENT in cleaned:
        return FINAL_ANSWER_INSUFFICIENT

    return FINAL_ANSWER_INSUFFICIENT


def _compact(text):
    return re.sub(r"\s+", "", text or "").lower()


def _split_checkpoints(answer_checkpoints):
    if not answer_checkpoints:
        return []
    if isinstance(answer_checkpoints, str):
        return [line.strip() for line in answer_checkpoints.splitlines() if line.strip()]
    return [str(line).strip() for line in answer_checkpoints if str(line).strip()]


def _split_lines(value):
    if not value:
        return []
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    return [str(line).strip() for line in value if str(line).strip()]


def _normalize_question_criteria(question_criteria=None):
    if not question_criteria:
        return EMPTY_CRITERIA.copy()

    return {
        "yes": _split_lines(question_criteria.get("yes") or question_criteria.get("question_yes_facts")),
        "no": _split_lines(question_criteria.get("no") or question_criteria.get("question_no_facts")),
        "irrelevant": _split_lines(
            question_criteria.get("irrelevant") or question_criteria.get("question_irrelevant_facts")
        ),
        "ambiguous": _split_lines(
            question_criteria.get("ambiguous") or question_criteria.get("question_ambiguous_examples")
        ),
    }


def _meaningful_tokens(text):
    tokens = re.findall(r"[0-9A-Za-z가-힣]+", text or "")
    return [
        _normalize_token(token)
        for token in tokens
        if len(_normalize_token(token)) >= 2 and _normalize_token(token) not in TOKEN_STOPWORDS
    ]


def _normalize_token(token):
    normalized = (token or "").lower()
    for suffix in (
        "이었다",
        "였다",
        "에서",
        "으로",
        "에게",
        "의",
        "은",
        "는",
        "이",
        "가",
        "을",
        "를",
        "다",
    ):
        if len(normalized) > len(suffix) + 1 and normalized.endswith(suffix):
            return normalized[: -len(suffix)]
    return normalized


def _criteria_line_matches_question(line, question_text):
    line_tokens = set(_meaningful_tokens(line))
    question_tokens = set(_meaningful_tokens(question_text))
    if not line_tokens or not question_tokens:
        return False

    matched_tokens = line_tokens & question_tokens
    required_tokens = 1 if len(line_tokens) == 1 else max(2, round(len(line_tokens) * 0.6))
    return len(matched_tokens) >= required_tokens


def _classify_question_with_criteria(question_text, question_criteria=None):
    criteria = _normalize_question_criteria(question_criteria)
    ordered_criteria = [
        ("no", LABEL_NO),
        ("irrelevant", LABEL_IRRELEVANT),
        ("ambiguous", LABEL_AMBIGUOUS),
        ("yes", LABEL_YES),
    ]

    for key, label in ordered_criteria:
        if any(_criteria_line_matches_question(line, question_text) for line in criteria[key]):
            return label

    return None


def _classify_question_locally(question_text, question_criteria=None):
    """Small development fallback used when OpenAI is not configured."""
    criteria_label = _classify_question_with_criteria(question_text, question_criteria)
    if criteria_label:
        return criteria_label

    question = _compact(question_text)

    if any(keyword in question for keyword in IRRELEVANT_KEYWORDS):
        return LABEL_IRRELEVANT

    if any(all(keyword in question for keyword in keyword_group) for keyword_group in FALSE_PHRASE_KEYWORDS):
        return LABEL_NO

    if any(keyword in question for keyword in NO_KEYWORDS):
        return LABEL_NO

    if any(keyword in question for keyword in AMBIGUOUS_KEYWORDS):
        return LABEL_AMBIGUOUS

    if any(keyword in question for keyword in YES_KEYWORDS):
        return LABEL_YES

    return LABEL_AMBIGUOUS


def _checkpoint_is_matched(checkpoint, submitted_answer):
    compact_checkpoint = _compact(checkpoint)
    answer = _compact(submitted_answer)
    answer_tokens = set(_meaningful_tokens(submitted_answer))

    if compact_checkpoint and compact_checkpoint in answer:
        return True

    tokens = _meaningful_tokens(checkpoint)
    if not tokens:
        return False

    matched_tokens = sum(1 for token in tokens if _compact(token) in answer or token in answer_tokens)
    required_tokens = max(1, min(len(tokens), round(len(tokens) * 0.5)))
    return matched_tokens >= required_tokens


def _classify_final_answer_locally(submitted_answer, answer_checkpoints=None):
    checkpoints = _split_checkpoints(answer_checkpoints)
    if checkpoints:
        matched_checkpoints = sum(
            1 for checkpoint in checkpoints if _checkpoint_is_matched(checkpoint, submitted_answer)
        )
        if matched_checkpoints == len(checkpoints):
            return FINAL_ANSWER_CORRECT
        return FINAL_ANSWER_INSUFFICIENT

    answer = _compact(submitted_answer)
    matched_groups = 0
    for keyword_group in FINAL_ANSWER_KEYWORD_GROUPS:
        if any(_compact(keyword) in answer for keyword in keyword_group):
            matched_groups += 1

    if matched_groups >= 3:
        return FINAL_ANSWER_CORRECT
    return FINAL_ANSWER_INSUFFICIENT


def _format_question_criteria(question_criteria):
    criteria = _normalize_question_criteria(question_criteria)
    labels = [
        ("맞습니다 기준", "yes"),
        ("아닙니다 기준", "no"),
        ("관계없습니다 기준", "irrelevant"),
        ("질문이 모호합니다 예시", "ambiguous"),
    ]
    sections = []
    for title, key in labels:
        lines = criteria[key]
        body = "\n".join(f"- {line}" for line in lines) if lines else "- 없음"
        sections.append(f"{title}:\n{body}")
    return "\n\n".join(sections)


def classify_question(scenario, answer_text, question_text, question_criteria=None):
    criteria_label = _classify_question_with_criteria(question_text, question_criteria)
    if criteria_label:
        return criteria_label

    if not settings.OPENAI_API_KEY:
        return _classify_question_locally(question_text, question_criteria)

    try:
        from openai import OpenAI
    except ImportError:
        return _classify_question_locally(question_text, question_criteria)

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    prompt = f"""
너는 바다거북스프 게임의 질문 판정기다.
사용자의 질문을 보고 이야기의 진실과 비교하여 4개 중 하나만 반환한다.
설명하지 말고 결과만 출력한다.

반드시 아래 4개 중 정확히 하나만 출력하라:
맞습니다
아닙니다
질문이 모호합니다
관계없습니다

판정 기준:
- "맞습니다": 질문의 내용이 이야기의 사실과 직접적으로 일치할 때
- "아닙니다": 질문의 내용이 이야기의 사실과 직접적으로 일치하지 않을 때
- "질문이 모호합니다": 질문이 너무 넓거나 애매하거나, 예/아니오로 단정하기 어렵거나, 기준이 불명확할 때
- "관계없습니다": 질문 자체는 명확하지만 사건 해결과 거의 관련이 없는 주변 정보일 때
- 아래 문제별 판정 기준이 있으면 그것을 정답 원문보다 우선 참고한다.

이야기 시나리오:
{scenario}

이야기의 진실:
{answer_text}

문제별 판정 기준:
{_format_question_criteria(question_criteria)}

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

        return _normalize_label(getattr(response, "output_text", ""))
    except Exception as e:
        print("OPENAI ERROR:", e)
        return _classify_question_locally(question_text, question_criteria)


def _extract_json_object(text):
    if not text:
        return {}

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or start >= end:
            return {}
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return {}


def _normalize_generated_criteria(raw_criteria):
    return {
        "answer_checkpoints": _split_lines(raw_criteria.get("answer_checkpoints")),
        "question_yes_facts": _split_lines(raw_criteria.get("question_yes_facts")),
        "question_no_facts": _split_lines(raw_criteria.get("question_no_facts")),
        "question_irrelevant_facts": _split_lines(raw_criteria.get("question_irrelevant_facts")),
        "question_ambiguous_examples": _split_lines(raw_criteria.get("question_ambiguous_examples")),
    }


def _generate_puzzle_criteria_locally(scenario, answer_text):
    text = _compact(f"{scenario} {answer_text}")
    if all(keyword in text for keyword in ("바다거북스프", "자살")):
        return {
            "answer_checkpoints": [
                "남자는 과거 조난 상황에서 수프를 먹었다.",
                "그때 먹은 수프는 바다거북스프가 아니라 인육 수프였다.",
                "식당에서 진짜 바다거북스프를 먹고 과거의 진실을 깨달았다.",
            ],
            "question_yes_facts": [
                "남자는 식당에서 바다거북스프를 먹었다.",
                "남자는 집에 돌아온 뒤 자살했다.",
                "남자는 과거 조난 상황에서 수프를 먹은 적이 있다.",
                "남자는 식당의 수프 맛을 통해 과거의 진실을 깨달았다.",
            ],
            "question_no_facts": [
                "남자는 다른 사람에게 살해당했다.",
                "남자는 원래 자살 계획이 있었다.",
                "남자는 바다거북스프를 먹기 전부터 자살할 계획이었다.",
                "식당의 수프에는 독이 들어 있었다.",
                "식당에서 먹은 수프는 인육 수프였다.",
            ],
            "question_irrelevant_facts": [
                "남자의 신발 색깔",
                "남자의 이름",
                "남자의 옷 색깔",
                "식당의 위치",
            ],
            "question_ambiguous_examples": [
                "남자는 이상한 기분이 들었나요?",
                "남자에게 무언가 일이 있었나요?",
                "그 일이 중요했나요?",
            ],
        }

    return {
        "answer_checkpoints": _split_lines(answer_text),
        "question_yes_facts": [],
        "question_no_facts": [],
        "question_irrelevant_facts": [],
        "question_ambiguous_examples": [],
    }


def generate_puzzle_criteria(scenario, answer_text):
    if not settings.OPENAI_API_KEY:
        return _generate_puzzle_criteria_locally(scenario, answer_text)

    try:
        from openai import OpenAI
    except ImportError:
        return _generate_puzzle_criteria_locally(scenario, answer_text)

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    prompt = f"""
너는 바다거북스프 게임의 문제 설계 보조자다.
아래 시나리오와 정답을 바탕으로 게임 진행자가 질문 판정을 안정적으로 할 수 있는 기준을 생성한다.

반드시 JSON 객체 하나만 출력한다. 설명 문장은 쓰지 않는다.
각 배열에는 한국어 문장을 넣는다.

JSON 형식:
{{
  "answer_checkpoints": [],
  "question_yes_facts": [],
  "question_no_facts": [],
  "question_irrelevant_facts": [],
  "question_ambiguous_examples": []
}}

작성 기준:
- answer_checkpoints: 정답으로 인정하려면 반드시 포함되어야 하는 핵심 조건 3~5개
- question_yes_facts: 예/아니오 질문에 "맞습니다"로 답해야 하는 사실 5~8개
- question_no_facts: "아닙니다"로 답해야 하는 대표 오답 사실 5~8개
- question_irrelevant_facts: 사건 해결과 거의 무관한 주변 정보 4~6개
- question_ambiguous_examples: 너무 넓거나 기준이 애매한 질문 예시 3~5개
- question_no_facts에는 사용자가 헷갈리기 쉬운 함정 질문을 반드시 포함한다.

시나리오:
{scenario}

정답:
{answer_text}
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
                            "text": "너는 바다거북스프 문제의 판정 기준을 JSON으로 생성하는 도우미다. JSON 객체 하나만 출력한다.",
                        }
                    ],
                },
                {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
            ],
            max_output_tokens=1200,
        )
        generated = _normalize_generated_criteria(_extract_json_object(getattr(response, "output_text", "")))
        if any(generated.values()):
            return generated
    except Exception as e:
        print("OPENAI CRITERIA ERROR:", e)

    return _generate_puzzle_criteria_locally(scenario, answer_text)


def classify_final_answer(scenario, answer_text, submitted_answer, answer_checkpoints=None):
    if not submitted_answer.strip():
        return FINAL_ANSWER_INSUFFICIENT

    checkpoints = _split_checkpoints(answer_checkpoints)

    if not settings.OPENAI_API_KEY:
        return _classify_final_answer_locally(submitted_answer, checkpoints)

    try:
        from openai import OpenAI
    except ImportError:
        return _classify_final_answer_locally(submitted_answer, checkpoints)

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    prompt = f"""
너는 바다거북스프 게임의 정답 채점자다.
사용자의 정답 시도가 이야기의 핵심 진실을 충분히 설명했는지 판단한다.
설명하지 말고 아래 둘 중 하나만 출력한다.

정답입니다
아직 부족합니다

채점 기준:
- 표현이 정답 문장과 완전히 같을 필요는 없다.
- 아래 체크포인트가 모두 충족되면 "정답입니다"로 본다.
- 체크포인트 중 하나라도 빠지거나 일부 사실만 맞으면 "아직 부족합니다"로 본다.
- 사소한 표현 차이, 띄어쓰기, 문장 순서는 무시한다.
- 체크포인트가 비어 있으면 관리자가 등록한 정답의 핵심 원인과 인과관계를 기준으로 판단한다.

이야기 시나리오:
{scenario}

관리자가 등록한 정답:
{answer_text}

정답 체크포인트:
{chr(10).join(f"- {checkpoint}" for checkpoint in checkpoints) if checkpoints else "- 체크포인트 없음"}

사용자의 정답 시도:
{submitted_answer}
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
                            "text": "너는 바다거북스프 정답 채점자다. 반드시 '정답입니다' 또는 '아직 부족합니다' 중 하나만 출력한다.",
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
            max_output_tokens=60,
        )
        return _normalize_final_answer_label(getattr(response, "output_text", ""))
    except Exception as e:
        print("OPENAI FINAL ANSWER ERROR:", e)
        return _classify_final_answer_locally(submitted_answer, checkpoints)
