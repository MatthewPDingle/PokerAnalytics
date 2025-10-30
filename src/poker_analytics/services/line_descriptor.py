"""Schema and helpers for generalized betting line descriptors.

These data structures describe the sequence of actions that lead to a focal
moment we want to analyse. They are intentionally generic so we can reuse the
same representation for multiple endpoints (response mix, hand breakdowns,
context snapshots, etc.).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Optional, Sequence, Tuple

VALID_STREETS: Tuple[str, ...] = ("preflop", "flop", "turn", "river")
VALID_ACTOR_ROLES: Tuple[str, ...] = (
    "hero",
    "villain",
    "population",
    "preflop_aggressor",
    "bettor",
    "responder",
    "any",
)
VALID_ACTIONS: Tuple[str, ...] = (
    "check",
    "bet",
    "raise",
    "call",
    "fold",
    "open",
    "limp",
    "3bet",
    "4bet",
    "donk",
    "lead",
    "cbet",
    "probe",
)
VALID_QUALIFIERS: Tuple[str, ...] = (
    "multiway",
    "heads_up",
    "in_position",
    "out_of_position",
    "hero_excluded",
    "texture_low",
    "texture_connected",
    "texture_paired",
)


@dataclass(frozen=True)
class LineSizing:
    """Constraints describing the bet sizing for a line step."""

    bucket_keys: Tuple[str, ...] = field(default_factory=tuple)
    ratio_min: Optional[float] = None
    ratio_max: Optional[float] = None
    absolute_bb: Optional[float] = None
    label: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "bucket_keys": list(self.bucket_keys),
            "ratio_min": self.ratio_min,
            "ratio_max": self.ratio_max,
            "absolute_bb": self.absolute_bb,
            "label": self.label,
        }


@dataclass(frozen=True)
class LineStep:
    """Single action descriptor within a line."""

    street: str
    actor: str
    action: str
    sizing: Optional[LineSizing] = None
    qualifiers: Tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "street": self.street,
            "actor": self.actor,
            "action": self.action,
            "sizing": self.sizing.to_dict() if self.sizing else None,
            "qualifiers": list(self.qualifiers),
        }


@dataclass(frozen=True)
class LineDescriptor:
    """Complete description of the hand line up to the focal moment."""

    steps: Tuple[LineStep, ...]
    focus: str = "response"  # response, hand_mix, context (extensible)
    annotation: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "steps": [step.to_dict() for step in self.steps],
            "focus": self.focus,
            "annotation": self.annotation,
        }


def parse_line_descriptor(payload: Mapping[str, object]) -> LineDescriptor:
    """Parse a JSON-like payload into a `LineDescriptor`."""

    if "steps" not in payload:
        raise ValueError("line descriptor payload must include 'steps'")
    steps_raw = payload.get("steps")
    steps = tuple(_parse_line_step(item) for item in _iter_mappings("steps", steps_raw))

    focus_raw = str(payload.get("focus") or "response").strip().lower()
    if not focus_raw:
        focus_raw = "response"

    annotation_raw = payload.get("annotation")
    annotation = str(annotation_raw) if annotation_raw is not None else None

    return LineDescriptor(steps=steps, focus=focus_raw, annotation=annotation)


def descriptor_fingerprint(descriptor: LineDescriptor) -> str:
    """Return a stable hash for cache keys."""

    serialised = json.dumps(descriptor.to_dict(), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha1(serialised.encode("utf-8")).hexdigest()
    return digest


def _parse_line_step(item: Mapping[str, object]) -> LineStep:
    street = _coerce_choice(item.get("street"), VALID_STREETS, "street").lower()
    actor = _coerce_choice(item.get("actor"), VALID_ACTOR_ROLES, "actor").lower()
    action = _coerce_choice(item.get("action"), VALID_ACTIONS, "action").lower()
    qualifiers = tuple(
        _coerce_choice(value, VALID_QUALIFIERS, "qualifier").lower()
        for value in _iter_scalars("qualifiers", item.get("qualifiers"))
    )
    sizing_payload = item.get("sizing")
    sizing = _parse_line_sizing(sizing_payload) if sizing_payload else None
    return LineStep(street=street, actor=actor, action=action, sizing=sizing, qualifiers=qualifiers)


def _parse_line_sizing(payload: Mapping[str, object]) -> LineSizing:
    bucket_values = tuple(_iter_scalars("bucket_keys", payload.get("bucket_keys")))
    ratio_min = _coerce_optional_float(payload.get("ratio_min"))
    ratio_max = _coerce_optional_float(payload.get("ratio_max"))
    absolute_bb = _coerce_optional_float(payload.get("absolute_bb"))
    label_raw = payload.get("label")
    label = str(label_raw) if label_raw is not None else None

    if ratio_min is not None and ratio_max is not None and ratio_min > ratio_max:
        raise ValueError("sizing.ratio_min cannot exceed sizing.ratio_max")

    return LineSizing(bucket_keys=bucket_values, ratio_min=ratio_min, ratio_max=ratio_max, absolute_bb=absolute_bb, label=label)


def _coerce_choice(value: object, allowed: Sequence[str], field_name: str) -> str:
    if value is None:
        raise ValueError(f"{field_name} cannot be null")
    text = str(value).strip().lower()
    if not text:
        raise ValueError(f"{field_name} cannot be empty")
    if text not in allowed:
        allowed_display = ", ".join(allowed)
        raise ValueError(f"invalid {field_name} '{text}'. Allowed values: {allowed_display}")
    return text


def _iter_mappings(field: str, values: object) -> Iterable[Mapping[str, object]]:
    if not isinstance(values, Sequence):
        raise ValueError(f"{field} must be a sequence")
    for idx, item in enumerate(values):
        if not isinstance(item, Mapping):
            raise ValueError(f"{field}[{idx}] must be a mapping")
        yield item


def _iter_scalars(field: str, values: object) -> Iterable[str]:
    if values is None:
        return ()
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise ValueError(f"{field} must be a sequence of scalars")
    for idx, value in enumerate(values):
        if value is None:
            raise ValueError(f"{field}[{idx}] cannot be null")
        text = str(value).strip()
        if not text:
            raise ValueError(f"{field}[{idx}] cannot be empty")
        yield text


def _coerce_optional_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid float value: {value!r}") from exc
    return converted


__all__ = [
    "LineDescriptor",
    "LineSizing",
    "LineStep",
    "descriptor_fingerprint",
    "parse_line_descriptor",
]
