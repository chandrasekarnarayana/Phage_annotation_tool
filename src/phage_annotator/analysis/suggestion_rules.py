"""Configurable cross-channel gating rules for assisted suggestions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class ChannelRange:
    background_min: float = 0.0
    background_max: float = 1.0
    peak_min: Optional[float] = None
    peak_max: Optional[float] = None


@dataclass
class SemanticRule:
    name: str
    positive_modalities: Dict[str, float] = field(default_factory=dict)
    negative_modalities: Dict[str, float] = field(default_factory=dict)
    channel_a_peak_gt: Optional[float] = None
    channel_b_peak_gt: Optional[float] = None
    channel_a_lt: Optional[float] = None
    channel_b_lt: Optional[float] = None
    roi_id: Optional[str] = None


@dataclass
class SuggestionRuleConfig:
    channels: Dict[str, ChannelRange] = field(default_factory=dict)
    semantic_rules: Dict[str, SemanticRule] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict) -> "SuggestionRuleConfig":
        channels: Dict[str, ChannelRange] = {}
        semantic_rules: Dict[str, SemanticRule] = {}
        channel_rows = payload.get("channels", {}) if isinstance(payload, dict) else {}
        if isinstance(channel_rows, dict):
            for key, row in channel_rows.items():
                if not isinstance(row, dict):
                    continue
                channels[str(key)] = ChannelRange(
                    background_min=float(row.get("background_min", 0.0)),
                    background_max=float(row.get("background_max", 1.0)),
                    peak_min=(None if row.get("peak_min") is None else float(row.get("peak_min"))),
                    peak_max=(None if row.get("peak_max") is None else float(row.get("peak_max"))),
                )
        rule_rows = payload.get("semantic_rules", []) if isinstance(payload, dict) else []
        if isinstance(rule_rows, list):
            for row in rule_rows:
                if not isinstance(row, dict):
                    continue
                rule = SemanticRule(
                    name=str(row.get("name", "")),
                    positive_modalities={
                        str(k): float(v)
                        for k, v in dict(row.get("positive_modalities", {})).items()
                    },
                    negative_modalities={
                        str(k): float(v)
                        for k, v in dict(row.get("negative_modalities", {})).items()
                    },
                    channel_a_peak_gt=(
                        None
                        if row.get("channel_a_peak_gt") is None
                        else float(row.get("channel_a_peak_gt"))
                    ),
                    channel_b_peak_gt=(
                        None
                        if row.get("channel_b_peak_gt") is None
                        else float(row.get("channel_b_peak_gt"))
                    ),
                    channel_a_lt=(
                        None if row.get("channel_a_lt") is None else float(row.get("channel_a_lt"))
                    ),
                    channel_b_lt=(
                        None if row.get("channel_b_lt") is None else float(row.get("channel_b_lt"))
                    ),
                    roi_id=(None if row.get("roi_id") is None else str(row.get("roi_id"))),
                )
                if rule.name:
                    semantic_rules[rule.name] = rule
        return cls(channels=channels, semantic_rules=semantic_rules)


def load_suggestion_rule_config(path: Path) -> SuggestionRuleConfig:
    text = path.read_text(encoding="utf-8")
    data = None
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "YAML config requested but PyYAML is not installed. Use JSON or install PyYAML."
            ) from exc
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Suggestion rule config must be a JSON/YAML object at the top level.")
    return SuggestionRuleConfig.from_dict(data)
