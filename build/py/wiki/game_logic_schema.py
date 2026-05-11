#!/usr/bin/env python3
"""Schema definitions for structured game logic extracted from card game_text."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Trigger types ────────────────────────────────────────────────────────────

PHASE_TRIGGERS = [
    "fellowship",
    "shadow",
    "maneuver",
    "archery",
    "assignment",
    "skirmish",
    "regroup",
]

TRIGGER_PREFIXES = ["when", "each_time", "while", "response"]

ALL_TRIGGER_TYPES = PHASE_TRIGGERS + TRIGGER_PREFIXES

# Normalized timing tokens
TIMING_VALUES = [
    "when_playing",       # triggered when card is played
    "immediate",          # one-shot phase action
    "continuous",         # While / ongoing effects
    "on_event",           # When / Each Time triggers
    "start_of_turn",      # At the start of each turn/fellowship phase
    "on_move",            # triggered by fellowship movement
    "on_reconciliation",  # regroup / hand reconciliation triggers
]

# ── Cost types ───────────────────────────────────────────────────────────────

COST_TYPES = [
    "add_burden",
    "exert",
    "discard",
    "spot",
    "shuffle",
    "wound",
    "pay_twilight",
    "draw_card",
    "play_card",
    "exhaust",
]

# ── Effect types ─────────────────────────────────────────────────────────────

EFFECT_TYPES = [
    "heal",
    "modify_stat",
    "play_card_from_deck",
    "draw_card",
    "discard_card",
    "wound",
    "kill",
    "return_to_hand",
    "return_to_deck",
    "place_burden",
    "remove_burden",
    "assign_minion",
    "prevent_wound",
    "add_to_archery_total",
    "modify_shadow_number",
    "shuffle_from_discard",
    "place_card",
    "reveal_cards",
    "place_under_deck",
    "skip_phase",
    "modify_twilight",
    "change_ring_bearer",
    "look_at_hand",
    "draw_up_to",
    "place_token",
    "remove_token",
    "modify_resistance",
    "modify_strength",
    "modify_vitality",
    "play_from_hand",
    "play_from_discard",
    "attach_follower",
    "prevent_effect",
    "custom",  # fallback for unstructured effects
]

# ── Stat names ───────────────────────────────────────────────────────────────

STAT_NAMES = ["strength", "vitality", "resistance", "defender"]

# ── Duration tokens ─────────────────────────────────────────────────────────

DURATION_VALUES = [
    "until_regroup",
    "until_end_of_turn",
    "until_next_fellowship",
    "until_next_regroup",
    "permanent",
    "while_in_play",
    "while_at_site",
    "one_time",
]


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class Cost:
    """A cost that must be paid to activate an action."""

    cost_type: str
    value: int | str | None = None
    target: str | None = None
    card_name: str | None = None
    culture: str | None = None
    raw: str | None = None


@dataclass
class Condition:
    """A condition that must be true for an action to activate."""

    condition_type: str
    target: str | None = None
    value: int | str | None = None
    card_name: str | None = None
    culture: str | None = None
    raw: str | None = None


@dataclass
class Effect:
    """An effect produced by an action."""

    effect_type: str
    target: str | None = None
    value: int | str | None = None
    stat: str | None = None
    card_name: str | None = None
    culture: str | None = None
    duration: str | None = None
    raw: str | None = None
    filter: dict | None = None


@dataclass
class Target:
    """Explicit target of an action."""

    target_type: str
    identifier: str | None = None
    count: int | None = None


@dataclass
class Action:
    """A single structured game action extracted from card text."""

    action_id: str
    trigger: str | None = None
    timing: str | None = None
    costs: list[Cost] = field(default_factory=list)
    conditions: list[Condition] = field(default_factory=list)
    effects: list[Effect] = field(default_factory=list)
    targets: list[Target] = field(default_factory=list)
    confidence: float = 0.0
    ambiguous: bool = False
    notes: str = ""
    raw_text: str = ""


@dataclass
class CardGameLogic:
    """Structured game logic for a single card."""

    card_id: str
    name: str
    raw_text: str
    actions: list[Action] = field(default_factory=list)
    source_file: str = "gotdot/assets/data/card_database.json"
    created_by: str = "game_logic_parser:v0.1"
    has_keywords: bool = False
    keyword_actions: list[Action] = field(default_factory=list)


@dataclass
class GameLogicDatabase:
    """Top-level container for the game logic database."""

    cards: dict[str, CardGameLogic] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict."""
        return {
            card_id: {
                "card_id": cl.card_id,
                "name": cl.name,
                "raw_text": cl.raw_text,
                "actions": [
                    {
                        "action_id": a.action_id,
                        "trigger": a.trigger,
                        "timing": a.timing,
                        "costs": [
                            {
                                "type": c.cost_type,
                                "value": c.value,
                                "target": c.target,
                                "card_name": c.card_name,
                                "culture": c.culture,
                                "raw": c.raw,
                            }
                            for c in a.costs
                        ],
                        "conditions": [
                            {
                                "type": cond.condition_type,
                                "target": cond.target,
                                "value": cond.value,
                                "card_name": cond.card_name,
                                "culture": cond.culture,
                                "raw": cond.raw,
                            }
                            for cond in a.conditions
                        ],
                        "effects": [
                            {
                                "type": e.effect_type,
                                "target": e.target,
                                "value": e.value,
                                "stat": e.stat,
                                "card_name": e.card_name,
                                "culture": e.culture,
                                "duration": e.duration,
                                "raw": e.raw,
                                "filter": e.filter,
                            }
                            for e in a.effects
                        ],
                        "targets": [
                            {
                                "type": t.target_type,
                                "identifier": t.identifier,
                                "count": t.count,
                            }
                            for t in a.targets
                        ],
                        "confidence": a.confidence,
                        "ambiguous": a.ambiguous,
                        "notes": a.notes,
                        "raw_text": a.raw_text,
                    }
                    for a in cl.actions
                ],
                "source_file": cl.source_file,
                "created_by": cl.created_by,
                "has_keywords": cl.has_keywords,
                "keyword_actions": [
                    {
                        "action_id": a.action_id,
                        "trigger": a.trigger,
                        "timing": a.timing,
                        "costs": [
                            {
                                "type": c.cost_type,
                                "value": c.value,
                                "target": c.target,
                                "card_name": c.card_name,
                                "culture": c.culture,
                                "raw": c.raw,
                            }
                            for c in a.costs
                        ],
                        "conditions": [
                            {
                                "type": cond.condition_type,
                                "target": cond.target,
                                "value": cond.value,
                                "card_name": cond.card_name,
                                "culture": cond.culture,
                                "raw": cond.raw,
                            }
                            for cond in a.conditions
                        ],
                        "effects": [
                            {
                                "type": e.effect_type,
                                "target": e.target,
                                "value": e.value,
                                "stat": e.stat,
                                "card_name": e.card_name,
                                "culture": e.culture,
                                "duration": e.duration,
                                "raw": e.raw,
                            }
                            for e in a.effects
                        ],
                        "targets": [
                            {
                                "type": t.target_type,
                                "identifier": t.identifier,
                                "count": t.count,
                            }
                            for t in a.targets
                        ],
                        "confidence": a.confidence,
                        "ambiguous": a.ambiguous,
                        "notes": a.notes,
                        "raw_text": a.raw_text,
                    }
                    for a in cl.keyword_actions
                ],
            }
            for card_id, cl in sorted(self.cards.items())
        }
