#!/usr/bin/env python3
"""Local web UI for managing golden-images/components.json.

Run:
    python3 scripts/manage_images.py
Then open http://127.0.0.1:8765

Shows every tracked component/image with its current golden thumbnail
(if it's been promoted at least once) and a form to add a new one.
Adding an image doesn't touch main directly - main is protected, so
this opens a PR the same way any other change would, via a dedicated
branch. New (component, image) pairs need no golden yet: the pipeline's
existing bootstrap path (see compare_images.py) takes it from there on
the PR's first run.

Local-only by design (binds 127.0.0.1) - this shells out to git/gh
using whatever repo state currently exists on disk, so it refuses to
run if there are uncommitted changes rather than risk them.
"""
import http.server
import json
import re
import socketserver
import subprocess
import time
import urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPONENTS_PATH = REPO_ROOT / "golden-images" / "components.json"
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
HOST = "127.0.0.1"
PORT = 8765


def run(*args, check=True):
    return subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True, check=check)


def load_components() -> dict:
    return json.loads(COMPONENTS_PATH.read_text())


def load_manifest(component: str):
    path = REPO_ROOT / "golden-images" / f"{component}.manifest.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def image_id(component: str, image: str) -> str:
    return component if image == "default" else f"{component}-{image}"


def cs_version(image: str, version: str) -> str:
    return version if image == "default" else f"{image}-{version}"


def fetch_entitlement_token():
    try:
        result = run("gh", "api", "repos/koneu/gh-image-compare/actions/variables/CLOUDSMITH_ENTITLEMENT_TOKEN",
                      "--jq", ".value")
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


ENTITLEMENT_TOKEN = fetch_entitlement_token()


def golden_thumbnail_url(component: str, image: str, manifest: dict):
    if not manifest or not ENTITLEMENT_TOKEN:
        return None
    entry = manifest.get("images", {}).get(image)
    if not entry:
        return None
    version = cs_version(image, entry["current"]["version"])
    filename = entry["current"]["filename"]
    owner = manifest["cloudsmith_owner"]
    repo = manifest["cloudsmith_repo"]
    return f"https://dl.cloudsmith.io/{ENTITLEMENT_TOKEN}/{owner}/{repo}/raw/names/{component}/versions/{version}/{filename}"


def render_page(message: str = "", message_kind: str = "info") -> bytes:
    components = load_components()
    rows = []
    for component, images in components.items():
        manifest = load_manifest(component)
        for image in images:
            entry = manifest.get("images", {}).get(image) if manifest else None
            thumb_url = golden_thumbnail_url(component, image, manifest)
            thumb = f'<img src="{thumb_url}" width="80" alt="{image_id(component, image)}">' if thumb_url else "<em>no golden yet</em>"
            status = entry["current"]["version"] if entry else "not yet promoted"
            rows.append(f"""
                <tr>
                    <td>{thumb}</td>
                    <td><code>{component}</code></td>
                    <td><code>{image}</code></td>
                    <td><code>{image_id(component, image)}</code></td>
                    <td>{status}</td>
                </tr>""")

    existing_components = "".join(f'<option value="{c}">' for c in components)
    message_html = f'<p class="msg {message_kind}">{message}</p>' if message else ""

    return f"""<!doctype html>
<html>
<head>
<title>Golden images</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 760px; margin: 2rem auto; padding: 0 1rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
  th, td {{ border-bottom: 1px solid #ddd; padding: 0.5rem; text-align: left; vertical-align: middle; }}
  img {{ display: block; border-radius: 4px; border: 1px solid #ddd; }}
  form {{ display: flex; gap: 0.5rem; align-items: flex-end; flex-wrap: wrap; }}
  label {{ display: flex; flex-direction: column; font-size: 0.85rem; color: #555; }}
  input {{ padding: 0.4rem; font-size: 1rem; }}
  button {{ padding: 0.5rem 1rem; font-size: 1rem; cursor: pointer; }}
  .msg {{ padding: 0.75rem; border-radius: 4px; }}
  .msg.info {{ background: #e6f4ea; color: #1e4620; }}
  .msg.error {{ background: #fce8e6; color: #7c1e14; }}
  code {{ background: #f4f4f4; padding: 0.1rem 0.3rem; border-radius: 3px; }}
</style>
</head>
<body>
<h1>Golden images</h1>
{message_html}
<table>
  <tr><th>Golden</th><th>Component</th><th>Image</th><th>id</th><th>Version</th></tr>
  {"".join(rows) or "<tr><td colspan=5><em>components.json is empty</em></td></tr>"}
</table>

<h2>Add an image</h2>
<p>New or existing component; "default" is the special image name for a component's primary/only picture.</p>
<form method="POST" action="/add">
  <label>Component
    <input name="component" list="components" placeholder="e.g. button" required>
    <datalist id="components">{existing_components}</datalist>
  </label>
  <label>Image
    <input name="image" value="default" required>
  </label>
  <button type="submit">Add &amp; open PR</button>
</form>
</body>
</html>""".encode()


def add_image(component: str, image: str) -> str:
    """Returns a PR URL on success; raises ValueError with a user-facing message on failure."""
    if not NAME_RE.match(component) or not NAME_RE.match(image):
        raise ValueError("Component/image names must be lowercase letters, digits, and single hyphens only.")

    components = load_components()
    if image in components.get(component, []):
        raise ValueError(f"{component}/{image} is already tracked.")

    status = run("git", "status", "--porcelain").stdout
    if status.strip():
        raise ValueError("Working directory has uncommitted changes - commit or stash them before adding an image.")

    original_branch = run("git", "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    run("git", "fetch", "origin", "main")
    branch = f"add-image-{component}-{image}-{int(time.time())}"
    run("git", "checkout", "-b", branch, "origin/main")
    try:
        components = load_components()  # re-read against the fresh base
        components.setdefault(component, [])
        if image in components[component]:
            raise ValueError(f"{component}/{image} is already tracked.")
        components[component].append(image)
        COMPONENTS_PATH.write_text(json.dumps(components, indent=2) + "\n")

        run("git", "add", str(COMPONENTS_PATH.relative_to(REPO_ROOT)))
        run("git", "commit", "-m", f"Add {component}/{image} to tracked images")
        run("git", "push", "-u", "origin", branch)
        pr = run(
            "gh", "pr", "create",
            "--base", "main", "--head", branch,
            "--title", f"Add {component}/{image} to tracked images",
            "--body", f"Adds {component}/{image} via the local image-management tool. "
                      "No golden exists yet - the pipeline's bootstrap path establishes v1 once this is approved.",
        )
        return pr.stdout.strip()
    finally:
        run("git", "checkout", original_branch)


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # keep the terminal quiet; errors still surface in the page

    def _respond(self, body: bytes, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != "/":
            self._respond(b"Not found", 404)
            return
        self._respond(render_page())

    def do_POST(self):
        if self.path != "/add":
            self._respond(b"Not found", 404)
            return
        length = int(self.headers.get("Content-Length", 0))
        fields = urllib.parse.parse_qs(self.rfile.read(length).decode())
        component = fields.get("component", [""])[0].strip().lower()
        image = fields.get("image", [""])[0].strip().lower()
        try:
            pr_url = add_image(component, image)
            body = render_page(f'Added {component}/{image}. <a href="{pr_url}" target="_blank">{pr_url}</a>')
        except (ValueError, subprocess.CalledProcessError) as e:
            detail = e.stderr if isinstance(e, subprocess.CalledProcessError) else str(e)
            body = render_page(f"Failed to add {component}/{image}: {detail}", message_kind="error")
        self._respond(body)


def main() -> None:
    if ENTITLEMENT_TOKEN is None:
        print("Warning: couldn't fetch CLOUDSMITH_ENTITLEMENT_TOKEN via gh api - thumbnails will be blank.")
    with socketserver.TCPServer((HOST, PORT), Handler) as httpd:
        print(f"Serving on http://{HOST}:{PORT}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
