---
name: street-validator-radar-handoff
description: Maintain the Street Validator to Watchlist Radar card handoff, including provenance, measurement licensing, missing checks and schema compatibility. Use for validator cards or Radar integration, not for the frozen own-target pitch path.
---

# Street Validator to Radar handoff

Read the validator project's current winning spec, CLAUDE.md and PROGRESS.md. At creation the approved spec was v2.2, but verify before work. GitHub default-branch prose can lag the local approved checkout.

The automatically refreshed Radar is the immediate product. Existing checks and partial cards may be used without waiting for Check 3 or new valuation research.

- Preserve Decimal calculations, declared fact/derived/external provenance, and the rule that AI narrates supplied numbers rather than computing them. Verification verdicts are independent of stock direction and Radar priority.
- Missing checks remain `not_supplied`; unavailable evidence is explained. A measurement has no invented claim verdict. Rebuild a target chain before deriving assumptions from it.
- For comparisons, verify ticker, metric, period, basis, unit and source/as-of identity. Do not infer these from prose or fill missing consensus with an estimate.
- Treat licensing transitively: a derived measurement depending on licensed input is licensed. Check-level measurements need their own provenance/licence carrier; claim-only redaction is insufficient. Public values require explicit public classification, with unknown labels suppressed or refused. Local licensed inputs stay local.
- A new card representation must include schema compatibility and matching Radar redaction before production use. Test current cards and malformed/missing fields. Draft unresolved spec changes for disposition; this skill grants no spec exception or publication authority.
- Use synthetic or permitted local cards to test the boundary. Keep samples separate from historical cards. Record refusal reasons rather than crashing an otherwise valid daily scan on one malformed optional card.

Follow existing testing and Git skills as applicable. Work only in the assigned project. Return exact schema effects, a representative artifact, pass/skip/fail counts and remaining decisions. Coordinate consumer changes through Radar's owner; never silently update both repositories.
