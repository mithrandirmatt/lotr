extends Control

## Main entry point for the LotR TCG game.
##
## Architecture (2.5D):
##   SubViewportContainer/SubViewport/World3D  -- 3D background rendered via Forward+
##   CanvasLayer                               -- 2D sprites, cards, and UI drawn on top
##
## This hello-world scene spins a gold placeholder cube in the 3D world.
## Replace the cube with actual 3D environment assets (terrain, table, etc.)
## and add Sprite2D / AnimatedSprite2D nodes under CanvasLayer for card artwork.

@onready var _cube: MeshInstance3D = $SubViewportContainer/SubViewport/World3D/Cube


func _process(delta: float) -> void:
	_cube.rotate_y(delta * 1.2)
