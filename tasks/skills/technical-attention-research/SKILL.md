---
name: technical-attention-research
description: Evaluate Admiralty technical signals for Watchlist Radar, separating signal correctness, attention usefulness and trade performance. Use for VCP, MACD, Bollinger plus RSI and Heikin Ashi research or signal exports; not for WorldQuant BRAIN submission.
---

# Technical attention research

Read the Backtesting project's current instructions, approved research state, implementations and callers. The daily Radar webpage is the delivery priority; new research cannot become a prerequisite for publishing existing supported signals.

## Reuse from BRAIN, adapted to local research

The source skills are `C:/Users/user/.claude/skills/wq-brain-alpha-optimization-v1/SKILL.md` and `C:/Users/user/.agents/skills/brain-datafield-exploration-general/SKILL.md`. This skill adapts their frozen baseline, preflight, coverage probes, recorded failures and incremental comparisons. It does not invoke their platform workflow.

- Freeze the strategy/data versions before comparisons; preserve unsuccessful runs. Diagnose execution failures separately from a valid negative finding. Avoid repeating an axis whose outputs are identical.
- Probe actual local data directly: coverage, missing versus genuine zero, timestamp/update frequency, units/bounds, typical values and distribution. Include corporate actions and symbol mapping. Do not substitute a BRAIN long/short-count proxy for actual coverage.
- State one indicator purpose and one falsifiable question first. Use native strategy windows justified by that hypothesis. No Rule-of-8, BRAIN operator limits, fixed economic-window vocabulary, Sharpe/Fitness thresholds, correlation/submission gates or automatic promotion apply here.

## Deliver the smallest useful slice

1. Identify existing implementations and their real callers. Check prefix invariance: a historical signal must be unchanged when future observations are removed. Universe eligibility must use information available at the signal timestamp.
2. For operational export, use completed bars, explicit exchange/timezone and raw/adjusted price basis. Preserve VCP scanner interfaces and strictness. Distinguish detector minimum contractions from actionable-tier criteria; verify their current values instead of guessing.
3. Emit a small per-ticker signal record: identity, purpose/state, bar/as-of time, price basis, reference levels, code/version identity and coverage. Unsupported or failing implementations are unavailable, never neutral or silently repaired during export.
4. For performance research, preregister sample, signal definition, endpoint/horizon, controls, data/code hashes, chronological evaluation and stopping rule. Attention enrichment measures unusual future activity or relevant events; it does not establish a profitable trade. Trade claims additionally need execution timing, costs, liquidity and exits. Overlapping observations need appropriate dependence treatment.
5. Run deterministic checks within the assigned scope. Official experiments require the project's approved execution owner and gate. Preserve old artifacts when their hashes differ; do not attach old performance to current code.

Keep combined indicator scoring as a separate future hypothesis. An exported signal can be correctly calculated yet historically unvalidated; publish that evidence state accurately.

## Delegation and report

One owner maintains shared data/evaluation contracts. Propose a strategy-specific worker only with exclusive files, an independent deliverable and a bounded comparison budget. Data/execution workers follow the project's ownership rules. Deployment starts only for a reviewed operational artifact.

Report status, signal correctness, exact check outcomes, artifact paths, compatibility effects and next decision. Never relabel skipped, synthetic or failed checks as live/performance validation.
