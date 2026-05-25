# Debugging Patterns & Common Issues

## Game Logic Debugging

### Issue: Effects not triggering at expected time
**Root cause**: Timing window mismatch
**Solution**: Log exact phase transitions with timestamps
```python
def log_phase_transition(phase, player_id):
    logger.info(f"[{phase}] Player {player_id} at {datetime.now().isoformat()}")
    for card in player.hand:
        if card.has_effect(Trigger(phase)):
            logger.debug(f"  Card {card.id} has {phase} trigger")
```

### Issue: Twilight calculation errors
**Root cause**: Not accounting for roaming minion penalty
**Solution**: Centralized twilight calculator
```python
def calculate_twilight(player, site_path):
    base = 0
    base += player.fellowship.moves  # +1 per move
    base -= len(player.shadow.minions)  # -1 per deployed
    base -= len(player.shadow.roaming)  # -1 per roaming
    return max(0, base)  # Cannot go negative
```

### Issue: Skirmish damage calculation
**Root cause**: Special keywords not being evaluated
**Solution**: Pre-evaluate modifiers before combat
```python
def resolve_skirmish(attacker, defender):
    strength = attacker.stats['strength']
    resistance = defender.stats['resistance']

    # Apply modifiers
    if attacker.has_keyword('fierce'):
        resistance = 0
    if attacker.has_keyword('overwhelm'):
        return True  # Auto-win

    damage = max(1, strength - resistance)
    return damage
```

## Card Database Debugging

### Issue: Game text parsing failures
**Root cause**: Ambiguous phrasing, missing context
**Solution**: Multi-pass parsing with confidence scoring
```python
def parse_game_text(text):
    # Pass 1: Deterministic rules
    actions = apply_deterministic_rules(text)

    # Pass 2: LLM fallback with context
    if not actions:
        actions = llm_parse(text, context=get_card_context())

    # Pass 3: Validation
    validated = validate_actions(actions)
    return {
        'actions': validated,
        'confidence': len(validated) / len(text.split()),
        'ambiguous': not validated
    }
```

### Issue: Duplicate card entries
**Root cause**: Same card printed in multiple sets
**Solution**: Canonical ID + version tracking
```python
class CardEntry:
    def __init__(self, canonical_id, set_name, print_number):
        self.canonical_id = canonical_id  # e.g., "lotr00001"
        self.set_name = set_name
        self.print_number = print_number
        self.variations = []  # Different printings
```

## Performance Debugging

### Issue: Slow game state serialization
**Root cause**: Deep copying entire state
**Solution**: Incremental snapshots with delta encoding
```python
def create_snapshot(state, previous_snapshot):
    delta = {
        'changes': state.diff(previous_snapshot),
        'timestamp': datetime.now().isoformat(),
        'player_id': state.player_id
    }
    return delta  # Much smaller than full state
```

### Issue: Memory leaks in WebSocket connections
**Root cause**: Unreleased game objects
**Solution**: Context managers with cleanup
```python
class GameSession:
    def __enter__(self):
        self.game = Game()
        return self.game

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.game.cleanup()  # Release all resources
        return False
```

## Testing Strategies

### Unit Tests
- Test individual effect resolution
- Test timing windows
- Test edge cases (0 twilight, max minions)

### Integration Tests
- Full turn simulation
- Multi-player interactions
- Network latency simulation

### Replay Tests
- Load recorded game state
- Verify each move was valid
- Check for rule violations
