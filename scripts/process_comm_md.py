#!/usr/bin/env python3
"""
Detect communications/*.md files changed in the push event and send them to a Claude endpoint.
Stores response(s) under outputs/ and optionally creates GitHub issues.

Environment variables used:
- GITHUB_EVENT_PATH (provided by Actions automatically)
- GITHUB_REPOSITORY (owner/repo)
- GITHUB_TOKEN (for creating issues or committing)
- CLAUDE_API_URL (endpoint to send markdown to)
- CLAUDE_API_KEY (API key for Claude endpoint)
- ALLOWED_PUSHER (optional: GitHub username allowed to trigger processing)
- OUTPUT_TO_ISSUES ('true'/'false')
- COMMIT_OUTPUTS ('true'/'false')
"""
import os
import json
import sys
import requests
from pathlib import Path
from typing import List, Dict

GITHUB_EVENT_PATH = os.environ.get("GITHUB_EVENT_PATH")
REPO = os.environ.get("GITHUB_REPOSITORY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
CLAUDE_API_URL = os.environ.get("CLAUDE_API_URL", "https://api.anthropic.com/v1/messages")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
ALLOWED_PUSHER = os.environ.get("ALLOWED_PUSHER")
OUTPUT_TO_ISSUES = os.environ.get("OUTPUT_TO_ISSUES", "false").lower() == "true"
COMMIT_OUTPUTS = os.environ.get("COMMIT_OUTPUTS", "false").lower() == "true"

if not GITHUB_EVENT_PATH or not REPO:
    print("GITHUB_EVENT_PATH and GITHUB_REPOSITORY must be set (this script is designed for GitHub Actions).")
    sys.exit(1)

def load_event() -> dict:
    with open(GITHUB_EVENT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def collect_changed_markdowns(event: dict) -> List[str]:
    files = []
    for commit in event.get("commits", []):
        for key in ("added", "modified"):
            for fname in commit.get(key, []):
                if fname.startswith("communications/") and fname.lower().endswith(".md"):
                    files.append(fname)
    return sorted(set(files))

def verify_pusher(event: dict) -> bool:
    if not ALLOWED_PUSHER:
        return True
    pusher = event.get("pusher", {}).get("name") or event.get("pusher", {}).get("username")
    if pusher:
        return pusher == ALLOWED_PUSHER
    return False

def read_file_content(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def send_to_claude(markdown: str, filename: str) -> Dict:
    """
    Call Anthropic Claude API with the markdown content.
    """
    if not CLAUDE_API_KEY:
        raise RuntimeError("CLAUDE_API_KEY must be set as a secret.")
    
    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2048,
        "messages": [{
            "role": "user",
            "content": f"Process this communication markdown file named {filename} and return structured instructions and next steps:\n\n{markdown}"
        }]
    }

    resp = requests.post(CLAUDE_API_URL, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()

def create_github_issue(title: str, body: str):
    if not GITHUB_TOKEN:
        print("GITHUB_TOKEN not set - cannot create issue.")
        return None
    api = f"https://api.github.com/repos/{REPO}/issues"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    data = {"title": title, "body": body}
    r = requests.post(api, json=data, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

def commit_outputs(files: List[Path], commit_message: str = "Add Claude outputs for communications"):
    import subprocess
    subprocess.check_call(["git", "config", "user.name", "github-actions"])
    subprocess.check_call(["git", "config", "user.email", "github-actions@users.noreply.github.com"])
    subprocess.check_call(["git", "add"] + [str(p) for p in files])
    subprocess.check_call(["git", "commit", "-m", commit_message])
    subprocess.check_call(["git", "push", "origin", "HEAD:main"])

def main():
    event = load_event()

    if not verify_pusher(event):
        print("Pusher verification failed (ALLOWED_PUSHER mismatch) - exiting.")
        sys.exit(0)

    changed = collect_changed_markdowns(event)
    if not changed:
        print("No communications/*.md files changed in the push.")
        return

    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)

    files_to_commit = []
    for fname in changed:
        print(f"Processing {fname} ...")
        if not Path(fname).is_file():
            print(f"File {fname} not found in checkout - skipping.")
            continue
        md = read_file_content(fname)
        try:
            resp = send_to_claude(md, Path(fname).name)
        except Exception as e:
            print(f"Error sending to Claude endpoint: {e}")
            resp = {"error": str(e)}

        outpath = outputs_dir / (Path(fname).stem + ".json")
        with open(outpath, "w", encoding="utf-8") as f:
            json.dump({
                "source_file": fname,
                "claude_response": resp
            }, f, indent=2)
        files_to_commit.append(outpath)

        if OUTPUT_TO_ISSUES:
            title = f"Claude processing result for {fname}"
            body = f"Source file: `{fname}`\n\n```json\n{json.dumps(resp, indent=2)}\n```"
            try:
                issue = create_github_issue(title, body)
                print(f"Created issue: {issue.get('html_url')}")
            except Exception as e:
                print(f"Failed to create issue: {e}")

    if COMMIT_OUTPUTS and files_to_commit:
        try:
            commit_outputs(files_to_commit)
            print("Committed outputs back to the repo.")
        except Exception as e:
            print(f"Failed to commit outputs: {e}")

if __name__ == "__main__":
    main()
