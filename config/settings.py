import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parent.parent

if load_dotenv:
    load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-change-this-in-production")

DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()]
SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "False").lower() == "true"
SESSION_COOKIE_SECURE = os.getenv("DJANGO_SESSION_COOKIE_SECURE", "False").lower() == "true"
CSRF_COOKIE_SECURE = os.getenv("DJANGO_CSRF_COOKIE_SECURE", "False").lower() == "true"
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "0"))


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "game",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "game.middleware.NicknameRequiredMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "game.context_processors.account_flags",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "ko-kr"

TIME_ZONE = "Asia/Seoul"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Database cache: rate-limit counters are shared by every worker. The table is
# created by a game migration (createcachetable), so `migrate` is enough.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "game_cache",
    }
}

# Login: Google accounts only (django-allauth). Players need no password here.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_LOGIN_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
SOCIALACCOUNT_ONLY = True
ACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_STORE_TOKENS = False
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": [{"client_id": GOOGLE_CLIENT_ID, "secret": GOOGLE_CLIENT_SECRET, "key": ""}]
        if GOOGLE_LOGIN_ENABLED
        else [],
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}
LOGIN_URL = "game:home"
LOGIN_REDIRECT_URL = "game:home"
ACCOUNT_LOGOUT_REDIRECT_URL = "game:home"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("GAME_CLAUDE_MODEL", "claude-sonnet-5-5")
CLAUDE_EFFORT = os.getenv("GAME_CLAUDE_EFFORT", "low")
CLAUDE_TIMEOUT_SECONDS = float(os.getenv("GAME_CLAUDE_TIMEOUT_SECONDS", "60"))
CLAUDE_MAX_RETRIES = int(os.getenv("GAME_CLAUDE_MAX_RETRIES", "2"))
# Env names use a GAME_ prefix so they never collide with Claude Code's own CLAUDE_* variables.
# Server-side refusal fallback (beta). Disable for models without it, e.g. claude-haiku-5-5.
CLAUDE_REFUSAL_FALLBACK = os.getenv("GAME_CLAUDE_REFUSAL_FALLBACK", "True").lower() == "true"
# max_tokens caps thinking plus the JSON answer.
CLAUDE_QUESTION_MAX_TOKENS = int(os.getenv("GAME_CLAUDE_QUESTION_MAX_TOKENS", "4000"))
CLAUDE_FINAL_ANSWER_MAX_TOKENS = int(os.getenv("GAME_CLAUDE_FINAL_ANSWER_MAX_TOKENS", "4000"))
CLAUDE_CRITERIA_MAX_TOKENS = int(os.getenv("GAME_CLAUDE_CRITERIA_MAX_TOKENS", "16000"))
QUESTION_HISTORY_LIMIT = int(os.getenv("GAME_QUESTION_HISTORY_LIMIT", "8"))
# Abuse and cost limits for billed Claude calls (questions and final answers); 0 disables each.
# The per-minute window is per client IP and lives in the database cache, so it holds
# across workers. Daily caps count per account when logged in, else per guest session.
AI_CALLS_PER_MINUTE = int(os.getenv("GAME_AI_CALLS_PER_MINUTE", "10"))
MAX_QUESTIONS_PER_GAME = int(os.getenv("GAME_MAX_QUESTIONS_PER_GAME", "100"))
DAILY_AI_CALLS_PER_ACCOUNT = int(os.getenv("GAME_DAILY_AI_CALLS_PER_ACCOUNT", "300"))
DAILY_AI_CALLS_PER_GUEST = int(os.getenv("GAME_DAILY_AI_CALLS_PER_GUEST", "50"))
# Service-wide daily spend stop, estimated from AIUsageLog tokens (local day, TIME_ZONE).
DAILY_AI_BUDGET_USD = float(os.getenv("GAME_DAILY_AI_BUDGET_USD", "5"))
# USD per million tokens; defaults are claude-sonnet-5-5 list prices (cache write = 5-minute TTL).
AI_PRICE_INPUT_PER_MTOK = float(os.getenv("GAME_AI_PRICE_INPUT_PER_MTOK", "2"))
AI_PRICE_CACHE_WRITE_PER_MTOK = float(os.getenv("GAME_AI_PRICE_CACHE_WRITE_PER_MTOK", "2.5"))
AI_PRICE_CACHE_READ_PER_MTOK = float(os.getenv("GAME_AI_PRICE_CACHE_READ_PER_MTOK", "0.1"))
AI_PRICE_OUTPUT_PER_MTOK = float(os.getenv("GAME_AI_PRICE_OUTPUT_PER_MTOK", "10"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "game.services": {
            "handlers": ["console"],
            "level": os.getenv("GAME_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
}
