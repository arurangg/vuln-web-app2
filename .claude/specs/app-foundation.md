# Software Specification Document (Implementation Addendum)

## Vulnerable Web Application — Security Lab

**Version:** 1.0.0
**Status:** Implementation Addendum to PRD.md v1.0.0 and TDD.md v1.0.0
**Last Updated:** 2026-06-27

---

## 1. Scope

This document captures **implementation-level behavior only** — the runtime
mechanics, user-facing flows, and visual design needed to reproduce the
application exactly. It deliberately **omits** everything already specified in
the companion documents:

- **Product goals, audience, success metrics, roadmap** — see `docs/PRD.md`.
- **System architecture and three-layer design** — see `docs/TDD.md` §2.
- **Technology stack and versions** — see `docs/TDD.md` §2.2 / §11.1.
- **Vulnerability descriptions, root causes, and exploitation steps** — see
  `docs/PRD.md` §3.2 / §6 and `docs/TDD.md` §4.
- **Database schema definitions** — see `docs/TDD.md` §3.1.4 / §11.3.
- **Endpoint inventory** — see `docs/TDD.md` §3.1.2 / §11.4.

Where this document references a vulnerability, endpoint, or schema, it does so
only to describe *observable runtime behavior*, not to re-specify the artifact.
This addendum is authoritative for behavior and visual presentation; on conflict
with PRD/TDD for those concerns, this document governs.

---

## 2. Runtime Behavior

**RB-01 — Automatic database initialization on startup.** On application boot,
the schema-creation routine runs before the server begins accepting requests.
The `users` table is created if it does not already exist (idempotent
`CREATE TABLE IF NOT EXISTS`).

**RB-02 — Missing DB files recreated automatically.** If the SQLite database
file at the project root (`vulnerable_app.db`) is absent, it is created on the
next startup (or first connection). Deleting the file and restarting yields a
fresh, empty schema with no error.

**RB-03 — Data preserved across restarts.** Because persistence is a file on
disk, all user records survive process restarts. Stopping and restarting the
server without deleting the file retains every previously registered account.

**RB-04 — Static assets available after boot.** CSS and image assets mounted
under `/static/*` are served immediately once the server is up. No build step,
warm-up, or per-request preparation is required.

**RB-05 — Templates loaded from disk at request time with no caching.** Each
HTML template (`login.html`, `signup.html`, `dashboard.html`) is read fresh from
disk on every request that serves it. There is no in-memory template cache.
Editing a template file is reflected on the next request without restarting the
process (see BR-05).

**RB-06 — Dashboard content modified via runtime string substitution.** The
dashboard template is served by reading the raw file and performing a literal
string replacement of the `{{username}}` placeholder with the session username
before the response is returned. Substitution is plain text replacement, not a
templating engine, and applies no HTML escaping.

**RB-07 — Authentication state based solely on session presence.** A request is
considered authenticated if and only if the session contains a `user_id`. There
is no token validation, expiry check, or server-side session store lookup beyond
the signed cookie. Presence of the key is sufficient; absence denies access.

---

## 3. User Flows

### 3.1 Registration Flow

1. User navigates to `/signup`; the server reads and returns `signup.html`.
2. User completes four fields: username, email, password, confirm password.
3. On submit, **client-side JavaScript** compares password and confirm password.
   If they differ, an inline red error is shown beneath the confirm field and the
   form is **not** submitted (no page reload).
4. If the passwords match, the form performs a standard `POST /signup` with
   `application/x-www-form-urlencoded` body (username, email, password).
5. Server hashes the password (MD5), builds the INSERT via string concatenation,
   and executes it.
6. On success, the server returns a redirect to `/login`.
7. On a duplicate username (DB UNIQUE constraint violation), the server returns
   an HTML response indicating the username already exists (no redirect).

### 3.2 Login Flow

1. User navigates to `/login`; the server reads and returns `login.html`.
2. User enters username and password.
3. On submit, **client-side JavaScript intercepts** the submission and issues an
   asynchronous `fetch()` `POST /login` request (no full page navigation).
4. Server hashes the input password (MD5), builds the SELECT via string
   concatenation, and executes it.
5. **On success:** the session is populated with `user_id`, `username`, and
   `email`; the server responds in a form the client treats as success.
6. The client-side handler processes the response and **navigates the browser to
   `/welcome`** on success.
7. **On failure:** the server returns a JSON failure payload; the client
   displays the error inline in the error message area **without reloading**.

### 3.3 Dashboard Flow

1. User (or browser) issues `GET /welcome`.
2. Server checks the session for `user_id`.
3. If absent, the request is treated as unauthorized and redirected to `/login`.
4. If present, the server reads `dashboard.html` fresh from disk.
5. The server substitutes `{{username}}` with the session's `username` value.
6. The fully substituted HTML is returned as the response.

### 3.4 Logout Flow

1. User activates logout (`GET /logout`) from the dashboard.
2. Server clears all session data.
3. Server redirects the browser to `/login`.
4. After logout, any subsequent request to a protected resource (`/welcome`)
   finds no `user_id` in the session and is redirected back to `/login`;
   protected content is inaccessible.

---

## 4. Functional Requirements

**FR-01 — Session Management.** The application establishes a signed session
cookie on successful login storing `user_id`, `username`, and `email`. The
session is the sole carrier of authentication state and is destroyed on logout.

**FR-02 — Dynamic User Context.** The authenticated dashboard reflects the
current user by substituting the session `username` into the served page at
request time. The page is therefore per-user without any per-user stored
template.

**FR-03 — Route Protection.** `/welcome` is gated on the presence of `user_id`
in the session. Unauthenticated access redirects to `/login`. All other declared
routes are unprotected by design.

**FR-04 — Error Handling.** Registration surfaces a duplicate-username condition
as an HTML error response. Login surfaces invalid-credential conditions as a
JSON failure consumed by client-side script and rendered inline. Client-side
password mismatch is handled entirely in the browser before submission.

**FR-05 — Search Processing.** `/search` accepts a query parameter, matches it
against username and email, and returns the results embedded directly in an HTML
response. Input is interpolated into the HTML without escaping (observable
reflected-XSS behavior; see TDD §4).

**FR-06 — Persistence.** All registered users persist in the SQLite file across
requests and restarts. There is no in-memory-only data path for accounts.

---

## 5. Complete Visual Design Specification

This is the most detailed section. A compatible rebuild must reproduce the
following presentation exactly.

### 5.1 Global Design System

**Typography family (all text):**
`"Segoe UI", system-ui, -apple-system, sans-serif`

**Typography scale:**

| Role | Size | Weight |
|------|------|--------|
| Main titles | 2rem | 800 |
| Section titles | 1.4rem | 700 |
| Form titles | 1.7rem | 700 |
| Card titles | 0.95rem | 700 |
| Body text | 0.9rem | 400 |
| Labels | 0.82rem | 600 |
| Buttons | 1rem | 600 |

**Primary colors:**

| Token | Hex | Typical use |
|-------|-----|-------------|
| Indigo (deepest brand) | `#1a237e` | Primary buttons, headings, hero start |
| Indigo accent | `#3949ab` | Focus border, hero end, gradient mid |
| Indigo dark | `#283593` | Gradient stop (login panel) |
| Near-black slate | `#0f172a` | Deep text / dark surfaces |
| Page tint | `#eef1f8` | Dashboard body background |
| White | `#ffffff` | Form panels, cards, header |

**Text colors:**

| Hex | Use |
|-----|-----|
| `#1e293b` | Primary body text |
| `#475569` | Secondary text |
| `#64748b` | Muted / subtitle text |
| `#c5cae9` | Input borders, light-on-dark text |
| `#1a237e` | Emphasis / link text |

**Border radius:**

| Element | Radius |
|---------|--------|
| Inputs | 8px |
| Buttons | 8px |
| Cards | 10–12px |
| Status tags | 6px |

**Shadows:**

| Element | Shadow |
|---------|--------|
| Header | `0 2px 10px rgba(26,35,126,0.08)` |
| Card hover | `0 4px 16px rgba(26,35,126,0.10)` |
| Input focus glow | `0 0 0 3px rgba(57,73,171,0.12)` |

### 5.2 Shared Header

- Fixed position, **70px** height, full width.
- White background, subtle bottom border, header shadow (per table above).
- App title aligned to the **left**.
- Three organizational logos (PUCIT, Excaliat, FCCU / blue-logo-scl2) aligned to
  the **right**, each rendered at **54×54px**.

### 5.3 Login Page

- **Two-column 50/50 split-screen** layout.
- **Left panel:** deep blue gradient `#0d1b5e → #1a237e → #283593` containing:
  - a badge label,
  - a welcome heading,
  - a description paragraph,
  - a bullet list,
  - semi-transparent white circle decorative overlays at roughly **7% opacity**.
- **Right panel:** white background, with a centered form constrained to
  **max 400px** width containing, in order:
  - form title,
  - subtitle,
  - username field,
  - password field,
  - error message area,
  - full-width login button (`#1a237e` background, white text),
  - signup link.
- **Input styling:** `#f8f9ff` background, **1.5px solid `#c5cae9`** border;
  on focus the border changes to `#3949ab` with the blue focus glow.
- **Error messages:** light red background, red border, dark red text.

### 5.4 Signup Page

- **Identical structure** to the login page — same split-screen, same left-panel
  gradient, same decorative circles, same right-panel styling.
- **Form fields (in order):** username, email, password, confirm password.
- **Password mismatch** is shown as red text **below the confirm field**, with
  **no page reload**.

### 5.5 Dashboard

- **Body background:** `#eef1f8`.
- **Hero banner** directly beneath the fixed header, with gradient
  `#1a237e → #3949ab`:
  - **Left section:** title and subtitle.
  - **Right section:** the logged-in username and a semi-transparent white
    logout button.
- **Content area:** centered, **max 1100px** wide.
- **Mission card:** white card with a section title and description.
- **"Vulnerabilities to Discover" section:** introduced by an uppercase, small,
  bold header.
- **Vulnerability grid:** **two-column** grid of **8** cards. Each card is white,
  rounded, with a light border and a hover shadow, and contains a colored pill
  tag plus a description.

  **Tag colors:**

  | Tag | Color family |
  |-----|--------------|
  | SQLi | Yellow |
  | XSS | Red |
  | Session | Purple |
  | Brute | Orange |
  | Crypto | Green |
  | Exposed | Blue |
  | CSRF | Pink |

- **Process steps:** three step cards with `#1a237e` background, circular
  numbered badges, and white text — labeled **Find**, **Exploit**, **Mitigate**.

### 5.6 Responsive Behavior

- **Desktop:** auth pages render as the 50/50 split-screen.
- **Mobile:** auth panels **stack vertically**.
- **Dashboard cards:** collapse to a **single column**.
- **Process steps:** become a **vertical** stack.
- **Header logos:** shrink to fit narrower viewports.

---

## 6. Form Specifications

### 6.1 Registration Form

- **Four inputs:** username, email, password, confirm password.
- **Client-side password confirmation** runs before submission; a mismatch
  blocks submission and shows an inline error without reloading.
- On a valid match, submits via a standard form `POST /signup`.

### 6.2 Login Form

- **Two inputs:** username, password.
- Submitted via an **asynchronous `fetch()`** request, not a native form post.
- The client processes the success/failure response **dynamically without a page
  reload**: success navigates to `/welcome`; failure renders an inline error.

---

## 7. Validation Rules

### 7.1 Registration

- Username, email, and password are **required** (non-null/non-empty checked
  server-side; no format/length validation beyond presence).
- Confirm-password match is enforced **client-side** only.
- **Username uniqueness is enforced at the database level** via the `UNIQUE`
  constraint; there is no application-level pre-check (see BR-06).

### 7.2 Login

- Username and password are **required** (presence checked).
- No additional format validation; the values flow into the lookup as provided.

### 7.3 Search

- The query parameter is **required** for the search to execute and match
  against username and email.

---

## 8. Session State Model

**Stored values:** `user_id`, `username`, `email`.

**Lifecycle:**

1. **Creation** — after successful login authentication, all three values are
   written to the session.
2. **Usage** — during route access, `user_id` presence authorizes `/welcome`;
   `username` is read for dashboard substitution.
3. **Destruction** — on logout, the entire session is cleared, removing all
   stored values.

The session is carried in a signed cookie; it is the only authentication
mechanism.

---

## 9. Data Lifecycle Rules

- **Create:** a user record is created on successful registration.
- **No modification workflow:** there is no path to edit a user record after
  creation.
- **No deletion workflow:** there is no path to delete a user account.
- **No recovery workflow:** there is no password reset or account recovery path.

User records are effectively immutable once written (see BR-03).

---

## 10. Success Paths

- **SP-01 (Registration):** Valid, unique account data → record created →
  redirect to `/login`.
- **SP-02 (Login):** Valid credentials → session established (`user_id`,
  `username`, `email`) → client navigates to `/welcome`.
- **SP-03 (Dashboard):** Authenticated request → `dashboard.html` read →
  `{{username}}` substituted → page returned.
- **SP-04 (Logout):** Logout request → session cleared → redirect to `/login` →
  protected resources no longer accessible.

---

## 11. Alternate Paths

- **AP-01 (Duplicate username):** Registration with an existing username →
  DB UNIQUE violation → HTML error response indicating the username exists; no
  redirect, no record created.
- **AP-02 (Invalid credentials):** Login with non-matching username/password →
  JSON failure → inline error shown by client script; no session created.
- **AP-03 (Unauthorized dashboard):** `GET /welcome` without `user_id` in
  session → redirect to `/login`.
- **AP-04 (Empty search):** Search without the required query parameter → no
  matching execution / empty result behavior (no successful match listing).

---

## 12. Edge Cases

- **EC-01 (Existing username):** Re-registering a taken username fails at the DB
  constraint and surfaces the duplicate error.
- **EC-02 (Empty registration data):** Missing required registration fields are
  rejected by presence checks; no record is created.
- **EC-03 (Empty login data):** Missing required login fields are rejected by
  presence checks; no session is created.
- **EC-04 (Missing session):** A protected request with no session is redirected
  to `/login`.
- **EC-05 (Corrupted session):** A session cookie that fails signature
  verification is treated as absent → no `user_id` → redirect to `/login`.
- **EC-06 (Missing template):** If a template file cannot be read from disk, the
  request cannot be served normally (no cached fallback exists; see RB-05).
- **EC-07 (Missing database file):** An absent DB file is recreated empty on
  startup/connection; no users exist until re-registered (see RB-02).
- **EC-08 (Application restart):** After a restart without deleting the DB file,
  all previously registered users remain available (see RB-03).

---

## 13. Business Rules

- **BR-01 — Authentication depends on session.** Access is granted purely by the
  presence of `user_id` in the session; no other check applies.
- **BR-02 — Dashboard requires runtime substitution.** The dashboard is only
  correct after `{{username}}` is replaced at request time; the raw template is
  never the final response.
- **BR-03 — User records are immutable after creation.** No update or delete
  workflow exists for accounts.
- **BR-04 — Login and registration use different response formats.** Login
  responds with JSON consumed by client-side `fetch()`; registration responds
  with a redirect (success) or HTML (error).
- **BR-05 — Template updates are visible without restart.** Because templates are
  read from disk per request, edits take effect on the next request.
- **BR-06 — DB constraint is the primary uniqueness mechanism.** Username
  uniqueness is guaranteed by the database `UNIQUE` constraint rather than an
  application-level check.

---

## 14. Rebuild Requirements

A compatible implementation must reproduce all of the following observable
behaviors:

1. Initialize/recreate the SQLite schema automatically on startup (RB-01, RB-02).
2. Persist users to a file that survives restarts (RB-03).
3. Serve `/static/*` assets immediately after boot (RB-04).
4. Read templates from disk per request with no caching (RB-05).
5. Render the dashboard via literal `{{username}}` string substitution with no
   escaping (RB-06).
6. Authenticate solely on `user_id` session presence (RB-07).
7. Implement registration as form-post → create → redirect to `/login`, with
   client-side password-confirm gating (3.1, 6.1).
8. Implement login as async `fetch()` → JSON result → client navigation to
   `/welcome` on success, inline error on failure (3.2, 6.2).
9. Store `user_id`, `username`, `email` in the session on login and clear them on
   logout (§8).
10. Redirect unauthenticated `/welcome` requests to `/login` (FR-03, AP-03).
11. Reflect the search query into HTML without escaping (FR-05).
12. Reproduce the full visual design system, header, login/signup split-screen,
    and dashboard layout in §5 exactly (typography, colors, radii, shadows, tag
    colors, responsive collapse).
13. Enforce username uniqueness via the DB constraint (BR-06, 7.1).
14. Provide no modification, deletion, or recovery workflows (§9).

---

## 15. Acceptance Criteria

- **AC-01 (Registration):** Submitting valid, unique data creates a user and
  redirects to `/login`; a duplicate username shows an error and creates nothing.
- **AC-02 (Login):** Valid credentials establish a session and result in the
  client landing on `/welcome`; invalid credentials show an inline error with no
  reload and no session.
- **AC-03 (Dashboard):** An authenticated user sees their own username injected
  into the dashboard; the placeholder never appears literally.
- **AC-04 (Logout):** Logout clears the session, redirects to `/login`, and
  blocks subsequent `/welcome` access.
- **AC-05 (Search):** A query returns matching users in an HTML response and
  reflects the query input back into the page.
- **AC-06 (Persistence):** Users registered before a restart remain available
  after the restart; deleting the DB file yields an empty fresh schema.

---

## 16. Test Cases

| ID | Scenario | Steps | Expected Result |
|----|----------|-------|-----------------|
| TC-01 | Valid registration | POST `/signup` with unique username/email/password | User created; redirect to `/login` |
| TC-02 | Duplicate username | Register a username that already exists | HTML error; no new record |
| TC-03 | Password mismatch (client) | Enter differing password/confirm on signup | Inline red error; no submission, no reload |
| TC-04 | Missing registration field | Submit signup with an empty required field | Rejected by presence check; no record |
| TC-05 | Valid login | `fetch` POST `/login` with valid credentials | Session set; client navigates to `/welcome` |
| TC-06 | Invalid login | POST `/login` with wrong credentials | JSON failure; inline error; no reload; no session |
| TC-07 | Missing login field | Submit login with empty username or password | Rejected by presence check; no session |
| TC-08 | Authenticated dashboard | GET `/welcome` with `user_id` in session | Dashboard returned with username substituted |
| TC-09 | Unauthenticated dashboard | GET `/welcome` with no session | Redirect to `/login` |
| TC-10 | Logout clears session | GET `/logout` while authenticated | Session cleared; redirect to `/login` |
| TC-11 | Post-logout protection | GET `/welcome` after logout | Redirect to `/login` |
| TC-12 | Corrupted session cookie | Tamper session cookie, GET `/welcome` | Treated as unauthenticated; redirect to `/login` |
| TC-13 | Search with query | GET `/search?q=<term>` | HTML response listing matches; query reflected |
| TC-14 | Empty search | GET `/search` with no query parameter | No match listing produced |
| TC-15 | Persistence across restart | Register, restart process (keep DB file), GET data | Previously registered user still present |

---

## 17. Documentation Gaps

The following discrepancies exist between the PRD/TDD documents and the
implementation reality described here:

1. **Static asset caching.** PRD §4.1 states static assets "must be cached
   appropriately," but the implementation reads **templates** with no caching at
   all (RB-05), and the requirement gives no concrete cache policy for the
   served static files — the documents and the no-cache template behavior are in
   tension.

2. **Root path behavior.** TDD §3.1.2 lists `GET /` as "Redirect to signup,"
   while PRD §3 / user flows emphasize login as the primary entry. The
   destination of the root redirect (signup vs. login) is documented
   inconsistently across the two documents.

3. **Login response format.** The PRD describes login simply as
   "redirects to the protected dashboard" (FR-2), but the implementation returns
   a **JSON** result consumed by client-side `fetch()` and performs the
   navigation client-side (3.2, BR-04). The redirect-vs-JSON contract is not
   reconciled in the source documents.

4. **Username uniqueness enforcement.** The PRD states "Username must be unique"
   as a functional rule (FR-1) without specifying *where* it is enforced; the
   implementation relies solely on the **database `UNIQUE` constraint** with no
   application-level pre-check (BR-06), which the documents do not make explicit.
