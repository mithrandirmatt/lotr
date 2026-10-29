"""Deck legality checks (LOT-014), grounded in the official LOTR TCG
Comprehensive Rules 4.2, "Building Your Deck" section
(https://wiki.lotrtcgpc.net/wiki/Comprehensive_Rules_4.2#Building_Your_Deck):

- Draw deck must have at least 60 cards, with an equal number of Shadow
  cards and Free Peoples cards. Site cards and The One Ring are not part
  of the draw deck.
- Up to 4 copies of each card title (ignoring subtitles) are allowed in
  the draw deck.
- The adventure deck must have exactly 9 site cards, all different.

Card attributes relevant here (populated by the wiki card importer, see
`server/scripts/migrate_import_card_catalog.py`) live in `Card.attributes`:
  - "kind": "Free Peoples" | "Shadow" | None (sites / The One Ring)
  - "card_type": "Site" | "The One Ring" | "Companion" | "Ally" | "Minion" |
    "Possession" | "Artifact" | "Event" | "Condition" | "Follower" | "Map"

Our current `Deck`/`DeckCard` schema stores a single flat list of cards
(no separate adventure-deck/ring-bearer slots), so these checks operate on
that flat list, classifying each card by its `card_type`/`kind` attributes.

Format/X-List/errata (LOT-014's other acceptance criterion) are handled
using two more scraped `Card.attributes` fields, also populated by
`migrate_import_card_catalog.py` straight from the wiki catalog:
  - "formats": list of real tournament format names the card is legal in
    (e.g. ["Fellowship Block", "Open"]), or absent/empty for cards with no
    scraped format data (treated as legal everywhere -- missing data must
    never silently ban a card).
  - "on_xlist": list of format names whose Exclusion List (X-List) bans
    this card, or a falsy value if not excluded anywhere.
  - "has_errata": bool, whether the card has known tournament errata. This
    is surfaced as an informational note only (`errata_notes`), never as a
    legality failure -- there is no card-text engine in this repo (see
    LOT-013) to actually execute the corrected wording/effect, so we can't
    honestly "enforce" errata, only disclose it.

R-List (Restricted List) is a genuine, documented gap: no R-List data has
been scraped anywhere in this repo (see `build/py/wiki/create_xlist_databases.py`,
which only builds X-List + errata databases), so there is nothing real to
enforce here. Fabricating an R-List would risk silently banning/restricting
cards based on invented data -- intentionally not done.
"""
from typing import Any, Dict, List, Optional

from ..models.models import Card, DeckCard

MIN_DRAW_DECK_SIZE = 60
MAX_COPIES_PER_TITLE = 4
REQUIRED_SITE_COUNT = 9

SITE_CARD_TYPE = "Site"
ONE_RING_CARD_TYPE = "The One Ring"
NON_DRAW_DECK_CARD_TYPES = {SITE_CARD_TYPE, ONE_RING_CARD_TYPE}


def card_title(name: str) -> str:
    """Return a card's title, ignoring any subtitle after the first comma."""
    return name.split(",")[0].strip()


def is_format_legal(card: Card, format_name: str) -> bool:
    """True if `card` can legally be included in a deck built for
    `format_name`. Cards imported without scraped `formats` data (e.g.
    dev-seed placeholder rows predating the real catalog import) are
    treated as legal everywhere. X-List membership always overrides an
    otherwise-legal `formats` membership.
    """
    attrs = card.attributes or {}
    formats = attrs.get("formats")
    if formats and format_name not in formats:
        return False
    on_xlist = attrs.get("on_xlist")
    if on_xlist and format_name in on_xlist:
        return False
    return True


def check_format_legality(card: Card, format_name: str) -> None:
    """Raise ValueError with a precise reason if `card` isn't legal in
    `format_name` (see `is_format_legal`)."""
    attrs = card.attributes or {}
    formats = attrs.get("formats")
    if formats and format_name not in formats:
        raise ValueError(
            f"'{card.name}' is not legal in the '{format_name}' format "
            f"(legal in: {', '.join(formats)})."
        )
    on_xlist = attrs.get("on_xlist")
    if on_xlist and format_name in on_xlist:
        raise ValueError(
            f"'{card.name}' is on the {format_name} exclusion list (X-List) and cannot be used."
        )


def evaluate_deck_legality(deck_cards: List[DeckCard], format_name: Optional[str] = None) -> Dict[str, Any]:
    """Evaluate aggregate deck-construction legality for a full list of
    `DeckCard` rows (with `.card` relationship loaded).

    `format_name` is optional (older callers/tests that only care about
    size/split/site-count rules can omit it) -- when given, each card is
    also checked against `is_format_legal`/`check_format_legality`.

    Returns a dict with counts and a list of human-readable issue strings.
    `is_legal` is True only if `issues` is empty. `errata_notes` is a
    separate informational list that never affects `is_legal` (see module
    docstring).
    """
    draw_deck_size = 0
    free_peoples_count = 0
    shadow_count = 0
    site_count = 0
    issues: List[str] = []
    errata_notes: List[str] = []

    for dc in deck_cards:
        card: Card = dc.card
        if card is None:
            continue
        attrs = card.attributes or {}
        card_type = attrs.get("card_type")
        kind = attrs.get("kind")

        if format_name:
            try:
                check_format_legality(card, format_name)
            except ValueError as exc:
                issues.append(str(exc))
        if attrs.get("has_errata"):
            errata_notes.append(
                f"'{card.name}' has known tournament errata -- verify current card text before play."
            )

        if card_type == SITE_CARD_TYPE:
            site_count += dc.quantity
            continue
        if card_type == ONE_RING_CARD_TYPE:
            continue

        draw_deck_size += dc.quantity
        if kind == "Free Peoples":
            free_peoples_count += dc.quantity
        elif kind == "Shadow":
            shadow_count += dc.quantity

    if draw_deck_size < MIN_DRAW_DECK_SIZE:
        issues.append(
            f"Draw deck has {draw_deck_size} cards; at least {MIN_DRAW_DECK_SIZE} are required."
        )
    if free_peoples_count != shadow_count:
        issues.append(
            f"Draw deck must have an equal number of Free Peoples and Shadow cards "
            f"(currently {free_peoples_count} Free Peoples, {shadow_count} Shadow)."
        )
    if site_count != REQUIRED_SITE_COUNT:
        issues.append(
            f"Adventure deck has {site_count} site cards; exactly {REQUIRED_SITE_COUNT} are required."
        )

    return {
        "is_legal": not issues,
        "issues": issues,
        "errata_notes": errata_notes,
        "draw_deck_size": draw_deck_size,
        "free_peoples_count": free_peoples_count,
        "shadow_count": shadow_count,
        "site_count": site_count,
    }


def check_copy_limit(deck_cards: List[DeckCard], card: Card, added_quantity: int) -> None:
    """Raise ValueError if adding `added_quantity` copies of `card` would
    violate the copy-limit rules:
      - Site cards: at most 1 copy (each site on the adventure path must be different).
      - All other cards: at most 4 copies of the same card title (ignoring subtitle).
    """
    attrs = card.attributes or {}
    card_type = attrs.get("card_type")

    if card_type == SITE_CARD_TYPE:
        existing = sum(
            dc.quantity for dc in deck_cards
            if dc.card and dc.card.id == card.id
        )
        if existing + added_quantity > 1:
            raise ValueError(
                f"'{card.name}' is a site card; only one copy is allowed (each site must be different)."
            )
        return

    if card_type == ONE_RING_CARD_TYPE:
        return

    title = card_title(card.name)
    existing_same_title = sum(
        dc.quantity for dc in deck_cards
        if dc.card and card_title(dc.card.name) == title
    )
    if existing_same_title + added_quantity > MAX_COPIES_PER_TITLE:
        raise ValueError(
            f"'{title}' already has {existing_same_title} cop{'y' if existing_same_title == 1 else 'ies'} "
            f"in this deck; maximum is {MAX_COPIES_PER_TITLE}."
        )
