"""Server-side users, sessions, and CSRF tokens for one organization."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
from dataclasses import dataclass

from .core import Store, WorkflowError

ITERATIONS = 600_000
SESSION_SECONDS = 8 * 60 * 60
LOCK_SECONDS = 15 * 60
ROLES = {"viewer", "reviewer", "admin"}
DUMMY_SALT = b"ledgerbridge-no-such-user"


@dataclass(frozen=True)
class Identity:
    username: str
    role: str
    csrf: str


def derive(password: str, salt: bytes, iterations: int = ITERATIONS) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)


class Auth:
    def __init__(self, store: Store):
        self.store = store
        with store.connect(write=True) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY, role TEXT NOT NULL, salt BLOB NOT NULL,
                password_hash BLOB NOT NULL, iterations INTEGER NOT NULL,
                failed INTEGER NOT NULL DEFAULT 0, locked_until INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY, username TEXT NOT NULL,
                csrf TEXT NOT NULL, expires_at INTEGER NOT NULL,
                FOREIGN KEY (username) REFERENCES users(username)
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at)")
            db.execute("PRAGMA user_version=2")

    def has_users(self) -> bool:
        with self.store.connect() as db:
            return db.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None

    def add_user(self, username: str, password: str, role: str):
        if not isinstance(username, str) or not re.fullmatch(r"[a-zA-Z0-9_.-]{3,60}", username):
            raise WorkflowError("Username must be 3–60 letters, numbers, dots, hyphens, or underscores.")
        if role not in ROLES:
            raise WorkflowError("Role must be viewer, reviewer, or admin.")
        if not isinstance(password, str) or not 15 <= len(password) <= 1024 or len(password.encode("utf-8")) > 4096:
            raise WorkflowError("Password must be 15–1024 characters (maximum 4096 UTF-8 bytes).")
        salt = secrets.token_bytes(32)
        digest = derive(password, salt)
        with self.store.connect(write=True) as db:
            if not db.execute("SELECT 1 FROM users LIMIT 1").fetchone() and role != "admin":
                raise WorkflowError("First user must be an admin.")
            try:
                db.execute("INSERT INTO users(username,role,salt,password_hash,iterations) VALUES(?,?,?,?,?)", (username, role, salt, digest, ITERATIONS))
                self.store.audit(db, None, "user_created", "local-operator", {"username": username, "role": role})
            except Exception as exc:
                if "UNIQUE constraint failed" in str(exc):
                    raise WorkflowError("Username already exists.", 409) from None
                raise

    def login(self, username: str, password: str):
        if not isinstance(username, str) or not isinstance(password, str) or len(username) > 60 or len(password.encode("utf-8")) > 4096:
            raise WorkflowError("Invalid credentials.", 401)
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM users WHERE username=? COLLATE BINARY", (username,)).fetchone()
        salt = row["salt"] if row else DUMMY_SALT
        iterations = row["iterations"] if row else ITERATIONS
        candidate = derive(password, salt, iterations)
        valid = bool(row and row["active"] and row["locked_until"] <= int(time.time()) and hmac.compare_digest(candidate, row["password_hash"]))
        if not valid:
            if row:
                with self.store.connect(write=True) as db:
                    db.execute("UPDATE users SET failed=failed+1, locked_until=CASE WHEN failed+1>=5 THEN ? ELSE 0 END WHERE username=?", (int(time.time()) + LOCK_SECONDS, username))
            raise WorkflowError("Invalid credentials.", 401)
        with self.store.connect(write=True) as db:
            token = secrets.token_urlsafe(48)
            csrf = secrets.token_urlsafe(32)
            db.execute("UPDATE users SET failed=0, locked_until=0 WHERE username=?", (username,))
            db.execute("DELETE FROM sessions WHERE expires_at <= ?", (int(time.time()),))
            db.execute("INSERT INTO sessions VALUES (?,?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), username, csrf, int(time.time()) + SESSION_SECONDS))
        return token

    def identity(self, token: str | None) -> Identity | None:
        if not token or not re.fullmatch(r"[a-zA-Z0-9_-]{40,100}", token):
            return None
        with self.store.connect() as db:
            row = db.execute("""SELECT u.username,u.role,s.csrf FROM sessions s
                JOIN users u ON u.username=s.username
                WHERE s.token_hash=? AND s.expires_at>? AND u.active=1""", (hashlib.sha256(token.encode()).hexdigest(), int(time.time()))).fetchone()
            return Identity(**dict(row)) if row else None

    def logout(self, token: str | None):
        if token:
            with self.store.connect(write=True) as db:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))

    def change_password(self, username: str, password: str):
        if not isinstance(password, str) or not 15 <= len(password) <= 1024 or len(password.encode("utf-8")) > 4096:
            raise WorkflowError("Password must be 15–1024 characters (maximum 4096 UTF-8 bytes).")
        salt = secrets.token_bytes(32)
        with self.store.connect(write=True) as db:
            if not db.execute("UPDATE users SET salt=?,password_hash=?,iterations=?,failed=0,locked_until=0 WHERE username=?", (salt, derive(password, salt), ITERATIONS, username)).rowcount:
                raise WorkflowError("User not found.", 404)
            db.execute("DELETE FROM sessions WHERE username=?", (username,))
            self.store.audit(db, None, "password_changed", "local-operator", {"username": username})

    def set_active(self, username: str, active: bool):
        with self.store.connect(write=True) as db:
            row = db.execute("SELECT role, active FROM users WHERE username=?", (username,)).fetchone()
            if not row:
                raise WorkflowError("User not found.", 404)
            if row["role"] == "admin" and row["active"] and not active:
                count = db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1").fetchone()[0]
                if count <= 1:
                    raise WorkflowError("Cannot disable the last active admin.")
            db.execute("UPDATE users SET active=? WHERE username=?", (int(active), username))
            if not active:
                db.execute("DELETE FROM sessions WHERE username=?", (username,))
            self.store.audit(db, None, "user_activation_changed", "local-operator", {"username": username, "active": active})
