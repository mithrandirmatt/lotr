"""Unit tests for the LOT-014 deck legality service (server/server/services/deck_legality.py).

Uses lightweight stub objects (duck-typed to the `DeckCard`/`Card` attributes
the service actually reads) instead of a live DB, matching this repo's
convention of pure schema/logic tests without a DB fixture (see
test_lot006_schemas.py).
"""
import pytest

try:
    from server.server.services.deck_legality import (
        evaluate_deck_legality,
        check_copy_limit,
        card_title,
        is_format_legal,
        check_format_legality,
    )
except ModuleNotFoundError:
    from server.services.deck_legality import (
        evaluate_deck_legality,
        check_copy_limit,
        card_title,
        is_format_legal,
        check_format_legality,
    )


class FakeCard:
    def __init__(self, id, name, kind=None, card_type=None, formats=None, on_xlist=None, has_errata=False):
        self.id = id
        self.name = name
        self.attributes = {
            "kind": kind, "card_type": card_type,
            "formats": formats, "on_xlist": on_xlist, "has_errata": has_errata,
        }


class FakeDeckCard:
    def __init__(self, card, quantity):
        self.card = card
        self.quantity = quantity


def _fp(id_, name, qty):
    return FakeDeckCard(FakeCard(id_, name, kind="Free Peoples", card_type="Companion"), qty)


def _shadow(id_, name, qty):
    return FakeDeckCard(FakeCard(id_, name, kind="Shadow", card_type="Minion"), qty)


def _site(id_, name, qty=1):
    return FakeDeckCard(FakeCard(id_, name, card_type="Site"), qty)


def test_card_title_ignores_subtitle():
    assert card_title("Aragorn, King in Exile") == "Aragorn"
    assert card_title("Gandalf") == "Gandalf"


def test_evaluate_deck_legality_empty_deck_has_all_issues():
    result = evaluate_deck_legality([])
    assert result["is_legal"] is False
    assert result["draw_deck_size"] == 0
    assert result["site_count"] == 0
    # 0 Free Peoples == 0 Shadow, so only size and site-count issues apply.
    assert len(result["issues"]) == 2


def test_evaluate_deck_legality_legal_deck():
    # Build an exactly-legal deck: 30 FP + 30 Shadow (equal), + 9 sites.
    deck_cards = (
        [_fp(f"fp{i}", f"Free Peoples Card {i}", 3) for i in range(10)]  # 30
        + [_shadow(f"sh{i}", f"Shadow Card {i}", 3) for i in range(10)]  # 30
        + [_site(f"site{i}", f"Site {i}") for i in range(9)]  # 9
    )
    result = evaluate_deck_legality(deck_cards)
    assert result["draw_deck_size"] == 60
    assert result["free_peoples_count"] == 30
    assert result["shadow_count"] == 30
    assert result["site_count"] == 9
    assert result["issues"] == []
    assert result["is_legal"] is True


def test_evaluate_deck_legality_unequal_split_is_illegal():
    deck_cards = (
        [_fp(f"fp{i}", f"Free Peoples Card {i}", 4) for i in range(10)]  # 40
        + [_shadow(f"sh{i}", f"Shadow Card {i}", 2) for i in range(10)]  # 20
        + [_site(f"site{i}", f"Site {i}") for i in range(9)]
    )
    result = evaluate_deck_legality(deck_cards)
    assert result["draw_deck_size"] == 60
    assert result["is_legal"] is False
    assert any("equal number" in issue for issue in result["issues"])


def test_evaluate_deck_legality_wrong_site_count_is_illegal():
    deck_cards = (
        [_fp(f"fp{i}", f"Free Peoples Card {i}", 3) for i in range(10)]
        + [_shadow(f"sh{i}", f"Shadow Card {i}", 3) for i in range(10)]
        + [_site(f"site{i}", f"Site {i}") for i in range(5)]
    )
    result = evaluate_deck_legality(deck_cards)
    assert result["site_count"] == 5
    assert result["is_legal"] is False
    assert any("Adventure deck" in issue for issue in result["issues"])


def test_check_copy_limit_allows_up_to_four_copies():
    existing = [FakeDeckCard(FakeCard("c1", "Aragorn, King in Exile", "Free Peoples", "Companion"), 3)]
    new_card = FakeCard("c1", "Aragorn, King in Exile", "Free Peoples", "Companion")
    check_copy_limit(existing, new_card, 1)  # 3 + 1 = 4, allowed


def test_check_copy_limit_rejects_fifth_copy():
    existing = [FakeDeckCard(FakeCard("c1", "Aragorn, King in Exile", "Free Peoples", "Companion"), 4)]
    new_card = FakeCard("c1", "Aragorn, King in Exile", "Free Peoples", "Companion")
    with pytest.raises(ValueError, match="maximum is 4"):
        check_copy_limit(existing, new_card, 1)


def test_check_copy_limit_counts_across_subtitles_by_title():
    # Two different printings/subtitles of the same title share the copy limit.
    existing = [
        FakeDeckCard(FakeCard("c1", "Aragorn, King in Exile", "Free Peoples", "Companion"), 2),
        FakeDeckCard(FakeCard("c2", "Aragorn, Heir of Isildur", "Free Peoples", "Companion"), 2),
    ]
    new_card = FakeCard("c3", "Aragorn, Death of Denethor", "Free Peoples", "Companion")
    with pytest.raises(ValueError, match="maximum is 4"):
        check_copy_limit(existing, new_card, 1)


def test_check_copy_limit_sites_allow_only_one_copy():
    existing = [FakeDeckCard(FakeCard("s1", "Sarn Ford", card_type="Site"), 1)]
    new_card = FakeCard("s1", "Sarn Ford", card_type="Site")
    with pytest.raises(ValueError, match="only one copy"):
        check_copy_limit(existing, new_card, 1)


def test_check_copy_limit_the_one_ring_is_unrestricted():
    existing = [FakeDeckCard(FakeCard("r1", "The One Ring, The Binding Ring", card_type="The One Ring"), 1)]
    new_card = FakeCard("r1", "The One Ring, The Binding Ring", card_type="The One Ring")
    check_copy_limit(existing, new_card, 1)  # should not raise


def test_is_format_legal_true_when_format_in_card_formats():
    card = FakeCard("c1", "Galadriel, Lady of Light", formats=["Fellowship Block", "Open"])
    assert is_format_legal(card, "Open") is True
    assert is_format_legal(card, "Fellowship Block") is True


def test_is_format_legal_false_when_format_not_in_card_formats():
    card = FakeCard("c1", "Galadriel, Lady of Light", formats=["Fellowship Block", "Open"])
    assert is_format_legal(card, "King Block") is False


def test_is_format_legal_true_when_card_has_no_formats_data():
    # Missing scraped data (e.g. dev-seed placeholder rows) must never
    # silently ban a card.
    card = FakeCard("c1", "Placeholder Common 1")
    assert is_format_legal(card, "Standard") is True


def test_is_format_legal_false_when_on_xlist_for_format():
    card = FakeCard("c1", "Galadriel, Lady of Light", formats=["Expanded", "Open"], on_xlist=["Expanded"])
    assert is_format_legal(card, "Expanded") is False
    assert is_format_legal(card, "Open") is True


def test_check_format_legality_raises_for_wrong_format():
    card = FakeCard("c1", "Galadriel, Lady of Light", formats=["Fellowship Block"])
    with pytest.raises(ValueError, match="not legal in the 'King Block' format"):
        check_format_legality(card, "King Block")


def test_check_format_legality_raises_for_xlisted_card():
    card = FakeCard("c1", "Galadriel, Lady of Light", formats=["Expanded"], on_xlist=["Expanded"])
    with pytest.raises(ValueError, match="exclusion list"):
        check_format_legality(card, "Expanded")


def test_evaluate_deck_legality_adds_format_issue_for_illegal_card():
    deck_cards = (
        [_fp(f"fp{i}", f"Free Peoples Card {i}", 3) for i in range(10)]
        + [_shadow(f"sh{i}", f"Shadow Card {i}", 3) for i in range(10)]
        + [_site(f"site{i}", f"Site {i}") for i in range(9)]
    )
    # Swap one Free Peoples card for one that's only legal in "King Block".
    deck_cards[0] = FakeDeckCard(
        FakeCard("fp0", "Free Peoples Card 0", kind="Free Peoples", card_type="Companion", formats=["King Block"]),
        3,
    )
    result = evaluate_deck_legality(deck_cards, format_name="Open")
    assert result["is_legal"] is False
    assert any("not legal in the 'Open' format" in issue for issue in result["issues"])


def test_evaluate_deck_legality_errata_notes_are_informational_only():
    deck_cards = (
        [_fp(f"fp{i}", f"Free Peoples Card {i}", 3) for i in range(10)]
        + [_shadow(f"sh{i}", f"Shadow Card {i}", 3) for i in range(10)]
        + [_site(f"site{i}", f"Site {i}") for i in range(9)]
    )
    deck_cards[0] = FakeDeckCard(
        FakeCard("fp0", "Free Peoples Card 0", kind="Free Peoples", card_type="Companion", has_errata=True),
        3,
    )
    result = evaluate_deck_legality(deck_cards)
    assert result["is_legal"] is True  # errata never blocks legality
    assert any("known tournament errata" in note for note in result["errata_notes"])
