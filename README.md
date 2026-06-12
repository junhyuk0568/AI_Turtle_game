# AI Turtle Game

OpenAI API를 사용해 질문과 최종 정답을 판정하는 Django 기반 바다거북스프 게임입니다.

## 준비

- Python 3.13
- OpenAI API 키

```powershell
cd C:\AI_Turtle_game
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`의 `OPENAI_API_KEY`에 발급받은 키를 입력합니다. `.env`는 Git에 업로드되지 않습니다.

```env
OPENAI_API_KEY=발급받은_API_키
OPENAI_CLASSIFIER_MODEL=gpt-5-mini
```

## 실행

```powershell
python manage.py migrate
python manage.py runserver
```

브라우저에서 `http://127.0.0.1:8000/`에 접속합니다.

## 테스트

```powershell
python manage.py test
```

전체 테스트에는 실제 OpenAI API 호출과 출력값 검증이 포함됩니다. API 키, 네트워크, 사용 한도에 문제가 있으면 테스트가 실패합니다.

## OpenAI 동작

- 실제 게임의 질문 판정, 최종 정답 판정, 관리자 판정 기준 생성은 항상 OpenAI API를 사용합니다.
- API 호출은 기본 30초 제한과 최대 2회 재시도를 사용합니다.
- API 키 누락이나 호출 실패 시 로컬 판정으로 숨기지 않고 화면에 오류를 표시합니다.
- API 오류 로그에는 API 키를 기록하지 않습니다.

## GitHub Actions

저장소의 `Settings > Secrets and variables > Actions`에서 `OPENAI_API_KEY` 저장소 비밀값을 등록해야 자동 테스트가 통과합니다.

## 운영 전 확인

- `DJANGO_SECRET_KEY`를 안전한 값으로 변경
- `DJANGO_DEBUG=False` 설정
- `DJANGO_ALLOWED_HOSTS`에 실제 도메인 등록
- HTTPS 적용 후 `DJANGO_SECURE_SSL_REDIRECT`, 보안 쿠키, HSTS 설정 활성화
- 현재 추적 중인 `db.sqlite3`를 계속 공유할지 결정
