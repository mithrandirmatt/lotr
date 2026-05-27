"""
=== LOTR TCG: Artifact Card System ===

This module implements the Artifact card type system, a new card category
that provides passive buffs, equipment effects, and strategic positioning.

Artifact Cards are unique in that:
- They remain on the board until destroyed or end of game
- They provide continuous effects (While keywords)
- They can be equipped to companions or placed on sites
- They have durability (can be damaged in skirmishes)
"""

from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class ArtifactType(Enum):
    """Types of Artifact cards"""
    WEAPON = "weapon"           # Equipment that boosts strength
    ARMOR = "armor"             # Equipment that boosts resistance/vitality
    RELIC = "relic"             # Passive buffs and abilities
    TREASURE = "treasure"       # Resource generation effects
    ENCHANTMENT = "enchantment" # Site-based effects
    CURSE = "curse"             # Negative effects (usually shadow side)


class ArtifactPosition(Enum):
    """Where an artifact can be placed"""
    EQUIPPED = "equipped"       # Attached to a companion
    SITE = "site"               # Placed on a site
    HAND = "hand"               # Still in player's hand
    DECK = "deck"               # In draw deck
    DISCARD = "discard"         # In discard pile
    GRAVEYARD = "graveyard"     # Destroyed artifacts


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ArtifactCost:
    """Represents the cost to play an artifact"""
    burden: int = 0
    twilight: int = 0
    life: int = 0
    special: List[Dict[str, Any]] = field(default_factory=list)

    def total_cost(self) -> int:
        """Calculate total resource cost"""
        return self.burden + self.twilight + self.life + len(self.special)


@dataclass
class ArtifactEffect:
    """A single effect that an artifact provides"""
    effect_id: str
    effect_type: str
    target: str
    value: Any
    duration: str = "permanent"  # permanent, until_regroup, until_end_turn
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)

    def is_active(self, game_state: Dict[str, Any]) -> bool:
        """Check if this effect is currently active"""
        # Duration check
        if self.duration == "permanent":
            return True
        elif self.duration == "until_end_turn":
            return game_state.get("phase") != "regroup"
        elif self.duration == "until_regroup":
            return True  # Simplified - would check actual regroup state

        return True


@dataclass
class Artifact:
    """
    Complete artifact card definition.

    Artifacts have unique properties that distinguish them from regular cards:
    - Continuous effects (While keywords)
    - Position-dependent abilities
    - Equipment mechanics
    - Durability system
    """
    artifact_id: str
    name: str
    artifact_type: ArtifactType
    cost: ArtifactCost
    stats: Dict[str, int] = field(default_factory=dict)  # strength, resistance, vitality
    effects: List[ArtifactEffect] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    description: str = ""
    image_path: str = ""
    rarity: str = "common"
    durability: int = 0  # How much damage it can take
    current_durability: int = 0

    # Position-specific properties
    equipable: bool = True
    site_effect: bool = False
    destroy_on_leave: bool = False

    # Combat properties
    fierce: bool = False
    overwhelm: bool = False
    archer: bool = False

    def __post_init__(self):
        """Initialize derived properties"""
        self.current_durability = self.durability
        self.position = ArtifactPosition.HAND

    def apply_effect(self, effect: ArtifactEffect, game_state: Dict[str, Any]) -> bool:
        """Apply an effect and return True if still active"""
        if not effect.is_active(game_state):
            return False

        # Apply the effect based on type
        effect_type = effect.effect_type.lower()

        if effect_type == "add_strength":
            target = self._find_target(effect.target, game_state)
            if target:
                target["strength"] += effect.value

        elif effect_type == "add_resistance":
            target = self._find_target(effect.target, game_state)
            if target:
                target["resistance"] += effect.value

        elif effect_type == "add_vitality":
            target = self._find_target(effect.target, game_state)
            if target:
                target["vitality"] += effect.value

        elif effect_type == "generate_twilight":
            game_state["twilight"] += effect.value

        elif effect_type == "draw_cards":
            target = self._find_target(effect.target, game_state)
            if target:
                target["hand_size"] += effect.value

        return True

    def _find_target(self, target_name: str, game_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find the target entity for an effect"""
        if target_name == "self":
            return self  # Return artifact itself

        if target_name == "equipped_companion":
            for companion in game_state.get("companions", []):
                if companion.get("equipped_artifact_id") == self.artifact_id:
                    return companion

        if target_name == "site":
            # Find site where artifact is placed
            for site in game_state.get("sites", []):
                if site.get("artifact_id") == self.artifact_id:
                    return site

        return None

    def take_damage(self, damage: int) -> bool:
        """
        Take damage in a skirmish.
        Returns True if artifact is still alive.
        """
        self.current_durability -= damage
        if self.current_durability <= 0:
            self.destroy()
            return False
        return True

    def destroy(self):
        """Destroy the artifact"""
        self.position = ArtifactPosition.GRAVEYARD
        # Trigger on-destroy effects here

    def equip(self, companion_id: str, game_state: Dict[str, Any]) -> bool:
        """Equip artifact to a companion"""
        if not self.equipable:
            return False

        # Unequip any existing artifact
        existing_artifact = game_state.get("equipped_artifact_id")
        if existing_artifact:
            existing_artifact.position = ArtifactPosition.HAND

        self.position = ArtifactPosition.EQUIPPED
        companion = next((c for c in game_state.get("companions", []) if c["id"] == companion_id), None)
        if companion:
            companion["equipped_artifact_id"] = self.artifact_id

        # Apply equipment effects
        for effect in self.effects:
            if effect.target == "equipped_companion":
                self.apply_effect(effect, game_state)

        return True

    def place_on_site(self, site_id: str, game_state: Dict[str, Any]) -> bool:
        """Place artifact on a site"""
        if not self.site_effect:
            return False

        site = next((s for s in game_state.get("sites", []) if s["id"] == site_id), None)
        if site:
            site["artifact_id"] = self.artifact_id
            self.position = ArtifactPosition.SITE

            # Apply site effects
            for effect in self.effects:
                if effect.target == "site":
                    self.apply_effect(effect, game_state)

            return True
        return False


# ============================================================================
# ARTIFACT FACTORY
# ============================================================================

class ArtifactFactory:
    """Factory for creating and managing artifact cards"""

    def __init__(self):
        self.artifacts: Dict[str, Artifact] = {}
        self.artifact_database: List[Artifact] = []

    def register_artifact(self, artifact: Artifact) -> None:
        """Register an artifact in the database"""
        self.artifact_database.append(artifact)
        self.artifacts[artifact.artifact_id] = artifact

    def get_artifact(self, artifact_id: str) -> Optional[Artifact]:
        """Retrieve an artifact by ID"""
        return self.artifacts.get(artifact_id)

    def get_artifacts_by_type(self, artifact_type: ArtifactType) -> List[Artifact]:
        """Get all artifacts of a specific type"""
        return [a for a in self.artifact_database if a.artifact_type == artifact_type]

    def get_artifacts_by_keyword(self, keyword: str) -> List[Artifact]:
        """Get all artifacts with a specific keyword"""
        return [a for a in self.artifact_database if keyword in a.keywords]

    def search_artifacts(self, query: str) -> List[Artifact]:
        """Search artifacts by name, description, or keywords"""
        query_lower = query.lower()
        results = []
        for artifact in self.artifact_database:
            if (query_lower in artifact.name.lower() or
                query_lower in artifact.description.lower() or
                any(query_lower in kw.lower() for kw in artifact.keywords)):
                results.append(artifact)
        return results

    def generate_sample_artifacts(self) -> List[Artifact]:
        """Generate sample artifacts for testing"""
        samples = [
            # Weapon Artifacts
            Artifact(
                artifact_id="art_001",
                name="Elendil's Sword",
                artifact_type=ArtifactType.WEAPON,
                cost=ArtifactCost(burden=1, twilight=1),
                stats={"strength": 3},
                keywords=["fierce"],
                description="A legendary blade that grants fierce ability.",
                equipable=True,
                durability=5
            ),

            Artifact(
                artifact_id="art_002",
                name="Shield of Gondor",
                artifact_type=ArtifactType.ARMOR,
                cost=ArtifactCost(burden=1),
                stats={"resistance": 2},
                keywords=["overwhelm"],
                description="A mighty shield that grants overwhelm ability.",
                equipable=True,
                durability=4
            ),

            # Relic Artifacts
            Artifact(
                artifact_id="art_003",
                name="Palantír of Orthanc",
                artifact_type=ArtifactType.RELIC,
                cost=ArtifactCost(burden=2, twilight=2),
                effects=[
                    ArtifactEffect(
                        effect_id="palantir_1",
                        effect_type="draw_cards",
                        target="self",
                        value=1,
                        duration="until_end_turn",
                        triggers=["regroup"]
                    )
                ],
                keywords=["While in play: Draw 1 card during Regroup"],
                description="A seeing stone that grants vision.",
                durability=3
            ),

            Artifact(
                artifact_id="art_004",
                name="One Ring",
                artifact_type=ArtifactType.CURSE,
                cost=ArtifactCost(burden=0, twilight=0),
                effects=[
                    ArtifactEffect(
                        effect_id="ring_1",
                        effect_type="add_strength",
                        target="equipped_companion",
                        value=2,
                        duration="permanent"
                    ),
                    ArtifactEffect(
                        effect_id="ring_2",
                        effect_type="add_vitality",
                        target="equipped_companion",
                        value=-1,
                        duration="permanent"
                    )
                ],
                keywords=["While equipped: +2 Strength, -1 Vitality"],
                description="The Ring of Power. Powerful but corrupting.",
                equipable=True,
                durability=1
            ),

            # Treasure Artifacts
            Artifact(
                artifact_id="art_005",
                name="Isildur's Crown",
                artifact_type=ArtifactType.TREASURE,
                cost=ArtifactCost(burden=1),
                effects=[
                    ArtifactEffect(
                        effect_id="crown_1",
                        effect_type="generate_twilight",
                        target="self",
                        value=1,
                        triggers=["archery"]
                    )
                ],
                keywords=["While in play: Generate 1 twilight during Archery"],
                description="A crown that stores twilight.",
                durability=2
            ),

            # Enchantment Artifacts
            Artifact(
                artifact_id="art_006",
                name="Mount Doom",
                artifact_type=ArtifactType.ENCHANTMENT,
                cost=ArtifactCost(burden=3, twilight=3),
                site_effect=True,
                effects=[
                    ArtifactEffect(
                        effect_id="doom_1",
                        effect_type="add_resistance",
                        target="site",
                        value=5,
                        duration="permanent"
                    ),
                    ArtifactEffect(
                        effect_id="doom_2",
                        effect_type="add_vitality",
                        target="site",
                        value=-2,
                        duration="permanent"
                    )
                ],
                keywords=["Site effect: +5 Resistance, -2 Vitality"],
                description="The fiery mountain. A dangerous site.",
                durability=10
            ),
        ]

        for artifact in samples:
            self.register_artifact(artifact)

        return samples


# ============================================================================
# ARTIFACT GAME STATE MANAGER
# ============================================================================

class ArtifactGameState:
    """Manages artifact state during gameplay"""

    def __init__(self, artifact_factory: ArtifactFactory):
        self.factory = artifact_factory
        self.active_artifacts: Dict[str, Artifact] = {}
        self.artifact_events: List[Dict[str, Any]] = []

    def play_artifact(self, artifact_id: str, player: str, game_state: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Attempt to play an artifact.
        Returns (success, message)
        """
        artifact = self.factory.get_artifact(artifact_id)
        if not artifact:
            return False, f"Artifact {artifact_id} not found"

        # Check cost
        if game_state.get("twilight", 0) < artifact.cost.twilight:
            return False, "Not enough twilight"
        if game_state.get("burden", 0) < artifact.cost.burden:
            return False, "Not enough burden"

        # Pay cost
        game_state["twilight"] -= artifact.cost.twilight
        game_state["burden"] -= artifact.cost.burden

        # Place artifact
        artifact.position = ArtifactPosition.EQUIPPED

        # Apply effects
        for effect in artifact.effects:
            self.apply_effect(effect, artifact, game_state)

        self.active_artifacts[artifact_id] = artifact
        self.artifact_events.append({
            "type": "artifact_played",
            "artifact_id": artifact_id,
            "player": player,
            "timestamp": datetime.now().isoformat()
        })

        return True, f"Played {artifact.name}"

    def apply_effect(self, effect: ArtifactEffect, artifact: Artifact, game_state: Dict[str, Any]) -> None:
        """Apply an artifact effect"""
        # Simplified effect application
        pass

    def get_active_artifacts(self, player: str) -> List[Artifact]:
        """Get all active artifacts belonging to a player"""
        return list(self.active_artifacts.values())


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    # Demo/test code
    print("=== LOTR TCG Artifact Card System Demo ===\n")

    # Create factory and generate samples
    factory = ArtifactFactory()
    samples = factory.generate_sample_artifacts()

    print(f"Generated {len(samples)} sample artifacts:\n")

    for artifact in samples:
        print(f"  {artifact.artifact_id}: {artifact.name}")
        print(f"    Type: {artifact.artifact_type.value}")
        print(f"    Cost: Burden={artifact.cost.burden}, Twilight={artifact.cost.twilight}")
        print(f"    Stats: {artifact.stats}")
        print(f"    Keywords: {', '.join(artifact.keywords)}")
        print(f"    Description: {artifact.description}")
        print()

    # Demonstrate artifact creation
    print("=== Artifact Creation Demo ===\n")

    # Create a custom artifact
    custom_artifact = Artifact(
        artifact_id="art_custom",
        name="Test Artifact",
        artifact_type=ArtifactType.RELIC,
        cost=ArtifactCost(burden=1, twilight=1),
        effects=[
            ArtifactEffect(
                effect_id="test_1",
                effect_type="add_strength",
                target="equipped_companion",
                value=1,
                duration="permanent"
            )
        ],
        description="A test artifact for demonstration"
    )

    factory.register_artifact(custom_artifact)
    print(f"Created custom artifact: {custom_artifact.name}")
    print(f"  - Has {len(custom_artifact.effects)} effect(s)")
    print(f"  - Durability: {custom_artifact.durability}")

    # Demonstrate damage system
    print("\n=== Damage System Demo ===\n")
    print(f"Before damage: {custom_artifact.current_durability}/{custom_artifact.durability}")
    custom_artifact.take_damage(2)
    print(f"After 2 damage: {custom_artifact.current_durability}/{custom_artifact.durability}")
    custom_artifact.take_damage(3)
    print(f"After 3 more damage: {custom_artifact.current_durability}/{custom_artifact.durability}")
    print(f"Artifact destroyed: {custom_artifact.position == ArtifactPosition.GRAVEYARD}")
