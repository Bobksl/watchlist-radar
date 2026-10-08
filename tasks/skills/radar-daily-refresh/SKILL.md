---
name: radar-daily-refresh
description: Extend Watchlist Radar into a daily automatically refreshed static webpage, preserving source coverage, last-good output and local/public separation. Use for scan scheduling, publication, refresh health and daily dashboard delivery.
---

# Daily Radar delivery

Reuse `radar.py`, `page.py` and existing tests. Prioritize a complete collect/validate/render/publish/read path over research expansion. Read current callers and output conventions before changes.

## Resolve the execution location

The current collector requires logged-in Windows OpenD, an external Admiralty detector and local validator cards. A GitHub-hosted schedule cannot access those automatically. Distinguish two choices explicitly:

- Local scheduled collection with static public hosting: the computer/session and OpenD must be available; failures are visible.
- Hosted independent collection: requires approved reachable data sources and a deployable detector or clearly labeled omissions. Do not imply cloud independence while retaining local paths.

Prepare common reliability work while execution location is unresolved. Keep registration and live recurring work separate from dry-run implementation and tests. Never create a Codex heartbeat as a substitute for the webpage's data-refresh pipeline.

## A working daily slice

1. Define the default cadence relative to the US trading session, convert for HKT/US daylight saving and honor exchange holidays/early closes. Keep an explicit manual trigger and document source timing.
2. Record per-source/per-ticker coverage: success-empty, skipped, error, stale, AI-reviewed and keyword fallback are different states. Optional-card/news failure must not imply confirmed absence.
3. Validate model booleans/indices/tags and imported cards. Restrict public claim and measurement values to explicit public provenance. Leave licensed cards/notes/keys in ignored local storage.
4. Render and validate new artifacts before replacement. Preserve last-good content on failure; publish refresh health separately so readers can see when success stopped. Avoid overlapping scans and unbounded retries/API spend.
5. Publish only the intended public artifacts. Never sweep pre-staged unrelated changes into an automatic commit. Verify remote publication before claiming delivery; record push/deploy failure separately from scan success.
6. On the page show last success, current coverage and stale/failure state. A reload loads a snapshot; automatic browser polling is a separate behavior and should be specified if needed. Use a few attention cards with source/time, next catalyst, risk and reference levels; keep details collapsible.

## Verification

Use offline fixtures for failure retention, mixed coverage, licensing, overlap, session timing and publication scope. Verify desktop/mobile and keyboard flows for UI changes. A scheduler dry-run or saved-snapshot render is not proof of a live scan, automatic execution or deployment. Report each boundary precisely.

Existing general CI/CD, frontend, browser-testing and Git skills can support the work when applicable; translate their examples to this Python/static project without adding a new frontend stack or unnecessary services.
