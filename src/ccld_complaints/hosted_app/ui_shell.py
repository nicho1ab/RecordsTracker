# ruff: noqa: E501

from __future__ import annotations

import html
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

APP_TITLE = "CCLD RecordsTracker"
WORKSPACE_LABEL = "Reviewer Workspace"
EYEBROW_TEXT = ""
FAVICON_PATH = "/favicon.ico"
PRIMARY_NAV_LINKS: tuple[tuple[str, str], ...] = (
    ("Home", "/"),
    ("Facilities", "/ccld/facilities"),
    ("Compare Facilities", "/ccld/facilities/intelligence"),
    ("Request Records", "/ccld/records/request"),
    ("Review", "/reviewer"),
    ("Feedback", "/feedback"),
    ("Help", "/ccld/help"),
)
COMPARE_FACILITIES_PATH = "/ccld/facilities/intelligence"
COMPARE_FACILITIES_VIEWS: tuple[tuple[str, str, str], ...] = (
    ("complaint-patterns", "Complaint Patterns", COMPARE_FACILITIES_PATH),
    (
        "licensing-visit-activity",
        "Licensing and Visit Activity",
        f"{COMPARE_FACILITIES_PATH}?view=licensing-visit-activity",
    ),
    (
        "complaint-activity-over-time",
        "Complaint Activity Over Time",
        f"{COMPARE_FACILITIES_PATH}?view=complaint-activity-over-time",
    ),
)
OPERATOR_NAV_LINKS: tuple[tuple[str, str], ...] = (
    ("Source coverage", "/operator/source-coverage"),
)

@dataclass(frozen=True)
class ActionItem:
  label: str
  href: str
  aria_label: str | None = None


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
    "Select the Facility ID.",
  ),
  GuidedStep(
    "date_range",
    "Dates",
    "/ccld/records/request",
    "Choose the complaint date range.",
  ),
  GuidedStep(
    "retrieve",
    "Request",
    "/ccld/records/request",
    "Request complaint records.",
  ),
  GuidedStep(
    "review_results",
    "Records",
    "/reviewer",
    "Open records after Request Records returns results.",
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
    "Send feedback without private values.",
  ),
)

DEFAULT_NEXT_ACTIONS: Mapping[str, str] = {
  "start": "Start facility complaint review",
  "facility": "Confirm a facility, then choose a date range",
  "date_range": "Choose dates, then request complaint records",
  "retrieve": "Request complaint records",
  "review_results": "Review records or check support diagnostics only when needed",
  "review_records": "Open next record or send feedback",
  "feedback": "Submit feedback when useful",
}

MODE_BADGE_CLASSES = {
  "Live public CCLD": "ds-badge ds-badge--success",
  "Fixture/mock demo": "ds-badge ds-badge--info",
  "Review aids only": "ds-badge ds-badge--muted",
}


def render_page_shell(
    *,
    title: str,
    heading: str,
    main: str,
    skip_label: str,
    eyebrow: str | None = EYEBROW_TEXT,
    actor_label: str | None = None,
    active_path: str | None = None,
    mode_label: str | None = None,
    step_id: str | None = None,
    next_action: str | None = None,
    show_workflow_indicator: bool = False,
    show_operator_navigation: bool = False,
) -> str:
    runtime_mode = mode_label or _runtime_mode_label()
    links = _nav_links(
        active_path=active_path,
        show_operator_navigation=show_operator_navigation,
    )
    current_step = step_id or _step_id_for_path(active_path)
    stepper = _guided_stepper(current_step, next_action) if show_workflow_indicator else ""
    actor_markup = (
      f'<p class="pilot-actor">Signed in as {html.escape(actor_label)}.</p>'
      if actor_label
      else ""
    )
    eyebrow_markup = f'<p class="pilot-eyebrow">{html.escape(eyebrow)}</p>' if eyebrow else ""
    badge_class = MODE_BADGE_CLASSES.get(runtime_mode, "ds-badge ds-badge--muted")
    body_class = "ds-page-bg civic-ledger-page"
    header_markup = _civic_ledger_header(links, runtime_mode, badge_class)
    footer_markup = _civic_ledger_footer()
    document_head = render_document_head(
        title=f"{title} - {APP_TITLE}",
        styles=SHARED_CSS,
    )
    return f"""<!doctype html>
<html lang="en">
{document_head}
<body class="{body_class}">
  <a class="skip-link" href="#main-content">{html.escape(skip_label)}</a>
{header_markup}
  <main id="main-content" class="ds-page-main app-page" tabindex="-1">
    <div class="shell page-main app-page-main">
      <section class="page-title-block" aria-labelledby="page-heading">
        {eyebrow_markup}
        <h1 id="page-heading">{html.escape(heading)}</h1>
        {actor_markup}
      </section>
{stepper}
{main}
    </div>
  </main>
{footer_markup}
{INLINE_GLOSSARY_SCRIPT}
</body>
</html>
"""


def render_document_head(*, title: str, styles: str | None = None) -> str:
    style_markup = f"\n  <style>\n{styles}\n  </style>" if styles is not None else ""
    return f"""<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="{FAVICON_PATH}" sizes="any" type="image/x-icon">
  <title>{html.escape(title)}</title>{style_markup}
</head>"""


def render_inline_glossary_term(term: str, definition: str, term_id: str) -> str:
    """Render the governed inline glossary pattern with its accessible tooltip."""
    escaped_term = html.escape(term)
    escaped_definition = html.escape(definition, quote=True)
    escaped_term_id = html.escape(term_id, quote=True)
    definition_id = f"inline-glossary-definition-{term_id}"
    escaped_definition_id = html.escape(definition_id, quote=True)
    return (
        '<span class="inline-glossary-anchor">'
        f'<dfn class="inline-glossary-term" tabindex="0" role="term" '
        f'aria-description="{escaped_definition}" '
        f'aria-describedby="{escaped_definition_id}" '
        f'title="{escaped_definition}" data-definition="{escaped_definition}" '
        f'data-term-id="{escaped_term_id}">{escaped_term}</dfn>'
        f'<span class="inline-glossary-definition" id="{escaped_definition_id}" '
        f'role="tooltip">{html.escape(definition)}</span>'
        "</span>"
    )


def _civic_ledger_header(links: str, runtime_mode: str, badge_class: str) -> str:
    return f"""  <header class="civic-header">
    <div class="shell civic-header__inner">
      <div class="civic-brand">
        <a class="civic-brand__name" href="/">RecordsTracker</a>
        <span class="civic-brand__tagline">Review public records</span>
        <div class="mode-panel civic-mode-panel" aria-label="Retrieval mode">
          <span class="{badge_class}">{html.escape(runtime_mode)}</span>
        </div>
      </div>
      <span class="civic-menu-label" aria-hidden="true">Menu</span>
      <nav class="civic-nav" aria-label="Primary navigation">
        <ul>
{links}
        </ul>
      </nav>
    </div>
  </header>"""


def _civic_ledger_footer() -> str:
    return """  <footer class="civic-footer">
    <div class="shell civic-footer__inner">
      <div><strong>RecordsTracker</strong><span>Public CCLD records remain the source of record.</span></div>
      <nav aria-label="Footer navigation"><a href="/ccld/help">Help</a><span aria-hidden="true"> · </span><a href="/feedback">Feedback</a><span aria-hidden="true"> · </span><a href="/ccld/help#accessibility">Accessibility</a></nav>
    </div>
  </footer>"""


def render_action_group(
    *,
    primary: ActionItem | None = None,
    secondary: Sequence[ActionItem] = (),
    tertiary: Sequence[ActionItem] = (),
    aria_label: str = "Actions",
) -> str:
    button_items = []
    if primary is not None:
        button_items.append(_action_anchor(primary, "button"))
    button_items.extend(_action_anchor(item, "button button-secondary") for item in secondary)
    button_markup = ""
    if button_items:
        button_markup = f"""<div class="action-group" aria-label="{html.escape(aria_label)}">
{chr(10).join(button_items)}
</div>"""
    reference_markup = ""
    if tertiary:
        reference_links = "\n".join(_action_anchor(item, "") for item in tertiary)
        reference_markup = f"""<div class="action-reference-links" aria-label="{html.escape(aria_label)} reference links">
{reference_links}
</div>"""
    return "\n".join(part for part in (button_markup, reference_markup) if part)


def render_compare_facilities_views(active_view: str) -> str:
    """Render plain-link Compare Facilities views without a tab interaction."""
    items = []
    for view_id, label, href in COMPARE_FACILITIES_VIEWS:
        current = ' aria-current="page"' if view_id == active_view else ""
        items.append(
            f'          <li><a href="{html.escape(href, quote=True)}"{current}>'
            f"{html.escape(label)}</a></li>"
        )
    return f"""      <nav class="compare-facilities-views" aria-label="Compare facility information">
        <p><strong>Choose information to compare</strong></p>
        <ul>
{chr(10).join(items)}
        </ul>
      </nav>"""


def _action_anchor(item: ActionItem, class_name: str) -> str:
    class_attr = f' class="{html.escape(class_name, quote=True)}"' if class_name else ""
    aria_attr = (
        f' aria-label="{html.escape(item.aria_label, quote=True)}"'
        if item.aria_label
        else ""
    )
    return (
        f'  <a{class_attr} href="{html.escape(item.href, quote=True)}"{aria_attr}>'
        f"{html.escape(item.label)}</a>"
    )


def _nav_links(*, active_path: str | None, show_operator_navigation: bool = False) -> str:
    seen: set[str] = set()
    items: list[str] = []
    links = PRIMARY_NAV_LINKS + (OPERATOR_NAV_LINKS if show_operator_navigation else ())
    for label, href in links:
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
  if active_path == COMPARE_FACILITIES_PATH or active_path.startswith(
    f"{COMPARE_FACILITIES_PATH}/"
  ):
    return href == COMPARE_FACILITIES_PATH
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


INLINE_GLOSSARY_SCRIPT = """<script>
(function () {
  'use strict';
  var viewportPadding = 8;
  var triggerGap = 8;

  function definitionFor(term) {
    var sibling = term.nextElementSibling;
    if (sibling && sibling.classList.contains('inline-glossary-definition')) {
      return sibling;
    }
    var definitionId = term.getAttribute('aria-describedby');
    return definitionId ? document.getElementById(definitionId) : null;
  }

  function assignUniqueDefinitionIds() {
    var definitionCounts = {};
    document.querySelectorAll('.inline-glossary-term').forEach(function (term) {
      var definition = definitionFor(term);
      if (!definition || !definition.id) return;
      var baseId = definition.id;
      var count = definitionCounts[baseId] || 0;
      definitionCounts[baseId] = count + 1;
      if (count > 0) {
        var uniqueId = baseId + '-' + count;
        definition.id = uniqueId;
        term.setAttribute('aria-describedby', uniqueId);
      }
    });
  }

  function hide(term) {
    var definition = definitionFor(term);
    term.classList.remove('is-glossary-definition-visible');
    if (definition) {
      definition.classList.remove('is-visible');
      definition.style.left = '';
      definition.style.maxHeight = '';
      definition.style.top = '';
    }
  }

  function position(term, definition) {
    var trigger = term.getBoundingClientRect();
    var popup = definition.getBoundingClientRect();
    var availableBelow = window.innerHeight - trigger.bottom - triggerGap - viewportPadding;
    var availableAbove = trigger.top - triggerGap - viewportPadding;
    var showBelow = availableBelow >= availableAbove;
    var availableHeight = Math.max(0, showBelow ? availableBelow : availableAbove);
    definition.style.maxHeight = availableHeight + 'px';
    popup = definition.getBoundingClientRect();
    var left = Math.min(
      Math.max(trigger.left, viewportPadding),
      Math.max(viewportPadding, window.innerWidth - popup.width - viewportPadding)
    );
    definition.style.left = left + 'px';
    definition.style.top = (showBelow ? trigger.bottom + triggerGap : trigger.top - popup.height - triggerGap) + 'px';
  }

  function show(term) {
    var definition = definitionFor(term);
    if (!definition) return;
    document.querySelectorAll('.inline-glossary-term.is-glossary-definition-visible').forEach(function (other) {
      if (other !== term) hide(other);
    });
    term.removeAttribute('data-glossary-dismissed');
    term.classList.add('is-glossary-definition-visible');
    definition.classList.add('is-visible');
    position(term, definition);
  }

  assignUniqueDefinitionIds();
  document.querySelectorAll('.inline-glossary-term').forEach(function (term) {
    term.addEventListener('pointerenter', function () { show(term); });
    term.addEventListener('pointerleave', function () {
      if (document.activeElement !== term) hide(term);
    });
    term.addEventListener('focusin', function () { show(term); });
    term.addEventListener('focusout', function () { hide(term); });
    term.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        term.setAttribute('data-glossary-dismissed', 'true');
        hide(term);
      }
    });
  });

  window.addEventListener('resize', function () {
    document.querySelectorAll('.inline-glossary-term.is-glossary-definition-visible').forEach(function (term) {
      var definition = definitionFor(term);
      if (definition) position(term, definition);
    });
  });
  window.addEventListener('scroll', function () {
    document.querySelectorAll('.inline-glossary-term.is-glossary-definition-visible').forEach(function (term) {
      var definition = definitionFor(term);
      if (definition) position(term, definition);
    });
  }, true);
}());
</script>"""


SHARED_CSS = r"""
    :root {
      color-scheme: light;
      --ds-font-display: "Libre Baskerville", Georgia, "Times New Roman", serif;
      --ds-font-ui: "DM Sans", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      --ds-font-mono: "DM Mono", "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      --ds-page-bg: #F2F4F7;
      --ds-surface: #ffffff;
      --ds-surface-muted: #F8FAFB;
      --ds-surface-info: #EEF8F8;
      --ds-surface-success: #ECFDF5;
      --ds-surface-attention: #FFF3CD;
      --ds-text: #17212B;
      --ds-text-muted: #64748B;
      --ds-text-subtle: #7A8797;
      --ds-border: #D8E1E8;
      --ds-border-soft: rgba(15, 30, 45, 0.1);
      --ds-primary: #0D6E6E;
      --ds-primary-hover: #0A5555;
      --ds-primary-soft: #EFF8F8;
      --ds-link: #2457A6;
      --ds-link-hover: #173F78;
      --ds-info: #2457A6;
      --ds-info-soft: #E6EEF9;
      --ds-nav-active-bg: #EEF3FA;
      --ds-nav-active-border: #9DB4D6;
      --ds-attention: #92400E;
      --ds-attention-soft: #FEF3C7;
      --ds-danger: #9B2C3A;
      --ds-danger-soft: #FFF0F2;
      --ds-success: #2E7D4F;
      --ds-focus: #0D6E6E;
      --ds-radius-sm: 4px;
      --ds-radius-md: 6px;
      --ds-radius-lg: 8px;
      --ds-shadow-card: 0 1px 4px rgb(15 30 45 / 6%), 0 0 0 1px rgb(15 30 45 / 3%);
      --ds-shadow-raised: 0 2px 10px rgb(15 30 45 / 8%), 0 0 0 1px rgb(15 30 45 / 4%);
      --ds-space-1: 0.25rem;
      --ds-space-2: 0.5rem;
      --ds-space-3: 0.75rem;
      --ds-space-4: 1rem;
      --ds-space-5: 1.25rem;
      --bg: var(--ds-page-bg);
      --surface: var(--ds-surface);
      --surface-alt: var(--ds-surface-info);
      --surface-strong: var(--ds-text);
      --ink: var(--ds-text);
      --teal: var(--ds-primary);
      --muted: var(--ds-text-muted);
      --muted-2: var(--ds-text-subtle);
      --line: var(--ds-border);
      --line-soft: var(--ds-border-soft);
      --accent: var(--ds-primary);
      --accent-strong: var(--ds-primary-hover);
      --accent-soft: var(--ds-primary-soft);
      --blue: var(--ds-link);
      --blue-soft: var(--ds-info-soft);
      --amber: var(--ds-attention);
      --amber-soft: var(--ds-attention-soft);
      --rose: var(--ds-danger);
      --rose-soft: var(--ds-danger-soft);
      --status-attention-bg: var(--ds-surface-attention);
      --status-attention-line: #D89B00;
      --danger-bg: #FFF0F0;
      --danger-line: #B42318;
      --success-bg: var(--ds-surface-success);
      --success-line: var(--ds-success);
      --focus: var(--ds-focus);
      --shadow: var(--ds-shadow-card);
      --shadow-strong: var(--ds-shadow-raised);
    }
    * {
      box-sizing: border-box;
    }
    body {
      background: var(--bg);
      color: var(--ink);
      font-family: var(--ds-font-ui);
      font-size: 16px;
      line-height: 1.55;
      margin: 0;
    }
    .shell {
      margin: 0 auto;
      max-width: 87.5rem;
      padding: 0 1.25rem;
    }
    .app-shell {
      max-width: 87.5rem;
    }
    .app-shell-compact {
      max-width: 87.5rem;
    }
    .ds-page-bg {
      background: var(--ds-page-bg);
      color: var(--ds-text);
    }
    .ds-page-main {
      display: block;
    }
    .ds-surface {
      background: var(--ds-surface);
      border-color: var(--ds-border-soft);
    }
    .ds-text-muted {
      color: var(--ds-text-muted);
    }
    .ds-link {
      color: var(--ds-link);
      font-weight: 650;
    }
    .ds-link:hover {
      color: var(--ds-link-hover);
    }
    .ds-card,
    .ds-card--neutral,
    .ds-card--info,
    .ds-card--success {
      border: 1px solid var(--ds-border-soft);
      border-radius: var(--ds-radius-lg);
      box-shadow: var(--ds-shadow-card);
      padding: var(--ds-space-4);
    }
    .ds-card,
    .ds-card--neutral {
      background: var(--ds-surface);
    }
    .ds-card--info {
      background: var(--ds-surface-info);
      border-color: #B8CAE3;
    }
    .ds-card--success {
      background: var(--ds-surface-success);
      border-color: #94C3A9;
    }
    .ds-action-primary,
    .ds-action-secondary {
      border-radius: var(--ds-radius-md);
      display: inline-block;
      font-weight: 700;
      text-decoration: none;
    }
    .ds-action-primary {
      background: var(--ds-primary);
      border: 1px solid var(--ds-primary-hover);
      color: #fff;
    }
    .ds-action-secondary {
      background: var(--ds-surface);
      border: 1px solid var(--ds-border);
      color: var(--ds-link);
    }
    .ds-badge,
    .ds-chip {
      border: 1px solid var(--ds-border);
      border-radius: 999px;
      display: inline-flex;
      font-weight: 800;
      line-height: 1.2;
      white-space: nowrap;
    }
    .ds-badge {
      font-size: 0.88rem;
      gap: 0.35rem;
      padding: 0.35rem 0.65rem;
    }
    .ds-chip {
      font-size: 0.82rem;
      padding: 0.22rem 0.55rem;
    }
    .ds-badge--success,
    .ds-chip--success {
      background: var(--ds-surface-success);
      border-color: #94C3A9;
      color: #1E5D3B;
    }
    .ds-badge--info,
    .ds-chip--info {
      background: var(--ds-info-soft);
      border-color: #83A2D3;
      color: var(--ds-info);
    }
    .ds-badge--muted,
    .ds-chip--muted {
      background: #EEF1F3;
      color: #495661;
    }
    .ds-badge--attention,
    .ds-chip--attention {
      background: var(--ds-attention-soft);
      border-color: #D7A529;
      color: var(--ds-attention);
    }
    .ds-badge--danger,
    .ds-chip--danger {
      background: var(--ds-danger-soft);
      border-color: #D88992;
      color: var(--ds-danger);
    }
    .ds-form-control {
      border: 1px solid #9AA6AC;
      border-radius: var(--ds-radius-md);
      color: var(--ds-text);
      font: inherit;
      padding: 0.55rem 0.65rem;
    }
    .ds-table {
      border-collapse: collapse;
      width: 100%;
    }
    .site-header {
      background: rgba(255, 255, 255, 0.98);
      border-bottom: 1px solid var(--line-soft);
      box-shadow: 0 1px 8px rgb(23 33 43 / 7%);
    }
    .site-title-row {
      align-items: center;
      display: grid;
      gap: 0.9rem;
      grid-template-columns: minmax(10rem, 12rem) minmax(16rem, 30rem) max-content;
      justify-content: space-between;
      padding: 0.62rem 0;
    }
    .brand-title-block {
      align-items: start;
      display: grid;
      flex: 0 0 auto;
      gap: 0.08rem;
      min-width: 0;
    }
    .product-name {
      color: var(--ink);
      font-family: var(--ds-font-display);
      font-size: 1.02rem;
      font-weight: 900;
      letter-spacing: 0;
      margin: 0;
      text-decoration: none;
      text-transform: none;
    }
    .product-name span {
      color: var(--ds-primary);
    }
    .workspace-divider {
      background: var(--line);
      display: none;
      height: 1.15rem;
      width: 1px;
    }
    .workspace-label {
      color: var(--muted);
      font-size: 0.66rem;
      font-weight: 850;
      letter-spacing: 0.08em;
      line-height: 1.15;
      text-transform: uppercase;
      white-space: nowrap;
    }
    .shell-lookup {
      display: block;
      justify-self: stretch;
      max-width: 30rem;
      min-width: 0;
    }
    .shell-lookup input {
      background: var(--ds-surface-muted);
      border: 1px solid var(--line-soft);
      border-radius: var(--ds-radius-md);
      color: var(--ink);
      font: inherit;
      min-height: 2.5rem;
      padding: 0.48rem 0.85rem;
      width: 100%;
    }
    .shell-lookup input::placeholder {
      color: #8492A4;
    }
    .shell-nav-cluster {
      align-items: center;
      display: flex;
      flex: 0 1 auto;
      gap: 0.55rem;
      justify-content: flex-end;
      min-width: max-content;
    }
    .pilot-eyebrow, .pilot-actor, .site-footer p, .helper-text {
      color: var(--muted);
      margin: 0 0 0.4rem;
    }
    h1 {
      font-size: 2rem;
      line-height: 1.15;
      margin: 0 0 0.25rem;
      max-width: 58rem;
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
      color: var(--ds-link);
      font-weight: 650;
      overflow-wrap: anywhere;
      text-underline-offset: 0.16em;
    }
    a:hover {
      color: var(--ds-link-hover);
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
      flex-wrap: nowrap;
      gap: 0.12rem;
      list-style: none;
      margin: 0;
      padding: 0;
    }
    .site-nav a {
      border: 1px solid transparent;
      border-radius: 6px;
      display: inline-block;
      color: var(--ds-link);
      font-size: 0.9rem;
      line-height: 1.2;
      padding: 0.42rem 0.42rem;
      text-decoration: none;
      white-space: nowrap;
    }
    .site-nav a:hover {
      background: var(--ds-surface-muted);
      border-color: var(--ds-border);
      color: var(--ds-link-hover);
    }
    .site-nav a.is-active {
      background: transparent;
      border-color: transparent;
      box-shadow: inset 0 -2px 0 var(--ds-link);
      color: var(--ds-link-hover);
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
      padding-bottom: 3rem;
      padding-top: 1.35rem;
    }
    .app-page-main {
      max-width: 87.5rem;
    }
    .page-title-block {
      margin: 0 0 1rem;
      padding-top: 1.4rem;
    }
    .page-title-block .pilot-eyebrow {
      margin-bottom: 0.25rem;
    }
    .page-title-block .pilot-actor {
      margin-top: 0.35rem;
    }
    section {
      margin: 0 0 1.5rem;
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
      max-width: 100%;
      overflow-wrap: anywhere;
      padding: 0.6rem 0.85rem;
      text-align: center;
      text-decoration: none;
      white-space: normal;
    }
    button:hover, input[type="submit"]:hover, .button:hover {
      background: var(--accent-strong);
      color: #fff;
    }
    .button-large {
      font-size: 1.08rem;
      padding: 0.85rem 1.1rem;
    }
    .action-group {
      align-items: center;
      display: flex;
      flex-wrap: wrap;
      gap: 0.55rem;
      margin-top: 0.35rem;
    }
    .action-group .button,
    .action-group button {
      margin: 0;
    }
    .action-reference-links {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem 0.8rem;
      margin-top: 0.45rem;
    }
    .action-reference-links a {
      font-size: 0.94rem;
    }
    .button-secondary, button.secondary {
      background: #fff;
      border-color: var(--ds-border);
      color: var(--ds-link);
    }
    .button-secondary:hover, button.secondary:hover {
      background: var(--ds-info-soft);
      border-color: var(--ds-nav-active-border);
      color: var(--ds-link-hover);
    }
    .button-quiet {
      background: transparent;
      border-color: transparent;
      color: var(--ds-link);
      padding-left: 0;
      padding-right: 0;
    }
    .button-quiet:hover {
      background: transparent;
      color: var(--ds-link-hover);
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
      background: var(--ds-surface-muted);
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
      align-items: center;
      display: flex;
      justify-content: flex-end;
      min-width: max-content;
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
      background: var(--ds-surface-success);
      border-color: #94C3A9;
      color: #1E5D3B;
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
    .badge-attention {
      background: var(--amber-soft);
      border-color: #d7a529;
      color: var(--amber);
    }
    .badge-attention--warning {
      background: #FFF1B8;
      border-color: #B7791F;
      color: #7A3E00;
      box-shadow: inset 0 0 0 1px rgb(183 121 31 / 18%);
    }
    .badge-danger {
      background: var(--rose-soft);
      border-color: #d88992;
      color: var(--rose);
    }
    .hero-card {
      background: #ffffff;
      border: 1px solid var(--line-soft);
      border-left: 5px solid var(--ds-link);
      border-radius: 10px;
      box-shadow: var(--shadow-strong);
      padding: 1.4rem;
    }
    .hero-card h2 {
      font-size: 1.55rem;
      max-width: 54rem;
    }
    .facility-case-brief {
      background: transparent;
      border: 0;
      border-bottom: 1px solid var(--line-soft);
      border-radius: 0;
      box-shadow: none;
      margin-bottom: 0.34rem;
      padding: 0.08rem 0 0.58rem;
    }
    .facility-case-brief .case-brief-header {
      align-items: center;
    }
    .facility-case-brief h2 {
      font-size: 1rem;
      line-height: 1.2;
      margin-bottom: 0.16rem;
    }
    .facility-case-brief .launch-kicker {
      font-size: 0.74rem;
      margin-bottom: 0.18rem;
    }
    .facility-case-brief .metric-strip {
      display: flex;
      flex-wrap: wrap;
      gap: 0.35rem 0.65rem;
      margin: 0.26rem 0 0;
    }
    .facility-case-brief .brief-metric {
      align-items: baseline;
      background: transparent;
      border: 0;
      box-shadow: none;
      display: inline-flex;
      gap: 0.28rem;
      padding: 0;
    }
    .facility-case-brief .brief-metric strong {
      font-size: 0.96rem;
      line-height: 1;
    }
    .facility-case-brief .brief-metric span {
      font-size: 0.76rem;
      margin: 0;
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
      display: flex;
      flex-wrap: wrap;
      gap: 0.55rem;
      min-width: 12rem;
    }
    .case-brief-header {
      align-items: flex-start;
      display: flex;
      gap: 1rem;
      justify-content: space-between;
    }
    .support-note {
      background: var(--ds-surface-info);
      border-left: 4px solid var(--ds-info);
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
      background: #EEF1F3;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: #34495E;
      display: inline-flex;
      font-size: 0.82rem;
      font-weight: 800;
      padding: 0.22rem 0.55rem;
    }
    .badge-info {
      background: var(--ds-info-soft);
      border-color: #B8CAE3;
      color: var(--ds-info);
    }
    .source-chip {
      background: #E8F7F2;
      border-color: #75C9AE;
      color: #006B5F;
    }
    .workflow-cards {
      display: grid;
      gap: 0.85rem;
      grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
    }
    .workflow-cards .action-card p:last-child {
      margin-bottom: 0;
    }
    .action-card, .summary-card, .detail-card, .empty-state-card, .notice-card {
      background: var(--surface);
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 1rem;
    }
    .action-card {
      min-height: 100%;
    }
    .notice-card {
      background: var(--ds-surface-info);
      border-color: #B8CAE3;
    }
    .next-action-panel {
      background: var(--surface-alt);
      border-color: var(--ds-nav-active-border);
      border-left: 5px solid var(--ds-link);
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
      border-color: rgba(13, 110, 110, 0.18);
      gap: 0.85rem 1.1rem;
      grid-template-columns: minmax(0, 1fr) minmax(11rem, 13.5rem);
      padding: 0.78rem 0.9rem;
    }
    .worklist-intro {
      border-bottom: 1px solid var(--line-soft);
      padding-bottom: 0.45rem;
    }
    .worklist-intro h2,
    .worklist-intro p {
      margin-bottom: 0.3rem;
    }
    .worklist-controls {
      align-items: end;
      background: var(--surface);
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      box-shadow: 0 1px 2px rgb(23 33 43 / 5%);
      display: grid;
      gap: 1rem 1.5rem;
      grid-template-columns: minmax(14rem, 0.8fr) minmax(25rem, 1.2fr);
      padding: 0.85rem 1rem;
    }
    .worklist-controls h2,
    .worklist-controls p {
      margin-bottom: 0.2rem;
    }
    .worklist-result-count {
      color: var(--ink);
      font-weight: 800;
    }
    .compact-search-form,
    .worklist-search-field {
      display: grid;
      gap: 0.35rem;
      min-width: 0;
    }
    .compact-search-form input {
      width: 100%;
    }
    .compact-search-form .form-actions {
      margin-top: 0;
    }
    .review-worklist-section {
      min-width: 0;
    }
    .review-worklist {
      display: grid;
      gap: 0.55rem;
      list-style: none;
      margin: 0;
      padding: 0;
    }
    .review-worklist-row {
      align-items: center;
      background: var(--surface);
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      box-shadow: 0 1px 2px rgb(23 33 43 / 5%);
      display: grid;
      gap: 0.65rem 1rem;
      grid-template-areas: "identity dates outcome state action";
      grid-template-columns: minmax(15rem, 1.55fr) minmax(18rem, 1.15fr) minmax(10rem, 0.8fr) minmax(10rem, 0.8fr) minmax(9rem, 0.65fr);
      padding: 0.72rem 0.85rem;
    }
    .review-worklist-row.is-suggested {
      border-left: 4px solid var(--teal);
      box-shadow: 0 5px 14px rgb(13 110 110 / 9%);
      padding-left: 0.7rem;
    }
    .worklist-identity {
      grid-area: identity;
      min-width: 0;
    }
    .worklist-identity h3 {
      font-family: var(--ds-font-mono);
      font-size: 1rem;
      margin: 0.08rem 0 0.2rem;
      overflow-wrap: anywhere;
    }
    .worklist-review-next {
      align-items: center;
      color: var(--muted);
      display: flex;
      flex-wrap: wrap;
      font-size: 0.82rem;
      gap: 0.35rem;
      margin: 0 0 0.2rem;
    }
    .worklist-review-next > span {
      background: var(--ds-primary-soft);
      border: 1px solid #75B9B9;
      border-radius: 999px;
      color: var(--ds-primary);
      font-weight: 900;
      padding: 0.16rem 0.45rem;
    }
    .worklist-facility-name {
      color: var(--ink);
      font-weight: 750;
      margin: 0 0 0.15rem;
    }
    .worklist-facility-id {
      color: var(--muted);
      font-size: 0.84rem;
      margin: 0;
    }
    .worklist-field-label {
      color: var(--muted);
      display: block;
      font-size: 0.72rem;
      font-weight: 850;
      letter-spacing: 0.01em;
      line-height: 1.2;
      margin-bottom: 0.08rem;
    }
    .worklist-dates {
      display: grid;
      gap: 0.25rem 0.65rem;
      grid-area: dates;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      min-width: 0;
    }
    .worklist-dates p,
    .worklist-outcome p,
    .worklist-state p {
      margin: 0;
      min-width: 0;
      overflow-wrap: anywhere;
    }
    .worklist-dates p {
      white-space: nowrap;
    }
    .worklist-outcome {
      display: grid;
      gap: 0.35rem;
      grid-area: outcome;
      min-width: 0;
    }
    .worklist-review-flags .flag-list {
      gap: 0.25rem;
      margin: 0;
    }
    .worklist-review-flags .review-chip {
      font-size: 0.76rem;
      padding: 0.2rem 0.42rem;
    }
    .worklist-state {
      display: grid;
      gap: 0.3rem;
      grid-area: state;
      min-width: 0;
    }
    .worklist-state .review-chip {
      font-size: 0.76rem;
      padding: 0.2rem 0.42rem;
    }
    .worklist-source {
      color: #286A5B;
      font-weight: 700;
    }
    .worklist-action {
      grid-area: action;
      min-width: 0;
    }
    .worklist-action .button {
      margin: 0;
      white-space: normal;
      width: 100%;
    }
    .review-worklist-empty {
      background: #f8fafb;
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 1rem;
    }
    .review-worklist-empty h3,
    .review-worklist-empty p {
      margin-bottom: 0.35rem;
    }
    .worklist-result-details .aggregate-context {
      margin-top: 0.75rem;
    }
    .result-card.work-item.is-suggested {
      border-color: #86C8B9;
      box-shadow: 0 8px 18px rgb(13 110 110 / 10%);
    }
    .work-item-main {
      min-width: 0;
    }
    .work-item-main h3 {
      font-family: var(--ds-font-mono);
      font-size: 1.08rem;
      margin: 0 0 0.24rem;
    }
    .work-item-facts {
      display: grid;
      gap: 0.38rem 0.85rem;
      grid-template-columns: repeat(5, minmax(7rem, 1fr));
      margin: 0.12rem 0 0;
    }
    .work-item-fact-pair {
      display: grid;
      gap: 0.12rem;
      min-width: 0;
    }
    .work-item-facts dt {
      color: var(--muted);
      font-size: 0.76rem;
      font-weight: 850;
      margin: 0;
    }
    .work-item-facts dd {
      color: var(--ink);
      font-weight: 650;
      margin: 0;
      overflow-wrap: anywhere;
    }
    .work-item-actions {
      align-items: stretch;
      display: grid;
      gap: 0.34rem;
      justify-items: stretch;
      min-width: 0;
    }
    .work-item-actions .button {
      margin: 0;
      width: 100%;
    }
    .packet-preview-record {
      grid-template-columns: minmax(0, 1fr) minmax(0, 13.5rem);
    }
    .packet-record-actions {
      max-width: 100%;
      overflow-wrap: anywhere;
    }
    .packet-record-actions .button {
      line-height: 1.25;
      max-width: 100%;
      white-space: normal;
      word-break: break-word;
    }
    .queue-record-badges {
      display: flex;
      flex-wrap: wrap;
      gap: 0.3rem;
      margin-bottom: 0.42rem;
    }
    .work-item-source {
      margin: 0.42rem 0 0;
    }
    .work-item-source .source-chip {
      border-radius: var(--ds-radius-md);
      display: inline-flex;
      font-size: 0.78rem;
      font-weight: 850;
      line-height: 1.2;
      max-width: 100%;
      padding: 0.24rem 0.5rem;
      white-space: normal;
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
      color: var(--ds-link);
      font-size: 0.92rem;
    }
    .detail-shell {
      display: grid;
      gap: 0.75rem;
    }
    .reviewer-detail-page {
      gap: 0.75rem;
    }
    .reviewer-detail-context {
      align-items: center;
      color: var(--muted);
      display: flex;
      flex-wrap: wrap;
      font-size: 0.88rem;
      gap: 0.4rem;
    }
    .reviewer-detail-context a {
      font-weight: 800;
      text-decoration: none;
    }
    .detail-heading-context {
      color: var(--muted);
      font-size: 0.98rem;
      font-weight: 700;
      margin: -0.25rem 0 0.35rem;
    }
    .complaint-overview-card {
      border-color: #C9DCE0;
      border-top: 3px solid var(--teal);
      box-shadow: var(--shadow-strong);
      padding: 0;
      overflow: visible;
    }
    .overview-card-bar {
      align-items: center;
      background: #EEF8F7;
      border-bottom: 1px solid var(--line-soft);
      border-radius: 8px 8px 0 0;
      display: flex;
      gap: 0.75rem;
      justify-content: space-between;
      padding: 0.55rem 0.85rem;
    }
    .overview-card-bar .launch-kicker {
      color: #165F61;
      margin: 0;
    }
    .overview-layout {
      align-items: start;
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(15rem, 18rem);
    }
    .overview-main {
      display: grid;
      gap: 0.42rem;
      padding: 0.66rem 0.86rem 0.58rem;
    }
    .overview-primary-row {
      align-items: start;
      display: flex;
      gap: 1rem;
      justify-content: space-between;
    }
    .complaint-number-heading {
      color: var(--ink);
      font-family: var(--ds-font-mono);
      font-size: 1.25rem;
      line-height: 1.2;
      margin: 0 0 0.35rem;
    }
    .finding-context-line {
      align-items: center;
      display: flex;
      flex-wrap: wrap;
      gap: 0.45rem;
      margin: 0;
    }
    .overview-source-action {
      flex: 0 0 auto;
    }
    .overview-source-action .button {
      box-shadow: 0 1px 2px rgb(23 33 43 / 8%);
    }
    .overview-side-panel {
      background: #F8FBFB;
      border-left: 1px solid var(--line-soft);
      border-radius: 0 0 8px 0;
      display: grid;
      gap: 0.34rem;
      align-content: start;
      align-self: start;
      padding: 0.66rem 0.72rem;
    }
    .overview-review-cues,
    .overview-source-narrative,
    .overview-timeline {
      display: grid;
      gap: 0.34rem;
    }
    .overview-review-cues h3,
    .overview-source-narrative h3,
    .overview-timeline h3 {
      color: var(--ink);
      font-size: 0.88rem;
      font-weight: 900;
      letter-spacing: 0;
      margin: 0;
      text-transform: uppercase;
    }
    .section-heading-with-copy {
      align-items: center;
      display: inline-flex;
      gap: 0.45rem;
    }
    .overview-source-narrative blockquote {
      border-left: 3px solid #16B8AC;
      color: var(--ink);
      font-size: 0.98rem;
      font-weight: 500;
      line-height: 1.62;
      margin: 0;
      padding: 0.22rem 0 0.22rem 0.62rem;
    }
    .overview-tertiary-actions {
      border-top: 1px solid var(--line-soft);
      display: grid;
      gap: 0.45rem;
      padding-top: 0.75rem;
    }
    .overview-tertiary-actions a {
      font-size: 0.92rem;
      font-weight: 800;
      text-decoration: none;
    }
    .reviewer-brief-card {
      border-left-color: var(--teal);
    }
    .reviewer-brief-card.hero-card {
      padding: 1rem;
    }
    .facility-identity-line {
      color: var(--muted);
      font-weight: 700;
      margin-bottom: 0.35rem;
    }
    .top-fact-strip {
      background: #F8FAFB;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      display: grid;
      gap: 0;
      grid-template-columns: minmax(7.5rem, 0.8fr) minmax(18rem, 2.3fr) minmax(7rem, 0.8fr) minmax(5.25rem, 0.62fr) minmax(5.5rem, 0.62fr);
      align-items: center;
      margin: 0;
      overflow: hidden;
      padding: 0;
    }
    .compact-fact {
      align-items: start;
      background: transparent;
      border-right: 1px solid var(--line-soft);
      display: grid;
      gap: 0.08rem;
      max-width: 100%;
      min-width: 0;
      padding: 0.48rem 0.62rem;
    }
    .compact-fact:last-child {
      border-right: 0;
    }
    .compact-fact dt {
      color: var(--muted);
      font-size: 0.68rem;
      font-weight: 900;
      line-height: 1.2;
      text-transform: uppercase;
      white-space: nowrap;
    }
    .compact-fact dt::after {
      content: "";
    }
    .compact-fact dd {
      color: var(--ink);
      font-size: 0.9rem;
      font-weight: 850;
      line-height: 1.25;
      margin: 0;
      overflow-wrap: anywhere;
    }
    .compact-fact--name {
      min-width: min(18rem, 100%);
    }
    .compact-fact--name dd {
      display: -webkit-box;
      font-weight: 760;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 2;
      overflow: hidden;
      overflow-wrap: normal;
    }
    .compact-fact--status dd {
      color: var(--ink);
      font-size: 0.9rem;
      padding: 0;
    }
    .reviewer-brief-card .launch-value {
      font-size: 0.98rem;
      margin-bottom: 0.55rem;
    }
    .reviewer-primary-actions {
      align-items: center;
      border-top: 1px solid var(--line-soft);
      display: flex;
      flex-wrap: wrap;
      gap: 0.55rem;
      margin-top: 1rem;
      padding-top: 0.85rem;
    }
    .button-disabled {
      background: #eef1f3;
      border-color: var(--line);
      color: var(--muted);
      cursor: not-allowed;
    }
    .copy-summary-details {
      border: 0;
      margin: 0;
      padding: 0;
    }
    .copy-summary-details > summary {
      background: #ffffff;
      border: 1px solid var(--line);
      border-radius: 6px;
      color: var(--ds-link);
      display: inline-flex;
      font-size: 0.92rem;
      line-height: 1.2;
      padding: 0.55rem 0.75rem;
    }
    .copyable-summary {
      background: #f8fafb;
      border: 1px solid var(--line);
      border-radius: 8px;
      margin: 0.65rem 0 0;
      max-width: 52rem;
      overflow-x: auto;
      padding: 0.8rem;
      white-space: pre-wrap;
    }
    .copyable-value {
      align-items: center;
      display: inline-flex;
      gap: 0.35rem;
      max-width: 100%;
    }
    .copy-icon-button {
      align-items: center;
      background: transparent;
      border: 1px solid transparent;
      border-radius: 4px;
      color: #64748B;
      cursor: pointer;
      display: inline-flex;
      font: inherit;
      font-size: 0.82rem;
      font-weight: 800;
      justify-content: center;
      line-height: 1;
      min-height: 1.45rem;
      min-width: 1.45rem;
      padding: 0.15rem;
    }
    .copy-icon-button:hover {
      background: var(--ds-primary-soft);
      border-color: #B7E2DD;
      color: var(--ds-primary);
    }
    .copy-icon-button svg {
      display: block;
      height: 1rem;
      width: 1rem;
    }
    .review-status-panel {
      display: grid;
      gap: 0.34rem;
    }
    .review-status-panel .summary-list {
      font-size: 0.86rem;
      gap: 0.18rem 0.55rem;
      grid-template-columns: minmax(6rem, 8rem) 1fr;
      margin: 0;
    }
    .review-status-panel h2 {
      border-bottom: 1px solid var(--line-soft);
      font-size: 1rem;
      font-weight: 900;
      margin: 0;
      padding-bottom: 0.45rem;
    }
    .reviewer-panel-actions {
      align-items: stretch;
      border-bottom: 1px solid var(--line-soft);
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      margin: 0.44rem 0 0.5rem;
      padding-bottom: 0.5rem;
    }
    .reviewer-panel-actions .button,
    .reviewer-panel-actions .button-disabled {
      flex: 1 1 9rem;
      justify-content: center;
      text-align: center;
    }
    .reviewer-panel-note {
      color: var(--muted);
      font-size: 0.9rem;
      margin: 0.25rem 0 0.48rem;
    }
    .review-status-panel form p {
      margin: 0.28rem 0;
    }
    .review-status-panel select,
    .review-status-panel textarea,
    .review-status-panel button {
      width: 100%;
    }
    .review-status-panel textarea {
      min-height: 3.25rem;
    }
    .review-status-panel h3 {
      font-size: 0.98rem;
      margin-bottom: 0.35rem;
    }
    .quick-review-section h2 {
      font-size: 1rem;
    }
    .quick-review-section h3 {
      font-size: 0.98rem;
      margin-top: 0.7rem;
    }
    .quick-review-grid {
      display: grid;
      gap: 0.75rem;
      grid-template-columns: repeat(6, minmax(0, 1fr));
    }
    .quick-review-card {
      background: #ffffff;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      box-shadow: 0 1px 2px rgb(23 33 43 / 5%);
      color: var(--ink);
      display: grid;
      gap: 0.35rem;
      min-height: 8.25rem;
      padding: 0.8rem;
      text-decoration: none;
    }
    .quick-review-card:hover,
    .quick-review-card:focus {
      border-color: var(--ds-nav-active-border);
      box-shadow: var(--shadow);
      outline: 2px solid transparent;
    }
    .quick-review-card strong {
      color: var(--teal);
      overflow-wrap: anywhere;
    }
    .quick-review-card span:last-child {
      color: var(--ds-link);
      font-size: 0.88rem;
      font-weight: 800;
      margin-top: auto;
    }
    .reviewer-brief-card .quick-review-grid {
      gap: 0.45rem;
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .reviewer-brief-card .quick-review-card {
      gap: 0.2rem;
      min-height: 0;
      padding: 0.55rem;
    }
    .reviewer-brief-card .quick-review-card span:last-child {
      font-size: 0.8rem;
    }
    .reviewer-note-guidance {
      background: #ffffff;
      margin: 0.55rem 0;
    }
    .source-confidence-details {
      background: var(--surface-alt);
    }
    .inline-glossary-term {
      border-bottom: 1px dotted currentColor;
      color: var(--ink);
      cursor: help;
      font-style: normal;
      font-family: inherit;
      font-size: inherit;
      font-weight: inherit;
      text-decoration: none;
      text-underline-offset: 0.18em;
    }
    .inline-glossary-term:focus {
      border-radius: 3px;
      outline: 2px solid var(--focus);
      outline-offset: 3px;
    }
    .inline-glossary-anchor {
      display: inline;
    }
    .inline-glossary-definition {
      background: #ffffff;
      border: 1px solid var(--line);
      border-radius: 6px;
      box-shadow: var(--shadow-strong);
      color: var(--ink);
      display: block;
      font-size: 0.86rem;
      font-weight: 600;
      line-height: 1.35;
      max-width: min(22rem, calc(100vw - 1rem));
      overflow-y: auto;
      padding: 0.55rem 0.65rem;
      pointer-events: none;
      position: fixed;
      text-transform: none;
      visibility: hidden;
      width: max-content;
      z-index: 2;
    }
    .inline-glossary-definition.is-visible {
      visibility: visible;
    }
    .why-flagged-panel {
      background: #fffaf0;
      border-color: #efd39a;
    }
    .timeline-list {
      display: grid;
      gap: 0.5rem;
      grid-template-columns: repeat(auto-fit, minmax(8.5rem, 1fr));
      list-style: none;
      margin: 0;
      padding: 0;
    }
    .timeline-item {
      border-left: 0;
      border-top: 3px solid var(--teal);
      display: grid;
      gap: 0.15rem;
      padding-top: 0.45rem;
    }
    .rt-timeline {
      --timeline-marker-size: 1.08rem;
      --timeline-line-top: calc(1rem + (var(--timeline-marker-size) / 2));
      padding: 1rem 0 0;
      position: relative;
    }
    .rt-timeline__line {
      background: rgba(15, 30, 45, 0.18);
      height: 1.5px;
      left: 10%;
      position: absolute;
      right: 10%;
      top: var(--timeline-line-top);
    }
    .rt-timeline.has-gap .rt-timeline__line::after {
      background: #FBBF24;
      content: "";
      height: 2px;
      left: 0;
      position: absolute;
      top: -0.25px;
      width: 33.333%;
    }
    .timeline-list-linear {
      align-items: start;
      gap: 0;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      padding-bottom: 0;
      padding-top: 0;
      position: relative;
    }
    .timeline-list-linear::before {
      display: none;
    }
    .timeline-list-linear.has-gap::after {
      display: none;
    }
    .timeline-list-linear .timeline-item {
      border-top: 0;
      justify-items: center;
      min-width: 0;
      padding-top: 0;
      position: relative;
      text-align: center;
    }
    .timeline-marker {
      align-items: center;
      background: #0D6E6E;
      border: 3px solid #ffffff;
      border-radius: 999px;
      box-shadow: 0 0 0 1px #0A6F6A;
      display: inline-flex;
      height: var(--timeline-marker-size);
      justify-content: center;
      margin-bottom: 0.3rem;
      position: relative;
      width: var(--timeline-marker-size);
      z-index: 1;
    }
    .timeline-marker--received {
      background: #ffffff;
      border-color: #0D6E6E;
      border-radius: 5px;
      box-shadow: 0 0 0 3px #DFF5F2;
      width: 0.92rem;
    }
    .timeline-marker--received::after {
      background: #0D6E6E;
      border-radius: 2px;
      content: "";
      height: 0.5rem;
      width: 0.38rem;
    }
    .timeline-marker--report {
      background: #2457A6;
      box-shadow: 0 0 0 1px #2457A6;
    }
    .timeline-marker--signed {
      background: #2E7D4F;
      box-shadow: 0 0 0 1px #2E7D4F;
    }
    .timeline-marker--activity::after,
    .timeline-marker--visit::after,
    .timeline-marker--report::after,
    .timeline-marker--signed::after {
      background: #ffffff;
      border-radius: 999px;
      content: "";
      height: 0.28rem;
      width: 0.28rem;
    }
    .timeline-list-linear .timeline-label {
      color: var(--ink);
      font-size: 0.78rem;
      font-weight: 900;
      line-height: 1.15;
    }
    .rt-timeline__date {
      display: block;
      font-size: 0.84rem;
      line-height: 1.25;
      margin-top: 0.12rem;
    }
    .timing-summary-heading {
      color: var(--muted);
      font-size: 0.78rem;
      font-weight: 900;
      letter-spacing: 0.035em;
      margin: 0.72rem 0 0;
      text-transform: uppercase;
    }
    .timing-summary {
      display: grid;
      gap: 0.45rem;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      margin: 0;
    }
    .timing-fact {
      background: var(--surface-alt);
      border: 1px solid var(--line-soft);
      border-radius: var(--ds-radius-md);
      min-width: 0;
      padding: 0.5rem 0.58rem;
    }
    .timing-fact dt {
      color: var(--muted);
      font-size: 0.76rem;
      font-weight: 750;
      line-height: 1.25;
    }
    .timing-fact dd {
      color: var(--ink);
      font-size: 0.92rem;
      font-weight: 900;
      margin: 0.18rem 0 0;
    }
    .timing-discrepancy {
      background: var(--ds-attention-soft);
      border-left: 4px solid #D89D2B;
      color: var(--ink);
      margin: 0.55rem 0 0;
      padding: 0.5rem 0.62rem;
    }
    .timeline-gap-badge {
      list-style: none;
      margin: 0;
      position: absolute;
      left: 25%;
      text-align: center;
      top: calc(var(--timeline-line-top) - 0.68rem);
      transform: translateX(-50%);
      width: max-content;
      z-index: 2;
    }
    .timeline-gap-badge .review-chip {
      border-radius: var(--ds-radius-md);
      font-size: 0.75rem;
      padding: 0.18rem 0.45rem;
    }
    .finding-badge {
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 999px;
      display: inline-flex;
      font-size: 0.82rem;
      font-weight: 850;
      line-height: 1.2;
      padding: 0.24rem 0.55rem;
    }
    .finding-badge--unsubstantiated {
      background: #F1F5F8;
      border-color: #C7D3DE;
      color: #34495E;
    }
    .finding-badge--substantiated {
      background: var(--ds-attention-soft);
      border-color: #D89D2B;
      color: #704600;
    }
    .finding-badge--inconclusive,
    .finding-badge--unknown {
      background: var(--ds-info-soft);
      border-color: #9DB4D6;
      color: var(--ds-link-hover);
    }
    #allegations-findings-heading {
      color: var(--ink);
      font-size: 1rem;
      font-weight: 900;
      letter-spacing: 0;
      text-transform: uppercase;
    }
    .timeline-label {
      color: var(--muted);
      font-size: 0.88rem;
      font-weight: 800;
    }
    .timeline-item strong {
      color: var(--ink);
    }
    .timeline-item em {
      color: var(--muted);
      font-style: normal;
    }
    .glossary-details {
      border-top: 1px solid var(--line-soft);
    }
    .glossary-list {
      display: grid;
      gap: 0.45rem 1rem;
      grid-template-columns: minmax(10rem, 15rem) 1fr;
    }
    .glossary-list dt {
      color: var(--ink);
      font-weight: 800;
    }
    .glossary-list dd {
      margin: 0;
    }
    .reviewer-history-section table {
      margin-top: 0.75rem;
    }
    .related-activity-list {
      display: grid;
      gap: 0.75rem;
      grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
      margin: 0.85rem 0;
    }
    .related-activity-card {
      background: #ffffff;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      box-shadow: 0 1px 2px rgb(23 33 43 / 5%);
      display: grid;
      gap: 0.45rem;
      padding: 0.85rem;
    }
    .related-activity-card header {
      align-items: center;
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
      justify-content: space-between;
    }
    .related-activity-type {
      color: var(--teal);
      font-size: 0.82rem;
      font-weight: 800;
    }
    .related-activity-card h3 {
      font-size: 1rem;
      margin: 0;
      overflow-wrap: anywhere;
    }
    .related-activity-card p {
      color: var(--muted);
      font-size: 0.9rem;
      margin: 0;
    }
    .related-activity-meta {
      display: grid;
      font-size: 0.9rem;
      gap: 0.2rem 0.65rem;
      grid-template-columns: minmax(4.5rem, 6rem) 1fr;
      margin: 0;
    }
    .related-activity-meta dt {
      color: var(--muted);
      font-weight: 800;
    }
    .related-activity-meta dd {
      margin: 0;
    }
    .related-source-details {
      margin-top: 0.75rem;
    }
    .related-source-details section {
      padding-top: 0.6rem;
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
      border-left: 5px solid var(--status-attention-line);
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
    .dense-page-header {
      align-items: start;
      display: grid;
      gap: 1rem;
      grid-template-columns: minmax(0, 1fr) auto;
    }
    .dense-page-header .form-actions,
    .dense-page-actions {
      justify-content: flex-end;
    }
    .dense-section-header {
      align-items: end;
      border-bottom: 1px solid var(--line-soft);
      display: flex;
      gap: 0.75rem;
      justify-content: space-between;
      margin-bottom: 0.75rem;
      padding-bottom: 0.55rem;
    }
    .dense-section-header h2,
    .dense-section-header h3,
    .dense-section-header p {
      margin-bottom: 0;
    }
    .dense-card-grid {
      display: grid;
      gap: 0.85rem;
      grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
    }
    .dense-card-grid .result-card,
    .dense-card-grid .work-item {
      min-height: 100%;
    }
    .dense-table-details,
    .diagnostic-details {
      background: transparent;
      border-top: 1px solid var(--line-soft);
      box-shadow: none;
      margin-top: 1rem;
      padding-top: 0.75rem;
    }
    .diagnostic-details > summary::before {
      color: var(--muted);
      content: "Operator/runtime ";
      font-weight: 700;
    }
    .dense-fact-row {
      display: grid;
      gap: 0.65rem;
      grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
      margin: 0.75rem 0;
    }
    .dense-fact-row .fixed-field,
    .dense-fact-row .stat-card {
      min-height: 100%;
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
    .form-actions.action-group {
      gap: 0.55rem;
      margin-top: 0.35rem;
    }
    .compact-filter-form {
      display: grid;
      gap: 0.85rem;
    }
    .compact-filter-form fieldset {
      border: 0;
      margin: 0;
      padding: 0;
    }
    .compact-filter-form legend {
      font-weight: 800;
      margin-bottom: 0.45rem;
    }
    .filter-chip-group {
      display: flex;
      flex-wrap: wrap;
      gap: 0.45rem;
    }
    .filter-chip {
      align-items: center;
      background: #ffffff;
      border: 1px solid var(--line);
      border-radius: 999px;
      cursor: pointer;
      display: inline-flex;
      gap: 0.35rem;
      min-height: 2rem;
      padding: 0.35rem 0.65rem;
    }
    .filter-chip:focus-within,
    .filter-chip:hover {
      border-color: var(--ds-nav-active-border);
      box-shadow: 0 0 0 3px rgb(36 87 166 / 12%);
    }
    .filter-chip input {
      accent-color: var(--ds-link);
      margin: 0;
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
      border-color: var(--ds-nav-active-border);
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
      border-color: var(--ds-nav-active-border);
      box-shadow: 0 14px 34px rgb(36 87 166 / 14%);
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
      max-width: min(42rem, 100%);
      position: relative;
    }
    .facility-suggestions {
      background: var(--surface);
      border: 1px solid var(--ds-nav-active-border);
      border-radius: 8px;
      box-shadow: 0 8px 24px rgb(19 32 43 / 14%);
      left: 0;
      list-style: none;
      margin: 0;
      max-height: 18rem;
      overflow-x: hidden;
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
      min-width: 0;
      padding: 0.5rem 0.6rem;
      text-align: left;
      width: 100%;
    }
    .suggestion-btn:hover, .suggestion-btn:focus {
      background: var(--ds-info-soft);
      color: var(--ink);
    }
    .suggestion-main {
      align-items: flex-start;
      display: flex;
      flex-wrap: wrap;
      gap: 0.35rem;
      min-width: 0;
      width: 100%;
    }
    .suggestion-status {
      border: 1px solid var(--line);
      border-radius: 4px;
      display: inline-flex;
      flex: 0 0 auto;
      font-size: 0.72rem;
      font-weight: 800;
      line-height: 1.2;
      padding: 0.12rem 0.3rem;
      white-space: nowrap;
    }
    .suggestion-status-licensed {
      background: var(--success-bg);
      border-color: var(--success-line);
      color: #1E5D3B;
    }
    .suggestion-status-closed {
      background: var(--ds-danger-soft);
      border-color: #D88992;
      color: var(--ds-danger);
    }
    .suggestion-status-pending {
      background: var(--ds-attention-soft);
      border-color: #D7A529;
      color: var(--ds-attention);
    }
    .suggestion-status-other {
      background: #EEF1F3;
      color: #495661;
    }
    .suggestion-name {
      flex: 1 1 13rem;
      font-size: 0.96rem;
      font-weight: 700;
      line-height: 1.3;
      min-width: 0;
      overflow-wrap: anywhere;
    }
    .suggestion-badge {
      background: var(--surface-alt);
      border: 1px solid var(--line);
      border-radius: 4px;
      display: inline-block;
      font-size: 0.78rem;
      font-weight: 700;
      max-width: 100%;
      overflow-wrap: anywhere;
      padding: 0.05rem 0.3rem;
      white-space: normal;
    }
    .suggestion-details {
      color: var(--muted);
      font-size: 0.82rem;
      line-height: 1.3;
      overflow-wrap: anywhere;
      white-space: normal;
    }
    .suggestion-empty {
      color: var(--muted);
      display: block;
      font-size: 0.88rem;
      padding: 0.5rem 0.6rem;
    }
    .facility-selected-card {
      background: var(--ds-info-soft);
      border: 2px solid var(--ds-nav-active-border);
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
    .civic-ledger-page {
      --ds-page-bg: #f6f1e7;
      --ds-surface: #fffdf8;
      --ds-surface-muted: #f2eadc;
      --ds-text: #17212b;
      --ds-text-muted: #5f6872;
      --ds-border: #b8b1a5;
      --ds-border-soft: #d8d0c3;
      --ds-primary: #14283d;
      --ds-primary-hover: #0b1d2f;
      --ds-primary-soft: #e7edf5;
      --ds-link: #174d74;
      --ds-link-hover: #0d3654;
      --ds-info: #254f73;
      --ds-info-soft: #e7edf5;
      --ds-nav-active-border: #d5a21a;
      --ds-attention: #7b5608;
      --ds-attention-soft: #fff1c7;
      --ds-danger: #9f281c;
      --ds-danger-soft: #fde8e6;
      --ds-success: #1c5a35;
      --ds-focus: #d5a21a;
      --bg: var(--ds-page-bg);
      --surface: var(--ds-surface);
      --surface-alt: var(--ds-surface-muted);
      --ink: var(--ds-text);
      --muted: var(--ds-text-muted);
      --line: var(--ds-border);
      --line-soft: var(--ds-border-soft);
      --accent: var(--ds-primary);
      --accent-strong: var(--ds-primary-hover);
      --focus: var(--ds-focus);
      background: var(--ds-page-bg);
      font-family: Inter, "Segoe UI", system-ui, sans-serif;
      font-size: 14px;
      line-height: 1.42;
    }
    .civic-ledger-page .shell {
      max-width: 90rem;
      padding-left: 1.5rem;
      padding-right: 1.5rem;
    }
    .civic-header,
    .civic-footer {
      background: #14283d;
      color: #fff;
    }
    .civic-header {
      margin: 1.5rem 1.5rem 0;
    }
    .civic-header__inner {
      align-items: center;
      display: grid;
      gap: 1.5rem;
      grid-template-columns: minmax(16rem, 1fr) auto minmax(32rem, auto);
      min-height: 5rem;
      padding-bottom: 1rem;
      padding-top: 1rem;
    }
    .civic-brand {
      display: grid;
      gap: 0.55rem;
    }
    .civic-brand__name {
      color: #fff;
      font-size: 1.15rem;
      font-weight: 700;
      text-decoration: none;
    }
    .civic-brand__tagline {
      font-size: 0.82rem;
    }
    .civic-mode-panel {
      justify-content: flex-start;
    }
    .civic-menu-label {
      color: #f3d77d;
      display: none;
      font-weight: 650;
    }
    .civic-nav ul {
      display: grid;
      gap: 0.75rem;
      grid-template-columns: repeat(7, minmax(5rem, auto));
      list-style: none;
      margin: 0;
      padding: 0;
    }
    .civic-nav a {
      border-bottom: 3px solid transparent;
      color: #fff;
      display: block;
      font-weight: 500;
      min-height: 2.75rem;
      padding: 0.7rem 0.35rem 0.45rem;
      text-align: center;
      text-decoration: none;
    }
    .civic-nav a:hover,
    .civic-nav a:focus-visible,
    .civic-nav a.is-active {
      border-bottom-color: #d5a21a;
      color: #fff;
    }
    .civic-ledger-page .app-page-main {
      padding-bottom: 1rem;
      padding-top: 1.15rem;
    }
    .civic-ledger-page .page-title-block {
      margin-bottom: 0;
    }
    .civic-ledger-page h1 {
      font-size: 1.625rem;
      font-weight: 650;
      line-height: 2.375rem;
    }
    .intelligence-purpose {
      color: var(--muted);
      margin-bottom: 1rem;
    }
    .compare-facilities-views {
      border-block: 1px solid #b8b1a5;
      margin-bottom: 1rem;
      padding-block: 0.75rem;
    }
    .compare-facilities-views p {
      margin: 0 0 0.5rem;
    }
    .compare-facilities-views ul {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem 1rem;
      list-style: none;
      margin: 0;
      padding: 0;
    }
    .compare-facilities-views a {
      display: inline-block;
      font-weight: 650;
      padding: 0.35rem 0;
    }
    .compare-facilities-views a[aria-current="page"] {
      text-decoration-thickness: 0.2rem;
      text-underline-offset: 0.35rem;
    }
    .intelligence-scope,
    .intelligence-filters,
    .facility-intelligence-results,
    .intelligence-message {
      background: #fffdf8;
      border: 1px solid #b8b1a5;
      border-radius: 4px;
      box-shadow: none;
      margin-bottom: 1rem;
      padding: 1rem;
    }
    .intelligence-scope p,
    .intelligence-message p {
      margin-bottom: 0.25rem;
    }
    .intelligence-scope p:last-child,
    .intelligence-message p:last-child {
      color: var(--muted);
      margin-bottom: 0;
    }
    .intelligence-filters h2,
    .facility-intelligence-results h2,
    .intelligence-message h2 {
      font-size: 1rem;
      line-height: 1.45;
      margin-bottom: 0.75rem;
    }
    .civic-ledger-page .facility-intelligence-filter-grid {
      gap: 0.2rem 0;
      grid-template-columns: repeat(7, minmax(8.5rem, 1fr));
    }
    .civic-ledger-page .facility-intelligence-filter-grid p:nth-child(8) {
      grid-column: 1 / 2;
    }
    .civic-ledger-page .facility-intelligence-filter-grid label,
    .facility-intelligence-sort label {
      display: block;
      font-size: 0.8rem;
      font-weight: 600;
      margin-bottom: 0.25rem;
    }
    .civic-ledger-page .facility-intelligence-filter-grid input,
    .civic-ledger-page .facility-intelligence-filter-grid select,
    .facility-intelligence-sort select {
      background: #fffdf8;
      border-color: #b8b1a5;
      border-radius: 4px;
      min-height: 2.5rem;
      width: 100%;
    }
    .civic-ledger-page button,
    .civic-ledger-page .button {
      border-radius: 4px;
      min-height: 2.5rem;
    }
    .civic-ledger-page .button-secondary {
      background: #fffdf8;
      border-color: #14283d;
      color: #14283d;
    }
    .civic-ledger-page .button-secondary:hover {
      background: #f2eadc;
      color: #14283d;
    }
    .button-link {
      align-items: center;
      display: inline-flex;
      min-height: 2.75rem;
      padding: 0 0.75rem;
      text-decoration: none;
    }
    .applied-filter-empty {
      color: var(--muted);
      margin: 0;
    }
    .applied-filters ul {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      list-style: none;
      margin: 0;
      padding: 0;
    }
    .applied-filter-chip {
      align-items: center;
      background: #fffdf8;
      border: 1px solid #b8b1a5;
      border-radius: 999px;
      color: #17212b;
      display: inline-flex;
      gap: 0.45rem;
      min-height: 2rem;
      padding: 0.35rem 0.75rem;
      text-decoration: none;
    }
    .intelligence-glossary-line {
      align-items: center;
      display: flex;
      gap: 3rem;
      margin: 0 0 1rem 0.25rem;
      max-width: 22rem;
    }
    .intelligence-glossary-line > span:last-child {
      color: var(--muted);
    }
    .civic-ledger-page .inline-glossary-term {
      border-bottom-color: #174d74;
      color: #174d74;
    }
    .intelligence-message--info {
      background: #e7edf5;
      border-color: #82a6c7;
      color: #254f73;
    }
    .intelligence-message--review {
      background: #fff1c7;
      border-color: #dda800;
      color: #7b5608;
    }
    .intelligence-message--error {
      background: #fde8e6;
      border-color: #e07a70;
      color: #9f281c;
    }
    .facility-intelligence-results {
      padding: 0;
    }
    .facility-intelligence-results__header {
      align-items: end;
      display: flex;
      justify-content: space-between;
      padding: 1rem;
    }
    .facility-intelligence-results__header h2 {
      margin: 0;
    }
    .facility-inventory-context {
      align-items: start;
      background: #f5efe3;
      border-bottom: 1px solid #b8b1a5;
      border-top: 1px solid #b8b1a5;
      display: flex;
      gap: 1rem;
      justify-content: space-between;
      padding: 0.75rem 1rem;
    }
    .facility-inventory-context__summary {
      display: grid;
      gap: 0.35rem;
      min-width: 0;
    }
    .facility-result-position {
      font-weight: 700;
      margin: 0;
    }
    .facility-order-description {
      color: var(--muted);
      font-size: 0.84rem;
      margin: 0;
      overflow-wrap: anywhere;
    }
    .facility-inventory-context .applied-filter-empty {
      font-size: 0.82rem;
    }
    .facility-inventory-context .applied-filter-chip {
      background: #fffdf8;
      font-size: 0.78rem;
      min-height: 1.75rem;
      padding: 0.25rem 0.6rem;
    }
    .facility-pagination {
      display: flex;
      flex: 0 0 auto;
      flex-wrap: wrap;
      gap: 0.5rem;
    }
    .facility-pagination__control {
      min-width: 6.5rem;
      text-align: center;
    }
    .facility-pagination__control.is-disabled {
      background: #eee7da;
      border-color: #b8b1a5;
      color: #5f6872;
      cursor: not-allowed;
    }
    .facility-intelligence-sort {
      min-width: 13.75rem;
    }
    .facility-intelligence-inventory {
      list-style: none;
      margin: 0;
      padding: 0;
    }
    .facility-intelligence-row {
      border-top: 1px solid #b8b1a5;
      margin: 0;
    }
    .facility-intelligence-row > article {
      display: grid;
      gap: 1rem;
      grid-template-columns: minmax(15rem, 1.05fr) minmax(20rem, 1.8fr) minmax(15rem, 1fr) minmax(11rem, 0.75fr) minmax(10rem, 0.7fr);
      padding: 1rem;
    }
    .facility-intelligence-row :focus {
      scroll-margin-top: 9rem;
    }
    .facility-intelligence-row.is-selected {
      background: #f5e5b5;
      border: 2px solid #c38a09;
      border-radius: 4px;
    }
    .facility-intelligence-row:hover:not(.is-selected) {
      background: #fbf7ef;
      box-shadow: inset 4px 0 0 #d5a21a;
    }
    .facility-row-kicker,
    .facility-row-source h4,
    .facility-row-reviewer h4 {
      color: var(--muted);
      font-size: 0.78rem;
      font-weight: 500;
      margin-bottom: 0.45rem;
    }
    .facility-row-identity h3,
    .facility-row-reason h4 {
      font-size: 1rem;
      margin: 0 0 0.45rem;
    }
    .facility-row-identity h3 {
      font-size: 1.12rem;
      font-weight: 700;
      line-height: 1.35;
    }
    .facility-row-identity p,
    .facility-row-reason p,
    .facility-row-source p,
    .facility-row-reviewer p {
      margin-bottom: 0.55rem;
    }
    .ordering-explanation {
      overflow-wrap: anywhere;
    }
    .facility-row-source,
    .facility-row-reviewer {
      align-content: start;
      background: #f2eadc;
      border: 1px solid #b8b1a5;
      border-radius: 4px;
      display: grid;
      gap: 0.4rem;
      padding: 0.75rem;
    }
    .facility-row-actions {
      align-content: start;
      display: grid;
      gap: 0.5rem;
    }
    .facility-row-source .button,
    .facility-row-reviewer .button,
    .facility-row-actions .button {
      width: 100%;
    }
    .facility-row-actions .button-secondary {
      background: transparent;
      border-color: #817a70;
      color: #254f73;
      font-weight: 500;
    }
    .civic-ledger-page .review-chip {
      background: #f5efe3;
      border-color: #b8b1a5;
      color: #17212b;
      font-size: 0.78rem;
    }
    .civic-ledger-page .source-chip {
      background: #e1f1e8;
      border-color: #79b594;
      color: #1c5a35;
    }
    .civic-ledger-page .badge-danger {
      background: #fde8e6;
      border-color: #e07a70;
      color: #9f281c;
    }
    .civic-ledger-page .badge-attention {
      background: #fff1c7;
      border-color: #dda800;
      color: #7b5608;
    }
    .civic-ledger-page .badge-info {
      background: #e7edf5;
      border-color: #82a6c7;
      color: #254f73;
    }
    .civic-ledger-page .facility-row-reviewer .badge-info {
      background: #f5efe3;
      border-color: #b8b1a5;
      color: #17212b;
    }
    .civic-ledger-page .copy-icon-button,
    .copy-text-button {
      background: #fffdf8;
      border: 1px solid #b8b1a5;
      color: #174d74;
    }
    .copy-text-control {
      display: grid;
      gap: 0.25rem;
    }
    .copy-text-button {
      align-items: center;
      display: inline-flex;
      font-size: 0.82rem;
      gap: 0.35rem;
      justify-content: flex-start;
      min-height: 2.75rem;
      padding: 0.45rem 0.55rem;
      text-align: left;
    }
    .copy-text-button svg {
      flex: 0 0 auto;
      height: 1rem;
      width: 1rem;
    }
    .copy-feedback:not([hidden]) {
      color: #1c5a35;
      display: inline-block;
      font-weight: 700;
    }
    .civic-ledger-page .button-disabled,
    .civic-ledger-page button:disabled {
      background: #eee7da;
      border-color: #b8b1a5;
      color: #5f6872;
      cursor: not-allowed;
    }
    .intelligence-loading-row {
      border: 1px solid #b8b1a5;
      display: grid;
      gap: 1rem;
      grid-template-columns: 1fr 1fr 0.5fr;
      margin: 0 1rem 1rem;
      min-height: 9rem;
      padding: 1rem;
    }
    .intelligence-loading-row div {
      display: grid;
      gap: 0.5rem;
    }
    .intelligence-results-empty {
      color: var(--muted);
      padding: 0 1rem 1rem;
    }
    .civic-footer {
      margin: 0 1.5rem 1.5rem;
    }
    .civic-footer__inner {
      align-items: center;
      display: flex;
      justify-content: space-between;
      min-height: 6rem;
      padding-bottom: 1rem;
      padding-top: 1rem;
    }
    .civic-footer__inner div {
      display: grid;
      font-size: 0.82rem;
      gap: 0.65rem;
    }
    .civic-footer a {
      color: #f3d77d;
      font-weight: 500;
    }
    @media (max-width: 1100px) {
      .civic-header__inner {
        grid-template-columns: minmax(12rem, 1fr) auto;
      }
      .civic-menu-label {
        display: inline;
      }
      .civic-nav {
        grid-column: 1 / -1;
      }
      .civic-nav ul {
        grid-template-columns: repeat(7, minmax(0, 1fr));
      }
      .civic-ledger-page .facility-intelligence-filter-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .civic-ledger-page .facility-intelligence-filter-grid p:nth-child(8) {
        grid-column: auto;
      }
      .facility-intelligence-row > article {
        grid-template-areas:
          "identity reason"
          "source reviewer"
          "actions actions";
        grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      }
      .facility-row-identity { grid-area: identity; }
      .facility-row-reason { grid-area: reason; }
      .facility-row-source { grid-area: source; }
      .facility-row-reviewer { grid-area: reviewer; }
      .facility-row-actions {
        display: flex;
        grid-area: actions;
      }
      .facility-row-actions .button {
        width: auto;
      }
    }
    @media (min-width: 1101px) {
      .facility-inventory-context {
        position: sticky;
        top: 0.5rem;
        z-index: 3;
      }
    }
    @media (max-width: 760px) {
      .civic-header,
      .civic-footer {
        margin-left: 0.75rem;
        margin-right: 0.75rem;
      }
      .civic-ledger-page .shell {
        padding-left: 0.75rem;
        padding-right: 0.75rem;
      }
      .civic-header__inner {
        gap: 0.75rem;
        grid-template-columns: 1fr auto;
      }
      .civic-nav ul {
        gap: 0.25rem 0.5rem;
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
      .civic-nav a {
        align-items: center;
        display: flex;
        font-size: 0.78rem;
        justify-content: center;
        min-height: 2.75rem;
        padding-left: 0.15rem;
        padding-right: 0.15rem;
        white-space: normal;
      }
      .civic-ledger-page h1 {
        font-size: 1.35rem;
        line-height: 1.45;
      }
      .civic-ledger-page .facility-intelligence-filter-grid {
        grid-template-columns: minmax(0, 1fr);
      }
      .facility-intelligence-results__header {
        align-items: stretch;
        display: grid;
        gap: 0.75rem;
      }
      .facility-intelligence-sort {
        min-width: 0;
      }
      .facility-intelligence-sort select {
        max-width: 14rem;
      }
      .facility-inventory-context {
        align-items: stretch;
        display: grid;
        position: static;
      }
      .facility-pagination {
        width: 100%;
      }
      .facility-pagination__control {
        flex: 1 1 8rem;
        min-width: 0;
      }
      .facility-intelligence-row > article {
        display: grid;
        grid-template-areas:
          "identity"
          "reason"
          "source"
          "reviewer"
          "actions";
        grid-template-columns: minmax(0, 1fr);
        padding: 0.75rem;
      }
      .facility-row-actions {
        display: grid;
      }
      .facility-row-actions .button {
        width: min(100%, 14rem);
      }
      .facility-row-source,
      .facility-row-reviewer {
        min-width: 0;
      }
      .intelligence-glossary-line {
        gap: 1rem;
        justify-content: space-between;
      }
      .civic-footer__inner {
        align-items: start;
        display: grid;
        gap: 1rem;
      }
    }
    @media print {
      body {
        background: #fff;
        color: #000;
        font-size: 11pt;
      }
      .site-header, .civic-header, .guided-stepper, .site-footer, .civic-footer,
      .packet-draft-actions, .technical-details, .skip-link, .mode-panel,
      .copy-icon-button, .copy-text-control, .facility-intelligence-sort,
      .facility-pagination, .facility-row-actions, .compare-facilities-views,
      .intelligence-filters, .compact-filter-panel {
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
      .civic-ledger-page .intelligence-scope,
      .civic-ledger-page .intelligence-filters,
      .civic-ledger-page .facility-intelligence-results,
      .civic-ledger-page .facility-intelligence-row,
      .civic-ledger-page .facility-row-source,
      .civic-ledger-page .facility-row-reviewer {
        background: #fff !important;
        border-color: #000 !important;
        color: #000 !important;
        box-shadow: none !important;
      }
      .civic-ledger-page .facility-intelligence-row > article {
        grid-template-columns: 1fr 1.5fr 1fr 1fr;
      }
      .civic-ledger-page .facility-inventory-context {
        position: static !important;
      }
    }
    @media (max-width: 760px) {
      h1 {
        font-size: 1.55rem;
      }
      .site-title-row, .two-column, .request-layout {
        display: block;
      }
      .brand-title-block {
        min-width: 0;
      }
      .shell-lookup {
        margin-top: 0.75rem;
        max-width: none;
        min-width: 0;
      }
      .shell-nav-cluster {
        align-items: stretch;
        display: grid;
        gap: 0.6rem;
        justify-content: stretch;
        margin-top: 0.75rem;
        min-width: 0;
      }
      .attorney-hero, .legal-summary-grid, .detail-top-grid, .support-layout,
      .dense-page-header, .dense-section-header {
        display: block;
      }
      .worklist-controls {
        display: block;
      }
      .compact-search-form {
        margin-top: 0.75rem;
      }
      .review-worklist-row {
        align-items: stretch;
        grid-template-areas: "identity" "dates" "outcome" "state" "action";
        grid-template-columns: minmax(0, 1fr);
      }
      .worklist-dates {
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
      .overview-layout,
      .overview-primary-row {
        display: block;
      }
      .overview-side-panel {
        border-left: 0;
        border-top: 1px solid var(--line-soft);
      }
      .overview-source-action {
        margin-top: 0.75rem;
      }
      .top-fact-strip {
        grid-template-columns: minmax(0, 1fr);
      }
      .compact-fact--name {
        min-width: 0;
      }
      .rt-timeline {
        padding-top: 0;
      }
      .rt-timeline__line {
        display: none;
      }
      .timeline-list-linear {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        padding-bottom: 0;
        padding-top: 0;
        row-gap: 0.85rem;
      }
      .timing-summary {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .timeline-list-linear::before {
        display: none;
      }
      .timeline-list-linear.has-gap::after {
        display: none;
      }
      .timeline-marker {
        left: auto;
        margin-bottom: 0.25rem;
        position: static;
        top: auto;
        transform: none;
      }
      .timeline-gap-badge {
        grid-column: 1 / -1;
        position: static;
        transform: none;
        width: auto;
      }
      .quick-review-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .quick-review-card {
        min-height: 7.5rem;
      }
      .reviewer-brief-card .quick-review-card {
        min-height: 0;
      }
      .glossary-list {
        display: block;
      }
      .glossary-list dt {
        margin-top: 0.55rem;
      }
      .dense-page-header .form-actions,
      .dense-page-actions {
        justify-content: flex-start;
        margin-top: 0.75rem;
      }
      .attorney-hero-actions {
        margin-top: 1rem;
      }
      .mode-panel {
        justify-content: flex-start;
        min-width: 0;
      }
      .site-nav ul {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .site-nav a {
        width: 100%;
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
    @media (min-width: 761px) and (max-width: 1180px) {
      .review-worklist-row {
        align-items: start;
        grid-template-areas:
          "identity identity action"
          "dates outcome state";
        grid-template-columns: minmax(0, 1.4fr) minmax(10rem, 0.8fr) minmax(10rem, 0.8fr);
      }
    }
""".strip()
