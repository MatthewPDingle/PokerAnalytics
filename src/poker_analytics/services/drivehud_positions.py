"""DriveHUD positional helpers based on seat offsets."""

from __future__ import annotations

DRIVEHUD_OFFSET_TO_POSITION = {
    0: "BTN",
    1: "SB",
    2: "BB",
    3: "UTG",
    4: "MP",
    5: "CO",
}


def offset_position(offset: int) -> str:
    return DRIVEHUD_OFFSET_TO_POSITION.get(offset, "UNKNOWN")


__all__ = ["offset_position"]
