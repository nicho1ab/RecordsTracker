from __future__ import annotations

import html
from collections.abc import Sequence

APP_TITLE = "CCLD Records Review"
BOUNDARY_TEXT = (
  "Local/test pilot scaffold: source-derived public records with separate "
  "reviewer-created notes/status."
)
FOOTER_NOTE = (
  "CCLD public portal material remains the source of record. This local/test "
  "pilot UI is a review aid only and does not prove source completeness, legal "
  "findings, facility-wide conclusions, harm, abuse, neglect, liability, or "
  "rights-deprivation."
)

PRIMARY_NAV_LINKS: tuple[tuple[str, str], ...] = (
    ("Home", "/"),
    ("Facility Lookup", "/ccld/facilities"),
  ("CCLD record request", "/ccld/records/request"),
    ("Reviewer", "/reviewer"),
    ("Retrieval job history", "/ccld/retrieval/jobs"),
    ("Feedback", "/feedback"),
    ("How this works", "/ccld/help"),
)


def render_page_shell(
    *,
    title: str,
    heading: str,
    main: str,
    skip_label: str,
    nav_label: str,
    eyebrow: str | None = BOUNDARY_TEXT,
    actor_label: str | None = None,
    extra_nav_links: Sequence[tuple[str, str]] = (),
) -> str:
    links = _nav_links(extra_nav_links)
    actor_markup = (
      f'<p class="pilot-actor">Signed in as {html.escape(actor_label)}.</p>'
      if actor_label
      else ""
    )
    eyebrow_markup = f'<p class="pilot-eyebrow">{html.escape(eyebrow)}</p>' if eyebrow else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} - {APP_TITLE}</title>
  <style>
{SHARED_CSS}
  </style>
</head>
<body>
  <a class="skip-link" href="#main-content">{html.escape(skip_label)}</a>
  <header class="site-header">
    <div class="shell">
      <div class="site-title-row">
        <div>
          {eyebrow_markup}
          <h1>{html.escape(heading)}</h1>
          {actor_markup}
        </div>
      </div>
      <nav class="site-nav" aria-label="{html.escape(nav_label)}">
        <ul>
{links}
        </ul>
      </nav>
    </div>
  </header>
  <main id="main-content" tabindex="-1">
    <div class="shell page-main">
{main}
    </div>
  </main>
  <footer class="site-footer">
    <div class="shell">
      <p>{html.escape(FOOTER_NOTE)}</p>
    </div>
  </footer>
</body>
</html>
"""


def _nav_links(extra_nav_links: Sequence[tuple[str, str]]) -> str:
    seen: set[str] = set()
    items: list[str] = []
    for label, href in (*PRIMARY_NAV_LINKS, *tuple(extra_nav_links)):
        if href in seen:
            continue
        seen.add(href)
        items.append(
            f'          <li><a href="{html.escape(href, quote=True)}">{html.escape(label)}</a></li>'
        )
    return "\n".join(items)


SHARED_CSS = r"""
    :root {
      color-scheme: light;
      --bg: #f7f7f4;
      --surface: #ffffff;
      --surface-alt: #eef5f3;
      --ink: #1f2933;
      --muted: #52606d;
      --line: #c9d2d0;
      --accent: #176b63;
      --accent-strong: #0f4f49;
      --accent-soft: #dcefed;
      --warning-bg: #fff7df;
      --warning-line: #d8aa3d;
      --danger-bg: #fff1f0;
      --danger-line: #d66b61;
      --focus: #7c3aed;
      --shadow: 0 1px 2px rgb(31 41 51 / 8%), 0 8px 24px rgb(31 41 51 / 8%);
    }
    * {
      box-sizing: border-box;
    }
    body {
      background: var(--bg);
      color: var(--ink);
      font-family: "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      font-size: 16px;
      line-height: 1.55;
      margin: 0;
    }
    .shell {
      margin: 0 auto;
      max-width: 76rem;
      padding: 0 1rem;
    }
    .site-header {
      background: var(--surface);
      border-bottom: 1px solid var(--line);
      box-shadow: 0 1px 8px rgb(31 41 51 / 6%);
    }
    .site-title-row {
      padding: 1.25rem 0 0.75rem;
    }
    .pilot-eyebrow, .pilot-actor, .site-footer p {
      color: var(--muted);
      margin: 0 0 0.4rem;
    }
    h1 {
      font-size: 2rem;
      line-height: 1.15;
      margin: 0;
    }
    h2 {
      font-size: 1.35rem;
      line-height: 1.25;
      margin: 0 0 0.65rem;
    }
    h3 {
      font-size: 1.05rem;
      line-height: 1.3;
      margin: 0.8rem 0 0.45rem;
    }
    p, ul, ol, dl {
      margin-top: 0;
    }
    a {
      color: var(--accent-strong);
      font-weight: 650;
      text-underline-offset: 0.16em;
    }
    a:hover {
      color: #083b36;
    }
    a:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible,
    textarea:focus-visible, main:focus-visible {
      outline: 3px solid var(--focus);
      outline-offset: 3px;
    }
    .skip-link {
      background: var(--ink);
      color: #fff;
      left: 1rem;
      padding: 0.6rem 0.8rem;
      position: absolute;
      top: 0.5rem;
      transform: translateY(-140%);
      z-index: 10;
    }
    .skip-link:focus {
      transform: translateY(0);
    }
    .site-nav ul {
      display: flex;
      flex-wrap: wrap;
      gap: 0.45rem;
      list-style: none;
      margin: 0;
      padding: 0 0 1rem;
    }
    .site-nav a {
      border: 1px solid var(--line);
      border-radius: 6px;
      display: inline-block;
      padding: 0.45rem 0.65rem;
      text-decoration: none;
    }
    .site-nav a:hover {
      background: var(--accent-soft);
      border-color: var(--accent);
    }
    .page-main {
      padding-bottom: 2rem;
      padding-top: 1rem;
    }
    section {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      margin: 0 0 1rem;
      padding: 1rem;
    }
    section section {
      background: var(--surface-alt);
      box-shadow: none;
      margin-top: 1rem;
    }
    form {
      display: grid;
      gap: 0.85rem;
    }
    fieldset {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 1rem;
    }
    label, legend, caption, th {
      font-weight: 700;
    }
    label {
      display: block;
      margin-bottom: 0.25rem;
    }
    input, select, textarea {
      border: 1px solid #9aa6ac;
      border-radius: 6px;
      color: var(--ink);
      font: inherit;
      max-width: 100%;
      padding: 0.55rem 0.65rem;
      width: min(100%, 28rem);
    }
    textarea {
      min-height: 12rem;
      width: 100%;
    }
    button, input[type="submit"] {
      background: var(--accent);
      border: 1px solid var(--accent-strong);
      border-radius: 6px;
      color: #fff;
      cursor: pointer;
      font: inherit;
      font-weight: 700;
      padding: 0.6rem 0.85rem;
    }
    button:hover, input[type="submit"]:hover {
      background: var(--accent-strong);
    }
    table {
      border-collapse: collapse;
      width: 100%;
    }
    caption {
      color: var(--muted);
      margin-bottom: 0.5rem;
      text-align: left;
    }
    th, td {
      border: 1px solid var(--line);
      padding: 0.6rem;
      text-align: left;
      vertical-align: top;
    }
    thead th {
      background: var(--surface-alt);
    }
    tbody tr:nth-child(even) {
      background: #fbfcfb;
    }
    dl {
      display: grid;
      gap: 0.35rem 1rem;
      grid-template-columns: minmax(10rem, 16rem) 1fr;
    }
    dt {
      color: var(--muted);
      font-weight: 700;
    }
    dd {
      margin: 0;
    }
    code {
      background: #edf2f0;
      border-radius: 4px;
      padding: 0.05rem 0.25rem;
      overflow-wrap: anywhere;
    }
    .site-footer {
      border-top: 1px solid var(--line);
      padding: 1.25rem 0;
    }
    @media (max-width: 760px) {
      h1 {
        font-size: 1.55rem;
      }
      .site-nav ul {
        display: grid;
      }
      dl {
        display: block;
      }
      dt {
        margin-top: 0.6rem;
      }
      table {
        display: block;
        overflow-x: auto;
      }
    }
""".strip()
