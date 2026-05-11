"""Simple validators for decks and actions (placeholders)."""
from typing import List, Tuple, Dict


def validate_deck(deck: List[str], card_db: Dict | None = None) -> Tuple[bool, List[str]]:
    errors = []
    if not isinstance(deck, list):
        errors.append("deck must be a list of card ids")
        return False, errors
    # Additional validation rules go here
    return True, errors
