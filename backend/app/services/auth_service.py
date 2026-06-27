"""Authentication business logic.

WARNING -- INTENTIONAL VULNERABILITIES:
  * VULNERABILITY #1 (SQL Injection): every SQL statement in this module is
    built with raw Python string concatenation. This is DELIBERATE. Do NOT
    convert these to parameterized queries (``?`` placeholders), an ORM, or add
    any input escaping/sanitization -- that removes the educational flaw.
  * Passwords are hashed with unsalted MD5 (see core.security) -- VULN #5.
  * Error messages reveal whether a username already exists -- information
    leakage, intentional.
"""

from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.core.security import hash_password
from app.db.session import get_db


def signup(username: str, email: str, password: str):
    """Register a new user.

    Returns a RedirectResponse to /login on success, or an HTMLResponse error
    when the username already exists.
    """
    # Presence-only validation (no format/length checks -- intentional).
    if not username or not email or not password:
        return HTMLResponse("All fields are required", status_code=400)

    hashed = hash_password(password)

    # VULNERABILITY #1: SQL Injection via string concatenation. DO NOT FIX.
    query = (
        "INSERT INTO users (username, email, password) VALUES ('"
        + username + "', '" + email + "', '" + hashed + "')"
    )

    conn = get_db()
    try:
        conn.execute(query)
        conn.commit()
    except Exception:
        # UNIQUE constraint on username (or any other error) lands here.
        # Information leakage is intentional.
        return HTMLResponse("Username already exists", status_code=400)
    finally:
        conn.close()

    # Standard form POST -> redirect to the login page.
    return RedirectResponse(url="/login", status_code=302)


def login(request, username: str, password: str):
    """Authenticate a user.

    Returns a JSONResponse so the login page (which submits via fetch()) can
    handle success/failure client-side without a page reload. On success the
    session is populated and a redirect target is returned in the JSON body.
    """
    if not username or not password:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Username and password are required"},
        )

    hashed = hash_password(password)

    # VULNERABILITY #1: SQL Injection via string concatenation. DO NOT FIX.
    # This is what enables payloads like:  admin' OR '1'='1' --
    query = (
        "SELECT * FROM users WHERE username = '"
        + username + "' AND password = '" + hashed + "'"
    )

    conn = get_db()
    try:
        row = conn.execute(query).fetchone()
    finally:
        conn.close()

    if row:
        # Establish the session -- presence of user_id is the sole auth signal.
        request.session["user_id"] = row["id"]
        request.session["username"] = row["username"]
        request.session["email"] = row["email"]
        return JSONResponse({"success": True, "redirect": "/welcome"})

    return JSONResponse(
        status_code=401,
        content={"success": False, "error": "Invalid credentials"},
    )
