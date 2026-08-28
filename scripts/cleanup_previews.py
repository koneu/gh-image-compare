#!/usr/bin/env python3
"""Delete stale candidate/diff preview packages from Cloudsmith.

Every pipeline run pushes a short-lived "output-preview" and
"output-diff-preview" package (candidate/diff images for that run's job
summary) alongside the real golden line ("output"). Those previews are
only needed for as long as someone might look at that run's summary, so
this deletes any older than --retention-days. The "output" package
(actual golden images) is never touched.
"""
import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API_BASE = "https://api.cloudsmith.io/v1"
PREVIEW_PACKAGE_NAMES = ["output-preview", "output-diff-preview"]


def api_request(method: str, path: str, api_key: str) -> bytes:
    req = urllib.request.Request(f"{API_BASE}{path}", method=method, headers={"X-Api-Key": api_key})
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--retention-days", type=int, default=7)
    args = parser.parse_args()

    api_key = os.environ["CLOUDSMITH_API_KEY"]
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.retention_days)

    deleted = 0
    for name in PREVIEW_PACKAGE_NAMES:
        query = f"name:^{name}$"
        body = api_request("GET", f"/packages/{args.owner}/{args.repo}/?query={urllib.parse.quote(query)}", api_key)
        for pkg in json.loads(body):
            uploaded_at = datetime.fromisoformat(pkg["uploaded_at"].replace("Z", "+00:00"))
            if uploaded_at < cutoff:
                api_request("DELETE", f"/packages/{args.owner}/{args.repo}/{pkg['identifier_perm']}/", api_key)
                print(f"deleted {name} {pkg['version']} (uploaded {pkg['uploaded_at']})")
                deleted += 1

    print(f"done: deleted {deleted} stale preview package(s), kept anything newer than {args.retention_days}d")


if __name__ == "__main__":
    main()
