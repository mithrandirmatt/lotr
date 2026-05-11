"""Deterministic core engine primitives (stubbed).

This module provides a minimal deterministic `apply_action` interface used
by the host/referee loop. It should be extended to implement full rules.
"""
from typing import Tuple, Any, Dict
from .schema import GameState


def apply_action(state: GameState, action: Dict[str, Any], rng_state: Any = None) -> Tuple[GameState, Dict[str, Any]]:
    """Apply `action` to `state` and return (new_state, events).

    This is a placeholder implementation that advances the turn counter
    and echoes the action. Replace with full deterministic rule execution.
    """
    new_state = GameState(turn=state.turn + 1, players=list(state.players), meta=dict(state.meta))
    events = {"ok": True, "action_id": action.get("action_id")}
    return new_state, events
