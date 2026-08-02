from ccld_complaints.hosted_app.compare_facilities_controls import (
    CHECKBOX_MULTISELECT_SCRIPT,
    FACILITY_INTELLIGENCE_CHIP_SCRIPT,
    REVIEW_NEXT_SCRIPT,
    render_checkbox_multiselect,
)
from ccld_complaints.hosted_app.ui_shell import SHARED_CSS


def test_checkbox_multiselect_has_native_fallback_and_described_trigger() -> None:
    markup = render_checkbox_multiselect(
        control_id="finding",
        name="finding",
        label="Finding",
        options=(("Substantiated", "Substantiated"),),
    )

    assert 'aria-expanded="false"' in markup
    assert 'aria-controls="finding-panel"' in markup
    assert 'class="filter-control filter-control--multiselect checkbox-multiselect"' in markup
    assert '<fieldset>' in markup
    assert 'name="finding" value="all" checked' in markup
    assert 'name="finding" value="Substantiated"' in markup
    assert 'class="checkbox-multiselect__label">Finding</span>' in markup
    assert 'class="checkbox-multiselect__option-label">Substantiated</span>' in markup
    assert 'class="checkbox-multiselect__cue" aria-hidden="true">⌄</span>' in markup
    assert "Escape" in CHECKBOX_MULTISELECT_SCRIPT
    assert "pointerdown" in CHECKBOX_MULTISELECT_SCRIPT
    assert "data-checkbox-multiselect-ready" in CHECKBOX_MULTISELECT_SCRIPT
    assert "controls.forEach" in CHECKBOX_MULTISELECT_SCRIPT


def test_checkbox_multiselect_option_rows_keep_checkbox_and_label_together() -> None:
    assert "align-items: flex-start;" in SHARED_CSS
    assert "grid-template-columns: max-content minmax(0, 1fr);" in SHARED_CSS
    assert ".checkbox-multiselect__option input[type=\"checkbox\"]" in SHARED_CSS
    assert "inline-size: auto;" in SHARED_CSS
    assert "width: auto;" in SHARED_CSS
    assert "min-height: 0;" in SHARED_CSS
    assert ".checkbox-multiselect__option-label" in SHARED_CSS
    assert "grid-column: 2;" in SHARED_CSS
    assert "max-width: 100%;" in SHARED_CSS
    assert "word-break: normal;" in SHARED_CSS
    assert "inline-size: min(100%, 12rem);" in SHARED_CSS
    assert "max-width: 100%;" in SHARED_CSS
    assert "min-width: 0;" in SHARED_CSS
    assert (
        ".facility-intelligence-filter-grid label.checkbox-multiselect__option"
    ) in SHARED_CSS


def test_filter_controls_share_two_line_label_value_contract() -> None:
    assert "--filter-control-label-size: 0.74rem;" in SHARED_CSS
    assert "--filter-control-label-weight: 700;" in SHARED_CSS
    assert "--filter-control-label-line-height: 1;" in SHARED_CSS
    assert "--filter-control-value-size: 0.88rem;" in SHARED_CSS
    assert "--filter-control-value-line-height: 1.25;" in SHARED_CSS
    assert "--filter-control-min-height: 2.5rem;" in SHARED_CSS
    assert "--filter-control-padding-block: 0.38rem;" in SHARED_CSS
    assert ".filter-control--multiselect .checkbox-multiselect__summary" in SHARED_CSS
    assert "grid-template-rows: auto auto;" in SHARED_CSS
    assert "text-align: left;" in SHARED_CSS
    assert "grid-row: 1 / span 2;" in SHARED_CSS


def test_filter_chip_enhancement_uses_canonical_fallback_and_history_updates() -> None:
    assert "data-filter-chip-remove" in FACILITY_INTELLIGENCE_CHIP_SCRIPT
    assert "fetch(url" in FACILITY_INTELLIGENCE_CHIP_SCRIPT
    assert "history.pushState" in FACILITY_INTELLIGENCE_CHIP_SCRIPT
    assert "window.addEventListener('popstate'" in FACILITY_INTELLIGENCE_CHIP_SCRIPT
    assert "fullDocumentNavigation" in FACILITY_INTELLIGENCE_CHIP_SCRIPT
    assert "focusAfterRemoval" in FACILITY_INTELLIGENCE_CHIP_SCRIPT
    assert "initializeCheckboxMultiselect" in FACILITY_INTELLIGENCE_CHIP_SCRIPT


def test_review_next_enhancement_is_bounded_and_cancels_stale_requests() -> None:
    assert "#review-next-region" in REVIEW_NEXT_SCRIPT
    assert "AbortController" in REVIEW_NEXT_SCRIPT
    assert "requestNumber" in REVIEW_NEXT_SCRIPT
    assert "history.pushState" in REVIEW_NEXT_SCRIPT
    assert "window.addEventListener('popstate'" in REVIEW_NEXT_SCRIPT
    assert "#facility-intelligence-dynamic-region" not in REVIEW_NEXT_SCRIPT
    assert (
        ".facility-suggestions {\n"
        "        box-shadow: none;\n"
        "        margin-top: 0.25rem;\n"
        "        position: static;"
    ) in SHARED_CSS


def test_checkbox_multiselect_omits_all_when_specific_value_is_selected() -> None:
    markup = render_checkbox_multiselect(
        control_id="finding",
        name="finding",
        label="Finding",
        options=(("Substantiated", "Substantiated"),),
        selected=("Substantiated",),
    )

    assert 'name="finding" value="all" checked' not in markup
    assert 'name="finding" value="Substantiated" checked' in markup
