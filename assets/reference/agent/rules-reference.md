# LotR TCG Comprehensive Rules Reference (v4.2 / v5.0)

Sources:
- v4.2 (Decipher): `build/do/assets/wiki/Comprehensive_Rules_4.2.html`
- v5.0 (Player's Council): `build/do/assets/wiki/Comprehensive_Rules_5.0.html`

---

## v5.0 / Player's Council Changes

The following rules changes apply in **Player's Council (PC) formats** (Open, Standard, and PC Block formats). v4.2 is the Decipher base; v5.0 supersedes it for PC play.

1. **PC Errata in effect** — All Player's Council errata are enforced in PC formats.
2. **"Item"** — New term meaning "Artifact or Possession." Card text using "item" refers to either type.
3. **"Here" on site text** — Shorthand for "while the fellowship is at this site." Functionally equivalent.
4. **Win condition timing** — The game ends when the Shadow player is *about to reconcile* (start of reconciliation), not at the start of the Regroup phase. Regroup actions may still be performed before the game ends.
5. **Discard piles are public** — All discard piles are face-up and visible to all players at all times. You may look through your own freely; you cannot physically search an opponent's, but you can see all cards in it.
6. **"Cannot" overrides "Can"** — Explicit priority rule: any game text stating something "cannot happen" takes precedence over any text stating it "can happen."

---

## Card Kinds

| Kind | Indicator |
|------|-----------|
| Free Peoples | Light circular field, upper-left corner |
| Shadow | Dark diamond-shaped field, upper-left corner |
| Site | Dark compass, upper-left corner |
| The One Ring | Neither FP nor Shadow |

---

## Card Types (10 total)

| Type | Description |
|------|-------------|
| The One Ring | Unique powerful item; no twilight cost; not FP or Shadow |
| Site | Location card; lives in adventure deck (9 per player) |
| Companion | FP character in your fellowship |
| Ally | FP character in support area; does not move with fellowship |
| Minion | Shadow character; attacks fellowships |
| Follower | Short-term helper; not a character |
| Possession | Object borne by a character (weapon, armor, etc.) |
| Artifact | Unique object; different card type from possession — not interchangeable |
| Event | Play from hand once; discard after play; effects may persist |
| Condition | Stays in play until discarded; plays to support area or on a card |

Companion + Ally + Minion = **character cards**. Followers are NOT characters.

---

## Cultures

**Free Peoples:** Dwarven, Elven, Gandalf, Gollum, Gondor, Rohan, Shire

**Shadow (Movie-era):** Dunland, Gollum, Isengard, Moria, Raider, Ringwraith, Sauron

**Shadow (Shadows-era):** Men, Orc, Uruk-hai, Wraith

Sites and The One Ring have no culture.

---

## Core Stats

### Vitality
- Life force of a character. Each wound reduces vitality by 1.
- Vitality reaches 0 → character is immediately **killed**.
- Reducing strength to 0 does NOT kill.

### Wounds vs. Exert
- Both place wound tokens. Cards that *prevent wounds* cannot prevent exert tokens.
- Once placed, either type can be healed by any heal effect.
- Cannot exert an **exhausted** character (1 vitality remaining).
- "Exhaust" = exert as many times as possible.

### Healing
- At **sanctuary** (site 3 or site 6): heal up to 5 wounds from companions (not allies) at start of turn.

### Killed
- FP characters (companions/allies) → **dead pile**
- Minions → **discard pile**
- Unique companion/ally in dead pile → cannot replay that title

### Resistance (Companions only)
- Represents resistance to The One Ring.
- Pre-Shadows companions (non-Frodo/Sam) without printed resistance = **6**.
- Allies have resistance **0**.
- Ring icon around resistance = eligible to be Ring-bearer.

### Burdens
- Placed only on the Ring-bearer.
- Each burden reduces **all companions'** resistance by 1.
- Ring-bearer resistance → 0 = **corrupted** = you lose.
- Only the Ring-bearer can be corrupted; other companions reaching 0 resistance have no immediate penalty.

### Strength
- Used in skirmish resolution. Winner = higher total strength.
- Tie → Shadow wins.
- Double or more → losing side is **overwhelmed** and all killed.

---

## Signet
Found in lower-left corner of some FP characters. Available signets: **Aragorn, Frodo, Gandalf, Théoden**. Cards with matching signets synergize.

---

## Twilight Pool

- FP cards played → **add** twilight equal to cost.
- Shadow cards played → **remove** twilight equal to cost.
- Shadow card cannot be played if pool is insufficient.

---

## Deck Building

| Component | Requirement |
|-----------|-------------|
| Ring-bearer + The One Ring | 2 cards, not in draw deck |
| Draw deck | Minimum 60 cards, equal FP and Shadow cards |
| Adventure deck | Exactly 9 site cards, all different |
| Copy limit | Up to 4 copies per title (ignoring subtitles) |
| Ring-bearer in draw deck | Max 3 copies (1 is in starting fellowship) |

---

## Game Formats

| Format | Sets Allowed | Sites |
|--------|-------------|-------|
| Fellowship block | 1, 2, 3 | Numbered sequential |
| Tower block | 4, 5, 6 | Numbered sequential |
| King block | 7, 8, 10 | Numbered sequential |
| War of the Ring block | 11, 12, 13 | Player choice |
| Open | All (including set 9 Reflections) | From set 11+ (Shadows) |
| Standard | All (with X-List restrictions) | From set 11+ |

Block formats: sites must be played in sequential order; no region twilight penalty.

---

## Setup

1. **Bid burdens** to determine turn order (highest bid = first choice; bid tokens become burdens on Ring-bearer).
2. Each player places their adventure deck face-down.
3. First player plays a site from their adventure deck as **site 1**.
4. All players place player markers on site 1.
5. Each player reveals **starting fellowship**: Ring-bearer + companions with total twilight cost ≤ 4 (Ring-bearer cost excluded). No twilight added for starting fellowship.
6. Shuffle draw decks; draw **8 cards**.

Mulligan available (from Tournament Guidelines).

---

## Turn Sequence

### Start of Turn
- Remove all tokens from twilight pool.
- Resolve "start of turn" actions (once each).

### 1. Fellowship Phase
- FP player may perform fellowship actions in any order:
  - Play companion, ally, possession, artifact, or condition from hand.
  - "Discard to heal": discard card with same title as a wounded unique companion/ally to heal it.
  - Special abilities and events with **Fellowship:** keyword.
- **Rule of 4**: Cannot draw more than 4 cards during fellowship phase.
- **Rule of 9**: Cannot have more than 9 companions total (in play + dead pile).
- Allies go to **support area** (no fellowship limit; considered at their home site).
- Equipment classes: one weapon per class (hand, ranged, armor, cloak, staff) per character.
- **Move**: Fellowship must move to the next site. A Shadow player (indicated by site arrow) places the new site from their adventure deck.

**Twilight added on movement:**
- Shadow number of new site
- +3 if region 2 (past site 3), +6 if region 3 (past site 6)
- +1 per companion in fellowship

### 2. Shadow Phase(s)
- Each non-FP player (right-to-left) gets one Shadow phase.
- May play minions, possessions, artifacts, conditions from hand.
- All Shadow players share the same twilight pool.
- Minions played to center table. Each minion has a site number; playing below it = **roaming** (+2 twilight cost).
- If no minions in play after final Shadow phase → skip to Regroup.

### 3. Maneuver Phase
- Players perform **Maneuver:** actions using action procedure.
- Action procedure: FP player first, then counter-clockwise. Pass to skip (can act later).
- All consecutive passes → end phase.
- No minions remaining → skip to Regroup.

### 4. Archery Phase
- Players perform **Archery:** actions, then conduct archery fire.
- Minion archery total = count all Shadow archer minions.
- Fellowship archery total = count all FP archer companions (+ allies at home site).
- FP assigns wounds equal to minion archery total to companions/allies.
- FP chooses one Shadow player who assigns wounds equal to fellowship archery total to their minions.
- Wounds assigned one at a time; cannot exceed vitality; excess ignored.
- No minions remaining → skip to Regroup.

### 5. Assignment Phase
- Players perform **Assignment:** actions.
- FP player assigns companions (and eligible allies) to defend against minions.
- One companion per minion maximum (unless **defender +X**).
- Shadow players then assign any leftover unassigned minions to any companions.
- **Ambush X**: when FP assigns a character to this minion, Shadow player may add X twilight.
- Once all assignments made → each assigned companion leads to a separate Skirmish.

### 6. Skirmish Phase(s)
- FP player chooses order of skirmishes.
- Each skirmish: players perform **Skirmish:** actions, then resolve.
- Resolution:
  - Higher total strength wins. Tie = Shadow wins.
  - Loser takes 1 wound per character.
  - **Damage +X**: additional wounds on losers.
  - **Overwhelming**: winning side ≥ double losing strength → all losers killed instantly (no wounds).
- After all normal skirmishes, **Fierce** minions trigger a second assignment + skirmish round.

### 7. Regroup Phase
- Players perform **Regroup:** actions.
- Shadow players reconcile hand to 8 cards (may discard 1 first; draw up or discard down to 8).
- FP player chooses:
  - **Move again** (if within move limit): add twilight for new site, return to Shadow phase.
  - **Stay**: reconcile hand to 8, Shadow players discard all minions, turn ends.
- **Move limit**: 2 moves per turn in 2-3 player games; equal to number of opponents in 4+ player games.

---

## Winning and Losing

- **Win**: Fellowship reaches site 9 and Ring-bearer survives all skirmishes. **(v4.2)** No regroup phase on final turn. **(v5.0/PC)** Regroup actions may still occur; game ends when the Shadow player is about to reconcile their hand.
- **Lose (Ring-bearer killed)**: Ring-bearer dies. Another character may take over if game text allows.
- **Lose (corrupted)**: Ring-bearer's resistance reaches 0 from burdens.
- **Eliminated player**: Remove all their cards; replace their sites on the adventure path.

---

## Key Glossary Terms

| Term | Meaning |
|------|---------|
| **Active** | Your FP cards, opponent's Shadow cards, and all sites are active on your turn. Other players' FP cards are inactive. |
| **Aid – X** | Maneuver action to attach follower to a character for the turn by paying X twilight. |
| **Ambush X** | When FP assigns to this minion, Shadow may add X twilight. |
| **Archer** | Keyword; contributes to archery total. |
| **Defender +X** | Can defend against X additional minions. |
| **Damage +X** | Adds X wounds to losers of a skirmish. |
| **Fierce** | Minion fights a second time after normal skirmishes. |
| **Overwhelmed** | Outstrengthened 2:1 or more → immediately killed. |
| **Roaming** | Minion played below its site number; costs +2 twilight. |
| **Rule of 4** | Max 4 cards drawn per fellowship phase. |
| **Rule of 9** | Max 9 companions total across play and dead pile. |
| **Sanctuary** | Site 3 or site 6; heal up to 5 wounds at start of turn. |
| **Spot** | Check a card is in play to meet a requirement. |
| **Support area** | Area behind fellowship for allies, conditions, and some possessions. |
| **Unhasty** | Cannot be assigned to a skirmish by assignment actions. |
| **Unique** | Only one copy with same title in play at a time; dead pile blocks replay. |
| **When / Each Time / While** | Triggers: When=once, Each Time=repeatable, While=continuous. |
| **Response** | Optional action taken immediately after a trigger; not a phase action. |
| **Item** *(v5.0)* | Synonym for "Artifact or Possession" in card text. |
| **Here** *(v5.0, site text)* | Shorthand for "while the fellowship is at this site." |
| **Cannot > Can** *(v5.0)* | Priority rule: "cannot happen" game text overrides "can happen" game text. |

---

## Formats & X-Lists

- **X-List (Standard)**: Cards banned or restricted in Standard format.
- **R-List (Open/Block)**: Cards with restricted quantities in Open and Block formats.
- **Expanded format** has its own X-list and R-list.
- See Section Four of the rules HTML for full lists.

---

*This reference covers Section One (Overview) and key terms from Section Two (Glossary) of Comprehensive Rules 4.2, annotated with changes from v5.0 (Player's Council). For individual card rulings see Section Three of the respective source file.*
