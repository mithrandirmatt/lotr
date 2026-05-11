"""Pack manifest verification helpers (placeholder).

In production this should verify a digital signature against a trusted public
key embedded in the client/host.
"""


def verify_manifest(manifest: dict, public_key: str | None = None) -> bool:
    # Minimal check for required fields
    required = {"pack_id", "card_ids", "issued_at", "signature"}
    return required.issubset(set(manifest.keys()))
