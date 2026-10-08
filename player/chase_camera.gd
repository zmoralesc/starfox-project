class_name ChaseCamera
extends Camera3D
## Third-person chase camera. Trails the ship's orientation with a little lag
## so turns feel weighty, and pulls back / widens FOV above cruise speed.

@export var target: Ship
@export var offset := Vector3(0.0, 2.6, 11.0)
@export var look_ahead := 30.0
## How tightly the camera follows the ship's rotation. Higher = stiffer.
@export var follow_sharpness := 7.0
## Extra distance per unit of speed above cruise.
@export var speed_pullback := 0.05
## FOV at cruise speed and below...
@export var base_fov := 70.0
## ...widening to this at the ship's max_speed (full throttle).
@export var top_speed_fov := 84.0
## On planet missions, the camera stays at least this high above the ground
## (or water), so flying low never puts it underground.
@export var ground_clearance := 3.0

@export_group("Wreck")
## Where the camera sits while following the player's wreck: higher and further
## back than `offset`, looking down on it, so its smoke trail runs out below
## the camera instead of through it.
@export var wreck_offset := Vector3(0.0, 7.0, 18.0)
## Seconds to move from `offset` to `wreck_offset` after the ship is destroyed.
@export var wreck_offset_time := 1.0

var _basis := Basis.IDENTITY
## 0 = at `offset`, 1 = at `wreck_offset` (eased in after death).
var _wreck_blend := 0.0
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
	# Once the ship is destroyed, follow its wreck instead; when that has
	# exploded too, hold still and watch.
	if not target.is_dead or is_instance_valid(target.wreck):
		if _following_wreck():
			_wreck_blend = move_toward(_wreck_blend, 1.0, delta / maxf(wreck_offset_time, 0.01))
		_follow(1.0 - exp(-follow_sharpness * delta))
	var speed_range := maxf(target.max_speed - target.cruise_speed, 1.0)
	var fast := clampf((_followed_speed() - target.cruise_speed) / speed_range, 0.0, 1.0)
	var target_fov := lerpf(base_fov, top_speed_fov, fast)
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
	var ship_basis := _followed_basis()
	var ship_position := _followed_position()
	_basis = _basis.slerp(ship_basis, weight).orthonormalized()
	global_position = ship_position + _basis * _current_offset()
	if _terrain:
		var lowest := _terrain.surface_height(global_position.x, global_position.z) + ground_clearance
		global_position.y = maxf(global_position.y, lowest)
	look_at(ship_position - ship_basis.z * look_ahead, _basis.y)


## The camera offset including the extra pull-back when flying above cruise speed.
func _current_offset() -> Vector3:
	var pullback := maxf(_followed_speed() - target.cruise_speed, 0.0) * speed_pullback
	# Eased both ends, so the camera starts and stops rising smoothly.
	var base := offset.lerp(wreck_offset, smoothstep(0.0, 1.0, _wreck_blend))
	return base + Vector3(0.0, 0.0, pullback)


## What the camera chases: the ship, or after its death its wreck (if any).
## The wreck's flight_basis leaves out its spin, so the camera turns and dives
## with it but doesn't roll.
func _following_wreck() -> bool:
	return target.is_dead and is_instance_valid(target.wreck)


func _followed_position() -> Vector3:
	return target.wreck.global_position if _following_wreck() else target.global_position


func _followed_basis() -> Basis:
	return target.wreck.flight_basis if _following_wreck() else target.global_basis


func _followed_speed() -> float:
	return target.wreck.velocity.length() if _following_wreck() else target.speed
