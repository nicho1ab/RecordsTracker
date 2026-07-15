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

from ccld_complaints.hosted_app.facility_review_signals import (
    FacilityReviewSignalsSummary,
    load_active_facility_review_signals,
)
from ccld_complaints.hosted_app.ui_shell import (
    ActionItem,
    render_action_group,
    render_page_shell,
)
from ccld_complaints.presentation_values import (
    PresentationValueKind,
    presentation_value,
    presentation_value_for_field,
)

CCLD_FACILITY_LOOKUP_PATH = "/ccld/facilities"
CCLD_FACILITY_SUGGESTIONS_PATH = f"{CCLD_FACILITY_LOOKUP_PATH}/suggestions"
CCLD_FACILITY_REVIEW_HUB_PATH = f"{CCLD_FACILITY_LOOKUP_PATH}/detail"
CCLD_FACILITY_REVIEW_PRIORITY_PATH = f"{CCLD_FACILITY_LOOKUP_PATH}/review-priority"
CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH = f"{CCLD_FACILITY_LOOKUP_PATH}/intelligence"
CCLD_RECORD_REQUEST_PATH = "/ccld/records/request"
REVIEWER_UI_RECORDS_PATH = "/reviewer/records"
REVIEWER_UI_DETAIL_PATH = f"{REVIEWER_UI_RECORDS_PATH}/detail"
REVIEWER_UI_MATRIX_EXPORT_PATH = "/reviewer/records/matrix.csv"
REVIEWER_UI_PACKET_PREVIEW_PATH = "/reviewer/packet/preview"
REVIEWER_UI_PACKET_DRAFT_PATH = "/reviewer/packet/draft"
DEFAULT_CCLD_FACILITY_REFERENCE_PATH = Path(
    "tests/fixtures/public_source_facilities/ccld_program_facilities_tiny.csv"
)
DEFAULT_FULL_CCLD_FACILITY_REFERENCE_PATH = Path(
  "data/raw/ccld/facility-reference.csv"
)
CCLD_FACILITY_REFERENCE_CSV_ENV = "CCLD_FACILITY_REFERENCE_CSV"
MAX_FACILITY_LOOKUP_RESULTS = 25
MAX_FACILITY_PRIORITY_RESULTS = 100
_PROGRAM_FACILITY_REQUIRED_COLUMNS = (
    "Facility Number",
    "Facility Name",
    "Facility City",
    "Facility State",
    "County Name",
    "Facility Zip",
    "Facility Type",
    "Facility Capacity",
    "Facility Status",
    "Closed Date",
)
_CHHS_FACILITY_MASTER_REQUIRED_COLUMNS = (
    "FAC_NBR",
    "NAME",
    "PROGRAM_TYPE",
    "STATUS",
    "CAPACITY",
    "RES_CITY",
    "RES_STATE",
    "RES_ZIP_CODE",
    "COUNTY",
    "FAC_TYPE_DESC",
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
_FACILITY_STATUS_CODE_LABELS = {
    "3": "Licensed",
}

_FACILITY_COMBOBOX_JS = r"""(function(){
  'use strict';
  var wrap=document.getElementById('facility-selector-wrap');
  if(!wrap)return;
  var mode=wrap.getAttribute('data-facility-mode')||'request';
  var si=document.getElementById('facility-search-input');
  var nf=document.getElementById('facility-number-field');
  var of_=document.getElementById('facility-origin-field');
  var lf=document.getElementById('facility-name-field');
  var sb=document.getElementById('facility-submit-btn');
  var sl=document.getElementById('facility-suggestion-list');
  var sc=document.getElementById('facility-selected-card');
  var de=document.getElementById('facility-reference-json');
  var suggestUrl=wrap.getAttribute('data-facility-suggest-url')||'';
  if(!si||!sl||!de)return;
  var facs=[];
  var requestSeq=0;
  try{facs=JSON.parse(de.textContent||'[]');}catch(e){return;}
  // Show JS combobox, hide no-JS fallback
  var co=document.getElementById('facility-combobox-outer');
  if(co)co.style.display='';
  if(nf)nf.style.display='none';
  // Enhance input placeholder for text search
  si.placeholder='Name, Facility ID, city, or ZIP';
  si.removeAttribute('inputmode');
  // ARIA
  si.setAttribute('aria-expanded','false');
  si.setAttribute('aria-autocomplete','list');
  si.setAttribute('aria-controls','facility-suggestion-list');
  sl.setAttribute('role','listbox');
  function norm(s){return(s||'').toLowerCase().replace(/\s+/g,' ').trim();}
  function updateSubmitState(){
    if(sb)sb.disabled=!si.value.trim();
  }
  function match(f,toks){
        var h=norm([f.num,f.n,f.city,f.state,f.co,f.zip,f.t,f.p,f.cap,f.s].join(' '));
    return toks.every(function(t){return h.indexOf(t)!==-1;});
  }
  function esc(s){
    return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
  function statusInfo(s){
    var raw=String(s==null?'':s).trim();
    var v=norm(raw);
    if(v==='3'||v.indexOf('licensed')!==-1)return{label:'Licensed',cls:'licensed'};
    if(v.indexOf('closed')!==-1)return{label:'Closed',cls:'closed'};
    if(v.indexOf('pending')!==-1)return{label:'Pending',cls:'pending'};
    if(raw)return{label:'Other',cls:'other',title:'Other status: '+raw};
    return{label:'Unknown',cls:'other',title:'Status unknown'};
  }
  function buildHtml(matches){
    var h='';
    for(var i=0;i<matches.length;i++){
      var f=matches[i];
    var info=statusInfo(f.s);
    var geo=[f.city,f.state,f.zip].filter(Boolean).join(' \u00b7 ');
    var meta=[f.num,f.co,f.t,f.p].filter(Boolean).join(' \u2022 ');
      var det=[geo,meta].filter(Boolean).join(' | ');
      h+='<li role="option"><button type="button" class="suggestion-btn"'
        +' data-num="'+esc(f.num)+'" data-name="'+esc(f.n)+'"'
        +' data-city="'+esc(f.city||'')+'" data-state="'+esc(f.state||'')+'"'
        +' data-zip="'+esc(f.zip||'')+'" data-type="'+esc(f.t||'')+'"'
        +' data-program="'+esc(f.p||'')+'" data-status="'+esc(f.s||'')+'">'
        +'<span class="suggestion-main">'
        +'<span class="suggestion-status suggestion-status-'+esc(info.cls)+'" aria-label="Facility status: '+esc(info.title||info.label)+'" title="'+esc(info.title||('Facility status: '+info.label))+'">'+esc(info.label)+'</span>'
        +'<span class="suggestion-name">'+esc(f.n)+'</span>'
        +'</span>'
        +' <span class="suggestion-badge">Facility ID '+esc(f.num)+'</span>'
        +(det?'<span class="suggestion-details">'+esc(det)+'</span>':'')
        +'</button></li>';
    }
    return h;
  }
  function renderMatches(matches){
    if(!matches.length){sl.innerHTML='<li><span class="suggestion-empty">No matches found.</span></li>';}
    else{sl.innerHTML=buildHtml(matches);}
    sl.removeAttribute('hidden');
    si.setAttribute('aria-expanded','true');
  }
  function showSugs(q){
    var toks=norm(q).split(' ').filter(Boolean);
    if(!toks.length){hideSugs();return;}
    if(suggestUrl&&typeof fetch==='function'){
      var seq=++requestSeq;
      sl.innerHTML='<li><span class="suggestion-empty">Searching...</span></li>';
      sl.removeAttribute('hidden');
      si.setAttribute('aria-expanded','true');
      fetch(suggestUrl+'?q='+encodeURIComponent(q),{headers:{'Accept':'application/json'}})
        .then(function(resp){if(!resp.ok)throw new Error('lookup');return resp.json();})
        .then(function(data){if(seq!==requestSeq)return;renderMatches(data.records||[]);})
        .catch(function(){if(seq!==requestSeq)return;renderMatches([]);});
      return;
    }
    var ms=[];
    for(var i=0;i<facs.length&&ms.length<25;i++){if(match(facs[i],toks))ms.push(facs[i]);}
    renderMatches(ms);
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
    var sf=sc.querySelector('.selected-facility-number-field');
    var so=sc.querySelector('.selected-facility-origin-field');
    var sn=sc.querySelector('.selected-facility-name-field');
    if(ne)ne.textContent=f.n;
    if(nue)nue.textContent=f.num;
    if(ge)ge.textContent=[f.city,f.state,f.zip].filter(Boolean).join(', ');
    if(me)me.textContent=[f.t,f.p,f.s].filter(Boolean).join(' \u2022 ');
    if(sf)sf.value=f.num;
    if(so)so.value='facility_lookup';
    if(sn)sn.value=f.n;
    if(ul){
      ul.href='/ccld/records/request?facility_number='+encodeURIComponent(f.num)
        +'&request_context_origin=facility_lookup'
        +'&lookup_facility_name='+encodeURIComponent(f.n);
    ul.setAttribute('aria-label','Use '+f.n+' / '+f.num+' for Request Records');
    }
    sc.removeAttribute('hidden');
  }
  function clearSel(){
    if(sc)sc.setAttribute('hidden','');
    si.value='';
    if(of_)of_.value='manual_entry';
    if(lf)lf.value='';
    var sf=sc?sc.querySelector('.selected-facility-number-field'):null;
    var sn=sc?sc.querySelector('.selected-facility-name-field'):null;
    if(sf)sf.value='';
    if(sn)sn.value='';
    updateSubmitState();
    si.focus();
  }
  function selFac(btn){
    var f={
      num:btn.getAttribute('data-num'),n:btn.getAttribute('data-name'),
      city:btn.getAttribute('data-city'),zip:btn.getAttribute('data-zip'),
            state:btn.getAttribute('data-state'),t:btn.getAttribute('data-type'),
            p:btn.getAttribute('data-program'),s:btn.getAttribute('data-status')
    };
    hideSugs();
    if(mode==='request'){
      si.value=f.num;
      if(of_)of_.value='facility_lookup';
      if(lf)lf.value=f.n;
    }else{
      si.value=f.n;
    }
    updateSubmitState();
    setCard(f);
    si.focus();
  }
  si.addEventListener('input',function(){
    if(mode==='request'){
      if(of_)of_.value='manual_entry';
      if(lf)lf.value='';
      if(sc)sc.setAttribute('hidden','');
    }
    updateSubmitState();
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
  updateSubmitState();
  document.addEventListener('click',function(e){if(!wrap.contains(e.target))hideSugs();});
}());"""


@dataclass(frozen=True)
class CcldFacilityLookupRecord:
    facility_number: str
    facility_name: str
    city: str
    state: str
    county: str
    zip_code: str
    facility_type: str
    program_type: str
    capacity: str
    status: str
    closed_date: str
    address: str = ""
    regional_office: str = ""
    facility_address: str | None = None
    fac_do_desc: str | None = None
    res_street_addr: str | None = None
    capacity_source_present: bool | None = None
    closed_date_source_present: bool | None = None


@dataclass(frozen=True)
class CcldFacilityReferenceSource:
    source_kind: str
    label: str
    path_label: str
    records: tuple[CcldFacilityLookupRecord, ...]
    notices: tuple[str, ...] = ()
    record_count: int | None = None


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


@dataclass(frozen=True)
class CcldReviewNextRecommendation:
    label: str
    finding_status_cue: str
    date_label: str
    detail_href: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class CcldFacilityReviewContext:
    loaded_complaint_record_count: int = 0
    start_date: str = ""
    end_date: str = ""
    source_label: str = "Loaded source-derived complaint records"
    finding_counts: tuple[tuple[str, int], ...] = ()
    source_traceability_count: int = 0
    delay_review_record_count: int = 0
    missing_date_record_count: int = 0
    recent_activity_date: str = ""
    reviewer_status_counts: tuple[tuple[str, int], ...] = ()
    reviewer_note_record_count: int = 0
    review_next_label: str = ""
    review_next_recommendations: tuple[CcldReviewNextRecommendation, ...] = ()

    @property
    def has_loaded_context(self) -> bool:
        return self.loaded_complaint_record_count > 0

    @property
    def has_date_context(self) -> bool:
        return bool(self.start_date and self.end_date)


def load_ccld_facility_reference(
    path: Path = DEFAULT_CCLD_FACILITY_REFERENCE_PATH,
) -> tuple[CcldFacilityLookupRecord, ...]:
    with path.open("r", encoding="utf-8-sig", newline="") as fixture_file:
        reader = csv.DictReader(fixture_file)
        fieldnames = tuple(reader.fieldnames or ())
        row_mapper = _facility_row_mapper(fieldnames)
        records = tuple(row_mapper(row) for row in reader)
    return _deduplicate_facility_records(records)


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
                    label="Full CCLD facility reference CSV",
                    path_label=_safe_path_label(configured_reference),
                    records=load_ccld_facility_reference(configured_reference),
                )
            except ValueError as error:
                return _tiny_fixture_reference(
                    notices=(
                        "Configured full CCLD facility reference CSV "
                        f"could not be loaded: {error}. Using tiny fixture fallback.",
                    )
                )
        return _tiny_fixture_reference(
            notices=(
                "Configured full CCLD facility reference CSV was not found. "
                "Using tiny fixture fallback.",
            )
        )
    if DEFAULT_FULL_CCLD_FACILITY_REFERENCE_PATH.exists():
        try:
            return CcldFacilityReferenceSource(
                source_kind="full_local_test_csv",
                label="Full CCLD facility reference CSV",
                path_label=_safe_path_label(DEFAULT_FULL_CCLD_FACILITY_REFERENCE_PATH),
                records=load_ccld_facility_reference(
                    DEFAULT_FULL_CCLD_FACILITY_REFERENCE_PATH
                ),
            )
        except ValueError as error:
            return _tiny_fixture_reference(
                notices=(
                    "Default full CCLD facility reference CSV could not be "
                    f"loaded: {error}. Using tiny fixture fallback.",
                )
            )
    return _tiny_fixture_reference(
        notices=(
            "No full CCLD facility reference CSV is configured or available. "
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
    review_context: CcldFacilityReviewContext | None = None,
    lookup_result: CcldFacilityLookupResult | None = None,
) -> tuple[int, str, bytes]:
    parsed_url = urlparse(path)
    if parsed_url.path not in {
        CCLD_FACILITY_LOOKUP_PATH,
        CCLD_FACILITY_SUGGESTIONS_PATH,
        CCLD_FACILITY_REVIEW_HUB_PATH,
        CCLD_FACILITY_REVIEW_PRIORITY_PATH,
        CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH,
    }:
        return _html_response(
            404,
            _render_message_page(
                title="CCLD facility lookup not found",
                heading="CCLD facility lookup not found",
                message="The requested CCLD facility lookup page was not found.",
            ),
        )
    query_values = parse_qs(parsed_url.query, keep_blank_values=True)
    if parsed_url.path == CCLD_FACILITY_SUGGESTIONS_PATH:
        return _json_response(
            200,
            _facility_suggestions_payload(
                _first_query_value(query_values, "q"),
                reference_source,
                lookup_result=lookup_result,
            ),
        )
    if parsed_url.path == CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH:
        return _html_response(
            503,
            _render_message_page(
                title="Facility review intelligence unavailable",
                heading="Facility review intelligence unavailable",
                message=(
                    "This route requires an authorized loaded-corpus reviewer context. "
                    "It does not fall back to facility-summary or fixture records."
                ),
            ),
        )
    if parsed_url.path == CCLD_FACILITY_REVIEW_PRIORITY_PATH:
        return _html_response(200, render_ccld_facility_review_priority_page(query_values))
    if parsed_url.path == CCLD_FACILITY_REVIEW_HUB_PATH:
        facility_number = _first_query_value(query_values, "facility_number")
        return _html_response(
            200,
            render_ccld_facility_review_hub_page(
                facility_number,
                reference_source,
                review_context=review_context,
            ),
        )
    query = _first_query_value(query_values, "q")
    return _html_response(
        200,
        render_ccld_facility_lookup_page(
            query,
            reference_source,
            lookup_result=lookup_result,
        ),
    )


def render_ccld_facility_lookup_page(
    query: str = "",
    reference_source: CcldFacilityReferenceSource | None = None,
    lookup_result: CcldFacilityLookupResult | None = None,
    active_path: str = CCLD_FACILITY_LOOKUP_PATH,
) -> str:
    reference_source = reference_source or load_active_ccld_facility_reference()
    result = lookup_result or search_ccld_facilities(
        query,
        reference_source.records,
        reference_source=reference_source,
    )
    limited_note = _limited_reference_note(reference_source)
    lookup_unavailable = _is_lookup_unavailable(reference_source)
    if lookup_unavailable:
        hero_value = (
            "Enter a known CCLD Facility ID, then continue to Request Records to choose a complaint date range."
        )
        primary_action_section = f"""    <section class="workflow-panel" aria-labelledby="facility-manual-entry-primary-heading">
      <h2 id="facility-manual-entry-primary-heading">Enter a Facility ID directly</h2>
      <p>Use manual entry when lookup is unavailable or when you already know the digit Facility ID.</p>
      {render_action_group(primary=ActionItem("Open Request Records", CCLD_RECORD_REQUEST_PATH), aria_label="Known facility number actions")}
    </section>"""
        lookup_section_label = "Facility directory search (not configured)"
        lookup_section_intro = f"""    <section class="quiet-section" aria-labelledby="facility-start-guidance-heading">
      <h2 id="facility-start-guidance-heading">{_escape(lookup_section_label)}</h2>
      <p>Use Request Records to enter a known Facility ID directly.</p>
      <p>Lookup rows are public facility-directory data for finding the Facility ID before Request Records.</p>
    </section>"""
    else:
        hero_value = (
            "Start review by finding the CCLD Facility ID in the preloaded facility directory, "
            "then carry that selected facility into the request page to choose a complaint date range."
        )
        primary_action_section = ""
        lookup_section_intro = ""
    optional_planning_actions = render_action_group(
        secondary=(
            ActionItem(
                "Facility review priority list",
                CCLD_FACILITY_REVIEW_PRIORITY_PATH,
            ),
            ActionItem(
                "Facility review intelligence",
                CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH,
            ),
        ),
        aria_label="Optional planning view actions",
    )
    manual_entry_section = "" if lookup_unavailable else f"""    <details class="technical-details">
      <summary id="manual-entry-heading">Enter a Facility ID directly</summary>
      <p>If you already know the CCLD Facility ID, type it on Request Records.</p>
      {render_action_group(secondary=(ActionItem("Open Request Records", CCLD_RECORD_REQUEST_PATH),), aria_label="Manual entry actions")}
    </details>"""
    return _page(
        title="Find a Facility",
        heading="Find a Facility",
        active_path=active_path,
        main=f"""    <section class="hero-card attorney-hero" aria-labelledby="facility-lookup-scope-heading">
      <div>
        <p class="launch-kicker">Facility intake</p>
        <h2 id="facility-lookup-scope-heading">Find a facility</h2>
        <p class="launch-value">{_escape(hero_value)}</p>
      </div>
    </section>
{primary_action_section}
{lookup_section_intro}
    {_render_facility_combobox_section(reference_source, query, limited_note)}
{manual_entry_section}
    {_render_lookup_results(result)}
        <section class="quiet-section" aria-labelledby="facility-priority-link-heading">
            <h2 id="facility-priority-link-heading">Optional planning views</h2>
            <p>Optional planning views provide supplemental facility-review context when available. They are not required for Request Records or review.</p>
            <details>
                <summary>Open optional planning views</summary>
                {optional_planning_actions}
            </details>
        </section>
    {_render_reference_details_section(reference_source)}""",
    )


def render_ccld_facility_review_hub_page(
    facility_number: str,
    reference_source: CcldFacilityReferenceSource | None = None,
    *,
    review_context: CcldFacilityReviewContext | None = None,
) -> str:
    reference_source = reference_source or load_active_ccld_facility_reference()
    facility_number = facility_number.strip()
    matching_records = tuple(
        record
        for record in reference_source.records
        if record.facility_number == facility_number
    )
    signals_summary = load_active_facility_review_signals().summary_for_facility(
        facility_number
    )
    if not facility_number or not matching_records:
        if facility_number and signals_summary is not None:
            return _render_signal_only_facility_hub_page(
                signals_summary,
                review_context=review_context or CcldFacilityReviewContext(),
            )
        return _page(
            title="Facility review hub not found",
            heading="Facility review hub",
            main=_render_facility_hub_not_found(facility_number),
        )
    record = matching_records[0]
    review_context = review_context or CcldFacilityReviewContext()
    return _page(
        title="Facility review hub",
        heading="Facility review hub",
        main=f"""    {_render_facility_identity_and_core_facts(record, review_context)}
    {_render_facility_pattern_review_summary(record, review_context)}
    {_render_review_next_section(review_context)}
    {_render_facility_review_signals_section(signals_summary)}
    {_render_facility_hub_actions(record, review_context)}
    {_render_secondary_facility_facts(record)}
    """,
    )


def _render_signal_only_facility_hub_page(
    summary: FacilityReviewSignalsSummary,
    *,
    review_context: CcldFacilityReviewContext,
) -> str:
    record = _facility_record_from_signal_summary(summary)
    facility_label = _safe_priority_text(summary.facility_name or summary.facility_number)
    if not review_context.has_loaded_context:
        return _page(
            title="Facility summary",
            heading="Facility summary",
            main=f"""    <section class="hero-card attorney-hero" aria-labelledby="signal-only-facility-hub-heading">
            <div>
                <p class="launch-kicker">Facility summary</p>
                <h2 id="signal-only-facility-hub-heading">{_render_copyable_value("Copy facility name", facility_label)}</h2>
                <p class="launch-value">Facility-directory record not available. Uploaded public summary cues can still guide the next review step.</p>
                <dl class="summary-list">
                    <dt>Facility ID</dt>
                    <dd>{_render_copyable_value("Copy Facility ID", summary.facility_number)}</dd>
                </dl>
            </div>
        </section>
        <section aria-labelledby="signal-only-context-heading">
            <h2 id="signal-only-context-heading">Facility-directory record not available</h2>
            <p>Uploaded summary signals exist. Start a complaint request before drawing conclusions from complaint activity.</p>
        </section>
        {_render_facility_pattern_review_summary(record, review_context)}
        {_render_review_next_section(review_context)}
        {_render_facility_review_signals_section(summary)}
        {_render_facility_hub_actions(record, review_context)}
        {_render_copy_control_script()}
        """,
        )
    return _page(
    title="Facility summary",
    heading="Facility summary",
    main=f"""    <section class="hero-card attorney-hero" aria-labelledby="signal-only-facility-hub-heading">
            <div>
                <p class="launch-kicker">Facility summary</p>
                <h2 id="signal-only-facility-hub-heading">{_render_copyable_value("Copy facility name", facility_label)}</h2>
                <p class="launch-value">Facility-directory record not available. Uploaded public summary cues and loaded complaint records can still guide the next review step.</p>
                <dl class="summary-list">
                    <dt>Facility ID</dt>
                    <dd>{_render_copyable_value("Copy Facility ID", summary.facility_number)}</dd>
                </dl>
            </div>
        </section>
        <section aria-labelledby="signal-only-context-heading">
            <h2 id="signal-only-context-heading">Facility-directory record not available</h2>
            <p>Uploaded summary signals exist. Review loaded complaint records separately from directory lookup.</p>
        </section>
        {_render_facility_pattern_review_summary(record, review_context)}
        {_render_review_next_section(review_context)}
        {_render_facility_review_signals_section(summary)}
        {_render_facility_hub_actions(record, review_context)}
        {_render_copy_control_script()}""",
    )


def _facility_record_from_signal_summary(
    summary: FacilityReviewSignalsSummary,
) -> CcldFacilityLookupRecord:
    return CcldFacilityLookupRecord(
    facility_number=summary.facility_number,
    facility_name=summary.facility_name or summary.facility_number,
    city="",
    state="",
    county="; ".join(summary.counties),
    zip_code="",
    facility_type="; ".join(summary.facility_types),
    program_type="",
    capacity="; ".join(summary.capacities),
    status="; ".join(summary.statuses),
    closed_date="; ".join(summary.closed_dates),
    capacity_source_present=bool(summary.capacities),
    closed_date_source_present=bool(summary.closed_dates),
    )


def render_ccld_facility_review_priority_page(
        query_values: dict[str, list[str]] | None = None,
) -> str:
        query_values = query_values or {}
        signal_result = load_active_facility_review_signals()
        cue_filters = _selected_priority_cues(query_values)
        search_query = _priority_search_query(query_values)
        summaries = _searched_priority_summaries(
            _filtered_priority_summaries(signal_result.summaries, cue_filters),
            search_query,
        )
        returned_summaries = summaries[:MAX_FACILITY_PRIORITY_RESULTS]
        rows = "\n".join(_render_priority_row(summary) for summary in returned_summaries)
        if not rows:
                rows = _render_priority_empty_rows(cue_filters)
        cards = _render_priority_cards(signal_result, cue_filters, search_query)
        return _page(
                title="Facility review priority",
                heading="Facility review priority",
                main=f"""    <section class="hero-card attorney-hero" aria-labelledby="facility-priority-heading">
            <div>
                <p class="launch-kicker">Facility review priority</p>
                <h2 id="facility-priority-heading">Find facilities with review cues.</h2>
            </div>
        </section>
        {_render_priority_filter(cue_filters, search_query)}
        {_render_priority_summary(signal_result, summaries, returned_summaries)}
        {cards}
        <section aria-labelledby="facility-priority-list-heading">
            <h2 id="facility-priority-list-heading">Detailed priority table</h2>
            <table>
                <caption>Facility review priority from uploaded public summary fields</caption>
                <thead>
                    <tr>
                        <th scope="col">Facility</th>
                        <th scope="col">Review cues</th>
                        <th scope="col">Uploaded summary fields</th>
                        <th scope="col">Next action</th>
                    </tr>
                </thead>
                <tbody>
{rows}
                </tbody>
            </table>
        </section>
        {_render_priority_guidance_disclosure()}""",
        )


def facility_reference_from_source_derived_records(
    records: Iterable[Mapping[str, Any]],
    *,
    notice: str | None = None,
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
    notices = () if notice is None else (notice,)
    if not facility_records and notice is None:
        notices = (
            "Facility lookup suggestions are not available. Source-derived records may not include "
            "facility directory rows. Enter a Facility ID directly if you know it.",
        )
    return CcldFacilityReferenceSource(
        source_kind="postgres_source_derived",
        label="PostgreSQL source-derived facility records",
        path_label="hosted_source_derived_records",
        records=facility_records,
        notices=notices,
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
        state=_source_value(values, "state"),
        county=_source_value(values, "county"),
        zip_code=_source_value(values, "zip_code"),
        facility_type=_source_value(values, "facility_type"),
        program_type=_source_value(values, "program_type"),
        capacity=_source_value(values, "capacity"),
        status=_source_value(values, "status"),
        closed_date=_source_value(values, "closed_date"),
        address=_source_value(values, "address") or _source_value(values, "facility_address"),
        regional_office=_source_value(values, "regional_office") or _source_value(values, "FAC_DO_DESC"),
        facility_address=_source_value_if_present(values, "facility_address"),
        fac_do_desc=_source_value_if_present(values, "FAC_DO_DESC"),
        res_street_addr=_source_value_if_present(values, "RES_STREET_ADDR"),
        capacity_source_present="capacity" in values,
        closed_date_source_present="closed_date" in values,
    )


def _source_value(values: Mapping[str, Any], key: str) -> str:
    value = values.get(key)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, int | float) and not isinstance(value, bool):
        return str(value)
    return ""


def _source_value_if_present(values: Mapping[str, Any], key: str) -> str | None:
    if key not in values:
        return None
    value = values.get(key)
    if value is None:
        return ""
    return str(value).strip()


def _record_from_row(row: dict[str, str]) -> CcldFacilityLookupRecord:
    return _record_from_program_facility_row(row)


def _facility_row_mapper(fieldnames: tuple[str, ...]) -> Any:
    if all(column in fieldnames for column in _PROGRAM_FACILITY_REQUIRED_COLUMNS):
        return _record_from_program_facility_row
    if all(column in fieldnames for column in _CHHS_FACILITY_MASTER_REQUIRED_COLUMNS):
        return _record_from_chhs_facility_master_row
    missing_program_columns = [
        column for column in _PROGRAM_FACILITY_REQUIRED_COLUMNS if column not in fieldnames
    ]
    missing_chhs_columns = [
        column for column in _CHHS_FACILITY_MASTER_REQUIRED_COLUMNS if column not in fieldnames
    ]
    raise ValueError(
        "CCLD facility reference CSV is missing required column set. "
        "Program CSV missing: "
        + ", ".join(missing_program_columns)
        + ". CDSS/CHHS facility directory CSV missing: "
        + ", ".join(missing_chhs_columns)
        + "."
    )


def _record_from_program_facility_row(row: dict[str, str]) -> CcldFacilityLookupRecord:
    facility_number = _clean_value(row["Facility Number"])
    if not facility_number.isdigit():
        raise ValueError("CCLD facility reference facility numbers must contain digits only.")
    return CcldFacilityLookupRecord(
        facility_number=facility_number,
        facility_name=_clean_value(row["Facility Name"]),
        city=_clean_value(row["Facility City"]),
        state=_clean_value(row["Facility State"]),
        county=_clean_value(row["County Name"]),
        zip_code=_clean_value(row["Facility Zip"]),
        facility_type=_clean_value(row["Facility Type"]),
        program_type=_clean_value(row.get("Program Type", "")),
        capacity=_clean_value(row["Facility Capacity"]),
        status=_clean_value(row["Facility Status"]),
        closed_date=_clean_value(row["Closed Date"]),
        address=_clean_value(row.get("Facility Address", "")),
        regional_office=_clean_value(row.get("Regional Office", "")),
        facility_address=_raw_query_field(row, "Facility Address"),
        capacity_source_present="Facility Capacity" in row,
        closed_date_source_present="Closed Date" in row,
    )


def _record_from_chhs_facility_master_row(row: dict[str, str]) -> CcldFacilityLookupRecord:
    facility_number = _clean_value(row["FAC_NBR"])
    if not facility_number.isdigit():
        raise ValueError("CCLD facility reference facility numbers must contain digits only.")
    return CcldFacilityLookupRecord(
        facility_number=facility_number,
        facility_name=_clean_value(row["NAME"]),
        city=_clean_value(row["RES_CITY"]),
        state=_clean_value(row["RES_STATE"]),
        county=_clean_value(row["COUNTY"]),
        zip_code=_clean_value(row["RES_ZIP_CODE"]),
        facility_type=_clean_value(row["FAC_TYPE_DESC"]),
        program_type=_clean_value(row["PROGRAM_TYPE"]),
        capacity=_clean_value(row["CAPACITY"]),
        status=_clean_value(row["STATUS"]),
        closed_date="",
        address=_clean_value(row.get("RES_STREET_ADDR", "")),
        regional_office=_clean_value(row.get("FAC_DO_DESC", "")),
        fac_do_desc=_raw_query_field(row, "FAC_DO_DESC"),
        res_street_addr=_raw_query_field(row, "RES_STREET_ADDR"),
        capacity_source_present="CAPACITY" in row,
        closed_date_source_present=False,
    )


def _raw_query_field(row: Mapping[str, Any], key: str) -> str | None:
    if key not in row:
        return None
    value = row.get(key)
    return "" if value is None else str(value).strip()


def _deduplicate_facility_records(
    records: tuple[CcldFacilityLookupRecord, ...],
) -> tuple[CcldFacilityLookupRecord, ...]:
    unique_records = dict.fromkeys(records)
    return tuple(
        sorted(
            unique_records,
            key=lambda record: (
                record.facility_name,
                record.facility_number,
                record.city,
                record.state,
                record.county,
                record.zip_code,
                record.facility_type,
                record.program_type,
                record.capacity,
                record.status,
            ),
        )
    )


def _tiny_fixture_reference(
    *,
    notices: tuple[str, ...] = (),
) -> CcldFacilityReferenceSource:
    return CcldFacilityReferenceSource(
        source_kind="tiny_fixture_fallback",
        label="Tiny committed CCLD facility fixture fallback",
        path_label=DEFAULT_CCLD_FACILITY_REFERENCE_PATH.as_posix(),
        records=load_ccld_facility_reference(DEFAULT_CCLD_FACILITY_REFERENCE_PATH),
        notices=notices,
    )


def _no_reference_source(
    *,
    notices: tuple[str, ...] = (),
) -> CcldFacilityReferenceSource:
    """Return a reference source indicating no directory is configured for live mode."""
    default_notices = (
        "Facility directory lookup is not configured for this hosted environment. "
        "Enter a known CCLD Facility ID to continue. "
        "Directory lookup is optional and does not affect Request Records or review.",
    )
    return CcldFacilityReferenceSource(
        source_kind="no_reference",
        label="Facility directory lookup not configured",
        path_label="",
        records=(),
        notices=notices if notices else default_notices,
    )


def no_reference_facility_source() -> CcldFacilityReferenceSource:
    """Return a facility reference source indicating no directory is configured.

    Use in live/postgres mode when no real facility reference CSV is available
    and synthetic fixture facility data must not appear in the UI.
    """
    return _no_reference_source()


def load_active_ccld_facility_reference_live_safe(
    *,
    configured_path: str | None = None,
) -> CcldFacilityReferenceSource:
    """Load the active facility reference; return no_reference instead of tiny fixture fallback.

    Use in live/postgres mode where synthetic fixture facility data must not appear.
    When a real reference CSV is configured or available, that CSV is used as normal.
    When no real reference is available, returns no_reference instead of the tiny fixture.
    """
    source = load_active_ccld_facility_reference(configured_path=configured_path)
    if source.source_kind == "tiny_fixture_fallback":
        return _no_reference_source()
    return source


def _is_lookup_unavailable(source: CcldFacilityReferenceSource) -> bool:
    """True when no real facility directory data is loaded (no live suggestions available)."""
    return source.source_kind == "no_reference" or (
        source.source_kind
        in {
            "postgres_facility_reference",
            "postgres_source_derived",
        }
        and not source.records
        and _source_record_count(source) == 0
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
                record.state,
                record.county,
                record.zip_code,
                record.facility_type,
                record.program_type,
                record.capacity,
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
      <p id="facility-search-help">Search by Facility ID, facility name, city,
      county, ZIP code, facility type, or status when those fields are present in the
      reference list.</p>
      <form action="{CCLD_FACILITY_LOOKUP_PATH}" method="get">
        <p>
          <label for="facility_lookup_query">Facility search</label>
          <input id="facility_lookup_query" name="q" type="search"
            value="{_escape(query)}" aria-describedby="facility-search-help">
        </p>
        <p><button type="submit">Search CCLD facilities</button></p>
      </form>
    </section>"""


def _render_facility_combobox_section(
    reference_source: CcldFacilityReferenceSource,
    current_query: str,
    limited_note: str,
) -> str:
    if _is_lookup_unavailable(reference_source):
        return _render_facility_combobox_section_unavailable(current_query, limited_note)
    json_data = _build_facility_json_data(reference_source)
    suggest_url = _facility_suggest_url(reference_source)
    suggest_attr = (
        f' data-facility-suggest-url="{_escape(suggest_url)}"' if suggest_url else ""
    )
    limited_note_markup = (
        f'<p class="helper-text limited-note">{_escape(limited_note)}</p>'
        if limited_note
        else ""
    )
    selected_card = _render_facility_selected_card_html(mode="facility")
    return f"""    <section class="workflow-panel" aria-labelledby="facility-combobox-heading" id="facility-selector-wrap" data-facility-mode="facility"{suggest_attr}>
            <p class="stage-kicker">Facility lookup</p>
            <h2 id="facility-combobox-heading">Find the Facility ID</h2>
            <label for="facility-search-input">Facility</label>
            <p id="facility-search-hint" class="helper-text">Search by name, Facility ID, city, county, ZIP, or facility type.</p>
            <form action="{CCLD_FACILITY_LOOKUP_PATH}" method="get" class="facility-search-form">
                <div class="facility-combobox-outer" id="facility-combobox-outer">
                    <input id="facility-search-input" name="q" type="search" autocomplete="off"
                        placeholder="Name, Facility ID, city, or ZIP"
                        aria-describedby="facility-search-hint"
                        value="{_escape(current_query)}">
                    <ul id="facility-suggestion-list" class="facility-suggestions" aria-label="Facility suggestions" hidden></ul>
                </div>
                <div class="form-actions action-group" aria-label="Facility search actions">
                    <button type="submit">Search CCLD facilities</button>
                </div>
            </form>
            <details class="technical-details">
                <summary>When to use lookup vs. manual entry</summary>
                <p>Use facility lookup when you know a facility name, city, county, ZIP, or facility type but not the exact Facility ID. Use manual entry when you already know the digit Facility ID.</p>
                <p>Lookup rows are public facility-directory data for facility lookup assistance before Request Records.</p>
            </details>
{limited_note_markup}
{selected_card}
            <script type="application/json" id="facility-reference-json">{json_data}</script>
            <script>{_FACILITY_COMBOBOX_JS}</script>
    </section>"""


def _render_facility_combobox_section_unavailable(
    current_query: str,
    limited_note: str,
) -> str:
    """Render the facility search section when no real directory data is configured.

    Does not embed JS combobox suggestions. Shows a plain search form with a
    clear notice that directory lookup is not configured.
    """
    limited_note_markup = (
        f'<p class="helper-text limited-note">{_escape(limited_note)}</p>'
        if limited_note
        else ""
    )
    return f"""    <section class="workflow-panel" aria-labelledby="facility-combobox-heading">
            <p class="stage-kicker">Facility lookup</p>
            <h2 id="facility-combobox-heading">Find the Facility ID</h2>
            <label for="facility-search-input">Search facility directory (not configured)</label>
            <p id="facility-search-hint" class="helper-text">Enter a known CCLD Facility ID on Request Records instead. Directory lookup is optional and does not affect Request Records or review.</p>
            <form action="{CCLD_FACILITY_LOOKUP_PATH}" method="get" class="facility-search-form">
                <div>
                    <input id="facility-search-input" name="q" type="search" autocomplete="off"
                        placeholder="Facility name or number"
                        aria-describedby="facility-search-hint"
                        value="{_escape(current_query)}">
                </div>
                <div class="form-actions action-group" aria-label="Facility search actions">
                    <button type="submit" class="button-secondary">Search facility directory</button>
                </div>
            </form>
{limited_note_markup}
    </section>"""


def _render_facility_selected_card_html(*, mode: str = "facility") -> str:
    """Render the hidden selected-facility confirmation card filled by JS."""
    if mode == "request":
        actions = """<div class="form-actions action-group" aria-label="Selected facility actions">
                    <button type="submit" class="button">Confirm facility</button>
                    <button type="button" id="facility-change-btn" class="button-secondary">Change selected facility</button>
                </div>"""
    else:
        actions = f"""<form action="{CCLD_RECORD_REQUEST_PATH}" method="get" class="selected-facility-request-form" aria-describedby="selected-facility-date-help">
                    <input class="selected-facility-number-field" type="hidden" name="facility_number" value="">
                    <input class="selected-facility-origin-field" type="hidden" name="request_context_origin" value="facility_lookup">
                    <input class="selected-facility-name-field" type="hidden" name="lookup_facility_name" value="">
                    <div class="form-row">
                        <p>
                            <label for="lookup_start_date">Start date</label>
                            <input id="lookup_start_date" name="start_date" type="date" aria-describedby="selected-facility-date-help">
                        </p>
                        <p>
                            <label for="lookup_end_date">End date</label>
                            <input id="lookup_end_date" name="end_date" type="date" aria-describedby="selected-facility-date-help">
                        </p>
                    </div>
                    <p id="selected-facility-date-help" class="helper-text">Choose dates now, or leave them blank and set the date range on Request Records.</p>
                    <div class="form-actions action-group" aria-label="Selected facility actions">
                        <button type="submit" class="button">Continue to Request Records</button>
                        <button type="button" id="facility-change-btn" class="button-secondary">Change selected facility</button>
                    </div>
                </form>"""
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
    notice_markup = ""
    if source.notices:
        notice_items = "\n".join(
            f"        <li>{_escape(notice)}</li>" for notice in source.notices
        )
        notice_markup = f"""      <ul>
{notice_items}
      </ul>"""
    card_class = "notice-card" if source.source_kind == "tiny_fixture_fallback" else "summary-card"
    return f"""    <section class="{card_class}" aria-labelledby="reference-source-heading">
      <h2 id="reference-source-heading">Facility reference source</h2>
            <p id="reference-source-help">Active source: {_escape(source.label)}.</p>
      <dl aria-describedby="reference-source-help">
        <dt>Rows loaded for lookup</dt>
        <dd>{len(source.records)}</dd>
      </dl>
{notice_markup}
        <p>Reference data is lookup assistance only; use it to find a Facility ID before Request Records.</p>
        <details>
            <summary>Reference data note</summary>
            <p>Reference data is lookup assistance only and may not include every facility.</p>
            <p>Use a known Facility ID directly when the facility does not appear in lookup results.</p>
        </details>
    </section>"""


def _render_reference_details_section(source: CcldFacilityReferenceSource) -> str:
    """Collapsed reference data details section for developer/operator reference."""
    notice_markup = ""
    if source.notices:
        notice_items = "\n".join(
            f"            <li>{_escape(notice)}</li>" for notice in source.notices
        )
        notice_markup = f"""          <ul>
{notice_items}
          </ul>"""
    user_label = _user_facing_source_label(source)
    return f"""    <details class="reference-details-section">
            <summary>Reference data details</summary>
            <p>{_escape(user_label)} &mdash; {_source_record_count(source)} record(s) loaded.</p>
            <p>Reference data is lookup assistance only and may not include every facility. Use it to find a Facility ID before Request Records. Open source links from record detail when a source check is needed.</p>
{notice_markup}
            <p>If the facility does not appear here, enter a known Facility ID directly in Request Records.</p>
    </details>"""


def _render_lookup_results(result: CcldFacilityLookupResult) -> str:
    if result.empty_search:
        return ""
    if not result.returned_records:
        return f"""    <section class="empty-state-card" aria-labelledby="facility-results-heading">
      <h2 id="facility-results-heading">Facility results</h2>
        <p>No facility-directory results matched <strong>{_escape(result.query)}</strong>.</p>
        <p>Try a shorter name, Facility ID, city, county, ZIP, facility type, or program type. You can also enter
      a Facility ID directly on Request Records.</p>
    {render_action_group(secondary=(ActionItem("Open Request Records", CCLD_RECORD_REQUEST_PATH),), aria_label="No-match recovery actions")}
    </section>"""
    cards = "\n".join(
        _render_result_card(record, index=index)
        for index, record in enumerate(result.returned_records, start=1)
    )
    if result.has_more_matches:
        more_guidance = f"""      <p class="helper-text">Showing {len(result.returned_records)} of
      {result.total_match_count} matches. Refine your search to narrow the list.</p>"""
    else:
        more_guidance = f"""      <p class="helper-text">Showing {len(result.returned_records)} of
      {result.total_match_count} matching facilit{"y" if result.total_match_count == 1 else "ies"}.</p>"""
    return f"""    <section aria-labelledby="facility-results-heading">
        <h2 id="facility-results-heading">Facility results</h2>
        <p>Choose a facility to carry its Facility ID and name into Request Records. Date controls appear as soon as a facility is selected.</p>
{more_guidance}
            <div class="result-list" aria-label="Facility matches">
{cards}
            </div>
    </section>"""


def _render_result_card(record: CcldFacilityLookupRecord, *, index: int) -> str:
        request_href = _facility_request_href(record)
        hub_href = _facility_hub_href(record.facility_number)
        heading_id = f"facility-{_escape(record.facility_number)}-{index}-heading"
        return f"""        <article class="result-card" aria-labelledby="{heading_id}">
                    <div>
                        <h3 id="{heading_id}">{_escape(record.facility_name)}</h3>
                        <dl class="summary-list">
                            <dt>Facility ID</dt>
                            <dd>{_escape(record.facility_number)}</dd>
                            <dt>Facility type</dt>
                            <dd>{_escape(_display_value(record.facility_type))}</dd>
                            <dt>Location</dt>
                            <dd>{_escape(_display_value(_display_location(record)))}</dd>
                            <dt>Status</dt>
                            <dd>{_escape(_display_value(_display_facility_status_code(record.status)))}</dd>
                        </dl>
                        <details class="secondary-actions reference-details-section">
                            <summary>Directory details</summary>
                            {_render_facility_directory_details(record)}
                        </details>
                    </div>
                    <div class="form-actions action-group" aria-label="Actions for facility {_escape(record.facility_number)}">
                        <a class="button" href="{_escape(request_href)}" aria-label="Use facility {_escape(record.facility_number)} ({_escape(record.facility_name)}) in Request Records">Continue to Request Records</a>
                        <details class="secondary-actions">
                            <summary>More actions</summary>
                            <p><a href="{_escape(hub_href)}" aria-label="Open facility review hub for {_escape(record.facility_number)} ({_escape(record.facility_name)})">Open facility hub when loaded context is available</a></p>
                        </details>
                    </div>
                </article>"""


def _render_facility_directory_details(
        record: CcldFacilityLookupRecord,
        *,
        concise_labels: bool = False,
) -> str:
        labels = (
                "Facility ID",
                "Name",
                "Program type",
                "Facility type",
                "City/state/ZIP" if not concise_labels else "City / State / ZIP",
                "County",
                "Capacity",
                "Status",
                "Closed date",
        )
        return f"""<dl class="summary-list">
                <dt>{labels[0]}</dt>
                <dd>{_escape(record.facility_number)}</dd>
                <dt>{labels[1]}</dt>
                <dd>{_escape(_display_value(record.facility_name))}</dd>
                <dt>{labels[2]}</dt>
                <dd>{_escape(_display_value(record.program_type))}</dd>
                <dt>{labels[3]}</dt>
                <dd>{_escape(_display_value(record.facility_type))}</dd>
                <dt>{labels[4]}</dt>
                <dd>{_escape(_display_value(_display_location(record)))}</dd>
                <dt>{labels[5]}</dt>
                <dd>{_escape(_display_value(record.county))}</dd>
                <dt>{labels[6]}</dt>
                <dd>{_escape(_record_display_value(record, "capacity", kind="number"))}</dd>
                <dt>{labels[7]}</dt>
                <dd>{_escape(_display_value(_display_facility_status_code(record.status)))}</dd>
                <dt>{labels[8]}</dt>
                <dd>{_escape(_record_display_value(record, "closed_date", kind="date"))}</dd>
            </dl>"""


def _render_facility_identity_and_core_facts(
    record: CcldFacilityLookupRecord,
    review_context: CcldFacilityReviewContext,
) -> str:
    launch_value = (
        "Open loaded records or start a new complaint request for this facility."
        if review_context.has_loaded_context
        else "No complaint records are loaded for this facility. Choose a date range to request or show complaint records."
    )
    return f"""<section class="hero-card attorney-hero" aria-labelledby="facility-hub-heading">
      <div>
        <p class="launch-kicker">Facility</p>
        <h2 id="facility-hub-heading">{_render_copyable_value("Copy facility name", record.facility_name)}</h2>
        <p class="launch-value">{_escape(launch_value)}</p>
        <dl class="summary-list" aria-label="Primary facility facts">
          <dt>Facility ID</dt>
          <dd>{_render_copyable_value("Copy Facility ID", record.facility_number)}</dd>
          <dt>Facility type</dt>
          <dd>{_escape(_display_value(record.facility_type))}</dd>
          <dt>Status</dt>
          <dd>{_escape(_display_value(_display_facility_status_code(record.status)))}</dd>
          <dt>Address</dt>
          <dd>{_escape(_display_facility_address(record))}</dd>
          <dt>County</dt>
          <dd>{_escape(_display_value(record.county))}</dd>
          <dt>Capacity</dt>
          <dd>{_escape(_record_display_value(record, "capacity", kind="number"))}</dd>
        </dl>
      </div>
    </section>
    {_render_copy_control_script()}"""


def _render_secondary_facility_facts(record: CcldFacilityLookupRecord) -> str:
    return f"""    <details class="secondary-actions reference-details-section" id="secondary-facility-facts">
      <summary>More facility facts</summary>
      <dl class="summary-list" aria-label="Secondary facility facts">
        <dt>Program type</dt>
        <dd>{_escape(_display_value(record.program_type))}</dd>
        <dt>Regional office</dt>
        <dd>{_escape(_display_value(record.regional_office))}</dd>
        <dt>Closed date</dt>
        <dd>{_escape(_record_display_value(record, "closed_date", kind="date"))}</dd>
      </dl>
    </details>"""


def _display_facility_address(record: CcldFacilityLookupRecord) -> str:
    street_value = record.address
    street_source_present = bool(street_value)
    if not street_value and record.facility_address is not None:
        street_value = record.facility_address
        street_source_present = True
    if not street_value and record.res_street_addr is not None:
        street_value = record.res_street_addr
        street_source_present = True

    street_values = {"address": street_value} if street_source_present else {}
    presentations = (
        presentation_value_for_field(street_values, "address"),
        presentation_value(record.city),
        presentation_value(record.state),
        presentation_value(record.zip_code),
    )
    present_values = tuple(
        value.display_text
        for value in presentations
        if value.state in {"present", "verified_zero"}
    )
    if present_values:
        street_text = presentations[0].display_text if presentations[0].state == "present" else ""
        city_text = presentations[1].display_text if presentations[1].state == "present" else ""
        state_text = presentations[2].display_text if presentations[2].state == "present" else ""
        zip_text = presentations[3].display_text if presentations[3].state == "present" else ""
        state_zip = " ".join(part for part in (state_text, zip_text) if part)
        locality = ", ".join(part for part in (city_text, state_zip) if part)
        return ", ".join(part for part in (street_text, locality) if part)

    state_priority = (
        "invalid",
        "source_unavailable",
        "not_applicable",
        "null",
        "present_blank",
        "absent",
    )
    for state in state_priority:
        for value in presentations:
            if value.state == state:
                return value.display_text
    return presentation_value().display_text


def _render_copyable_value(accessible_label: str, value: str) -> str:
    if not value:
        return _escape(_display_value(value))
    return (
        f'<span class="copyable-value">{_escape(value)}'
        f'<button class="copy-icon-button" type="button" data-copy-value="{_escape(value)}" '
        f'aria-label="{_escape(accessible_label)}" title="{_escape(accessible_label)}">'
        f'{_clipboard_icon_svg()}</button>'
        '<span class="copy-feedback" data-copy-status aria-live="polite"></span></span>'
    )


def _clipboard_icon_svg() -> str:
    return (
        '<svg aria-hidden="true" viewBox="0 0 24 24" focusable="false" width="16" height="16">'
        '<path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round" d="M8 8h9a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2Z"/>'
        '<path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round" d="M4 15H3a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>'
        '</svg>'
    )


def _render_copy_control_script() -> str:
    return """<script>
(function () {
  document.querySelectorAll('[data-copy-value]').forEach(function (button) {
    button.addEventListener('click', function () {
      var status = button.parentNode.querySelector('[data-copy-status]');
      var value = button.getAttribute('data-copy-value') || '';
      if (!navigator.clipboard || !navigator.clipboard.writeText) {
        if (status) status.textContent = ' Copy unavailable';
        return;
      }
      navigator.clipboard.writeText(value).then(function () {
        if (status) status.textContent = ' Copied';
      }, function () {
        if (status) status.textContent = ' Copy unavailable';
      });
    });
  });
}());
</script>"""


def _display_facility_status_code(status: str) -> str:
        if not status:
                return ""
        if not status.isdigit():
                return status
        label = _FACILITY_STATUS_CODE_LABELS.get(status)
        if not label:
                return status
        return f"{status} ({label})"


def _render_facility_hub_not_found(facility_number: str) -> str:
        searched = facility_number if facility_number else "not provided"
        request_link = ""
        if facility_number.isdigit():
                request_link = f"""        <a class="button button-secondary" href="{_escape(_facility_request_href_for_values(facility_number=facility_number))}">Start complaint request</a>"""
        return f"""    <section class="empty-state-card" aria-labelledby="facility-hub-not-found-heading">
            <h2 id="facility-hub-not-found-heading">Facility-directory result not found</h2>
            <p>No active preloaded facility-directory row matched facility number <strong>{_escape(searched)}</strong>.</p>
            <p>Try a different search, enter the Facility ID directly, or report an issue if the lookup result is confusing.</p>
            <div class="action-group" aria-label="Facility hub recovery actions">
                <a class="button" href="{CCLD_FACILITY_LOOKUP_PATH}">Back to search</a>
                {request_link}
            </div>
        </section>"""


def _render_facility_pattern_review_summary(
        record: CcldFacilityLookupRecord,
        review_context: CcldFacilityReviewContext,
) -> str:
        request_href = _facility_request_href(record)
        queue_href = f"{REVIEWER_UI_RECORDS_PATH}?{urlencode({'q': record.facility_number})}"
        if not review_context.has_loaded_context:
                return f"""    <section class="summary-card" aria-labelledby="facility-pattern-summary-heading">
            <h2 id="facility-pattern-summary-heading">Review summary</h2>
            <p>No loaded complaint records are currently available for this facility in the review context. This is not a public-source completeness conclusion.</p>
            <dl class="summary-list">
                <dt>Loaded complaint records</dt>
                <dd>0</dd>
                <dt>CCLD source availability</dt>
                <dd>No loaded complaint record is available for source review.</dd>
                <dt>Reviewer-created status and notes</dt>
                <dd>No reviewer-created status or note summary is available without loaded records.</dd>
            </dl>
            <p><a class="button" href="{_escape(request_href)}">Request or load records for this facility</a></p>
        </section>"""
        finding_items = _render_pattern_summary_finding_items(review_context)
        status_items = _render_pattern_summary_status_items(review_context)
        review_next_text = _review_next_summary_label(review_context)
        return f"""    <section class="summary-card" aria-labelledby="facility-pattern-summary-heading">
            <h2 id="facility-pattern-summary-heading">Review summary</h2>
            <p>These ordered review signals use loaded source-derived complaint records and separate reviewer-created state. They may deserve closer review; they are not legal conclusions or source-completeness findings.</p>
            <div class="dense-fact-row" aria-label="Facility pattern review signals">
                <div class="stat-card"><strong>{review_context.loaded_complaint_record_count}</strong><span>Loaded complaint records</span></div>
                <div class="stat-card"><strong>{review_context.delay_review_record_count}</strong><span>Delay-review records</span></div>
                <div class="stat-card"><strong>{review_context.missing_date_record_count}</strong><span>Missing-date records</span></div>
            </div>
            <dl class="summary-list">
                <dt>CCLD source availability</dt>
                <dd>{review_context.source_traceability_count} of {review_context.loaded_complaint_record_count} loaded complaint record(s) have source traceability available.</dd>
                <dt>Recent complaint/report/visit activity in loaded records</dt>
                <dd>{_escape(_display_date(review_context.recent_activity_date) if review_context.recent_activity_date else _display_value(review_context.recent_activity_date))}</dd>
                <dt>Finding counts in loaded records</dt>
                <dd>
                    <ul class="flag-list">
{finding_items}
                    </ul>
                </dd>
                <dt>Reviewer-created status summary</dt>
                <dd>
                    <ul class="flag-list">
{status_items}
                    </ul>
                </dd>
                <dt>Reviewer-created note cue</dt>
                <dd>{review_context.reviewer_note_record_count} loaded record(s) have reviewer-created note rows.</dd>
                <dt>Suggested next loaded complaint</dt>
                <dd>{_escape(review_next_text)}</dd>
            </dl>
            <nav aria-label="Facility pattern review next actions">
                <ul>
                    <li><a href="{_escape(queue_href)}">Open reviewer queue filtered to this facility</a></li>
                    <li><a href="{_escape(request_href)}">Request or load records for this facility</a></li>
                </ul>
            </nav>
        </section>"""


def _render_review_next_section(
        review_context: CcldFacilityReviewContext,
) -> str:
        if not review_context.has_loaded_context or not review_context.review_next_recommendations:
                return """    <section class="empty-state-card" aria-labelledby="review-next-heading">
            <h2 id="review-next-heading">Review next</h2>
            <p>No loaded records have review-next signals in this context.</p>
            <p>This only reflects the currently loaded local/test records and does not imply source completeness or absence of problems.</p>
        </section>"""
        items = "\n".join(
                _render_review_next_item(item, index)
                for index, item in enumerate(review_context.review_next_recommendations, start=1)
        )
        return f"""    <section class="summary-card" aria-labelledby="review-next-heading">
            <h2 id="review-next-heading">Review next</h2>
            <p>Open loaded records in this suggested order when deciding what needs attorney review first. Reasons use existing source-derived values and existing reviewer-created status cues only.</p>
            <ol class="review-next-list">
{items}
            </ol>
        </section>"""


def _render_review_next_item(
        item: CcldReviewNextRecommendation,
        index: int,
) -> str:
        visible_reasons = tuple(
                reason
                for reason in item.reasons
                if reason != "Source traceability available for detail review."
        )
        reasons = "\n".join(
                f"                    <li>{_escape(reason)}</li>" for reason in visible_reasons
        )
        if not reasons:
                reasons = "                    <li>Open the record for the displayed review cues.</li>"
        return f"""                <li class="review-next-item">
                    <p><strong>{index}. {_escape(item.label)}</strong></p>
                    <dl class="summary-list">
                        <dt>Finding/status cue</dt>
                        <dd>{_escape(_display_value(item.finding_status_cue))}</dd>
                        <dt>Date shown</dt>
                        <dd>{_escape(_display_value(item.date_label))}</dd>
                        <dt>Why suggested</dt>
                        <dd>
                            <ul class="flag-list">
{reasons}
                            </ul>
                        </dd>
                    </dl>
                    <p><a href="{_escape(item.detail_href)}">Open reviewer detail for {_escape(item.label)}</a></p>
                </li>"""


def _review_next_summary_label(review_context: CcldFacilityReviewContext) -> str:
        if review_context.review_next_recommendations:
                return review_context.review_next_recommendations[0].label
        return _display_value(review_context.review_next_label)


def _render_facility_review_signals_section(
        summary: FacilityReviewSignalsSummary | None,
) -> str:
        if summary is None:
                return """    <section class="empty-state-card" aria-labelledby="facility-review-signals-heading">
            <h2 id="facility-review-signals-heading">Additional review signals</h2>
            <p>No uploaded public summary fields are available in the supported licensing/visit/citation summary inputs.</p>
            <p>This empty state does not mean the facility has no complaints, visits, citations, POC dates, or public-source records. Start a complaint request or return to facility lookup when you need a different facility context.</p>
        </section>"""
        cues = "\n".join(
                f"        <li>{_escape(_priority_filter_label(cue))}</li>" for cue in summary.review_cues
        )
        if not cues:
                cues = "        <li>No supported uploaded public summary review cue is present for this facility.</li>"
        return f"""    <section aria-labelledby="facility-review-signals-heading">
            <h2 id="facility-review-signals-heading">Additional review signals</h2>
            <p>These uploaded public summary counts and dates are planning cues only. They are separate from loaded complaint records and are not legal findings or proof of source completeness.</p>
            <div class="dense-fact-row" aria-label="Facility signal highlights">
                <div class="stat-card"><strong>{summary.complaint_visit_count}</strong><span>Complaint visits</span></div>
                <div class="stat-card"><strong>{summary.citation_count}</strong><span>Citation values</span></div>
                <div class="stat-card"><strong>{summary.poc_date_count}</strong><span>POC dates</span></div>
                <div class="stat-card"><strong>{_escape(_display_date(summary.last_visit_date))}</strong><span>Last visit date</span></div>
            </div>
            <dl class="summary-list">
                <dt>Visit activity</dt>
                <dd>{summary.total_visit_count} total; {summary.inspection_visit_count} inspection; {summary.complaint_visit_count} complaint; {summary.other_visit_count} other</dd>
                <dt>Citation indicators</dt>
                <dd>{summary.citation_count} citation value(s); {summary.type_a_citation_count} Type A value(s); {summary.type_b_citation_count} Type B value(s)</dd>
                <dt>POC date indicators</dt>
                <dd>{summary.poc_date_count}</dd>
            </dl>
            <section aria-labelledby="facility-review-cues-heading">
                <h3 id="facility-review-cues-heading">What to review next</h3>
                <ul>
{cues}
                </ul>
                <p>Use these cues to decide whether to start a complaint request, review loaded records, or return to facility lookup.</p>
            </section>
        </section>"""


def _render_pattern_summary_finding_items(
        review_context: CcldFacilityReviewContext,
) -> str:
        if not review_context.finding_counts:
                return "                        <li>Finding values not available in loaded records.</li>"
        return "\n".join(
                f"                        <li>{_escape(_display_value(label))}: {count}</li>"
                for label, count in review_context.finding_counts
        )


def _render_pattern_summary_status_items(
        review_context: CcldFacilityReviewContext,
) -> str:
        if not review_context.reviewer_status_counts:
                return "                        <li>No reviewer-created status rows are available for loaded records.</li>"
        return "\n".join(
                f"                        <li>{_escape(_reviewer_status_label(label))}: {count}</li>"
                for label, count in review_context.reviewer_status_counts
        )


def _reviewer_status_label(value: str) -> str:
        labels = {
                "not_started": "Not started",
                "in_review": "In review",
                "needs_follow_up": "Needs follow-up",
                "reviewed": "Reviewed",
                "blocked": "Blocked",
        }
        return labels.get(value, value.replace("_", " "))


_PRIORITY_CUE_ORDER = (
    "Multiple signal types present",
    "Complaint visit activity present",
    "Citation indicator present",
    "POC indicator present",
    "Recent visit activity",
    "High-capacity facility",
    "Closed status in uploaded summary",
    "Long gap since last visit",
)


def _filtered_priority_summaries(
    summaries: tuple[FacilityReviewSignalsSummary, ...],
    cue_filters: tuple[str, ...],
) -> tuple[FacilityReviewSignalsSummary, ...]:
    ordered = tuple(sorted(summaries, key=_priority_sort_key))
    active_filters = tuple(cue for cue in cue_filters if cue and cue != "all")
    if not active_filters:
        return ordered
    return tuple(
        summary
        for summary in ordered
        if any(cue in _priority_cues(summary) for cue in active_filters)
    )


def _selected_priority_cues(query_values: Mapping[str, list[str]]) -> tuple[str, ...]:
    selected = tuple(
        cue
        for cue in query_values.get("cue", [])
        if cue == "all" or cue in _PRIORITY_CUE_ORDER
    )
    return selected if selected else ("all",)


def _priority_search_query(query_values: Mapping[str, list[str]]) -> str:
    return _clean_value(_first_query_value(dict(query_values), "q"))


def _searched_priority_summaries(
    summaries: tuple[FacilityReviewSignalsSummary, ...],
    query: str,
) -> tuple[FacilityReviewSignalsSummary, ...]:
    normalized = _normalized_text(query)
    if not normalized:
        return summaries
    return tuple(
        summary
        for summary in summaries
        if normalized in _normalized_text(summary.facility_number)
        or normalized in _normalized_text(summary.facility_name)
        or any(normalized in _normalized_text(value) for value in summary.facility_types)
    )


def _priority_sort_key(summary: FacilityReviewSignalsSummary) -> tuple[Any, ...]:
    cues = _priority_cues(summary)
    cue_ranks = tuple(_PRIORITY_CUE_ORDER.index(cue) for cue in cues if cue in _PRIORITY_CUE_ORDER)
    best_rank = min(cue_ranks) if cue_ranks else len(_PRIORITY_CUE_ORDER)
    return (
        -len(cues),
        best_rank,
        -summary.complaint_visit_count,
        -summary.citation_count,
        -summary.poc_date_count,
        _reverse_date_key(summary.last_visit_date),
        summary.facility_name,
        summary.facility_number,
    )


def _priority_cues(summary: FacilityReviewSignalsSummary) -> tuple[str, ...]:
    cues = list(summary.review_cues)
    if len(cues) >= 2:
        cues.insert(0, "Multiple signal types present")
    return tuple(cues)


def _reverse_date_key(value: str) -> int:
    return -int(value.replace("-", "")) if value and value.replace("-", "").isdigit() else 0


def _render_priority_filter(active_cues: tuple[str, ...], search_query: str) -> str:
    active_set = set(active_cues or ("all",))
    cue_controls = "\n".join(
        f"""          <label class="filter-chip">
            <input type="checkbox" name="cue" value="{_escape(value)}"{_checked_attr(value in active_set)}>
            <span>{_escape(_priority_filter_label(value))}</span>
          </label>"""
        for value in ("all",) + _PRIORITY_CUE_ORDER
    )
    clear_link = (
        f'<a class="button button-quiet" href="{CCLD_FACILITY_REVIEW_PRIORITY_PATH}">Clear cues</a>'
        if active_set != {"all"}
        else ""
    )
    return f"""    <section class="workflow-panel compact-filter-panel" aria-labelledby="facility-priority-filter-heading">
      <h2 id="facility-priority-filter-heading">Filter</h2>
      <form action="{CCLD_FACILITY_REVIEW_PRIORITY_PATH}" method="get" class="compact-filter-form">
        <fieldset>
          <legend>Review cues</legend>
          <div class="filter-chip-group">
{cue_controls}
          </div>
        </fieldset>
        <p>
          <label for="priority-search">Search</label>
          <input id="priority-search" name="q" type="search" value="{_escape(search_query)}" placeholder="Facility name or license">
        </p>
        <div class="form-actions">
          <button type="submit" class="button button-secondary">Apply filters</button>
          {clear_link}
        </div>
      </form>
    </section>"""


def _render_priority_guidance_disclosure() -> str:
    return """        <details class="technical-details">
            <summary>How to use these review cues</summary>
            <p>This facility review priority list is derived from uploaded public summary fields in supported public licensing/visit/citation summary CSVs; complaint records are requested/reviewed separately.</p>
            <p>Use these cues to choose facility hubs, start complaint requests, open loaded records, and decide where source-traceability review should happen next.</p>
            <p>Open facility review hub links continue into existing request, queue, packet preview, and source-traceability review paths.</p>
        </details>"""


def _priority_filter_label(value: str) -> str:
    labels = {
        "all": "All cues",
        "Multiple signal types present": "Priority cue",
        "Complaint visit activity present": "Possible delay",
        "Citation indicator present": "Check source",
        "POC indicator present": "Check source",
        "Recent visit activity": "Check source",
        "High-capacity facility": "Priority cue",
        "Closed status in uploaded summary": "Check source",
        "Long gap since last visit": "120+ day gap",
    }
    return labels.get(value, value)


def _selected_attr(value: str, active_value: str) -> str:
    return " selected" if value == active_value else ""


def _checked_attr(value: bool) -> str:
    return " checked" if value else ""


def _render_priority_cards(
    signal_result: Any,
    active_cues: tuple[str, ...],
    search_query: str,
) -> str:
    cue_counts = {
        cue: sum(1 for summary in signal_result.summaries if cue in _priority_cues(summary))
        for cue in _PRIORITY_CUE_ORDER
    }
    card_items = tuple((cue, count) for cue, count in cue_counts.items() if count)
    if not card_items:
        return """        <section aria-labelledby="facility-priority-cards-heading">
            <h2 id="facility-priority-cards-heading">Review cue summary</h2>
            <p>No review cues are available.</p>
        </section>"""
    cards = "\n".join(
        _render_priority_card(cue, count, active_cues=active_cues, search_query=search_query)
        for cue, count in card_items
    )
    return f"""        <section aria-labelledby="facility-priority-cards-heading">
            <h2 id="facility-priority-cards-heading">Review cue summary</h2>
            <div class="card-grid priority-card-grid">
{cards}
            </div>
        </section>"""


def _render_priority_card(
    cue: str,
    count: int,
    *,
    active_cues: tuple[str, ...],
    search_query: str,
) -> str:
    query_values: dict[str, str] = {"cue": cue}
    if search_query:
        query_values["q"] = search_query
    active_class = " is-active" if cue in active_cues else ""
    return f"""                <article class="summary-card priority-summary-card">
                    <h3><a class="{active_class.strip()}" href="{CCLD_FACILITY_REVIEW_PRIORITY_PATH}?{_escape(urlencode(query_values))}">{_escape(_priority_filter_label(cue))}</a></h3>
                    <p><strong>{count}</strong> facilit{"y" if count == 1 else "ies"}</p>
                </article>"""


def _render_priority_summary(
    signal_result: Any,
    summaries: tuple[FacilityReviewSignalsSummary, ...],
    returned_summaries: tuple[FacilityReviewSignalsSummary, ...],
) -> str:
    cue_counts = {
        cue: sum(1 for summary in signal_result.summaries if cue in _priority_cues(summary))
        for cue in _PRIORITY_CUE_ORDER
    }
    cue_rows = "\n".join(
        f"        <dt>{_escape(_priority_filter_label(cue))}</dt><dd>{count}</dd>"
        for cue, count in cue_counts.items()
        if count
    )
    if not cue_rows:
        cue_rows = "        <dt>Review cue groups</dt><dd>No uploaded summary review cues available</dd>"
    return f"""    <section aria-labelledby="facility-priority-summary-heading">
      <div class="dense-section-header">
        <div>
          <p class="stage-kicker">Facility review priority</p>
          <h2 id="facility-priority-summary-heading">Priority list summary</h2>
        </div>
        <p class="helper-text">Use the cue counts to pick a facility hub, then request complaint records for the intended date range.</p>
      </div>
      <dl class="summary-list">
        <dt>Facilities with supported uploaded summary signals</dt>
        <dd>{len(signal_result.summaries)}</dd>
        <dt>Facilities shown under current filter</dt>
        <dd>{len(returned_summaries)} of {len(summaries)} matching facilit{"y" if len(summaries) == 1 else "ies"}</dd>
        <dt>Supported summary CSV sources loaded</dt>
        <dd>{signal_result.loaded_source_count}</dd>
        <dt>Unsupported summary CSV sources skipped</dt>
        <dd>{signal_result.unsupported_source_count}</dd>
        <dt>Malformed or shifted rows skipped</dt>
        <dd>{signal_result.skipped_malformed_row_count}</dd>
{cue_rows}
      </dl>
    </section>"""


def _render_priority_empty_rows(cue_filters: tuple[str, ...]) -> str:
    active_filters = tuple(cue for cue in cue_filters if cue and cue != "all")
    filter_text = (
        " for selected review cues"
        if active_filters
        else ""
    )
    return f"""          <tr>
            <td colspan="4">
              <p>No facility review priority rows are available{filter_text}.</p>
              <p>Optional planning views provide supplemental facility-review context when available. They are not required for Request Records or review.</p>
              <p>This does not mean facilities have no complaints, visits, citations, POC dates, or public-source records. It only means supported uploaded public summary fields did not produce a visible row for this view.</p>
              <p><a href="{CCLD_FACILITY_LOOKUP_PATH}">Back to search to find a facility and retrieve complaint records.</a></p>
            </td>
          </tr>"""


def _render_priority_row(summary: FacilityReviewSignalsSummary) -> str:
    cues = _priority_cues(summary)
    cue_text = "; ".join(_priority_filter_label(cue) for cue in cues) if cues else "No uploaded summary signals available"
    field_text = (
        f"{summary.total_visit_count} total visits; {summary.complaint_visit_count} complaint visits; "
        f"{summary.citation_count} citation value(s); {summary.poc_date_count} POC date(s); "
        f"last visit {_display_date(summary.last_visit_date)}; status {_display_tuple(summary.statuses)}; "
        f"capacity {_display_tuple(summary.capacities, kind='number')}"
    )
    facility_label = _safe_priority_text(summary.facility_name or summary.facility_number)
    return f"""          <tr>
            <th scope="row">
              {_escape(facility_label)}<br>
              <span class="helper-text">Facility ID {_escape(summary.facility_number)}</span>
            </th>
            <td>{_escape(cue_text)}</td>
            <td>{_escape(_safe_priority_text(field_text))}</td>
            <td><a href="{_escape(_facility_hub_href(summary.facility_number))}">Open facility review hub for {_escape(summary.facility_number)}</a></td>
          </tr>"""


def _safe_priority_text(value: str) -> str:
    lowered = value.casefold()
    if any(marker in lowered for marker in _SECRET_HTML_MARKERS):
        return "review label hidden"
    return value


def _render_facility_hub_actions(
        record: CcldFacilityLookupRecord,
        review_context: CcldFacilityReviewContext,
) -> str:
        request_href = _facility_request_href(record)
        lookup_href = f"{CCLD_FACILITY_LOOKUP_PATH}?{urlencode({'q': record.facility_number})}"
        if review_context.has_loaded_context and review_context.has_date_context:
                queue_query = {
                        "facility_number": record.facility_number,
                        "start_date": review_context.start_date,
                        "end_date": review_context.end_date,
                        "request_context_origin": "facility_lookup",
                        "lookup_facility_name": record.facility_name,
                }
                return f"""    <section aria-labelledby="facility-hub-actions-heading">
            <h2 id="facility-hub-actions-heading">Next actions</h2>
            <form action="{CCLD_RECORD_REQUEST_PATH}" method="post" class="action-group" aria-label="Facility review hub actions">
                        <input type="hidden" name="facility_number" value="{_escape(record.facility_number)}">
                        <input type="hidden" name="record_type" value="complaints">
                        <input type="hidden" name="start_date" value="{_escape(review_context.start_date)}">
                        <input type="hidden" name="end_date" value="{_escape(review_context.end_date)}">
                        <input type="hidden" name="request_context_origin" value="facility_lookup">
                        <input type="hidden" name="lookup_facility_name" value="{_escape(record.facility_name)}">
                        <button type="submit" class="button">Open loaded records</button>
                        <a class="button button-secondary" href="{_escape(request_href)}">Start complaint request</a>
                        <a class="button button-secondary" href="{_escape(lookup_href)}">Back to search</a>
                    </form>
            <details class="technical-details dense-table-details">
                <summary>Packet and export actions</summary>
                <div class="action-group" aria-label="Facility packet and export actions">
                    <a class="button button-secondary" href="{REVIEWER_UI_RECORDS_PATH}?{_escape(urlencode({'q': record.facility_number}))}">Open reviewer queue filtered to this facility</a>
                    <a class="button button-secondary" href="{REVIEWER_UI_MATRIX_EXPORT_PATH}?{_escape(urlencode(queue_query))}">Download complaint review matrix CSV</a>
                    <a class="button button-secondary" href="{REVIEWER_UI_PACKET_PREVIEW_PATH}?{_escape(urlencode(queue_query))}">Packet preview</a>
                    <a class="button button-secondary" href="{REVIEWER_UI_PACKET_DRAFT_PATH}?{_escape(urlencode(queue_query))}">Packet draft</a>
                </div>
            </details>
        </section>"""
        elif review_context.has_loaded_context:
                return f"""    <section aria-labelledby="facility-hub-actions-heading">
            <h2 id="facility-hub-actions-heading">Next actions</h2>
            {render_action_group(
                primary=ActionItem("Start complaint request", request_href),
                secondary=(ActionItem("Back to search", lookup_href),),
                aria_label="Facility review hub actions",
            )}
            <p class="helper-text">Date range needed before loaded records can be scoped.</p>
        </section>"""
        return f"""    <section aria-labelledby="facility-hub-actions-heading">
            <h2 id="facility-hub-actions-heading">Next actions</h2>
            {render_action_group(
                primary=ActionItem("Start complaint request", request_href),
                secondary=(ActionItem("Back to search", lookup_href),),
                aria_label="Facility review hub actions",
            )}
        </section>"""


def _facility_request_href(record: CcldFacilityLookupRecord) -> str:
        return _facility_request_href_for_values(
                facility_number=record.facility_number,
                facility_name=record.facility_name,
        )


def _facility_request_href_for_values(
        *,
        facility_number: str,
        facility_name: str = "",
) -> str:
        query_values = {
                "facility_number": facility_number,
                "request_context_origin": "facility_lookup",
                "lookup_facility_name": facility_name,
        }
        return f"{CCLD_RECORD_REQUEST_PATH}?{urlencode(query_values)}"


def _facility_hub_href(facility_number: str) -> str:
        return f"{CCLD_FACILITY_REVIEW_HUB_PATH}?{urlencode({'facility_number': facility_number})}"


def _display_location(record: CcldFacilityLookupRecord) -> str:
    city_state = ", ".join(part for part in (record.city, record.state) if part)
    return " ".join(part for part in (city_state, record.zip_code) if part)


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


def _page(
    *,
    title: str,
    heading: str,
    main: str,
    active_path: str = CCLD_FACILITY_LOOKUP_PATH,
) -> str:
        return render_page_shell(
                title=title,
                heading=heading,
                main=main,
                skip_label="Skip to main CCLD facility lookup content",
                nav_label="CCLD facility navigation",
                active_path=active_path,
                step_id="start" if active_path == "/" else "facility",
                next_action="Find a facility",
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
    return presentation_value(value).display_text


def _record_display_value(
    record: CcldFacilityLookupRecord,
    field_name: str,
    *,
    kind: PresentationValueKind,
) -> str:
    source_present = getattr(record, f"{field_name}_source_present", None)
    raw_value = getattr(record, field_name)
    if source_present is not False and isinstance(raw_value, str) and ";" in raw_value:
        return "; ".join(
            presentation_value(value.strip(), kind=kind).display_text
            for value in raw_value.split(";")
        )
    values = {} if source_present is False else {field_name: raw_value}
    return presentation_value_for_field(values, field_name, kind=kind).display_text


def _display_date(value: str) -> str:
    return presentation_value(value, kind="date").display_text


def _display_tuple(
    values: tuple[str, ...],
    *,
    kind: PresentationValueKind = "text",
) -> str:
    if not values:
        return presentation_value().display_text
    return "; ".join(presentation_value(value, kind=kind).display_text for value in values)


def _user_facing_source_label(source: CcldFacilityReferenceSource) -> str:
    """Return a clean, user-facing label for the reference source (no internal paths/jargon)."""
    if source.source_kind == "no_reference":
        return "Facility directory lookup not configured"
    if source.source_kind == "tiny_fixture_fallback":
        return "Limited reference list"
    return "Facility reference list"


def _limited_reference_note(source: CcldFacilityReferenceSource) -> str:
    """Return a concise limited-reference note when only the tiny fallback is loaded."""
    if source.source_kind == "no_reference":
        return (
            "Facility directory lookup is not configured for this hosted environment. "
            "Enter a known CCLD Facility ID to continue."
        )
    if (
        source.source_kind
        in {
            "postgres_facility_reference",
            "postgres_source_derived",
        }
        and not source.records
        and _source_record_count(source) == 0
    ):
        return (
            "Facility directory lookup is not configured for this hosted environment. "
            "Enter a known CCLD Facility ID to continue."
        )
    if source.source_kind == "tiny_fixture_fallback" or _source_record_count(source) <= 2:
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
            "state": record.state,
            "co": record.county,
            "zip": record.zip_code,
            "t": record.facility_type,
            "p": record.program_type,
            "cap": record.capacity,
            "s": record.status,
        }
        for record in source.records[:limit]
    ]
    raw = json.dumps(records, ensure_ascii=True)
    # Prevent </script> injection in the embedded JSON block
    return raw.replace("</", "<\\/")


def _source_record_count(source: CcldFacilityReferenceSource) -> int:
    if source.record_count is not None:
        return source.record_count
    return len(source.records)


def _facility_suggest_url(source: CcldFacilityReferenceSource) -> str:
    if source.source_kind == "postgres_facility_reference":
        return CCLD_FACILITY_SUGGESTIONS_PATH
    return ""


def _facility_suggestions_payload(
    query: str,
    reference_source: CcldFacilityReferenceSource | None,
    *,
    lookup_result: CcldFacilityLookupResult | None = None,
) -> dict[str, Any]:
    reference_source = reference_source or load_active_ccld_facility_reference()
    result = lookup_result or search_ccld_facilities(
        query,
        reference_source.records,
        reference_source=reference_source,
    )
    return {
        "query": result.query,
        "total_match_count": result.total_match_count,
        "result_limit": result.result_limit,
        "records": _facility_json_records(result.returned_records),
    }


def _facility_json_records(
    records: Iterable[CcldFacilityLookupRecord],
) -> list[dict[str, str | None]]:
    return [
        {
            "num": record.facility_number,
            "n": record.facility_name,
            "city": record.city,
            "state": record.state,
            "co": record.county,
            "zip": record.zip_code,
            "t": record.facility_type,
            "p": record.program_type,
            "cap": record.capacity,
            "s": record.status,
            "address": record.address,
            "regional_office": record.regional_office,
        }
        for record in records
    ]


def _json_response(status: int, payload: Mapping[str, Any]) -> tuple[int, str, bytes]:
    return (
        status,
        "application/json; charset=utf-8",
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8"),
    )


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
