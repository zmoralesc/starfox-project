class_name Fighter
extends CharacterBody3D
## Shared flight model and guns for the player and AI ships.
##
## The ship always flies forward. A virtual stick sets pitch/yaw rates, the
## model banks into turns, and the ship rolls itself level when not rolling
## manually. Subclasses are the "pilot": they override the _get_* / _wants_*
## methods, plus _think() (before moving) and _aim() (after moving).

## Physics layer bits. Asteroids live on WORLD, the player's side on FRIENDLY,
## hostile fighters on ENEMY. Each side's lasers only hit WORLD and the other side.
const LAYER_WORLD := 1
const LAYER_FRIENDLY := 2
const LAYER_ENEMY := 4
## Enlarged enemy hit zones (Hurtbox areas). Only friendly bolts and the
## player's crosshair ray look for it; nothing collides with it.
const LAYER_HURTBOX := 8

@export_group("Speed")
## Speed with no throttle input. The player's ship overrides these in ship.tscn.
@export var cruise_speed := 45.0
@export var min_speed := 20.0
## Top speed in normal flight (the player's full throttle).
@export var max_speed := 75.0
## Absolute top speed: no target speed goes above it. The AI sprints at it
## (enemies evading or closing in, wingmen catching up with the formation).
@export var boost_speed := 130.0
@export var acceleration := 35.0
## Acceleration while above max_speed or heading there.
@export var boost_acceleration := 90.0

@export_group("Handling")
@export var pitch_rate := 1.5
@export var yaw_rate := 1.1
@export var roll_rate := 2.6
## How quickly turn rates follow the stick. Higher = snappier.
@export var turn_response := 5.0
@export var auto_level_strength := 1.2
## Visual bank angle (radians) at full yaw.
@export var bank_angle := 0.7

@export_group("Weapons")
@export var laser_scene: PackedScene = preload("res://weapons/laser.tscn")
## Bolt speed relative to the ship.
@export var laser_speed := 350.0
@export var fire_interval := 0.11
## How far ahead the guns aim when there's nothing to aim at.
@export var aim_distance := 220.0
## Random inaccuracy per shot, in degrees.
@export var spread_deg := 0.0
## Twin lasers: each bolt flies from its muzzle parallel to the line from the
## ship's centre through the aim point, so the pair never crosses or bends and
## lands within one muzzle offset of the crosshair at any range. Off = each
## bolt flies straight from its muzzle to the aim point, meeting there.
@export var parallel_fire := false
## Size of the flash at the muzzle on each shot (0 = none). It takes the colour
## of the bolt's impacts.
@export var muzzle_flash_size := 0.0

@export_group("Sounds")
## Played where the ship blows up (one-shot, see SoundFX).
@export var explosion_sound: AudioStream
## Engine pitch change per m/s above or below cruise speed (1.0 at cruise).
## Measured from cruise rather than across min..boost speed, so ships with a
## single fixed speed just keep a steady pitch.
@export var engine_pitch_per_speed := 0.008

@export_group("Engine glow")
## Engine glow strength change per m/s above or below cruise speed (1.0 at
## cruise), like engine_pitch_per_speed. Scales the Model/Glow mesh's brightness
## and size and the Model/EngineLight's energy, when the scene has them.
@export var engine_glow_per_speed := 0.015
## Weakest and strongest the glow gets, as multiples of its look at cruise.
@export var engine_glow_range := Vector2(0.5, 2.3)

@export_group("Comms")
## Who this pilot is on the comms (name, colour, portrait, beep pitch). Empty
## for pilots who never talk.
@export var speaker: CommsSpeaker

var speed := 0.0
## Point the guns aim at (see parallel_fire).
var aim_point := Vector3.ZERO

var _rates := Vector3.ZERO
var _fire_cooldown := 0.0
var _next_cannon := 0

@onready var _model: Node3D = $Model
@onready var _cannons: Array[Node3D] = [$Model/MuzzleL, $Model/MuzzleR]
## Optional sound players in the ship's scene: a shot sound, and a looping
## engine sound whose pitch follows speed.
@onready var _fire_sound := get_node_or_null("FireSound") as AudioStreamPlayer3D
@onready var _engine_sound := get_node_or_null("EngineSound") as AudioStreamPlayer3D
## Optional engine glow (an emissive mesh) and light, scaled with speed.
@onready var _engine_glow := get_node_or_null("Model/Glow") as MeshInstance3D
@onready var _engine_light := get_node_or_null("Model/EngineLight") as OmniLight3D
## This ship's copy of the glow material, and the glow's look at cruise speed.
var _glow_material: StandardMaterial3D
var _glow_energy := 1.0
var _glow_scale := Vector3.ONE
var _light_energy := 1.0


## Radius of a target or obstacle, for anything that exposes a `radius`.
static func radius_of(node: Node) -> float:
	var r = node.get("radius")
	return r if r is float else 5.0


## Whether the crosshair turns red over a shootable `node`: its
## `highlight_on_crosshair` property, or true if it doesn't have one.
static func highlights_crosshair(node: Object) -> bool:
	return node.get("highlight_on_crosshair") != false


## Whether the Attack order can pick `node`: its `attack_target` property, or
## true if it doesn't have one.
static func is_attack_target(node: Object) -> bool:
	return node.get("attack_target") != false


func _ready() -> void:
	speed = cruise_speed
	aim_point = global_position - global_basis.z * aim_distance
	if _engine_glow:
		# The material is shared by every ship of this scene: copy it so each
		# ship's glow follows its own speed.
		var shared := _engine_glow.mesh.surface_get_material(0) as StandardMaterial3D
		if shared:
			_glow_material = shared.duplicate()
			_engine_glow.material_override = _glow_material
			_glow_energy = _glow_material.emission_energy_multiplier
		_glow_scale = _engine_glow.scale
	if _engine_light:
		_light_energy = _engine_light.light_energy


func _physics_process(delta: float) -> void:
	_think(delta)
	_update_rotation(delta)
	_update_speed(delta)
	velocity = -global_basis.z * speed + _velocity_offset()
	move_and_slide()
	_handle_collisions()
	_update_model(delta)
	_update_engine_sound()
	_update_engine_glow()
	_aim(delta)
	_update_weapons(delta)


#region Pilot interface

## Runs before the ship moves each physics frame.
func _think(_delta: float) -> void:
	pass


## Runs after the ship moves; set aim_point here.
func _aim(_delta: float) -> void:
	aim_point = global_position - global_basis.z * aim_distance


## x = yaw right, y = pitch down (screen-style), each -1..1.
func _get_stick() -> Vector2:
	return Vector2.ZERO


## Positive rolls left. Return 0 to let the ship auto-level.
func _get_roll() -> float:
	return 0.0


func _get_target_speed() -> float:
	return cruise_speed


func _wants_fire() -> bool:
	return false


## Extra velocity on top of flying forward at `speed`. Normally none: ships
## only move where they point. Wingmen use it to hold formation tightly.
func _velocity_offset() -> Vector3:
	return Vector3.ZERO


## The "up" direction the ship rolls towards when not rolling manually.
func _get_level_up() -> Vector3:
	return Vector3.UP


## Pitch rate (rad/s) at full stick right now. Normally pitch_rate; wingmen
## raise it for the somersault when rejoining.
func _get_pitch_rate() -> float:
	return pitch_rate


## How fast speed changes towards the target speed (m/s²). `fast`: above or
## heading above max_speed.
func _get_acceleration(fast: bool) -> float:
	return boost_acceleration if fast else acceleration

#endregion


func _update_rotation(delta: float) -> void:
	var s := _get_stick().limit_length(1.0)
	var roll_input := _get_roll()
	var target_rates := Vector3(-s.y * _get_pitch_rate(), -s.x * yaw_rate, roll_input * roll_rate)
	_rates = _rates.lerp(target_rates, 1.0 - exp(-turn_response * delta))

	var roll := _rates.z
	if is_zero_approx(roll_input):
		# basis.x · up is how far the right wing points "up"; roll against it.
		roll -= global_basis.x.dot(_get_level_up()) * auto_level_strength

	var turn := Basis.from_euler(Vector3(_rates.x, _rates.y, roll) * delta)
	global_basis = (global_basis * turn).orthonormalized()


func _update_speed(delta: float) -> void:
	var target_speed := clampf(_get_target_speed(), min_speed, boost_speed)
	var fast := speed > max_speed or target_speed > max_speed
	var accel := _get_acceleration(fast)
	speed = move_toward(speed, target_speed, accel * delta)


func _handle_collisions() -> void:
	if get_slide_collision_count() == 0:
		return
	var collision := get_slide_collision(0)
	speed = minf(speed, min_speed)
	global_position += collision.get_normal() * 0.5


func _update_model(delta: float) -> void:
	var t := 1.0 - exp(-6.0 * delta)
	var rates := _visual_turn_rates()
	_model.rotation.z = lerpf(_model.rotation.z, clampf(rates.y / yaw_rate, -1.0, 1.0) * bank_angle, t)
	_model.rotation.x = lerpf(_model.rotation.x, clampf(rates.x / pitch_rate, -1.0, 1.0) * 0.12, t)


## Pitch and yaw rates (rad/s) the model banks and tilts with. The stick-driven
## rates by default; override when something else turns the ship.
func _visual_turn_rates() -> Vector2:
	return Vector2(_rates.x, _rates.y)


func _update_engine_sound() -> void:
	if _engine_sound:
		_engine_sound.pitch_scale = clampf(1.0 + (speed - cruise_speed) * engine_pitch_per_speed, 0.5, 2.0)


## Brighter, longer engine glow the faster we go; dimmer when slowing down.
func _update_engine_glow() -> void:
	var strength := clampf(1.0 + (speed - cruise_speed) * engine_glow_per_speed,
		engine_glow_range.x, engine_glow_range.y)
	if _glow_material:
		_glow_material.emission_energy_multiplier = _glow_energy * strength
	if _engine_glow:
		# Size, not just brightness: bloom washes a bright glow out to white
		# whatever its energy, and from the chase camera only its width and
		# height show.
		_engine_glow.scale = _glow_scale * strength
	if _engine_light:
		_engine_light.light_energy = _light_energy * strength


func _update_weapons(delta: float) -> void:
	_fire_cooldown -= delta
	if _wants_fire() and _fire_cooldown <= 0.0:
		_fire_cooldown = fire_interval
		_fire()


func _fire() -> void:
	if _fire_sound:
		# A little pitch variation so rapid fire doesn't sound mechanical.
		_fire_sound.pitch_scale = randf_range(0.95, 1.05)
		_fire_sound.play()
	var muzzle := _cannons[_next_cannon]
	_next_cannon = (_next_cannon + 1) % _cannons.size()
	var laser := laser_scene.instantiate() as Laser
	get_tree().current_scene.add_child(laser)
	var origin := muzzle.global_position
	var direction := origin.direction_to(aim_point)
	if parallel_fire:
		# Aim along the line from between the muzzles, not from this muzzle.
		var center := (_cannons[0].global_position + _cannons[1].global_position) * 0.5
		direction = center.direction_to(aim_point)
	laser.launch(origin, _apply_spread(direction), laser_speed + speed, self)
	if muzzle_flash_size > 0.0:
		MuzzleFlash.spawn(muzzle, laser.impact_color, muzzle_flash_size)


## Random inaccuracy of up to spread_deg around `direction`.
func _apply_spread(direction: Vector3) -> Vector3:
	if spread_deg <= 0.0:
		return direction
	var axis := direction.cross(Vector3(randf() - 0.5, randf() - 0.5, randf() - 0.5)).normalized()
	if axis.is_normalized():
		direction = direction.rotated(axis, deg_to_rad(randf() * spread_deg))
	return direction
