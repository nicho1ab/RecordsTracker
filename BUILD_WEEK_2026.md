# RecordsTracker — OpenAI Build Week 2026

## Inspiration

RecordsTracker began in June 2026 with a simple question from a legal-aid attorney:

> “Would it be possible to build a scraper with AI?”

His team worked with public licensing and complaint records from the California Community Care Licensing Division, or CCLD. They represented and advocated for children living in foster care, group homes, residential treatment programs, temporary shelters, and other licensed settings—children whose safety and well-being may depend on whether complaints are investigated, whether recurring problems are recognized, and whether the state responds effectively.

The information they needed was technically public, but the CCLD site made meaningful review difficult. Facility data, complaint reports, findings, visits, citations, licensing information, and downloadable files were spread across different parts of the portal. Searching was brittle. Reports had to be opened individually. Comparing facilities or identifying repeated patterns required significant manual work.

For an attorney preparing a case or investigating a system failure, that fragmentation matters. One complaint may look isolated until it is compared with others. A delay may not be apparent until multiple dates are assembled. A facility name may change while the license number remains the same. A pattern may exist across facilities operated by the same organization. Important facts may be buried in narrative reports that are difficult to search or summarize.

The attorney’s original request was modest: could AI help scrape the site?

I decided to find out.

I was not a software developer, and I had never used Codex before. My professional strengths were in ideas, policy, governance, security, compliance, systems thinking, and translating complicated needs into requirements. I began using ordinary language in place of code and relied on AI—primarily Codex and ChatGPT—to perform the technical implementation.

The first goal was simply to prove that the public reports could be retrieved, preserved, and transformed into structured data. I initially thought of it as a small proof-of-concept: scrape a facility’s reports, extract useful fields, and store the results in a file or database.

Then I met directly with an attorney who did this work.

That conversation changed the scale of the project. He described the difficulty of using the public site, the kinds of questions attorneys needed to answer, and the reality that sophisticated research tools are often built for firms with substantial resources, not for legal-aid organizations, nonprofit advocates, or publicly funded teams representing children.

What began as “scrape it and dump it into a file” became a larger question:

> What would it look like to build an actual platform for the people doing this work?

I realized there was no reason to lock the concept permanently to one California website. Other states publish licensing, inspection, complaint, provider, enforcement, and facility information through their own combinations of portals, spreadsheets, APIs, PDFs, and searchable databases. The formats differ, but the underlying need is similar: help reviewers find the right records, understand patterns, verify the evidence, and decide what to examine next.

That insight became the foundation of RecordsTracker.

In only a few weeks, a question from a legal-aid attorney grew into a working, production-style public-record intelligence platform with deterministic extraction, raw-evidence preservation, PostgreSQL storage, facility enrichment, reviewer workflows, cross-facility analysis, responsive design, accessibility requirements, deployment procedures, and a governed path for adding new states and sources.

## What it does

RecordsTracker is an attorney-focused workspace for public-record intelligence and review.

It helps attorneys, advocates, researchers, and public-interest reviewers move from fragmented records to a clear and verifiable next action.

A reviewer can:

- Search for a facility by name, license number, city, county, ZIP code, facility type, license status, licensee, or other public attributes.
- View a consistent facility identity, including readable facility type, address, license status, capacity, county, licensee, and regional office when those values are available.
- See when facility-reference information was published, retrieved, or refreshed.
- Review the complaint and investigation activity for a selected facility.
- Compare facilities using explainable public-record indicators.
- Identify facilities or complaints that may warrant closer review.
- Understand why a facility or complaint was prioritized.
- Review complaint dates, allegations, findings, investigation activity, delays, deficiencies, and source availability.
- Follow the links back to the original public records.
- Add reviewer-created notes and statuses without modifying source-derived facts.
- Prepare review and packet context for litigation, advocacy, investigation, or oversight work.

RecordsTracker is designed to support professional judgment, not replace it.

The application does not claim that a facility is dangerous, that a state agency acted unlawfully, or that a complaint proves harm. Instead, it helps qualified reviewers find and organize the source-backed evidence that may support further review.

That distinction is important because the potential real-world impact is significant.

The attorneys and advocates who inspired this project work with children who may have experienced unsafe placements, inadequate services, abuse, neglect, disrupted education, inappropriate institutionalization, or failures of monitoring and oversight. Their work may involve protecting an individual child, challenging conditions at a single facility, identifying a recurring operator-level problem, or demonstrating that a state system repeatedly failed to respond.

Every hour spent navigating an outdated portal, reopening individual reports, manually comparing dates, or rebuilding the same spreadsheet is an hour that cannot be spent interviewing a child, preparing an argument, developing a case, or advocating for reform.

RecordsTracker cannot perform that legal work. It can give those professionals more of their time back and make important patterns easier to see.

It may help a reviewer discover that:

- Multiple complaints at one facility contain similar allegations.
- The same operator appears across several facilities.
- Substantiated findings recur over time.
- Investigation or report dates deserve closer examination.
- A facility’s license status or capacity changed.
- Records appear incomplete or inconsistent.
- Several reports reference related deficiencies or corrective actions.
- A source field shown as missing in the application was actually present in the public report.

RecordsTracker distinguishes a verified numeric zero from missing, blank, unavailable, unsupported, conflicting, uninspected, and not-applicable information. Incomplete source coverage is never silently converted into a favorable-looking result.

The CCLD portal remains the source of record. RecordsTracker makes that source more usable, reviewable, and traceable.

## How I built it

I built RecordsTracker without a traditional coding background.

I did not begin by learning a programming language, selecting a framework, or manually writing an application from scratch. I began by describing the problem, the users, the evidence requirements, the risks, and the desired behavior.

I used AI as the technical development layer.

Codex analyzed the repository, wrote and modified code, created tests, diagnosed errors, implemented database migrations, optimized queries, updated documentation, and helped turn requirements into working features. ChatGPT became the architecture, product management, UX, issue planning, and acceptance review layer.

I remained responsible for deciding:

- What problem the product should solve.
- Which user needs mattered most.
- What the application was allowed to conclude.
- How source evidence should be preserved.
- Which data should be treated as authoritative.
- What qualified as an acceptable design.
- Which implementation results should be rejected.
- When the project was ready to move to the next stage.

The result is a governed public-data pipeline:

1. Controlled retrieval discovers public records for selected facilities, record types, and date ranges.
2. Original source artifacts are preserved before extraction.
3. SHA-256 hashes, source URLs, retrieval timestamps, connector versions, and report identifiers preserve provenance.
4. Deterministic extraction processes fields that can be reliably identified in the source.
5. Source-specific records are normalized into shared canonical structures.
6. Schema validation and data-quality rules reject invalid derived records.
7. SQLite supports local validation and inspection.
8. PostgreSQL supports the hosted application and larger data corpus.
9. Facility-reference sources enrich complaint records with consistent facility identity.
10. Reviewer-created notes and statuses are stored separately and never overwrite public-source facts.
11. The application presents facility intelligence, comparison tools, worklists, complaint review, and packet-preparation workflows.

### From Codex-generated screens to a real design system

Codex was highly effective at implementing functionality, but the early user experience did not look or behave the way I wanted.

The pages worked, but they often felt like technical scaffolding: too many cards, too much explanatory text, inconsistent hierarchy, developer-oriented labels, and interfaces that exposed data without clearly helping an attorney decide what to do next.

I asked ChatGPT to critique the experience and suggest a better approach.

That led me to Figma.

I connected Figma to ChatGPT and began treating the interface as a designed product rather than asking a coding agent to “make it look better.” ChatGPT helped translate the attorney workflow into page briefs, content hierarchies, design constraints, responsive requirements, component states, and acceptance criteria. I used Figma to explore alternatives visually before asking Codex to implement them.

The design process became:

1. I identified the page and the decision the attorney needed to make.
2. ChatGPT produced a structured page brief and content inventory.
3. I used Figma and Figma AI to explore visual directions.
4. I reviewed and selected the final direction.
5. The approved design was converted into an implementation package.
6. Codex implemented the approved design rather than inventing one.
7. I captured the exact running route at multiple screen widths.
8. ChatGPT compared the implementation with the Figma reference.
9. Material differences were treated as defects rather than subjective preferences.

This process produced the Civic Ledger design system.

Civic Ledger uses:

- A warm neutral canvas.
- Deep navy navigation and primary actions.
- Restrained gold navigation and focus cues.
- Compact editorial density.
- Modest corner radii.
- Minimal elevation.
- Accessible traffic-light status semantics.
- Clear separation between source facts, reviewer-created state, help content, and operator diagnostics.
- Responsive behavior that preserves information hierarchy rather than turning every section into a stack of generic cards.

The Figma work went well beyond a single mockup.

I developed or governed:

- A product header and navigation system.
- Typography and spacing foundations.
- Primary, secondary, and text action patterns.
- Status chips and review indicators.
- Facility identity banners.
- Complaint inventory rows.
- Filter and search patterns.
- Reviewer action controls.
- Missing, unavailable, partial, and failed-data states.
- Responsive tables and labeled stacked rows.
- Desktop, narrow-desktop, mobile, and zoomed layouts.
- Selected, hover, focus, disabled, empty, populated, partial, unavailable, and error conditions.
- Facility review hub frames.
- Complaint overview frames.
- Cross-facility intelligence frames.
- A reusable design-system and pattern-library frame.

The design documentation now states that Figma is the authoritative visual reference. Implementation agents must cite the applicable design requirements, identify intentional variances, and stop when they cannot conform. Passing tests alone does not establish visual acceptance.

That was a major evolution in how I used AI. Codex remained the implementation engine, but ChatGPT and Figma gave me a way to exercise product judgment and visual control without needing to become a frontend developer.

### Designed for more than one state

Although California is the first implemented jurisdiction, I deliberately designed RecordsTracker so that it is not permanently tied to CCLD.

Each public source is handled through a source-specific connector. A connector is responsible for:

- Discovering records.
- Fetching the original source.
- Preserving the raw artifact.
- Computing hashes.
- Extracting reliable fields.
- Normalizing values into governed canonical structures.
- Validating the result.
- Emitting extraction and provenance evidence.
- Documenting source-specific limitations.

This means a future source can use an API, CSV download, HTML portal, provider list, searchable database, PDF report, or another structure without requiring the entire application to be rewritten.

The shared platform can preserve common concepts such as:

- Facility identity.
- License status.
- Facility type.
- Operator or licensee.
- Complaint identity.
- Allegations and findings.
- Investigative activity.
- Visits and inspections.
- Citations and deficiencies.
- Plans of correction.
- Source documents.
- Publication and retrieval dates.
- Reviewer-created notes and statuses.

At the same time, each state can retain its own terminology, identifiers, limitations, and source semantics.

I have already begun evaluating future sources in states such as Idaho and Tennessee. Their systems differ from California’s: some rely more heavily on provider lists or searchable inspection interfaces than on downloadable facility packages. RecordsTracker’s architecture was designed to accommodate those differences rather than forcing every jurisdiction through one brittle scraper.

The future experience could allow a reviewer to choose a jurisdiction and source, work within that state’s terminology and evidence, and use a consistent review layer without pretending that every state collects identical information.

### Documentation and governance as part of the product

Because I am not a software developer, documentation was never an afterthought. It was essential to make the project understandable, maintainable, and safe.

The repository contains plain-language and technical documentation covering:

- Project purpose and scope.
- Architecture.
- Data contracts.
- Source connector requirements.
- Security and privacy.
- Accessibility.
- Testing strategy.
- Design and usability.
- Deployment.
- Adding a new source.
- Release procedures.
- Known limitations.
- Operational runbooks.
- Database migrations.
- Evidence capture.
- QNAP deployment and recovery.
- Authentication boundaries.
- Facility-data refresh.
- Reviewer workflow behavior.
- Product decisions and architecture decision records.

The governance files do more than describe the project. They guide AI agents and future maintainers.

Before changing important behavior, an implementation agent is instructed to read the relevant contracts and design rules. Schema changes require corresponding tests and documentation. Extraction defects require regression fixtures. User-facing changes require accessibility and visual review. Source-derived facts must remain separate from reviewer-created content. Secrets and private infrastructure details are prohibited from code, tests, screenshots, and documentation.

This creates a repeatable way for a non-developer—or a new developer unfamiliar with the project—to understand what the system does, run it, validate changes, and avoid violating critical boundaries.

A technically motivated user can follow the instructions to:

- Create the local environment.
- Run fixture-backed examples.
- Start the hosted application.
- Execute validation.
- Build or import data.
- Configure Docker.
- Apply migrations.
- Capture UI evidence.
- Verify container and route health.
- Back up and restore PostgreSQL.
- Add a new source through the governed connector process.
- Deploy the application to another supported environment.

The documentation also reduces dependence on any one AI session. Decisions are documented in the repository rather than getting trapped in conversation history.

### Robust testing

AI accelerated development, but I did not want speed to come at the cost of reliability.

RecordsTracker has a broad automated validation model that includes:

- Unit tests.
- Fixture-based extraction tests.
- Regression tests for previously observed report layouts.
- JSON-schema and contract validation.
- Data-quality checks.
- Raw-file hash verification.
- Source-traceability tests.
- SQLite/PostgreSQL parity tests.
- Idempotency tests.
- Refresh and backfill tests.
- Authentication and authorization boundary tests.
- Security and no-secret-output tests.
- Pagination and large-corpus query tests.
- Accessibility assertions.
- Documentation validation.
- Deployment configuration tests.
- Exact-route UI evidence.
- Desktop, narrow, mobile, focus, empty, partial, error, and 200%-zoom review.

When a defect is fixed, the project generally requires a test that reproduces the failure first. This prevents the same extraction, query, design, or workflow defect from silently returning.

The combination of governance, documentation, automated tests, and visual evidence enables me to build rapidly with AI while still maintaining quality and control over the results.

### Portable deployment

RecordsTracker currently runs on my QNAP NAS using Docker Compose and PostgreSQL.

QNAP was the first practical production-style environment, but the application is not written specifically for QNAP.

The runtime uses:

- Docker containers.
- PostgreSQL in Docker.
- Alembic migrations.
- Named volumes.
- Environment-based configuration.
- Health checks.
- Portable raw-artifact storage boundaries.
- Host-managed secrets.
- Documented backup and restore procedures.

QNAP-specific paths and operational details stay in configuration and deployment documentation rather than application code.

The same deployment model can be moved to:

- AWS.
- Microsoft Azure.
- DigitalOcean.
- Render.
- Fly.io.
- Railway.
- Supabase or Neon for managed PostgreSQL.
- Another Linux or Docker-capable host.

Someone following the documentation could run the application locally, on a workstation, on a NAS, or in a cloud environment without changing the core extraction, storage, review, or source-traceability architecture.

## OpenAI Build Week extension

RecordsTracker existed before OpenAI Build Week as a governed public-record ingestion and early review application. The submission is the substantial extension I created during the July 13–21, 2026 submission period.

The repository establishes this boundary:

- **Pre-Build Week baseline:**
  `bb5b1246fbf677a328c70abad48af3023fa1ebb0`
- **First eligible Build Week commit:**
  `508102077ec57dcf673142620e412ad2bf7078b1`
- **Current deployed Build Week checkpoint (not the final release):**
  `d7e9b1fff9e1826c3387a7313777d14c1480d3b4`
- **Final Build Week release:**
  `<PENDING FINAL BUILD WEEK COMMIT>`
- **Release tag:**
  `openai-build-week-2026` (must eventually point to the final accepted SHA)

The current deployed checkpoint is an intermediate accepted checkpoint. It must
not be described or tagged as the final Build Week release. Phase A merged at
`41d512127febdfd086432e7f082d0651da232e9f` with the evidence-supported
**SUPPLEMENT** decision. Build Week completion therefore includes the complete
governed dual-source ArcGIS facility-reference supplement sequence in the
[ArcGIS facility-reference completion plan](docs/planning/build-week-2026-arcgis-facility-reference-completion-plan.md):
separate immutable program and ArcGIS snapshots; ArcGIS-specific extension of
the shared facility identity, reconciliation, controlled backfill, and downstream
consumer work already completed for eligible program-reference data under
#521-#523; source-to-screen and operator reconciliation; separate governed refresh
workflows with checkpoint recovery; production deployment; and automated Hosted
acceptance.

Until every required phase is merged, deployed, and accepted, the final Build
Week SHA remains pending and tag `openai-build-week-2026` must not be moved to
the current checkpoint.

During Build Week, I added or materially expanded:

- Deterministic extraction of complaint, investigation, facility, event, and source-evidence fields.
- Canonical field allocation and SQLite/PostgreSQL parity.
- Explicit missing-value and aggregate-readiness semantics.
- Source-to-screen completeness auditing.
- Expanded complaint detail and facility review hubs.
- Governed refresh and idempotent backfill tooling.
- Large-corpus PostgreSQL performance improvements.
- A redesigned reviewer worklist.
- Explainable facility prioritization.
- Cross-facility intelligence and filtering.
- Responsive and accessible Civic Ledger implementation.
- Large-corpus pagination and exact-route UI evidence.
- Public facility-reference enrichment.
- Governed display of verified facility-type labels in current loaded data.
- Expanded facility identity projection across current reviewer pages.
- Freshness metadata and source-precedence rules.
- Production-oriented deployment, backup, validation, and release procedures.

Those completed extensions do not establish that ArcGIS is currently active,
statewide-complete, current, authoritative, or a replacement for the program
sources. Issue #490 remains completed historical evaluation evidence, and the
governed Phase A evaluation under #516 now establishes **SUPPLEMENT**: the
program-specific snapshots remain the primary source family while ArcGIS is a
separately versioned current-reference supplement. The final Build Week release
must add the remaining ArcGIS-specific dual-source implementation without
inventing a descriptive label for raw type value `733`. The original #516
replacement premise is superseded by this merged decision; it is not an
authorization to cut over, activate, or backfill ArcGIS.

These changes transformed RecordsTracker from a promising early application into a substantially more complete public-record intelligence platform.

## How Codex and GPT-5.6 were used

Before this project, I had never used Codex.

I learned it by building RecordsTracker.

Codex became the implementation engine for work that would otherwise have been beyond my technical background. It analyzed the repository and implemented coordinated changes across:

- Python application code.
- Deterministic extraction.
- Schemas and data contracts.
- Alembic migrations.
- PostgreSQL queries.
- Refresh and backfill tools.
- Test fixtures.
- Automated validation.
- Documentation.
- Deployment procedures.
- Reviewer-facing pages.
- Accessibility behavior.
- Evidence capture.

Codex was especially valuable for:

- Tracing missing data across multiple application layers.
- Implementing coordinated multi-file changes.
- Writing regression tests before applying fixes.
- Diagnosing PostgreSQL performance and pagination problems.
- Maintaining SQLite/PostgreSQL parity.
- Converting approved Figma designs into working interfaces.
- Updating code, tests, and documentation together.
- Finding root causes rather than patching only visible symptoms.

ChatGPT played a different but equally important role.

I used GPT-5.6 as:

- Architect.
- Product manager.
- UX lead.
- Source analyst.
- Security and governance reviewer.
- Issue planner.
- Prompt author.
- Evidence reviewer.
- Acceptance reviewer.

ChatGPT helped me turn conversations with attorneys into product requirements. It challenged weak ideas, separated reviewer needs from developer convenience, identified data-completeness gaps, designed source and persistence boundaries, planned work for Codex, reviewed implementation handoffs, interpreted failures, and decided whether results actually met the goal.

Connecting Figma to ChatGPT was particularly important. It let me use ChatGPT to reason directly about page structure, visual hierarchy, components, responsive layouts, and implementation variance. Instead of asking Codex to invent a design while coding, I could approve the design first and then require Codex to implement it.

I relied on AI for the technical development, but I did not outsource accountability.

I decided what to build, why it mattered, what the source evidence allowed the system to say, which design was acceptable, which risks required controls, and whether the completed work was good enough.

The production application also intentionally avoids using an LLM to infer public-record facts when deterministic extraction is possible. This preserves repeatability, auditability, and source traceability.

AI built the software with me; it did not replace the evidence or the professional judgment of the people who will use it.

## Challenges I ran into

The first challenge was that public records that look consistent to a person are often inconsistent in code.

Labels change. Values wrap across lines. Some headings contain punctuation and others do not. Older reports use different layouts. A field can be present but blank. The same concept may appear in an HTML report, a CSV file, and a facility-reference dataset using different names.

The second challenge was determining why a value was missing.

A blank field in the application could mean:

- The public source omitted it.
- The source contained it but extraction failed.
- Extraction succeeded but no canonical field existed.
- A canonical field existed but import did not populate it.
- PostgreSQL stored it but the query did not select it.
- The read model returned it but the page did not render it.

RecordsTracker now distinguishes those states rather than collapsing all of them into “not provided.”

The third challenge was scale.

Queries that worked perfectly against tiny fixture datasets either failed or slowed down against a real PostgreSQL corpus. I had to replace inefficient access patterns, add bounded pagination, verify first, middle, and final result pages, and test filtered, empty, narrow, mobile, keyboard, and zoomed states.

The fourth challenge was user experience.

Codex could make a functional page, but functionality was not enough. Attorneys should not need to understand database schemas, connector metadata, import batches, or extraction internals just to review a complaint.

The ChatGPT and Figma workflow helped me separate:

- What attorneys need to decide.
- What belongs in Help.
- What operators need for diagnostics.
- What developers need for debugging.
- What must remain available for traceability without dominating the page.

The fifth challenge was building for future jurisdictions without pretending that every state publishes equivalent data.

A multi-state platform must preserve differences in terminology, record availability, update schedules, source reliability, and legal context. RecordsTracker therefore expands through governed source connectors and inventories rather than one universal scraper.

## Accomplishments that I’m proud of

I am proud that RecordsTracker became far more than the original request for a scraper.

Starting only in June 2026, and without a software-development background, I built a working system that combines:

- Public-source discovery and retrieval.
- Raw evidence preservation.
- Deterministic extraction.
- Governed canonical storage.
- PostgreSQL persistence.
- Facility enrichment.
- Large-corpus analysis.
- Explainable prioritization.
- Reviewer-created workflow state.
- Accessibility.
- Responsive visual design.
- Automated validation.
- Production-style deployment.
- Detailed operational documentation.
- A governed architecture for future states and sources.

Specific accomplishments include:

- Every derived record retains a path back to preserved source evidence.
- Reviewer-created notes and statuses cannot overwrite source-derived facts.
- Missing and unavailable data are not misrepresented as zero.
- Facility-type identifiers are translated into understandable labels.
- Facility identity is projected consistently across reviewer surfaces.
- Refresh and backfill operations are bounded, repeatable, and idempotent.
- Cross-facility indicators remain explainable instead of becoming an opaque risk score.
- Large datasets are queried and paginated without fragile deep-offset behavior.
- Accessibility is treated as a release requirement.
- Important pages are designed in Figma before implementation.
- Exact-route evidence is compared with approved design references.
- The application runs in a production-style PostgreSQL and Docker environment.
- The deployment model is portable beyond the QNAP where it currently runs.
- The repository contains enough documentation and governance for another person or AI agent to understand how to operate and extend it safely.
- The architecture can support new jurisdictions without sacrificing source traceability.

The speed of the transformation is one of the most remarkable parts of the project.

In June, this was a question in a Signal chat.

Then it was a small proof of concept.

Then it was a transcribed call with an attorney.

Then it was a local data pipeline.

Then it became a hosted reviewer application.

Then it gained facility intelligence, worklists, complaint review, PostgreSQL storage, backfill tooling, a design system, responsive layouts, governance, testing, deployment, and a roadmap for multi-state expansion.

I had never used Codex before any of this.

## What I learned

I learned that a person does not need to become a conventional programmer before building meaningful software with AI.

But building good software still requires judgment.

The most important skills I brought were:

- Understanding the problem.
- Listening to the intended users.
- Asking precise questions.
- Defining boundaries.
- Recognizing risk.
- Rejecting weak results.
- Preserving decisions.
- Testing assumptions.
- Demanding evidence.
- Knowing why the product should exist.

I learned that reliable public-data products require clear answers to four questions:

1. What did the source actually provide?
2. How was the displayed value derived?
3. What happened when the source was incomplete, unavailable, or conflicting?
4. What should the reviewer do next?

I learned that passing automated tests is necessary but not sufficient. A page can pass every test and still be confusing. A query can work on fixtures and fail at real scale. A field can exist in the database and still disappear before reaching the screen.

I learned that Codex works best when I provide:

- A concrete user outcome.
- Explicit constraints.
- Clear acceptance criteria.
- Prohibited behaviors.
- Focused regression tests.
- Documentation requirements.
- Stop conditions.

I learned that ChatGPT works best as more than a code generator. It became most valuable when I used it to connect user needs, architecture, evidence, design, implementation planning, and acceptance review.

I also learned that Figma gave me something AI-generated code alone could not: a place to see, compare, approve, and govern the product before implementation.

Finally, I learned that extensibility must exist in the governance as well as the code. Adding another state is not merely writing another scraper. It requires understanding the jurisdiction, agency, source terms, identifiers, update cadence, available records, parsing risks, missing-data semantics, and limitations.

## What’s next for RecordsTracker

The immediate next steps include:

- Scheduled governed facility and complaint refresh.
- Additional California record types, including visits, inspections, citations, deficiencies, and plans of correction.
- Stronger annotation and correction workflows.
- Additional packet and source-traceable export capabilities.
- Coverage and freshness monitoring.
- Broader geographic, licensee, and operator-level pattern review.
- More complete facility identity reconciliation.
- Additional explainable oversight and trend indicators.
- Carefully governed onboarding of sources from other states.

I plan to expand RecordsTracker jurisdiction by jurisdiction.

Initial research includes states such as Idaho and Tennessee, whose public systems differ significantly from California’s. Some provide searchable inspection databases, some publish provider lists, and some offer facility lookups without downloadable complaint packages.

RecordsTracker’s connector architecture makes it possible to add those sources while preserving:

- The original state-specific evidence.
- Source URLs and timestamps.
- Raw artifacts and hashes.
- Source-specific terminology.
- Jurisdiction-specific limitations.
- Shared reviewer workflows.
- Clear separation between source facts and reviewer-created work.

The current design system also supports that future.

A jurisdiction selector, new source-aware filters, state-specific terminology, additional facility types, new record categories, and new reviewer workflows can be added through the established patterns rather than redesigning the product for every source.

Over time, RecordsTracker could help public-interest teams:

- Compare facilities within a state.
- Identify recurring operator-level patterns.
- Review complaints and enforcement activity.
- Detect gaps in monitoring or follow-up.
- Preserve direct links to original evidence.
- Understand differences between jurisdictions.
- Avoid misleading comparisons when state data is incomplete or incompatible.
- Build stronger case, policy, and advocacy research with less repetitive manual work.

My long-term goal is to create a durable public-interest records platform for attorneys, advocates, researchers, and oversight professionals, especially those serving vulnerable children and operating without the resources available to large private firms.

RecordsTracker began with one attorney asking whether AI could scrape a difficult website.

What it has become is evidence that a non-developer, working with Codex, ChatGPT, and Figma, can rapidly build a governed, tested, portable, and potentially high-impact product around a real human need.
