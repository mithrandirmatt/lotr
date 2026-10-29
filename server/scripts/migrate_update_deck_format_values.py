"""One-off migration: update existing decks.format values from the old
placeholder enum ('standard'/'modern'/'open') to the real LOTR TCG
tournament format names now used by Deck.format/DeckFormat (LOT-014
format/X-list enforcement follow-up). Idempotent -- re-running after values
are already updated is a no-op (no rows match the old values anymore).

'modern' had no real-format equivalent (it was a fictional placeholder, not
part of the actual LOTR TCG format list) -- mapped to 'Open' (the most
permissive real format) so any pre-existing deck stays legal rather than
being retroactively invalidated by this migration.

Run inside the dev container (working directory pinned to server/):
    python scripts/migrate_update_deck_format_values.py
"""
from sqlalchemy import text

from server.core.database import engine

VALUE_MAP = {
    "open": "Open",
    "standard": "Standard",
    "modern": "Open",
}


def main():
    with engine.begin() as conn:
        for old, new in VALUE_MAP.items():
            result = conn.execute(
                text("UPDATE decks SET format = :new WHERE format = :old"),
                {"new": new, "old": old},
            )
            if result.rowcount:
                print(f"Updated {result.rowcount} deck(s) from format='{old}' to '{new}'.")
        print("Done.")


if __name__ == "__main__":
    main()
