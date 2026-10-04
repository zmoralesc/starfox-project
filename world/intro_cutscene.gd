class_name IntroCutscene
extends Node
## Level intro: the formation flies into the zone past a static camera, then
## the camera swoops to its chase position and control is handed over.
##
## Move the IntroStart and IntroCameraSpot markers in the scene to reframe it.
## Fire / Enter / gamepad A skips it.

signal finished

enum Phase { IDLE, FLYBY, CAMERA_FLY, DONE }

@export var ship: Ship
@export var camera: ChaseCamera
@export var hud: CanvasLayer
## Where the formation starts. It flies along this marker's -Z axis.
@export var start_point: Marker3D
## Where the static camera sits during the fly-by.
@export var camera_spot: Marker3D
@export var intro_speed := 80.0
## The camera leaves its spot once the player is this far past it.
@export var handover_distance := 60.0
## Seconds for the camera to fly to its chase position.
@export var camera_fly_time := 1.2
## Narrower field of view for the fly-by shot.
@export var intro_fov := 50.0
@export var hud_fade_time := 0.6

var _phase := Phase.IDLE
var _fly_from := Transform3D.IDENTITY
var _fly_t := 0.0


func _ready() -> void:
	# Run after the ships have moved this physics frame.
	process_physics_priority = 20


func is_playing() -> bool:
	return _phase == Phase.FLYBY or _phase == Phase.CAMERA_FLY


func play() -> void:
	var start := start_point.global_transform
	ship.global_transform = start
	ship.speed = intro_speed
	ship.controls_enabled = false
	ship.autopilot_speed = intro_speed
	for wingman: Wingman in get_tree().get_nodes_in_group("wingmen"):
		wingman.global_transform = Transform3D(start.basis, start * wingman.slot_offset)
		wingman.speed = intro_speed

	hud.hide()
	camera.set_physics_process(false)
	camera.global_position = camera_spot.global_position
	camera.fov = intro_fov
	camera.look_at(ship.global_position)
	_phase = Phase.FLYBY


func skip() -> void:
	if is_playing():
		_finish()


func _unhandled_input(event: InputEvent) -> void:
	if is_playing() and (event.is_action_pressed("ui_accept") or event.is_action_pressed("fire")):
		skip()
		get_viewport().set_input_as_handled()


func _physics_process(delta: float) -> void:
	match _phase:
		Phase.FLYBY:
			# Camera stays put and pans to keep the fighters in frame.
			camera.look_at(ship.global_position)
			var past_camera := (ship.global_position - camera_spot.global_position).dot(-ship.global_basis.z)
			if past_camera > handover_distance:
				_fly_from = camera.global_transform
				_fly_t = 0.0
				_phase = Phase.CAMERA_FLY
		Phase.CAMERA_FLY:
			_fly_t = minf(_fly_t + delta / camera_fly_time, 1.0)
			var weight := smoothstep(0.0, 1.0, _fly_t)
			camera.global_transform = _fly_from.interpolate_with(camera.chase_transform(), weight)
			camera.fov = lerpf(intro_fov, camera.base_fov, weight)
			if _fly_t >= 1.0:
				_finish()


func _finish() -> void:
	_phase = Phase.DONE
	camera.fov = camera.base_fov
	camera.snap()
	camera.set_physics_process(true)
	ship.controls_enabled = true

	hud.show()
	for child in hud.get_children():
		if child is CanvasItem:
			child.modulate.a = 0.0
			create_tween().tween_property(child, "modulate:a", 1.0, hud_fade_time)
	finished.emit()
