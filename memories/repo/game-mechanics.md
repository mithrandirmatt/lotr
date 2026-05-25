# LotR TCG Game Mechanics Reference

## Core Game Flow

### Turn Structure (per player)
1. **Fellowship Phase** — Play companions, draw cards
2. **Shadow Phase** — Deploy minions within twilight budget
3. **Maneuver Phase** — Move companions (add twilight per FP move)
4. **Archery Phase** — Remove twilight to destroy shadow minions
5. **Assignment Phase** — Assign minions to companions
6. **Skirmish Phase** — Resolve combat (strength vs resistance)
7. **Regroup Phase** — Reset positions, discard top of deck

### Win/Loss Conditions
- **Win**: Shadow Ring-bearer killed OR corrupted OR site 9 reached
- **Loss**: Fellowship Ring-bearer killed OR corrupted OR site 9 reached

## Key Mechanics

### Twilight Pool
- Starts at 0
- +1 when FP moves
- -1 when Shadow deploys minion
- -1 per roaming minion (penalty)
- Cannot go negative

### Wound/Burden/Resistance
- **Wound**: HP of companions/minions
- **Burden**: Resource cost for certain actions
- **Resistance**: Defense value in skirmish

### Skirmish Resolution
- Compare Strength vs Resistance
- Damage = Strength - Resistance (minimum 1)
- Special keywords: fierce (ignore resistance), overwhelm (auto-win)

## Trigger Types

| Trigger | Timing | Description |
|---------|--------|-------------|
| Fellowship | Phase start | Effects when phase begins |
| Shadow | Phase start | Deploy minions |
| Maneuver | During movement | Movement-related effects |
| Archery | During archery | Archery phase effects |
| Skirmish | During combat | Combat resolution |
| Regroup | Phase end | End-of-turn effects |
| Assignment | During assignment | Minion placement |

## Special Keywords

- **Archer**: Can be destroyed by archery
- **Fierce**: Ignore resistance in skirmish
- **Damage +X**: Deal X damage
- **When Playing**: Trigger when card enters play
- **While**: Continuous effect
- **Each Time**: Repeatable trigger

## Format Rules

- **Fellowship Block**: Specific card pool and rules
- **Standard**: Current legal cards
- **Open**: All cards ever printed
- **4-copy limit**: Maximum 4 of same card
- **9 sites**: Maximum minions per site
- **60-card minimum**: Deck size requirement
