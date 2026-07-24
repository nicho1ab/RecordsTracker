# ruff: noqa: E501

from __future__ import annotations

import csv
import html
import json
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from ccld_complaints.hosted_app.facility_identity_presenter import (
    present_facility_field,
    projected_display_text,
    projected_selected_text,
)
from ccld_complaints.hosted_app.facility_identity_projection import (
    FacilityIdentityProjection,
    FacilityProjectionCandidate,
    FacilityProjectionField,
    FacilitySourceKind,
    FacilityValueContext,
    FacilityValueState,
    project_facility_identity,
)
from ccld_complaints.hosted_app.facility_review_signals import (
    FacilityReviewSignalsSummary,
    load_active_facility_review_signals,
)
from ccld_complaints.hosted_app.ui_shell import (
    ActionItem,
    render_action_group,
    render_compare_facilities_views,
    render_inline_glossary_term,
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
_STATE_TEXT_VALUES = frozenset(
    {
        "Blank in source",
        "Conflicting source values",
        "Invalid source value",
        "Not found in source",
        "Source unavailable",
    }
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
  var sb=document.getElementById('facility-submit-btn');
  var sl=document.getElementById('facility-suggestion-list');
  var sc=document.getElementById('facility-selected-card');
  var de=document.getElementById('facility-reference-json');
  var suggestUrl=wrap.getAttribute('data-facility-suggest-url')||'';
  if(!si||!sl||!de)return;
  var facs=[];
  var requestSeq=0;
  var pendingSuggestionTimer=null;
  var activeSuggestionController=null;
  // A short delay coalesces ordinary typing without making facility lookup feel delayed.
  var SUGGESTION_DEBOUNCE_MS=250;
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
  function statusInfo(s,state,conflict){
    var raw=String(s==null?'':s).trim();
    var v=norm(raw);
    var cls='other';
    if(v.indexOf('licensed')!==-1)cls='licensed';
    else if(v.indexOf('closed')!==-1)cls='closed';
    else if(v.indexOf('pending')!==-1)cls='pending';
    var title=conflict?'Conflicting source observations':raw;
    return{label:raw,cls:cls,title:title,state:state};
  }
  function buildHtml(matches){
    var h='';
    for(var i=0;i<matches.length;i++){
      var f=matches[i];
    var info=statusInfo(f.s,f.ss,f.sc);
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
  function hasUsefulSuggestionQuery(q){
    // Two letters/digits preserve short city, county, ZIP, and Facility ID searches;
    // punctuation does not turn a one-character broad query into a useful request.
    return norm(q).replace(/[^a-z0-9]/g,'').length>=2;
  }
  function cancelPendingSuggestions(){
    if(pendingSuggestionTimer!==null){
      clearTimeout(pendingSuggestionTimer);
      pendingSuggestionTimer=null;
    }
    if(activeSuggestionController&&typeof activeSuggestionController.abort==='function'){
      activeSuggestionController.abort();
    }
    activeSuggestionController=null;
  }
  function isAbortError(error){
    return Boolean(error&&error.name==='AbortError');
  }
  function showSugs(q){
    var toks=norm(q).split(' ').filter(Boolean);
    cancelPendingSuggestions();
    var seq=++requestSeq;
    sl.setAttribute('hidden','');
    si.setAttribute('aria-expanded','false');
    if(!toks.length||!hasUsefulSuggestionQuery(q)){hideSugs();return;}
    if(suggestUrl&&typeof fetch==='function'){
      pendingSuggestionTimer=setTimeout(function(){
        if(seq!==requestSeq)return;
        pendingSuggestionTimer=null;
        var controller=(typeof AbortController==='function')?new AbortController():null;
        activeSuggestionController=controller;
        sl.innerHTML='<li><span class="suggestion-empty">Searching...</span></li>';
        sl.removeAttribute('hidden');
        si.setAttribute('aria-expanded','true');
        var options={headers:{'Accept':'application/json'}};
        if(controller)options.signal=controller.signal;
        fetch(suggestUrl+'?q='+encodeURIComponent(q),options)
          .then(function(resp){if(!resp.ok)throw new Error('lookup');return resp.json();})
          .then(function(data){if(seq!==requestSeq)return;renderMatches(data.records||[]);})
          .catch(function(error){
            if(seq!==requestSeq||isAbortError(error))return;
            renderMatches([]);
          })
          .finally(function(){
            if(seq===requestSeq&&activeSuggestionController===controller){
              activeSuggestionController=null;
            }
          });
      },SUGGESTION_DEBOUNCE_MS);
      return;
    }
    var ms=[];
    for(var i=0;i<facs.length&&ms.length<25;i++){if(match(facs[i],toks))ms.push(facs[i]);}
    renderMatches(ms);
  }
  function hideSugs(){
    cancelPendingSuggestions();
    requestSeq++;
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
    administrator: str = ""
    licensee: str = ""
    telephone: str = ""
    identity_projection: FacilityIdentityProjection | None = field(
        default=None,
        compare=False,
        hash=False,
        repr=False,
    )


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
class CcldFacilityComplaintContext:
    source_record_key: str
    stable_complaint_id: str
    complaint_control_number: str
    activity_date: str
    finding: str
    detail_href: str
    source_url_href: str = ""
    serious_topics: tuple[str, ...] = ()
    substantiated: bool = False
    strongest_delay_days: int = 0
    missing_dates: bool = False
    source_available: bool = False
    reviewer_status: str = "not_started"
    reviewer_note_count: int = 0


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
    date_dimension: str = "complaint_received_date"
    date_dimension_label: str = "Complaint received date"
    coverage_status: str = "unavailable"
    source_unavailable_count: int = 0
    serious_topic_counts: tuple[tuple[str, int], ...] = ()
    anomaly_cues: tuple[str, ...] = ()
    complaints: tuple[CcldFacilityComplaintContext, ...] = ()
    reviewer_state_available: bool = True
    origin: str = ""
    active_filters: tuple[tuple[str, str], ...] = ()

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


def project_ccld_facility_reference_source(
    source: CcldFacilityReferenceSource,
) -> CcldFacilityReferenceSource:
    if source.records and all(
        record.identity_projection is not None for record in source.records
    ):
        return source
    records_by_id: dict[str, list[CcldFacilityLookupRecord]] = {}
    for record in source.records:
        if record.facility_number.isdigit():
            records_by_id.setdefault(record.facility_number, []).append(record)
    projected_records = tuple(
        facility_lookup_record_from_projection(
            _project_lookup_records(
                facility_id,
                records,
                source=source,
            ),
            supplemental_records=records,
        )
        for facility_id, records in sorted(records_by_id.items())
    )
    return CcldFacilityReferenceSource(
        source_kind=source.source_kind,
        label=source.label,
        path_label=source.path_label,
        records=projected_records,
        notices=source.notices,
        record_count=(
            len(projected_records)
            if source.records
            else source.record_count
        ),
    )


def facility_lookup_record_from_projection(
    projection: FacilityIdentityProjection,
    *,
    supplemental_records: Iterable[CcldFacilityLookupRecord] = (),
) -> CcldFacilityLookupRecord:
    records = tuple(supplemental_records)
    return CcldFacilityLookupRecord(
        facility_number=projection.public_facility_id,
        facility_name=projected_selected_text(
            projection, FacilityProjectionField.FACILITY_NAME
        ),
        city=projected_selected_text(projection, FacilityProjectionField.CITY),
        state=projected_selected_text(projection, FacilityProjectionField.STATE),
        county=projected_selected_text(projection, FacilityProjectionField.COUNTY),
        zip_code=projected_selected_text(projection, FacilityProjectionField.ZIP),
        facility_type=projected_selected_text(
            projection, FacilityProjectionField.FACILITY_TYPE
        ),
        program_type=_consistent_record_value(records, "program_type"),
        capacity=projected_selected_text(projection, FacilityProjectionField.CAPACITY),
        status=projected_selected_text(projection, FacilityProjectionField.STATUS),
        closed_date=projected_selected_text(
            projection, FacilityProjectionField.CLOSED_DATE
        ),
        address=projected_selected_text(
            projection, FacilityProjectionField.FULL_ADDRESS
        ),
        regional_office=projected_selected_text(
            projection, FacilityProjectionField.REGIONAL_OFFICE
        ),
        administrator=projected_selected_text(
            projection, FacilityProjectionField.ADMINISTRATOR
        ),
        licensee=projected_selected_text(
            projection, FacilityProjectionField.LICENSEE
        ),
        telephone=projected_selected_text(
            projection, FacilityProjectionField.TELEPHONE
        ),
        identity_projection=projection,
    )


def facility_lookup_result_from_projections(
    result: CcldFacilityLookupResult,
    projections: Mapping[str, FacilityIdentityProjection],
) -> CcldFacilityLookupResult:
    records_by_id: dict[str, list[CcldFacilityLookupRecord]] = {}
    for record in result.returned_records:
        records_by_id.setdefault(record.facility_number, []).append(record)
    projected_records = tuple(
        facility_lookup_record_from_projection(
            projections[facility_id],
            supplemental_records=records_by_id.get(facility_id, ()),
        )
        for facility_id in dict.fromkeys(
            record.facility_number for record in result.returned_records
        )
        if facility_id in projections
        and not projections[facility_id].ineligible_candidate_excluded
    )
    hidden_count = len(
        {
            record.facility_number
            for record in result.returned_records
            if record.facility_number in projections
            and projections[record.facility_number].ineligible_candidate_excluded
        }
    )
    return CcldFacilityLookupResult(
        query=result.query,
        total_match_count=max(0, result.total_match_count - hidden_count),
        returned_records=projected_records,
        result_limit=result.result_limit,
        reference_source=result.reference_source,
    )


def project_ccld_facility_lookup_result(
    result: CcldFacilityLookupResult,
    source: CcldFacilityReferenceSource,
) -> CcldFacilityLookupResult:
    if result.returned_records and all(
        record.identity_projection is not None for record in result.returned_records
    ):
        return result
    records_by_id: dict[str, list[CcldFacilityLookupRecord]] = {}
    for record in result.returned_records:
        records_by_id.setdefault(record.facility_number, []).append(record)
    projections = {
        facility_id: _project_lookup_records(facility_id, records, source=source)
        for facility_id, records in records_by_id.items()
    }
    return facility_lookup_result_from_projections(result, projections)


def _project_lookup_records(
    facility_id: str,
    records: Iterable[CcldFacilityLookupRecord],
    *,
    source: CcldFacilityReferenceSource,
) -> FacilityIdentityProjection:
    if source.source_kind == "postgres_source_derived":
        source_kind = FacilitySourceKind.COMPLAINT_LINKED_FACILITY
        context = FacilityValueContext.HISTORICAL_COMPLAINT
    elif source.source_kind == "postgres_transparencyapi_reference":
        source_kind = FacilitySourceKind.TRANSPARENCY_API_CURRENT
        context = FacilityValueContext.CURRENT_REFERENCE
    else:
        source_kind = FacilitySourceKind.PROGRAM_REFERENCE
        context = FacilityValueContext.HISTORICAL_REFERENCE
    candidates = tuple(
        _projection_candidate_from_lookup_record(
            record,
            source=source,
            source_kind=source_kind,
            context=context,
        )
        for record in records
    )
    return project_facility_identity(facility_id, candidates)


def _projection_candidate_from_lookup_record(
    record: CcldFacilityLookupRecord,
    *,
    source: CcldFacilityReferenceSource,
    source_kind: FacilitySourceKind,
    context: FacilityValueContext,
) -> FacilityProjectionCandidate:
    values: dict[FacilityProjectionField, Any] = {
        FacilityProjectionField.PUBLIC_FACILITY_ID: record.facility_number,
        FacilityProjectionField.FACILITY_NAME: record.facility_name,
        FacilityProjectionField.FACILITY_TYPE: record.facility_type,
        FacilityProjectionField.STATUS: record.status,
        FacilityProjectionField.CLOSED_DATE: record.closed_date,
        FacilityProjectionField.CITY: record.city,
        FacilityProjectionField.STATE: record.state,
        FacilityProjectionField.ZIP: record.zip_code,
        FacilityProjectionField.COUNTY: record.county,
        FacilityProjectionField.CAPACITY: record.capacity,
        FacilityProjectionField.REGIONAL_OFFICE: record.regional_office,
        FacilityProjectionField.ADMINISTRATOR: record.administrator,
        FacilityProjectionField.LICENSEE: record.licensee,
        FacilityProjectionField.TELEPHONE: record.telephone,
    }
    present_fields = set(values)
    if record.facility_address is not None:
        values[FacilityProjectionField.FULL_ADDRESS] = record.facility_address
        present_fields.add(FacilityProjectionField.FULL_ADDRESS)
    elif record.res_street_addr is not None:
        values[FacilityProjectionField.FULL_ADDRESS] = record.res_street_addr
        present_fields.add(FacilityProjectionField.FULL_ADDRESS)
    elif record.address:
        values[FacilityProjectionField.FULL_ADDRESS] = record.address
        present_fields.add(FacilityProjectionField.FULL_ADDRESS)
    record_identity = "|".join(
        str(values[field]) for field in sorted(values, key=lambda item: item.value)
    )
    return FacilityProjectionCandidate(
        source_kind=source_kind,
        source_row_identity=f"{source.path_label}:{record_identity}",
        snapshot_identity=source.path_label,
        observed_at=None,
        context=context,
        values=values,
        present_fields=frozenset(present_fields),
        source_fields={field: field.value for field in present_fields},
    )


def _consistent_record_value(
    records: Iterable[CcldFacilityLookupRecord],
    attribute: str,
) -> str:
    values = {
        value
        for record in records
        if (value := str(getattr(record, attribute, "")).strip())
    }
    return next(iter(values)) if len(values) == 1 else ""


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
                title="Compare Facilities unavailable",
                heading="Compare Facilities unavailable",
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
    reference_source = project_ccld_facility_reference_source(
        reference_source or load_active_ccld_facility_reference()
    )
    result = (
        project_ccld_facility_lookup_result(lookup_result, reference_source)
        if lookup_result is not None
        else search_ccld_facilities(
            query,
            reference_source.records,
            reference_source=reference_source,
        )
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
                "Compare Facilities",
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
    reference_source = project_ccld_facility_reference_source(
        reference_source or load_active_ccld_facility_reference()
    )
    facility_number = facility_number.strip()
    review_context = review_context or CcldFacilityReviewContext()
    matching_records = tuple(
        record
        for record in reference_source.records
        if record.facility_number == facility_number
    )
    signals_summary = (
        None
        if reference_source.source_kind.startswith("postgres_")
        else load_active_facility_review_signals().summary_for_facility(facility_number)
    )
    if not facility_number or not matching_records:
        if facility_number and (
            review_context.has_loaded_context or signals_summary is not None
        ):
            return _render_signal_only_facility_hub_page(
                facility_number,
                signals_summary=signals_summary,
                review_context=review_context,
            )
        return _page(
            title="Facility Overview not found",
            heading="Facility Overview",
            main=_render_facility_hub_not_found(facility_number),
        )
    record = matching_records[0]
    return _page(
        title="Facility Overview",
        heading="Facility Overview",
        main=f"""    {_render_facility_identity_and_core_facts(record, review_context)}
    {_render_facility_pattern_review_summary(record, review_context)}
    {_render_review_next_section(review_context)}
    {_render_facility_contributor_sections(review_context)}
    {_render_facility_review_signals_section(signals_summary)}
    {_render_facility_hub_actions(record, review_context)}
    {_render_secondary_facility_facts(record)}
    {_render_facility_hub_limitations(review_context)}
    """,
    )


def _render_signal_only_facility_hub_page(
    facility_number: str,
    *,
    signals_summary: FacilityReviewSignalsSummary | None,
    review_context: CcldFacilityReviewContext,
) -> str:
    record = (
        _facility_record_from_signal_summary(signals_summary)
        if signals_summary is not None
        else CcldFacilityLookupRecord(
            facility_number=facility_number,
            facility_name="",
            city="",
            state="",
            county="",
            zip_code="",
            facility_type="",
            program_type="",
            capacity="",
            status="",
            closed_date="",
        )
    )
    facility_label = _safe_priority_text(
        signals_summary.facility_name if signals_summary is not None else facility_number
    )
    signal_context_message = (
        "Supported public licensing and visit observations are available. Review "
        "loaded complaint records separately from facility-reference information."
        if signals_summary is not None
        else (
            "Loaded complaint records exist. Directory-sourced facility facts are "
            "not available for this Facility ID."
        )
    )
    signals_section = (
        _render_facility_review_signals_section(signals_summary)
        if signals_summary is not None
        else ""
    )
    facility_label_copy_aria = (
        "Copy facility name" if signals_summary is not None else "Copy Facility ID"
    )
    loaded_context_intro = (
        "Facility-directory record not available. Supported public licensing and "
        "visit observations and loaded complaint records can still guide the next "
        "review step."
        if signals_summary is not None
        else (
            "Facility-directory record not available. Loaded complaint records can "
            "still guide the next review step."
        )
    )
    if not review_context.has_loaded_context:
        return _page(
            title="Facility Overview",
            heading="Facility Overview",
            main=f"""    <section class="hero-card attorney-hero" aria-labelledby="signal-only-facility-hub-heading">
            <div>
                <p class="launch-kicker">Facility Overview</p>
                <h2 id="signal-only-facility-hub-heading">{_render_copyable_value("Copy facility name", facility_label)}</h2>
                <p class="launch-value">Facility-directory record not available. Supported public licensing and visit observations can still guide the next review step.</p>
                <dl class="summary-list">
                    <dt>Facility ID</dt>
                    <dd>{_render_copyable_value("Copy Facility ID", facility_number)}</dd>
                </dl>
            </div>
        </section>
        <section aria-labelledby="signal-only-context-heading">
            <h2 id="signal-only-context-heading">Facility-directory record not available</h2>
            <p>Supported public licensing and visit observations are available. Start a complaint request before drawing conclusions from complaint activity.</p>
        </section>
        {_render_facility_pattern_review_summary(record, review_context)}
        {_render_review_next_section(review_context)}
        {_render_facility_contributor_sections(review_context)}
        {signals_section}
        {_render_facility_hub_actions(record, review_context)}
        {_render_facility_hub_limitations(review_context)}
        {_render_copy_control_script()}
        """,
        )
    return _page(
    title="Facility Overview",
    heading="Facility Overview",
    main=f"""    <section class="hero-card attorney-hero" aria-labelledby="signal-only-facility-hub-heading">
            <div>
                <p class="launch-kicker">Facility Overview</p>
                <h2 id="signal-only-facility-hub-heading">{_render_copyable_value(facility_label_copy_aria, facility_label)}</h2>
                <p class="launch-value">{loaded_context_intro}</p>
                <dl class="summary-list">
                    <dt>Facility ID</dt>
                    <dd>{_render_copyable_value("Copy Facility ID", facility_number)}</dd>
                </dl>
            </div>
        </section>
        <section aria-labelledby="signal-only-context-heading">
            <h2 id="signal-only-context-heading">Facility-directory record not available</h2>
            <p>{signal_context_message}</p>
        </section>
        {_render_facility_pattern_review_summary(record, review_context)}
        {_render_review_next_section(review_context)}
        {_render_facility_contributor_sections(review_context)}
        {signals_section}
        {_render_facility_hub_actions(record, review_context)}
        {_render_facility_hub_limitations(review_context)}
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
                title="Compare Facilities",
                heading="Find Facilities That May Need Closer Review",
                active_path=CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH,
                main=f"""    <section class="hero-card attorney-hero" aria-labelledby="facility-priority-heading">
            <div>
                <p class="launch-kicker">Compare Facilities</p>
                <h2 id="facility-priority-heading">Licensing and Visit Activity</h2>
                <p>Available public visit, citation, Plan of Correction, status, and capacity information. This view does not show complaint coverage.</p>
            </div>
        </section>
        {render_compare_facilities_views('licensing-visit-activity')}
        {_render_priority_filter(cue_filters, search_query)}
        {_render_priority_summary(signal_result, summaries, returned_summaries)}
        {cards}
        <section aria-labelledby="facility-priority-list-heading">
            <h2 id="facility-priority-list-heading">Licensing and visit activity by facility</h2>
            <table>
                <caption>Available public licensing and visit activity by facility</caption>
                <thead>
                    <tr>
                        <th scope="col">Facility</th>
                        <th scope="col">Supported observations</th>
                        <th scope="col">Public licensing and visit information</th>
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
        facility_name = _facility_record_field(
            record,
            FacilityProjectionField.FACILITY_NAME,
        )
        overview_action = ""
        if record.facility_number.strip():
            hub_href = _facility_hub_href(record.facility_number)
            overview_action = f'''\n                        <a class="button button-secondary" href="{_escape(hub_href)}"
                           aria-label="View Facility Overview for {_escape(record.facility_number)} ({_escape(facility_name)})">View Facility Overview</a>'''
        heading_id = f"facility-{_escape(record.facility_number)}-{index}-heading"
        return f"""        <article class="result-card" aria-labelledby="{heading_id}">
                    <div>
                        <h3 id="{heading_id}">{_escape(facility_name)}</h3>
                        <dl class="summary-list">
                            <dt>Facility ID</dt>
                            <dd>{_escape(record.facility_number)}</dd>
                            <dt>Facility type</dt>
                            <dd>{_escape(_facility_record_field(record, FacilityProjectionField.FACILITY_TYPE))}</dd>
                            <dt>Location</dt>
                            <dd>{_escape(_display_value(_display_location(record)))}</dd>
                            <dt>Status</dt>
                            <dd>{_escape(_facility_record_field(record, FacilityProjectionField.STATUS))}</dd>
                        </dl>{_render_facility_conflict_note(record, (FacilityProjectionField.FACILITY_NAME, FacilityProjectionField.FACILITY_TYPE, FacilityProjectionField.STATUS))}
                        <details class="secondary-actions reference-details-section">
                            <summary>Directory details</summary>
                            {_render_facility_directory_details(record)}
                        </details>
                    </div>
                    <div class="form-actions action-group" aria-label="Actions for facility {_escape(record.facility_number)}">
                        <a class="button" href="{_escape(request_href)}" aria-label="Use facility {_escape(record.facility_number)} ({_escape(facility_name)}) in Request Records">Continue to Request Records</a>
{overview_action}
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
                <dd>{_escape(_facility_record_field(record, FacilityProjectionField.FACILITY_NAME))}</dd>
                <dt>{labels[2]}</dt>
                <dd>{_escape(_display_value(record.program_type))}</dd>
                <dt>{labels[3]}</dt>
                <dd>{_escape(_facility_record_field(record, FacilityProjectionField.FACILITY_TYPE))}</dd>
                <dt>{labels[4]}</dt>
                <dd>{_escape(_display_value(_display_location(record)))}</dd>
                <dt>{labels[5]}</dt>
                <dd>{_escape(_facility_record_field(record, FacilityProjectionField.COUNTY))}</dd>
                <dt>{labels[6]}</dt>
                <dd>{_escape(_facility_record_field(record, FacilityProjectionField.CAPACITY))}</dd>
                <dt>{labels[7]}</dt>
                <dd>{_escape(_facility_record_field(record, FacilityProjectionField.STATUS))}</dd>
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
        <h2 id="facility-hub-heading">{_render_copyable_value("Copy facility name", _facility_record_field(record, FacilityProjectionField.FACILITY_NAME))}</h2>
        <p class="launch-value">{_escape(launch_value)}</p>
        <dl class="summary-list" aria-label="Primary facility facts">
          <dt>Facility ID</dt>
          <dd>{_render_copyable_value("Copy Facility ID", record.facility_number)}</dd>
          <dt>Facility type</dt>
          <dd>{_escape(_facility_record_field(record, FacilityProjectionField.FACILITY_TYPE))}</dd>
          <dt>Status</dt>
          <dd>{_escape(_facility_record_field(record, FacilityProjectionField.STATUS))}</dd>
          <dt>Address</dt>
          <dd>{_escape(_display_facility_address(record))}</dd>
          <dt>County</dt>
          <dd>{_escape(_facility_record_field(record, FacilityProjectionField.COUNTY))}</dd>
          <dt>Capacity</dt>
          <dd>{_escape(_facility_record_field(record, FacilityProjectionField.CAPACITY))}</dd>
        </dl>
        {_render_facility_conflict_note(record, (FacilityProjectionField.FACILITY_NAME, FacilityProjectionField.FACILITY_TYPE, FacilityProjectionField.STATUS, FacilityProjectionField.FULL_ADDRESS, FacilityProjectionField.COUNTY, FacilityProjectionField.CAPACITY))}
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
        <dd>{_escape(_facility_record_field(record, FacilityProjectionField.REGIONAL_OFFICE))}</dd>
        <dt>Closed date</dt>
        <dd>{_escape(_record_display_value(record, "closed_date", kind="date"))}</dd>
      </dl>
    </details>"""


def _display_facility_address(record: CcldFacilityLookupRecord) -> str:
    if record.identity_projection is not None:
        result = record.identity_projection.field(FacilityProjectionField.FULL_ADDRESS)
        street = projected_selected_text(
            record.identity_projection,
            FacilityProjectionField.FULL_ADDRESS,
        )
        location = _display_location(record)
        if street:
            return ", ".join(
                part
                for part in (
                    street,
                    location if location not in _STATE_TEXT_VALUES else "",
                )
                if part
            )
        if location not in _STATE_TEXT_VALUES:
            return location
        return present_facility_field(result).text
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
        "source_artifact_unavailable",
        "unsupported_layout",
        "conflicting_sources",
        "not_applicable",
        "null",
        "present_blank",
        "source_label_absent",
    )
    for state in state_priority:
        for value in presentations:
            if value.state == state:
                return value.display_text
    return presentation_value(state_hint="source_label_absent").display_text


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


def _render_copy_button(accessible_label: str, value: str) -> str:
    if not value:
        return ""
    return (
        f'<span class="copyable-value"><button class="copy-icon-button" type="button" '
        f'data-copy-value="{_escape(value)}" aria-label="{_escape(accessible_label)}" '
        f'title="{_escape(accessible_label)}">{_clipboard_icon_svg()}</button>'
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
        return status


def _render_facility_hub_not_found(facility_number: str) -> str:
        searched = facility_number if facility_number else "not provided"
        request_link = ""
        if facility_number.isdigit():
                request_link = f"""        <a class="button button-secondary" href="{_escape(_facility_request_href_for_values(facility_number=facility_number))}">Start complaint request</a>"""
        return f"""    <section class="empty-state-card" aria-labelledby="facility-hub-not-found-heading">
            <h2 id="facility-hub-not-found-heading">Facility-directory result not found</h2>
            <p>No active preloaded facility-directory row matched facility number <strong>{_escape(searched)}</strong>.</p>
            <p>Try a different search, enter the Facility ID directly, or report an issue if the lookup result is confusing.</p>
            <div class="action-group" aria-label="Facility Overview recovery actions">
                <a class="button" href="{CCLD_FACILITY_LOOKUP_PATH}">Back to search</a>
                {request_link}
            </div>
        </section>"""


def _render_facility_pattern_review_summary(
        record: CcldFacilityLookupRecord,
        review_context: CcldFacilityReviewContext,
) -> str:
        if review_context.complaints:
                return _render_governed_facility_review_summary(record, review_context)
        request_href = _facility_request_href(record)
        queue_href = f"{REVIEWER_UI_RECORDS_PATH}?{urlencode({'q': record.facility_number})}"
        if not review_context.has_loaded_context:
                empty_message = (
                    review_context.source_label
                    if review_context.source_label != "Loaded source-derived complaint records"
                    else "No loaded complaint records are currently available for this facility in the review context."
                )
                origin_markup = _render_facility_origin_context(review_context)
                return f"""    <section class="summary-card" aria-labelledby="facility-pattern-summary-heading">
            <h2 id="facility-pattern-summary-heading">Review summary</h2>
            <p>{_escape(empty_message)} This is not a public-source completeness conclusion.</p>
            {origin_markup}
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
                    <li><a href="{_escape(queue_href)}">Open Complaint Worklist filtered to this facility</a></li>
                    <li><a href="{_escape(request_href)}">Request or load records for this facility</a></li>
                </ul>
            </nav>
        </section>"""


def _render_governed_facility_review_summary(
    record: CcldFacilityLookupRecord,
    review_context: CcldFacilityReviewContext,
) -> str:
    request_href = _facility_request_href(record)
    finding_items = "\n".join(
        f'                  <li><a href="#{_facility_contributor_id("finding", label)}">'
        f'{_escape(_display_value(label))}: {count} exact complaint record(s)</a></li>'
        for label, count in review_context.finding_counts
    ) or "                  <li>Finding values are not available.</li>"
    serious_items = "\n".join(
        f'                  <li><a href="#{_facility_contributor_id("serious", label)}">'
        f'{_escape(label)}: {count} exact complaint record(s)</a></li>'
        for label, count in review_context.serious_topic_counts
    ) or "                  <li>No governed serious-review category is present in these complaint records.</li>"
    status_items = "\n".join(
        f'                  <li><a href="#{_facility_contributor_id("status", label)}">'
        f'{_escape(_reviewer_status_label(label))}: {count} complaint record(s)</a></li>'
        for label, count in review_context.reviewer_status_counts
    )
    if not review_context.reviewer_state_available:
        status_items = "                  <li>Reviewer-created status and note counts are unavailable.</li>"
    note_count = sum(item.reviewer_note_count for item in review_context.complaints)
    note_records = sum(item.reviewer_note_count > 0 for item in review_context.complaints)
    notes_markup = (
        f'<a href="#facility-hub-contributors-notes">{note_count} note(s) across '
        f'{note_records} complaint record(s)</a>'
        if review_context.reviewer_state_available and note_records
        else (
            "0 notes"
            if review_context.reviewer_state_available
            else "Reviewer-created note counts are unavailable."
        )
    )
    origin_markup = _render_facility_origin_context(review_context)
    timeline = _render_facility_activity_timeline(review_context)
    anomaly_markup = (
        '<ul class="compact-list">'
        + "".join(
            f'<li><a href="#facility-hub-contributors-trend">{_escape(cue)}</a></li>'
            for cue in review_context.anomaly_cues
        )
        + "</ul>"
        if review_context.anomaly_cues
        else "No governed monthly anomaly cue is present for the relevant dated records."
    )
    coverage_label = review_context.coverage_status.title()
    return f"""    <section class="summary-card" aria-labelledby="facility-pattern-summary-heading">
      <h2 id="facility-pattern-summary-heading">Review summary</h2>
      <p>This summary reconciles deduplicated loaded complaint records to the exact records below. Source facts and reviewer-created state remain separate.</p>
      {origin_markup}
      <div class="form-actions" aria-label="Primary facility review actions">
        <a class="button" href="{_escape(review_context.complaints[0].detail_href)}">Open recommended complaint</a>
        <a class="button button-secondary" href="#facility-hub-contributors-all">Open exact contributing complaints</a>
        <a class="button button-secondary" href="{_escape(request_href)}">Request records</a>
      </div>
      <div class="dense-fact-row" aria-label="Facility complaint summary">
        <div class="stat-card"><strong><a href="#facility-hub-contributors-all">{review_context.loaded_complaint_record_count}</a></strong><span>Deduplicated complaints</span></div>
        <div class="stat-card"><strong><a href="#facility-hub-contributors-source-available">{review_context.source_traceability_count}</a></strong><span>CCLD reports available</span></div>
        <div class="stat-card"><strong><a href="#facility-hub-contributors-review-flags">{review_context.delay_review_record_count + review_context.missing_date_record_count}</a></strong><span>Complaint records with review flags</span></div>
      </div>
      {timeline}
      <dl class="summary-list">
        <dt>{_inline_definition("Finding", "The outcome or status shown in a public complaint record.", "hub-finding")} distribution</dt>
        <dd><ul class="compact-list">
{finding_items}
        </ul></dd>
        <dt>{_inline_definition("Serious-review category", "A governed source category or cautious keyword-assisted review cue; it is not a legal conclusion.", "hub-serious-category")}</dt>
        <dd><ul class="compact-list">
{serious_items}
        </ul></dd>
        <dt>Trend or anomaly summary</dt>
        <dd>{anomaly_markup}</dd>
        <dt>{_inline_definition("Source coverage", "Whether contributing loaded complaint records include an original public-report link.", "hub-source-coverage")}</dt>
        <dd>{_escape(coverage_label)}: <a href="#facility-hub-contributors-source-available">{review_context.source_traceability_count} with a CCLD report</a>; <a href="#facility-hub-contributors-source-unavailable">{review_context.source_unavailable_count} without a report link</a>.</dd>
        <dt>Reviewer-created status counts</dt>
        <dd><ul class="compact-list">
{status_items}
        </ul></dd>
        <dt>Reviewer-created note count</dt>
        <dd>{notes_markup}</dd>
      </dl>
    </section>"""


def _render_facility_origin_context(
    review_context: CcldFacilityReviewContext,
) -> str:
    if not review_context.active_filters:
        return ""
    items = "\n".join(
        f"          <dt>{_escape(label)}</dt><dd>{_escape(value)}</dd>"
        for label, value in review_context.active_filters
    )
    return f"""      <details class="technical-details" open>
        <summary>Current review context</summary>
        <dl class="summary-list">
{items}
        </dl>
      </details>"""


def _render_facility_activity_timeline(
    review_context: CcldFacilityReviewContext,
) -> str:
    dated = tuple(
        item for item in review_context.complaints if item.activity_date != "unknown"
    )
    if not dated:
        return """      <section class="overview-timeline" aria-labelledby="facility-activity-range-heading">
        <h3 id="facility-activity-range-heading">Relevant complaint date range</h3>
        <p>Date not listed for the selected date field.</p>
      </section>"""
    milestones = [("Earliest", review_context.start_date)]
    if review_context.end_date != review_context.start_date:
        milestones.append(("Latest", review_context.end_date))
    items = "\n".join(
        f"          <li class=\"timeline-item\"><span class=\"timeline-marker timeline-marker--activity rt-timeline__marker\" aria-hidden=\"true\"></span><span class=\"timeline-label rt-timeline__label\">{label}</span><strong class=\"rt-timeline__date\">{_render_copyable_value(f'Copy {label.casefold()} relevant date', _display_date(value))}</strong></li>"
        for label, value in milestones
    )
    return f"""      <section class="overview-timeline" aria-labelledby="facility-activity-range-heading">
        <h3 id="facility-activity-range-heading"><a href="#facility-hub-contributors-dates">Relevant { _escape(review_context.date_dimension_label.casefold()) } range</a></h3>
        <div class="rt-timeline rt-timeline--linear">
          <div class="rt-timeline__line" aria-hidden="true"></div>
          <ol class="timeline-list timeline-list-linear rt-timeline__milestones" aria-label="Relevant complaint date range">
{items}
          </ol>
        </div>
      </section>"""


def _render_review_next_section(
        review_context: CcldFacilityReviewContext,
) -> str:
        if review_context.complaints:
                return _render_governed_review_next(review_context)
        if not review_context.has_loaded_context or not review_context.review_next_recommendations:
                return """    <section class="empty-state-card" aria-labelledby="review-next-heading">
            <h2 id="review-next-heading">Review next</h2>
            <p>No loaded records have review-next signals in this context.</p>
            <p>This only reflects the currently loaded records and does not imply source completeness or absence of problems.</p>
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


def _render_governed_review_next(
    review_context: CcldFacilityReviewContext,
) -> str:
    item = review_context.complaints[0]
    label = (
        item.complaint_control_number
        if item.complaint_control_number != "unknown"
        else item.stable_complaint_id
    )
    flags = _render_facility_complaint_flags(item)
    date_text = _display_date(item.activity_date) if item.activity_date != "unknown" else "Date not listed"
    return f"""    <section class="summary-card" aria-labelledby="review-next-heading">
      <h2 id="review-next-heading">Review next</h2>
      <p><strong>{_render_copyable_value("Copy recommended complaint or control number", label)}</strong></p>
      <p>Recommended because it has the most recent supported {_escape(review_context.date_dimension_label.casefold())}. When dates match or are unavailable, the stable source-derived record identity provides the deterministic tie order.</p>
      <dl class="summary-list">
        <dt>Date used</dt>
        <dd>{_render_copyable_value("Copy recommended complaint date", date_text)}</dd>
        <dt>Finding</dt>
        <dd>{_render_copyable_value("Copy recommended complaint finding", _display_value(item.finding))}</dd>
        <dt>Reviewer-created status</dt>
        <dd>{_render_copyable_value("Copy recommended complaint reviewer status", _reviewer_status_label(item.reviewer_status))}</dd>
      </dl>
      {flags}
      <div class="form-actions">
        <a class="button" href="{_escape(item.detail_href)}">Open recommended complaint {_escape(label)}</a>
        <a class="button button-secondary" href="#facility-hub-contributors-all">Open exact contributing complaints</a>
      </div>
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


def _render_facility_contributor_sections(
    review_context: CcldFacilityReviewContext,
) -> str:
    complaints = review_context.complaints
    if not complaints:
        return ""
    groups: list[tuple[str, str, tuple[CcldFacilityComplaintContext, ...]]] = [
        (
            "facility-hub-contributors-all",
            "All deduplicated contributing complaint records",
            complaints,
        ),
        (
            "facility-hub-contributors-dates",
            f"Complaint records contributing to the {review_context.date_dimension_label.casefold()} range",
            tuple(item for item in complaints if item.activity_date != "unknown"),
        ),
        (
            "facility-hub-contributors-review-flags",
            "Complaint records with review flags",
            tuple(
                item
                for item in complaints
                if item.strongest_delay_days or item.missing_dates or item.serious_topics
            ),
        ),
    ]
    groups.extend(
        (
            _facility_contributor_id("finding", label),
            f"Finding: {label}",
            tuple(item for item in complaints if item.finding == label),
        )
        for label, _count in review_context.finding_counts
    )
    groups.extend(
        (
            _facility_contributor_id("serious", topic),
            f"Serious-review category: {topic}",
            tuple(item for item in complaints if topic in item.serious_topics),
        )
        for topic, _count in review_context.serious_topic_counts
    )
    if review_context.anomaly_cues:
        groups.append(
            (
                "facility-hub-contributors-trend",
                "Dated complaint records contributing to the monthly trend summary",
                tuple(item for item in complaints if item.activity_date != "unknown"),
            )
        )
    groups.extend(
        (
            section_id,
            label,
            tuple(item for item in complaints if predicate(item)),
        )
        for section_id, label, predicate in (
            (
                "facility-hub-contributors-source-available",
                "Complaint records with an original CCLD report link",
                lambda item: item.source_available,
            ),
            (
                "facility-hub-contributors-source-unavailable",
                "Complaint records without an original CCLD report link",
                lambda item: not item.source_available,
            ),
        )
    )
    if review_context.reviewer_state_available:
        groups.extend(
            (
                _facility_contributor_id("status", status),
                f"Reviewer-created status: {_reviewer_status_label(status)}",
                tuple(item for item in complaints if item.reviewer_status == status),
            )
            for status, _count in review_context.reviewer_status_counts
        )
        if any(item.reviewer_note_count for item in complaints):
            groups.append(
                (
                    "facility-hub-contributors-notes",
                    "Complaint records with reviewer-created notes",
                    tuple(item for item in complaints if item.reviewer_note_count),
                )
            )
    rendered_groups = "\n".join(
        _render_facility_contributor_group(section_id, label, records)
        for section_id, label, records in groups
    )
    return f"""    <section aria-labelledby="facility-contributors-heading">
      <h2 id="facility-contributors-heading">Exact contributing complaints</h2>
      <p>Each summary value above links to the deduplicated complaint records used for that value.</p>
{rendered_groups}
    </section>"""


def _render_facility_contributor_group(
    section_id: str,
    label: str,
    complaints: tuple[CcldFacilityComplaintContext, ...],
) -> str:
    items = "\n".join(
        _render_facility_contributor_item(item) for item in complaints
    ) or "          <li>No exact complaint records contribute to this value.</li>"
    return f"""      <details id="{_escape(section_id)}" class="technical-details">
        <summary>{_escape(label)} ({len(complaints)})</summary>
        <ul class="compact-list contributor-list">
{items}
        </ul>
      </details>"""


def _render_facility_contributor_item(
    item: CcldFacilityComplaintContext,
) -> str:
    label = (
        item.complaint_control_number
        if item.complaint_control_number != "unknown"
        else item.stable_complaint_id
    )
    date_text = (
        _display_date(item.activity_date)
        if item.activity_date != "unknown"
        else "Date not listed"
    )
    source_markup = (
        f'<a href="{_escape(item.source_url_href)}">Open original CCLD report for {_escape(label)}</a> '
        f'{_render_copy_button("Copy original CCLD report URL", item.source_url_href)}'
        if item.source_available and item.source_url_href
        else "Original CCLD report link not available for this loaded complaint."
    )
    flags = _render_facility_complaint_flags(item)
    note_text = (
        f"{item.reviewer_note_count} reviewer-created note(s)"
        if item.reviewer_status != "unavailable"
        else "Reviewer-created note count unavailable"
    )
    return f"""          <li>
            <p><a href="{_escape(item.detail_href)}">Open complaint record {_escape(label)}</a> {_render_copyable_value("Copy complaint or control number", label)}</p>
            <dl class="summary-list">
              <dt>Date used</dt><dd>{_render_copyable_value("Copy complaint date", date_text)}</dd>
              <dt>Finding</dt><dd>{_render_copyable_value("Copy complaint finding", _display_value(item.finding))}</dd>
              <dt>Reviewer-created status</dt><dd>{_render_copyable_value("Copy reviewer-created status", _reviewer_status_label(item.reviewer_status))}</dd>
              <dt>Reviewer-created notes</dt><dd>{_escape(note_text)}</dd>
              <dt>CCLD source</dt><dd>{source_markup}</dd>
            </dl>
            {flags}
          </li>"""


def _render_facility_complaint_flags(
    item: CcldFacilityComplaintContext,
) -> str:
    labels: list[str] = []
    if item.strongest_delay_days:
        labels.append(f"{item.strongest_delay_days}+ day gap")
    if item.missing_dates:
        labels.append("Missing source date")
    labels.extend(item.serious_topics)
    if not labels:
        return ""
    badges = "".join(
        f'<li><span class="review-chip">{_escape(label)}</span></li>'
        for label in dict.fromkeys(labels)
    )
    return f'<ul class="flag-list" aria-label="Review flags">{badges}</ul>'


def _facility_contributor_id(group: str, value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "unknown"
    return f"facility-hub-contributors-{group}-{slug}"


def _inline_definition(term: str, definition: str, term_id: str) -> str:
    return render_inline_glossary_term(term, definition, term_id)


def _render_facility_hub_limitations(
    review_context: CcldFacilityReviewContext,
) -> str:
    if not review_context.complaints:
        return ""
    return """    <details class="technical-details">
      <summary>Coverage and interpretation limits</summary>
      <p>This page summarizes authorized loaded public records; it does not establish source completeness or a facility-wide conclusion. Missing and unavailable values remain distinct from zero. Review flags and serious-review categories are review cues, not legal conclusions.</p>
    </details>"""


def _render_facility_review_signals_section(
        summary: FacilityReviewSignalsSummary | None,
) -> str:
        if summary is None:
                return """    <section class="empty-state-card" aria-labelledby="facility-review-signals-heading">
            <h2 id="facility-review-signals-heading">Additional review signals</h2>
            <p>No supported public licensing, visit, citation, or Plan of Correction observations are available.</p>
            <p>This empty state does not mean the facility has no complaints, visits, citations, POC dates, or public-source records. Start a complaint request or return to facility lookup when you need a different facility context.</p>
        </section>"""
        cues = "\n".join(
                f"        <li>{_escape(_priority_filter_label(cue))}</li>" for cue in summary.review_cues
        )
        if not cues:
                cues = "        <li>No supported licensing or visit observation is present for this facility.</li>"
        return f"""    <section aria-labelledby="facility-review-signals-heading">
            <h2 id="facility-review-signals-heading">Additional review signals</h2>
            <p>These supported public licensing, visit, citation, and Plan of Correction counts and dates are review observations only. They are separate from loaded complaint records and are not legal findings or proof of source completeness.</p>
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
        f'<a class="button button-quiet" href="{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}?view=licensing-visit-activity">Clear Filters</a>'
        if active_set != {"all"}
        else ""
    )
    return f"""    <section class="workflow-panel compact-filter-panel" aria-labelledby="facility-priority-filter-heading">
      <h2 id="facility-priority-filter-heading">Filter</h2>
      <form action="{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}" method="get" class="compact-filter-form">
        <input type="hidden" name="view" value="licensing-visit-activity">
        <fieldset>
          <legend>Supported observations</legend>
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
    return """        <section class="quiet-section" aria-labelledby="licensing-visit-boundary-heading">
            <h2 id="licensing-visit-boundary-heading">How to use this information</h2>
            <p>These observations come from supported public licensing, visit, citation, and Plan of Correction summary fields. They remain separate from loaded complaint counts and do not establish complaint coverage.</p>
            <p>Use the visible observations to choose a facility for closer source review. They are not a hidden score or legal conclusion.</p>
        </section>"""


def _priority_filter_label(value: str) -> str:
    labels = {
        "all": "All supported observations",
        "Multiple signal types present": "Multiple supported observations",
        "Complaint visit activity present": "Complaint-related visit activity",
        "Citation indicator present": "Citation activity",
        "POC indicator present": "Plan of Correction activity",
        "Recent visit activity": "Recent visit activity",
        "High-capacity facility": "Capacity of 50 or more",
        "Closed status in uploaded summary": "Closed licensing status",
        "Long gap since last visit": "Last recorded visit before 2023",
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
            <h2 id="facility-priority-cards-heading">Observation summary</h2>
            <p>No supported observations are available.</p>
        </section>"""
    cards = "\n".join(
        _render_priority_card(cue, count, active_cues=active_cues, search_query=search_query)
        for cue, count in card_items
    )
    return f"""        <section aria-labelledby="facility-priority-cards-heading">
            <h2 id="facility-priority-cards-heading">Observation summary</h2>
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
    query_values["view"] = "licensing-visit-activity"
    return f"""                <article class="summary-card priority-summary-card">
                    <h3><a class="{active_class.strip()}" href="{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}?{_escape(urlencode(query_values))}">{_escape(_priority_filter_label(cue))}</a></h3>
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
        cue_rows = "        <dt>Supported observation groups</dt><dd>No supported licensing or visit observations available</dd>"
    return f"""    <section aria-labelledby="facility-priority-summary-heading">
      <div class="dense-section-header">
        <div>
          <p class="stage-kicker">Licensing and Visit Activity</p>
          <h2 id="facility-priority-summary-heading">Activity overview</h2>
        </div>
        <p class="helper-text">Use the observation counts to choose a Facility Overview, then request complaint records for the intended date range.</p>
      </div>
      <dl class="summary-list">
        <dt>Facilities with supported licensing or visit observations</dt>
        <dd>{len(signal_result.summaries)}</dd>
        <dt>Facilities shown under current filter</dt>
        <dd>{len(returned_summaries)} of {len(summaries)} matching facilit{"y" if len(summaries) == 1 else "ies"}</dd>
{cue_rows}
      </dl>
    </section>"""


def _render_priority_empty_rows(cue_filters: tuple[str, ...]) -> str:
    active_filters = tuple(cue for cue in cue_filters if cue and cue != "all")
    filter_text = (
        " with the selected review cues"
        if active_filters
        else ""
    )
    return f"""          <tr>
            <td colspan="4">
              <p>No licensing or visit activity is available for these filters{filter_text}.</p>
              <p>This does not mean facilities have no complaints, visits, citations, Plan of Correction dates, or public-source records. It only means the supported public licensing and visit information did not produce a visible row for this view.</p>
              <p><a href="{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}?view=licensing-visit-activity">Clear Filters</a></p>
            </td>
          </tr>"""


def _render_priority_row(summary: FacilityReviewSignalsSummary) -> str:
    cues = _priority_cues(summary)
    cue_text = "; ".join(_priority_filter_label(cue) for cue in cues) if cues else "No supported licensing or visit observations available"
    field_text = (
        f"{summary.total_visit_count} total visits; {summary.complaint_visit_count} complaint visits; "
        f"{summary.citation_count} citation value(s); {summary.poc_date_count} POC date(s); "
        f"last visit {_display_date(summary.last_visit_date)}; status {_display_tuple(summary.statuses)}; "
        f"capacity {_display_tuple(summary.capacities, kind='number')}"
    )
    facility_label = _safe_priority_text(summary.facility_name or "Facility name unavailable")
    return f"""          <tr>
            <th scope="row">
              {_escape(facility_label)}<br>
              <span class="helper-text">Facility ID {_escape(summary.facility_number)}</span>
            </th>
            <td>{_escape(cue_text)}</td>
            <td>{_escape(_safe_priority_text(field_text))}</td>
            <td><a href="{_escape(_facility_hub_href(summary.facility_number))}" aria-label="Open Facility Overview for {_escape(facility_label)}">Open Facility Overview</a></td>
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
        if review_context.complaints:
                return ""
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
            <form action="{CCLD_RECORD_REQUEST_PATH}" method="post" class="action-group" aria-label="Facility Overview actions">
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
                    <a class="button button-secondary" href="{REVIEWER_UI_RECORDS_PATH}?{_escape(urlencode({'q': record.facility_number}))}">Open Complaint Worklist filtered to this facility</a>
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
                aria_label="Facility Overview actions",
            )}
            <p class="helper-text">Date range needed before loaded records can be scoped.</p>
        </section>"""
        return f"""    <section aria-labelledby="facility-hub-actions-heading">
            <h2 id="facility-hub-actions-heading">Next actions</h2>
            {render_action_group(
                primary=ActionItem("Start complaint request", request_href),
                secondary=(ActionItem("Back to search", lookup_href),),
                aria_label="Facility Overview actions",
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
    if record.identity_projection is not None:
        city = projected_selected_text(
            record.identity_projection, FacilityProjectionField.CITY
        )
        state = projected_selected_text(
            record.identity_projection, FacilityProjectionField.STATE
        )
        zip_code = projected_selected_text(
            record.identity_projection, FacilityProjectionField.ZIP
        )
        city_state = ", ".join(part for part in (city, state) if part)
        location = " ".join(part for part in (city_state, zip_code) if part)
        if location:
            return location
        states = tuple(
            record.identity_projection.field(field).state
            for field in (
                FacilityProjectionField.CITY,
                FacilityProjectionField.STATE,
                FacilityProjectionField.ZIP,
            )
        )
        if FacilityValueState.UNAVAILABLE in states:
            return "Source unavailable"
        if FacilityValueState.BLANK in states:
            return "Blank in source"
        return "Not found in source"
    city_state = ", ".join(part for part in (record.city, record.state) if part)
    return " ".join(part for part in (city_state, record.zip_code) if part)


def _facility_record_field(
    record: CcldFacilityLookupRecord,
    field: FacilityProjectionField,
) -> str:
    if record.identity_projection is not None:
        return projected_display_text(record.identity_projection, field)
    if field is FacilityProjectionField.CAPACITY:
        return _record_display_value(record, "capacity", kind="number")
    fallback_by_field = {
        FacilityProjectionField.FACILITY_NAME: record.facility_name,
        FacilityProjectionField.PUBLIC_FACILITY_ID: record.facility_number,
        FacilityProjectionField.FACILITY_TYPE: record.facility_type,
        FacilityProjectionField.STATUS: record.status,
        FacilityProjectionField.FULL_ADDRESS: record.address,
        FacilityProjectionField.CITY: record.city,
        FacilityProjectionField.STATE: record.state,
        FacilityProjectionField.ZIP: record.zip_code,
        FacilityProjectionField.COUNTY: record.county,
        FacilityProjectionField.CAPACITY: record.capacity,
        FacilityProjectionField.ADMINISTRATOR: record.administrator,
        FacilityProjectionField.LICENSEE: record.licensee,
        FacilityProjectionField.TELEPHONE: record.telephone,
        FacilityProjectionField.REGIONAL_OFFICE: record.regional_office,
    }
    return _display_value(fallback_by_field[field])


def facility_lookup_display_text(
    record: CcldFacilityLookupRecord,
    field: FacilityProjectionField,
) -> str:
    return _facility_record_field(record, field)


def _render_facility_conflict_note(
    record: CcldFacilityLookupRecord,
    fields: Iterable[FacilityProjectionField],
) -> str:
    if record.identity_projection is None:
        return ""
    labels = {
        FacilityProjectionField.FACILITY_NAME: "name",
        FacilityProjectionField.FACILITY_TYPE: "type",
        FacilityProjectionField.STATUS: "status",
        FacilityProjectionField.FULL_ADDRESS: "address",
        FacilityProjectionField.COUNTY: "county",
        FacilityProjectionField.CAPACITY: "capacity",
    }
    conflicts = tuple(
        labels.get(field, field.value.replace("_", " "))
        for field in fields
        if record.identity_projection.field(field).conflict
    )
    if not conflicts:
        return ""
    return (
        '<p class="helper-text facility-identity-conflict">Source records differ for '
        f"{_escape(', '.join(conflicts))}. Current reference values are shown when "
        "the projection can select one safely; complaint-time values remain preserved.</p>"
    )


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
            "n": _facility_record_field(record, FacilityProjectionField.FACILITY_NAME),
            "city": _facility_record_field(record, FacilityProjectionField.CITY),
            "state": _facility_record_field(record, FacilityProjectionField.STATE),
            "co": _facility_record_field(record, FacilityProjectionField.COUNTY),
            "zip": _facility_record_field(record, FacilityProjectionField.ZIP),
            "t": _facility_record_field(record, FacilityProjectionField.FACILITY_TYPE),
            "p": record.program_type,
            "cap": _facility_record_field(record, FacilityProjectionField.CAPACITY),
            "s": _facility_record_field(record, FacilityProjectionField.STATUS),
            "ss": _facility_field_state(record, FacilityProjectionField.STATUS),
            "sc": _facility_field_conflict(record, FacilityProjectionField.STATUS),
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
    if source.source_kind in {
        "postgres_facility_reference",
        "postgres_transparencyapi_reference",
    }:
        return CCLD_FACILITY_SUGGESTIONS_PATH
    return ""


def _facility_suggestions_payload(
    query: str,
    reference_source: CcldFacilityReferenceSource | None,
    *,
    lookup_result: CcldFacilityLookupResult | None = None,
) -> dict[str, Any]:
    reference_source = project_ccld_facility_reference_source(
        reference_source or load_active_ccld_facility_reference()
    )
    if (
        lookup_result is not None
        and reference_source.source_kind == "postgres_transparencyapi_reference"
    ):
        result = lookup_result
    else:
        result = (
            project_ccld_facility_lookup_result(lookup_result, reference_source)
            if lookup_result is not None
            else search_ccld_facilities(
                query,
                reference_source.records,
                reference_source=reference_source,
            )
        )
    return {
        "query": result.query,
        "total_match_count": result.total_match_count,
        "result_limit": result.result_limit,
        "records": _facility_json_records(result.returned_records),
    }


def _facility_json_records(
    records: Iterable[CcldFacilityLookupRecord],
) -> list[dict[str, str | bool | None]]:
    return [
        {
            "num": record.facility_number,
            "n": _facility_record_field(record, FacilityProjectionField.FACILITY_NAME),
            "city": _facility_record_field(record, FacilityProjectionField.CITY),
            "state": _facility_record_field(record, FacilityProjectionField.STATE),
            "co": _facility_record_field(record, FacilityProjectionField.COUNTY),
            "zip": _facility_record_field(record, FacilityProjectionField.ZIP),
            "t": _facility_record_field(record, FacilityProjectionField.FACILITY_TYPE),
            "p": record.program_type,
            "cap": _facility_record_field(record, FacilityProjectionField.CAPACITY),
            "s": _facility_record_field(record, FacilityProjectionField.STATUS),
            "ss": _facility_field_state(record, FacilityProjectionField.STATUS),
            "sc": _facility_field_conflict(record, FacilityProjectionField.STATUS),
            "ts": _facility_field_state(record, FacilityProjectionField.FACILITY_TYPE),
            "tc": _facility_field_conflict(record, FacilityProjectionField.FACILITY_TYPE),
            "address": _facility_record_field(record, FacilityProjectionField.FULL_ADDRESS),
            "regional_office": _facility_record_field(record, FacilityProjectionField.REGIONAL_OFFICE),
        }
        for record in records
    ]


def _facility_field_state(
    record: CcldFacilityLookupRecord,
    field: FacilityProjectionField,
) -> str:
    if record.identity_projection is None:
        return FacilityValueState.POPULATED.value if _facility_record_field(record, field) else FacilityValueState.ABSENT.value
    return record.identity_projection.field(field).state.value


def _facility_field_conflict(
    record: CcldFacilityLookupRecord,
    field: FacilityProjectionField,
) -> bool:
    return bool(
        record.identity_projection is not None
        and record.identity_projection.field(field).conflict
    )


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
