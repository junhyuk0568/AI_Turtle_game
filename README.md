# AI Turtle Game

Claude API가 진행자가 되어 플레이어의 질문과 최종 정답을 판정하는 Django 기반 바다거북스프 게임입니다.

## 준비

- Python 3.13
- Claude API 키 (Claude Console에서 발급, 사용량만큼 과금)

```powershell
cd E:\AI_Turtle_game
uv venv .venv --python 3.13
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
Copy-Item .env.example .env
```

`.env`의 `ANTHROPIC_API_KEY`에 발급받은 키를 입력합니다. `.env`는 Git에 업로드되지 않습니다.

```env
ANTHROPIC_API_KEY=발급받은_API_키
GAME_CLAUDE_MODEL=claude-opus-5-5
GAME_CLAUDE_EFFORT=low
```

게임 설정 환경 변수는 `GAME_` 접두사를 씁니다. Claude Code 같은 도구가 설정하는 `CLAUDE_*` 변수와 겹치지 않게 하기 위해서입니다.

## 실행

```powershell
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py runserver
```

브라우저에서 `http://127.0.0.1:8000/`에 접속합니다.

## 테스트

```powershell
# API를 호출하지 않는 테스트 (무료)
.venv\Scripts\python.exe manage.py test game --exclude-tag=claude_api

# 실제 Claude API를 호출하는 통합 테스트 (과금)
.venv\Scripts\python.exe manage.py test game --tag=claude_api
```

`python manage.py test`는 둘 다 실행합니다. 통합 테스트는 API 키, 네트워크, 사용 한도에 문제가 있으면 실패합니다.

## 진행자(Claude) 동작

- 질문 판정, 최종 정답 판정, 관리자 판정 기준 생성은 항상 Claude API를 사용합니다.
- Claude는 구조화 출력(JSON 스키마)으로만 답합니다. 플레이어에게 보이는 문장은 사이트 템플릿이 만들기 때문에 진실이 문장으로 새어 나가지 않습니다.
- 질문 판정: `맞습니다` / `일부만 맞습니다` / `아닙니다` / `질문이 모호합니다` / `관계없습니다` 중 하나와 함께, 질문으로 밝혀진 정답 체크포인트 번호를 돌려줍니다.
- 진행자 답변은 짧게 표시합니다: 그렇습니다 / 그렇지 않습니다 / 그럴 수도 있습니다(일부만 맞거나 모호한 질문) / 관계없습니다.
- 직전 질문 기록(기본 8개, `GAME_QUESTION_HISTORY_LIMIT`)을 함께 보내 앞 질문을 이어서 묻는 질문을 이해하고 판정이 앞뒤로 엇갈리지 않게 합니다.
- 최종 정답 판정: 체크포인트별 충족 여부를 받고, 모든 체크포인트가 충족되어야 정답으로 처리합니다(최종 결정은 코드가 합니다).
- Claude가 안전 정책으로 판정을 거부하면 같은 요청을 다른 모델로 다시 시도하는 서버 측 대체 기능(`GAME_CLAUDE_REFUSAL_FALLBACK`)을 씁니다. 그래도 거부되면 "판정할 수 없는 질문" 안내를 보여줍니다. Haiku 계열처럼 이 기능을 지원하지 않는 모델을 쓰면 `False`로 설정하세요.
- API 키 누락이나 호출 실패 시 로컬 판정으로 숨기지 않고 화면에 오류를 표시합니다.
- 오류 로그에는 API 키를 기록하지 않습니다. 관리자 화면의 `AI usage logs`에서 호출 종류, 실제 응답한 모델, 토큰 수, 성공 여부를 확인할 수 있습니다.

## 게임 진행

- 같은 브라우저나 로그인 사용자가 진행 중인 문제를 다시 시작하면 기존 게임을 이어갑니다.
- 힌트는 아직 밝혀내지 못한 체크포인트의 힌트(`checkpoint_hints`)부터 공개하고, 다 쓰면 고정 힌트 1~3을 공개합니다. 최대 3개입니다.
- 정답 입력 창에는 정답에 포함되어야 하는 핵심 키워드(정답 체크포인트) 개수를 안내합니다.
- 정답이 부족하면 "핵심 N개 중 M개를 맞혔어요"처럼 맞힌 개수만 알려줍니다. 어떤 키워드인지는 알려주지 않습니다.
- 점수는 1,000점에서 시작하며 질문당 20점, 힌트당 150점이 차감됩니다.

## 판정 품질 관리

- 플레이어는 판정마다 `판정이 이상해요`를 눌러 신고할 수 있습니다.
- 관리자 화면 `Question logs`에서 신고된 질문만 걸러 보고, `테스트 질문으로 등록 (기대 판정: …)` 액션으로 테스트 질문에 추가합니다.
- 문제 편집 화면의 `테스트 질문 실행`으로 프롬프트나 모델을 바꾼 뒤 통과율을 비교합니다.
- `AI 판정 기준 생성`은 체크포인트 힌트까지 함께 만듭니다.

## GitHub Actions

저장소의 `Settings > Secrets and variables > Actions`에서 `ANTHROPIC_API_KEY` 저장소 비밀값을 등록해야 통합 테스트가 통과합니다.

## 배포

운영 배포 전에는 `.env.production.example`과 `DEPLOYMENT.md`를 확인하세요.

## 운영 전 확인

- `DJANGO_SECRET_KEY`를 안전한 값으로 변경
- `DJANGO_DEBUG=False` 설정
- `DJANGO_ALLOWED_HOSTS`에 실제 도메인 등록
- HTTPS 적용 후 `DJANGO_SECURE_SSL_REDIRECT`, 보안 쿠키, HSTS 설정 활성화
- 현재 `db.sqlite3`에는 기본 퍼즐 데이터가 있어 Git에서 계속 추적합니다. 실제 운영에서는 별도 데이터베이스로 이전하는 것을 권장합니다.
