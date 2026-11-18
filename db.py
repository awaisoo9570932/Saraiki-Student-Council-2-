import hashlib
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "users.db"


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
            """
        )


def hash_password(password: str, salt: bytes | None = None) -> str:
    if salt is None:
        salt = os.urandom(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"{salt.hex()}:{pwd_hash.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, hash_hex = stored.split(":")
        salt = bytes.fromhex(salt_hex)
        return hash_password(password, salt) == stored
    except Exception:
        return False


def create_user(full_name: str, email: str, password: str) -> tuple[bool, str]:
    full_name = full_name.strip()
    email = email.strip().lower()
    if not full_name:
        return False, "Please enter your full name."
    if "@" not in email or "." not in email:
        return False, "Please enter a valid email address."
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."

    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO users (full_name, email, password_hash) VALUES (?, ?, ?)",
                (full_name, email, hash_password(password)),
            )
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists."
    except Exception as exc:
        return False, f"Error creating account: {exc}"


def authenticate(email: str, password: str) -> dict | None:
    email = email.strip().lower()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, full_name, email, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    if row and verify_password(password, row[3]):
        return {"id": row[0], "full_name": row[1], "email": row[2]}
    return None
