# Line Explorer – Implementation Plan

## Goals
- Support arbitrarily defined betting lines from preflop through river using a declarative sequence of action steps.
- Surface responder hand distributions and response outcomes at the focal moment, with hero excluded and stakes filtered via `StakePolicy`.
- Provide a UX that lets analysts compose lines intuitively, save presets, and compare scenarios without juggling dozens of independent filters.

## Scope Overview
1. **Line description model** – a normalized structure representing the path from hand start to focal action, including actors, action families, sizing constraints, and board tags.
2. **Backend services** – ingestion + aggregation that accept the line descriptor, filter DriveHUD events, and emit rich metrics (hand mix, response mix, pot/equity deltas, contextual metadata).
3. **Frontend experience** – timeline-based line builder, synchronized result tables/cards, saved line management, and responsive layout.
4. **Testing & cache discipline** – unit/integration coverage for new services, deterministic sample payloads for the frontend, and versioned caches under `var/cache/`.

## Data Requirements
- **Line steps**: round (preflop/flop/turn/river), actor role (hero, population, aggressor, responder), action type (check, bet, raise, call, fold), sizing bucket (pot ratio, absolute BB, all-in flag), and optional qualifiers (multiway count, position, texture tags).
- **Focal point metadata**: pot size before action, SPR, player counts remaining, aggressor identity, hero positional snapshot.
- **Responder details**: primary hand classification + draw flags (reuse `flop_hand_categories`) and potential future extensions (turn/river board interaction, stack depth buckets).
- **Outcome aggregates**: fold/call/raise counts, continuation to later streets, pot contribution on flop and remaining streets, EV proxies if available.
- **Filtering**: stake policy, hero exclusion, time windows (future), table size, player pool segments.

## Backend Architecture
1. **Descriptor schema**
   - Add `LineStep` dataclass capturing round, actor role, action family, sizing filter, and optional tags.
   - Introduce `LineDescriptor` (ordered tuple of `LineStep`, focal context definition).
   - Provide parser/validator for incoming JSON payloads (driven by API request).
2. **Event extraction**
   - Extend `collect_line_events` to accept `LineDescriptor` and traverse hand histories, accumulating pot/pot share metrics across rounds.
   - Cache raw extracts keyed by stake + descriptor hash (`line_query_<hash>.json`).
3. **Aggregation services**
   - Build `line_query.py` service producing:
     - Response distribution metrics (fold/call/raise, continuation, breakeven fold %, fold surplus, pot share rows).
     - Responder hand breakdown (groupable into presets).
     - Context summary block (player counts, SPR, position snapshots).
   - Ensure results include bucket metadata, ratio averages, and underlying sample sizes.
4. **API layer**
   - Add endpoints:
     - `POST /api/lines/query` – returns combined response + context.
     - `POST /api/lines/hand-breakdown` – hand mix only (powering multiple tables).
     - Potential `GET /api/lines/templates` – list of curated line presets for the builder.
   - Enforce versioning + cache invalidation, surface `using_sample` flag for empty datasets.
5. **Testing**
   - Unit tests for descriptor parsing/validation, aggregation math, cache key derivation.
   - Integration tests with synthetic hand histories covering multiway, raises, all-in, and mixed streets.

## Frontend Architecture
1. **State model**
   - Global `LineBuilderState` capturing steps, filters, and focal settings.
   - Derived selectors feeding hooks (`useLineQuery`, `useLineHandBreakdown`, `useLineTemplates`).
2. **Line builder UI**
   - Timeline composer: each step rendered as a chip with quick-edit modal (action, actor, sizing).
   - Preset gallery and “save line” workflow (local storage initially).
   - Validation feedback for impossible combos (e.g., double raise without intermediate call).
3. **Results layout**
   - Context header card summarizing line, player counts, pot sizes.
   - Response table (per current flop matrix design) with row-level gradients.
   - Hand breakdown table with grouped/ungrouped toggles and consistent column widths.
   - Metric cards for pot share, SPR changes, future street contributions.
4. **Interaction patterns**
   - Auto-refresh on builder change with debounce + loading skeletons.
   - Compare mode (queue two descriptors side-by-side) — optional later milestone.
   - Persistent query string serialization for deep links.
5. **Testing**
   - Storybook stories for builder components.
   - Vitest/unit tests for reducers/selectors, React Testing Library for fetch flows.
   - Playwright smoke test: compose line, view results, toggle groupings.

## Milestones & Deliverables
1. **Milestone A – Backend foundation**
   - Descriptor schema, endpoint contract, minimal aggregation (response + hand mix).
   - Unit tests + cache versioning.
2. **Milestone B – Frontend prototype**
   - Basic line builder (linear steps), results tables wired to live data, loading/error handling.
3. **Milestone C – UX polish & analytics**
   - Presets, saved lines, advanced metrics (breakeven fold, pot share, SPR cards).
   - Responsive layout & accessibility audit.
4. **Milestone D – Validation & docs**
   - Integration tests, sample payloads, updated AGENTS.md + README sections, onboarding guide.

## Status Snapshot
- ✅ Descriptor parsing, hashing, and cache-aware aggregation live behind `POST /api/lines/query`.
- ✅ Initial line-builder state model and React hook (`useLineQuery`) with sample fallback.
- ✅ Prototype Line Explorer page with configurable response/filter controls and synced response/hand tables.
- ✅ Builder presets and hero-exclusion toggle wired end-to-end through the new line query pipeline.
- ⏳ Extend aggregation to support richer qualifiers (board textures, stack depth) and expose preset descriptors.
- ⏳ Persist user-defined lines and add comparison mode / timeline UI polish.
- ⏳ Replace the linear builder with a timeline composer capable of representing arbitrary sequences and branches.

## Table-Oriented Line Composer Blueprint

### Goals
- Present the hand from a top-down table view so analysts assign actions seat-by-seat.
- Use positional presets (6-max, full-ring, heads-up) with quick seat toggles for in/out of play.
- Let each seat specify street-by-street actions via contextual menus; those actions become filters for the dataset.
- Reflect the current line by drawing annotated arrows/badges on the table (e.g., “UTG raises 3x”, “BTN folds”).
- Keep response metrics/hand breakdowns context-aware, updating as soon as the focal bettor and responders are defined.

### Core Concepts
- **Table Layout**: canonical positions rendered around a circular (or oval) table. Each seat card displays position, stack state, and current action summary.
- **Seat Model**: `seatId`, `position`, `isActive`, `streetActions` map keyed by `preflop/flop/turn/river`. Each action entry tracks `actionType`, `sizing`, `notes`.
- **Action Palette**: context menu per seat with quick actions (fold, call, raise x%, raise x pot, all-in). Secondary drawer for detailed sizing and qualifiers (texture, stack depth).
- **Focal Flow**: user identifies a focal bettor (the seat whose action is under review). The backend line descriptor is derived from the sequence of seat actions up to that focal moment.
- **Street Progression**: timeline chips still exist but become supplementary, reflecting the sequence derived from table inputs instead of being primary editors.

### Interaction Model

**Seat Editing**
- Click a seat → radial/context menu offering street selection (`preflop | flop | turn | river`) and quick actions.
- Actions appear as badges on the seat (e.g., “Raise 3x”, “Call”, “Fold”). Hover shows detailed sizing/qualifiers.
- Drag-and-drop chips to reorder seats (optional for later), or use a lobby to toggle players in/out.

**Updating Filters**
- Whenever an action is set, the composer recomputes the underlying descriptor and immediately refetches response + hand data.
- Visual feedback indicates which filters are active (e.g., pill bar summarizing “UTG raises 3x”, “BB defends”, “Flop texture: Two-Tone”).

**Street Navigation**
- Global street tabs or timeline chips highlight current stage. Selecting a later street automatically ensures prior actions are defined.
- For flop/turn/river filters, a board widget lets users pick texture presets or explicit boards (future iteration).

### State & Validation
- `tableState`: array of seat records plus metadata (button index, stack presets).
- `lineDescriptor` derived via deterministic function reading `tableState` in seat order.
- Validation rules ensure hand progression is coherent (e.g., cannot set flop action if preflop unresolved; bet sizing only valid on bet/raise).
- History (undo/redo) maintained per seat edits.

### Implementation Phases
1. **Table Skeleton**: render static table with seat cards, introduce seat action menu, map edits to internal state (no backend).
2. **Descriptor Integration**: convert seat actions into descriptor payloads, call `/api/lines/query`, display metrics.
3. **Street Layers**: add flop/turn/river controls including texture selector, pot/SPR overviews.
4. **Advanced Qualifiers**: stack-depth tags, hero exclusion, multi-branch scenarios (split lines for alternate responses).

## Open Questions
- How to model multi-actor branches (e.g., split lines for multiple responders) — out of scope for initial release?
- Should turn/river board textures be part of the descriptor now or deferred?
- Cache storage footprint for arbitrary user-defined descriptors; consider expiry policy.
- Preset management: backend curated list vs. user-owned saved queries.

## Next Steps
1. Implement `LineStep` / `LineDescriptor` schema and payload validation utilities.
2. Refactor backend collector to accept descriptor-driven filtering and return enriched metrics.
3. Scaffold frontend state + hooks with mocked payloads while backend evolves.
