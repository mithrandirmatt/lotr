# Architecture Decisions

## Technology Stack

### Frontend/Engine
- **Godot 4** — 2D game engine for the actual game
  - GDScript for game logic
  - C# for complex systems
  - Built-in physics and collision detection
  - Scene system for modular design

### Backend
- **FastAPI (Python)** — REST API for deck builder, accounts, tournaments
  - Async support for WebSocket game state
  - Automatic OpenAPI documentation
  - Pydantic validation

### Database
- **PostgreSQL** — Primary database
  - Cards, decks, users, game history
  - JSONB fields for flexible card data
  - Full-text search for card lookup

### Data Processing
- **Python scripts** — Card database generation, game logic parsing
- **FastAPI workers** — Background processing for large operations

## Design Patterns

### Game State Management
```
PlayerState
├── RingBearer (wound, position, stats)
├── Fellowship (companions, hand, deck)
├── Shadow (minions, twilight, hand)
└── SitePath (current site, path history)
```

### Card Effect System
```
CardEffect
├── Trigger (phase, event, condition)
├── Cost (burden, twilight, resources)
├── Conditions (targets, values, timing)
└── Effects (instant, continuous, delayed)
```

### Data Layer
```
Repository Pattern
├── CardRepository (read/write cards)
├── DeckRepository (CRUD decks)
├── GameLogRepository (match history)
└── UserRepository (accounts, collections)
```

## API Design

### REST Endpoints
- `/api/v1/cards` — Card database
- `/api/v1/decks` — Deck management
- `/api/v1/matches` — Game state (WebSocket)
- `/api/v1/auth` — Authentication

### WebSocket Protocol
```json
{
  "type": "game_state_update",
  "player_id": "uuid",
  "state": { ... },
  "timestamp": "iso8601"
}
```

## File Organization

```
lotr/
├── assets/           # Game assets, reference docs
├── build/            # Build scripts, pipelines
├── gotdot/           # Godot project files
├── server/           # FastAPI backend
├── web/              # Frontend components
└── scripts/          # Data processing scripts
```

## Performance Considerations

- **Card database**: Indexed lookups for O(1) retrieval
- **Game state**: Immutable snapshots for replay/debugging
- **WebSocket**: Heartbeat every 30s, reconnection handling
- **Database**: Connection pooling, query caching
