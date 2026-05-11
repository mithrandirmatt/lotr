"""Deterministic filter resolver.

Resolver should prefer explicit overrides (applied by review) and avoid
fuzzy heuristics in referee mode.
"""
from typing import Dict, List, Any


def resolve_filter(filter_obj: Dict[str, Any], overrides: Dict[str, str] | None = None) -> List[str]:
    """Resolve a parsed filter deterministically.

    If `overrides` maps `action_id` -> `card_id`, return that. Otherwise
    return an empty list (ambiguous).
    """
    action_id = filter_obj.get("action_id") or filter_obj.get("raw_text")
    if overrides and action_id in overrides:
        return [overrides[action_id]]
    return []
