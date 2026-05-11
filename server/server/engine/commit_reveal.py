"""Simple commit-reveal utilities (non-cryptographic helpers).

Replace or extend with stronger primitives for production (e.g., HMAC,
digital signatures) if required.
"""
import hashlib


def commit(seed: bytes) -> str:
    return hashlib.sha256(seed).hexdigest()


def reveal(seed: bytes) -> bytes:
    return seed
