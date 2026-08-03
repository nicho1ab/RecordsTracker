# Issue #656 owner decisions

## Owner approval (2026-08-02)

The determinations below authorize implementation only within the current
Issue #656 prompt. Decisions 9 and 10 remain deferred. Decision 13 is revised
to retain only the 30-, 60-, and 90-day analytical screening cues, and decision
15 is revised to require deterministic bounded synthetic/unit coverage for
every implemented mapping or state. This approval does not authorize new color
tokens, a stronger adverse style, a source-derived topic/severity derivation,
schema or connector work, production-data changes, or a material redesign.

## 1. Canonical complaint-status terminology

- Current inconsistency: `active`, `pending`, `uninvestigated`, `not determined`, and `not yet determined` can be treated as a missing finding.
- Repository evidence: the legacy finding renderer recognizes those five strings; no canonical complaint-status field exists.
- Recommended decision: retain exact source text under **Complaint status** only after a governed source-field decision.
- Alternatives considered: normalize them as findings; hide all status-like values.
- User-visible effect: no complaint status is called a finding.
- Implementation effect: a domain-aware renderer replaces label-only finding fallback.
- Risk if deferred: status/finding conflation remains.
- Owner decision: APPROVE

## 2. Canonical investigation-status terminology

- Current inconsistency: investigation narrative can be mistaken for a status.
- Repository evidence: `investigation_findings_narrative` exists; no discrete investigation-status field/value exists.
- Recommended decision: do not invent an investigation-status vocabulary; render a future supported value as **Investigation status**.
- Alternatives considered: derive status from narrative; omit the domain permanently.
- User-visible effect: no unsupported investigation classification.
- Implementation effect: no mapping until source evidence is approved.
- Risk if deferred: future pages may create incompatible status labels.
- Owner decision: APPROVE

## 3. Canonical allegation-finding terminology

- Current inconsistency: detail uses finding badges while queue/aggregate paths use generic chips.
- Repository evidence: `Substantiated`, `Unsubstantiated`, and `Inconclusive` are the current badge values; `Founded`/`Sustained` qualify aggregate logic but are not approved display synonyms.
- Recommended decision: retain the three source-derived labels verbatim and treat other values as labeled source facts pending evidence.
- Alternatives considered: display equivalence labels; collapse inconclusive into unknown.
- User-visible effect: a finding means the same thing on every page.
- Implementation effect: one finding component with explicit value mapping.
- Risk if deferred: conflicting visual and semantic meaning persists.
- Owner decision: APPROVE

## 4. Treatment of dispositions

- Current inconsistency: `pending_policy` exists only in governance fixtures and has no complaint UI meaning.
- Repository evidence: no complaint-disposition field or renderer was found.
- Recommended decision: preserve dispositions as raw/labeled source facts only when a governed field exists; otherwise omit.
- Alternatives considered: reuse workflow or finding labels.
- User-visible effect: no invented disposition label.
- Implementation effect: no current production change.
- Risk if deferred: future code may overload a governance value as a complaint fact.
- Owner decision: APPROVE

## 5. Review-topic normalization and displayed wording

- Current inconsistency: raw categories, internal `*-topic` strings, and facility-card labels differ.
- Repository evidence: six raw categories map to six internal normalized values; keyword matches produce `Possible keyword cue` only.
- Recommended decision: display normalized labels such as **Staff misconduct** and **Supervision**, while retaining source category and matched evidence.
- Alternatives considered: display raw categories everywhere; infer high-impact topics from keywords.
- User-visible effect: readable, consistent review-topic chips with auditable basis.
- Implementation effect: shared topic display mapping across both topic routes.
- Risk if deferred: a topic has different wording across pages.
- Owner decision: APPROVE

## 6. Source availability and source-state distinctions

- Current inconsistency: five availability phrases and multiple data-state labels appear across routes.
- Repository evidence: typed presentation states distinguish source absence, unavailable artifact, unknown, and source pending.
- Recommended decision: use **Source available** and **Source unavailable** only for availability; render the typed reason separately.
- Alternatives considered: one generic unavailable label.
- User-visible effect: reviewers can distinguish no source, unavailable source, and a source field not listed.
- Implementation effect: source-state component accepts typed state, not a bare label.
- Risk if deferred: source completeness claims become misleading.
- Owner decision: APPROVE

## 7. Missing-state distinctions

- Current inconsistency: generic chips can collapse missing/null, unknown, unavailable, conflicting, extraction-failed, and pending states.
- Repository evidence: 20 presentation states and nine facility-projection states expressly preserve these distinctions.
- Recommended decision: retain each typed state and its existing governed label; do not normalize across state families.
- Alternatives considered: generic `Not provided`.
- User-visible effect: reason for absence remains visible.
- Implementation effect: explicit state enum/renderer tests.
- Risk if deferred: material source/data failures are hidden.
- Owner decision: APPROVE

## 8. Shared component categories

- Current inconsistency: finding badges, review chips, source chips, status badges, warnings, and plain facts overlap by label.
- Repository evidence: `_review_flag_chip_class` categorizes from display text alone.
- Recommended decision: create separate shared renderers for finding, source/data state, review topic, reviewer workflow state, timing evidence, and labeled fact.
- Alternatives considered: extend the string classifier.
- User-visible effect: component meaning is consistent and understandable.
- Implementation effect: route migration and cross-page regression coverage.
- Risk if deferred: new labels bypass semantic governance.
- Owner decision: APPROVE

## 9. Shared semantic visual categories and token intent

- Current inconsistency: generic chip classes represent unrelated domains.
- Repository evidence: current CSS has info, attention, danger, source, and finding classes; design rules require approved semantic tokens and non-color meaning.
- Recommended decision: approve token intent by domain, with text/icon/accessible name, before any CSS migration.
- Alternatives considered: retain page-local colors; apply a generic palette.
- User-visible effect: visual category never replaces wording.
- Implementation effect: requires approved design package and contrast evidence.
- Risk if deferred: cross-site color drift.
- Owner decision: DEFER

## 10. Substantiated adverse styling

- Current inconsistency: `Substantiated` is amber in detail but info-styled in generic chips.
- Repository evidence: `finding-badge--substantiated` is amber; no approved strong-adverse token is named.
- Recommended decision: approve a strong adverse finding treatment with contrast and text/icon semantics.
- Alternatives considered: retain amber; use generic danger style.
- User-visible effect: substantiated finding is visually distinct without implying a new legal conclusion.
- Implementation effect: design token and accessibility validation required.
- Risk if deferred: adverse meaning remains inconsistent.
- Owner decision: DEFER

## 11. Unsubstantiated and inconclusive styling

- Current inconsistency: detail classes differ from generic queue chips.
- Repository evidence: unsubstantiated is neutral and inconclusive/unknown are info styled in detail.
- Recommended decision: keep separate non-adverse and unresolved-finding categories; do not collapse inconclusive into unknown.
- Alternatives considered: one neutral class; adverse styling for all findings.
- User-visible effect: source outcome remains readable and distinct.
- Implementation effect: shared finding mapping and tests.
- Risk if deferred: inconclusive findings lose meaning.
- Owner decision: APPROVE

## 12. Workflow-state styling

- Current inconsistency: reviewer-created states can enter generic review-chip handling.
- Repository evidence: five actual states (`not_started`, `in_review`, `needs_follow_up`, `reviewed`, `blocked`) are separate reviewer-created data.
- Recommended decision: use a dedicated workflow-state component family, separate from source facts and findings.
- Alternatives considered: share source-status chips.
- User-visible effect: reviewers can tell saved workflow progress from source content.
- Implementation effect: preserve existing write/read semantics while changing rendering only.
- Risk if deferred: reviewer state may be mistaken for source status.
- Owner decision: APPROVE

## 13. Timing-cue treatment

- Current inconsistency: all threshold flags render as attention chips while proxy/missing/mismatch use separate warnings.
- Repository evidence: stored flags are screening aids; source date basis has ordered fallbacks.
- Recommended decision: retain the 30-, 60-, and 90-day cues with visible and accessible analytical-screening wording, show typed missing/proxy/mismatch warnings, and omit the 120-day cue.
- Alternatives considered: retain all existing attention chips; remove all timing information.
- User-visible effect: timing context is visible without a delay conclusion.
- Implementation effect: timing renderer must receive source basis/state.
- Risk if deferred: cue wording overstates evidence.
- Owner decision: REVISE

## 14. Whether the 120-day threshold is authorized

- Current inconsistency: code renders a `120+ day gap` chip despite the owner instruction not to do so.
- Repository evidence: connector and data contract define strictly greater than 120 days on the earliest available deterministic basis; no legal/regulatory authority was found.
- Recommended decision: retain the stored analytical flag but omit the visible 120-day chip until separately approved.
- Alternatives considered: approve the current chip; substitute another threshold.
- User-visible effect: no unsupported severity cue.
- Implementation effect: a follow-on must remove/guard current 120 rendering if approved.
- Risk if deferred: owner direction and production UI remain in conflict.
- Owner decision: APPROVE

## 15. Fixture coverage before implementation

- Current inconsistency: the seeded corpus has one complaint and cannot exercise all categories/states.
- Repository evidence: only two raw categories and `Unsubstantiated` occur in the loaded seeded corpus; many values are synthetic tests or code-only paths.
- Recommended decision: add deterministic bounded synthetic/unit coverage for every mapping and state implemented in this issue; do not require new source-derived records.
- Alternatives considered: implement from current tiny corpus; derive coverage from free-text cues.
- User-visible effect: approved semantics are demonstrably stable.
- Implementation effect: fixture and test work needs separate scope if source records change.
- Risk if deferred: mappings become speculative.
- Owner decision: REVISE

## 16. Unresolved raw source codes

- Current inconsistency: facility projection preserves raw numeric codes while other paths may use generic text.
- Repository evidence: `unresolved_raw_code` renders `Source code <value> — label not verified`.
- Recommended decision: retain that governed fallback as a labeled fact where reviewer-relevant; otherwise intentionally omit it rather than inventing a label.
- Alternatives considered: infer a readable label; hide every raw code.
- User-visible effect: uncertainty is explicit without unnecessary noise.
- Implementation effect: shared renderer must preserve raw code and source state.
- Risk if deferred: unsupported labels may enter the UI.
- Owner decision: APPROVE

## Recommended implementation boundary

The owner approval authorizes a domain-and-state shared renderer; migration of
existing finding, source/data-state, review-topic, reviewer-workflow, and
30/60/90 timing renderers; removal of the status-as-finding fallback; visible
120-day suppression; and bounded deterministic regression coverage. It does
not authorize source extraction, schemas, connectors, production data, or
review-topic derivation.

Separate evidence/design approval remains required for semantic color tokens,
the substantiated adverse treatment, any visible 120-day treatment, a complete
authorized-corpus topic audit, new/expanded fixtures based on source records,
high-impact topic/severity derivation, and any material page redesign.
