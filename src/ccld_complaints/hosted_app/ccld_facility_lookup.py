# ruff: noqa: E501

from __future__ import annotations

import csv
import html
import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from ccld_complaints.hosted_app.ui_shell import render_page_shell

CCLD_FACILITY_LOOKUP_PATH = "/ccld/facilities"
CCLD_RECORD_REQUEST_PATH = "/ccld/records/request"
DEFAULT_CCLD_FACILITY_REFERENCE_PATH = Path(
    "tests/fixtures/public_source_facilities/ccld_program_facilities_tiny.csv"
)
DEFAULT_FULL_CCLD_FACILITY_REFERENCE_PATH = Path(
  "data/raw/ccld/facility-reference.csv"
)
CCLD_FACILITY_REFERENCE_CSV_ENV = "CCLD_FACILITY_REFERENCE_CSV"
MAX_FACILITY_LOOKUP_RESULTS = 25
_REQUIRED_COLUMNS = (
    "Facility Number",
    "Facility Name",
    "Facility City",
    "County Name",
    "Facility Zip",
    "Facility Type",
    "Facility Status",
    "Closed Date",
)
_SECRET_HTML_MARKERS = (
    "authorization",
    "client_secret",
    "connection string",
    "connection_string",
    "cookie",
    "password",
    "private_header",
    "private header",
    "provider_issuer",
    "provider_subject",
    "secret",
    "token",
)

_FACILITY_COMBOBOX_JS = r"""(function(){
  'use strict';
  var wrap=document.getElementById('facility-selector-wrap');
  if(!wrap)return;
  var mode=wrap.getAttribute('data-facility-mode')||'request';
  var si=document.getElementById('facility-search-input');
  var nf=document.getElementById('facility-number-field');
  var of_=document.getElementById('facility-origin-field');
  var lf=document.getElementById('facility-name-field');
  var sl=document.getElementById('facility-suggestion-list');
  var sc=document.getElementById('facility-selected-card');
  var de=document.getElementById('facility-reference-json');
  if(!si||!sl||!de)return;
  var facs=[];
  try{facs=JSON.parse(de.textContent||'[]');}catch(e){return;}
  // Show JS combobox, hide no-JS fallback
  var co=document.getElementById('facility-combobox-outer');
  if(co)co.style.display='';
  if(nf)nf.style.display='none';
  // Enhance input placeholder for text search
  si.placeholder='Name, license number, city, or ZIP';
  si.removeAttribute('inputmode');
  // ARIA
  si.setAttribute('aria-expanded','false');
  si.setAttribute('aria-autocomplete','list');
  si.setAttribute('aria-controls','facility-suggestion-list');
  sl.setAttribute('role','listbox');
  function norm(s){return(s||'').toLowerCase().replace(/\s+/g,' ').trim();}
  function match(f,toks){
    var h=norm([f.num,f.n,f.city,f.co,f.zip,f.t,f.s].join(' '));
    return toks.every(function(t){return h.indexOf(t)!==-1;});
  }
  function esc(s){
    return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
  function buildHtml(matches){
    var h='';
    for(var i=0;i<matches.length;i++){
      var f=matches[i];
      var geo=[f.city,f.zip].filter(Boolean).join(' \u00b7 ');
      var meta=[f.t,f.s].filter(Boolean).join(' \u2022 ');
      var det=[geo,meta].filter(Boolean).join(' | ');
      h+='<li role="option"><button type="button" class="suggestion-btn"'
        +' data-num="'+esc(f.num)+'" data-name="'+esc(f.n)+'"'
        +' data-city="'+esc(f.city||'')+'" data-zip="'+esc(f.zip||'')+'"'
        +' data-type="'+esc(f.t||'')+'" data-status="'+esc(f.s||'')+'">'
        +'<span class="suggestion-name">'+esc(f.n)+'</span>'
        +' <span class="suggestion-badge">'+esc(f.num)+'</span>'
        +(det?'<span class="suggestion-details">'+esc(det)+'</span>':'')
        +'</button></li>';
    }
    return h;
  }
  function showSugs(q){
    var toks=norm(q).split(' ').filter(Boolean);
    if(!toks.length){hideSugs();return;}
    var ms=[];
    for(var i=0;i<facs.length&&ms.length<25;i++){if(match(facs[i],toks))ms.push(facs[i]);}
    if(!ms.length){sl.innerHTML='<li><span class="suggestion-empty">No matches found.</span></li>';}
    else{sl.innerHTML=buildHtml(ms);}
    sl.removeAttribute('hidden');
    si.setAttribute('aria-expanded','true');
  }
  function hideSugs(){
    sl.setAttribute('hidden','');
    si.setAttribute('aria-expanded','false');
  }
  function setCard(f){
    if(!sc)return;
    var ne=sc.querySelector('.selected-name');
    var nue=sc.querySelector('.selected-number');
    var ge=sc.querySelector('.selected-geo');
    var me=sc.querySelector('.selected-meta');
    var ul=sc.querySelector('.selected-use-link');
    if(ne)ne.textContent=f.n;
    if(nue)nue.textContent=f.num;
    if(ge)ge.textContent=[f.city,f.zip].filter(Boolean).join(', ');
    if(me)me.textContent=[f.t,f.s].filter(Boolean).join(' \u2022 ');
    if(ul){
      ul.href='/ccld/records/request?facility_number='+encodeURIComponent(f.num)
        +'&request_context_origin=facility_lookup'
        +'&lookup_facility_name='+encodeURIComponent(f.n);
    ul.setAttribute('aria-label','Use '+f.n+' / '+f.num+' for complaint record retrieval');
    }
    sc.removeAttribute('hidden');
  }
  function clearSel(){
    if(sc)sc.setAttribute('hidden','');
    si.value='';
    if(of_)of_.value='manual_entry';
    if(lf)lf.value='';
    si.focus();
  }
  function selFac(btn){
    var f={
      num:btn.getAttribute('data-num'),n:btn.getAttribute('data-name'),
      city:btn.getAttribute('data-city'),zip:btn.getAttribute('data-zip'),
      t:btn.getAttribute('data-type'),s:btn.getAttribute('data-status')
    };
    hideSugs();
    if(mode==='request'){
      si.value=f.num;
      if(of_)of_.value='facility_lookup';
      if(lf)lf.value=f.n;
    }else{
      si.value=f.n;
    }
    setCard(f);
    si.focus();
  }
  si.addEventListener('input',function(){
    if(mode==='request'){
      if(of_)of_.value='manual_entry';
      if(lf)lf.value='';
      if(sc)sc.setAttribute('hidden','');
    }
    showSugs(this.value);
  });
  si.addEventListener('keydown',function(e){
    var open=!sl.hasAttribute('hidden');
    if(e.key==='Escape'){hideSugs();return;}
    if(e.key==='ArrowDown'&&open){
      e.preventDefault();
      var fb=sl.querySelector('.suggestion-btn');
      if(fb)fb.focus();
    }
  });
  sl.addEventListener('click',function(e){
    var t=e.target;
    var btn=(typeof t.closest==='function')?t.closest('.suggestion-btn'):null;
    if(!btn&&t.classList&&t.classList.contains('suggestion-btn'))btn=t;
    if(btn)selFac(btn);
  });
  sl.addEventListener('keydown',function(e){
    var bs=Array.prototype.slice.call(sl.querySelectorAll('.suggestion-btn'));
    var idx=bs.indexOf(document.activeElement);
    if(e.key==='ArrowDown'){e.preventDefault();var nx=bs[idx+1]||bs[0];if(nx)nx.focus();}
    else if(e.key==='ArrowUp'){e.preventDefault();if(idx<=0)si.focus();else bs[idx-1].focus();}
    else if(e.key==='Escape'){hideSugs();si.focus();}
    else if(e.key==='Enter'){e.preventDefault();if(bs[idx])selFac(bs[idx]);}
  });
  var cb=document.getElementById('facility-change-btn');
  if(cb)cb.addEventListener('click',clearSel);
  document.addEventListener('click',function(e){if(!wrap.contains(e.target))hideSugs();});
}());"""


@dataclass(frozen=True)
class CcldFacilityLookupRecord:
    facility_number: str
    facility_name: str
    city: str
    county: str
    zip_code: str
    facility_type: str
    status: str
    closed_date: str


@dataclass(frozen=True)
class CcldFacilityReferenceSource:
    source_kind: str
    label: str
    path_label: str
    records: tuple[CcldFacilityLookupRecord, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CcldFacilityLookupResult:
  query: str
  total_match_count: int
  returned_records: tuple[CcldFacilityLookupRecord, ...]
  result_limit: int
  reference_source: CcldFacilityReferenceSource | None = None

  @property
  def empty_search(self) -> bool:
    return not self.query.strip()

  @property
  def has_more_matches(self) -> bool:
    return self.total_match_count > len(self.returned_records)


def load_ccld_facility_reference(
    path: Path = DEFAULT_CCLD_FACILITY_REFERENCE_PATH,
) -> tuple[CcldFacilityLookupRecord, ...]:
    with path.open("r", encoding="utf-8", newline="") as fixture_file:
        reader = csv.DictReader(fixture_file)
        fieldnames = tuple(reader.fieldnames or ())
        missing_columns = [
            column for column in _REQUIRED_COLUMNS if column not in fieldnames
        ]
        if missing_columns:
            raise ValueError(
                "CCLD facility reference CSV is missing required column(s): "
                + ", ".join(missing_columns)
            )
        records = tuple(_record_from_row(row) for row in reader)
    return tuple(
        sorted(records, key=lambda record: (record.facility_name, record.facility_number))
    )


def load_active_ccld_facility_reference(
    *,
    configured_path: str | None = None,
) -> CcldFacilityReferenceSource:
    configured_value = configured_path
    if configured_value is None:
        configured_value = os.environ.get(CCLD_FACILITY_REFERENCE_CSV_ENV)
    if configured_value:
        configured_reference = Path(configured_value)
        if configured_reference.exists():
            try:
                return CcldFacilityReferenceSource(
                    source_kind="full_local_test_csv",
                    label="Full local/test CCLD facility reference CSV",
                    path_label=_safe_path_label(configured_reference),
                    records=load_ccld_facility_reference(configured_reference),
                )
            except ValueError as error:
                return _tiny_fixture_reference(
                    warnings=(
                        "Configured full local/test CCLD facility reference CSV "
                        f"could not be loaded: {error}. Using tiny fixture fallback.",
                    )
                )
        return _tiny_fixture_reference(
            warnings=(
                "Configured full local/test CCLD facility reference CSV was not found. "
                "Using tiny fixture fallback.",
            )
        )
    if DEFAULT_FULL_CCLD_FACILITY_REFERENCE_PATH.exists():
        try:
            return CcldFacilityReferenceSource(
                source_kind="full_local_test_csv",
                label="Full local/test CCLD facility reference CSV",
                path_label=_safe_path_label(DEFAULT_FULL_CCLD_FACILITY_REFERENCE_PATH),
                records=load_ccld_facility_reference(
                    DEFAULT_FULL_CCLD_FACILITY_REFERENCE_PATH
                ),
            )
        except ValueError as error:
            return _tiny_fixture_reference(
                warnings=(
                    "Default full local/test CCLD facility reference CSV could not be "
                    f"loaded: {error}. Using tiny fixture fallback.",
                )
            )
    return _tiny_fixture_reference(
        warnings=(
            "No full local/test CCLD facility reference CSV is configured or available. "
            "Using tiny fixture fallback.",
        )
    )


def search_ccld_facilities(
    query: str,
    records: Iterable[CcldFacilityLookupRecord] | None = None,
    *,
    result_limit: int = MAX_FACILITY_LOOKUP_RESULTS,
    reference_source: CcldFacilityReferenceSource | None = None,
) -> CcldFacilityLookupResult:
    if result_limit < 1:
        raise ValueError("result_limit must be at least 1.")
    normalized_query = _normalized_text(query)
    if not normalized_query:
        return CcldFacilityLookupResult(
            query=query.strip(),
            total_match_count=0,
            returned_records=(),
            result_limit=result_limit,
            reference_source=reference_source,
        )
    active_reference: CcldFacilityReferenceSource | None = reference_source
    active_records: tuple[CcldFacilityLookupRecord, ...] | None = (
        tuple(records) if records is not None else None
    )
    if active_records is None:
        active_reference = load_active_ccld_facility_reference()
        active_records = active_reference.records
    query_tokens = tuple(normalized_query.split())
    matches = tuple(
        record for record in active_records if _record_matches_query(record, query_tokens)
    )
    return CcldFacilityLookupResult(
        query=query.strip(),
        total_match_count=len(matches),
        returned_records=matches[:result_limit],
        result_limit=result_limit,
        reference_source=active_reference,
    )


def route_ccld_facility_lookup_response(path: str) -> tuple[int, str, bytes]:
    return route_ccld_facility_lookup_response_with_source(path, None)


def route_ccld_facility_lookup_response_with_source(
    path: str,
    reference_source: CcldFacilityReferenceSource | None,
) -> tuple[int, str, bytes]:
    parsed_url = urlparse(path)
    if parsed_url.path != CCLD_FACILITY_LOOKUP_PATH:
        return _html_response(
            404,
            _render_message_page(
                title="CCLD facility lookup not found",
                heading="CCLD facility lookup not found",
                message="The requested local/test CCLD facility lookup page was not found.",
            ),
        )
    query_values = parse_qs(parsed_url.query, keep_blank_values=True)
    query = _first_query_value(query_values, "q")
    return _html_response(200, render_ccld_facility_lookup_page(query, reference_source))


def render_ccld_facility_lookup_page(
    query: str = "",
    reference_source: CcldFacilityReferenceSource | None = None,
) -> str:
    reference_source = reference_source or load_active_ccld_facility_reference()
    result = search_ccld_facilities(
        query,
        reference_source.records,
        reference_source=reference_source,
    )
    limited_note = _limited_reference_note(reference_source)
    return _page(
        title="Find CCLD facility",
                heading="Find a facility",
                main=f"""    <section class="hero-card attorney-hero" aria-labelledby="facility-lookup-scope-heading">
                    <div>
                        <p class="launch-kicker">Facility intake</p>
            <h2 id="facility-lookup-scope-heading">Find a facility</h2>
                        <p class="launch-value">Start review by finding the CCLD facility/license number, then carry that selected facility into the request page to choose a complaint date range.</p>
                    </div>
        </section>
        <section class="quiet-section" aria-labelledby="facility-start-guidance-heading">
            <h2 id="facility-start-guidance-heading">Lookup or manual entry?</h2>
            <p>Use facility lookup when you know a facility name, city, ZIP, type, or status but not the exact facility/license number. Use manual entry when you already know the digit facility/license number.</p>
            <p>Lookup rows are local/test reference assistance, not complaint source truth, not statewide completeness proof, and not legal or facility-wide conclusions.</p>
        </section>
    {_render_facility_combobox_section(reference_source, query, limited_note)}
    {_render_lookup_results(result)}
    {_render_reference_details_section(reference_source)}
        <details class="technical-details">
            <summary id="manual-entry-heading">Enter a facility/license number directly</summary>
            <p>If you already know the CCLD facility/license number, type it on the request form.</p>
            <p><a class="button-quiet" href="{CCLD_RECORD_REQUEST_PATH}">Open request form</a></p>
        </details>""",
    )


def facility_reference_from_source_derived_records(
    records: Iterable[Mapping[str, Any]],
    *,
    warning: str | None = None,
) -> CcldFacilityReferenceSource:
    facility_records = tuple(
        sorted(
            (
                _facility_lookup_record_from_source_record(record)
                for record in records
                if _source_record_entity_type(record) == "facility"
            ),
            key=lambda record: (record.facility_name, record.facility_number),
        )
    )
    warnings = () if warning is None else (warning,)
    if not facility_records and warning is None:
        warnings = (
            "No PostgreSQL-backed source-derived facility rows are loaded yet. "
            "Run migrations and import a validated CCLD artifact before facility search.",
        )
    return CcldFacilityReferenceSource(
        source_kind="postgres_source_derived",
        label="PostgreSQL source-derived facility records",
        path_label="hosted_source_derived_records",
        records=facility_records,
        warnings=warnings,
    )


def _source_record_entity_type(record: Mapping[str, Any]) -> str:
    value = record.get("entity_type")
    return value if isinstance(value, str) else ""


def _facility_lookup_record_from_source_record(
    record: Mapping[str, Any],
) -> CcldFacilityLookupRecord:
    original_values = record.get("original_values")
    values = original_values if isinstance(original_values, Mapping) else {}
    facility_number = _source_value(values, "external_facility_number") or _source_value(
        values, "facility_id"
    )
    return CcldFacilityLookupRecord(
        facility_number=facility_number,
        facility_name=_source_value(values, "facility_name"),
        city=_source_value(values, "city"),
        county=_source_value(values, "county"),
        zip_code=_source_value(values, "zip_code"),
        facility_type=_source_value(values, "facility_type"),
        status=_source_value(values, "status"),
        closed_date=_source_value(values, "closed_date"),
    )


def _source_value(values: Mapping[str, Any], key: str) -> str:
    value = values.get(key)
    return value.strip() if isinstance(value, str) else ""


def _record_from_row(row: dict[str, str]) -> CcldFacilityLookupRecord:
    facility_number = _clean_value(row["Facility Number"])
    if not facility_number.isdigit():
        raise ValueError("CCLD facility reference facility numbers must contain digits only.")
    return CcldFacilityLookupRecord(
        facility_number=facility_number,
        facility_name=_clean_value(row["Facility Name"]),
        city=_clean_value(row["Facility City"]),
        county=_clean_value(row["County Name"]),
        zip_code=_clean_value(row["Facility Zip"]),
        facility_type=_clean_value(row["Facility Type"]),
        status=_clean_value(row["Facility Status"]),
        closed_date=_clean_value(row["Closed Date"]),
    )


def _tiny_fixture_reference(
    *,
    warnings: tuple[str, ...] = (),
) -> CcldFacilityReferenceSource:
    return CcldFacilityReferenceSource(
        source_kind="tiny_fixture_fallback",
        label="Tiny committed CCLD facility fixture fallback",
        path_label=DEFAULT_CCLD_FACILITY_REFERENCE_PATH.as_posix(),
        records=load_ccld_facility_reference(DEFAULT_CCLD_FACILITY_REFERENCE_PATH),
        warnings=warnings,
    )


def _record_matches_query(
    record: CcldFacilityLookupRecord,
    query_tokens: tuple[str, ...],
) -> bool:
    search_text = _normalized_text(
        " ".join(
            (
                record.facility_number,
                record.facility_name,
                record.city,
                record.county,
                record.zip_code,
                record.facility_type,
                record.status,
                record.closed_date,
            )
        )
    )
    return all(token in search_text for token in query_tokens)


def _render_lookup_form(query: str) -> str:
    """Legacy search form – preserved for no-JS fallback submission only."""
    return f"""    <section aria-labelledby="facility-search-heading">
            <h2 id="facility-search-heading">Search facility reference</h2>
      <p id="facility-search-help">Search by facility/license number, facility name, city,
      county, ZIP code, facility type, or status when those fields are present in the
      reference list.</p>
      <form action="{CCLD_FACILITY_LOOKUP_PATH}" method="get">
        <p>
          <label for="facility_lookup_query">Facility search</label>
          <input id="facility_lookup_query" name="q" type="search"
            value="{_escape(query)}" aria-describedby="facility-search-help">
        </p>
        <p><button type="submit" class="button-secondary">Search CCLD facilities</button></p>
      </form>
    </section>"""


def _render_facility_combobox_section(
    reference_source: CcldFacilityReferenceSource,
    current_query: str,
    limited_note: str,
) -> str:
    json_data = _build_facility_json_data(reference_source)
    limited_note_markup = (
        f'<p class="helper-text limited-note">{_escape(limited_note)}</p>'
        if limited_note
        else ""
    )
    selected_card = _render_facility_selected_card_html(mode="facility")
    return f"""    <section class="workflow-panel" aria-labelledby="facility-combobox-heading" id="facility-selector-wrap" data-facility-mode="facility">
            <label for="facility-search-input">Facility</label>
            <p id="facility-search-hint" class="helper-text">Search by name, license number, city, ZIP, type, or status.</p>
            <form action="{CCLD_FACILITY_LOOKUP_PATH}" method="get" class="facility-search-form">
                <div class="facility-combobox-outer" id="facility-combobox-outer">
                    <input id="facility-search-input" name="q" type="search" autocomplete="off"
                        placeholder="Name, license number, city, or ZIP"
                        aria-describedby="facility-search-hint"
                        value="{_escape(current_query)}">
                    <ul id="facility-suggestion-list" class="facility-suggestions" aria-label="Facility suggestions" hidden></ul>
                </div>
                <div class="form-actions">
                    <button type="submit" class="button-secondary">Search CCLD facilities</button>
                </div>
            </form>
{limited_note_markup}
{selected_card}
            <script type="application/json" id="facility-reference-json">{json_data}</script>
            <script>{_FACILITY_COMBOBOX_JS}</script>
    </section>"""


def _render_facility_selected_card_html(*, mode: str = "facility") -> str:
    """Render the hidden selected-facility confirmation card filled by JS."""
    if mode == "request":
        actions = """<div class="form-actions">
                    <button type="submit" class="button">Continue to dates</button>
                    <button type="button" id="facility-change-btn" class="button-secondary">Change selected facility</button>
                </div>"""
    else:
        actions = """<div class="form-actions">
                    <a id="facility-use-link" class="button selected-use-link" href="#">Use this facility for complaint record retrieval</a>
                    <button type="button" id="facility-change-btn" class="button-secondary">Change selected facility</button>
                </div>"""
    return f"""    <div id="facility-selected-card" class="facility-selected-card" hidden>
                <div class="selected-facility-info">
                    <h3 class="selected-name"></h3>
                    <p><span class="badge badge-muted selected-number"></span></p>
                    <p class="selected-geo sr-note"></p>
                    <p class="selected-meta sr-note"></p>
                </div>
{actions}
    </div>"""


def _render_reference_source_section(source: CcldFacilityReferenceSource) -> str:
    """Legacy - renders the reference source section (now only used as a visible panel when there is a problem)."""
    warning_markup = ""
    if source.warnings:
        warning_items = "\n".join(
            f"        <li>{_escape(warning)}</li>" for warning in source.warnings
        )
        warning_markup = f"""      <ul>
{warning_items}
      </ul>"""
    card_class = "warning-card" if source.source_kind == "tiny_fixture_fallback" else "summary-card"
    return f"""    <section class="{card_class}" aria-labelledby="reference-source-heading">
      <h2 id="reference-source-heading">Facility reference source</h2>
            <p id="reference-source-help">Active source: {_escape(source.label)}.</p>
      <dl aria-describedby="reference-source-help">
        <dt>Rows loaded for lookup</dt>
        <dd>{len(source.records)}</dd>
      </dl>
{warning_markup}
        <p>Reference data is lookup assistance only. It is not imported, persisted, or source-completeness proof.</p>
        <details>
            <summary>Developer reference setup</summary>
            <p>Full local/test CSV support is read-only. Full facility CSV files must stay outside
            the repository and are not imported or persisted by this app.</p>
            <p>To use a full local/test CSV, set <code>{CCLD_FACILITY_REFERENCE_CSV_ENV}</code>
            or configure the documented ignored local reference location. Local paths are not shown in the browser.</p>
        </details>
    </section>"""


def _render_reference_details_section(source: CcldFacilityReferenceSource) -> str:
    """Collapsed reference data details section for developer/operator reference."""
    warning_markup = ""
    if source.warnings:
        warning_items = "\n".join(
            f"            <li>{_escape(warning)}</li>" for warning in source.warnings
        )
        warning_markup = f"""          <ul>
{warning_items}
          </ul>"""
    user_label = _user_facing_source_label(source)
    return f"""    <details class="reference-details-section">
            <summary>Reference data details</summary>
            <p>{_escape(user_label)} &mdash; {len(source.records)} record(s) loaded.</p>
            <p>Reference data is lookup assistance only. It is not imported, persisted, or
            source-completeness proof. CCLD public portal remains the source of record.</p>
{warning_markup}
            <p>To use a full facility reference CSV, set
            <code>{CCLD_FACILITY_REFERENCE_CSV_ENV}</code> or place the file at the documented
            local reference location. Local paths are not shown here.</p>
    </details>"""


def _render_lookup_results(result: CcldFacilityLookupResult) -> str:
    if result.empty_search:
                return ""
    if not result.returned_records:
        return f"""    <section class="empty-state-card" aria-labelledby="facility-results-heading">
      <h2 id="facility-results-heading">Facility results</h2>
      <p>No facilities matched <strong>{_escape(result.query)}</strong>.</p>
      <p>Try a shorter name, license number, city, ZIP, or facility type. You can also enter
      a facility/license number directly on the request form.</p>
    <p><a class="button-quiet" href="{CCLD_RECORD_REQUEST_PATH}">Open request form</a></p>
    </section>"""
    cards = "\n".join(_render_result_card(record) for record in result.returned_records)
    if result.has_more_matches:
        more_guidance = f"""      <p class="helper-text">Showing {len(result.returned_records)} of
      {result.total_match_count} matches. Refine your search to narrow the list.</p>"""
    else:
        more_guidance = f"""      <p class="helper-text">Showing {len(result.returned_records)} of
      {result.total_match_count} matching facilit{"y" if result.total_match_count == 1 else "ies"}.</p>"""
    return f"""    <section aria-labelledby="facility-results-heading">
      <h2 id="facility-results-heading">Facility results</h2>
{more_guidance}
            <div class="result-list" aria-label="Facility matches">
{cards}
            </div>
    </section>"""


def _render_result_card(record: CcldFacilityLookupRecord) -> str:
    query_values = {
        "facility_number": record.facility_number,
        "request_context_origin": "facility_lookup",
        "lookup_facility_name": record.facility_name,
    }
    href = f"{CCLD_RECORD_REQUEST_PATH}?{urlencode(query_values)}"
    geo_parts = [record.city, record.county, record.zip_code]
    geo = ", ".join(p for p in geo_parts if p)
    type_status = " ".join(
        f'<span class="badge badge-muted">{_escape(value)}</span>'
        for value in (record.facility_type, record.status)
        if value
    )
    return f"""        <article class="result-card" aria-labelledby="facility-{_escape(record.facility_number)}-heading">
          <div>
            <h3 id="facility-{_escape(record.facility_number)}-heading">{_escape(record.facility_name)}</h3>
            <p><span class="badge badge-muted">{_escape(record.facility_number)}</span></p>
            {f'<p class="sr-note">{_escape(geo)}</p>' if geo else ''}
                        {f'<p>{type_status}</p>' if type_status else ''}
          </div>
          <p><a class="button" href="{_escape(href)}" aria-label="Use {_escape(record.facility_name)} / {_escape(record.facility_number)} for complaint record retrieval">Use this facility for complaint record retrieval</a></p>
        </article>"""


def _render_message_page(*, title: str, heading: str, message: str) -> str:
    return _page(
        title=title,
        heading=heading,
        main=f"""    <section aria-labelledby="message-heading">
      <h2 id="message-heading">{_escape(heading)}</h2>
      <p>{_escape(message)}</p>
      <p><a href="{CCLD_FACILITY_LOOKUP_PATH}">Open CCLD facility lookup</a></p>
    </section>""",
    )


def _page(*, title: str, heading: str, main: str) -> str:
        return render_page_shell(
                title=title,
                heading=heading,
                main=main,
                skip_label="Skip to main CCLD facility lookup content",
                nav_label="Hosted scaffold navigation",
                active_path=CCLD_FACILITY_LOOKUP_PATH,
                step_id="facility",
                next_action="Review this facility",
        )


def _first_query_value(query_values: dict[str, list[str]], key: str) -> str:
    values = query_values.get(key, [])
    if not values:
        return ""
    return values[0].strip()


def _safe_path_label(path: Path) -> str:
    if path.is_absolute():
        return path.name
    return path.as_posix()


def _clean_value(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.split())


def _normalized_text(value: str) -> str:
    return _clean_value(value).casefold()


def _display_value(value: str) -> str:
    return value if value else "not listed"


def _user_facing_source_label(source: CcldFacilityReferenceSource) -> str:
    """Return a clean, user-facing label for the reference source (no internal paths/jargon)."""
    if source.source_kind == "tiny_fixture_fallback":
        return "Limited reference list"
    return "Facility reference list"


def _limited_reference_note(source: CcldFacilityReferenceSource) -> str:
    """Return a concise limited-reference note when only the tiny fallback is loaded."""
    if source.source_kind == "tiny_fixture_fallback" or len(source.records) <= 2:
        return "Limited reference list: suggestions may not include every CCLD facility."
    return ""


def _build_facility_json_data(
    source: CcldFacilityReferenceSource,
    *,
    limit: int = 100,
) -> str:
    """Return a safe JSON array of facility objects for the combobox JS enhancement."""
    records = [
        {
            "num": record.facility_number,
            "n": record.facility_name,
            "city": record.city,
            "co": record.county,
            "zip": record.zip_code,
            "t": record.facility_type,
            "s": record.status,
        }
        for record in source.records[:limit]
    ]
    raw = json.dumps(records, ensure_ascii=True)
    # Prevent </script> injection in the embedded JSON block
    return raw.replace("</", "<\\/")


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def _html_response(status: int, markup: str) -> tuple[int, str, bytes]:
    _assert_no_secret_markers(markup)
    return status, "text/html; charset=utf-8", markup.encode("utf-8")


def _assert_no_secret_markers(markup: str) -> None:
    lowered = markup.casefold()
    for marker in _SECRET_HTML_MARKERS:
        if marker in lowered:
            raise ValueError(f"CCLD facility lookup HTML contains blocked marker: {marker}")
