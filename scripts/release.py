"""Publish an immutable version tag and release after main's CI gates pass."""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate release metadata without network or credentials")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    match = re.search(r'^__version__ = "(\d+\.\d+\.\d+)"$', (root / "ledgerbridge/__init__.py").read_text(), re.M)
    if not match:
        raise SystemExit("Missing semantic release version")
    tag = "v" + match.group(1)
    notes = (root / "docs/RELEASE_NOTES.md").read_text(encoding="utf-8").strip()
    if not notes.startswith(f"# LedgerBridge {tag}\n") or not (root / "LICENSE").is_file():
        raise SystemExit("Release notes or license do not match this version")
    if args.check:
        print(f"Release metadata valid: {tag}")
        return
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    sha = os.environ.get("GITHUB_SHA", "")
    token = os.environ.get("GH_TOKEN", "")
    if os.environ.get("GITHUB_REF") != "refs/heads/main" or not re.fullmatch(r"[\w.-]+/[\w.-]+", repository) or not re.fullmatch(r"[a-f0-9]{40}", sha) or not token:
        raise SystemExit("Release publication requires the trusted main CI environment")

    def api(path, body=None):
        request = Request(f"https://api.github.com/repos/{repository}/{path}",
                          data=None if body is None else json.dumps(body).encode(),
                          headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                                   "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28"},
                          method="GET" if body is None else "POST")
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code == 404 and body is None:
                return None
            raise SystemExit(f"Release API failed (HTTP {exc.code}); no existing tag was moved") from None

    if api(f"releases/tags/{tag}") is not None:
        print(f"Release {tag} already exists; leaving it unchanged")
        return
    previous = api(f"git/ref/tags/{tag}")
    if previous is None:
        api("git/refs", {"ref": f"refs/tags/{tag}", "sha": sha})
    elif previous.get("object", {}).get("sha") != sha:
        raise SystemExit("Release tag already points to another commit; refusing to move it")
    release = api("releases", {"tag_name": tag, "target_commitish": sha, "name": f"LedgerBridge {tag}",
                               "body": notes, "draft": False, "prerelease": False})
    print(release["html_url"])


if __name__ == "__main__":
    main()
