"""Models package (submodule of `server.server`).

The canonical, actively-wired models live in `.models` (imported directly by
`routes/api.py` as `from ..models.models import ...`) and `.schemas`.

NOTE: An earlier, incomplete LOT-025 prototype added `.entities` /
`.economy.*` / `.base` (BaseModel/TimestampMixin/Money/ItemType) as a second,
parallel model system. That prototype was never finished (`entities.py` was
never created, and `base.py`/`economy/*.py` reference `Column`/`Integer`/
SQLAlchemy's `Enum` without importing them) and is not used by any route.
This package used to eagerly import that broken code at import time, which
crashed the entire app (`NameError` on every `import server.models`). Those
eager imports have been removed so the real app can boot; the unfinished
`base.py`/`entities.py`/`economy/` files are left in place for a future
cleanup/decision (extend vs. remove) rather than silently deleted here.
"""

