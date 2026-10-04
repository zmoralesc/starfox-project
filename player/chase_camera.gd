class_name ChaseCamera
extends Camera3D
## Third-person chase camera. Trails the ship's orientation with a little lag
## so turns feel weighty, and pulls back / widens FOV while boosting.

@export var target: Ship
@export var offset := Vector3(0.0, 2.6, 11.0)
@export var look_ahead := 30.0
## How tightly the camera follows the ship's rotation. Higher = stiffer.
@export var follow_sharpness := 7.0
## Extra distance per unit of speed above cruise.
@export var boost_pullback := 0.05
@export var base_fov := 70.0
@export var boost_fov := 84.0
## On planet missions, the camera stays at least this high above the ground
## (or water), so flying low never puts it underground.
@export var ground_clearance := 3.0

var _basis := Basis.IDENTITY
var _shake := 0.0
## The mission's Terrain, if it has one (found through the "terrain" group).
var _terrain: Terrain


func add_shake(amount: float) -> void:
	_shake = clampf(_shake + amount, 0.0, 1.0)


func _ready() -> void:
	# Run after the ship has moved this physics frame.
	process_physics_priority = 10
	_terrain = get_tree().get_first_node_in_group("terrain") as Terrain
	fov = base_fov
	if target:
		_basis = target.global_basis
		_follow(1.0)


func _physics_process(delta: float) -> void:
	if target == null:
		return
	_follow(1.0 - exp(-follow_sharpness * delta))
	var target_fov := boost_fov if target.boosting else base_fov
	fov = lerpf(fov, target_fov, 1.0 - exp(-4.0 * delta))
	
	if _shake > 0.0:
		var intensity := _shake * _shake * 1.5
		h_offset = randf_range(-intensity, intensity)
		v_offset = randf_range(-intensity, intensity)
		_shake = move_toward(_shake, 0.0, delta * 2.0)
	else:
		h_offset = 0.0
		v_offset = 0.0


## Where the camera would be with no lag: directly in its spot behind the ship.
func chase_transform() -> Transform3D:
	var ship_basis := target.global_basis
	var pos := target.global_position + ship_basis * _current_offset()
	var look := target.global_position - ship_basis.z * look_ahead
	return Transform3D(Basis.looking_at(look - pos, ship_basis.y), pos)


## Jump straight to the chase position, dropping any accumulated lag.
func snap() -> void:
	_basis = target.global_basis
	_follow(1.0)


func _follow(weight: float) -> void:
	var ship_basis := target.global_basis
	_basis = _basis.slerp(ship_basis, weight).orthonormalized()
	global_position = target.global_position + _basis * _current_offset()
	if _terrain:
		var lowest := _terrain.surface_height(global_position.x, global_position.z) + ground_clearance
		global_position.y = maxf(global_position.y, lowest)
	look_at(target.global_position - ship_basis.z * look_ahead, _basis.y)


## The camera offset including the extra pull-back when flying above cruise speed.
func _current_offset() -> Vector3:
	var pullback := maxf(target.speed - target.cruise_speed, 0.0) * boost_pullback
	return offset + Vector3(0.0, 0.0, pullback)
