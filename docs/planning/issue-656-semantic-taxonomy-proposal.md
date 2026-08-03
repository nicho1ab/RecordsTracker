# Issue #656 semantic taxonomy and mapping proposal

## Status and decision gate

This is an evidence-bounded proposal with a limited owner-approved
implementation boundary. It records the current implementation and a shared
treatment so that the authorized change does not silently normalize source
values, alter review-topic derivation, or introduce cross-site chip colors.

The Issue #656 owner clarification requires this proposal before either of the
following changes:

- a production review-topic derivation rule; or
- cross-site chip-color styling.

The repository's reviewer-design governance still requires an approved design
package and a numbered page-change inventory before a material reviewer-facing
redesign. Neither is supplied by this issue. The owner approval below therefore
authorizes only bounded semantic rendering and regression work; it does not
authorize source-derived-record, schema, connector, CSS, design-token, or
material redesign changes.

## Owner approval (2026-08-02)

The owner approved implementation only within the current Issue #656 prompt:
separate complaint status from findings; use the three canonical finding labels;
use the six approved category-backed topic labels; preserve keyword-only
evidence as `Possible keyword cue`; keep source/data and reviewer-workflow
states distinct; and remove visible 120-day rendering while retaining the
stored analytical flag. New semantic color tokens and a stronger adverse
substantiated treatment remain deferred. The approval does not authorize a new
investigation-status or disposition mapping, topic/severity derivation, source
ingestion change, production-data change, or material page redesign.

## Evidence basis and inventory boundary

The current local loaded corpus is
`tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json`. It is a
validated, tiny, fixture-only corpus: one complaint, two allegations, one
investigation activity event, and one source document. It is not a complete
live complaint corpus and cannot establish production completeness, prevalence,
or the authority of a proposed safety-severity tier.

The inventory below also records values present in governed fixture files and
currently supported code paths. A value listed as a code path, test probe, or
unresolved source value is not a claim that it occurred in the loaded corpus.
Source text and raw values remain internal/source-derived; a display mapping
does not rewrite them.

## Observed fixture values

| Domain | Exact observed source/internal value | Current user-facing label and locations | Current component/styling | Proposed canonical category and treatment | Authority and preservation rule |
| --- | --- | --- | --- | --- | --- |
| Complaint status | No complaint-status field is present in the loaded corpus. | None. The facility-intelligence renderer nevertheless recognizes `active`, `pending`, `uninvestigated`, `not determined`, and `not yet determined` when they appear in the legacy `finding` field. | Those values are rendered as `Finding not provided` with `finding-badge--unavailable`. | **Complaint status**; labeled fact, not a finding. Preserve the received value as text after the `Complaint status` label. | No canonical complaint-status field is approved by `DATA_CONTRACT.md`; do not infer a finding from the legacy field. |
| Investigation status | No investigation-status field/value is present in the loaded corpus or current complaint fixture contract. | None. | None. | **Investigation status**; labeled fact, not a finding. Omit when not supplied. | Requires a source-field and data-contract decision before normalization. |
| Allegation finding | `Unsubstantiated` in the complaint and both allegation fixture records. Governed fixture files also exercise `Substantiated`, `Inconclusive`, `Deficiency cited`, and `No deficiency cited`. | `Unsubstantiated` is shown in complaint detail, queue/worklist, packet preview, facility intelligence, and serious-topic worklist. | Detail uses `finding-badge--unsubstantiated`; generic queue/aggregate helpers use `review-chip badge-info`; facility intelligence may use `finding-badge`. | **Finding**. `Substantiated`: semantic adverse chip; `Unsubstantiated`: semantic non-adverse finding chip; `Inconclusive`: semantic unresolved-finding chip. `Deficiency cited` and `No deficiency cited` remain source-derived labeled facts until separately mapped. | `DATA_CONTRACT.md` and `docs/user/data-dictionary.md` govern normalized findings; source values are retained. |
| Disposition | `pending_policy` appears in a governed fixture. No complaint disposition is in the loaded corpus. | No reviewer rendering located. | None. | **Disposition**; labeled fact only when a governed source field is available. Do not convert it to a finding or workflow state. | Unsupported for current complaint UI; preserve raw value without inventing a readable label. |
| Review topic | Source `Staff conduct` maps to internal `Staff-conduct topic`; source `Inadequate supervision` maps to `Supervision topic`. | Facility intelligence locally changes them to `Staff misconduct` and `Supervision`; serious-topic worklist exposes internal labels and `Possible keyword cue`. | `review-chip` in facility cards; plain table text in serious-topic worklist. | **Review topic**. A chip displays the normalized value: `Staff misconduct`, `Supervision`, `Mistreatment`, `Care omission`, `Medication or medical care`, or `Runaway or AWOL`. | Current mapping is source-category normalization, not a complete corpus taxonomy. Keep source category and matched field/term auditable. |
| Review topic, keyword cue | Code recognizes bounded cues: `sexual assault`, `abuse`, `mistreatment`, `neglect`, `supervision`, `unsupervised`, `unattended`, `medication`, `medical care`, `runaway`, `awol`, `staff misconduct`, `injury`, and `restraint`; it excludes policy/training and prevention phrases. | `Possible keyword cue` in the serious-topic worklist/filter. | Plain table text/filter option. | **Possible keyword cue**; warning/labeled fact with matching evidence, never a specific severe topic or severity tier. | Owner clarification prohibits unsupported inference and requires a complete loaded-corpus audit before changing derivation. |
| Source availability | Loaded source URL is present; fixture source is available. Current code also recognizes `unknown`, `unavailable`, `not available`, and a missing URL. | `CCLD source available`, `Source not available`, `Source unavailable`, and `Source link unavailable` appear on worklist, detail, packet, and facility views. | Mix of `source-chip`, `review-chip`, and `badge-danger`. | **Source state**. `Available`: semantic source chip; `Unavailable`: warning; absent source URL: warning with the distinct reason; unknown raw text remains a labeled fact. | `DATA_CONTRACT.md` requires separate source-artifact-unavailable and source-label-absent states. Do not treat either as numeric zero or a finding. |
| Source/data state | Fixture and contracts distinguish null/unknown, source label absent, source artifact unavailable, unsupported layout, present-but-not-extracted, conflicting sources, unresolved raw code, invalid, and extraction failed. | Presentation labels are governed centrally for field values but review cues currently collapse several meanings into generic chips. | Mixed plain text, source warnings, and field presentation markup. | **Source/data state**. Use the existing typed presentation-value label as a labeled fact or warning; preserve `unknown`, `unavailable`, `conflicting`, `unresolved_raw_code`, `extraction_failed`, `missing`, and `not_applicable` separately. | `DATA_CONTRACT.md`; no invented label for an unresolved source code. |
| Activity type | `investigation_activity` for the fixture event. | The detail timeline calls it `First investigation activity`; activity type itself is not a general chip. | Labeled timing fact. | **Activity type**; labeled fact in the timeline. Unknown activity types remain source text or are omitted if not useful to the reviewer task. | `SOURCE_CONNECTOR_CONTRACT.md` and the event fixture; no new canonical activity taxonomy is approved. |
| Timing/delay cue | Fixture flags: all `review_delay_over_30_days`, `60`, `90`, and `120` are `false`; fixture values include true 30- and 60-day flags and missing/proxy states. The loaded record has 7 days received-to-first-activity and 139 days received-to-visit/report. | `30+`, `60+`, `90+`, and `120+ day gap`; `Missing first activity`, `Missing source date`, and `Date mismatch`. | `review-chip badge-attention badge-attention--warning` for a day gap; danger chip for source/date warnings. | **Timing cue**. Retain the stored interval as a labeled fact. Use source-supported missing/proxy/mismatch warnings. See the 120-day decision below. | `docs/user/data-dictionary.md` defines the flags as screening flags, not a conclusion that an investigation was delayed. |

## Current rendering inventory

The affected reviewer renderers are intentionally listed before any shared
component is introduced:

| Surface | Current rendering mechanisms | Observed inconsistency/risk |
| --- | --- | --- |
| Compare Facilities and Facility Review Hub | `reviewer_ui.py`: `_render_facility_intelligence_topics`, `_facility_intelligence_topic_label`, `_facility_intelligence_finding_markup`, `_render_facility_intelligence_badges`, and `_render_facility_intelligence_recommended_complaint`; `ccld_facility_lookup.py`: facility complaint flags and pattern-summary finding/status items. | Local topic relabeling; status-like source values can become `Finding not provided`; findings, topics, timing, and source availability share generic `review-chip` styling. |
| Complaint queue and worklist | `reviewer_ui.py`: `_render_queue_record_badges`, `_render_worklist_review_flags`, `_worklist_source_chip`, `_render_review_flag_chips`, `_review_flag_chip_class`, and `_review_chip_markup`. | One label-only classifier assigns class names across findings, workflow values, source states, and timing cues, making the input domain implicit. |
| Complaint detail | `reviewer_ui.py`: `_finding_badge`, `_render_allegations_findings_section`, `_render_overview_review_cues`, `_source_availability_chip`, `_source_warning_labels`, and the timing section. | Finding badges are more specific than generic queue chips; timing and source evidence require a distinct state contract. |
| Packet preview and exports | `reviewer_ui.py`: `_packet_preview_record_badges`, `_render_packet_preview_record`, and complaint/facility export helpers. | Packet cues reuse label-based chip classes; CSV/export wording must preserve raw source values rather than use display-only labels. |
| Serious-topic worklist | `reviewer_ui.py`: `_serious_topic_evidence`, `_render_serious_topic_row`, and `_render_serious_topics_filter_form`; `source_derived_reads.py`: serious-category and bounded-keyword expressions. | Category normalization and keyword cues are different evidence types, but the route exposes both alongside generic topic text. |

## Proposed shared semantic contract

The following contract is proposed for owner/design approval. It is not an
implementation authorization.

| Domain | Supported value/state | Canonical reviewer label | Component treatment | Semantic category |
| --- | --- | --- | --- | --- |
| Finding | `substantiated` | Substantiated | Semantic finding chip with icon/text; strong adverse treatment and contrast verification required | adverse finding |
| Finding | `unsubstantiated` | Unsubstantiated | Semantic finding chip with icon/text | non-adverse finding |
| Finding | `inconclusive` | Inconclusive | Semantic finding chip with icon/text | unresolved finding |
| Finding | absent/unknown raw value | Unknown finding or the governed typed-value label | Labeled fact, not an adverse chip | unknown finding |
| Complaint status | `active` | Active | Labeled fact under `Complaint status` | active workflow/source status |
| Complaint status | `pending` | Pending | Labeled fact under `Complaint status` | pending workflow/source status |
| Complaint status | `uninvestigated` | Uninvestigated | Labeled fact under `Complaint status` | uninvestigated workflow/source status |
| Complaint or investigation status | `not determined` | Not determined | Labeled fact under the actual status domain | unresolved status |
| Complaint or investigation status | `not yet determined` | Not yet determined | Labeled fact under the actual status domain | pending determination |
| Review topic | normalized supported value | Normalized topic value (for example, Staff misconduct or Supervision) | Semantic topic chip with visible text | review topic |
| Topic evidence | keyword-only evidence | Possible keyword cue | Warning/labeled fact with matching field and term | screening cue |
| Source/data state | unavailable | Source unavailable | Warning with non-color text | unavailable source |
| Source/data state | missing/source label absent | Not listed in source or No value recorded, as supplied by the typed presentation state | Labeled fact | missing or absent |
| Source/data state | unknown | Unknown | Labeled fact | unknown |
| Source/data state | contradictory/conflicting | Sources differ | Warning/labeled fact | contradictory |
| Source/data state | extraction failed | Data processing incomplete | Warning/labeled fact | extraction failed |
| Source/data state | unresolved raw code | Raw value preserved; no descriptive label | Labeled fact or intentionally omitted when not useful | unresolved raw code |
| Timing | supported date/proxy/missing mismatch | Existing governed field label | Labeled fact or source warning | timing evidence |
| Reviewer-created workflow state | existing `REVIEWER_STATUS_VALUES` | Existing reviewed-state label | Separate labeled fact/chip family | reviewer-created state |

`missing`, `unavailable`, `unknown`, `contradictory`, `extraction failed`,
`unresolved raw code`, and `not yet determined` are distinct semantic states.
They must not share a normalization key, fall through to one display label, or
be promoted to a finding. A future shared renderer must take both a domain and
a state/value; it must not classify a bare display string.

## Review-topic provenance and severity proposal

Current category-backed review topics are rule-based normalizations of the
source-derived `allegation_category` field. Current keyword matching is a
bounded screening aid over `allegation_text` only when category is empty or
unknown. It produces `Possible keyword cue`, not a named topic. The loaded
fixture supports only `Staff conduct` and `Inadequate supervision`; it does not
support a claim that the other mapped categories occur in the live corpus.

Before proposing high-impact categories for sexual abuse or exploitation,
illegal drugs or substance exposure, physical abuse, neglect, unsafe restraint,
weapons, trafficking, serious medical neglect, or another severe category, the
owner review must have a complete authorized-corpus audit that records the
source field/text trigger, count, exclusions, false-positive risk, and the
reviewer-facing evidence link. No severity tier, safety conclusion, or
topic-specific chip is approved from a loose keyword match.

## Timing-cue decision: 120 days before first visit

The repository currently stores the `review_delay_over_120_days` screening flag
and the user data dictionary defines it as **more than** 120 days on the
earliest available deterministic delay basis. It is therefore not a `120 or
more` threshold, and it does not specifically mean "before first visit". The
loaded fixture's 139-day received-to-visit interval does not set that flag,
which demonstrates why the actual flag basis must be shown rather than inferred
from another interval.

The field has governed data semantics as a screening flag, but no approved
visual attention-chip authority for the 120-day condition. Per the Issue #656
owner clarification, it must have **no visible chip or severity color** at this
time. A later approved display would need to name the exact stored flag, its
earliest-available date basis, source dates, proxy/missing/contradiction state,
and cautious non-conclusory wording. Missing, unavailable, contradictory, and
not-yet-determined dates must show their own typed source/data state instead of
creating a timing cue.

## Required approval before implementation

Owner and design approval must resolve all of the following before a follow-on
implementation applies this proposal:

1. Approve or reject the proposed domain/state/component matrix and the strong
   adverse finding treatment.
2. Supply the approved design package, requirement IDs, and numbered
   page-change inventory for each affected reviewer route.
3. Authorize a complete loaded-corpus topic audit and identify its allowed
   data-access boundary.
4. Approve any new topic derivation, severity tier, or semantic color token.
5. Decide whether legacy `finding` values that are actually complaint or
   investigation statuses have a governed source field/normalization path, or
   must remain a visibly labeled legacy source value.

Until then, unresolved source codes, unsupported dispositions, unobserved
statuses, keyword cues, and absent values are preserved rather than normalized.

## Repository audit evidence (2026-08-02)

This audit searched application and rendering helpers, the shared shell CSS,
connector/allocation code, schemas and migrations as historical context,
fixture and synthetic records, unit/integration tests, exports, user
documentation, accessibility/design requirements, approved decisions, and
ADRs. It found no complete production complaint corpus in the repository. The
counts below are therefore distinct repository-observed or code-supported
values, not live-corpus prevalence.

| Domain | Distinct values or states found | Audit result |
| --- | ---: | --- |
| Complaint status | 5 | `active`, `pending`, `uninvestigated`, `not determined`, and `not yet determined` occur only in legacy finding-renderer handling; there is no canonical complaint-status field. |
| Investigation status | 0 | No discrete investigation-status field or supported value was found. `investigation_findings_narrative` is narrative, not status. |
| Finding | 8 | `Substantiated`, `Unsubstantiated`, `Inconclusive`, `Unknown`, `Founded`, `Sustained`, `Deficiency cited`, and `No deficiency cited`. Only the first three have a current finding-badge treatment; `Founded`/`Sustained` are qualification equivalents, not proven display synonyms. |
| Disposition | 1 | `pending_policy` occurs in a governance fixture, not as a complaint disposition. No reviewer-facing complaint-disposition field was found. |
| Raw source categories | 6 | `Abuse or mistreatment`, `Neglect`, `Inadequate supervision`, `Medication or medical care`, `Runaway or AWOL`, and `Staff conduct`. |
| Internal normalized topics | 6 | `Mistreatment-topic`, `Care-omission topic`, `Supervision topic`, `Medication/medical-care topic`, `Runaway/AWOL topic`, and `Staff-conduct topic`. |
| Bounded keyword cues | 14 | `sexual assault`, `abuse`, `mistreatment`, `neglect`, `supervision`, `unsupervised`, `unattended`, `medication`, `medical care`, `runaway`, `awol`, `staff misconduct`, `injury`, and `restraint`; they produce only `Possible keyword cue`. |
| Source-availability wording | 5 | `CCLD source available`, `Source available`, `Source not available`, `Source unavailable`, and `Source link unavailable`. |
| Typed presentation states | 20 | Includes `present`, `verified_zero`, `present_blank`, `null`, `source_label_absent`, `source_artifact_unavailable`, `not_applicable`, `undated`, `invalid`, `unsupported_layout`, `explicit_unknown`, lineage states, `conflicting_sources`, `intentionally_internal`, and `source_pending`. |
| Facility projection states | 9 | `populated`, `blank`, `absent`, `unavailable`, `unresolved_raw_code`, `conflicting`, `internal_only`, `invalid`, and `extraction_failed`. |
| Source confidence | 3 numeric fixture values | `0.9`, `0.95`, and `1.0`; confidence is support/operator context, not a reviewer finding or severity label. |
| Activity type | 1 | `investigation_activity`, rendered as the distinct First investigation activity milestone when supported. |
| Timing flags | 4 | `review_delay_over_30_days`, `60`, `90`, and `120`, plus `missing_first_activity_date` and `report_date_used_as_proxy`. |
| Reviewer-created workflow states | 5 | `not_started`, `in_review`, `needs_follow_up`, `reviewed`, and `blocked`; these are distinct from source-derived statuses and findings. |

### Material audit corrections and conflicts

1. The earlier proposal correctly identified local topic relabeling, but the
   audit establishes that the serious-topic route also exposes the internal
   hyphenated topic strings. A shared display mapping must therefore cover both
   Facility Intelligence and the serious-topic route; it cannot assume the
   facility-card helper is the only renderer.
2. The current `_review_flag_chip_class` uses one label-only classifier for
   findings, source states, timing cues, reviewer workflow states, and generic
   fallback text. That is direct evidence for the proposed domain-plus-value
   renderer; a string-only mapping cannot reliably keep these categories apart.
3. Existing detail finding badges and generic queue chips render the same
   finding with different components/classes. Existing `Substantiated` styling
   is amber (`finding-badge--substantiated`), not a documented strong adverse
   token. Its contrast and adverse meaning require design approval rather than
   a silent CSS change.
4. The original proposal understated an existing conflict with the owner
   clarification: `30+`, `60+`, `90+`, and `120+ day gap` are currently
   rendered as attention chips in queue, detail, packet, and facility paths.
   The owner specifically withheld approval for the 120-day chip. This audit
   does not change that behavior.
5. `Unknown`, missing/null, source unavailable, source pending, conflicting,
   unresolved raw code, invalid, and extraction failed have distinct typed
   evidence states. A visible fallback such as `Finding not provided` for a
   legacy status-like value conflicts with those distinctions and must not be
   normalized without an actual source-domain decision.

### Audited 120-day threshold

`DATA_CONTRACT.md` and the CCLD connector define the four delay flags. The
connector selects the earliest available deterministic delay basis in this
order: complaint received to first investigation activity, then complaint
received to visit, then complaint received to report only when neither earlier
date is available. `_review_delay_over` uses strict `>` comparison, so the
flag means **more than 120 days**, not 120 or more days and not necessarily
before the first visit. `missing_first_activity_date` and
`report_date_used_as_proxy` identify two conditions that require cautious
interpretation; a typed missing, unavailable, invalid, or conflicting date
state likewise prevents a reliable display.

The evidence supports an analytical screening flag only. It does not establish
a legal, regulatory, or approved product-severity threshold. The owner has
explicitly withheld authority for a visible 120-day chip or severity color;
the recommended current treatment is omission from reviewer chips and
retention of the stored flag/source-backed timing facts for later, approved
analysis. No alternative numerical threshold is supported by repository
evidence.
