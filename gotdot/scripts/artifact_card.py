"""
=== LOTR TCG: Artifact Card Godot Integration ===

This module provides Godot-specific classes and scripts for artifact cards.
"""

from scripts.artifact_system import (
    Artifact, ArtifactFactory, ArtifactType, ArtifactEffect,
    ArtifactPosition, ArtifactCost
)


class ArtifactCard:
    """
    Godot-specific artifact card wrapper.

    Handles Godot scene loading, sprite display, and game integration.
    """

    def __init__(self, artifact: Artifact, scene_path: str = ""):
        self.artifact = artifact
        self.scene_path = scene_path
        self.godot_node = None
        self.sprite = None
        self.is_equipped = False
        self.is_on_site = False

    def load_scene(self, godot_engine) -> bool:
        """Load the artifact's Godot scene"""
        if not self.scene_path:
            # Default scene path based on artifact ID
            self.scene_path = f"res://scenes/artifacts/{self.artifact.artifact_id}.tscn"

        try:
            scene = godot_engine.load(self.scene_path)
            if scene:
                instance = scene.instantiate()
                return instance
            return None
        except Exception as e:
            print(f"Failed to load artifact scene: {e}")
            return None

    def create_godot_node(self, parent_node, godot_engine) -> bool:
        """Create a Godot node for this artifact"""
        scene = self.load_scene(godot_engine)
        if not scene:
            return False

        node = scene.instantiate()
        parent_node.add_child(node)
        self.godot_node = node

        # Set up sprite if scene has one
        if hasattr(node, "get_node"):
            sprite_node = node.get_node_or_null("Sprite2D")
            if sprite_node:
                self.sprite = sprite_node
                # Set texture from asset path
                texture_path = f"res://assets/cards/{self.artifact.image_path}"
                texture = godot_engine.load(texture_path)
                if texture:
                    sprite_node.texture = texture

        return True

    def equip(self, companion_node):
        """Equip this artifact to a companion"""
        self.is_equipped = True
        self.artifact.position = ArtifactPosition.EQUIPPED

        # In Godot, you might want to:
        # 1. Move the artifact node to the companion's parent
        # 2. Add visual indicator (equipped icon)
        # 3. Apply equipment effects

        if self.godot_node:
            # Add equipped indicator
            equipped_indicator = companion_node.add_child()
            equipped_indicator.name = "EquippedIndicator"
            # Configure indicator appearance

    def unequip(self):
        """Unequip this artifact"""
        self.is_equipped = False
        self.artifact.position = ArtifactPosition.HAND

        if self.godot_node:
            # Remove equipped indicator
            if hasattr(self.godot_node, "get_node"):
                indicator = self.godot_node.get_node_or_null("EquippedIndicator")
                if indicator:
                    indicator.queue_free()

    def place_on_site(self, site_node):
        """Place this artifact on a site"""
        self.is_on_site = True
        self.artifact.position = ArtifactPosition.SITE

        if self.godot_node:
            # Add site indicator
            site_indicator = site_node.add_child()
            site_indicator.name = "SiteArtifactIndicator"

    def destroy(self):
        """Destroy this artifact in Godot"""
        self.artifact.destroy()

        if self.godot_node:
            self.godot_node.queue_free()
            self.godot_node = None

    def take_damage(self, damage: int) -> bool:
        """Handle damage in Godot"""
        if not self.artifact.take_damage(damage):
            self.destroy()
            return False
        return True


class ArtifactCardManager:
    """
    Manages all artifact cards in the game.

    Handles:
    - Card database and lookup
    - Card display and rendering
    - Card interactions (equip, unequip, destroy)
    - Card animations and effects
    """

    def __init__(self, artifact_factory: ArtifactFactory):
        self.factory = artifact_factory
        self.active_cards: dict = {}  # artifact_id -> ArtifactCard
        self.card_database: dict = {}  # artifact_id -> Artifact
        self.selected_card = None
        self.hovered_card = None

    def register_card(self, artifact: Artifact) -> None:
        """Register an artifact card"""
        self.card_database[artifact.artifact_id] = artifact

    def get_card(self, artifact_id: str) -> ArtifactCard:
        """Get an artifact card instance"""
        if artifact_id not in self.card_database:
            return None

        artifact = self.card_database[artifact_id]

        if artifact_id not in self.active_cards:
            # Create new card instance
            card = ArtifactCard(artifact)
            self.active_cards[artifact_id] = card

        return self.active_cards[artifact_id]

    def play_card(self, artifact_id: str, player: str, game_state: dict) -> tuple:
        """
        Play an artifact card.
        Returns (success, message)
        """
        card = self.get_card(artifact_id)
        if not card:
            return False, "Card not found"

        # Check cost
        if game_state.get("twilight", 0) < card.artifact.cost.twilight:
            return False, "Not enough twilight"
        if game_state.get("burden", 0) < card.artifact.cost.burden:
            return False, "Not enough burden"

        # Pay cost
        game_state["twilight"] -= card.artifact.cost.twilight
        game_state["burden"] -= card.artifact.cost.burden

        # Create Godot node
        if card.godot_node is None:
            # Find parent node (usually the hand or board)
            parent_node = game_state.get("parent_node")
            if parent_node:
                card.create_godot_node(parent_node, game_state.get("engine"))

        # Apply effects
        for effect in card.artifact.effects:
            card.apply_effect(effect, game_state)

        return True, f"Played {card.artifact.name}"

    def equip_card(self, artifact_id: str, companion_id: str) -> tuple:
        """Equip an artifact to a companion"""
        card = self.get_card(artifact_id)
        if not card:
            return False, "Card not found"

        if not card.artifact.equipable:
            return False, "Cannot equip this artifact"

        # Unequip any existing artifact
        existing_id = game_state.get("equipped_artifact_id")
        if existing_id:
            existing_card = self.get_card(existing_id)
            if existing_card:
                existing_card.unequip()

        # Equip new artifact
        companion_node = game_state.get("companions", {}).get(companion_id)
        if companion_node:
            card.equip(companion_node)

        return True, f"Equipped {card.artifact.name}"

    def unequip_card(self, artifact_id: str) -> tuple:
        """Unequip an artifact"""
        card = self.get_card(artifact_id)
        if not card:
            return False, "Card not found"

        card.unequip()
        return True, "Unequipped artifact"

    def destroy_card(self, artifact_id: str) -> tuple:
        """Destroy an artifact"""
        card = self.get_card(artifact_id)
        if not card:
            return False, "Card not found"

        card.destroy()
        return True, "Artifact destroyed"

    def get_card_info(self, artifact_id: str) -> dict:
        """Get display information for a card"""
        artifact = self.card_database.get(artifact_id)
        if not artifact:
            return {}

        return {
            "id": artifact.artifact_id,
            "name": artifact.name,
            "type": artifact.artifact_type.value,
            "cost": {
                "burden": artifact.cost.burden,
                "twilight": artifact.cost.twilight
            },
            "stats": artifact.stats,
            "description": artifact.description,
            "image_path": artifact.image_path,
            "rarity": artifact.rarity,
            "durability": artifact.durability
        }


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=== LOTR TCG Artifact Card Godot Integration Demo ===\n")

    # Create factory and manager
    factory = ArtifactFactory()
    manager = ArtifactCardManager(factory)

    # Generate sample artifacts
    samples = factory.generate_sample_artifacts()

    print(f"Registered {len(samples)} artifact cards\n")

    # Demonstrate card operations
    print("=== Card Operations Demo ===\n")

    # Get card info
    card_info = manager.get_card_info("art_001")
    print(f"Card Info for Elendil's Sword:")
    print(f"  Name: {card_info['name']}")
    print(f"  Type: {card_info['type']}")
    print(f"  Cost: {card_info['cost']}")
    print(f"  Description: {card_info['description']}\n")

    # Get card instance
    card = manager.get_card("art_001")
    print(f"Card Instance:")
    print(f"  Artifact ID: {card.artifact.artifact_id}")
    print(f"  Position: {card.artifact.position.value}")
    print(f"  Is Equipped: {card.is_equipped}")
    print(f"  Is on Site: {card.is_on_site}")
