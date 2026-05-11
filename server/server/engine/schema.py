from dataclasses import dataclass, field
from typing import List, Optional, Dict

@dataclass
class Card:
    id: str
    name: str
    set_num: Optional[int] = None
    collector_info: Optional[str] = None
    unique: Optional[bool] = None


@dataclass
class GameState:
    turn: int = 0
    players: List[str] = field(default_factory=list)
    # placeholder for richer state (zones, decks, hands)
    meta: Dict = field(default_factory=dict)
