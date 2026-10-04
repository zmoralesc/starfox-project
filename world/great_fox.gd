class_name GreatFox
extends Node3D
## Scenery: the Star Fox team's mothership, parked just outside a mission's
## play area. Purely decorative: no collision, no AI awareness, not
## shootable. Place it beyond the PlayBoundary's turn-back distance (or far
## outside the action on missions without one) so the player can't fly into it.
##
## The imported model (models/great_fox/) is rotated in great_fox.tscn so that
## this node's -Z is the bow, +Y is up and its origin is the centre of the hull
## (about 464 m long, 310 m wide, 97 m tall). Its materials are swapped for
## cel-shaded copies at load (ToonMaterial), so the editor shows the originals.

## How far it rises and sinks while hovering (metres). 0 = perfectly still.
@export var bob_height := 3.0
## Seconds for one rise-and-sink cycle.
@export var bob_period := 14.0

var _rest := Vector3.ZERO
var _time := 0.0


func _ready() -> void:
	# Cel-shade the imported PBR materials to match the rest of the game.
	ToonMaterial.convert_tree($Model)
	_rest = position


func _process(delta: float) -> void:
	if bob_height <= 0.0 or bob_period <= 0.0:
		return
	_time += delta
	position = _rest + Vector3.UP * sin(_time * TAU / bob_period) * bob_height
