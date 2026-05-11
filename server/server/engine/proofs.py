"""JSON canonicalization and state-hash helpers."""
import json
import hashlib


def canonical_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'))


def state_hash(canonical_str: str) -> str:
    return hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()
