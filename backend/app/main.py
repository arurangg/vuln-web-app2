"""Application entry point.

Boots the FastAPI app for the intentionally vulnerable security lab.

WARNING -- INTENTIONAL VULNERABILITIES:
  * VULNERABILITY #4 (Session Hijacking): the session secret key is hardcoded
    and weak ("super-secret-key-12345"). DO NOT replace it with a strong random
    key.
  * VULNERABILITY #7 (No Rate Limiting): no throttling middleware is configured.
  * VULNERABILITY #8 (CSRF): no CSRF protection is configured.
"""

import os
import sys
from pathlib import Path

# --- sys.path fix -------------------------------------------------------------
# Add the backend/ directory to sys.path so the `app` package resolves no matter
# which directory the process is launched from (e.g. `uv run backend/app/main.py`
# from the project root, or `python app/main.py` from inside backend/).
#   main.py -> app -> backend
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from starlette.middleware.sessions import SessionMiddleware  # noqa: E402

from app.api.routes.auth import router as auth_router  # noqa: E402
from app.db.session import init_db  # noqa: E402

# Project root = backend/.. = <project root>
PROJECT_ROOT = BACKEND_DIR.parent
STATIC_DIR = PROJECT_ROOT / "frontend" / "static"

# VULNERABILITY #4: hardcoded weak session secret. DO NOT FIX.
SECRET_KEY = os.environ.get("SECRET_KEY", "super-secret-key-12345")

app = FastAPI(title="Vulnerable Web Application - Security Lab")

# Session middleware signs the cookie with the weak key above.
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Register all routes.
app.include_router(auth_router)

# Mount static assets (CSS + images).
app.mount("/static/css", StaticFiles(directory=str(STATIC_DIR / "css")), name="css")
app.mount(
    "/static/images",
    StaticFiles(directory=str(STATIC_DIR / "images")),
    name="images",
)

# Initialize the database schema on startup (creates the file if missing).
init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "3001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
