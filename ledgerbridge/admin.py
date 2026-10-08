"""Local operator commands; run on the host with filesystem access to the database."""
import argparse
import getpass
import sys

from .auth import Auth
from .core import Store, WorkflowError


def main():
    parser = argparse.ArgumentParser(description="Manage LedgerBridge users")
    parser.add_argument("--db", default="data/ledgerbridge.sqlite3")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add-user")
    add.add_argument("username")
    add.add_argument("--role", choices=("admin", "reviewer", "viewer"), default="reviewer")
    change = commands.add_parser("set-password")
    change.add_argument("username")
    disable = commands.add_parser("disable-user")
    disable.add_argument("username")
    args = parser.parse_args()
    auth = Auth(Store(args.db))
    try:
        if args.command == "disable-user":
            auth.set_active(args.username, False)
        else:
            password = getpass.getpass("Password: ")
            if args.command == "add-user":
                if password != getpass.getpass("Confirm password: "):
                    raise WorkflowError("Passwords did not match.")
                auth.add_user(args.username, password, args.role)
            else:
                auth.change_password(args.username, password)
    except WorkflowError as exc:
        parser.exit(1, f"Error: {exc}\n")
    print(f"{args.command} complete for {args.username}.")


if __name__ == "__main__":
    main()
