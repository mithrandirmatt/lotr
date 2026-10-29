import random
from dataclasses import dataclass

try:
    from server.server.engine import booster
except ModuleNotFoundError:
    from server.engine import booster


@dataclass
class FakeCard:
    """Minimal stand-in for a Card row (generate_booster_pack only reads
    .id, .name, and .image_url)."""
    id: str
    name: str
    image_url: str | None = None


def _pool(rarity: str, count: int):
    return [FakeCard(id=f"{rarity}-{i}", name=f"{rarity.title()} Card {i}") for i in range(count)]


def _full_cards_by_rarity():
    return {
        "common": _pool("common", 20),
        "uncommon": _pool("uncommon", 10),
        "rare": _pool("rare", 5),
    }


class _NeverFoilRandom(random.Random):
    def random(self):
        return 0.999


class _AlwaysFoilRandom(random.Random):
    def random(self):
        return 0.0


def test_generate_booster_pack_has_correct_composition():
    pack = booster.generate_booster_pack(_full_cards_by_rarity(), rng=random.Random(42))
    assert len(pack) == booster.PACK_SIZE == 11
    counts = {"common": 0, "uncommon": 0, "rare": 0}
    for entry in pack:
        counts[entry["rarity"]] += 1
    assert counts == booster.RARITY_COMPOSITION


def test_generate_booster_pack_raises_when_rarity_bucket_empty():
    cards_by_rarity = _full_cards_by_rarity()
    cards_by_rarity["rare"] = []
    try:
        booster.generate_booster_pack(cards_by_rarity, rng=random.Random(1))
    except ValueError:
        return
    assert False, "Expected ValueError when a required rarity bucket is empty"


def test_generate_booster_pack_no_foil_by_default_with_low_luck_rng():
    pack = booster.generate_booster_pack(_full_cards_by_rarity(), rng=_NeverFoilRandom())
    assert all(not entry["is_foil"] for entry in pack)


def test_generate_booster_pack_at_most_one_foil_and_prefers_rare():
    pack = booster.generate_booster_pack(_full_cards_by_rarity(), rng=_AlwaysFoilRandom())
    foils = [entry for entry in pack if entry["is_foil"]]
    assert len(foils) == 1
    # Rare is checked first in FOIL_ODDS priority order, so with a
    # guaranteed-hit rng the rare card should be the one marked foil.
    assert foils[0]["rarity"] == "rare"


def test_compute_sell_back_value_tolkiens_baseline_pack_price():
    assert booster.compute_sell_back_value_tolkiens("common", 1) == 1
    assert booster.compute_sell_back_value_tolkiens("uncommon", 1) == 2
    assert booster.compute_sell_back_value_tolkiens("rare", 1) == 5


def test_compute_sell_back_value_tolkiens_unknown_rarity_is_zero():
    assert booster.compute_sell_back_value_tolkiens("mythic", 1) == 0


def test_compute_sell_back_value_never_negative():
    assert booster.compute_sell_back_value_tolkiens("common", 0) == 0
