# CLAUDE.md

Guidance for working in this repository.

## Project context

This is the **Vulnerable Web Application — Security Lab**: an *intentionally
insecure* FastAPI + SQLite web app used for hands-on OWASP Top 10 security
education. It contains **8 deliberate, exploitable vulnerabilities**. These are
**required features, not bugs**.

> ⚠️ **Do NOT "fix" or harden the intentional vulnerabilities.** Do not convert
> SQL to parameterized queries, add input escaping/sanitization, replace MD5,
> add a salt, randomize the session secret, add auth to `/download/db`, or add
> rate-limiting / CSRF protection. Doing so destroys the educational purpose.
>
> ⚠️ **Never deploy this app to production or any publicly reachable host.**
> Run it only on localhost / isolated networks for authorized education.

## Development commands

```bash
# Install dependencies (from project root, uv-managed)
uv sync

# Run the app (works from the project root thanks to the sys.path fix in main.py)
uv run backend/app/main.py
# ...or from inside backend/:  python app/main.py

# App serves on http://localhost:3001  (PORT and SECRET_KEY are env-overridable)

# Reset the database: delete the file and restart (schema auto-recreates)
rm vulnerable_app.db

# Inspect the database
python -c "import sqlite3; c=sqlite3.connect('vulnerable_app.db'); [print(r) for r in c.execute('SELECT * FROM users')]; c.close()"
```

## Architecture overview

Three-layer separation of concerns:

- **Routes** — `backend/app/api/routes/auth.py` (HTTP handlers on one APIRouter)
- **Service / business logic** — `backend/app/services/auth_service.py`
- **Data layer** — `backend/app/db/session.py` (SQLite, `users` table)
- **Security util** — `backend/app/core/security.py` (MD5 hashing)
- **Entry point** — `backend/app/main.py` (FastAPI app, session middleware,
  static mounts, `init_db()`, uvicorn)
- **Frontend** — `frontend/templates/*.html` (read from disk per request, no
  caching) and `frontend/static/{css,images}`

The SQLite file `vulnerable_app.db` lives at the **project root** (so it is
trivially downloadable via `/download/db`).

## Vulnerability map

| # | Vulnerability | Location | Mechanism (do NOT fix) |
|---|---------------|----------|------------------------|
| 1 | SQL Injection | `services/auth_service.py` (login, signup) | String-concatenated SQL |
| 2 | Stored XSS | `api/routes/auth.py` `/welcome` | `html.replace('{{username}}', username)`, unescaped |
| 3 | Reflected XSS | `api/routes/auth.py` `/search` | `q` + rows interpolated into HTML, unescaped |
| 4 | Session Hijacking | `main.py` | Hardcoded `SECRET_KEY = "super-secret-key-12345"` |
| 5 | Weak Password Storage | `core/security.py` | `hashlib.md5`, no salt |
| 6 | Exposed Database | `api/routes/auth.py` `/download/db` | `FileResponse`, no auth |
| 7 | No Rate Limiting | global | No throttling middleware |
| 8 | CSRF | all forms | No CSRF tokens / SameSite |

## Frontend ↔ backend integration

- **Login** (`login.html`): submits via JS `fetch()` with `FormData` to
  `POST /login`; the server returns **JSON** (`{success, redirect}` or a 401 with
  `{error}`); the client redirects via `window.location.href` on success or
  shows the error inline without reloading.
- **Signup** (`signup.html`): standard `<form method="POST" action="/signup">`;
  client-side JS blocks submission if password ≠ confirm; the server responds
  with a **RedirectResponse** to `/login` on success.
- **Dashboard** (`dashboard.html`): server reads the template and substitutes
  `{{username}}` (unescaped) before responding; `/welcome` is gated on a
  `user_id` in the session.
- **Static assets** mounted at `/static/css` and `/static/images`.

## Security education context

- Educational, ethical use only — see `docs/PRD.md` §6 and `docs/TDD.md` §5 for
  safety guidelines and the legal disclaimer.
- Run isolated; never use real credentials/PII.
- Exploitation walkthroughs are intended to live in `docs/EXPLOITS.md`.

## Specification hierarchy

Authoritative documents, most general → most specific:

1. `docs/PRD.md` — product requirements
2. `docs/TDD.md` — technical design (architecture, stack, schema, endpoints)
3. `.claude/specs/app-foundation.md` — implementation addendum (behavior +
   visual design spec)
4. `.claude/specs/app-foundation-plan.md` — phase-by-phase build plan

This codebase implements that plan.
