"""
=== LOTR TCG: Artifact Card Scenes ===

This module contains Godot scene definitions for artifact cards.
Each artifact has its own scene file with unique appearance and effects.
"""

# Scene structure for each artifact card:
#
# ArtifactCard.tscn
# ├── Sprite2D (main card display)
# │   ├── CardBorder (visual border based on rarity)
# │   ├── CardBack (reverse side)
# │   └── CardOverlay (rarity glow, equipped indicator)
# ├── Label (card name)
# ├── Label (card description)
# ├── Label (cost display)
# ├── Label (stats display)
# ├── TextureRect (card image)
# ├── PanelContainer (effects display)
# │   └── Label (active effects)
# └── AnimationPlayer (card animations)

ARTIFACT_SCENES = {
    "art_001": {
        "name": "Elendil's Sword",
        "type": "weapon",
        "rarity": "legendary",
        "scene_path": "res://scenes/artifacts/ElendilsSword.tscn",
        "image_path": "cards/ElendilsSword.png",
        "border_color": "#FFD700",  # Gold for legendary
        "effects": [
            "While equipped: +3 Strength",
            "Fierce: Cannot be targeted by skirmishes"
        ]
    },
    "art_002": {
        "name": "Shield of Gondor",
        "type": "armor",
        "rarity": "rare",
        "scene_path": "res://scenes/artifacts/ShieldOfGondor.tscn",
        "image_path": "cards/ShieldOfGondor.png",
        "border_color": "#C0C0C0",  # Silver for rare
        "effects": [
            "While equipped: +2 Resistance",
            "Overwhelm: Can target companions"
        ]
    },
    "art_003": {
        "name": "Palantír of Orthanc",
        "type": "relic",
        "rarity": "epic",
        "scene_path": "res://scenes/artifacts/PalantirOfOrthanc.tscn",
        "image_path": "cards/PalantirOfOrthanc.png",
        "border_color": "#8B4513",  # Brown for epic
        "effects": [
            "While in play: Draw 1 card during Regroup",
            "Requires 2 Burden and 2 Twilight to play"
        ]
    },
    "art_004": {
        "name": "One Ring",
        "type": "curse",
        "rarity": "unique",
        "scene_path": "res://scenes/artifacts/OneRing.tscn",
        "image_path": "cards/OneRing.png",
        "border_color": "#000000",  # Black for unique
        "effects": [
            "While equipped: +2 Strength, -1 Vitality",
            "Cannot be destroyed by normal means"
        ]
    },
    "art_005": {
        "name": "Isildur's Crown",
        "type": "treasure",
        "rarity": "rare",
        "scene_path": "res://scenes/artifacts/IsildursCrown.tscn",
        "image_path": "cards/IsildursCrown.png",
        "border_color": "#C0C0C0",  # Silver for rare
        "effects": [
            "While in play: Generate 1 twilight during Archery",
            "Requires 1 Burden to play"
        ]
    },
    "art_006": {
        "name": "Mount Doom",
        "type": "enchantment",
        "rarity": "legendary",
        "scene_path": "res://scenes/artifacts/MountDoom.tscn",
        "image_path": "cards/MountDoom.png",
        "border_color": "#FFD700",  # Gold for legendary
        "effects": [
            "Site effect: +5 Resistance, -2 Vitality",
            "Requires 3 Burden and 3 Twilight to play"
        ]
    }
}


def get_artifact_scene(artifact_id: str) -> dict:
    """Get scene configuration for an artifact"""
    return ARTIFACT_SCENES.get(artifact_id, {})


def create_artifact_scene(artifact_id: str, parent_node) -> bool:
    """
    Create a Godot scene for an artifact card.

    Returns True if scene was created successfully.
    """
    scene_config = get_artifact_scene(artifact_id)
    if not scene_config:
        print(f"No scene configuration found for artifact {artifact_id}")
        return False

    # In Godot, this would be:
    # scene = load(scene_config["scene_path"])
    # node = scene.instantiate()
    # parent_node.add_child(node)

    print(f"Creating scene for {scene_config['name']}")
    print(f"  Scene: {scene_config['scene_path']}")
    print(f"  Image: {scene_config['image_path']}")
    print(f"  Rarity: {scene_config['rarity']}")
    print(f"  Effects: {scene_config['effects']}")

    return True


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=== LOTR TCG Artifact Card Scenes Demo ===\n")

    # Display all artifact scenes
    for artifact_id, config in ARTIFACT_SCENES.items():
        print(f"Artifact: {config['name']}")
        print(f"  ID: {artifact_id}")
        print(f"  Type: {config['type']}")
        print(f"  Rarity: {config['rarity']}")
        print(f"  Scene: {config['scene_path']}")
        print(f"  Effects: {', '.join(config['effects'])}")
        print()

    # Demonstrate scene creation
    print("=== Scene Creation Demo ===\n")
    create_artifact_scene("art_001", None)
    create_artifact_scene("art_004", None)
