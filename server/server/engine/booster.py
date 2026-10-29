"""Server-authoritative booster pack card generation and sell-back valuation
(LOT-020 / LOT-025 slice 2).

All pack/starter/prize card outcomes must be generated server-side and be
auditable (LOT-020 acceptance criteria). This module contains the pure,
seedable generation and valuation logic; routes/api.py is responsible for
fetching the eligible Card catalog rows, calling into here, persisting
Ownership deltas, and recording a DistributionTransaction.

Baseline composition/odds below are the LOT-025 "baseline, set-overridable
later" values from assets/reference/agent/game-mechanism-release-and-gifting.md
and issues-tracker.md. They are module-level constants (not yet per-set
config) so a future slice can make them set-overridable without changing the
generation algorithm.
"""

import math
from typing import Dict, List, Optional
import random


# 11 cards per pack: 1 Rare, 3 Uncommon, 7 Common (LOT-025 baseline).
RARITY_COMPOSITION: Dict[str, int] = {"rare": 1, "uncommon": 3, "common": 7}
PACK_SIZE = sum(RARITY_COMPOSITION.values())

# Foil insertion probability per opened pack, checked in this priority order
# (rare, then uncommon, then common); the first hit wins and no further rolls
# are made, enforcing "at most one foil insertion event per pack" while still
# approximating the independently-specified per-rarity odds. Priority order
# is an implementation choice -- the design doc gives independent odds per
# rarity but does not specify precedence when more than one would hit.
FOIL_ODDS: Dict[str, float] = {"rare": 1 / 26, "uncommon": 1 / 18, "common": 1 / 13}

SELL_BACK_RATE = 0.5

# Native Tolkien pack pricing (1 Tolkien/pack) is too coarse to produce
# meaningful non-zero per-card sell-back values on its own (splitting 1
# Tolkien across 11 cards of 3 rarity tiers yields sub-1 fractions for every
# rarity). This scale factor is a tunable economy knob -- not specified
# numerically in the LOT-025 design doc -- chosen so that, at the current
# 1-Tolkien pack price, sell-back values come out to whole, differentiated
# amounts: common=1, uncommon=2, rare=5 Tolkien. Revisit once real pack
# pricing/playtesting data is available.
SELL_BACK_VALUE_SCALE_TOLKIENS = 30


def _round_half_up(value: float) -> int:
    """Deterministic rounding: halves always round up (never banker's
    rounding), per LOT-025's "deterministic rounding behavior documented and
    applied consistently" requirement."""
    return int(math.floor(value + 0.5))


def card_purchase_equivalent_value_tolkiens(rarity: str, pack_price_tolkiens: int = 1) -> float:
    """Normalized rarity-weighted expected value of one card of `rarity`,
    derived by splitting the pack price evenly across rarity tiers, then
    evenly across the cards of that tier within a pack, then applying the
    sell-back scale knob. Returns 0 for rarities not present in the pack
    composition (nothing to derive a value from)."""
    count_in_pack = RARITY_COMPOSITION.get(rarity)
    if not count_in_pack:
        return 0.0
    tiers = len(RARITY_COMPOSITION)
    per_tier_value = pack_price_tolkiens / tiers
    per_card_value = per_tier_value / count_in_pack
    return per_card_value * SELL_BACK_VALUE_SCALE_TOLKIENS


def compute_sell_back_value_tolkiens(rarity: str, pack_price_tolkiens: int = 1) -> int:
    """Whole-Tolkien sell-back value for one copy of a card of `rarity`:
    50% of its normalized purchase-equivalent value, rounded half-up, floored
    at 0."""
    raw_value = card_purchase_equivalent_value_tolkiens(rarity, pack_price_tolkiens) * SELL_BACK_RATE
    return max(0, _round_half_up(raw_value))


def generate_booster_pack(cards_by_rarity: Dict[str, List], rng: Optional[random.Random] = None) -> List[Dict]:
    """Generate one booster pack's server-authoritative card outcomes.

    `cards_by_rarity` must map each rarity key in RARITY_COMPOSITION to the
    list of catalog Card rows eligible for the target set (already filtered
    by set_number + is_active by the caller). Each returned entry is
    {card_id, name, rarity, is_foil}.

    Raises ValueError if any required rarity bucket has zero eligible cards
    (i.e. the catalog isn't populated for that set/rarity yet) -- callers
    should surface this as a 400 rather than silently returning a short pack.
    """
    rng = rng or random.Random()
    pack: List[Dict] = []

    for rarity, count in RARITY_COMPOSITION.items():
        pool = cards_by_rarity.get(rarity) or []
        if not pool:
            raise ValueError(f"No '{rarity}' cards available in this set's catalog")
        for _ in range(count):
            card = rng.choice(pool)
            pack.append({
                "card_id": card.id, "name": card.name, "rarity": rarity,
                "is_foil": False, "image_url": card.image_url,
            })

    for rarity in ("rare", "uncommon", "common"):
        if rng.random() < FOIL_ODDS[rarity]:
            candidate_indexes = [i for i, entry in enumerate(pack) if entry["rarity"] == rarity]
            if candidate_indexes:
                pack[rng.choice(candidate_indexes)]["is_foil"] = True
            break

    return pack
