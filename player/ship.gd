class_name Ship
extends Fighter
## The player's ship: mouse / gamepad input on top of the shared Fighter model.

signal died
signal shields_depleted
signal shields_online
signal thrusters_overheated
signal thrusters_cooled

## How far ahead (metres) the automatic turn back aims (see _update_turn_back).
const TURN_BACK_GOAL_DISTANCE := 150.0

@export_group("Controls")
@export var stick_deadzone := 0.06
@export var mouse_sensitivity := 0.0025
## How fast the mouse stick drifts back to center (0 = never).
@export var mouse_recenter := 0.0
@export var invert_y := false

@export_group("Targeting")
## How far ahead we look for something to aim at.
@export var aim_range := 700.0
## Seconds the wingmen keep engaging your last target after you stop firing.
@export var target_memory := 1.5

@export_group("Shields")
## Shields stop every shot while they have at least 1 point left. With the
## shields knocked out, the next hit destroys the ship.
@export var max_shields := 100.0
## Seconds without being hit before damaged shields start recharging.
@export var shield_regen_delay := 3.0
@export var shield_regen_rate := 10.0
## When knocked out completely, shields stay offline this long before
## they come back online and start recharging from zero.
@export var shield_reboot_time := 12.0
## Seconds the HUD's hit-direction marker takes to fade after a shot hits you.
@export var shot_flash_time := 0.8

@export_group("Thrusters")
## Throttling up or down heats the thrusters, in proportion to how far the
## throttle is pushed. At full heat they overheat: the throttle stops working
## (the ship eases back to cruise speed) until they've cooled right down.
##
## Seconds of full throttle (up or down) from cold to overheated.
@export var heat_time := 5.2
## Seconds to cool from full heat to cold while the throttle is released.
@export var cool_time := 3.0
## After overheating, seconds before the throttle works again (the heat drains
## to zero meanwhile).
@export var overheat_time := 3.0

@export_group("Boundary")
## Flying too far past the mission's PlayBoundary, the ship turns itself back
## towards the middle of the area. It hands control back once heading within
## this many degrees of the way back.
@export var turn_back_done_deg := 25.0
## How hard the automatic turn pulls the stick (like AIPilot.steer_gain).
@export var turn_back_steer_gain := 2.5
## While turning back over a planet, climb to at least this high above the
## ground ahead (the boundary usually sits on a mountain range).
@export var turn_back_clearance := 60.0

@export_group("Crash")
## Shield damage from flying into something (at most once per crash_cooldown).
@export var crash_damage := 30
## Seconds after a crash before another one can do damage.
@export var crash_cooldown := 0.5
## Which way the ship bounces off: 0 = skims along the surface, 1 = straight
## out from it. In between is a glancing deflection.
@export_range(0.0, 1.0) var crash_deflect := 0.5
## How quickly the nose swings round to the bounce direction (per second;
## higher = snappier). The turn is smooth, never a jump.
@export var crash_turn_sharpness := 5.0
## Seconds after a crash during which the ship steers itself away and the
## player's steering is ignored.
@export var crash_recover_time := 0.6
## Speed away from the surface right after the crash (m/s, on top of cancelling
## any speed into it), fading out at crash_push_fade per second.
@export var crash_push_speed := 10.0
@export var crash_push_fade := 4.0
## Random spin rate (rad/s) added at the crash, for a little tumble.
@export var crash_wobble := 1.0
## Camera shake at the crash (0..1).
@export_range(0.0, 1.0) var crash_shake := 0.6

## When false the player has no control: the ship flies straight ahead at
## autopilot_speed (used by the intro cutscene).
var controls_enabled := true
var autopilot_speed := 0.0
var shields := 0.0
## True while knocked out and rebooting. Any hit is fatal meanwhile.
var shields_down := false
var is_dead := false
## 1 right after the shields absorb a hit, fading to 0. Read by the HUD.
var damage_flash := 0.0
## 1 right after a shot hits you, fading to 0 over shot_flash_time; with
## last_shot_from (where it was fired from), the HUD shows which way it came.
var shot_flash := 0.0
var last_shot_from := Vector3.ZERO
## Virtual stick, each axis in -1..1. Read by the HUD.
var stick := Vector2.ZERO
## Shootable thing under the crosshair, if any.
var aim_target: Node3D
## Whether the crosshair should show red: there's a target under it and its
## highlight_on_crosshair allows it (Fighter.highlights_crosshair; off for asteroids).
var aim_on_target := false
var is_firing := false
## What you've been shooting at recently. Wingmen in formation engage it.
var fire_target: Node3D
## True while the ship is turning itself back into the play area (see
## PlayBoundary). The player has no steering meanwhile. Read by the HUD.
var turning_back := false
## Thruster temperature, 0 (cold) to 1 (overheating). Read by the HUD.
var thruster_heat := 0.0
## True from overheating until the thrusters have cooled down; the throttle is
## ignored meanwhile. Read by the HUD.
var overheated := false

var _pad_active := false
## Throttle in use this tick (-1..1): the input, or 0 while overheated.
var _throttle := 0.0
var _fire_target_timer := 0.0
var _since_crash := 0.0
## Crash recovery: seconds left steering away, the heading to swing to, and
## the fading push away from the surface.
var _crash_time_left := 0.0
var _crash_heading := Vector3.ZERO
var _crash_push := Vector3.ZERO
var _since_hit := 0.0
var _boundary: PlayBoundary
var _auto_stick := Vector2.ZERO
var _terrain: Terrain

@onready var _shield_fx: ShieldEffect = $Model/Shield


func _ready() -> void:
	super()
	add_to_group("player")
	shields = max_shields
	_boundary = get_tree().get_first_node_in_group("boundary") as PlayBoundary
	_terrain = get_tree().get_first_node_in_group("terrain") as Terrain


## Called by a laser that hits us, with the point it was fired from, just
## before take_hit(). Lets the HUD show which way the shot came from.
func notify_shot(from: Vector3) -> void:
	if is_dead:
		return
	last_shot_from = from
	shot_flash = 1.0


## Called by a laser we fired when it destroys `victim`. Enemy fighters get a
## chance of a compliment from a wingman (WingCommand.praise_player_kill).
func notify_kill(victim: Node) -> void:
	if victim is EnemyFighter:
		get_tree().call_group("wing_command", "praise_player_kill")


func take_hit(damage: int, at: Vector3) -> void:
	if is_dead:
		return
	_since_hit = 0.0
	if shields_down or shields < 1.0:
		_die()
		return
	# Shields stop the shot, whatever its damage.
	shields = maxf(shields - damage, 0.0)
	damage_flash = 1.0
	_shield_fx.flash(at)
	if shields < 1.0:
		shields = 0.0
		shields_down = true
		_shield_fx.collapse()
		shields_depleted.emit()


## 0..1 progress of the shield reboot while shields_down. Read by the HUD.
func shield_reboot_progress() -> float:
	return clampf(_since_hit / shield_reboot_time, 0.0, 1.0)


func _update_shields(delta: float) -> void:
	_since_hit += delta
	damage_flash = move_toward(damage_flash, 0.0, delta * 2.0)
	shot_flash = move_toward(shot_flash, 0.0, delta / maxf(shot_flash_time, 0.01))
	if shields_down:
		if _since_hit >= shield_reboot_time:
			shields_down = false
			_shield_fx.shimmer()
			shields_online.emit()
		return
	if _since_hit >= shield_regen_delay:
		shields = minf(shields + shield_regen_rate * delta, max_shields)


func _die() -> void:
	is_dead = true
	shields = 0.0
	is_firing = false
	fire_target = null
	velocity = Vector3.ZERO
	Impact.spawn(get_parent(), global_position, Color(1.0, 0.6, 0.25), 6.0)
	SoundFX.play_at(get_parent(), explosion_sound, global_position)
	# The ship stays in the scene (hidden), so its engine would keep humming.
	if _engine_sound:
		_engine_sound.stop()
	_model.hide()
	collision_layer = 0
	set_physics_process(false)
	died.emit()


func _unhandled_input(event: InputEvent) -> void:
	if not controls_enabled:
		return
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		stick = (stick + event.relative * mouse_sensitivity).limit_length(1.0)
		_pad_active = false


func _think(delta: float) -> void:
	_since_crash += delta
	_update_shields(delta)
	_update_thrusters(delta)
	if not controls_enabled:
		stick = Vector2.ZERO
		_pad_active = false
		is_firing = false
		return
	var pad := Input.get_vector("steer_left", "steer_right", "steer_up", "steer_down")
	if pad != Vector2.ZERO:
		stick = pad
		_pad_active = true
	elif _pad_active:
		stick = Vector2.ZERO
		_pad_active = false
	else:
		stick = stick.move_toward(Vector2.ZERO, mouse_recenter * delta)
	is_firing = Input.is_action_pressed("fire")
	_update_turn_back()


## Past the boundary's turn-back line, steer back towards the middle of the
## play area at the current altitude until heading roughly that way.
func _update_turn_back() -> void:
	if _boundary == null:
		return
	if not turning_back and _boundary.should_turn_back(global_position):
		turning_back = true
	if not turning_back:
		return
	var to_home := _boundary.global_position - global_position
	var forward := -global_basis.z
	var heading_error := Vector2(forward.x, forward.z).angle_to(Vector2(to_home.x, to_home.z))
	if absf(heading_error) < deg_to_rad(turn_back_done_deg):
		turning_back = false
		# Drop whatever the mouse did meanwhile, so we don't swing straight back out.
		stick = Vector2.ZERO
		return
	# Head level for a point a little way towards the middle, or climb if
	# the ground under us or ahead is too close.
	var flat := Vector3(to_home.x, 0.0, to_home.z).normalized()
	var goal := global_position + flat * TURN_BACK_GOAL_DISTANCE
	var local := global_basis.inverse() * (goal - global_position).normalized()
	if _terrain:
		var ahead := global_position + forward * TURN_BACK_GOAL_DISTANCE * 0.5
		var ground := maxf(_terrain.clearance_height(global_position.x, global_position.z),
			maxf(_terrain.clearance_height(goal.x, goal.z), _terrain.clearance_height(ahead.x, ahead.z)))
		if global_position.y < ground + turn_back_clearance:
			# Ground close: pull up hard while still turning. A flat turn could
			# carry us into the slope we were flying at.
			_auto_stick = Vector2(signf(local.x) if absf(local.x) > 0.01 else 1.0, -1.0).normalized()
			return
	_auto_stick = Vector2(local.x, -local.y)
	if local.z > 0.0:
		# Facing away: turn as hard as possible.
		_auto_stick = _auto_stick.normalized() if _auto_stick.length() > 0.01 else Vector2.RIGHT
	else:
		_auto_stick = (_auto_stick * turn_back_steer_gain).limit_length(1.0)


func _get_stick() -> Vector2:
	if _crash_time_left > 0.0:
		return Vector2.ZERO  # _update_rotation() steers away from the surface
	if turning_back:
		return _auto_stick
	var s := stick if stick.length() > stick_deadzone else Vector2.ZERO
	return Vector2(s.x, -s.y) if invert_y else s


func _get_roll() -> float:
	if not controls_enabled or turning_back or _crash_time_left > 0.0:
		return 0.0
	return Input.get_axis("roll_right", "roll_left")


func _get_target_speed() -> float:
	if not controls_enabled:
		return autopilot_speed
	if _throttle > 0.0:
		return lerpf(cruise_speed, max_speed, _throttle)
	return lerpf(cruise_speed, min_speed, -_throttle)


## Reads the throttle and heats or cools the thrusters (see the Thrusters
## group). Overheated, the throttle is ignored while the heat drains away
## over overheat_time; then it works again.
func _update_thrusters(delta: float) -> void:
	if overheated:
		_throttle = 0.0
		thruster_heat = move_toward(thruster_heat, 0.0, delta / maxf(overheat_time, 0.01))
		if thruster_heat <= 0.0:
			overheated = false
			thrusters_cooled.emit()
		return
	_throttle = Input.get_axis("throttle_down", "throttle_up") if controls_enabled else 0.0
	if _throttle == 0.0:
		thruster_heat = move_toward(thruster_heat, 0.0, delta / maxf(cool_time, 0.01))
		return
	thruster_heat = minf(thruster_heat + absf(_throttle) * delta / maxf(heat_time, 0.01), 1.0)
	if thruster_heat >= 1.0:
		overheated = true
		_throttle = 0.0
		thrusters_overheated.emit()


func _wants_fire() -> bool:
	return is_firing


func _aim(delta: float) -> void:
	var forward := -global_basis.z
	var from := global_position + forward * 4.0
	var query := PhysicsRayQueryParameters3D.create(from, from + forward * aim_range,
		LAYER_WORLD | LAYER_ENEMY | LAYER_HURTBOX)
	query.collide_with_areas = true  # enemy hurtboxes, same as friendly bolts
	var hit := get_world_3d().direct_space_state.intersect_ray(query)
	aim_target = null
	if hit.is_empty():
		aim_point = global_position + forward * aim_distance
	else:
		aim_point = hit.position
		var collider: Object = Hurtbox.resolve(hit.collider)
		# Destroyed destroyer parts still stop shots but aren't targets any more.
		if collider.has_method("take_hit") and not collider.get("is_destroyed"):
			aim_target = collider
	aim_on_target = aim_target != null and Fighter.highlights_crosshair(aim_target)

	if is_firing and aim_target:
		fire_target = aim_target
		_fire_target_timer = target_memory
	else:
		_fire_target_timer -= delta
		if _fire_target_timer <= 0.0 or not is_instance_valid(fire_target):
			fire_target = null


## Flying into something: damage (with a cooldown) and a bounce that plays out
## over crash_recover_time instead of in one frame. The nose swings smoothly
## to a glancing deflection off the surface (_update_rotation), a fading push
## carries the ship clear (_velocity_offset), and it slows to min_speed and
## accelerates back as usual.
func _handle_collisions() -> void:
	if get_slide_collision_count() == 0:
		return
	var collision := get_slide_collision(0)
	var normal := collision.get_normal()
	speed = minf(speed, min_speed)
	# A small nudge out, like Fighter's, so we never stick in the surface.
	global_position += normal * 0.5

	var collider := collision.get_collider() as Node
	if collider == null or _since_crash < crash_cooldown or _crash_time_left > 0.0:
		return
	_since_crash = 0.0
	take_hit(crash_damage, collision.get_position())

	var forward := -global_basis.z
	var along := forward.slide(normal)
	if along.length_squared() < 0.01:
		# Head-on: skim off towards the ship's own "up" along the surface.
		along = global_basis.y.slide(normal)
	var heading := along.normalized().lerp(normal, crash_deflect)
	heading += Vector3(randf_range(-1, 1), randf_range(-1, 1), randf_range(-1, 1)) * 0.1
	_crash_heading = heading.normalized()
	_crash_time_left = crash_recover_time
	# Cancel whatever speed we still have into the surface, then push off.
	var into := maxf(-forward.dot(normal), 0.0) * speed
	_crash_push = normal * (into + crash_push_speed)
	_rates += Vector3(randf_range(-1, 1), randf_range(-1, 1), randf_range(-1, 1)) * crash_wobble

	var cam := get_viewport().get_camera_3d()
	if cam and cam.has_method("add_shake"):
		cam.add_shake(crash_shake)


## After a crash, swing the nose towards the bounce direction (smoothly, on top
## of the stick-driven turn, which is idle meanwhile) and fade the push.
func _update_rotation(delta: float) -> void:
	super(delta)
	_crash_push *= exp(-crash_push_fade * delta)
	if _crash_time_left <= 0.0:
		return
	_crash_time_left -= delta
	var up := Vector3.UP if absf(_crash_heading.dot(Vector3.UP)) < 0.95 else global_basis.y
	var target := Basis.looking_at(_crash_heading, up).get_rotation_quaternion()
	var weight := 1.0 - exp(-crash_turn_sharpness * delta)
	global_basis = Basis(global_basis.get_rotation_quaternion().slerp(target, weight)).orthonormalized()


func _velocity_offset() -> Vector3:
	return _crash_push
