# Future Visualization Concepts

This document captures follow-up ideas for analytic and UI components that build on the existing Performance Overview work. Each section outlines the concept, what it would visualize, the data required, and early implementation considerations.

## 1. Position Response Curves
- **Goal:** Show how opponents react to different preflop sizing choices in comparable spots (fold/call/raise rates, resulting EV) so we can pick sizings that keep dominated hands in.
- **Primary View:** Multi-line chart where the x-axis is bet sizing expressed as pot ratio and the y-axis is villain response frequency (fold, flat, 3-bet). Include an EV overlay or tooltips with chip EV.
- **Inputs:** Aggregated DriveHUD hand histories grouped by table size, hero position, stack depth bucket, and villain archetype (VPIP/PFR buckets). Requires storing the frequency with which each sizing was used and the downstream outcome.
- **Implementation Notes:** Builds on the current `bet_sizing` helpers. We should cache pre-aggregated sizing buckets (e.g., `var/cache/preflop_response_curves_v1.json`) to avoid recomputing on demand.

## 2. Counterfactual Premium-Line Explorer
- **Goal:** Evaluate what would have happened if we changed hero’s flop or preflop line for premium holdings (AA/KK/QQ/AKs) to alternative sizes or all-ins, using historical villain response data.
- **Primary View:** Scenario picker (hand class, position, stack depth) with a stacked bar or table comparing actual EV vs simulated EV for alternative sizings. Include variance bands to show sample uncertainty.
- **Inputs:** Observed premium hands, villain response frequencies from the response-curve aggregation, and simple EV calculation logic to replay alternate lines.
- **Implementation Notes:** Needs a helper that maps from a hypothetical size to expected fold/call/raise frequencies. Could live in a `counterfactual` service that reuses our DriveHUD adapter and caches per-position results.

## 3. Population Propensity Heatmap
- **Goal:** Model villains’ likelihood to continue versus fold given a bet size, and surface the model output as a heatmap by position and stack depth.
- **Primary View:** Matrix (position vs sizing bucket) colored by continuation probability. Secondary card showing recommended size range for maximum stack-off probability.
- **Inputs:** Training dataset of preflop decisions with features: bet size ratio, effective stack, position, player archetype, blind level. Simple logistic regression or gradient-boosted tree trained offline and serialized.
- **Implementation Notes:** Store model outputs per discretized bucket so the UI query stays fast. Expose API at `/api/preflop/propensity` returning probabilities and confidence intervals.

## 4. Premium Hand Induction Dashboard
- **Goal:** Dedicated dashboard to understand how well premiums extract value when not all-in preflop.
- **Primary View:**
  - Left column: grid of summary cards (VPIP vs our raises, average 4-bet frequency, EV per hand) segmented by villain archetype.
  - Right column: stacked bar or area chart showing money won by line (3-bet, 4-bet, flat) and a small multiples table showing call frequencies by sizing.
- **Inputs:** Filtered DriveHUD hands tagged as premiums, aggregated by line, sizing bucket, villain archetype, and table size.
- **Implementation Notes:** Shares queries with the response curves; build a shared premium-hand cache to keep extract time low.

## 5. Stack-Off Probability Simulator
- **Goal:** Estimate probability of getting stacks in preflop for a chosen hand class and sizing sequence across multiple villains.
- **Primary View:** Interactive simulator UI where users choose hand class, positions behind, and sizing steps; output a probability gauge plus a fan chart over stack depth.
- **Inputs:** Historical continuation probabilities, seat count distribution, and hero equity vs villain calling ranges (from `/api/preflop/shove/equity`).
- **Implementation Notes:** Needs a small simulation engine that iterates through positions applying continuation odds. Could reuse our cumulative net line chart style for probability over stack depth.

## 6. All-In Call Range Revealer
- **Goal:** Show what ranges opponents call all-ins with after we shove (open-shove or jam over a raise), helping decide when to induce vs jam.
- **Primary View:** 13×13 hand-grid heatmap showing call frequencies and EV, similar to the existing preflop shove explorer but filtered by inducing scenarios.
- **Inputs:** All-in hands from DriveHUD, aggregated by effective stack and position, with hero/villain equity outcomes.
- **Implementation Notes:** Likely an extension of `/api/preflop/shove/ranges`. Need to label scenarios (open-shove vs 4-bet jam) and version the cache.

## Shared Considerations
- Build adapters so new extracts piggyback on `DriveHudDataSource` and land in `var/cache/` with explicit versioning.
- Introduce property-based tests for bucket/aggregation helpers to guard against regression when we add new sizing definitions.
- Keep UI components modular: each visualization should accept pre-aggregated data plus formatting metadata, mirroring the existing Performance Overview design.
- Document any new data contracts in `AGENTS.md` and extend API schemas once we decide which ideas to prototype first.

