# Poker Analytics - Agent Orientation

## Data Sources & Environments
- **Canonical source**: `drivehud.db` located at `T:\Dev\ignition\drivehud\drivehud.db` (Windows). On Linux/macOS mount via WSL path `/mnt/t/Dev/ignition/drivehud/drivehud.db` or sync to `drivehud/drivehud.db` in the repo (git-ignored).
- Expect future sources with similar schemas. Plan to wrap each datasource behind an adapter implementing a shared interface (`HandHistoryDataSource.load_events(...)`). Keep raw ingestion + normalization logic isolated from visualization code.
- Cache heavy extracts in `analysis/cache/` during transition; new system should use `var/cache/` (git-ignored) with versioned cache keys.

## Environment Setup
- Run `scripts/bootstrap_env.sh` (or `scripts\bootstrap_env.ps1` on Windows) to create `.venv/` and install project + dev dependencies using standard `pip` + `venv`.
- Activate later with `source .venv/bin/activate` (Unix) or `. .venv/Scripts/Activate.ps1` (Windows).
- Dependencies come from `pyproject.toml`; editable installs (`pip install -e .`) keep code + tests in sync.

## Local Development Workflow
### Quick Start Checklist
1. Clone the repository and `cd` into `poker-analytics`.
2. Run `./scripts/bootstrap_env.sh` (Unix) or `./scripts/bootstrap_env.ps1` (Windows PowerShell) to set up `.venv/` with project + dev dependencies.
3. Activate the environment (`source .venv/bin/activate` or `. .venv/Scripts/Activate.ps1`).
4. Start the backend with `uvicorn poker_analytics.app:app --reload` (or `python -m poker_analytics`) — API available at `http://127.0.0.1:8000/api`.
5. In `frontend/`, run `npm install` once (npm may warn about optional audit fixes), then `npm run dev`; open `http://127.0.0.1:5173`.
6. Build the production bundle via `npm run build`, then restart the backend to serve `/` and `/static`.
7. Validate with `python -m unittest discover -s tests -t .`.

### Reference Commands
- Backend dev server: `uvicorn poker_analytics.app:app --reload`.
- Backend via entry point: `python -m poker_analytics`.
- Frontend dev server: `npm run dev` inside `frontend/`.
- Frontend build: `npm run build` inside `frontend/`.
- Test suite: `python -m unittest discover -s tests -t .`.

### Cache Refresh Automation
- The backend clears and rebuilds flop analytics caches automatically on FastAPI startup. Restarting `uvicorn` is enough to pick up new bucket logic and data extracts.
- Running `npm run dev` (or `npm run build`) triggers the same cache sweep via the `predev`/`prebuild` hooks before Vite starts.
- Use `python scripts/refresh_flop_caches.py` manually when needed (e.g., CI, ad-hoc smoke tests). Append `--skip-build` to delete without rebuilding, or `--max-hands N` to rebuild from a limited sample.

## Repository Layout (current & planned)
```
AGENTS.md               # This guide (root locator for notebooks)
analysis/               # Legacy notebooks & scripts from Python project
  analysis/             # Higher-level orchestration helpers
  features/, models/    # Feature engineering and ML experiments
  ...
src/                    # (planned) application code
  poker_analytics/
    __init__.py
    config.py             # Environment + data path resolution
    data/
      textures.py       # Canonical flop texture groupings
      bet_sizing.py     # Canonical bet-size buckets
      drivehud.py       # DriveHUD-specific data adapter
    db/
      sqlite.py         # Read-only SQLite helper mirroring legacy behaviour
    ...
frontend/               # (planned) React application root (Vite + Chakra)
```
- Maintain `analysis/` as read-only reference until logic is ported. Do not delete or edit legacy notebooks unless backfilling context.
- Treat `analysis/` as archival content only; do not place new caches, generated data, or scripts in that directory.
- Dependency management: standard `python -m venv` + `pip install -e .[dev]` (see `scripts/bootstrap_env.*`).

## Legacy Resources to Reuse
- `analysis/flop_board_texture_explorer.ipynb`: source of board texture predicates and exploratory summaries. The `TEXTURE_SPECS` list is our ground truth for initial texture groups.
- `analysis/flop_cbet_explorer.ipynb`: defines hero flop bet-size buckets (`RAW_BUCKET_BOUNDS`) used across analyses.
- `analysis/cbet_utils.py`, `analysis/flop_texture_tables.py`, `analysis/sqlite_utils.py`: contain classification helpers worth porting into reusable services.
- Other notebooks cover preflop, turn, river, ML experiments. Catalogue relevant logic when those areas enter scope.

## Canonical Definitions (v0)

### Data Access Abstractions
- `poker_analytics.data.drivehud.DriveHudDataSource` centralizes read-only access to `drivehud.db` (reuses the same locking strategy as the legacy notebooks).
- `poker_analytics.db.sqlite.connect_readonly` provides the shared URI + temp-copy logic for safe access over network mounts.
### Flop Board Texture Groups
| Key | Description |
| --- | --- |
| `rainbow` | Three different suits on the flop.
| `monotone` | All three cards share the same suit.
| `two_tone` | Exactly two suits present.
| `paired` | Any rank appears at least twice.
| `connected` | Rank spread <= 4 (wheel-aware).
| `ace_high` | Ace present and highest card.
| `low` | All ranks <= Ten.
| `high` | At least two Broadway ranks (J-Q-K-A).

Implementations live in `src/poker_analytics/data/textures.py` (see below) and provide reusable predicates for analytics and filtering widgets.

### Flop Bet Size Buckets (ratio of bet to pot)
| Label | Range (inclusive of lower bound, exclusive of upper) |
| --- | --- |
| `0-25%` | `[0.00, 0.25)` |
| `25-40%` | `[0.25, 0.40)` |
| `40-60%` | `[0.40, 0.60)` |
| `60-80%` | `[0.60, 0.80)` |
| `80-100%` | `[0.80, 1.00)` |
| `100%+` | `[1.00, inf)` |

Stored in `src/poker_analytics/data/bet_sizing.py`. Always normalize bet sizes by pot size before bucketizing.

### Flop Bet Taxonomy
- **Continuation bet (c-bet)**: The player who executed the last preflop raise fires the flop regardless of position or caller count.
- **Donk bet**: A non-aggressor seated out of position leads into the preflop aggressor before that aggressor acts on the flop.
- **Stab / other flop bets**: Any flop bet that is neither a c-bet nor a donk. Typical cases include betting after the preflop aggressor checks or betting in limped pots with no aggressor.
- **Stab vs missed c-bet**: Specific subset of “other” bets where the preflop aggressor checks and another player bets afterward.
- **Limped pots**: With no preflop raise there is no aggressor; every flop bet is a generic lead/bet (treated as part of the “other” bucket).
- **Multiway & 3/4-bet pots**: The preflop aggressor remains the only potential c-bettor. Earlier-position players who lead before the aggressor act are donking; bets made after the aggressor checks revert to the “other” classification.

### Preflop Shove Analysis
- Backend exposes `/api/preflop/shove/ranges` for shove distributions split by category (13x13 grid).
- `/api/preflop/shove/equity` returns simulated equity/EV grids (aligned with the legacy heatmaps).
- Data leverages parsed DriveHUD XML with caches in `var/cache/preflop_shove_events_<stake>.json` and `preflop_equity.json` (legacy cache copied on first run).
- Flop aggregations cache per-stake payloads (`flop_response_matrix_<stake>.json`, `flop_hand_matrix_<stake>.json`) under `var/cache/`.

### Stake Filtering
- Set `POKER_ANALYTICS_ALLOWED_BIG_BLINDS` (comma/semicolon delimited) to limit analytics to specific cash-game stakes; use `*` to disable filtering.
- Cache files include the stake token (`bb_0p1`, etc.) to keep per-stake extracts isolated under `var/cache/`.

## Development Workflow & Best Practices
- Treat data contracts as APIs. Any change to schemas, bucket definitions, or poker terminology must update documentation and tests.
- Keep visualization components dumb: they receive already aggregated data + metadata describing filters, color tokens, and legends.
- Prefer property-based tests for bucketizing and classification helpers to ensure coverage across edge cases (e.g., missing suits, wheel straights).
- Maintain `migrations/` (future) for schema transformations; version caches accordingly.
- Enforce formatting + linting: `ruff` + `black` for Python (in that order), `prettier` + `eslint` for TypeScript.
- For notebooks that must persist, run `jupyter nbconvert --ClearOutputPreprocessor.enabled=True` before commits.

## Style Guide Snapshot
- Typography: Inter for body, Roboto Mono for numeric tables. Base font-size 16px, scale up for dashboards.
- Layout: default max content width 1500px for analytical explorers; use responsive grids or flex layouts so paired visuals stay aligned without wrapping. Keep landing page cards consistent height and include miniature KPIs.
- Colors: use theme tokens above; encode meaning consistently (e.g., hero actions = blue, villain responses = orange/red).
- Interaction: always expose tooltips detailing raw counts alongside percentages. Provide download buttons for CSV behind each visualization.

### Visualization Layout Standards
- Preflop shove explorers (and similar 13×13 hand-grid views) must render the shoving range, calling equity, and calling EV heatmaps on the same row; when EV is unavailable the calling equity grid stays centered between the surrounding columns.
- Hand-grid tables use fixed 30×30 px cells with clipped overflow, dynamic black/white text for contrast, and the following gradients: white→blue for frequency, red→white→green anchored at 50% for equity, red→white→green anchored at 0 for EV.
- Label each grid with inline headings (`Shoving Range (%)`, `Calling Equity (%)`, `Calling EV (bb)`); place supporting summaries (Hand Groups, Aggregate Buckets, etc.) directly beneath the shoving range column and cap combined width (~440px) to avoid wrapping.
- Always describe the caller perspective in the section introduction when equity/EV tables reflect calling outcomes; reuse the phrasing from the Preflop Shove Explorer for future pages.
- Performance dashboards with tabular metrics (e.g., Performance by Opponent Count) should present aggregate stats via `Stat` cards followed by a borderless table for positional splits. Use the shared metric order (`Hand Count`, `Net (bb)`, `Net ($)`, `bb/100`, `VPIP %`, `PFR %`, `3-Bet %`, `Average Pot (bb)`) and `Intl.NumberFormat` helpers for consistent number formatting.
- Performance overview pages aggregate the same metrics across every opponent count; compute combined percentages using the underlying raw counts and reuse the shared formatting helpers so values match the detailed breakdown screens.
- Include a cumulative net line chart on overview pages. Feed the chart cumulative big-blind results over hand index, allow quick filters (e.g., clicking a position row), and provide a reset affordance alongside the section heading.
- Position ordering is canonical: `SB`, `BB`, `UTG`, `UTG+1`, `UTG+2`, `LJ`, `HJ`, `CO`, `BTN`. For shorter tables the list collapses from the middle (e.g., four-handed → `SB`, `BB`, `CO`, `BTN`). Heads-up hands assign the button seat to `SB` and keep the big blind bucket separate.
- Heads-up rows in breakdown tables therefore read `SB` (button) and `BB`; when one opponent is present, the hero’s button stats live under the `SB` label.

## Testing & Validation Checklist
- [x] Unit tests for bucket assignment (`bet_sizing`), texture predicates (`textures`).
- [x] Integration tests for data adapters once APIs exist (mock SQLite rows, assert aggregated results).
- [ ] Snapshot tests for key charts (e.g., using Storybook + chromatic or percy once front-end starts).
- [ ] CI pipeline: GitHub Actions matrix (Linux, Python 3.11) with lint + test stages.

## Open Questions / Follow-ups
1. Confirm whether we ingest directly from `drivehud.db` or through an ETL into an analytical store (DuckDB/Parquet) for performance.
2. Align on hosting/deployment preferences (self-hosted vs managed platform).
3. Decide on caching strategy for large extracts (Redis? On-disk?).
4. Determine additional canonical groupings (turn textures, river runouts, stack-depth buckets).

## Agent Interaction & Session Notes

### Communication Preferences
- Favour concise updates when describing changes; avoid unnecessary detail.
- Always call out any follow-up actions required from the user (e.g., scripts to run, services to restart) using explicit commands.

### Data Source & Cache Decisions
- Global Data Source is selected via the NavBar dropdown (upper-right). Key values:
  - `drivehud` → Ignition / DriveHUD (canonical, hero + population).
  - `pokerstars_nl10` → PokerStars NL10 population dataset (no hero).
- Backend normalises `source=drivehud` to the default `None` internally so legacy DriveHUD loaders continue to hit the database and root caches (e.g., `var/cache/flop_response_matrix_<stake>.json`).
- Non-DriveHUD sources (e.g., `pokerstars_nl10`) never touch the DB; they rely entirely on precomputed per-source caches under `var/cache/<source>/`.
- Performance pages (`/performance/overview`, `/performance/opponent-count`) are always DriveHUD-only and ignore the global Data Source selector.

### Preflop Shove Equity (Equity / EV Grids)
- Canonical equity tables live at:
  - DriveHUD: `var/cache/preflop_equity.json` (legacy seed from `analysis/cache/preflop_equity.json` on first run).
  - Per source: `var/cache/<source>/preflop_equity.json`.
- Equity/EV API:
  - Ignition: `/api/preflop/shove/equity` → `get_equity_payload(source=None)`.
  - PokerStars NL10: `/api/preflop/shove/equity?source=pokerstars_nl10` → `get_equity_payload(source='pokerstars_nl10')`.
- Equity simulation script (Monte Carlo) lives in `scripts/preflop_equity.py` and supports both DB-backed and JSON-backed runs:
  - From a DriveHUD SQLite DB (default):
    - `python scripts/preflop_equity.py --database drivehud/drivehud.db --trials 10000 --workers 16 --output var/cache/preflop_equity.json`
  - From precomputed shove events JSON (used for PokerStars NL10):
    - `python scripts/preflop_equity.py --events-json var/cache/pokerstars_nl10/preflop_shove_events_bb_0p1.json --trials 10000 --workers 16 --output var/cache/pokerstars_nl10/preflop_equity.json`
- When adding a new source, follow the PokerStars pattern: materialise `preflop_shove_events_<stake>.json` under `var/cache/<source>/`, then run `scripts/preflop_equity.py` with `--events-json` to generate `preflop_equity.json` for that source.

### Flop / Turn / River Response Matrices & Hand Breakdowns
- Default (Ignition / DriveHUD) caches live at `var/cache/`:
  - Flop: `flop_response_matrix_<stake>.json`, `flop_pot_contribution_<stake>.json`, `flop_hand_matrix_<stake>.json`, `flop_responder_hand_matrix_<stake>.json`.
  - Turn: `turn_response_matrix_<stake>.json`, `turn_pot_contribution_<stake>.json`, `turn_hand_matrix_<stake>.json`, `turn_responder_hand_matrix_<stake>.json`.
  - River: `river_response_matrix_<stake>.json`, `river_pot_contribution_<stake>.json`, `river_hand_matrix_<stake>.json`, `river_responder_hand_matrix_<stake>.json`.
- Per-source caches follow the same naming but live under `var/cache/<source>/`.
- DriveHUD (`source=None`):
  - Response matrices and hand breakdowns are built from the DriveHUD DB if the root caches are missing.
  - Bettor’s and Responder’s Hand Breakdown tables on the Flop/Turn/River Response Matrix pages are populated from the DriveHUD hero/responder hand matrix caches.
  - For DriveHUD, hero actions are excluded from population aggregates:
    - Hero as bettor is excluded at event-build time; bet events are always non-hero bettors.
    - Hero as responder to others’ bets is filtered out in `_collect_flop_responses`, `_collect_turn_responses`, and `_collect_river_responses`, so hero responses do not contribute to Bet Responses or Responder Hand Breakdown tables.
- Non-DriveHUD sources (e.g., PokerStars):
  - Response matrices and responder hand breakdowns use per-source JSON caches under `var/cache/<source>/`.
  - Flop Bettor’s Hand Breakdown for PokerStars NL10:
    - Built from raw PokerStars HH text files under `data/NL10` via `scripts/build_pokerstars_flop_hand_matrix.py`.
    - Uses only hands where the bettor’s hole cards are revealed at showdown; hands with no shown cards are excluded from the bettor hand-mix tables.
    - Command to (re)build:
      - `PYTHONPATH=src python scripts/build_pokerstars_flop_hand_matrix.py`
    - Output cache: `var/cache/pokerstars_nl10/flop_hand_matrix_<stake_token>.json` (e.g., `flop_hand_matrix_bb_0p1.json`).
  - Turn Bettor’s Hand Breakdown for PokerStars NL10:
    - Built from the same `data/NL10` PokerStars HH files via `scripts/build_pokerstars_turn_hand_matrix.py`.
    - Parser focuses on the **first turn bet per hand** where the bettor’s hole cards are shown at showdown.
    - Bet-size buckets are derived from bet-to-pot ratio at the start of the turn; SPR buckets are currently treated as “any” for PokerStars.
    - Turn betting line classification is not inferred for PokerStars; events participate in the “Any betting line” aggregates but will not match specific line filters.
    - Command to (re)build:
      - `PYTHONPATH=src python scripts/build_pokerstars_turn_hand_matrix.py`
    - Output cache: `var/cache/pokerstars_nl10/turn_hand_matrix_<stake_token>.json` (e.g., `turn_hand_matrix_bb_0p1.json`).
  - River Bettor’s Hand Breakdown for PokerStars NL10:
    - Built from the same `data/NL10` PokerStars HH files via `scripts/build_pokerstars_river_hand_matrix.py`.
    - Parser focuses on the **first river bet per hand** where the bettor’s hole cards are shown at showdown.
    - Bet-size buckets are derived from bet-to-pot ratio at the start of the river; SPR buckets are currently treated as “any” for PokerStars.
    - River betting line classification is not inferred for PokerStars; events participate in “Any betting line” aggregates only.
    - Command to (re)build:
      - `PYTHONPATH=src python scripts/build_pokerstars_river_hand_matrix.py`
    - Output cache: `var/cache/pokerstars_nl10/river_hand_matrix_<stake_token>.json` (e.g., `river_hand_matrix_bb_0p1.json`).

### Scripts & Commands to Refresh Analytics
- Refresh flop/turn/river response matrices and related caches from DriveHUD:
  - `python scripts/refresh_flop_caches.py` (optional: `--max-hands N` to limit for smoke tests).
- Build preflop response curves (DriveHUD):
  - `python scripts/build_response_curves.py --max-hands N` (writes `var/cache/preflop_response_curves.json`).
- Build flop response matrix only (DriveHUD):
  - `python scripts/build_flop_response_matrix.py --max-hands N`.
- Build PokerStars NL10 Bettor’s Hand Breakdown caches from raw HH text:
  - Flop: `PYTHONPATH=src python scripts/build_pokerstars_flop_hand_matrix.py`
  - Turn: `PYTHONPATH=src python scripts/build_pokerstars_turn_hand_matrix.py`
  - River: `PYTHONPATH=src python scripts/build_pokerstars_river_hand_matrix.py`
- Refresh DriveHUD responder hand-matrix caches (flop/turn/river):
  - `PYTHONPATH=src python scripts/refresh_responder_caches.py`

Keep this document updated as architecture solidifies. Treat it as the root source of truth for future agent reactivation.
