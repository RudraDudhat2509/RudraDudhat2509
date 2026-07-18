#!/usr/bin/env python3
"""Refresh the Selected work block of the profile README.

Renders, inside the WORK markers, a table of every repo tagged with the
"flagship" GitHub topic on github.com/RudraDudhat2509: project name and
description, both pulled straight from the API. No hand-written copy —
tag a repo `flagship`, it shows up here on the next scheduled run.

Same "flagship" topic convention drives the auto-detected tier on the
portfolio site (rudradudhat2509.github.io), so tagging a repo once keeps
both in sync.

Runs in CI on a schedule.
"""
import json
import os
import re
import urllib.request

USER = "RudraDudhat2509"
README = "README.md"
START = "<!-- WORK:START -->"
END = "<!-- WORK:END -->"
REPOS = f"https://api.github.com/users/{USER}/repos"


def gh_get(url):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def list_repos():
    repos, page = [], 1
    while True:
        batch = gh_get(f"{REPOS}?per_page=100&page={page}")
        repos.extend(batch)
        if len(batch) < 100:
            return repos
        page += 1


def build_block():
    repos = [
        r for r in list_repos()
        if not r["fork"] and not r["archived"] and "flagship" in (r.get("topics") or [])
    ]
    repos.sort(key=lambda r: r["pushed_at"], reverse=True)

    if not repos:
        return "*No projects tagged `flagship` yet.*"

    rows = "\n".join(
        f"| **[{r['name']}]({r['html_url']})** | {(r['description'] or '').strip()} |"
        for r in repos
    )
    return "| Project | What it does |\n|---|---|\n" + rows


def inject(block):
    with open(README, encoding="utf-8") as f:
        content = f.read()
    wrapped = f"{START}\n\n{block}\n\n{END}"
    new = re.sub(re.escape(START) + r".*?" + re.escape(END), wrapped, content, flags=re.DOTALL)
    if new == content:
        print("no change")
        return
    with open(README, "w", encoding="utf-8") as f:
        f.write(new)
    print("updated")


if __name__ == "__main__":
    inject(build_block())
