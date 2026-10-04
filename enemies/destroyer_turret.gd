class_name DestroyerTurret
extends DestroyerPart
## Hull turret. Shoots at the player when they're within aggro range. If the
## player isn't, it shoots at a wingman in range instead, so the wingmen look
## like they're in the fight (they can't be hurt). Each turret can only pitch
## between min/max_pitch_deg, so there are blind spots, and the hull or
## asteroids block its line of fire. Destroying it just disables it.

@export var aggro_range := 450.0
## Radians per second for both yaw and pitch.
@export var turn_rate := 1.2
@export var fire_interval := 1.4
@export var bolt_speed := 200.0
@export var spread_deg := 1.5
@export var min_pitch_deg := -5.0
@export var max_pitch_deg := 80.0
## Only fire when the barrels are this close to lined up.
@export var fire_tolerance_deg := 3.0
@export var laser_scene: PackedScene = preload("res://weapons/turret_laser.tscn")

## What it's currently aiming at, if anything.
var current_target: Node3D

var _cooldown := 0.0
var _next_muzzle := 0

@onready var _yaw: Node3D = $Yaw
@onready var _pitch: Node3D = $Yaw/Pitch
@onready var _muzzles: Array[Node3D] = [$Yaw/Pitch/MuzzleL, $Yaw/Pitch/MuzzleR]


func _ready() -> void:
	super()
	_cooldown = randf() * fire_interval  # so turrets don't all fire in unison


func _physics_process(delta: float) -> void:
	current_target = null
	if is_destroyed or destroyer == null or not destroyer.is_vulnerable():
		return
	current_target = _pick_target()
	if current_target == null:
		return

	var aim := _lead_point(current_target)
	# Desired angles in the turret's own frame, measured from the pitch pivot.
	var local := global_transform.affine_inverse() * aim - _yaw.position - _pitch.position
	var want_yaw := atan2(-local.x, -local.z)
	var want_pitch := atan2(local.y, Vector2(local.x, local.z).length())
	var reachable := want_pitch >= deg_to_rad(min_pitch_deg) and want_pitch <= deg_to_rad(max_pitch_deg)
	want_pitch = clampf(want_pitch, deg_to_rad(min_pitch_deg), deg_to_rad(max_pitch_deg))
	_yaw.rotation.y = rotate_toward(_yaw.rotation.y, want_yaw, turn_rate * delta)
	_pitch.rotation.x = rotate_toward(_pitch.rotation.x, want_pitch, turn_rate * delta)

	_cooldown -= delta
	if _cooldown > 0.0 or not reachable:
		return
	var muzzle := _muzzles[_next_muzzle]
	var to_aim := aim - muzzle.global_position
	var barrel_forward := -_pitch.global_basis.z
	if rad_to_deg(barrel_forward.angle_to(to_aim)) > fire_tolerance_deg:
		return
	if not _clear_shot(muzzle.global_position, current_target.global_position):
		return
	_cooldown = fire_interval
	_next_muzzle = (_next_muzzle + 1) % _muzzles.size()
	_fire(muzzle.global_position, to_aim.normalized())


## The player if within aggro range; otherwise the nearest wingman in range.
func _pick_target() -> Node3D:
	var player := get_tree().get_first_node_in_group("player") as Ship
	if player and not player.is_dead \
			and global_position.distance_to(player.global_position) <= aggro_range:
		return player
	var best: Node3D = null
	var best_distance := aggro_range
	for wingman: Node3D in get_tree().get_nodes_in_group("wingmen"):
		var d := global_position.distance_to(wingman.global_position)
		if d <= best_distance:
			best_distance = d
			best = wingman
	return best


func _lead_point(node: Node3D) -> Vector3:
	var pos := node.global_position
	var v = node.get("velocity")
	if not v is Vector3:
		return pos
	return pos + v * (global_position.distance_to(pos) / bolt_speed)


## Nothing solid (hull, asteroids) between the muzzle and the target.
func _clear_shot(from: Vector3, to: Vector3) -> bool:
	var query := PhysicsRayQueryParameters3D.create(from, to, Fighter.LAYER_WORLD)
	return get_world_3d().direct_space_state.intersect_ray(query).is_empty()


func _fire(origin: Vector3, direction: Vector3) -> void:
	var axis := direction.cross(Vector3(randf() - 0.5, randf() - 0.5, randf() - 0.5)).normalized()
	if axis.is_normalized():
		direction = direction.rotated(axis, deg_to_rad(randf() * spread_deg))
	var laser := laser_scene.instantiate() as Laser
	get_tree().current_scene.add_child(laser)
	laser.launch(origin, direction, bolt_speed, self)


func _on_broken() -> void:
	super()
	_pitch.rotation.x = deg_to_rad(-20.0)  # barrels droop
