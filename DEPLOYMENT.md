# Deployment Checklist

## 1. GitHub Actions

- `OPENAI_API_KEY` repository secret is required.
- After adding or rotating the secret, rerun the failed `Tests` workflow.

## 2. Production Environment

Create a production `.env` from `.env.production.example`.

Required changes:

- `OPENAI_API_KEY`: production OpenAI API key
- `DJANGO_SECRET_KEY`: long random secret, never reused from local dev
- `DJANGO_ALLOWED_HOSTS`: production domain names
- `DJANGO_DEBUG=False`

HTTPS production settings:

- `DJANGO_SECURE_SSL_REDIRECT=True`
- `DJANGO_SESSION_COOKIE_SECURE=True`
- `DJANGO_CSRF_COOKIE_SECURE=True`
- `DJANGO_SECURE_HSTS_SECONDS=31536000`

Only enable HSTS after HTTPS works correctly on the final domain.

## 3. Database

The repository currently tracks `db.sqlite3` for the starter puzzle data.
For real production use, move to a server-managed database and keep production data outside Git.

## 4. Preflight Commands

```powershell
python manage.py migrate
python manage.py check --deploy
python manage.py test
```

`check --deploy` should only be clean when production environment values are loaded.

## 5. Run

```powershell
python manage.py runserver
```

For public hosting, run Django behind a production web server instead of the development server.
