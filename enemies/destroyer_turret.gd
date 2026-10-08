class_name DestroyerTurret
extends DestroyerPart
## Hull turret. Shoots at the player when they're within aggro range, or much
## farther (Destroyer retaliation_range) after they've shot the ship. If the
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

@export_group("Lock-on")
## A target flying slowly is easy prey: the turret locks on to it over time,
## and the more locked on it is, the faster, straighter and quicker to turn it
## fires (lerping from the values above to the locked_* ones). Flying fast
## breaks the lock. This makes hanging behind the destroyer to spray it a
## high-risk tactic, while strafing runs at speed stay safe-ish.
##
## Target speed (m/s) below which the lock starts building.
@export var lock_speed := 50.0
## At or below this speed, the lock builds at its full rate.
@export var crawl_speed := 25.0
## Seconds at crawl speed from no lock to fully locked.
@export var lock_time := 3.0
## Seconds above lock_speed for a full lock to break completely.
@export var unlock_time := 1.0
@export var locked_fire_interval := 0.15
@export var locked_spread_deg := 0.2
@export var locked_turn_rate := 3.0
## How quickly the turret's estimate of the target's acceleration follows the
## real thing. Locked on, it leads along the target's curving path rather than
## a straight line, so circling slowly doesn't save you.
@export var accel_tracking := 4.0

## What it's currently aiming at, if anything.
var current_target: Node3D
## How locked on to current_target it is, 0 to 1 (see the Lock-on group).
var lock := 0.0

## The target's velocity last frame and its estimated acceleration.
var _target_velocity := Vector3.ZERO
var _target_accel := Vector3.ZERO

var _cooldown := 0.0
var _next_muzzle := 0

@onready var _yaw: Node3D = $Yaw
@onready var _pitch: Node3D = $Yaw/Pitch
@onready var _muzzles: Array[Node3D] = [$Yaw/Pitch/MuzzleL, $Yaw/Pitch/MuzzleR]


func _ready() -> void:
	super()
	_cooldown = randf() * fire_interval  # so turrets don't all fire in unison


func _physics_process(delta: float) -> void:
	var previous := current_target
	current_target = null
	if is_destroyed or destroyer == null or not destroyer.is_damageable():
		lock = 0.0
		return
	current_target = _pick_target()
	if current_target != previous:
		lock = 0.0
		_target_accel = Vector3.ZERO
		_target_velocity = _velocity_of(current_target) if current_target else Vector3.ZERO
	if current_target == null:
		return
	_update_lock(delta)

	var aim := _lead_point(current_target)
	# Desired angles in the turret's own frame, measured from the pitch pivot.
	var local := global_transform.affine_inverse() * aim - _yaw.position - _pitch.position
	var want_yaw := atan2(-local.x, -local.z)
	var want_pitch := atan2(local.y, Vector2(local.x, local.z).length())
	var reachable := want_pitch >= deg_to_rad(min_pitch_deg) and want_pitch <= deg_to_rad(max_pitch_deg)
	want_pitch = clampf(want_pitch, deg_to_rad(min_pitch_deg), deg_to_rad(max_pitch_deg))
	var turn := lerpf(turn_rate, locked_turn_rate, lock) * delta
	_yaw.rotation.y = rotate_toward(_yaw.rotation.y, want_yaw, turn)
	_pitch.rotation.x = rotate_toward(_pitch.rotation.x, want_pitch, turn)

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
	_cooldown = lerpf(fire_interval, locked_fire_interval, lock)
	_next_muzzle = (_next_muzzle + 1) % _muzzles.size()
	_fire(muzzle.global_position, to_aim.normalized())


## Builds the lock on a slow current_target, breaks it on a fast one, and
## tracks the target's acceleration for the curved lead.
func _update_lock(delta: float) -> void:
	var v := _velocity_of(current_target)
	var accel := (v - _target_velocity) / maxf(delta, 0.0001)
	_target_accel = _target_accel.lerp(accel, 1.0 - exp(-accel_tracking * delta))
	_target_velocity = v
	var target_speed := v.length()
	if target_speed >= lock_speed:
		lock = move_toward(lock, 0.0, delta / maxf(unlock_time, 0.01))
		return
	var slowness := clampf(inverse_lerp(lock_speed, crawl_speed, target_speed), 0.0, 1.0)
	lock = move_toward(lock, 1.0, slowness * delta / maxf(lock_time, 0.01))


## The player if within range; otherwise the nearest wingman in range. The
## range is aggro_range, or the destroyer's retaliation_range for whoever has
## shot it lately (Destroyer.reach_for).
func _pick_target() -> Node3D:
	var player := get_tree().get_first_node_in_group("player") as Ship
	if player and not player.is_dead \
			and global_position.distance_to(player.global_position) <= destroyer.reach_for(player, aggro_range):
		return player
	var best: Node3D = null
	var best_distance := INF
	for wingman: Node3D in get_tree().get_nodes_in_group("wingmen"):
		var d := global_position.distance_to(wingman.global_position)
		if d <= destroyer.reach_for(wingman, aggro_range) and d < best_distance:
			best_distance = d
			best = wingman
	return best


## Where to aim so a bolt meets `node`: straight-line lead, bending along the
## target's curving path as the lock builds.
func _lead_point(node: Node3D) -> Vector3:
	var pos := node.global_position
	var t := global_position.distance_to(pos) / bolt_speed
	return pos + _velocity_of(node) * t + _target_accel * (0.5 * t * t * lock)


static func _velocity_of(node: Node3D) -> Vector3:
	var v = node.get("velocity")
	return v if v is Vector3 else Vector3.ZERO


## Nothing solid (hull, asteroids) between the muzzle and the target.
func _clear_shot(from: Vector3, to: Vector3) -> bool:
	var query := PhysicsRayQueryParameters3D.create(from, to, Fighter.LAYER_WORLD)
	return get_world_3d().direct_space_state.intersect_ray(query).is_empty()


func _fire(origin: Vector3, direction: Vector3) -> void:
	var axis := direction.cross(Vector3(randf() - 0.5, randf() - 0.5, randf() - 0.5)).normalized()
	if axis.is_normalized():
		direction = direction.rotated(axis, deg_to_rad(randf() * lerpf(spread_deg, locked_spread_deg, lock)))
	var laser := laser_scene.instantiate() as Laser
	get_tree().current_scene.add_child(laser)
	laser.launch(origin, direction, bolt_speed, self)


func _on_broken() -> void:
	super()
	_pitch.rotation.x = deg_to_rad(-20.0)  # barrels droop
