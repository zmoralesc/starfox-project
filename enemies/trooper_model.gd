class_name TrooperModel
extends Node3D
## On the imported Shogun Trooper model (models/trooper/, built by
## source/build_trooper.py): cel-shades it, paints its markings and lights in
## this type's colours (like FighterModel), and animates it for Trooper.
##
## Animation: an AnimationTree built here from the model's clips.
## - A state machine for the body (hover_idle, dash, brake, land, landed_idle,
##   take_off), cross-fading between them; the one-off clips run on into
##   hover_idle or landed_idle.
## - fire_windup on the upper body (UPPER_BONES), blended in while aiming and
##   held at its last frame through the burst; fire_recoil fired per shot.
## - Two LookAtModifier3D on the skeleton, faded in while aiming: the chest
##   turns towards the aim point (aim_yaw_limit_deg), then the cannon forearm
##   pitches onto it (aim_pitch_limit_deg), so it can fire in any direction its
##   arm can reach.
## The heel thrusters are thruster_glow.gdshader flames on the HeelL / HeelR
## markers, their strength set by Trooper (set_thrust()).

## Painted plates: shoulder plate edges, skirt, shield emblem, cheek plates
## (material Trooper_Accent).
@export var accent_color := Color(0.5, 0.09, 0.08)
## Visor, cannon ring, backpack vents, heel nozzles (material Trooper_Lights).
@export var light_color := Color(1.0, 0.62, 0.2)
@export var light_energy := 4.0

@export_group("Animation")
## Cross-fade between body clips (s).
@export var crossfade := 0.15
## How fast aiming (the wind-up pose and the look-at) fades in and out (1/s).
@export var aim_fade_speed := 8.0
## How far the chest turns towards the aim point, and how far the cannon arm
## pitches, either way (degrees). Keep within Trooper's aim limits.
@export var aim_yaw_limit_deg := 70.0
@export var aim_pitch_limit_deg := 85.0
## Seconds the look-at takes to follow a moving aim point.
@export var aim_follow_time := 0.12

@export_group("Thrusters")
@export var flame_color := Color(1.0, 0.55, 0.2)
## Flame length at strength 1 (m), and the nozzle glow's radius.
@export var flame_length := 2.2
@export var flame_radius := 0.32

const ACCENT_MATERIAL := "Trooper_Accent"
const LIGHTS_MATERIAL := "Trooper_Lights"
const BASE_CLIPS: Array[StringName] = [&"hover_idle", &"dash", &"brake", &"land", &"landed_idle", &"take_off"]
## One-off clips and the clip each runs on into.
const RUNS_INTO := {&"dash": &"hover_idle", &"brake": &"hover_idle", &"take_off": &"hover_idle", &"land": &"landed_idle"}
const LOOPS: Array[StringName] = [&"hover_idle", &"landed_idle"]
## Bones the upper-body clips (fire_windup, fire_recoil) drive.
const UPPER_BONES: Array[String] = ["chest", "head", "rangefinder", "shoulder.L", "shoulder.R",
	"upper_arm.L", "upper_arm.R", "forearm.L", "forearm.R"]

static var _painted := {}
static var _flame_material: ShaderMaterial

var _tree: AnimationTree
var _playback: AnimationNodeStateMachinePlayback
var _skeleton: Skeleton3D
var _aim_target: Marker3D
var _looks: Array[LookAtModifier3D] = []
var _aim := 0.0
var _aiming := false
var _base := &"hover_idle"
var _flames: Array[MeshInstance3D] = []
var _sputtering := false
var _sputter_left := 0.0


func _ready() -> void:
	ToonMaterial.convert_tree(self)
	_paint(self, _accent_material(), _lights_material())
	_skeleton = find_child("Skeleton3D", true, false) as Skeleton3D
	var player := find_child("AnimationPlayer", true, false) as AnimationPlayer
	if player:
		_build_tree(player)
	if _skeleton:
		_build_looks()
	for heel in [marker(&"HeelL"), marker(&"HeelR")]:
		if heel:
			_flames.append(_make_flame(heel))


## A marker exported with the model (MuzzleTipL, BackpackPoint, HeelL...), or null.
func marker(marker_name: StringName) -> Node3D:
	return find_child(marker_name, true, false) as Node3D


## Plays body clip `clip` (one of BASE_CLIPS), cross-fading from the current
## one; `restart` plays it from the start even if it's already playing.
func play(clip: StringName, restart := false) -> void:
	if _playback == null or (clip == _base and not restart):
		return
	_base = clip
	if restart:
		_playback.start(clip, true)
	else:
		_playback.travel(clip)


## Aiming at `point`: on, the wind-up pose blends in from its start and the
## chest and cannon turn towards it; off, they fade back.
func aim(point: Vector3, on: bool) -> void:
	if _aim_target:
		_aim_target.global_position = point
	if on and not _aiming and _tree:
		_tree.set("parameters/seek/seek_request", 0.0)
	_aiming = on


func recoil() -> void:
	if _tree:
		_tree.set("parameters/recoil/request", AnimationNodeOneShot.ONE_SHOT_REQUEST_FIRE)


## Heel flame strength: 0 = off, 1 = hovering, more for dashes.
func set_thrust(strength: float) -> void:
	for flame in _flames:
		flame.visible = strength > 0.02
		flame.set_instance_shader_parameter("strength", strength)
		flame.scale = Vector3.ONE * clampf(strength, 0.3, 2.0)


## Called by Wreck (propagate_call) when the dead trooper starts flying out of
## control: its heel thrusters sputter from then on.
func on_wrecked() -> void:
	_sputtering = true
	_aiming = false


func _process(delta: float) -> void:
	if _sputtering:
		_sputter_left -= delta
		if _sputter_left <= 0.0:
			_sputter_left = randf_range(0.03, 0.12)
			set_thrust(0.0 if randf() < 0.2 else randf_range(0.6, 2.4))
	_aim = move_toward(_aim, 1.0 if _aiming else 0.0, aim_fade_speed * delta)
	if _tree:
		_tree.set("parameters/aim/blend_amount", _aim)
	for look in _looks:
		look.influence = _aim


func _build_tree(player: AnimationPlayer) -> void:
	for clip in LOOPS:
		if player.has_animation(clip):
			player.get_animation(clip).loop_mode = Animation.LOOP_LINEAR
	var machine := AnimationNodeStateMachine.new()
	for clip in BASE_CLIPS:
		var node := AnimationNodeAnimation.new()
		node.animation = clip
		machine.add_node(clip, node)
	var start := AnimationNodeStateMachineTransition.new()
	start.advance_mode = AnimationNodeStateMachineTransition.ADVANCE_MODE_AUTO
	machine.add_transition(&"Start", &"hover_idle", start)
	for from in BASE_CLIPS:
		for to in BASE_CLIPS:
			if from == to:
				continue
			var transition := AnimationNodeStateMachineTransition.new()
			transition.xfade_time = crossfade
			if RUNS_INTO.get(from) == to:
				transition.switch_mode = AnimationNodeStateMachineTransition.SWITCH_MODE_AT_END
				transition.advance_mode = AnimationNodeStateMachineTransition.ADVANCE_MODE_AUTO
			machine.add_transition(from, to, transition)

	var blend_tree := AnimationNodeBlendTree.new()
	blend_tree.add_node(&"base", machine)
	var windup := AnimationNodeAnimation.new()
	windup.animation = &"fire_windup"
	blend_tree.add_node(&"windup", windup)
	blend_tree.add_node(&"seek", AnimationNodeTimeSeek.new())
	blend_tree.connect_node(&"seek", 0, &"windup")
	var aim_blend := AnimationNodeBlend2.new()
	_filter_upper(aim_blend, player)
	blend_tree.add_node(&"aim", aim_blend)
	blend_tree.connect_node(&"aim", 0, &"base")
	blend_tree.connect_node(&"aim", 1, &"seek")
	var recoil_clip := AnimationNodeAnimation.new()
	recoil_clip.animation = &"fire_recoil"
	blend_tree.add_node(&"recoil_clip", recoil_clip)
	var shot := AnimationNodeOneShot.new()
	shot.fadein_time = 0.02
	shot.fadeout_time = 0.06
	_filter_upper(shot, player)
	blend_tree.add_node(&"recoil", shot)
	blend_tree.connect_node(&"recoil", 0, &"aim")
	blend_tree.connect_node(&"recoil", 1, &"recoil_clip")
	blend_tree.connect_node(&"output", 0, &"recoil")

	_tree = AnimationTree.new()
	_tree.name = "AnimationTree"
	add_child(_tree)
	_tree.anim_player = _tree.get_path_to(player)
	_tree.tree_root = blend_tree
	_tree.active = true
	_playback = _tree.get("parameters/base/playback")


## Limits `node` to the upper-body bones' tracks.
func _filter_upper(node: AnimationNode, player: AnimationPlayer) -> void:
	node.filter_enabled = true
	var skeleton_path := String(player.get_node(player.root_node).get_path_to(_skeleton)) if _skeleton else "Rig/Skeleton3D"
	for bone in UPPER_BONES:
		node.set_filter_path(NodePath("%s:%s" % [skeleton_path, bone]), true)


func _build_looks() -> void:
	_aim_target = Marker3D.new()
	_aim_target.name = "AimTarget"
	_aim_target.top_level = true
	add_child(_aim_target)
	# Chest first (yaw), then the cannon forearm (pitch), so the arm aims from
	# where the turned chest has put it.
	_looks.append(_add_look(&"chest", SkeletonModifier3D.BONE_AXIS_MINUS_Z, Vector3.AXIS_Y, aim_yaw_limit_deg))
	_looks.append(_add_look(&"forearm.R", SkeletonModifier3D.BONE_AXIS_PLUS_Y, Vector3.AXIS_X, aim_pitch_limit_deg))


func _add_look(bone: StringName, forward: SkeletonModifier3D.BoneAxis, axis: Vector3.Axis, limit_deg: float) -> LookAtModifier3D:
	var look := LookAtModifier3D.new()
	look.name = "Look_" + String(bone).replace(".", "_")
	_skeleton.add_child(look)
	look.bone_name = bone
	look.forward_axis = forward
	look.primary_rotation_axis = axis
	look.use_secondary_rotation = false
	look.use_angle_limitation = true
	look.symmetry_limitation = true
	look.primary_limit_angle = deg_to_rad(limit_deg)
	look.primary_damp_threshold = 1.0
	look.duration = aim_follow_time
	look.target_node = look.get_path_to(_aim_target)
	look.influence = 0.0
	return look


func _make_flame(heel: Node3D) -> MeshInstance3D:
	if _flame_material == null:
		_flame_material = ShaderMaterial.new()
		_flame_material.shader = preload("res://effects/thruster_glow.gdshader")
		_flame_material.set_shader_parameter("glow_color", flame_color)
		_flame_material.set_shader_parameter("plume_length", flame_length)
	var mesh := SphereMesh.new()
	mesh.radius = flame_radius
	mesh.height = flame_radius * 2.0
	mesh.radial_segments = 12
	mesh.rings = 6
	mesh.material = _flame_material
	var flame := MeshInstance3D.new()
	flame.name = "Flame"
	flame.mesh = mesh
	flame.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	flame.extra_cull_margin = flame_length * 2.0
	heel.add_child(flame)
	# The plume runs along the flame's +Z; the marker's -Z points out of the nozzle.
	flame.transform = Transform3D(Basis(Vector3.UP, PI), Vector3.ZERO)
	return flame


func _paint(node: Node, accent: Material, lights: Material) -> void:
	for child in node.get_children():
		if child is MeshInstance3D:
			var mesh := (child as MeshInstance3D).mesh
			for surface in mesh.get_surface_count():
				var source := mesh.surface_get_material(surface)
				if source == null:
					continue
				if source.resource_name == ACCENT_MATERIAL:
					(child as MeshInstance3D).set_surface_override_material(surface, accent)
				elif source.resource_name == LIGHTS_MATERIAL:
					(child as MeshInstance3D).set_surface_override_material(surface, lights)
		_paint(child, accent, lights)


func _accent_material() -> ShaderMaterial:
	var key := "accent %s" % accent_color
	if not _painted.has(key):
		var material := ShaderMaterial.new()
		material.shader = ToonMaterial.SHADER
		material.set_shader_parameter("albedo", accent_color)
		_painted[key] = material
	return _painted[key]


func _lights_material() -> ShaderMaterial:
	var key := "lights %s %s" % [light_color, light_energy]
	if not _painted.has(key):
		var material := ShaderMaterial.new()
		material.shader = ToonMaterial.SHADER
		material.set_shader_parameter("albedo", light_color)
		material.set_shader_parameter("emission", light_color)
		material.set_shader_parameter("emission_energy", light_energy)
		_painted[key] = material
	return _painted[key]
