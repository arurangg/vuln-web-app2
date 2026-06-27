"""HTTP route handlers.

WARNING -- INTENTIONAL VULNERABILITIES:
  * VULNERABILITY #2 (Stored XSS): /welcome substitutes the username into the
    dashboard HTML with a plain string replace and NO escaping.
  * VULNERABILITY #3 (Reflected XSS): /search interpolates the query parameter
    and result rows directly into the HTML response with NO escaping, and the
    SQL is built via string concatenation.
  * VULNERABILITY #6 (Exposed Database): /download/db serves the SQLite file
    with NO authentication.
Templates are read fresh from disk on every request (no caching). DO NOT add
escaping, sanitization, parameterized queries, or auth checks to the flagged
handlers.
"""

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app.db.session import DB_PATH, get_db
from app.services import auth_service

router = APIRouter()

# Resolve project paths relative to this file.
#   auth.py -> routes -> api -> app -> backend -> <project root>
PROJECT_ROOT = Path(__file__).resolve().parents[4]
TEMPLATES_DIR = PROJECT_ROOT / "frontend" / "templates"


def _read_template(name: str) -> str:
    """Read a template file from disk at request time (no caching)."""
    return (TEMPLATES_DIR / name).read_text(encoding="utf-8")


@router.get("/")
def index():
    """Redirect the root path to the signup page."""
    return RedirectResponse(url="/signup", status_code=302)


@router.get("/signup", response_class=HTMLResponse)
def signup_page():
    """Serve the signup form."""
    return HTMLResponse(_read_template("signup.html"))


@router.post("/signup")
def signup_post(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    """Process a registration (standard form POST -> redirect)."""
    return auth_service.signup(username, email, password)


@router.get("/login", response_class=HTMLResponse)
def login_page():
    """Serve the login form."""
    return HTMLResponse(_read_template("login.html"))


@router.post("/login")
def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    """Process a login (returns JSON for the fetch()-based client)."""
    return auth_service.login(request, username, password)


@router.get("/download/db")
def download_db():
    """VULNERABILITY #6: serve the database file with NO authentication."""
    return FileResponse(
        str(DB_PATH),
        media_type="application/octet-stream",
        filename="vulnerable_app.db",
    )


@router.get("/search", response_class=HTMLResponse)
def search_user(q: str = ""):
    """VULNERABILITY #3: Reflected XSS + SQL injection in user search.

    The query parameter is interpolated into both the SQL (string concatenation)
    and the HTML response with NO escaping.
    """
    try:
        # VULNERABILITY #1/#3: string-concatenated SQL with LIKE. DO NOT FIX.
        query = (
            "SELECT username, email FROM users WHERE username LIKE '%"
            + q + "%' OR email LIKE '%" + q + "%'"
        )
        conn = get_db()
        try:
            rows = conn.execute(query).fetchall()
        finally:
            conn.close()

        # VULNERABILITY #3: raw, unescaped interpolation of q and result rows.
        results = "".join("<li>" + row[0] + " (" + row[1] + ")</li>" for row in rows)
        html = (
            "<html><head><link rel='stylesheet' href='/static/css/styles.css'>"
            "</head><body><h2>Search results for: " + q + "</h2>"
            "<ul>" + results + "</ul></body></html>"
        )
        return HTMLResponse(html)
    except Exception as e:
        # Information leakage is intentional.
        return HTMLResponse("Search error: " + str(e), status_code=500)


@router.get("/welcome", response_class=HTMLResponse)
def welcome_page(request: Request):
    """Protected dashboard.

    Access requires a ``user_id`` in the session. VULNERABILITY #2: the username
    is substituted into the dashboard HTML via a plain string replace with NO
    escaping, so a stored XSS payload in a username executes here.
    """
    if "user_id" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    username = request.session.get("username", "")
    html = _read_template("dashboard.html")
    # VULNERABILITY #2: Stored XSS via unescaped substitution. DO NOT FIX.
    html = html.replace("{{username}}", username)
    return HTMLResponse(html)


@router.get("/logout")
def logout(request: Request):
    """Clear the session and redirect to login."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)
