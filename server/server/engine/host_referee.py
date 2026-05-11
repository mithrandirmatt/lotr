"""Host referee helpers: apply actions, write signed logs, compute state hashes."""
from typing import Any, Dict
from .proofs import canonical_json, state_hash
from .core import apply_action


class HostReferee:
    def __init__(self, initial_state: Any, signing_key: Any | None = None):
        self.state = initial_state
        self.signing_key = signing_key
        self.log = []

    def apply(self, action: Dict[str, Any], rng_state: Any | None = None) -> Dict[str, Any]:
        prev = state_hash(canonical_json(self.state.__dict__))
        new_state, events = apply_action(self.state, action, rng_state)
        post = state_hash(canonical_json(new_state.__dict__))
        entry = {"action": action, "prev": prev, "post": post, "events": events}
        # signing hook could be added here
        self.log.append(entry)
        self.state = new_state
        return entry
