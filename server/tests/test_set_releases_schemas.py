try:
    from server.server.models.schemas import (
        SetReleaseSummary,
        SetReleaseListResponse,
        ActiveSetsResponse,
    )
    from server.server.routes.api import _is_protected_set, PROTECTED_SET_NUMBERS
except ModuleNotFoundError:
    from server.models.schemas import (
        SetReleaseSummary,
        SetReleaseListResponse,
        ActiveSetsResponse,
    )
    from server.routes.api import _is_protected_set, PROTECTED_SET_NUMBERS


def _make_summary(**overrides):
    payload = {
        "id": "set-1",
        "set_number": 1,
        "set_code": None,
        "name": "Fellowship of the Ring",
        "is_active": True,
        "is_locked_active": True,
        "activated_at": None,
    }
    payload.update(overrides)
    return SetReleaseSummary(**payload)


def test_set_release_summary_defaults():
    summary = _make_summary()
    assert summary.set_number == 1
    assert summary.is_locked_active is True


def test_set_release_list_response_wraps_items():
    items = [_make_summary(), _make_summary(id="set-2", set_number=2, name="Set 2", is_active=False, is_locked_active=False)]
    response = SetReleaseListResponse(items=items)
    assert len(response.items) == 2
    assert response.items[1].set_number == 2


def test_active_sets_response_wraps_items():
    response = ActiveSetsResponse(active_sets=[_make_summary()])
    assert response.active_sets[0].name == "Fellowship of the Ring"


def test_fellowship_is_protected():
    assert 1 in PROTECTED_SET_NUMBERS
    assert _is_protected_set(1) is True


def test_other_sets_are_not_protected():
    assert _is_protected_set(2) is False
    assert _is_protected_set(19) is False
