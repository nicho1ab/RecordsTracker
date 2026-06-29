# ruff: noqa: E501

from __future__ import annotations

import html
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

APP_TITLE = "CCLD RecordsTracker"
BOUNDARY_TEXT = (
  "CCLD-only public-record review workspace."
)
PRIMARY_NAV_LINKS: tuple[tuple[str, str], ...] = (
    ("Home", "/"),
  ("Facility", "/ccld/facilities"),
  ("Request Records", "/ccld/records/request"),
  ("Review", "/reviewer"),
  ("Job Status", "/ccld/retrieval/jobs"),
    ("Feedback", "/feedback"),
  ("Help", "/ccld/help"),
)

@dataclass(frozen=True)
class GuidedStep:
  step_id: str
  label: str
  href: str
  help_text: str


GUIDED_STEPS: tuple[GuidedStep, ...] = (
  GuidedStep(
    "start",
    "Start",
    "/",
    "Start facility complaint review.",
  ),
  GuidedStep(
    "facility",
    "Facility",
    "/ccld/facilities",
    "Select the facility/license number.",
  ),
  GuidedStep(
    "date_range",
    "Dates",
    "/ccld/records/request",
    "Choose the complaint date range.",
  ),
  GuidedStep(
    "retrieve",
    "Retrieve",
    "/ccld/records/request",
    "Retrieve complaint records.",
  ),
  GuidedStep(
    "review_results",
    "Results",
    "/ccld/retrieval/jobs",
    "Review retrieval outcome.",
  ),
  GuidedStep(
    "review_records",
    "Review",
    "/reviewer",
    "Open records for legal review.",
  ),
  GuidedStep(
    "feedback",
    "Feedback",
    "/feedback",
    "Send concise tester feedback without private values.",
  ),
)

DEFAULT_NEXT_ACTIONS: Mapping[str, str] = {
  "start": "Start retrieval",
  "facility": "Confirm a facility, then choose a date range",
  "date_range": "Choose dates, then retrieve complaint records",
  "retrieve": "Retrieve complaint records",
  "review_results": "Review imported records",
  "review_records": "Open next record or send feedback",
  "feedback": "Submit feedback when useful",
}

MODE_BADGE_CLASSES = {
  "Live public CCLD": "badge badge-live",
  "Fixture/mock demo": "badge badge-demo",
  "Review aids only": "badge badge-muted",
}


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
    active_path: str | None = None,
    mode_label: str | None = None,
    step_id: str | None = None,
    next_action: str | None = None,
    show_workflow_indicator: bool = False,
) -> str:
    runtime_mode = mode_label or _runtime_mode_label()
    links = _nav_links(extra_nav_links, active_path=active_path)
    current_step = step_id or _step_id_for_path(active_path)
    stepper = _guided_stepper(current_step, next_action) if show_workflow_indicator else ""
    actor_markup = (
      f'<p class="pilot-actor">Signed in as {html.escape(actor_label)}.</p>'
      if actor_label
      else ""
    )
    eyebrow_markup = f'<p class="pilot-eyebrow">{html.escape(eyebrow)}</p>' if eyebrow else ""
    badge_class = MODE_BADGE_CLASSES.get(runtime_mode, "badge badge-muted")
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
        <div class="brand-block">
          <p class="product-name">{APP_TITLE}</p>
          {eyebrow_markup}
          <h1>{html.escape(heading)}</h1>
          {actor_markup}
        </div>
        <div class="mode-panel" aria-label="Retrieval mode">
          <span class="{badge_class}">{html.escape(runtime_mode)}</span>
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
{stepper}
{main}
    </div>
  </main>
</body>
</html>
"""


def _nav_links(
    extra_nav_links: Sequence[tuple[str, str]],
    *,
    active_path: str | None,
) -> str:
    seen: set[str] = set()
    items: list[str] = []
    for label, href in (*PRIMARY_NAV_LINKS, *tuple(extra_nav_links)):
        if href in seen:
            continue
        seen.add(href)
        active = _is_active_nav(href, active_path)
        active_class = ' class="is-active"' if active else ""
        current = ' aria-current="page"' if active else ""
        items.append(
          f'          <li><a{active_class}{current} href="{html.escape(href, quote=True)}">'
          f"{html.escape(label)}</a></li>"
        )
    return "\n".join(items)


def _guided_stepper(current_step_id: str, next_action: str | None) -> str:
  current_index = _step_index(current_step_id)
  current_step = GUIDED_STEPS[current_index]
  next_action_text = next_action or DEFAULT_NEXT_ACTIONS[current_step.step_id]
  items = "\n".join(
    _guided_step_markup(step, index, current_index)
    for index, step in enumerate(GUIDED_STEPS)
  )
  return f"""      <section class="guided-stepper" aria-labelledby="guided-stepper-heading">
    <div class="stepper-summary" role="group" aria-label="Current workflow step">
      <p class="stepper-eyebrow">Attorney workflow</p>
      <h2 id="guided-stepper-heading">Current step: {html.escape(current_step.label)}</h2>
      <p class="next-action"><strong>Next:</strong> {html.escape(next_action_text)}</p>
      <p class="helper-text stepper-keyboard-help">Keyboard flow: use the skip link, top navigation, and step links to move through the current review path; the current step and next action are stated in text.</p>
    </div>
    <ol class="stepper-list">
{items}
    </ol>
    </section>"""


def _guided_step_markup(step: GuidedStep, index: int, current_index: int) -> str:
  if index < current_index:
    state = "Completed"
    state_class = "is-complete"
    content = (
      f'<a href="{html.escape(step.href, quote=True)}">'
      f"{html.escape(step.label)}</a>"
    )
  elif index == current_index:
    state = "Current step"
    state_class = "is-current"
    content = (
      f'<a aria-current="step" href="{html.escape(step.href, quote=True)}">'
      f"{html.escape(step.label)}</a>"
    )
  else:
    state = "Future step"
    state_class = "is-upcoming"
    content = (
      f'<a href="{html.escape(step.href, quote=True)}">'
      f"{html.escape(step.label)}</a>"
    )
  return f"""          <li class="stepper-item {state_class}">
      <span class="step-index" aria-hidden="true">{index + 1}</span>
      <span class="step-main">{content}</span>
      <span class="step-state">{state}</span>
      <span class="sr-only">{html.escape(step.help_text)}</span>
      </li>"""


def _step_id_for_path(active_path: str | None) -> str:
  if active_path == "/":
    return "start"
  if active_path == "/ccld/facilities":
    return "facility"
  if active_path == "/ccld/records/request":
    return "retrieve"
  if active_path == "/ccld/retrieval/jobs" or (
    active_path is not None and active_path.startswith("/ccld/retrieval/jobs/")
  ):
    return "review_results"
  if active_path == "/reviewer" or (
    active_path is not None and active_path.startswith("/reviewer/")
  ):
    return "review_records"
  if active_path == "/feedback":
    return "feedback"
  if active_path == "/ccld/help":
    return "start"
  return "start"


def _step_index(step_id: str) -> int:
  for index, step in enumerate(GUIDED_STEPS):
    if step.step_id == step_id:
      return index
  return 0


def _is_active_nav(href: str, active_path: str | None) -> bool:
  if not active_path:
    return False
  if href == "/":
    return active_path == "/"
  return active_path == href or active_path.startswith(f"{href}/")


def _runtime_mode_label() -> str:
  demo_mode = os.environ.get("CCLD_RETRIEVAL_DEMO_MODE", "").strip().casefold()
  retrieval_enabled = os.environ.get("CCLD_RETRIEVAL_ENABLED", "").strip().casefold()
  raw_dir = os.environ.get("CCLD_RETRIEVAL_RAW_DIR", "").strip()
  if demo_mode == "mock-success":
    return "Fixture/mock demo"
  if retrieval_enabled == "enabled" and raw_dir:
    return "Live public CCLD"
  return "Review aids only"


SHARED_CSS = r"""
    :root {
      color-scheme: light;
      --bg: #F5F7FA;
      --surface: #ffffff;
      --surface-alt: #EEF7F6;
      --surface-strong: #17212b;
      --ink: #17212b;
      --muted: #5B6775;
      --muted-2: #6B7785;
      --line: #D8E0E7;
      --line-soft: #E6EBF0;
      --accent: #006b5f;
      --accent-strong: #00564D;
      --accent-soft: #EEF7F6;
      --blue: #2457a6;
      --blue-soft: #e6eef9;
      --amber: #8a5a00;
      --amber-soft: #fff5db;
      --rose: #9b2c3a;
      --rose-soft: #fff0f2;
      --warning-bg: #FFF7E0;
      --warning-line: #D89B00;
      --danger-bg: #FFF0F0;
      --danger-line: #B42318;
      --success-bg: #EAF7EF;
      --success-line: #2E7D4F;
      --focus: #2457a6;
      --shadow: 0 1px 2px rgb(23 33 43 / 6%), 0 10px 24px rgb(23 33 43 / 7%);
      --shadow-strong: 0 18px 42px rgb(23 33 43 / 12%);
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
      max-width: 80rem;
      padding: 0 1.25rem;
    }
    .site-header {
      background: rgba(255, 255, 255, 0.98);
      border-bottom: 1px solid var(--line-soft);
      box-shadow: 0 1px 8px rgb(23 33 43 / 5%);
    }
    .site-title-row {
      align-items: flex-start;
      display: flex;
      gap: 1rem;
      justify-content: space-between;
      padding: 1rem 0 0.7rem;
    }
    .product-name {
      color: var(--accent-strong);
      font-size: 0.9rem;
      font-weight: 800;
      letter-spacing: 0;
      margin: 0 0 0.2rem;
      text-transform: uppercase;
    }
    .pilot-eyebrow, .pilot-actor, .site-footer p, .helper-text {
      color: var(--muted);
      margin: 0 0 0.4rem;
    }
    h1 {
      font-size: 2.05rem;
      line-height: 1.15;
      margin: 0 0 0.25rem;
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
    textarea:focus-visible, main:focus-visible, summary:focus-visible {
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
      border: 1px solid transparent;
      border-radius: 6px;
      display: inline-block;
      padding: 0.38rem 0.55rem;
      text-decoration: none;
      white-space: nowrap;
    }
    .site-nav a:hover, .site-nav a.is-active {
      background: var(--accent-soft);
      border-color: var(--accent);
    }
    .site-nav a.is-active {
      box-shadow: inset 0 -3px 0 var(--accent);
    }
    .guided-stepper {
      align-items: center;
      background: transparent;
      border-bottom: 1px solid var(--line-soft);
      display: grid;
      gap: 0.75rem;
      grid-template-columns: minmax(13rem, 0.26fr) minmax(0, 1fr);
      margin: 0 0 1.1rem;
      padding: 0 0 0.85rem;
    }
    .stepper-summary {
      background: transparent;
      border: 0;
      border-left: 3px solid var(--accent);
      padding: 0 0 0 0.75rem;
    }
    .stepper-eyebrow {
      color: var(--muted);
      font-size: 0.74rem;
      font-weight: 800;
      margin-bottom: 0.25rem;
      pointer-events: none;
      text-transform: uppercase;
    }
    .stepper-summary h2 {
      font-size: 0.98rem;
      margin-bottom: 0.25rem;
    }
    .stepper-summary p {
      margin-bottom: 0.35rem;
    }
    .next-action {
      color: var(--ink);
    }
    .stepper-list {
      align-items: center;
      display: flex;
      flex-wrap: wrap;
      gap: 0.35rem 0.5rem;
      list-style: none;
      margin: 0;
      padding: 0;
    }
    .stepper-item {
      align-items: center;
      background: transparent;
      border: 0;
      border-radius: 0;
      display: inline-flex;
      gap: 0.35rem;
      min-height: 0;
      padding: 0.15rem 0.2rem;
      position: relative;
    }
    .stepper-item.is-complete {
      color: var(--accent-strong);
    }
    .stepper-item.is-current {
      border-bottom: 3px solid var(--blue);
      color: var(--blue);
    }
    .stepper-item.is-upcoming {
      color: var(--muted-2);
    }
    .step-index {
      align-items: center;
      display: none;
    }
    .step-main {
      align-self: center;
      min-width: 0;
    }
    .step-main a {
      font-weight: 800;
      line-height: 1.2;
      overflow-wrap: normal;
      text-decoration: none;
      white-space: nowrap;
      word-break: keep-all;
    }
    .step-state {
      clip: rect(0 0 0 0);
      clip-path: inset(50%);
      height: 1px;
      overflow: hidden;
      position: absolute;
      white-space: nowrap;
      width: 1px;
    }
    .page-main {
      padding-bottom: 2.5rem;
      padding-top: 1.15rem;
    }
    section {
      margin: 0 0 1.35rem;
    }
    section section, .nested-card {
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
    button, input[type="submit"], .button {
      background: var(--accent);
      border: 1px solid var(--accent-strong);
      border-radius: 6px;
      color: #fff;
      cursor: pointer;
      display: inline-block;
      font: inherit;
      font-weight: 700;
      padding: 0.6rem 0.85rem;
      text-align: center;
      text-decoration: none;
      white-space: nowrap;
    }
    button:hover, input[type="submit"]:hover, .button:hover {
      background: var(--accent-strong);
      color: #fff;
    }
    .button-large {
      font-size: 1.08rem;
      padding: 0.85rem 1.1rem;
    }
    .button-secondary, button.secondary {
      background: #fff;
      border-color: var(--accent);
      color: var(--accent-strong);
    }
    .button-secondary:hover, button.secondary:hover {
      background: var(--accent-soft);
      color: var(--accent-strong);
    }
    .button-quiet {
      background: transparent;
      border-color: transparent;
      color: var(--accent-strong);
      padding-left: 0;
      padding-right: 0;
    }
    .button-quiet:hover {
      background: transparent;
      color: #083b36;
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
    tbody tr:hover {
      background: #f4faf9;
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
    .mode-panel {
      align-items: flex-start;
      display: flex;
      justify-content: flex-end;
      min-width: 12rem;
    }
    .badge {
      border: 1px solid var(--line);
      border-radius: 999px;
      display: inline-flex;
      font-size: 0.88rem;
      font-weight: 800;
      gap: 0.35rem;
      line-height: 1.2;
      padding: 0.35rem 0.65rem;
      white-space: nowrap;
    }
    .badge-live {
      background: #e6f6ef;
      border-color: #4aa37f;
      color: #0d5138;
    }
    .badge-demo {
      background: var(--blue-soft);
      border-color: #83a2d3;
      color: var(--blue);
    }
    .badge-muted {
      background: #eef1f3;
      color: #495661;
    }
    .badge-warning {
      background: var(--amber-soft);
      border-color: #d7a529;
      color: var(--amber);
    }
    .badge-danger {
      background: var(--rose-soft);
      border-color: #d88992;
      color: var(--rose);
    }
    .hero-card {
      background: #ffffff;
      border: 1px solid var(--line-soft);
      border-left: 5px solid var(--accent);
      border-radius: 10px;
      box-shadow: var(--shadow-strong);
      padding: 1.4rem;
    }
    .hero-card h2 {
      font-size: 1.55rem;
      max-width: 54rem;
    }
    .launch-kicker {
      color: var(--muted);
      font-size: 0.88rem;
      font-weight: 800;
      margin-bottom: 0.35rem;
      pointer-events: none;
      text-transform: uppercase;
    }
    .launch-value {
      font-size: 1.08rem;
      max-width: 54rem;
    }
    .attorney-hero {
      display: grid;
      gap: 1rem;
      grid-template-columns: minmax(0, 1fr) auto;
    }
    .attorney-hero-actions {
      align-content: start;
      display: grid;
      gap: 0.55rem;
      min-width: 12rem;
    }
    .case-brief-header {
      align-items: flex-start;
      display: flex;
      gap: 1rem;
      justify-content: space-between;
    }
    .boundary-note {
      background: var(--surface-alt);
      border-left: 4px solid var(--accent);
      color: var(--muted);
      margin-bottom: 0;
      max-width: 62rem;
      padding: 0.65rem 0.85rem;
    }
    .metric-strip {
      display: grid;
      gap: 0.75rem;
      grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
      margin: 0.75rem 0;
    }
    .metric-card {
      background: #ffffff;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      box-shadow: 0 1px 2px rgb(23 33 43 / 5%);
      padding: 0.8rem;
    }
    .metric-card strong {
      display: block;
      font-size: 1.55rem;
      line-height: 1.1;
    }
    .metric-card span {
      color: var(--muted);
      display: block;
      font-size: 0.88rem;
      margin-top: 0.15rem;
    }
    .flag-list {
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
      margin: 0.45rem 0 0;
      padding: 0;
    }
    .flag-list li {
      list-style: none;
    }
    .review-chip {
      background: var(--amber-soft);
      border: 1px solid var(--warning-line);
      border-radius: 999px;
      color: var(--amber);
      display: inline-flex;
      font-size: 0.82rem;
      font-weight: 800;
      padding: 0.22rem 0.55rem;
    }
    .source-chip {
      background: var(--blue-soft);
      border-color: #83a2d3;
      color: var(--blue);
    }
    .workflow-cards {
      display: grid;
      gap: 0.85rem;
      grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
    }
    .workflow-cards .action-card p:last-child {
      margin-bottom: 0;
    }
    .action-card, .summary-card, .detail-card, .empty-state-card, .warning-card {
      background: var(--surface);
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 1rem;
    }
    .action-card {
      min-height: 100%;
    }
    .warning-card {
      background: var(--warning-bg);
      border-color: var(--warning-line);
    }
    .next-action-panel {
      background: var(--surface-alt);
      border-color: #8ab9b4;
      border-left: 5px solid var(--accent);
      box-shadow: var(--shadow-strong);
    }
    .empty-state-card {
      background: #f8fafb;
      border-style: dashed;
    }
    .grid, .action-grid, .stat-grid, .two-column, .request-layout {
      display: grid;
      gap: 1rem;
    }
    .action-grid {
      grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
    }
    .compact-actions {
      align-items: stretch;
      display: grid;
      gap: 0.75rem;
      grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
    }
    .compact-actions p {
      margin: 0;
    }
    .compact-actions .button {
      width: 100%;
    }
    .quiet-section {
      background: transparent;
      border: 0;
      box-shadow: none;
      padding: 0.25rem 0;
    }
    .case-brief-section-break {
      border-top: 1px solid var(--line);
      margin-top: 1.35rem;
      padding-top: 1rem;
    }
    .quiet-section > h2 {
      font-size: 1rem;
    }
    .technical-grid {
      margin-top: 0.8rem;
    }
    .stat-grid {
      grid-template-columns: repeat(auto-fit, minmax(9.5rem, 1fr));
    }
    .two-column {
      grid-template-columns: minmax(0, 1fr) minmax(16rem, 0.42fr);
    }
    .request-layout {
      align-items: start;
      grid-template-columns: minmax(0, 1fr) minmax(17rem, 22rem);
    }
    .sidebar-stack {
      display: grid;
      gap: 1rem;
    }
    .stat-card {
      background: var(--surface);
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      box-shadow: 0 1px 2px rgb(23 33 43 / 5%);
      padding: 0.85rem;
    }
    .result-list {
      display: grid;
      gap: 0.75rem;
    }
    .result-card {
      align-items: center;
      background: #ffffff;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      box-shadow: var(--shadow);
      display: grid;
      gap: 1rem;
      grid-template-columns: minmax(0, 1fr) auto;
      padding: 0.9rem;
    }
    .result-card.work-item {
      align-items: start;
      grid-template-columns: minmax(0, 1fr) minmax(8rem, auto);
    }
    .legal-summary-grid {
      display: grid;
      gap: 1rem;
      grid-template-columns: minmax(0, 1.2fr) minmax(18rem, 0.8fr);
    }
    .summary-list {
      display: grid;
      gap: 0.45rem 1rem;
      grid-template-columns: minmax(9rem, 14rem) 1fr;
    }
    .summary-list dt {
      color: var(--muted);
    }
    .technical-details {
      background: transparent;
      border: 0;
      box-shadow: none;
      padding: 0;
    }
    .technical-details > summary {
      color: var(--accent-strong);
      font-size: 0.92rem;
    }
    .detail-shell {
      display: grid;
      gap: 1rem;
    }
    .detail-top-grid {
      display: grid;
      gap: 1rem;
      grid-template-columns: minmax(0, 1.25fr) minmax(18rem, 0.75fr);
    }
    .detail-signal-grid {
      display: grid;
      gap: 1rem;
      grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
    }
    .fact-grid {
      display: grid;
      gap: 0.75rem;
      grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
    }
    .fact-card {
      background: var(--surface);
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      padding: 0.75rem;
    }
    .fact-card strong {
      display: block;
      font-size: 1.05rem;
    }
    .fact-card span {
      color: var(--muted);
      display: block;
      font-size: 0.86rem;
    }
    .support-layout {
      display: grid;
      gap: 1rem;
      grid-template-columns: minmax(0, 0.9fr) minmax(20rem, 1.1fr);
    }
    .recovery-panel {
      border-left: 5px solid var(--warning-line);
    }
    .source-separation-note {
      background: #f8fbfb;
      border: 1px solid var(--line);
      border-radius: 8px;
      color: var(--muted);
      padding: 0.75rem;
    }
    .result-card h3, .result-card p {
      margin-bottom: 0.25rem;
    }
    .stat-card strong {
      display: block;
      font-size: 1.7rem;
      line-height: 1.1;
    }
    .form-row {
      display: grid;
      gap: 1rem;
      grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
    }
    .facility-intelligence-filter-grid {
      display: grid;
      gap: 0.85rem 1rem;
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .facility-intelligence-filter-grid p {
      margin: 0;
    }
    .facility-intelligence-filter-grid select {
      width: 100%;
    }
    .form-actions {
      align-items: center;
      display: flex;
      flex-wrap: wrap;
      gap: 0.65rem;
      margin-top: 0.25rem;
    }
    .fixed-field {
      background: #f7fafb;
      border: 1px solid var(--line-soft);
      border-radius: 6px;
      padding: 0.65rem;
    }
    .wizard-sequence {
      display: grid;
      gap: 0.85rem;
    }
    .wizard-stage {
      background: #ffffff;
      border: 1px solid var(--line);
      border-radius: 10px;
      box-shadow: 0 1px 2px rgb(31 41 51 / 6%);
      padding: 1rem;
    }
    .wizard-stage-primary {
      border-color: #8ab9b4;
      box-shadow: var(--shadow);
    }
    .workflow-panel {
      background: #ffffff;
      border: 1px solid var(--line-soft);
      border-radius: 10px;
      box-shadow: var(--shadow-strong);
      padding: 1.25rem;
    }
    .workflow-panel-primary {
      border-color: var(--accent);
      box-shadow: 0 14px 34px rgb(18 103 95 / 16%);
    }
    .stage-kicker {
      color: var(--muted);
      font-size: 0.82rem;
      font-weight: 800;
      margin-bottom: 0.25rem;
      pointer-events: none;
      text-transform: uppercase;
    }
    .compact-list {
      margin-bottom: 0;
      padding-left: 1.2rem;
    }
    .sr-note {
      color: var(--muted);
      font-size: 0.92rem;
    }
    .sr-only {
      clip: rect(0 0 0 0);
      clip-path: inset(50%);
      height: 1px;
      overflow: hidden;
      position: absolute;
      white-space: nowrap;
      width: 1px;
    }
    details {
      border-top: 1px solid var(--line-soft);
      margin-top: 0.75rem;
      padding-top: 0.75rem;
    }
    summary {
      cursor: pointer;
      font-weight: 800;
    }
    .reference-details-section {
      border-top: 1px solid var(--line);
      margin-top: 0.75rem;
      padding-top: 0.75rem;
    }
    .reference-details-section > summary {
      font-size: 0.88rem;
      font-weight: 800;
    }
    .facility-combobox-outer {
      max-width: 28rem;
      position: relative;
    }
    .facility-suggestions {
      background: var(--surface);
      border: 1px solid var(--accent);
      border-radius: 8px;
      box-shadow: 0 8px 24px rgb(19 32 43 / 14%);
      left: 0;
      list-style: none;
      margin: 0;
      max-height: 18rem;
      overflow-y: auto;
      padding: 0.3rem;
      position: absolute;
      top: calc(100% + 4px);
      width: 100%;
      z-index: 200;
    }
    .suggestion-btn {
      background: transparent;
      border: none;
      border-radius: 6px;
      color: var(--ink);
      cursor: pointer;
      display: flex;
      flex-direction: column;
      gap: 0.1rem;
      padding: 0.5rem 0.6rem;
      text-align: left;
      width: 100%;
    }
    .suggestion-btn:hover, .suggestion-btn:focus {
      background: var(--accent-soft);
      color: var(--ink);
    }
    .suggestion-name {
      font-size: 0.96rem;
      font-weight: 700;
      line-height: 1.3;
    }
    .suggestion-badge {
      background: var(--surface-alt);
      border: 1px solid var(--line);
      border-radius: 4px;
      display: inline-block;
      font-size: 0.78rem;
      font-weight: 700;
      padding: 0.05rem 0.3rem;
    }
    .suggestion-details {
      color: var(--muted);
      font-size: 0.82rem;
      line-height: 1.3;
    }
    .suggestion-empty {
      color: var(--muted);
      display: block;
      font-size: 0.88rem;
      padding: 0.5rem 0.6rem;
    }
    .facility-selected-card {
      background: var(--accent-soft);
      border: 2px solid var(--accent);
      border-radius: 8px;
      margin-top: 0.75rem;
      padding: 0.85rem;
    }
    .facility-selected-card .selected-name {
      font-size: 1rem;
      font-weight: 700;
      margin: 0 0 0.25rem;
    }
    .facility-selected-card .selected-number {
      font-size: 0.85rem;
    }
    .facility-selected-card .selected-geo,
    .facility-selected-card .selected-meta {
      color: var(--muted);
      font-size: 0.85rem;
      margin: 0.1rem 0 0;
    }
    .limited-note {
      font-size: 0.88rem;
      margin-top: 0.5rem;
    }
    .packet-draft {
      background: #fff;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 1.4rem;
    }
    .packet-draft-header {
      border-bottom: 2px solid var(--ink);
      margin-bottom: 1rem;
      padding-bottom: 0.8rem;
    }
    .packet-draft-record {
      break-inside: avoid;
      border-top: 1px solid var(--line);
      padding-top: 0.9rem;
    }
    .copyable-packet-summary {
      background: #f8fafb;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow-x: auto;
      padding: 1rem;
      white-space: pre-wrap;
    }
    @media print {
      body {
        background: #fff;
        color: #000;
        font-size: 11pt;
      }
      .site-header, .guided-stepper, .site-footer, .packet-draft-actions,
      .technical-details, .skip-link, .mode-panel {
        display: none !important;
      }
      .shell {
        max-width: none;
        padding: 0;
      }
      .page-main {
        padding: 0;
      }
      .packet-draft {
        border: 0;
        box-shadow: none;
        padding: 0;
      }
      .packet-draft-record {
        break-inside: avoid;
        page-break-inside: avoid;
      }
      a {
        color: #000;
        text-decoration: none;
      }
      .badge, .review-chip {
        border-color: #000;
        color: #000;
      }
    }
    @media (max-width: 760px) {
      h1 {
        font-size: 1.55rem;
      }
      .site-title-row, .two-column, .request-layout {
        display: block;
      }
      .attorney-hero, .legal-summary-grid, .detail-top-grid, .support-layout {
        display: block;
      }
      .attorney-hero-actions {
        margin-top: 1rem;
      }
      .mode-panel {
        justify-content: flex-start;
        margin-top: 0.75rem;
      }
      .site-nav ul {
        display: grid;
      }
      .guided-stepper {
        display: block;
      }
      .stepper-list {
        align-items: stretch;
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(8.25rem, 1fr));
        margin-top: 0.75rem;
      }
      .stepper-item {
        justify-content: flex-start;
        min-height: auto;
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
      .facility-intelligence-filter-grid {
        grid-template-columns: minmax(0, 1fr);
      }
    }
""".strip()
