# Watchlist Radar takeover and continuation plan

Reviewed 8 October 2026 HKT. Owner's updated first priority: a daily automatically refreshed webpage supporting the trading workflow. Start with a vertical slice of Task 6 plus essential Tasks 1-2 safeguards. Keep the current Python scanner and static page; extend them in small slices.

## Where work stopped

- Local `main` and GitHub `main` both resolve to `3e3e3669484f011bdb599d6ad9860fedf6d1d0f3`: the 2 October run, following v1.1 (`7e7f6d7`). No open issues or PRs were returned by the GitHub searches.
- Latest saved run: 2 October 2026, 23:16 HKT / scan started 11:10 ET; 431 names, 426 with history, 34 watchlist names, five picks. News review reports 58/58 names, with 416 returned headlines marked DeepSeek-checked. One Street Validator card, MU. These are historical snapshot facts, not current market observations.
- Existing: earnings calendar/options context, VCP, squeezes, news review with keyword fallback, theme-peer earnings, levels, sortable watchlist, historical scoreboard, public/local validation-card rendering.
- Missing: market overview, independent news-led discovery, change-since-last-scan view, refresh health, scheduling, and usable personal feedback.
- Operation is manual: `radar.py` scans and writes outputs; `--publish` stages the page and run, commits, then pushes. Browser reload only reads the published snapshot. No workflow exists in the remote tree.
- Current purpose is attention prioritization. The additive score measures flags, not expected return, calibrated probability, or suitability to buy. Larger absolute moves can include declines.

## Verification and findings

All ten existing offline tests passed using Python 3.14 and a fresh `--basetemp` under ignored `local/`. The first attempt had nine passes and one fixture-setup error because the sandbox temporary directory was inaccessible; changing only the temporary location resolved it. Both stored snapshots rendered successfully in memory. No live OpenD scan, paid AI call, browser interaction, or deployment verification was performed.

Offline reproductions beyond the existing suite:

1. `apply_review` accepts strings `"false"` for both verdict booleans and keeps the headline: `bool("false")` is true. Validate the model response before merging it.
2. `redact_card` retains a claim whose source has no `licence`. Public output should accept explicitly public claims only; unknown labels must not expose values. No actual leakage is claimed from the saved MU card.
3. `run_outcomes` counts the next available bar as the next session. Removing Tuesday from a Monday/Tuesday/Wednesday fixture makes Wednesday the one-session outcome.

Code inspection also finds:

- Failed news retrieval and a deliberately skipped search both become an empty news list; the page can show zero news without explaining coverage. `--no-news` still renders wording that news was checked.
- News searches target watchlist names and a subset selected by earnings, actionable VCP, squeeze or current move. An otherwise unflagged outsider with material news can be missed. Peer-only and quiet-volume-only names are also absent from that selection unless another condition qualifies them.
- `scoreboard` calls the current `score()` on old rows rather than using frozen flags; old observations can change meaning after rule changes. Outcomes are available only for names with frames in the current universe. Two saved runs cannot establish a durable edge.
- Calendar windows use weekdays, not exchange sessions. Daily-bar completion uses a fixed 16:15 ET cutoff, with no early-close treatment. Option estimates can fall back to last trades without freshness or spread checks.
- VCP imports an absolute external folder. If `LEG_FLOOR` is absent, the check returns unknown; unknown currently remains eligible for VCP points. Preserve the detector; make version and diagnostic availability visible.
- VCP helper frames have adjusted OHLC and raw close. Displayed levels compare adjusted high/low/pivot values with a raw live quote. Normalize display units at the boundary without changing detector inputs.
- The table sort is mouse-click only; summaries and dense tables dominate the page. Browser/mobile accessibility still needs runtime verification.

## Reference projects: what to reuse

- [Fund Coverage Dashboard](https://github.com/Bobksl/Fund-Coverage-News-Dashboard): reuse interaction patterns for dates, filters, source disclosures, review state and partial-failure notices. Its [frontend notes](https://github.com/Bobksl/Fund-Coverage-News-Dashboard/blob/main/docs/dashboard-events-and-reports.md) describe these patterns; counts in that document are dated, not current. Do not transplant its credit-sector taxonomy or ranking weights.
- [Stock Pitch Engine](https://github.com/Bobksl/Stock-Pitch-Engine): GitHub default-branch README/PROGRESS still describes the older pitch project. Local `../Equity Filings RAG` is on `v2-street-validator` (`456e926`) with approved spec v2.2. The live remote branch listing has no `v2-street-validator`. Local PROGRESS names checks 1 and 2 as built, checks 3–5 not supplied, and a MU card; Radar already consumes that contract. Its next engine task is Check 3, not another Radar card renderer. This is a separate project dependency, not authorization to publish its local branch.
- Keep validator claims independent from attention ranking. A confirmed claim or arithmetically consistent target does not imply a stock should rise.

## Ordered action plan

Each task is a proposed increment, not an implemented feature. Estimates are rough focused-work-session sizes and exclude delays from vendors.

Updated order: daily Windows collection/publication and freshness first, incorporating required coverage/public-output/timing protections. New strategy experiments, Check 3 and composite scoring are optional enrichment, not prerequisites for the daily release. The owner confirmed Windows scans and automatic publication; their computer can remain on. Default proposed scan time is 10:00 ET on US exchange sessions. Actual schedule activation and live publication status must be recorded separately from code/tests.

### Task 1 — Make coverage and public output trustworthy (1–2 sessions)

Files: `radar.py`, `page.py`, `test_radar.py`, `README.md`. Dependency: none.

Acceptance:
- Persist and display per-ticker news state: successful, skipped, failed, plus AI-reviewed versus keyword fallback; show missing history and stale quotes explicitly. Unknown data earns no claim of absence.
- Reject malformed AI verdicts, indices, duplicate verdicts and tag shapes; fallback is visibly unreviewed. Require explicit `public` licensing for public claim values; validate imported card shape and retain licensed verdict counts.
- A failed critical stage/render keeps the last good page. Validate complete output before atomic replacement; retain actionable failure details.

Verify: focused tests for malformed AI JSON, unknown licensing, missing history, skipped news and stage failures; render old snapshots for compatibility and compare public/local redaction. Existing tests stay green.

### Task 2 — Correct timing and price reference units (1 session)

Files: `radar.py`, `page.py`, `test_radar.py`, `README.md`. Dependency: Task 1.

Acceptance:
- Use actual US exchange sessions for earnings windows and completed-bar decisions; cover holidays, early closes and after-hours scans. Reuse an available calendar if suitable; avoid maintaining a guessed holiday list.
- Convert technical display levels to the current raw-price basis, while keeping adjusted inputs inside the VCP detector. Record the VCP revision and leg-floor check availability; label unknown checks.
- Label option quotes with their timestamp/basis; suppress stale, crossed, empty or incompatible-strike estimates rather than showing false precision.

Verify: deterministic holiday/early-close, split/dividend adjustment and option-chain fixtures; assert detector input values remain unchanged. Document the calendar source and dependency choice.

### Task 3 — Build the daily attention view (1–2 sessions)

Files: `radar.py`, `page.py`, `test_radar.py`, `README.md`. Dependencies: Tasks 1–2.

Acceptance:
- Add a small market pulse from timestamped benchmark and scanned-universe data: market direction, breadth among scanned names, leading/lagging groups. Label limited-universe breadth precisely; AI narrates supplied figures only.
- Show two clear lanes: prioritized watchlist names and outside-watchlist discoveries. Keep the opening view to a few cards, each with why now, next event/time, risk, reference level and coverage. Let details expand below.
- Show new/changed/resolved flags versus the previous comparable scan, with ticker search, watchlist/theme filters and keyboard-accessible controls. No surprise reordering from language or formatting changes.

Verify: saved/synthetic scans with no prior run, mixed coverage and changed flags; real-browser keyboard checks and narrow-screen layout. Keep ranks deterministic and explain tie-breaking.

### Task 4 — Discover outsiders through news (1–2 sessions)

Files: `radar.py`, `page.py`, `test_radar.py`, `README.md`. Dependency: Task 3.

Acceptance:
- Add one bounded market/sector news discovery pass independent of existing technical flags. Prefer company releases/filings for confirmation; headlines remain headline-level evidence.
- Resolve a candidate to a verified ticker, then apply the existing price/cap/universe policy and quote/history checks before ranking. Label excluded or uncovered candidates; do not silently expand to all markets.
- Group duplicate coverage of an event and persist its identity; repeated articles cannot inflate the multi-news bonus. Record sources, review state and explicit API/AI request caps.

Verify: a news-only outsider reaches the discovery lane; ambiguous names are refused; duplicate coverage does not boost rank; request limits stop work visibly. Do not search every ticker on every run.

### Task 5 — Make the scoreboard faithful to each scan (1 session, then accumulate observations)

Files: `radar.py`, `page.py`, `test_radar.py`, `README.md`. Dependency: Task 2; collection can continue while Tasks 3–4 are built.

Acceptance:
- Save scoring version, frozen flags/weights and relevant dependency versions; never reclassify old runs using today's rules. Mark legacy rows separately if frozen flags are absent.
- Fetch outcomes for archived names too, use exact session targets, handle corporate actions consistently, and distinguish missing from not-yet-mature outcomes.
- Show sample/run counts and separate attention quality (absolute movement/event relevance) from direction. Preserve chronological holdout evaluation before any learned weighting; overlapping runs are not independent samples.

Verify: changed-rule, removed-ticker, missing-bar, split and immature-horizon fixtures. Report current evidence as descriptive; no automatic weight tuning from two runs.

### Task 6 — Make refresh repeatable (1 session)

Files: `radar.py`, `test_radar.py`, `README.md`, optional local scheduling script. Dependency: Tasks 1–3.

Acceptance:
- Add a short setup/dependency guide, dependency check and configurable VCP root. Preserve the external detector's API and use a known revision.
- Start with a local scheduled run because OpenD and local validator files are required. Compute scan time from US session time so HKT changes with US daylight saving. Show last success, failure and next planned scan.
- Prevent overlapping scans and separate scanning from optional public publication; a failed scan must not publish. Stage only intended artifacts and do not include unrelated pre-staged files in an automatic commit.

Verify: simulated offline OpenD, overlapping jobs, failure recovery and publication-scope tests. Installation and publication settings need an explicit implementation decision; this review creates no schedule or remote changes.

### Task 7 — Add minimal personal feedback (1 session)

Files: `page.py`, `test_radar.py`, `README.md`. Dependency: Task 3.

Acceptance:
- Allow interested/dismissed/snoozed state, a short thesis and next review date on the local page, using browser storage with export/import. State clearly that it does not sync across devices or edit `watchlist.txt`.
- Preserve ticker identity, private notes and licensed claims locally; apply snoozing to the view without rewriting historical ranks or outcomes.
- Surface Street Validator as-of dates, unverified claims and absent checks; do not turn verdict counts into buy scores. Check 3–5 development stays in the validator project under its spec.

Verify: reload, export/import, expiry and public-output exclusion checks. Add a private backend only if multi-device synchronization becomes a real requirement.

## Deliberately deferred

No frontend framework rewrite, database, autonomous trading, calibrated probability claims, full filings ingestion inside Radar, or learned weights yet. Technical indicator research proceeds separately under the coordination decision below. The next useful Radar release is trustworthy coverage plus a compact market/watchlist/discovery view.

## Coordination decision — 8 October 2026

The owner authorized separate project chats and delegated decisions about further splitting to the Radar coordinator. Start with one active owner per workstream:

- Street Validator: project `Stock Pitch Engine`, chat `01a11732-eb2e-7031-b0d4-0aec4a6e294b`, first bounded approved Check 3 slice. Owns that project's code/tests/docs; preserves the existing card contract.
- Technical research: project `Backtesting`, chat `01a11733-0aed-7073-b9de-b99697df4708`, first inventories VCP/MACD/BB+RSI/Heikin Ashi and proposes the evaluation contract and first research slice. Initial scope is inspection, documentation and deterministic checks; no new official performance experiments or deployment.
- Radar reliability and integration: this chat `01a1171f-ad54-7aa1-bb17-bd7718a39db7`. Task 1 remains the next Radar implementation increment.

The owner agrees each indicator should start with its specific purpose. A combined indicator score remains a future research problem, with evaluation before incorporation into Radar.

Approve a narrower worker only when it has exclusive ownership, a concrete independently verifiable deliverable, agreed input/output contracts, and useful work that does not depend on another worker's unfinished decision. Strategy workers can share frozen data and one evaluator; do not create separate datasets or competing backtest assumptions per indicator. A fresh reviewer can help at checkpoints. Keep data preparation and official execution ownership explicit; create a deployment worker only when a validated candidate is actually ready for an approved operational stage.

Each project owner reports status, artifact paths, verification scope, interface effects, blockers and the next decision. The coordinator reads the chats and sends authorized follow-ups. These are separate project chats; creating them does not establish an automatic permanent supervisor or scheduled monitoring.

Follow-up dispatched after inspecting both first deliveries:

- Validator: Check 3 awaits a concrete metadata/provenance/licensing/schema disposition. Preserve current cards for the daily page; produce an exact synthetic future-contract example and compatibility recommendation without activating a new schema. Initial evidence: 41 focused tests passed, nine fact-dependent skipped, full-suite collection blocked by tokenizer DNS errors.
- Backtesting: prioritize unchanged VCP operational export readiness and deterministic interface checks. MACD prefix-invariance failure, incomplete Heikin Ashi strategy, BB+RSI setup/evidence gaps and historical hash mismatch remain disclosed. No official experiment is approved. Initial report: three existing synthetic tests passed, inventory checks nine passes/three failures.
- A bounded Radar delivery worker owns scanner/page/scheduler/test implementation; coordinator owns this plan and project-local skills. Further strategy splits await independent deliverables and the shared evaluation contract.

Project-local skills live under `tasks/skills/`: `technical-attention-research`, `street-validator-radar-handoff` and `radar-daily-refresh`. Each passed skill-creator frontmatter validation and was supplied to its responsible chat/worker by explicit path. They are not claimed installed in the global skill catalogue. Original BRAIN skills remain unchanged; only applicable research discipline is adapted.

## Review checkpoint

After Tasks 1–3: all offline tests pass, an explicitly authorized real scan completes, public/local output is checked, browser/mobile interactions work, and you can answer in under a minute: what changed, which watched names matter, which outsider merits research, and what data is missing. Then decide whether news discovery or refresh convenience is the greater need.
