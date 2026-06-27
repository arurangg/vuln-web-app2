# App Foundation — Implementation Plan

**Target application:** Vulnerable Web Application — Security Lab
**Source documents:** `docs/PRD.md`, `docs/TDD.md`, `.claude/specs/app-foundation.md`
**Status:** Implementation plan (build instructions)
**Last Updated:** 2026-06-27

---

> ## ⚠️ INTENTIONAL VULNERABILITIES — READ FIRST
>
> This application is an **educational security lab**. It contains **8 deliberate,
> exploitable vulnerabilities**. These flaws are **required features**, not bugs.
> A correct implementation **must reproduce every vulnerability exactly as
> specified**.
>
> **Non-negotiable rule:** All SQL in `auth_service.py` and `auth.py` MUST be
> built with **raw Python string concatenation**. Do **NOT** use parameterized
> queries, bound parameters (`?` placeholders), an ORM, or any escaping/
> sanitization. Do **NOT** HTML-escape user input on output. Do **NOT** add
> rate limiting, CSRF tokens, salts, or strong hashing. "Hardening" this app
> breaks its purpose.
>
> **This application must never be deployed to production or any
> publicly-reachable host.**

### Vulnerability map

| # | Vulnerability | Where it lives | Mechanism to preserve |
|---|---------------|----------------|-----------------------|
| 1 | SQL Injection | `auth_service.py` (login + signup) | String-concatenated SQL |
| 2 | Stored XSS | `auth.py` `/welcome` | `html.replace('{{username}}', username)`, no escaping |
| 3 | Reflected XSS | `auth.py` `/search` | `q` interpolated into HTML, no escaping |
| 4 | Session Hijacking | `main.py` | Hardcoded `SECRET_KEY = "super-secret-key-12345"` |
| 5 | Weak Password Storage | `core/security.py` | `hashlib.md5`, no salt |
| 6 | Exposed Database | `auth.py` `/download/db` | `FileResponse` of the DB, no auth check |
| 7 | No Rate Limiting | global | No throttling middleware anywhere |
| 8 | CSRF | all forms | No CSRF tokens / SameSite protection |

---

## Current repository state (baseline)

Greenfield. Already present:

- `docs/PRD.md`, `docs/TDD.md`, `docs/prompts/*`
- `.claude/specs/app-foundation.md` (the implementation spec)
- `frontend/static/images/` containing `PUCIT_Logo.png`, `excaliat-logo.png`,
  `blue-logo-scl2.png`
- Root `pyproject.toml` (`paart4`, uv-managed) + `uv.lock` + `.python-version` (3.12)

Does **not** exist yet (to be created): `backend/`, `frontend/templates/`,
`frontend/static/css/`, `vulnerable_app.db` (auto-created at runtime),
`CLAUDE.md`, `backend/pyproject.toml`.

> Note: a root `pyproject.toml` already exists from `uv init`. Per the prompt,
> Phase 1 adds a **separate** `backend/pyproject.toml` (hatchling). Having two
> pyproject files is intentional — the backend package is self-contained.

---

## Phase 1 — Project Structure

**Goal:** Lay down the directory skeleton and the backend package manifest.

### Backend files to create

| Path | Contents |
|------|----------|
| `backend/app/__init__.py` | empty |
| `backend/app/main.py` | entry point (Phase 6) |
| `backend/app/core/__init__.py` | empty |
| `backend/app/core/security.py` | password hashing (Phase 3) |
| `backend/app/db/__init__.py` | empty |
| `backend/app/db/session.py` | DB connection + init (Phase 2) |
| `backend/app/services/__init__.py` | empty |
| `backend/app/services/auth_service.py` | signup/login logic (Phase 4) |
| `backend/app/api/__init__.py` | empty |
| `backend/app/api/routes/__init__.py` | empty |
| `backend/app/api/routes/auth.py` | route handlers (Phase 5) |

### `backend/pyproject.toml`

- Build system: **hatchling** (`[build-system]` → `requires = ["hatchling"]`,
  `build-backend = "hatchling.build"`).
- `[project]` name e.g. `vulnerable-app-backend`, version `1.0.0`,
  `requires-python = ">=3.9"` (per PRD/TDD; the dev machine runs 3.12).
- Dependencies:
  - `fastapi>=0.109.0`
  - `uvicorn>=0.27.0`
  - `python-multipart>=0.0.6`
  - `itsdangerous>=2.0.0`
- Optional dev dependency group (e.g. `[project.optional-dependencies]` `dev`)
  containing `pytest`.
- Configure hatchling to target the `app` package (e.g.
  `[tool.hatch.build.targets.wheel] packages = ["app"]`).

### Frontend directories

- `frontend/templates/` → will hold `login.html`, `signup.html`, `dashboard.html`
- `frontend/static/css/` → will hold `styles.css`
- `frontend/static/images/` → already populated with the three logo files

**Acceptance:** all directories and empty `__init__.py` files exist; the backend
package imports cleanly once later phases add code.

---

## Phase 2 — Database Layer (`backend/app/db/session.py`)

**Goal:** A minimal SQLite access layer with automatic schema creation.

Implementation details:

- Resolve the database path to **`vulnerable_app.db` at the project root**
  (not inside `backend/`). Compute the project root relative to this file
  (e.g. walk up from `__file__`) so the path is stable regardless of launch CWD.
- `get_db() -> sqlite3.Connection`:
  - `sqlite3.connect(DB_PATH, check_same_thread=False)` (**vuln-adjacent
    simplification**: shared connection across threads).
  - Set `conn.row_factory = sqlite3.Row` for dict-style row access.
  - Return the connection.
- `init_db() -> None`:
  - Open a connection and execute:
    ```sql
    CREATE TABLE IF NOT EXISTS users (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        email    TEXT,
        password TEXT
    )
    ```
  - Commit and close.
  - Idempotent — safe to call on every startup. Recreates the file/schema if the
    DB was deleted (supports the "delete file to reset" workflow).

**Acceptance:** calling `init_db()` on a fresh checkout creates
`vulnerable_app.db` with the `users` table; data persists across restarts.

---

## Phase 3 — Security Utilities (`backend/app/core/security.py`)

**Goal:** Password hashing — deliberately weak (**vuln #5**).

- `hash_password(password: str) -> str`:
  - Return `hashlib.md5(password.encode()).hexdigest()`.
  - **No salt, no pepper, no KDF, no iteration count.** This is intentional.
- `verify_password(plain: str, hashed: str) -> bool`:
  - Return `hash_password(plain) == hashed` (compare MD5 hexdigests).

> Do not "upgrade" to bcrypt/argon2/scrypt or add a salt — VULN-5 requires MD5
> without salt so it is reversible via rainbow tables.

**Acceptance:** a known password hashes to its standard MD5 hexdigest;
`verify_password` round-trips.

---

## Phase 4 — Business Logic (`backend/app/services/auth_service.py`)

**Goal:** Signup and login logic. **All SQL here is string-concatenated
(vuln #1). Never parameterize.**

### `signup(...)`

- Receives `username`, `email`, `password` (FastAPI `Form(...)` params, passed
  from the route).
- Validate all three fields are present/non-empty (presence only — no format,
  length, or content validation).
- Hash the password via `hash_password()`.
- Build the INSERT with **string concatenation** (vuln #1):
  ```python
  query = ("INSERT INTO users (username, email, password) VALUES ('"
           + username + "', '" + email + "', '" + hashed + "')")
  ```
- Execute + commit via `get_db()`.
- On success: return `RedirectResponse(url="/login", status_code=302)`.
- On `sqlite3.IntegrityError` (UNIQUE constraint on `username`): return an
  HTML/error response with the message **"Username already exists"** (information
  leakage is intentional — no redirect, no record created).

### `login(request, ...)`

- Receives the `request` object plus `username`, `password` (`Form(...)`).
- Validate fields present.
- Hash the input password via `hash_password()`.
- Build the SELECT with **string concatenation** (vuln #1):
  ```python
  query = ("SELECT * FROM users WHERE username = '" + username
           + "' AND password = '" + hashed + "'")
  ```
- Execute via `get_db()` and fetch a matching row.
- **On match:** set session values and return a success JSON payload so the
  frontend JS can redirect itself:
  - `request.session["user_id"] = row["id"]`
  - `request.session["username"] = row["username"]`
  - `request.session["email"] = row["email"]`
  - `return JSONResponse({"success": True, "redirect": "/welcome"})`
- **On no match:** return
  `JSONResponse(status_code=401, content={"success": False, "error": "Invalid credentials"})`
  so the frontend shows the error inline **without a page reload**.

> ⚠️ Reminder: the concatenated `WHERE` clause is what enables
> `admin' OR '1'='1' --` authentication bypass. This is the single most important
> intentional flaw — do not touch it.

**Acceptance:** valid signup creates a user and redirects to `/login`; duplicate
username yields "Username already exists"; valid login sets the session + returns
success JSON; invalid login returns 401 JSON; the SQLi payload bypasses auth.

---

## Phase 5 — Route Handlers (`backend/app/api/routes/auth.py`)

**Goal:** All HTTP endpoints on a single `APIRouter`. Templates are read fresh
from disk on every request (no caching). Resolve `frontend/templates/*` paths
relative to the project root.

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/` | `RedirectResponse("/signup", status_code=302)` |
| GET | `/signup` | Read `signup.html` from disk → `HTMLResponse` |
| POST | `/signup` | Call `auth_service.signup(username, email, password)` |
| GET | `/login` | Read `login.html` from disk → `HTMLResponse` |
| POST | `/login` | Call `auth_service.login(request, username, password)` |
| GET | `/download/db` | `FileResponse("vulnerable_app.db")` — **NO auth** (vuln #6) |
| GET | `/search` | See below — **reflected XSS** (vuln #3) |
| GET | `/welcome` | See below — session-protected, **stored XSS** (vuln #2) |
| GET | `/logout` | `request.session.clear()` → `RedirectResponse("/login")` |

### `GET /download/db` (vuln #6)

- Return `FileResponse` of the project-root `vulnerable_app.db` with a download
  filename and `application/octet-stream`-style media type.
- **No session check, no auth, no authorization** — anyone can download it.

### `GET /search?q=` (vuln #3)

- Read query param `q`.
- Build SELECT via **string concatenation** with a `LIKE` clause against both
  `username` and `email`, e.g.:
  ```python
  query = ("SELECT username, email FROM users WHERE username LIKE '%"
           + q + "%' OR email LIKE '%" + q + "%'")
  ```
- Build an HTML response that **interpolates `q` and the result rows directly
  into the markup with no escaping** (e.g. `f"<li>{row[0]} ({row[1]})</li>"` and
  echoing the raw `q` back into the page). Return `HTMLResponse`.
- On exception, return an error string that **includes `str(e)`** (intentional
  information leakage).

### `GET /welcome` (session protection + vuln #2)

- If `"user_id"` **not** in `request.session` → `RedirectResponse("/login")`.
- Otherwise read `dashboard.html` from disk and perform
  `html = html.replace("{{username}}", username)` using the session username —
  **no HTML escaping** (so a stored `<script>`/`<img onerror>` username executes;
  vuln #2).
- Return `HTMLResponse(html)`.

### `GET /logout`

- `request.session.clear()` then `RedirectResponse("/login")`.

**Acceptance:** every route behaves as above; `/download/db` serves the file
unauthenticated; `/search` reflects `q`; `/welcome` redirects when logged out and
substitutes the username when logged in.

---

## Phase 6 — Application Entry Point (`backend/app/main.py`)

**Goal:** Wire the app together, configure the (weak) session, mount static
assets, init the DB, and run the server.

Implementation details, in order:

1. **`sys.path` fix (top of file, before importing `app.*`):** prepend the
   `backend/` directory to `sys.path` so the `app` package resolves regardless of
   launch directory — supports both `uv run backend/app/main.py` from the project
   root and `python app/main.py` from inside `backend/`.
2. Import FastAPI, `SessionMiddleware`, `StaticFiles`, the auth router, and
   `init_db`.
3. Create the FastAPI app instance.
4. Add session middleware with the **hardcoded weak secret** (vuln #4):
   ```python
   SECRET_KEY = os.environ.get("SECRET_KEY", "super-secret-key-12345")
   app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
   ```
   Default value must be the weak hardcoded key per the docs.
5. `app.include_router(auth_router)`.
6. Mount static files (paths resolved to project root):
   - `/static/css` → `frontend/static/css`
   - `/static/images` → `frontend/static/images`
7. Call `init_db()` at module level so the schema exists before serving.
8. Under `if __name__ == "__main__":` run uvicorn:
   ```python
   port = int(os.environ.get("PORT", "3001"))
   uvicorn.run(app, host="0.0.0.0", port=port)
   ```

> ⚠️ Do **not** add rate-limiting middleware (vuln #7) or CSRF middleware
> (vuln #8). Their absence is intentional.

**Acceptance:** `uv run backend/app/main.py` from the project root starts the
server on port 3001; `PORT`/`SECRET_KEY` env overrides work; the app boots with
the DB initialized and static assets reachable.

---

## Phase 7 — Frontend Templates (`frontend/templates/`)

All three pages share a **fixed header**: app title on the left, the three
organizational logos (`PUCIT_Logo.png`, `excaliat-logo.png`,
`blue-logo-scl2.png`) at 54×54px on the right. Reference CSS at
`/static/css/styles.css` and images under `/static/images/`. Follow the visual
design spec in `app-foundation.md` §5 exactly.

### `login.html`

- Split-screen layout: left deep-blue gradient panel (badge, welcome heading,
  description, bullet list, faint white circle overlays); right white panel with
  the login form (max 400px): title, subtitle, username field, password field,
  error message area, full-width login button, signup link.
- **JS via `fetch()`:** intercept submit, POST `/login` with `FormData`, parse
  the JSON response. On `data.success`, redirect with
  `window.location.href = data.redirect` (`/welcome`). On failure, show
  `data.error` inline in the error area **without reloading**.
- **No CSRF token** (vuln #8).

### `signup.html`

- Same split-screen layout, same gradient and decorative circles.
- Standard HTML form: `<form action="/signup" method="POST">` with four fields:
  `username`, `email`, `password`, `confirm_password`.
- **Client-side JS** validates that `password === confirm_password` before
  submit; on mismatch, show an inline error span beneath the confirm field and
  block submission (no reload). On match, allow the native POST.
- **No CSRF token** (vuln #8).

### `dashboard.html`

- `#eef1f8` body background; hero banner beneath the header with gradient
  `#1a237e → #3949ab`.
  - Left: "Security Vulnerability Lab" title + subtitle.
  - Right: **"Logged in as {{username}}"** (the `{{username}}` placeholder is
    substituted server-side, unescaped — vuln #2) + a semi-transparent white
    logout button linking to `/logout`.
- Content area (max 1100px, centered): a white mission card; a "Vulnerabilities
  to Discover" section header (uppercase, small, bold); a **2-column grid of 8
  vulnerability cards**, each with a colored pill tag + description; **3 process
  step cards** (`#1a237e` background, circular numbered badges, white text):
  **Find**, **Exploit**, **Mitigate**.
- Tag colors: SQLi=yellow, XSS=red, Session=purple, Brute=orange, Crypto=green,
  Exposed=blue, CSRF=pink.

**Acceptance:** pages render per spec; login uses async fetch + JSON; signup
validates password match client-side; dashboard shows the substituted username.

---

## Phase 8 — Styling (`frontend/static/css/styles.css`)

**Goal:** Complete, responsive stylesheet matching `app-foundation.md` §5.

Must implement:

- **Typography:** family `"Segoe UI", system-ui, -apple-system, sans-serif`;
  scale — main titles 2rem/800, section titles 1.4rem/700, form titles
  1.7rem/700, card titles 0.95rem/700, body 0.9rem/400, labels 0.82rem/600,
  buttons 1rem/600.
- **Colors:** primary `#1a237e`, `#3949ab`, `#283593`, `#0f172a`, `#eef1f8`,
  `#ffffff`; text `#1e293b`, `#475569`, `#64748b`, `#c5cae9`, `#1a237e`.
- **Radii:** inputs 8px, buttons 8px, cards 10–12px, status tags 6px.
- **Shadows:** header `0 2px 10px rgba(26,35,126,0.08)`; card hover
  `0 4px 16px rgba(26,35,126,0.10)`; input focus glow
  `0 0 0 3px rgba(57,73,171,0.12)`.
- **Header:** fixed, 70px, white, bottom border, header shadow; logos 54×54px.
- **Auth split-screen:** left gradient `#0d1b5e → #1a237e → #283593` + ~7%
  white circle overlays; right white form panel (max 400px). Inputs: `#f8f9ff`
  bg, 1.5px solid `#c5cae9` border; focus border `#3949ab` + glow. Errors: light
  red bg, red border, dark red text.
- **Dashboard:** hero gradient `#1a237e → #3949ab`; 2-col vulnerability grid;
  colored tags (per Phase 7); 3 dark process step cards with circular badges.
- **Responsive:** desktop split-screen; mobile stacks panels vertically;
  dashboard grid collapses to single column; process steps stack vertically;
  header logos shrink.

**Acceptance:** layout matches the spec on desktop and collapses correctly on
mobile widths.

---

## Phase 9 — `CLAUDE.md` (project root)

**Goal:** Codebase guide for future contributors/agents. Sections:

- **Project context:** intentionally vulnerable FastAPI/SQLite security lab;
  educational use only; never deploy.
- **Development commands:** install (`uv sync`), run
  (`uv run backend/app/main.py` from root, or `python app/main.py` from
  `backend/`), reset DB (delete `vulnerable_app.db` and restart), view DB
  contents (sqlite one-liner from TDD §6.4).
- **Architecture overview:** three layers — routes (`auth.py`) → service
  (`auth_service.py`) → DB (`session.py`); security util (`security.py`); entry
  (`main.py`); frontend templates + static.
- **Vulnerability map:** the 8 intentional vulns with file locations (mirror the
  table at the top of this plan) and a bold "do not fix" warning.
- **Frontend↔backend integration:** login = async `fetch()` → JSON →
  client-side redirect; signup = native form POST + client-side password match;
  dashboard = `{{username}}` server-side substitution; static mounts.
- **Security education context:** ethical-use guidelines, isolation requirement,
  reference to `docs/EXPLOITS.md` (future) and PRD/TDD safety sections.
- **Specification hierarchy:** `docs/PRD.md` → `docs/TDD.md` →
  `.claude/specs/app-foundation.md` (spec) → `.claude/specs/app-foundation-plan.md`
  (this plan).

**Acceptance:** `CLAUDE.md` exists at root and accurately reflects the build.

---

## Phase 10 — Testing & Validation

Primarily **manual** verification (pytest is an optional dev dependency; no test
suite is required for the foundation). Steps:

1. **Boot:** run `uv run backend/app/main.py` (from project root); confirm it
   starts on `http://localhost:3001` and `vulnerable_app.db` is created.
2. **Pages load:** `GET /` redirects to `/signup`; `/signup`, `/login` render;
   static CSS + logos load.
3. **Signup flow:** register a new user → redirect to `/login`; re-register the
   same username → "Username already exists".
4. **Login flow:** valid credentials → async fetch returns success JSON →
   browser lands on `/welcome` with the username shown; invalid credentials →
   inline error, no reload.
5. **Session protection:** visit `/welcome` while logged out → redirect to
   `/login`.
6. **Logout:** `/logout` clears the session and redirects to `/login`; `/welcome`
   is then inaccessible.
7. **Persistence:** restart the server (keep the DB file) → previously registered
   user still logs in; delete the DB file + restart → empty fresh schema.
8. **Vulnerability spot-checks (confirm flaws are present):**
   - `/download/db` downloads the SQLite file **without authentication** (#6).
   - `/search?q=<img src=x onerror=alert(1)>` reflects the payload unescaped (#3).
   - Login with `admin' OR '1'='1' --` bypasses authentication (#1).
   - A username containing `<script>`/`<img onerror>` executes on `/welcome` (#2).
   - DB stores MD5 hashes, not plaintext, and not salted (#5).

**Acceptance:** all functional flows pass and all 8 intentional vulnerabilities
are demonstrably present.

---

## Build order summary

1. Phase 1 — structure + `backend/pyproject.toml`
2. Phase 2 — `db/session.py`
3. Phase 3 — `core/security.py`
4. Phase 4 — `services/auth_service.py`
5. Phase 5 — `api/routes/auth.py`
6. Phase 6 — `main.py`
7. Phase 7 — templates
8. Phase 8 — `styles.css`
9. Phase 9 — `CLAUDE.md`
10. Phase 10 — manual validation

Backend (Phases 2→6) is buildable/runnable before the frontend; templates/CSS
(7→8) layer on top; docs + validation (9→10) finish the foundation.
