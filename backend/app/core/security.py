"""Password hashing utilities.

VULNERABILITY #5 (Weak Password Storage): passwords are hashed with MD5 and
NO SALT. This is INTENTIONAL for the security lab. MD5 is fast and unsalted
hashes are reversible via rainbow tables. Do NOT "upgrade" this to bcrypt/
argon2/scrypt or add a salt -- doing so removes the educational vulnerability.
"""

import hashlib


def hash_password(password: str) -> str:
    """Return the MD5 hexdigest of ``password`` (no salt -- VULNERABLE)."""
    return hashlib.md5(password.encode()).hexdigest()


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if ``plain`` hashes (MD5) to ``hashed``."""
    return hash_password(plain) == hashed
