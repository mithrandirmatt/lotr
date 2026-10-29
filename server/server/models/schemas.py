"""
Pydantic schemas for API request/response validation.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from enum import Enum

# ============== USER SCHEMAS ==============

class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=8, max_length=100)
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)


class UserUpdate(BaseModel):
    """Schema for updating user information."""
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    current_password: Optional[str] = None
    new_password: Optional[str] = Field(None, min_length=8, max_length=100)


class UserResponse(UserBase):
    """User response schema (includes ID)."""
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_active: bool = True
    is_verified: bool = False
    is_admin: bool = False
    tolkien_balance: int = 0
    is_2fa_enabled: bool = False


class RegisterRequest(BaseModel):
    """Schema for the account-creation form (LOT-007)."""
    email: EmailStr
    unique_name: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)
    confirm_password: str = Field(..., min_length=8, max_length=100)

    @field_validator("unique_name")
    @classmethod
    def unique_name_no_spaces(cls, v: str) -> str:
        if " " in v:
            raise ValueError("Unique name cannot contain spaces")
        return v


# ============== AUTH SCHEMAS ==============

class Token(BaseModel):
    """Authentication token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    """Decoded token payload."""
    sub: str
    type: str
    exp: int
    iat: int


class LoginRequest(BaseModel):
    """Login request schema."""
    email: EmailStr
    password: str = Field(..., min_length=8)


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""
    refresh_token: str


# ============== TWO-FACTOR AUTH SCHEMAS ==============

class CheckExistsResponse(BaseModel):
    """Response for check-email / check-unique-name lookups."""
    exists: bool


class TwoFactorSetupResponse(BaseModel):
    """Response for POST /auth/2fa/setup."""
    secret: str
    otpauth_uri: str
    qr_code_png_base64: str


class TwoFactorEnableRequest(BaseModel):
    """Request for POST /auth/2fa/enable."""
    code: str = Field(..., min_length=6, max_length=6)


class TwoFactorEnableResponse(BaseModel):
    """Response for POST /auth/2fa/enable."""
    recovery_codes: List[str]


class TwoFactorDisableRequest(BaseModel):
    """Request for POST /auth/2fa/disable."""
    password: str
    code: str


class TwoFactorLoginChallenge(BaseModel):
    """Response for POST /auth/login when the account has 2FA enabled."""
    requires_2fa: bool = True
    mfa_token: str


class TwoFactorVerifyLoginRequest(BaseModel):
    """Request for POST /auth/2fa/verify-login."""
    mfa_token: str
    code: str


class TwoFactorRecoverRequest(BaseModel):
    """Request for POST /auth/2fa/recover.

    Used when the user has lost access to their authenticator app (and thus
    cannot produce a live TOTP code): a valid recovery code both completes
    login and clears the account's 2FA state, so the user is routed back
    through the normal /auth/2fa/setup flow to re-enroll with a fresh QR code.
    """
    mfa_token: str
    recovery_code: str


# ============== CARD SCHEMAS ==============

class Rarity(str, Enum):
    """Card rarity enum."""
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"
    MYTHIC = "mythic"


class CardPublishStatus(str, Enum):
    """Card-authoring review gate states (LOT-100 follow-up to LOT-025)."""
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    PUBLISHED = "published"


class CardBase(BaseModel):
    """Base card schema."""
    name: str = Field(..., min_length=1, max_length=200)
    cost: int = Field(..., ge=0)
    rarity: Rarity = Rarity.COMMON
    description: Optional[str] = Field(None, max_length=1000)
    stats: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None
    set_number: Optional[int] = Field(
        None, description="Release set this card belongs to (must reference an existing set)."
    )

    model_config = ConfigDict(from_attributes=True)


class CardCreate(CardBase):
    """Schema for creating a new card.

    `publish_status` is intentionally not settable here -- new cards always
    start as `draft` and must go through the review-gate endpoints
    (`POST /admin/cards/{id}/submit-review`, `.../publish`) to go live.
    """
    pass


class CardUpdate(BaseModel):
    """Schema for updating card information.

    `publish_status` is intentionally not settable here -- use the
    dedicated review-gate endpoints instead, so every status transition is
    an explicit, auditable action.
    """
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    cost: Optional[int] = Field(None, ge=0)
    rarity: Optional[Rarity] = None
    description: Optional[str] = Field(None, max_length=1000)
    stats: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None
    set_number: Optional[int] = None


class CardResponse(CardBase):
    """Card response schema (includes ID)."""
    id: str
    publish_status: CardPublishStatus = CardPublishStatus.PUBLISHED
    review_notes: Optional[str] = None
    created_at: datetime
    # Nullable: the `cards.updated_at` column only gets a value via
    # onupdate (see models.Card) -- rows inserted directly (e.g. the real
    # card catalog import in migrate_import_card_catalog.py) never had it
    # set, so it stays NULL until the row is first modified.
    updated_at: Optional[datetime] = None


class CardListResponse(BaseModel):
    """Card list response with pagination."""
    items: List[CardResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class CardRejectRequest(BaseModel):
    """Optional reviewer feedback when rejecting a card back to draft."""
    review_notes: Optional[str] = Field(None, max_length=500)


# ============== OWNERSHIP SCHEMAS ==============

class OwnershipBase(BaseModel):
    """Base ownership schema."""
    card_id: str
    source: str = Field(..., description="How card was acquired: purchase, match_reward, event, etc.")
    quantity: int = Field(1, ge=1, description="Number of copies owned")
    metadata: Optional[Dict[str, Any]] = None


class OwnershipCreate(OwnershipBase):
    """Schema for creating ownership record."""
    pass


class OwnershipUpdate(BaseModel):
    """Schema for updating ownership."""
    source: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class OwnershipResponse(OwnershipBase):
    """Ownership response schema."""
    id: str
    user_id: str
    acquired_at: datetime
    is_active: bool = True


class UserCardList(BaseModel):
    """User's card collection response."""
    user_id: str
    cards: List[OwnershipResponse]
    total_cards: int
    total_cost: float


# ============== PURCHASE SCHEMAS ==============

class PurchaseItem(BaseModel):
    """Purchase item schema."""
    card_id: str
    quantity: int = Field(..., ge=1)


class PurchaseRequest(BaseModel):
    """Schema for purchase request."""
    items: List[PurchaseItem]
    payment_method: str = Field(..., description="Payment method: credit_card, paypal, etc.")
    coupon_code: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=500)


class PurchaseResponse(BaseModel):
    """Purchase response schema."""
    id: str
    user_id: str
    items: List[Dict[str, Any]]
    subtotal: float
    tax: float
    total: float
    payment_method: str
    coupon_code: Optional[str]
    notes: Optional[str]
    status: str = "completed"
    created_at: datetime


class RefundRequest(BaseModel):
    """Schema for refund request."""
    partial_amount: Optional[float] = Field(None, ge=0)
    reason: str = Field(..., max_length=500)


class RefundResponse(BaseModel):
    """Refund response schema."""
    id: str
    purchase_id: str
    amount: float
    reason: str
    status: str = "pending"
    created_at: datetime


class StoreProduct(str, Enum):
    """Supported store product keys."""
    PACK = "pack"
    STARTER_DECK = "starter_deck"
    BOOSTER_BOX = "booster_box"


class StorePurchaseRequest(BaseModel):
    """Purchase a predefined product using Tolkien balance."""
    product: StoreProduct
    quantity: int = Field(1, ge=1)
    # Required (validated in the route) only for product == "pack", so this
    # stays optional here to not break requests for products that don't yet
    # generate cards (starter_deck, booster_box — follow-up LOT-025 slice).
    set_number: Optional[int] = Field(
        None, description="Active set to draw generated cards from (required for product=pack)"
    )


class GrantedCardSummary(BaseModel):
    """One server-generated card outcome from a booster pack opening."""
    card_id: str
    name: str
    rarity: str
    is_foil: bool
    image_url: Optional[str] = None


class StorePurchaseResponse(BaseModel):
    """Store purchase response with updated balance."""
    user_id: str
    product: StoreProduct
    quantity: int
    unit_price_tolkiens: int
    total_price_tolkiens: int
    balance_before: int
    balance_after: int
    # Populated only for product == "pack" (server-generated card outcomes,
    # LOT-020). Empty for products that don't yet grant cards.
    cards_granted: List[GrantedCardSummary] = Field(default_factory=list)
    transaction_id: Optional[str] = None


class StoreSellBackRequest(BaseModel):
    """Sell owned card copies back to the store for Tolkien."""
    card_id: str
    quantity: int = Field(1, ge=1)
    is_foil: bool = False


class StoreSellBackResponse(BaseModel):
    """Sell-back response with updated balance."""
    user_id: str
    card_id: str
    quantity: int
    is_foil: bool
    unit_value_tolkiens: int
    total_value_tolkiens: int
    balance_before: int
    balance_after: int
    transaction_id: str


class StorePricingResponse(BaseModel):
    """Current product pricing for Tolkien currency."""
    currency: str
    usd_per_tolkien: float
    products: Dict[str, int]


class AdminTolkienAdjustRequest(BaseModel):
    """Admin request to add/remove Tolkien from a user account."""
    amount: int = Field(..., description="Positive adds, negative removes")
    reason: Optional[str] = Field(None, max_length=250)

    @field_validator("amount")
    @classmethod
    def amount_cannot_be_zero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("amount must be non-zero")
        return value


class AdminUserDeleteRequest(BaseModel):
    """Triple-confirm payload for admin user deletion."""
    confirm_user_id: str
    confirm_username: str
    confirm_email: EmailStr


class AdminUserSummary(BaseModel):
    """Admin-focused summary of a user account."""
    id: str
    email: EmailStr
    username: str
    is_active: bool
    is_admin: bool
    is_moderator: bool = False
    tolkien_balance: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUserListResponse(BaseModel):
    """List response for admin user search/list."""
    items: List[AdminUserSummary]
    total: int


# ============== SET RELEASE SCHEMAS (LOT-025) ==============

class SetReleaseSummary(BaseModel):
    """Admin/public-facing view of a set's release status."""
    id: str
    set_number: int
    set_code: Optional[str] = None
    name: str
    is_active: bool
    is_locked_active: bool
    activated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SetReleaseListResponse(BaseModel):
    """Admin list of all sets with their release status."""
    items: List[SetReleaseSummary]


class ActiveSetsResponse(BaseModel):
    """Public list of currently-active (purchasable) sets."""
    active_sets: List[SetReleaseSummary]


# ============== ECONOMY TELEMETRY SCHEMAS (LOT-021) ==============

class CirculationEntry(BaseModel):
    """Total copies of one card currently owned across all users."""
    card_id: str
    name: str
    set_number: Optional[int] = None
    rarity: str
    non_foil_quantity: int
    foil_quantity: int


class DistributionSourceTotals(BaseModel):
    """Aggregate transaction counts/Tolkien flow for one distribution source
    (purchase, sell_back, gift, starter, event, admin)."""
    source: str
    transaction_count: int
    total_tolkien_delta: int


class SellBackRarityTotals(BaseModel):
    """Sell-back volume/value aggregated by card rarity."""
    rarity: str
    cards_sold: int
    total_tolkien_returned: int


class WeeklyRewardStats(BaseModel):
    """Weekly active-user random foil reward telemetry (LOT-021/LOT-100).

    Aggregated across all recorded `weekly_reward_rolls` rows (one per user
    per per-user week_index, win or loss). `distinct_users_rolled` is a
    proxy for weekly-active users, since a roll row is only ever created via
    a successful login.
    """
    total_rolls: int
    total_wins: int
    total_losses: int
    win_rate: float
    distinct_users_rolled: int
    wins_by_rarity: Dict[str, int]


class EconomySummaryResponse(BaseModel):
    """Admin economy/circulation telemetry snapshot (LOT-021 baseline).

    Covers current-totals circulation, audit-trail aggregates, and weekly
    reward roll stats. See `EconomySnapshotSummary`/`EconomyTrendsResponse`
    below for the historical trend/drift-alerting follow-up.
    """
    circulation: List[CirculationEntry]
    foil_issuance_by_rarity: Dict[str, int]
    distribution_by_source: List[DistributionSourceTotals]
    sell_back_by_rarity: List[SellBackRarityTotals]
    weekly_reward_stats: WeeklyRewardStats


class EconomySnapshotSummary(BaseModel):
    """One captured point-in-time economy snapshot (LOT-021/LOT-100
    historical trend telemetry). `alerts` is computed by the endpoint
    (relative to the previous snapshot), not stored on the row."""
    id: str
    captured_at: datetime
    total_cards_in_circulation: int
    total_foil_issued: int
    total_tolkien_net_flow: int
    total_sell_back_cards: int
    total_sell_back_tolkien_returned: int
    weekly_reward_total_rolls: int
    weekly_reward_total_wins: int
    weekly_reward_distinct_users: int
    alerts: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class EconomyTrendsResponse(BaseModel):
    """Historical economy snapshots, oldest first, with simple threshold/
    drift alerts computed between consecutive snapshots."""
    items: List[EconomySnapshotSummary]
    total: int


# ============== GIFT LEDGER SCHEMAS (LOT-019) ==============

class GiftStatus(str, Enum):
    """Gift lifecycle states (LOT-019)."""
    CREATED = "created"
    GRANTED = "granted"
    REDEEMED = "redeemed"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    REVOKED = "revoked"


class AdminGiftCreateRequest(BaseModel):
    """Admin request to gift a store product to a user."""
    recipient_id: str
    product: StoreProduct
    quantity: int = Field(1, ge=1)
    set_number: Optional[int] = Field(
        None, description="Required for product=pack/booster_box"
    )
    note: Optional[str] = Field(None, max_length=250)
    expires_at: Optional[datetime] = None


class GiftSummary(BaseModel):
    """A gift ledger entry as seen by its recipient or an admin."""
    id: str
    sender_id: Optional[str] = None
    recipient_id: str
    product: str
    quantity: int
    set_number: Optional[int] = None
    status: GiftStatus
    note: Optional[str] = None
    expires_at: Optional[datetime] = None
    redeemed_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    transaction_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GiftListResponse(BaseModel):
    """A user's (or admin-queried) list of gifts."""
    items: List[GiftSummary]


class GiftRedeemResponse(BaseModel):
    """Result of redeeming a gift (cards granted, if any)."""
    gift: GiftSummary
    cards_granted: List[GrantedCardSummary] = Field(default_factory=list)


# ============== ENTITLEMENT SCHEMAS (LOT-018 / LOT-025) ==============

class EntitlementStatus(str, Enum):
    """Entitlement lifecycle states."""
    PENDING = "pending"
    ACTIVE = "active"
    CONSUMED = "consumed"
    REVOKED = "revoked"


class EntitlementType(str, Enum):
    """Types of entitlements (starter decks and booster packs)."""
    STARTER_DECK = "starter_deck"
    BOOSTER_PACK = "booster_pack"


class EntitlementSummary(BaseModel):
    """A user's entitlement to a store product."""
    id: str
    user_id: str
    product_type: str  # starter_deck or booster_pack
    set_number: int
    quantity: int
    status: EntitlementStatus
    granted_at: datetime
    consumed_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revocation_reason: Optional[str] = None
    transaction_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class EntitlementListResponse(BaseModel):
    """User's list of active entitlements."""
    items: List[EntitlementSummary]


class EntitlementClaimResponse(BaseModel):
    """Result of claiming an entitlement (cards granted at claim time)."""
    entitlement: EntitlementSummary
    cards_granted: List[GrantedCardSummary] = Field(default_factory=list)
    # Populated only for product_type == "starter_deck" (which curated deck
    # was granted -- there can be more than one eligible deck per set).
    deck_name: Optional[str] = None


class EntitlementClaimRequest(BaseModel):
    """Optional claim parameters.

    `deck_key` selects which curated starter deck to grant (see
    GET /entitlements/starter-deck-options) -- only meaningful for
    product_type == "starter_deck" claims; ignored for booster_pack claims.
    If omitted, a deck is chosen at random (previous behavior).
    """
    deck_key: Optional[str] = None


class StarterDeckOption(BaseModel):
    """A curated starter deck the player can choose to claim (LOT-018)."""
    deck_key: str
    name: str
    card_count: int


class StarterDeckOptionsResponse(BaseModel):
    """Available starter deck choices for a given set."""
    items: List[StarterDeckOption]


# ============== RELEASE EVENT SCHEMAS (LOT-022 / LOT-025) ==============

class ReleaseEventStatus(str, Enum):
    """Release event lifecycle states."""
    SCHEDULED = "scheduled"
    LIVE = "live"
    CLOSED = "closed"


class ReleaseEventCreate(BaseModel):
    """Admin request to create a release event for a set."""
    set_number: int
    title: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=500)
    reward_policy: Optional[Dict[str, Any]] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class ReleaseEventSummary(BaseModel):
    """A release event as seen by admins or participants."""
    id: str
    set_number: int
    title: str
    description: Optional[str] = None
    status: ReleaseEventStatus
    reward_policy: Optional[Dict[str, Any]] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReleaseEventListResponse(BaseModel):
    """List of release events (admin or public view)."""
    items: List[ReleaseEventSummary]


class EventParticipationSummary(BaseModel):
    """A user's participation record for a release event."""
    id: str
    event_id: str
    user_id: str
    reward_transaction_id: Optional[str] = None
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EventParticipationListResponse(BaseModel):
    """Admin-queryable list of participation records for an event."""
    items: List[EventParticipationSummary]


# ============== MATCH SCHEMAS ==============

class MatchMode(str, Enum):
    """Match mode enum."""
    STANDARD = "standard"
    CUSTOM = "custom"
    TOURNAMENT = "tournament"


class MatchBase(BaseModel):
    """Base match schema."""
    mode: MatchMode = MatchMode.STANDARD
    max_players: int = Field(..., ge=2, le=16)
    card_limit: int = Field(..., ge=1, le=100)
    rules_override: Optional[Dict[str, Any]] = None


class MatchCreate(MatchBase):
    """Schema for creating a match."""
    pass


class MatchResponse(MatchBase):
    """Match response schema."""
    id: str
    code: str
    status: str = "waiting"
    current_players: int = 0
    created_at: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class MatchPlayer(BaseModel):
    """Match player schema."""
    player_id: str
    username: str
    joined_at: datetime
    ready: bool = False


class MatchPlayerList(BaseModel):
    """Match players list response."""
    match_id: str
    players: List[MatchPlayer]
    max_players: int


# ============== AUDIT SCHEMAS ==============

class AuditReport(BaseModel):
    """Match audit report."""
    match_id: str
    total_checks: int
    anomalies_found: int
    integrity_score: int
    last_checked: datetime
    recent_anomalies: List[Dict[str, Any]]


# ============== DECK SCHEMAS ==============

class DeckFormat(str, Enum):
    """Deck format/ruleset enum -- real LOTR TCG tournament format names
    (matches the `formats` values scraped into Card.attributes; see
    deck_legality.is_format_legal/check_format_legality). "War of the
    Ring"/"Hunters Block" aren't included -- no card in the current catalog
    lists them."""
    FELLOWSHIP_BLOCK = "Fellowship Block"
    TOWER_BLOCK = "Tower Block"
    KING_BLOCK = "King Block"
    EXPANDED = "Expanded"
    STANDARD = "Standard"
    OPEN = "Open"


class DeckCardEntry(BaseModel):
    """A single card entry inside a deck."""
    card_id: str
    quantity: int = Field(..., ge=1)
    card: Optional[CardResponse] = None

    model_config = ConfigDict(from_attributes=True)


class DeckCreate(BaseModel):
    """Schema for creating a new deck."""
    name: str = Field(..., min_length=1, max_length=100)
    format: DeckFormat = DeckFormat.OPEN
    description: Optional[str] = Field(None, max_length=500)


class DeckUpdate(BaseModel):
    """Schema for updating a deck."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    format: Optional[DeckFormat] = None
    description: Optional[str] = Field(None, max_length=500)


class DeckResponse(BaseModel):
    """Deck response schema."""
    id: str
    user_id: str
    name: str
    format: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    cards: List[DeckCardEntry] = []
    total_cards: int = 0

    model_config = ConfigDict(from_attributes=True)


class DeckListResponse(BaseModel):
    """List of decks for a user."""
    items: List[DeckResponse]
    total: int


class DeckCardAdd(BaseModel):
    """Request to add a card to a deck."""
    card_id: str
    quantity: int = Field(1, ge=1)


class DeckCardRemove(BaseModel):
    """Request to remove a card from a deck (optional partial quantity)."""
    quantity: Optional[int] = Field(None, ge=1)


class DeckLegalityResponse(BaseModel):
    """Aggregate deck-construction legality report (LOT-014)."""
    is_legal: bool
    issues: List[str] = []
    # Informational only -- cards with known tournament errata are flagged
    # here but never make a deck illegal, since this repo has no card-text
    # engine (LOT-013) to actually apply the corrected text/effect.
    errata_notes: List[str] = []
    draw_deck_size: int
    free_peoples_count: int
    shadow_count: int
    site_count: int


class OwnedCardAvailability(BaseModel):
    """Per-card breakdown of owned vs. deck-assigned copies (deck builder
    'available pool' -- a card only has spare copies to add to a deck if
    `available_quantity` > 0, tracked across ALL of the user's decks
    combined, not just the one currently being edited)."""
    card: CardResponse
    owned_quantity: int
    assigned_quantity: int
    available_quantity: int


class OwnedCardAvailabilityListResponse(BaseModel):
    """Response for GET /users/me/cards/available."""
    items: List[OwnedCardAvailability]


# ============== GENERIC SCHEMAS ==============

class PageParams(BaseModel):
    """Pagination parameters."""
    page: int = 1
    page_size: int = 20


class ErrorResponse(BaseModel):
    """Error response schema."""
    detail: str
    code: Optional[str] = None


# ============== CONFIGURATION ==============

class ModelConfig:
    """Pydantic model configuration."""
    from pydantic import ConfigDict

    model_config = ConfigDict(
        populate_by_name=True,  # Allow alias access
        validate_assignment=True,  # Validate on assignment
        arbitrary_types_allowed=True,  # Allow arbitrary types
        json_schema_extra={
            "title": "LOTR TCG API",
            "description": "Schemas for the Lord of the Rings TCG API"
        }
    )
