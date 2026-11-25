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
GAME_CLAUDE_MODEL=claude-sonnet-5-5
GAME_CLAUDE_EFFORT=low
```

게임 설정 환경 변수는 `GAME_` 접두사를 씁니다. Claude Code 같은 도구가 설정하는 `CLAUDE_*` 변수와 겹치지 않게 하기 위해서입니다.

## 실행

```powershell
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py loaddata starter_puzzles
.venv\Scripts\python.exe manage.py createsuperuser
.venv\Scripts\python.exe manage.py runserver
```

`loaddata starter_puzzles`는 처음 한 번만 실행합니다. 기본 문제와 테스트 질문을 `game/fixtures/starter_puzzles.json`에서 불러옵니다. `db.sqlite3`는 Git에 올리지 않습니다.

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
- 질문은 페이지를 새로 고치지 않고 전송합니다. 질문이 바로 채팅에 올라가고, 진행자가 판정하는 동안 "…" 말풍선이 보입니다. 오류는 입력창 위에 표시되고 입력한 질문은 그대로 남습니다. 자바스크립트가 꺼져 있으면 기존처럼 페이지를 새로 고쳐 전송합니다.
- 힌트는 아직 밝혀내지 못한 체크포인트의 힌트(`checkpoint_hints`)부터 공개하고, 다 쓰면 고정 힌트 1~3을 공개합니다. 최대 3개입니다.
- 정답 입력 창에는 정답에 포함되어야 하는 핵심 키워드(정답 체크포인트) 개수를 안내합니다.
- 정답이 부족하면 "핵심 N개 중 M개를 맞혔어요"처럼 맞힌 개수만 알려줍니다. 어떤 키워드인지는 알려주지 않습니다.
- 점수는 1,000점에서 시작하며 질문당 20점, 힌트당 150점이 차감됩니다.
- 결과 화면에서 내가 한 질문과 진행자 답변을 순서대로 다시 볼 수 있습니다.
- 문제 목록에서 이미 푼 문제에는 `클리어 · 최고 N점`이 표시됩니다.

## 로그인 (구글)

- 게스트로도 플레이할 수 있고, 구글로 로그인하면 기록이 계정에 남습니다. 게스트로 하던 게임은 로그인할 때 계정으로 옮겨집니다.
- 처음 로그인하면 닉네임(2~12자, 한글·영문·숫자·`_`)을 정합니다. 다른 사람에게는 닉네임만 보이고 구글 이름과 이메일은 보이지 않습니다.
- 화면 아래의 `개인정보 처리방침`, `계정 삭제`(닉네임·연결 정보·게임 기록 삭제)를 제공합니다.
- `.env`의 `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`이 비어 있으면 로그인 버튼이 나타나지 않습니다.
- 구글 이메일이 이미 다른 계정(예: 관리자 계정)에 등록되어 있으면 보안상 자동 가입되지 않고 "로그인할 수 없어요" 안내가 나옵니다. 관리자 계정은 이메일을 비워 두고 플레이용 구글 계정과 분리하세요.
- Google Cloud Console의 OAuth 클라이언트(웹 애플리케이션)에 승인된 리디렉션 URI를 등록합니다.
  - 로컬: `http://localhost:8000/accounts/google/login/callback/`
  - 운영: `https://<도메인>/accounts/google/login/callback/`

## 남용 방지

- 게임은 만든 사람(같은 브라우저 세션, 또는 로그인한 사용자)만 열 수 있습니다. 다른 사람의 게임 번호로 접근하면 404가 됩니다.
- 유료 Claude 호출(질문, 정답 제출)은 IP당 1분에 `GAME_AI_CALLS_PER_MINUTE`회(기본 10)로 제한합니다. 0이면 제한하지 않습니다.
- 게임 하나에서 할 수 있는 질문은 `GAME_MAX_QUESTIONS_PER_GAME`개(기본 100)까지입니다.
- 같은 질문을 다시 보내면 Claude를 호출하지 않고 횟수도 세지 않습니다.

## 판정 품질 관리

- 플레이어는 판정마다 `판정이 이상해요`를 눌러 신고할 수 있습니다.
- 관리자 화면 `Question logs`에서 신고된 질문만 걸러 보고, `테스트 질문으로 등록 (기대 판정: …)` 액션으로 테스트 질문에 추가합니다.
- 문제 편집 화면의 `테스트 질문 실행`으로 프롬프트나 모델을 바꾼 뒤 통과율을 비교합니다. 질문마다 요금이 들기 때문에 확인 화면을 거쳐 실행됩니다.
- `AI 판정 기준 생성`은 먼저 확인 화면을 보여줍니다. **빈 칸만 채우기**는 직접 다듬은 항목을 그대로 두고, **모두 덮어쓰기**는 전부 새로 만듭니다.
- 체크포인트 힌트는 체크포인트와 줄 단위로 짝을 이루므로, 체크포인트를 새로 만들 때만 함께 생성됩니다.
- 목록 화면의 일괄 작업은 빈 칸만 채우며, 채울 칸이 없는 문제는 API를 호출하지 않고 건너뜁니다.

## 문제 옮기기 (정답 비공개)

기본 문제(`starter_puzzles`)만 공개 저장소에 있습니다. 직접 추가한 문제의 정답은 Git에 올리지 않고 비공개 파일로 옮깁니다.

```powershell
# 내 PC에서: 기본 문제를 뺀 나머지를 내보내기 (private/ 폴더는 Git에서 제외됨)
.venv\Scripts\python.exe manage.py export_puzzles private/puzzles.json --exclude-starter

# 서버에서: 파일을 비공개 경로로 복사한 뒤 확인하고 불러오기
python manage.py import_puzzles private/puzzles.json --dry-run
python manage.py import_puzzles private/puzzles.json
```

불러오기는 제목 기준으로 추가하거나 갱신하고, 테스트 질문도 함께 옮깁니다. 같은 파일을 여러 번 불러와도 중복되지 않습니다.

## GitHub Actions

저장소의 `Settings > Secrets and variables > Actions`에서 `ANTHROPIC_API_KEY` 저장소 비밀값을 등록해야 통합 테스트가 통과합니다.

## 배포

운영 배포 전에는 `.env.production.example`과 `DEPLOYMENT.md`를 확인하세요.

## 운영 전 확인

- `DJANGO_SECRET_KEY`를 안전한 값으로 변경
- `DJANGO_DEBUG=False` 설정
- `DJANGO_ALLOWED_HOSTS`에 실제 도메인 등록
- HTTPS 적용 후 `DJANGO_SECURE_SSL_REDIRECT`, 보안 쿠키, HSTS 설정 활성화
- 운영 데이터는 Git 밖의 별도 데이터베이스에 둡니다. 기본 문제는 fixture로 불러옵니다.
- 서버 여러 대 또는 여러 워커로 실행하면 요청 제한이 워커마다 따로 계산됩니다. Redis 같은 공유 캐시를 설정하세요.
- 리버스 프록시 뒤에서는 `REMOTE_ADDR`가 프록시 주소가 되므로, 실제 클라이언트 IP를 넘겨받도록 설정해야 요청 제한이 사용자별로 동작합니다.
