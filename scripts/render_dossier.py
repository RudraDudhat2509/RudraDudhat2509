#!/usr/bin/env python3
"""Render the profile banner: a case file on myself.

Two variants, light and dark, swapped by <picture> in the README.

The merged-PR count is stamped into the artwork, so it is generated here from
the same live search the README table uses rather than typed in by hand. A
hardcoded number on a banner is a number that is wrong by next month.

Constraints this file is written against:
  - GitHub serves SVGs under `default-src 'none'; style-src 'unsafe-inline';
    sandbox`. Inline CSS runs, so the animation works. Script never will.
  - `default-src 'none'` also blocks webfonts, so the type has to be a stack of
    faces that already exist on the reader's machine.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from update_oss_prs import build_counts  # noqa: E402

README = "README.md"
START = "<!-- BANNER:START -->"
END = "<!-- BANNER:END -->"
LINKS_START = "<!-- LINKS:START -->"
LINKS_END = "<!-- LINKS:END -->"
RAW = "https://raw.githubusercontent.com/RudraDudhat2509/RudraDudhat2509/main/assets"

W, H = 1000, 394

# The rule stops short of the stamp rather than running under it. The stamp is
# rotated, so its corners reach further left than its bounding box suggests.
RULE_END = 726

# Typewriter faces that ship with Windows, macOS and most Linux desktops. No
# webfont can load inside the sandbox, so this stack is the whole type system.
MONO = "'Courier New', 'Nimbus Mono PS', 'DejaVu Sans Mono', monospace"

THEMES = {
    "light": {
        "paper": "#E9E3D3", "grain": "#8C7F5F", "grain_opacity": "0.10",
        "border": "#C6BCA3", "ink": "#23201A", "muted": "#6B6252",
        "stamp": "#A03826", "rule": "#23201A",
    },
    "dark": {
        "paper": "#14120E", "grain": "#C9B98C", "grain_opacity": "0.07",
        "border": "#342E22", "ink": "#E6DCC4", "muted": "#8B8068",
        "stamp": "#C4593B", "rule": "#6E6350",
    },
}

# Link chips, drawn as file tabs rather than rounded shields. Each one is its
# own SVG because an SVG loaded through <img> is inert: internal <a> elements
# never fire, so a single combined strip could only ever carry one link.
LINKS = [
    ("portfolio", "PORTFOLIO", "https://rudradudhat2509.github.io/", True),
    ("notes", "FIELD NOTES", "https://rudradudhat2509.github.io/notes.html", False),
    ("linkedin", "LINKEDIN", "https://www.linkedin.com/in/rdudhat-iitbhilai/", False),
    ("x", "X / @RUDRABUILDS", "https://twitter.com/rudrabuilds", False),
    ("email", "EMAIL", "mailto:contact.rdudhat@gmail.com", False),
    ("pypi", "DIFFPROMPT ON PyPI", "https://pypi.org/project/diffprompt/", False),
]

# Deliberately excludes anything already named in PRIORS. The two rows sit
# next to each other, and repeating opentelemetry across both reads as a
# stutter rather than as emphasis.
STACK = [
    "python", "pytorch", "fastapi", "langgraph",
    "postgres", "redis", "docker", "aws",
]

CLOSING = "PEER REVIEWED: FUNNY · DELUSIONAL · AMBITIOUS · FUELED BY TEA, NOT COFFEE"

ROWS = [
    ("SUBJECT", "builds AI agents, then breaks them"),
    ("METHOD", "agentic attack surfaces · observability · evals"),
    ("PRIORS", "opentelemetry · mlflow · litellm · kedro · grpc"),
    ("TOOLING", " · ".join(STACK)),
    ("LOCATION", "IIT Bhilai · "),          # redaction bar lands after this
    ("STATUS", "available, winter 2026"),
]


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(theme: str, merged: int, repos: int) -> str:
    c = THEMES[theme]
    row_y = 172
    row_gap = 30

    rows_svg = []
    for i, (label, value) in enumerate(ROWS):
        y = row_y + i * row_gap
        delay = 0.05 * i
        rows_svg.append(
            f'<g class="row" style="animation-delay:{delay:.2f}s">'
            f'<text x="52" y="{y}" class="lbl">{esc(label)}</text>'
            f'<text x="196" y="{y}" class="val">{esc(value)}</text>'
            f'</g>'
        )

    # The redaction bar sits over where the rest of the LOCATION line would be.
    # Found by label rather than by index, so inserting a row above it cannot
    # silently slide the bar onto a different line.
    loc = next(i for i, (label, _) in enumerate(ROWS) if label == "LOCATION")
    redaction_y = row_y + loc * row_gap - 13
    redaction_x = 196 + len(ROWS[loc][1]) * 9.6

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"
     viewBox="0 0 {W} {H}" role="img"
     aria-label="Case file on Rudra Dudhat, AI product engineer. {merged} patches merged into {repos} production repositories. Available winter 2026.">
  <defs>
    <filter id="grain" x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="3" seed="7"/>
      <feColorMatrix type="saturate" values="0"/>
    </filter>
  </defs>

  <style>
    .lbl {{ font: 500 12px {MONO}; fill: {c['muted']}; letter-spacing: 1.6px; }}
    .val {{ font: 500 14px {MONO}; fill: {c['ink']}; }}
    .name {{ font: 700 46px {MONO}; fill: {c['ink']}; letter-spacing: 7px; }}
    .file {{ font: 500 12px {MONO}; fill: {c['muted']}; letter-spacing: 3.4px; }}
    .foot {{ font: 500 11px {MONO}; fill: {c['muted']}; letter-spacing: 2px; }}
    .stamp-t {{ font: 700 13px {MONO}; fill: {c['stamp']}; letter-spacing: 2.2px; }}
    .stamp-n {{ font: 700 26px {MONO}; fill: {c['stamp']}; letter-spacing: 1px; }}

    .row {{ opacity: 0; animation: fade .34s ease-out forwards; }}
    .redact {{ transform-box: fill-box; transform-origin: left center;
               transform: scaleX(0); animation: wipe .30s ease-in .34s forwards; }}
    .stamp {{ transform-box: fill-box; transform-origin: center;
              opacity: 0; animation: thump .42s cubic-bezier(.2,.9,.3,1.3) .64s forwards; }}

    @keyframes fade {{ to {{ opacity: 1; }} }}
    @keyframes wipe {{ to {{ transform: scaleX(1); }} }}
    @keyframes thump {{
      0%   {{ opacity: 0; transform: scale(2.3) rotate(-15deg); }}
      70%  {{ opacity: 1; transform: scale(.95) rotate(-7deg); }}
      100% {{ opacity: 1; transform: scale(1) rotate(-7deg); }}
    }}

    @media (prefers-reduced-motion: reduce) {{
      .row, .redact, .stamp {{ animation: none; opacity: 1; transform: none; }}
      .stamp {{ transform: rotate(-7deg); }}
      .redact {{ transform: scaleX(1); }}
    }}
  </style>

  <rect width="{W}" height="{H}" fill="{c['paper']}"/>
  <rect width="{W}" height="{H}" filter="url(#grain)"
        fill="{c['grain']}" opacity="{c['grain_opacity']}"/>
  <rect x="14" y="14" width="{W - 28}" height="{H - 28}"
        fill="none" stroke="{c['border']}" stroke-width="1"/>

  <text x="52" y="86" class="name">R. DUDHAT</text>
  <text x="55" y="112" class="file">FILE 2509 &#183; AI PRODUCT ENGINEER</text>
  <line x1="52" y1="132" x2="{RULE_END}" y2="132" stroke="{c['rule']}" stroke-width="2"/>

  {''.join(rows_svg)}

  <rect class="redact" x="{redaction_x:.0f}" y="{redaction_y}" width="132" height="17"
        fill="{c['ink']}"/>

  <g class="stamp">
    <rect x="{W - 250}" y="44" width="196" height="106" fill="none"
          stroke="{c['stamp']}" stroke-width="3"/>
    <text x="{W - 152}" y="78" class="stamp-t" text-anchor="middle">PATCHES MERGED</text>
    <text x="{W - 152}" y="112" class="stamp-n" text-anchor="middle">&#215; {merged}</text>
    <text x="{W - 152}" y="136" class="stamp-t" text-anchor="middle">{repos} PROD REPOS</text>
  </g>

  <text x="52" y="{H - 38}" class="foot">EVIDENCE ATTACHED BELOW &#183; UPDATED DAILY BY CI</text>
</svg>
'''


# Courier advances at 0.6em; the tracking is added on top of that.
CHAR_W = 12 * 0.6 + 1.9
CHIP_H = 34


def render_chip(theme: str, label: str, accent: bool) -> str:
    c = THEMES[theme]
    stroke = c["stamp"] if accent else c["border"]
    fill = c["stamp"] if accent else c["ink"]
    w = int(len(label) * CHAR_W + 34)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{CHIP_H}"
     viewBox="0 0 {w} {CHIP_H}" role="img" aria-label="{label}">
  <rect x="1" y="1" width="{w - 2}" height="{CHIP_H - 2}" fill="{c['paper']}"
        stroke="{stroke}" stroke-width="{'2' if accent else '1'}"/>
  <text x="{w / 2:.0f}" y="22" text-anchor="middle"
        style="font: 700 12px {MONO}; fill: {fill}; letter-spacing: 1.9px;">{esc(label)}</text>
</svg>
'''


def banner_markup(merged: int, repos: int) -> str:
    """The <picture> block, written with absolute raw URLs.

    Relative paths are NOT rewritten inside srcset, so `assets/...` renders as
    a dead link and the banner silently disappears. Absolute raw URLs resolve,
    but GitHub proxies and caches them through camo, and the URL alone would
    never change when the stamped count does. The ?v token changes exactly when
    the numbers change, which is the only time the cache needs busting.
    """
    version = f"{merged}-{repos}"
    alt = (f"Case file on Rudra Dudhat, AI product engineer. {merged} patches "
           f"merged into {repos} production repositories. Available winter 2026.")
    return f'''<a href="https://rudradudhat2509.github.io/">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="{RAW}/dossier-dark.svg?v={version}">
    <source media="(prefers-color-scheme: light)" srcset="{RAW}/dossier-light.svg?v={version}">
    <img src="{RAW}/dossier-light.svg?v={version}" alt="{alt}" width="100%">
  </picture>
</a>'''


def links_markup(version: str) -> str:
    chips = []
    for name, label, href, _ in LINKS:
        chips.append(
            f'<a href="{href}">'
            f'<picture>'
            f'<source media="(prefers-color-scheme: dark)" srcset="{RAW}/link-{name}-dark.svg?v={version}">'
            f'<img src="{RAW}/link-{name}-light.svg?v={version}" alt="{label}" height="34">'
            f'</picture></a>'
        )
    return "\n".join(chips)


def inject(start: str, end: str, markup: str, what: str) -> None:
    with open(README, encoding="utf-8") as f:
        content = f.read()
    wrapped = f"{start}\n\n{markup}\n\n{end}"
    new = re.sub(re.escape(start) + r".*?" + re.escape(end), wrapped, content,
                 flags=re.DOTALL)
    if new == content:
        print(f"{what} unchanged")
        return
    with open(README, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    print(f"{what} updated")


def write(path: str, body: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)


def main() -> None:
    merged, repos = build_counts()
    version = f"{merged}-{repos}"
    os.makedirs("assets", exist_ok=True)

    for theme in THEMES:
        write(f"assets/dossier-{theme}.svg", render(theme, merged, repos))
        for name, label, _, accent in LINKS:
            write(f"assets/link-{name}-{theme}.svg", render_chip(theme, label, accent))

    print(f"wrote banner and {len(LINKS)} chips per theme "
          f"({merged} merged, {repos} repos)")

    inject(START, END, banner_markup(merged, repos), "banner")
    inject(LINKS_START, LINKS_END, links_markup(version), "links")


if __name__ == "__main__":
    main()
