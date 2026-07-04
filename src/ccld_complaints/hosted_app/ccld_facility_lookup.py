# ruff: noqa: E501

from __future__ import annotations

import csv
import html
import json
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from ccld_complaints.hosted_app.facility_review_signals import (
    FacilityReviewSignalsSummary,
    load_active_facility_review_signals,
)
from ccld_complaints.hosted_app.ui_shell import render_page_shell

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
PRELOADED_FACILITY_DIRECTORY_EXAMPLE_NUMBER = "434417302"
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
  si.placeholder='Name, license number, city, or ZIP';
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
        +' <span class="suggestion-badge">Facility '+esc(f.num)+'</span>'
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
        return _html_response(200, render_ccld_facility_review_intelligence_page(query_values, reference_source))
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
            "Facility directory lookup is not configured for this hosted environment. "
            "Enter a known CCLD facility/license number to continue. "
            "Directory lookup is optional and does not affect Request Records or review."
        )
        primary_action_section = f"""    <section class="workflow-panel" aria-labelledby="facility-manual-entry-primary-heading">
      <h2 id="facility-manual-entry-primary-heading">Enter a facility/license number directly</h2>
      <p>Facility directory lookup is not configured. Enter a known CCLD facility/license number on Request Records.</p>
      <p>Use manual entry when lookup is unavailable; complaint record requests still start from Request Records.</p>
      <p><a class="button" href="{CCLD_RECORD_REQUEST_PATH}">Open Request Records</a></p>
    </section>"""
        lookup_section_label = "Facility directory search (not configured)"
        lookup_section_intro = f"""    <section class="quiet-section" aria-labelledby="facility-start-guidance-heading">
      <h2 id="facility-start-guidance-heading">{_escape(lookup_section_label)}</h2>
      <p>Facility directory lookup is not configured for this hosted environment. Use Request Records to enter a known facility/license number directly.</p>
      <p>Lookup rows are public facility-directory data for finding the facility/license number before Request Records.</p>
    </section>"""
    else:
        hero_value = (
            "Start review by finding the CCLD facility/license number in the preloaded facility directory, "
            "then carry that selected facility into the request page to choose a complaint date range."
        )
        primary_action_section = ""
        lookup_section_intro = f"""    <section class="quiet-section" aria-labelledby="facility-start-guidance-heading">
      <h2 id="facility-start-guidance-heading">Facility lookup start</h2>
            <p>Try a preloaded facility-directory example: <a href="{_escape(_facility_hub_href(PRELOADED_FACILITY_DIRECTORY_EXAMPLE_NUMBER))}">open facility review hub for known loaded facility {PRELOADED_FACILITY_DIRECTORY_EXAMPLE_NUMBER}</a>.</p>
    </section>"""
    manual_entry_section = "" if lookup_unavailable else f"""    <details class="technical-details">
      <summary id="manual-entry-heading">Enter a facility/license number directly</summary>
      <p>If you already know the CCLD facility/license number, type it on Request Records.</p>
      <p><a class="button-quiet" href="{CCLD_RECORD_REQUEST_PATH}">Open Request Records</a></p>
    </details>"""
    return _page(
        title="Find CCLD facility",
        heading="Find a facility",
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
    {_render_lookup_results(result)}
        <section class="quiet-section" aria-labelledby="facility-priority-link-heading">
            <h2 id="facility-priority-link-heading">Optional: review-priority and intelligence</h2>
            <p>These views require uploaded public summary CSVs. They are not required for Request Records or review.</p>
            <details>
                <summary>Open optional review-priority or intelligence views</summary>
                <p><a class="button button-secondary" href="{CCLD_FACILITY_REVIEW_PRIORITY_PATH}">Facility review priority list</a></p>
                <p><a class="button button-secondary" href="{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}">Facility review intelligence</a></p>
            </details>
        </section>
    {_render_reference_details_section(reference_source)}
{manual_entry_section}""",
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
    duplicate_note = ""
    if len(matching_records) > 1:
        duplicate_note = f"""      <p class="helper-text">This directory has {len(matching_records)} distinct rows with this facility number. The hub shows the first deterministic directory row for review navigation only.</p>"""
    return _page(
        title=f"Facility review hub {record.facility_number}",
        heading="Facility review hub",
        main=f"""    <section class="hero-card attorney-hero" aria-labelledby="facility-hub-heading">
      <div>
        <p class="launch-kicker">Facility-directory context</p>
        <h2 id="facility-hub-heading">{_escape(record.facility_name)}</h2>
        <p class="launch-value">Use this facility-centered hub to move from directory discovery into the existing complaint request and review routes for facility {_escape(record.facility_number)}.</p>
        <dl class="summary-list">
          <dt>Facility/license number</dt>
          <dd>{_escape(record.facility_number)}</dd>
          <dt>Facility type</dt>
          <dd>{_escape(_display_value(record.facility_type))}</dd>
          <dt>Location</dt>
          <dd>{_escape(_display_value(_display_location(record)))}</dd>
          <dt>Status</dt>
          <dd>{_escape(_display_value(_display_facility_status_code(record.status)))}</dd>
        </dl>
      </div>
    </section>
    {_render_facility_pattern_review_summary(record, review_context, signals_summary)}
    {_render_review_next_section(review_context)}
    {_render_packet_readiness_section(record, review_context)}
    <section aria-labelledby="facility-directory-details-heading">
      <h2 id="facility-directory-details-heading">Facility-directory details</h2>
      <p>These fields come from the active preloaded facility directory. Complaint records are requested and reviewed separately. Open source links from record detail when a source check is needed.</p>
{duplicate_note}
      {_render_facility_directory_details(record, concise_labels=True)}
    </section>
    {_render_facility_review_signals_section(record, signals_summary)}
    {_render_facility_hub_review_context(record, review_context)}
    {_render_facility_hub_actions(record, review_context)}
    <section aria-labelledby="facility-hub-review-actions-heading">
      <h2 id="facility-hub-review-actions-heading">Facility hub review actions</h2>
      <p>Use this hub to start a complaint request, open loaded review records, prepare a packet, or return to lookup.</p>
      <p>Opening this page leaves source-derived records and reviewer-created notes/statuses unchanged.</p>
    </section>""",
    )


def _render_signal_only_facility_hub_page(
    summary: FacilityReviewSignalsSummary,
    *,
    review_context: CcldFacilityReviewContext,
) -> str:
    record = _facility_record_from_signal_summary(summary)
    facility_label = _safe_priority_text(summary.facility_name or summary.facility_number)
    return _page(
    title=f"Signal-only facility hub {summary.facility_number}",
    heading="Facility review hub",
    main=f"""    <section class="hero-card attorney-hero" aria-labelledby="signal-only-facility-hub-heading">
            <div>
                <p class="launch-kicker">signal-only facility hub</p>
                <h2 id="signal-only-facility-hub-heading">{_escape(facility_label)}</h2>
                <p class="launch-value">Facility-directory record not available. Showing uploaded public summary fields for facility {_escape(summary.facility_number)}.</p>
            </div>
        </section>
        <section aria-labelledby="signal-only-context-heading">
            <h2 id="signal-only-context-heading">Facility-directory record not available</h2>
            <p>Showing uploaded public summary fields because the active preloaded facility-directory data does not currently include this facility number.</p>
            <p>Use the uploaded summary fields to decide whether to start a complaint request, then review complaint records separately.</p>
        </section>
        {_render_facility_pattern_review_summary(record, review_context, summary)}
        {_render_review_next_section(review_context)}
        {_render_packet_readiness_section(record, review_context)}
        {_render_facility_review_signals_section(record, summary)}
        {_render_facility_hub_review_context(record, review_context)}
        {_render_facility_hub_actions(record, review_context)}
        <section aria-labelledby="signal-only-actions-heading">
            <h2 id="signal-only-actions-heading">Signal-only hub actions</h2>
            <p>Opening this page keeps source-derived records and reviewer-created notes/statuses unchanged.</p>
            <p>Use the request links when this facility/date context is ready for complaint review.</p>
        </section>""",
    )


def _facility_record_from_signal_summary(
    summary: FacilityReviewSignalsSummary,
) -> CcldFacilityLookupRecord:
    return CcldFacilityLookupRecord(
    facility_number=summary.facility_number,
    facility_name=summary.facility_name or summary.facility_number,
    city="",
    state="",
    county=_display_tuple(summary.counties),
    zip_code="",
    facility_type=_display_tuple(summary.facility_types),
    program_type="",
    capacity=_display_tuple(summary.capacities),
    status=_display_tuple(summary.statuses),
    closed_date=_display_tuple(summary.closed_dates),
    )


def render_ccld_facility_review_priority_page(
        query_values: dict[str, list[str]] | None = None,
) -> str:
        query_values = query_values or {}
        signal_result = load_active_facility_review_signals()
        cue_filter = _first_query_value(query_values, "cue")
        summaries = _filtered_priority_summaries(signal_result.summaries, cue_filter)
        returned_summaries = summaries[:MAX_FACILITY_PRIORITY_RESULTS]
        rows = "\n".join(_render_priority_row(summary) for summary in returned_summaries)
        if not rows:
                rows = _render_priority_empty_rows(cue_filter)
        return _page(
                title="Facility review priority",
                heading="Facility review priority",
                main=f"""    <section class="hero-card attorney-hero" aria-labelledby="facility-priority-heading">
            <div>
                <p class="launch-kicker">Facility review priority</p>
                <h2 id="facility-priority-heading">Which facilities should I review first?</h2>
                <p class="launch-value">Use transparent review cue groups from uploaded public summary fields to choose which facility review hub to open next.</p>
            </div>
        </section>
        {_render_priority_filter(cue_filter)}
        {_render_priority_summary(signal_result, summaries, returned_summaries)}
        <section aria-labelledby="facility-priority-list-heading">
            <h2 id="facility-priority-list-heading">Facilities grouped by review cue priority</h2>
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


def render_ccld_facility_review_intelligence_page(
    query_values: dict[str, list[str]] | None = None,
    reference_source: CcldFacilityReferenceSource | None = None,
) -> str:
    query_values = query_values or {}
    reference_source = reference_source or load_active_ccld_facility_reference()
    signal_result = load_active_facility_review_signals()
    cue_filter = _first_query_value(query_values, "cue") or "all"
    county_filter = _first_query_value(query_values, "county") or "all"
    status_filter = _first_query_value(query_values, "status") or "all"
    sort_value = _first_query_value(query_values, "sort") or "priority"
    summaries = _intelligence_filtered_summaries(
        signal_result.summaries,
        cue_filter=cue_filter,
        county_filter=county_filter,
        status_filter=status_filter,
        sort_value=sort_value,
    )
    rows = "\n".join(
        _render_intelligence_row(summary, reference_source)
        for summary in summaries[:MAX_FACILITY_PRIORITY_RESULTS]
    )
    if not rows:
        rows = _render_intelligence_empty_rows(cue_filter, county_filter, status_filter)
    return _page(
        title="Facility review intelligence",
        heading="Facility review intelligence",
        main=f"""    <section class="hero-card attorney-hero" aria-labelledby="facility-intelligence-heading">
      <div>
        <p class="launch-kicker">Facility review intelligence</p>
        <h2 id="facility-intelligence-heading">Where should reviewers spend time first?</h2>
        <p class="launch-value">Use transparent review-priority indicators from existing public facility-directory and uploaded public summary fields to choose a facility hub, complaint request, or review queue.</p>
      </div>
    </section>
    {_render_intelligence_filters(signal_result.summaries, cue_filter, county_filter, status_filter, sort_value)}
    {_render_intelligence_summary(signal_result, summaries)}
    <section aria-labelledby="facility-intelligence-table-heading">
      <h2 id="facility-intelligence-table-heading">Facilities by review-priority indicator</h2>
      <table>
        <caption>Facility review intelligence from public summary fields</caption>
        <thead>
          <tr>
            <th scope="col">Facility</th>
            <th scope="col">Why this facility appears</th>
            <th scope="col">Public summary fields</th>
            <th scope="col">Navigation</th>
          </tr>
        </thead>
        <tbody>
{rows}
        </tbody>
      </table>
    </section>
    {_render_intelligence_guidance_disclosure()}""",
    )


def _intelligence_filtered_summaries(
    summaries: tuple[FacilityReviewSignalsSummary, ...],
    *,
    cue_filter: str,
    county_filter: str,
    status_filter: str,
    sort_value: str,
) -> tuple[FacilityReviewSignalsSummary, ...]:
    filtered = [
        summary
        for summary in summaries
        if _intelligence_filter_matches(summary, cue_filter, county_filter, status_filter)
    ]
    return tuple(sorted(filtered, key=lambda summary: _intelligence_sort_key(summary, sort_value)))


def _intelligence_filter_matches(
    summary: FacilityReviewSignalsSummary,
    cue_filter: str,
    county_filter: str,
    status_filter: str,
) -> bool:
    if cue_filter not in {"", "all"} and cue_filter not in _priority_cues(summary):
        return False
    if county_filter not in {"", "all"} and county_filter not in summary.counties:
        return False
    if status_filter not in {"", "all"} and status_filter not in summary.statuses:
        return False
    return True


def _intelligence_sort_key(
    summary: FacilityReviewSignalsSummary,
    sort_value: str,
) -> tuple[Any, ...]:
    if sort_value == "complaint_activity":
        return (-summary.complaint_visit_count, summary.facility_name, summary.facility_number)
    if sort_value == "citation_activity":
        return (-summary.citation_count, -summary.type_a_citation_count, -summary.type_b_citation_count, summary.facility_name, summary.facility_number)
    if sort_value == "poc_activity":
        return (-summary.poc_date_count, summary.facility_name, summary.facility_number)
    if sort_value == "recent_visit":
        return (_reverse_date_key(summary.last_visit_date), summary.facility_name, summary.facility_number)
    if sort_value == "capacity":
        return (-_max_int(summary.capacities), summary.facility_name, summary.facility_number)
    if sort_value == "facility_name":
        return (summary.facility_name, summary.facility_number)
    return _priority_sort_key(summary)


def _render_intelligence_filters(
    summaries: tuple[FacilityReviewSignalsSummary, ...],
    cue_filter: str,
    county_filter: str,
    status_filter: str,
    sort_value: str,
) -> str:
    cue_options = ("all",) + _PRIORITY_CUE_ORDER
    county_options = ("all",) + _unique_values(value for summary in summaries for value in summary.counties)
    status_options = ("all",) + _unique_values(value for summary in summaries for value in summary.statuses)
    sort_options = (
        ("priority", "Review-priority indicators"),
        ("complaint_activity", "Complaint activity"),
        ("citation_activity", "Citation activity"),
        ("poc_activity", "POC activity"),
        ("recent_visit", "Recent visit activity"),
        ("capacity", "High capacity"),
        ("facility_name", "Facility name"),
    )
    cue_markup = _select_options(cue_options, cue_filter, labeler=_priority_filter_label)
    county_markup = _select_options(county_options, county_filter, labeler=_identity_label)
    status_markup = _select_options(status_options, status_filter, labeler=_identity_label)
    sort_markup = "\n".join(
        f'          <option value="{_escape(value)}"{_selected_attr(value, sort_value)}>{_escape(label)}</option>'
        for value, label in sort_options
    )
    return f"""    <section class="workflow-panel" aria-labelledby="facility-intelligence-filters-heading">
      <h2 id="facility-intelligence-filters-heading">Filter and sort review cues</h2>
      <form action="{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}" method="get">
        <div class="facility-intelligence-filter-grid">
          <p>
            <label for="intelligence-cue-filter">Indicator</label>
            <select id="intelligence-cue-filter" name="cue">{cue_markup}</select>
          </p>
          <p>
            <label for="intelligence-county-filter">County</label>
            <select id="intelligence-county-filter" name="county">{county_markup}</select>
          </p>
          <p>
            <label for="intelligence-status-filter">Facility status</label>
            <select id="intelligence-status-filter" name="status">{status_markup}</select>
          </p>
          <p>
            <label for="intelligence-sort">Sort by</label>
            <select id="intelligence-sort" name="sort">{sort_markup}</select>
          </p>
        </div>
        <p class="helper-text">Filters use existing public summary fields as transparent grouping controls for review planning.</p>
        <p><button type="submit">Apply intelligence filters</button></p>
      </form>
    </section>"""


def _render_intelligence_guidance_disclosure() -> str:
    return """    <details class="technical-details">
      <summary>How to use these indicators</summary>
      <p>This view uses existing public facility-directory fields and supported uploaded public licensing/visit/citation summary fields for review planning.</p>
      <p>Use indicators to choose a facility hub, start a complaint request, inspect loaded records, and decide what feedback or packet preparation may be useful.</p>
    </details>"""


def _select_options(
    values: tuple[str, ...],
    active_value: str,
    *,
    labeler: Any,
) -> str:
    return "\n".join(
        f'          <option value="{_escape(value)}"{_selected_attr(value, active_value)}>{_escape(labeler(value))}</option>'
        for value in values
    )


def _identity_label(value: str) -> str:
    return "All" if value == "all" else value


def _unique_values(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if value}))


def _render_intelligence_summary(
    signal_result: Any,
    summaries: tuple[FacilityReviewSignalsSummary, ...],
) -> str:
    cue_counts = {
        cue: sum(1 for summary in signal_result.summaries if cue in _priority_cues(summary))
        for cue in _PRIORITY_CUE_ORDER
    }
    return f"""    <section aria-labelledby="facility-intelligence-summary-heading">
      <h2 id="facility-intelligence-summary-heading">Review intelligence summary</h2>
      <dl class="summary-list">
        <dt>Facilities with supported uploaded summary signals</dt>
        <dd>{len(signal_result.summaries)}</dd>
        <dt>Facilities shown after filters</dt>
        <dd>{len(summaries)}</dd>
        <dt>Facilities with complaint activity</dt>
        <dd>{cue_counts['Complaint visit activity present']}</dd>
        <dt>Facilities with citation activity</dt>
        <dd>{cue_counts['Citation indicator present']}</dd>
        <dt>Facilities with POC activity</dt>
        <dd>{cue_counts['POC indicator present']}</dd>
        <dt>Facilities with recent visit activity</dt>
        <dd>{cue_counts['Recent visit activity']}</dd>
        <dt>Facilities with long periods since last visit</dt>
        <dd>{cue_counts['Long gap since last visit']}</dd>
        <dt>High-capacity facilities</dt>
        <dd>{cue_counts['High-capacity facility']}</dd>
        <dt>Closed facilities</dt>
        <dd>{cue_counts['Closed status in uploaded summary']}</dd>
      </dl>
    </section>"""


def _render_intelligence_empty_rows(
    cue_filter: str,
    county_filter: str,
    status_filter: str,
) -> str:
    filter_text = "; ".join(
        part
        for part in (
            f"indicator {cue_filter}" if cue_filter not in {"", "all"} else "",
            f"county {county_filter}" if county_filter not in {"", "all"} else "",
            f"status {status_filter}" if status_filter not in {"", "all"} else "",
        )
        if part
    ) or "current filters"
    return f"""          <tr>
            <td colspan="4">
              <p>No facility review intelligence rows are available for {_escape(filter_text)}.</p>
              <p>This does not mean facilities have no complaints, visits, citations, POC dates, or public-source records. It only means supported uploaded public summary fields did not produce a visible row for this view.</p>
            </td>
          </tr>"""


def _render_intelligence_row(
    summary: FacilityReviewSignalsSummary,
    reference_source: CcldFacilityReferenceSource,
) -> str:
    cues = _priority_cues(summary)
    cue_items = "\n".join(
        f"                <li>{_escape(cue)} review cue</li>"
        for cue in cues
    ) or "                <li>No review cue available from supported summary fields</li>"
    context_label = _facility_context_label(summary.facility_number, reference_source)
    field_text = (
        f"{summary.total_visit_count} total visits; {summary.complaint_visit_count} complaint visits; "
        f"{summary.citation_count} citation value(s); {summary.poc_date_count} POC date(s); "
        f"last visit {_display_value(summary.last_visit_date)}; status {_display_tuple(summary.statuses)}; "
        f"capacity {_display_tuple(summary.capacities)}; county {_display_tuple(summary.counties)}"
    )
    facility_label = _safe_priority_text(summary.facility_name or summary.facility_number)
    request_href = _facility_request_href_for_values(
        facility_number=summary.facility_number,
        facility_name=facility_label,
    )
    queue_href = f"{REVIEWER_UI_RECORDS_PATH}?{urlencode({'q': summary.facility_number})}"
    return f"""          <tr>
            <th scope="row">
              {_escape(facility_label)}<br>
              <span class="helper-text">Facility/license {_escape(summary.facility_number)}; {_escape(context_label)}</span>
            </th>
            <td>
              <ul>
{cue_items}
              </ul>
            </td>
            <td>{_escape(_safe_priority_text(field_text))}</td>
            <td>
              <ul>
                <li><a href="{_escape(_facility_hub_href(summary.facility_number))}">Open Facility Review Hub for {_escape(summary.facility_number)}</a></li>
                <li><a href="{_escape(request_href)}">Start Complaint Request for {_escape(summary.facility_number)}</a></li>
                <li><a href="{_escape(queue_href)}">Open Review Queue filtered to {_escape(summary.facility_number)}</a></li>
              </ul>
            </td>
          </tr>"""


def _facility_context_label(
    facility_number: str,
    reference_source: CcldFacilityReferenceSource,
) -> str:
    if any(record.facility_number == facility_number for record in reference_source.records):
        return "directory-backed facility hub available"
    return "signal-only facility hub when summary signals are available"


def _max_int(values: tuple[str, ...]) -> int:
    parsed = [_safe_int(value) for value in values]
    return max(parsed) if parsed else 0


def _safe_int(value: str) -> int:
    cleaned = _clean_value(value)
    return int(cleaned) if cleaned.isdigit() else 0


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
            "facility directory rows. Enter a facility/license number directly if you know it.",
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
    )


def _source_value(values: Mapping[str, Any], key: str) -> str:
    value = values.get(key)
    return value.strip() if isinstance(value, str) else ""


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
    )


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
        "Enter a known CCLD facility/license number to continue. "
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
      <p id="facility-search-help">Search by facility/license number, facility name, city,
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
            <h2 id="facility-combobox-heading">Find the facility/license number</h2>
            <label for="facility-search-input">Facility</label>
            <p id="facility-search-hint" class="helper-text">Search by name, license number, city, county, ZIP, facility type, program type, or status code.</p>
            <form action="{CCLD_FACILITY_LOOKUP_PATH}" method="get" class="facility-search-form">
                <div class="facility-combobox-outer" id="facility-combobox-outer">
                    <input id="facility-search-input" name="q" type="search" autocomplete="off"
                        placeholder="Name, license number, city, or ZIP"
                        aria-describedby="facility-search-hint"
                        value="{_escape(current_query)}">
                    <ul id="facility-suggestion-list" class="facility-suggestions" aria-label="Facility suggestions" hidden></ul>
                </div>
                <div class="form-actions">
                    <button type="submit">Search CCLD facilities</button>
                </div>
            </form>
            <details class="technical-details">
                <summary>When to use lookup vs. manual entry</summary>
                <p>Use facility lookup when you know a facility name, city, county, ZIP, facility type, program type, or status code but not the exact facility/license number. Use manual entry when you already know the digit facility/license number.</p>
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
            <h2 id="facility-combobox-heading">Find the facility/license number</h2>
            <label for="facility-search-input">Search facility directory (not configured)</label>
            <p id="facility-search-hint" class="helper-text">Facility directory lookup is not configured for this hosted environment. Enter a known CCLD facility/license number on Request Records instead. Directory lookup is optional and does not affect Request Records or review.</p>
            <form action="{CCLD_FACILITY_LOOKUP_PATH}" method="get" class="facility-search-form">
                <div>
                    <input id="facility-search-input" name="q" type="search" autocomplete="off"
                        placeholder="Facility name or number"
                        aria-describedby="facility-search-hint"
                        value="{_escape(current_query)}">
                </div>
                <div class="form-actions">
                    <button type="submit" class="button-secondary">Search facility directory</button>
                </div>
            </form>
{limited_note_markup}
    </section>"""


def _render_facility_selected_card_html(*, mode: str = "facility") -> str:
    """Render the hidden selected-facility confirmation card filled by JS."""
    if mode == "request":
        actions = """<div class="form-actions">
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
                    <div class="form-actions">
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
        <p>Reference data is lookup assistance only; use it to find a facility/license number before Request Records.</p>
        <details>
            <summary>Developer reference setup</summary>
            <p>Full facility CSV support is read-only. Full facility CSV files must stay outside
            the repository and are not imported or persisted by this app.</p>
            <p>To use a full facility CSV, set <code>{CCLD_FACILITY_REFERENCE_CSV_ENV}</code>
            or configure the documented ignored local reference location. Local paths are not shown in the browser.</p>
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
            <p>Reference data is lookup assistance only; use it to find a facility/license
            number before Request Records. Open source links from record detail when a source check is needed.</p>
{notice_markup}
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
        <p>No facility-directory results matched <strong>{_escape(result.query)}</strong>.</p>
        <p>Try a shorter name, license number, city, county, ZIP, facility type, or program type. You can also enter
      a facility/license number directly on Request Records.</p>
    <p><a class="button-quiet" href="{CCLD_RECORD_REQUEST_PATH}">Open Request Records</a></p>
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
        <h2 id="facility-results-heading">Facility-directory results</h2>
        <p>Choose a facility to carry its facility/license number and name into Request Records. Date controls appear as soon as a facility is selected.</p>
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
                        {_render_facility_directory_details(record)}
                    </div>
                    <div class="form-actions" aria-label="Actions for facility {_escape(record.facility_number)}">
                        <a class="button" href="{_escape(request_href)}" aria-label="Use facility {_escape(record.facility_number)} ({_escape(record.facility_name)}) in Request Records">Use this facility in Request Records</a>
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
                "Facility number",
                "Name",
                "Program type",
                "Facility type",
                "City/state/ZIP" if not concise_labels else "City / State / ZIP",
                "County",
                "Capacity",
                "Status",
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
                <dd>{_escape(_display_value(record.capacity))}</dd>
                <dt>{labels[7]}</dt>
                <dd>{_escape(_display_value(_display_facility_status_code(record.status)))}</dd>
            </dl>"""


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
                request_link = f"""        <li><a href="{_escape(_facility_request_href_for_values(facility_number=facility_number))}">Start complaint request for facility { _escape(facility_number) }</a></li>"""
        return f"""    <section class="empty-state-card" aria-labelledby="facility-hub-not-found-heading">
            <h2 id="facility-hub-not-found-heading">Facility-directory result not found</h2>
            <p>No active preloaded facility-directory row matched facility number <strong>{_escape(searched)}</strong>.</p>
            <p>Try a different search, enter the facility/license number directly, or report an issue if the lookup result is confusing.</p>
            <nav aria-label="Facility hub recovery actions">
                <ul>
                    <li><a href="{CCLD_FACILITY_LOOKUP_PATH}">Return to facility lookup</a></li>
{request_link}
                </ul>
            </nav>
        </section>"""


def _render_facility_hub_review_context(
        record: CcldFacilityLookupRecord,
        review_context: CcldFacilityReviewContext,
) -> str:
        if not review_context.has_loaded_context:
                return f"""    <section class="empty-state-card" aria-labelledby="facility-hub-context-heading">
            <h2 id="facility-hub-context-heading">Complaint review context</h2>
            <p>No complaint context is currently available for facility {_escape(record.facility_number)} in the loaded review data.</p>
            <p>Date range is needed before the review queue, packet preview, or packet draft can be scoped for this facility. Start a complaint request to choose dates or retrieve records through the existing controlled workflow.</p>
        </section>"""
        date_text = _hub_date_context_text(review_context)
        return f"""    <section aria-labelledby="facility-hub-context-heading">
            <h2 id="facility-hub-context-heading">Complaint review context</h2>
            <p>{review_context.loaded_complaint_record_count} loaded complaint record(s) currently reference this facility in existing source-derived review data.</p>
            <dl class="summary-list">
                <dt>Complaint context basis</dt>
                <dd>{_escape(review_context.source_label)}</dd>
                <dt>Known date context</dt>
                <dd>{_escape(date_text)}</dd>
            </dl>
            <p>Use this navigation context to open the complaint request, loaded records, packet preview, or Report an issue route that matches this facility/date review.</p>
        </section>"""


def _render_facility_pattern_review_summary(
        record: CcldFacilityLookupRecord,
        review_context: CcldFacilityReviewContext,
        signals_summary: FacilityReviewSignalsSummary | None,
) -> str:
        request_href = _facility_request_href(record)
        queue_href = f"{REVIEWER_UI_RECORDS_PATH}?{urlencode({'q': record.facility_number})}"
        if not review_context.has_loaded_context:
                signals_text = _pattern_summary_signal_text(signals_summary)
                return f"""    <section class="summary-card" aria-labelledby="facility-pattern-summary-heading">
            <h2 id="facility-pattern-summary-heading">Facility pattern review summary</h2>
            <p>No loaded complaint records are currently available for this facility in the review context. This is not a public-source completeness conclusion.</p>
            {signals_text}
            <ul>
                <li>Request or load records for this facility before drawing review conclusions from complaint activity.</li>
                <li>Review available source traceability when records become available.</li>
                <li>Use uploaded public summary review signals only as planning cues, not legal findings.</li>
            </ul>
            <p><a class="button" href="{_escape(request_href)}">Request or load records for this facility</a></p>
        </section>"""
        finding_items = _render_pattern_summary_finding_items(review_context)
        status_items = _render_pattern_summary_status_items(review_context)
        review_next_text = _review_next_summary_label(review_context)
        signal_metrics = _pattern_summary_signal_metrics(signals_summary)
        return f"""    <section class="summary-card" aria-labelledby="facility-pattern-summary-heading">
            <h2 id="facility-pattern-summary-heading">Facility pattern review summary</h2>
            <p>Review signals below use source-derived loaded records and available uploaded public summary fields for facility {_escape(record.facility_number)}. They may deserve closer review; they are not legal conclusions or source-completeness findings.</p>
            <div class="dense-fact-row" aria-label="Facility pattern review signals">
                <div class="stat-card"><strong>{review_context.loaded_complaint_record_count}</strong><span>Loaded complaint records</span></div>
                <div class="stat-card"><strong>{review_context.delay_review_record_count}</strong><span>Delay-review records</span></div>
                <div class="stat-card"><strong>{review_context.missing_date_record_count}</strong><span>Missing-date records</span></div>
                <div class="stat-card"><strong>{review_context.source_traceability_count}</strong><span>Records with source traceability</span></div>
            </div>
            <dl class="summary-list">
                <dt>Recent complaint/report/visit activity in loaded records</dt>
                <dd>{_escape(_display_value(review_context.recent_activity_date))}</dd>
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
{signal_metrics}
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
        reasons = "\n".join(
                f"                    <li>{_escape(reason)}</li>" for reason in item.reasons
        )
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


def _render_packet_readiness_section(
        record: CcldFacilityLookupRecord,
        review_context: CcldFacilityReviewContext,
) -> str:
        request_href = _facility_request_href(record)
        priority_href = CCLD_FACILITY_REVIEW_PRIORITY_PATH
        if not review_context.has_loaded_context:
                return f"""    <section class="empty-state-card" aria-labelledby="packet-readiness-heading">
            <h2 id="packet-readiness-heading">Packet readiness</h2>
            <p>No loaded complaint records are available in this facility context. This is not a public-source completeness conclusion.</p>
            <ul>
                <li>Request records for this facility before preparing packet content.</li>
                <li>Review prioritized records first after loaded records and review-next signals are available.</li>
                <li>No packet preview/draft content is implied until loaded records match this context.</li>
            </ul>
            <p><a class="button" href="{_escape(request_href)}">Request records for this facility</a></p>
            <p><a href="{_escape(priority_href)}">Open facility review priority list</a></p>
        </section>"""
        packet_query = _packet_readiness_query(record, review_context)
        packet_query_text = urlencode(packet_query)
        preview_href = f"{REVIEWER_UI_PACKET_PREVIEW_PATH}?{packet_query_text}"
        draft_href = f"{REVIEWER_UI_PACKET_DRAFT_PATH}?{packet_query_text}"
        prioritized_count = len(review_context.review_next_recommendations)
        prioritized_text = (
                f"{prioritized_count} prioritized loaded record(s) available from Review next."
                if prioritized_count
                else "No prioritized loaded records are available from Review next in this context."
        )
        status_text = _packet_readiness_reviewer_status_text(review_context)
        return f"""    <section class="summary-card" aria-labelledby="packet-readiness-heading">
            <h2 id="packet-readiness-heading">Packet readiness</h2>
            <p>Prepare a review packet from this selected facility context using the existing packet preview or draft routes. This is a local/test review-readiness step, not a legal report, final export, certified record, source-verification result, or source-completeness finding.</p>
            <dl class="summary-list">
                <dt>Selected facility identity</dt>
                <dd>{_escape(record.facility_number)}; {_escape(_display_value(record.facility_name))}</dd>
                <dt>Loaded complaint/review context</dt>
                <dd>{review_context.loaded_complaint_record_count} loaded complaint record(s){_escape(_packet_readiness_date_text(review_context))}</dd>
                <dt>Prioritized records available</dt>
                <dd>{_escape(prioritized_text)}</dd>
                <dt>Source traceability availability</dt>
                <dd>{review_context.source_traceability_count} of {review_context.loaded_complaint_record_count} loaded record(s) have visible source traceability cues.</dd>
                <dt>Reviewer-created status/note presence</dt>
                <dd>{_escape(status_text)} {review_context.reviewer_note_record_count} loaded record(s) have reviewer-created note rows.</dd>
            </dl>
            <ul>
                <li>Review prioritized records first when the readiness summary shows source-check or reviewer-created status/note attention.</li>
                <li>Use packet preview to inspect included records before browser copy or print.</li>
                <li>Use packet draft only for manual review preparation; no packet lifecycle state is saved.</li>
            </ul>
            <nav aria-label="Packet readiness actions">
                <ul>
                    <li><a class="button" href="{_escape(preview_href)}">Open packet preview for this facility/date context</a></li>
                    <li><a class="button button-secondary" href="{_escape(draft_href)}">Open packet draft for this facility/date context</a></li>
                    <li><a href="{_escape(request_href)}">Request or refresh records for this facility</a></li>
                </ul>
            </nav>
        </section>"""


def _packet_readiness_query(
        record: CcldFacilityLookupRecord,
        review_context: CcldFacilityReviewContext,
) -> dict[str, str]:
        return {
                "facility_number": record.facility_number,
                "start_date": review_context.start_date,
                "end_date": review_context.end_date,
                "request_context_origin": "facility_lookup",
                "lookup_facility_name": record.facility_name,
        }


def _packet_readiness_date_text(review_context: CcldFacilityReviewContext) -> str:
        if review_context.has_date_context:
                return f" from {review_context.start_date} to {review_context.end_date}"
        return " without a bounded date range"


def _packet_readiness_reviewer_status_text(
        review_context: CcldFacilityReviewContext,
) -> str:
        if not review_context.reviewer_status_counts:
                return "No reviewer-created status summary is available."
        status_text = "; ".join(
                f"{_reviewer_status_label(status)}: {count}"
                for status, count in review_context.reviewer_status_counts
        )
        return f"Reviewer-created status summary: {status_text}."


def _review_next_summary_label(review_context: CcldFacilityReviewContext) -> str:
        if review_context.review_next_recommendations:
                return review_context.review_next_recommendations[0].label
        return _display_value(review_context.review_next_label)


def _render_facility_review_signals_section(
        record: CcldFacilityLookupRecord,
        summary: FacilityReviewSignalsSummary | None,
) -> str:
        if summary is None:
                return f"""    <section class="empty-state-card" aria-labelledby="facility-review-signals-heading">
            <h2 id="facility-review-signals-heading">Facility review signals</h2>
            <p>No uploaded public summary fields are available for facility {_escape(record.facility_number)} in the supported licensing/visit/citation summary CSV inputs.</p>
            <p>This empty state does not mean the facility has no complaints, visits, citations, POC dates, or public-source records. Start a complaint request or return to facility lookup when you need a different facility context.</p>
        </section>"""
        cues = "\n".join(
                f"        <li>{_escape(cue)} review cue</li>" for cue in summary.review_cues
        )
        if not cues:
                cues = "        <li>No supported uploaded public summary review cue is present for this facility.</li>"
        return f"""    <section aria-labelledby="facility-review-signals-heading">
            <h2 id="facility-review-signals-heading">Facility review signals</h2>
            <div class="dense-fact-row" aria-label="Facility signal highlights">
                <div class="stat-card"><strong>{summary.complaint_visit_count}</strong><span>Complaint visits</span></div>
                <div class="stat-card"><strong>{summary.citation_count}</strong><span>Citation values</span></div>
                <div class="stat-card"><strong>{summary.poc_date_count}</strong><span>POC dates</span></div>
                <div class="stat-card"><strong>{_escape(_display_value(summary.last_visit_date))}</strong><span>Last visit date</span></div>
            </div>
            <details class="technical-details dense-table-details">
                <summary>Uploaded summary field details</summary>
            <dl class="summary-list">
                <dt>Source dataset label</dt>
                <dd>{_render_source_dataset_labels(summary.source_dataset_labels)}</dd>
                <dt>Facility type in uploaded summary</dt>
                <dd>{_escape(_display_tuple(summary.facility_types))}</dd>
                <dt>Status in uploaded summary</dt>
                <dd>{_escape(_display_tuple(summary.statuses))}</dd>
                <dt>Capacity in uploaded summary</dt>
                <dd>{_escape(_display_tuple(summary.capacities))}</dd>
                <dt>County / regional office in uploaded summary</dt>
                <dd>{_escape(_display_joined_parts((_display_tuple(summary.counties), _display_tuple(summary.regional_offices))))}</dd>
                <dt>License first date in uploaded summary</dt>
                <dd>{_escape(_display_tuple(summary.license_first_dates))}</dd>
                <dt>Closed date in uploaded summary</dt>
                <dd>{_escape(_display_tuple(summary.closed_dates))}</dd>
                <dt>Last visit date in uploaded summary</dt>
                <dd>{_escape(_display_value(summary.last_visit_date))}</dd>
                <dt>Visit activity in uploaded summary</dt>
                <dd>{summary.total_visit_count} total; {summary.inspection_visit_count} inspection; {summary.complaint_visit_count} complaint; {summary.other_visit_count} other</dd>
                <dt>Citation indicators in uploaded summary</dt>
                <dd>{summary.citation_count} citation value(s); {summary.type_a_citation_count} Type A value(s); {summary.type_b_citation_count} Type B value(s)</dd>
                <dt>POC date indicators in uploaded summary</dt>
                <dd>{summary.poc_date_count}</dd>
            </dl>
            </details>
            <section aria-labelledby="facility-review-cues-heading">
                <h3 id="facility-review-cues-heading">What to review next</h3>
                <ul>
{cues}
                </ul>
                <p>Use these cues to decide whether to start a complaint request, review loaded records where available, or return to facility lookup. Review source traceability before relying on summary fields.</p>
            </section>
            <details class="technical-details diagnostic-details">
                <summary>How to use these signals</summary>
                <p>These facility review signals come from uploaded public summary fields in supported public licensing/visit/citation summary CSVs; complaint records are requested/reviewed separately.</p>
                <p>Use signals to choose the next review route, then check source traceability before relying on summary fields.</p>
            </details>
        </section>"""


def _pattern_summary_signal_text(
        signals_summary: FacilityReviewSignalsSummary | None,
) -> str:
        if signals_summary is None:
                return "<p>No uploaded public summary review signals are available for this facility.</p>"
        return (
                "<p>Uploaded public summary fields are available as planning cues: "
                f"{signals_summary.complaint_visit_count} complaint visit(s), "
                f"{signals_summary.citation_count} citation value(s), "
                f"{signals_summary.poc_date_count} POC date(s), and last visit "
                f"{_escape(_display_value(signals_summary.last_visit_date))}.</p>"
        )


def _pattern_summary_signal_metrics(
        signals_summary: FacilityReviewSignalsSummary | None,
) -> str:
        if signals_summary is None:
                return ""
        return f"""                <dt>Uploaded public summary citation/POC indicators</dt>
                <dd>{signals_summary.type_a_citation_count} Type A value(s); {signals_summary.type_b_citation_count} Type B value(s); {signals_summary.poc_date_count} POC date(s)</dd>
                <dt>Uploaded public summary visit activity</dt>
                <dd>{signals_summary.complaint_visit_count} complaint visit(s); last visit {_escape(_display_value(signals_summary.last_visit_date))}</dd>"""


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
    cue_filter: str,
) -> tuple[FacilityReviewSignalsSummary, ...]:
    ordered = tuple(sorted(summaries, key=_priority_sort_key))
    if not cue_filter or cue_filter == "all":
        return ordered
    return tuple(summary for summary in ordered if cue_filter in _priority_cues(summary))


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


def _render_priority_filter(active_cue: str) -> str:
    options = ("all",) + _PRIORITY_CUE_ORDER
    option_markup = "\n".join(
        f'          <option value="{_escape(value)}"{_selected_attr(value, active_cue or "all")}>{_escape(_priority_filter_label(value))}</option>'
        for value in options
    )
    return f"""    <section class="workflow-panel" aria-labelledby="facility-priority-filter-heading">
      <h2 id="facility-priority-filter-heading">Filter review cues</h2>
      <form action="{CCLD_FACILITY_REVIEW_PRIORITY_PATH}" method="get">
        <p>
          <label for="priority-cue-filter">Cue type</label>
          <select id="priority-cue-filter" name="cue" aria-describedby="priority-cue-filter-help">
{option_markup}
          </select>
        </p>
        <p id="priority-cue-filter-help" class="helper-text">Filter by transparent review cue over uploaded public summary fields.</p>
        <p><button type="submit">Apply review cue filter</button></p>
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
    return "All review cues" if value == "all" else value


def _selected_attr(value: str, active_value: str) -> str:
    return " selected" if value == active_value else ""


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
        f"        <dt>{_escape(cue)} facilities</dt><dd>{count}</dd>"
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


def _render_priority_empty_rows(cue_filter: str) -> str:
    filter_text = (
        f" for review cue {_escape(cue_filter)}"
        if cue_filter and cue_filter != "all"
        else ""
    )
    return f"""          <tr>
            <td colspan="4">
              <p>No facility review priority rows are available{filter_text}.</p>
              <p>This optional feature requires uploaded public summary CSVs to be configured. It is not required for Request Records or review.</p>
              <p>This does not mean facilities have no complaints, visits, citations, POC dates, or public-source records. It only means supported uploaded public summary fields did not produce a visible row for this view.</p>
              <p><a href="{CCLD_FACILITY_LOOKUP_PATH}">Return to facility lookup to find a facility and retrieve complaint records.</a></p>
            </td>
          </tr>"""


def _render_priority_row(summary: FacilityReviewSignalsSummary) -> str:
    cues = _priority_cues(summary)
    cue_text = "; ".join(f"{cue} review cue" for cue in cues) if cues else "No uploaded summary signals available"
    field_text = (
        f"{summary.total_visit_count} total visits; {summary.complaint_visit_count} complaint visits; "
        f"{summary.citation_count} citation value(s); {summary.poc_date_count} POC date(s); "
        f"last visit {_display_value(summary.last_visit_date)}; status {_display_tuple(summary.statuses)}; "
        f"capacity {_display_tuple(summary.capacities)}"
    )
    facility_label = _safe_priority_text(summary.facility_name or summary.facility_number)
    return f"""          <tr>
            <th scope="row">
              {_escape(facility_label)}<br>
              <span class="helper-text">Facility/license {_escape(summary.facility_number)}</span>
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
        context_actions = ""
        if review_context.has_loaded_context and review_context.has_date_context:
                queue_query = {
                        "facility_number": record.facility_number,
                        "start_date": review_context.start_date,
                        "end_date": review_context.end_date,
                        "request_context_origin": "facility_lookup",
                        "lookup_facility_name": record.facility_name,
                }
                context_actions = f"""        <li>
                    <form action="{CCLD_RECORD_REQUEST_PATH}" method="post">
                        <input type="hidden" name="facility_number" value="{_escape(record.facility_number)}">
                        <input type="hidden" name="record_type" value="complaints">
                        <input type="hidden" name="start_date" value="{_escape(review_context.start_date)}">
                        <input type="hidden" name="end_date" value="{_escape(review_context.end_date)}">
                        <input type="hidden" name="request_context_origin" value="facility_lookup">
                        <input type="hidden" name="lookup_facility_name" value="{_escape(record.facility_name)}">
                        <button type="submit" class="button button-secondary">Review loaded records for this facility/date context</button>
                    </form>
                </li>
                <li><a class="button button-secondary" href="{REVIEWER_UI_RECORDS_PATH}?{_escape(urlencode({'q': record.facility_number}))}">Open reviewer queue filtered to this facility</a></li>
                <li><a class="button button-secondary" href="{REVIEWER_UI_MATRIX_EXPORT_PATH}?{_escape(urlencode(queue_query))}">Download complaint review matrix CSV</a></li>
                <li><a class="button button-secondary" href="{REVIEWER_UI_PACKET_PREVIEW_PATH}?{_escape(urlencode(queue_query))}">Open packet preview for this facility/date context</a></li>
                <li><a class="button button-secondary" href="{REVIEWER_UI_PACKET_DRAFT_PATH}?{_escape(urlencode(queue_query))}">Open packet draft for this facility/date context</a></li>"""
        elif review_context.has_loaded_context:
                context_actions = """        <li><span>Date range needed before review queue or packet routes can be scoped.</span></li>"""
        return f"""    <section aria-labelledby="facility-hub-actions-heading">
            <h2 id="facility-hub-actions-heading">Next actions</h2>
            <nav aria-label="Facility review hub actions">
                <ul>
                    <li><a class="button" href="{_escape(request_href)}">Start complaint request for this facility</a></li>
{context_actions}
                    <li><a class="button button-secondary" href="{CCLD_FACILITY_REVIEW_PRIORITY_PATH}">Open facility review priority list</a></li>
                    <li><a class="button button-quiet" href="{_escape(lookup_href)}">Return to facility lookup</a></li>
                </ul>
            </nav>
        </section>"""


def _hub_date_context_text(review_context: CcldFacilityReviewContext) -> str:
        if review_context.has_date_context:
                return f"{review_context.start_date} to {review_context.end_date}"
        return "date range needed before review queue can be scoped"


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


def _page(*, title: str, heading: str, main: str) -> str:
        return render_page_shell(
                title=title,
                heading=heading,
                main=main,
                skip_label="Skip to main CCLD facility lookup content",
                nav_label="CCLD facility navigation",
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


def _display_tuple(values: tuple[str, ...]) -> str:
    return "; ".join(values) if values else "not listed"


def _render_source_dataset_labels(values: tuple[str, ...]) -> str:
    if not values:
        return "not listed"
    return "; ".join(_render_source_dataset_label(value) for value in values)


def _render_source_dataset_label(value: str) -> str:
    loaded_date_text = _loaded_date_text_from_filename(value)
    if not loaded_date_text:
        return f"<code>{_escape(value)}</code>"
    return f"<code>{_escape(value)}</code> {_escape(loaded_date_text)}"


def _loaded_date_text_from_filename(filename: str) -> str:
    match = re.search(r"(?<!\d)(\d{2})(\d{2})(\d{4})(?!\d)", filename)
    if match is None:
        return ""
    month, day, year = (int(part) for part in match.groups())
    try:
        loaded_date = date(year, month, day)
    except ValueError:
        return ""
    return f"(loaded {loaded_date:%B} {loaded_date.day}, {loaded_date:%Y})"


def _display_joined_parts(values: tuple[str, ...]) -> str:
    parts = tuple(value for value in values if value and value != "not listed")
    return " / ".join(parts) if parts else "not listed"


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
            "Enter a known CCLD facility/license number to continue."
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
            "Enter a known CCLD facility/license number to continue."
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
) -> list[dict[str, str]]:
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
