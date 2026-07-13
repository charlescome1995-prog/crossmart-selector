#!/usr/bin/env python3
"""
Station-side helper to push a JSON blob into crossmart-hub/data/<name>.json.

Usage (from any of the 5 stations, at end of their daily/weekly job):

    from push_to_hub import push_to_hub
    push_to_hub(
        filename="selection.json",         # or monitor.json / listing.json / ops.json / predictions.json
        payload={"schema_version":"v1", "generated_at":"...", "source":"crossmart-selector", "items":[...]},
        github_token=os.environ["GITHUB_TOKEN_HUB"],  # PAT with repo scope
    )

Environment vars accepted:
    GITHUB_TOKEN_HUB   - PAT with `repo` scope on crossmart-hub
    HUB_OWNER          - default: charlescome1995-prog
    HUB_REPO           - default: crossmart-hub
    HUB_BRANCH         - default: main

Requires only stdlib.
"""
from __future__ import annotations
import base64
import json
import os
import ssl
import urllib.request
import urllib.error

_HUB_OWNER = os.environ.get("HUB_OWNER", "charlescome1995-prog")
_HUB_REPO  = os.environ.get("HUB_REPO",  "crossmart-hub")
_HUB_BRANCH= os.environ.get("HUB_BRANCH","main")
_API = "https://api.github.com"

def _req(method: str, url: str, token: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "crossmart-hub-push")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    ctx = ssl.create_default_context()
    # local Windows sometimes needs revocation off
    ctx.check_hostname = True
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
            raw = r.read().decode("utf-8", "replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            j = json.loads(raw)
        except Exception:
            j = {"raw": raw}
        raise RuntimeError(f"GitHub API {e.code}: {j}") from e

def push_to_hub(
    filename: str,
    payload: dict,
    github_token: str | None = None,
    commit_message: str | None = None,
) -> dict:
    """PUT data/<filename> in crossmart-hub. Returns the API response."""
    token = github_token or os.environ.get("GITHUB_TOKEN_HUB")
    if not token:
        raise RuntimeError("push_to_hub: no GitHub token (arg or GITHUB_TOKEN_HUB env)")

    path = f"data/{filename}"
    content_b64 = base64.b64encode(
        json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    ).decode("ascii")

    # fetch current sha (if file exists)
    sha = None
    try:
        cur = _req(
            "GET",
            f"{_API}/repos/{_HUB_OWNER}/{_HUB_REPO}/contents/{path}?ref={_HUB_BRANCH}",
            token,
        )
        sha = cur.get("sha")
    except RuntimeError as e:
        if "404" not in str(e):
            raise

    body = {
        "message": commit_message or f"chore: update {path}",
        "content": content_b64,
        "branch":  _HUB_BRANCH,
    }
    if sha:
        body["sha"] = sha

    return _req(
        "PUT",
        f"{_API}/repos/{_HUB_OWNER}/{_HUB_REPO}/contents/{path}",
        token,
        body,
    )

if __name__ == "__main__":
    import argparse, sys, datetime
    ap = argparse.ArgumentParser()
    ap.add_argument("filename", help="e.g. selection.json / monitor.json")
    ap.add_argument("payload_file", help="path to local JSON to push")
    ap.add_argument("--source", default="unknown", help="crossmart-<station>")
    args = ap.parse_args()

    with open(args.payload_file, "r", encoding="utf-8") as f:
        payload = json.load(f)

    payload.setdefault("schema_version", "v1")
    payload["generated_at"] = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=8))
    ).isoformat(timespec="seconds")
    payload["source"] = args.source

    res = push_to_hub(args.filename, payload)
    print(f"pushed {args.filename}: commit={res.get('commit',{}).get('sha','?')[:8]}")
