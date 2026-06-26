#!/usr/bin/env python3
"""Refresh the live OSS proof block of the profile README.

Renders, inside the OSS markers:
  - stat badges (merged-upstream PR count, distinct repo count)
  - an "in review" line (open PRs into external repos)
  - a table of every merged PR into a repo USER does NOT own

Only counts upstream work. Anything in a repo USER owns is dropped.
Runs in CI on a schedule.
"""
import json
import os
import re
import urllib.request

USER = "RudraDudhat2509"
README = "README.md"
START = "<!-- OSS:START -->"
END = "<!-- OSS:END -->"
SEARCH = "https://api.github.com/search/issues"

INK = "1C1812"        # label bg
TERRACOTTA = "B5532F"
BRASS = "C8922F"
OLIVE = "3F5A36"


def gh_get(url):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def search(qualifier):
    items, page = [], 1
    q = f"author:{USER}+type:pr+{qualifier}"
    while True:
        data = gh_get(f"{SEARCH}?q={q}&per_page=100&page={page}")
        batch = data.get("items", [])
        items.extend(batch)
        if len(batch) < 100:
            return items
        page += 1


def repo_of(item):
    return item["repository_url"].split("/repos/", 1)[1]


def is_external(item):
    return repo_of(item).split("/", 1)[0].lower() != USER.lower()


def badge(label, message, color):
    enc = lambda s: s.replace("-", "--").replace("_", "__").replace(" ", "_")
    url = (f"https://img.shields.io/badge/{enc(label)}-{enc(message)}-{color}"
           f"?style=for-the-badge&labelColor={INK}")
    return f"![{label}]({url})"


def build_block():
    merged = [i for i in search("is:merged") if is_external(i)]
    open_prs = [i for i in search("is:open") if is_external(i)]

    repos = sorted({repo_of(i) for i in merged})
    review_repos = sorted({repo_of(i) for i in open_prs})

    badges = " ".join([
        badge("MERGED UPSTREAM", f"{len(merged)} PRs", TERRACOTTA),
        badge("PROD REPOS", str(len(repos)), BRASS),
        badge("diffprompt", "LIVE ON PyPI", OLIVE),
    ])

    review = ""
    if review_repos:
        chips = " · ".join(f"[{r.split('/')[1]}](https://github.com/{r})" for r in review_repos)
        review = f"\n\n**In review:** {chips}"

    rows = sorted(merged, key=lambda i: i.get("closed_at") or "", reverse=True)
    table_rows = "\n".join(
        f"| [{repo_of(i)}](https://github.com/{repo_of(i)}) "
        f"| [{i['title'].strip().replace('|', chr(92) + '|')}]({i['html_url']}) "
        f"| {(i.get('closed_at') or '')[:10]} |"
        for i in rows
    )
    table = "| Repo | Contribution | Merged |\n|---|---|---|\n" + table_rows

    return (
        f'<div align="center">\n\n{badges}{review}\n\n</div>\n\n{table}'
        if rows else f'<div align="center">\n\n{badges}\n\n</div>'
    )


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
