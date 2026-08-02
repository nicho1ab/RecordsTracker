# ruff: noqa: E501

"""Shared progressive controls for the governed Compare Facilities filters."""

from __future__ import annotations

import html
from collections.abc import Iterable


def render_checkbox_multiselect(
    *,
    control_id: str,
    name: str,
    label: str,
    options: Iterable[tuple[str, str]],
    selected: Iterable[str] = (),
    all_label: str = "All",
    disabled: bool = False,
) -> str:
    """Render native-checkbox fallback markup enhanced only when JavaScript runs."""
    selected_values = {value.casefold() for value in selected}
    all_selected = not selected_values
    panel_id = f"{control_id}-panel"
    summary_id = f"{control_id}-summary"
    disabled_attr = " disabled" if disabled else ""
    option_rows = [
        _checkbox_row(
            control_id=control_id,
            name=name,
            value="all",
            label=all_label,
            checked=all_selected,
            disabled=disabled,
        )
    ]
    selected_labels: list[str] = []
    for index, (value, option_label) in enumerate(options, start=1):
        checked = value.casefold() in selected_values
        if checked:
            selected_labels.append(option_label)
        option_rows.append(
            _checkbox_row(
                control_id=f"{control_id}-{index}",
                name=name,
                value=value,
                label=option_label,
                checked=checked,
                disabled=disabled,
            )
        )
    summary = all_label if not selected_labels else ", ".join(selected_labels)
    return f'''<div class="filter-control filter-control--multiselect checkbox-multiselect" data-checkbox-multiselect>
  <button class="checkbox-multiselect__trigger" type="button" id="{html.escape(control_id, quote=True)}"
      aria-expanded="false" aria-controls="{html.escape(panel_id, quote=True)}" aria-describedby="{html.escape(summary_id, quote=True)}"{disabled_attr}>
    <span class="checkbox-multiselect__label">{html.escape(label)}</span><span class="checkbox-multiselect__summary" id="{html.escape(summary_id, quote=True)}">{html.escape(summary)}</span><span class="checkbox-multiselect__cue" aria-hidden="true">⌄</span>
  </button>
  <div class="checkbox-multiselect__panel" id="{html.escape(panel_id, quote=True)}">
    <fieldset{disabled_attr}>
      <legend>{html.escape(label)}</legend>
      {''.join(option_rows)}
    </fieldset>
  </div>
</div>'''


def _checkbox_row(
    *,
    control_id: str,
    name: str,
    value: str,
    label: str,
    checked: bool,
    disabled: bool,
) -> str:
    checked_attr = " checked" if checked else ""
    disabled_attr = " disabled" if disabled else ""
    escaped_id = html.escape(f"{control_id}-option", quote=True)
    return f'''<label class="checkbox-multiselect__option" for="{escaped_id}">
  <input id="{escaped_id}" type="checkbox" name="{html.escape(name, quote=True)}" value="{html.escape(value, quote=True)}"{checked_attr}{disabled_attr}>
  <span class="checkbox-multiselect__option-label">{html.escape(label)}</span>
</label>'''


CHECKBOX_MULTISELECT_SCRIPT = r"""<script>
(function () {
  'use strict';
  function selectedLabels(root) {
    return Array.prototype.slice.call(root.querySelectorAll('input[type="checkbox"]:checked'))
      .filter(function (input) { return input.value !== 'all'; })
      .map(function (input) { return input.parentElement.textContent.trim(); });
  }
  function sync(root) {
    var all = root.querySelector('input[value="all"]');
    var selected = Array.prototype.slice.call(root.querySelectorAll('input[type="checkbox"]:checked'))
      .filter(function (input) { return input.value !== 'all'; });
    if (!selected.length) { all.checked = true; }
    var summary = root.querySelector('.checkbox-multiselect__summary');
    summary.textContent = selected.length ? selectedLabels(root).join(', ') : all.parentElement.textContent.trim();
  }
  function close(root, restore) {
    var trigger = root.querySelector('.checkbox-multiselect__trigger');
    var panel = root.querySelector('.checkbox-multiselect__panel');
    panel.hidden = true;
    trigger.setAttribute('aria-expanded', 'false');
    if (restore) { trigger.focus(); }
  }
  function open(root) {
    var trigger = root.querySelector('.checkbox-multiselect__trigger');
    var panel = root.querySelector('.checkbox-multiselect__panel');
    panel.hidden = false;
    trigger.setAttribute('aria-expanded', 'true');
  }
  function initialize(scope) {
    var controls = Array.prototype.slice.call((scope || document).querySelectorAll('[data-checkbox-multiselect]'));
    controls.forEach(function (root) {
      if (root.dataset.checkboxMultiselectReady === 'true') { return; }
      var trigger = root.querySelector('.checkbox-multiselect__trigger');
      var panel = root.querySelector('.checkbox-multiselect__panel');
      root.dataset.checkboxMultiselectReady = 'true';
      root.classList.add('checkbox-multiselect--enhanced');
      panel.hidden = true;
    trigger.addEventListener('click', function () {
      if (panel.hidden) { open(root); } else { close(root, false); }
    });
    root.addEventListener('change', function (event) {
      var input = event.target;
      if (!input.matches('input[type="checkbox"]')) { return; }
      var all = root.querySelector('input[value="all"]');
      if (input.value === 'all' && input.checked) {
        Array.prototype.forEach.call(root.querySelectorAll('input[type="checkbox"]'), function (box) {
          if (box !== all) { box.checked = false; }
        });
      } else if (input.checked) {
        all.checked = false;
      }
      sync(root);
    });
    root.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && !panel.hidden) {
        event.preventDefault(); close(root, true);
      }
    });
      sync(root);
    });
  }
  if (!window.__checkboxMultiselectOutsideListener) {
    document.addEventListener('pointerdown', function (event) {
      Array.prototype.slice.call(document.querySelectorAll('[data-checkbox-multiselect]')).forEach(function (root) {
        var panel = root.querySelector('.checkbox-multiselect__panel');
        if (!root.contains(event.target) && panel && !panel.hidden) { close(root, false); }
      });
    });
    window.__checkboxMultiselectOutsideListener = true;
  }
  window.initializeCheckboxMultiselect = initialize;
  initialize(document);
  document.documentElement.setAttribute('data-checkbox-multiselect-ready', 'true');
}());
</script>"""


FACILITY_INTELLIGENCE_CHIP_SCRIPT = r"""<script>
(function () {
  'use strict';
  var diagnostics = window.__facilityIntelligenceChipDiagnostics || {
    navigationEntriesAtLoad: performance.getEntriesByType('navigation').length,
    actions: []
  };
  window.__facilityIntelligenceChipDiagnostics = diagnostics;

  function replaceFromDocument(nextDocument) {
    ['.intelligence-scope', '.intelligence-filters', '#facility-intelligence-dynamic-region'].forEach(function (selector) {
      var current = document.querySelector(selector);
      var replacement = nextDocument.querySelector(selector);
      if (!current || !replacement) { throw new Error('Missing canonical Issue #642 region: ' + selector); }
      current.replaceWith(replacement.cloneNode(true));
    });
    if (window.initializeCheckboxMultiselect) { window.initializeCheckboxMultiselect(document); }
    initialize(document);
  }

  function focusAfterRemoval(index) {
    var buttons = Array.prototype.slice.call(document.querySelectorAll('[data-filter-chip-remove]'));
    var destination = buttons[index] || buttons[index - 1] || document.querySelector('#applied-filters-heading');
    if (destination) { destination.focus({ preventScroll: true }); }
  }

  function update(url, options) {
    var before = {
      href: location.href,
      navigationEntries: performance.getEntriesByType('navigation').length,
      scrollX: window.scrollX,
      scrollY: window.scrollY
    };
    return fetch(url, { credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } })
      .then(function (response) {
        if (!response.ok) { throw new Error('Issue #642 chip update returned HTTP ' + response.status); }
        return response.text();
      })
      .then(function (markup) {
        replaceFromDocument(new DOMParser().parseFromString(markup, 'text/html'));
        if (options.push) { history.pushState({ facilityIntelligenceChip: true }, '', url); }
        window.scrollTo(before.scrollX, before.scrollY);
        if (options.focusIndex !== null) { focusAfterRemoval(options.focusIndex); }
        diagnostics.actions.push({
          before: before.href,
          after: location.href,
          navigationEntriesBefore: before.navigationEntries,
          navigationEntriesAfter: performance.getEntriesByType('navigation').length,
          fullDocumentNavigation: before.navigationEntries !== performance.getEntriesByType('navigation').length,
          focusId: document.activeElement ? document.activeElement.id || '' : ''
        });
      });
  }

  function initialize(scope) {
    Array.prototype.slice.call((scope || document).querySelectorAll('[data-filter-chip-remove]')).forEach(function (button) {
      if (button.dataset.filterChipReady === 'true') { return; }
      button.dataset.filterChipReady = 'true';
      button.addEventListener('click', function (event) {
        event.preventDefault();
        var buttons = Array.prototype.slice.call(document.querySelectorAll('[data-filter-chip-remove]'));
        var index = buttons.indexOf(button);
        button.disabled = true;
        update(button.dataset.filterChipHref, { push: true, focusIndex: index })
          .catch(function (error) { button.disabled = false; console.error(error); });
      });
    });
    document.documentElement.setAttribute('data-facility-intelligence-chips-ready', 'true');
  }

  window.addEventListener('popstate', function () {
    update(location.href, { push: false, focusIndex: null })
      .then(function () {
        var region = document.querySelector('#applied-filters-heading');
        if (region) { region.focus({ preventScroll: true }); }
      })
      .catch(function (error) { console.error(error); });
  });
  initialize(document);
}());
</script>"""


REVIEW_NEXT_SCRIPT = r"""<script>
(function () {
  'use strict';
  if (window.__reviewNextControllerReady) { return; }
  window.__reviewNextControllerReady = true;
  var activeController = null;
  var requestNumber = 0;
  function controls(region) { return Array.prototype.slice.call(region.querySelectorAll('a.review-next-control')); }
  function setPending(region, pending) {
    region.setAttribute('aria-busy', pending ? 'true' : 'false');
    controls(region).forEach(function (control) { control.setAttribute('aria-disabled', pending ? 'true' : 'false'); });
  }
  function replace(markup, url, historyMode, focus) {
    var documentResponse = new DOMParser().parseFromString(markup, 'text/html');
    var next = documentResponse.querySelector('#review-next-region');
    var current = document.querySelector('#review-next-region');
    if (!next || !current) { throw new Error('Missing canonical Review next region'); }
    current.replaceWith(next.cloneNode(true));
    if (historyMode === 'push') { history.pushState({ reviewNext: true }, '', url); }
    if (historyMode === 'replace') { history.replaceState({ reviewNext: true }, '', next.dataset.currentUrl || url); }
    if (focus) { var heading = document.querySelector('#review-next-heading'); if (heading) { heading.focus({ preventScroll: true }); } }
  }
  function update(url, historyMode, trigger, focus) {
    var region = document.querySelector('#review-next-region');
    if (!region) { return Promise.reject(new Error('Review next region is unavailable')); }
    if (activeController) { activeController.abort(); }
    activeController = new AbortController();
    var currentRequest = ++requestNumber;
    var scrollX = window.scrollX, scrollY = window.scrollY;
    setPending(region, true);
    return fetch(url, { credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' }, signal: activeController.signal })
      .then(function (response) { if (!response.ok) { throw new Error('Review next update returned HTTP ' + response.status); } return response.text(); })
      .then(function (markup) {
        if (currentRequest !== requestNumber) { return; }
        replace(markup, url, historyMode, focus);
        window.scrollTo(scrollX, scrollY);
      })
      .catch(function (error) {
        if (error.name === 'AbortError') { return; }
        if (currentRequest !== requestNumber) { return; }
        setPending(region, false);
        var errorRegion = region.querySelector('#review-next-error');
        if (errorRegion) { errorRegion.hidden = false; errorRegion.textContent = 'Could not update Review next. Use the available link to continue.'; }
        if (trigger) { trigger.focus({ preventScroll: true }); }
        console.error(error);
      });
  }
  document.addEventListener('click', function (event) {
    var control = event.target.closest('a.review-next-control');
    if (!control || control.getAttribute('aria-disabled') === 'true' || !window.fetch) { return; }
    event.preventDefault(); update(control.href, 'push', control, true);
  });
  window.addEventListener('popstate', function () { update(location.href, 'none', null, true); });
}());
</script>"""
