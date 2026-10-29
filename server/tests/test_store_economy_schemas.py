try:
    from server.server.models.schemas import (
        StoreProduct,
        StorePurchaseRequest,
        StorePurchaseResponse,
        GrantedCardSummary,
        StoreSellBackRequest,
        StoreSellBackResponse,
    )
except ModuleNotFoundError:
    from server.models.schemas import (
        StoreProduct,
        StorePurchaseRequest,
        StorePurchaseResponse,
        GrantedCardSummary,
        StoreSellBackRequest,
        StoreSellBackResponse,
    )


def test_store_purchase_request_set_number_optional_and_defaults_none():
    payload = StorePurchaseRequest(product=StoreProduct.BOOSTER_BOX)
    assert payload.set_number is None
    assert payload.quantity == 1


def test_store_purchase_request_accepts_set_number_for_packs():
    payload = StorePurchaseRequest(product=StoreProduct.PACK, set_number=1)
    assert payload.set_number == 1


def test_store_purchase_response_cards_granted_defaults_empty():
    response = StorePurchaseResponse(
        user_id="u-1",
        product=StoreProduct.STARTER_DECK,
        quantity=1,
        unit_price_tolkiens=5,
        total_price_tolkiens=5,
        balance_before=10,
        balance_after=5,
    )
    assert response.cards_granted == []
    assert response.transaction_id is None


def test_store_purchase_response_can_carry_granted_cards():
    granted = [GrantedCardSummary(card_id="c-1", name="Test Card", rarity="rare", is_foil=True)]
    response = StorePurchaseResponse(
        user_id="u-1",
        product=StoreProduct.PACK,
        quantity=1,
        unit_price_tolkiens=1,
        total_price_tolkiens=1,
        balance_before=10,
        balance_after=9,
        cards_granted=granted,
        transaction_id="tx-1",
    )
    assert len(response.cards_granted) == 1
    assert response.cards_granted[0].is_foil is True
    assert response.transaction_id == "tx-1"


def test_store_sell_back_request_defaults():
    payload = StoreSellBackRequest(card_id="c-1")
    assert payload.quantity == 1
    assert payload.is_foil is False


def test_store_sell_back_response_roundtrip():
    response = StoreSellBackResponse(
        user_id="u-1",
        card_id="c-1",
        quantity=2,
        is_foil=False,
        unit_value_tolkiens=1,
        total_value_tolkiens=2,
        balance_before=5,
        balance_after=7,
        transaction_id="tx-2",
    )
    assert response.total_value_tolkiens == 2
