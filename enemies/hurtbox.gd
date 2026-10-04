class_name Hurtbox
extends Area3D
## A larger, invisible target around an enemy, so it's easier to hit without
## being easier to crash into: the ship's own collision shape stays the size of
## its model. Only friendly bolts and the player's crosshair ray see it (layer
## Fighter.LAYER_HURTBOX, queried with collide_with_areas).
##
## Shots that hit it go to `target` (the parent) as if they'd hit the ship
## itself; use Hurtbox.resolve() on a raycast's collider to get that.

## What gets hit. Set to the parent when the hurtbox enters the tree.
var target: Node


func _ready() -> void:
	collision_layer = Fighter.LAYER_HURTBOX
	collision_mask = 0
	monitoring = false  # nothing needs overlap events, only raycasts
	target = get_parent()


## The node a raycast really hit: a hurtbox's target, or the collider itself.
static func resolve(collider: Object) -> Object:
	return (collider as Hurtbox).target if collider is Hurtbox else collider
