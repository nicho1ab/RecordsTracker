# RecordsTracker Reviewer Redesign Artifact Governance

## Authority and scope

This is the authoritative anti-fossilization contract for material
reviewer-facing redesigns under Issue #504. It applies when an approved change
removes, merges, renames, relocates, replaces, or substantially reorganizes a
reviewer-facing route, workflow, term, or interaction.

This contract authorizes an implementation task to rewrite or remove an
obsolete presentation assertion when the approved design supersedes it. It does
not authorize an agent to invent a design, erase useful behavior, weaken a
durable protection, or expand the task's capability, route, data, deployment,
or mutation scope.

The repository-readable Issue #501 information architecture is an explicitly
approved controlled design variance for the remaining dependent work. No
editable Figma artifact was changed by that approval. Implementations must cite
the exact repository requirement IDs they consume, provide a pre-code variance
inventory, capture automated exact-route evidence for every governed viewport
and state, satisfy every applicable `RT-UI-GATE-001` through
`RT-UI-GATE-009`, and receive explicit visual acceptance before merge.

## Artifact classification model

Classify each affected artifact by what it protects, not by its file type. One
test or document can contain more than one class; split the affected assertions
into separate rows when their treatment differs.

| Class | Name | What it protects | Redesign treatment |
|---|---|---|---|
| 1 | Durable product outcome | The attorney capability, decision, or useful route behavior that must remain possible. | Preserve the outcome; its route, label, layout, or control may change through the approved design. |
| 2 | Accessibility or safety invariant | Keyboard operation, focus, semantic structure, non-color meaning, safe wording, privacy, authorization, and other user-safety boundaries. | Preserve or strengthen it. A redesign cannot waive it. |
| 3 | Source/data/domain contract | Source fidelity, traceability, canonical data, deterministic reconciliation, public identifiers, safe exports, and source-derived/reviewer-created separation. | Preserve it exactly unless a separately governed contract change is authorized. |
| 4 | Approved design requirement | The currently approved hierarchy, interaction, terminology, responsive behavior, token, state, or requirement ID. | Implement it or obtain an explicit controlled variance; update the requirement register when superseded. |
| 5 | Implementation regression test | Behavior needed by the current approved implementation, including compatibility behavior during a bounded migration. | Keep while the implementation remains current; rewrite or remove in the same change that supersedes it. |
| 6 | Presentation snapshot or exact-string assertion | Potentially temporary wording, heading, route marker, ordering, markup structure, disclosure, CSS class, or screenshot label. | Retain only with a stated durable reason or approved requirement ID; otherwise rewrite around the user outcome or remove when superseded. |
| 7 | Historical documentation | Accurate evidence of prior behavior, decisions, releases, or captures. | Preserve as history and label it as historical; do not treat it as the current implementation contract. |

File location is not classification evidence. An accessibility document can
contain temporary page names; a unit test can enforce a durable authorization
boundary; a changelog can contain accurate obsolete terminology. When the
classification is genuinely ambiguous, the redesign stops for product-owner or
contract-owner resolution.

## Required redesign inventory and change process

Before implementation, inventory every affected test, evidence assertion,
documentation statement, Figma frame or approved artifact, design requirement
ID, route contract, accessibility requirement, changelog entry, and known
limitation. For each affected assertion record:

1. artifact path and assertion or section;
2. class number and name;
3. durable reason, requirement ID, or reason it is temporary;
4. disposition: `preserve`, `rewrite`, `remove`, or `historical only`;
5. replacement test, evidence, documentation, redirect, or migration behavior;
6. owner or approval for a controlled variance; and
7. the dependent issue or task that performs the change.

The implementation and its directly affected tests, evidence contracts, active
documentation, requirement register, and limitations must change together.
Keeping superseded UI solely because a test or capture marker expects it is a
review blocker. Removing an accessibility, security, privacy, source,
data-integrity, export, reviewer-state, or deterministic-reconciliation
protection under the label of redesign is also a review blocker.

An intentionally superseded behavior or route must be stated explicitly. A
route may redirect or retire only after its useful behavior, supported query or
fragment semantics, state recovery, and evidence have moved to the approved
destination. Redirect tests must prove destination, supported context
preservation, focus or fragment behavior where applicable, and safe recovery;
they must not merely prove a status code or matching link string.

## Outcome-based test design

Prefer assertions about user-visible outcomes, accessible names, navigation
results, state transitions, reconciliation, and governed boundaries. Exact
wording is appropriate only when the wording is governed, legally necessary,
safety-critical, accessibility-critical, an official source term, or part of an
approved terminology requirement. Structural markup assertions are appropriate
only when the structure itself protects semantics or an approved design
requirement.

Browser behavior is required when static markup cannot prove navigation,
focus, disclosure behavior, responsive reflow, keyboard operation, print, or a
state transition. A test tied to an approved design must cite its requirement
ID. When that requirement changes, update the register and its directly affected
tests together.

### Focused example: Help navigation

Durable outcome test:

```text
Given keyboard focus on the Help link for finding a facility,
when the user activates it,
the browser reaches the visible task guidance,
focus moves to the target heading,
and Back/Forward and the copied fragment remain useful.
```

This protects Classes 1, 2, and 4 without prescribing an accordion, a table of
contents, a specific helper paragraph, or a particular container class.

Brittle presentation assertion:

```text
assert '<details id="find-facility"><summary>Find a facility</summary>' in html
```

This is Class 6 unless an approved requirement explicitly mandates that exact
disclosure and wording. It proves neither focus movement nor browser fragment
behavior and must not force #503 to retain the current Help accordion.

### Focused example: valid unmatched Facility ID

Durable outcome test:

```text
Given a syntactically valid public Facility ID with no directory match,
the reviewer can continue with that same ID,
the page does not claim that the facility does not exist,
and no internal identity or operator diagnostic is exposed.
```

This protects Classes 1, 2, and 3. The precise card layout and helper paragraph
are not durable.

Brittle presentation assertion:

```text
assert '<summary id="manual-entry-heading">Enter a Facility ID directly</summary>' in html
```

This is Class 6 and conflicts with the approved single-input #502 design. It is
rewritten when #502 implements the outcome-based test.

## Evidence and acceptance

Replacement evidence must use sanitized automated exact-route capture for the
canonical destination, every applicable viewport and named state, and any
legacy redirect or migration behavior. The evidence report must cite applicable
requirement IDs and classify each as `PASS`, `VARIANCE`, `REGRESSION`, or
justified `NOT APPLICABLE`. Matching old headings, links, or screenshot labels
is not acceptance evidence for a superseded design.

Historical screenshots, manifests, route markers, and acceptance reports remain
evidence of the commit they captured. Do not rewrite them to look current. The
active capture and acceptance contracts must be updated in the same dependent
implementation that changes the routes or presentation they assert.

## Pull request and handoff contract

Every material reviewer-facing redesign PR and implementation handoff must
include an artifact-classification table with these columns:

| Artifact or assertion | Class | Disposition | Durable reason or requirement ID | Replacement evidence |
|---|---|---|---|---|
| One row per affected assertion | 1 through 7 | `preserve`, `rewrite`, `remove`, or `historical only` | Why this treatment is governed | Test, redirect, document, or exact-route evidence |

The PR must explicitly list preserved, rewritten, removed, and historical-only
artifacts; state every intentionally superseded behavior or route; identify
redirect or migration behavior; cite the controlled-variance approval when
used; and confirm that no durable protection was weakened. `Not applicable` is
acceptable only when the change is not a material reviewer-facing redesign and
the reason is specific.

Unexplained preservation of superseded UI, unexplained removal of a durable
protection, an unclassified affected assertion, or missing replacement evidence
is a review blocker.

## Issue 501, 502, and 503 findings

These findings classify the known stale-contract inventory. They do not change
application behavior or authorize dependent implementation.

| Dependent scope | Artifact or assertion family | Classification | Required dependent treatment |
|---|---|---|---|
| #501 controlling design | Canonical attorney tasks, route dispositions, six-link navigation, approved terminology, information tiers, responsive/state requirements, and controlled repository-readable variance | Class 4, with Classes 1 through 3 embedded | Preserve the approved outcomes and boundaries. Cite `RT-IA-004`, `RT-NAV-001`, `RT-LANG-001`, and all other applicable requirement IDs. |
| #419 cross-facility consolidation | Current independent priority, trends, substantiated, serious-topic, and public-summary routes; legacy headings and evidence marker lists | Useful behavior is Classes 1 through 3; current separate renderers are Class 5; names, route markers, and duplicate inventories are Class 6 | Preserve filters, factors, source-domain separation, query semantics, pagination, reconciliation, and recovery. Migrate them into approved canonical views before redirecting legacy URLs; rewrite active tests and evidence together. |
| #502 Home and Facilities | Tests requiring Home and Facilities to share one renderer, a manual-entry disclosure, `Optional planning views`, `Reference data details`, and old navigation/action wording | Shared renderer and exact presentation are Classes 5 and 6; facility discovery, valid unmatched-ID continuation, truthful source states, and tier separation are Classes 1 through 3 | Replace duplication and disclosures with the approved Home launch and single-input facility flow. Preserve valid-ID continuation and move safe diagnostics to the governed operator/support tier. |
| #503 Help | Tests requiring the current topic order, matching `href`/`id` strings, `<details>` elements, exact summary text, and legacy `Review Queue`/`Request Records` names | Current renderer is Class 5; markup, order, and legacy strings are Class 6; task guidance, working navigation, focus, official terms, and tier separation are Classes 1 through 4 | Replace static-presence checks with browser-observable fragment, focus, Back/Forward, keyboard, responsive, and visible-guidance tests. Permit disclosures only for approved secondary content. |
| Shared evidence | Legacy route capture lists, screenshot labels, active-navigation expectations, and old H1/text markers in capture and acceptance tools | Current compatibility coverage is Class 5; labels and markers are Class 6; exact-route, privacy, accessibility, and state evidence are Classes 1 through 4 | Update the active contract during each dependent implementation; retain old packets as Class 7 history and prove redirect/view parity before removing a legacy capture. |
| Shared documentation | Current user docs and Unreleased descriptions using obsolete page names or manual-entry concepts | Active guidance is Class 5 or 6; accurate released changelog entries are Class 7 | Update active guidance with implementation. Preserve accurate history and label it by release or commit context. |

## Prohibited shortcuts and stop conditions

- Do not classify all presentation tests as disposable.
- Do not convert a durable boundary into a temporary assertion to make a
  redesign easier.
- Do not preserve a superseded route, disclosure, paragraph, heading, or CSS
  structure solely to pass a stale test.
- Do not silently delete unique behavior, supported URL context, official
  terminology, reviewer-created state, source traceability, safe export fields,
  authorization, or accessibility behavior.
- Do not claim that Figma was updated under the #501 controlled variance.
- Do not substitute manual browser inspection for required automated evidence.
- Stop when the approved artifact, classification, replacement behavior, or
  variance authority cannot be reconciled.
