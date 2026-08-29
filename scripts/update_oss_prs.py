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
EMAIL = "contact.rdudhat@gmail.com"
# PRs someone else opened that I co-authored a commit on. `author:` search only
# ever matches the person who opened the PR, so these can't be discovered and
# have to be named. Each one is still verified before it's counted.
CO_AUTHORED = [
    "Arize-ai/phoenix#14361",
]
# PRs where a maintainer folded my fix into a bigger consolidation PR instead
# of merging mine directly, so neither externally_merged_commit() (no
# reachable commit) nor co_authored_upstream() (no trailer) can verify them
# from the API. Asserted by hand -- checked once against the consolidation
# PR's diff -- and each entry names the PR that actually carries the change.
MANUAL = [
    {
        "repo": "567-labs/instructor",
        "number": 2451,
        "title": "fix(openai): copy schema before strict mutation to prevent lru_cache poisoning",
        "merged_at": "2026-07-29T04:34:52Z",
        "folded_into": 2495,
    },
]
README = "README.md"
START = "<!-- OSS:START -->"
END = "<!-- OSS:END -->"
SEARCH = "https://api.github.com/search/issues"

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


def co_authored_upstream():
    """Merged PRs from CO_AUTHORED, shaped like a search result.

    Listing a PR here is a claim, not proof, so each one is checked against the
    PR's own commits: it must be merged and must carry a Co-authored-by trailer
    for EMAIL. A wrong number or a PR I didn't actually work on is dropped
    rather than silently inflating the count.
    """
    items = []
    for ref in CO_AUTHORED:
        repo, _, number = ref.partition("#")
        pr = gh_get(f"https://api.github.com/repos/{repo}/pulls/{number}")
        if not pr.get("merged_at"):
            continue
        commits = gh_get(
            f"https://api.github.com/repos/{repo}/pulls/{number}/commits?per_page=100"
        )
        trailer = f"<{EMAIL}>".lower()
        mine = any(
            line.lower().startswith("co-authored-by:") and trailer in line.lower()
            for commit in commits
            for line in commit["commit"]["message"].splitlines()
        )
        if not mine:
            continue
        items.append({
            "title": pr["title"],
            "html_url": pr["html_url"],
            "repository_url": f"https://api.github.com/repos/{repo}",
            "closed_at": pr["merged_at"],
            "number": pr["number"],
        })
    return items


def manual_upstream():
    """Merged PRs from MANUAL, shaped like a search result.

    Nothing here is API-verifiable (that's why it's manual), so each entry
    carries the PR that actually landed the change for a human to spot-check.
    """
    items = []
    for m in MANUAL:
        pr_url = f"https://github.com/{m['repo']}/pull/{m['number']}"
        folded_url = f"https://github.com/{m['repo']}/pull/{m['folded_into']}"
        items.append({
            "title": m["title"],
            "html_url": pr_url,
            "repository_url": f"https://api.github.com/repos/{m['repo']}",
            "closed_at": m["merged_at"],
            "number": m["number"],
            "suffix": f"(folded into [#{m['folded_into']}]({folded_url}))",
        })
    return items


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

    merged.extend(i for i in co_authored_upstream() if is_external(i))
    merged.extend(i for i in manual_upstream() if is_external(i))
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

    review = ""
    if review_repos:
        chips = " · ".join(f"[{r.split('/')[1]}](https://github.com/{r})" for r in review_repos)
        review = f"**In review:** {chips}"

    rows = sorted(merged, key=lambda i: i.get("closed_at") or "", reverse=True)
    table_rows = "\n".join(
        f"| [{repo_of(i)}](https://github.com/{repo_of(i)}) "
        f"| [{i['title'].strip().replace('|', chr(92) + '|')}]({i['html_url']})"
        f"{' ' + i['suffix'] if i.get('suffix') else ''} "
        f"| {(i.get('closed_at') or '')[:10]} |"
        for i in rows
    )
    table = "| Repo | Contribution | Merged |\n|---|---|---|\n" + table_rows

    header = f'<div align="center">\n\n{review}\n\n</div>\n\n' if review else ""
    return f"{header}{table}" if rows else header.rstrip()


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
