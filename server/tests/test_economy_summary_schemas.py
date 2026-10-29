"""Schema tests for LOT-021 economy/circulation telemetry (admin summary)."""
try:
    from server.server.models.schemas import (
        CirculationEntry, DistributionSourceTotals, SellBackRarityTotals, EconomySummaryResponse,
        WeeklyRewardStats,
    )
except ModuleNotFoundError:
    from server.models.schemas import (
        CirculationEntry, DistributionSourceTotals, SellBackRarityTotals, EconomySummaryResponse,
        WeeklyRewardStats,
    )


def _empty_weekly_reward_stats() -> WeeklyRewardStats:
    return WeeklyRewardStats(
        total_rolls=0, total_wins=0, total_losses=0, win_rate=0.0,
        distinct_users_rolled=0, wins_by_rarity={},
    )


def test_circulation_entry_defaults():
    entry = CirculationEntry(
        card_id="c1", name="Test Card", set_number=1, rarity="rare",
        non_foil_quantity=3, foil_quantity=1,
    )
    assert entry.non_foil_quantity == 3
    assert entry.foil_quantity == 1
    assert entry.set_number == 1


def test_distribution_source_totals():
    totals = DistributionSourceTotals(source="purchase", transaction_count=5, total_tolkien_delta=-25)
    assert totals.source == "purchase"
    assert totals.total_tolkien_delta == -25


def test_sell_back_rarity_totals():
    totals = SellBackRarityTotals(rarity="common", cards_sold=4, total_tolkien_returned=4)
    assert totals.cards_sold == 4


def test_weekly_reward_stats():
    stats = WeeklyRewardStats(
        total_rolls=10, total_wins=1, total_losses=9, win_rate=0.1,
        distinct_users_rolled=8, wins_by_rarity={"common": 1},
    )
    assert stats.distinct_users_rolled == 8
    assert stats.wins_by_rarity == {"common": 1}


def test_economy_summary_response_empty_defaults_are_explicit():
    # No default_factory on these fields (all required lists/dicts) -- the
    # route always supplies them, even if empty, so construction should
    # succeed with explicit empty containers.
    summary = EconomySummaryResponse(
        circulation=[],
        foil_issuance_by_rarity={},
        distribution_by_source=[],
        sell_back_by_rarity=[],
        weekly_reward_stats=_empty_weekly_reward_stats(),
    )
    assert summary.circulation == []
    assert summary.foil_issuance_by_rarity == {}


def test_economy_summary_response_with_data():
    summary = EconomySummaryResponse(
        circulation=[CirculationEntry(
            card_id="c1", name="Test Card", set_number=1, rarity="rare",
            non_foil_quantity=2, foil_quantity=0,
        )],
        foil_issuance_by_rarity={"rare": 1},
        distribution_by_source=[
            DistributionSourceTotals(source="purchase", transaction_count=2, total_tolkien_delta=-2),
        ],
        sell_back_by_rarity=[
            SellBackRarityTotals(rarity="rare", cards_sold=1, total_tolkien_returned=5),
        ],
        weekly_reward_stats=_empty_weekly_reward_stats(),
    )
    assert summary.distribution_by_source[0].transaction_count == 2
    assert summary.sell_back_by_rarity[0].total_tolkien_returned == 5
