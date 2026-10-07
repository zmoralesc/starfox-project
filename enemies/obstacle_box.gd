@tool
class_name ObstacleBox
extends Node3D
## An invisible box the AI steers around, for large blocky shapes (a capital
## ship's hull) that spheres (ObstacleProxy) fit badly: a few boxes hug a hull
## that would take hundreds of spheres. Centred on this node, aligned with its
## axes (so it turns with its parent). AIPilot keeps `margin` + its own
## avoid_margin from the faces, where a sphere gets radius * 1.3 + avoid_margin
## from its centre.
##
## Place them as children of what they cover (the Juggernaut has an
## `AvoidanceBoxes` node full of them). In the editor each one is drawn as a
## see-through cyan box (in the game it's invisible). Resize it with `size` or
## the scale gizmo (both count); rotate it freely.

const PREVIEW_COLOR := Color(0.2, 0.8, 1.0, 0.15)

## Full size (m) along this node's x, y and z, before the node's scale.
@export var size := Vector3(10.0, 10.0, 10.0):
	set(value):
		size = value
		_update_preview()
## Clearance (m) the AI keeps from the faces, on top of its avoid_margin.
@export var margin := 10.0

## Radius of a sphere round the box (half its diagonal), for code that only
## knows spheres (Fighter.radius_of) and for quick distance checks.
var radius: float:
	get:
		return _half_extents().length()

var _preview: MeshInstance3D


func _ready() -> void:
	if Engine.is_editor_hint():
		_make_preview()
		return
	add_to_group("obstacles")


## How far along a straight path from `from` (world) in `direction` (unit) the
## path enters this box grown by `grow` on every side, if it does within
## `length`; INF if it doesn't. 0 if `from` is already inside.
func entry_distance(from: Vector3, direction: Vector3, length: float, grow: float) -> float:
	var inverse := _frame().affine_inverse()
	var origin := inverse * from
	var dir := inverse.basis * direction
	var half := _half_extents() + Vector3.ONE * grow
	var near := 0.0
	var far := length
	for axis in 3:
		if absf(dir[axis]) < 0.000001:
			if absf(origin[axis]) > half[axis]:
				return INF
			continue
		var t1 := (-half[axis] - origin[axis]) / dir[axis]
		var t2 := (half[axis] - origin[axis]) / dir[axis]
		near = maxf(near, minf(t1, t2))
		far = minf(far, maxf(t1, t2))
		if near > far:
			return INF
	return near


## True if `point` (world) is inside this box grown by `grow`.
func contains(point: Vector3, grow: float) -> bool:
	var local := _frame().affine_inverse() * point
	var half := _half_extents() + Vector3.ONE * grow
	return absf(local.x) <= half.x and absf(local.y) <= half.y and absf(local.z) <= half.z


## The shortest move (world vector) that takes `point` out of this box grown by
## `grow`, straight out through one of its faces. Faces whose outward
## direction is within ~45 degrees of `across` (if given) are skipped: going
## round an obstacle in our path means leaving it sideways, not straight ahead
## or back. Zero if the point is already outside.
func way_out(point: Vector3, grow: float, across := Vector3.ZERO) -> Vector3:
	if not contains(point, grow):
		return Vector3.ZERO
	var frame := _frame()
	var local := frame.affine_inverse() * point
	var half := _half_extents() + Vector3.ONE * grow
	var best := INF
	var best_move := Vector3.ZERO
	for axis in 3:
		var outward := frame.basis[axis]
		if absf(outward.dot(across)) > 0.7:
			continue
		for side: float in [1.0, -1.0]:
			var distance := half[axis] - side * local[axis]
			if distance < best:
				best = distance
				best_move = outward * side * distance
	return best_move


## The box's world frame without scale (scale goes into _half_extents()), so
## distances in it are metres.
func _frame() -> Transform3D:
	return Transform3D(global_basis.orthonormalized(), global_position)


## Half the box's size in metres along each of its axes, scale included.
func _half_extents() -> Vector3:
	return (size * global_basis.get_scale()).abs() * 0.5


func _make_preview() -> void:
	var material := StandardMaterial3D.new()
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	material.albedo_color = PREVIEW_COLOR
	_preview = MeshInstance3D.new()
	_preview.mesh = BoxMesh.new()
	_preview.material_override = material
	_preview.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	# Internal: not saved with the scene, not shown in the scene tree.
	add_child(_preview, false, Node.INTERNAL_MODE_FRONT)
	_update_preview()


func _update_preview() -> void:
	if _preview:
		(_preview.mesh as BoxMesh).size = size
