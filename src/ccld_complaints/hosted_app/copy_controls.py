from __future__ import annotations

import html


def render_copy_icon_button(
    accessible_label: str,
    displayed_value: str,
    *,
    class_name: str = "copy-icon-button",
) -> str:
    """Render one compact copy control for an already displayed reviewer value."""
    return (
        f'<button class="{html.escape(class_name, quote=True)}" type="button" '
        f'data-copy-value="{html.escape(displayed_value, quote=True)}" '
        'data-copy-feedback="Copied" '
        f'aria-label="{html.escape(accessible_label, quote=True)}" '
        f'title="{html.escape(accessible_label, quote=True)}">'
        f'{clipboard_icon_svg()}</button>'
        '<span class="copy-feedback" data-copy-status hidden '
        'aria-live="polite" aria-atomic="true"></span>'
    )


def clipboard_icon_svg() -> str:
    return (
        '<svg aria-hidden="true" viewBox="0 0 24 24" focusable="false" '
        'width="16" height="16">'
        '<path fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round" '
        'd="M8 8h9a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2Z"/>'
        '<path fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round" '
        'd="M4 15H3a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>'
        "</svg>"
    )


_COPY_CONTROL_SCRIPT_BODY = """
(function () {
  function ensureCopyStatus(button) {
    var status = button.nextElementSibling;
    if (!status || !status.hasAttribute('data-copy-status')) {
      status = document.createElement('span');
      status.className = 'copy-feedback';
      status.setAttribute('data-copy-status', '');
      status.setAttribute('aria-live', 'polite');
      status.setAttribute('aria-atomic', 'true');
      status.hidden = true;
      button.insertAdjacentElement('afterend', status);
    }
    return status;
  }
  function showCopyStatus(button, message) {
    var status = ensureCopyStatus(button);
    window.clearTimeout(button._copyStatusTimer);
    button.setAttribute('data-copy-feedback', message);
    status.textContent = message;
    status.hidden = false;
    button._copyStatusTimer = window.setTimeout(function () {
      status.hidden = true;
      status.textContent = '';
      button.removeAttribute('data-copy-state');
    }, 2000);
  }
  document.querySelectorAll('[data-copy-value]').forEach(function (button) {
    if (button.getAttribute('data-copy-control-bound') === 'true') {
      return;
    }
    button.setAttribute('data-copy-control-bound', 'true');
    button.addEventListener('click', function () {
      var value = button.getAttribute('data-copy-value') || '';
      if (!value || typeof navigator === 'undefined' ||
          !navigator.clipboard || !navigator.clipboard.writeText) {
        button.setAttribute('data-copy-state', 'unavailable');
        showCopyStatus(button, 'Copy unavailable');
        return;
      }
      navigator.clipboard.writeText(value).then(function () {
        button.setAttribute('data-copy-state', 'copied');
        showCopyStatus(button, 'Copied');
      }).catch(function () {
        button.setAttribute('data-copy-state', 'unavailable');
        showCopyStatus(button, 'Copy unavailable');
      });
    });
  });
}());
"""


def render_copy_control_script(*, additional_script: str = "") -> str:
    """Render the shared copy initializer with optional static page behavior."""
    return f"<script>{_COPY_CONTROL_SCRIPT_BODY}{additional_script}</script>"


COPY_CONTROL_SCRIPT = render_copy_control_script()
