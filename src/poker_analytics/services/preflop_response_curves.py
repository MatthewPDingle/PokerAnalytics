"""Prototype loaders for preflop sizing response curves."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List

from poker_analytics.config import build_data_paths


@dataclass(frozen=True)
class ResponseCurvePoint:
    """Fold/call/raise mix and EV for a specific bet-size bucket."""

    bucket_key: str
    bucket_label: str
    representative_ratio: float
    fold_pct: float
    call_pct: float
    raise_pct: float
    ev_bb: float
    expected_final_pot_bb: float
    expected_players_remaining: float


@dataclass(frozen=True)
class ResponseCurveScenario:
    """Population response curve for a specific preflop configuration."""

    id: str
    hero_position: str
    stack_bucket_key: str
    stack_depth: str
    villain_profile: str
    vpip_ahead: int
    players_behind: int
    pot_bucket_key: str
    pot_bucket: str
    pot_size_bb: float
    effective_stack_bb: float
    sample_size: int
    points: List[ResponseCurvePoint]
    situation_key: str = ""
    situation_label: str = ""


def _point(
    bucket_key: str,
    bucket_label: str,
    representative_ratio: float,
    fold_pct: float,
    call_pct: float,
    raise_pct: float,
    ev_bb: float,
    expected_final_pot_bb: float,
    expected_players_remaining: float,
) -> ResponseCurvePoint:
    return ResponseCurvePoint(
        bucket_key=bucket_key,
        bucket_label=bucket_label,
        representative_ratio=representative_ratio,
        fold_pct=fold_pct,
        call_pct=call_pct,
        raise_pct=raise_pct,
        ev_bb=ev_bb,
        expected_final_pot_bb=expected_final_pot_bb,
        expected_players_remaining=expected_players_remaining,
    )


_STACK_BUCKET_LABEL_TO_KEY = {
    "0-30 bb": "bb_0_30",
    "30-60 bb": "bb_30_60",
    "60-100 bb": "bb_60_100",
    "100+ bb": "bb_100_plus",
}

_STACK_BUCKET_KEY_TO_LABEL = {value: key for key, value in _STACK_BUCKET_LABEL_TO_KEY.items()}

_STACK_BUCKET_KEY_TO_APPROX = {
    "bb_0_30": 20.0,
    "bb_30_60": 45.0,
    "bb_60_100": 80.0,
    "bb_100_plus": 140.0,
}

_POT_BUCKET_LABEL_TO_KEY = {
    "Blinds Only (~1.5 bb)": "pot_blinds",
    "2-4 bb": "pot_small",
    "4-7 bb": "pot_medium",
    "7-12 bb": "pot_large",
    "12+ bb": "pot_huge",
}

_POT_BUCKET_KEY_TO_LABEL = {value: key for key, value in _POT_BUCKET_LABEL_TO_KEY.items()}


_SAMPLE_SCENARIOS: List[ResponseCurveScenario] = [
    ResponseCurveScenario(
        id="btn_bb_30_60_vpip0_pot_blinds_players2",
        hero_position="BTN",
        stack_bucket_key="bb_30_60",
        stack_depth="30-60 bb",
        villain_profile="Population",
        vpip_ahead=0,
        players_behind=2,
        pot_bucket_key="pot_blinds",
        pot_bucket="Blinds Only (~1.5 bb)",
        pot_size_bb=1.5,
        effective_stack_bb=45.0,
        sample_size=1843,
        points=[
            _point("pct_0_25", "0-25%", 0.125, 15, 68, 17, 6.2, 6.0, 2.0),
            _point("pct_25_40", "25-40%", 0.325, 19, 63, 18, 7.0, 6.5, 2.0),
            _point("pct_40_60", "40-60%", 0.5, 26, 57, 17, 7.6, 7.0, 2.0),
            _point("pct_60_80", "60-80%", 0.7, 34, 51, 15, 7.8, 7.5, 2.0),
            _point("pct_80_100", "80-100%", 0.9, 40, 46, 14, 7.4, 8.0, 2.0),
            _point("pct_100_125", "100-125%", 1.125, 51, 39, 10, 6.9, 8.5, 2.0),
            _point("pct_125_200", "125-200%", 1.6, 56, 35, 9, 6.3, 9.0, 2.0),
            _point("pct_200_300", "200-300%", 2.5, 61, 31, 8, 5.7, 9.5, 1.5),
            _point("pct_300_plus", "300%+ / All-In", 3.5, 67, 26, 7, 5.0, 10.0, 1.0),
        ],
        situation_key="folded_to_hero",
        situation_label="Folded to hero (blinds only)",
    ),
    ResponseCurveScenario(
        id="btn_bb_30_60_vpip1_pot_medium_players2",
        hero_position="BTN",
        stack_bucket_key="bb_30_60",
        stack_depth="30-60 bb",
        villain_profile="Population",
        vpip_ahead=1,
        players_behind=2,
        pot_bucket_key="pot_medium",
        pot_bucket="4-7 bb",
        pot_size_bb=4.0,
        effective_stack_bb=45.0,
        sample_size=1320,
        points=[
            _point("pct_25_40", "25-40%", 0.325, 18, 49, 33, 5.8, 11.0, 2.5),
            _point("pct_40_60", "40-60%", 0.5, 24, 47, 29, 6.6, 11.5, 2.4),
            _point("pct_60_80", "60-80%", 0.7, 31, 43, 26, 6.9, 12.0, 2.3),
            _point("pct_80_100", "80-100%", 0.9, 39, 38, 23, 6.5, 12.5, 2.2),
            _point("pct_100_125", "100-125%", 1.125, 48, 33, 19, 6.1, 13.0, 2.0),
            _point("pct_125_200", "125-200%", 1.6, 53, 30, 17, 5.7, 13.5, 1.9),
            _point("pct_200_300", "200-300%", 2.5, 58, 27, 15, 5.2, 14.0, 1.7),
            _point("pct_300_plus", "300%+ / All-In", 3.5, 64, 23, 13, 4.7, 15.0, 1.5),
        ],
        situation_key="facing_single_raise",
        situation_label="Facing CO open to 2.5 bb (no callers)",
    ),
    ResponseCurveScenario(
        id="hj_bb_60_100_vpip2_pot_small_players4",
        hero_position="HJ",
        stack_bucket_key="bb_60_100",
        stack_depth="60-100 bb",
        villain_profile="Population",
        vpip_ahead=2,
        players_behind=4,
        pot_bucket_key="pot_small",
        pot_bucket="2-4 bb",
        pot_size_bb=3.5,
        effective_stack_bb=80.0,
        sample_size=1675,
        points=[
            _point("pct_0_25", "0-25%", 0.125, 12, 71, 17, 4.8, 6.5, 3.5),
            _point("pct_25_40", "25-40%", 0.325, 18, 65, 17, 5.4, 7.5, 3.4),
            _point("pct_40_60", "40-60%", 0.5, 26, 58, 16, 5.7, 8.5, 3.3),
            _point("pct_60_80", "60-80%", 0.7, 35, 51, 14, 5.6, 9.5, 3.0),
            _point("pct_80_100", "80-100%", 0.9, 43, 45, 12, 5.2, 10.5, 2.8),
            _point("pct_100_125", "100-125%", 1.125, 52, 38, 10, 4.7, 11.5, 2.6),
            _point("pct_125_200", "125-200%", 1.6, 58, 33, 9, 4.2, 12.5, 2.4),
            _point("pct_200_300", "200-300%", 2.5, 63, 29, 8, 3.8, 13.5, 2.2),
            _point("pct_300_plus", "300%+ / All-In", 3.5, 68, 24, 8, 3.3, 15.0, 2.0),
        ],
        situation_key="facing_limpers",
        situation_label="Two limpers ahead",
    ),
]


def _scenario_from_dict(data: dict) -> ResponseCurveScenario:
    points: List[ResponseCurvePoint] = []
    for point in data.get("points", []):
        points.append(
            ResponseCurvePoint(
                bucket_key=point.get("bucket_key", ""),
                bucket_label=point.get("bucket_label", point.get("bucket_key", "")),
                representative_ratio=point.get("representative_ratio", 0.0),
                fold_pct=point.get("fold_pct", 0.0),
                call_pct=point.get("call_pct", 0.0),
                raise_pct=point.get("raise_pct", 0.0),
                ev_bb=point.get("ev_bb", 0.0),
                expected_final_pot_bb=point.get("expected_final_pot_bb", point.get("final_pot_bb", 0.0)),
                expected_players_remaining=point.get(
                    "expected_players_remaining", point.get("players_remaining", 0.0)
                ),
            )
        )

    stack_bucket_key = str(data.get("stack_bucket_key", "") or "")
    stack_depth = data.get("stack_depth") or _STACK_BUCKET_KEY_TO_LABEL.get(stack_bucket_key, "")
    if not stack_bucket_key and stack_depth:
        stack_bucket_key = _STACK_BUCKET_LABEL_TO_KEY.get(stack_depth, "")

    pot_bucket_label = data.get("pot_bucket") or data.get("pot_bucket_label", "")
    pot_bucket_key = str(data.get("pot_bucket_key", "") or "")
    if not pot_bucket_key and pot_bucket_label:
        pot_bucket_key = _POT_BUCKET_LABEL_TO_KEY.get(pot_bucket_label, "")
    if not pot_bucket_label and pot_bucket_key:
        pot_bucket_label = _POT_BUCKET_KEY_TO_LABEL.get(pot_bucket_key, "")

    players_behind_raw = data.get("players_behind")
    if players_behind_raw is None:
        players_behind_raw = data.get("players_to_act", 0)
    try:
        players_behind = int(round(float(players_behind_raw)))
    except (TypeError, ValueError):
        players_behind = 0

    effective_stack_bb_raw = data.get("effective_stack_bb")
    try:
        effective_stack_bb = float(effective_stack_bb_raw)
    except (TypeError, ValueError):
        effective_stack_bb = 0.0
    if effective_stack_bb <= 0 and stack_bucket_key:
        effective_stack_bb = _STACK_BUCKET_KEY_TO_APPROX.get(stack_bucket_key, 0.0)

    pot_size_bb_raw = data.get("pot_size_bb", data.get("pot_before_bb", 0.0))
    try:
        pot_size_bb = float(pot_size_bb_raw)
    except (TypeError, ValueError):
        pot_size_bb = 0.0

    return ResponseCurveScenario(
        id=str(data.get("id", "")),
        hero_position=str(data.get("hero_position", "")),
        stack_bucket_key=stack_bucket_key or "",
        stack_depth=stack_depth or "",
        villain_profile=str(data.get("villain_profile", "Population")),
        vpip_ahead=int(data.get("vpip_ahead", 0) or 0),
        players_behind=players_behind,
        pot_bucket_key=pot_bucket_key or "",
        pot_bucket=pot_bucket_label or "",
        pot_size_bb=pot_size_bb,
        effective_stack_bb=effective_stack_bb,
        sample_size=int(data.get("sample_size", 0) or 0),
        points=points,
        situation_key=str(data.get("situation_key", data.get("situation", "")) or ""),
        situation_label=str(data.get("situation_label", data.get("pre_action_summary", "")) or ""),
    )


def _serialise_scenarios(scenarios: Iterable[ResponseCurveScenario]) -> list[dict]:
    return [asdict(scenario) for scenario in scenarios]


def load_response_curve_scenarios(
    cache_path: Path | None = None,
    *,
    force: bool = False,
) -> list[ResponseCurveScenario]:
    """Return response-curve scenarios, preferring cached extracts when available."""

    cache_path = cache_path or (build_data_paths().cache_dir / "preflop_response_curves.json")

    if force:
        cache_path.unlink(missing_ok=True)

    if cache_path.exists():
        with cache_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not raw:
            return list(_SAMPLE_SCENARIOS)
        return [_scenario_from_dict(item) for item in raw]

    return list(_SAMPLE_SCENARIOS)


def get_response_curve_payload(cache_path: Path | None = None) -> list[dict]:
    """Return serialised response-curve scenarios ready for JSON output."""

    scenarios = load_response_curve_scenarios(cache_path=cache_path)
    return _serialise_scenarios(scenarios)


__all__ = [
    "ResponseCurvePoint",
    "ResponseCurveScenario",
    "get_response_curve_payload",
    "load_response_curve_scenarios",
]
