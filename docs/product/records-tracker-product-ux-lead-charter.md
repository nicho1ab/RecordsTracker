# CCLD RecordsTracker Product UX Lead Charter

## Purpose

RecordsTracker exists because the public CCLD site provides access to facility, licensing, complaint, visit, citation, and report data, but it is not designed for attorney advocacy, investigation, pattern detection, oversight review, or case preparation.

RecordsTracker must turn public CCLD data into a usable attorney-facing portal that helps advocates identify facilities with poor outcomes for children, detect oversight and monitoring failures, review source-backed evidence, and prioritize legal or advocacy action.

RecordsTracker is not a prettier mirror of the CCLD site. It is an attorney public-record review workspace built from public CCLD data because the source site is organized around transparency access, not legal review, triage, pattern detection, or source-backed advocacy.

## Primary User

The primary user is an attorney or advocate working on behalf of children served by licensed or state-sponsored care facilities.

Representative user story:

> As an attorney at YLC, I need to research and identify facilities with poor outcomes for the children in their care so that I can target the most egregious facilities and the state for failing to meet the needs of their clients and for a lack of monitoring, oversight, and timely action in investigating complaints.

## Product North Star

RecordsTracker should answer three questions quickly:

1. Which facilities appear to have the most serious or repeated problems?
2. What does the public source record show about a specific facility?
3. What should an attorney or advocate review next?

Every major page should help users move from public source data to advocacy-relevant understanding.

## Source Site Problem

The public CCLD site appears to be designed around public transparency and legal disclosure obligations. It is not designed to help attorneys identify dangerous facilities, compare facility performance, detect patterns, or evaluate whether the state responded appropriately.

Known source-site limitations include:

- Exact-name searching is too brittle.
- There is no strong fuzzy match, typeahead, or guided lookup.
- Facility detail data is difficult to reuse and copy/paste cleanly.
- Facility details are spread across tabs without strong synthesis.
- Complaints, inspections, citations, visits, and reports are presented as separate fragments.
- The site does not provide a clear risk picture for a facility.
- The site does not help users compare facilities or identify patterns across facilities.
- The site does not translate CCLD terminology into an attorney-facing review workflow.
- The site is visually dated and not optimized for reviewer decision-making.

RecordsTracker must correct those weaknesses.

## Product Positioning

RecordsTracker is an attorney public-record review workspace.

RecordsTracker should not describe itself as a prototype or proof of concept in user-facing or stakeholder-facing language. Preferred language includes current app, current version, RecordsTracker, early version, pilot build, or attorney public-record review workspace, depending on context.

RecordsTracker should not imply legal conclusions. It should support attorney review by organizing source-derived public information, review flags, source traceability, facility context, and reviewer-created workflow state.

## Product Design Principles

### 1. Lead with the user decision, not raw source data

Default views must start with what the attorney needs to know and do. Raw source fields, source bundle data, extraction metadata, and runtime details must not dominate the screen.

### 2. Above the fold must answer the core question

For detail pages, the first screen should identify the facility, record or event, why it matters, review status, key dates, important review flags or oversight indicators, and available next actions.

### 3. Preserve source traceability without creating a source-data dump

The system must preserve source traceability. The reviewer-facing page does not need to display traceability internals. Traceability internals belong in support, developer, or operator tiers unless they directly support the current attorney task.

Reviewer-facing source traceability should usually be limited to a compact source cue, such as original source available, source link, source type, or source-backed status. Full traceability internals such as raw SHA-256, source artifact identity, connector metadata, report index, extraction audit rows, source-derived bundle rows, raw paths, and field-level traceability tables belong outside the normal reviewer-facing tier.

### 4. Use CCLD terminology, but translate it into reviewer meaning

The product should preserve source terms such as citation, inspection, complaint investigation report, facility evaluation report, substantiated, inconclusive, unsubstantiated, Type A citation, Type B citation, POC, STRTP, group home, temporary shelter, and residential shelter family home.

Definitions should be delivered at the point of use through inline term treatment: a standard color, dotted underline, keyboard focus, and hover/focus definition window. Terms should not look like ordinary links. Do not consume page space with repeated definition paragraphs when inline definitions can explain the term.

### 5. Make patterns visible

RecordsTracker must help users see patterns across time and across facilities, including repeated complaints, substantiated allegations, Type A and Type B citations, inspection frequency, complaint investigation timelines, recurring report themes, state response delays, facility status changes, and clusters by facility type, geography, licensee, or operator.

### 6. Search must be forgiving

RecordsTracker search should not require exact CCLD facility names. It should support fuzzy matching, typeahead, license number lookup, partial facility name, city, county, ZIP, facility type, licensee or operator, status, and high-risk or recently active facilities.

### 7. Dashboards should synthesize, not decorate

A facility dashboard should not be a tabbed reproduction of the source site. It should synthesize current facility identity and license status, recent complaint, visit, citation, inspection, and report activity, risk indicators, trends, source documents, review status, and attorney action opportunities.

### 8. Design before code

Do not ask a coding agent to make the UI better without an approved page blueprint or an approved sitewide pattern standard.

For important pages, the workflow must be:

1. Identify the page and user task.
2. Create a page blueprint or identify the approved sitewide pattern.
3. Define above-the-fold content.
4. Define default visible sections.
5. Define support-tier, help-tier, and operator/developer-tier content.
6. Define raw/source data handling.
7. Define visual acceptance criteria.
8. Only then give the coding agent an implementation prompt.
9. Capture or manually review the exact route screenshot before opening or merging a PR.

### 9. Tests are necessary but not sufficient

Passing tests only confirms that behavior and expected markup did not break. Tests do not prove that the page is usable or visually successful.

A page redesign is not complete until the screenshot of the target route passes visual review against the blueprint or approved sitewide pattern.

### 10. Reject superficial redesigns

Reject changes that only add classes, cards, spacing, or collapsible sections while the page still feels like a raw data dump.

A successful redesign materially changes how quickly an attorney can understand the page and choose the next action.

### 11. Prefer product tiers over long pages

RecordsTracker should use intentional information tiers:

1. **Reviewer-facing tier**: what the attorney needs to decide what record/facility is open, why it may matter, what source facts are available, what reviewer-created state exists, and what action to take next.
2. **Help tier**: definitions, field interpretation, how-to-read guidance, first-run instructions, and longer explanatory material.
3. **Support/dev/operator tier**: source bundle rows, source-derived field dumps, connector metadata, raw hashes, extraction audit, runtime status, operational metadata, debug navigation, and technical context.
4. **Data/enrichment tier**: source-derived enrichment, conflict handling, data completeness checks, and source-to-facility sync work.

Do not put help-tier or operator-tier material in the default reviewer-facing flow merely because it is accurate or accessible. Accessibility requires that visible content be accessible; it does not require every technical or explanatory detail to remain visible on the primary page.

## Sitewide Reviewer-Facing UI Standards

### User tier versus operator/developer tier

Reviewer-facing pages must not expose raw scaffold, source-bundle, source-derived field dump, operator/runtime, technical navigation, issue-bridge, or first-run training content in the primary user tier.

Move the following out of reviewer-facing pages unless the user explicitly approves a reviewer-facing reason:

- full source-derived field tables;
- selected source-derived bundle summaries;
- related source-derived row tables;
- source traceability internals;
- source-confidence/source-derived value check tables;
- connector metadata;
- raw SHA-256 hashes;
- raw artifact references;
- machine-readable keys except where a copyable ID is needed;
- technical/operator runtime details;
- facility context cue internals;
- detail navigation dumps;
- first-run detail steps;
- issue-report bridge copy;
- repeated help/return/action lists;
- long reviewer-created note/status guidance tables.

### Help tier

Definitions, “how to read this record,” first-run orientation, cautious note-writing guidance, and issue-report instructions belong in Help or in focused workflow help, not as repeated visible content on every reviewer detail page.

### Source traceability tier

Source traceability must be preserved, but the reviewer-facing tier should show only compact source availability and source-link cues. Detailed traceability belongs to support/dev/operator surfaces.

### Issue reporting tier

“Report an issue” should be a concise action with safe page context. Do not repeat issue-report bridge copy, issue-report note instructions, or long lists of what to include across pages. Put that guidance on the Report an issue page or Help.

### Facility facts

Facility identity should appear once per page, preferably near the top. Do not repeat facility name, facility/license number, facility type, county, status, capacity, or source ID across multiple cards/sections.

### Copy affordances

Core values should have a recognizable copy-to-clipboard icon next to the value when copying is useful. This includes facility/license number, complaint number, key dates, finding/status, source URL, and complaint summary. Do not place the copy action far away from the value it copies.

### Date format

Display dates sitewide as `MM/DD/YYYY` without times unless the time is part of complaint narrative or another source text, rather than a timestamp field. Preserve underlying timestamps in data and operator tiers where needed.

### Review flags

Use badges as the single primary visual expression for review flags. Do not duplicate the same review flag as both a badge and a card.

### Timeline pattern

When a record has ordered event dates, use a compact linear timeline visualization instead of vertical prose/list blocks. Avoid repeated explanatory text such as “source-derived complaint received date.” Use inline term definitions where a term needs explanation.

### Related activity

Do not include “related facility activity” unless it clearly helps the attorney answer a review question. A useful related activity section must explain what related records are included, why they are related, and what decision it helps the reviewer make. If it only repeats the selected source bundle or raw rows, remove it.

## Current Product Priorities

### Immediate UI/UX priority

Fix the reviewer record detail page so it becomes a true attorney-facing complaint/detail review page.

Target route:

`/reviewer/records/detail?source_record_key=complaint%3Accld%3Acomplaint%3A32-CR-20220407124448`

The page must stop looking like a long raw source dump.

### Immediate sitewide pattern priority

Standardize the user tier, help tier, support/dev/operator tier, timeline pattern, inline glossary pattern, date formatting, review flag badges, copy affordances, and issue-report action pattern across reviewer-facing pages. Avoid solving these same problems one page at a time.

### Immediate data priority

Ensure the portal has all current facilities for the facility type already implemented.

### Facility enrichment priority

When imported complaint/source records contain facility attributes missing from the facility reference data, RecordsTracker needs a governed source-derived enrichment path to update or supplement existing facility records while preserving source traceability, original values, and conflict rules.

Examples of facility/source attributes that may appear in complaint records or source documents and should be evaluated for enrichment include capacity, state, ZIP, administrator, regional office, evaluator, supervisor, met-with person, time began/completed, signature/appeal/report availability text, and detailed investigation findings narrative.

This is a data capability need, not only a display issue. It should not overwrite source-derived records without approved conflict handling and source traceability.

### Near-term data priorities

Pre-populate data in batches for, at minimum:

- all facilities in the currently supported facility type;
- all complaints;
- all visits;
- all reports where available;
- current open/licensed facilities first.

### Facility type expansion priorities

After immediate current-facility coverage is stable, expand to:

- Short Term Residential Therapeutic Program (STRTP);
- group homes;
- temporary shelters;
- residential shelter family homes;
- pending facilities;
- historical and closed facilities.

## Required Page Blueprint Standard

Every major page blueprint must specify:

- page purpose;
- primary user question;
- above-the-fold content;
- primary actions;
- secondary actions;
- default visible sections;
- help-tier content;
- support/dev/operator-tier content;
- raw/source data handling;
- diagnostics/operator detail handling;
- glossary/acronym support;
- accessibility expectations;
- visual acceptance criteria;
- implementation boundaries.

Blueprints must say what should be removed from the reviewer-facing tier, not just what should be collapsed.

## Reviewer Detail Page Direction

The reviewer detail page should be redesigned around this hierarchy:

1. Complaint identity and facility identity at the top.
2. Copyable complaint/facility/source identifiers where useful.
3. Source narrative plus compact investigation timeline.
4. Review flag badges.
5. Finding and allegation summary.
6. Reviewer-created status/note action area only if it directly supports the current review.
7. Primary next actions.
8. Optional compact source link/status cue.

The reviewer-facing page should not include:

- source traceability internals;
- full source-derived fields;
- source-derived value check tables;
- selected source-derived bundle summaries;
- related source-derived row tables;
- technical/operator runtime details;
- facility context cue internals;
- detail navigation dumps;
- first-run detail steps;
- issue-report bridge copy;
- long note/status guidance tables;
- repeated facility facts;
- repeated action lists;
- empty citations/POC panels when no useful source content exists;
- related facility activity unless it has a clearly defined review purpose.

The default view must not show a giant raw table of all extracted fields, and it must not become a long sequence of collapsed technical sections that still reads as a raw source/debug page.

## Facility Dashboard Direction

A facility dashboard should answer:

- What is this facility?
- Is it currently licensed or open?
- What type of facility is it?
- Who operates it?
- What recent complaints, inspections, visits, citations, and reports exist?
- Are there substantiated allegations?
- Are there Type A or Type B citations?
- Are there repeated events over time?
- Are there signs of poor outcomes or weak oversight?
- What source documents should the attorney open first?

The dashboard may use tabs, but tabs must support attorney workflow rather than simply copying the source site categories.

Facility identity should appear once at the top, with copy affordances for useful identifiers. Related facility activity should synthesize patterns and review value rather than repeat source bundle rows.

## Facility Search Direction

Search should become one of the strongest parts of RecordsTracker.

Search should support fuzzy facility lookup, typeahead, exact license number, partial name, facility type, status, city, county, ZIP, licensee or operator, recent complaints, citation counts, inspection or visit activity, and high-risk indicators.

Search results should not just list matches. They should help attorneys choose what to review first.

The current Home page should not waste a click by merely forwarding users to facility lookup. The Home page should either become a true start page with search, review-priority summaries, and next actions, or the facility lookup route should become the primary landing experience.

## Data Dictionary Alignment

RecordsTracker currently tracks complaint and report timing fields such as facility name, external facility number, complaint received date, first investigation activity date, visit date, report date, date signed, finding, date-difference fields, delay review flags, missing first activity date, report date used as proxy, and extraction confidence.

These fields should be treated as review and triage aids. Delay flags are screening flags, not conclusions that an investigation was delayed. Report date used as proxy must not be treated as proof that the report date was the first investigative activity.

## Source and Field Matrix Alignment

The Field and Source Matrix is the product's current stakeholder-friendly reference for captured data, source types, where data appears, why it matters, and review guidance.

Design work should align with that matrix by ensuring that reviewer-facing screens preserve practical source-backed value without allowing raw field overload. The matrix identifies source-derived facility details, complaint identifiers, complaint dates, findings, delay flags, citation information, plan of correction information, complaint visit counts, reviewer-created state, packet/export outputs, source traceability, and feedback as major product concepts.

Important design implications:

- The page should show why data matters and how to use it, not merely expose that the data exists.
- Reviewer-created status and notes must remain visibly distinct from source-derived values.
- Source traceability must be preserved and available, but traceability internals should not dominate the default reviewer-facing screen.
- Facility facts should be deduplicated and presented once at the point of use.

## Local Review Workflow Alignment

The previous local Datasette workflow contains useful product logic even though RecordsTracker is now a custom hosted app. Its most important concepts should influence the portal UX:

- start with a review home or task-based starting surface;
- provide low-noise first-pass complaint review;
- support public-record allegation search;
- support timeline review;
- support delay triage;
- support facility comparison and pattern review;
- support source traceability review in support/dev/operator tier when needed;
- support field-level source traceability outside the default reviewer-facing flow;
- provide accessible exports while preserving source context.

The hosted app should eventually absorb the useful parts of this local workflow into a more usable reviewer-facing portal.

## CCLD Report Design Implications

The sample CCLD reports show why RecordsTracker needs stronger synthesis.

The reports contain highly relevant legal-review facts, including:

- facility name and number;
- report type;
- complaint control number;
- complaint received date;
- visit or inspection date;
- allegations;
- investigation findings;
- substantiated, unsubstantiated, or inconclusive findings;
- Type A and Type B deficiency/citation data;
- plan of correction information;
- licensing evaluator and facility representative signature/date information;
- narrative text that describes what happened and what evidence was reviewed.

RecordsTracker must extract and surface those facts in attorney-friendly form. It should not force attorneys to read the full raw report first just to find the most important review cues.

For complaint investigation reports, the default detail page should emphasize allegation summary, finding, substantiated count or status, citation/deficiency information when present, received date, visit or first activity date, report date, delay or missing-date review flags, compact source document link/status, extracted narrative, and next review action.

## Glossary and Acronym Support

RecordsTracker should incorporate source terminology from CCLD, including acronyms and terms used in the public site. The glossary should be available when users encounter terms, but it should not overwhelm task screens.

Recommended pattern:

- inline term treatment for high-impact terms;
- standard term color;
- dotted underline;
- keyboard focus support;
- hover/focus definition window;
- not styled as ordinary hyperlinks;
- optional glossary link for full definitions;
- no repeated definition paragraphs when inline definitions can reduce page length.

Terms that likely need support include Type A citation, Type B citation, POC, complaint investigation report, facility evaluation report, substantiated, unsubstantiated, inconclusive, STRTP, group home, temporary shelter, residential shelter family home, source-derived, reviewer-created, source traceability, and source of record.

## Figma and Design Handoff

The current design direction may be refined in Figma before implementation. Figma output can help define layout, hierarchy, icons, copy affordances, timelines, badges, and glossary interactions before Codex implements them.

Every reviewer-facing visual or interaction implementation requires an approved
Figma frame or another explicit user-approved design package before coding.
Figma is not required for a nonvisual correction that preserves an already
approved pattern, but the implementation handoff must cite that pattern and
state why no visual variance is expected. Agents must not invent missing visual
direction while coding.

A Figma-to-Codex handoff should specify:

- exact route/page;
- target screen width if relevant;
- above-the-fold content;
- sections to remove;
- sections to move to Help or dev/operator tier;
- shared components/patterns;
- responsive behavior;
- accessibility expectations;
- copy/icon affordances;
- visual acceptance criteria.

## My Role as Product/UX Lead

When acting as Product/UX Lead, ChatGPT must:

- prioritize attorney workflow over code convenience;
- challenge superficial design changes;
- require page blueprints or approved sitewide pattern standards before implementation prompts;
- separate design acceptance from test acceptance;
- ask for screenshots when visual quality matters;
- reject PRs that pass tests but fail the user task;
- maintain the product north star;
- preserve source traceability without allowing raw data to dominate;
- keep terminology aligned with CCLD source language while making it understandable;
- identify when old tests or docs are forcing outdated scaffold UI and recommend updating them;
- prevent drift into governance-only, scaffold-only, or class-only work;
- use ChatGPT project terminology accurately.

## ChatGPT Model Terminology and Usage

When discussing ChatGPT chats in this project, use the model-picker terminology shown in ChatGPT:

- Latest / 5.5
- Instant
- Thinking
- Pro
- Standard
- Extended

Do not describe ChatGPT project chat options as High, XHigh, or Max. Those terms are closer to Codex, Copilot, or other coding-agent reasoning controls and should only be used when discussing those tools.

Recommended ChatGPT use:

- Use Thinking with Extended reasoning for product/UX leadership, page blueprints, critique synthesis, and implementation specifications.
- Use Pro with Extended reasoning when available for broad multi-page synthesis, final challenge review, or major product architecture decisions.
- Use Standard only for routine command blocks, PR validation, or small wording cleanups.
- Do not use Instant for product strategy, page design, or final acceptance review.

## Codex and GitHub Copilot Role

Codex and GitHub Copilot should implement approved designs and approved sitewide patterns. They should not be asked to invent product strategy or visual hierarchy from broad prompts.

A Codex or Copilot prompt for major UI work should only be issued after the page blueprint or sitewide pattern standard is approved.

If Codex preserves outdated scaffold sections because older tests or documentation require them, update those tests or documentation to match the current product direction rather than accepting the outdated UI.

## Acceptance Gate for UI PRs

A UI PR is not ready merely because:

- tests pass;
- route capture succeeds;
- evidence zip is generated;
- classes were added;
- markup changed;
- a section was collapsed but still dominates the page;
- old scaffold visibility tests still pass.

A UI PR is ready only when:

- automated exact-route screenshots exist for every applicable approved
  viewport and component state;
- the screenshots have been compared with the exact approved design artifact
  and an explicit visual-acceptance decision is recorded;
- the screenshot matches the blueprint or approved sitewide pattern;
- the primary user task is visibly easier;
- source/reviewer/operator tiers are respected;
- duplicate facility facts, review flags, issue bridges, and action dumps are removed;
- behavior and source traceability are preserved in the correct tier;
- no user-facing defensive caveat, boundary, warning, or limitation model is reintroduced.

## Immediate Next Artifacts

The next product artifacts should be:

1. **Reviewer Detail Tier Correction**: update the current reviewer detail implementation and its tests/docs so the page no longer shows source traceability internals, source-derived value checks, raw bundle rows, technical/operator sections, issue bridges, first-run training, or repeated facility/action content in the user tier.
2. **Reviewer-Facing Sitewide Pattern Standard**: define reusable patterns for user tier versus help tier versus support/dev/operator tier, timeline display, inline definitions, review flag badges, copy icons, date formatting, issue-report actions, and source traceability support.
3. **Facility Enrichment Requirement**: define the governed source-derived enrichment path for updating missing facility attributes from imported complaint/source records when source traceability supports it.

Do not create another broad Codex implementation prompt until the relevant blueprint, tier standard, or enrichment requirement is approved.
