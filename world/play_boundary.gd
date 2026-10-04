class_name PlayBoundary
extends Node3D
## Edge of a mission's play area: a vertical cylinder around this node (only
## horizontal distance counts). Past `radius` the HUD warns the player; past
## `radius + turn_back_margin` the ship turns itself around and flies back in,
## like Star Fox's all-range mode. Enemy patrols and waves stay inside it.
##
## Optional: a mission without one has no edge. Both current missions have one.

## Horizontal distance from this node where the play area ends.
@export var radius := 1450.0
## How far past the edge the player may fly before the ship turns back by
## itself. Negative = never take control (warning only).
@export var turn_back_margin := 200.0


func _enter_tree() -> void:
	add_to_group("boundary")


## How far `point` is outside the play area horizontally (negative = inside).
func distance_outside(point: Vector3) -> float:
	var offset := point - global_position
	return Vector2(offset.x, offset.z).length() - radius


## `point` moved horizontally so it lies at least `margin` inside the edge.
func clamp_inside(point: Vector3, margin := 0.0) -> Vector3:
	var offset := point - global_position
	var flat := Vector2(offset.x, offset.z)
	var limit := maxf(radius - margin, 0.0)
	if flat.length() <= limit:
		return point
	flat = flat.normalized() * limit
	return Vector3(global_position.x + flat.x, point.y, global_position.z + flat.y)


## Whether a ship at `point` has gone far enough out to be turned back.
func should_turn_back(point: Vector3) -> bool:
	return turn_back_margin >= 0.0 and distance_outside(point) > turn_back_margin
