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


def externally_merged_commit(item):
    """Some orgs (e.g. grpc, via Copybara) sync a PR's change into an
    internal repo and close the GitHub PR from a bot, without ever setting
    GitHub's native "merged" flag. `is:merged` search never finds these, and
    once closed they're not `is:open` either, so they'd silently vanish from
    this README with no human noticing. Detect the pattern (a bot-authored
    "closed" timeline event carrying a commit id) and verify that commit is
    actually reachable on the repo's default branch before trusting it.
    Returns the commit sha if verified, else None.
    """
    repo = repo_of(item)
    events = gh_get(
        f"https://api.github.com/repos/{repo}/issues/{item['number']}/timeline?per_page=100"
    )
    closing_commit = None
    for event in events:
        if event.get("event") == "closed" and event.get("commit_id"):
            closing_commit = event["commit_id"]
    if not closing_commit:
        return None
    default_branch = gh_get(f"https://api.github.com/repos/{repo}")["default_branch"]
    compare = gh_get(
        f"https://api.github.com/repos/{repo}/compare/{default_branch}...{closing_commit}"
    )
    if compare.get("status") in ("identical", "behind"):
        return closing_commit
    return None


def badge(label, message, color):
    enc = lambda s: s.replace("-", "--").replace("_", "__").replace(" ", "_")
    url = (f"https://img.shields.io/badge/{enc(label)}-{enc(message)}-{color}"
           f"?style=for-the-badge&labelColor={INK}")
    return f"![{label}]({url})"


def merged_upstream():
    """Every PR of mine that landed in someone else's repo."""
    merged = [i for i in search("is:merged") if is_external(i)]

    # Closed-but-not-natively-merged external PRs may still have actually
    # landed via an internal sync (see externally_merged_commit). Check each
    # one so real contributions like that don't quietly disappear.
    unmerged_closed = [i for i in search("is:unmerged") if is_external(i)]
    for item in unmerged_closed:
        if externally_merged_commit(item):
            merged.append(item)
    return merged


def build_counts():
    """(merged PRs, distinct repos) for the banner to stamp.

    Shared with render_dossier so the number on the artwork and the number in
    the table can never disagree.
    """
    merged = merged_upstream()
    return len(merged), len({repo_of(i) for i in merged})


def build_block():
    merged = merged_upstream()
    open_prs = [i for i in search("is:open") if is_external(i)]

    repos = sorted({repo_of(i) for i in merged})
    review_repos = sorted({repo_of(i) for i in open_prs})

    # The merged-PR and repo counts are stamped into the banner by
    # render_dossier, so repeating them here as badges would just say the same
    # thing twice on one screen.
    badges = badge("diffprompt", "LIVE ON PyPI", OLIVE)

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
