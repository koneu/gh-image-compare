#!/usr/bin/env python3
"""Delete stale candidate/diff preview packages from Cloudsmith.

Every pipeline run pushes a short-lived "<component>-preview" and
"<component>-diff-preview" package (candidate/diff images for that run's
job summary) per component, alongside the real golden line
("<component>"). Those previews are only needed for as long as someone
might look at that run's summary, so this deletes any older than
--retention-days. A single "name ends with -preview" query catches both
kinds for every component without needing to know the component list -
golden packages (bare component names) never match it.
"""
import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API_BASE = "https://api.cloudsmith.io/v1"
PREVIEW_QUERY = "name:*-preview$"


def api_request(method: str, path: str, api_key: str):
    req = urllib.request.Request(f"{API_BASE}{path}", method=method, headers={"X-Api-Key": api_key})
    with urllib.request.urlopen(req) as resp:
        return resp.read(), resp.headers


def list_all_previews(owner: str, repo: str, api_key: str) -> list:
    """Cloudsmith paginates package listings (30/page by default); walk every
    page via X-Pagination-PageTotal or the list would silently stop at the
    first page's worth of matches."""
    packages = []
    page = 1
    while True:
        query = urllib.parse.quote(PREVIEW_QUERY)
        body, headers = api_request(
            "GET", f"/packages/{owner}/{repo}/?query={query}&page={page}&page_size=100", api_key
        )
        pkgs = json.loads(body)
        if not pkgs:
            break
        packages.extend(pkgs)
        page_total = int(headers.get("X-Pagination-PageTotal", "1"))
        if page >= page_total:
            break
        page += 1
    return packages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--retention-days", type=int, default=7)
    args = parser.parse_args()

    api_key = os.environ["CLOUDSMITH_API_KEY"]
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.retention_days)

    deleted = 0
    for pkg in list_all_previews(args.owner, args.repo, api_key):
        uploaded_at = datetime.fromisoformat(pkg["uploaded_at"].replace("Z", "+00:00"))
        if uploaded_at < cutoff:
            api_request("DELETE", f"/packages/{args.owner}/{args.repo}/{pkg['identifier_perm']}/", api_key)
            print(f"deleted {pkg['name']} {pkg['version']} (uploaded {pkg['uploaded_at']})")
            deleted += 1

    print(f"done: deleted {deleted} stale preview package(s), kept anything newer than {args.retention_days}d")


if __name__ == "__main__":
    main()
