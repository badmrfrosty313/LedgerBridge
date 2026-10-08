"""Consistent SQLite backups using the SQLite online backup API."""

import argparse
import os
import sqlite3
import tempfile
from pathlib import Path


def backup_database(source: str | Path, destination: str | Path) -> Path:
    source = Path(source)
    destination = Path(destination)
    if not source.is_file():
        raise ValueError(f"Database does not exist: {source}")
    if destination.exists():
        raise ValueError(f"Backup already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() == destination.resolve():
        raise ValueError("Backup destination must differ from source.")
    fd, temporary = tempfile.mkstemp(prefix=".ledgerbridge-backup-", suffix=".sqlite3", dir=destination.parent)
    try:
        os.chmod(temporary, 0o600)
        with os.fdopen(fd, "wb"):
            pass
        with sqlite3.connect(source) as src, sqlite3.connect(temporary) as dst:
            src.backup(dst)
            if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Backup integrity check failed.")
        os.replace(temporary, destination)
        return destination
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description="Create a checked SQLite snapshot")
    parser.add_argument("backup", choices=["backup"])
    parser.add_argument("--db", default="data/ledgerbridge.sqlite3")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        print(backup_database(args.db, args.out))
    except (ValueError, sqlite3.Error, OSError) as exc:
        parser.exit(1, f"Backup failed: {exc}\n")


if __name__ == "__main__":
    main()
