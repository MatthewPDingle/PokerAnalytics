from __future__ import annotations

from typing import Dict, Iterable, List

import pandas as pd

from analysis.flop_board_texture_utils import derive_texture

PRIMARY_DISPLAY_ORDER: List[str] = [
    "Air",
    "Draw",
    "Weak Pair",
    "Top Pair",
    "Overpair",
    "Two Pair",
    "Trips/Set",
    "Monster",
]

TEXTURE_ORDER: List[str] = [
    "Paired Two-tone",
    "Paired Rainbow",
    "Unpaired Monotone",
    "Unpaired Two-tone",
    "Unpaired Rainbow",
]

COMBINED_TEXTURE_ORDER: List[str] = [
    "Paired",
    "Unpaired",
    "Connected",
    "Disconnected",
    "Ace-High",
    "Low Board",
    "High Board",
]

CELL_SIZE = 30
FONT_SIZE = "10px"
HEADER_FONT_SIZE = "11px"

TOTAL_COUNT_COL = "Total (count)"
TOTAL_PCT_COL = "Total (pct)"
TOTAL_COUNT_ROW = "Total (count)"
TOTAL_PCT_ROW = "Total (pct)"

RANK_VALUES: Dict[str, int] = {
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "T": 10,
    "J": 11,
    "Q": 12,
    "K": 13,
    "A": 14,
}
BROADWAY_RANKS = {"T", "J", "Q", "K", "A"}
SUIT_CHARS = {"C", "D", "H", "S"}

PRIMARY_MAP: Dict[str, str] = {
    "Air": "Air",
    "Underpair": "Weak Pair",
    "Bottom Pair": "Weak Pair",
    "Middle Pair": "Weak Pair",
    "Top Pair": "Top Pair",
    "Overpair": "Overpair",
    "Two Pair": "Two Pair",
    "Trips/Set": "Trips/Set",
    "Straight": "Monster",
    "Flush": "Monster",
    "Full House": "Monster",
    "Quads": "Monster",
}


def _parse_simple(cards_text: str | None) -> List[tuple[str, str, int]]:
    if not cards_text:
        return []
    tokens = [tok.strip() for tok in cards_text.split() if tok.strip()]
    if len(tokens) != 3:
        return []
    parsed: List[tuple[str, str, int]] = []
    for token in tokens:
        if len(token) != 2:
            return []
        first, second = token[0].upper(), token[1].upper()
        if first in SUIT_CHARS and second in RANK_VALUES:
            suit = first.lower()
            rank = second
        elif second in SUIT_CHARS and first in RANK_VALUES:
            suit = second.lower()
            rank = first
        else:
            return []
        parsed.append((rank, suit, RANK_VALUES[rank]))
    return parsed


def _is_connected(values: Iterable[int]) -> bool:
    values = list(values)
    if len(values) != 3:
        return False
    sorted_vals = sorted(values)
    if sorted_vals[-1] - sorted_vals[0] <= 4:
        return True
    if 14 in sorted_vals:
        alt = sorted(1 if v == 14 else v for v in values)
        return alt[-1] - alt[0] <= 4
    return False


def classify_combined_texture(cards_text: str | None) -> List[str]:
    parsed = _parse_simple(cards_text)
    if not parsed:
        return ["Unpaired"]

    ranks = [rank for rank, _, _ in parsed]
    values = [value for _, _, value in parsed]

    categories: List[str] = ["Paired" if len(set(ranks)) < 3 else "Unpaired"]

    if _is_connected(values):
        categories.append("Connected")
    else:
        categories.append("Disconnected")
    if max(values) == 14:
        categories.append("Ace-High")
    if all(value <= 10 for value in values):
        categories.append("Low Board")
    if sum(1 for rank in ranks if rank in BROADWAY_RANKS) >= 2:
        categories.append("High Board")

    return categories


def _event_group(row: pd.Series) -> str:
    if row.get("has_flush_draw") or row.get("has_oesd_dg"):
        return "Draw"
    primary = row.get("primary")
    return PRIMARY_MAP.get(primary, "Air")


def prepare_texture_dataframe(events) -> pd.DataFrame:
    if isinstance(events, pd.DataFrame):
        df = events.copy()
    else:
        if not events:
            return pd.DataFrame(columns=["primary_group", "flop_cards"])
        df = pd.DataFrame(events)

    if "flop_cards" not in df.columns:
        raise KeyError("Expected 'flop_cards' column in event dataframe")

    df = df[df["flop_cards"].notnull()].copy()
    df["primary_group"] = df.apply(_event_group, axis=1)
    df = df[df["primary_group"].isin(PRIMARY_DISPLAY_ORDER)]
    return df


def _add_totals(base: pd.DataFrame, texture_labels: List[str]) -> pd.DataFrame:
    row_totals = base.sum(axis=1)
    grand_total = float(row_totals.sum())

    base[TOTAL_COUNT_COL] = row_totals
    base[TOTAL_PCT_COL] = (row_totals / grand_total * 100.0) if grand_total else 0.0

    col_totals = base.loc[PRIMARY_DISPLAY_ORDER, texture_labels].sum(axis=0)

    total_rows = pd.DataFrame(0.0, index=[TOTAL_COUNT_ROW, TOTAL_PCT_ROW], columns=base.columns)
    total_rows.loc[TOTAL_COUNT_ROW, texture_labels] = col_totals
    total_rows.loc[TOTAL_COUNT_ROW, TOTAL_COUNT_COL] = grand_total
    total_rows.loc[TOTAL_COUNT_ROW, TOTAL_PCT_COL] = 100.0 if grand_total else 0.0

    if grand_total:
        texture_pct = (col_totals / grand_total) * 100.0
    else:
        texture_pct = 0.0
    total_rows.loc[TOTAL_PCT_ROW, texture_labels] = texture_pct
    total_rows.loc[TOTAL_PCT_ROW, TOTAL_COUNT_COL] = grand_total
    total_rows.loc[TOTAL_PCT_ROW, TOTAL_PCT_COL] = 100.0 if grand_total else 0.0

    return pd.concat([base, total_rows])


def _compute_table(
    df: pd.DataFrame,
    texture_labels: List[str],
    classifier,
    expand_multiple: bool = False,
) -> pd.DataFrame:
    base = pd.DataFrame(0.0, index=PRIMARY_DISPLAY_ORDER, columns=texture_labels)

    if not df.empty:
        if expand_multiple:
            for _, row in df.iterrows():
                for bucket in classifier(row["flop_cards"]):
                    if bucket in texture_labels:
                        base.loc[row["primary_group"], bucket] += 1
        else:
            for _, row in df.iterrows():
                bucket = classifier(row["flop_cards"])
                if bucket in texture_labels:
                    base.loc[row["primary_group"], bucket] += 1

    return _add_totals(base, texture_labels)


def compute_percent_table(count_table: pd.DataFrame) -> pd.DataFrame:
    table = count_table.copy()

    body_rows = [row for row in table.index if row not in {TOTAL_COUNT_ROW, TOTAL_PCT_ROW}]
    body_cols = [col for col in table.columns if col not in {TOTAL_COUNT_COL, TOTAL_PCT_COL}]

    col_totals = count_table.loc[TOTAL_COUNT_ROW, body_cols]
    for col in body_cols:
        denom = col_totals[col]
        if denom > 0:
            table.loc[body_rows, col] = (count_table.loc[body_rows, col] / denom) * 100.0
        else:
            table.loc[body_rows, col] = 0.0

    grand_total = count_table.loc[TOTAL_COUNT_ROW, TOTAL_COUNT_COL]
    if grand_total > 0:
        table.loc[body_rows, TOTAL_COUNT_COL] = (
            count_table.loc[body_rows, TOTAL_COUNT_COL] / grand_total
        ) * 100.0
    else:
        table.loc[body_rows, TOTAL_COUNT_COL] = 0.0

    table.loc[TOTAL_COUNT_ROW, body_cols] = 100.0
    table.loc[TOTAL_COUNT_ROW, TOTAL_COUNT_COL] = 100.0

    # Preserve existing percentage column/row.
    table.loc[TOTAL_PCT_ROW, :] = count_table.loc[TOTAL_PCT_ROW, :]

    return table


def compute_primary_texture_table(df: pd.DataFrame) -> pd.DataFrame:
    return _compute_table(df, TEXTURE_ORDER, derive_texture, expand_multiple=False)


def compute_combined_texture_table(df: pd.DataFrame) -> pd.DataFrame:
    return _compute_table(
        df,
        COMBINED_TEXTURE_ORDER,
        classify_combined_texture,
        expand_multiple=True,
    )

def style_heatmap_table(table: pd.DataFrame, title: str):
    if table.empty:
        return table.style.set_caption(title)

    body_rows = [row for row in table.index if row not in {TOTAL_COUNT_ROW, TOTAL_PCT_ROW}]
    count_rows = body_rows + [TOTAL_COUNT_ROW]
    percent_rows = [TOTAL_PCT_ROW]
    body_cols = [col for col in table.columns if col not in {TOTAL_COUNT_COL, TOTAL_PCT_COL}]
    count_cols = body_cols + [TOTAL_COUNT_COL]
    percent_cols = [TOTAL_PCT_COL]

    styler = table.style
    styler = styler.format('{:,.0f}', subset=pd.IndexSlice[count_rows, count_cols], na_rep='')
    styler = styler.format('{:.1f}%', subset=pd.IndexSlice[count_rows, percent_cols], na_rep='')
    styler = styler.format('{:.1f}%', subset=pd.IndexSlice[percent_rows, body_cols + percent_cols], na_rep='')
    styler = styler.format('{:,.0f}', subset=pd.IndexSlice[percent_rows, [TOTAL_COUNT_COL]], na_rep='')

    body_subset = table.loc[body_rows, body_cols]
    body_max = body_subset.to_numpy().max() if not body_subset.empty else 1
    styler = styler.background_gradient(
        cmap='Blues',
        subset=pd.IndexSlice[body_rows, body_cols],
        vmin=0,
        vmax=body_max if body_max > 0 else 1,
    )

    if body_cols:
        row_totals = table.loc[[TOTAL_COUNT_ROW], body_cols]
        row_max = row_totals.to_numpy().max() if not row_totals.empty else 1
        styler = styler.background_gradient(
            cmap='Blues',
            subset=pd.IndexSlice[[TOTAL_COUNT_ROW], body_cols],
            vmin=0,
            vmax=row_max if row_max > 0 else 1,
        )

    if body_rows:
        col_totals = table.loc[body_rows, [TOTAL_COUNT_COL]]
        col_max = col_totals.to_numpy().max() if not col_totals.empty else 1
        styler = styler.background_gradient(
            cmap='Blues',
            subset=pd.IndexSlice[body_rows, [TOTAL_COUNT_COL]],
            vmin=0,
            vmax=col_max if col_max > 0 else 1,
        )

    grand_totals = table.loc[[TOTAL_COUNT_ROW, TOTAL_PCT_ROW], [TOTAL_COUNT_COL]]
    gt_max = grand_totals.to_numpy().max() if not grand_totals.empty else 1
    styler = styler.background_gradient(
        cmap='Blues',
        subset=pd.IndexSlice[[TOTAL_COUNT_ROW, TOTAL_PCT_ROW], [TOTAL_COUNT_COL]],
        vmin=0,
        vmax=gt_max if gt_max > 0 else 1,
    )

    table_styles = [
        {
            'selector': 'th.col_heading',
            'props': [
                ('writing-mode', 'vertical-rl'),
                ('transform', 'rotate(180deg)'),
                ('padding', '2px 0px'),
                ('min-width', f'{CELL_SIZE}px'),
                ('max-width', f'{CELL_SIZE}px'),
                ('text-align', 'center'),
                ('font-size', HEADER_FONT_SIZE),
                ('line-height', f'{CELL_SIZE}px'),
                ('white-space', 'nowrap'),
            ],
        },
        {
            'selector': 'th.row_heading',
            'props': [
                ('text-align', 'left'),
                ('padding', '4px 6px'),
                ('white-space', 'nowrap'),
                ('font-size', HEADER_FONT_SIZE),
            ],
        },
        {
            'selector': 'td',
            'props': [
                ('width', f'{CELL_SIZE}px'),
                ('min-width', f'{CELL_SIZE}px'),
                ('max-width', f'{CELL_SIZE}px'),
                ('height', f'{CELL_SIZE}px'),
                ('min-height', f'{CELL_SIZE}px'),
                ('max-height', f'{CELL_SIZE}px'),
                ('line-height', f'{CELL_SIZE}px'),
                ('text-align', 'center'),
                ('padding', '0'),
                ('font-size', FONT_SIZE),
                ('box-sizing', 'border-box'),
                ('overflow', 'hidden'),
            ],
        },
        {
            'selector': 'table',
            'props': [
                ('border-collapse', 'collapse'),
                ('margin', '0px'),
            ],
        },
        {
            'selector': 'tbody tr:nth-last-child(2) td, tbody tr:nth-last-child(2) th',
            'props': [('border-top', '2px solid #1f2937')],
        },
        {
            'selector': 'tbody tr:last-child td, tbody tr:last-child th',
            'props': [('border-top', '2px solid #1f2937')],
        },
        {
            'selector': 'tbody td:nth-last-child(2), thead th:nth-last-child(2)',
            'props': [('border-left', '2px solid #1f2937')],
        },
        {
            'selector': 'tbody td:last-child, thead th:last-child',
            'props': [('border-left', '2px solid #1f2937')],
        },
    ]

    styler = styler.set_table_styles(table_styles)
    styler = styler.set_caption(title)
    return styler


def style_heatmap_percentage_table(table: pd.DataFrame, title: str):
    if table.empty:
        return table.style.set_caption(title)

    body_rows = [row for row in table.index if row not in {TOTAL_COUNT_ROW, TOTAL_PCT_ROW}]
    count_rows = body_rows + [TOTAL_COUNT_ROW]
    percent_rows = [TOTAL_PCT_ROW]
    body_cols = [col for col in table.columns if col not in {TOTAL_COUNT_COL, TOTAL_PCT_COL}]
    count_cols = body_cols + [TOTAL_COUNT_COL]
    percent_cols = [TOTAL_PCT_COL]

    styler = table.style
    styler = styler.format('{:.1f}%', subset=pd.IndexSlice[count_rows, count_cols], na_rep='')
    styler = styler.format('{:.1f}%', subset=pd.IndexSlice[count_rows, percent_cols], na_rep='')
    styler = styler.format('{:.1f}%', subset=pd.IndexSlice[percent_rows, body_cols + percent_cols], na_rep='')
    styler = styler.format('{:.1f}%', subset=pd.IndexSlice[percent_rows, [TOTAL_COUNT_COL]], na_rep='')

    body_subset = table.loc[body_rows, body_cols]
    body_max = body_subset.to_numpy().max() if not body_subset.empty else 1
    styler = styler.background_gradient(
        cmap='Blues',
        subset=pd.IndexSlice[body_rows, body_cols],
        vmin=0,
        vmax=body_max if body_max > 0 else 1,
    )

    if body_cols:
        row_totals = table.loc[[TOTAL_COUNT_ROW], body_cols]
        row_max = row_totals.to_numpy().max() if not row_totals.empty else 1
        styler = styler.background_gradient(
            cmap='Blues',
            subset=pd.IndexSlice[[TOTAL_COUNT_ROW], body_cols],
            vmin=0,
            vmax=row_max if row_max > 0 else 1,
        )

    if body_rows:
        col_totals = table.loc[body_rows, [TOTAL_COUNT_COL]]
        col_max = col_totals.to_numpy().max() if not col_totals.empty else 1
        styler = styler.background_gradient(
            cmap='Blues',
            subset=pd.IndexSlice[body_rows, [TOTAL_COUNT_COL]],
            vmin=0,
            vmax=col_max if col_max > 0 else 1,
        )

    grand_totals = table.loc[[TOTAL_COUNT_ROW, TOTAL_PCT_ROW], [TOTAL_COUNT_COL]]
    gt_max = grand_totals.to_numpy().max() if not grand_totals.empty else 1
    styler = styler.background_gradient(
        cmap='Blues',
        subset=pd.IndexSlice[[TOTAL_COUNT_ROW, TOTAL_PCT_ROW], [TOTAL_COUNT_COL]],
        vmin=0,
        vmax=gt_max if gt_max > 0 else 1,
    )

    table_styles = [
        {
            'selector': 'th.col_heading',
            'props': [
                ('writing-mode', 'vertical-rl'),
                ('transform', 'rotate(180deg)'),
                ('padding', '2px 0px'),
                ('min-width', f'{CELL_SIZE}px'),
                ('max-width', f'{CELL_SIZE}px'),
                ('text-align', 'center'),
                ('font-size', HEADER_FONT_SIZE),
                ('line-height', f'{CELL_SIZE}px'),
                ('white-space', 'nowrap'),
            ],
        },
        {
            'selector': 'th.row_heading',
            'props': [
                ('text-align', 'left'),
                ('padding', '4px 6px'),
                ('white-space', 'nowrap'),
                ('font-size', HEADER_FONT_SIZE),
            ],
        },
        {
            'selector': 'td',
            'props': [
                ('width', f'{CELL_SIZE}px'),
                ('min-width', f'{CELL_SIZE}px'),
                ('max-width', f'{CELL_SIZE}px'),
                ('height', f'{CELL_SIZE}px'),
                ('min-height', f'{CELL_SIZE}px'),
                ('max-height', f'{CELL_SIZE}px'),
                ('line-height', f'{CELL_SIZE}px'),
                ('text-align', 'center'),
                ('padding', '0'),
                ('font-size', FONT_SIZE),
                ('box-sizing', 'border-box'),
                ('overflow', 'hidden'),
            ],
        },
        {
            'selector': 'table',
            'props': [
                ('border-collapse', 'collapse'),
                ('margin', '0px'),
            ],
        },
        {
            'selector': 'tbody tr:nth-last-child(2) td, tbody tr:nth-last-child(2) th',
            'props': [('border-top', '2px solid #1f2937')],
        },
        {
            'selector': 'tbody tr:last-child td, tbody tr:last-child th',
            'props': [('border-top', '2px solid #1f2937')],
        },
        {
            'selector': 'tbody td:nth-last-child(2), thead th:nth-last-child(2)',
            'props': [('border-left', '2px solid #1f2937')],
        },
        {
            'selector': 'tbody td:last-child, thead th:last-child',
            'props': [('border-left', '2px solid #1f2937')],
        },
    ]

    styler = styler.set_table_styles(table_styles)
    styler = styler.set_caption(title)
    return styler
