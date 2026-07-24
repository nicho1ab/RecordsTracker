from ccld_complaints.hosted_app.copy_controls import (
    COPY_CONTROL_SCRIPT,
    render_copy_control_script,
    render_copy_icon_button,
)


def test_compact_copy_icon_keeps_the_displayed_value_boundary_and_feedback() -> None:
    markup = (
        '<span class="copyable-value">04/14/2022'
        f'{render_copy_icon_button("Copy First investigation activity date", "04/14/2022")}'
        "</span>"
    )

    assert markup.index("04/14/2022") < markup.index("copy-icon-button")
    assert 'type="button"' in markup
    assert 'data-copy-value="04/14/2022"' in markup
    assert 'aria-label="Copy First investigation activity date"' in markup
    assert 'data-copy-status hidden aria-live="polite" aria-atomic="true"' in markup
    assert "id=" not in markup


def test_shared_copy_script_handles_success_failure_and_independent_controls() -> None:
    assert "data-copy-control-bound" in COPY_CONTROL_SCRIPT
    assert "button._copyStatusTimer" in COPY_CONTROL_SCRIPT
    assert "typeof navigator === 'undefined'" in COPY_CONTROL_SCRIPT
    assert "!navigator.clipboard || !navigator.clipboard.writeText" in COPY_CONTROL_SCRIPT
    assert "navigator.clipboard.writeText(value).then" in COPY_CONTROL_SCRIPT
    assert "showCopyStatus(button, 'Copied')" in COPY_CONTROL_SCRIPT
    assert "showCopyStatus(button, 'Copy unavailable')" in COPY_CONTROL_SCRIPT


def test_shared_copy_script_composes_page_behavior_inside_one_script_element() -> None:
    script = render_copy_control_script(additional_script="function pageBehavior() {}")

    assert script.count("<script>") == 1
    assert script.count("</script>") == 1
    assert script.index("function pageBehavior() {}") < script.index("</script>")
