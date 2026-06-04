"""
API v1 module initialization.
"""
from api.v1.routes import (
    auth,
    cards,
    purchases,
    matches,
    audits,
    users,
)
from api.v1.deps import get_db

# Register routes
api_router = [
    auth.router,
    cards.router,
    purchases.router,
    matches.router,
    audits.router,
    users.router,
]
