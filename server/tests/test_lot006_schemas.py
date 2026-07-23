from pydantic import ValidationError

try:
    from server.server.models.schemas import (
        AdminTolkienAdjustRequest,
        AdminUserDeleteRequest,
        StoreProduct,
        StorePurchaseRequest,
    )
except ModuleNotFoundError:
    from server.models.schemas import (
        AdminTolkienAdjustRequest,
        AdminUserDeleteRequest,
        StoreProduct,
        StorePurchaseRequest,
    )


def test_admin_tolkien_adjust_rejects_zero():
    try:
        AdminTolkienAdjustRequest(amount=0)
    except ValidationError:
        return
    assert False, "Expected ValidationError when amount=0"


def test_admin_tolkien_adjust_accepts_positive_and_negative():
    add_payload = AdminTolkienAdjustRequest(amount=25)
    remove_payload = AdminTolkienAdjustRequest(amount=-7)
    assert add_payload.amount == 25
    assert remove_payload.amount == -7


def test_store_purchase_defaults_and_enum():
    payload = StorePurchaseRequest(product=StoreProduct.BOOSTER_BOX)
    assert payload.product == StoreProduct.BOOSTER_BOX
    assert payload.quantity == 1


def test_admin_user_delete_request_requires_all_confirm_fields():
    payload = AdminUserDeleteRequest(
        confirm_user_id="u-123",
        confirm_username="frodo",
        confirm_email="frodo@shire.me",
    )
    assert payload.confirm_user_id == "u-123"
    assert payload.confirm_username == "frodo"
    assert str(payload.confirm_email) == "frodo@shire.me"
