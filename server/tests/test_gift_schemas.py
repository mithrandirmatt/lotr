"""Schema tests for LOT-019 gift ledger and redemption lifecycle."""
from datetime import datetime, timedelta

try:
    from server.server.models.schemas import (
        GiftStatus, AdminGiftCreateRequest, GiftSummary, GiftListResponse,
        GiftRedeemResponse, StoreProduct, GrantedCardSummary,
    )
except ModuleNotFoundError:
    from server.models.schemas import (
        GiftStatus, AdminGiftCreateRequest, GiftSummary, GiftListResponse,
        GiftRedeemResponse, StoreProduct, GrantedCardSummary,
    )


def test_admin_gift_create_request_defaults():
    req = AdminGiftCreateRequest(recipient_id="u1", product=StoreProduct.PACK, set_number=1)
    assert req.quantity == 1
    assert req.note is None
    assert req.expires_at is None


def test_gift_summary_round_trip():
    now = datetime.utcnow()
    gift = GiftSummary(
        id="g1", sender_id="admin1", recipient_id="u1", product="pack",
        quantity=1, set_number=1, status=GiftStatus.GRANTED, note="Welcome gift",
        expires_at=None, redeemed_at=None, revoked_at=None, transaction_id=None,
        created_at=now,
    )
    assert gift.status == GiftStatus.GRANTED
    assert gift.status == "granted"


def test_gift_summary_from_orm_like_object():
    class _FakeGift:
        id = "g2"
        sender_id = None
        recipient_id = "u1"
        product = "booster_box"
        quantity = 2
        set_number = 3
        status = "redeemed"
        note = None
        expires_at = None
        redeemed_at = datetime.utcnow()
        revoked_at = None
        transaction_id = "tx1"
        created_at = datetime.utcnow()

    summary = GiftSummary.model_validate(_FakeGift())
    assert summary.id == "g2"
    assert summary.status == GiftStatus.REDEEMED
    assert summary.transaction_id == "tx1"


def test_gift_list_response():
    listing = GiftListResponse(items=[])
    assert listing.items == []


def test_gift_redeem_response_with_cards():
    now = datetime.utcnow()
    gift = GiftSummary(
        id="g3", sender_id=None, recipient_id="u1", product="pack",
        quantity=1, set_number=1, status=GiftStatus.REDEEMED, note=None,
        expires_at=now + timedelta(days=1), redeemed_at=now, revoked_at=None,
        transaction_id="tx2", created_at=now,
    )
    response = GiftRedeemResponse(
        gift=gift,
        cards_granted=[GrantedCardSummary(card_id="c1", name="Test Card", rarity="common", is_foil=False)],
    )
    assert len(response.cards_granted) == 1
    assert response.gift.status == GiftStatus.REDEEMED
